"""
KRX (Korea Exchange) 데이터 변환기
"""
from typing import Dict, Any, List, Optional, Union
import logging
from datetime import datetime, date
import redis
import json
import asyncio
import pandas as pd

from ..base import MarketDataTransformer
from kardia.unique_key import UniqueKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from ...models import AssetMaster
from pykrx.website import krx
from pykrx import stock

logger = logging.getLogger(__name__)


class KRXTransformer(MarketDataTransformer):
    """KRX 데이터 변환기"""
    
    def __init__(self, db_session: AsyncSession, redis_client: Optional[redis.Redis] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__("krx", config)
        self.db = db_session
        self.unique_key = UniqueKey()
        self._asset_cache = {}  # UUID 캐싱
        self.redis = redis_client
        self.cache_ttl = 86400  # 24시간 캐싱
    
    async def transform(self, data: Union[List[Dict[str, Any]], Dict[str, Any]], rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        KRX 원시 데이터를 데이터베이스 형식으로 변환
        - Extract에서 받은 metadata의 new_assets를 처리하여 AssetMaster 데이터 생성
        - 일일 가격 데이터를 krs_daily_prices 형식으로 변환
        """
        rules = rules or {}
        
        # Extract 단계에서 받은 데이터와 메타데이터 분리
        if isinstance(data, dict) and 'data' in data and 'metadata' in data:
            # ETL Service에서 전달하는 형식
            price_data = data['data']
            metadata = data['metadata']
            new_assets_info = metadata.get('new_assets', [])
        elif isinstance(data, list):
            # 리스트 형식으로 전달되는 경우 (레거시)
            price_data = data
            metadata = {}
            new_assets_info = []
        else:
            raise ValueError(f"Invalid data schema for KRX transformation: expected dict with 'data' and 'metadata' keys or list, got {type(data)}")
        
        # 결과 데이터 구조
        result = {
            'new_assets': [],  # AssetMaster에 추가할 신규 종목
            'price_data': []   # krs_daily_prices에 추가할 가격 데이터
        }
        
        # 1. 신규 AssetMaster 데이터 생성
        for asset_info in new_assets_info:
            # 주식 종류 추론
            stock_type = "보통주"
            name_kr = asset_info.get('name_kr', '')
            if name_kr.endswith("우"):
                stock_type = "우선주"
            elif name_kr.endswith("우B") or name_kr.endswith("2우B"):
                stock_type = "우선주B"
            
            new_asset = {
                'uuid': self.unique_key.generate("KRS", 6),  # KRS-XXXXXX
                'asset_type': "STOCK",
                'asset_subtype': "DOMESTIC",
                'symbol': asset_info['ticker'],
                'isin': asset_info.get('isin'),
                'name_kr': name_kr,
                'name_en': None,
                'market': asset_info['market'],
                'country_code': "KR",
                'currency': "KRW",
                'listing_date': await self._get_listing_date(asset_info['ticker']),
                'delisting_date': None,
                'is_active': True,
                'asset_metadata': {
                    "full_name_kr": name_kr,
                    "security_type": "주권",
                    "stock_type": stock_type,
                    "par_value": await self._get_par_value(asset_info['ticker']),
                    "shares_outstanding": str(asset_info.get('shares', 0)) if asset_info.get('shares') else None
                },
                'created_by': "SYS_WORKFLOW",
                'updated_by': "SYS_WORKFLOW"
            }
            result['new_assets'].append(new_asset)
        
        # 2. 가격 데이터 변환
        for item in price_data:
            # UUID가 없는 경우 (신규 종목) new_assets에서 찾기
            uuid = item.get('uuid')
            if not uuid:
                # 신규 종목의 UUID 매핑
                for new_asset in result['new_assets']:
                    if new_asset['symbol'] == item['ticker']:
                        uuid = new_asset['uuid']
                        break
            
            if not uuid:
                self.logger.warning(f"No UUID found for ticker {item['ticker']}")
                continue
            
            # 기본 변환
            transformed = {
                'uuid': uuid,
                'trade_date': self._parse_trade_date(item['trade_date']),
                'open_price': self.clean_numeric(item['ohlcv']['open']),
                'high_price': self.clean_numeric(item['ohlcv']['high']),
                'low_price': self.clean_numeric(item['ohlcv']['low']),
                'close_price': self.clean_numeric(item['ohlcv']['close']),
                'volume': int(item['ohlcv']['volume']) if item['ohlcv']['volume'] else 0,
                'change_rate': self.clean_numeric(item['ohlcv']['change_rate']),
                'market_cap': self.normalize_market_cap(item.get('market_cap')),
                'shares_outstanding': int(item['shares']) if item.get('shares') else None
            }
            
            # 추가 계산
            if rules.get('calculate_change_amount', True) and transformed['close_price'] and transformed['change_rate'] is not None:
                transformed['change_amount'] = self.calculate_change_amount(
                    transformed['close_price'],
                    transformed['change_rate']
                )
            else:
                transformed['change_amount'] = None
            
            if rules.get('calculate_trading_value', True) and transformed['close_price'] and transformed['volume']:
                transformed['trading_value'] = self.calculate_trading_value(
                    transformed['close_price'],
                    transformed['volume']
                )
            else:
                transformed['trading_value'] = None
            
            # 추가 메타데이터
            transformed['currency'] = 'KRW'
            transformed['data_source'] = 'KRX'
            transformed['created_by'] = 'SYS_WORKFLOW'
            transformed['updated_by'] = 'SYS_WORKFLOW'
            
            # 데이터 품질 체크
            if self._validate_transformed_data(transformed):
                result['price_data'].append(transformed)
            else:
                self.logger.warning(f"Invalid transformed data for UUID {uuid}")
        
        self.logger.info(f"Transformed {len(result['new_assets'])} new assets and {len(result['price_data'])} price records")
        return result
    
    async def _sync_asset_master_old(self, data: List[Dict[str, Any]]):
        """
        AssetMaster 동기화 - KRX 데이터와 DB를 비교하여 추가/삭제 처리
        당일 1번만 실행
        """
        # KRX에서 받은 모든 심볼
        krx_symbols = {item['ticker'] for item in data}
        krx_symbol_info = {item['ticker']: item for item in data}
        
        # DB의 모든 활성 국내 주식
        result = await self.db.execute(
            select(AssetMaster).where(
                and_(
                    AssetMaster.country_code == "KR",
                    AssetMaster.asset_type == "STOCK",
                    AssetMaster.is_active == True
                )
            )
        )
        db_assets = result.scalars().all()
        db_symbols = {asset.symbol for asset in db_assets}
        
        # 1. 신규 상장 종목 처리
        new_symbols = krx_symbols - db_symbols
        if new_symbols:
            # 신규 종목의 ISIN 정보 가져오기
            isin_map = {}
            try:
                for symbol in new_symbols:
                    isin = await self._get_isin_for_ticker(symbol)
                    if isin:
                        isin_map[symbol] = isin
            except Exception as e:
                self.logger.warning(f"Failed to get ISIN info: {e}")
            new_assets = []
            for symbol in new_symbols:
                info = krx_symbol_info[symbol]
                uuid = self.unique_key.generate("KRS", 6)  # KRS-BBBBBBC (10자리, 하이픈 포함 11자리)
                cache_key = f"{symbol}_{info['market']}"
                self._asset_cache[cache_key] = uuid
                
                # 주식 종류 추론 (종목명에서)
                stock_type = "보통주"  # 기본값
                if info['name_kr'].endswith("우"):
                    stock_type = "우선주"
                elif info['name_kr'].endswith("우B") or info['name_kr'].endswith("2우B"):
                    stock_type = "우선주B"
                
                new_assets.append(AssetMaster(
                    uuid=uuid,
                    asset_type="STOCK",
                    asset_subtype="DOMESTIC",
                    symbol=symbol,
                    isin=isin_map.get(symbol),  # 개별 조회한 ISIN
                    name_kr=info['name_kr'],
                    name_en=None,  # TODO: 영문명 가져오기
                    market=info['market'],
                    country_code="KR",
                    currency="KRW",
                    listing_date=None,  # TODO: 상장일 정보 가져오기
                    delisting_date=None,
                    is_active=True,
                    asset_metadata={
                        "full_name_kr": info['name_kr'],  # TODO: 정식 명칭 가져오기
                        "security_type": "주권",
                        "stock_type": stock_type,
                        "par_value": "500",  # TODO: 실제 액면가 정보 가져오기 (현재는 기본값)
                        "shares_outstanding": str(info.get('shares', 0)) if info.get('shares') else None
                    },
                    created_by="SYS_WORKFLOW",
                    created_at=datetime.now(),
                    updated_by="SYS_WORKFLOW",
                    updated_at=datetime.now()
                ))
            
            self.db.add_all(new_assets)
            await self.db.flush()
            await self.db.commit()
            self.logger.info(f"Added {len(new_assets)} new assets: {new_symbols}")
        
        # 2. 상장폐지 종목 처리
        delisted_symbols = db_symbols - krx_symbols
        if delisted_symbols:
            # is_active를 False로 업데이트
            for asset in db_assets:
                if asset.symbol in delisted_symbols:
                    asset.is_active = False
                    asset.updated_by = "SYS_WORKFLOW"
                    asset.updated_at = datetime.now()
            await self.db.flush()
            await self.db.commit()
            self.logger.info(f"Marked {len(delisted_symbols)} assets as inactive: {delisted_symbols}")
        
        # 3. 활성 종목들 캐싱
        for asset in db_assets:
            if asset.symbol in krx_symbols:
                cache_key = f"{asset.symbol}_{asset.market}"
                self._asset_cache[cache_key] = asset.uuid
        
        # 캐시 저장
        today = datetime.now().strftime('%Y%m%d')
        await self._save_cache_to_redis(today)
    
    async def _load_cache_from_redis_old(self, date_key: str) -> bool:
        """
        Redis에서 당일 AssetMaster 캐시 로드
        
        Returns:
            캐시 로드 성공 여부
        """
        if not self.redis:
            return False
        
        try:
            cache_key = f"krx:asset_master:{date_key}"
            cached_data = self.redis.get(cache_key)
            
            if cached_data:
                self._asset_cache = json.loads(cached_data)
                self.logger.info(f"Loaded {len(self._asset_cache)} assets from Redis cache")
                return True
        except Exception as e:
            self.logger.warning(f"Failed to load from Redis cache: {e}")
        
        return False
    
    async def _save_cache_to_redis_old(self, date_key: str):
        """
        AssetMaster 캐시를 Redis에 저장
        """
        if not self.redis:
            return
        
        try:
            cache_key = f"krx:asset_master:{date_key}"
            self.redis.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(self._asset_cache)
            )
            self.logger.info(f"Saved {len(self._asset_cache)} assets to Redis cache")
        except Exception as e:
            self.logger.warning(f"Failed to save to Redis cache: {e}")
    
    async def _check_daily_sync_done_old(self, date_key: str) -> bool:
        """
        당일 AssetMaster 동기화 완료 여부 확인
        """
        if not self.redis:
            return False
        
        try:
            sync_key = f"krx:asset_sync_done:{date_key}"
            return bool(self.redis.get(sync_key))
        except Exception as e:
            self.logger.warning(f"Failed to check sync status: {e}")
            return False
    
    async def _mark_daily_sync_done_old(self, date_key: str):
        """
        당일 AssetMaster 동기화 완료 표시
        """
        if not self.redis:
            return
        
        try:
            sync_key = f"krx:asset_sync_done:{date_key}"
            # 25시간 동안 유지 (다음날 자동 만료)
            self.redis.setex(sync_key, 90000, "1")
            self.logger.info(f"Marked daily sync as done for {date_key}")
        except Exception as e:
            self.logger.warning(f"Failed to mark sync done: {e}")
    
    async def validate_schema(self, data: Any) -> bool:
        """KRX 데이터 스키마 검증"""
        # Transform에서는 Extract 결과를 그대로 받음
        if isinstance(data, dict) and 'data' in data:
            price_data = data['data']
        elif isinstance(data, list):
            price_data = data
        else:
            return False
            
        if not price_data:
            return False
        
        required_fields = ['ticker', 'market', 'trade_date', 'ohlcv']
        required_ohlcv_fields = ['close']
        
        # 첫 번째 레코드로 스키마 검증
        sample = price_data[0]
        
        # 필수 필드 체크
        for field in required_fields:
            if field not in sample:
                self.logger.error(f"Missing required field: {field}")
                return False
        
        # OHLCV 필드 체크
        if not isinstance(sample['ohlcv'], dict):
            self.logger.error("ohlcv must be a dictionary")
            return False
        
        for field in required_ohlcv_fields:
            if field not in sample['ohlcv']:
                self.logger.error(f"Missing required OHLCV field: {field}")
                return False
        
        return True
    
    def get_target_schema(self) -> Dict[str, Any]:
        """KrsDailyPrices 테이블 스키마"""
        return {
            'table': 'krs_daily_prices',
            'columns': {
                'uuid': 'VARCHAR(36)',
                'trade_date': 'DATE',
                'open_price': 'DECIMAL(20,4)',
                'high_price': 'DECIMAL(20,4)',
                'low_price': 'DECIMAL(20,4)',
                'close_price': 'DECIMAL(20,4)',
                'volume': 'BIGINT',
                'change_rate': 'DECIMAL(10,4)',
                'change_amount': 'DECIMAL(20,4)',
                'trading_value': 'DECIMAL(30,2)',
                'market_cap': 'DECIMAL(30,2)',
                'shares_outstanding': 'BIGINT',
                'currency': 'VARCHAR(3)',
                'data_source': 'VARCHAR(20)'
            },
            'primary_key': ['uuid', 'trade_date'],
            'indexes': ['trade_date', 'uuid']
        }
    
    async def _get_or_create_asset_uuid_old(self, symbol: str, name_kr: str, market: str) -> str:
        """AssetMaster UUID 조회 (캐시에서만)"""
        # 캐시 확인 (이미 _bulk_load_asset_cache에서 로드됨)
        cache_key = f"{symbol}_{market}"
        if cache_key in self._asset_cache:
            return self._asset_cache[cache_key]
        
        # 캐시에 없으면 에러 (bulk load에서 처리했어야 함)
        raise ValueError(f"Asset not found in cache: {symbol} ({market})")
    
    async def _get_isin_for_ticker_old(self, ticker: str) -> Optional[str]:
        """개별 종목의 ISIN 조회"""
        try:
            loop = asyncio.get_event_loop()
            isin = await loop.run_in_executor(None, krx.get_stock_ticker_isin, ticker)
            return isin
        except Exception as e:
            self.logger.debug(f"Failed to get ISIN for {ticker}: {e}")
            return None
    
    async def _get_listing_date(self, ticker: str) -> Optional[date]:
        """종목의 상장일 조회"""
        try:
            loop = asyncio.get_event_loop()
            # get_stock_major_changes의 첫 번째 날짜를 상장일로 간주
            major_changes = await loop.run_in_executor(None, stock.get_stock_major_changes, ticker)
            if not major_changes.empty:
                return major_changes.index[0].date()
            return None
        except Exception as e:
            self.logger.debug(f"Failed to get listing date for {ticker}: {e}")
            return None
    
    async def _get_par_value(self, ticker: str) -> str:
        """종목의 액면가 조회"""
        try:
            loop = asyncio.get_event_loop()
            major_changes = await loop.run_in_executor(None, stock.get_stock_major_changes, ticker)
            
            if major_changes.empty:
                return "5000"  # 기본 액면가
            
            # 역순으로 확인하여 최신 액면가 찾기
            for idx in reversed(range(len(major_changes))):
                val_after = major_changes['액면변경후'].iloc[idx]
                if str(val_after) not in ['-', 'nan'] and pd.notna(val_after):
                    # 0이면 무액면주식
                    return str(val_after) if val_after != 0 else "0"
            
            # 변경 이력이 없다면 변경전 값 확인
            for idx in range(len(major_changes)):
                val_before = major_changes['액면변경전'].iloc[idx]
                if str(val_before) not in ['-', 'nan', '0'] and pd.notna(val_before):
                    return str(val_before)
            
            return "5000"  # 기본값
            
        except Exception as e:
            self.logger.debug(f"Failed to get par value for {ticker}: {e}")
            return "5000"
    
    def _parse_trade_date(self, trade_date_str: str) -> date:
        """거래일 문자열을 date 객체로 변환"""
        if isinstance(trade_date_str, date):
            return trade_date_str
        
        if isinstance(trade_date_str, datetime):
            return trade_date_str.date()
        
        if isinstance(trade_date_str, str):
            # YYYY-MM-DD 형식
            if '-' in trade_date_str:
                return datetime.strptime(trade_date_str, '%Y-%m-%d').date()
            # YYYYMMDD 형식
            elif len(trade_date_str) == 8:
                return datetime.strptime(trade_date_str, '%Y%m%d').date()
            else:
                raise ValueError(f"Unsupported date format: {trade_date_str}")
        
        raise ValueError(f"Invalid trade_date type: {type(trade_date_str)}")
    
    def _validate_transformed_data(self, data: Dict[str, Any]) -> bool:
        """변환된 데이터 유효성 검증"""
        # 필수 필드 확인
        if not data.get('uuid') or not data.get('trade_date'):
            return False
        
        # 가격 데이터 확인 (최소한 종가는 있어야 함)
        if data.get('close_price') is None:
            return False
        
        # 가격 논리 검증
        prices = ['open_price', 'high_price', 'low_price', 'close_price']
        price_values = [data.get(p) for p in prices if data.get(p) is not None]
        
        if price_values:
            # 고가가 다른 가격들보다 낮으면 안됨
            if data.get('high_price') is not None:
                if any(data['high_price'] < p for p in price_values if p is not None):
                    self.logger.warning(f"Invalid high price for {data['uuid']}")
                    return False
            
            # 저가가 다른 가격들보다 높으면 안됨
            if data.get('low_price') is not None:
                if any(data['low_price'] > p for p in price_values if p is not None):
                    self.logger.warning(f"Invalid low price for {data['uuid']}")
                    return False
        
        # 거래량/거래대금 검증
        if data.get('volume', 0) < 0:
            return False
        
        if data.get('trading_value', 0) < 0:
            return False
        
        return True