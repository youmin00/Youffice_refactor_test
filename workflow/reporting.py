"""YOUFFICE 업무 결과를 프로젝트 보고서로 생성합니다."""

from datetime import datetime

import streamlit as st

from conversation.employee_prompts import build_employee_system_prompt
from conversation.ollama_client import MODEL_NAME, optimized_chat
from conversation.prompts import (
    build_memory_context,
    build_project_context,
    build_source_context,
)
from conversation.response_formats import (
    FINAL_REPORT_FORMAT_INSTRUCTION,
    FINAL_REPORT_MARKERS,
)
from conversation.response_recovery import (
    EMPTY_ANSWER_MESSAGE,
    final_answer_with_retry,
)
from database import (
    add_handoff,
    add_message,
    add_report,
    create_or_get_report_approval,
    get_team_meeting,
    list_employee_results,
    list_fact_records,
    list_meeting_turns,
    list_memories,
    list_messages,
    list_project_records,
    list_reviews,
    list_sources,
    list_team_tasks,
    save_report_structured_data,
    set_employee_activity,
    update_report_approval,
)
from workflow.assignment import (
    ACTIVE_EMPLOYEE_ID,
    build_employee_assignment,
    employee_workstream,
)

from workflow.review import user_allows_unverified_progress
from workflow.report_revision_service import revise_report_safely
from workflow.structured_classifier import classify_structured_report
from workflow.structured_report import (
    STRUCTURED_REPORT_JSON_INSTRUCTION,
    parse_structured_report_json,
    render_structured_final_report,
)
from workflow.source_quality import sanitize_unverified_links, verified_source_urls


def resolve_report_task_id(
    revision_source_report: dict | None,
    latest_task_id: int | None,
) -> int | None:
    """새 보고서가 원본 보고서의 업무 참조를 유지하도록 업무 ID를 선택합니다."""

    if revision_source_report is not None:
        return revision_source_report.get("task_id")
    return latest_task_id


def build_saved_meeting_context(
    task_id: int,
    employee_lookup: dict[str, dict] | None = None,
) -> str:
    """저장된 회의 발언과 결론을 검수·보고용 문맥으로 복원합니다."""

    meeting = get_team_meeting(task_id)
    if meeting is None:
        return ""
    lookup = employee_lookup or {}
    turn_sections = []
    for turn in list_meeting_turns(meeting["id"]):
        employee = lookup.get(turn["employee_id"], {})
        speaker_name = employee.get("name", turn["employee_id"])
        speaker_role = "팀장 결론" if turn["turn_type"] == "conclusion" else "직원 의견"
        turn_sections.append(
            f"[{speaker_role} · {speaker_name}]\n{turn['content']}"
        )
    if not turn_sections and meeting.get("conclusion"):
        turn_sections.append(f"[팀장 결론]\n{meeting['conclusion']}")
    if not turn_sections:
        return ""
    return (
        f"[팀 회의 기록 · 상태: {meeting['status']}]\n"
        + "\n\n".join(turn_sections)
    )




def generate_project_report(
    project: dict,
    report_employee: dict,
    report_department: str,
    supporting_employees: list[tuple[dict, str]],
    revision_source_report: dict | None = None,
    revision_feedback: str = "",
    revision_approval_id: int | None = None,
) -> None:
    """저장 기록으로 새 보고서 또는 사용자 의견을 반영한 수정본을 작성합니다."""

    project_id = project["id"]
    messages = list_messages(project_id)
    sources = list_sources(project_id)
    memories = list_memories(project_id)
    records = list_project_records(project_id)
    fact_records = list_fact_records(project_id)
    tasks = list_team_tasks(project_id, limit=10)
    has_completed_team_work = any(
        task.get("status") == "completed"
        for task in tasks
    )
    if revision_source_report is None and not has_completed_team_work:
        st.info(
            "아직 완료된 준비 업무가 없어요. 유키와 핵심 조건을 정한 뒤 제작 준비 계획부터 만들어보세요."
        )
        return
    report_employee_lookup = {
        employee["id"]: employee
        for employee, _ in supporting_employees
    }
    report_employee_lookup[report_employee["id"]] = report_employee
    report_employee_lookup.setdefault(
        ACTIVE_EMPLOYEE_ID,
        {"name": "프로젝트 팀장"},
    )

    conversation_text = "\n".join(
        f"[{message['role']}/{message.get('employee_id') or 'user'}] {message['content']}"
        for message in messages[-30:]
    )
    task_sections: list[str] = []
    for task in reversed(tasks[:5]):
        result_text = "\n".join(
            f"- {result['employee_id']}: {result['output'] or result['error']}"
            for result in list_employee_results(task["id"])
        )
        review_text = "\n".join(
            f"- {review['reviewer_employee_id']} / {review['verdict']}: {review['feedback']}"
            for review in list_reviews(task["id"])
        )
        meeting_text = build_saved_meeting_context(
            task["id"],
            report_employee_lookup,
        )
        task_sections.append(
            f"[업무 #{task['id']} / {task['status']}]\n"
            f"요청: {task['request']}\n직원 결과:\n{result_text or '없음'}\n"
            f"팀 회의:\n{meeting_text or '미진행'}\n"
            f"검수:\n{review_text or '없음'}"
        )

    report_material = (
        f"프로젝트 대화:\n{conversation_text or '없음'}\n\n"
        f"팀 업무 기록:\n{'\n\n'.join(task_sections) or '없음'}"
    )
    if revision_source_report is not None:
        report_material += (
            f"\n\n[사용자가 수정 요청한 기존 보고서]\n"
            f"{revision_source_report['content']}\n\n"
            f"[사용자 수정 요청]\n{revision_feedback}"
        )
    # 작은 로컬 모델의 입력 한도를 넘지 않도록 최근 핵심 기록을 우선합니다.
    report_material = report_material[-24000:]
    latest_task_id = tasks[0]["id"] if tasks else None
    report_task_id = resolve_report_task_id(
        revision_source_report,
        latest_task_id,
    )
    try:
        if revision_source_report is not None and report_task_id is not None:
            add_handoff(
                report_task_id,
                ACTIVE_EMPLOYEE_ID,
                report_employee["id"],
                f"[사용자 최종 보고서 수정 요청]\n{revision_feedback}",
            )
            set_employee_activity(
                project_id,
                report_employee["id"],
                "synthesizing",
                "사용자 보고서 수정 요청 반영 중",
                report_task_id,
            )
        if revision_source_report is not None:
            with st.spinner(
                f"{report_employee['name']} \uc9c1\uc6d0\uc774 "
                "\uc694\uccad\ud55c \ubd80\ubd84\ub9cc \uc548\uc804\ud558\uac8c "
                "\uc218\uc815\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4..."
            ):
                revision_result = revise_report_safely(
                    revision_source_report["content"],
                    revision_feedback,
                    project,
                )

            if not revision_result.changed:
                st.warning(
                    "\uc218\uc815 \uc694\uccad\uc744 \uc548\uc804\ud558\uac8c "
                    "\uc801\uc6a9\ud560 \uc218 \uc5c6\uc5b4 \uae30\uc874 \ubcf4\uace0\uc11c\ub97c "
                    "\uadf8\ub300\ub85c \uc720\uc9c0\ud588\uc2b5\ub2c8\ub2e4. "
                    "\uc218\uc815\ud560 \ubd80\ubd84\uc744 \uc870\uae08 \ub354 "
                    "\uad6c\uccb4\uc801\uc73c\ub85c \uc801\uc5b4\uc8fc\uc138\uc694."
                )
                return

            report_content = revision_result.content

        else:
            with st.spinner(f"{report_employee['name']} 직원이 프로젝트 보고서를 작성하고 있습니다..."):
                response = optimized_chat(
                    model=MODEL_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                build_project_context(project)
                                + build_source_context(sources)
                                + build_memory_context(memories, records, fact_records)
                                + build_employee_system_prompt(
                                    report_employee,
                                    report_department,
                                    [
                                        employee_data
                                        for employee_data in supporting_employees
                                        if employee_data[0]["id"] != report_employee["id"]
                                    ],
                                )
                                + "저장된 실제 기록만 사용해 전문적인 한국어 Markdown 프로젝트 문서를 작성한다. "
                                "구성은 프로젝트 개요, 확정 요구사항과 기본 가정, 준비 내용, 직원별 핵심 결과, "
                                "검토 및 보완, 사용자가 직접 할 일, 외부 도구로 넘길 일, 테스트 계획, 미해결 위험, 출처 순서로 한다. "
                                "자료가 없거나 확인되지 않은 내용은 사실처럼 만들지 않는다. "
                                + (
                                    "기존 보고서의 확인된 사실과 전체 구조는 유지하되 사용자 수정 요청을 "
                                    "빠짐없이 반영하고, 반영할 근거가 없는 요청은 확인 필요로 표시한다. "
                                    if revision_source_report is not None
                                    else ""
                                )
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"다음 저장 기록을 바탕으로 보고서를 작성하세요.\n\n{report_material}\n\n/no_think",
                        },
                    ],
                    think=False,
                    stream=False,
                    answer_prefix="# 프로젝트 준비서 및 진행 보고\n",
                )
            report_content = final_answer_with_retry(
                response.message.content,
                report_material,
            )
        report_content = sanitize_unverified_links(
            report_content,
            verified_source_urls(sources),
        )
        report_title = (
            f"{project['name']} 프로젝트 "
            f"{'수정 보고서' if revision_source_report is not None else '보고서'} "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        report_id = add_report(
            project_id,
            report_employee["id"],
            report_title,
            report_content,
            task_id=report_task_id,
            parent_report_id=(
                revision_source_report["id"]
                if revision_source_report is not None
                else None
            ),
        )
        create_or_get_report_approval(project_id, report_id)
        if revision_approval_id is not None:
            update_report_approval(
                revision_approval_id,
                "revision_requested",
                user_feedback=revision_feedback,
                replacement_report_id=report_id,
            )
        if revision_source_report is not None and report_task_id is not None:
            add_handoff(
                report_task_id,
                report_employee["id"],
                ACTIVE_EMPLOYEE_ID,
                f"[수정 보고서 #{report_id}]\n{report_content}",
            )
            set_employee_activity(
                project_id,
                report_employee["id"],
                "completed",
                "수정 보고서 제출 · 사용자 승인 대기",
                report_task_id,
            )
    except Exception as error:
        if revision_source_report is not None and report_task_id is not None:
            set_employee_activity(
                project_id,
                report_employee["id"],
                "error",
                "수정 보고서 생성 오류",
                report_task_id,
            )
        st.error(f"보고서를 생성하지 못했습니다: {error}")
        return
    st.rerun()


def _saved_final_review_status(
    reviews: list[dict],
) -> str:
    """Derive final review status from the latest saved review round."""

    if not reviews:
        return "\uac80\uc218 \uae30\ub85d \uc5c6\uc74c"

    latest_round = max(
        int(review.get("review_round") or 0)
        for review in reviews
    )

    latest_reviews = [
        review
        for review in reviews
        if int(review.get("review_round") or 0) == latest_round
    ]

    verdicts = {
        str(review.get("verdict") or "").strip()
        for review in latest_reviews
    }

    if "failed" in verdicts:
        return "\ud300 \ubb38\uc11c \uac80\ud1a0 \ubbf8\ud1b5\uacfc"

    if "rework_requested" in verdicts:
        return "\ud300 \ubb38\uc11c \uac80\ud1a0 \uc7ac\uc791\uc5c5 \ud544\uc694"

    if verdicts and verdicts <= {"passed"}:
        return "\ud300 \ubb38\uc11c \uac80\ud1a0 \ud1b5\uacfc"

    return "\ud300 \ubb38\uc11c \uac80\ud1a0 \uc0c1\ud0dc \ubbf8\ud655\uc778"


def retry_task_synthesis(
    project: dict,
    task: dict,
    manager_profile: dict,
    manager_department: str,
    supporting_employees: list[tuple[dict, str]],
    employees_by_id: dict[str, dict],
) -> None:
    """직원 호출을 반복하지 않고 저장된 결과로 최종 보고만 다시 만듭니다."""

    report_employee_data = next(
        (
            employee_data
            for employee_data in supporting_employees
            if employee_workstream(employee_data[0], employee_data[1]) == "report"
        ),
        None,
    )
    final_employee, final_department = report_employee_data or (
        manager_profile,
        manager_department,
    )
    worker_result_ids = {
        employee["id"]
        for employee, department in supporting_employees
        if employee_workstream(employee, department)
        in ("memory", "planning", "technical", "general")
    }
    sources = list_sources(project["id"])

    employee_reports = "\n\n".join(
        (
            f"[{employees_by_id.get(result['employee_id'], {}).get('name', result['employee_id'])}]\n"
            f"{result['output'] or result['error']}"
        )
        for result in list_employee_results(task["id"])
        if result["employee_id"] in worker_result_ids
    )
    saved_reviews = list_reviews(task["id"])

    review_reports = "\n\n".join(
        (
            f"[{employees_by_id.get(review['reviewer_employee_id'], {}).get('name', review['reviewer_employee_id'])}] "
            f"{review['verdict']}\n{review['feedback']}"
        )
        for review in saved_reviews
    )
    meeting_reports = build_saved_meeting_context(
        task["id"],
        employees_by_id,
    )
    task_context = (
        f"사용자 요청:\n{task['request']}\n\n"
        f"승인된 팀장 계획:\n{task['manager_context']}\n\n"
        f"팀 회의 기록:\n{meeting_reports or '회의 미진행'}\n\n"
        f"직원 보고:\n{employee_reports or '없음'}\n\n"
        f"검수 결과:\n{review_reports or '없음'}"
    )
    final_review_status = _saved_final_review_status(
        saved_reviews
    )

    try:
        with st.spinner(
            f"{final_employee['name']} \uc9c1\uc6d0\uc774 "
            "\uc800\uc7a5\ub41c \uacb0\uacfc\ub97c \ub2e4\uc2dc "
            "\uc885\ud569\ud558\uace0 \uc788\uc2b5\ub2c8\ub2e4..."
        ):
            structured_data = classify_structured_report(
                task_context[-18000:]
            )

        answer = render_structured_final_report(
            project,
            final_review_status,
            structured_data,
            allow_unverified_progress=(
                user_allows_unverified_progress(
                    task["request"]
                )
            ),
        )

        if answer == EMPTY_ANSWER_MESSAGE:
            raise RuntimeError("최종 보고 응답을 확인하지 못했습니다.")
        answer = sanitize_unverified_links(
            answer,
            verified_source_urls(sources),
        )
        message_id = add_message(
            project["id"],
            "assistant",
            answer,
            final_employee["id"],
        )
        report_id = add_report(
            project["id"],
            final_employee["id"],
            (
                f"{project['name']} 재종합 프로젝트 문서 "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ),
            answer,
            task_id=task["id"],
            message_id=message_id,
        )
        save_report_structured_data(
            report_id,
            project["id"],
            structured_data.proposals,
            structured_data.unverified,
            structured_data.limitations,
        )
        create_or_get_report_approval(project["id"], report_id)
        st.session_state.messages.append(
            {
                "message_id": message_id,
                "role": "assistant",
                "content": answer,
                "employee_id": final_employee["id"],
            }
        )
    except Exception as error:
        st.error(f"최종 답변을 다시 생성하지 못했습니다: {error}")
        return
    st.rerun()
