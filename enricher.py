#!/usr/bin/env python3
"""
Enricher
--------
Google Gemini API(gemini-2.5-flash-lite)로 논문 초록을 분석해
1) 초록 한글 번역(abstract_ko)
2) 국립공원 실무 정보(ai_analysis)
를 함께 생성합니다.
역할: raw_papers.json 읽기 → AI 번역·분석 → raw_papers.json 업데이트
"""
import json, os, time, re
import requests

RAW_FILE = "raw_papers.json"
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

SYSTEM = """당신은 국립공원(한국 국립공원 포함) 관리 실무 전문가입니다.
해외 학술논문의 초록을 분석해 한국 국립공원 현장 실무자가 논문을 읽지 않아도
바로 업무에 적용할 수 있는 구체적인 정보를 JSON으로 제공합니다.
또한 초록 전체를 자연스러운 한국어로 번역합니다. 학술 언어를 실무 언어로 바꿔 서술하세요."""

USER_TMPL = """다음 해외 국립공원 관련 논문을 분석하세요.

제목: {title}
저자: {authors}
학술지: {journal}  연도: {year}
초록(원문): {abstract}

반드시 아래 JSON 형식으로만 응답하세요 (```json 마크다운 없이, 다른 설명 없이 JSON 객체만):

{{
  "title_ko": "논문 제목을 자연스러운 한국어로 번역한 내용",
  "abstract_ko": "초록 전체를 자연스러운 한국어로 번역한 내용",
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
  "korea_np_applicability_score": 4,
  "korea_np_applicability_reason": "한국 국립공원의 지형·생태·탐방 특성을 근거로 적용 가능한 이유 서술",
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
- korea_np_applicability_score: 1(무관)~5(직접 관련)
- practical_utility_score: 1(활용 어려움)~5(즉시 적용 가능)

참고 법령: 자연공원법, 국립공원공단법, 문화재보호법, 야생생물 보호 및 관리에 관한 법률,
산림자원의 조성 및 관리에 관한 법률, 백두대간 보호에 관한 법률, 환경영향평가법"""


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```json\s*|^```\s*|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def analyze(api_key: str, paper: dict) -> dict | None:
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

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 3000,
            "responseMimeType": "application/json",
        },
    }

    try:
        r = requests.post(
            GEMINI_URL,
            params={"key": api_key},
            json=body,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = extract_json(text)
        result["analyzed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result["model"]       = GEMINI_MODEL
        return result
    except Exception as exc:
        print(f"  [Enricher] 실패: {exc}")
        return None


def run():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Enricher] GEMINI_API_KEY 없음 — 건너뜁니다.")
        return

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

        result = analyze(api_key, paper)
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
