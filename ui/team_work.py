"""팀 업무 기록 상세와 팀장 계획 수정 요청 Streamlit UI."""

from __future__ import annotations

import html

import streamlit as st

from workflow.assignment import ACTIVE_EMPLOYEE_ID
from workflow.plan_revision import revise_manager_plan


@st.dialog("업무 기록 상세", width="large")
def show_team_record_detail(
    title: str,
    content: str = "",
    error: str = "",
    meeting_turns: list[dict] | None = None,
    employees: list[dict] | None = None,
) -> None:
    """화면 위치와 관계없이 중앙의 스크롤 가능한 창에 업무 기록을 표시합니다."""

    st.markdown(f"### {html.escape(title)}")
    st.caption("내용이 길면 아래 상세 영역 안에서 스크롤할 수 있습니다.")
    employees_by_id = {
        employee["id"]: employee for employee in (employees or [])
    }
    with st.container(height=560, border=True):
        if meeting_turns is not None:
            if not meeting_turns:
                st.info("아직 저장된 회의 발언이 없습니다.")
            for turn in meeting_turns:
                speaker = employees_by_id.get(turn["employee_id"])
                speaker_name = (
                    speaker["name"] if speaker is not None else turn["employee_id"]
                )
                turn_label = (
                    "팀장 결론"
                    if turn["turn_type"] == "conclusion"
                    else "직원 의견"
                )
                with st.container(border=True):
                    st.markdown(f"**{speaker_name} · {turn_label}**")
                    st.markdown(turn["content"])
        elif content:
            st.markdown(content)
        elif error:
            st.error(error)
        else:
            st.info("아직 작성된 내용이 없습니다.")


def task_record_action_button(label: str, button_label: str, key: str) -> bool:
    """업무 설명 바로 옆에 일정한 크기의 상세 버튼을 배치합니다."""

    with st.container(
        key=f"task_record_row_{key}",
        horizontal=True,
        vertical_alignment="top",
        horizontal_alignment="left",
        gap="small",
        width="stretch",
    ):
        st.markdown(
            f'<div class="task-record-label">{html.escape(label)}</div>',
            unsafe_allow_html=True,
            width=460,
        )
        return st.button(button_label, key=key, width=180)


@st.dialog("팀장 계획 수정 요청", width="large")
def show_plan_revision(
    approval: dict,
    project: dict,
    sources: list[dict],
    user_message: dict,
    manager_profile: dict,
    manager_department: str,
    supporting_employees: list[tuple[dict, str]],
) -> None:
    """사용자 피드백을 받아 팀장의 계획을 다시 작성합니다."""

    st.markdown("**현재 계획**")
    st.write(approval["plan_content"])
    with st.form(f"approval_revision_{approval['id']}"):
        feedback = st.text_area(
            "수정할 내용",
            height=140,
            max_chars=2000,
            placeholder="예: 예산을 30만 원 이내로 줄이고 안전 검수 단계를 추가해주세요.",
        )
        submitted = st.form_submit_button(
            "수정 계획 요청",
            use_container_width=True,
        )

    if not submitted:
        return
    if not feedback.strip():
        st.error("수정할 내용을 입력해주세요.")
        return

    with st.spinner(f"{manager_profile['name']} 직원이 계획을 수정하고 있습니다..."):
        result = revise_manager_plan(
            approval=approval,
            project=project,
            sources=sources,
            user_message=user_message,
            manager_profile=manager_profile,
            manager_department=manager_department,
            supporting_employees=supporting_employees,
            feedback=feedback,
        )
    if not result.succeeded:
        st.error(result.error)
        return

    st.session_state.messages.append(
        {
            "message_id": result.message_id,
            "role": "assistant",
            "content": result.content,
            "employee_id": ACTIVE_EMPLOYEE_ID,
        }
    )
    st.rerun()
