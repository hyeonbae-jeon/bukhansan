# 북한산 논문 아카이브 — 설정 가이드

## 이번에 바뀐 점
academic.naver.com에 짧은 시간 동안 요청이 몰려서 서버가 응답을 늦춘 것으로 보였습니다. 그래서:
1. **요청마다 2~5초씩 랜덤으로 대기**하도록 늘려서 서버 부담을 줄였습니다.
2. **한 번 실행할 때 검색어 17개를 한꺼번에 다 처리하지 않고, 3개씩만 처리**합니다. 다음 실행 때 자동으로 이어서 나머지를 처리해요 (어디까지 했는지는 `fetch_state.json`에 저장됩니다).
3. 매일 자동으로 조금씩 실행되도록 스케줄을 바꿨습니다.
4. 다시 GitHub Actions에서 실행합니다 (본인 컴퓨터에 Python 설치 안 해도 됩니다).
5. **네이버 공식 API("전문자료 검색")를 보조 채널로 추가했습니다.** 이건 정식 등록된 키로 쓰는 공식 API라 차단될 위험이 거의 없어요. 저자·학술지·초록 같은 상세정보는 못 주지만(제목/설명/링크만), academic.naver.com 스크래핑이 또 막히더라도 이 채널은 계속 논문을 찾아줍니다. **API 키 없이도 사이트는 정상 작동하고, 있으면 보너스로 더 많이 모입니다.**

## 네이버 API 키 등록 방법 (선택이지만 추천)
1. https://developers.naver.com/apps/#/register 접속 (네이버 계정 로그인 필요)
2. 애플리케이션 이름 아무거나 입력, **사용 API**에서 "검색" 선택
3. 등록하면 **Client ID**, **Client Secret** 이 발급됩니다
4. GitHub 저장소 → Settings → Secrets and variables → Actions → **New repository secret**
   - Name: `NAVER_CLIENT_ID` / Secret: 발급받은 Client ID
   - Name: `NAVER_CLIENT_SECRET` / Secret: 발급받은 Client Secret
5. 이 두 개를 등록해두면 다음 실행부터 자동으로 API 채널도 같이 돕니다.

## 파일 구성
- `index.html` — 실제 보여지는 사이트 (GitHub Pages로 배포)
- `fetch_naver.py` — 북한산 관련 논문을 네이버 학술정보(academic.naver.com)에서 수집하는 스크립트 (GitHub Actions가 실행)
- `papers.json` — 수집된 논문 데이터 (누적됨 — 실행할 때마다 기존 데이터에 새로 찾은 것만 추가)
- `fetch_state.json` — 지금까지 검색어 몇 번째까지 처리했는지 기억하는 파일 (자동 생성/갱신됨)
- `.github/workflows/fetch-naver.yml` — 매일 자동으로 `fetch_naver.py`를 실행하는 워크플로우

## 1. GitHub 저장소에 파일 올리기
기존 `bukhansan` 저장소에 위 파일들을 그대로 업로드하세요. 폴더 구조(`.github/workflows/` 포함)를 그대로 유지해야 합니다. (이전에 로컬 실행용으로 안내드렸던 내용은 무시하셔도 됩니다.)

## 2. 첫 실행
저장소 상단 **Actions** 탭 → **Fetch Bukhansan Papers (Naver)** 선택 → **Run workflow** 버튼 클릭.
검색어 17개 중 3개만 처리하기 때문에 한 번 실행은 비교적 빨리 끝나요(몇 분 정도). **검색어를 전부 다 돌려면 총 6번 실행해야 합니다** (17개 ÷ 3개씩 = 6번, 마지막 배치는 2개). 매일 자동 스케줄이 걸려있어서 그냥 둬도 6일이면 한 바퀴 다 돌아요. 빨리 채우고 싶으면 Actions 탭에서 **Run workflow**를 몇 분 간격으로 여러 번 눌러도 됩니다 (너무 연달아 누르면 다시 부담을 주는 거니, 몇 분씩은 간격을 두는 걸 권장해요).

## 3. GitHub Pages 활성화
Settings → Pages → Branch: main → Save. 잠시 후 아래 주소에서 접속 가능합니다.
```
https://<본인아이디>.github.io/bukhansan
```

## 이후 운영
- 매일 자동으로 배치 1개씩 처리되어 `papers.json`이 점점 채워집니다.
- 검색어를 한 바퀴 다 돌고 나면, 다음 배치는 다시 처음 검색어부터 시작해서 새로 올라온 논문이 있는지 확인합니다 (이미 수집된 논문은 건너뛰므로 빠르게 끝나요).
- 급하게 갱신하고 싶으면 Actions 탭에서 수동으로 **Run workflow**를 눌러도 됩니다.

## 그래도 계속 타임아웃이 나면
`fetch_naver.py` 상단의 `MIN_DELAY, MAX_DELAY = 2.0, 5.0` 값을 더 늘려보세요(예: 5~10초). 그래도 안 되면 이번엔 IP 자체가 차단된 것일 수 있어요 — 그 경우엔 본인 컴퓨터에서 직접 실행하는 방식으로 다시 돌아가야 할 수도 있습니다.
