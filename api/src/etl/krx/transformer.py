"""
KRX (Korea Exchange) 데이터 변환기
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, date
import redis
import json
import asyncio

from ..base import MarketDataTransformer
from kardia.unique_key import UniqueKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from ...models import AssetMaster
from pykrx.website import krx

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
    
    async def transform(self, data: List[Dict[str, Any]], rules: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        KRX 원시 데이터를 데이터베이스 형식으로 변환
        
        Args:
            data: KRX에서 추출한 원시 데이터
            rules: 변환 규칙
        """
        rules = rules or {}
        transformed_data = []
        
        # 스키마 검증
        if not await self.validate_schema(data):
            raise ValueError("Invalid data schema for KRX transformation")
        
        # 1. 당일 동기화 여부 확인
        today = datetime.now().strftime('%Y%m%d')
        sync_done = await self._check_daily_sync_done(today)
        
        if not sync_done:
            # 당일 첫 실행: AssetMaster 동기화 (신규/삭제 확인)
            await self._sync_asset_master(data)
            await self._mark_daily_sync_done(today)
        else:
            # 당일 두 번째 이후 실행: 캐시에서 로드만
            await self._load_cache_from_redis(today)
        
        for item in data:
            try:
                # 캐시에서 UUID 가져오기 (이미 로드됨)
                uuid = await self._get_or_create_asset_uuid(
                    symbol=item['ticker'],
                    name_kr=item['name_kr'],
                    market=item['market']
                )
                
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
                
                # 추가 계산 (규칙에 따라)
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
                    transformed_data.append(transformed)
                else:
                    self.logger.warning(f"Invalid transformed data for {item['ticker']} on {item['trade_date']}")
                    
            except Exception as e:
                self.logger.error(f"Failed to transform data for {item.get('ticker', 'UNKNOWN')}: {str(e)}")
                continue
        
        self.logger.info(f"Transformed {len(transformed_data)} out of {len(data)} records")
        return transformed_data
    
    async def _sync_asset_master(self, data: List[Dict[str, Any]]):
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
    
    async def _load_cache_from_redis(self, date_key: str) -> bool:
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
    
    async def _save_cache_to_redis(self, date_key: str):
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
    
    async def _check_daily_sync_done(self, date_key: str) -> bool:
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
    
    async def _mark_daily_sync_done(self, date_key: str):
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
    
    async def validate_schema(self, data: List[Dict[str, Any]]) -> bool:
        """KRX 데이터 스키마 검증"""
        if not data:
            return False
        
        required_fields = ['ticker', 'name_kr', 'market', 'trade_date', 'ohlcv']
        required_ohlcv_fields = ['close']
        
        # 첫 번째 레코드로 스키마 검증
        sample = data[0]
        
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
    
    async def _get_or_create_asset_uuid(self, symbol: str, name_kr: str, market: str) -> str:
        """AssetMaster UUID 조회 (캐시에서만)"""
        # 캐시 확인 (이미 _bulk_load_asset_cache에서 로드됨)
        cache_key = f"{symbol}_{market}"
        if cache_key in self._asset_cache:
            return self._asset_cache[cache_key]
        
        # 캐시에 없으면 에러 (bulk load에서 처리했어야 함)
        raise ValueError(f"Asset not found in cache: {symbol} ({market})")
    
    async def _get_isin_for_ticker(self, ticker: str) -> Optional[str]:
        """개별 종목의 ISIN 조회"""
        try:
            loop = asyncio.get_event_loop()
            isin = await loop.run_in_executor(None, krx.get_stock_ticker_isin, ticker)
            return isin
        except Exception as e:
            self.logger.debug(f"Failed to get ISIN for {ticker}: {e}")
            return None
    
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