"""
KRX (Korea Exchange) 데이터 적재기
"""
from typing import Dict, Any, List, Optional, Tuple, Union
import logging
from datetime import datetime, date

from ..base import MarketDataLoader, LoadMode, LoadResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete
from sqlalchemy.dialects.postgresql import insert
from ...models import KrsDailyPrices, AssetMaster

logger = logging.getLogger(__name__)


class KRXLoader(MarketDataLoader):
    """KRX 데이터 적재기"""
    
    def __init__(self, db_session: AsyncSession, config: Optional[Dict[str, Any]] = None):
        super().__init__("krx", db_session, config)
        self.table_model = KrsDailyPrices
    
    async def load(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        target: str = "krs_daily_prices",
        mode: LoadMode = LoadMode.UPSERT
    ) -> LoadResult:
        """
        KRX 데이터를 데이터베이스에 적재
        Transform에서 받은 데이터:
        - new_assets: AssetMaster에 추가할 신규 종목
        - price_data: krs_daily_prices에 추가할 가격 데이터
        """
        result = LoadResult()
        
        # data가 딕셔너리인지 리스트인지 확인
        if isinstance(data, dict):
            # Transform 결과 분리
            new_assets = data.get('new_assets', [])
            price_data = data.get('price_data', [])
        else:
            # 리스트로 전달된 경우 (레거시)
            new_assets = []
            price_data = data
        
        # 1. 신규 AssetMaster 저장
        if new_assets:
            try:
                self.db.add_all([AssetMaster(**asset) for asset in new_assets])
                await self.db.flush()
                await self.db.commit()
                self.logger.info(f"Added {len(new_assets)} new assets to AssetMaster")
            except Exception as e:
                self.logger.error(f"Failed to add new assets: {str(e)}")
                await self.db.rollback()
                result.add_failure(f"AssetMaster insert failed: {str(e)}")
                return result
        
        # 2. 가격 데이터 적재
        if not price_data:
            self.logger.warning("No price data to load")
            return result
        
        # 적재 전 검증
        valid_data, invalid_data = await self.validate_before_load(price_data, target)
        
        if invalid_data:
            for item in invalid_data:
                result.add_failure("Validation failed", item)
        
        if not valid_data:
            self.logger.error("No valid data to load after validation")
            return result
        
        # 메타데이터 추가
        valid_data = self.add_metadata(valid_data)
        
        # 휴장일 데이터 처리
        valid_data = await self.handle_market_holidays(valid_data)
        
        # 적재 모드에 따른 처리
        try:
            # 디버깅을 위한 첫 번째 아이템 로그
            if valid_data:
                self.logger.info(f"First item keys: {list(valid_data[0].keys())}")
            
            if mode == LoadMode.UPSERT:
                load_result = await self._upsert_data(valid_data)
            elif mode == LoadMode.INSERT:
                load_result = await self._insert_data(valid_data)
            elif mode == LoadMode.REPLACE:
                load_result = await self._replace_data(valid_data)
            else:
                raise ValueError(f"Unsupported load mode: {mode}")
            
            result.loaded = load_result.get('loaded', 0)
            result.updated = load_result.get('updated', 0)
            
            # 최신 가격 업데이트 (선택적)
            if self.config.get('update_latest_prices', True):
                await self._update_latest_prices(valid_data)
            
            self.logger.info(f"Load completed: {result.to_dict()}")
            
        except Exception as e:
            self.logger.error(f"Load failed: {str(e)}", exc_info=True)
            result.add_failure(str(e))
        
        return result
    
    async def validate_before_load(
        self,
        data: List[Dict[str, Any]],
        target: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """적재 전 데이터 검증 - 최소한의 형변환만 수행"""
        valid_data = []
        invalid_data = []
        
        # 중복 체크
        unique_data, duplicates = await self.check_duplicates(
            data,
            key_fields=['uuid', 'trade_date']
        )
        
        # 각 레코드 검증
        for item in unique_data:
            if await self._validate_record(item):
                valid_data.append(item)
            else:
                invalid_data.append(item)
        
        # 중복 데이터는 invalid로 처리
        invalid_data.extend(duplicates)
        
        self.logger.info(f"Validation result: {len(valid_data)} valid, {len(invalid_data)} invalid")
        
        return valid_data, invalid_data
    
    def get_conflict_columns(self, target: str) -> List[str]:
        """UPSERT 시 충돌 판단 컬럼"""
        if target == "krs_daily_prices":
            return ['uuid', 'trade_date']
        else:
            raise ValueError(f"Unknown target table: {target}")
    
    async def _upsert_data(self, data: List[Dict[str, Any]]) -> Dict[str, int]:
        """UPSERT 모드로 데이터 적재"""
        # 업데이트할 컬럼 목록 (충돌 시 업데이트할 필드)
        # update_columns을 None으로 설정하면 데이터에 있는 모든 필드가 업데이트됨
        update_columns = None
        
        return await self.upsert_postgres(
            self.table_model,
            data,
            conflict_columns=['uuid', 'trade_date'],
            update_columns=update_columns
        )
    
    async def _insert_data(self, data: List[Dict[str, Any]]) -> Dict[str, int]:
        """INSERT 모드로 데이터 적재"""
        loaded = 0
        
        # 배치 단위로 삽입
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            
            try:
                # bulk insert
                await self.db.execute(
                    insert(self.table_model),
                    batch
                )
                await self.db.commit()
                loaded += len(batch)
                
            except Exception as e:
                self.logger.error(f"Batch insert failed: {str(e)}")
                await self.db.rollback()
                raise
        
        return {'loaded': loaded, 'updated': 0}
    
    async def _replace_data(self, data: List[Dict[str, Any]]) -> Dict[str, int]:
        """REPLACE 모드로 데이터 적재 (기존 데이터 삭제 후 삽입)"""
        # 거래일 기준으로 기존 데이터 삭제
        trade_dates = list(set(item['trade_date'] for item in data))
        
        for trade_date in trade_dates:
            await self.db.execute(
                delete(self.table_model).where(
                    self.table_model.trade_date == trade_date
                )
            )
        
        # 새 데이터 삽입
        return await self._insert_data(data)
    
    async def _validate_record(self, record: Dict[str, Any]) -> bool:
        """개별 레코드 검증"""
        # 필수 필드 확인
        required_fields = ['uuid', 'trade_date', 'close_price']
        for field in required_fields:
            if field not in record or record[field] is None:
                self.logger.warning(f"Missing required field: {field}")
                return False
        
        # UUID 형식 검증
        uuid_str = record.get('uuid', '')
        if not uuid_str or not isinstance(uuid_str, str):
            self.logger.warning(f"Invalid UUID format: {uuid_str}")
            return False
        
        # KRS UUID 형식 검증 (KRS-XXXXXX 형식)
        if not uuid_str.startswith('KRS-') or len(uuid_str) != 11:
            self.logger.warning(f"Invalid KRS UUID format: {uuid_str}")
            return False
        
        # 날짜 유효성 - 문자열이면 date로 변환
        trade_date = record['trade_date']
        if isinstance(trade_date, str):
            try:
                # YYYY-MM-DD 형식
                if '-' in trade_date:
                    record['trade_date'] = datetime.strptime(trade_date, '%Y-%m-%d').date()
                # YYYYMMDD 형식
                elif len(trade_date) == 8:
                    record['trade_date'] = datetime.strptime(trade_date, '%Y%m%d').date()
                else:
                    self.logger.warning(f"Invalid trade_date format: {trade_date}")
                    return False
            except ValueError:
                self.logger.warning(f"Invalid trade_date value: {trade_date}")
                return False
        elif not isinstance(trade_date, (datetime, date)):
            self.logger.warning(f"Invalid trade_date type: {type(trade_date)}")
            return False
        
        # 가격 데이터 유효성
        price_fields = ['open_price', 'high_price', 'low_price', 'close_price']
        prices = {k: record.get(k) for k in price_fields if record.get(k) is not None}
        
        if prices:
            # 모든 가격은 0 이상이어야 함
            if any(p < 0 for p in prices.values()):
                self.logger.warning("Negative price detected")
                return False
            
            # 고가는 다른 가격보다 낮을 수 없음
            if 'high_price' in prices:
                if any(prices['high_price'] < p for k, p in prices.items() if k != 'high_price'):
                    self.logger.warning("High price is lower than other prices")
                    return False
            
            # 저가는 다른 가격보다 높을 수 없음
            if 'low_price' in prices:
                if any(prices['low_price'] > p for k, p in prices.items() if k != 'low_price'):
                    self.logger.warning("Low price is higher than other prices")
                    return False
        
        return True
    
    async def _update_latest_prices(self, data: List[Dict[str, Any]]):
        """최신 가격 정보 업데이트"""
        # 가장 최근 거래일 데이터만 필터링
        if not data:
            return
        
        latest_date = max(item['trade_date'] for item in data)
        latest_data = [item for item in data if item['trade_date'] == latest_date]
        
        # TODO: latest_prices 테이블이 있다면 업데이트
        # 현재는 로깅만
        self.logger.info(f"Updated latest prices for {len(latest_data)} assets on {latest_date}")
    
    def add_metadata(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """메타데이터 추가 - KrsDailyPrices에 맞게 오버라이드"""
        # KrsDailyPrices 테이블에는 created_by, updated_by, source 필드가 없음
        # created_at, updated_at은 DB 서버 타임스탬프 사용
        return data