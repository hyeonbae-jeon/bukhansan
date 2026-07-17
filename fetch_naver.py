"""
북한산 관련 논문을 네이버 학술정보(academic.naver.com) 검색결과 페이지에서
직접 읽어와(스크래핑) papers.json으로 저장한다.

※ openapi.naver.com의 "doc.json" API는 title/link/description 3개 필드뿐이라
   저자·학술지·연도 정보가 부실해서, 실제 웹페이지(academic.naver.com)를 직접 읽는 방식으로 변경.
※ 아래 CSS 선택자(ui_listing_info 등)는 실제 페이지 HTML을 보고 확인한 것.
   초록(abstract)·소속(institution)은 상세 페이지(article.naver?doc_id=...)에만 있는데
   그 페이지 구조는 추정치라, 실제로 안 맞으면 상세 페이지 HTML을 한 번 더 확인해서 고쳐야 한다.
GitHub Actions에서 실행한다 (브라우저 직접 호출은 CORS로 막혀서 불가능).
"""
import re
import json
import time
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE = "https://academic.naver.com"
SEARCH_URL = f"{BASE}/search.naver"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

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


def fetch_abstract_detail(detail_url: str) -> dict:
    """상세 페이지(article.naver?doc_id=...)에서 초록/소속을 읽어온다.
    초록은 <div id="div_abstract"><p class="ui_enddetail_txt"> 안에 한글 초록과
    영어 초록이 <br><br>로 구분되어 함께 들어있다 (실제 페이지 HTML로 확인됨)."""
    result = {"abstract": "", "institution": ""}
    try:
        resp = requests.get(detail_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return result
        soup = BeautifulSoup(resp.text, "html.parser")

        abstract_p = soup.select_one("div#div_abstract p.ui_enddetail_txt")
        if abstract_p:
            raw = abstract_p.get_text("\n", strip=True)
            result["abstract"] = re.sub(r"\n{2,}", "\n\n", raw).strip()

        # 소속 정보는 이 페이지에서 확인되지 않음 (있으면 아래에서 시도, 없으면 빈 값 유지)
        for tag in soup.find_all(["dt", "span", "div", "th"]):
            if tag.get_text(strip=True) == "소속":
                nxt = tag.find_next(["dd", "span", "div", "td"])
                if nxt:
                    result["institution"] = nxt.get_text(" ", strip=True)
                    break

    except Exception as e:
        print(f"    (상세페이지 읽기 실패: {e})")
    return result


def search_academic(keyword: str):
    """academic.naver.com 검색결과 페이지를 읽어 논문 목록을 파싱한다."""
    items = []
    try:
        resp = requests.get(
            SEARCH_URL,
            headers=HEADERS,
            params={"field": 0, "docType": 1, "query": keyword},
            timeout=15,
        )
        print(f"  '{keyword}' → HTTP {resp.status_code}")
        if resp.status_code != 200:
            print(f"  응답 실패: {resp.text[:200]}")
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        blocks = soup.select("div.ui_listing_info")
        print(f"  결과 블록 {len(blocks)}건 발견")

        for block in blocks:
            title_a = block.select_one("h4 a.ui_listing_subtit")
            if not title_a:
                continue
            title = title_a.get_text(strip=True)
            detail_url = urljoin(BASE, title_a.get("href", ""))

            free_badge = block.select_one("h4 span.spimg")
            is_free = "무료" in free_badge.get_text(strip=True) if free_badge else False

            year, journal, authors = "", "", []
            desc_div = block.select_one("div.ui_listing_desc")
            if desc_div:
                for src in desc_div.select("span.ui_listing_source"):
                    text = src.get_text(strip=True)
                    if src.find("a"):
                        journal = text
                    elif re.fullmatch(r"(19|20)\d{2}", text):
                        year = text
                    elif text:
                        authors.append(text)

            cited_el = block.select_one("span.ui_listing_cited_num")
            cited = cited_el.get_text(strip=True) if cited_el else ""

            snippet_el = block.select_one("p.ui_listing_txt")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            items.append({
                "title": title,
                "detail_url": detail_url,
                "is_free": is_free,
                "year": year or "-",
                "journal": journal,
                "authors": ", ".join(authors),
                "cited": cited,
                "snippet": snippet,
            })

    except Exception as e:
        print(f"  검색 오류: {e}")
    return items


def fetch_papers():
    papers = []
    seen_titles = set()

    for keyword in SEARCH_KEYWORDS:
        print(f"\n[검색] '{keyword}'")
        items = search_academic(keyword)

        for item in items:
            title = item["title"]
            if not title or title in seen_titles:
                continue
            if "북한산" not in f"{title} {item['snippet']}":
                continue
            seen_titles.add(title)

            category = classify(title, item["snippet"])
            location = guess_location(title, item["snippet"])

            print(f"  수집: [{category}] {title[:50]}")
            detail = fetch_abstract_detail(item["detail_url"])
            time.sleep(0.5)

            pub_info_parts = [p for p in [item["journal"], item["year"], f"{item['cited']}회 피인용" if item["cited"] else ""] if p and p != "-"]

            papers.append({
                "title": title,
                "description": item["snippet"],
                "year": item["year"],
                "authors": item["authors"],
                "journal": item["journal"],
                "institution": detail["institution"],
                "pub_info": " · ".join(pub_info_parts),
                "abstract": detail["abstract"],
                "category": category,
                "location": location,
                "url": item["detail_url"],
                "is_free": item["is_free"],
            })

        time.sleep(0.5)

    print(f"\n=== 총 수집: {len(papers)}건 ===")
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
