"""
ETL 서비스 - Extract, Transform, Load 로직
"""
import yaml
import os
from pathlib import Path
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import Depends
from kardia.db import PostgresDB, get_postgres_db
try:
    from kardia.db import RedisDB, get_redis_db
except ImportError:
    RedisDB = None
    get_redis_db = None

from ..etl import (
    # KRX
    KRXExtractor,
    KRXTransformer,
    KRXLoader,
    LoadMode
)
# TODO: Import other data source ETL components when implemented
# from ..etl.dart import DARTExtractor, DARTTransformer, DARTLoader
# from ..etl.sec import SECExtractor, SECTransformer, SECLoader
# from ..etl.tipranks import TipRanksExtractor, TipRanksTransformer, TipRanksLoader
# from ..etl.investing import InvestingExtractor, InvestingTransformer, InvestingLoader

logger = logging.getLogger(__name__)


class ETLService:
    """ETL 서비스 - 설정 기반 ETL 파이프라인 관리"""
    
    def __init__(self, postgres_db: PostgresDB, redis_db: Optional[RedisDB] = None, config_path: Optional[str] = None):
        self.postgres_db = postgres_db
        self.redis_db = redis_db
        self.config = self._load_config(config_path)
        
        # ETL 컴포넌트 레지스트리
        self.extractors = {}
        self.transformers = {}
        self.loaders = {}
        
        # 설정에 따라 컴포넌트 초기화
        self._initialize_components()
    
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """ETL 설정 파일 로드"""
        if not config_path:
            config_path = Path(__file__).parent.parent / "config" / "etl_config.yaml"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 환경변수 치환
        return self._substitute_env_vars(config)
    
    def _substitute_env_vars(self, config: Any) -> Any:
        """설정 파일의 환경변수 치환"""
        if isinstance(config, dict):
            return {k: self._substitute_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            env_var = config[2:-1]
            return os.getenv(env_var, config)
        else:
            return config
    
    async def _initialize_components(self):
        """설정에 따라 ETL 컴포넌트 초기화"""
        # 각 컴포넌트는 필요할 때마다 새 세션으로 생성
        for source_name, source_config in self.config.get('sources', {}).items():
            if not source_config.get('enabled', False):
                logger.info(f"Skipping disabled source: {source_name}")
                continue
            
            # Extractor는 미리 등록만 (실제 세션은 extract_data에서 생성)
            if source_name == "krx":
                self.extractors[source_name] = "krx"  # placeholder
                self.transformers[source_name] = "krx"  # placeholder
                self.loaders[source_name] = "krx"  # placeholder
    
    async def extract_data(self, source: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract - 지정된 소스에서 데이터 추출
        
        Args:
            source: 데이터 소스 (krx, dart, sec, tipranks, investing)
            params: 추출 파라미터
        """
        if source not in self.extractors:
            raise ValueError(f"No extractor registered for source: {source}")
        
        logger.info(f"Extracting data from {source} with params: {params}")
        
        try:
            # 새 세션으로 extractor 생성
            async with self.postgres_db.session() as session:
                if source == "krx":
                    extractor = KRXExtractor(session)
                else:
                    raise ValueError(f"Extractor not implemented for source: {source}")
                
                result = await extractor.extract(params)
                return result
        except Exception as e:
            logger.error(f"Failed to extract data from {source}: {str(e)}")
            raise
    
    async def transform_data(self, source: str, task_id: str, data: List[Dict[str, Any]], rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Transform - 소스별 변환기를 사용해 데이터 변환
        """
        if source not in self.transformers:
            raise ValueError(f"No transformer registered for source: {source}")
        
        # 새로운 세션으로 transformer 재생성 (각 요청마다 새 세션 사용)
        async with self.postgres_db.session() as session:
            transformer_config = self.config['sources'][source].get('transformer', {})
            
            if source == "krx":
                # Redis 클라이언트 가져오기
                redis_client = None
                if self.redis_db:
                    try:
                        redis_client = await self.redis_db.get_client()
                    except Exception as e:
                        logger.warning(f"Failed to get Redis client: {e}")
                
                transformer = KRXTransformer(session, redis_client, transformer_config)
            else:
                raise ValueError(f"Transformer not implemented for source: {source}")
            
            logger.info(f"Transforming {len(data)} items for {source} (task: {task_id})")
            
            # 설정에서 기본 규칙 로드
            default_rules = transformer_config.get('default_rules', {})
            if rules:
                default_rules.update(rules)
            
            try:
                # Extract 결과를 그대로 transform에 전달
                transformed_result = await transformer.transform(data, default_rules)
                
                return {
                    "task_id": task_id,
                    "source": source,
                    "data": transformed_result,  # new_assets와 price_data를 포함
                    "count": len(transformed_result.get('price_data', [])),
                    "new_assets_count": len(transformed_result.get('new_assets', []))
                }
            except Exception as e:
                logger.error(f"Transform failed for {source}: {str(e)}")
                raise
    
    async def load_data(self, source: str, task_id: str, target: str, data: List[Dict[str, Any]], mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Load - 소스별 로더를 사용해 데이터 적재
        """
        if source not in self.loaders:
            raise ValueError(f"No loader registered for source: {source}")
        
        # 새로운 세션으로 loader 재생성
        async with self.postgres_db.session() as session:
            loader_config = self.config['sources'][source].get('loader', {}).get('config', {})
            
            if source == "krx":
                loader = KRXLoader(session, loader_config)
            else:
                raise ValueError(f"Loader not implemented for source: {source}")
            
            logger.info(f"Loading {len(data)} items to {target} for {source} (task: {task_id})")
            
            # 적재 모드 결정
            if not mode:
                mode = self.config['sources'][source]['loader'].get('default_mode', 'upsert')
            
            load_mode = LoadMode(mode)
            
            try:
                result = await loader.load(data, target, load_mode)
                
                return {
                    "task_id": task_id,
                    "source": source,
                    "target": target,
                    "loaded": result.loaded,
                    "updated": result.updated,
                    "failed": result.failed,
                    "skipped": result.skipped,
                    "errors": result.errors[:5]  # 처음 5개 에러만
                }
            except Exception as e:
                logger.error(f"Load failed for {source}: {str(e)}")
                raise
    
    def get_source_config(self, source: str) -> Dict[str, Any]:
        """특정 소스의 설정 반환"""
        if source not in self.config.get('sources', {}):
            raise ValueError(f"Unknown source: {source}")
        
        return self.config['sources'][source]
    
    async def run_full_pipeline(self, source: str, task_id: str, params: Optional[Dict[str, Any]]):
        """전체 ETL 파이프라인 실행"""
        try:
            # Extract
            extract_result = await self.extract_data(source, params)
            
            # Transform
            transform_result = await self.transform_data(
                source=source,
                task_id=task_id,
                data=extract_result["data"],
                rules=params.get("transform_rules") if params else None
            )
            
            # Load
            source_config = self.get_source_config(source)
            target_table = params.get("target", source_config['loader']['target_table']) if params else source_config['loader']['target_table']
            
            load_result = await self.load_data(
                source=source,
                task_id=task_id,
                target=target_table,
                data=transform_result["data"],
                mode=params.get("load_mode") if params else None
            )
            
            logger.info(f"ETL pipeline completed: {load_result['loaded']} loaded, {load_result['failed']} failed")
            
        except Exception as e:
            logger.error(f"ETL pipeline failed: {str(e)}")
            raise
    
    def get_enabled_sources(self) -> List[str]:
        """활성화된 소스 목록 반환"""
        enabled = []
        for source_name, source_config in self.config.get('sources', {}).items():
            if source_config.get('enabled', False):
                enabled.append(source_name)
        return enabled
    
    async def validate_pipeline(self, source: str) -> Dict[str, bool]:
        """파이프라인 구성 검증"""
        return {
            "extractor_ready": source in self.extractors,
            "transformer_ready": source in self.transformers,
            "loader_ready": source in self.loaders,
            "config_valid": source in self.config.get('sources', {})
        }


# FastAPI 의존성 주입을 위한 팩토리 함수
async def get_etl_service(postgres_db: PostgresDB = Depends(get_postgres_db)) -> ETLService:
    """ETL 서비스 인스턴스 생성"""
    redis_db = None
    if get_redis_db:
        try:
            redis_db = await get_redis_db()
        except Exception as e:
            logger.warning(f"Failed to get Redis DB: {e}")
    
    service = ETLService(postgres_db, redis_db)
    await service._initialize_components()
    return service