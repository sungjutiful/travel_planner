#!/usr/bin/env python3
"""
travel_planner.py
------------------
LLM API(OpenAI)와 지도/장소 검색 API(Kakao Local)를 조합한
국내 여행지 추천 CLI 프로그램.

실행 예:
    python travel_planner.py --date "2026-03-15"

필요 환경변수 (.env 파일 또는 시스템 환경변수):
    OPENAI_API_KEY      - OpenAI API 키
    KAKAO_REST_API_KEY  - Kakao REST API 키 (카카오 디벨로퍼스 > REST API 키)

자세한 설정 방법은 README.md 참고.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# python-dotenv가 설치되어 있으면 .env 파일을 자동으로 읽어온다.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv가 없어도 시스템 환경변수만으로 동작 가능하도록 허용
    pass


# --------------------------------------------------------------------------
# 설정값
# --------------------------------------------------------------------------
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_MODEL = "gpt-4o-mini"

KAKAO_LOCAL_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

RESULTS_DIR = Path("results")

REQUIRED_KEYS_STEP1 = ["recommended_city", "weather", "events", "reason"]


# --------------------------------------------------------------------------
# 공통 유틸
# --------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


def validate_date(date_str: str) -> str:
    """YYYY-MM-DD 형식인지 검증. 형식이 틀리면 사용법을 출력하고 종료."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        print(f"[오류] 날짜 형식이 올바르지 않습니다: '{date_str}'")
        print('사용법: python travel_planner.py --date "YYYY-MM-DD"')
        print('예시  : python travel_planner.py --date "2026-03-15"')
        sys.exit(1)


def check_api_keys() -> tuple[str, str]:
    """필수 API 키가 설정되어 있는지 확인. 없으면 즉시 종료 + 안내."""
    openai_key = os.getenv("OPENAI_API_KEY")
    kakao_key = os.getenv("KAKAO_REST_API_KEY")

    missing = []
    if not openai_key:
        missing.append("OPENAI_API_KEY")
    if not kakao_key:
        missing.append("KAKAO_REST_API_KEY")

    if missing:
        print("[오류] 다음 API 키가 설정되지 않았습니다:", ", ".join(missing))
        print()
        print("설정 방법:")
        print("  1) 프로젝트 루트에 .env 파일을 만들고 아래처럼 작성하세요.")
        print("     OPENAI_API_KEY=your_openai_key_here")
        print("     KAKAO_REST_API_KEY=your_kakao_key_here")
        print("  2) 또는 터미널에서 환경변수로 직접 설정하세요.")
        print('     (macOS/Linux) export OPENAI_API_KEY="your_key"')
        print('     (Windows PS)  $env:OPENAI_API_KEY="your_key"')
        sys.exit(1)

    return openai_key, kakao_key


def extract_json_from_text(text: str) -> dict:
    """LLM 응답에서 JSON 부분만 안전하게 추출한다 (코드블록 등 방어)."""
    text = text.strip()
    if text.startswith("```"):
        # ```json ... ``` 형태 방어
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise json.JSONDecodeError("JSON object not found", text, 0)
    return json.loads(text[start:end + 1])


# --------------------------------------------------------------------------
# 1. LLM API 연동 - 1차 추천 (날씨/행사 정보)
# --------------------------------------------------------------------------
def call_openai(api_key: str, system_prompt: str, user_prompt: str) -> str:
    """OpenAI Chat Completions API 호출. 실패 시 예외를 발생시킨다."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }
    resp = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def get_recommendation(api_key: str, date_str: str, errors: list) -> dict:
    """
    1차 추천 JSON을 생성한다.
    파싱 실패 시 "필수 키만 다시 JSON으로 출력"하도록 프롬프트를 수정해 1회 재시도.
    """
    system_prompt = (
        "너는 국내 여행 추천 도우미다. 사용자가 제공한 날짜를 기준으로 "
        "여행하기 좋은 국내 도시를 1곳 추천한다. "
        "반드시 아래 JSON 스키마만 출력하고, 그 외의 설명/코드블록/문장은 절대 포함하지 마라.\n"
        "{\n"
        '  "recommended_city": "string",\n'
        '  "weather": "string",\n'
        '  "events": ["string", "..."],\n'
        '  "reason": "string"\n'
        "}"
    )
    user_prompt = f"여행 예정 날짜: {date_str}"

    def _try_once(sys_p: str, usr_p: str) -> dict:
        raw_text = call_openai(api_key, sys_p, usr_p)
        parsed = extract_json_from_text(raw_text)
        missing = [k for k in REQUIRED_KEYS_STEP1 if k not in parsed]
        if missing:
            raise ValueError(f"필수 키 누락: {missing}")
        return parsed

    try:
        return _try_once(system_prompt, user_prompt)
    except (json.JSONDecodeError, ValueError, requests.RequestException) as e1:
        errors.append({
            "step": "llm_recommendation",
            "type": "PARSE_ERROR_RETRY",
            "message": str(e1),
        })
        log("    - 1차 추천 JSON 파싱 실패, 재시도 중...")
        try:
            retry_system_prompt = (
                system_prompt
                + "\n\n[중요] 이전 응답이 JSON 파싱에 실패했다. "
                  "이번에는 반드시 필수 키(recommended_city, weather, events, reason)만 "
                  "포함한 순수 JSON 객체 하나만 출력하라. 코드블록이나 설명 문장을 절대 넣지 마라."
            )
            return _try_once(retry_system_prompt, user_prompt)
        except (json.JSONDecodeError, ValueError, requests.RequestException) as e2:
            errors.append({
                "step": "llm_recommendation",
                "type": "PARSE_ERROR_FINAL",
                "message": str(e2),
            })
            # 재시도까지 실패하면 최소한의 기본값으로 다음 단계를 진행시킨다.
            return {
                "recommended_city": "서울",
                "weather": "정보 없음 (LLM 응답 파싱 실패)",
                "events": [],
                "reason": "추천 정보를 생성하지 못했습니다.",
            }


# --------------------------------------------------------------------------
# 2. 지도/장소 검색 API 연동 - 맛집 검색 (Kakao Local)
# --------------------------------------------------------------------------
def search_restaurants(api_key: str, city: str, errors: list, limit: int = 5) -> list:
    """
    Kakao Local 키워드 검색으로 '{city} 맛집'을 검색한다.
    실패/0건이어도 프로그램은 중단되지 않고 빈 리스트를 반환한다.
    """
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {
        "query": f"{city} 맛집",
        "size": limit,
        "sort": "accuracy",
    }

    try:
        resp = requests.get(KAKAO_LOCAL_URL, headers=headers, params=params, timeout=15)

        if resp.status_code in (401, 403):
            errors.append({
                "step": "place_search",
                "type": "AUTH_ERROR",
                "message": f"HTTP {resp.status_code}",
            })
            log(f"    - 오류: 인증 실패({resp.status_code}). 키 설정을 확인하세요.")
            log("    - 맛집 섹션은 '데이터 없음'으로 처리하고 계속 진행합니다.")
            return []

        resp.raise_for_status()
        data = resp.json()
        documents = data.get("documents", [])

        if not documents:
            errors.append({
                "step": "place_search",
                "type": "EMPTY_RESULT",
                "message": f"0 results for query={city} 맛집",
            })
            log("    - 검색 결과 0건")
            return []

        restaurants = []
        for doc in documents[:limit]:
            restaurants.append({
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "category": doc.get("category_name", ""),
                "url": doc.get("place_url", ""),
                "x": doc.get("x"),  # 경도
                "y": doc.get("y"),  # 위도
            })
        return restaurants

    except requests.RequestException as e:
        errors.append({
            "step": "place_search",
            "type": "NETWORK_ERROR",
            "message": str(e),
        })
        log(f"    - 오류: 네트워크/요청 실패 ({e})")
        log("    - 맛집 섹션은 '데이터 없음'으로 처리하고 계속 진행합니다.")
        return []


# --------------------------------------------------------------------------
# 3. LLM API 연동 - 최종 리포트 생성
# --------------------------------------------------------------------------
def generate_report(api_key: str, date_str: str, recommendation: dict,
                     restaurants: list, errors: list) -> str:
    """1차 추천 + 맛집 목록을 바탕으로 최종 Markdown 리포트를 생성한다."""
    system_prompt = (
        "너는 국내 여행 리포트 작성 도우미다. 주어진 데이터를 바탕으로 "
        "Markdown 형식의 여행 리포트를 작성한다. "
        "리포트에는 반드시 아래 섹션이 이 순서대로 포함되어야 한다:\n"
        "# {날짜} 국내 여행 추천 리포트\n"
        "## 추천 지역\n"
        "## 추천 이유\n"
        "## 날씨 요약\n"
        "## 행사/축제\n"
        "## 맛집 추천\n"
        "## 1일 일정 제안 (오전/오후/저녁)\n"
        "## 오류 요약\n\n"
        "맛집 리스트가 비어 있으면 '## 맛집 추천' 섹션에 '- 데이터 없음'이라고 표기하라. "
        "오류 리스트가 비어 있으면 '## 오류 요약' 섹션에 '- 없음'이라고 표기하라. "
        "Markdown 텍스트만 출력하고 다른 설명은 추가하지 마라."
    )
    user_prompt = (
        f"날짜: {date_str}\n"
        f"1차 추천 데이터: {json.dumps(recommendation, ensure_ascii=False)}\n"
        f"맛집 목록: {json.dumps(restaurants, ensure_ascii=False)}\n"
        f"오류 목록: {json.dumps(errors, ensure_ascii=False)}"
    )

    try:
        report_text = call_openai(api_key, system_prompt, user_prompt)
        return report_text.strip()
    except requests.RequestException as e:
        errors.append({
            "step": "report_generation",
            "type": "LLM_ERROR",
            "message": str(e),
        })
        # LLM 리포트 생성 자체가 실패하면, 로컬에서 최소한의 리포트를 조립해 폴백한다.
        return build_fallback_report(date_str, recommendation, restaurants, errors)


def build_fallback_report(date_str, recommendation, restaurants, errors) -> str:
    """리포트 생성 LLM 호출이 실패했을 때 사용하는 로컬 폴백 리포트."""
    lines = [f"# {date_str} 국내 여행 추천 리포트", ""]
    lines.append("## 추천 지역")
    lines.append(f"- {recommendation.get('recommended_city', '정보 없음')}")
    lines.append("")
    lines.append("## 추천 이유")
    lines.append(f"- {recommendation.get('reason', '정보 없음')}")
    lines.append("")
    lines.append("## 날씨 요약")
    lines.append(f"- {recommendation.get('weather', '정보 없음')}")
    lines.append("")
    lines.append("## 행사/축제")
    events = recommendation.get("events") or []
    if events:
        for ev in events:
            lines.append(f"- {ev}")
    else:
        lines.append("- 데이터 없음")
    lines.append("")
    lines.append("## 맛집 추천")
    if restaurants:
        for r in restaurants:
            lines.append(f"- {r.get('name')} ({r.get('category', '')}) - {r.get('address', '')}")
    else:
        lines.append("- 데이터 없음")
    lines.append("")
    lines.append("## 1일 일정 제안")
    lines.append("- 오전: 주요 관광지 방문")
    lines.append("- 오후: 자유 일정 / 카페 투어")
    lines.append("- 저녁: 추천 맛집에서 식사")
    lines.append("")
    lines.append("## 오류 요약")
    if errors:
        for e in errors:
            lines.append(f"- [{e.get('step')}] {e.get('type')}: {e.get('message')}")
    else:
        lines.append("- 없음")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 결과 저장
# --------------------------------------------------------------------------
def save_results(date_str: str, recommendation: dict, restaurants: list,
                  errors: list, report_md: str) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(exist_ok=True)

    raw_data = {
        "date": date_str,
        "recommendation": recommendation,
        "restaurants": restaurants,
        "errors": errors,
    }

    json_path = RESULTS_DIR / f"{date_str}_raw_data.json"
    md_path = RESULTS_DIR / f"{date_str}_travel_plan.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return json_path, md_path


# --------------------------------------------------------------------------
# 메인 흐름
# --------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="LLM + 지도 API를 활용한 국내 여행지 추천 프로그램"
    )
    parser.add_argument(
        "--date", required=True,
        help='여행 예정 날짜, 형식: "YYYY-MM-DD" (예: 2026-03-15)'
    )
    args = parser.parse_args()

    date_str = validate_date(args.date)
    openai_key, kakao_key = check_api_keys()

    errors: list = []

    log("[1/3] 1차 추천 생성 중(LLM)...")
    recommendation = get_recommendation(openai_key, date_str, errors)
    log(f"    - recommended_city: \"{recommendation.get('recommended_city')}\"")

    log("[2/3] 맛집 검색 중(지도/장소 API)...")
    restaurants = search_restaurants(
        kakao_key, recommendation.get("recommended_city", ""), errors
    )
    if restaurants:
        log(f"    - 맛집 {len(restaurants)}곳 검색 완료")

    log("[3/3] 최종 리포트 생성 중(LLM)...")
    report_md = generate_report(openai_key, date_str, recommendation, restaurants, errors)
    log("    - 리포트 생성 완료")

    json_path, md_path = save_results(date_str, recommendation, restaurants, errors, report_md)

    print()
    print(f"완료! {md_path} 를 확인하세요.")
    print(f"(원본 데이터: {json_path})")


if __name__ == "__main__":
    main()
