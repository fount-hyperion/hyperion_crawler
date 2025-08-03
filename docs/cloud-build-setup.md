# Cloud Build 설정 가이드

## 개요
이 문서는 Hyperion Crawler의 Cloud Build를 통한 자동 배포 설정 방법을 설명합니다.

## 사전 준비사항

1. **API 활성화**
   ```bash
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   ```

2. **서비스 계정 권한 설정**
   Cloud Build 서비스 계정에 필요한 권한 부여:
   ```bash
   PROJECT_ID=$(gcloud config get-value project)
   PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
   
   # Cloud Run 관리자 권한
   gcloud projects add-iam-policy-binding $PROJECT_ID \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/run.admin"
   
   # 서비스 계정 사용자 권한
   gcloud iam service-accounts add-iam-policy-binding \
     hyperion-crawler@${PROJECT_ID}.iam.gserviceaccount.com \
     --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```

## Cloud Build 트리거 설정

### 1. GitHub 연결
1. [Cloud Build 트리거 페이지](https://console.cloud.google.com/cloud-build/triggers) 접속
2. "저장소 연결" 클릭
3. GitHub 선택 및 인증
4. hyperion_crawler 저장소 선택

### 2. 개발 환경 트리거 생성
- **이름**: hyperion-crawler-dev-trigger
- **이벤트**: 브랜치에 push
- **소스**:
  - 저장소: hyperion_crawler
  - 브랜치: `^develop$`
- **빌드 구성**: Cloud Build 구성 파일 (yaml 또는 json)
- **Cloud Build 구성 파일 위치**: `/cloudbuild.yaml`

### 3. 프로덕션 환경 트리거 생성
- **이름**: hyperion-crawler-prod-trigger
- **이벤트**: 브랜치에 push
- **소스**:
  - 저장소: hyperion_crawler
  - 브랜치: `^main$`
- **빌드 구성**: Cloud Build 구성 파일 (yaml 또는 json)
- **Cloud Build 구성 파일 위치**: `/cloudbuild.prod.yaml`

## 환경별 차이점

### 개발 환경 (develop 브랜치)
- 서비스명: hyperion-crawler-develop
- 최소 인스턴스: 0 (비용 절감)
- 메모리: 512Mi
- 테스트 실패 시에도 배포 진행

### 프로덕션 환경 (main 브랜치)
- 서비스명: hyperion-crawler-prod
- 최소 인스턴스: 1 (항상 실행)
- 메모리: 1Gi
- 테스트 실패 시 배포 중단

## 로컬 테스트

Cloud Build를 로컬에서 테스트하려면:

```bash
# Cloud Build 로컬 빌더 설치
gcloud components install cloud-build-local

# 로컬 빌드 실행
cloud-build-local --config=cloudbuild.yaml --dryrun=false .
```

## 배포 확인

배포 후 확인사항:

1. **서비스 상태 확인**
   ```bash
   gcloud run services list --region asia-northeast3
   ```

2. **로그 확인**
   ```bash
   gcloud logging read "resource.type=cloud_run_revision" --limit 50
   ```

3. **헬스 체크**
   ```bash
   SERVICE_URL=$(gcloud run services describe hyperion-crawler-develop \
     --region asia-northeast3 --format 'value(status.url)')
   curl $SERVICE_URL/health
   ```

## 트러블슈팅

### 빌드 실패 시
1. Cloud Build 로그 확인
2. 권한 문제인 경우 서비스 계정 권한 재확인
3. 이미지 빌드 실패 시 Dockerfile 확인

### 배포 실패 시
1. Cloud Run 로그 확인
2. 환경 변수 설정 확인
3. 메모리/CPU 리소스 부족 여부 확인

## 모니터링

1. **Cloud Build 대시보드**: 빌드 성공률 및 소요 시간
2. **Cloud Run 메트릭**: 요청 수, 레이턴시, 에러율
3. **로그 기반 메트릭**: 커스텀 알림 설정 가능