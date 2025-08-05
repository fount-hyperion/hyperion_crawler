#!/usr/bin/env python3
"""
pykrx 전종목 기본정보 조회 테스트
"""
from pykrx import stock
from datetime import datetime
import pandas as pd

today = datetime.now().strftime("%Y%m%d")

print("=== 전종목 기본정보 조회 테스트 ===")

# stock 모듈의 함수들 중 기본정보 관련 함수 찾기
print("\n1. 기본정보 관련 함수 찾기:")
for func in dir(stock):
    if 'basic' in func.lower() or 'info' in func.lower() or 'master' in func.lower():
        print(f"- {func}")

# get_stock_major_changes 테스트
print("\n2. get_stock_major_changes 테스트:")
try:
    df = stock.get_stock_major_changes()
    print(f"Columns: {list(df.columns)}")
    print(f"Shape: {df.shape}")
    if len(df) > 0:
        print(df.head(2))
except Exception as e:
    print(f"Error: {e}")

# 전종목 조회 가능한 함수들 테스트
print("\n3. 전종목 정보 관련 함수 테스트:")

# market_ticker_list와 함께 정보 가져오기
try:
    # KOSPI 종목 하나로 테스트
    test_ticker = "005930"
    
    # get_market_sector_classifications 테스트
    print("\n- get_market_sector_classifications:")
    df_sector = stock.get_market_sector_classifications(test_ticker)
    print(f"Type: {type(df_sector)}")
    print(f"Content: {df_sector}")
    
except Exception as e:
    print(f"Error: {e}")

# DataFrame을 반환하는 함수들 확인
print("\n4. DataFrame 반환 함수들 확인:")
test_funcs = [
    "get_market_ticker_list",
    "get_market_cap_by_ticker",
    "get_market_fundamental_by_ticker",
    "get_market_trading_value_and_volume_by_ticker"
]

for func_name in test_funcs:
    try:
        func = getattr(stock, func_name)
        if "ticker" in func_name and "list" not in func_name:
            result = func(today)
            print(f"\n{func_name}:")
            print(f"- Columns: {list(result.columns) if hasattr(result, 'columns') else 'N/A'}")
            if hasattr(result, 'shape'):
                print(f"- Shape: {result.shape}")
    except Exception as e:
        print(f"\n{func_name}: Error - {e}")

# 전종목 정보를 한번에 가져올 수 있는 방법 찾기
print("\n5. 종목별 상세정보 조회:")
# 몇 개 종목으로 테스트
test_tickers = ["005930", "000660", "035720"]  # 삼성전자, SK하이닉스, 카카오

for ticker in test_tickers:
    print(f"\n=== {ticker} ===")
    name = stock.get_market_ticker_name(ticker)
    print(f"종목명: {name}")
    
    # 섹터 정보
    sector_info = stock.get_market_sector_classifications(ticker)
    print(f"섹터: {sector_info}")