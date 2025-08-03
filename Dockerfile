FROM python:3.13-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치 (headless 모드용)
RUN playwright install chromium

# 애플리케이션 코드 복사
COPY src ./src

# 환경 변수 설정
ENV PYTHONPATH=/app
ENV PORT=8080

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# 실행
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]