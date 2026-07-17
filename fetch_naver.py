"""
북한산 관련 논문/자료를 네이버 "전문자료 검색"(doc) API에서 수집해 papers.json으로 저장한다.
AI 요약 기능 없이, 검색 결과의 title/link/description을 기본으로 쓰고,
각 논문의 원문 링크 페이지에서 citation_* 메타태그(구글 스칼라 색인 표준)를 읽어
저자/소속/학술지/발행정보/초록을 최대한 보강한다.

※ 네이버에는 "academic" 검색 API가 없다. 논문류를 다루는 것은
   https://openapi.naver.com/v1/search/doc.json ("전문자료 검색")이다.
※ 이 API 자체는 title, link, description 3개 필드만 준다 — 저자/학술지/초록 등은
   원문 페이지의 citation_* 메타태그에서 별도로 읽어와야 한다. 사이트에 따라
   이 메타태그가 없을 수도 있고, 그런 경우 해당 필드는 빈 값으로 남는다.
GitHub Actions에서 실행한다 (브라우저 직접 호출은 CORS로 막혀서 불가능).
"""
import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BukhansanArchiveBot/1.0)"}

# 검색어를 다양하게 던져서 최대한 많이 모으고, 실제 카테고리는 내용으로 재분류한다.
SEARCH_KEYWORDS = ["북한산", "북한산국립공원", "북한산 생태", "북한산 재난", "북한산 탐방", "북한산 역사", "북한산성"]

CATEGORY_RULES = [
    ("재난", r"산사태|홍수|재난|토사|침수|피해|위험|산불|붕괴|안전사고"),
    ("탐방", r"탐방|등산|이용객|방문자|탐방로|관광|트래킹|둘레길"),
    ("생태", r"생태|식생|서식지|동식물|종다양성|산림|곤충|조류|식물상"),
    ("역사문화", r"역사|문화재|유적|사찰|성곽|북한산성|전통"),
]

LOCATION_TABLE = [
    ("백운대", 37.6585, 126.9765),
    ("인수봉", 37.6600, 126.9775),
    ("만경대", 37.6580, 126.9760),
    ("북한산성", 37.6505, 126.9660),
    ("도봉산", 37.6890, 127.0110),
    ("우이동", 37.6630, 127.0075),
    ("정릉", 37.6070, 127.0075),
    ("구기동", 37.6115, 126.9615),
    ("불광동", 37.6115, 126.9295),
    ("의상능선", 37.6480, 126.9640),
]
DEFAULT_LOCATION = (37.6585, 126.9770)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def classify(title: str, desc: str) -> str:
    text = f"{title} {desc}"
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text):
            return category
    return "자원조사"


def guess_location(title: str, desc: str):
    text = f"{title} {desc}"
    for name, lat, lng in LOCATION_TABLE:
        if name in text:
            return {"name": name, "lat": lat, "lng": lng}
    lat, lng = DEFAULT_LOCATION
    return {"name": "북한산 일대", "lat": lat, "lng": lng}


def enrich_from_link(url: str) -> dict:
    """원문 페이지의 citation_* 메타태그에서 상세 정보를 읽어온다. 실패하면 빈 값을 돌려준다."""
    empty = {"authors": "", "institution": "", "journal": "", "pub_info": "", "abstract": ""}
    if not url:
        return empty
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code != 200:
            return empty
        soup = BeautifulSoup(resp.text, "html.parser")

        def meta_all(name):
            return [
                m.get("content", "").strip()
                for m in soup.find_all("meta", attrs={"name": name})
                if m.get("content")
            ]

        def meta_one(name):
            vals = meta_all(name)
            return vals[0] if vals else ""

        authors = meta_all("citation_author")
        institutions = meta_all("citation_author_institution")
        journal = meta_one("citation_journal_title") or meta_one("citation_conference_title")
        volume = meta_one("citation_volume")
        issue = meta_one("citation_issue")
        pages = f"{meta_one('citation_firstpage')}-{meta_one('citation_lastpage')}".strip("-")
        date = meta_one("citation_publication_date") or meta_one("citation_date")
        abstract = meta_one("citation_abstract")

        pub_info_parts = [p for p in [journal, f"{volume}권" if volume else "", f"{issue}호" if issue else "", pages, date] if p]

        return {
            "authors": ", ".join(authors),
            "institution": ", ".join(institutions),
            "journal": journal,
            "pub_info": " · ".join(pub_info_parts),
            "abstract": strip_html(abstract),
        }
    except Exception as e:
        print(f"    (상세 정보 보강 실패: {e})")
        return empty


def search_naver(keyword: str, display: int = 100):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("  ⚠ NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 시크릿이 비어있음")
        return []
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/doc.json",
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": keyword, "display": display, "start": 1},
            timeout=30,
        )
        print(f"  '{keyword}' → HTTP {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items", [])
            print(f"  API가 돌려준 원본 결과: {len(items)}건 (전체 {data.get('total', '?')}건 중)")
            return items
        print(f"  오류 응답: {resp.text[:300]}")
    except Exception as e:
        print(f"  검색 오류: {e}")
    return []


def fetch_papers():
    papers = []
    seen_titles = set()
    skipped_irrelevant = 0

    for keyword in SEARCH_KEYWORDS:
        print(f"\n[검색] '{keyword}'")
        items = search_naver(keyword)

        for item in items:
            title = strip_html(item.get("title", ""))
            desc = strip_html(item.get("description", ""))

            if not title:
                continue
            # 북한산과 무관해 보이는 결과는 제외 (제목이나 설명 어디에도 "북한산"이 없는 경우)
            if "북한산" not in f"{title} {desc}":
                skipped_irrelevant += 1
                continue
            if title in seen_titles:
                continue
            seen_titles.add(title)

            url = item.get("link", "")
            category = classify(title, desc)
            location = guess_location(title, desc)
            year_match = re.search(r"(19|20)\d{2}", f"{title} {desc}")
            year = year_match.group(0) if year_match else "-"

            print(f"  수집: [{category}] {title[:50]}")
            detail = enrich_from_link(url)
            time.sleep(0.5)  # 원문 사이트 부담을 줄이기 위한 텀

            papers.append(
                {
                    "title": title,
                    "description": desc,
                    "year": year,
                    "category": category,
                    "location": location,
                    "url": url,
                    "authors": detail["authors"],
                    "institution": detail["institution"],
                    "journal": detail["journal"],
                    "pub_info": detail["pub_info"],
                    "abstract": detail["abstract"],
                }
            )

        time.sleep(0.3)

    print(f"\n=== 총 수집: {len(papers)}건 (북한산 무관으로 제외: {skipped_irrelevant}건) ===")
    return papers


if __name__ == "__main__":
    papers = fetch_papers()
    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(
            {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "papers": papers},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("papers.json 저장 완료")
