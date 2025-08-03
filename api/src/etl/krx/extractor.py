"""
KRX (Korea Exchange) 데이터 추출기
"""
from typing import Dict, Any, List, Optional
import asyncio
import logging
from pykrx import stock

from ..base import MarketDataExtractor

logger = logging.getLogger(__name__)


class KRXExtractor(MarketDataExtractor):
    """KRX 데이터 추출기"""
    
    def __init__(self):
        super().__init__("krx")
    
    async def extract(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        KRX에서 주식 데이터 추출
        
        Args:
            params: 
                - trade_date: 거래일 (YYYYMMDD 형식)
                - markets: 추출할 시장 리스트 (기본: ["KOSPI", "KOSDAQ"])
        """
        # 파라미터 검증
        validated_params = await self.validate_params(params)
        
        # 거래일 설정
        target_date = self.get_trade_date(validated_params)
        date_str = target_date.strftime("%Y%m%d")
        
        self.logger.info(f"Extracting KRX data for {date_str}")
        
        # 비동기로 pykrx 호출
        loop = asyncio.get_event_loop()
        
        try:
            # OHLCV 데이터 추출
            df_ohlcv = await loop.run_in_executor(None, stock.get_market_ohlcv_by_ticker, date_str)
            
            # 시가총액 데이터 추출
            df_cap = await loop.run_in_executor(None, stock.get_market_cap_by_ticker, date_str)
            
            # 시장별 티커 정보 수집
            markets = validated_params.get("markets", ["KOSPI", "KOSDAQ"])
            market_info = {}
            name_info = {}
            
            for market in markets:
                try:
                    tickers = await loop.run_in_executor(None, stock.get_market_ticker_list, date_str, market)
                    for ticker in tickers:
                        market_info[ticker] = market
                        if ticker not in name_info:
                            name_info[ticker] = await loop.run_in_executor(None, stock.get_market_ticker_name, ticker)
                except Exception as e:
                    self.logger.warning(f"Failed to get {market} tickers: {e}")
            
            # 원시 데이터 구성
            raw_data = []
            for ticker in df_ohlcv.index:
                ohlcv_row = df_ohlcv.loc[ticker]
                cap_row = df_cap.loc[ticker] if ticker in df_cap.index else {}
                
                raw_data.append({
                    'ticker': ticker,
                    'name_kr': name_info.get(ticker, ticker),
                    'market': market_info.get(ticker, 'UNKNOWN'),
                    'trade_date': target_date,
                    'ohlcv': {
                        'open': ohlcv_row.get('시가'),
                        'high': ohlcv_row.get('고가'),
                        'low': ohlcv_row.get('저가'),
                        'close': ohlcv_row.get('종가'),
                        'volume': ohlcv_row.get('거래량'),
                        'change_rate': ohlcv_row.get('등락률')
                    },
                    'market_cap': cap_row.get('시가총액') if isinstance(cap_row, dict) else None,
                    'shares': cap_row.get('상장주식수') if isinstance(cap_row, dict) else None
                })
            
            # 응답 생성
            return self.create_response(
                task_id=self.create_task_id(date_str),
                data=raw_data,
                metadata={
                    "trade_date": date_str,
                    "total_tickers": len(raw_data),
                    "markets": list(set(market_info.values()))
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to extract KRX data: {str(e)}")
            raise
    
    async def validate_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """KRX 파라미터 검증"""
        validated = params or {}
        
        # 시장 리스트 기본값
        if "markets" not in validated:
            validated["markets"] = ["KOSPI", "KOSDAQ"]
        
        # KONEX는 선택적으로만 포함
        if isinstance(validated["markets"], str):
            validated["markets"] = [m.strip().upper() for m in validated["markets"].split(",")]
        
        # 유효한 시장만 필터링
        valid_markets = ["KOSPI", "KOSDAQ", "KONEX"]
        validated["markets"] = [m for m in validated["markets"] if m in valid_markets]
        
        return validated