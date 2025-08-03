#!/bin/bash
set -e

# 환경 변수 설정
ENVIRONMENT=${1:-dev}
JOB_NAME="dev-krx-daily-schedule"
REGION="asia-northeast3"
PROJECT_ID="dev-hyperion-kaidra"
WORKFLOW_NAME="krx-daily-crawl-dev"
SCHEDULE="0 9 * * *"  # 매일 오전 9시 (KST)

# Production 환경인 경우
if [ "$ENVIRONMENT" = "prod" ]; then
  JOB_NAME="prod-krx-daily-schedule"
  PROJECT_ID="prod-hyperion-kaidra"
  WORKFLOW_NAME="krx-daily-crawl-prod"
fi

# 서비스 계정 이메일 (Terraform에서 생성됨)
SERVICE_ACCOUNT="scheduler-${ENVIRONMENT}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Deploying scheduler to $ENVIRONMENT environment..."
echo "  Job Name: $JOB_NAME"
echo "  Region: $REGION"
echo "  Project: $PROJECT_ID"
echo "  Workflow: $WORKFLOW_NAME"
echo "  Schedule: $SCHEDULE"
echo "  Service Account: $SERVICE_ACCOUNT"

# 현재 프로젝트 설정
gcloud config set project $PROJECT_ID

# 기존 스케줄러가 있는지 확인
if gcloud scheduler jobs describe $JOB_NAME --location=$REGION &>/dev/null; then
  echo "Updating existing scheduler job..."
  gcloud scheduler jobs update http $JOB_NAME \
    --location=$REGION \
    --schedule="$SCHEDULE" \
    --time-zone="Asia/Seoul" \
    --uri="https://workflowexecutions.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/workflows/${WORKFLOW_NAME}/executions" \
    --http-method=POST \
    --oauth-service-account-email=$SERVICE_ACCOUNT \
    --message-body='{}'
else
  echo "Creating new scheduler job..."
  gcloud scheduler jobs create http $JOB_NAME \
    --location=$REGION \
    --schedule="$SCHEDULE" \
    --time-zone="Asia/Seoul" \
    --uri="https://workflowexecutions.googleapis.com/v1/projects/${PROJECT_ID}/locations/${REGION}/workflows/${WORKFLOW_NAME}/executions" \
    --http-method=POST \
    --oauth-service-account-email=$SERVICE_ACCOUNT \
    --message-body='{}'
fi

echo "Scheduler deployed successfully!"

# 배포 확인
echo ""
echo "Verifying deployment..."
gcloud scheduler jobs describe $JOB_NAME --location=$REGION --format="table(name,state,schedule,timeZone)"

echo ""
echo "To test the scheduler manually:"
echo "gcloud scheduler jobs run $JOB_NAME --location=$REGION"