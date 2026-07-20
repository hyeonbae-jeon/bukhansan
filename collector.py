"""
collector.py
-------------
Collector 단계 실행 스크립트.
여러 검색어로 OpenAlex를 조회해 북한산(국립공원) 관련 논문을 수집하고,
기존 papers.json에 없는 논문만 추가해서 저장한다 (중복 방지, 기존 ai_analysis 보존).
"""

from __future__ import annotations

import json
import os

from openalex_client import search_papers

# 검색 키워드 목록. 필요에 따라 추가/수정하세요.
SEARCH_QUERIES = [
    "Bukhansan National Park",
    "Bukhansan national park management",
    "Korea national park visitor management",
    "Korea national park ecological restoration",
    "Korea national park trail management",
]

PAPERS_PATH = os.environ.get("PAPERS_PATH", "papers.json")


def load_existing(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def collect() -> None:
    existing = load_existing(PAPERS_PATH)
    existing_ids = {p["openalex_id"] for p in existing if p.get("openalex_id")}

    new_records: list[dict] = []
    for query in SEARCH_QUERIES:
        print(f"[collector] 검색: {query}")
        results = search_papers(query, per_page=25, max_pages=2)
        for r in results:
            if r["openalex_id"] not in existing_ids:
                new_records.append(r)
                existing_ids.add(r["openalex_id"])

    combined = existing + new_records
    with open(PAPERS_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"[collector] 신규 {len(new_records)}건 추가, 총 {len(combined)}건 저장 -> {PAPERS_PATH}")


if __name__ == "__main__":
    collect()
