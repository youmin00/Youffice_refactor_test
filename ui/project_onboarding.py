"""새 프로젝트를 자연 대화에서 팀 업무 시작까지 안내하는 UI."""

from __future__ import annotations

from typing import Any

import streamlit as st

from conversation.project_collaboration import (
    build_idea_conversation_start_prompt,
    build_next_idea_question_prompt,
    build_team_plan_request_prompt,
    is_manager_plan_content,
)


MANAGER_EMPLOYEE_ID = "project_manager"
MANAGER_PLAN_REQUEST_STATE = "manager_plan_request_project_id"


def project_onboarding_stage(
    messages: list[dict[str, Any]],
    latest_task: dict[str, Any] | None,
) -> str:
    """저장된 대화와 업무 상태만으로 현재 시작 단계를 판단합니다."""

    if latest_task is not None:
        return "work_started"

    latest_user_index = next(
        (
            index
            for index in range(len(messages) - 1, -1, -1)
            if messages[index].get("role") == "user"
        ),
        None,
    )
    if latest_user_index is None:
        return "project_created"

    latest_manager_answer = next(
        (
            message
            for message in reversed(messages[latest_user_index + 1 :])
            if message.get("role") == "assistant"
            and message.get("employee_id") == MANAGER_EMPLOYEE_ID
        ),
        None,
    )
    if latest_manager_answer is None:
        return "waiting_for_yuki"
    if is_manager_plan_content(latest_manager_answer.get("content")):
        return "plan_ready"
    return "idea_conversation"


def _render_step(title: str, description: str, state: str) -> None:
    st.markdown(f"**{title}**")
    if state == "done":
        st.success("완료")
    elif state == "current":
        st.info("지금 할 일")
    else:
        st.caption("다음 단계")
    st.caption(description)


def _switch_to_manager(project_id: int) -> None:
    st.session_state.chat_employee_request = MANAGER_EMPLOYEE_ID
    st.session_state.workspace_view_request = "💬 대화"
    st.session_state.new_project_onboarding_id = project_id
    st.rerun()


def _step_states(stage: str) -> tuple[str, str, str, str]:
    if stage == "project_created":
        return "current", "next", "next", "next"
    if stage == "waiting_for_yuki":
        return "done", "current", "next", "next"
    if stage == "idea_conversation":
        return "done", "current", "next", "next"
    return "done", "done", "done", "current"


def render_project_onboarding(
    project: dict[str, Any],
    messages: list[dict[str, Any]],
    latest_task: dict[str, Any] | None,
    *,
    is_manager_chat: bool,
    plan_request_pending: bool = False,
) -> str | None:
    """상황별 안내를 표시하고 원클릭으로 보낼 유키 요청을 반환합니다."""

    stage = project_onboarding_stage(messages, latest_task)
    if stage == "work_started":
        return None

    project_id = int(project["id"])
    just_created = st.session_state.pop("new_project_onboarding_id", None) == project_id
    if just_created:
        st.success(
            "프로젝트가 만들어졌습니다. 유키와 편하게 대화하며 아이디어를 정리한 뒤, "
            "준비됐을 때 팀 계획을 만들고 승인하면 됩니다."
        )

    with st.container(border=True):
        st.markdown("### 🚀 유키와 함께 프로젝트 만들기")
        st.caption(
            "처음부터 전체 설계나 부품명을 알 필요가 없습니다. 유키가 한 번에 중요한 "
            "질문 하나씩 물으며 아이디어를 함께 구체화합니다."
        )

        states = _step_states(stage)
        step_columns = st.columns(4, gap="small")
        steps = (
            ("1. 아이디어 공유", "만들고 싶은 결과 말하기"),
            ("2. 유키와 구체화", "질문과 추천으로 조건 정하기"),
            ("3. 팀 계획", "직원 담당과 순서 만들기"),
            ("4. 승인·업무 시작", "확인 후 실제 팀 실행"),
        )
        for column, (title, description), state in zip(step_columns, steps, states):
            with column:
                _render_step(title, description, state)

        if not is_manager_chat:
            st.warning("프로젝트 공동 설계는 팀장 유키와 진행합니다.")
            if st.button(
                "유키에게 돌아가서 계속하기",
                type="primary",
                use_container_width=True,
                key=f"onboarding_switch_manager_{project_id}",
            ):
                _switch_to_manager(project_id)
            return None

        if stage == "project_created":
            st.write(
                "버튼을 누르면 프로젝트 목표가 유키에게 전달됩니다. 유키의 질문에 "
                "아는 만큼만 답하고, 모르면 그대로 모른다고 말해도 됩니다."
            )
            if st.button(
                "유키와 아이디어 대화 시작하기",
                type="primary",
                use_container_width=True,
                key=f"onboarding_start_{project_id}",
            ):
                return build_idea_conversation_start_prompt(project)
        elif stage == "waiting_for_yuki":
            request_kind = "팀 계획" if plan_request_pending else "아이디어 질문"
            st.warning(
                f"유키의 {request_kind} 답변이 아직 저장되지 않았습니다. 요청 중이라면 "
                "잠시 기다리고, 오류가 표시됐다면 아래 버튼으로 다시 요청하세요."
            )
            if st.button(
                f"유키에게 {request_kind} 다시 요청하기",
                use_container_width=True,
                key=f"onboarding_retry_{project_id}",
            ):
                if plan_request_pending:
                    return build_team_plan_request_prompt(project)
                return build_idea_conversation_start_prompt(project)
        elif stage == "idea_conversation":
            st.info(
                "유키의 질문에 채팅으로 답하며 계속 다듬어도 됩니다. 준비됐다고 느낄 "
                "때만 팀 계획으로 넘어가세요."
            )
            next_column, plan_column = st.columns(2, gap="medium")
            with next_column:
                if st.button(
                    "다음으로 정할 것 물어보기",
                    use_container_width=True,
                    key=f"onboarding_next_question_{project_id}",
                ):
                    return build_next_idea_question_prompt()
            with plan_column:
                if st.button(
                    "현재 아이디어로 팀 계획 만들기",
                    type="primary",
                    use_container_width=True,
                    key=f"onboarding_make_plan_{project_id}",
                ):
                    st.session_state[MANAGER_PLAN_REQUEST_STATE] = project_id
                    return build_team_plan_request_prompt(project)
        else:
            st.success(
                "유키의 팀 계획이 준비됐습니다. 아래의 ‘계획 승인 및 업무 시작’ 버튼을 "
                "누르면 실제 직원 협업이 시작됩니다."
            )
            if st.button(
                "팀 계획과 시작 버튼으로 이동",
                use_container_width=True,
                key=f"onboarding_focus_plan_{project_id}",
            ):
                st.session_state.onboarding_focus_plan_approval = project_id

    return None


def render_plan_approval_anchor(project_id: int) -> None:
    """온보딩 안내에서 승인 영역으로 안전하게 스크롤합니다."""

    anchor_id = f"youffice-plan-approval-{project_id}"
    st.markdown(f'<div id="{anchor_id}"></div>', unsafe_allow_html=True)
    should_focus = st.session_state.pop("onboarding_focus_plan_approval", None) == project_id
    if should_focus:
        st.html(
            f"""
            <script>
            setTimeout(() => {{
                const target = document.getElementById({anchor_id!r});
                if (target) {{
                    target.scrollIntoView({{behavior: "smooth", block: "center"}});
                }}
            }}, 200);
            </script>
            """,
            unsafe_allow_javascript=True,
        )
