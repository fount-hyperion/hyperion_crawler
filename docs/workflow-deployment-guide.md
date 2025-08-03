# Workflow 별도 배포 가이드

## 개요

Terraform은 Workflow 인프라(서비스 계정, IAM 권한)만 관리하고, 실제 Workflow 정의는 애플리케이션 코드와 함께 배포됩니다.

## 아키텍처

```
Terraform (인프라)          애플리케이션 (비즈니스 로직)
    │                              │
    ├─ Workflow 리소스 생성          ├─ Workflow 정의 (YAML)
    ├─ 서비스 계정                  ├─ Cloud Run 앱
    └─ IAM 권한                    └─ CI/CD 배포
```

## 배포 프로세스

### 1. 인프라 배포 (Terraform)

```bash
cd environments/dev
terraform apply -var-file=terraform.tfvars

# 출력 확인
terraform output crawler_workflow_name
terraform output crawler_service_url
```

### 2. 수동 Workflow 배포

```bash
cd ~/Hyperion/hyperion_crawler

# 개발 환경
./scripts/deploy-workflow.sh dev

# 운영 환경
./scripts/deploy-workflow.sh prod
```

### 3. 자동 배포 (GitHub Actions)

Push 시 자동으로:
1. Cloud Run 서비스 빌드 및 배포
2. Workflow 파일 변경 시 Workflow 업데이트

## Workflow 관리

### 실행

```bash
# 수동 실행
gcloud workflows run krx-daily-crawl-dev \
  --location=asia-northeast3 \
  --data='{"trade_date":"2024-01-15"}'

# 실행 상태 확인
gcloud workflows executions list \
  --workflow=krx-daily-crawl-dev \
  --location=asia-northeast3
```

### 업데이트

```bash
# Workflow 정의 수정 후
cd ~/Hyperion/hyperion_crawler
vim workflows/krx_daily_crawl.yaml

# 배포
./scripts/deploy-workflow.sh dev
```

### 롤백

```bash
# 이전 버전 확인
gcloud workflows revisions list \
  --workflow=krx-daily-crawl-dev \
  --location=asia-northeast3

# 특정 버전으로 롤백
gcloud workflows deploy krx-daily-crawl-dev \
  --location=asia-northeast3 \
  --source=@<revision-id>
```

## 장점

1. **독립적 배포**: Terraform과 Workflow를 별도로 배포 가능
2. **빠른 수정**: Workflow 변경 시 Terraform 실행 불필요
3. **버전 관리**: Workflow 코드와 앱 코드를 함께 관리
4. **CI/CD 통합**: 애플리케이션 배포와 함께 자동화

## 주의사항

1. **최초 배포**: Terraform 실행 후 Workflow 배포 필요
2. **환경변수**: Cloud Run URL 등은 배포 시점에 결정
3. **권한**: Workflow SA가 Cloud Run 호출 권한 필요

## 트러블슈팅

### Workflow가 Cloud Run을 호출할 수 없는 경우

```bash
# IAM 권한 확인
gcloud run services get-iam-policy hyperion-crawler-dev \
  --location=asia-northeast3

# 권한 추가 (필요시)
gcloud run services add-iam-policy-binding hyperion-crawler-dev \
  --location=asia-northeast3 \
  --member="serviceAccount:wf-krx-daily-crawl-dev@dev-hyperion-kaidra.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

### 환경변수가 설정되지 않은 경우

```bash
# Workflow 환경변수 확인
gcloud workflows describe krx-daily-crawl-dev \
  --location=asia-northeast3 \
  --format="value(envVariables)"

# 환경변수 업데이트
gcloud workflows deploy krx-daily-crawl-dev \
  --location=asia-northeast3 \
  --source=workflows/krx_daily_crawl.yaml \
  --set-env-vars=CRAWLER_API_URL=https://new-url.run.app
```