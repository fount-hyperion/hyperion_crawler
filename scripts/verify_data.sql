-- KRX ETL 워크플로우 데이터 검증 쿼리

-- 1. AssetMaster 테이블 확인
SELECT 
    COUNT(*) as total_assets,
    COUNT(CASE WHEN is_active = true THEN 1 END) as active_assets,
    COUNT(CASE WHEN created_by = 'SYS_WORKFLOW' THEN 1 END) as workflow_created
FROM finance.asset_master
WHERE asset_type = 'STOCK' AND asset_subtype = 'DOMESTIC';

-- 2. 오늘 추가된 자산 확인
SELECT uuid, symbol, name_kr, market, created_at
FROM finance.asset_master
WHERE DATE(created_at) = CURRENT_DATE
  AND created_by = 'SYS_WORKFLOW'
ORDER BY created_at DESC
LIMIT 10;

-- 3. KrsDailyPrices 테이블 확인
SELECT 
    COUNT(*) as total_prices,
    COUNT(DISTINCT asset_uuid) as unique_assets,
    MIN(date) as oldest_date,
    MAX(date) as latest_date
FROM finance.krs_daily_prices
WHERE created_by = 'SYS_WORKFLOW';

-- 4. 오늘 수집된 가격 데이터 샘플
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
LIMIT 10;