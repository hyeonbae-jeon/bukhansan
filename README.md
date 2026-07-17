# 북한산 논문 아카이브 — 설정 가이드

## 파일 구성
- `index.html` — 실제 보여지는 사이트 (GitHub Pages로 배포)
- `fetch_naver.py` — 네이버 학술정보(academic.naver.com)에서 논문을 수집하는 스크립트 (GitHub Actions가 실행)
- `.github/workflows/fetch-naver.yml` — 매주 자동으로 `fetch_naver.py`를 실행해 `papers.json`을 갱신하는 워크플로우
- `papers.json` — 수집된 논문 데이터 (최초 실행 전에는 없음, Actions가 처음 실행되면 자동 생성됨)

## 1. GitHub 저장소에 파일 올리기
기존 `bukhansan` 저장소에 위 파일들을 그대로 업로드하세요. 폴더 구조(`.github/workflows/` 포함)를 그대로 유지해야 합니다.

## 2. 첫 실행
저장소 상단 **Actions** 탭 → **Fetch Bukhansan Papers (Naver)** 선택 → **Run workflow** 버튼 클릭.
API 키가 따로 필요 없어요 (네이버 학술정보 페이지를 직접 읽어오는 방식). 1~2분 후 저장소에 `papers.json`이 새로 생기거나 갱신됩니다.

## 3. 카카오맵 키 입력
`index.html` 안의 `YOUR_KAKAO_APP_KEY`를 카카오 개발자센터의 JavaScript 키로 교체하세요.
카카오 개발자센터 → 내 애플리케이션 → 플랫폼 키 → JavaScript 키 → JavaScript SDK 도메인에 아래 두 줄 등록:
```
https://<본인아이디>.github.io
http://localhost
```

## 4. GitHub Pages 활성화
Settings → Pages → Branch: main → Save. 잠시 후 아래 주소에서 접속 가능합니다.
```
https://<본인아이디>.github.io/bukhansan
```

## 이후 운영
`fetch-naver.yml`은 매주 일요일 자동 실행되어 `papers.json`을 최신 상태로 유지합니다.
새로운 논문을 바로 반영하고 싶으면 Actions 탭에서 **Run workflow**를 수동으로 눌러도 됩니다.
