import os, json, time, re, requests

NAVER_CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
GEMINI_API_KEY      = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

KEYWORDS = {
    "북한산": "전체",
    "북한산 생태": "생태",
    "북한산 재난": "재난",
    "북한산 탐방": "탐방",
    "북한산 역사": "역사문화",
    "북한산 자원": "자원조사",
}

def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()

def summarize(text):
    if not text or not GEMINI_API_KEY:
        return ""
    try:
        prompt = f"다음 학술논문 초록을 3문장으로 간결하게 한국어로 요약해주세요:\n\n{text[:2000]}"
        resp = requests.post(
            GEMINI_URL,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"  Gemini 오류: {resp.status_code}")
    except Exception as e:
        print(f"  요약 실패: {e}")
    return ""

def search_naver(keyword, display=10):
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        print("  ⚠ Naver API 키 없음 — Secrets 확인 필요")
        return []
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/academic.json",
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": keyword, "display": display, "start": 1, "sort": "sim"},
            timeout=30
        )
        print(f"  Naver API HTTP {resp.status_code}")
        if resp.status_code == 200:
            items = resp.json().get("items", [])
            print(f"  결과: {len(items)}개")
            return items
        print(f"  오류 응답: {resp.text[:150]}")
    except Exception as e:
        print(f"  검색 오류: {e}")
    return []

def fetch_papers():
    papers = []
    seen = set()

    for keyword, category in KEYWORDS.items():
        print(f"\n[검색] '{keyword}'")
        items = search_naver(keyword, display=10)

        for item in items:
            title = strip_html(item.get("title", ""))
            if not title or title in seen:
                continue
            seen.add(title)

            author   = strip_html(item.get("author", "")) or "미상"
            journal  = strip_html(item.get("publisher", "")) or "-"
            pub      = item.get("pubdate", "")
            year     = pub[:4] if pub else "-"
            abstract = strip_html(item.get("description", ""))
            url      = item.get("link", "")

            print(f"  수집: {title[:40]}")

            summary = ""
            if abstract and GEMINI_API_KEY:
                print(f"    Gemini 요약 중...")
                summary = summarize(abstract)
                time.sleep(1)

            papers.append({
                "title":    title,
                "author":   author,
                "year":     year,
                "journal":  journal,
                "abstract": abstract,
                "summary":  summary,
                "category": category,
                "url":      url
            })

        time.sleep(0.5)

    print(f"\n=== 총 수집: {len(papers)}건 ===")
    return papers

papers = fetch_papers()
with open("papers.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=2)
print("papers.json 저장 완료")
