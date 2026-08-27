"""Tavily·GPT 협업 조사 로직의 네트워크 없는 회귀 검사입니다."""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflow.internet_research import (  # noqa: E402
    build_component_plan_prompt,
    build_component_search_query,
    build_chatgpt_review_prompt,
    build_devicemart_review_prompt,
    component_plan_issues,
    component_recommendation_issues,
    extract_price_won,
    parse_chatgpt_review,
    parse_component_plan,
    parse_devicemart_review,
    persist_component_recommendations,
    persist_research_review,
    price_for_product,
    product_has_supported_evidence,
    product_is_purchase_ready,
    search_tavily,
)


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def run_regression() -> None:
    captured_request = {}

    def fake_opener(request, timeout):
        captured_request["body"] = json.loads(request.data.decode("utf-8"))
        captured_request["timeout"] = timeout
        return _FakeResponse(
            {
                "results": [
                    {
                        "title": "공식 자료",
                        "url": "https://example.com/official",
                        "content": "검증할 내용",
                        "score": 0.91,
                    },
                    {
                        "title": "보조 자료",
                        "url": "https://example.org/support",
                        "content": "보조 근거",
                        "score": 0.82,
                    },
                ],
                "usage": {"credits": 1},
            }
        )

    search_result = search_tavily(
        "협업 기능 조사",
        "tvly-test-key",
        max_results=5,
        opener=fake_opener,
    )
    assert captured_request["body"]["include_answer"] is False
    assert captured_request["body"]["search_depth"] == "basic"
    assert len(search_result["results"]) == 2
    assert search_result["credits"] == 1
    assert search_result["queried_at"]
    assert extract_price_won("판매가 36,300원") == 36300
    assert extract_price_won("가격 정보 없음") is None

    prompt = build_chatgpt_review_prompt(
        {"name": "학생 프로젝트", "field": "교육", "goal": "협업 도구 만들기"},
        search_result["query"],
        search_result["results"],
    )
    assert "[출처 1]" in prompt
    assert "JSON 형식 하나만 출력" in prompt

    review = parse_chatgpt_review(
        """```json
        {
          "summary": "검토 요약",
          "confirmed_candidates": [
            {"content": "두 출처가 같은 사실을 설명한다.", "source_numbers": [1, 2]}
          ],
          "conflicts": [],
          "unverified": ["추가 확인 필요"],
          "proposals": [
            {"content": "기능을 먼저 시험한다.", "source_numbers": [1]}
          ]
        }
        ```"""
    )
    assert review["summary"] == "검토 요약"
    assert review["unverified"][0]["source_numbers"] == []

    source_rows = []
    status_changes = []
    fact_rows = []

    def fake_add_source(project_id, title, url, source_type, notes):
        source_id = len(source_rows) + 10
        source_rows.append(
            {
                "id": source_id,
                "project_id": project_id,
                "title": title,
                "url": url,
                "source_type": source_type,
                "notes": notes,
            }
        )
        return source_id

    def fake_update_source_status(source_id, status):
        status_changes.append((source_id, status))

    def fake_add_fact_record(
        project_id,
        fact_type,
        content,
        *,
        origin,
        source_id=None,
    ):
        fact_rows.append((project_id, fact_type, content, origin, source_id))
        return len(fact_rows)

    saved = persist_research_review(
        project_id=7,
        results=search_result["results"],
        selected_source_numbers={1, 2},
        review=review,
        approved_candidate_indexes={0},
        existing_sources=[],
        add_source=fake_add_source,
        update_source_status=fake_update_source_status,
        add_fact_record=fake_add_fact_record,
    )
    assert saved == {"sources": 2, "confirmed": 1, "review_notes": 2}
    assert status_changes == [(10, "verified")]
    assert fact_rows[0][1] == "confirmed_fact"
    assert fact_rows[0][3] == "user"
    assert {row[1] for row in fact_rows[1:]} == {"unverified", "proposal"}

    captured_request.clear()
    plan_prompt = build_component_plan_prompt(
        {"name": "라인트레이서", "field": "로봇", "goal": "선을 따라 이동"},
        "라인트레이서를 만들고 싶다",
        budget="10만원",
        owned_parts="모터와 감속기",
    )
    assert "감속기 필요 여부를 반드시 판정" in plan_prompt
    incomplete_plan = parse_component_plan(
        """{
          "status": "ready",
          "summary": "모터만 고르면 됩니다.",
          "questions": [],
          "gearbox_decision": {"status": "unknown", "reason": ""},
          "components": [
            {
              "id": "motor",
              "category": "DC 모터",
              "purpose": "바퀴 구동",
              "required": true,
              "already_owned": false,
              "search_terms": ["DC 모터"],
              "minimum_requirements": ["속도 확인"],
              "compatibility_checks": ["전압 확인"],
              "overspec_avoidance": ["불필요한 고속 모터 제외"]
            }
          ],
          "global_checks": []
        }"""
    )
    incomplete_issues = component_plan_issues(
        incomplete_plan,
        "라인트레이서 자동차가 움직여야 한다",
    )
    assert any("드라이버" in issue for issue in incomplete_issues)
    assert any("감속기" in issue for issue in incomplete_issues)

    ready_plan = parse_component_plan(
        """{
          "status": "ready",
          "summary": "구동계와 전원을 함께 확인했습니다.",
          "questions": [],
          "gearbox_decision": {"status": "required", "reason": "속도를 낮추고 토크를 높여야 합니다."},
          "components": [
            {
              "id": "motor",
              "category": "DC 모터",
              "purpose": "바퀴 구동",
              "required": true,
              "already_owned": true,
              "search_terms": ["DC 모터"],
              "minimum_requirements": ["목표 토크"],
              "compatibility_checks": ["전압"],
              "overspec_avoidance": ["목표보다 과한 출력 제외"]
            },
            {
              "id": "gearbox",
              "category": "감속기",
              "purpose": "속도와 토크 변환",
              "required": true,
              "already_owned": true,
              "search_terms": ["감속기"],
              "minimum_requirements": ["감속비"],
              "compatibility_checks": ["축 지름"],
              "overspec_avoidance": ["불필요한 고토크 제외"]
            },
            {
              "id": "driver",
              "category": "모터 드라이버",
              "purpose": "모터 전류 제어",
              "required": true,
              "already_owned": true,
              "search_terms": ["H브리지 모터 드라이버"],
              "minimum_requirements": ["정지 전류 이상"],
              "compatibility_checks": ["모터 전압과 논리 전압"],
              "overspec_avoidance": ["필요 이상의 채널 수 제외"]
            },
            {
              "id": "power",
              "category": "배터리 전원",
              "purpose": "전체 전원 공급",
              "required": true,
              "already_owned": true,
              "search_terms": ["배터리 홀더"],
              "minimum_requirements": ["최대 전류 이상"],
              "compatibility_checks": ["모터와 제어보드 전압"],
              "overspec_avoidance": ["불필요한 대용량 제외"]
            },
            {
              "id": "controller",
              "category": "제어보드",
              "purpose": "센서 입력과 모터 명령",
              "required": true,
              "already_owned": false,
              "search_terms": ["Arduino Uno"],
              "minimum_requirements": ["PWM 출력"],
              "compatibility_checks": ["5V 논리"],
              "overspec_avoidance": ["고성능 Linux 보드 제외"]
            }
          ],
          "global_checks": ["모든 접지 연결"]
        }"""
    )
    assert component_plan_issues(ready_plan, "라인트레이서 자동차") == []
    assert "Arduino Uno" in build_component_search_query(
        ready_plan,
        "라인트레이서 자동차",
    )

    component_search_result = search_tavily(
        "라인트레이서 부품",
        "tvly-test-key",
        max_results=5,
        include_domains=["devicemart.co.kr"],
        opener=fake_opener,
    )
    assert captured_request["body"]["include_domains"] == ["devicemart.co.kr"]
    component_search_result["results"][0]["price_won"] = 36300
    component_search_result["results"][0]["content"] = (
        "Arduino Uno 입문용 제어 보드 / 판매가 36,300원"
    )
    assert (
        price_for_product(
            component_search_result["results"][0],
            "Arduino Uno",
        )
        == 36300
    )
    assert (
        price_for_product(
            component_search_result["results"][0],
            "다른 상품",
        )
        is None
    )
    component_prompt = build_devicemart_review_prompt(
        {"name": "라인트레이서", "field": "로봇", "goal": "선을 따라 이동"},
        "라인트레이서를 만들고 싶다",
        component_search_result["results"],
        component_plan=ready_plan,
        budget="10만원",
        owned_parts="없음",
    )
    assert "가격은 JSON에 쓰지 마세요" in component_prompt
    assert "36,300원" in component_prompt

    component_review = parse_devicemart_review(
        """{
          "summary": "입문용 구성을 추천합니다.",
          "recommended_products": [
            {
              "product_name": "Arduino Uno",
              "component_id": "controller",
              "purpose": "센서와 모터를 제어합니다.",
              "source_number": 1,
              "compatibility_status": "compatible",
              "compatibility": "5V 확인",
              "overspec_status": "appropriate",
              "overspec_reason": "필요한 PWM 기능을 충족하고 과하지 않습니다.",
              "evidence": ["Arduino Uno 입문용 제어 보드"],
              "missing_information": [],
              "caution": "모터 전원 분리",
              "required": true,
              "price_won": 999999
            }
          ],
          "coverage": [
            {"component_id": "motor", "status": "owned", "note": "보유"},
            {"component_id": "gearbox", "status": "owned", "note": "보유"},
            {"component_id": "driver", "status": "owned", "note": "보유"},
            {"component_id": "power", "status": "owned", "note": "보유"},
            {"component_id": "controller", "status": "selected", "note": "선정"}
          ],
          "global_compatibility": {"status": "compatible", "issues": []},
          "missing_categories": [],
          "cautions": ["정격 전류 확인"]
        }"""
    )
    assert "price_won" not in component_review["recommended_products"][0]
    assert product_is_purchase_ready(component_review["recommended_products"][0])
    assert product_has_supported_evidence(
        component_review["recommended_products"][0],
        component_search_result["results"][0],
    )
    assert component_recommendation_issues(
        component_review,
        ready_plan,
        component_search_result["results"],
    ) == []
    unsupported_review = json.loads(json.dumps(component_review))
    unsupported_review["recommended_products"][0]["evidence"] = [
        "원문에 없는 사양"
    ]
    assert any(
        "근거" in issue
        for issue in component_recommendation_issues(
            unsupported_review,
            ready_plan,
            component_search_result["results"],
        )
    )

    component_source_rows = []
    component_fact_rows = []

    def component_add_source(project_id, title, url, source_type, notes):
        component_source_rows.append((project_id, title, url, source_type, notes))
        return 77

    def component_add_fact(
        project_id,
        fact_type,
        content,
        *,
        origin,
        source_id=None,
    ):
        component_fact_rows.append(
            (project_id, fact_type, content, origin, source_id)
        )
        return 88

    try:
        persist_component_recommendations(
            project_id=7,
            results=component_search_result["results"],
            review=component_review,
            component_plan=ready_plan,
            selected_product_indexes=set(),
            existing_sources=[],
            add_source=component_add_source,
            add_fact_record=component_add_fact,
            queried_at=component_search_result["queried_at"],
        )
    except ValueError:
        pass
    else:
        raise AssertionError("필수 구매 후보 누락을 차단하지 못했습니다.")

    component_saved = persist_component_recommendations(
        project_id=7,
        results=component_search_result["results"],
        review=component_review,
        component_plan=ready_plan,
        selected_product_indexes={0},
        existing_sources=[],
        add_source=component_add_source,
        add_fact_record=component_add_fact,
        queried_at=component_search_result["queried_at"],
    )
    assert component_saved == {"sources": 1, "proposals": 1}
    assert component_source_rows[0][3] == "디바이스마트 상품"
    assert "36,300원(조회 시점)" in component_fact_rows[0][2]
    assert component_fact_rows[0][1] == "proposal"


if __name__ == "__main__":
    run_regression()
    print("INTERNET_RESEARCH_REGRESSION_OK")
