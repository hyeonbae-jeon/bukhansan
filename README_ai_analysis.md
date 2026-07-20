# 북한산 실무 AI 지식 플랫폼 — ai_analysis 구조 가이드

## 전체 파이프라인

```
Collector (openalex_client.py)
    ↓ OpenAlex에서 초록 있는 논문 수집 → papers.json (ai_analysis: null)
Enricher (gemini_enricher.py)
    ↓ Gemini API로 초록 분석 → papers.json (ai_analysis: {...})
Indexer (indexer.py)
    ↓ ai_analysis 집계 → index.json (검색/필터/통계용)
Frontend
    ↓ papers.json + index.json 소비
```

## papers.json 레코드 구조

```jsonc
{
  "openalex_id": "W1234567890",
  "title": "...",
  "authors": ["..."],
  "publication_year": 2022,
  "doi": "10.xxxx/xxxx",
  "journal": "...",
  "abstract": "...",
  "has_abstract": true,
  "cited_by_count": 12,
  "landing_page_url": "https://...",
  "concepts": ["Ecology", "..."],
  "source": "openalex",
  "ai_analysis": {
    "summary_3lines": ["...", "...", "..."],
    "research_purpose": "...",
    "key_findings": "...",
    "practical_application": "...",
    "applicability_score": 4,
    "applicability_reason": "...",
    "related_tasks": ["탐방로 관리", "..."],
    "related_facilities": ["탐방로", "..."],
    "related_laws": ["자연공원법 등 관련 법령 검토 필요"],
    "field_check_checklist": ["...", "..."],
    "practical_utility_score": 3,
    "cautions": "...",
    "tags": ["생태복원", "탐방객관리"],
    "ai_recommended_papers": ["관련 키워드/주제 제안 (실제 논문 단정 아님)"],
    "follow_up_research_needed": "...",
    "analyzed_at": "2026-07-20T12:00:00+00:00",
    "model": "gemini-2.5-flash-lite"
  }
}
```

## 실행 방법

```bash
# 1. 논문 수집 (Collector)
python openalex_client.py   # 또는 기존 collector.py에서 import해서 사용

# 2. AI 분석 (Enricher) — GEMINI_API_KEY 필요
export GEMINI_API_KEY="your-api-key"
python gemini_enricher.py --input papers.json --limit 50

# 3. 인덱스 생성 (Indexer)
python indexer.py --input papers.json --output index.json
```

## requirements.txt에 추가할 항목

```
requests
google-generativeai
```

GitHub Actions 워크플로에서 requirements.txt 누락으로 실패했던 이력이 있으니,
`pip install -r requirements.txt` 스텝이 워크플로 파일에 반드시 포함되어 있는지
확인하세요. 예:

```yaml
- name: Install dependencies
  run: pip install -r requirements.txt

- name: Enrich papers
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  run: python gemini_enricher.py --input papers.json --limit 50

- name: Build index
  run: python indexer.py --input papers.json --output index.json
```

## 설계상 유의점

1. **Gemini 구조화 출력(response_schema) 사용**
   `gemini_enricher.py`는 `response_mime_type: application/json` +
   `response_schema`를 지정해 Gemini가 정확히 16개 필드를 가진 JSON만
   반환하도록 강제합니다. 이렇게 하면 파싱 실패나 필드 누락 위험이 크게 줄어듭니다.

2. **ai_recommended_papers 필드는 신뢰도 낮음**
   LLM이 실재하지 않는 논문 제목을 만들어낼 수 있습니다. 프론트엔드에
   "AI가 제안하는 후속 검색 키워드" 정도로 표시하고, 실제 관련 논문이
   필요하면 OpenAlex의 `related_works`/`referenced_works` API로 별도 검증하는
   것을 권장합니다.

3. **법령명도 마찬가지로 검증 필요**
   `related_laws`는 프롬프트에서 확실하지 않으면 "관련 법령 검토 필요" 식으로
   완화 표현을 쓰도록 지시했지만, 실무 게시 전에는 사람이 한 번 검수하는
   단계를 두는 것이 안전합니다.

4. **비용/쿼터 관리**
   `enrich_papers_file()`에 `limit` 파라미터가 있어 한 번 실행 시 처리량을
   제한할 수 있습니다. GitHub Actions에서 주기 실행 시 `--limit 30~50` 정도로
   잡고 여러 번 실행에 걸쳐 전체 논문을 분석하는 방식을 권장합니다.

5. **중단 복구**
   `gemini_enricher.py`는 논문 1건 분석할 때마다 즉시 papers.json에 저장하므로,
   Actions 워크플로가 타임아웃/실패해도 이미 분석된 논문은 유실되지 않습니다.
