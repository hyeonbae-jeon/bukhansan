"""
main.py — 파이프라인 진입점
Collector → Enricher → Indexer → papers.json 저장
"""
import json, os
from datetime import datetime, timezone

from collector import collect_from_openalex, collect_from_naver, merge_papers
from enricher  import enrich_all
from indexer   import build_index

PAPERS_JSON     = "papers.json"
STATE_JSON      = "fetch_state.json"
MAX_OPENALEX    = int(os.environ.get("MAX_OPENALEX", 200))
MAX_NAVER       = int(os.environ.get("MAX_NAVER", 100))
OPENALEX_EMAIL  = os.environ.get("OPENALEX_EMAIL", "")


def load_existing() -> list:
    if os.path.exists(PAPERS_JSON):
        with open(PAPERS_JSON, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("papers", [])
    return []


def save_output(result: dict):
    result["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(PAPERS_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    # 상태 파일
    state = {"last_run": result["updated_at"], "total": result["stats"]["total"]}
    with open(STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"[Main] papers.json 저장 완료 ({result['stats']['total']}건)")


if __name__ == "__main__":
    print("=== 북한산 실무 AI 지식 플랫폼 — 파이프라인 시작 ===")

    # 1. Collect
    existing  = load_existing()
    openalex  = collect_from_openalex(max_results=MAX_OPENALEX, email=OPENALEX_EMAIL)
    naver     = collect_from_naver(max_results=MAX_NAVER)
    papers    = merge_papers(existing, openalex + naver)

    # 2. Enrich (Gemini)
    papers    = enrich_all(papers)

    # 3. Index
    result    = build_index(papers)

    # 4. Save
    save_output(result)
    print("=== 파이프라인 완료 ===")
