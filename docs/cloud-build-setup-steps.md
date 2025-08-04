# Cloud Build 설정 단계별 가이드

## 1. Cloud Build Console에서 GitHub 연결

1. Cloud Build 트리거 페이지 열기:
   ```
   https://console.cloud.google.com/cloud-build/triggers?project=dev-hyperion-kaidra
   ```

2. "저장소 연결" 또는 "CONNECT REPOSITORY" 클릭

3. "GitHub (Cloud Build GitHub App)" 선택

4. GitHub 인증 및 hyperion_crawler 저장소 선택

## 2. 트리거 생성

### 개발 환경 트리거
1. "트리거 만들기" 클릭
2. 설정:
   - **이름**: `hyperion-crawler-dev`
   - **이벤트**: 브랜치에 push
   - **브랜치**: `^dev$`
   - **구성 파일**: `/cloudbuild.yaml`

### 프로덕션 환경 트리거 (나중에)
1. "트리거 만들기" 클릭
2. 설정:
   - **이름**: `hyperion-crawler-prod`
   - **이벤트**: 브랜치에 push
   - **브랜치**: `^main$`
   - **구성 파일**: `/cloudbuild.prod.yaml`

## 3. Teams Webhook 설정 (선택사항)

Teams 알림을 받으려면:

```bash
# Teams Webhook URL을 Secret Manager에 저장
echo -n "YOUR_TEAMS_WEBHOOK_URL" | \
gcloud secrets create teams-webhook-build-url --data-file=-

# Cloud Build 서비스 계정에 권한 부여
PROJECT_NUMBER=$(gcloud projects describe dev-hyperion-kaidra --format='value(projectNumber)')

gcloud secrets add-iam-policy-binding teams-webhook-build-url \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## 4. 테스트

GitHub에 push하면 자동으로 빌드가 시작됩니다:

```bash
# 작은 변경사항 만들기
echo "# Build test" >> README.md
git add README.md
git commit -m "test: Cloud Build 트리거 테스트"
git push origin dev
```

## 5. 빌드 상태 확인

```bash
# 최근 빌드 확인
gcloud builds list --limit=5

# 빌드 로그 보기
gcloud builds log <BUILD_ID>
```

또는 Console에서 확인:
https://console.cloud.google.com/cloud-build/builds?project=dev-hyperion-kaidra