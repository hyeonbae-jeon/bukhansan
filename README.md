# 북한산 실무 AI 지식 플랫폼

> 북한산 관련 학술논문을 AI가 자동 분석하여  
> 국립공원 실무자가 **논문을 읽지 않아도 현장에 바로 적용**할 수 있는 정보를 제공합니다.

## 아키텍처

```
OpenAlex API ──▶ collector.py ──▶ raw_papers.json
                                        │
                      OpenAI API ──▶ enricher.py  (AI 실무 분석)
                                        │
                               indexer.py ──▶ papers.json
                                                  │
                                         index.html (GitHub Pages)
```

## 파일 구조

| 파일 | 역할 |
|------|------|
| `collector.py` | OpenAlex API 논문 수집 |
| `enricher.py` | OpenAI GPT로 AI 실무 분석 생성 |
| `indexer.py` | papers.json 인덱스 빌드 |
| `run_pipeline.py` | 세 단계 한 번에 실행 |
| `index.html` | 프론트엔드 (GitHub Pages) |
| `papers.json` | 최종 데이터 (자동 생성) |
| `raw_papers.json` | 수집 원본 데이터 (자동 생성) |

## 배포 방법

### 1. 저장소 생성 및 Push
```bash
git init && git add . && git commit -m "init"
git remote add origin https://github.com/<USER>/<REPO>.git
git push -u origin main
```

### 2. GitHub Pages 활성화
Settings → Pages → Source: `main` 브랜치, `/ (root)`

### 3. Secrets 등록
Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|------------|-----|
| `OPENAI_API_KEY` | OpenAI API 키 (필수 — AI 분석에 사용) |
| `OPENALEX_EMAIL` | 이메일 주소 (선택 — API 요청 속도 향상) |

> **OpenAI API 키 발급**: https://platform.openai.com/api-keys  
> **예상 비용**: 논문 100건 분석 시 약 $0.50~$1.00 (gpt-4o-mini 기준)

### 4. 첫 실행
Actions 탭 → `Update Papers Pipeline` → `Run workflow`

---

## AI 분석 항목

각 논문에 다음 14가지 정보가 자동 생성됩니다:

| 항목 | 설명 |
|------|------|
| 3줄 핵심요약 | 배경·결과·시사점을 각 1줄로 요약 |
| 연구목적 | 2~3문장 실무 언어로 재서술 |
| 핵심결과 | 주요 수치·발견 3개 이상 |
| 실무 적용방안 | 현장 행동 중심 방안 3개 이상 |
| 북한산 적용 가능성 | 1~5점 + 적용 근거 서술 |
| 관련 업무 분야 | 탐방로 관리, 생태계 모니터링 등 |
| 관련 법령 | 자연공원법 조항 등 |
| 현장점검 체크리스트 | 측정 가능한 체크 항목 5개 이상 |
| 실무 활용도 | 1~5점 |
| 적용 시 주의사항 | 예산·법령·계절 제약 등 |
| 관련 태그 | 검색·필터용 키워드 |
| 후속 연구 필요 내용 | 추가 연구 방향 제안 |
| AI 추천 연구 키워드 | 유사 논문 검색용 |

---

## 로컬 실행 (개발 시)

```bash
# 파이프라인 실행
export OPENAI_API_KEY="sk-..."
python run_pipeline.py

# 로컬 웹 서버
python -m http.server 8000
# → http://localhost:8000 에서 확인
```

## 라이선스
- 코드: MIT
- 논문 메타데이터: OpenAlex CC0
- AI 분석 결과: 생성 주체 소유
