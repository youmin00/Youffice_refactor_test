"""검수 완료 결과를 구조화 최종 보고서로 생성하고 저장합니다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3

from conversation.ollama_client import OllamaResponseFormatError
from conversation.response_recovery import EMPTY_ANSWER_MESSAGE
from database import (
    add_handoff,
    add_message,
    add_report,
    create_or_get_report_approval,
    finish_employee_result,
    save_report_structured_data,
    set_employee_activity,
    start_employee_result,
)
from workflow.assignment import ACTIVE_EMPLOYEE_ID, build_employee_assignment
from workflow.errors import workflow_error_detail
from workflow.review import (
    WorkflowCancelled,
    ensure_workflow_not_cancelled,
    review_verdict,
    user_allows_unverified_progress,
)
from workflow.structured_classifier import classify_structured_report
from workflow.structured_report import render_structured_final_report


EmployeeResult = tuple[dict, str, int]


@dataclass
class FinalReportExecutionResult:
    """최종 보고 실행 뒤 엔진이 사용할 실패 직원 상태입니다."""

    failed_employee_names: list[str]


def run_final_report(
    *,
    task_id: int,
    project_id: int,
    project: dict,
    user_message: dict,
    manager_profile: dict,
    report_employees: list[tuple[dict, str]],
    successful_results: list[EmployeeResult],
    review_results: list[EmployeeResult],
    unresolved_review_employee_ids: set[str],
    has_unresolved_reviews: bool,
    pre_report_failures: list[str],
    meeting_context: str,
    failed_employee_names: list[str],
) -> FinalReportExecutionResult:
    """검수 통과 결과만 최종 보고서로 저장하고 실패 상태를 반환합니다."""

    failed_employee_names = list(failed_employee_names)
    results_by_employee_id = {
        employee["id"]: result
        for result in successful_results
        for employee in [result[0]]
    }

    if (
        (successful_results or review_results)
        and not has_unresolved_reviews
        and not pre_report_failures
    ):
        employee_reports = "\n\n".join(
            f"[{employee['name']} 보고]\n{answer}"
            for employee, answer, _ in successful_results
        )
        review_reports = "\n\n".join(
            f"[{reviewer['name']} 검수]\n{answer}"
            for reviewer, answer, _ in review_results
        )
        has_unresolved_reviews = bool(unresolved_review_employee_ids) or any(
            review_verdict(answer) != "passed"
            for _, answer, _ in review_results
        )
        if has_unresolved_reviews:
            unresolved_names = ", ".join(
                results_by_employee_id[employee_id][0]["name"]
                for employee_id in sorted(unresolved_review_employee_ids)
                if employee_id in results_by_employee_id
            ) or "검수 결과 확인 필요"
            final_review_status = f"팀 문서 검토 미통과: {unresolved_names}"
        elif review_results:
            final_review_status = "팀 문서 검토 통과"
        else:
            final_review_status = "팀 문서 검토 기록 없음"
        synthesis_input = (
            f"사용자 요청:\n{user_message['content']}\n\n"
            f"팀 회의 기록:\n{meeting_context or '회의 미진행'}\n\n"
            f"직원 보고:\n{employee_reports or '없음'}\n\n"
            f"검수 결과:\n{review_reports or '없음'}\n\n"
            f"팀 문서 검토 상태:\n{final_review_status}"
        )
        report_result_id: int | None = None
        final_employee = manager_profile
        try:
            ensure_workflow_not_cancelled(task_id)
            if report_employees:
                final_employee, final_department = report_employees[0]
                report_assignment = build_employee_assignment(
                    final_employee,
                    final_department,
                )
                report_input = (
                    f"[최종 보고 전담 업무]\n{report_assignment}\n\n"
                    f"{synthesis_input}"
                )
                set_employee_activity(
                    project_id,
                    ACTIVE_EMPLOYEE_ID,
                    "waiting",
                    f"{final_employee['name']} 최종 보고 대기",
                    task_id,
                )
                set_employee_activity(
                    project_id,
                    final_employee["id"],
                    "synthesizing",
                    "직원 결과 종합 중",
                    task_id,
                )
                add_handoff(
                    task_id,
                    ACTIVE_EMPLOYEE_ID,
                    final_employee["id"],
                    report_assignment,
                )
                for employee, employee_answer, _ in successful_results:
                    add_handoff(
                        task_id,
                        employee["id"],
                        final_employee["id"],
                        employee_answer,
                    )
                for reviewer, review_answer, _ in review_results:
                    add_handoff(
                        task_id,
                        reviewer["id"],
                        final_employee["id"],
                        review_answer,
                    )
                report_result_id = start_employee_result(
                    task_id,
                    final_employee["id"],
                    report_input,
                )
            else:
                report_input = synthesis_input
                set_employee_activity(
                    project_id,
                    ACTIVE_EMPLOYEE_ID,
                    "synthesizing",
                    "직원 결과 종합 중",
                    task_id,
                )
            # Structured Final Report v1:
            # Qwen classifies only proposals/unverified/limitations/actions.
            # Confirmed project facts and review status are owned by code.
            structured_data = classify_structured_report(
                synthesis_input
            )

            ensure_workflow_not_cancelled(task_id)

            synthesis_answer = render_structured_final_report(
                project,
                final_review_status,
                structured_data,
                allow_unverified_progress=(
                    user_allows_unverified_progress(
                        user_message["content"]
                    )
                ),
            )
            ensure_workflow_not_cancelled(task_id)
            if synthesis_answer == EMPTY_ANSWER_MESSAGE:
                raise OllamaResponseFormatError(
                    "최종 보고 응답을 확인하지 못했습니다."
                )
            if report_result_id is not None:
                finish_employee_result(
                    report_result_id,
                    "completed",
                    output=synthesis_answer,
                )
                add_handoff(
                    task_id,
                    final_employee["id"],
                    ACTIVE_EMPLOYEE_ID,
                    synthesis_answer,
                )
                set_employee_activity(
                    project_id,
                    final_employee["id"],
                    "completed",
                    "최종 보고 전달 완료",
                    task_id,
                )
            workflow_message_id = add_message(
                project_id,
                "assistant",
                synthesis_answer,
                final_employee["id"],
            )
            workflow_report_id = add_report(
                project_id,
                final_employee["id"],
                (
                    f"{project['name']} 최종 보고서 "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ),
                synthesis_answer,
                task_id=task_id,
                message_id=workflow_message_id,
            )
            save_report_structured_data(
                workflow_report_id,
                project_id,
                structured_data.proposals,
                structured_data.unverified,
                structured_data.limitations,
            )
            create_or_get_report_approval(project_id, workflow_report_id)
        except WorkflowCancelled:
            raise
        except Exception as error:
            failed_employee_names.append(final_employee["name"])
            if report_result_id is not None:
                try:
                    finish_employee_result(
                        report_result_id,
                        "failed",
                        error=str(error),
                    )
                except sqlite3.Error:
                    pass
            if final_employee.get("id") != ACTIVE_EMPLOYEE_ID:
                set_employee_activity(
                    project_id,
                    final_employee["id"],
                    "error",
                    workflow_error_detail("최종 보고", error)[:180],
                    task_id,
                )


    return FinalReportExecutionResult(
        failed_employee_names=failed_employee_names,
    )
