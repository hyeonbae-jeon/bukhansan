# 북한산 논문 아카이브

## 데이터 출처
- **OpenAlex** (주): 무료 오픈 API, 2억 5천만 건+ 논문, CC0 라이선스
- **네이버 학술정보** (보조): 한국어 논문 보완

## 빠른 시작

```bash
pip install requests
python fetch_papers.py
```

## GitHub Pages 배포
1. 저장소 전체 push
2. Settings → Pages → main 브랜치 루트 설정
3. Actions → Fetch Papers → Run workflow 클릭

## Secrets 설정 (선택)
| Secret | 용도 |
|--------|------|
| `OPENALEX_API_KEY` | 일일 100,000 요청 무료 키 |
| `CONTACT_EMAIL`    | polite pool 등록 (속도 향상) |

## OpenAlex API 키 발급
1. https://openalex.org 회원가입
2. https://openalex.org/settings/api 에서 무료 키 발급

## 파일 구조
```
index.html                  ← 사이트 본체
fetch_papers.py             ← 논문 수집 스크립트
papers.json                 ← 수집 결과 (자동 갱신)
fetch_state.json            ← 마지막 실행 정보
.github/workflows/          ← GitHub Actions 설정
```
