"""
enricher.py — AI 분석 모듈 (Google Gemini)
논문 초록을 분석하여 14개 실무 정보를 생성합니다.
무료 한도: gemini-2.5-flash-lite 기준 하루 1,000회 요청 (신용카드 불필요)
"""
import json, time, re, os
import google.generativeai as genai

MODEL_NAME        = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
RATE_LIMIT_DELAY  = 4   # 초 (무료 티어: 15 RPM → 4초 간격)
MAX_ABSTRACT_CHARS = 2000

PROMPT = """당신은 북한산국립공원 관리 전문가입니다.
아래 논문 정보를 분석하여 현장 실무자가 논문을 읽지 않아도 바로 활용할 수 있는 정보를 JSON으로 생성하세요.

논문 제목: {title}
발행연도: {year}
카테고리: {category}
초록:
{abstract}

아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
  "summary_3lines": ["핵심 내용 1줄", "핵심 내용 2줄", "핵심 내용 3줄"],
  "research_purpose": "연구 목적을 1~2문장으로",
  "key_findings": ["핵심 결과 1", "핵심 결과 2", "핵심 결과 3"],
  "practical_applications": ["실무 적용 방안 1", "실무 적용 방안 2", "실무 적용 방안 3"],
  "bukhansan_applicability_score": 3,
  "applicability_reason": "북한산에 적용 가능한 구체적 이유 1~2문장",
  "related_tasks": ["탐방로 관리", "생태계 모니터링"],
  "related_laws": ["자연공원법 제00조 (내용)", "관련 법령명"],
  "field_checklist": ["현장 점검 항목 1", "현장 점검 항목 2", "현장 점검 항목 3"],
  "practical_utility_score": 3,
  "cautions": ["적용 시 주의사항 1", "주의사항 2"],
  "tags": ["태그1", "태그2", "태그3", "태그4"],
  "recommended_papers": ["추천 논문 주제/키워드 1", "추천 논문 주제/키워드 2"],
  "future_research": ["후속 연구 필요 내용 1", "후속 연구 필요 내용 2"]
}}

점수 기준:
- bukhansan_applicability_score: 1(거의 무관) 2(간접 참고) 3(부분 적용 가능) 4(높은 적용성) 5(즉시 직접 적용)
- practical_utility_score: 1(학술 참고만) 2(정책 참고) 3(중기 활용 가능) 4(단기 적용 가능) 5(즉시 현장 적용)

모든 내용은 반드시 한국어로, 북한산국립공원 실무 맥락에 맞게 구체적으로 작성하세요."""


def _default_analysis(reason: str = "") -> dict:
    return {
        "summary_3lines": ["분석 정보 없음"],
        "research_purpose": reason or "초록 정보 부족으로 분석 불가",
        "key_findings": [],
        "practical_applications": [],
        "bukhansan_applicability_score": 0,
        "applicability_reason": "",
        "related_tasks": [],
        "related_laws": [],
        "field_checklist": [],
        "practical_utility_score": 0,
        "cautions": [],
        "tags": [],
        "recommended_papers": [],
        "future_research": [],
    }


def enrich_paper(paper: dict, model) -> dict:
    """논문 1건 분석"""
    abstract = (paper.get("abstract") or "").strip()
    if len(abstract) < 50:
        paper["ai_analysis"] = _default_analysis("초록 없음 또는 너무 짧음")
        return paper

    prompt = PROMPT.format(
        title    = paper.get("title", "제목 없음"),
        year     = paper.get("year", ""),
        category = paper.get("category", ""),
        abstract = abstract[:MAX_ABSTRACT_CHARS],
    )

    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            # JSON 블록 추출
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                analysis = json.loads(m.group())
                paper["ai_analysis"] = analysis
                paper["ai_analyzed"] = True
                return paper
            else:
                raise ValueError("JSON 블록을 찾을 수 없음")
        except Exception as e:
            print(f"    시도 {attempt+1}/3 실패: {e}")
            if attempt < 2:
                time.sleep(RATE_LIMIT_DELAY * (attempt + 1))

    paper["ai_analysis"] = _default_analysis("Gemini 응답 파싱 실패")
    return paper


def enrich_all(papers: list) -> list:
    """전체 논문 목록 Gemini 분석"""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("[Enricher] GEMINI_API_KEY 없음 → AI 분석 건너뜀")
        return papers

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        MODEL_NAME,
        generation_config={"response_mime_type": "application/json"},
    )

    todo = [p for p in papers if not p.get("ai_analyzed")]
    total = len(papers)
    print(f"[Enricher] 분석 대상: {len(todo)}건 / 전체: {total}건")
    print(f"[Enricher] 모델: {MODEL_NAME}  요청 간격: {RATE_LIMIT_DELAY}s")

    for i, paper in enumerate(papers):
        if paper.get("ai_analyzed"):
            continue
        label = paper.get("title", "")[:45]
        print(f"  [{i+1}/{total}] {label}...")
        papers[i] = enrich_paper(paper, model)
        time.sleep(RATE_LIMIT_DELAY)

    analyzed = sum(1 for p in papers if p.get("ai_analyzed"))
    print(f"[Enricher] 완료: {analyzed}/{total}건 분석")
    return papers
