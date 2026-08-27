"""Tavily 검색과 ChatGPT Plus 검수를 연결하는 Streamlit 화면입니다."""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Callable

import streamlit as st

from workflow.internet_research import (
    DEVICEMART_DOMAIN,
    TavilySearchError,
    build_chatgpt_review_prompt,
    build_component_plan_prompt,
    build_component_search_query,
    build_devicemart_review_prompt,
    component_plan_issues,
    component_recommendation_issues,
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


GENERAL_RESEARCH_MODE = "일반 인터넷 조사"
COMPONENT_RESEARCH_MODE = "디바이스마트 부품 찾기"


def _state_key(project_id: int, name: str) -> str:
    return f"internet_research_{project_id}_{name}"


def research_mode_session_key(project_id: int) -> str:
    """대화 화면의 바로가기와 조사창이 공유하는 모드 상태 키입니다."""

    return _state_key(project_id, "mode")


def _claim_caption(claim: dict[str, Any]) -> str:
    numbers = claim.get("source_numbers") or []
    if not numbers:
        return "연결된 출처 없음"
    return "근거 출처: " + ", ".join(f"{number}번" for number in numbers)


def _render_component_review(
    *,
    project_id: int,
    search_result: dict[str, Any],
    review: dict[str, Any],
    component_plan: dict[str, Any],
    existing_sources: list[dict[str, Any]],
    add_source: Callable[..., int],
    add_fact_record: Callable[..., int | None],
    result_key: str,
    review_key: str,
) -> None:
    """검수된 디바이스마트 상품을 가격·호환성과 함께 표시합니다."""

    products = review.get("recommended_products") or []
    if review.get("summary"):
        st.info(review["summary"])
    if not products:
        st.warning(
            "추천 가능한 상품을 찾지 못했습니다. 검색 문맥이 부족할 수 있으니 "
            "만들려는 기능을 더 구체적으로 적어 다시 검색해보세요."
        )
        return

    recommendation_issues = component_recommendation_issues(
        review,
        component_plan,
        search_result["results"],
    )
    if recommendation_issues:
        st.error("아직 바로 구매할 수 있는 완성 목록이 아닙니다.")
        for issue in recommendation_issues:
            st.write(f"- {issue}")

    selected_product_indexes: set[int] = set()
    known_total = 0
    unknown_price_count = 0
    for index, product in enumerate(products):
        source_number = int(product.get("source_number") or 0)
        source = (
            search_result["results"][source_number - 1]
            if 1 <= source_number <= len(search_result["results"])
            else None
        )
        with st.container(border=True):
            if source is None:
                st.error(
                    f"{product['product_name']}의 원문 출처를 찾지 못해 구매 후보로 저장할 수 없습니다."
                )
                continue
            required_label = "필수 후보" if product.get("required") else "선택 후보"
            purchase_ready = product_is_purchase_ready(
                product
            ) and product_has_supported_evidence(product, source)
            selected = st.checkbox(
                f"[{required_label}] {product['product_name']}",
                value=bool(product.get("required")) and purchase_ready,
                key=_state_key(project_id, f"component_{index}"),
                disabled=not purchase_ready,
            )
            if selected:
                selected_product_indexes.add(index)
            st.write(f"**용도** · {product['purpose']}")
            price = price_for_product(source, product["product_name"])
            if price:
                st.write(f"**검색 문맥 표시 가격** · {price:,}원")
                if selected:
                    known_total += int(price)
            else:
                st.write("**가격** · 검색 문맥에서 확인되지 않음")
                if selected:
                    unknown_price_count += 1
            if product.get("compatibility"):
                st.write(f"**호환성 확인** · {product['compatibility']}")
            compatibility_status = product.get("compatibility_status")
            overspec_status = product.get("overspec_status")
            if compatibility_status == "compatible":
                st.success("호환성: 검색 문맥 안에서 확인됨")
            elif compatibility_status == "incompatible":
                st.error("호환성: 맞지 않는 상품")
            else:
                st.warning("호환성: 추가 확인이 필요해 선택할 수 없음")
            if overspec_status == "appropriate":
                st.caption("사양 수준: 목적에 적절함")
            elif overspec_status == "excessive":
                st.warning("사양 수준: 목적보다 과해 구매 후보에서 제외")
            else:
                st.warning("사양 수준: 적절한지 판단할 정보 부족")
            if product.get("overspec_reason"):
                st.caption(product["overspec_reason"])
            if product.get("missing_information"):
                st.write(
                    "**원문에서 더 확인할 정보** · "
                    + ", ".join(product["missing_information"])
                )
            if product.get("evidence"):
                st.caption("원문 근거: " + " / ".join(product["evidence"]))
            if product.get("caution"):
                st.warning(f"구매 전 확인 · {product['caution']}")
            st.caption(f"근거: 검색 결과 {source_number}번 · {source['title']}")
            st.link_button("디바이스마트 원문 열기", source["url"])

    st.markdown(f"**선택 상품의 확인된 가격 합계: {known_total:,}원**")
    if unknown_price_count:
        st.caption(
            f"가격을 확인하지 못한 선택 상품 {unknown_price_count}개는 합계에서 제외됐습니다."
        )
    st.caption(
        f"조회 시각: {search_result.get('queried_at') or '확인 불가'} · "
        "배송비·옵션·재고에 따라 실제 결제 금액이 달라질 수 있습니다."
    )

    missing_categories = review.get("missing_categories") or []
    cautions = review.get("cautions") or []
    if missing_categories:
        with st.expander("추가로 검색할 부품 종류"):
            for item in missing_categories:
                st.write(f"- {item}")
    if cautions:
        with st.expander("전체 구성 주의사항"):
            for item in cautions:
                st.write(f"- {item}")

    if st.button(
        "선택한 상품을 구매 후보로 저장",
        type="primary",
        use_container_width=True,
        key=_state_key(project_id, "save_components"),
        disabled=bool(recommendation_issues),
    ):
        if not selected_product_indexes:
            st.error("저장할 상품을 하나 이상 선택해주세요.")
            return
        try:
            saved = persist_component_recommendations(
                project_id=project_id,
                results=search_result["results"],
                review=review,
                component_plan=component_plan,
                selected_product_indexes=selected_product_indexes,
                existing_sources=existing_sources,
                add_source=add_source,
                add_fact_record=add_fact_record,
                queried_at=search_result.get("queried_at") or "확인 불가",
            )
        except (ValueError, RuntimeError, sqlite3.Error) as error:
            st.error(f"구매 후보를 저장하지 못했습니다: {error}")
        else:
            st.success(
                f"새 상품 출처 {saved['sources']}건과 구매 후보 "
                f"{saved['proposals']}건을 저장했습니다."
            )
            st.session_state.pop(result_key, None)
            st.session_state.pop(review_key, None)


@st.dialog("인터넷 자료 도우미", width="large")
def show_internet_research_dialog(
    project: dict[str, Any],
    existing_sources: list[dict[str, Any]],
    *,
    add_source: Callable[..., int],
    update_source_status: Callable[[int, str], None],
    add_fact_record: Callable[..., int | None],
) -> None:
    """검색, GPT 검수, 사용자 승인을 한 화면에서 단계별로 안내합니다."""

    project_id = int(project["id"])
    result_key = _state_key(project_id, "result")
    review_key = _state_key(project_id, "review")
    plan_key = _state_key(project_id, "component_plan")
    plan_signature_key = _state_key(project_id, "component_plan_signature")

    research_mode = st.radio(
        "무엇을 찾고 있나요?",
        [GENERAL_RESEARCH_MODE, COMPONENT_RESEARCH_MODE],
        horizontal=True,
        key=research_mode_session_key(project_id),
    )
    component_mode = research_mode == COMPONENT_RESEARCH_MODE
    if component_mode:
        st.info(
            "부품명을 몰라도 괜찮습니다. 만들고 싶은 것을 적으면 디바이스마트 상품을 찾아 "
            "가격·용도·호환성을 비교합니다."
        )
        st.caption(
            "진행 순서: 만들고 싶은 것 입력 → 필요한 부품 종류 확인 → 상품 검색 → "
            "ChatGPT로 호환성 확인 → 구매 후보 선택"
        )
        st.warning("표시 가격은 조회 시점 참고값입니다. 구매 전 반드시 상품 원문을 확인하세요.")
    else:
        st.info(
            "궁금한 내용을 문장으로 적으면 Tavily가 웹 자료를 찾습니다. "
            "ChatGPT Plus로 비교한 뒤 사용자가 고른 내용만 프로젝트에 저장됩니다."
        )
        st.caption(
            "진행 순서: 질문 입력 → 웹 자료 검색 → ChatGPT로 비교 → 저장할 내용 선택"
        )
    st.caption(
        "인터넷 검색에는 Tavily 키가 필요합니다. ChatGPT Plus는 API 연결이 아니라 "
        "화면에 표시되는 내용을 복사해서 사용합니다."
    )

    environment_api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if environment_api_key:
        api_key = environment_api_key
        st.success("환경변수에 설정된 Tavily API 키를 사용합니다.")
    else:
        api_key = st.text_input(
            "Tavily 검색 API 키",
            type="password",
            key=_state_key(project_id, "api_key"),
            placeholder="tvly-...",
        )

    budget = ""
    owned_parts = ""
    component_plan: dict[str, Any] | None = None
    if component_mode:
        with st.expander("부품을 전혀 몰라도 되는 이유", expanded=False):
            st.markdown(
                "1. **만들고 싶은 결과**만 적으세요. 부품 이름은 몰라도 됩니다.  \n"
                "2. 설계표가 센서·조명·소리·통신·전원·기구물·제어부처럼 필요한 기능 블록을 먼저 찾습니다.  \n"
                "3. 움직임이 필요할 때만 모터·감속기·드라이버까지 따로 확인합니다.  \n"
                "4. 질문이 나오면 아는 것만 답하세요. 모르는 항목은 모른다고 적어도 됩니다.  \n"
                "5. 설계표 검사를 통과한 뒤에만 디바이스마트 상품을 찾습니다."
            )
            st.caption(
                "예: ‘사람이 지나가면 빛과 소리로 알려주는 장치’, ‘온도·습도를 기록하는 교실 측정기’, "
                "‘화분이 마르면 물을 주는 장치’, ‘천천히 움직이며 장애물을 피하는 작은 자동차’"
            )
        need = st.text_area(
            "무엇을 만들고 싶나요?",
            key=_state_key(project_id, "component_need"),
            placeholder="예: 사람이 지나가면 알려주는 장치 / 온도·습도 측정기 / 화분 자동 물주기 장치",
            height=100,
        )
        budget = st.text_input(
            "희망 예산 (선택)",
            key=_state_key(project_id, "component_budget"),
            placeholder="예: 10만원 이내",
        )
        owned_parts = st.text_area(
            "이미 가지고 있는 부품 (선택)",
            key=_state_key(project_id, "owned_parts"),
            placeholder="예: 아두이노 우노, 브레드보드 / 없으면 비워두세요",
            height=70,
        )
        st.markdown("### 1단계 · 필요한 부품 종류 정하기")
        st.caption(
            "GPT가 특정 상품이 아니라 필요한 부품 종류, 최소 사양, 호환 조건, "
            "과잉 사양 방지 기준을 먼저 정합니다."
        )
        additional_answers = st.text_area(
            "GPT의 추가 질문에 대한 답변 (처음에는 비워두세요)",
            key=_state_key(project_id, "component_plan_answers"),
            placeholder="예: 차체 무게는 약 1kg, 목표 속도는 걷는 속도, AA 배터리를 사용하고 싶어요.",
            height=90,
        )
        plan_signature = "\u241f".join(
            [need.strip(), budget.strip(), owned_parts.strip(), additional_answers.strip()]
        )
        plan_gpt_consent = st.checkbox(
            "제작 목적·예산·보유 부품을 ChatGPT에 전달해 부품 설계표를 만드는 것에 동의합니다.",
            key=_state_key(project_id, "plan_gpt_consent"),
        )
        if plan_gpt_consent and need.strip():
            plan_prompt = build_component_plan_prompt(
                project,
                need,
                budget=budget,
                owned_parts=owned_parts,
                additional_answers=additional_answers,
            )
            st.write(
                "아래 내용을 ChatGPT Plus에 붙여넣고 JSON 답변 전체를 다시 가져오세요."
            )
            st.code(plan_prompt, language=None)
            plan_response = st.text_area(
                "ChatGPT 부품 설계표 답변 붙여넣기",
                key=_state_key(project_id, "component_plan_response"),
                height=220,
                placeholder='{"status": "needs_input", "questions": [...]}',
            )
            if st.button(
                "부품 설계표 해석하기",
                use_container_width=True,
                key=_state_key(project_id, "parse_component_plan"),
            ):
                try:
                    parsed_plan = parse_component_plan(plan_response)
                except ValueError as error:
                    st.error(str(error))
                else:
                    st.session_state[plan_key] = parsed_plan
                    st.session_state[plan_signature_key] = plan_signature
                    st.session_state.pop(result_key, None)
                    st.session_state.pop(review_key, None)
                    st.success("부품 설계표를 읽었습니다.")
        elif not need.strip():
            st.info("먼저 만들고 싶은 것을 입력해주세요.")
        else:
            st.info("동의하면 ChatGPT Plus에 전달할 부품 설계 프롬프트가 표시됩니다.")

        stored_plan = st.session_state.get(plan_key)
        stored_signature = st.session_state.get(plan_signature_key)
        if stored_plan and stored_signature == plan_signature:
            component_plan = stored_plan
            if component_plan.get("summary"):
                st.info(component_plan["summary"])
            questions = component_plan.get("questions") or []
            if questions:
                st.warning("아래 질문에 답한 뒤 갱신된 프롬프트를 ChatGPT에 다시 보내주세요.")
                for question in questions:
                    st.write(f"- **{question['question']}**")
                    if question.get("why"):
                        st.caption(question["why"])
            gearbox = component_plan.get("gearbox_decision") or {}
            if gearbox.get("status") != "unknown":
                decision_label = (
                    "필요함" if gearbox.get("status") == "required" else "필요하지 않음"
                )
                st.write(f"**감속기 판단** · {decision_label}")
                st.caption(gearbox.get("reason") or "판단 근거 없음")
            components = component_plan.get("components") or []
            if components:
                with st.expander("부품 설계표 보기", expanded=True):
                    for component in components:
                        owned_label = " · 이미 보유" if component.get("already_owned") else ""
                        required_label = "필수" if component.get("required") else "선택"
                        st.markdown(
                            f"**[{required_label}] {component['category']}**{owned_label}"
                        )
                        st.write(component["purpose"])
                        if component.get("minimum_requirements"):
                            st.caption(
                                "최소 조건: "
                                + " / ".join(component["minimum_requirements"])
                            )
                        if component.get("compatibility_checks"):
                            st.caption(
                                "호환 확인: "
                                + " / ".join(component["compatibility_checks"])
                            )
                        if component.get("overspec_avoidance"):
                            st.caption(
                                "과잉 사양 방지: "
                                + " / ".join(component["overspec_avoidance"])
                            )
        elif stored_plan:
            st.warning("제작 조건이나 답변이 바뀌었습니다. 부품 설계표를 다시 해석해주세요.")

        plan_issues = (
            component_plan_issues(component_plan, need)
            if component_plan is not None
            else ["부품 설계표가 아직 없습니다."]
        )
        if plan_issues:
            st.error("상품 검색 전에 해결해야 할 항목이 있습니다.")
            for issue in plan_issues:
                st.write(f"- {issue}")
            return
        st.success("부품 종류·감속기·전원·호환 조건 검사를 통과했습니다.")
        query = build_component_search_query(component_plan, need)
    else:
        need = ""
        query = st.text_area(
            "조사 질문",
            key=_state_key(project_id, "query"),
            placeholder="예: 대학생 팀 프로젝트에 적합한 실시간 협업 도구의 핵심 기능을 조사해줘",
            height=100,
        )
    with st.expander("검색 결과 개수 설정 (선택)"):
        max_results = st.slider(
            "가져올 원문 수",
            min_value=3,
            max_value=8,
            value=8 if component_mode else 5,
            key=_state_key(project_id, "max_results"),
        )
    consent = st.checkbox(
        (
            "제작 목적과 부품 검색어가 Tavily 서버로 전송되는 것에 동의합니다."
            if component_mode
            else "검색 질문이 Tavily 서버로 전송되는 것에 동의합니다."
        ),
        key=_state_key(project_id, "consent"),
    )
    if st.button(
        "2단계 · 디바이스마트 상품 검색" if component_mode else "1단계 · 웹 자료 검색",
        type="primary",
        use_container_width=True,
        key=_state_key(project_id, "search"),
    ):
        if not consent:
            st.error("외부 전송 동의를 먼저 확인해주세요.")
        elif not api_key.strip():
            st.error("Tavily API 키를 입력해주세요.")
        elif component_mode and not need.strip():
            st.error("만들고 싶은 것을 한 문장 이상 입력해주세요.")
        else:
            try:
                with st.spinner("Tavily가 관련 원문을 찾고 있습니다..."):
                    search_result = search_tavily(
                        query,
                        api_key,
                        max_results=max_results,
                        include_domains=[DEVICEMART_DOMAIN] if component_mode else None,
                    )
            except (ValueError, TavilySearchError) as error:
                st.error(str(error))
            else:
                search_result["mode"] = "components" if component_mode else "general"
                search_result["need"] = need
                search_result["budget"] = budget
                search_result["owned_parts"] = owned_parts
                search_result["component_plan"] = component_plan
                st.session_state[result_key] = search_result
                st.session_state.pop(review_key, None)
                st.success(
                    f"원문 {len(search_result['results'])}개를 찾았습니다. "
                    f"사용 크레딧: {search_result['credits'] or '확인 불가'}"
                )

    search_result = st.session_state.get(result_key)
    if not search_result:
        st.info("먼저 조사 질문을 입력하고 원문을 찾아주세요.")
        return
    expected_mode = "components" if component_mode else "general"
    if search_result.get("mode") != expected_mode:
        st.info("조사 종류를 바꿨습니다. 현재 모드에서 새로 검색해주세요.")
        return

    st.divider()
    st.subheader("검색된 디바이스마트 자료" if component_mode else "검색된 원문")
    selected_source_numbers: set[int] = set()
    for number, result in enumerate(search_result["results"], start=1):
        with st.container(border=True):
            if component_mode:
                st.markdown(f"**{number}. {result['title']}**")
            else:
                selected = st.checkbox(
                    f"{number}. {result['title']}",
                    value=True,
                    key=_state_key(project_id, f"source_{number}"),
                )
                if selected:
                    selected_source_numbers.add(number)
            st.caption(result["url"])
            if component_mode:
                price = result.get("price_won")
                st.write(
                    f"검색 문맥 표시 가격: {price:,}원"
                    if price
                    else "검색 문맥 표시 가격: 확인되지 않음"
                )
            if result.get("content"):
                st.write(result["content"])
            st.caption(f"검색 관련도: {result.get('score', 0.0):.0%}")

    if component_mode:
        review_prompt = build_devicemart_review_prompt(
            project,
            search_result["need"],
            search_result["results"],
            component_plan=search_result["component_plan"],
            budget=search_result.get("budget") or "",
            owned_parts=search_result.get("owned_parts") or "",
        )
    else:
        review_prompt = build_chatgpt_review_prompt(
            project,
            search_result["query"],
            search_result["results"],
        )
    st.subheader(
        "3단계 · ChatGPT Plus로 호환성 확인"
        if component_mode
        else "2단계 · ChatGPT Plus로 비교하기"
    )
    gpt_consent = st.checkbox(
        "프로젝트 이름·분야·목표와 검색 결과를 ChatGPT에 직접 붙여넣는 것에 동의합니다.",
        key=_state_key(project_id, "gpt_consent"),
    )
    if not gpt_consent:
        st.info("동의하면 ChatGPT Plus에 전달할 검수용 프롬프트가 표시됩니다.")
        return
    st.write(
        "아래 상자의 복사 아이콘을 누르고 ChatGPT Plus에 붙여넣으세요. "
        "ChatGPT의 답변 전체를 다시 그 아래 입력칸에 붙여넣으면 됩니다."
    )
    st.code(review_prompt, language=None)
    gpt_response = st.text_area(
        "ChatGPT 답변 붙여넣기",
        key=_state_key(project_id, "gpt_response"),
        height=220,
        placeholder=(
            '{"summary": "...", "recommended_products": [...]}'
            if component_mode
            else '{"summary": "...", "confirmed_candidates": [...]}'
        ),
    )
    if st.button(
        "GPT 답변 해석하기",
        use_container_width=True,
        key=_state_key(project_id, "parse"),
    ):
        try:
            st.session_state[review_key] = (
                parse_devicemart_review(gpt_response)
                if component_mode
                else parse_chatgpt_review(gpt_response)
            )
        except ValueError as error:
            st.error(str(error))
        else:
            st.success("GPT 답변을 항목별로 나눴습니다. 이제 직접 확인해주세요.")

    review = st.session_state.get(review_key)
    if not review:
        return

    st.divider()
    st.subheader(
        "4단계 · 구매 후보 고르기"
        if component_mode
        else "3단계 · 사용자가 최종 확인하기"
    )
    if component_mode:
        _render_component_review(
            project_id=project_id,
            search_result=search_result,
            review=review,
            component_plan=search_result["component_plan"],
            existing_sources=existing_sources,
            add_source=add_source,
            add_fact_record=add_fact_record,
            result_key=result_key,
            review_key=review_key,
        )
        return
    if review.get("summary"):
        st.info(review["summary"])

    candidates = review.get("confirmed_candidates") or []
    approved_candidate_indexes: set[int] = set()
    if candidates:
        st.markdown("#### 확정 사실 후보")
        st.caption(
            "체크한 항목만 확정 사실로 저장됩니다. 연결된 첫 번째 출처도 ‘확인됨’으로 바뀝니다."
        )
        for index, claim in enumerate(candidates):
            approved = st.checkbox(
                claim["content"],
                value=False,
                key=_state_key(project_id, f"approve_{index}"),
            )
            st.caption(_claim_caption(claim))
            if approved:
                approved_candidate_indexes.add(index)

    category_labels = {
        "conflicts": "서로 충돌하는 정보",
        "unverified": "추가 확인이 필요한 정보",
        "proposals": "GPT의 제안",
    }
    for category, label in category_labels.items():
        claims = review.get(category) or []
        if not claims:
            continue
        with st.expander(f"{label} ({len(claims)}건)"):
            for claim in claims:
                st.write(f"- {claim['content']}")
                st.caption(_claim_caption(claim))

    save_review_notes = st.checkbox(
        "미승인·충돌·제안 항목도 검토 기록으로 저장합니다.",
        value=True,
        key=_state_key(project_id, "save_review_notes"),
    )
    if st.button(
        "선택한 조사 결과 저장",
        type="primary",
        use_container_width=True,
        key=_state_key(project_id, "save"),
    ):
        missing_source_candidates = [
            claim["content"]
            for index, claim in enumerate(candidates)
            if index in approved_candidate_indexes
            and not any(
                number in selected_source_numbers
                for number in claim.get("source_numbers") or []
            )
        ]
        if missing_source_candidates:
            st.error(
                "승인한 사실 중 선택된 근거 출처가 없는 항목이 있습니다. "
                "해당 출처를 다시 체크해주세요."
            )
            return
        try:
            saved = persist_research_review(
                project_id=project_id,
                results=search_result["results"],
                selected_source_numbers=selected_source_numbers,
                review=review,
                approved_candidate_indexes=approved_candidate_indexes,
                existing_sources=existing_sources,
                add_source=add_source,
                update_source_status=update_source_status,
                add_fact_record=add_fact_record,
                save_review_notes=save_review_notes,
            )
        except (ValueError, RuntimeError, sqlite3.Error) as error:
            st.error(f"조사 결과를 저장하지 못했습니다: {error}")
        else:
            st.success(
                f"새 출처 {saved['sources']}건, 확정 사실 {saved['confirmed']}건, "
                f"검토 기록 {saved['review_notes']}건을 저장했습니다."
            )
            st.session_state.pop(result_key, None)
            st.session_state.pop(review_key, None)
