"""
openalex_client.py
-------------------
OpenAlex API(https://openalex.org)를 통해 논문 메타데이터와 초록(Abstract)을 수집하는 모듈.

OpenAlex는 초록을 그대로 주지 않고 'abstract_inverted_index' 형태
(단어 -> 등장 위치 리스트)로 제공하므로, 이를 원문 순서로 복원하는
reconstruct_abstract() 함수가 핵심이다.

Collector 단계에서 이 모듈을 사용해 papers.json에 넣을 원본 레코드를 만든다.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

import requests

OPENALEX_BASE_URL = "https://api.openalex.org/works"
# OpenAlex는 이메일을 붙여 요청하면 'polite pool'로 우선 처리해준다 (권장).
USER_AGENT_EMAIL = "jhb1226@naver.com"  # TODO: 실제 연락처 이메일로 교체


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex의 abstract_inverted_index를 원문 순서의 문자열로 복원한다.

    inverted_index 예시:
        {"National": [0], "parks": [1], "in": [2], "Korea": [3], ...}

    Returns:
        복원된 초록 문자열. inverted_index가 없으면 빈 문자열.
    """
    if not inverted_index:
        return ""

    position_word: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word[pos] = word

    if not position_word:
        return ""

    max_pos = max(position_word.keys())
    words = [position_word.get(i, "") for i in range(max_pos + 1)]
    return " ".join(w for w in words if w)


def _to_record(work: dict[str, Any]) -> dict[str, Any]:
    """OpenAlex work 객체를 papers.json에 저장할 표준 레코드로 변환한다."""
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    authorships = work.get("authorships", []) or []
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in authorships
        if a.get("author")
    ]

    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}

    return {
        "openalex_id": work.get("id", "").replace("https://openalex.org/", ""),
        "title": work.get("display_name") or work.get("title") or "",
        "authors": authors,
        "publication_year": work.get("publication_year"),
        "doi": work.get("doi"),
        "journal": source.get("display_name"),
        "abstract": abstract,
        "has_abstract": bool(abstract),
        "cited_by_count": work.get("cited_by_count", 0),
        "landing_page_url": primary_location.get("landing_page_url"),
        "concepts": [
            c.get("display_name")
            for c in (work.get("concepts") or [])
            if c.get("score", 0) >= 0.3
        ],
        "source": "openalex",
        "ai_analysis": None,  # Enricher 단계에서 채워짐
    }


def search_papers(
    query: str,
    per_page: int = 25,
    max_pages: int = 4,
    filter_has_abstract: bool = True,
) -> list[dict[str, Any]]:
    """키워드로 OpenAlex 논문을 검색하고 표준 레코드 리스트로 반환한다.

    Args:
        query: 검색어 (예: "Bukhansan National Park")
        per_page: 페이지당 결과 수 (최대 200)
        max_pages: 최대 페이지 수 (rate limit 보호용)
        filter_has_abstract: True면 초록이 있는 논문만 요청 (has_abstract 필터)
    """
    records: list[dict[str, Any]] = []
    cursor = "*"

    params = {
        "search": query,
        "per-page": per_page,
        "cursor": cursor,
        "mailto": USER_AGENT_EMAIL,
    }
    if filter_has_abstract:
        params["filter"] = "has_abstract:true"

    for _ in range(max_pages):
        params["cursor"] = cursor
        resp = requests.get(OPENALEX_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for work in data.get("results", []):
            records.append(_to_record(work))

        cursor = (data.get("meta") or {}).get("next_cursor")
        if not cursor:
            break

        time.sleep(0.2)  # OpenAlex rate limit 배려 (초당 요청 제한)

    return records


def get_work_by_id(openalex_id: str) -> dict[str, Any] | None:
    """단일 논문을 openalex_id로 조회한다 (재수집/보강용)."""
    url = f"{OPENALEX_BASE_URL}/{openalex_id}"
    resp = requests.get(url, params={"mailto": USER_AGENT_EMAIL}, timeout=30)
    if resp.status_code != 200:
        return None
    return _to_record(resp.json())


if __name__ == "__main__":
    # 간단한 동작 확인용
    results = search_papers("Bukhansan National Park", per_page=5, max_pages=1)
    for r in results:
        print(r["title"], "-", r["has_abstract"])
