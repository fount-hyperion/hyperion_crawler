"""
Hyperion Crawler API
"""
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from .core.config import settings
from .routers import etl_router

try:
    from kardia.db.fastapi import setup_database
    from kardia.db import get_postgres_db, get_redis_db
    KARDIA_AVAILABLE = True
except ImportError:
    logger.warning("Kardia module not available")
    KARDIA_AVAILABLE = False
    
    def setup_database(app: FastAPI):
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Custom lifespan that only connects to PostgreSQL and Redis"""
    logger.info("Starting up...")
    
    if KARDIA_AVAILABLE:
        try:
            # PostgreSQL 연결
            postgres = await get_postgres_db()
            await postgres.connect()
            logger.info("PostgreSQL connected")
            
            # Redis 연결 (선택사항)
            try:
                redis = await get_redis_db()
                await redis.connect()
                logger.info("Redis connected")
            except Exception as e:
                logger.warning(f"Redis connection failed (non-critical): {e}")
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            # 연결 실패해도 서버는 시작하도록 함
    
    yield
    
    if KARDIA_AVAILABLE:
        try:
            postgres = await get_postgres_db()
            await postgres.disconnect()
            
            redis = await get_redis_db()
            await redis.disconnect()
        except Exception:
            pass
    
    logger.info("Shutting down...")

# Build test comment for Cloud Build trigger
# Build timestamp: 2025-08-03 - Global region test


# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Kardia 데이터베이스 설정
setup_database(app)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(etl_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running"
    }


@app.get("/health")
async def health():
    """헬스 체크"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION
    }


