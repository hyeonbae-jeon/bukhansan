"""
북한산 관련 논문을 네이버 학술정보(academic.naver.com) 검색결과 페이지에서
직접 읽어와(스크래핑) papers.json으로 저장한다. (AI 연동 없음 — 규칙기반 분류만 사용)

※ openapi.naver.com의 "doc.json" API는 title/link/description 3개 필드뿐이라
   저자·학술지·연도 정보가 부실해서, 실제 웹페이지(academic.naver.com)를 직접 읽는 방식을 쓴다.
※ 아래 CSS 선택자(ui_listing_info 등)는 실제 페이지 HTML을 보고 확인한 것.
GitHub Actions에서 실행한다 (브라우저 직접 호출은 CORS로 막혀서 불가능).
"""
import re
import json
import time
import random
from collections import Counter
import requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE = "https://academic.naver.com"
SEARCH_URL = f"{BASE}/search.naver"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://academic.naver.com/",
    "Connection": "keep-alive",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4

# 검색어를 다양하게 던져서 최대한 많이 모으고, 실제 카테고리는 내용으로 재분류한다.
SEARCH_KEYWORDS = [
    "북한산", "북한산국립공원", "북한산 생태", "북한산 재난", "북한산 탐방", "북한산 역사", "북한산성",
    "북한산 등산로", "북한산 산림", "북한산 문화재", "북한산 사찰", "북한산 산사태",
    "북한산 식생", "북한산 둘레길", "북한산 지질", "북한산 토양", "북한산 관리",
]
RESULTS_PER_PAGE = 20      # academic.naver.com 한 페이지당 결과 수(확인된 값)
MAX_PAGES_PER_KEYWORD = 30  # 검색어당 최대 30페이지(최대 600건) — 새 결과 없으면 자동으로 더 일찍 멈춤

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

STOPWORDS = {
    "논문", "연구", "분석", "결과", "본", "통해", "대한", "위한", "이번", "그리고", "또한",
    "에서", "으로", "에게", "것으로", "등을", "및", "처럼", "국립공원", "북한산", "이용",
    "관련", "경우", "이러한", "그러나", "따라서", "하지만", "때문에", "이용한", "기반",
    "제시", "필요", "중심", "대상", "조사", "이상", "이하", "각각", "다양한", "전체", "가장",
}
JOSA_SUFFIXES = ["으로부터", "에서의", "로서의", "이라는", "하는", "이나", "에서", "으로", "까지",
                  "부터", "에게", "에는", "이며", "하고", "하며", "이고", "만을",
                  "의", "은", "는", "이", "가", "을", "를", "에", "로", "와", "과", "도", "만"]


def polite_get(url, params=None):
    """academic.naver.com에 재시도 + 점점 길어지는 대기시간을 적용해 요청한다."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
            return resp
        except requests.exceptions.RequestException as e:
            wait = attempt * 8 + random.uniform(0, 4)
            print(f"    (요청 실패, {attempt}/{MAX_RETRIES}회차: {e} — {wait:.0f}초 대기 후 재시도)")
            if attempt < MAX_RETRIES:
                time.sleep(wait)
    return None


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
        resp = polite_get(detail_url)
        if resp is None or resp.status_code != 200:
            return result
        soup = BeautifulSoup(resp.text, "html.parser")

        abstract_p = soup.select_one("div#div_abstract p.ui_enddetail_txt")
        if abstract_p:
            raw = abstract_p.get_text("\n", strip=True)
            result["abstract"] = re.sub(r"\n{2,}", "\n\n", raw).strip()

        for tag in soup.find_all(["dt", "span", "div", "th"]):
            if tag.get_text(strip=True) == "소속":
                nxt = tag.find_next(["dd", "span", "div", "td"])
                if nxt:
                    result["institution"] = nxt.get_text(" ", strip=True)
                    break

    except Exception as e:
        print(f"    (상세페이지 읽기 실패: {e})")
    return result


def search_academic(keyword: str, start: int = 1):
    """academic.naver.com 검색결과 페이지를 읽어 논문 목록을 파싱한다."""
    items = []
    try:
        resp = polite_get(SEARCH_URL, params={"field": 0, "docType": 1, "query": keyword, "start": start})
        if resp is None:
            print(f"  '{keyword}' (start={start}) → 재시도 다 실패, 이 요청은 포기")
            return items
        print(f"  '{keyword}' (start={start}) → HTTP {resp.status_code}")
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


def extract_keywords(papers: list, top_n: int = 30):
    """수집된 논문들의 제목+초록에서 자주 나오는 한글 단어를 뽑아 빈도순으로 정리한다.
    형태소 분석기 없이 정규식 + 조사 제거 휴리스틱만 쓰기 때문에 100% 정확하진 않다."""
    counter = Counter()
    for p in papers:
        text = f"{p['title']} {p.get('abstract', '')}"
        for token in re.findall(r"[가-힣]{2,}", text):
            word = token
            for josa in JOSA_SUFFIXES:
                if word.endswith(josa) and len(word) - len(josa) >= 2:
                    word = word[: -len(josa)]
                    break
            if len(word) < 2 or word in STOPWORDS:
                continue
            counter[word] += 1
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n)]


def fetch_papers():
    papers = []
    seen_titles = set()

    for keyword in SEARCH_KEYWORDS:
        print(f"\n[검색] '{keyword}'")

        for page in range(MAX_PAGES_PER_KEYWORD):
            start = 1 + page * RESULTS_PER_PAGE
            items = search_academic(keyword, start=start)

            if not items:
                break

            new_count = 0
            for item in items:
                title = item["title"]
                if not title or title in seen_titles:
                    continue
                if "북한산" not in f"{title} {item['snippet']}":
                    continue
                seen_titles.add(title)
                new_count += 1

                category = classify(title, item["snippet"])
                location = guess_location(title, item["snippet"])

                print(f"  수집: [{category}] {title[:50]}")
                detail = fetch_abstract_detail(item["detail_url"])
                time.sleep(1.5 + random.uniform(0, 1))

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

            print(f"  → 이 페이지에서 새로 추가된 논문 {new_count}건")
            time.sleep(1.5 + random.uniform(0, 1))

            if new_count == 0:
                break

        time.sleep(2 + random.uniform(0, 1.5))

    print(f"\n=== 총 수집: {len(papers)}건 ===")
    return papers


if __name__ == "__main__":
    papers = fetch_papers()
    keywords = extract_keywords(papers)
    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(
            {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "papers": papers, "keywords": keywords},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print("papers.json 저장 완료")
