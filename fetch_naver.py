"""
북한산 국립공원 논문을 academic.naver.com 에서 스크래핑해
papers.json 으로 저장한다. GitHub Actions 에서 실행.
"""
import os, re, json, time, random, requests
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE       = "https://academic.naver.com"
SEARCH_URL = f"{BASE}/search.naver"
HEADERS    = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer":         "https://academic.naver.com/",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ── Gemini 설정 ──────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = "gemini-2.0-flash"          # ← 2.5-flash-lite 에서 교체
GEMINI_URL     = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)
CATEGORY_LABELS = ["자원조사", "재난", "탐방", "생태", "역사문화"]

# ── 수집 대상 (북한산 단독 테스트) ───────────────────────────
PARK = {"id": "bukhansan", "name": "북한산", "lat": 37.6585, "lng": 126.9770}
KEYWORD_SUFFIXES     = ["", "국립공원", " 생태", " 탐방", " 식물", " 동물", " 탐방객"]
RESULTS_PER_PAGE     = 20
MAX_PAGES_PER_KEYWORD = 5
REQUEST_TIMEOUT      = 30
MAX_RETRIES          = 4

# ── 규칙 기반 분류 ────────────────────────────────────────────
CATEGORY_RULES = [
    ("재난",   r"산사태|홍수|재난|토사|침수|피해|위험|산불|붕괴|안전사고"),
    ("탐방",   r"탐방|등산|이용객|방문자|탐방로|관광|트래킹|둘레길"),
    ("생태",   r"생태|식생|서식지|동식물|종다양성|산림|곤충|조류|식물상|식물|동물"),
    ("역사문화", r"역사|문화재|유적|사찰|성곽|전통"),
]

def classify(title: str, desc: str) -> str:
    text = f"{title} {desc}"
    for cat, pat in CATEGORY_RULES:
        if re.search(pat, text):
            return cat
    return "자원조사"


# ── HTTP 요청 (재시도 포함) ───────────────────────────────────
def polite_get(url, params=None):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp
            print(f"    HTTP {resp.status_code} (시도 {attempt}/{MAX_RETRIES})")
        except requests.exceptions.RequestException as e:
            print(f"    요청 실패 (시도 {attempt}/{MAX_RETRIES}): {e}")
        if attempt < MAX_RETRIES:
            time.sleep(attempt * 8 + random.uniform(0, 4))
    return None


# ── Gemini AI 분석 ────────────────────────────────────────────
def analyze_with_ai(title: str, abstract: str, snippet: str) -> dict | None:
    if not GEMINI_API_KEY:
        return None
    text = abstract or snippet or title
    if not text:
        return None

    prompt = f"""너는 국립공원 관련 학술논문을 분류·요약하는 도우미다.
아래 북한산 관련 논문을 분석해라.

분류 기준 (반드시 이 중 하나):
- 재난: 산사태, 산불, 침수, 안전사고 등
- 탐방: 등산객·탐방객 행태, 이용 실태, 관광
- 생태: 동식물, 식생, 서식지, 생물다양성
- 역사문화: 역사, 문화재, 유적, 사찰, 전통
- 자원조사: 위 네 가지 외 환경조사·정책·관리

제목: {title}
초록: {text[:1800]}

JSON 형식으로만 답하라 (다른 텍스트 없이):
{{"category":"5개 중 하나","summary":"2~3문장 한국어 요약","usage":"2~3문장 활용방안"}}"""

    for attempt in range(1, 4):
        try:
            resp = requests.post(
                GEMINI_URL,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30,
            )
            if resp.status_code == 429:
                wait = 60 * attempt
                print(f"    Gemini 429 → {wait}초 대기 후 재시도")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                print(f"    Gemini 실패: HTTP {resp.status_code} {resp.text[:150]}")
                return None

            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

            # ★ 핵심 수정: ```json 블록이든 순수 JSON이든 중괄호만 추출
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                print(f"    Gemini JSON 추출 실패: {raw[:100]}")
                return None

            data = json.loads(match.group())
            if data.get("category") not in CATEGORY_LABELS:
                data["category"] = classify(title, snippet)
            return data

        except json.JSONDecodeError as e:
            print(f"    Gemini JSON 파싱 실패: {e}")
            return None
        except Exception as e:
            print(f"    Gemini 오류: {e}")
            return None
    return None


# ── 상세 페이지에서 초록/소속 추출 ───────────────────────────
def fetch_abstract(detail_url: str) -> dict:
    result = {"abstract": "", "institution": ""}
    if not detail_url:
        return result
    try:
        resp = polite_get(detail_url)
        if not resp:
            return result
        soup = BeautifulSoup(resp.text, "html.parser")

        # 초록: 여러 선택자를 순서대로 시도
        abstract = ""
        for sel in [
            "div#div_abstract p.ui_enddetail_txt",
            "div.abs_area p",
            "div#abstractArea",
            "p.abstract",
        ]:
            el = soup.select_one(sel)
            if el:
                abstract = el.get_text("\n", strip=True)
                break
        result["abstract"] = re.sub(r"\n{2,}", "\n\n", abstract).strip()

        # 소속
        for tag in soup.find_all(["dt", "th", "span"]):
            if "소속" in tag.get_text(strip=True):
                nxt = tag.find_next(["dd", "td", "span"])
                if nxt:
                    result["institution"] = nxt.get_text(" ", strip=True)
                    break
    except Exception as e:
        print(f"    상세페이지 오류: {e}")
    return result


# ── 검색 결과 페이지 파싱 ─────────────────────────────────────
def search_academic(keyword: str, start: int = 1) -> list:
    items = []
    try:
        resp = polite_get(SEARCH_URL, params={
            "field": 0, "docType": 1, "query": keyword, "start": start
        })
        if not resp:
            return items
        print(f"  '{keyword}' (start={start}) → HTTP {resp.status_code}")

        soup = BeautifulSoup(resp.text, "html.parser")
        blocks = soup.select("div.ui_listing_info")
        print(f"  결과 블록 {len(blocks)}건")

        for block in blocks:
            title_a = block.select_one("h4 a.ui_listing_subtit")
            if not title_a:
                continue
            title      = title_a.get_text(strip=True)
            href       = title_a.get("href", "")
            detail_url = urljoin(BASE, href) if href else ""

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

            snippet_el = block.select_one("p.ui_listing_txt")
            snippet    = snippet_el.get_text(strip=True) if snippet_el else ""
            cited_el   = block.select_one("span.ui_listing_cited_num")
            cited      = cited_el.get_text(strip=True) if cited_el else ""

            items.append({
                "title":      title,
                "detail_url": detail_url,
                "year":       year or "-",
                "journal":    journal,
                "authors":    ", ".join(authors),
                "cited":      cited,
                "snippet":    snippet,
            })
    except Exception as e:
        print(f"  검색 오류: {e}")
    return items


# ── 메인 수집 루프 ────────────────────────────────────────────
def fetch_papers() -> list:
    papers   = []
    seen_urls = set()          # ★ URL 기준 중복 제거 (제목 기준에서 교체)
    park      = PARK
    park_name = park["name"]

    for suffix in KEYWORD_SUFFIXES:
        keyword = f"{park_name}{suffix}"
        print(f"\n[검색] '{keyword}'")
        time.sleep(2 + random.uniform(0, 1.5))

        for page in range(MAX_PAGES_PER_KEYWORD):
            start = 1 + page * RESULTS_PER_PAGE
            items = search_academic(keyword, start=start)
            if not items:
                break

            new_count = 0
            for item in items:
                title      = item["title"]
                detail_url = item["detail_url"]
                if not title:
                    continue

                # ★ 핵심 수정: park_name 필터 제거
                #   (기존 코드: if park_name not in f"{title} {item['snippet']}": continue)
                #   → 삭제. "북한산"이 제목에 없어도 관련 논문이 많음.

                dedup_key = detail_url or title
                if dedup_key in seen_urls:
                    continue
                seen_urls.add(dedup_key)
                new_count += 1

                print(f"  수집: {title[:60]}")
                detail = fetch_abstract(detail_url)
                time.sleep(1.5 + random.uniform(0, 1))

                ai = analyze_with_ai(title, detail["abstract"], item["snippet"])
                if GEMINI_API_KEY:
                    time.sleep(5)      # 무료 티어 분당 호출 제한 대응

                if ai:
                    category   = ai.get("category", classify(title, item["snippet"]))
                    ai_summary = ai.get("summary", "")
                    ai_usage   = ai.get("usage", "")
                    print(f"    → [{category}] (AI)")
                else:
                    category   = classify(title, item["snippet"])
                    ai_summary = ""
                    ai_usage   = ""
                    print(f"    → [{category}] (규칙)")

                pub_parts = [p for p in [
                    item["journal"],
                    item["year"] if item["year"] != "-" else "",
                    f"{item['cited']}회 피인용" if item["cited"] else "",
                ] if p]

                papers.append({
                    "title":       title,
                    "description": item["snippet"],
                    "year":        item["year"],
                    "authors":     item["authors"],
                    "journal":     item["journal"],
                    "institution": detail["institution"],
                    "pub_info":    " · ".join(pub_parts),
                    "abstract":    detail["abstract"],
                    "ai_summary":  ai_summary,
                    "ai_usage":    ai_usage,
                    "category":    category,
                    "park":        {"id": park["id"], "name": park_name},
                    "location":    {"name": park_name, "lat": park["lat"], "lng": park["lng"]},
                    "url":         detail_url,
                })

            print(f"  → 새로 추가 {new_count}건 / 누적 {len(papers)}건")
            time.sleep(2 + random.uniform(0, 1.5))
            if new_count == 0:
                break

    print(f"\n=== 총 수집: {len(papers)}건 ===")
    return papers


if __name__ == "__main__":
    papers = fetch_papers()
    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(
            {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "papers": papers},
            f, ensure_ascii=False, indent=2,
        )
    print("papers.json 저장 완료")
