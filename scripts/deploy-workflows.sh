#!/bin/bash

# Workflow 배포 스크립트

PROJECT_ID=${1:-dev-hyperion-kaidra}
REGION=${2:-asia-northeast3}

echo "Deploying workflows to project: $PROJECT_ID in region: $REGION"

# 1. KRX 일일 데이터 수집 워크플로우 배포
echo "Deploying KRX daily crawl workflow..."
gcloud workflows deploy krx-daily-crawl-dev \
  --source=workflows/krx-daily-crawl.yaml \
  --location=$REGION \
  --project=$PROJECT_ID \
  --service-account=wf-krx-daily-crawl-dev@$PROJECT_ID.iam.gserviceaccount.com

# 2. 워크플로우 실행 권한 부여 (Cloud Run 호출 권한)
echo "Granting permissions to workflow service account..."
gcloud run services add-iam-policy-binding hyperion-crawler-dev \
  --region=$REGION \
  --member="serviceAccount:wf-krx-daily-crawl-dev@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --project=$PROJECT_ID

echo "Workflow deployment completed!"

# 3. 테스트 실행
echo ""
echo "To test the workflow, run:"
echo "gcloud workflows run krx-daily-crawl-dev --data='{\"date\":\"$(date +%Y-%m-%d)\"}' --location=$REGION"