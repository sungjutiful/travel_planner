# 설계 노트 (Travel Planner)

구현 과정에서 정리한 설계 결정과 개념 노트.

---

## 1. 전체 구조

사용자 입력(날짜) → LLM 1차 추천(JSON) → 지도 API 맛집 검색 → LLM 최종 리포트(Markdown)

기능별 함수 분리:
validate_date / check_api_keys / get_recommendation / search_restaurants / generate_report / save_results
main()에서 전체 파이프라인을 순서대로 호출.

핵심은 단일 API 호출이 아니라, 한 API의 출력을 다음 API의 입력으로 넘기는 연결 구조.

---

## 2. REST API 기본기

요청은 URL / 메서드(GET, POST) / 헤더 / body 또는 query parameter로 구성. 응답은 상태 코드 + JSON.

- OpenAI 호출: POST, body에 프롬프트를 담아 전송 (데이터를 새로 생성 요청하는 성격)
- Kakao Local 호출: GET, query parameter에 검색어 전달 (단순 조회, 상태 변경 없음)

---

## 3. LLM 출력을 구조화하는 방법

1. 프롬프트에 JSON 스키마를 명시하고 "다른 설명 없이 JSON만 출력"하도록 지시
2. 코드블록으로 감싸 응답하는 경우 대비 → extract_json_from_text()로 방어적 파싱
3. 1차 JSON의 recommended_city를 그대로 다음 함수(search_restaurants)의 인자로 전달

→ 이 연결 지점이 미션에서 요구한 "구조화된 출력 → 다음 단계 입력" 흐름.

---

## 4. API 제공자 선택

공통 조건: 장소 검색 가능 + JSON 응답 + 최소 필드(place_name/address/lat,lng 또는 x,y/url) 확보.

Kakao 선택 이유: Naver는 최근 검색 API를 네이버클라우드 플랫폼(API HUB)으로 이전해 신규 신청 절차가 복잡해진 상태. Kakao는 기존 개발자센터에서 바로 REST API 키 발급 가능.

필드를 name/address/category/url/x,y로 통일해서, 나중에 다른 제공자로 바꿔도 이 딕셔너리 형태만 맞추면 나머지 로직 재사용 가능하도록 설계.

---

## 5. 에러 처리 설계

| 상황 | 처리 |
|---|---|
| API 키 미설정 | 즉시 종료 + 안내 |
| 인증/쿼터/네트워크 오류 | 해당 단계만 "데이터 없음" 처리, 계속 진행 |
| 검색 결과 0건 | 프로그램 중단 없이 다음 단계 진행 |
| JSON 파싱 실패 | 프롬프트 수정 후 1회만 재시도, 그래도 실패 시 폴백값 |

try-except는 외부 API 호출 지점 세 곳(1차 추천 / 맛집 검색 / 리포트 생성)에 개별 배치. 한 단계 실패가 전체를 죽이지 않는 게 핵심 설계 의도.

errors 리스트는 로그와 별개로 결과 파일(JSON/리포트)에 영구 기록 → 나중에 파일만 봐도 어느 단계에서 문제가 있었는지 추적 가능.

### 실전 트러블슈팅 사례
Kakao 403 발생 → curl로 직접 요청 보내 원인 진단 → 응답 메시지에서 "OPEN_MAP_AND_LOCAL 서비스 비활성화" 확인 → 비즈앱 전환 필요, 개인 개발자는 본인인증만으로 전환 가능 → 해결.
(자세한 재현 과정과 실행 로그는 TESTING.md 참고)

---

## 6. 보안 (API 키 관리)

.env로 관리하는 이유 세 가지:
1) 협업 시 실수 노출 방지
2) 키 교체해도 코드 수정 불필요
3) 과금/쿼터 서비스 사고 예방

.gitignore에 .env 등록 → Git에 실수로 커밋되는 것 원천 차단.
키 노출 시: 즉시 폐기 후 재발급.

---

## 7. 리포트/결과 저장 형식

미션 문서: "결과 예시는 참고용, 실제 출력 방식은 달라도 됨" → 필수 섹션 7개(추천 지역/이유/날씨/행사/맛집/1일 일정/오류 요약)는 유지하고 세부 형식은 자유롭게 구성.

저장 파일명: {date}_raw_data.json / {date}_travel_plan.md → 날짜 기준 저장이라 같은 날짜 재실행은 덮어쓰기, 다른 날짜는 누적되어 비교 가능.

---

## 8. 개발 환경 대응

- Python 3.8에서 tuple[str, str] 문법 미지원 → TypeError → from __future__ import annotations 추가
- 시스템 Python externally-managed-environment로 설치 차단 → venv 생성 후 그 안에서 패키지 설치
- 최종 실행 환경은 venv에서 3.10 이상으로 맞춰 미션 요구사항(Python 3.10+) 충족
- CLI로 구현한 이유: 미션 요구사항이 터미널 실행만 요구, 웹 UI는 요구하지 않음

