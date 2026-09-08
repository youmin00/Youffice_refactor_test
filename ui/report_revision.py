"""저장된 프로젝트 준비서와 진행 보고서의 수정 요청 dialog."""

from __future__ import annotations

import streamlit as st

from database import add_message
from workflow.report_revision_service import revise_report_safely
from workflow.reporting import generate_project_report
from workflow.structured_report import is_structured_final_report


def clear_report_revision_dialog() -> None:
    """보고서 수정 요청 창의 선택 상태를 정리합니다."""

    st.session_state.pop("report_revision_id", None)


def structured_report_revision_key(message: dict, message_index: int) -> str:
    """채팅 보고서 수정 대상을 안정적으로 식별할 키를 만듭니다."""

    message_id = message.get("message_id")
    if message_id is not None:
        return f"message-{message_id}"
    return f"legacy-message-{message_index}"


def clear_structured_report_revision_dialog() -> None:
    """채팅 최종 보고서 수정 창의 선택 상태를 정리합니다."""

    st.session_state.pop("structured_report_revision_message_key", None)


@st.dialog(
    "채팅 프로젝트 준비서 수정",
    width="large",
    dismissible=True,
    on_dismiss=clear_structured_report_revision_dialog,
)
def show_structured_final_report_revision(
    project: dict,
    message: dict,
    message_index: int,
    report_employee: dict,
) -> None:
    """채팅에 저장된 프로젝트 준비서를 새 메시지로 안전하게 수정합니다."""

    message_key = structured_report_revision_key(message, message_index)
    st.caption("원본 프로젝트 문서는 유지되고, 수정본은 새 채팅 메시지로 추가됩니다.")
    with st.expander("수정 대상 프로젝트 문서 확인"):
        st.markdown(message["content"])

    with st.form(f"structured_report_revision_form_{message_key}"):
        revision_request = st.text_area(
            "어떤 부분을 수정할까요?",
            placeholder="예: '다음 행동'의 첫 문장만 더 간결하게 바꿔주세요.",
            height=130,
        )
        submitted = st.form_submit_button(
            "수정본 추가",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        return

    cleaned_request = revision_request.strip()
    if not cleaned_request:
        st.warning("수정할 내용을 한 문장 이상 입력해주세요.")
        return

    with st.spinner(f"{report_employee['name']} 직원이 요청한 부분만 수정하고 있습니다..."):
        revision_result = revise_report_safely(
            message["content"],
            cleaned_request,
            project,
        )

    if not revision_result.changed:
        st.warning(
            "수정 요청을 안전하게 적용할 수 없어 원본 보고서를 그대로 유지했습니다. "
            "수정할 문장이나 범위를 조금 더 구체적으로 적어주세요."
        )
        return

    if not is_structured_final_report(revision_result.content):
        st.error("수정 후 프로젝트 준비서 형식을 확인하지 못해 저장하지 않았습니다.")
        return

    employee_id = message.get("employee_id") or report_employee["id"]
    revised_message_id = add_message(
        project["id"],
        "assistant",
        revision_result.content,
        employee_id,
    )
    st.session_state.messages.append(
        {
            "message_id": revised_message_id,
            "role": "assistant",
            "content": revision_result.content,
            "employee_id": employee_id,
        }
    )
    clear_structured_report_revision_dialog()
    st.rerun()


@st.dialog(
    "프로젝트 문서 수정 요청",
    width="large",
    dismissible=True,
    on_dismiss=clear_report_revision_dialog,
)
def show_report_revision_dialog(
    project: dict,
    report: dict,
    approval: dict,
    report_employee: dict,
    report_department: str,
    supporting_employees: list[tuple[dict, str]],
) -> None:
    """사용자 의견을 받아 보고 담당자가 새 수정 보고서를 만들게 합니다."""

    st.caption("기존 보고서는 보존되고, 수정 의견을 반영한 새 보고서가 생성됩니다.")
    st.markdown(f"**수정 대상:** {report['title']}")
    with st.expander("현재 보고서 내용 확인"):
        st.markdown(report["content"])
    with st.form(f"report_revision_form_{report['id']}"):
        feedback = st.text_area(
            "어떤 부분을 수정할까요?",
            placeholder=(
                "예: 부품 예산 근거를 더 자세히 적고, 2주차 시험 절차를 "
                "초보자도 따라 할 수 있게 단계별로 수정해주세요."
            ),
            height=150,
        )
        submitted = st.form_submit_button(
            "수정 보고서 생성",
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    cleaned_feedback = feedback.strip()
    if not cleaned_feedback:
        st.warning("수정할 내용을 한 문장 이상 입력해주세요.")
        return
    generate_project_report(
        project,
        report_employee,
        report_department,
        supporting_employees,
        revision_source_report=report,
        revision_feedback=cleaned_feedback,
        revision_approval_id=approval["id"],
    )
