"""
Base Extractor - 모든 데이터 소스 Extractor의 기본 클래스
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import date
import logging

logger = logging.getLogger(__name__)


class BaseExtractor(ABC):
    """
    모든 데이터 추출기의 기본 추상 클래스
    각 데이터 소스(KRX, DART, SEC, TipRanks, Investing.com)는 이를 상속해서 구현
    """
    
    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logging.getLogger(f"{__name__}.{source_name}")
    
    @abstractmethod
    async def extract(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        데이터 추출 메서드
        
        Args:
            params: 추출 파라미터 (날짜, 심볼, 필터 등)
        
        Returns:
            Dict with:
                - task_id: 작업 ID
                - data: 추출된 원시 데이터 리스트
                - metadata: 메타데이터 (추출 날짜, 개수 등)
        """
        pass
    
    @abstractmethod
    async def validate_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        파라미터 검증 및 기본값 설정
        
        Args:
            params: 검증할 파라미터
        
        Returns:
            검증되고 기본값이 설정된 파라미터
        """
        pass
    
    def create_task_id(self, suffix: str = "") -> str:
        """공통 task_id 생성"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if suffix:
            return f"{self.source_name}_{suffix}_{timestamp}"
        return f"{self.source_name}_extract_{timestamp}"
    
    def create_response(
        self,
        task_id: str,
        data: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """공통 응답 형식 생성"""
        return {
            "task_id": task_id,
            "source": self.source_name,
            "data": data,
            "metadata": metadata or {},
            "count": len(data)
        }


class MarketDataExtractor(BaseExtractor):
    """
    시장 데이터 추출기의 기본 클래스
    KRX, Investing.com 등 시장 데이터를 다루는 추출기가 상속
    """
    
    def get_trade_date(self, params: Optional[Dict[str, Any]] = None) -> date:
        """거래일 계산 (주말 제외)"""
        from datetime import datetime, timedelta
        
        if params and params.get("trade_date"):
            target_date = datetime.strptime(params["trade_date"], "%Y%m%d").date()
        else:
            target_date = date.today()
            # 주말인 경우 가장 최근 평일로
            while target_date.weekday() >= 5:  # 토요일(5), 일요일(6)
                target_date -= timedelta(days=1)
        
        return target_date


class FilingDataExtractor(BaseExtractor):
    """
    공시 데이터 추출기의 기본 클래스
    DART, SEC 등 공시 데이터를 다루는 추출기가 상속
    """
    
    def get_filing_date_range(self, params: Optional[Dict[str, Any]] = None) -> tuple[date, date]:
        """공시 조회 날짜 범위 계산"""
        from datetime import datetime, timedelta
        
        if params:
            if params.get("start_date") and params.get("end_date"):
                start = datetime.strptime(params["start_date"], "%Y%m%d").date()
                end = datetime.strptime(params["end_date"], "%Y%m%d").date()
                return start, end
            elif params.get("date"):
                target = datetime.strptime(params["date"], "%Y%m%d").date()
                return target, target
        
        # 기본값: 오늘
        today = date.today()
        return today, today


class AnalyticsDataExtractor(BaseExtractor):
    """
    분석 데이터 추출기의 기본 클래스
    TipRanks 등 분석가 데이터를 다루는 추출기가 상속
    """
    
    def parse_symbols(self, params: Optional[Dict[str, Any]] = None) -> List[str]:
        """심볼 리스트 파싱"""
        if not params or not params.get("symbols"):
            return []
        
        symbols = params["symbols"]
        if isinstance(symbols, str):
            # 쉼표로 구분된 문자열
            return [s.strip().upper() for s in symbols.split(",")]
        elif isinstance(symbols, list):
            return [s.strip().upper() for s in symbols]
        
        return []