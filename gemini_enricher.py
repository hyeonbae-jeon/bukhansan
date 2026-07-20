"""
gemini_enricher.py
--------------------
Enricher 단계: OpenAlex 초록(Abstract)을 Gemini API로 분석하여
국립공원 실무자 관점의 ai_analysis 객체를 생성하고 papers.json에 병합한다.

요구되는 ai_analysis 스키마 (16개 항목):
  - summary_3lines            : 3줄 핵심요약 (리스트, 정확히 3개 문장)
  - research_purpose          : 연구목적
  - key_findings               : 핵심결과
  - practical_application      : 실무 적용방안
  - applicability_score        : 우리나라 국립공원 적용 가능성 (1~5)
  - applicability_reason        : 적용 가능한 이유
  - related_tasks               : 관련 업무 (리스트)
  - related_facilities          : 관련 시설 (리스트)
  - related_laws                 : 관련 법령 (리스트)
  - field_check_checklist        : 현장점검 체크리스트 (리스트)
  - practical_utility_score      : 실무 활용도 (1~5)
  - cautions                    : 적용 시 주의사항
  - tags                         : 관련 태그 (리스트)
  - ai_recommended_papers        : AI 추천 논문 (리스트, 아래 주의사항 참고)
  - follow_up_research_needed    : 후속 연구가 필요한 내용

※ ai_recommended_papers 관련 주의:
  Gemini가 실제로 존재하지 않는 논문 제목을 만들어낼(hallucinate) 위험이 있다.
  이 필드는 "이런 주제의 후속 연구를 찾아보면 좋다"는 방향성 제안 정도로만
  프론트엔드에 노출하고, 실제 링크가 필요하면 OpenAlex의 관련 논문 API
  (related_works, referenced_works)로 별도 검증하는 것을 권장한다.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai

MODEL_NAME = "gemini-2.5-flash-lite"

# Gemini structured output을 위한 응답 스키마.
# 이 스키마를 강제하면 파싱 실패/필드 누락 문제를 크게 줄일 수 있다.
AI_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "summary_3lines": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
        "research_purpose": {"type": "string"},
        "key_findings": {"type": "string"},
        "practical_application": {"type": "string"},
        "applicability_score": {"type": "integer"},
        "applicability_reason": {"type": "string"},
        "related_tasks": {"type": "array", "items": {"type": "string"}},
        "related_facilities": {"type": "array", "items": {"type": "string"}},
        "related_laws": {"type": "array", "items": {"type": "string"}},
        "field_check_checklist": {"type": "array", "items": {"type": "string"}},
        "practical_utility_score": {"type": "integer"},
        "cautions": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "ai_recommended_papers": {"type": "array", "items": {"type": "string"}},
        "follow_up_research_needed": {"type": "string"},
    },
    "required": [
        "summary_3lines",
        "research_purpose",
        "key_findings",
        "practical_application",
        "applicability_score",
        "applicability_reason",
        "related_tasks",
        "related_facilities",
        "related_laws",
        "field_check_checklist",
        "practical_utility_score",
        "cautions",
        "tags",
        "ai_recommended_papers",
        "follow_up_research_needed",
    ],
}

SYSTEM_INSTRUCTION = """\
너는 대한민국 국립공원공단에서 근무하는 시니어 정책·현장 실무 분석가다.
해외 학술 논문의 초록(Abstract)을 읽고, 논문을 직접 읽지 않아도 되는
국립공원 실무자가 바로 업무에 활용할 수 있도록 분석 결과를 작성한다.

작성 원칙:
1. 초록에 없는 내용을 지어내지 말 것. 특히 구체적 수치·법령명·시설명은
   초록에서 추론 가능한 범위 내에서만 작성하고, 근거가 약하면 일반적인
   표현으로 완화해서 쓸 것.
2. 모든 텍스트는 한국어로, 실무자가 읽기 쉬운 간결한 문장으로 작성할 것.
3. applicability_score(적용 가능성)와 practical_utility_score(실무 활용도)는
   1~5 정수로, 5에 가까울수록 우리나라 국립공원 현장에 바로 적용 가능함을 의미.
4. related_laws(관련 법령)는 확실하지 않으면 "자연공원법 등 관련 법령 검토 필요"처럼
   신중하게 표현하고, 존재하지 않는 법령명을 지어내지 말 것.
5. ai_recommended_papers는 실제 논문 제목을 단정하지 말고, 어떤 주제/키워드의
   후속 논문을 찾아보면 좋을지 방향성 위주로 제안할 것.
"""


def _build_user_prompt(title: str, abstract: str, journal: str | None, year: int | None) -> str:
    return f"""\
다음 해외 학술 논문의 정보를 분석하여 국립공원 실무 관점의 JSON을 생성하라.

[논문 제목]
{title}

[학술지 / 연도]
{journal or "정보 없음"} / {year or "정보 없음"}

[초록(Abstract)]
{abstract}

위 스키마에 맞춰 실무자가 바로 활용할 수 있는 분석 결과를 JSON으로만 출력하라.
"""


def analyze_paper(
    title: str,
    abstract: str,
    journal: str | None = None,
    year: int | None = None,
    api_key: str | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """단일 논문 초록을 Gemini로 분석해 ai_analysis 딕셔너리를 반환한다."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    prompt = _build_user_prompt(title, abstract, journal, year)

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=AI_ANALYSIS_SCHEMA,
                    temperature=0.3,
                ),
            )
            result = json.loads(response.text)
            result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
            result["model"] = MODEL_NAME
            return result
        except Exception as e:  # noqa: BLE001 - Gemini/네트워크 예외 포괄 처리
            last_error = e
            wait = 2 ** attempt
            print(f"[gemini_enricher] 시도 {attempt}/{max_retries} 실패: {e} -> {wait}초 대기")
            time.sleep(wait)

    raise RuntimeError(f"Gemini 분석 실패 (재시도 {max_retries}회 초과): {last_error}")


def enrich_papers_file(
    papers_path: str,
    output_path: str | None = None,
    limit: int | None = None,
    skip_existing: bool = True,
) -> None:
    """papers.json을 읽어 ai_analysis가 없는 논문을 분석하고 파일에 저장한다.

    Args:
        papers_path: 입력 papers.json 경로
        output_path: 출력 경로 (None이면 papers_path에 덮어씀)
        limit: 이번 실행에서 처리할 최대 논문 수 (Gemini 쿼터 보호용)
        skip_existing: True면 이미 ai_analysis가 있는 논문은 건너뜀
    """
    output_path = output_path or papers_path

    with open(papers_path, "r", encoding="utf-8") as f:
        papers: list[dict[str, Any]] = json.load(f)

    processed = 0
    for paper in papers:
        if limit is not None and processed >= limit:
            break

        if skip_existing and paper.get("ai_analysis"):
            continue

        if not paper.get("abstract"):
            # 초록이 없는 논문은 AI 분석 대상에서 제외 (has_abstract=False)
            continue

        try:
            paper["ai_analysis"] = analyze_paper(
                title=paper.get("title", ""),
                abstract=paper["abstract"],
                journal=paper.get("journal"),
                year=paper.get("publication_year"),
            )
            print(f"[gemini_enricher] 분석 완료: {paper.get('title', '')[:50]}")
        except Exception as e:  # noqa: BLE001
            print(f"[gemini_enricher] 분석 실패, 건너뜀: {paper.get('title', '')[:50]} ({e})")
            continue

        processed += 1
        # papers.json을 매 건마다 저장해 중간에 중단되어도 진행 상황을 보존한다.
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)

    print(f"[gemini_enricher] 총 {processed}건 분석 완료. 저장 위치: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="papers.json의 논문을 Gemini로 실무 분석")
    parser.add_argument("--input", default="papers.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="이미 분석된 논문도 재분석")
    args = parser.parse_args()

    enrich_papers_file(
        papers_path=args.input,
        output_path=args.output,
        limit=args.limit,
        skip_existing=not args.force,
    )
