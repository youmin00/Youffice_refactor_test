"""새 프로젝트를 자연 대화에서 팀 업무 시작까지 안내하는 UI."""

from __future__ import annotations

from typing import Any

import streamlit as st

from conversation.project_collaboration import (
    MAX_GUIDED_QUESTIONS,
    build_idea_conversation_start_prompt,
    build_next_idea_question_prompt,
    build_supplemental_question_prompt,
    build_team_plan_request_prompt,
    is_manager_plan_content,
    manager_guided_turn_count,
    supplemental_question_count,
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
    if manager_guided_turn_count(messages) >= MAX_GUIDED_QUESTIONS:
        return "draft_ready"
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
    if stage == "draft_ready":
        return "done", "done", "current", "next"
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
            "프로젝트가 만들어졌습니다. 유키와 핵심 조건만 짧게 정리한 뒤, "
            "제작 준비 계획을 만들고 팀의 조사·설계 검토를 시작할 수 있습니다."
        )

    with st.container(border=True):
        st.markdown("### 🚀 아이디어를 제작 가능한 계획으로 바꾸기")
        st.caption(
            "처음부터 설계나 부품명을 알 필요가 없습니다. 유키는 처음 핵심 질문을 최대 "
            f"{MAX_GUIDED_QUESTIONS}개만 한 뒤 초안을 먼저 보여 줍니다. 이후에는 원하는 만큼 중요한 항목을 "
            "하나씩 구체화할 수 있고, 사용자가 유키에게 묻는 질문은 이 횟수에 포함되지 않습니다."
        )

        states = _step_states(stage)
        step_columns = st.columns(4, gap="small")
        steps = (
            ("1. 아이디어 공유", "만들고 싶은 결과 말하기"),
            ("2. 핵심 조건 정리", "첫 질문은 최대 3개"),
            ("3. 초안·보충 확인", "필요한 질문만 선택"),
            ("4. 계획 확정", "팀의 자료 작성 시작"),
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
                "유키의 질문에 아는 만큼만 답하세요. 궁금한 것을 반대로 물어보면 유키가 먼저 답하며, "
                "그 답변은 핵심 질문 횟수에 포함되지 않습니다. 언제든 현재 내용이나 기본 가정으로 준비 계획을 만들 수 있습니다."
            )
            next_column, plan_column, default_column = st.columns(3, gap="medium")
            with next_column:
                if st.button(
                    "핵심 질문 하나 더",
                    use_container_width=True,
                    key=f"onboarding_next_question_{project_id}",
                ):
                    return build_next_idea_question_prompt()
            with plan_column:
                if st.button(
                    "현재 내용으로 준비 계획",
                    type="primary",
                    use_container_width=True,
                    key=f"onboarding_make_plan_{project_id}",
                ):
                    st.session_state[MANAGER_PLAN_REQUEST_STATE] = project_id
                    return build_team_plan_request_prompt(project)
            with default_column:
                if st.button(
                    "모르는 건 기본 가정으로",
                    use_container_width=True,
                    key=f"onboarding_default_plan_{project_id}",
                ):
                    st.session_state[MANAGER_PLAN_REQUEST_STATE] = project_id
                    return build_team_plan_request_prompt(
                        project,
                        use_default_assumptions=True,
                    )
        elif stage == "draft_ready":
            supplemental_count = supplemental_question_count(messages)
            st.success(
                "첫 핵심 질문 단계가 끝났습니다. 유키가 정리한 초안을 기준으로 바로 계획을 만들거나, "
                "결과에 영향을 주는 중요한 항목을 원하는 만큼 하나씩 더 확인할 수 있습니다."
            )
            st.caption(
                f"선택형 보충 질문 {supplemental_count}회 진행 · "
                "횟수 제한은 없으며 질문마다 필요한 이유와 답에 따라 달라지는 점을 먼저 보여 줍니다."
            )
            question_column, plan_column, default_column = st.columns(3, gap="medium")
            with question_column:
                if st.button(
                    "중요한 항목 하나 더 구체화",
                    use_container_width=True,
                    key=f"onboarding_supplemental_{project_id}",
                ):
                    return build_supplemental_question_prompt(project)
            with plan_column:
                if st.button(
                    "현재 내용으로 준비 계획",
                    type="primary",
                    use_container_width=True,
                    key=f"onboarding_draft_ready_plan_{project_id}",
                ):
                    st.session_state[MANAGER_PLAN_REQUEST_STATE] = project_id
                    return build_team_plan_request_prompt(project)
            with default_column:
                if st.button(
                    "모르는 건 기본 가정으로",
                    use_container_width=True,
                    key=f"onboarding_draft_ready_default_{project_id}",
                ):
                    st.session_state[MANAGER_PLAN_REQUEST_STATE] = project_id
                    return build_team_plan_request_prompt(
                        project,
                        use_default_assumptions=True,
                    )
        else:
            st.success(
                "유키의 제작 준비 계획이 마련됐습니다. 아래 승인 영역에서 내용을 확인하면 "
                "직원들이 요구사항·조사·기술·위험·테스트 자료를 작성하고 서로 검토합니다."
            )
            if st.button(
                "제작 준비 계획 확인하기",
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
