"""
ETL 엔드포인트 단위 테스트
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from api.src.etl.base import LoadResult


class TestHealthEndpoints:
    """헬스 체크 엔드포인트 테스트"""
    
    def test_root_endpoint(self, test_client):
        """루트 엔드포인트 테스트"""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["app"] == "Hyperion Crawler Test"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
    
    def test_health_db_endpoint(self, test_client):
        """DB 헬스 체크 엔드포인트 테스트"""
        response = test_client.get("/health/db")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "databases" in data
        assert "postgres" in data["databases"]
        assert "neo4j" in data["databases"]
        assert "redis" in data["databases"]


class TestETLEndpoints:
    """ETL 엔드포인트 테스트"""
    
    @patch('api.src.routers.etl.get_etl_service')
    async def test_extract_data(self, mock_get_etl_service, test_client):
        """Extract 엔드포인트 테스트"""
        # Mock ETL Service
        mock_etl_service = AsyncMock()
        mock_etl_service.extract_data = AsyncMock(return_value={
            "task_id": "krx_extract_20240101",
            "data": [{"ticker": "005930", "name": "삼성전자"}],
            "metadata": {"count": 1}
        })
        mock_get_etl_service.return_value = mock_etl_service
        
        # 요청
        response = test_client.post(
            "/api/v1/etl/extract/krx",
            json={"trade_date": "20240101"}
        )
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["items_extracted"] == 1
        assert data["task_id"] == "krx_extract_20240101"
    
    @patch('api.src.routers.etl.get_etl_service')
    async def test_transform_data(self, mock_get_etl_service, test_client):
        """Transform 엔드포인트 테스트"""
        # Mock ETL Service
        mock_etl_service = AsyncMock()
        mock_etl_service.transform_data = AsyncMock(return_value={
            "task_id": "krx_transform_20240101",
            "data": [{"uuid": "KRS-001", "close_price": 70000}]
        })
        mock_get_etl_service.return_value = mock_etl_service
        
        # 요청
        response = test_client.post(
            "/api/v1/etl/transform/krx",
            json={
                "task_id": "krx_extract_20240101",
                "data": [{"ticker": "005930", "ohlcv": {"close": 70000}}],
                "rules": {}
            }
        )
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["items_transformed"] == 1
    
    @patch('api.src.routers.etl.get_etl_service')
    async def test_load_data(self, mock_get_etl_service, test_client):
        """Load 엔드포인트 테스트"""
        # Mock ETL Service
        mock_etl_service = AsyncMock()
        mock_etl_service.load_data = AsyncMock(return_value={
            "loaded": 1,
            "failed": 0
        })
        mock_get_etl_service.return_value = mock_etl_service
        
        # 요청
        response = test_client.post(
            "/api/v1/etl/load/krx",
            json={
                "task_id": "krx_transform_20240101",
                "target": "krs_daily_prices",
                "data": [{"uuid": "KRS-001", "close_price": 70000}],
                "mode": "upsert"
            }
        )
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["items_loaded"] == 1
        assert data["items_failed"] == 0
    
    @patch('api.src.routers.etl.get_etl_service')
    async def test_pipeline_sync(self, mock_get_etl_service, test_client):
        """동기 파이프라인 실행 테스트"""
        # Mock ETL Service
        mock_etl_service = AsyncMock()
        mock_etl_service.extract_data = AsyncMock(return_value={
            "task_id": "krx_pipeline_20240101",
            "data": [{"ticker": "005930"}],
            "metadata": {}
        })
        mock_etl_service.transform_data = AsyncMock(return_value={
            "data": [{"uuid": "KRS-001"}]
        })
        mock_etl_service.load_data = AsyncMock(return_value={
            "loaded": 1,
            "failed": 0
        })
        mock_get_etl_service.return_value = mock_etl_service
        
        # 요청
        response = test_client.post(
            "/api/v1/etl/pipeline/krx",
            json={"async_mode": False}
        )
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["extracted"] == 1
        assert data["loaded"] == 1
    
    @patch('api.src.routers.etl.BackgroundTasks')
    @patch('api.src.routers.etl.get_etl_service')
    async def test_pipeline_async(self, mock_get_etl_service, mock_bg_tasks, test_client):
        """비동기 파이프라인 실행 테스트"""
        # Mock
        mock_etl_service = AsyncMock()
        mock_get_etl_service.return_value = mock_etl_service
        
        mock_bg = MagicMock()
        mock_bg_tasks.return_value = mock_bg
        
        # 요청
        response = test_client.post(
            "/api/v1/etl/pipeline/krx",
            json={"async_mode": True}
        )
        
        # 검증
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert "task_id" in data
        assert data["message"] == "ETL pipeline has been queued"
    
    @patch('api.src.routers.etl.get_etl_service')
    async def test_extract_error(self, mock_get_etl_service, test_client):
        """Extract 에러 처리 테스트"""
        # Mock ETL Service - 에러 발생
        mock_etl_service = AsyncMock()
        mock_etl_service.extract_data = AsyncMock(
            side_effect=Exception("Extract failed")
        )
        mock_get_etl_service.return_value = mock_etl_service
        
        # 요청
        response = test_client.post("/api/v1/etl/extract/krx")
        
        # 검증
        assert response.status_code == 500
        data = response.json()
        assert "Extract failed" in data["detail"]