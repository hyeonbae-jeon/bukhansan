"""
indexer.py — 검색 인덱스 및 통계 구축 모듈
papers 리스트를 받아 검색용 필드와 통계를 추가합니다.
"""
from collections import Counter

def build_index(papers: list) -> dict:
    """papers 리스트 → 검색 인덱스 + 통계가 포함된 최종 객체"""
    for p in papers:
        ai = p.get("ai_analysis") or {}
        tags  = ai.get("tags", [])
        tasks = ai.get("related_tasks", [])
        summary = " ".join(ai.get("summary_3lines", []))

        # 전문 검색용 통합 텍스트
        p["search_text"] = " ".join(filter(None, [
            p.get("title", ""),
            p.get("abstract", ""),
            summary,
            " ".join(tags),
            " ".join(tasks),
            " ".join(p.get("keywords", [])),
            p.get("category", ""),
        ])).lower()

        # 점수 정규화 (0 → None 처리)
        for score_field in ("bukhansan_applicability_score", "practical_utility_score"):
            val = ai.get(score_field, 0)
            if not val:
                ai[score_field] = None

    # 통계
    years      = [p["year"] for p in papers if p.get("year")]
    categories = [p["category"] for p in papers if p.get("category")]
    all_tags   = [t for p in papers for t in (p.get("ai_analysis") or {}).get("tags", [])]
    all_tasks  = [t for p in papers for t in (p.get("ai_analysis") or {}).get("related_tasks", [])]
    bk_scores  = [
        (p.get("ai_analysis") or {}).get("bukhansan_applicability_score")
        for p in papers
        if (p.get("ai_analysis") or {}).get("bukhansan_applicability_score")
    ]
    ut_scores  = [
        (p.get("ai_analysis") or {}).get("practical_utility_score")
        for p in papers
        if (p.get("ai_analysis") or {}).get("practical_utility_score")
    ]

    stats = {
        "total":           len(papers),
        "analyzed":        sum(1 for p in papers if p.get("ai_analyzed")),
        "oa_count":        sum(1 for p in papers if p.get("is_oa")),
        "year_dist":       dict(sorted(Counter(years).items())),
        "category_dist":   dict(Counter(categories).most_common()),
        "top_tags":        dict(Counter(all_tags).most_common(30)),
        "top_tasks":       dict(Counter(all_tasks).most_common(20)),
        "avg_bk_score":    round(sum(bk_scores)/len(bk_scores), 2) if bk_scores else 0,
        "avg_util_score":  round(sum(ut_scores)/len(ut_scores), 2) if ut_scores else 0,
        "high_priority":   sum(1 for s in bk_scores if s and s >= 4),
    }
    print(f"[Indexer] 완료 | 전체 {stats['total']}건 | 분석 {stats['analyzed']}건 | "
          f"평균 적용점수 {stats['avg_bk_score']}")
    return {"papers": papers, "stats": stats}
