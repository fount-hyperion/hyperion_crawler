"""
KRX (Korea Exchange) 데이터 추출기
"""
from typing import Dict, Any, List, Optional
import asyncio
import logging
from pykrx import stock
from pykrx.website import krx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..base import MarketDataExtractor
from ...models import AssetMaster

logger = logging.getLogger(__name__)


class KRXExtractor(MarketDataExtractor):
    """KRX 데이터 추출기"""
    
    def __init__(self, db_session: Optional[AsyncSession] = None):
        super().__init__("krx")
        self.db = db_session
    
    async def extract(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        KRX에서 주식 데이터 추출
        1. DB에서 KRS UUID와 symbol만 조회
        2. KRX 전체 데이터와 비교하여 신규 종목만 추가 추출
        """
        # 파라미터 검증
        validated_params = await self.validate_params(params)
        
        # 거래일 설정
        target_date = self.get_trade_date(validated_params)
        date_str = target_date.strftime("%Y%m%d")
        
        self.logger.info(f"Extracting KRX data for {date_str}")
        
        # 비동기로 pykrx 호출
        loop = asyncio.get_event_loop()
        
        # 1. DB에서 기존 AssetMaster 정보 가져오기 (KRS UUID, symbol만)
        existing_assets = {}
        if self.db:
            result = await self.db.execute(
                select(AssetMaster.uuid, AssetMaster.symbol).where(
                    AssetMaster.uuid.like('KRS-%')
                )
            )
            for row in result:
                existing_assets[row.symbol] = row.uuid
        
        try:
            # 시장별로 데이터 추출
            markets = validated_params.get("markets", ["KOSPI", "KOSDAQ"])
            all_data = []  # 전체 데이터
            new_assets = []  # 신규 종목만
            
            for market in markets:
                try:
                    # 각 시장별 OHLCV 데이터
                    df_ohlcv = await loop.run_in_executor(None, stock.get_market_ohlcv_by_ticker, date_str, market)
                    
                    # 각 시장별 시가총액 데이터  
                    df_cap = await loop.run_in_executor(None, stock.get_market_cap_by_ticker, date_str, market)
                    
                    # 전체 데이터 처리
                    for ticker in df_ohlcv.index:
                        ohlcv_row = df_ohlcv.loc[ticker]
                        cap_row = df_cap.loc[ticker] if ticker in df_cap.index else None
                        
                        data_item = {
                            'ticker': ticker,
                            'market': market,
                            'trade_date': target_date,
                            'uuid': existing_assets.get(ticker),  # 기존 UUID 매핑
                            'ohlcv': {
                                'open': ohlcv_row['시가'],
                                'high': ohlcv_row['고가'],
                                'low': ohlcv_row['저가'],
                                'close': ohlcv_row['종가'],
                                'volume': ohlcv_row['거래량'],
                                'change_rate': ohlcv_row['등락률']
                            },
                            'market_cap': cap_row['시가총액'] if cap_row is not None else None,
                            'shares': cap_row['상장주식수'] if cap_row is not None else None
                        }
                        
                        all_data.append(data_item)
                        
                        # 신규 종목인 경우 추가 정보 수집
                        if ticker not in existing_assets:
                            try:
                                name_kr = await loop.run_in_executor(None, stock.get_market_ticker_name, ticker)
                                isin = await loop.run_in_executor(None, krx.get_stock_ticker_isin, ticker)
                            except:
                                name_kr = ticker
                                isin = None
                                
                            new_asset = data_item.copy()
                            new_asset['name_kr'] = name_kr
                            new_asset['isin'] = isin
                            new_asset['is_new'] = True
                            new_assets.append(new_asset)
                    
                    # DataFrame 즉시 삭제하여 메모리 확보
                    del df_ohlcv
                    del df_cap
                    
                except Exception as e:
                    self.logger.warning(f"Failed to get {market} data: {e}")
            
            # 응답 생성
            return self.create_response(
                task_id=self.create_task_id(date_str),
                data=all_data,
                metadata={
                    "trade_date": date_str,
                    "total_tickers": len(all_data),
                    "new_tickers": len(new_assets),
                    "markets": markets,
                    "new_assets": new_assets  # 신규 종목 정보
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