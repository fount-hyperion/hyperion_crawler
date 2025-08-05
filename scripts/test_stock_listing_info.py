#!/usr/bin/env python3
"""
상장종목검색으로 전종목 기본정보 가져오기
"""
from pykrx.website import krx
from pykrx import stock
from datetime import datetime

print("=== 상장종목검색 전종목 조회 ===")

try:
    # 상장종목검색 클래스 사용
    searcher = krx.상장종목검색()
    
    # 전체 시장 조회
    df_all = searcher.fetch(mktsel='ALL')
    print(f"전체 종목 수: {len(df_all)}")
    print(f"컬럼: {list(df_all.columns)}")
    print("\n샘플 데이터:")
    print(df_all.head())
    
    # KOSPI만 조회
    print("\n\n=== KOSPI 종목만 조회 ===")
    df_kospi = searcher.fetch(mktsel='STK')  # STK가 KOSPI일 가능성
    print(f"KOSPI 종목 수: {len(df_kospi)}")
    
    # 특정 종목 검색
    print("\n\n=== 특정 종목 검색 (삼성전자) ===")
    df_samsung = searcher.fetch(searchText='삼성전자')
    print(f"검색 결과 수: {len(df_samsung)}")
    if len(df_samsung) > 0:
        print(df_samsung)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# get_stock_ticekr_market 테스트 (오타가 있는 함수명인듯)
print("\n\n=== get_stock_ticekr_market 테스트 ===")
try:
    result = krx.get_stock_ticekr_market("005930")
    print(f"005930 시장: {result}")
except Exception as e:
    print(f"Error: {e}")

# 기타 전종목 정보 함수들
print("\n\n=== 기타 전종목 정보 함수 테스트 ===")

# get_market_ticker_and_name 테스트
try:
    if hasattr(krx, 'get_market_ticker_and_name'):
        today = datetime.now().strftime("%Y%m%d")
        df = krx.get_market_ticker_and_name(today, "KOSPI")
        print(f"\nget_market_ticker_and_name 결과:")
        print(f"Shape: {df.shape}")
        print(df.head())
except Exception as e:
    print(f"get_market_ticker_and_name error: {e}")