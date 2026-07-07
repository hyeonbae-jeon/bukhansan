import requests
import json
import re
import datetime

# RISS API 키 (하드코딩 — 이미 index.html에 공개됨)
RISS_API_KEY = '70aaa00wqm60acd00aaa00ab01za378a'

def auto_category(text):
    t = text or ''
    if re.search(r'산사태|홍수|재난|토사|침수|피해|붕괴|방재|재해|위험', t):
        return '재난'
    if re.search(r'탐방|등산|이용객|방문자|탐방로|관광|입산|탐방객', t):
        return '탐방'
    if re.search(r'식물|동물|조류|곤충|서식지|생태계|군락|종다양|생물|수목|식생', t):
        return '생태'
    if re.search(r'문화재|성곽|유적|역사|전통|사찰|불교|문화|유산', t):
        return '역사문화'
    return '자원조사'

def fetch_papers():
    url = 'https://www.riss.kr/openapi/search'
    params = {
        'apiKey': RISS_API_KEY,
        'query': '북한산',
        'start': 1,
        'display': 100,
        'format': 'json'
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    print(f'[INFO] RISS API 요청 중...')
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    print(f'[INFO] 응답 코드: {resp.status_code}')

    # 응답 앞부분 출력 (디버깅)
    print(f'[DEBUG] 응답 앞 300자: {resp.text[:300]}')

    data = resp.json()

    # 다양한 응답 구조 처리
    items = []
    if isinstance(data, list):
        items = data
    elif 'channel' in data:
        ch = data['channel']
        if 'item' in ch:
            items = ch['item'] if isinstance(ch['item'], list) else [ch['item']]
    elif 'items' in data:
        items = data['items'] if isinstance(data['items'], list) else [data['items']]
    elif 'item' in data:
        items = data['item'] if isinstance(data['item'], list) else [data['item']]
    elif 'results' in data:
        items = data['results']

    print(f'[INFO] 파싱된 논문 수: {len(items)}')

    papers = []
    for i, item in enumerate(items):
        text = (str(item.get('title', '')) + ' ' +
                str(item.get('keyword', '')) + ' ' +
                str(item.get('abstract', '')))

        paper = {
            'id': str(item.get('rissId') or item.get('control_no') or f'riss_{i}'),
            'title': item.get('title', '제목 없음'),
            'author': item.get('author', '저자 미상'),
            'year': str(item.get('pubYear') or item.get('pub_year') or ''),
            'journal': str(item.get('journalName') or item.get('publisher') or item.get('pub_name') or ''),
            'category': auto_category(text),
            'summary': item.get('abstract') or '초록 정보가 없습니다.',
            'keywords': [k.strip() for k in str(item.get('keyword', '')).split(',') if k.strip()],
            'rissUrl': item.get('link') or 'https://www.riss.kr/search/Search.do?queryText=북한산',
            'fullTextUrl': item.get('fullTextUrl') or item.get('full_text_url') or ''
        }
        papers.append(paper)

    return papers

if __name__ == '__main__':
    papers = fetch_papers()
    result = {
        'total': len(papers),
        'updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC'),
        'papers': papers
    }
    with open('papers.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'[완료] papers.json 저장 — {len(papers)}건')
