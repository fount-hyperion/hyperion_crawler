# GitHub Personal Access Token 권한 문제 해결

## 문제
```
refusing to allow a Personal Access Token to create or update workflow .github/workflows/deploy-crawler.yml without `workflow` scope
```

## 해결 방법

### 방법 1: Personal Access Token 권한 업데이트 (권장)

1. GitHub 설정으로 이동: https://github.com/settings/tokens
2. 기존 토큰 클릭 또는 "Generate new token" 클릭
3. 다음 권한 선택:
   - `repo` (전체 저장소 접근)
   - `workflow` (워크플로우 파일 수정 권한) ✅ 필수!
4. "Generate token" 클릭
5. 새 토큰 복사

6. Git 자격 증명 업데이트:
```bash
# macOS (Keychain 사용 시)
git credential-osxkeychain erase
host=github.com
protocol=https
[Enter를 두 번 누르기]

# 다시 push하면 새 토큰 입력 프롬프트가 나타남
git push origin dev
```

### 방법 2: GitHub CLI 사용 (gh)

```bash
# GitHub CLI 설치 (없는 경우)
brew install gh

# 인증
gh auth login

# Push
git push origin dev
```

### 방법 3: SSH 키 사용

```bash
# SSH 키 생성 (없는 경우)
ssh-keygen -t ed25519 -C "your-email@example.com"

# 공개 키 복사
cat ~/.ssh/id_ed25519.pub

# GitHub Settings > SSH and GPG keys에 추가

# Remote URL을 SSH로 변경
git remote set-url origin git@github.com:fount-hyperion/hyperion_crawler.git

# Push
git push origin dev
```

### 방법 4: 임시 해결책 - workflow 파일 제외

```bash
# workflow 파일을 임시로 이동
mv .github/workflows/deploy-crawler.yml .github/workflows/deploy-crawler.yml.bak

# 다른 변경사항만 push
git add .
git commit -m "chore: workflow 파일 제외한 변경사항"
git push origin dev

# workflow 파일 복원 및 별도 push
mv .github/workflows/deploy-crawler.yml.bak .github/workflows/deploy-crawler.yml
git add .github/workflows/deploy-crawler.yml
git commit -m "ci: GitHub Actions workflow 추가"

# 이제 workflow 권한이 있는 토큰으로 push
git push origin dev
```

## 권장 사항

1. **Personal Access Token 업데이트가 가장 간단한 해결책**
2. 장기적으로는 GitHub CLI 또는 SSH 키 사용 권장
3. Cloud Build를 주로 사용한다면 GitHub Actions workflow는 선택사항

## Cloud Build만 사용하는 경우

GitHub Actions workflow가 필요 없다면:

```bash
# workflow 파일 삭제
rm -rf .github
git add -A
git commit -m "chore: GitHub Actions 제거 (Cloud Build 사용)"
git push origin dev
```