"""
Gemini API 연동만 단독으로 테스트하는 스크립트.
스크래핑 없이 미리 준비된 샘플 논문 하나로 실제 호출이 되는지, 어디서 막히는지 확인한다.

로컬에서 실행: GEMINI_API_KEY=발급받은키 python test_gemini.py
GitHub Actions에서 실행: test-gemini.yml 워크플로우 참고
"""
import os
import re
import json
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.5-flash-lite:generateContent?key={GEMINI_API_KEY}"
)

SAMPLE_TITLE = "국립공원 탐방객의 자연보호의식과 생태관광태도에 관한 연구 -북한산 국립공원을 중심으로-"
SAMPLE_ABSTRACT = (
    "국민소득의 증가, 여가시간의 확대, 웰빙 선호도의 확산 등으로 인해 국립공원에 대한 방문수요는 "
    "해마다 증가하고 있다. 그러나 우리나라의 국립공원은 보존하기보다 자원의 이용이라는 개념에 더욱 "
    "그 초점이 맞춰져 개발되었기 때문에, 이용객들 역시 일반관광지나 유원지로 인식하는 경향이 높다."
)

print("=" * 60)
print("1단계: GEMINI_API_KEY 환경변수가 설정되어 있는지 확인")
print("=" * 60)
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY가 비어있습니다.")
    print("   → GitHub Secrets에 정확히 'GEMINI_API_KEY'라는 이름으로 등록했는지 확인하세요.")
    print("   → 로컬 테스트라면: GEMINI_API_KEY=발급받은키 python test_gemini.py 처럼 실행하세요.")
    raise SystemExit(1)
else:
    masked = GEMINI_API_KEY[:4] + "..." + GEMINI_API_KEY[-4:] if len(GEMINI_API_KEY) > 8 else "****"
    print(f"✅ 키가 설정되어 있습니다 (일부만 표시: {masked}, 길이: {len(GEMINI_API_KEY)}자)")

print()
print("=" * 60)
print("2단계: 실제 Gemini API 호출 테스트")
print("=" * 60)

prompt = f"""너는 국립공원 관련 학술논문을 분류·요약하는 도우미다.
아래는 "북한산" 국립공원과 관련된 논문의 제목과 초록이다.

분류 기준 (반드시 이 중 하나만 고를 것):
- 재난: 산사태, 산불, 침수, 안전사고 등 재난·위험 관련
- 탐방: 등산객·탐방객 행태, 이용 실태, 관광, 트래킹 관련
- 생태: 동식물, 식생, 서식지, 산림, 생물다양성 관련
- 역사문화: 역사, 문화재, 유적, 사찰, 전통 관련
- 자원조사: 위 네 가지에 해당하지 않는 환경조사·정책·관리 등 일반 내용

제목: {SAMPLE_TITLE}
초록: {SAMPLE_ABSTRACT}

아래 JSON 형식으로만 답하고, 다른 텍스트는 절대 포함하지 마라:
{{"category": "위 5개 중 하나(한글 라벨 그대로)", "summary": "이 논문이 어떤 내용인지 2~3문장 한국어 요약", "usage": "이 논문 결과를 실제로 어떻게 활용할 수 있는지 2~3문장 한국어 제안"}}"""

try:
    resp = requests.post(
        GEMINI_URL,
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=30,
    )
    print(f"HTTP 상태 코드: {resp.status_code}")

    if resp.status_code != 200:
        print(f"❌ 호출 실패. 응답 본문:\n{resp.text[:1000]}")
        print()
        print("자주 나오는 원인:")
        print("  - 400: API 키 형식이 잘못됨 (복사할 때 앞뒤 공백/따옴표 섞였는지 확인)")
        print("  - 403: API 키가 유효하지 않거나 Generative Language API가 비활성화됨")
        print("  - 404: 모델 이름이 잘못됨 (현재 gemini-2.5-flash-lite 사용 중)")
        print("  - 429: 무료 티어 호출 한도 초과 (잠시 후 재시도)")
        raise SystemExit(1)

    print("✅ HTTP 200 — API 호출 자체는 성공")
    print()
    print("=" * 60)
    print("3단계: 응답 내용 파싱 테스트")
    print("=" * 60)

    data = resp.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
    print("모델이 보낸 원본 텍스트:")
    print("-" * 40)
    print(raw_text)
    print("-" * 40)

    cleaned = re.sub(r"```json|```", "", raw_text).strip()
    parsed = json.loads(cleaned)

    print()
    print("✅ JSON 파싱 성공:")
    print(f"  category: {parsed.get('category')}")
    print(f"  summary : {parsed.get('summary')}")
    print(f"  usage   : {parsed.get('usage')}")
    print()
    print("모든 단계 통과 — Gemini 연동 자체는 정상입니다.")

except json.JSONDecodeError as e:
    print(f"❌ JSON 파싱 실패: {e}")
    print("   → 모델이 순수 JSON이 아닌 다른 텍스트를 섞어서 반환했을 가능성이 있습니다.")
    print("   → 위 '모델이 보낸 원본 텍스트'를 확인해서 어떤 형식으로 왔는지 보세요.")
except requests.exceptions.RequestException as e:
    print(f"❌ 네트워크 오류: {e}")
