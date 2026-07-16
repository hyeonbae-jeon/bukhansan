"""
북한산 관련 논문을 네이버 "전문자료 검색"(doc) API에서 수집해 papers.json으로 저장한다.
※ 네이버에는 "academic" 검색 API가 별도로 없다 — 논문/보고서류를 다루는 것은
   https://openapi.naver.com/v1/search/doc.json ("전문자료 검색")이다.
GitHub Actions에서 실행되며(서버 IP), 브라우저에서 직접 호출하지 않는다 —
네이버 API도 CORS로 브라우저 직접 호출을 막기 때문에 반드시 서버(Actions)에서 실행해야 한다.
"""
import os
import re
import json
import time
import requests

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
)

# 검색 키워드 → 실패했던 이전 버전과 동일하게 카테고리 힌트로만 사용하고,
# 실제 카테고리는 아래 classify()에서 제목+초록 내용을 보고 다시 판정한다.
# (검색어만으로 분류하면 "북한산 생태"로 검색해도 재난 논문이 섞여 나오는 문제가 있었음)
SEARCH_KEYWORDS = ["북한산", "북한산 생태", "북한산 재난", "북한산 탐방", "북한산 역사", "북한산 자원조사"]

CATEGORY_ORDER = ["재난", "탐방", "생태", "역사문화", "자원조사"]

CATEGORY_RULES = [
    ("재난", r"산사태|홍수|재난|토사|침수|피해|위험|산불|붕괴|안전사고"),
    ("탐방", r"탐방|등산|이용객|방문자|탐방로|관광|트래킹|둘레길"),
    ("생태", r"생태|식생|서식지|동식물|종다양성|산림|곤충|조류|식물상"),
    ("역사문화", r"역사|문화재|유적|사찰|성곽|북한산성|전통"),
]

# 논문 제목/초록에 등장하는 대표 지명 → 좌표 (네이버 API는 좌표를 주지 않으므로
# 지명이 언급되면 근사 위치를 지도에 표시하기 위한 보조 테이블)
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
    ("둘레길", 37.6550, 126.9900),
]
DEFAULT_LOCATION = (37.6585, 126.9770)  # 북한산 대략 중심(백운대 인근)


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def classify(title: str, abstract: str) -> str:
    text = f"{title} {abstract}"
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, text):
            return category
    return "자원조사"


def guess_location(title: str, abstract: str):
    text = f"{title} {abstract}"
    for name, lat, lng in LOCATION_TABLE:
        if name in text:
            return {"name": name, "lat": lat, "lng": lng}
    lat, lng = DEFAULT_LOCATION
    return {"name": "북한산 일대", "lat": lat, "lng": lng}


def summarize(text: str) -> str:
    if not text or not GEMINI_API_KEY:
        return ""
    try:
        prompt = f"다음 학술논문 초록을 3문장으로 간결하게 한국어로 요약해줘:\n\n{text[:2000]}"
        resp = requests.post(
            GEMINI_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"  Gemini 오류: {resp.status_code} {resp.text[:150]}")
    except Exception as e:
        print(f"  요약 실패: {e}")
    return ""


def search_naver(keyword: str, display: int = 30):
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
            params={"query": keyword, "display": display, "start": 1, "sort": "sim"},
            timeout=30,
        )
        print(f"  '{keyword}' → HTTP {resp.status_code}")
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            print(f"  결과 {len(items)}건")
            return items
        print(f"  오류 응답: {resp.text[:200]}")
    except Exception as e:
        print(f"  검색 오류: {e}")
    return []


def fetch_papers():
    papers = []
    seen_titles = set()

    for keyword in SEARCH_KEYWORDS:
        print(f"\n[검색] '{keyword}'")
        items = search_naver(keyword)

        for item in items:
            title = strip_html(item.get("title", ""))
            abstract = strip_html(item.get("description", ""))

            # 북한산과 무관한 결과 제외 (검색어가 넓게 걸려서 관련 없는 논문이 섞여 들어오는 문제 방지)
            if "북한산" not in f"{title} {abstract}":
                continue
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            # 네이버 "전문자료 검색"(doc) API는 title/link/description 3개 필드만 준다.
            # author·publisher·pubdate 필드는 존재하지 않으므로, 제목/설명 텍스트에서 연도만 정규식으로 추출한다.
            author = "미상"
            journal = "-"
            year_match = re.search(r"(19|20)\d{2}", f"{title} {abstract}")
            year = year_match.group(0) if year_match else "-"
            url = item.get("link", "")
            category = classify(title, abstract)
            location = guess_location(title, abstract)

            print(f"  수집: [{category}] {title[:40]}")

            summary = summarize(abstract) if abstract else ""
            if summary:
                time.sleep(1)  # Gemini 호출 사이 텀

            papers.append(
                {
                    "title": title,
                    "author": author,
                    "year": year,
                    "journal": journal,
                    "abstract": abstract,
                    "summary": summary,
                    "category": category,
                    "location": location,
                    "url": url,
                }
            )

        time.sleep(0.5)  # 네이버 API 호출 사이 텀

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
