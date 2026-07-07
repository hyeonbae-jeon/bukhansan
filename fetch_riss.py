import asyncio
import json
import re
from playwright.async_api import async_playwright

CATEGORY_KEYWORDS = {
    "재난": ["산사태", "홍수", "토사", "붕괴", "재난", "위험", "지반", "침수", "산불", "사면", "위협", "낙석"],
    "탐방": ["탐방", "등산", "이용객", "입산", "등반", "방문", "탐방객", "행동", "트레킹", "방문객", "탐방로"],
    "생태": ["식물", "동물", "조류", "군락", "생태", "식생", "서식", "야생", "포유", "곤충", "양서", "어류", "균류"],
    "역사문화": ["문화재", "성곽", "유적", "사찰", "역사", "문화", "북한산성", "사적", "불교", "절", "성지", "고적"],
}

def classify(title, abstract=""):
    text = title + " " + abstract
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return cat
    return "자원조사"

async def fetch_papers():
    papers = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        search_url = (
            "https://www.riss.kr/search/Search.do"
            "?query=%EB%B6%81%ED%95%9C%EC%82%B0"
            "&isDetailSearch=N&searchGubun=true"
            "&colName=re_a_kor&pageSize=100&orderBy=score"
        )

        print(f"[1] RISS 접속 중...")
        await page.goto(search_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(5000)

        # 디버그용 HTML 저장
        html = await page.content()
        with open("debug_riss.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[2] HTML 저장 완료 (길이: {len(html)})")

        # 핵심: RISS 상세 페이지 링크를 가진 <a> 태그만 추출
        # 논문 상세 링크는 반드시 DetailView.do 또는 searchdetail/DetailView 포함
        all_links = await page.query_selector_all("a[href]")
        print(f"[3] 전체 링크 수: {len(all_links)}")

        detail_links = []
        for link in all_links:
            href = await link.get_attribute("href") or ""
            if "DetailView" in href or "detail/Detail" in href:
                detail_links.append(link)

        print(f"[4] 상세 링크 수: {len(detail_links)}")

        for link in detail_links:
            try:
                href = await link.get_attribute("href") or ""
                if not href.startswith("http"):
                    href = "https://www.riss.kr" + href

                title = (await link.inner_text()).strip()
                title = re.sub(r"\s+", " ", title)

                # 제목 필터: 한국어 10자 이상
                if len(title) < 10:
                    continue
                if not re.search(r"[가-힣]", title):
                    continue

                # 부모 요소에서 추가 정보 추출
                parent_text = await link.evaluate("""el => {
                    let p = el.closest("li") || el.closest("tr") || el.parentElement;
                    return p ? p.innerText : "";
                }""")

                # 연도 추출
                year_match = re.search(r"\b(19|20)\d{2}\b", parent_text)
                year = year_match.group() if year_match else ""

                # 저자 추출 (연도 앞 텍스트에서)
                author = ""
                if year:
                    before_year = parent_text[:parent_text.find(year)]
                    lines = [l.strip() for l in before_year.split("\n") if l.strip()]
                    if len(lines) >= 2:
                        author = lines[-1][:50]

                # 학술지명 추출 (연도 뒤 텍스트)
                journal = ""
                if year:
                    after_year = parent_text[parent_text.find(year) + 4:].strip()
                    lines = [l.strip() for l in after_year.split("\n") if l.strip() and len(l.strip()) > 2]
                    if lines:
                        journal = lines[0][:60]

                paper_id = re.sub(r"[^\w]", "_", title[:40])

                if paper_id not in papers:
                    papers[paper_id] = {
                        "id": paper_id,
                        "title": title,
                        "authors": author,
                        "year": year,
                        "journal": journal,
                        "abstract": "",
                        "category": classify(title),
                        "riss_url": href,
                        "full_text_url": ""
                    }
                    print(f"  수집: {title[:60]}")

            except Exception as e:
                print(f"  오류: {e}")
                continue

        print(f"[5] 총 {len(papers)}건 수집")

        # 결과 없으면 구조 디버그 출력
        if len(papers) == 0:
            print("[DEBUG] 페이지 내 모든 ID 목록:")
            ids = await page.evaluate("""
                () => Array.from(document.querySelectorAll("[id]"))
                    .map(e => e.id + " / " + e.tagName)
                    .slice(0, 30)
            """)
            for i in ids:
                print(f"  {i}")

        await browser.close()

    return list(papers.values())


if __name__ == "__main__":
    papers = asyncio.run(fetch_papers())

    if papers:
        with open("papers.json", "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
        print(f"=== 총 수집: {len(papers)}건 ===")
        print("papers.json 저장 완료")
    else:
        print("ERROR: 수집된 논문 없음 — debug_riss.html 확인 필요")
        raise SystemExit(1)
