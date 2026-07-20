"""
indexer.py
-----------
Indexer 단계: papers.json의 ai_analysis 필드를 바탕으로
Frontend에서 바로 쓸 수 있는 검색/필터/통계용 인덱스(index.json)를 생성한다.

Frontend는 papers.json 전체를 매번 훑지 않고, 이 index.json으로
빠르게 필터링 옵션(태그, 업무, 시설, 법령 등)과 통계를 그려준다.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any


def _count_field(papers: list[dict[str, Any]], field: str) -> Counter:
    counter: Counter = Counter()
    for paper in papers:
        analysis = paper.get("ai_analysis")
        if not analysis:
            continue
        values = analysis.get(field) or []
        counter.update(values)
    return counter


def build_index(papers: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = [p for p in papers if p.get("ai_analysis")]
    unanalyzed_count = len(papers) - len(analyzed)

    applicability_scores = [
        a["ai_analysis"]["applicability_score"] for a in analyzed
        if "applicability_score" in a["ai_analysis"]
    ]
    utility_scores = [
        a["ai_analysis"]["practical_utility_score"] for a in analyzed
        if "practical_utility_score" in a["ai_analysis"]
    ]

    index = {
        "generated_at": None,  # 호출부에서 채움
        "stats": {
            "total_papers": len(papers),
            "analyzed_papers": len(analyzed),
            "unanalyzed_papers": unanalyzed_count,
            "avg_applicability_score": round(
                sum(applicability_scores) / len(applicability_scores), 2
            ) if applicability_scores else None,
            "avg_practical_utility_score": round(
                sum(utility_scores) / len(utility_scores), 2
            ) if utility_scores else None,
            "score_distribution": {
                "applicability": dict(Counter(applicability_scores)),
                "practical_utility": dict(Counter(utility_scores)),
            },
        },
        "filters": {
            "tags": _count_field(analyzed, "tags").most_common(),
            "related_tasks": _count_field(analyzed, "related_tasks").most_common(),
            "related_facilities": _count_field(analyzed, "related_facilities").most_common(),
            "related_laws": _count_field(analyzed, "related_laws").most_common(),
        },
        # 검색용 경량 레코드: 논문 전체가 아니라 검색/카드 표시에 필요한 필드만 추림
        "search_records": [
            {
                "openalex_id": p.get("openalex_id"),
                "title": p.get("title"),
                "publication_year": p.get("publication_year"),
                "journal": p.get("journal"),
                "summary_3lines": (p.get("ai_analysis") or {}).get("summary_3lines"),
                "applicability_score": (p.get("ai_analysis") or {}).get("applicability_score"),
                "practical_utility_score": (p.get("ai_analysis") or {}).get("practical_utility_score"),
                "tags": (p.get("ai_analysis") or {}).get("tags", []),
                "related_tasks": (p.get("ai_analysis") or {}).get("related_tasks", []),
            }
            for p in analyzed
        ],
    }
    return index


def build_index_file(papers_path: str, index_output_path: str) -> None:
    from datetime import datetime, timezone

    with open(papers_path, "r", encoding="utf-8") as f:
        papers = json.load(f)

    index = build_index(papers)
    index["generated_at"] = datetime.now(timezone.utc).isoformat()

    with open(index_output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"[indexer] index.json 생성 완료: {index_output_path}")
    print(f"[indexer] 분석 완료 {index['stats']['analyzed_papers']}/{index['stats']['total_papers']}건")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="papers.json -> index.json 생성")
    parser.add_argument("--input", default="papers.json")
    parser.add_argument("--output", default="index.json")
    args = parser.parse_args()

    build_index_file(args.input, args.output)
