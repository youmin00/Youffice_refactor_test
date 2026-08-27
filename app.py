import html
import importlib
import json
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import streamlit as st
import markdown as markdown_renderer

from animation.lab import render_animation_lab
from ui.styles import apply_global_styles
from ui.sidebar import employee_card_html
from ui.office_dialogs import (
    show_office_employee_dialog,
    show_office_handoff_dialog,
    show_office_meeting_dialog,
)
from ui.organization import (
    ACTIVE_EMPLOYEE_ID,
    department_name,
    load_organization,
    show_organization_editor,
    show_profile_editor,
)
from ui.project_tools import render_project_research_tools
from ui.project_onboarding import (
    MANAGER_PLAN_REQUEST_STATE,
    render_plan_approval_anchor,
    render_project_onboarding,
)
from ui.projects import (
    render_project_summary,
    show_project_creator,
    show_project_delete_confirmation,
)
from ui.report_revision import (
    clear_report_revision_dialog,
    clear_structured_report_revision_dialog,
    show_report_revision_dialog,
    show_structured_final_report_revision,
    structured_report_revision_key,
)
from ui.team_work import (
    show_plan_revision,
    show_team_record_detail,
    task_record_action_button,
)
from workflow.engine import start_team_workflow_background
from workflow.team_consultation import (
    is_team_consultation_running,
    recover_stale_team_consultation_activities,
    start_team_consultation_background,
)
from workflow.external_review import (
    ExternalReviewError,
    external_review_status,
    run_external_cross_review,
)
from workflow.reporting import (
    build_saved_meeting_context,
    generate_project_report,
    retry_task_synthesis,
)
from workflow.structured_report import is_structured_final_report

from workflow.recovery import (
    employee_names_in_text,
    ensure_failed_task_clarification,
    resume_workflow_from_clarification,
)
from workflow.review import (
    WorkflowCancelled,
    ensure_workflow_not_cancelled,
    has_explicit_review_targets,
    has_explicit_review_verdict,
    has_valid_review_contract,
    review_clarification_questions,
    review_target_employee_ids,
    review_verdict,
)

from workflow.assignment import (
    EMPLOYEE_WORKSTREAM_LABELS,
    build_employee_assignment,
    build_employee_output_instruction,
    build_manager_delegation_instruction,
    normalize_manager_plan_project_name,
    employee_workstream,
    is_memory_employee,
    is_report_employee,
    is_review_employee,
)

from ui.office import (
    employee_action_sprite_data,
    employee_animation_action,
    employee_sprite_content,
    office_background_data,
    office_employee_states,
    render_employee_room_office,
    render_live_pixel_office,
    render_pixel_office,
)
from ui.chat import (
    profile_avatar_content,
    render_chat_message,
    render_manager_context,
)
from ui.ai_progress import start_chat_progress
from animation.staff_specs import build_staff_app_specs
import database as database_module
from conversation.employee_prompts import build_employee_system_prompt
from conversation.project_collaboration import (
    build_team_plan_request_prompt,
    build_manager_collaboration_instruction,
    is_manager_plan_content,
    is_substantially_repeated_reply,
)
from conversation.dialogue_state import build_dialogue_state_instruction
from conversation.context_window import select_recent_model_messages
from conversation.prompts import (
    build_memory_context,
    build_project_context,
    build_source_context,
)
from conversation.response_validator import is_korean_answer, remove_thinking
from conversation.response_recovery import EMPTY_ANSWER_MESSAGE, final_answer_with_retry
from conversation.ollama_client import (
    OllamaResponseFormatError,
    describe_ollama_failure,
    optimized_chat,
)
from conversation.response_formats import MANAGER_PLAN_MARKERS

# Streamlit 자동 새로고침 중 이전 database 모듈이 메모리에 남는 경우에만
# 최신 파일을 다시 읽어 새로 추가된 DB 함수를 안전하게 사용할 수 있게 합니다.
_REQUIRED_DATABASE_APIS = (
    "clear_employee_activities",
    "create_team_meeting",
    "add_meeting_turn",
    "finish_team_meeting",
    "get_team_meeting",
    "list_meeting_turns",
    "add_review_targets",
    "mark_review_targets_resubmitted",
    "list_review_targets",
    "create_or_get_report_approval",
    "list_report_approvals",
    "update_report_approval",
    "create_task_control",
    "get_task_control",
    "update_task_control_state",
    "create_or_get_clarification_request",
    "get_pending_clarification_request",
    "answer_clarification_request",
    "add_fact_record",
    "list_fact_records",
    "update_fact_record_source",
    "delete_fact_record",
)
if not all(hasattr(database_module, name) for name in _REQUIRED_DATABASE_APIS):
    importlib.reload(database_module)

from database import (
    add_fact_record,
    add_meeting_turn,
    add_report,
    add_review,
    add_review_targets,
    add_source,
    add_handoff,
    add_message,
    clear_project_messages,
    clear_employee_activities,
    create_task_control,
    create_or_get_clarification_request,
    create_or_get_approval,
    create_or_get_report_approval,
    create_team_meeting,
    create_team_task,
    finish_employee_result,
    finish_team_meeting,
    get_pending_clarification_request,
    get_project,
    get_team_meeting,
    get_task_for_source_message,
    get_task_control,
    get_team_task,
    initialize_database,
    list_employee_activities,
    list_employee_results,
    list_fact_records,
    list_handoffs,
    list_memories,
    list_meeting_turns,
    list_messages,
    list_project_records,
    list_projects,
    list_reports,
    list_report_approvals,
    list_reviews,
    list_review_targets,
    list_sources,
    list_team_tasks,
    start_employee_result,
    set_employee_activity,
    mark_review_targets_resubmitted,
    update_approval,
    update_report_approval,
    update_task_control_state,
    update_source_status,
    update_team_task_status,
    answer_clarification_request,
)


MODEL_NAME = "qwen3:8b"
MODEL_DISPLAY_NAME = "Qwen3 8B"
OFFICE_BACKGROUND_FILE = (
    Path(__file__).resolve().parent / "assets" / "youffice_pixel_office.png"
)
EMPLOYEE_SPRITE_DIR = Path(__file__).resolve().parent / "assets" / "sprites"
OFFICE_ROOM_DIR = Path(__file__).resolve().parent / "assets" / "rooms"
EMPLOYEE_ACTION_SPRITES = build_staff_app_specs()


st.set_page_config(
    page_title="YOUFFICE",
    page_icon="🏢",
    layout="wide",
)

if st.query_params.get("animation_lab") == "1":
    render_animation_lab()
    st.stop()

try:
    departments, employees = load_organization()
except (OSError, json.JSONDecodeError, ValueError) as error:
    st.error(f"직원 프로필을 불러오지 못했습니다: {error}")
    st.stop()

try:
    initialize_database()
    projects = list_projects()
except sqlite3.Error as error:
    st.error(f"프로젝트 데이터베이스를 준비하지 못했습니다: {error}")
    st.stop()

project_ids = [project["id"] for project in projects]
current_project_id = st.session_state.get("current_project_id")
if current_project_id not in project_ids:
    current_project_id = project_ids[0] if project_ids else None
    st.session_state.current_project_id = current_project_id

current_project = (
    get_project(current_project_id)
    if current_project_id is not None
    else None
)
current_sources = (
    list_sources(current_project_id)
    if current_project_id is not None
    else []
)
current_memories = (
    list_memories(current_project_id)
    if current_project_id is not None
    else []
)
current_records = (
    list_project_records(current_project_id)
    if current_project_id is not None
    else []
)
current_fact_records = (
    list_fact_records(current_project_id)
    if current_project_id is not None
    else []
)
current_reports = (
    list_reports(current_project_id)
    if current_project_id is not None
    else []
)
current_report_approvals = (
    list_report_approvals(current_project_id)
    if current_project_id is not None
    else []
)
report_approvals_by_report_id = {
    approval["report_id"]: approval for approval in current_report_approvals
}
for current_report in current_reports:
    if current_report["id"] not in report_approvals_by_report_id:
        report_approvals_by_report_id[current_report["id"]] = (
            create_or_get_report_approval(
                current_project_id,
                current_report["id"],
            )
        )
if st.session_state.get("loaded_project_id") != current_project_id:
    st.session_state.messages = (
        list_messages(current_project_id)
        if current_project_id is not None
        else []
    )
    st.session_state.loaded_project_id = current_project_id

manager_profile = next(
    employee for employee in employees
    if employee["id"] == ACTIVE_EMPLOYEE_ID
)
manager_department = department_name(
    manager_profile["department_id"], departments
)
employees_by_id = {employee["id"]: employee for employee in employees}
active_supporting_employees = [
    (
        employee,
        department_name(employee["department_id"], departments),
    )
    for employee in employees
    if employee["id"] != ACTIVE_EMPLOYEE_ID and employee["enabled"]
]
active_report_employees = [
    employee_data
    for employee_data in active_supporting_employees
    if employee_workstream(employee_data[0], employee_data[1]) == "report"
]
current_latest_task = None
pending_clarification = None
if current_project_id is not None:
    current_task_items = list_team_tasks(current_project_id, limit=1)
    current_latest_task = current_task_items[0] if current_task_items else None
    if current_latest_task is None or current_latest_task["status"] != "running":
        try:
            recover_stale_team_consultation_activities(current_project_id)
        except sqlite3.Error:
            # 의견 요청은 보조 흐름이므로, 오래된 상태 복구 실패가 화면 진입을 막지 않습니다.
            pass
    try:
        pending_clarification = ensure_failed_task_clarification(
            current_project_id,
            current_latest_task,
        )
    except sqlite3.Error:
        pending_clarification = get_pending_clarification_request(current_project_id)

apply_global_styles()

# 대화 기록 생성
if "messages" not in st.session_state:
    st.session_state.messages = []

requested_workspace_view = st.session_state.pop(
    "workspace_view_request",
    None,
)
if requested_workspace_view is not None:
    st.session_state.workspace_view = requested_workspace_view
elif "workspace_view" not in st.session_state:
    st.session_state.workspace_view = "🏢 오피스"

# 사이드바
with st.sidebar:
    st.markdown(
        f"""
        <div class="youffice-brand">
            <div class="youffice-logo">🏢</div>
            <div>
                <div class="youffice-brand-name">YOUFFICE</div>
                <div class="youffice-brand-subtitle">Youmin's Local AI Office</div>
            </div>
        </div>
        <div class="youffice-meta">
            <span class="youffice-chip">로컬 모드</span>
            <span class="youffice-chip">{MODEL_DISPLAY_NAME}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    project_title_column, new_project_column = st.columns(
        [0.78, 0.22],
        gap="small",
        vertical_alignment="center",
    )
    with project_title_column:
        st.markdown("**프로젝트 작업 공간**")
    with new_project_column:
        if st.button(
            "+",
            key="new_project_sidebar",
            type="tertiary",
            help="새 프로젝트 만들기",
            use_container_width=True,
        ):
            show_project_creator()

    if projects:
        project_selector_column, project_delete_column = st.columns(
            [0.82, 0.18],
            gap="small",
            vertical_alignment="center",
        )
        with project_selector_column:
            with st.container(key="project-selector-wrap"):
                selected_project_id = st.selectbox(
                    "현재 프로젝트",
                    options=project_ids,
                    index=project_ids.index(current_project_id),
                    format_func=lambda project_id: next(
                        project["name"]
                        for project in projects
                        if project["id"] == project_id
                    ),
                    label_visibility="collapsed",
                )
                selected_project_name = next(
                    project["name"]
                    for project in projects
                    if project["id"] == selected_project_id
                )
                st.markdown(
                    (
                        '<div class="project-name-hover-anchor">'
                        '<div class="project-name-hover-card">'
                        f'{html.escape(selected_project_name)}'
                        '</div></div>'
                    ),
                    unsafe_allow_html=True,
                )
        with project_delete_column:
            delete_project_clicked = st.button(
                "🗑",
                key=f"delete_project_{selected_project_id}",
                type="tertiary",
                help="선택한 프로젝트 삭제",
                use_container_width=True,
            )
        if selected_project_id != current_project_id:
            st.session_state.current_project_id = selected_project_id
            st.session_state.loaded_project_id = selected_project_id
            st.session_state.messages = list_messages(selected_project_id)
            st.rerun()
        if delete_project_clicked:
            selected_project = next(
                project
                for project in projects
                if project["id"] == selected_project_id
            )
            show_project_delete_confirmation(selected_project, projects)
    else:
        st.caption("아직 생성된 프로젝트가 없습니다.")

    if current_project is not None:
        st.caption("작업 화면")
        workspace_view = st.segmented_control(
            "화면 선택",
            options=["🏢 오피스", "💬 대화"],
            key="workspace_view",
            label_visibility="collapsed",
            width="stretch",
        )
        if current_latest_task is not None:
            latest_task_control = get_task_control(current_latest_task["id"])
            latest_control_state = (
                latest_task_control["state"] if latest_task_control is not None else "active"
            )
            if current_latest_task["status"] == "running":
                if latest_control_state == "cancel_requested":
                    st.warning("중단 요청을 받았습니다. 현재 AI 응답이 끝나면 멈춥니다.")
                elif st.button(
                    "⏹ 현재 작업 중단",
                    key=f"cancel_task_{current_latest_task['id']}",
                    type="secondary",
                    use_container_width=True,
                ):
                    if latest_task_control is None:
                        create_task_control(current_latest_task["id"])
                    update_task_control_state(
                        current_latest_task["id"],
                        "cancel_requested",
                    )
                    st.toast("작업 중단을 요청했습니다.")
                    st.rerun()
            elif latest_control_state == "waiting_for_user" or pending_clarification:
                st.warning("검수를 계속하려면 사용자 답변이 필요합니다.")
                if st.button(
                    "💬 보완 질문 답변하기",
                    key=f"open_clarification_{current_latest_task['id']}",
                    use_container_width=True,
                ):
                    st.session_state.workspace_view_request = "💬 대화"
                    st.session_state.scroll_to_clarification = True
                    st.rerun()

    st.link_button(
        "🎞️ 애니메이션 실험실",
        "/?animation_lab=1",
        use_container_width=True,
    )

    st.divider()

    organization_title_column, department_menu_column = st.columns(
        [0.82, 0.18],
        gap="small",
        vertical_alignment="center",
    )
    with organization_title_column:
        st.markdown('<div class="org-title">회사 조직도</div>', unsafe_allow_html=True)
    with department_menu_column:
        if st.button(
            "⚙",
            key="department_settings",
            type="tertiary",
            help="부서 이름 설정",
            use_container_width=True,
        ):
            show_organization_editor(departments, employees)

    for department in departments:
        department_employees = [
            employee for employee in employees
            if employee["department_id"] == department["id"]
        ]
        st.markdown(
            f'<div class="org-group-title">'
            f'{html.escape(department["name"].upper())}</div>',
            unsafe_allow_html=True,
        )
        if not department_employees:
            st.caption("소속 직원 없음")
        for employee in department_employees:
            employee_column, menu_column = st.columns(
                [0.86, 0.14],
                gap="small",
                vertical_alignment="center",
            )
            is_current_employee = employee["id"] == ACTIVE_EMPLOYEE_ID
            with employee_column:
                st.markdown(
                    employee_card_html(employee, is_current_employee),
                    unsafe_allow_html=True,
                )
            with menu_column:
                if st.button(
                    "⋮",
                    key=f"profile_menu_{employee['id']}",
                    type="tertiary",
                    help=f"{employee['name']} 프로필 설정",
                    use_container_width=True,
                ):
                    show_profile_editor(employee, employees, departments)

    st.markdown(
        """
        <div class="org-note">
            ⚙ 버튼에서 부서 이름을, ⋮ 버튼에서 직원 프로필을 변경합니다.<br>
            초록색은 활성 직원입니다. 오피스에서 캐릭터를 누르면 해당 직원과 직접 대화할 수 있습니다.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if current_project_id is not None:
        if st.button("현재 프로젝트 대화 초기화", use_container_width=True):
            try:
                clear_project_messages(current_project_id)
            except sqlite3.Error as error:
                st.error(f"대화를 초기화하지 못했습니다: {error}")
            else:
                st.session_state.messages = []
                st.rerun()

if current_project is None:
    st.info(
        "만들고 싶은 것을 한 문장으로 적어 첫 프로젝트를 시작해 보세요. "
        "정확한 설계는 AI 팀과 대화하면서 하나씩 정하면 됩니다."
    )
    if st.button(
        "새 프로젝트 만들기",
        key="new_project_main",
        type="primary",
    ):
        show_project_creator()
    st.stop()

requested_chat_employee_id = st.session_state.pop(
    "chat_employee_request",
    None,
)
if requested_chat_employee_id in employees_by_id:
    st.session_state.chat_employee_id = requested_chat_employee_id
chat_employee_id = st.session_state.get(
    "chat_employee_id",
    ACTIVE_EMPLOYEE_ID,
)
if chat_employee_id not in employees_by_id:
    chat_employee_id = ACTIVE_EMPLOYEE_ID
    st.session_state.chat_employee_id = chat_employee_id
chat_profile = employees_by_id[chat_employee_id]
chat_department = department_name(chat_profile["department_id"], departments)

if workspace_view == "🏢 오피스":
    render_live_pixel_office(
        current_project,
        departments,
        employees,
    )
    office_states, office_latest_task = office_employee_states(
        current_project["id"],
        employees,
    )
    office_handoffs = (
        list_handoffs(office_latest_task["id"])
        if office_latest_task is not None
        else []
    )
    office_handoffs_by_id = {
        str(handoff["id"]): handoff for handoff in office_handoffs
    }
    requested_employee_id = st.query_params.get("employee")
    if requested_employee_id in employees_by_id:
        st.session_state.office_selected_employee_id = requested_employee_id
        st.session_state.office_dialog_action = "greeting"
        st.session_state.pop("office_meeting_room_open", None)
        st.session_state.pop("office_selected_handoff_id", None)
        del st.query_params["employee"]

    requested_meeting_room = st.query_params.get("meeting_room")
    if requested_meeting_room == "1":
        st.session_state.office_meeting_room_open = True
        st.session_state.pop("office_selected_employee_id", None)
        st.session_state.pop("office_selected_handoff_id", None)
        del st.query_params["meeting_room"]

    requested_handoff_id = st.query_params.get("handoff_id")
    if requested_handoff_id in office_handoffs_by_id:
        st.session_state.office_selected_handoff_id = requested_handoff_id
        st.session_state.pop("office_selected_employee_id", None)
        st.session_state.pop("office_meeting_room_open", None)
        del st.query_params["handoff_id"]

    selected_handoff_id = st.session_state.get("office_selected_handoff_id")
    if selected_handoff_id in office_handoffs_by_id:
        show_office_handoff_dialog(
            office_handoffs_by_id[selected_handoff_id],
            employees,
            current_project,
        )

    if st.session_state.get("office_meeting_room_open"):
        show_office_meeting_dialog(
            current_project,
            employees,
            office_latest_task,
        )

    selected_employee_id = st.session_state.get("office_selected_employee_id")
    if selected_employee_id in employees_by_id:
        selected_employee = employees_by_id[selected_employee_id]
        show_office_employee_dialog(
            selected_employee,
            department_name(selected_employee["department_id"], departments),
            office_states.get(selected_employee_id, ("waiting", "대기 중")),
            current_project,
            office_latest_task,
        )
    st.caption(
        "작업실에서는 직원 상태를, 자료 확인 버튼에서는 실제 전달 내용을, 회의실에서는 저장된 팀 회의 발언을 볼 수 있습니다."
    )
    st.stop()

st.session_state.messages = list_messages(current_project_id)

st.markdown(
    f"""
    <div class="direct-chat-banner">
        <div class="direct-chat-avatar">{profile_avatar_content(chat_profile)}</div>
        <div>
            <div class="direct-chat-label">현재 대화 중</div>
            <div class="direct-chat-name">{html.escape(chat_profile['name'])}</div>
            <div class="direct-chat-role">{html.escape(chat_department)} · {html.escape(chat_profile['title'])}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_project_summary(current_project)

guided_user_input = render_project_onboarding(
    current_project,
    st.session_state.messages,
    current_latest_task,
    is_manager_chat=chat_employee_id == ACTIVE_EMPLOYEE_ID,
    plan_request_pending=(
        st.session_state.get(MANAGER_PLAN_REQUEST_STATE) == current_project_id
    ),
)

render_project_research_tools(
    current_project,
    st.session_state.messages,
    current_sources,
    current_memories,
    current_records,
    current_fact_records,
    add_source=add_source,
    update_source_status=update_source_status,
    add_fact_record=add_fact_record,
)

report_employee_data = (
    active_report_employees[0]
    if active_report_employees
    else (manager_profile, manager_department)
)
has_completed_team_work = (
    current_latest_task is not None
    and current_latest_task.get("status") == "completed"
)
report_action_column, report_caption_column = st.columns(
    [0.3, 0.7],
    vertical_alignment="center",
)
with report_action_column:
    if st.button(
        "팀 작업 결과 안내 생성",
        key=f"generate_report_{current_project_id}",
        disabled=not has_completed_team_work,
        help=(
            "팀 작업이 끝난 뒤에만 결과 안내를 만들 수 있어요. 아이디어를 구체화하는 단계라면 유키와 먼저 다음 설계 결정을 정해보세요."
            if not has_completed_team_work
            else "팀이 작성한 문서와 검토 기록을 바탕으로, 다음 설계 결정을 안내합니다. 실제 제품 완성 보고서는 아닙니다."
        ),
        use_container_width=True,
    ):
        generate_project_report(
            current_project,
            report_employee_data[0],
            report_employee_data[1],
            active_supporting_employees,
        )
with report_caption_column:
    st.caption(
        f"결과 안내 담당: {report_employee_data[0]['name']} · "
        f"저장된 결과 안내 {len(current_reports)}건"
    )

if current_reports:
    with st.expander(f"📄 생성된 보고서 · {len(current_reports)}건"):
        for report in current_reports:
            report_approval = report_approvals_by_report_id[report["id"]]
            with st.container(border=True):
                st.markdown(f"**{report['title']}**")
                st.caption(f"생성일: {report['created_at']}")
                if report_approval["status"] == "approved":
                    st.success(
                        f"사용자 승인 완료 · {report_approval['decided_at'] or report_approval['updated_at']}"
                    )
                elif report_approval["status"] == "revision_requested":
                    st.warning("수정 요청 완료 · 새 수정 보고서가 생성되었습니다.")
                    if report_approval.get("user_feedback"):
                        st.caption(f"수정 의견: {report_approval['user_feedback']}")
                    if report_approval.get("replacement_report_id"):
                        st.caption(
                            f"대체 보고서: #{report_approval['replacement_report_id']}"
                        )
                else:
                    st.info("사용자 승인 대기 중")
                st.markdown(report["content"])
                safe_project_name = re.sub(
                    r'[\\/:*?"<>|]+',
                    "_",
                    current_project["name"],
                )
                if report_approval["status"] == "pending":
                    approval_column, revision_column = st.columns(2)
                    with approval_column:
                        if st.button(
                            "이 보고서 승인",
                            key=f"approve_report_{report['id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            update_report_approval(
                                report_approval["id"],
                                "approved",
                            )
                            st.session_state.pop("report_revision_id", None)
                            st.rerun()
                    with revision_column:
                        if st.button(
                            "수정 요청",
                            key=f"revise_report_{report['id']}",
                            use_container_width=True,
                        ):
                            st.session_state.report_revision_id = report["id"]
                st.download_button(
                    (
                        "승인된 Markdown 보고서 다운로드"
                        if report_approval["status"] == "approved"
                        else "Markdown 초안 다운로드"
                    ),
                    data=report["content"].encode("utf-8-sig"),
                    file_name=f"{safe_project_name}_report_{report['id']}.md",
                    mime="text/markdown",
                    key=f"download_report_{report['id']}",
                    use_container_width=True,
                )

selected_revision_report_id = st.session_state.get("report_revision_id")
selected_revision_report = next(
    (
        report
        for report in current_reports
        if report["id"] == selected_revision_report_id
    ),
    None,
)
if selected_revision_report is not None:
    selected_revision_approval = report_approvals_by_report_id[
        selected_revision_report["id"]
    ]
    if selected_revision_approval["status"] == "pending":
        show_report_revision_dialog(
            current_project,
            selected_revision_report,
            selected_revision_approval,
            report_employee_data[0],
            report_employee_data[1],
            active_supporting_employees,
        )
    else:
        clear_report_revision_dialog()



recent_team_tasks = list_team_tasks(current_project_id)
if recent_team_tasks:
    with st.expander(f"🤝 팀 업무 전달 기록 · {len(recent_team_tasks)}건"):
        status_labels = {
            "pending": "대기",
            "running": "작업 중",
            "completed": "완료",
            "failed": "실패",
        }
        for task in recent_team_tasks:
            task_control = get_task_control(task["id"])
            task_control_state = (
                task_control["state"] if task_control is not None else "active"
            )
            task_status_label = status_labels.get(task["status"], task["status"])
            if task_control_state == "waiting_for_user":
                task_status_label = "사용자 답변 대기"
            elif task_control_state == "cancel_requested":
                task_status_label = "중단 처리 중"
            elif task_control_state == "cancelled":
                task_status_label = "사용자 중단"
            with st.container(border=True):
                st.markdown(
                    f"**업무 #{task['id']} · "
                    f"{task_status_label}**"
                )
                st.caption(task["request"])

                task_meeting = get_team_meeting(task["id"])
                if task_meeting is not None:
                    meeting_status_labels = {
                        "running": "회의 중",
                        "completed": "합의 완료",
                        "partial": "일부 의견 미제출",
                        "failed": "결론 확인 필요",
                    }
                    meeting_turns = list_meeting_turns(task_meeting["id"])
                    meeting_label = (
                        "🗣️ 실제 팀 회의 · "
                        f"{meeting_status_labels.get(task_meeting['status'], task_meeting['status'])} · "
                        f"발언 {len(meeting_turns)}건"
                    )
                    if task_record_action_button(
                        meeting_label,
                        "회의 내용",
                        f"meeting_detail_{task['id']}",
                    ):
                        show_team_record_detail(
                            f"업무 #{task['id']} · 실제 팀 회의",
                            meeting_turns=meeting_turns,
                            employees=employees,
                        )

                for result in list_employee_results(task["id"]):
                    result_employee = employees_by_id.get(result["employee_id"])
                    result_name = (
                        result_employee["name"]
                        if result_employee is not None
                        else result["employee_id"]
                    )
                    result_status = status_labels.get(
                        result["status"], result["status"]
                    )
                    result_label = f"{result_name} · {result_status}"
                    if task_record_action_button(
                        result_label,
                        "결과 보기",
                        f"result_detail_{task['id']}_{result['id']}",
                    ):
                        show_team_record_detail(
                            f"업무 #{task['id']} · {result_name} 결과",
                            content=result.get("output") or "",
                            error=result.get("error") or "",
                        )

                task_review_targets = list_review_targets(task["id"])
                review_target_status_labels = {
                    "rework_requested": "재작업 요청됨",
                    "resubmitted": "수정본 제출됨",
                    "passed": "2차 통과",
                    "unresolved": "미통과",
                }
                for review in list_reviews(task["id"]):
                    reviewer = employees_by_id.get(review["reviewer_employee_id"])
                    reviewer_name = (
                        reviewer["name"]
                        if reviewer is not None
                        else review["reviewer_employee_id"]
                    )
                    verdict_labels = {
                        "passed": "통과",
                        "rework_requested": "재작업 요청",
                        "failed": "검수 실패",
                    }
                    linked_targets = [
                        target
                        for target in task_review_targets
                        if target["review_id"] == review["id"]
                    ]
                    linked_target_labels = []
                    for target in linked_targets:
                        target_employee = employees_by_id.get(
                            target["target_employee_id"]
                        )
                        target_name = (
                            target_employee["name"]
                            if target_employee is not None
                            else target["target_employee_id"]
                        )
                        target_state = review_target_status_labels.get(
                            target["status"],
                            target["status"],
                        )
                        linked_target_labels.append(f"{target_name}({target_state})")
                    target_summary = ", ".join(linked_target_labels)
                    review_label = (
                        f"검수 {review['review_round']}차 · {reviewer_name} · "
                        f"{verdict_labels.get(review['verdict'], review['verdict'])}"
                        + (f" · 대상: {target_summary}" if target_summary else "")
                    )
                    if task_record_action_button(
                        review_label,
                        "검수 내용",
                        f"review_detail_{task['id']}_{review['id']}",
                    ):
                        show_team_record_detail(
                            f"업무 #{task['id']} · {reviewer_name} {review['review_round']}차 검수",
                            content=(
                                review["feedback"]
                                or "저장된 검수 의견이 없습니다."
                            ),
                        )
                st.markdown(
                    '<div class="task-record-bottom-space"></div>',
                    unsafe_allow_html=True,
                )

# 이전 대화 표시
for message_index, message in enumerate(st.session_state.messages):
    content = message["content"]
    display_message = message
    if message["role"] == "assistant":
        content = remove_thinking(content) or EMPTY_ANSWER_MESSAGE
        if not is_korean_answer(content):
            content = (
                "이 응답은 영어 중심으로 생성되어 화면에 표시하지 않았습니다. "
                "팀장의 최종 답변이라면 아래의 다시 생성 버튼을 이용해주세요."
            )
        display_message = {**message, "content": content}

    message_employee = employees_by_id.get(
        message.get("employee_id", ACTIVE_EMPLOYEE_ID),
        manager_profile,
    )
    render_chat_message(display_message, message_index, message_employee)
    if (
        message["role"] == "assistant"
        and is_structured_final_report(message["content"])
    ):
        message_key = structured_report_revision_key(message, message_index)
        if st.button(
            "최종 보고서 수정",
            key=f"structured_report_revision_{message_key}",
        ):
            st.session_state.structured_report_revision_message_key = message_key

selected_structured_report_revision_key = st.session_state.get(
    "structured_report_revision_message_key"
)
selected_structured_report_revision = next(
    (
        (message_index, message)
        for message_index, message in enumerate(st.session_state.messages)
        if structured_report_revision_key(message, message_index)
        == selected_structured_report_revision_key
    ),
    None,
)
if selected_structured_report_revision is not None:
    selected_message_index, selected_message = selected_structured_report_revision
    selected_report_employee = employees_by_id.get(
        selected_message.get("employee_id", ACTIVE_EMPLOYEE_ID),
        manager_profile,
    )
    show_structured_final_report_revision(
        current_project,
        selected_message,
        selected_message_index,
        selected_report_employee,
    )
elif selected_structured_report_revision_key is not None:
    clear_structured_report_revision_dialog()

if pending_clarification is not None:
    clarification_anchor_id = (
        f"clarification-answer-anchor-{pending_clarification['id']}"
    )
    st.markdown(
        f'<div id="{clarification_anchor_id}"></div>',
        unsafe_allow_html=True,
    )
    st.warning(
        "2차 검수에서 사용자가 정해야 하거나 알려줘야 하는 정보가 남았습니다. "
        "아는 내용을 입력하고, 정하지 않은 항목은 '기본 가정으로 진행'이라고 답해도 됩니다."
    )
    readable_questions = employee_names_in_text(
        pending_clarification["questions"],
        employees,
    )
    with st.container(border=True):
        st.markdown("#### 업무를 계속하기 위한 보완 질문")
        st.markdown(readable_questions)
        with st.form(
            key=f"clarification_answer_{pending_clarification['id']}",
            clear_on_submit=False,
        ):
            clarification_answer = st.text_area(
                "답변",
                placeholder=(
                    "예: 대회 제한은 아직 정해지지 않았습니다. 모터는 보유하지 않았으며 "
                    "예산 안에서 추천해주세요. 나머지는 기본 가정으로 계획을 진행해주세요."
                ),
                height=150,
            )
            continue_workflow = st.form_submit_button(
                "답변 저장 후 업무 이어서 진행",
                type="primary",
                use_container_width=True,
            )
        if continue_workflow:
            try:
                resumed, resume_message = resume_workflow_from_clarification(
                    pending_clarification,
                    clarification_answer,
                    current_project,
                    manager_profile,
                    manager_department,
                    active_supporting_employees,
                )
            except sqlite3.Error as error:
                st.error(f"보완 답변을 저장하지 못했습니다: {error}")
            else:
                if resumed:
                    st.session_state.workspace_view_request = "🏢 오피스"
                    st.toast(resume_message)
                    st.rerun()
                else:
                    st.warning(resume_message)
    if st.session_state.pop("scroll_to_clarification", False):
        st.html(
            f"""
            <script>
            setTimeout(() => {{
                const target = document.getElementById(
                    {json.dumps(clarification_anchor_id)}
                );
                if (target) {{
                    target.scrollIntoView({{behavior: "smooth", block: "center"}});
                }}
            }}, 250);
            </script>
            """,
            unsafe_allow_javascript=True,
        )

# 사용자 입력
quick_team_plan_input = None
external_review_requested = False
team_consultation_running = (
    chat_employee_id == ACTIVE_EMPLOYEE_ID
    and is_team_consultation_running(current_project_id)
)
if (
    chat_employee_id == ACTIVE_EMPLOYEE_ID
    and current_latest_task is None
    and st.session_state.get(MANAGER_PLAN_REQUEST_STATE) != current_project_id
):
    consultation_column, quick_plan_column, quick_plan_hint_column = st.columns(
        [0.3, 0.3, 0.4],
        vertical_alignment="center",
    )
    with consultation_column:
        if st.button(
            "👥 팀 의견 받기",
            key=f"team_consultation_{current_project_id}",
            use_container_width=True,
            disabled=team_consultation_running,
        ):
            recent_consultation_context = "\n".join(
                f"{'사용자' if message['role'] == 'user' else message.get('employee_name', '유키')}: "
                f"{str(message.get('content') or '').strip()}"
                for message in select_recent_model_messages(
                    st.session_state.messages,
                    ACTIVE_EMPLOYEE_ID,
                    max_messages=6,
                    max_characters=4_000,
                )
            )
            recent_user_message = next(
                (
                    str(message.get("content") or "").strip()
                    for message in reversed(st.session_state.messages)
                    if message.get("role") == "user"
                ),
                "",
            )
            consultation_request = (
                "현재 대화를 바탕으로, 이미 정한 내용을 반복하지 말고 학생이 다음에 정해야 할 한 가지에 도움이 될 "
                "새 쟁점·위험·대안을 팀원 두 명이 각자의 역할에서 검토하고 유키가 쉬운 말로 정리해줘."
                + (
                    f"\n최근 사용자의 말: {recent_user_message}"
                    if recent_user_message
                    else ""
                )
                + (
                    f"\n\n최근 대화와 현재 결정:\n{recent_consultation_context}"
                    if recent_consultation_context
                    else ""
                )
            )
            consultation_started, consultation_message = (
                start_team_consultation_background(
                    current_project_id,
                    current_project,
                    consultation_request,
                    manager_profile,
                    manager_department,
                    active_supporting_employees,
                )
            )
            if consultation_started:
                consultation_message_id = add_message(
                    current_project_id,
                    "user",
                    "팀원 두 명의 의견을 받아 쉽게 정리해줘.",
                )
                st.session_state.messages.append(
                    {
                        "message_id": consultation_message_id,
                        "role": "user",
                        "content": "팀원 두 명의 의견을 받아 쉽게 정리해줘.",
                    }
                )
                st.session_state.workspace_view_request = "🏢 오피스"
                st.toast(consultation_message)
                st.rerun()
            else:
                st.warning(consultation_message)
    with quick_plan_column:
        if st.button(
            "🤝 지금 내용으로 팀에 맡기기",
            type="primary",
            key=f"quick_team_plan_{current_project_id}",
            use_container_width=True,
        ):
            st.session_state[MANAGER_PLAN_REQUEST_STATE] = current_project_id
            quick_team_plan_input = build_team_plan_request_prompt(
                current_project
            )
    with quick_plan_hint_column:
        external_status = external_review_status()
        external_review_requested = st.button(
            "✨ 외부 AI 교차 검토",
            key=f"external_review_{current_project_id}",
            use_container_width=True,
            disabled=not bool(external_status["ready"]),
            help=str(external_status["message"]),
        )
        st.caption(
            "의견 받기: 실행 전 두 팀원의 관점으로 확인해요. · 팀에 맡기기: 계획을 승인한 뒤 실제 작업을 시작해요."
            if not team_consultation_running
            else "팀원들이 의견을 검토 중이에요. 오피스에서 상태를 확인한 뒤 대화로 돌아오세요."
        )
        if not external_status["ready"]:
            st.caption("외부 교차 검토는 아직 설정 전입니다. `EXTERNAL_AI_SETUP.md`를 확인하세요.")

if external_review_requested:
    try:
        with st.spinner("Gemini가 조건을 정리하고 Claude가 독립 검토하고 있어요..."):
            external_review_answer = run_external_cross_review(
                current_project,
                st.session_state.messages,
            )
        external_request_id = add_message(
            current_project_id,
            "user",
            "외부 AI 두 명의 관점으로 현재 프로젝트를 교차 검토해줘.",
        )
        external_answer_id = add_message(
            current_project_id,
            "assistant",
            external_review_answer,
            ACTIVE_EMPLOYEE_ID,
        )
    except ExternalReviewError as error:
        st.warning(f"외부 AI 교차 검토를 완료하지 못했습니다: {error}")
    except sqlite3.Error as error:
        st.error(f"외부 AI 검토 결과를 저장하지 못했습니다: {error}")
    else:
        st.session_state.messages.extend(
            [
                {
                    "message_id": external_request_id,
                    "role": "user",
                    "content": "외부 AI 두 명의 관점으로 현재 프로젝트를 교차 검토해줘.",
                },
                {
                    "message_id": external_answer_id,
                    "role": "assistant",
                    "content": external_review_answer,
                    "employee_id": ACTIVE_EMPLOYEE_ID,
                },
            ]
        )
        st.rerun()

retry_saved_plan_input = None
latest_saved_message = (
    st.session_state.messages[-1] if st.session_state.messages else None
)
saved_plan_request = build_team_plan_request_prompt(current_project)
if (
    chat_employee_id == ACTIVE_EMPLOYEE_ID
    and current_latest_task is None
    and latest_saved_message is not None
    and latest_saved_message.get("role") == "user"
    and str(latest_saved_message.get("content") or "").strip()
    == saved_plan_request
):
    st.warning("마지막 팀 계획 요청은 답변을 받기 전에 멈췄어요.")
    if st.button(
        "마지막 계획 요청 다시 이어서 답변 받기",
        key=f"retry_saved_team_plan_{current_project_id}",
        use_container_width=True,
    ):
        st.session_state[MANAGER_PLAN_REQUEST_STATE] = current_project_id
        retry_saved_plan_input = saved_plan_request

typed_user_input = st.chat_input(f"{chat_profile['name']}에게 업무를 입력하세요.")
if typed_user_input and not guided_user_input and not quick_team_plan_input:
    # 계획 버튼을 누른 뒤 사용자가 별도 문장을 직접 입력했다면 자연 대화로 처리합니다.
    st.session_state.pop(MANAGER_PLAN_REQUEST_STATE, None)
user_input = (
    guided_user_input
    or quick_team_plan_input
    or retry_saved_plan_input
    or typed_user_input
)
reusing_saved_plan_request = retry_saved_plan_input is not None

if user_input:
    if not reusing_saved_plan_request:
        try:
            user_message_id = add_message(
                current_project_id,
                "user",
                user_input,
            )
        except sqlite3.Error as error:
            st.error(f"사용자 메시지를 저장하지 못했습니다: {error}")
            st.stop()

        st.session_state.messages.append(
            {
                "message_id": user_message_id,
                "role": "user",
                "content": user_input,
            }
        )
        render_chat_message(
            st.session_state.messages[-1],
            len(st.session_state.messages) - 1,
            chat_profile,
        )

    try:
        manager_plan_in_progress = (
            chat_employee_id == ACTIVE_EMPLOYEE_ID
            and st.session_state.get(MANAGER_PLAN_REQUEST_STATE)
            == current_project_id
        )
        chat_progress = start_chat_progress(
            chat_profile["name"],
            is_plan_request=manager_plan_in_progress,
        )
        spinner_text = (
            "유키가 팀 계획 초안을 만들고 형식을 확인하고 있어요..."
            if chat_employee_id == ACTIVE_EMPLOYEE_ID
            and st.session_state.get(MANAGER_PLAN_REQUEST_STATE)
            == current_project_id
            else f"{chat_profile['name']} 직원이 업무를 확인하고 있습니다..."
        )
        with st.spinner(spinner_text):

            # 모델에는 화면 표시용 추가 정보 없이 role과 content만 전달합니다.
            conversation_messages = select_recent_model_messages(
                st.session_state.messages[:-1],
                chat_employee_id,
            )
            model_memories = current_memories[:8]
            model_records = current_records[:8]
            model_fact_records = current_fact_records[:12]
            chat_progress.context_ready()
            manager_plan_requested = (
                chat_employee_id == ACTIVE_EMPLOYEE_ID
                and st.session_state.get(MANAGER_PLAN_REQUEST_STATE)
                == current_project_id
            )
            manager_delegation_instruction = (
                build_manager_delegation_instruction(
                    active_supporting_employees
                )
                if manager_plan_requested
                else ""
            )
            manager_collaboration_instruction = (
                build_manager_collaboration_instruction()
                + build_dialogue_state_instruction(
                    st.session_state.messages,
                    has_running_task=(
                        current_latest_task is not None
                        and current_latest_task["status"] == "running"
                    ),
                    plan_request_pending=manager_plan_requested,
                )
                if chat_employee_id == ACTIVE_EMPLOYEE_ID
                and not manager_plan_requested
                else ""
            )
            model_messages = [
                {
                    "role": "system",
                    "content": (
                        build_project_context(current_project)
                        + build_source_context(current_sources)
                        + build_memory_context(
                            model_memories,
                            model_records,
                            model_fact_records,
                        )
                        + build_employee_system_prompt(
                            chat_profile,
                            chat_department,
                            (
                                active_supporting_employees
                                if chat_employee_id == ACTIVE_EMPLOYEE_ID
                                else None
                            ),
                        )
                        + "현재 사용자는 너와 직접 대화하고 있다. "
                        + manager_collaboration_instruction
                        + manager_delegation_instruction
                    ),
                },
                *conversation_messages,
                {
                    "role": "user",
                    "content": f"{user_input}\n\n/no_think",
                },
            ]

            chat_progress.generating()
            response = optimized_chat(
                model=MODEL_NAME,
                messages=model_messages,
                think=False,
                stream=False,
                answer_prefix=(
                    "[업무 접수]\n"
                    if manager_plan_requested
                    else (
                        "[담당 결과]\n"
                        if chat_employee_id != ACTIVE_EMPLOYEE_ID
                        else ""
                    )
                ),
            )

            # 혹시 사고 과정이 섞여도 화면에서 제거합니다.
            answer_task_context = (
                build_project_context(current_project)
                + build_source_context(current_sources)
                + build_memory_context(
                    model_memories,
                    model_records,
                    model_fact_records,
                )
                + f"사용자 요청:\n{user_input}"
            )
            chat_progress.checking_format()
            answer = final_answer_with_retry(
                response.message.content,
                answer_task_context,
                output_instruction=(
                    manager_delegation_instruction
                    or manager_collaboration_instruction
                ),
                required_markers=(
                    MANAGER_PLAN_MARKERS
                    if manager_delegation_instruction
                    else ()
                ),
                max_regenerations=1 if manager_plan_requested else 2,
                on_regeneration=chat_progress.regenerating,
            )
            if answer == EMPTY_ANSWER_MESSAGE:
                raise OllamaResponseFormatError(
                    "유키 또는 직원 응답의 형식을 확인하지 못했습니다."
                )
            previous_manager_answer = next(
                (
                    message.get("content")
                    for message in reversed(st.session_state.messages[:-1])
                    if message.get("role") == "assistant"
                    and message.get("employee_id") == ACTIVE_EMPLOYEE_ID
                ),
                None,
            )
            if (
                manager_collaboration_instruction
                and previous_manager_answer is not None
                and is_substantially_repeated_reply(
                    answer,
                    previous_manager_answer,
                )
            ):
                chat_progress.retrying_repetition()
                repeat_retry_response = optimized_chat(
                    model=MODEL_NAME,
                    messages=[
                        *model_messages,
                        {"role": "assistant", "content": answer},
                        {
                            "role": "user",
                            "content": (
                                "방금 후보 답변은 직전 유키 답변을 반복했습니다. "
                                "같은 인사나 도움 제안을 다시 쓰지 말고, 사용자의 "
                                "마지막 말에 맞춰 바로 이어지는 구체적인 다음 행동 "
                                "또는 꼭 필요한 질문 하나만 새로 답하세요.\n/no_think"
                            ),
                        },
                    ],
                    think=False,
                    stream=False,
                    answer_prefix="",
                )
                answer = final_answer_with_retry(
                    repeat_retry_response.message.content,
                    answer_task_context,
                    output_instruction=(
                        manager_collaboration_instruction
                        + "직전 답변과 같은 문장이나 도움 제안을 반복하지 않는다."
                    ),
                )
                if answer == EMPTY_ANSWER_MESSAGE:
                    raise OllamaResponseFormatError(
                        "반복되지 않는 유키 답변을 만들지 못했습니다."
                    )
            if manager_delegation_instruction:
                answer = normalize_manager_plan_project_name(
                    answer,
                    current_project["name"],
                )

        chat_progress.complete()
        try:
            assistant_message_id = add_message(
                current_project_id,
                "assistant",
                answer,
                chat_employee_id,
            )
        except sqlite3.Error as error:
            st.error(f"AI 답변을 저장하지 못했습니다: {error}")
        else:
            assistant_message = {
                "message_id": assistant_message_id,
                "role": "assistant",
                "content": answer,
                "employee_id": chat_employee_id,
                "employee_name": chat_profile["name"],
            }
            st.session_state.messages.append(assistant_message)
            if manager_plan_requested and is_manager_plan_content(answer):
                st.session_state.pop(MANAGER_PLAN_REQUEST_STATE, None)
                st.session_state.onboarding_focus_plan_approval = current_project_id
            render_chat_message(
                assistant_message,
                len(st.session_state.messages) - 1,
                chat_profile,
            )

    except Exception as error:
        chat_progress.fail()
        failure = describe_ollama_failure(error)
        st.error(
            failure.message
            if failure is not None
            else (
                "AI 답변을 생성하지 못했습니다. "
                f"상세 오류: {error}"
            )
        )

if (
    chat_employee_id == ACTIVE_EMPLOYEE_ID
    and active_supporting_employees
    and st.session_state.messages
):
    latest_user_index = next(
        (
            index
            for index in range(len(st.session_state.messages) - 1, -1, -1)
            if st.session_state.messages[index]["role"] == "user"
        ),
        None,
    )
    if latest_user_index is not None:
        latest_user_message = st.session_state.messages[latest_user_index]
        latest_manager_message = next(
            (
                message
                for message in st.session_state.messages[latest_user_index + 1:]
                if message["role"] == "assistant"
                and message.get("employee_id") == ACTIVE_EMPLOYEE_ID
                and is_manager_plan_content(message.get("content"))
            ),
            None,
        )
        source_message_id = latest_user_message.get("message_id")
        if source_message_id is not None and latest_manager_message is not None:
            try:
                approval = create_or_get_approval(
                    current_project_id,
                    source_message_id,
                    latest_manager_message["content"],
                )
                existing_team_task = get_task_for_source_message(
                    current_project_id,
                    source_message_id,
                )
            except sqlite3.Error as error:
                st.error(f"계획 승인 상태를 불러오지 못했습니다: {error}")
            else:
                render_plan_approval_anchor(current_project_id)
                st.divider()
                active_employee_names = ", ".join(
                    employee["name"]
                    for employee, _ in active_supporting_employees
                )
                st.caption(f"활성 지원 직원: {active_employee_names}")

                if existing_team_task is None:
                    if approval["status"] == "revision_requested":
                        st.warning(
                            "이전 계획 수정이 완료되지 않았습니다. 수정 요청을 다시 열어주세요."
                        )
                    else:
                        st.info(
                            "팀장의 계획을 확인해주세요. 승인해야 실제 직원별 AI 호출과 "
                            "업무 전달이 시작됩니다."
                        )
                    approval_column, revision_column = st.columns(2)
                    with approval_column:
                        if st.button(
                            "계획 승인 및 업무 시작",
                            type="primary",
                            use_container_width=True,
                            key=f"approve_message_{source_message_id}",
                        ):
                            try:
                                update_approval(approval["id"], "approved")
                            except sqlite3.Error as error:
                                st.error(f"계획 승인을 저장하지 못했습니다: {error}")
                            else:
                                approved_manager_message = {
                                    **latest_manager_message,
                                    "content": approval["plan_content"],
                                    "employee_name": manager_profile["name"],
                                }
                                workflow_started, workflow_message = (
                                    start_team_workflow_background(
                                        current_project_id,
                                        current_project,
                                        latest_user_message,
                                        approved_manager_message,
                                        manager_profile,
                                        manager_department,
                                        active_supporting_employees,
                                        st.session_state.messages,
                                    )
                                )
                                if workflow_started:
                                    st.session_state.workspace_view_request = "🏢 오피스"
                                    st.toast(workflow_message)
                                    st.rerun()
                                else:
                                    st.warning(workflow_message)
                    with revision_column:
                        if st.button(
                            "계획 수정 요청",
                            use_container_width=True,
                            key=f"revise_message_{source_message_id}",
                        ):
                            show_plan_revision(
                                approval,
                                current_project,
                                current_sources,
                                latest_user_message,
                                manager_profile,
                                manager_department,
                                active_supporting_employees,
                            )
                else:
                    task_status_labels = {
                        "pending": "대기",
                        "running": "작업 중",
                        "completed": "완료",
                        "failed": "일부 실패",
                    }
                    existing_task_control = get_task_control(existing_team_task["id"])
                    existing_task_control_state = (
                        existing_task_control["state"]
                        if existing_task_control is not None
                        else "active"
                    )
                    existing_task_label = task_status_labels.get(
                        existing_team_task["status"],
                        existing_team_task["status"],
                    )
                    if existing_task_control_state == "waiting_for_user":
                        existing_task_label = "사용자 답변 대기"
                    elif existing_task_control_state == "cancel_requested":
                        existing_task_label = "중단 처리 중"
                    elif existing_task_control_state == "cancelled":
                        existing_task_label = "사용자 중단"
                    st.caption(
                        "최근 요청의 팀 협업 상태: "
                        f"{existing_task_label}"
                    )
                    final_response_employee = report_employee_data[0]
                    final_responses = [
                        message
                        for message in st.session_state.messages[latest_user_index + 1:]
                        if message["role"] == "assistant"
                        and message.get("employee_id") == final_response_employee["id"]
                    ]
                    if (
                        existing_team_task["status"] in ("completed", "failed")
                        and (
                            not final_responses
                            or (
                            final_responses[-1]["content"] == EMPTY_ANSWER_MESSAGE
                            or not is_korean_answer(final_responses[-1]["content"])
                            )
                        )
                    ):
                        st.warning(
                            f"{final_response_employee['name']}의 마지막 종합 답변이 비어 있거나 "
                            "영어로 생성됐습니다. "
                            "직원 업무를 다시 실행하지 않고 저장된 결과만 재종합할 수 있습니다."
                        )
                        if st.button(
                            f"{final_response_employee['name']} 최종 답변 다시 생성",
                            type="primary",
                            use_container_width=True,
                            key=f"retry_synthesis_{existing_team_task['id']}",
                        ):
                            retry_task_synthesis(
                                current_project,
                                existing_team_task,
                                manager_profile,
                                manager_department,
                                active_supporting_employees,
                                employees_by_id,
                            )
