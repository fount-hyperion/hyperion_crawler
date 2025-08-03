"""
크롤러 작업 로그 모델
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, String, JSON, Float, BigInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from kardia.models.base import Base


class CrawlerTaskLog(Base):
    """크롤러 작업 로그 테이블 - 모든 크롤러 공통"""
    __tablename__ = "crawler_task_logs"
    __table_args__ = {"schema": "crawler"}
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    crawler_type: Mapped[str] = mapped_column(String, nullable=False, index=True)  # krx, dart, sec, tipranks, investing
    task_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)  # pending, running, success, failed
    
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    execution_time: Mapped[float] = mapped_column(Float, nullable=True)  # seconds
    
    # 작업 파라미터 및 결과
    parameters: Mapped[dict] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    
    # 수집 데이터 통계
    items_collected: Mapped[int] = mapped_column(BigInteger, default=0)
    items_processed: Mapped[int] = mapped_column(BigInteger, default=0)
    items_failed: Mapped[int] = mapped_column(BigInteger, default=0)
    
    # 이력 관리
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )