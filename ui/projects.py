"""프로젝트 생성·삭제·요약을 담당하는 Streamlit UI."""

from __future__ import annotations

import re
import sqlite3

import streamlit as st

from conversation.prompts import BEGINNER_GUIDANCE_MARKER
from database import create_project, delete_project, list_messages, list_team_tasks


def _project_name_from_idea(project_goal: str) -> str:
    """아이디어의 첫 문장을 짧고 읽기 쉬운 프로젝트명으로 만듭니다."""

    first_line = project_goal.strip().splitlines()[0]
    normalized_line = re.sub(r"\s+", " ", first_line).strip()
    if len(normalized_line) <= 40:
        return normalized_line
    return normalized_line[:39].rstrip() + "…"


def new_project_session_updates(project_id: int) -> dict[str, object]:
    """새 프로젝트 생성 직후 적용할 화면·대화 상태를 한곳에서 정의합니다."""

    return {
        "current_project_id": project_id,
        "loaded_project_id": project_id,
        "messages": [],
        "workspace_view_request": "💬 대화",
        "chat_employee_request": "project_manager",
        "new_project_onboarding_id": project_id,
    }


@st.dialog("새 프로젝트 만들기", width="medium")
def show_project_creator() -> None:
    """완성된 설계 없이도 아이디어만으로 프로젝트를 시작합니다."""

    st.caption(
        "정확한 설계가 없어도 괜찮아요. 지금 생각나는 만큼만 적으면 "
        "AI 직원들이 대화하면서 하나씩 정리해 드립니다."
    )
    with st.form("create_project_form"):
        project_goal = st.text_area(
            "무엇을 만들고 싶나요?",
            max_chars=1500,
            height=150,
            placeholder=(
                "예: 책상 위 물건을 카메라로 구분해서 종류별로 옮기는 장치를 "
                "만들고 싶어요. 아직 어떤 모터나 부품이 필요한지는 몰라요."
            ),
        )
        step_by_step_guidance = st.checkbox(
            "AI가 필요한 내용을 한두 가지씩 질문하며 같이 정리해 주세요.",
            value=True,
            help="모르는 선택에는 쉬운 예시와 추천 이유도 함께 설명합니다.",
        )
        project_name = st.text_input(
            "프로젝트 이름 (선택)",
            max_chars=80,
            placeholder="비워두면 위 내용에서 자동으로 만들어집니다.",
        )

        with st.expander("알고 있는 내용 더 적기 (선택)"):
            project_field = st.text_input(
                "분야 (몰라도 괜찮아요)",
                max_chars=80,
                placeholder="예: 로봇, 전자, 소프트웨어",
            )
            project_notes = st.text_area(
                "이미 가지고 있거나 해본 것",
                max_chars=1000,
                height=100,
                placeholder=(
                    "예: 아두이노 1개가 있고 Python은 조금 해봤어요. "
                    "아무것도 없으면 비워두세요."
                ),
            )
        submitted = st.form_submit_button(
            "이 아이디어로 시작",
            use_container_width=True,
        )

    if not submitted:
        return

    normalized_goal = project_goal.strip()
    if not normalized_goal:
        st.error("만들고 싶은 것을 한 문장만이라도 적어주세요.")
        return

    normalized_name = project_name.strip() or _project_name_from_idea(normalized_goal)
    normalized_field = project_field.strip()
    normalized_notes = project_notes.strip()
    if step_by_step_guidance:
        normalized_notes = "\n".join(
            part
            for part in (BEGINNER_GUIDANCE_MARKER, normalized_notes)
            if part
        )

    try:
        project_id = create_project(
            normalized_name,
            normalized_field,
            normalized_goal,
            "",
            "",
            "",
            normalized_notes,
        )
    except sqlite3.Error as error:
        st.error(f"프로젝트를 저장하지 못했습니다: {error}")
        return

    for state_name, state_value in new_project_session_updates(project_id).items():
        st.session_state[state_name] = state_value
    st.rerun()


@st.dialog("프로젝트 삭제", width="small")
def show_project_delete_confirmation(
    project: dict,
    projects: list[dict],
) -> None:
    """선택한 프로젝트를 확인 후 삭제합니다."""

    st.warning(f"‘{project['name']}’ 프로젝트를 삭제합니다.")
    st.write(
        "이 프로젝트에 저장된 대화, 팀 업무, 출처, 장기 기억, 결정·오류와 "
        "보고서가 함께 삭제됩니다. 직원 프로필과 다른 프로젝트는 삭제되지 않습니다."
    )
    with st.form(f"delete_project_form_{project['id']}"):
        confirmed = st.checkbox("삭제할 프로젝트 이름과 범위를 확인했습니다.")
        submitted = st.form_submit_button(
            "프로젝트 영구 삭제",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return
    if not confirmed:
        st.error("삭제하려면 확인 항목을 선택해주세요.")
        return

    running_task = next(
        (
            task
            for task in list_team_tasks(project["id"], limit=100)
            if task["status"] == "running"
        ),
        None,
    )
    if running_task is not None:
        st.error(
            f"팀 업무 #{running_task['id']}가 실행 중이라 지금은 삭제할 수 없습니다. "
            "업무가 끝난 뒤 다시 시도해주세요."
        )
        return

    try:
        delete_project(project["id"])
    except sqlite3.Error as error:
        st.error(f"프로젝트를 삭제하지 못했습니다: {error}")
        return

    remaining_project_ids = [
        existing_project["id"]
        for existing_project in projects
        if existing_project["id"] != project["id"]
    ]
    next_project_id = remaining_project_ids[0] if remaining_project_ids else None
    st.session_state.current_project_id = next_project_id
    st.session_state.loaded_project_id = next_project_id
    st.session_state.messages = (
        list_messages(next_project_id)
        if next_project_id is not None
        else []
    )
    st.rerun()


def render_project_summary(project: dict) -> None:
    """현재 프로젝트의 사용자가 입력한 핵심 정보만 간단히 표시합니다."""

    with st.expander(f"📁 현재 프로젝트 · {project['name']}"):
        st.markdown(f"**만들고 싶은 것**  \n{project['goal']}")

        if project["field"]:
            st.markdown(f"**분야**  \n{project['field']}")

        project_notes = str(project["skills"] or "").strip()
        uses_step_by_step_guidance = project_notes.startswith(
            BEGINNER_GUIDANCE_MARKER
        )
        project_notes = project_notes.removeprefix(
            BEGINNER_GUIDANCE_MARKER
        ).strip()
        if uses_step_by_step_guidance:
            st.markdown(
                "**진행 방식**  \n"
                "AI가 필요한 질문을 쉬운 말로 한두 가지씩 나누어 안내"
            )
        if project_notes:
            st.markdown(
                f"**현재 알고 있거나 보유한 것**  \n{project_notes}"
            )
        st.caption(
            "필요한 조건과 부품은 직원들과 대화하면서 하나씩 정하면 됩니다."
        )
