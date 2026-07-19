#!/usr/bin/env python3
"""
fetch_papers.py
북한산 관련 논문을 OpenAlex API + 네이버 학술정보에서 수집해 papers.json으로 저장.
GitHub Actions에서 주 1회 자동 실행.
"""

import requests, json, os, time, re, html
from datetime import datetime

# ── 설정 ───────────────────────────────────────────────────────────────────
PAPERS_FILE   = "papers.json"
STATE_FILE    = "fetch_state.json"
OPENALEX_BASE = "https://api.openalex.org"
MAILTO        = os.environ.get("CONTACT_EMAIL", "your-email@example.com")
OPENALEX_KEY  = os.environ.get("OPENALEX_API_KEY", "")   # 무료 키, 없어도 동작(제한↑)

CATEGORIES = {
    "생태": ["식물","동물","생태","서식","수목","조류","포유","곤충","균류","생물","종다양성","식생","군락","개체","생육","분포","멸종","환경","녹지"],
    "재난": ["산사태","화재","산불","붕괴","위험","안전","재난","재해","침식","사면","홍수","낙석"],
    "탐방": ["등산","탐방","방문","탐방객","관광","탐방로","이용","방문객","탐방자","행태","만족","레크리에이션"],
    "자원조사": ["조사","모니터링","현황","분포","밀도","분석","실태","평가","측정","데이터","GIS","원격탐사"],
    "역사문화": ["역사","문화","유적","사찰","불교","민속","전통","경관","문화재","인문","지명","고고"],
}

SEARCH_KEYWORDS = [
    "Bukhansan", "Bukhan Mountain", "Buk-han mountain",
    "Bukhansan National Park", "Seoul national park ecology",
]

def categorize(title: str, abstract: str) -> str:
    text = (title + " " + abstract).lower()
    scores = {cat: sum(text.count(w) for w in words) for cat, words in CATEGORIES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "기타"

def reconstruct_abstract(inv_idx: dict) -> str:
    """OpenAlex inverted-index → 평문 초록"""
    if not inv_idx:
        return ""
    pairs = []
    for word, positions in inv_idx.items():
        for p in positions:
            pairs.append((p, word))
    pairs.sort()
    return " ".join(w for _, w in pairs)

# ── OpenAlex ───────────────────────────────────────────────────────────────
def fetch_openalex() -> list:
    all_papers, seen = [], set()
    headers = {"mailto": MAILTO}
    if OPENALEX_KEY:
        headers["api_key"] = OPENALEX_KEY

    SELECT = ",".join([
        "id","title","abstract_inverted_index","authorships",
        "publication_year","primary_location","cited_by_count",
        "open_access","concepts","doi","type","biblio"
    ])

    for kw in SEARCH_KEYWORDS:
        for page in range(1, 4):   # 최대 3페이지(=600건)
            params = {
                "search": kw,
                "filter": "is_paratext:false",
                "select": SELECT,
                "per-page": 200,
                "page": page,
            }
            try:
                r = requests.get(f"{OPENALEX_BASE}/works", params=params,
                                 headers=headers, timeout=30)
                r.raise_for_status()
                data = r.json()
                results = data.get("results", [])
                if not results:
                    break

                for w in results:
                    wid = w.get("id", "")
                    if wid in seen:
                        continue
                    seen.add(wid)

                    abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
                    authors  = [a["author"]["display_name"]
                                for a in w.get("authorships", [])[:6]
                                if a.get("author", {}).get("display_name")]
                    institutions = list({
                        inst["display_name"]
                        for a in w.get("authorships", [])
                        for inst in a.get("institutions", [])
                        if inst.get("display_name")
                    })[:3]

                    src   = (w.get("primary_location") or {}).get("source") or {}
                    doi   = (w.get("doi") or "").replace("https://doi.org/", "")
                    url   = f"https://doi.org/{doi}" if doi else wid

                    title = w.get("title") or ""
                    paper = {
                        "id":              wid,
                        "title":           title,
                        "authors":         ", ".join(authors),
                        "institutions":    ", ".join(institutions),
                        "year":            str(w.get("publication_year") or ""),
                        "journal":         src.get("display_name", ""),
                        "journal_type":    src.get("type", ""),
                        "abstract":        abstract,
                        "category":        categorize(title, abstract),
                        "url":             url,
                        "doi":             doi,
                        "cited_by_count":  w.get("cited_by_count", 0),
                        "is_open_access":  (w.get("open_access") or {}).get("is_oa", False),
                        "oa_url":          (w.get("open_access") or {}).get("oa_url", ""),
                        "type":            w.get("type", ""),
                        "concepts":        [c["display_name"] for c in w.get("concepts", [])[:6]],
                        "source":          "OpenAlex",
                        "fetched_at":      datetime.utcnow().isoformat(),
                    }
                    all_papers.append(paper)

                time.sleep(0.3)
                if len(results) < 200:
                    break
            except Exception as e:
                print(f"[OpenAlex] '{kw}' p{page} 오류: {e}")
                break

    print(f"[OpenAlex] {len(all_papers)}건 수집 완료")
    return all_papers

# ── 네이버 학술정보(스크래핑, fallback) ─────────────────────────────────────
def fetch_naver() -> list:
    """네이버 학술정보 스크래핑 (IP 차단 시 빈 리스트 반환)"""
    from urllib.parse import quote
    NAVER_QUERIES = ["북한산", "북한산 생태", "북한산 탐방", "북한산 식물"]
    papers, seen = [], set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    for q in NAVER_QUERIES:
        for page in range(1, 6):
            url = (f"https://academic.naver.com/search.naver?"
                   f"query={quote(q)}&offset={(page-1)*10}&display=10&sort=0")
            try:
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code != 200 or "검색 결과가 없습니다" in r.text:
                    break
                # 제목·링크 파싱 (간단한 정규식)
                titles = re.findall(r'class="title"[^>]*>([^<]+)<', r.text)
                links  = re.findall(r'href="(https://academic\.naver\.com/article\.naver\?[^"]+)"', r.text)
                for title, link in zip(titles, links):
                    if link in seen:
                        continue
                    seen.add(link)
                    papers.append({
                        "id": link, "title": html.unescape(title.strip()),
                        "authors": "", "institutions": "", "year": "",
                        "journal": "", "journal_type": "", "abstract": "",
                        "category": "기타", "url": link, "doi": "",
                        "cited_by_count": 0, "is_open_access": False,
                        "oa_url": "", "type": "article",
                        "concepts": [], "source": "Naver",
                        "fetched_at": datetime.utcnow().isoformat(),
                    })
                time.sleep(1.5)
            except Exception as e:
                print(f"[Naver] '{q}' p{page} 오류: {e}")
                break
    print(f"[Naver] {len(papers)}건 수집 완료")
    return papers

# ── 메인 ───────────────────────────────────────────────────────────────────
def main():
    # 기존 데이터 로드
    existing = {}
    if os.path.exists(PAPERS_FILE):
        try:
            for p in json.load(open(PAPERS_FILE, encoding="utf-8")):
                existing[p["id"]] = p
        except Exception:
            pass

    new_papers = fetch_openalex() + fetch_naver()

    for p in new_papers:
        existing[p["id"]] = p

    result = sorted(existing.values(),
                    key=lambda x: int(x.get("year") or 0), reverse=True)

    with open(PAPERS_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n papers.json 저장 완료: 총 {len(result)}건")

    # 상태 기록
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_run": datetime.utcnow().isoformat(),
                   "total": len(result)}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
