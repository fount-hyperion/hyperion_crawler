"""
테스트 환경 설정
"""
import sys
import os
from pathlib import Path
import pytest
import asyncio
from typing import AsyncGenerator
from unittest.mock import MagicMock, AsyncMock, patch

# API 경로를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 테스트용 환경변수 설정
os.environ["TESTING"] = "true"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """이벤트 루프 fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """테스트용 인메모리 데이터베이스"""
    from api.src.db.postgres import Base
    
    # 인메모리 SQLite 사용
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )
    
    # 테이블 생성
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 세션 생성
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
def mock_settings():
    """테스트용 설정"""
    from api.src.core.config import Settings
    
    settings = MagicMock(spec=Settings)
    settings.APP_NAME = "Hyperion Crawler Test"
    settings.VERSION = "1.0.0"
    settings.API_V1_STR = "/api/v1"
    settings.DEBUG = False
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    settings.POSTGRES_HOST = "localhost"
    settings.POSTGRES_PORT = "5432"
    settings.POSTGRES_USER = "test"
    settings.POSTGRES_PASSWORD = "test"
    settings.POSTGRES_DB = "test"
    settings.NEO4J_URI = "bolt://localhost:7687"
    settings.NEO4J_USER = "neo4j"
    settings.NEO4J_PASSWORD = "test"
    settings.REDIS_HOST = "localhost"
    settings.REDIS_PORT = 6379
    settings.SECRET_KEY = "test-secret-key"
    
    return settings


@pytest.fixture
def mock_secret_manager():
    """테스트용 Secret Manager Mock"""
    secret_manager = MagicMock()
    secret_manager.get_json_secret = MagicMock(side_effect=lambda key: {
        "postgres-config": {
            "host": "localhost",
            "port": "5432",
            "username": "test",
            "password": "test",
            "database": "test"
        },
        "neo4j-config": {
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "test"
        }
    }.get(key, {}))
    
    secret_manager.get_secret = MagicMock(side_effect=lambda key: {
        "jwt-secret-key": "test-secret-key",
        "redis-password": "test-redis-password"
    }.get(key, ""))
    
    secret_manager.current_project = "test-project"
    
    return secret_manager


@pytest.fixture
def mock_pykrx():
    """pykrx 모듈 Mock"""
    import pandas as pd
    from datetime import datetime
    
    # Mock 데이터
    ohlcv_data = pd.DataFrame({
        '시가': [71000, 2500],
        '고가': [72000, 2600],
        '저가': [70000, 2400],
        '종가': [71500, 2550],
        '거래량': [15000000, 5000000],
        '등락률': [1.5, -2.0]
    }, index=['005930', '000660'])
    
    cap_data = pd.DataFrame({
        '시가총액': [450000000000000, 180000000000000],
        '상장주식수': [5969782550, 70592343]
    }, index=['005930', '000660'])
    
    # Mock 함수들
    mock_stock = MagicMock()
    mock_stock.get_market_ohlcv_by_ticker = MagicMock(return_value=ohlcv_data)
    mock_stock.get_market_cap_by_ticker = MagicMock(return_value=cap_data)
    mock_stock.get_market_ticker_list = MagicMock(side_effect=lambda date, market: {
        "KOSPI": ["005930", "000660"],
        "KOSDAQ": [],
        "KONEX": []
    }.get(market, []))
    mock_stock.get_market_ticker_name = MagicMock(side_effect=lambda ticker: {
        "005930": "삼성전자",
        "000660": "SK하이닉스"
    }.get(ticker, ticker))
    
    return mock_stock


@pytest.fixture
def test_client(mock_settings, mock_secret_manager):
    """FastAPI 테스트 클라이언트"""
    # 설정과 Secret Manager를 Mock으로 교체
    import api.src.core.config as config_module
    config_module.settings = mock_settings
    config_module.secret_manager = mock_secret_manager
    
    # Kardia DB Mock
    with patch('kardia.db.fastapi.lifespan') as mock_lifespan:
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def test_lifespan(app):
            yield
        
        mock_lifespan.return_value = test_lifespan
        
        from api.src.main import app
        return TestClient(app)