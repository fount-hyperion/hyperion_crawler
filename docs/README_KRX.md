# KRX 크롤러 구현 가이드

## 구조 설명

### 1. 데이터 모델 (Kardia 활용)
- `AssetMaster`: 종목 마스터 정보 (Kardia에서 import)
- `KrsDailyPrices`: 일별 가격 정보 (Kardia에서 import)
- `CrawlerTaskLog`: 크롤러 작업 로그

### 2. KRX 크롤러 구현
- `api/src/crawlers/krx_crawler.py`: pykrx를 사용한 KRX 데이터 수집
- 비동기 처리로 성능 최적화
- Kardia UniqueKey를 사용한 자산 식별

### 3. FastAPI 엔드포인트
- `GET /api/v1/crawlers/`: 크롤러 목록
- `POST /api/v1/crawlers/krx/crawl`: KRX 크롤러 실행
- `GET /api/v1/crawlers/{crawler_type}/tasks`: 작업 목록
- `GET /api/v1/crawlers/tasks/{task_id}`: 작업 상태 조회

### 4. GCP Workflow
- `workflows/krx_daily_crawl.yaml`: 일별 KRX 데이터 수집 워크플로우
- API 호출, 에러 처리, Pub/Sub 이벤트 발행 포함

## 실행 방법

### 1. 환경 설정
```bash
# Python 3.13 가상환경 생성
python3.13 -m venv venv
source venv/bin/activate

# 의존성 설치
pip install -r api/requirements.txt
```

### 2. GCP Secret Manager 설정
다음 시크릿이 필요합니다:
- `postgres-config`: PostgreSQL 연결 정보
- `neo4j-config`: Neo4j 연결 정보 (선택사항)
- `redis-password`: Redis 비밀번호 (선택사항)
- `jwt-secret-key`: JWT 시크릿 키

### 3. 서버 실행
```bash
# 개발 서버 실행
python run_server.py

# 또는 uvicorn 직접 실행
uvicorn api.src.main:app --reload
```

### 4. 테스트
```bash
# 크롤러 직접 테스트
python test_krx_crawler.py

# API 테스트 (서버 실행 중)
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/crawlers/
```

### 5. GCP Workflow 배포
```bash
# 워크플로우 배포
gcloud workflows deploy krx-daily-crawl \
  --source=workflows/krx_daily_crawl.yaml \
  --location=asia-northeast3

# 환경변수 설정
gcloud workflows execute krx-daily-crawl \
  --data='{"trade_date":"20240801"}' \
  --location=asia-northeast3
```

## 다음 단계

1. **다른 크롤러 구현**
   - DART (전자공시)
   - SEC (미국 증권거래위원회)
   - TipRanks
   - Investing.com

2. **스케줄링**
   - Cloud Scheduler를 통한 정기 실행
   - 각 시장별 적절한 시간대 설정

3. **모니터링**
   - Cloud Logging
   - 작업 실패 알림 설정

4. **성능 최적화**
   - 배치 처리 개선
   - 캐싱 전략 구현