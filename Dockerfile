# 멀티 스테이지 빌드를 사용하여 이미지 크기 최적화
# Stage 1: 빌드 환경
FROM python:3.13-slim as builder

WORKDIR /app

# 빌드 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    curl \
    file \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치 (캐시 활용)
COPY api/requirements.txt .

# Build argument로 인증 토큰 받기
ARG ACCESS_TOKEN

# 모든 의존성 설치
RUN if [ -n "$ACCESS_TOKEN" ]; then \
        echo "Installing with Artifact Registry authentication..."; \
        # curl로 kardia 패키지 다운로드 (리다이렉트 따라가기)
        curl -L -f -S -H "Authorization: Bearer ${ACCESS_TOKEN}" \
             -o kardia-0.3.1.tar.gz \
             "https://asia-northeast3-python.pkg.dev/shared-hyperion/hyperion-python-packages/kardia/kardia-0.3.1.tar.gz" && \
        # 다운로드한 파일로 설치
        pip install --user --no-cache-dir kardia-0.3.1.tar.gz && \
        rm kardia-0.3.1.tar.gz && \
        # 나머지 패키지 설치
        pip install --user --no-cache-dir -r requirements.txt; \
    else \
        echo "Installing without private registry..."; \
        pip install --user --no-cache-dir -r requirements.txt; \
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