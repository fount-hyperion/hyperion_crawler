"""
Application configuration.
"""
from pydantic import BaseModel, Field
from functools import lru_cache
from kardia import get_secret_manager

# Kardia secret manager 인스턴스
secret_manager = get_secret_manager()


class Settings(BaseModel):
    """Application settings."""
    
    # Application
    APP_NAME: str = "Hyperion Crawler"
    VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "asia-northeast3"
    
    # Crawler Settings
    USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    
    def __init__(self, **kwargs):
        # JWT Secret Key
        try:
            secret_key = secret_manager.get_secret('jwt-secret-key')
            kwargs['SECRET_KEY'] = secret_key
        except Exception as e:
            print(f"Warning: Could not load jwt-secret-key from Kardia: {e}")
        
        # GCP Project 정보
        kwargs['GOOGLE_CLOUD_PROJECT'] = secret_manager.current_project
        
        super().__init__(**kwargs)


@lru_cache()
def get_settings() -> Settings:
    """싱글톤 패턴으로 설정 인스턴스 반환"""
    return Settings()


settings = get_settings()