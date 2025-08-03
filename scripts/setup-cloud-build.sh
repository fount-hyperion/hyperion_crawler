#!/bin/bash

# Cloud Build CI/CD 설정 스크립트
# 사용법: ./scripts/setup-cloud-build.sh [프로젝트ID] [GitHub저장소]
# 예시: ./scripts/setup-cloud-build.sh hyperion-dev-project username/hyperion_crawler

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 변수 설정
PROJECT_ID=${1:-$(gcloud config get-value project)}
GITHUB_REPO=${2:-"username/hyperion_crawler"}
REGION="asia-northeast3"

echo -e "${BLUE}=== Cloud Build CI/CD 설정 시작 ===${NC}"
echo "프로젝트: ${PROJECT_ID}"
echo "GitHub 저장소: ${GITHUB_REPO}"
echo ""

# 1. 필요한 API 활성화
echo -e "${YELLOW}1. Google Cloud API 활성화 중...${NC}"
gcloud services enable cloudbuild.googleapis.com \
    containerregistry.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    --project=${PROJECT_ID}

# 2. Cloud Build 서비스 계정 권한 설정
echo -e "${YELLOW}2. Cloud Build 서비스 계정 권한 설정 중...${NC}"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# Cloud Run 관리자 권한
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/run.admin"

# 서비스 계정 사용자 권한
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/iam.serviceAccountUser"

# Secret Manager 접근 권한
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/secretmanager.secretAccessor"

# 3. hyperion-crawler 서비스 계정 생성 (없는 경우)
echo -e "${YELLOW}3. hyperion-crawler 서비스 계정 확인/생성 중...${NC}"
if ! gcloud iam service-accounts describe hyperion-crawler@${PROJECT_ID}.iam.gserviceaccount.com &>/dev/null; then
    gcloud iam service-accounts create hyperion-crawler \
        --display-name="Hyperion Crawler Service Account" \
        --project=${PROJECT_ID}
    
    # 필요한 권한 부여
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:hyperion-crawler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor"
    
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:hyperion-crawler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --role="roles/datastore.user"
    
    echo -e "${GREEN}✓ 서비스 계정 생성 완료${NC}"
else
    echo -e "${GREEN}✓ 서비스 계정이 이미 존재합니다${NC}"
fi

# Cloud Build가 서비스 계정을 사용할 수 있도록 권한 부여
gcloud iam service-accounts add-iam-policy-binding \
    hyperion-crawler@${PROJECT_ID}.iam.gserviceaccount.com \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/iam.serviceAccountUser" \
    --project=${PROJECT_ID}

# 4. GitHub 연결 안내
echo ""
echo -e "${YELLOW}4. GitHub 저장소 연결${NC}"
echo -e "${BLUE}다음 단계는 GCP Console에서 수동으로 진행해야 합니다:${NC}"
echo ""
echo "1. Cloud Build 콘솔 열기:"
echo "   https://console.cloud.google.com/cloud-build/triggers?project=${PROJECT_ID}"
echo ""
echo "2. '저장소 연결' 클릭"
echo ""
echo "3. GitHub 선택 및 인증"
echo ""
echo "4. ${GITHUB_REPO} 저장소 선택"
echo ""
echo -e "${YELLOW}GitHub 연결을 완료한 후 Enter를 눌러주세요...${NC}"
read -p ""

# 5. 연결된 저장소 확인
echo -e "${YELLOW}5. 연결된 저장소 확인 중...${NC}"
CONNECTED_REPOS=$(gcloud builds repositories list --format="value(name)" 2>/dev/null || echo "")

if [ -z "$CONNECTED_REPOS" ]; then
    echo -e "${RED}연결된 저장소가 없습니다. Console에서 먼저 저장소를 연결해주세요.${NC}"
    echo "https://console.cloud.google.com/cloud-build/triggers/connect?project=${PROJECT_ID}"
    exit 1
fi

echo -e "${GREEN}연결된 저장소:${NC}"
echo "$CONNECTED_REPOS"
echo ""

# 저장소 이름 추출 (github_[owner]_[repo] 형식)
REPO_NAME="github_$(echo ${GITHUB_REPO} | sed 's/\//_/g')"
if ! echo "$CONNECTED_REPOS" | grep -q "$REPO_NAME"; then
    echo -e "${YELLOW}경고: ${GITHUB_REPO} 저장소가 연결되지 않았을 수 있습니다.${NC}"
    echo "연결된 저장소 중 하나를 선택하거나, Console에서 연결을 확인해주세요."
fi

# 6. Cloud Build 트리거 생성
echo -e "${YELLOW}6. Cloud Build 트리거 생성 중...${NC}"

# 개발 환경 트리거 생성
echo "개발 환경 트리거 생성..."
gcloud builds triggers create \
    --region=${REGION} \
    --name="hyperion-crawler-dev" \
    --repository="projects/${PROJECT_ID}/locations/${REGION}/connections/github/repositories/${REPO_NAME}" \
    --branch-pattern="^develop$" \
    --build-config="cloudbuild.yaml" \
    --description="Hyperion Crawler 개발 환경 자동 배포" \
    --substitutions="_ENVIRONMENT=dev" \
    2>/dev/null || {
        echo -e "${YELLOW}새로운 API 형식 실패, 기존 방식으로 재시도...${NC}"
        gcloud builds triggers create github \
            --name="hyperion-crawler-dev" \
            --repo-name="hyperion_crawler" \
            --branch-pattern="^develop$" \
            --build-config="cloudbuild.yaml" \
            --description="Hyperion Crawler 개발 환경 자동 배포" \
            --substitutions="_ENVIRONMENT=dev"
    }

# 프로덕션 환경 트리거 생성
echo "프로덕션 환경 트리거 생성..."
gcloud builds triggers create \
    --region=${REGION} \
    --name="hyperion-crawler-prod" \
    --repository="projects/${PROJECT_ID}/locations/${REGION}/connections/github/repositories/${REPO_NAME}" \
    --branch-pattern="^main$" \
    --build-config="cloudbuild.prod.yaml" \
    --description="Hyperion Crawler 프로덕션 환경 자동 배포" \
    --substitutions="_ENVIRONMENT=prod" \
    2>/dev/null || {
        echo -e "${YELLOW}새로운 API 형식 실패, 기존 방식으로 재시도...${NC}"
        gcloud builds triggers create github \
            --name="hyperion-crawler-prod" \
            --repo-name="hyperion_crawler" \
            --branch-pattern="^main$" \
            --build-config="cloudbuild.prod.yaml" \
            --description="Hyperion Crawler 프로덕션 환경 자동 배포" \
            --substitutions="_ENVIRONMENT=prod"
    }

# 7. 빌드 로그 버킷 생성
echo -e "${YELLOW}7. 빌드 로그 버킷 생성 중...${NC}"
LOGS_BUCKET="${PROJECT_ID}_cloudbuild_logs"
if ! gsutil ls -b gs://${LOGS_BUCKET} &>/dev/null; then
    gsutil mb -p ${PROJECT_ID} -l ${REGION} gs://${LOGS_BUCKET}
    echo -e "${GREEN}✓ 로그 버킷 생성 완료${NC}"
else
    echo -e "${GREEN}✓ 로그 버킷이 이미 존재합니다${NC}"
fi

# 8. 설정 확인
echo ""
echo -e "${GREEN}=== Cloud Build CI/CD 설정 완료 ===${NC}"
echo ""
echo -e "${BLUE}다음 명령으로 트리거를 확인할 수 있습니다:${NC}"
echo "gcloud builds triggers list"
echo ""
echo -e "${BLUE}수동으로 빌드를 실행하려면:${NC}"
echo "gcloud builds triggers run hyperion-crawler-dev-trigger --branch=develop"
echo ""
echo -e "${BLUE}빌드 히스토리 확인:${NC}"
echo "gcloud builds list --limit=10"
echo ""
echo -e "${GREEN}설정이 완료되었습니다! 🎉${NC}"