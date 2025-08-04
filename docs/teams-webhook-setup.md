# Microsoft Teams Webhook 설정 가이드

## 1. Teams에서 Webhook 생성

### Teams 채널에서 Webhook 추가
1. 알림을 받을 Teams 채널로 이동
2. 채널명 옆의 `...` (더보기) 클릭
3. `커넥터` 선택
4. `수신 웹후크` 검색 후 `구성` 클릭
5. 웹후크 이름 입력 (예: "Hyperion Crawler Build")
6. 선택적으로 이미지 업로드
7. `만들기` 클릭
8. **생성된 Webhook URL 복사** (중요!)

## 2. GCP Secret Manager에 Webhook URL 저장

```bash
# Webhook URL을 Secret Manager에 저장
echo -n "YOUR_TEAMS_WEBHOOK_URL" | \
gcloud secrets create teams-webhook-build-url \
  --data-file=- \
  --replication-policy="user-managed" \
  --locations="asia-northeast3"

# Cloud Build 서비스 계정에 권한 부여
PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')

gcloud secrets add-iam-policy-binding teams-webhook-build-url \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 3. 알림 형식

### 성공 알림
- **색상**: 녹색 (개발) / 파란색 (프로덕션)
- **정보**: 환경, 커밋 ID, 빌드 ID, 서비스 URL
- **버튼**: 서비스 열기, API 문서, 빌드 로그

### 실패 알림
- **색상**: 빨간색
- **정보**: 환경, 커밋 ID, 빌드 ID
- **버튼**: 빌드 로그 확인

## 4. 테스트

### Webhook 테스트
```bash
# Teams Webhook 테스트 메시지 전송
WEBHOOK_URL="YOUR_TEAMS_WEBHOOK_URL"

curl -X POST $WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "@type": "MessageCard",
    "@context": "https://schema.org/extensions",
    "themeColor": "0078D4",
    "summary": "테스트 메시지",
    "sections": [{
      "activityTitle": "Cloud Build 알림 테스트",
      "facts": [{
        "name": "상태",
        "value": "테스트 성공"
      }],
      "markdown": true
    }]
  }'
```

### Cloud Build 트리거 테스트
```bash
# 개발 환경 빌드 실행
gcloud builds triggers run hyperion-crawler-dev --branch=develop

# 알림이 Teams 채널에 전송되는지 확인
```

## 5. 문제 해결

### 알림이 오지 않는 경우
1. Secret Manager에 URL이 올바르게 저장되었는지 확인
   ```bash
   gcloud secrets versions access latest --secret="teams-webhook-build-url"
   ```

2. Cloud Build 서비스 계정 권한 확인
   ```bash
   gcloud secrets get-iam-policy teams-webhook-build-url
   ```

3. Cloud Build 로그에서 알림 스텝 확인
   ```bash
   gcloud builds log BUILD_ID --region=asia-northeast3
   ```

### Teams에서 메시지가 표시되지 않는 경우
- Webhook URL이 유효한지 확인
- Teams 채널의 커넥터 설정 확인
- 메시지 카드 JSON 형식이 올바른지 확인

## 6. 고급 설정

### 환경별 다른 채널로 알림
```bash
# 개발용 Webhook
gcloud secrets create teams-webhook-url-dev --data-file=-

# 프로덕션용 Webhook  
gcloud secrets create teams-webhook-url-prod --data-file=-
```

cloudbuild.yaml에서 환경에 따라 다른 secret 사용:
```yaml
availableSecrets:
  secretManager:
  - versionName: projects/${PROJECT_ID}/secrets/teams-webhook-url-${_ENVIRONMENT}/versions/latest
    env: 'TEAMS_WEBHOOK_URL'
```

### 특정 이벤트만 알림
- 프로덕션 배포만 알림
- 실패한 빌드만 알림
- 특정 브랜치 빌드만 알림

## 7. 보안 고려사항

- Webhook URL은 민감한 정보이므로 Secret Manager에만 저장
- 불필요한 사용자에게 Secret 접근 권한 부여 금지
- 정기적으로 Webhook URL 갱신 권장