"""프로젝트 자료 검색과 고급 기록 관리를 초보자용으로 묶은 UI."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from ui.internet_research import (
    COMPONENT_RESEARCH_MODE,
    GENERAL_RESEARCH_MODE,
    research_mode_session_key,
    show_internet_research_dialog,
)
from ui.project_records import show_record_manager, show_source_manager


_GUIDED_PROMPT_FRAGMENTS = (
    "프로젝트를 나와 함께 구체화해 줘",
    "지금까지 대화에서 확정된 내용",
    "승인용 팀 업무 계획을 만들어 줘",
)


def build_research_prefill(
    project: dict[str, Any],
    messages: list[dict[str, Any]],
) -> str:
    """프로젝트 목표와 최근 사용자 설명을 검색창의 시작 문장으로 만듭니다."""

    goal = str(project.get("goal") or "").strip()
    latest_user_detail = ""
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "").strip()
        if not 10 <= len(content) <= 400:
            continue
        if any(fragment in content for fragment in _GUIDED_PROMPT_FRAGMENTS):
            continue
        latest_user_detail = content
        break

    parts = []
    if goal:
        parts.append(f"프로젝트 목표: {goal}")
    if latest_user_detail and latest_user_detail != goal:
        parts.append(f"최근 대화 내용: {latest_user_detail}")
    return "\n".join(parts)


def render_project_research_tools(
    project: dict[str, Any],
    messages: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    records: list[dict[str, Any]],
    fact_records: list[dict[str, Any]],
    *,
    add_source: Callable[..., int],
    update_source_status: Callable[[int, str], None],
    add_fact_record: Callable[..., int | None],
) -> None:
    """검색 목적은 바로 고르게 하고 저장·기록 도구는 선택 영역에 둡니다."""

    project_id = int(project["id"])
    research_prefill = build_research_prefill(project, messages)
    verified_source_count = sum(
        source.get("verification_status") == "verified"
        for source in sources
    )

    with st.container(border=True):
        st.markdown("### 🔎 자료가 필요할 때")
        st.caption(
            "항상 사용할 필요는 없습니다. 유키의 계획에서 확인할 정보나 구매할 "
            "부품이 생겼을 때 목적에 맞는 버튼 하나만 누르세요."
        )

        web_column, component_column = st.columns(2, gap="medium")
        with web_column:
            st.markdown("**최신 정보·사례·규격이 궁금해요**")
            st.caption("웹 자료를 찾고 출처가 있는 내용만 골라 저장합니다.")
            open_general_research = st.button(
                "🌐 웹 자료 찾기",
                key=f"open_general_research_{project_id}",
                use_container_width=True,
            )
        with component_column:
            st.markdown("**어떤 부품을 사야 할지 모르겠어요**")
            st.caption("디바이스마트 상품의 가격·용도·호환성을 비교합니다.")
            open_component_research = st.button(
                "🧩 디바이스마트 부품 찾기",
                key=f"open_component_research_{project_id}",
                type="primary",
                use_container_width=True,
            )

        if open_general_research or open_component_research:
            if open_component_research:
                mode = COMPONENT_RESEARCH_MODE
                input_key = f"internet_research_{project_id}_component_need"
            else:
                mode = GENERAL_RESEARCH_MODE
                input_key = f"internet_research_{project_id}_query"
            st.session_state[research_mode_session_key(project_id)] = mode
            if research_prefill and not st.session_state.get(input_key):
                st.session_state[input_key] = research_prefill
            show_internet_research_dialog(
                project,
                sources,
                add_source=add_source,
                update_source_status=update_source_status,
                add_fact_record=add_fact_record,
            )

    with st.expander("저장된 자료·프로젝트 기록 관리 (선택)"):
        st.caption(
            f"저장 자료 {len(sources)}건 · 확인됨 {verified_source_count}건 · "
            f"장기 기억 {len(memories)}건 · 사실·근거 {len(fact_records)}건"
        )
        st.write(
            "검색 결과를 다시 확인하거나, 유키와 직원들이 기억해야 할 결정·오류를 "
            "직접 정리할 때만 사용하세요."
        )
        source_column, record_column = st.columns(2)
        with source_column:
            if st.button(
                "저장 자료 보기·수정",
                key=f"manage_sources_{project_id}",
                use_container_width=True,
            ):
                show_source_manager(project_id, sources)
        with record_column:
            if st.button(
                "기억·결정·오류 관리",
                key=f"manage_records_{project_id}",
                use_container_width=True,
            ):
                show_record_manager(
                    project_id,
                    sources,
                    memories,
                    records,
                    fact_records,
                )

        if sources:
            st.markdown("**최근 저장 자료**")
            source_status_labels = {
                "unverified": "미확인",
                "verified": "확인됨",
                "rejected": "사용 제외",
            }
            for source in sources[:5]:
                status = source_status_labels.get(
                    source.get("verification_status"),
                    "미확인",
                )
                st.write(f"- {source.get('title') or '제목 없음'} · {status}")
            if len(sources) > 5:
                st.caption(f"외 {len(sources) - 5}건은 ‘저장 자료 보기·수정’에서 확인할 수 있습니다.")
