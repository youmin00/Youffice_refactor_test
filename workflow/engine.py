"""YOUFFICE 팀 업무의 전체 실행 단계를 조정합니다."""

import sqlite3
import threading

from conversation.prompts import (
    build_memory_context,
    build_source_context,
)
from database import (
    add_message,
    clear_employee_activities,
    create_task_control,
    create_team_task,
    list_employee_activities,
    list_fact_records,
    list_memories,
    list_project_records,
    list_sources,
    list_team_tasks,
    set_employee_activity,
    update_task_control_state,
    update_team_task_status,
)
from workflow.assignment import (
    ACTIVE_EMPLOYEE_ID,
    employee_workstream,
)
from workflow.review import (
    WorkflowCancelled,
    ensure_workflow_not_cancelled,
    review_verdict,
)
from workflow.errors import workflow_error_detail
from workflow.employee_execution import run_employee_workstreams
from workflow.final_report_execution import run_final_report
from workflow.meeting import run_team_meeting
from workflow.review_execution import run_review_cycle


# A single Streamlit process can receive two approval actions before either
# registration marks its task as running. Keep that check-and-register sequence
# atomic so one project cannot launch overlapping workflows.
_WORKFLOW_START_LOCK = threading.Lock()


def execute_team_workflow_background(
    task_id: int,
    project_id: int,
    project: dict,
    user_message: dict,
    manager_message: dict,
    manager_profile: dict,
    manager_department: str,
    supporting_employees: list[tuple[dict, str]],
    recent_messages: list[dict],
) -> None:
    """Streamlit 화면을 막지 않고 직원별 Ollama 업무를 실행합니다."""

    try:
        source_message_id = user_message["message_id"]
        current_message_ids = {
            source_message_id,
            manager_message.get("message_id"),
        }
        conversation_context = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in recent_messages[-12:]
            if message.get("message_id") not in current_message_ids
        )
        source_context = build_source_context(list_sources(project_id))
        memory_context = build_memory_context(
            list_memories(project_id),
            list_project_records(project_id),
            list_fact_records(project_id),
        )
        workstream_employees = {
            workstream: [
                employee_data
                for employee_data in supporting_employees
                if employee_workstream(employee_data[0], employee_data[1]) == workstream
            ]
            for workstream in (
                "memory",
                "planning",
                "technical",
                "general",
                "review",
                "report",
            )
        }
        review_employees = workstream_employees["review"]
        report_employees = workstream_employees["report"]
        employee_order = {
            employee["id"]: index
            for index, (employee, _) in enumerate(supporting_employees)
        }

        ensure_workflow_not_cancelled(task_id)

    except Exception as exc:
        import traceback

        error_detail = workflow_error_detail("업무 시작", exc)
        print(error_detail, flush=True)
        traceback.print_exc()

        try:
            update_team_task_status(task_id, "failed")
            set_employee_activity(
                project_id,
                ACTIVE_EMPLOYEE_ID,
                "error",
                error_detail,
                task_id,
            )
        except sqlite3.Error:
            pass
        return


    try:
        employee_execution = run_employee_workstreams(
            task_id=task_id,
            project_id=project_id,
            project=project,
            user_message=user_message,
            manager_message=manager_message,
            workstream_employees=workstream_employees,
            employee_order=employee_order,
            conversation_context=conversation_context,
            source_context=source_context,
            memory_context=memory_context,
            source_message_id=source_message_id,
            report_employees=report_employees,
        )
        successful_results = employee_execution.successful_results
        failed_employee_names = employee_execution.failed_employee_names

        meeting_result = run_team_meeting(
            task_id=task_id,
            project_id=project_id,
            project=project,
            user_message=user_message,
            manager_message=manager_message,
            manager_profile=manager_profile,
            manager_department=manager_department,
            successful_results=successful_results,
            review_employees=review_employees,
            report_employees=report_employees,
            source_message_id=source_message_id,
        )
        meeting_context = meeting_result.context
        meeting_warning_names = list(meeting_result.warning_names)
        if meeting_result.manager_failed:
            failed_employee_names.append(manager_profile["name"])
        review_cycle = run_review_cycle(
            task_id=task_id,
            project_id=project_id,
            project=project,
            user_message=user_message,
            manager_message=manager_message,
            successful_results=successful_results,
            review_employees=review_employees,
            meeting_context=meeting_context,
            source_context=source_context,
            memory_context=memory_context,
            failed_employee_names=failed_employee_names,
        )
        successful_results = review_cycle.successful_results
        review_results = review_cycle.review_results
        failed_employee_names = review_cycle.failed_employee_names
        unresolved_review_employee_ids = (
            review_cycle.unresolved_review_employee_ids
        )
        missing_required_review = review_cycle.missing_required_review
        has_unresolved_reviews = review_cycle.has_unresolved_reviews
        waiting_for_user = review_cycle.waiting_for_user
        pre_report_failures = review_cycle.pre_report_failures

        report_execution = run_final_report(
            task_id=task_id,
            project_id=project_id,
            project=project,
            user_message=user_message,
            manager_profile=manager_profile,
            report_employees=report_employees,
            successful_results=successful_results,
            review_results=review_results,
            unresolved_review_employee_ids=unresolved_review_employee_ids,
            has_unresolved_reviews=has_unresolved_reviews,
            pre_report_failures=pre_report_failures,
            meeting_context=meeting_context,
            failed_employee_names=failed_employee_names,
        )
        failed_employee_names = report_execution.failed_employee_names
        ensure_workflow_not_cancelled(task_id)
        has_unresolved_reviews = missing_required_review or bool(
            unresolved_review_employee_ids
        ) or any(
            review_verdict(answer) != "passed"
            for _, answer, _ in review_results
        )
        workflow_failed = bool(failed_employee_names) or has_unresolved_reviews
        final_status = "failed" if workflow_failed else "completed"
        update_team_task_status(task_id, final_status)
        if waiting_for_user:
            manager_detail = "사용자 정보 확인 대기"
        elif missing_required_review:
            manager_detail = "최종 검수 기록 없음"
        elif has_unresolved_reviews:
            manager_detail = "2차 검수 미통과"
        elif failed_employee_names:
            manager_detail = "일부 업무 오류"
        elif meeting_warning_names:
            manager_detail = "팀 협업 완료 · 회의 일부 미제출"
        else:
            manager_detail = "팀 협업 완료"
        set_employee_activity(
            project_id,
            ACTIVE_EMPLOYEE_ID,
            "waiting" if waiting_for_user else ("error" if workflow_failed else "completed"),
            manager_detail,
            task_id,
        )
        transitional_statuses = {
            "waiting",
            "assigned",
            "working",
            "reviewing",
            "reworking",
            "synthesizing",
        }
        for activity in list_employee_activities(project_id):
            if (
                activity.get("task_id") == task_id
                and activity.get("status") in transitional_statuses
            ):
                set_employee_activity(
                    project_id,
                    activity["employee_id"],
                    (
                        "waiting"
                        if waiting_for_user
                        else ("error" if workflow_failed else "completed")
                    ),
                    (
                        "사용자 정보 확인 대기"
                        if waiting_for_user
                        else ("업무 종료 · 확인 필요" if workflow_failed else "업무 종료")
                    ),
                    task_id,
                )
    except WorkflowCancelled:
        try:
            update_team_task_status(task_id, "failed")
            update_task_control_state(task_id, "cancelled")
            set_employee_activity(
                project_id,
                ACTIVE_EMPLOYEE_ID,
                "inactive",
                "사용자가 작업을 중단했습니다",
                task_id,
            )
            for activity in list_employee_activities(project_id):
                if activity.get("task_id") == task_id and activity.get("status") in {
                    "waiting",
                    "assigned",
                    "working",
                    "reviewing",
                    "reworking",
                    "synthesizing",
                }:
                    set_employee_activity(
                        project_id,
                        activity["employee_id"],
                        "inactive",
                        "사용자가 작업을 중단했습니다",
                        task_id,
                    )
            add_message(
                project_id,
                "assistant",
                "사용자 요청으로 현재 팀 업무를 중단했습니다. 완료된 기록은 남아 있으며 최종 보고서는 생성하지 않았습니다.",
                ACTIVE_EMPLOYEE_ID,
            )
        except sqlite3.Error:
            pass
    except Exception as exc:
        import traceback

        error_detail = workflow_error_detail("팀 업무 실행", exc)
        print(error_detail, flush=True)
        traceback.print_exc()

        try:
            update_team_task_status(task_id, "failed")
            set_employee_activity(
                project_id,
                ACTIVE_EMPLOYEE_ID,
                "error",
                error_detail,
                task_id,
            )
        except sqlite3.Error:
            pass



def start_team_workflow_background(
    project_id: int,
    project: dict,
    user_message: dict,
    manager_message: dict,
    manager_profile: dict,
    manager_department: str,
    supporting_employees: list[tuple[dict, str]],
    recent_messages: list[dict],
) -> tuple[bool, str]:
    """팀 업무를 등록하고 백그라운드 실행 스레드를 시작합니다."""

    source_message_id = user_message.get("message_id")
    if source_message_id is None:
        return False, "업무의 원본 메시지 ID를 찾지 못했습니다."

    with _WORKFLOW_START_LOCK:
        try:
            running_task = next(
                (
                    task
                    for task in list_team_tasks(project_id, limit=100)
                    if task["status"] == "running"
                ),
                None,
            )
            if running_task is not None:
                return (
                    False,
                    f"현재 팀 업무 #{running_task['id']}가 실행 중입니다. "
                    "완료된 뒤 다음 업무를 시작해주세요.",
                )
            task_id = create_team_task(
                project_id,
                source_message_id,
                user_message["content"],
                manager_message["content"],
            )
            update_team_task_status(task_id, "running")
            create_task_control(task_id)
            clear_employee_activities(project_id)
            set_employee_activity(
                project_id,
                ACTIVE_EMPLOYEE_ID,
                "working",
                "업무 배분 중",
                task_id,
            )
            for employee, employee_department in supporting_employees:
                is_report_role = (
                    employee_workstream(employee, employee_department) == "report"
                )
                detail = "최종 보고 대기" if is_report_role else "업무 배정됨"
                set_employee_activity(
                    project_id,
                    employee["id"],
                    "waiting" if is_report_role else "assigned",
                    detail,
                    task_id,
                )
        except sqlite3.IntegrityError:
            return False, "이 요청은 이미 팀에 전달되었습니다."
        except sqlite3.Error as error:
            return False, f"팀 업무를 생성하지 못했습니다: {error}"

    thread = threading.Thread(
        target=execute_team_workflow_background,
        kwargs={
            "task_id": task_id,
            "project_id": project_id,
            "project": dict(project),
            "user_message": dict(user_message),
            "manager_message": dict(manager_message),
            "manager_profile": dict(manager_profile),
            "manager_department": manager_department,
            "supporting_employees": [
                ({**employee, "department_name": employee_department}, employee_department)
                for employee, employee_department in supporting_employees
            ],
            "recent_messages": [dict(message) for message in recent_messages],
        },
        daemon=True,
        name=f"youffice-task-{task_id}",
    )
    thread.start()
    return True, "팀 업무를 시작했습니다. 오피스에서 실시간 상태를 확인할 수 있습니다."
