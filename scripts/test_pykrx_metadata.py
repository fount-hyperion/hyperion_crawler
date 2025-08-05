#!/usr/bin/env python3
"""
pykrx에서 주식 상세 정보 가져오기 테스트
"""
from pykrx import stock
from datetime import datetime

# 테스트할 종목
test_ticker = "005930"  # 삼성전자
today = datetime.now().strftime("%Y%m%d")

print(f"=== {test_ticker} 종목 정보 조회 ===")

# 기본 정보
ticker_name = stock.get_market_ticker_name(test_ticker)
print(f"종목명: {ticker_name}")

# 종목 정보 조회 시도
try:
    # 전체 정보 조회
    from pykrx import stock
    
    # ISIN 코드
    # pykrx에는 직접적인 ISIN 조회 기능이 없음
    
    # 상장주식수는 이미 가져오고 있음
    df_cap = stock.get_market_cap_by_ticker(today)
    if test_ticker in df_cap.index:
        info = df_cap.loc[test_ticker]
        print(f"시가총액: {info['시가총액']:,}")
        print(f"상장주식수: {info['상장주식수']:,}")
        print(f"거래대금: {info['거래대금']:,}")
        print(f"거래량: {info['거래량']:,}")
        
    # 펀더멘털 정보
    df_fundamental = stock.get_market_fundamental_by_ticker(today)
    if test_ticker in df_fundamental.index:
        fund_info = df_fundamental.loc[test_ticker]
        print(f"\n=== 펀더멘털 정보 ===")
        print(f"BPS: {fund_info.get('BPS', 'N/A')}")
        print(f"PER: {fund_info.get('PER', 'N/A')}")
        print(f"PBR: {fund_info.get('PBR', 'N/A')}")
        print(f"EPS: {fund_info.get('EPS', 'N/A')}")
        print(f"DIV: {fund_info.get('DIV', 'N/A')}")
        print(f"DPS: {fund_info.get('DPS', 'N/A')}")
        
except Exception as e:
    print(f"Error: {e}")

# 사용 가능한 함수들 확인
print("\n=== pykrx.stock 사용 가능한 함수들 ===")
stock_functions = [attr for attr in dir(stock) if not attr.startswith('_')]
for func in sorted(stock_functions):
    if 'get_' in func:
        print(f"- {func}")