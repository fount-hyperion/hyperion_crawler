"""
Hyperion Crawler API
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from kardia.db.fastapi import lifespan, setup_database

from .core.config import settings
from .routers import etl_router

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    """헬스 체크"""
    return {
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running"
    }


