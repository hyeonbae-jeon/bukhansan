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
        print(f"  Gemini 오류: {resp.status_code}")
    except Exception as e:
        print(f"  요약 실패: {e}")
    return ""

def fetch_papers():
    papers = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="ko-KR",
            java_script_enabled=True,
        )

        # 봇 감지 우회
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR','ko','en-US','en'] });
            window.chrome = { runtime: {} };
        """)

        # 먼저 메인 페이지 방문해서 쿠키/세션 확보
        print("RISS 메인 페이지 접속 중...")
        main_page = context.new_page()
        main_page.goto("https://www.riss.kr", timeout=30000)
        main_page.wait_for_timeout(3000)
        print(f"  메인 페이지 로드 완료: {len(main_page.content())} bytes")
        main_page.close()

        for keyword, category in KEYWORDS.items():
            print(f"\n[검색] '{keyword}'")
            page = context.new_page()

            # XHR 응답 캡처
            captured_links = []

            def handle_response(response):
                url = response.url
                if "DetailView" in url and url not in captured_links:
                    captured_links.append(url)

            page.on("response", handle_response)

            try:
                search_url = f"https://www.riss.kr/search/Search.do?queryText={keyword}&colName=re_all&searchGubun=true"
                page.goto(search_url, timeout=30000)

                # networkidle 대기 (JS 렌더링 완료까지)
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except:
                    pass
                page.wait_for_timeout(5000)

                html_content = page.content()
                print(f"  HTML 길이: {len(html_content)}")

                # 첫 번째 검색어만 디버그 저장
                if keyword == "북한산":
                    with open("debug_main.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    print("  debug_main.html 저장됨")

                # 선택자 시도
                links = []
                selectors = [
                    "a[href*='DetailView']",
                    "a[href*='detail']",
                    ".srchResultListW li a",
                    "#searchResultListBox li a",
                    ".listTyle li a",
                    "ul.resultList li a",
                ]
                for sel in selectors:
                    found = page.query_selector_all(sel)
                    print(f"  선택자 '{sel}': {len(found)}개")
                    if found:
                        links = found
                        break

                # XHR로 캡처된 링크도 활용
                print(f"  XHR 캡처 링크: {len(captured_links)}개")

                hrefs = set()
                for link in links:
                    href = link.get_attribute("href") or ""
                    if "Detail" in href:
                        if not href.startswith("http"):
                            href = "https://www.riss.kr" + href
                        hrefs.add(href)
                hrefs.update(captured_links)

                print(f"  총 논문 링크: {len(hrefs)}개")

                for href in list(hrefs)[:10]:
                    if href in seen:
                        continue
                    seen.add(href)

                    detail = context.new_page()
                    try:
                        detail.goto(href, timeout=30000)
                        try:
                            detail.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            pass
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
                        for sel in [".author", ".writer", "dd.author", ".artiWriter", ".authorName"]:
                            el = detail.query_selector(sel)
                            if el:
                                author = el.inner_text().strip()
                                break

                        year = ""
                        for sel in [".year", ".pubYear", "dd.year", ".pubInfo"]:
                            el = detail.query_selector(sel)
                            if el:
                                year = el.inner_text().strip()[:4]
                                break

                        journal = ""
                        for sel in [".journalInfo", ".publisher", "dd.journal", ".journalName"]:
                            el = detail.query_selector(sel)
                            if el:
                                journal = el.inner_text().strip()
                                break

                        abstract = ""
                        for sel in [".abstractTxt", ".abstract", "#abstract", ".cont_abstract", ".summary"]:
                            el = detail.query_selector(sel)
                            if el:
                                abstract = el.inner_text().strip()
                                break

                        print(f"  수집: {title[:40]}")

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
