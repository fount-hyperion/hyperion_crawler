#!/bin/bash

# Cloud Build 서비스 계정에 Artifact Registry 접근 권한 부여
# 사용법: ./scripts/setup-artifact-registry-access.sh

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 변수 설정
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
SHARED_PROJECT_ID="shared-hyperion"

echo -e "${BLUE}=== Cloud Build Artifact Registry 접근 권한 설정 ===${NC}"
echo "프로젝트: ${PROJECT_ID}"
echo "Cloud Build 서비스 계정: ${CLOUD_BUILD_SA}"
echo ""

# 1. 현재 프로젝트의 Cloud Build 서비스 계정에 권한 부여
echo -e "${YELLOW}1. 현재 프로젝트에서 Artifact Registry 권한 부여${NC}"
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${CLOUD_BUILD_SA}" \
    --role="roles/artifactregistry.reader"

# 2. shared-hyperion 프로젝트의 Artifact Registry에 대한 접근 권한 부여
echo -e "${YELLOW}2. shared-hyperion 프로젝트의 Artifact Registry 접근 권한 부여${NC}"
echo "이 작업은 shared-hyperion 프로젝트에 대한 권한이 필요합니다."
echo "권한이 없다면 프로젝트 관리자에게 다음 명령을 실행하도록 요청하세요:"
echo ""
echo -e "${BLUE}gcloud projects add-iam-policy-binding ${SHARED_PROJECT_ID} \\"
echo "    --member=\"serviceAccount:${CLOUD_BUILD_SA}\" \\"
echo -e "    --role=\"roles/artifactregistry.reader\"${NC}"
echo ""

# 3. 권한 확인
echo -e "${YELLOW}3. 현재 권한 확인${NC}"
echo "Cloud Build 서비스 계정의 현재 권한:"
gcloud projects get-iam-policy ${PROJECT_ID} \
    --flatten="bindings[].members" \
    --filter="bindings.members:serviceAccount:${CLOUD_BUILD_SA}" \
    --format="table(bindings.role)" | grep -E "(artifactregistry|cloudbuild)" || true

echo ""
echo -e "${GREEN}=== 설정 완료 ===${NC}"
echo ""
echo -e "${BLUE}다음 단계:${NC}"
echo "1. shared-hyperion 프로젝트에 대한 권한이 부여되었는지 확인"
echo "2. Cloud Build 트리거 다시 실행"
echo ""
echo -e "${YELLOW}테스트 명령:${NC}"
echo "gcloud builds submit --config cloudbuild.yaml"