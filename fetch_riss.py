import os, json, time, requests
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

KEYWORDS = {
    "북한산": "전체",
    "북한산 생태": "생태",
    "북한산 재난": "재난",
    "북한산 탐방": "탐방",
    "북한산 역사": "역사문화",
    "북한산 자원": "자원조사",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.riss.kr",
}

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

def fetch_papers():
    papers = []
    seen = set()

    session = requests.Session()
    session.headers.update(HEADERS)

    # 메인 페이지 먼저 방문 → 쿠키 확보
    print("RISS 메인 접속 중...")
    try:
        session.get("https://www.riss.kr", timeout=30)
        print("  메인 접속 완료")
        time.sleep(2)
    except Exception as e:
        print(f"  메인 접속 실패: {e}")

    for keyword, category in KEYWORDS.items():
        print(f"\n[검색] '{keyword}'")
        try:
            search_url = "https://www.riss.kr/search/Search.do"
            params = {
                "queryText": keyword,
                "colName": "re_all",
                "searchGubun": "true",
                "isDetailSearch": "N",
                "viewYn": "OP",
                "strSort": "RANK",
                "pageScale": "20",
                "iStartCount": "0",
            }
            resp = session.get(search_url, params=params, timeout=30)
            print(f"  HTTP {resp.status_code} / HTML 길이: {len(resp.text)}")

            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("a", href=lambda h: h and "DetailView" in h)
            print(f"  DetailView 링크: {len(links)}개")

            hrefs = []
            for link in links:
                href = link["href"]
                if not href.startswith("http"):
                    href = "https://www.riss.kr" + href
                if href not in hrefs:
                    hrefs.append(href)

            print(f"  논문 링크: {len(hrefs)}개")

            for href in hrefs[:10]:
                if href in seen:
                    continue
                seen.add(href)

                try:
                    time.sleep(1)
                    detail_resp = session.get(href, timeout=30)
                    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

                    # 제목
                    title = ""
                    for sel in ["h3.title", "h2.title", ".titArea h3", ".cont_inner h3"]:
                        el = detail_soup.select_one(sel)
                        if el:
                            t = el.get_text(strip=True)
                            if len(t) > 5:
                                title = t
                                break

                    if not title or len(title) < 4:
                        continue

                    # 저자
                    author = ""
                    for sel in [".author", ".writer", "dd.author"]:
                        el = detail_soup.select_one(sel)
                        if el:
                            author = el.get_text(strip=True)
                            break

                    # 연도
                    year = ""
                    for sel in [".year", ".pubYear", "dd.year"]:
                        el = detail_soup.select_one(sel)
                        if el:
                            year = el.get_text(strip=True)[:4]
                            break

                    # 학술지
                    journal = ""
                    for sel in [".journalInfo", ".publisher", "dd.journal", ".journalName"]:
                        el = detail_soup.select_one(sel)
                        if el:
                            journal = el.get_text(strip=True)
                            break

                    # 초록
                    abstract = ""
                    for sel in [".abstractTxt", ".abstract", "#abstract", ".cont_abstract"]:
                        el = detail_soup.select_one(sel)
                        if el:
                            abstract = el.get_text(strip=True)
                            break

                    print(f"  수집: {title[:40]}")

                    summary = ""
                    if abstract and GEMINI_API_KEY:
                        print(f"    Gemini 요약 중...")
                        summary = summarize(abstract)
                        time.sleep(1.5)

                    papers.append({
                        "title": title,
                        "author": author or "미상",
                        "year": year or "-",
                        "journal": journal or "-",
                        "abstract": abstract,
                        "summary": summary,
                        "category": category,
                        "url": href
                    })

                except Exception as e:
                    print(f"  상세 오류: {e}")

            time.sleep(2)

        except Exception as e:
            print(f"  검색 오류: {e}")

    print(f"\n=== 총 수집: {len(papers)}건 ===")
    return papers

papers = fetch_papers()
with open("papers.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=2)
print("papers.json 저장 완료")
