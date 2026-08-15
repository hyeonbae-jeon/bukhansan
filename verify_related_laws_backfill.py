#!/usr/bin/env python3
"""
verify_related_laws_backfill.py (1회성/재실행 가능 백필 스크립트)
------------------------------------------------------
이미 AI 분석이 끝난 논문들의 ai_analysis.related_laws(AI가 생성한 법령명 목록)를
law_matcher.py를 통해 실제 국가법령정보 API(law.go.kr)와 대조해 교체합니다.

- law_matcher.verify_related_laws()를 그대로 재사용합니다. 매칭되면 실제 현행
  법령명으로 교체하고, 매칭 안 되면 "⚠ 확인 필요: ..." 표시를 붙입니다.
- AI가 원래 생성했던 값은 related_laws_original에 보존해둡니다(대조/롤백용).
- 이미 검증된 논문(related_laws_verified_at 있음)은 건너뛰어 중복 호출을 피합니다.
  → 시간 예산 안에서 다 못 끝내도, 다시 실행하면 안 한 것부터 이어서 처리합니다.
- 요청 사이 0.2초 간격(law_matcher 내부)이라 논문 1건(법령 2~3개)당 약 0.5~1초가
  걸립니다. 전체 약 1,580건 처리에는 실행을 여러 번 나눠 돌려야 할 수 있습니다.

필요 환경변수: LAW_API_OC (국가법령정보 API 신청 시 사용한 아이디)
사용법: python3 verify_related_laws_backfill.py
"""
import json, os, time

import law_matcher

RAW_FILE = "raw_papers.json"
TIME_BUDGET_SEC = int(os.getenv("LAW_VERIFY_TIME_BUDGET_SEC") or 20 * 60)   # 기본 20분


def run():
    oc = os.getenv("LAW_API_OC")
    if not oc:
        print("[LawVerifyBackfill] LAW_API_OC 환경변수가 없습니다. "
              "저장소 Secrets에 LAW_API_OC를 등록한 뒤 다시 실행하세요.")
        return

    with open(RAW_FILE, encoding="utf-8") as f:
        papers = json.load(f)

    targets = [p for p in papers
               if p.get("ai_analysis")
               and p["ai_analysis"].get("related_laws")
               and "related_laws_verified_at" not in p["ai_analysis"]]

    print(f"[LawVerifyBackfill] 검증 대상: {len(targets)}건 "
          f"(시간 예산 {TIME_BUDGET_SEC//60}분)")

    start = time.time()
    done = 0
    for p in targets:
        if time.time() - start > TIME_BUDGET_SEC:
            print(f"[LawVerifyBackfill] 시간 예산 도달 — {done}건 처리 후 중단. "
                  f"다시 실행하면 나머지 {len(targets)-done}건부터 이어서 진행됩니다.")
            break

        ai = p["ai_analysis"]
        original = ai["related_laws"]
        verified = law_matcher.verify_related_laws(original, oc)

        ai["related_laws_original"]      = original   # 원본 보존(대조·롤백용)
        ai["related_laws"]               = verified
        ai["related_laws_verified_at"]   = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        done += 1

        # 건별 저장 — 중간에 중단돼도 그때까지 검증한 내용은 보존
        with open(RAW_FILE, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)

        if done % 50 == 0:
            print(f"[LawVerifyBackfill] {done}/{len(targets)}건 처리…")

    print(f"[LawVerifyBackfill] 완료: 이번 실행에서 {done}건 검증. "
          f"남은 대상 {len(targets)-done}건.")
    print("[LawVerifyBackfill] 'python3 indexer.py'로 papers.json을 갱신하세요.")


if __name__ == "__main__":
    run()
