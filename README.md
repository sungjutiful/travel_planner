# 국내 여행지 추천 프로그램 (Python + API 연동)

LLM API(OpenAI)와 지도/장소 검색 API(Kakao Local)를 조합하여,
사용자가 입력한 날짜를 기준으로 국내 여행지를 추천하고, 해당 지역의 맛집을 검색한 뒤,
최종 여행 리포트(Markdown)를 자동으로 생성하는 CLI 프로그램입니다.

## 1. 프로그램 개요

전체 흐름은 다음과 같습니다.

```
사용자 입력(날짜)
      │
      ▼
[1] LLM API 호출 → 추천 도시 / 날씨 요약 / 행사·축제 / 추천 이유 (JSON)
      │
      ▼
[2] 지도 API 호출 → 추천 도시의 맛집 검색 (최대 5곳)
      │
      ▼
[3] LLM API 호출 → 위 정보를 종합해 최종 여행 리포트(Markdown) 생성
      │
      ▼
results/ 폴더에 원본 JSON + 리포트 Markdown 저장
```

사용한 API:
- **LLM API**: OpenAI Chat Completions API (`gpt-4o-mini`)
- **지도/장소 검색 API**: Kakao Local 키워드 검색 API

## 2. 실행 방법

### 2-1. 사전 준비

```bash
# 1) 필요한 패키지 설치
pip install -r requirements.txt

# 2) .env 파일 생성 (아래 "API 키 설정 방법" 참고)
cp .env.example .env
# .env 파일을 열어 실제 키 값을 입력하세요.
```

### 2-2. 실행

```bash
python travel_planner.py --date "2026-03-15"
```

- `--date`는 필수 옵션이며 `YYYY-MM-DD` 형식이어야 합니다.
- 형식이 올바르지 않으면 사용법 안내를 출력하고 프로그램을 종료합니다.

### 2-3. 실행 결과 예시

```
[1/3] 1차 추천 생성 중(LLM)...
    - recommended_city: "제주"
[2/3] 맛집 검색 중(지도/장소 API)...
    - 맛집 5곳 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
    - 리포트 생성 완료

완료! results/2026-03-15_travel_plan.md 를 확인하세요.
(원본 데이터: results/2026-03-15_raw_data.json)
```

## 3. API 키 설정 방법

**⚠️ API 키는 절대 코드에 직접 작성하지 않습니다.** `.env` 파일 또는 시스템 환경변수를 통해서만 읽어옵니다.

### 3-1. OpenAI API 키 발급

1. https://platform.openai.com/api-keys 접속 후 로그인
2. "Create new secret key" 클릭하여 키 발급

### 3-2. Kakao REST API 키 발급

1. https://developers.kakao.com 접속 후 로그인
2. "내 애플리케이션" → 애플리케이션 추가
3. "앱 키" 탭에서 **REST API 키** 확인 (Admin 키가 아닌 REST API 키 사용)
4. "플랫폼" 설정에서 사용할 플랫폼(Web 등)을 등록해야 로컬 검색 API가 정상 동작합니다.

### 3-3. .env 파일 작성

프로젝트 루트에 `.env` 파일을 만들고 아래와 같이 작성합니다.

```
OPENAI_API_KEY=발급받은_OpenAI_키
KAKAO_REST_API_KEY=발급받은_Kakao_REST_API_키
```

### 3-4. (대안) 시스템 환경변수로 직접 설정

`.env` 파일 대신 터미널에서 직접 설정할 수도 있습니다. (현재 터미널 세션에만 적용됨)

```bash
# macOS / Linux
export OPENAI_API_KEY="your_key"
export KAKAO_REST_API_KEY="your_key"
```

```powershell
# Windows PowerShell
$env:OPENAI_API_KEY="your_key"
$env:KAKAO_REST_API_KEY="your_key"
```

### 3-5. API 키 유출 방지 주의 사항

- `.env` 파일은 **절대 Git 저장소에 커밋하지 마세요.** (`.gitignore`에 `.env` 추가 권장)
- 캡처, 로그, README, 결과 파일(JSON/Markdown) 어디에도 실제 키 값을 남기지 마세요.
- 키가 실수로 노출되었다면 즉시 해당 플랫폼(OpenAI, Kakao)에서 키를 재발급/폐기하세요.
- 과금/쿼터가 있는 서비스이므로, 키를 공용 저장소나 공개 채널에 절대 공유하지 마세요.

## 4. 결과물 확인 방법

프로그램 실행 후 `results/` 폴더가 자동 생성되며, 아래 두 파일이 저장됩니다.

| 파일 | 설명 |
|---|---|
| `results/{date}_raw_data.json` | 1차 추천 결과(JSON) + 맛집 검색 결과 + 오류 목록을 포함한 원본 데이터 |
| `results/{date}_travel_plan.md` | 최종 여행 리포트 (추천 지역, 날씨, 행사, 맛집, 1일 일정, 오류 요약 포함) |

예: `2026-03-15`로 실행한 경우
```
results/
├── 2026-03-15_raw_data.json
└── 2026-03-15_travel_plan.md
```

## 5. 에러 처리 정책

| 상황 | 동작 |
|---|---|
| API 키 미설정 | 즉시 종료 + 설정 방법 안내 출력 |
| 지도/장소 API 실패 (네트워크/인증/쿼터) | 맛집 섹션 "데이터 없음" 처리, 리포트 생성은 계속 진행 |
| 맛집 검색 결과 0건 | 프로그램 중단 없이 "데이터 없음"으로 다음 단계 진행 |
| LLM JSON 파싱 실패 | 필수 키만 다시 출력하도록 프롬프트를 수정해 1회 재시도, 그래도 실패하면 기본값으로 진행 |
| 리포트 생성 LLM 호출 실패 | 로컬에서 조립한 폴백(fallback) 리포트로 대체 |

모든 오류는 `errors` 리스트로 관리되며, 원본 JSON과 최종 리포트의 "오류 요약" 섹션에 기록됩니다.

## 6. 코드 구조

```
travel_planner.py
├── validate_date()          # 날짜 형식 검증
├── check_api_keys()         # API 키 존재 여부 확인
├── call_openai()            # OpenAI API 공통 호출 함수
├── get_recommendation()     # [1] 1차 추천 (날씨/행사) - JSON, 파싱 실패 시 1회 재시도
├── search_restaurants()     # [2] Kakao Local 맛집 검색
├── generate_report()        # [3] 최종 Markdown 리포트 생성
├── build_fallback_report()  # 리포트 생성 실패 시 로컬 폴백
├── save_results()           # results/ 폴더에 JSON + Markdown 저장
└── main()                   # 전체 파이프라인 오케스트레이션
```

## 7. 다른 API 조합으로 바꾸고 싶다면

- **LLM API**: `call_openai()` 함수를 Google Gemini API 호출로 교체하면 됩니다. (요청/응답 형식만 다르고, 이후 로직은 동일하게 재사용 가능)
- **지도/장소 API**: `search_restaurants()` 함수를 Naver Local Search API 호출로 교체하면 됩니다. 응답에서 `name`, `address`, `category`, `url`, `x`/`y`(또는 `lat`/`lng`) 필드를 동일한 딕셔너리 형태로 매핑해주면 나머지 코드는 그대로 동작합니다.
