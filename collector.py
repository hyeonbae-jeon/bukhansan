"""
collector.py — 논문 수집 모듈
- Primary  : OpenAlex REST API (안정적, 무료)
- Fallback : 네이버 학술정보 스크래핑
"""
import time, re, json, os
import requests
from bs4 import BeautifulSoup

OPENALEX_BASE  = "https://api.openalex.org/works"
NAVER_BASE     = "https://academic.naver.com/search.naver"
HEADERS        = {"User-Agent": "BukhansanArchive/3.0 (mailto:{email})"}
QUERY_KEYWORDS = [
    "북한산", "bukhansan", "Bukhansan National Park",
    "북한산국립공원", "bukhansan mountain"
]
CATEGORY_RULES = {
    "생태·식생": ["식생","식물","군락","서식","생태","flora","vegetation","plant","species","habitat"],
    "탐방·이용": ["탐방","이용","방문","관광","trailhead","visitor","recreation","hiking","trail"],
    "토양·지질": ["토양","침식","지질","암석","soil","erosion","geology","rock","sediment"],
    "수문·수질": ["수질","하천","강우","유출","water","stream","runoff","hydrology","watershed"],
    "대기·기후": ["기후","기온","강수","대기","climate","temperature","precipitation","atmosphere"],
    "야생동물":  ["동물","조류","포유류","곤충","fauna","bird","mammal","insect","wildlife"],
    "문화·역사": ["문화","역사","유적","cultural","heritage","historical"],
    "관리·정책": ["관리","정책","보전","복원","management","policy","conservation","restoration"],
}

def _categorize(title: str, abstract: str) -> str:
    text = (title + " " + abstract).lower()
    for cat, kws in CATEGORY_RULES.items():
        if any(k in text for k in kws):
            return cat
    return "기타"

def collect_from_openalex(max_results: int = 200, email: str = "") -> list:
    """OpenAlex API로 논문 수집"""
    papers, seen_ids = [], set()
    h = HEADERS.copy()
    if email:
        h["User-Agent"] = h["User-Agent"].format(email=email)
    else:
        h["User-Agent"] = "BukhansanArchive/3.0"

    for keyword in QUERY_KEYWORDS:
        if len(papers) >= max_results:
            break
        cursor = "*"
        while len(papers) < max_results:
            params = {
                "search": keyword,
                "filter": "type:article",
                "sort": "cited_by_count:desc",
                "per-page": 50,
                "cursor": cursor,
                "select": "id,title,abstract_inverted_index,publication_year,"
                          "authorships,primary_location,doi,cited_by_count,"
                          "open_access,concepts",
            }
            try:
                r = requests.get(OPENALEX_BASE, params=params, headers=h, timeout=15)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                print(f"  [Collector/OpenAlex] 오류: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for w in results:
                oa_id = w.get("id", "")
                if oa_id in seen_ids:
                    continue
                seen_ids.add(oa_id)

                # 초록 복원 (inverted index → 문자열)
                inv = w.get("abstract_inverted_index") or {}
                abstract = ""
                if inv:
                    words = {pos: word for word, positions in inv.items() for pos in positions}
                    abstract = " ".join(words[i] for i in sorted(words))

                authors = [
                    a["author"]["display_name"]
                    for a in w.get("authorships", [])
                    if a.get("author", {}).get("display_name")
                ]
                loc = w.get("primary_location") or {}
                source = loc.get("source") or {}
                journal = source.get("display_name", "")
                doi = w.get("doi", "")
                url = f"https://doi.org/{doi.replace('https://doi.org/','')}" if doi else w.get("id","")
                year = w.get("publication_year") or 0
                concepts = [c["display_name"] for c in w.get("concepts", [])[:5]]

                papers.append({
                    "id": oa_id,
                    "source": "openalex",
                    "title": w.get("title", "제목 없음"),
                    "abstract": abstract,
                    "year": year,
                    "authors": authors[:5],
                    "journal": journal,
                    "doi": doi,
                    "url": url,
                    "citations": w.get("cited_by_count", 0),
                    "is_oa": w.get("open_access", {}).get("is_oa", False),
                    "category": _categorize(w.get("title",""), abstract),
                    "keywords": concepts,
                    "ai_analysis": None,
                    "ai_analyzed": False,
                })

            meta = data.get("meta", {})
            cursor = meta.get("next_cursor")
            if not cursor:
                break
            time.sleep(0.5)

    print(f"[Collector/OpenAlex] {len(papers)}건 수집")
    return papers


def collect_from_naver(query: str = "북한산", max_results: int = 100) -> list:
    """네이버 학술정보 스크래핑 (fallback)"""
    papers, seen = [], set()
    page = 1
    while len(papers) < max_results:
        params = {"field": 0, "docType": 1, "query": query, "page": page}
        try:
            r = requests.get(NAVER_BASE, params=params,
                             headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"  [Collector/Naver] 오류: {e}")
            break

        items = soup.select("div.ui_listing_info")
        if not items:
            break

        for item in items:
            a_tag = item.select_one("h4 a.ui_listing_subtit")
            if not a_tag:
                continue
            title = a_tag.get_text(strip=True)
            href  = a_tag.get("href", "")
            url   = f"https://academic.naver.com{href}" if href.startswith("/") else href
            if url in seen:
                continue
            seen.add(url)

            spans = item.select("div.ui_listing_desc span.ui_listing_source")
            year, authors, journal = 0, [], ""
            for sp in spans:
                txt = sp.get_text(strip=True)
                if re.match(r"^\d{4}$", txt):
                    year = int(txt)
                elif sp.select_one("a"):
                    journal = txt
                else:
                    authors.append(txt)

            cited_el = item.select_one("span.ui_listing_cited_num")
            citations = int(re.sub(r"\D", "", cited_el.get_text()) or 0) if cited_el else 0

            papers.append({
                "id": f"naver:{hash(url) & 0xFFFFFF:06x}",
                "source": "naver",
                "title": title,
                "abstract": "",
                "year": year,
                "authors": authors[:5],
                "journal": journal,
                "doi": "",
                "url": url,
                "citations": citations,
                "is_oa": False,
                "category": _categorize(title, ""),
                "keywords": [],
                "ai_analysis": None,
                "ai_analyzed": False,
            })

        page += 1
        time.sleep(1)

    print(f"[Collector/Naver] {len(papers)}건 수집")
    return papers


def merge_papers(existing: list, new_papers: list) -> list:
    """중복 제거 후 병합 (기존 ai_analysis 보존)"""
    existing_map = {p["id"]: p for p in existing}
    for p in new_papers:
        if p["id"] not in existing_map:
            existing_map[p["id"]] = p
        else:
            # 기존 AI 분석 보존
            old = existing_map[p["id"]]
            p["ai_analysis"]  = old.get("ai_analysis")
            p["ai_analyzed"]  = old.get("ai_analyzed", False)
            existing_map[p["id"]] = p
    merged = list(existing_map.values())
    merged.sort(key=lambda x: x.get("citations", 0), reverse=True)
    print(f"[Collector] 병합 결과: {len(merged)}건")
    return merged
