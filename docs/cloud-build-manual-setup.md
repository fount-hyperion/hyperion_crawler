# Cloud Build 수동 설정 가이드

## 1. GitHub 저장소 연결

1. Cloud Build 콘솔 열기: https://console.cloud.google.com/cloud-build/triggers
2. "저장소 연결" 또는 "CONNECT REPOSITORY" 클릭
3. "GitHub (Cloud Build GitHub App)" 선택
4. GitHub 인증 진행
5. hyperion_crawler 저장소 선택
6. "연결" 클릭

## 2. 트리거 생성 (개발 환경)

1. Cloud Build 콘솔에서 "트리거 만들기" 클릭
2. 다음 정보 입력:
   - **이름**: hyperion-crawler-dev
   - **설명**: Hyperion Crawler 개발 환경 자동 배포
   - **이벤트**: 브랜치에 push
   - **소스**: 
     - 저장소: 연결된 hyperion_crawler 선택
     - 브랜치: `^develop$`
   - **구성**:
     - 유형: Cloud Build 구성 파일
     - 위치: `/cloudbuild.yaml`
   - **대체 변수**:
     - `_ENVIRONMENT`: `dev`
3. "만들기" 클릭

## 3. 트리거 생성 (프로덕션 환경)

1. "트리거 만들기" 다시 클릭
2. 다음 정보 입력:
   - **이름**: hyperion-crawler-prod
   - **설명**: Hyperion Crawler 프로덕션 환경 자동 배포
   - **이벤트**: 브랜치에 push
   - **소스**: 
     - 저장소: 연결된 hyperion_crawler 선택
     - 브랜치: `^main$`
   - **구성**:
     - 유형: Cloud Build 구성 파일
     - 위치: `/cloudbuild.prod.yaml`
   - **대체 변수**:
     - `_ENVIRONMENT`: `prod`
3. "만들기" 클릭

## 4. Microsoft Teams 알림 설정 (선택사항)

1. Teams 채널에서 Webhook 생성:
   - 채널 → 커넥터 → 수신 웹후크 구성
   - Webhook URL 복사

2. Secret Manager에서 Teams Webhook URL 저장:
   ```bash
   echo -n "YOUR_TEAMS_WEBHOOK_URL" | \
   gcloud secrets create teams-webhook-url --data-file=-
   ```

3. Cloud Build 서비스 계정에 권한 부여:
   ```bash
   PROJECT_NUMBER=$(gcloud projects describe $(gcloud config get-value project) --format='value(projectNumber)')
   
   gcloud secrets add-iam-policy-binding teams-webhook-url \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

4. 자세한 설정은 `teams-webhook-setup.md` 참조

## 5. 트리거 테스트

### 수동 실행
```bash
# 개발 환경 트리거 실행
gcloud builds triggers run hyperion-crawler-dev --branch=develop

# 프로덕션 환경 트리거 실행
gcloud builds triggers run hyperion-crawler-prod --branch=main
```

### Git Push로 자동 실행
```bash
# develop 브랜치에 push
git checkout develop
git push origin develop

# main 브랜치에 push
git checkout main
git push origin main
```

## 6. 빌드 상태 확인

### Console에서 확인
https://console.cloud.google.com/cloud-build/builds

### CLI로 확인
```bash
# 최근 빌드 목록
gcloud builds list --limit=5

# 특정 빌드 상세 정보
gcloud builds describe BUILD_ID

# 빌드 로그 보기
gcloud builds log BUILD_ID
```

## 문제 해결

### 트리거가 실행되지 않는 경우
1. GitHub 연결 상태 확인
2. 브랜치 패턴이 정확한지 확인 (^develop$, ^main$)
3. cloudbuild.yaml 파일이 저장소 루트에 있는지 확인

### 빌드가 실패하는 경우
1. Cloud Build 서비스 계정 권한 확인
2. Secret Manager 접근 권한 확인
3. 빌드 로그에서 상세 오류 확인

### 배포가 실패하는 경우
1. Cloud Run 서비스 계정 확인
2. 리소스 할당량 확인
3. 환경 변수 설정 확인