import os, json, time, requests
from playwright.sync_api import sync_playwright

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=" + GEMINI_API_KEY

CATEGORIES = {
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
    prompt = f"다음 학술논문 초록을 3문장으로 간결하게 한국어로 요약해주세요. 핵심 연구목적, 방법, 결과 중심으로:\n\n{text[:2000]}"
    try:
        resp = requests.post(GEMINI_URL, json={"contents":[{"parts":[{"text":prompt}]}]}, timeout=30)
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print(f"  Gemini 오류: {resp.status_code} - {resp.text[:100]}")
            return ""
    except Exception as e:
        print(f"  요약 실패: {e}")
        return ""

def fetch_papers():
    papers = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36")

        for keyword, category in CATEGORIES.items():
            print(f"\n[검색] '{keyword}'")
            page = context.new_page()
            try:
                url = f"https://www.riss.kr/search/Search.do?queryText={requests.utils.quote(keyword)}&searchGubun=true&gubun=&morpheme=true&colName=re_all&pageScale=20&iStartCount=0&searchOrder=&searchOrderBy=SCORE&searchGubun=true&colName=re_all&is_personName=&resultCount=20&numFound=0&url="
                page.goto(f"https://www.riss.kr/search/Search.do?queryText={requests.utils.quote(keyword)}&colName=re_all&searchGubun=true", timeout=30000)
                page.wait_for_timeout(3000)

                links = page.query_selector_all("a[href*='DetailView']")
                print(f"  발견: {len(links)}개")

                hrefs = []
                for link in links:
                    href = link.get_attribute("href")
                    if href and "DetailView" in href:
                        if not href.startswith("http"):
                            href = "https://www.riss.kr" + href
                        hrefs.append(href)

                for href in hrefs[:10]:
                    if href in seen:
                        continue
                    seen.add(href)

                    detail = context.new_page()
                    try:
                        detail.goto(href, timeout=30000)
                        detail.wait_for_timeout(2000)

                        title = ""
                        for sel in ["h3.title", ".cont_inner h3", "h2.title", ".thesisInfo h3"]:
                            el = detail.query_selector(sel)
                            if el:
                                title = el.inner_text().strip()
                                break

                        if not title:
                            title_el = detail.query_selector("title")
                            if title_el:
                                title = title_el.inner_text().replace("RISS", "").strip(" | -")

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
                                year = el.inner_text().strip()
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

                        if not title or len(title) < 3:
                            detail.close()
                            continue

                        print(f"  수집: {title[:40]}...")

                        summary = ""
                        if abstract:
                            print(f"  요약 중...")
                            summary = summarize(abstract)
                            time.sleep(1)

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
                        print(f"  상세 페이지 오류: {e}")
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
