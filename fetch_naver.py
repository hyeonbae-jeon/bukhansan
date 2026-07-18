"""
전국 국립공원(24개) 관련 논문을 네이버 학술정보(academic.naver.com) 검색결과 페이지에서
직접 읽어와(스크래핑) papers.json으로 저장한다.

※ openapi.naver.com의 "doc.json" API는 필드가 부실해서, 실제 웹페이지(academic.naver.com)를
   직접 읽는 방식을 쓴다. 아래 CSS 선택자(ui_listing_info 등)는 실제 페이지 HTML로 확인한 것.
※ 제목+초록을 Gemini(AI)에 보내 카테고리 분류 / 내용 요약 / 활용방안을 받아온다.
   GEMINI_API_KEY가 없으면 AI 호출을 건너뛰고 기존 규칙기반 분류만 사용한다.
GitHub Actions에서 실행한다 (브라우저 직접 호출은 CORS로 막혀서 불가능).
"""
import os
import re
import json
import time
import random
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


def polite_get(url, params=None):
    """academic.naver.com에 재시도 + 점점 길어지는 대기시간을 적용해 요청한다.
    타임아웃/일시적 차단으로 보이는 상황에서 바로 포기하지 않고 버틴다."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
            return resp
        except requests.exceptions.RequestException as e:
            wait = attempt * 8 + random.uniform(0, 4)  # 8s, 16s, 24s, 32s (+지터)
            print(f"    (요청 실패, {attempt}/{MAX_RETRIES}회차: {e} — {wait:.0f}초 대기 후 재시도)")
            if attempt < MAX_RETRIES:
                time.sleep(wait)
    return None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
)
CATEGORY_LABELS = ["자원조사", "재난", "탐방", "생태", "역사문화"]

# 전국 국립공원 24개소 (2026년 기준: 2023년 팔공산, 2026년 금정산 추가분 포함)
ALL_PARKS = [
    {"id": "jirisan", "name": "지리산", "lat": 35.3372, "lng": 127.7315},
    {"id": "gyeongju", "name": "경주", "lat": 35.8562, "lng": 129.2247},
    {"id": "gyeryongsan", "name": "계룡산", "lat": 36.3623, "lng": 127.2093},
    {"id": "hallyeohaesang", "name": "한려해상", "lat": 34.7333, "lng": 127.8833},
    {"id": "seoraksan", "name": "설악산", "lat": 38.1197, "lng": 128.4655},
    {"id": "songnisan", "name": "속리산", "lat": 36.5384, "lng": 127.8694},
    {"id": "hallasan", "name": "한라산", "lat": 33.3617, "lng": 126.5292},
    {"id": "naejangsan", "name": "내장산", "lat": 35.4989, "lng": 126.8886},
    {"id": "gayasan", "name": "가야산", "lat": 35.7811, "lng": 128.1222},
    {"id": "deogyusan", "name": "덕유산", "lat": 35.8614, "lng": 127.7500},
    {"id": "odaesan", "name": "오대산", "lat": 37.7942, "lng": 128.5975},
    {"id": "juwangsan", "name": "주왕산", "lat": 36.3919, "lng": 129.1836},
    {"id": "taeanhaean", "name": "태안해안", "lat": 36.7450, "lng": 126.2975},
    {"id": "dadohaehaesang", "name": "다도해해상", "lat": 34.4667, "lng": 126.5833},
    {"id": "bukhansan", "name": "북한산", "lat": 37.6585, "lng": 126.9770},
    {"id": "chiaksan", "name": "치악산", "lat": 37.3697, "lng": 128.0472},
    {"id": "woraksan", "name": "월악산", "lat": 36.8536, "lng": 128.1078},
    {"id": "sobaeksan", "name": "소백산", "lat": 36.9569, "lng": 128.4856},
    {"id": "byeonsanbando", "name": "변산반도", "lat": 35.6389, "lng": 126.5219},
    {"id": "wolchulsan", "name": "월출산", "lat": 34.7597, "lng": 126.6969},
    {"id": "mudeungsan", "name": "무등산", "lat": 35.1339, "lng": 126.9886},
    {"id": "taebaeksan", "name": "태백산", "lat": 37.0956, "lng": 128.9158},
    {"id": "palgongsan", "name": "팔공산", "lat": 36.0069, "lng": 128.6975},
    {"id": "geumjeongsan", "name": "금정산", "lat": 35.2439, "lng": 129.0619},
]

# 지금은 AI 요약/활용방안 표출이 잘 되는지부터 확인하려고 북한산 하나만 테스트 중.
# 전체 24개 국립공원으로 다시 넓히려면 아래 줄을 `PARKS = ALL_PARKS`로 바꾸면 됨.
PARKS = [p for p in ALL_PARKS if p["id"] == "bukhansan"]

RESULTS_PER_PAGE = 20    # academic.naver.com 한 페이지당 결과 수(확인된 값)
MAX_PAGES_PER_KEYWORD = 5   # 북한산 하나만 테스트 중이라 페이지를 좀 더 넉넉히
KEYWORD_SUFFIXES = ["", "국립공원", " 생태", " 탐방"]  # 공원마다 이 4가지 변형으로 검색

CATEGORY_RULES = [
    ("재난", r"산사태|홍수|재난|토사|침수|피해|위험|산불|붕괴|안전사고"),
    ("탐방", r"탐방|등산|이용객|방문자|탐방로|관광|트래킹|둘레길"),
    ("생태", r"생태|식생|서식지|동식물|종다양성|산림|곤충|조류|식물상"),
    ("역사문화", r"역사|문화재|유적|사찰|성곽|전통"),
]


def classify(title: str, desc: str) -> str:
    text = f"{title} {desc}"
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text):
            return category
    return "자원조사"


def analyze_with_ai(park_name: str, title: str, abstract: str, snippet: str) -> dict:
    """제목+초록을 AI(Gemini)에 보내 분류/요약/활용방안을 받아온다.
    GEMINI_API_KEY가 없거나 호출이 실패하면 None을 반환한다.
    category가 5개 라벨 중 하나가 아니어도 summary/usage는 그대로 살려서 돌려준다
    (호출부에서 category만 규칙기반으로 대체하고 summary/usage는 버리지 않는다)."""
    if not GEMINI_API_KEY:
        return None
    text = abstract or snippet or title
    if not text:
        return None
    prompt = f"""너는 국립공원 관련 학술논문을 분류·요약하는 도우미다.
아래는 "{park_name}" 국립공원과 관련된 논문의 제목과 초록이다.

분류 기준 (반드시 이 중 하나만 고를 것):
- 재난: 산사태, 산불, 침수, 안전사고 등 재난·위험 관련
- 탐방: 등산객·탐방객 행태, 이용 실태, 관광, 트래킹 관련
- 생태: 동식물, 식생, 서식지, 산림, 생물다양성 관련
- 역사문화: 역사, 문화재, 유적, 사찰, 전통 관련
- 자원조사: 위 네 가지에 해당하지 않는 환경조사·정책·관리 등 일반 내용

제목: {title}
초록: {text[:1800]}

아래 JSON 형식으로만 답하고, 다른 텍스트는 절대 포함하지 마라:
{{"category": "위 5개 중 하나(한글 라벨 그대로)", "summary": "이 논문이 어떤 내용인지 2~3문장 한국어 요약", "usage": "이 논문 결과를 실제로 어떻게 활용할 수 있는지 2~3문장 한국어 제안"}}"""
    try:
        resp = requests.post(
            GEMINI_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"    (AI 분석 실패: HTTP {resp.status_code} {resp.text[:150]})")
            return None
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        cleaned = re.sub(r"```json|```", "", raw).strip()
        data = json.loads(cleaned)
        return data
    except Exception as e:
        print(f"    (AI 분석 실패: {e})")
        return None


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


def fetch_papers():
    papers = []
    seen_titles = set()

    for park in PARKS:
        park_name = park["name"]
        keywords = [f"{park_name}{suffix}" for suffix in KEYWORD_SUFFIXES]
        print(f"\n\n########## [국립공원] {park_name} ##########")
        time.sleep(3 + random.uniform(0, 2))

        for keyword in keywords:
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
                    if park_name not in f"{title} {item['snippet']}":
                        continue
                    seen_titles.add(title)
                    new_count += 1

                    print(f"  수집: {title[:50]}")
                    detail = fetch_abstract_detail(item["detail_url"])
                    time.sleep(1.5 + random.uniform(0, 1))

                    ai = analyze_with_ai(park_name, title, detail["abstract"], item["snippet"])
                    if GEMINI_API_KEY:
                        time.sleep(4.5)  # Gemini 무료 티어 분당 호출 제한 고려

                    if ai:
                        category = ai.get("category") if ai.get("category") in CATEGORY_LABELS else classify(title, item["snippet"])
                        ai_summary = ai.get("summary", "")
                        ai_usage = ai.get("usage", "")
                    else:
                        category = classify(title, item["snippet"])
                        ai_summary = ""
                        ai_usage = ""

                    print(f"    → 분류: [{category}]" + (" (AI)" if ai else " (규칙기반)"))

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
                        "ai_summary": ai_summary,
                        "ai_usage": ai_usage,
                        "category": category,
                        "park": {"id": park["id"], "name": park_name},
                        "location": {"name": park_name, "lat": park["lat"], "lng": park["lng"]},
                        "url": item["detail_url"],
                        "is_free": item["is_free"],
                    })

                print(f"  → 이 페이지에서 새로 추가된 논문 {new_count}건")
                time.sleep(1.5 + random.uniform(0, 1))

                if new_count == 0:
                    break

            time.sleep(2 + random.uniform(0, 1.5))

    print(f"\n\n=== 총 수집: {len(papers)}건 ===")
    return papers


STOPWORDS = {
    "논문", "연구", "분석", "결과", "본", "통해", "대한", "위한", "이번", "그리고", "또한",
    "에서", "으로", "에게", "것으로", "등을", "및", "처럼", "국립공원", "북한산", "이용",
    "관련", "경우", "이러한", "그러나", "따라서", "하지만", "때문에", "이용한", "기반",
    "제시", "필요", "중심", "대상", "조사", "이상", "이하", "각각", "다양한", "전체", "가장",
}
JOSA_SUFFIXES = ["으로부터", "에서의", "로서의", "이라는", "하는", "이나", "에서", "으로", "까지",
                  "부터", "에게", "에는", "에서", "이며", "하고", "하며", "이고", "만을",
                  "의", "은", "는", "이", "가", "을", "를", "에", "로", "와", "과", "도", "만", "이며"]


def extract_keywords(papers: list, top_n: int = 30):
    """수집된 논문들의 제목+초록에서 자주 나오는 한글 단어를 뽑아 빈도순으로 정리한다.
    형태소 분석기 없이 정규식 + 조사 제거 휴리스틱만 쓰기 때문에 100% 정확하진 않다."""
    from collections import Counter

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
