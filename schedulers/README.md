# Cloud Scheduler 관리 가이드

## 개요

Cloud Scheduler는 애플리케이션 레벨에서 관리됩니다. Terraform은 서비스 계정과 권한만 생성합니다.

## 디렉토리 구조

```
schedulers/
├── README.md
├── dev/
│   └── krx-daily.yaml
└── prod/
    └── krx-daily.yaml
```

## 스케줄러 배포

### 1. 수동 배포

```bash
# 개발 환경
../scripts/deploy-scheduler.sh dev

# 운영 환경
../scripts/deploy-scheduler.sh prod
```

### 2. 스케줄러 설정 파일 (예시)

```yaml
# schedulers/dev/krx-daily.yaml
name: dev-krx-daily-schedule
schedule: "0 9 * * *"  # 매일 오전 9시 (KST)
timeZone: "Asia/Seoul"
target:
  type: workflow
  workflow: krx-daily-crawl-dev
  payload: {}
```

### 3. 스케줄러 관리 명령어

```bash
# 스케줄러 목록 조회
gcloud scheduler jobs list --location=asia-northeast3

# 스케줄러 상세 정보
gcloud scheduler jobs describe dev-krx-daily-schedule --location=asia-northeast3

# 스케줄러 일시 중지
gcloud scheduler jobs pause dev-krx-daily-schedule --location=asia-northeast3

# 스케줄러 재개
gcloud scheduler jobs resume dev-krx-daily-schedule --location=asia-northeast3

# 스케줄러 수동 실행
gcloud scheduler jobs run dev-krx-daily-schedule --location=asia-northeast3

# 스케줄러 삭제
gcloud scheduler jobs delete dev-krx-daily-schedule --location=asia-northeast3
```

## 추가 스케줄러 생성

새로운 스케줄러가 필요한 경우:

1. Terraform에서 서비스 계정 권한 추가 (필요시)
2. 스케줄러 생성:

```bash
gcloud scheduler jobs create http <JOB_NAME> \
  --location=asia-northeast3 \
  --schedule="<CRON_EXPRESSION>" \
  --time-zone="Asia/Seoul" \
  --uri="<TARGET_URI>" \
  --http-method=POST \
  --oauth-service-account-email=scheduler-dev@dev-hyperion-kaidra.iam.gserviceaccount.com
```

## 모니터링

Cloud Console에서 확인:
- https://console.cloud.google.com/cloudscheduler

로그 확인:
```bash
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_id=dev-krx-daily-schedule" --limit=50
```