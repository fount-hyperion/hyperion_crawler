#!/usr/bin/env python3
"""
pykrx에서 ISIN 및 기본정보 가져오기
"""
from pykrx import stock
from pykrx.website import krx
from datetime import datetime
import pandas as pd

today = datetime.now().strftime("%Y%m%d")

print("=== pykrx.website.krx 모듈 탐색 ===")
print("\nkrx 모듈의 속성들:")
for attr in dir(krx):
    if not attr.startswith('_'):
        print(f"- {attr}")

# KRX 웹사이트 API 직접 사용 시도
print("\n=== KRX 데이터 직접 조회 시도 ===")

# get_market_sector_classifications 테스트
print("\n1. get_market_sector_classifications (전종목):")
try:
    df_kospi = stock.get_market_sector_classifications(today, "KOSPI")
    print(f"KOSPI columns: {list(df_kospi.columns)}")
    print(f"KOSPI shape: {df_kospi.shape}")
    if len(df_kospi) > 0:
        print("\nSample data:")
        print(df_kospi.head(3))
except Exception as e:
    print(f"Error: {e}")

# 특정 종목의 정보 조회 - KRX 모듈 사용
print("\n2. KRX 모듈 직접 사용:")
try:
    # StockFinder 클래스 확인
    if hasattr(krx, 'StockFinder'):
        finder = krx.StockFinder()
        print(f"StockFinder methods: {[m for m in dir(finder) if not m.startswith('_')]}")
    
    # 다른 클래스들 확인
    for cls_name in ['MKD30040', 'MKD30009', 'MKD20011']:
        if hasattr(krx, cls_name):
            print(f"\n{cls_name} class found")
            cls = getattr(krx, cls_name)
            instance = cls()
            print(f"Methods: {[m for m in dir(instance) if not m.startswith('_')]}")
            
except Exception as e:
    print(f"Error: {e}")

# 전종목 ISIN 조회 방법 찾기
print("\n3. 전종목 정보 통합 조회:")
try:
    # 시장별 종목 리스트
    kospi_tickers = stock.get_market_ticker_list(today, "KOSPI")
    print(f"KOSPI 종목 수: {len(kospi_tickers)}")
    
    # 첫 번째 종목으로 테스트
    if kospi_tickers:
        test_ticker = kospi_tickers[0]
        print(f"\n테스트 종목: {test_ticker}")
        
        # ETF ISIN 조회 함수가 있는지 확인
        if hasattr(stock, 'get_etf_isin'):
            try:
                # 일반 주식에도 작동하는지 테스트
                isin = stock.get_etf_isin(test_ticker)
                print(f"ISIN: {isin}")
            except:
                print("get_etf_isin은 ETF 전용")
                
except Exception as e:
    print(f"Error: {e}")