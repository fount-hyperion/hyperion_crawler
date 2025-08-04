#!/usr/bin/env python3
"""
ETL 데이터 검증 스크립트
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from kardia.db import get_postgres_db
from sqlalchemy import text


async def verify_data():
    """ETL 데이터 검증"""
    # PostgreSQL 연결
    postgres = await get_postgres_db()
    async with postgres.session() as session:
            # 1. AssetMaster 통계
            print("=== AssetMaster 통계 ===")
            result = await session.execute(text("""
                SELECT 
                    COUNT(*) as total_assets,
                    COUNT(CASE WHEN is_active = true THEN 1 END) as active_assets,
                    COUNT(CASE WHEN created_by = 'SYS_WORKFLOW' THEN 1 END) as workflow_created
                FROM finance.asset_master
                WHERE asset_type = 'STOCK' AND asset_subtype = 'DOMESTIC'
            """))
            stats = result.fetchone()
            print(f"전체 국내 주식: {stats.total_assets}")
            print(f"활성 주식: {stats.active_assets}")
            print(f"워크플로우로 생성된 주식: {stats.workflow_created}")
            
            # 2. 오늘 추가된 자산
            print("\n=== 오늘 추가된 자산 (최대 5개) ===")
            result = await session.execute(text("""
                SELECT uuid, symbol, name_kr, market, created_at
                FROM finance.asset_master
                WHERE DATE(created_at) = CURRENT_DATE
                  AND created_by = 'SYS_WORKFLOW'
                ORDER BY created_at DESC
                LIMIT 5
            """))
            new_assets = result.fetchall()
            for asset in new_assets:
                print(f"{asset.symbol} - {asset.name_kr} ({asset.market}) - {asset.created_at}")
            
            # 3. KrsDailyPrices 통계
            print("\n=== KrsDailyPrices 통계 ===")
            result = await session.execute(text("""
                SELECT 
                    COUNT(*) as total_prices,
                    COUNT(DISTINCT asset_uuid) as unique_assets,
                    MIN(date) as oldest_date,
                    MAX(date) as latest_date
                FROM finance.krs_daily_prices
                WHERE created_by = 'SYS_WORKFLOW'
            """))
            price_stats = result.fetchone()
            print(f"전체 가격 레코드: {price_stats.total_prices}")
            print(f"고유 자산 수: {price_stats.unique_assets}")
            print(f"가장 오래된 날짜: {price_stats.oldest_date}")
            print(f"가장 최근 날짜: {price_stats.latest_date}")
            
            # 4. 오늘 수집된 가격 샘플
            print("\n=== 오늘 수집된 가격 데이터 샘플 (최대 5개) ===")
            result = await session.execute(text("""
                SELECT 
                    am.symbol,
                    am.name_kr,
                    kp.close,
                    kp.volume,
                    kp.date
                FROM finance.krs_daily_prices kp
                JOIN finance.asset_master am ON kp.asset_uuid = am.uuid
                WHERE DATE(kp.created_at) = CURRENT_DATE
                ORDER BY kp.created_at DESC
                LIMIT 5
            """))
            prices = result.fetchall()
            for price in prices:
                print(f"{price.symbol} ({price.name_kr}) - 종가: {price.close:,}원, 거래량: {price.volume:,}")


if __name__ == "__main__":
    asyncio.run(verify_data())