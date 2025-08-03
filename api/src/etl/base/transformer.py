"""
Base Transformer - 모든 데이터 변환기의 기본 클래스
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BaseTransformer(ABC):
    """
    모든 데이터 변환기의 기본 추상 클래스
    각 데이터 소스는 이를 상속해서 구현
    """
    
    def __init__(self, source_name: str, config: Optional[Dict[str, Any]] = None):
        self.source_name = source_name
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{source_name}")
    
    @abstractmethod
    async def transform(self, data: List[Dict[str, Any]], rules: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        데이터 변환 메서드
        
        Args:
            data: 변환할 원시 데이터
            rules: 변환 규칙 (옵션)
        
        Returns:
            변환된 데이터
        """
        pass
    
    @abstractmethod
    async def validate_schema(self, data: List[Dict[str, Any]]) -> bool:
        """
        변환 전 스키마 검증
        
        Args:
            data: 검증할 데이터
        
        Returns:
            검증 성공 여부
        """
        pass
    
    @abstractmethod
    def get_target_schema(self) -> Dict[str, Any]:
        """
        타겟 스키마 정의 반환
        
        Returns:
            타겟 스키마 정보
        """
        pass
    
    # 공통 유틸리티 메서드들
    def normalize_date(self, date_value: Any, format: str = "%Y-%m-%d") -> Optional[str]:
        """날짜 정규화"""
        if not date_value:
            return None
        
        if isinstance(date_value, str):
            try:
                parsed = datetime.strptime(date_value, format)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                self.logger.warning(f"Failed to parse date: {date_value}")
                return None
        elif hasattr(date_value, 'strftime'):
            return date_value.strftime("%Y-%m-%d")
        
        return None
    
    def clean_numeric(self, value: Any) -> Optional[float]:
        """숫자 값 정제"""
        if value is None or value == '':
            return None
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # 쉼표, 통화 기호 등 제거
            cleaned = value.replace(',', '').replace('$', '').replace('₩', '').strip()
            try:
                return float(cleaned)
            except ValueError:
                self.logger.warning(f"Failed to parse numeric value: {value}")
                return None
        
        return None
    
    def map_fields(self, source_data: Dict[str, Any], field_mapping: Dict[str, str]) -> Dict[str, Any]:
        """필드 매핑"""
        result = {}
        for target_field, source_field in field_mapping.items():
            if '.' in source_field:
                # 중첩된 필드 처리
                value = self.get_nested_value(source_data, source_field)
            else:
                value = source_data.get(source_field)
            
            if value is not None:
                result[target_field] = value
        
        return result
    
    def get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """중첩된 딕셔너리에서 값 추출"""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def apply_default_values(self, data: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """기본값 적용"""
        for field, default_value in defaults.items():
            if field not in data or data[field] is None:
                data[field] = default_value
        
        return data
    
    def filter_fields(self, data: Dict[str, Any], allowed_fields: List[str]) -> Dict[str, Any]:
        """허용된 필드만 필터링"""
        return {k: v for k, v in data.items() if k in allowed_fields}


class MarketDataTransformer(BaseTransformer):
    """
    시장 데이터 변환기의 기본 클래스
    KRX, Investing.com 등이 상속
    """
    
    def calculate_change_amount(self, close_price: float, change_rate: float) -> Optional[float]:
        """변화량 계산"""
        if close_price and change_rate is not None:
            return round(close_price * change_rate / 100, 2)
        return None
    
    def calculate_trading_value(self, price: float, volume: int) -> Optional[float]:
        """거래대금 계산"""
        if price and volume:
            return round(price * volume, 2)
        return None
    
    def normalize_market_cap(self, value: Any, unit: str = "KRW") -> Optional[float]:
        """시가총액 정규화"""
        if not value:
            return None
        
        numeric_value = self.clean_numeric(value)
        if not numeric_value:
            return None
        
        # 단위 변환 (억원 -> 원)
        if unit == "KRW" and numeric_value < 1e8:
            return numeric_value * 1e8
        
        return numeric_value


class FilingDataTransformer(BaseTransformer):
    """
    공시 데이터 변환기의 기본 클래스
    DART, SEC 등이 상속
    """
    
    def extract_filing_metadata(self, filing: Dict[str, Any]) -> Dict[str, Any]:
        """공시 메타데이터 추출"""
        return {
            'filing_date': self.normalize_date(filing.get('filing_date')),
            'document_type': filing.get('document_type'),
            'company_name': filing.get('company_name'),
            'filing_url': filing.get('filing_url')
        }
    
    def parse_xbrl_data(self, xbrl_content: str) -> Dict[str, Any]:
        """XBRL 데이터 파싱 (구현 필요)"""
        # TODO: XBRL 파싱 로직
        return {}
    
    def normalize_company_identifier(self, identifier: str, identifier_type: str) -> str:
        """회사 식별자 정규화"""
        if identifier_type == "ticker":
            return identifier.upper()
        elif identifier_type == "cik":
            return identifier.zfill(10)  # CIK는 10자리로 패딩
        elif identifier_type == "corp_code":
            return identifier.zfill(8)   # DART 기업코드는 8자리
        
        return identifier


class AnalyticsDataTransformer(BaseTransformer):
    """
    분석 데이터 변환기의 기본 클래스
    TipRanks 등이 상속
    """
    
    def normalize_rating(self, rating: str) -> Optional[int]:
        """평가 등급 정규화 (1-5 scale)"""
        rating_map = {
            'strong_buy': 5, 'buy': 4, 'hold': 3, 'sell': 2, 'strong_sell': 1,
            'outperform': 4, 'market_perform': 3, 'underperform': 2,
            'overweight': 4, 'neutral': 3, 'underweight': 2
        }
        
        normalized = rating.lower().replace(' ', '_').replace('-', '_')
        return rating_map.get(normalized)
    
    def calculate_consensus(self, ratings: List[int]) -> Dict[str, Any]:
        """컨센서스 계산"""
        if not ratings:
            return {'consensus': None, 'count': 0}
        
        avg_rating = sum(ratings) / len(ratings)
        return {
            'consensus': round(avg_rating, 2),
            'count': len(ratings),
            'distribution': {
                'strong_buy': ratings.count(5),
                'buy': ratings.count(4),
                'hold': ratings.count(3),
                'sell': ratings.count(2),
                'strong_sell': ratings.count(1)
            }
        }
    
    def normalize_target_price(self, price: Any, currency: str = "USD") -> Optional[Dict[str, Any]]:
        """목표 주가 정규화"""
        numeric_price = self.clean_numeric(price)
        if not numeric_price:
            return None
        
        return {
            'target_price': numeric_price,
            'currency': currency
        }