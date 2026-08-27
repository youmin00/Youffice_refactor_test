"""YOUFFICE ?? ?? ?? UI."""

import streamlit as st


def render_console_handoff_list(
    handoffs: list[dict],
    employees_by_id: dict[str, dict],
    direction: str,
) -> None:
    """직원이 받은 자료 또는 보낸 자료의 실제 내용을 펼침 목록으로 표시합니다."""

    if not handoffs:
        empty_message = (
            "최근 업무에서 전달받은 자료가 없습니다."
            if direction == "received"
            else "최근 업무에서 다른 직원에게 보낸 자료가 없습니다."
        )
        st.info(empty_message)
        return

    for handoff_index, handoff in enumerate(reversed(handoffs), start=1):
        counterpart_id = (
            handoff["from_employee_id"]
            if direction == "received"
            else handoff["to_employee_id"]
        )
        counterpart = employees_by_id.get(counterpart_id)
        counterpart_name = counterpart["name"] if counterpart else counterpart_id
        direction_label = "보낸 직원" if direction == "received" else "받은 직원"
        with st.expander(
            f"{direction_label}: {counterpart_name} · 자료 {len(handoffs) - handoff_index + 1}",
            expanded=handoff_index == 1,
        ):
            st.markdown(handoff["content"] or "전달된 내용이 비어 있습니다.")
            st.caption(f"기록 시간: {handoff['created_at']}")
