# 배포 옵션

Hyperion Crawler는 두 가지 배포 방법을 지원합니다:

## 1. Cloud Build (권장)

### 장점
- Google Cloud 네이티브 솔루션
- 빠른 빌드 속도 (GCP 내부 네트워크 사용)
- 간단한 설정
- Cloud Run과 긴밀한 통합

### 설정 방법
1. GitHub 저장소를 Cloud Build와 연결
2. 트리거 생성 (main, develop 브랜치)
3. `cloudbuild.yaml` 파일 사용

### 사용 시나리오
- 프로덕션 배포
- 개발 환경 자동 배포
- 빠른 CI/CD 파이프라인 필요 시

## 2. GitHub Actions

### 장점
- GitHub 통합 (PR, Issues 연동)
- 다양한 Action 마켓플레이스
- 상세한 워크플로우 제어
- Workload Identity Federation 지원

### 설정 방법
1. GitHub Secrets 설정
2. Workload Identity 구성
3. `.github/workflows/deploy-crawler.yml` 사용

### 사용 시나리오
- PR 단위 테스트
- 복잡한 워크플로우 필요 시
- 다른 GitHub 기능과 연동 필요 시

## 권장 사항

### 개발 프로세스
1. **개발 중**: GitHub Actions로 PR 테스트
2. **브랜치 머지**: Cloud Build로 자동 배포

### 환경별 설정
- **develop 브랜치** → dev 환경 (Cloud Build 자동 배포)
- **main 브랜치** → prod 환경 (Cloud Build 자동 배포)
- **PR** → GitHub Actions 테스트만 실행

## 마이그레이션 가이드

GitHub Actions에서 Cloud Build로 전환하려면:

1. Cloud Build 트리거 생성
2. `cloudbuild.yaml` 파일 확인
3. 권한 설정 확인
4. 테스트 배포 실행
5. GitHub Actions 워크플로우 비활성화 (선택사항)