"""
ETL 전용 엔드포인트
"""
from typing import Optional, Dict, Any, List
from datetime import date
import logging

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from kardia.db import PostgresDB, get_postgres_db

from ..services.etl_service import ETLService, get_etl_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/etl", tags=["etl"])


class ExtractRequest(BaseModel):
    """Extract 요청 모델"""
    source: str = Field(..., description="데이터 소스 (krx, dart, sec 등)")
    params: Dict[str, Any] = Field(default_factory=dict, description="추출 파라미터")


class ExtractResponse(BaseModel):
    """Extract 응답 모델"""
    task_id: str
    status: str
    items_extracted: int
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class TransformRequest(BaseModel):
    """Transform 요청 모델"""
    task_id: str = Field(..., description="Extract 작업 ID")
    data: List[Dict[str, Any]] = Field(..., description="변환할 데이터")
    rules: Dict[str, Any] = Field(default_factory=dict, description="변환 규칙")


class TransformResponse(BaseModel):
    """Transform 응답 모델"""
    task_id: str
    status: str
    items_transformed: int
    data: List[Dict[str, Any]]


class LoadRequest(BaseModel):
    """Load 요청 모델"""
    task_id: str = Field(..., description="Transform 작업 ID")
    target: str = Field(..., description="적재 대상 테이블")
    data: List[Dict[str, Any]] = Field(..., description="적재할 데이터")
    mode: str = Field(default="upsert", description="적재 모드 (insert, update, upsert)")


class LoadResponse(BaseModel):
    """Load 응답 모델"""
    task_id: str
    status: str
    items_loaded: int
    items_failed: int


@router.post("/extract/{source}", response_model=ExtractResponse)
async def extract_data(
    source: str,
    params: Optional[Dict[str, Any]] = None,
    etl_service: ETLService = Depends(get_etl_service)
):
    """
    E - Extract: 데이터 소스에서 데이터 추출
    """
    try:
        # 소스별 추출 실행
        result = await etl_service.extract_data(source, params)
        
        return ExtractResponse(
            task_id=result["task_id"],
            status="success",
            items_extracted=len(result["data"]),
            data=result["data"],
            metadata=result["metadata"]
        )
        
    except Exception as e:
        logger.error(f"Extract failed for {source}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Extract failed: {str(e)}"
        )


@router.post("/transform/{source}", response_model=TransformResponse)
async def transform_data(
    source: str,
    request: TransformRequest,
    etl_service: ETLService = Depends(get_etl_service)
):
    """
    T - Transform: 추출된 데이터 변환
    """
    try:
        # 데이터 변환 실행
        result = await etl_service.transform_data(
            source=source,
            task_id=request.task_id,
            data=request.data,
            rules=request.rules
        )
        
        return TransformResponse(
            task_id=request.task_id,
            status="success",
            items_transformed=result["count"],
            data=result["data"]
        )
        
    except Exception as e:
        logger.error(f"Transform failed for task {request.task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Transform failed: {str(e)}"
        )


@router.post("/load/{source}", response_model=LoadResponse)
async def load_data(
    source: str,
    request: LoadRequest,
    etl_service: ETLService = Depends(get_etl_service)
):
    """
    L - Load: 변환된 데이터를 데이터베이스에 적재
    """
    try:
        # 데이터 적재 실행
        result = await etl_service.load_data(
            source=source,
            task_id=request.task_id,
            target=request.target,
            data=request.data,
            mode=request.mode
        )
        
        return LoadResponse(
            task_id=request.task_id,
            status="success",
            items_loaded=result["loaded"],
            items_failed=result["failed"]
        )
        
    except Exception as e:
        logger.error(f"Load failed for task {request.task_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Load failed: {str(e)}"
        )


@router.post("/pipeline/{source}")
async def run_etl_pipeline(
    source: str,
    background_tasks: BackgroundTasks,
    params: Optional[Dict[str, Any]] = None,
    async_mode: bool = True,
    etl_service: ETLService = Depends(get_etl_service)
):
    """
    전체 ETL 파이프라인 실행 (E -> T -> L)
    """
    if async_mode:
        # 비동기 실행
        task_id = f"{source}_etl_{date.today().strftime('%Y%m%d_%H%M%S')}"
        background_tasks.add_task(
            run_etl_pipeline_task,
            source,
            task_id,
            params
        )
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "ETL pipeline has been queued"
        }
    else:
        # 동기 실행
        # Extract
        extract_result = await etl_service.extract_data(
            source,
            params
        )
        
        # Transform
        transform_result = await etl_service.transform_data(
            source=source,
            task_id=extract_result["task_id"],
            data=extract_result["data"],
            rules={}
        )
        
        # Load
        load_result = await etl_service.load_data(
            source=source,
            task_id=extract_result["task_id"],
            target="krs_daily_prices",
            data=transform_result["data"],
            mode="upsert"
        )
        
        return {
            "task_id": extract_result["task_id"],
            "status": "completed",
            "extracted": len(extract_result["data"]),
            "transformed": len(transform_result["data"]),
            "loaded": load_result["loaded"],
            "failed": load_result["failed"]
        }


async def run_etl_pipeline_task(source: str, task_id: str, params: Optional[Dict[str, Any]]):
    """백그라운드 ETL 파이프라인 실행"""
    # Kardia DB를 사용하여 ETL 서비스 생성
    from kardia.db import get_postgres_db
    
    try:
        postgres_db = await get_postgres_db()
        etl_service = ETLService(postgres_db)
        await etl_service._initialize_components()
        
        # ETL 파이프라인 실행
        await etl_service.run_full_pipeline(source, task_id, params)
        
    except Exception as e:
        logger.error(f"ETL pipeline failed: {str(e)}")