# 멀티 스테이지 빌드를 사용하여 이미지 크기 최적화
# Stage 1: 빌드 환경
FROM python:3.13-slim as builder

# Docker BuildKit 캐시 활성화
# syntax = docker/dockerfile:1.4

WORKDIR /app

# 빌드 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치 (캐시 활용)
COPY api/requirements.txt .

# pip 업그레이드 및 캐시 최적화
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel

# Build argument로 GitHub 토큰 받기
ARG GH_TOKEN

# 모든 의존성 설치
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ -n "$GH_TOKEN" ]; then \
        echo "Installing with GitHub authentication..."; \
        # Git config로 HTTPS URL을 토큰 포함 URL로 자동 변환
        git config --global url."https://${GH_TOKEN}@github.com/".insteadOf "https://github.com/" && \
        # Kardia latest 버전 설치
        pip install --user --no-cache-dir git+https://github.com/fount-hyperion/kardia.git@latest && \
        # 나머지 패키지 설치
        pip install --user -r requirements.txt && \
        # 보안을 위해 git config 제거
        rm -rf ~/.gitconfig; \
    else \
        echo "Installing without private repository access..."; \
        pip install --user -r requirements.txt; \
    fi

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
ENV PATH=/home/appuser/.local/bin:${PATH}
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# 비루트 사용자로 전환 (보안 강화)
USER appuser

# 실행
CMD ["uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8080"]