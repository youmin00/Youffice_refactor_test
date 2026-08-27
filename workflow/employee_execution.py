"""직원별 전담 업무와 단계별 병렬 실행을 담당합니다."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import sqlite3

from conversation.employee_prompts import build_employee_system_prompt
from conversation.ollama_client import MODEL_NAME, OllamaResponseFormatError, optimized_chat
from conversation.prompts import build_project_context
from conversation.response_formats import EMPLOYEE_RESULT_MARKERS
from conversation.response_recovery import EMPTY_ANSWER_MESSAGE, final_answer_with_retry
from database import (
    add_handoff,
    add_memory,
    finish_employee_result,
    set_employee_activity,
    start_employee_result,
)
from workflow.assignment import (
    ACTIVE_EMPLOYEE_ID,
    EMPLOYEE_WORKSTREAM_LABELS,
    build_employee_assignment,
    build_employee_output_instruction,
    employee_workstream,
)
from workflow.errors import workflow_error_detail
from workflow.review import WorkflowCancelled, ensure_workflow_not_cancelled


EmployeeResult = tuple[dict, str, int]


@dataclass
class EmployeeExecutionResult:
    """회의 단계에 넘길 성공 결과와 실패 직원 목록입니다."""

    successful_results: list[EmployeeResult]
    failed_employee_names: list[str]


def run_employee_workstreams(
    *,
    task_id: int,
    project_id: int,
    project: dict,
    user_message: dict,
    manager_message: dict,
    workstream_employees: dict[str, list[tuple[dict, str]]],
    employee_order: dict[str, int],
    conversation_context: str,
    source_context: str,
    memory_context: str,
    source_message_id: int,
    report_employees: list[tuple[dict, str]],
) -> EmployeeExecutionResult:
    """기억→기획→기술→일반 단계를 실행하고 직원 결과를 프로필 순서로 반환합니다."""

    successful_results: list[EmployeeResult] = []
    failed_employee_names: list[str] = []

    def run_independent_employee(
        employee_data: tuple[dict, str],
        upstream_results: list[tuple[dict, str, int]],
    ) -> tuple[dict, str, int | None, str | None]:
        """직원별 전담 업무를 실행하고 다음 직원이 쓸 결과를 저장합니다."""

        employee, employee_department = employee_data
        workstream = employee_workstream(employee, employee_department)
        assignment = build_employee_assignment(employee, employee_department)
        upstream_context = "\n\n".join(
            f"[{upstream_employee['name']} 선행 결과]\n{upstream_answer}"
            for upstream_employee, upstream_answer, _ in upstream_results
        )
        handoff_content = (
            f"[직원 전담 업무]\n{assignment}\n\n"
            f"[프로젝트 핵심 목표]\n{project['goal']}\n\n"
            f"[사용자 요청]\n{user_message['content']}\n\n"
            f"[승인된 팀장 배정 계획]\n{manager_message['content']}\n\n"
            "[실행 단계 안내]\n"
            "사용자 승인이 끝났으므로 지금은 역할을 다시 소개하거나 배정 계획을 요약하는 "
            "단계가 아니다. 프로젝트 핵심 목표를 달성하기 위해 위 전담 범위의 실제 산출물을 "
            "지금 작성한다. 사용자 요청에 '배정'이라는 표현이 있더라도 승인된 담당 업무를 "
            "실행하고, 다른 직원의 결과가 필요한 부분만 명확히 전달한다.\n\n"
            f"[선행 직원 결과]\n{upstream_context or '없음'}"
        )
        output_instruction = build_employee_output_instruction(
            employee,
            employee_department,
        )
        result_id: int | None = None
        try:
            ensure_workflow_not_cancelled(task_id)
            set_employee_activity(
                project_id,
                employee["id"],
                "working",
                f"{EMPLOYEE_WORKSTREAM_LABELS[workstream]} 수행 중",
                task_id,
            )
            add_handoff(
                task_id,
                ACTIVE_EMPLOYEE_ID,
                employee["id"],
                handoff_content,
            )
            for upstream_employee, upstream_answer, _ in upstream_results:
                add_handoff(
                    task_id,
                    upstream_employee["id"],
                    employee["id"],
                    upstream_answer,
                )
            result_id = start_employee_result(
                task_id,
                employee["id"],
                handoff_content,
            )
            employee_response = optimized_chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            build_project_context(project)
                            + source_context
                            + (memory_context if workstream == "memory" else "")
                            + build_employee_system_prompt(
                                employee,
                                employee_department,
                            )
                            + output_instruction
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            (
                                f"이전 프로젝트 대화:\n{conversation_context}\n\n"
                                if workstream == "memory" and conversation_context
                                else ""
                            )
                            + f"{handoff_content}\n\n/no_think"
                        ),
                    },
                ],
                think=False,
                stream=False,
                answer_prefix="[담당 결과]\n",
            )
            ensure_workflow_not_cancelled(task_id)
            employee_answer = final_answer_with_retry(
                employee_response.message.content,
                handoff_content,
                output_instruction=output_instruction,
                required_markers=EMPLOYEE_RESULT_MARKERS,
            )
            ensure_workflow_not_cancelled(task_id)
            if employee_answer == EMPTY_ANSWER_MESSAGE:
                raise OllamaResponseFormatError(
                    "직원 응답이 역할 형식을 충족하지 못했습니다."
                )
            finish_employee_result(result_id, "completed", output=employee_answer)
            add_handoff(
                task_id,
                employee["id"],
                ACTIVE_EMPLOYEE_ID,
                employee_answer,
            )
            if workstream == "memory":
                try:
                    add_memory(
                        project_id,
                        employee_answer[:3000],
                        category="general",
                        employee_id=employee["id"],
                        source_message_id=source_message_id,
                    )
                except sqlite3.Error:
                    pass
            set_employee_activity(
                project_id,
                employee["id"],
                "completed",
                "결과 전달 완료",
                task_id,
            )
            return employee, employee_answer, result_id, None
        except WorkflowCancelled:
            raise
        except Exception as error:
            import traceback

            error_detail = workflow_error_detail("직원 업무", error)
            employee_label = employee.get("name") or employee.get("id")
            print(f"[{employee_label}] {error_detail}", flush=True)
            traceback.print_exc()

            if result_id is not None:
                try:
                    finish_employee_result(
                        result_id,
                        "failed",
                        error=str(error),
                    )
                except sqlite3.Error:
                    pass

            set_employee_activity(
                project_id,
                employee["id"],
                "error",
                error_detail[:180],
                task_id,
            )
            return employee, "", result_id, error_detail


    def run_employee_phase(
        employees_in_phase: list[tuple[dict, str]],
        upstream_results: list[tuple[dict, str, int]],
    ) -> list[tuple[dict, str, int]]:
        """같은 단계 직원만 병렬 실행하고 프로필 순서대로 결과를 반환합니다."""

        phase_results: list[tuple[dict, str, int]] = []
        ensure_workflow_not_cancelled(task_id)
        if not employees_in_phase:
            return phase_results
        worker_count = min(2, len(employees_in_phase))
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix=f"youffice-task-{task_id}-employee",
        ) as executor:
            futures = [
                executor.submit(
                    run_independent_employee,
                    employee_data,
                    list(upstream_results),
                )
                for employee_data in employees_in_phase
            ]
            for future in as_completed(futures):
                employee, answer, result_id, error = future.result()
                if error is not None or result_id is None:
                    failed_employee_names.append(employee["name"])
                else:
                    phase_results.append((employee, answer, result_id))
        phase_results.sort(key=lambda result: employee_order[result[0]["id"]])
        return phase_results

    has_execution_employee = any(
        workstream_employees[workstream]
        for workstream in ("memory", "planning", "technical", "general")
    )
    if not has_execution_employee:
        failed_employee_names.append("선행 업무 담당 직원 없음")
        for report_employee, _ in report_employees:
            set_employee_activity(
                project_id,
                report_employee["id"],
                "error",
                "최종 보고에 사용할 선행 결과 없음",
                task_id,
            )

    ensure_workflow_not_cancelled(task_id)
    memory_results = run_employee_phase(workstream_employees["memory"], [])
    successful_results.extend(memory_results)

    ensure_workflow_not_cancelled(task_id)
    planning_results = run_employee_phase(
        workstream_employees["planning"],
        memory_results,
    )
    successful_results.extend(planning_results)

    ensure_workflow_not_cancelled(task_id)
    technical_results = run_employee_phase(
        workstream_employees["technical"],
        memory_results + planning_results,
    )
    successful_results.extend(technical_results)

    ensure_workflow_not_cancelled(task_id)
    general_results = run_employee_phase(
        workstream_employees["general"],
        memory_results + planning_results + technical_results,
    )
    successful_results.extend(general_results)
    successful_results.sort(key=lambda result: employee_order[result[0]["id"]])

    return EmployeeExecutionResult(
        successful_results=successful_results,
        failed_employee_names=failed_employee_names,
    )

