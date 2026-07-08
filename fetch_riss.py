import os, json, time, requests
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
        print(f"  Gemini 오류: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"  요약 실패: {e}")
    return ""

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
            try:
                search_url = f"https://www.riss.kr/search/Search.do?queryText={keyword}&colName=re_all&searchGubun=true"
                page.goto(search_url, timeout=30000)
                page.wait_for_timeout(4000)

                # 디버그: 현재 URL 확인
                print(f"  현재 URL: {page.url}")
                print(f"  HTML 길이: {len(page.content())}")

                # 여러 선택자 시도
                links = []
                for selector in ["a[href*='DetailView']", "a[href*='detail']", ".srchResultListW li a"]:
                    links = page.query_selector_all(selector)
                    print(f"  선택자 '{selector}': {len(links)}개")
                    if len(links) > 0:
                        break

                if len(links) == 0:
                    # 디버그 HTML 저장
                    with open(f"debug_{keyword.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
                        f.write(page.content())
                    print(f"  ⚠ debug_{keyword.replace(' ', '_')}.html 저장됨")
                    page.close()
                    continue

                hrefs = []
                for link in links:
                    href = link.get_attribute("href") or ""
                    if "DetailView" in href or "detail" in href.lower():
                        if not href.startswith("http"):
                            href = "https://www.riss.kr" + href
                        hrefs.append(href)

                print(f"  논문 링크: {len(hrefs)}개")

                for href in hrefs[:10]:
                    if href in seen:
                        continue
                    seen.add(href)

                    detail = context.new_page()
                    try:
                        detail.goto(href, timeout=30000)
                        detail.wait_for_timeout(2000)

                        # 제목
                        title = ""
                        for sel in ["h3.title", ".cont_inner h3", "h2.title", ".thesisInfo h3", "h1", "h2", "h3"]:
                            el = detail.query_selector(sel)
                            if el:
                                t = el.inner_text().strip()
                                if len(t) > 5 and "RISS" not in t:
                                    title = t
                                    break

                        if not title or len(title) < 4:
                            detail.close()
                            continue

                        # 저자
                        author = ""
                        for sel in [".author", ".writer", "dd.author", ".artiWriter"]:
                            el = detail.query_selector(sel)
                            if el:
                                author = el.inner_text().strip()
                                break

                        # 연도
                        year = ""
                        for sel in [".year", ".pubYear", "dd.year", ".pubInfo"]:
                            el = detail.query_selector(sel)
                            if el:
                                year = el.inner_text().strip()[:4]
                                break

                        # 학술지
                        journal = ""
                        for sel in [".journalInfo", ".publisher", "dd.journal", ".journalName"]:
                            el = detail.query_selector(sel)
                            if el:
                                journal = el.inner_text().strip()
                                break

                        # 초록
                        abstract = ""
                        for sel in [".abstractTxt", ".abstract", "#abstract", ".cont_abstract", ".summary"]:
                            el = detail.query_selector(sel)
                            if el:
                                abstract = el.inner_text().strip()
                                break

                        print(f"  수집: {title[:40]}")

                        # Gemini 요약
                        summary = ""
                        if abstract and GEMINI_API_KEY:
                            print(f"    요약 중...")
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
