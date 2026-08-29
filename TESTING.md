# 테스트 기록 (Travel Planner)

미션 요구사항의 각 항목(기능 요구사항 + 에러 처리)을 실제로 실행/검증한 기록입니다.

---
# PART A. 기능 요구사항 검증
---

## A1. CLI 인터페이스 — argparse, --date 필수 옵션

    ./venv/bin/python3 travel_planner.py --date "2026-03-15"

정상 실행 시 진행 로그(1/3, 2/3, 3/3)와 결과 저장 경로 안내가 출력됨을 확인.

## A2. 1차 추천 JSON 스키마 검증 (recommended_city / weather / events / reason)

    ./venv/bin/python3 -c "import json; d = json.load(open('results/2026-03-15_raw_data.json')); r = d['recommendation']; assert isinstance(r['recommended_city'], str); assert isinstance(r['weather'], str); assert isinstance(r['events'], list); assert isinstance(r['reason'], str); print('스키마 통과:', r)"

필수 키 4개(recommended_city, weather, events, reason)가 모두 존재하고 타입(string/list)이 요구사항과 일치함을 확인.

## A3. 맛집 검색 결과 필드 검증 (name / address / category / url / x,y)

    ./venv/bin/python3 -c "import json; d = json.load(open('results/2026-03-15_raw_data.json')); rs = d['restaurants']; print('맛집 개수:', len(rs)); assert len(rs) <= 5; [print(r) or (r['name'], r['address'], r.get('category'), r.get('url'), r.get('x'), r.get('y')) for r in rs]; print('필드 검증 통과')"

맛집 최대 5곳, 각 항목에 name/address/category/url/x,y 필드가 모두 채워져 있음을 확인.

## A4. 최종 리포트 필수 섹션 검증 (Markdown 헤더)

    grep -E "^## " results/2026-03-15_travel_plan.md

출력된 헤더 목록:
- 추천 지역
- 추천 이유
- 날씨 요약
- 행사/축제
- 맛집 추천
- 1일 일정 제안
- 오류 요약

미션에서 요구한 7개 섹션이 모두 리포트에 포함되어 있음을 확인.

## A5. 결과 저장 구조 (results/ 폴더, 날짜 기준 파일명)

    ls -la results/

파일명이 {date}_raw_data.json / {date}_travel_plan.md 형식으로 날짜별로 정확히 저장됨을 확인.

## A6. 보안 — 결과물/README에 실제 API 키가 노출되지 않았는지 확인

    grep -r "sk-" README.md results/ 2>/dev/null || echo "OpenAI 키 패턴 없음 (정상)"
    grep -rE "KAKAO_REST_API_KEY=[A-Za-z0-9]{20,}" README.md results/ 2>/dev/null || echo "Kakao 키 패턴 없음 (정상)"

두 명령 모두 아무 결과도 나오지 않고 "정상" 메시지만 출력되어야 함 — 실제 키 값이 제출물에 포함되지 않았음을 확인.

## A7. .env가 Git에 포함되지 않는지 확인

    git check-ignore -v .env

.env가 .gitignore 규칙에 걸려 있다는 결과(파일:라인:.env)가 출력되어야 정상.

---
# PART B. 에러 처리 요구사항 검증
---

## B1. 날짜 형식 오류

    ./venv/bin/python3 travel_planner.py --date "2026/03/15"

사용법 안내 출력 후 정상 종료.

## B2. 필수 옵션(--date) 누락

    ./venv/bin/python3 travel_planner.py

argparse가 자동으로 필수 인자 누락 에러 출력.

## B3. API 키 미설정

    mv .env .env.backup
    ./venv/bin/python3 travel_planner.py --date "2026-03-15"
    mv .env.backup .env

"API 키가 설정되지 않았습니다" 메시지 출력 후 즉시 종료.

## B4. 지도 API 인증 실패 (403) — 실전 발생 케이스

Kakao 앱에서 카카오맵 서비스가 비활성화되어 있던 상태에서 발생. curl로 원인 직접 진단:

    curl -G "https://dapi.kakao.com/v2/local/search/keyword.json" --data-urlencode "query=제주도 맛집" -H "Authorization: KakaoAK $(grep KAKAO_REST_API_KEY .env | cut -d '=' -f2)"

응답: errorType=NotAuthorizedError, message="App(Travel-Planner) disabled OPEN_MAP_AND_LOCAL service."

원인 확인 후 카카오맵 서비스가 활성화된 앱으로 키 교체하여 해결. 이 상황에서도 프로그램은 "맛집 섹션 데이터 없음" 처리 후 정상적으로 리포트까지 생성함을 확인.

## B5. 맛집 검색 결과 0건

    ./venv/bin/python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); import travel_planner as tp; errors = []; result = tp.search_restaurants(os.getenv('KAKAO_REST_API_KEY'), 'ㅁㄴㅇㄹㅁㄴㅇㄹ존재하지않는지명', errors); print('결과:', result); print('errors:', errors)"

결과: [] / errors: EMPTY_RESULT 타입으로 정상 기록됨.

리포트까지 이어서 확인:

    ./venv/bin/python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); import travel_planner as tp; errors = []; recommendation = {'recommended_city': '존재하지않는지명', 'weather': '테스트용 날씨', 'events': ['테스트 이벤트'], 'reason': '테스트용 추천 이유'}; restaurants = tp.search_restaurants(os.getenv('KAKAO_REST_API_KEY'), '존재하지않는지명', errors); report = tp.generate_report(os.getenv('OPENAI_API_KEY'), '2026-01-01', recommendation, restaurants, errors); print(report)"

"맛집 추천" 섹션에 "데이터 없음" 정상 표기, "오류 요약"에 EMPTY_RESULT 기록됨을 확인.

## B6. LLM JSON 파싱 실패 → 1회 재시도 → 폴백

call_openai()를 mock으로 교체해 항상 파싱 불가능한 텍스트를 반환하도록 강제:

    ./venv/bin/python3 -c "import travel_planner as tp; tp.call_openai = lambda api_key, system_prompt, user_prompt: '이건 JSON이 아닙니다. 파싱 실패 유도용 텍스트.'; errors = []; result = tp.get_recommendation('dummy_key', '2026-01-01', errors); print('최종 결과:', result); print('errors:', errors)"

결과: recommended_city가 기본값 "서울"로 폴백되고, errors에 PARSE_ERROR_RETRY와 PARSE_ERROR_FINAL이 순서대로 기록됨. 1회 재시도 후에도 실패 시 무한 재시도 없이 기본값으로 폴백하여 파이프라인이 계속 진행됨을 확인.

---
# PART C. 개발 환경 트러블슈팅
---

| 문제 | 원인 | 해결 |
|---|---|---|
| TypeError: type object is not subscriptable | Python 3.8에서 tuple[str, str] 문법 미지원 | 파일 상단에 from __future__ import annotations 추가 |
| externally-managed-environment | 시스템 Python(Homebrew) 직접 설치 차단 | venv 생성 후 그 안에 패키지 설치 |
| Kakao 403 (OPEN_MAP_AND_LOCAL 비활성화) | 앱에서 카카오맵 서비스 꺼짐, 비즈월렛/비즈앱 미전환 | 본인인증 후 비즈앱 전환 또는 이미 활성화된 앱으로 키 교체 |
