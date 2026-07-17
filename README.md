# 북한산 논문 아카이브 — 설정 가이드

## 파일 구성
- `index.html` — 실제 보여지는 사이트 (GitHub Pages로 배포)
- `fetch_naver.py` — 네이버 학술정보(academic.naver.com)에서 논문을 수집하는 스크립트 (GitHub Actions가 실행)
- `.github/workflows/fetch-naver.yml` — 매주 자동으로 `fetch_naver.py`를 실행해 `papers.json`을 갱신하는 워크플로우
- `papers.json` — 수집된 논문 데이터 (최초 실행 전에는 없음, Actions가 처음 실행되면 자동 생성됨)

## 1. GitHub 저장소에 파일 올리기
기존 `bukhansan` 저장소에 위 파일들을 그대로 업로드하세요. 폴더 구조(`.github/workflows/` 포함)를 그대로 유지해야 합니다.

## 2. Gemini API 키 등록 (AI 분류·요약·활용방안 기능용, 선택이지만 강력 추천)
1. https://aistudio.google.com/app/apikey 에서 무료로 Gemini API 키 발급 (구글 계정만 있으면 됨)
2. 저장소 Settings → Secrets and variables → Actions → **New repository secret**
   - Name: `GEMINI_API_KEY`
   - Secret: 발급받은 키 값
3. 이 키가 없으면 AI 분류/요약/활용방안 없이 기존 규칙기반 분류만으로 동작합니다 (사이트는 정상 작동, 이 기능만 빠짐).

## 3. 첫 실행
저장소 상단 **Actions** 탭 → **Fetch Bukhansan Papers (Naver)** 선택 → **Run workflow** 버튼 클릭.
검색어가 많고(17개) 논문 하나하나 AI 분석까지 하기 때문에 **꽤 오래 걸릴 수 있어요(수십 분 단위)**. Actions 탭에서 실행 로그로 진행 상황을 확인할 수 있습니다.

## 4. 카카오맵 키 입력
`index.html` 안의 `YOUR_KAKAO_APP_KEY`를 카카오 개발자센터의 JavaScript 키로 교체하세요.
카카오 개발자센터 → 내 애플리케이션 → 플랫폼 키 → JavaScript 키 → JavaScript SDK 도메인에 아래 두 줄 등록:
```
https://<본인아이디>.github.io
http://localhost
```

## 5. GitHub Pages 활성화
Settings → Pages → Branch: main → Save. 잠시 후 아래 주소에서 접속 가능합니다.
```
https://<본인아이디>.github.io/bukhansan
```

## 이후 운영
`fetch-naver.yml`은 매주 일요일 자동 실행되어 `papers.json`을 최신 상태로 유지합니다.
새로운 논문을 바로 반영하고 싶으면 Actions 탭에서 **Run workflow**를 수동으로 눌러도 됩니다.
