import os, json, time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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

def extract_hrefs(html_bytes):
    soup = BeautifulSoup(html_bytes, "html.parser")
    hrefs = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "DetailView" in href:
            if not href.startswith("http"):
                href = "https://www.riss.kr" + href
            hrefs.append(href)
    return list(set(hrefs))

def fetch_papers():
    papers = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for keyword, category in KEYWORDS.items():
            print(f"\n[검색] '{keyword}'")
            page = context.new_page()

            # 모든 네트워크 응답 캡처
            all_riss_responses = {}

            def on_response(resp):
                if "riss.kr" not in resp.url:
                    return
                try:
                    body = resp.body()
                    all_riss_responses[resp.url] = body
                    if b"DetailView" in body:
                        print(f"  ★ DetailView 포함 응답: {len(body)}bytes | {resp.url[-70:]}")
                except:
                    pass

            page.on("response", on_response)

            try:
                search_url = f"https://www.riss.kr/search/Search.do?queryText={keyword}&colName=re_all&searchGubun=true"
                page.goto(search_url, timeout=60000)
                page.wait_for_timeout(12000)

                # 방법 1: 캡처된 응답에서 링크 추출
                hrefs = []
                for url, body in all_riss_responses.items():
                    found = extract_hrefs(body)
                    if found:
                        hrefs.extend(found)
                        print(f"  응답에서 {len(found)}개 링크 추출: {url[-50:]}")

                # 방법 2: DOM에서 추출 (혹시 DOM에 있을 경우)
                if not hrefs:
                    dom_links = page.query_selector_all("a[href*='DetailView']")
                    print(f"  DOM 링크: {len(dom_links)}개")
                    for link in dom_links:
                        href = link.get_attribute("href") or ""
                        if "DetailView" in href:
                            if not href.startswith("http"):
                                href = "https://www.riss.kr" + href
                            hrefs.append(href)

                hrefs = list(set(hrefs))
                print(f"  총 논문 링크: {len(hrefs)}개")

                # 전체 네트워크 응답 요약 출력 (디버그)
                print(f"  캡처된 RISS 응답 수: {len(all_riss_responses)}개")
                for url, body in all_riss_responses.items():
                    has_detail = "★" if b"DetailView" in body else " "
                    print(f"    {has_detail} {len(body)}bytes | {url[-80:]}")

                for href in hrefs[:10]:
                    if href in seen:
                        continue
                    seen.add(href)

                    detail = context.new_page()
                    try:
                        detail.goto(href, timeout=30000)
                        detail.wait_for_timeout(2000)

                        title = ""
                        for sel in ["h3.title", ".cont_inner h3", "h2.title", ".thesisInfo h3", ".titArea h3"]:
                            el = detail.query_selector(sel)
                            if el:
                                t = el.inner_text().strip()
                                if len(t) > 5:
                                    title = t
                                    break

                        if not title or len(title) < 4:
                            detail.close()
                            continue

                        author = ""
                        for sel in [".author", ".writer", "dd.author"]:
                            el = detail.query_selector(sel)
                            if el:
                                author = el.inner_text().strip()
                                break

                        year = ""
                        for sel in [".year", ".pubYear", "dd.year"]:
                            el = detail.query_selector(sel)
                            if el:
                                year = el.inner_text().strip()[:4]
                                break

                        journal = ""
                        for sel in [".journalInfo", ".publisher", "dd.journal"]:
                            el = detail.query_selector(sel)
                            if el:
                                journal = el.inner_text().strip()
                                break

                        abstract = ""
                        for sel in [".abstractTxt", ".abstract", "#abstract", ".cont_abstract"]:
                            el = detail.query_selector(sel)
                            if el:
                                abstract = el.inner_text().strip()
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
                    finally:
                        detail.close()
                    time.sleep(1)

            except Exception as e:
                print(f"  검색 오류: {e}")
            finally:
                page.close()

        browser.close()

    print(f"\n=== 총 수집: {len(papers)}건 ===")
    return papers

papers = fetch_papers()
with open("papers.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=2)
print("papers.json 저장 완료")
