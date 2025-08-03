"""
KRX (Korea Exchange) 데이터 변환기
"""
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from ..base import MarketDataTransformer
from kardia.unique_key import UniqueKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from ...models import AssetMaster

logger = logging.getLogger(__name__)


class KRXTransformer(MarketDataTransformer):
    """KRX 데이터 변환기"""
    
    def __init__(self, db_session: AsyncSession, config: Optional[Dict[str, Any]] = None):
        super().__init__("krx", config)
        self.db = db_session
        self.unique_key = UniqueKey()
        self._asset_cache = {}  # UUID 캐싱
    
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
        
        for item in data:
            try:
                # AssetMaster UUID 조회/생성
                uuid = await self._get_or_create_asset_uuid(
                    symbol=item['ticker'],
                    name_kr=item['name_kr'],
                    market=item['market']
                )
                
                # 기본 변환
                transformed = {
                    'uuid': uuid,
                    'trade_date': item['trade_date'],
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
        """AssetMaster UUID 조회 또는 생성"""
        # 캐시 확인
        cache_key = f"{symbol}_{market}"
        if cache_key in self._asset_cache:
            return self._asset_cache[cache_key]
        
        # 데이터베이스 조회
        result = await self.db.execute(
            select(AssetMaster).where(
                and_(
                    AssetMaster.symbol == symbol,
                    AssetMaster.country_code == "KR"
                )
            )
        )
        asset = result.scalar_one_or_none()
        
        if asset:
            self._asset_cache[cache_key] = asset.uuid
            return asset.uuid
        
        # 새 자산 생성
        uuid = self.unique_key.generate("KRS")
        asset = AssetMaster(
            uuid=uuid,
            asset_type="STOCK",
            asset_subtype="DOMESTIC",
            symbol=symbol,
            name_kr=name_kr,
            name_en=None,  # 추후 업데이트
            market=market,
            country_code="KR",
            currency="KRW",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.db.add(asset)
        await self.db.flush()
        
        self._asset_cache[cache_key] = uuid
        self.logger.info(f"Created new asset: {symbol} ({name_kr}) with UUID: {uuid}")
        
        return uuid
    
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