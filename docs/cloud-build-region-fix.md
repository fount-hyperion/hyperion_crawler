# Cloud Build 리전 Quota 문제 해결

## 문제
```
failed precondition: due to quota restrictions, Cloud Build cannot run builds in this region
```

## 해결 방법

### 방법 1: Global 리전 사용 (권장)

Cloud Build 트리거를 global 리전으로 다시 생성:

1. **기존 트리거 삭제** (선택사항)
```bash
gcloud builds triggers delete hyperion-crawler-dev --region=asia-northeast3
```

2. **Global 리전에 트리거 생성**
```bash
# GitHub 저장소와 연결된 경우
gcloud builds triggers create github \
  --name="hyperion-crawler-dev" \
  --repo-name="hyperion_crawler" \
  --repo-owner="fount-hyperion" \
  --branch-pattern="^dev$" \
  --build-config="cloudbuild.yaml" \
  --description="Hyperion Crawler 개발 환경 자동 배포"
```

### 방법 2: 다른 리전 사용

사용 가능한 Cloud Build 리전:
- us-central1
- us-west1
- europe-west1
- asia-southeast1

```bash
# 예: asia-southeast1 사용
gcloud builds triggers create github \
  --region=asia-southeast1 \
  --name="hyperion-crawler-dev" \
  --repo-name="hyperion_crawler" \
  --branch-pattern="^dev$" \
  --build-config="cloudbuild.yaml"
```

### 방법 3: Cloud Build Quota 증가 요청

1. GCP Console에서 Quotas 페이지 열기:
   https://console.cloud.google.com/iam-admin/quotas?project=dev-hyperion-kaidra

2. "Cloud Build API" 검색

3. asia-northeast3 리전의 quota 요청

### 방법 4: GitHub Actions 사용 (대안)

Cloud Build 대신 GitHub Actions 사용:
- `.github/workflows/deploy-crawler.yml` 파일이 이미 있음
- GitHub에서 직접 빌드 및 배포 가능

## 권장사항

1. **즉시 해결**: Global 리전 사용 (방법 1)
2. **장기적**: asia-northeast3 quota 요청하고, 승인 후 리전 변경

## Global 리전으로 트리거 재생성 스크립트

```bash
#!/bin/bash

# 프로젝트 설정
PROJECT_ID=$(gcloud config get-value project)
REPO_NAME="hyperion_crawler"
REPO_OWNER="fount-hyperion"

echo "Creating Cloud Build triggers in global region..."

# 개발 환경 트리거
gcloud builds triggers create github \
  --name="hyperion-crawler-dev" \
  --repo-name="${REPO_NAME}" \
  --repo-owner="${REPO_OWNER}" \
  --branch-pattern="^dev$" \
  --build-config="cloudbuild.yaml" \
  --description="Hyperion Crawler 개발 환경 자동 배포" \
  --substitutions="_ENVIRONMENT=dev"

# 프로덕션 환경 트리거
gcloud builds triggers create github \
  --name="hyperion-crawler-prod" \
  --repo-name="${REPO_NAME}" \
  --repo-owner="${REPO_OWNER}" \
  --branch-pattern="^main$" \
  --build-config="cloudbuild.prod.yaml" \
  --description="Hyperion Crawler 프로덕션 환경 자동 배포" \
  --substitutions="_ENVIRONMENT=prod"

echo "Triggers created successfully!"
```