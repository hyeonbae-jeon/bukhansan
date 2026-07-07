import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import json
import re
import time
import sys
from datetime import datetime

RISS_API_KEY = "70aaa00wqm60acd00aaa00ab01za378a"

def categorize(text):
    t = text or ""
    if re.search(r"산사태|홍수|재난|토사|침수|피해|위험|붕괴|산불|방재|재해", t):
        return "재난"
    if re.search(r"탐방|등산|이용객|방문자|탐방로|관광|탐방객|입산|등반", t):
        return "탐방"
    if re.search(r"식물|동물|조류|곤충|서식지|생태계|군락|종다양|식생|야생|포유", t):
        return "생태"
    if re.search(r"문화재|성곽|유적|역사|전통|사찰|불교|문화|사적|건축|유물", t):
        return "역사문화"
    return "자원조사"

def make_paper(idx, title, author, year, journal, abstract, link, keyword):
    cat_text = f"{title} {abstract} {keyword}"
    keywords = [k.strip() for k in (keyword or "").split(",") if k.strip()]
    return {
        "id": f"riss_{idx}",
        "title": (title or "").strip() or "제목 없음",
        "author": (author or "").strip() or "저자 미상",
        "year": str(year or "").strip(),
        "journal": (journal or "").strip(),
        "category": categorize(cat_text),
        "summary": (abstract or "").strip() or "초록 정보가 없습니다.",
        "rissUrl": (link or "").strip() or "https://www.riss.kr/search/Search.do?queryText=북한산",
        "keywords": keywords,
        "hasFulltext": bool(link and ("viewer" in link.lower() or "fulltext" in link.lower()))
    }

# ───────────────────────────────────────────────────────────────
# 방법 1: RISS OpenAPI (XML)
# ───────────────────────────────────────────────────────────────
def try_api():
    print("[API] RISS OpenAPI 시도 중...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/xml, application/xml, */*",
        "Referer": "https://www.riss.kr"
    }
    url = (
        f"https://www.riss.kr/openapi/search"
        f"?apiKey={RISS_API_KEY}"
        f"&query=%EB%B6%81%ED%95%9C%EC%82%B0"
        f"&start=1&display=100&sortType=RANK"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(f"[API] 상태코드: {resp.status_code}")
        text = resp.text.strip()
        print(f"[API] 응답 앞부분: {text[:200]}")

        if text.startswith("<!DOCTYPE") or text.lower().startswith("<html"):
            print("[API] HTML 응답 수신 — API 미작동, 스크래핑으로 전환")
            return None

        root = ET.fromstring(text)
        items = root.findall(".//item")
        print(f"[API] 아이템 수: {len(items)}")
        if not items:
            return None

        papers = []
        for i, item in enumerate(items):
            papers.append(make_paper(
                i,
                item.findtext("title", ""),
                item.findtext("author", ""),
                item.findtext("pubYear", ""),
                item.findtext("journalName", "") or item.findtext("publisher", ""),
                item.findtext("abstract", ""),
                item.findtext("link", ""),
                item.findtext("keyword", "")
            ))
        print(f"[API] 파싱 완료: {len(papers)}건")
        return papers

    except Exception as e:
        print(f"[API] 오류: {e}")
        return None

# ───────────────────────────────────────────────────────────────
# 방법 2: RISS 검색 결과 페이지 스크래핑
# ───────────────────────────────────────────────────────────────
def try_scraping():
    print("[SCRAPE] RISS 페이지 스크래핑 시도 중...")
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        # 세션 쿠키 수집
        session.get("https://www.riss.kr", headers=headers, timeout=30)
        time.sleep(2)
    except Exception as e:
        print(f"[SCRAPE] 홈 접속 오류 (무시): {e}")

    # 검색어 목록 (분야별 수집)
    queries = ["북한산", "북한산 생태", "북한산 재난", "북한산 탐방", "북한산 역사"]
    all_papers = []
    seen_titles = set()

    for q_idx, query in enumerate(queries):
        print(f"[SCRAPE] 검색어: {query}")
        url = "https://www.riss.kr/search/Search.do"
        params = {
            "queryText": query,
            "searchGubun": "true",
            "strQuery": query,
            "detailSearch": "false",
            "orderBy": "RANK",
            "onlyAbstract": "false",
            "isDetailSearch": "N",
            "FullTextYn": "N",
            "start": 1,
            "display": 100
        }

        try:
            resp = session.get(url, params=params, headers=headers, timeout=30)
            print(f"[SCRAPE] 상태코드: {resp.status_code}, 길이: {len(resp.text)}")
        except Exception as e:
            print(f"[SCRAPE] 요청 오류: {e}")
            continue

        soup = BeautifulSoup(resp.text, "lxml")

        # 여러 셀렉터 시도
        items = (
            soup.select("ul.result_list > li") or
            soup.select(".result_list li") or
            soup.select("li.list_item") or
            soup.select(".srch_result li") or
            soup.select("#content li") or
            []
        )
        print(f"[SCRAPE] 검색어 '{query}': {len(items)}개 항목")

        for i, item in enumerate(items):
            # 제목 + 링크
            title_elem = (
                item.select_one("a.title") or
                item.select_one(".title a") or
                item.select_one("strong.title") or
                item.select_one("a[class*=title]") or
                item.select_one("dt a") or
                item.select_one("h3 a") or
                item.select_one("h4 a")
            )
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            link = title_elem.get("href", "")
            if link and not link.startswith("http"):
                link = "https://www.riss.kr" + link

            # 저자
            author = ""
            for sel in [".author", "[class*=author]", ".writer", ".people"]:
                el = item.select_one(sel)
                if el:
                    author = el.get_text(strip=True)
                    break

            # 연도
            year = ""
            year_text = item.get_text()
            m = re.search(r"(19|20)\d{2}", year_text)
            if m:
                year = m.group()

            # 학술지/출판사
            journal = ""
            for sel in [".journal", "[class*=journal]", ".source", ".publisher", ".org"]:
                el = item.select_one(sel)
                if el:
                    journal = el.get_text(strip=True)
                    break

            # 초록
            abstract = ""
            for sel in [".abstract", "[class*=abstract]", ".summary", ".desc", "p"]:
                el = item.select_one(sel)
                if el:
                    txt = el.get_text(strip=True)
                    if len(txt) > 30:
                        abstract = txt
                        break

            paper = make_paper(
                q_idx * 1000 + i,
                title, author, year, journal, abstract, link, ""
            )
            all_papers.append(paper)
            print(f"  [{len(all_papers)}] {title[:60]}")

        time.sleep(1.5)

    print(f"[SCRAPE] 총 수집: {len(all_papers)}건")
    return all_papers if all_papers else None

# ───────────────────────────────────────────────────────────────
# 메인
# ───────────────────────────────────────────────────────────────
def main():
    papers = try_api()

    if not papers:
        papers = try_scraping()

    if not papers:
        print("ERROR: API와 스크래핑 모두 실패")
        sys.exit(1)

    output = {
        "updated": datetime.now().isoformat(),
        "total": len(papers),
        "papers": papers
    }

    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ papers.json 저장 완료: {len(papers)}건")

if __name__ == "__main__":
    main()
