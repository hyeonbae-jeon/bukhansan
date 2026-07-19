# 북한산 실무 AI 지식 플랫폼

북한산국립공원 학술논문을 AI가 분석하여 현장 실무자가 바로 활용할 수 있는 지식 플랫폼.

## 구조

```
├── main.py              # 파이프라인 진입점 (Collector → Enricher → Indexer)
├── collector.py         # OpenAlex API + 네이버 학술 스크래핑
├── enricher.py          # Google Gemini AI 분석 (14개 항목)
├── indexer.py           # 검색 인덱스 및 통계 구축
├── index.html           # 프론트엔드 (GitHub Pages)
├── papers.json          # 수집·분석 결과 (자동 갱신)
├── fetch_state.json     # 수집 상태
└── .github/workflows/
    └── fetch_papers.yml # 매주 자동 실행
```

## 배포 (3단계)

### 1. GitHub Secrets 등록
`Settings → Secrets and variables → Actions → New repository secret`

| 이름 | 값 |
|------|----|
| `GEMINI_API_KEY` | Google AI Studio에서 발급 ([aistudio.google.com](https://aistudio.google.com)) |
| `OPENALEX_EMAIL` | 본인 이메일 (OpenAlex polite pool 사용) |

### 2. GitHub Pages 활성화
`Settings → Pages → Source: Deploy from a branch → main / root`

### 3. 첫 수집 실행
`Actions 탭 → Collect & Enrich Papers → Run workflow`

---

## Gemini API 무료 한도 (2026 기준)

| 모델 | 무료 한도 | 논문 200건 분석 소요 시간 |
|------|-----------|--------------------------|
| gemini-2.5-flash-lite | 1,000 req/day | 약 14분 (4초 간격) |

- 신용카드 등록 불필요
- [aistudio.google.com](https://aistudio.google.com) → Get API Key

## AI 분석 항목 (14개)

| 항목 | 설명 |
|------|------|
| 3줄 핵심요약 | 논문 핵심을 3문장으로 압축 |
| 연구목적 | 연구 목적 1~2문장 |
| 핵심결과 | 주요 연구 결과 |
| 실무 적용방안 | 현장 적용 가능한 방법 |
| 북한산 적용 가능성 (1~5) | 직접 적용 가능성 점수 |
| 적용 가능한 이유 | 점수 근거 설명 |
| 관련 업무 | 연관 업무 분야 |
| 관련 법령 | 관련 자연공원법 등 법령 |
| 현장점검 체크리스트 | 현장에서 바로 사용 가능한 체크리스트 |
| 실무 활용도 (1~5) | 즉시 현장 적용 가능성 점수 |
| 적용 시 주의사항 | 현장 적용 시 유의점 |
| 관련 태그 | 검색용 키워드 |
| AI 추천 논문 | 연관 연구 주제 |
| 후속 연구 필요 내용 | 추가 연구 필요 항목 |
