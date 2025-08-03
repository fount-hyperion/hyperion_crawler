#!/bin/bash

# Cloud Run 배포 스크립트
# 사용법: ./scripts/deploy-cloud-run.sh [환경] [프로젝트ID]
# 예시: ./scripts/deploy-cloud-run.sh dev hyperion-dev-project

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 환경 및 프로젝트 설정
ENVIRONMENT=${1:-dev}
PROJECT_ID=${2:-$(gcloud config get-value project)}
REGION="asia-northeast3"
SERVICE_NAME="hyperion-crawler-${ENVIRONMENT}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo -e "${GREEN}=== Hyperion Crawler Cloud Run 배포 ===${NC}"
echo "환경: ${ENVIRONMENT}"
echo "프로젝트: ${PROJECT_ID}"
echo "리전: ${REGION}"
echo "서비스명: ${SERVICE_NAME}"
echo ""

# 프로젝트 설정
echo -e "${YELLOW}프로젝트 설정 중...${NC}"
gcloud config set project ${PROJECT_ID}

# Docker 이미지 빌드
echo -e "${YELLOW}Docker 이미지 빌드 중...${NC}"
docker build -t ${IMAGE_NAME} .

# Container Registry에 푸시
echo -e "${YELLOW}Container Registry에 이미지 푸시 중...${NC}"
docker push ${IMAGE_NAME}

# Cloud Run 서비스 배포
echo -e "${YELLOW}Cloud Run 서비스 배포 중...${NC}"
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --port 8080 \
  --set-env-vars "ENVIRONMENT=${ENVIRONMENT}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
  --service-account "hyperion-crawler@${PROJECT_ID}.iam.gserviceaccount.com"

# 서비스 URL 가져오기
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')

echo ""
echo -e "${GREEN}=== 배포 완료 ===${NC}"
echo "서비스 URL: ${SERVICE_URL}"
echo ""

# 헬스 체크
echo -e "${YELLOW}헬스 체크 중...${NC}"
if curl -s "${SERVICE_URL}/health" | grep -q "healthy"; then
    echo -e "${GREEN}✓ 서비스가 정상적으로 실행 중입니다.${NC}"
else
    echo -e "${RED}✗ 서비스 헬스 체크 실패${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}배포가 성공적으로 완료되었습니다!${NC}"
echo "API 문서: ${SERVICE_URL}/docs"