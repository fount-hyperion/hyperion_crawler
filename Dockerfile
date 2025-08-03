FROM python:3.13-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치 (필요한 경우에만)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY api/src ./api/src

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV PORT=8080
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}

# Cloud Run은 자체 헬스체크를 제공하므로 HEALTHCHECK 제거

# 실행
CMD ["uvicorn", "api.src.main:app", "--host", "0.0.0.0", "--port", "8080"]