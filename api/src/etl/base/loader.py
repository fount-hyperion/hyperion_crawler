"""
Base Loader - 모든 데이터 적재기의 기본 클래스
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import logging
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)


class LoadMode(Enum):
    """적재 모드"""
    INSERT = "insert"      # 단순 삽입
    UPDATE = "update"      # 업데이트만
    UPSERT = "upsert"      # 있으면 업데이트, 없으면 삽입
    REPLACE = "replace"    # 기존 데이터 삭제 후 삽입
    APPEND = "append"      # 추가만 (중복 허용)


class LoadResult:
    """적재 결과"""
    def __init__(self):
        self.loaded = 0
        self.updated = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
    
    def add_success(self, count: int = 1, updated: bool = False):
        if updated:
            self.updated += count
        else:
            self.loaded += count
    
    def add_failure(self, error: str, record: Optional[Dict[str, Any]] = None):
        self.failed += 1
        self.errors.append({
            'error': error,
            'record': record,
            'timestamp': datetime.now()
        })
    
    def add_skipped(self, count: int = 1):
        self.skipped += count
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'loaded': self.loaded,
            'updated': self.updated,
            'failed': self.failed,
            'skipped': self.skipped,
            'total_processed': self.loaded + self.updated + self.failed + self.skipped,
            'success_rate': (self.loaded + self.updated) / max(1, self.loaded + self.updated + self.failed),
            'errors': self.errors[:10]  # 처음 10개 에러만
        }


class BaseLoader(ABC):
    """
    모든 데이터 적재기의 기본 추상 클래스
    """
    
    def __init__(self, source_name: str, db_session: AsyncSession, config: Optional[Dict[str, Any]] = None):
        self.source_name = source_name
        self.db = db_session
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{source_name}")
        self.batch_size = self.config.get('batch_size', 1000)
    
    @abstractmethod
    async def load(
        self,
        data: List[Dict[str, Any]],
        target: str,
        mode: LoadMode = LoadMode.UPSERT
    ) -> LoadResult:
        """
        데이터 적재 메서드
        
        Args:
            data: 적재할 데이터
            target: 타겟 테이블/컬렉션
            mode: 적재 모드
        
        Returns:
            적재 결과
        """
        pass
    
    @abstractmethod
    async def validate_before_load(self, data: List[Dict[str, Any]], target: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        적재 전 데이터 검증
        
        Args:
            data: 검증할 데이터
            target: 타겟 정보
        
        Returns:
            (유효한 데이터, 무효한 데이터)
        """
        pass
    
    @abstractmethod
    def get_conflict_columns(self, target: str) -> List[str]:
        """
        UPSERT 시 충돌 판단 컬럼 반환
        
        Args:
            target: 타겟 테이블
        
        Returns:
            충돌 판단 컬럼 리스트
        """
        pass
    
    # 공통 유틸리티 메서드들
    async def batch_load(
        self,
        data: List[Dict[str, Any]],
        load_func,
        batch_size: Optional[int] = None
    ) -> LoadResult:
        """배치 단위로 데이터 적재"""
        batch_size = batch_size or self.batch_size
        result = LoadResult()
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            try:
                batch_result = await load_func(batch)
                result.loaded += batch_result.get('loaded', 0)
                result.updated += batch_result.get('updated', 0)
            except Exception as e:
                self.logger.error(f"Batch load failed: {str(e)}")
                result.add_failure(str(e))
        
        return result
    
    async def upsert_postgres(
        self,
        table_model,
        data: List[Dict[str, Any]],
        conflict_columns: List[str],
        update_columns: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """PostgreSQL UPSERT 헬퍼"""
        loaded = 0
        updated = 0
        
        for item in data:
            stmt = insert(table_model).values(**item)
            
            if update_columns:
                # 지정된 컬럼만 업데이트
                update_dict = {col: stmt.excluded[col] for col in update_columns if col in item}
            else:
                # 모든 컬럼 업데이트 (conflict 컬럼 제외)
                update_dict = {
                    col: stmt.excluded[col] 
                    for col in item.keys() 
                    if col not in conflict_columns
                }
            
            # updated_at 추가
            update_dict['updated_at'] = datetime.now()
            
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_=update_dict
            )
            
            result = await self.db.execute(stmt)
            
            # PostgreSQL의 경우 정확한 insert/update 구분이 어려움
            # 간단히 처리
            if result.rowcount:
                loaded += 1
        
        await self.db.commit()
        
        return {'loaded': loaded, 'updated': updated}
    
    async def check_duplicates(
        self,
        data: List[Dict[str, Any]],
        key_fields: List[str]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """중복 데이터 체크"""
        unique_data = []
        duplicate_data = []
        seen_keys = set()
        
        for item in data:
            key = tuple(item.get(field) for field in key_fields)
            if key in seen_keys:
                duplicate_data.append(item)
            else:
                seen_keys.add(key)
                unique_data.append(item)
        
        if duplicate_data:
            self.logger.warning(f"Found {len(duplicate_data)} duplicate records")
        
        return unique_data, duplicate_data
    
    def add_metadata(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """메타데이터 추가"""
        timestamp = datetime.now()
        for item in data:
            if 'created_at' not in item:
                item['created_at'] = timestamp
            item['updated_at'] = timestamp
            item['source'] = self.source_name
        
        return data


class MarketDataLoader(BaseLoader):
    """
    시장 데이터 적재기의 기본 클래스
    """
    
    async def handle_market_holidays(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """휴장일 처리"""
        # 휴장일 데이터는 제외하거나 특별 처리
        valid_data = []
        for item in data:
            if item.get('volume', 0) > 0:  # 거래량이 있는 경우만
                valid_data.append(item)
            else:
                self.logger.debug(f"Skipping holiday data for {item.get('trade_date')}")
        
        return valid_data
    
    async def update_latest_prices(self, data: List[Dict[str, Any]]):
        """최신 가격 테이블 업데이트"""
        # 별도의 latest_prices 테이블이 있다면 업데이트
        pass


class FilingDataLoader(BaseLoader):
    """
    공시 데이터 적재기의 기본 클래스
    """
    
    async def store_filing_content(self, filing_id: str, content: str, content_type: str = "html"):
        """공시 내용 저장 (별도 스토리지)"""
        # S3, GCS 등에 저장하는 로직
        pass
    
    async def update_filing_index(self, filing_data: Dict[str, Any]):
        """공시 인덱스 업데이트"""
        # 검색을 위한 인덱스 업데이트
        pass


class AnalyticsDataLoader(BaseLoader):
    """
    분석 데이터 적재기의 기본 클래스
    """
    
    async def aggregate_ratings(self, symbol: str, ratings: List[Dict[str, Any]]):
        """평가 데이터 집계"""
        # 심볼별 평가 집계 로직
        pass
    
    async def update_consensus(self, symbol: str):
        """컨센서스 업데이트"""
        # 최신 컨센서스 계산 및 업데이트
        pass