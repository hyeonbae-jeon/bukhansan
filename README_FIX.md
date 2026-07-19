# 실패한 GitHub Actions 수정 가이드

## 원인
두 워크플로 모두 `requirements.txt`가 저장소 루트에 없어서 발생했습니다.
- `Collect & Enrich Papers` → setup-python이 캐시할 `requirements.txt`를 못 찾아 실패
- `Update Papers Pipeline` → `pip install`이 아예 실행되지 않아 `bs4`(BeautifulSoup) 모듈 없음 에러

## 적용 방법

1. 이 3개 파일을 저장소에 그대로 추가/교체합니다.
   ```
   저장소 루트/
   ├── requirements.txt                          ← 새로 추가
   └── .github/workflows/
       ├── collect_enrich.yml                    ← 교체
       └── update_papers.yml                     ← 교체
   ```

2. 커밋 & 푸시
   ```bash
   git add requirements.txt .github/workflows/
   git commit -m "fix: add requirements.txt and stabilize workflows"
   git push
   ```

3. GitHub 저장소 → **Settings → Secrets and variables → Actions**에서
   `GEMINI_API_KEY`가 등록되어 있는지 확인합니다. (이전 단계에서 이미 등록했다면 그대로 두면 됩니다.)

4. **Actions 탭 → Collect & Enrich Papers → Run workflow** 클릭

## 이번 수정에서 바뀐 점
- `requirements.txt`에 `requests`, `beautifulsoup4`, `lxml`, `google-generativeai`, `python-dateutil`을 명시했습니다.
- 두 워크플로 모두 `actions/checkout@v4`가 **가장 먼저** 실행되도록 순서를 명확히 했습니다. (checkout 전에 setup-python 캐시가 파일을 찾으면 "make sure you have checked out the target repository" 에러가 납니다.)
- `pip install -r requirements.txt`로 통일했습니다. (이전 임시 수정처럼 yml 안에 패키지를 직접 나열하는 방식은 나중에 依存성이 바뀔 때마다 yml을 계속 고쳐야 해서 유지보수가 어렵습니다. requirements.txt 방식이 정석입니다.)
- 마지막 단계에서 `papers.json` 변경분을 자동으로 커밋·푸시하도록 추가했습니다. (이전 워크플로에 이 단계가 없었다면, 스크립트가 성공해도 로컬 파일만 바뀌고 저장소에는 반영되지 않았을 수 있습니다.)

## 만약 collector.py / enricher.py / indexer.py 파일 이름이 다르다면
워크플로의 `python collector.py` / `python enricher.py` / `python indexer.py` 부분을 실제 파일명에 맞게 바꿔주세요. 파일을 공유해주시면 정확히 맞춰서 다시 드릴게요.
