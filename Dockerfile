# 멀티 스테이지 빌드를 사용하여 이미지 크기 최적화
# Stage 1: 빌드 환경
FROM python:3.13-slim as builder

WORKDIR /app

# 빌드 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치 (캐시 활용)
COPY api/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: 실행 환경
FROM python:3.13-slim

WORKDIR /app

# 최소한의 시스템 패키지만 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 appuser

# 빌드 스테이지에서 설치된 Python 패키지 복사
COPY --from=builder /root/.local /home/appuser/.local

# 애플리케이션 코드 복사
COPY --chown=appuser:appuser api/src ./api/src

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# 비루트 사용자로 전환 (보안 강화)
USER appuser

# 실행
CMD ["uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8080"]