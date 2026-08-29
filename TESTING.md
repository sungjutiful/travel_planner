# 테스트 기록 (Travel Planner)

미션 요구사항의 각 항목을 실제로 실행/검증한 기록입니다.

## 1. 정상 실행 (계절/도시별 추천 확인)

    ./venv/bin/python3 travel_planner.py --date "2026-03-15"
    ./venv/bin/python3 travel_planner.py --date "2026-07-20"
    ./venv/bin/python3 travel_planner.py --date "2026-12-25"

- 3월: 제주도 (유채꽃 축제)
- 7월: 제주도 (해변 축제)
- 12월: 서울 (크리스마스 마켓)

날짜에 따라 다른 도시/이벤트가 추천되고, results/ 폴더에 날짜별로 JSON+MD가 정상 누적 저장됨.

## 2. 날짜 형식 오류

    ./venv/bin/python3 travel_planner.py --date "2026/03/15"

사용법 안내 출력 후 정상 종료.

## 3. 필수 옵션(--date) 누락

    ./venv/bin/python3 travel_planner.py

argparse가 자동으로 필수 인자 누락 에러 출력.

## 4. API 키 미설정

    mv .env .env.backup
    ./venv/bin/python3 travel_planner.py --date "2026-03-15"
    mv .env.backup .env

"API 키가 설정되지 않았습니다" 메시지 출력 후 즉시 종료.

## 5. 지도 API 인증 실패 (403) - 실전 발생 케이스

Kakao 앱에서 카카오맵 서비스가 비활성화되어 있던 상태에서 발생. curl로 원인 직접 진단:

    curl -G "https://dapi.kakao.com/v2/local/search/keyword.json" --data-urlencode "query=제주도 맛집" -H "Authorization: KakaoAK $(grep KAKAO_REST_API_KEY .env | cut -d '=' -f2)"

응답: errorType=NotAuthorizedError, message="App(Travel-Planner) disabled OPEN_MAP_AND_LOCAL service."

원인 확인 후 카카오맵 서비스가 활성화된 앱으로 키 교체하여 해결. 이 상황에서도 프로그램은 "맛집 섹션 데이터 없음" 처리 후 정상적으로 리포트까지 생성함을 확인.

## 6. 맛집 검색 결과 0건

    ./venv/bin/python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); import travel_planner as tp; errors = []; result = tp.search_restaurants(os.getenv('KAKAO_REST_API_KEY'), 'ㅁㄴㅇㄹㅁㄴㅇㄹ존재하지않는지명', errors); print('결과:', result); print('errors:', errors)"

결과: [] / errors: EMPTY_RESULT 타입으로 정상 기록됨.

리포트까지 이어서 확인:

    ./venv/bin/python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); import travel_planner as tp; errors = []; recommendation = {'recommended_city': '존재하지않는지명', 'weather': '테스트용 날씨', 'events': ['테스트 이벤트'], 'reason': '테스트용 추천 이유'}; restaurants = tp.search_restaurants(os.getenv('KAKAO_REST_API_KEY'), '존재하지않는지명', errors); report = tp.generate_report(os.getenv('OPENAI_API_KEY'), '2026-01-01', recommendation, restaurants, errors); print(report)"

"맛집 추천" 섹션에 "데이터 없음" 정상 표기, "오류 요약"에 EMPTY_RESULT 기록됨을 확인.

## 7. LLM JSON 파싱 실패 → 1회 재시도 → 폴백

call_openai()를 mock으로 교체해 항상 파싱 불가능한 텍스트를 반환하도록 강제:

    ./venv/bin/python3 -c "import travel_planner as tp; tp.call_openai = lambda api_key, system_prompt, user_prompt: '이건 JSON이 아닙니다. 파싱 실패 유도용 텍스트.'; errors = []; result = tp.get_recommendation('dummy_key', '2026-01-01', errors); print('최종 결과:', result); print('errors:', errors)"

결과: recommended_city가 기본값 "서울"로 폴백되고, errors에 PARSE_ERROR_RETRY와 PARSE_ERROR_FINAL이 순서대로 기록됨. 1회 재시도 후에도 실패 시 무한 재시도 없이 기본값으로 폴백하여 파이프라인이 계속 진행됨을 확인.

## 8. 개발 환경 트러블슈팅

| 문제 | 원인 | 해결 |
|---|---|---|
| TypeError: type object is not subscriptable | Python 3.8에서 tuple[str, str] 문법 미지원 | 파일 상단에 from __future__ import annotations 추가 |
| externally-managed-environment | 시스템 Python(Homebrew) 직접 설치 차단 | venv 생성 후 그 안에 패키지 설치 |
| Kakao 403 (OPEN_MAP_AND_LOCAL 비활성화) | 앱에서 카카오맵 서비스 꺼짐, 비즈월렛/비즈앱 미전환 | 본인인증 후 비즈앱 전환 또는 이미 활성화된 앱으로 키 교체 |
