#!/usr/bin/env python3
"""
Collector
---------
OpenAlex REST API에서 해외 국립공원 관리·연구 관련 논문을 수집합니다.
역할: 검색 → 정규화 → raw_papers.json에 누적 저장
"""
import requests, json, os, time
from datetime import datetime

OPENALEX = "https://api.openalex.org"
RAW_FILE  = "raw_papers.json"
STATE_FILE = "fetch_state.json"

# 국립공원 실무(탐방로 관리, 생태계 모니터링, 방문객 관리 등) 관련 검색어
# 특정 공원명이 아니라 국립공원 관리 전반의 해외 연구를 폭넓게 수집
QUERIES = [
    "national park trail management",
    "national park visitor management",
    "national park ecosystem monitoring",
    "national park biodiversity conservation",
    "national park trail erosion",
    "national park wildlife management",
    "protected area management effectiveness",
    "national park climate change adaptation",
    "national park carrying capacity",
    "national park invasive species management",
    "national park fire management",
    "national park recreation ecology",
    "protected area governance",
    "national park restoration ecology",
    "national park human wildlife conflict",
]


def reconstruct_abstract(inv: dict) -> str:
    """OpenAlex abstract_inverted_index → 일반 텍스트 변환"""
    if not inv:
        return ""
    pos: dict[int, str] = {}
    for word, positions in inv.items():
        for p in positions:
            pos[p] = word
    return " ".join(pos[i] for i in sorted(pos))


def normalize(raw: dict) -> dict:
    loc = raw.get("primary_location") or {}
    src = loc.get("source") or {}
    oa  = raw.get("open_access") or {}
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in raw.get("authorships", [])
    ]
    concepts = [c.get("display_name", "") for c in raw.get("concepts", [])[:6]]
    return {
        "id":             raw.get("id", "").split("/")[-1],
        "source":         "openalex",
        "title":          raw.get("title") or "",
        "abstract":       reconstruct_abstract(raw.get("abstract_inverted_index") or {}),
        "authors":        [a for a in authors if a],
        "year":           raw.get("publication_year"),
        "journal":        src.get("display_name", ""),
        "cited_by_count": raw.get("cited_by_count", 0),
        "doi":            raw.get("doi") or "",
        "is_oa":          oa.get("is_oa", False),
        "oa_url":         oa.get("oa_url") or "",
        "concepts":       concepts,
        "openalex_url":   raw.get("id", ""),
        "ai_analysis":    None,
    }


def fetch_query(query: str, email: str = "", limit: int = 100) -> list:
    papers, cursor = [], "*"
    select = (
        "id,title,abstract_inverted_index,authorships,"
        "publication_year,primary_location,cited_by_count,"
        "concepts,open_access,doi"
    )
    while len(papers) < limit:
        batch  = min(25, limit - len(papers))
        params = {
            "search":   query,
            "filter":   "has_abstract:true",
            "per-page": batch,
            "cursor":   cursor,
            "select":   select,
        }
        if email:
            params["mailto"] = email
        try:
            r = requests.get(f"{OPENALEX}/works", params=params, timeout=30)
            r.raise_for_status()
            data    = r.json()
            results = data.get("results", [])
            if not results:
                break
            for item in results:
                n = normalize(item)
                if n["title"]:
                    papers.append(n)
            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.35)
        except Exception as exc:
            print(f"[Collector] 오류 ({query[:30]}): {exc}")
            break
    return papers


def run():
    email = os.getenv("OPENALEX_EMAIL", "")

    existing: dict[str, dict] = {}
    if os.path.exists(RAW_FILE):
        with open(RAW_FILE, encoding="utf-8") as f:
            for p in json.load(f):
                existing[p["id"]] = p

    before = len(existing)

    for q in QUERIES:
        print(f"[Collector] 검색: {q}")
        for p in fetch_query(q, email=email):
            if p["id"] not in existing:
                existing[p["id"]] = p
        time.sleep(1)

    papers = list(existing.values())
    with open(RAW_FILE, "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    state = {
        "last_run":    datetime.now().isoformat(),
        "total_papers": len(papers),
        "new_papers":  len(papers) - before,
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    print(f"[Collector] 완료: 총 {len(papers)}건 (신규 {len(papers) - before}건)")


if __name__ == "__main__":
    run()
