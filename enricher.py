#!/usr/bin/env python3
"""
Enricher
--------
OpenAI API(gpt-4o-mini)로 논문 초록을 분석해
북한산국립공원 실무 정보를 ai_analysis 필드에 저장합니다.
역할: raw_papers.json 읽기 → AI 분석 → raw_papers.json 업데이트
"""
import json, os, time
from openai import OpenAI

RAW_FILE = "raw_papers.json"

SYSTEM = """당신은 북한산국립공원 관리 전문가입니다.
논문 초록을 분석해 현장 실무자가 논문을 읽지 않아도 바로 업무에 적용할 수 있는
구체적인 정보를 JSON으로 제공합니다. 학술 언어를 실무 언어로 바꿔 서술하세요."""

USER_TMPL = """다음 논문을 분석하세요.

제목: {title}
저자: {authors}
학술지: {journal}  연도: {year}
초록: {abstract}

반드시 아래 JSON 형식으로만 응답하세요 (```json 마크다운 없이):

{{
  "summary_3lines": [
    "1줄: 연구 배경과 목적",
    "2줄: 주요 방법과 결과",
    "3줄: 결론 및 실무 시사점"
  ],
  "research_purpose": "연구 목적을 2~3문장으로 서술",
  "key_findings": ["핵심 결과 1", "핵심 결과 2", "핵심 결과 3"],
  "practical_applications": [
    "실무 적용방안 1 (구체적 행동 중심)",
    "실무 적용방안 2",
    "실무 적용방안 3"
  ],
  "bukhansan_applicability_score": 4,
  "bukhansan_applicability_reason": "북한산 지형·생태·탐방 특성을 근거로 적용 가능한 이유 서술",
  "related_work_areas": ["탐방로 관리", "생태계 모니터링"],
  "related_laws": ["자연공원법 제00조", "야생생물 보호 및 관리에 관한 법률 제00조"],
  "field_checklist": [
    "체크항목 1 (측정·확인 가능한 수준으로)",
    "체크항목 2",
    "체크항목 3",
    "체크항목 4",
    "체크항목 5"
  ],
  "practical_utility_score": 4,
  "cautions": ["주의사항 1 (예산·법령·계절 제약 등)", "주의사항 2"],
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
  "recommended_followup_research": ["후속 연구 필요 내용 1", "후속 연구 필요 내용 2"],
  "ai_recommended_topics": ["유사 연구 검색 키워드 1", "유사 연구 검색 키워드 2"]
}}

점수 기준
- bukhansan_applicability_score: 1(무관)~5(직접 관련)
- practical_utility_score: 1(활용 어려움)~5(즉시 적용 가능)

참고 법령: 자연공원법, 국립공원공단법, 문화재보호법, 야생생물 보호 및 관리에 관한 법률,
산림자원의 조성 및 관리에 관한 법률, 백두대간 보호에 관한 법률, 환경영향평가법"""


def analyze(client: OpenAI, paper: dict) -> dict | None:
    abstract = (paper.get("abstract") or "").strip()
    if len(abstract) < 100:
        return None

    prompt = USER_TMPL.format(
        title    = paper.get("title", ""),
        authors  = ", ".join(paper.get("authors", [])[:3]) or "정보 없음",
        journal  = paper.get("journal", "정보 없음"),
        year     = paper.get("year", "정보 없음"),
        abstract = abstract[:3000],
    )
    try:
        resp = client.chat.completions.create(
            model           = "gpt-4o-mini",
            messages        = [
                {"role": "system", "content": SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            temperature     = 0.3,
            max_tokens      = 2500,
            response_format = {"type": "json_object"},
        )
        result = json.loads(resp.choices[0].message.content)
        result["analyzed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result["model"]       = "gpt-4o-mini"
        return result
    except Exception as exc:
        print(f"  [Enricher] 실패: {exc}")
        return None


def run():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Enricher] GEMINI_API_KEY 없음 — 건너뜁니다.")
        return

    client = OpenAI(api_key=api_key)

    with open(RAW_FILE, encoding="utf-8") as f:
        papers = json.load(f)

    pending = [p for p in papers
               if p.get("ai_analysis") is None and len(p.get("abstract", "")) > 100]
    print(f"[Enricher] 분석 대상: {len(pending)}건 / 전체 {len(papers)}건")

    done = 0
    for i, paper in enumerate(papers):
        if paper.get("ai_analysis") is not None:
            continue
        if len(paper.get("abstract", "")) < 100:
            continue

        preview = (paper.get("title") or "")[:50]
        print(f"  [{i+1}/{len(papers)}] {preview}…")

        result = analyze(client, paper)
        if result:
            paper["ai_analysis"] = result
            done += 1

        time.sleep(1.2)   # Rate-limit 방지

        if done > 0 and done % 10 == 0:
            with open(RAW_FILE, "w", encoding="utf-8") as f:
                json.dump(papers, f, ensure_ascii=False, indent=2)
            print(f"  [Enricher] 중간 저장 ({done}건 완료)")

    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    print(f"[Enricher] 완료: {done}건 분석됨")


if __name__ == "__main__":
    run()
