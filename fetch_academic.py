import os
import json
import time
import requests
from bs4 import BeautifulSoup

# GitHub Secrets에서 가져올 API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

def get_ai_summary(abstract_text):
    """초록 내용을 읽어 Gemini AI를 통해 2~3줄 요약본을 생성합니다."""
    if not GEMINI_API_KEY or not abstract_text or len(abstract_text.strip()) < 20:
        return "요약 정보를 가져올 수 없습니다. 원문을 참조하세요."
    
    prompt = f"다음은 학술 논문의 초록입니다. 일반인도 이해하기 쉽게 2~3줄 이내의 명확한 문장으로 핵심만 요약해줘:\n\n{abstract_text}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(GEMINI_URL, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        print(f"AI 요약 생성 중 오류: {e}")
    return "요약 생성 오류 (원문 링크를 확인하세요)"

def crawl_naver_academic():
    # 분야별 검색 키워드 매핑 (네이버 통합 전문자료 영역 크롤링)
    categories = {
        "식생": "resource",
        "산사태": "disaster",
        "둘레길": "tour"
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    papers = []
    
    for keyword, cat in categories.items():
        search_query = f"북한산 {keyword}"
        print(f"[{search_query}] 네이버 학술/전문자료 검색 수집 시작...")
        
        # 네이버 전문자료(doc) 탭 검색 주소
        url = f"https://search.naver.com/search.naver?where=doc&query={requests.utils.quote(search_query)}"
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code != 200: continue
            
            soup = BeautifulSoup(res.text, 'html.parser')
            # 네이버 통합검색 웹/전문자료 리스트 구조 파싱
            items = soup.select('ul.lst_total > li')
            
            for item in items:
                title_el = item.select_one('a.api_txt_lines.total_tit')
                if not title_el: continue
                
                title = title_el.text.strip()
                link = title_el['href']
                
                # 네이버 뷰어상 노출된 초록(요약글 덩어리) 추출
                dsc_el = item.select_one('.total_dsc .api_txt_lines')
                raw_abstract = dsc_el.text.strip() if dsc_el else ""
                
                # 출처/저자 정보 추출
                info_el = item.select_one('.total_sub .sub_txt')
                source_info = info_el.text.strip() if info_el else "네이버 학술 자료"
                
                print(f" - 논문 발견: {title}")
                
                # 원문 링크 분기 (RISS 링크인지 네이버 학술정보 등 타 사이트인지 감지)
                origin = "네이버 학술정보"
                if "riss.kr" in link:
                    origin = "RISS"
                elif "dbpia" in link:
                    origin = "DBpia"
                
                # 가져온 초록 기반 AI 자동 요약 요청
                ai_summary = get_ai_summary(raw_abstract)
                
                papers.append({
                    "title": title,
                    "author_source": source_info,
                    "category": cat,
                    "summary": ai_summary,
                    "origin_site": origin,
                    "link": link
                })
                
                time.sleep(2) # API 및 크롤링 차단 방지 휴식
        except Exception as e:
            print(f"검색 진행 중 에러 발생: {e}")
            
    # 결과를 json 파일로 저장하여 웹사이트 데이터 소스로 공급
    with open("papers.json", "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)
    print(f"수집 성공! 총 {len(papers)}개의 논문이 papers.json에 업데이트되었습니다.")

if __name__ == "__main__":
    crawl_naver_academic()
