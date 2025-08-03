#!/bin/bash
set -e

# 환경 변수 설정
ENVIRONMENT=${1:-dev}
WORKFLOW_NAME="krx-daily-crawl-dev"
REGION="asia-northeast3"
PROJECT_ID="dev-hyperion-kaidra"

# Production 환경인 경우
if [ "$ENVIRONMENT" = "prod" ]; then
  WORKFLOW_NAME="krx-daily-crawl-prod"
  PROJECT_ID="prod-hyperion-kaidra"
fi

echo "Deploying workflow to $ENVIRONMENT environment..."
echo "  Workflow: $WORKFLOW_NAME"
echo "  Region: $REGION"
echo "  Project: $PROJECT_ID"

# 현재 프로젝트 설정
gcloud config set project $PROJECT_ID

# Workflow 배포
gcloud workflows deploy $WORKFLOW_NAME \
  --location=$REGION \
  --source=workflows/krx_etl_workflow.yaml \
  --set-env-vars=CRAWLER_API_URL=https://hyperion-crawler-$ENVIRONMENT-qg56z3pouq-du.a.run.app

echo "Workflow deployed successfully!"

# 배포 확인
echo ""
echo "Verifying deployment..."
gcloud workflows describe $WORKFLOW_NAME --location=$REGION --format="table(name,state,createTime,updateTime)"

echo ""
echo "To execute the workflow manually:"
echo "gcloud workflows run $WORKFLOW_NAME --location=$REGION"