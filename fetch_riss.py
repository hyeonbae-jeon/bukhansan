import json
import re
import sys
import time

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


def auto_category(text):
    if re.search(r'산사태|홍수|재난|토사|침수|붕괴|피해|위험|방재', text):
        return '재난'
    if re.search(r'탐방|등산|이용객|방문자|탐방로|관광|입산', text):
        return '탐방'
    if re.search(r'식물|동물|조류|곤충|서식지|생태계|군락|종다양|생태|야생', text):
        return '생태'
    if re.search(r'문화재|성곽|유적|역사|전통|사찰|불교', text):
        return '역사문화'
    return '자원조사'


def parse_items(html, query):
    soup = BeautifulSoup(html, 'lxml')
    title_tag = soup.title.get_text(strip=True) if soup.title else '없음'
    print(f'  페이지 타이틀: {title_tag}')

    selectors = [
        '#srchResultListW li',
        'ul.srchResultListW li',
        '.srchResultListW li',
        '#resultListArea li',
        '.result_list_wrap li',
        'li.result_item',
        'div.result_item',
        '.thesis_item',
        'ul#thesisResult li',
        '#listForm li',
        '.listBtnWrap li',
        'ul > li[class]',
        '.srch_result_list > li',
        '[id*="result"] li',
        '[class*="result"] li',
    ]

    items = []
    for sel in selectors:
        found = soup.select(sel)
        if found:
            print(f'  선택자 매치: "{sel}" → {len(found)}개')
            items = found
            break

    if not items:
        print('  !! 선택자 모두 실패 — 페이지 id/class 목록:')
        seen_cls = set()
        for tag in soup.find_all(True):
            if tag.get('id'):
                print(f'    id="{tag["id"]}" ({tag.name})')
            elif tag.get('class'):
                cls = ' '.join(tag['class'])
                if cls not in seen_cls and len(seen_cls) < 50:
                    seen_cls.add(cls)
                    print(f'    class="{cls}" ({tag.name})')
        # 구조 파악을 위해 HTML 일부 저장
        with open('debug_riss.html', 'w', encoding='utf-8') as f:
            f.write(html[:20000])
        print('  debug_riss.html 저장됨')
        return []

    papers = []
    for item in items:
        title_el = (
            item.select_one('a.lnk_name') or
            item.select_one('.tit a') or
            item.select_one('.title a') or
            item.select_one('h4 a') or
            item.select_one('h3 a') or
            item.select_one('h2 a') or
            item.select_one('a[href*="detail"]') or
            item.select_one('a[href*="Search"]') or
            item.select_one('a')
        )
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or len(title) < 4:
            continue

        href = title_el.get('href', '')
        if href and not href.startswith('http'):
            href = 'https://www.riss.kr' + href
        riss_url = href or f'https://www.riss.kr/search/Search.do?queryText={query}'

        author_el = (
            item.select_one('.writer') or
            item.select_one('.author') or
            item.select_one('[class*="author"]') or
            item.select_one('[class*="writer"]')
        )
        author = author_el.get_text(strip=True) if author_el else ''

        year = ''
        m = re.search(r'\b(19|20)\d{2}\b', item.get_text())
        if m:
            year = m.group()

        journal_el = (
            item.select_one('.journal_name') or
            item.select_one('[class*="journal"]') or
            item.select_one('.publisher')
        )
        journal = journal_el.get_text(strip=True) if journal_el else ''

        abstract_el = (
            item.select_one('.abstract') or
            item.select_one('[class*="abstract"]') or
            item.select_one('.summary')
        )
        summary = abstract_el.get_text(strip=True) if abstract_el else ''

        kw_els = item.select('.keyword a, [class*="keyword"] a, .tag a')
        keywords = [k.get_text(strip=True) for k in kw_els]

        papers.append({
            'title': title,
            'author': author,
            'year': year,
            'journal': journal,
            'category': auto_category(title + ' ' + summary),
            'summary': summary or '초록 정보 없음',
            'rissUrl': riss_url,
            'keywords': keywords,
        })

    return papers


def main():
    queries = [
        '북한산',
        '북한산 생태',
        '북한산 재난',
        '북한산 탐방',
        '북한산 역사',
        '북한산 자원',
    ]

    all_papers = []
    seen_titles = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        ctx = browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '                'AppleWebKit/537.36 (KHTML, like Gecko) '                'Chrome/120.0.0.0 Safari/537.36'
            ),
            locale='ko-KR',
            viewport={'width': 1280, 'height': 800},
        )

        for query in queries:
            print(f'\n[검색] "{query}"')
            try:
                page = ctx.new_page()
                url = (
                    'https://www.riss.kr/search/Search.do'
                    f'?queryText={query}'
                    '&isDetailSearch=N&searchGubun=true&gubun=t'
                    '&sortOrder=RANK&saveSrchHistory=Y'
                )
                resp = page.goto(url, wait_until='networkidle', timeout=30000)
                print(f'  HTTP {resp.status}')
                time.sleep(3)

                html = page.content()
                print(f'  HTML 길이: {len(html)}')

                papers = parse_items(html, query)
                print(f'  수집: {len(papers)}편')

                for paper in papers:
                    if paper['title'] not in seen_titles:
                        seen_titles.add(paper['title'])
                        paper['id'] = len(all_papers) + 1
                        all_papers.append(paper)

                page.close()
                time.sleep(1)

            except Exception as exc:
                import traceback
                print(f'  오류: {exc}')
                traceback.print_exc()

        browser.close()

    print(f'\n=== 총 수집: {len(all_papers)}편 ===')

    with open('papers.json', 'w', encoding='utf-8') as f:
        json.dump(all_papers, f, ensure_ascii=False, indent=2)
    print('papers.json 저장 완료')

    if not all_papers:
        print('ERROR: 논문 0편')
        sys.exit(1)


main()
