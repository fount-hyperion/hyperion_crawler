#!/usr/bin/env python3
"""
pykrx에서 ISIN 및 상세정보 가져오기
"""
from pykrx.website import krx
from pykrx import stock
from datetime import datetime

today = datetime.now().strftime("%Y%m%d")

print("=== get_stock_ticker_isin 테스트 ===")

# 몇 가지 종목으로 테스트
test_tickers = ["005930", "000660", "035720"]  # 삼성전자, SK하이닉스, 카카오

for ticker in test_tickers:
    try:
        # ISIN 조회
        isin = krx.get_stock_ticker_isin(ticker)
        name = stock.get_market_ticker_name(ticker)
        print(f"\n{ticker} ({name}):")
        print(f"ISIN: {isin}")
        
        # 시가총액 정보도 확인 (상장주식수 포함)
        df_cap = stock.get_market_cap_by_ticker(today)
        if ticker in df_cap.index:
            cap_info = df_cap.loc[ticker]
            print(f"상장주식수: {cap_info['상장주식수']:,}")
            
    except Exception as e:
        print(f"Error for {ticker}: {e}")

# 전종목 상세정보 조회 방법 확인
print("\n\n=== 전종목 기본정보 조회 ===")

# krx 모듈의 클래스들 확인
print("\n사용 가능한 클래스들:")
for attr in dir(krx):
    if '전종목' in attr and '기본' in attr:
        print(f"- {attr}")

# 상장종목검색 클래스 사용해보기
print("\n\n=== 상장종목검색 클래스 테스트 ===")
try:
    searcher = krx.상장종목검색()
    print(f"Methods: {[m for m in dir(searcher) if not m.startswith('_')]}")
    
    # fetch 메서드 시도
    if hasattr(searcher, 'fetch'):
        # 파라미터 확인
        import inspect
        sig = inspect.signature(searcher.fetch)
        print(f"\nfetch 메서드 시그니처: {sig}")
        
except Exception as e:
    print(f"Error: {e}")

# get_stock_major_changes 테스트
print("\n\n=== get_stock_major_changes 테스트 ===")
try:
    # 단일 종목으로 테스트
    changes = krx.get_stock_major_changes("005930")
    print(f"Type: {type(changes)}")
    if hasattr(changes, 'shape'):
        print(f"Shape: {changes.shape}")
        print(f"Columns: {list(changes.columns)}")
        print(changes.head())
except Exception as e:
    print(f"Error: {e}")