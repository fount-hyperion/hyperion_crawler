# Artifact Registry 인증 설정 가이드

## 문제 상황
Cloud Build에서 다른 프로젝트(`shared-hyperion`)의 private Artifact Registry에 있는 Python 패키지(`kardia`)를 설치할 수 없음.

## 원인
1. Cloud Build 서비스 계정이 `shared-hyperion` 프로젝트의 Artifact Registry에 접근 권한이 없음
2. 잘못된 pip 설치 방법 사용 (`--index-url` 대신 `--extra-index-url` 사용 필요)

## 해결 방법

### 1. 권한 부여 (shared-hyperion 프로젝트 관리자가 실행)

```bash
# dev-hyperion-kaidra 프로젝트의 Cloud Build 서비스 계정에 권한 부여
gcloud projects add-iam-policy-binding shared-hyperion \
    --member="serviceAccount:104556394287@cloudbuild.gserviceaccount.com" \
    --role="roles/artifactregistry.reader"
```

### 2. Dockerfile 수정 (Cloud Build용)

```dockerfile
# Build arguments for authentication
ARG PIP_EXTRA_INDEX_URL

# 패키지 설치 - 인증 URL이 제공된 경우 사용
RUN if [ -n "$PIP_EXTRA_INDEX_URL" ]; then \
        pip install --user --no-cache-dir --extra-index-url $PIP_EXTRA_INDEX_URL kardia; \
    else \
        echo "Warning: Private repository URL not provided, skipping kardia installation"; \
    fi && \
    pip install --user --no-cache-dir -r requirements.txt
```

### 3. Cloud Build 설정

```yaml
# Docker 빌드 시 인증 토큰 전달
- name: 'gcr.io/cloud-builders/docker'
  entrypoint: 'bash'
  args:
    - '-c'
    - |
      TOKEN=$(gcloud auth print-access-token)
      docker build \
        --build-arg PIP_EXTRA_INDEX_URL=https://oauth2accesstoken:${TOKEN}@asia-northeast3-python.pkg.dev/shared-hyperion/hyperion-virtual/simple/ \
        -t IMAGE_NAME .
```

### 3. 로컬 테스트 방법

```bash
# 로컬에서 테스트하려면 먼저 Artifact Registry 설정 확인
gcloud artifacts print-settings python \
    --project=shared-hyperion \
    --repository=hyperion-virtual \
    --location=asia-northeast3

# 인증 후 패키지 설치
pip install keyrings.google-artifactregistry-auth
pip install --extra-index-url https://asia-northeast3-python.pkg.dev/shared-hyperion/hyperion-virtual/simple/ kardia
```

## 주요 포인트

1. **keyrings.google-artifactregistry-auth 필수**: 이 패키지가 없으면 인증이 작동하지 않음
2. **--extra-index-url 사용**: `--index-url`이 아닌 `--extra-index-url` 사용 (PyPI도 함께 사용하기 위함)
3. **서비스 계정 권한**: Cloud Build가 다른 프로젝트의 Artifact Registry에 접근하려면 명시적인 권한 부여 필요

## 참고 자료
- [Google Cloud Artifact Registry Python Authentication](https://cloud.google.com/artifact-registry/docs/python/authentication)
- [Stack Overflow: Install Artifact Registry Python package from Dockerfile with Cloud Build](https://stackoverflow.com/questions/78686622/)