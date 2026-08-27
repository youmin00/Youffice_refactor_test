"""1차 검수, 재작업, 2차 검수와 최종 보고 차단 조건을 실행합니다."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from conversation.employee_prompts import build_employee_system_prompt
from conversation.ollama_client import MODEL_NAME, OllamaResponseFormatError, optimized_chat
from conversation.prompts import build_project_context
from conversation.response_formats import EMPLOYEE_RESULT_MARKERS
from conversation.response_recovery import EMPTY_ANSWER_MESSAGE, final_answer_with_retry
from conversation.response_validator import is_korean_answer, remove_thinking
from database import (
    add_handoff,
    add_message,
    add_review,
    add_review_targets,
    create_or_get_clarification_request,
    finish_employee_result,
    mark_review_targets_resubmitted,
    set_employee_activity,
    start_employee_result,
    update_task_control_state,
)
from workflow.assignment import (
    ACTIVE_EMPLOYEE_ID,
    build_employee_output_instruction,
)
from workflow.errors import workflow_error_detail
from workflow.review import (
    WorkflowCancelled,
    ensure_workflow_not_cancelled,
    has_valid_review_contract,
    normalize_review_for_user_policy,
    review_clarification_questions,
    review_target_employee_ids,
    review_verdict,
)


EmployeeResult = tuple[dict, str, int]


@dataclass
class ReviewExecutionResult:
    """보고 단계에 넘길 검수 사이클의 최종 상태입니다."""

    successful_results: list[EmployeeResult]
    review_results: list[EmployeeResult]
    failed_employee_names: list[str]
    unresolved_review_employee_ids: set[str]
    missing_required_review: bool
    has_unresolved_reviews: bool
    waiting_for_user: bool
    pre_report_failures: list[str]


def run_review_cycle(
    *,
    task_id: int,
    project_id: int,
    project: dict,
    user_message: dict,
    manager_message: dict,
    successful_results: list[EmployeeResult],
    review_employees: list[tuple[dict, str]],
    meeting_context: str,
    source_context: str,
    memory_context: str,
    failed_employee_names: list[str],
) -> ReviewExecutionResult:
    """검수와 재작업을 최대 2차까지 실행하고 최종 보고 가능 여부를 반환합니다."""

    successful_results = list(successful_results)
    failed_employee_names = list(failed_employee_names)
    review_results: list[EmployeeResult] = []
    unresolved_review_employee_ids: set[str] = set()

    initial_reports = "\n\n".join(
        f"[{employee['name']} 보고 | ID: {employee['id']}]\n{answer}"
        for employee, answer, _ in successful_results
    ) or "별도 실행 직원 보고 없음"
    review_candidate_roster = "\n".join(
        f"- {employee['id']} | {employee['name']} | {employee['title']}"
        for employee, _, _ in successful_results
    ) or "- 검수할 실행 직원 없음"

    for reviewer, reviewer_department in review_employees:
        review_input = (
            f"사용자 요청:\n{user_message['content']}\n\n"
            f"팀장 계획:\n{manager_message['content']}\n\n"
            f"팀 회의 기록:\n{meeting_context or '회의 미진행'}\n\n"
            f"검수 대상 직원 ID:\n{review_candidate_roster}\n\n"
            f"직원 보고:\n{initial_reports}"
        )
        review_result_id: int | None = None
        try:
            set_employee_activity(
                project_id,
                reviewer["id"],
                "reviewing",
                "안전·품질 검수 중",
                task_id,
            )
            for employee, employee_answer, _ in successful_results:
                add_handoff(
                    task_id,
                    employee["id"],
                    reviewer["id"],
                    employee_answer,
                )
            add_handoff(
                task_id,
                ACTIVE_EMPLOYEE_ID,
                reviewer["id"],
                review_input,
            )
            review_result_id = start_employee_result(
                task_id,
                reviewer["id"],
                review_input,
            )
            review_response = optimized_chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            build_project_context(project)
                            + source_context
                            + memory_context
                            + build_employee_system_prompt(
                                reviewer,
                                reviewer_department,
                            )
                            + "팀장 계획과 직원 보고에서 기술 오류, 누락, 위험, "
                            "논리적 모순을 검수한다. 답변 첫 줄은 반드시 "
                            "'검수 결과: 통과' 또는 '검수 결과: 재작업'으로 작성하고, "
                            "재작업이면 고쳐야 할 항목을 구체적으로 설명한다. "
                            "직원이 자기 역할이나 계획만 다시 설명하고 사용자에게 필요한 "
                            "실제 산출물을 제출하지 않았다면 완료로 인정하지 말고 반드시 "
                            "재작업으로 판정한다. 실제 제작·시험 기록이 없다면 문서 검토 "
                            "통과와 실제 장치 검증 완료를 명확히 구분한다. "
                            "둘째 줄에는 반드시 '재작업 대상 ID: 없음' 또는 위 목록의 "
                            "실제 직원 ID만 쉼표로 구분해 쓴다. 통과 판정이면 대상은 없음이고, "
                            "재작업 판정이면 한 명 이상의 정확한 ID가 있어야 한다. "
                            "팀 회의의 조정 사항이 직원 결과에 반영되지 않았거나 회의에서 "
                            "남긴 위험이 해결되지 않았다면 해당 직원 ID를 재작업 대상으로 지정한다. "
                            "셋째 줄에는 반드시 '사용자 확인 필요: 없음' 또는 "
                            "'사용자 확인 필요: 질문 내용'을 쓴다. 직원이 현재 자료로 고칠 수 있는 "
                            "누락과, 대회 규정·보유 부품 사양·목표 수치처럼 사용자나 외부 자료 없이는 "
                            "확정할 수 없는 사실을 구분한다. 후자라면 추측하지 말고 사용자가 바로 "
                            "답할 수 있는 구체적인 질문을 적는다. 계획서 요청을 실제 제작 완료나 "
                            "실물 시험 완료 기준으로 과도하게 판정하지 않는다. "
                            "질문은 사용자의 원래 요청을 완료하는 데 반드시 필요한 정보로만 제한한다. 원래 요청과 무관한 자동 복구, 내부 모니터링, 외부 API, 데이터 소스, 메시지 큐, 추가 시스템 구조를 새로 요구하지 않는다. 최종 답변에서 '미확인'으로 표시할 수 있는 정보는 사용자에게 묻지 말고 '사용자 확인 필요: 없음'으로 판정한다. "
                        ),
                    },
                    {"role": "user", "content": f"{review_input}\n\n/no_think"},
                ],
                think=False,
                stream=False,
                answer_prefix="검수 결과: ",
            )
            ensure_workflow_not_cancelled(task_id)
            review_answer = remove_thinking(review_response.message.content)
            if (
                not review_answer
                or not has_valid_review_contract(
                    review_answer,
                    successful_results,
                )
                or not is_korean_answer(review_answer)
            ):
                review_retry = optimized_chat(
                    model=MODEL_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "너는 안전·품질 검수 담당자다. 반드시 한국어로 답한다. "
                                "첫 줄에는 정확히 '검수 결과: 통과' 또는 "
                                "'검수 결과: 재작업' 중 하나만 쓴다. "
                                "그 다음 줄부터 오류, 근거 없는 수치, 예산 모순, "
                                "안전 누락을 짧고 구체적으로 설명한다. 역할이나 계획만 있고 "
                                "실제 산출물이 없으면 반드시 재작업으로 판정한다. 실제 제작·시험 "
                                "기록이 없으면 문서 검토와 실제 검증 완료를 구분한다. "
                                "둘째 줄은 반드시 '재작업 대상 ID: 없음' 또는 입력에 제시된 "
                                "정확한 직원 ID 목록으로 작성한다. "
                                "셋째 줄은 '사용자 확인 필요: 없음' 또는 사용자가 답해야 할 "
                                "구체적인 질문으로 작성한다. 직원이 고칠 누락과 외부 정보 부재를 "
                                "구분하고, 계획서 요청에 실제 제작 완료를 요구하지 않는다. "
                                "질문은 사용자의 원래 요청을 완료하는 데 반드시 필요한 정보로만 제한한다. 원래 요청과 무관한 자동 복구, 내부 모니터링, 외부 API, 데이터 소스, 메시지 큐, 추가 시스템 구조를 새로 요구하지 않는다. 최종 답변에서 '미확인'으로 표시할 수 있는 정보는 사용자에게 묻지 말고 '사용자 확인 필요: 없음'으로 판정한다. "
                                "사고 과정은 쓰지 않는다. /no_think"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                "다음 계획과 보고를 다시 검수하세요.\n\n"
                                f"{review_input[-12000:]}\n\n/no_think"
                            ),
                        },
                    ],
                    think=False,
                    stream=False,
                    answer_prefix="검수 결과: ",
                )
                ensure_workflow_not_cancelled(task_id)
                review_answer = remove_thinking(review_retry.message.content)
            if (
                not review_answer
                or not has_valid_review_contract(
                    review_answer,
                    successful_results,
                )
                or not is_korean_answer(review_answer)
            ):
                fallback_target_ids = ", ".join(
                    employee["id"]
                    for employee, _, _ in successful_results
                ) or "없음"
                review_answer = (
                    "검수 결과: 재작업\n"
                    f"재작업 대상 ID: {fallback_target_ids}\n"
                    "사용자 확인 필요: 없음\n"
                    "검수 담당자의 응답 형식이 올바르지 않아 자동 통과를 중단했습니다. "
                    "근거 수치와 안전 조건을 다시 확인해야 합니다."
                )
            review_answer = normalize_review_for_user_policy(
                review_answer,
                user_message["content"],
            )
            verdict = review_verdict(review_answer)
            finish_employee_result(
                review_result_id,
                "completed",
                output=review_answer,
            )
            first_review_id = add_review(
                task_id,
                reviewer["id"],
                1,
                verdict,
                review_answer,
            )
            first_target_ids = (
                review_target_employee_ids(review_answer, successful_results)
                if verdict == "rework_requested"
                else set()
            )
            add_review_targets(
                first_review_id,
                task_id,
                first_target_ids,
                "rework_requested",
            )
            add_handoff(
                task_id,
                reviewer["id"],
                ACTIVE_EMPLOYEE_ID,
                review_answer,
            )
            review_results.append((reviewer, review_answer, review_result_id))
            set_employee_activity(
                project_id,
                reviewer["id"],
                "completed" if verdict == "passed" else "reviewing",
                "검수 통과" if verdict == "passed" else "재작업 요청",
                task_id,
            )
        except WorkflowCancelled:
            raise
        except Exception as error:
            failed_employee_names.append(reviewer["name"])
            if review_result_id is not None:
                try:
                    finish_employee_result(
                        review_result_id,
                        "failed",
                        error=str(error),
                    )
                except sqlite3.Error:
                    pass
            try:
                add_review(task_id, reviewer["id"], 1, "failed", str(error))
            except sqlite3.Error:
                pass
            set_employee_activity(
                project_id,
                reviewer["id"],
                "error",
                workflow_error_detail("1차 검수", error)[:180],
                task_id,
            )

    first_review_results = list(review_results)
    review_targets_by_reviewer: dict[str, set[str]] = {}
    feedback_by_employee_id: dict[str, list[tuple[dict, str]]] = {}
    for reviewer, review_answer, _ in first_review_results:
        if review_verdict(review_answer) != "rework_requested":
            continue
        target_ids = review_target_employee_ids(
            review_answer,
            successful_results,
        )
        review_targets_by_reviewer[reviewer["id"]] = target_ids
        for target_id in target_ids:
            feedback_by_employee_id.setdefault(target_id, []).append(
                (reviewer, review_answer)
            )

    results_by_employee_id = {
        employee["id"]: (employee, answer, result_id)
        for employee, answer, result_id in successful_results
    }
    reworked_employee_ids: set[str] = set()
    for employee_id, feedback_items in feedback_by_employee_id.items():
        ensure_workflow_not_cancelled(task_id)
        original_result = results_by_employee_id.get(employee_id)
        if original_result is None:
            continue
        employee, first_answer, result_id = original_result
        rework_feedback = "\n\n".join(
            f"[{reviewer['name']} 1차 검수]\n{review_answer}"
            for reviewer, review_answer in feedback_items
        )
        rework_input = (
            f"[사용자 요청]\n{user_message['content']}\n\n"
            f"[승인된 팀장 계획]\n{manager_message['content']}\n\n"
            f"[팀 회의 기록]\n{meeting_context or '회의 미진행'}\n\n"
            f"[기존 담당 결과]\n{first_answer}\n\n"
            f"[1차 검수 수정 요청]\n{rework_feedback}\n\n"
            "지적된 항목만 고치는 데 그치지 말고 수정으로 영향을 받는 연결 부분도 "
            "다시 확인한 실제 재작업본을 제출한다."
        )
        output_instruction = build_employee_output_instruction(
            employee,
            employee["department_name"],
        )
        try:
            set_employee_activity(
                project_id,
                employee_id,
                "reworking",
                "1차 검수 의견 반영 중",
                task_id,
            )
            for reviewer, review_answer in feedback_items:
                add_handoff(
                    task_id,
                    reviewer["id"],
                    employee_id,
                    review_answer,
                )
            rework_response = optimized_chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            build_project_context(project)
                            + source_context
                            + memory_context
                            + build_employee_system_prompt(
                                employee,
                                employee["department_name"],
                            )
                            + output_instruction
                            + "1차 검수 의견을 해결하는 실제 재작업본을 작성한다. "
                            "자기 역할이나 수정 계획만 설명하지 않는다. "
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"{rework_input}\n\n/no_think",
                    },
                ],
                think=False,
                stream=False,
                answer_prefix="[담당 결과]\n",
            )
            ensure_workflow_not_cancelled(task_id)
            rework_answer = final_answer_with_retry(
                rework_response.message.content,
                rework_input,
                output_instruction=output_instruction,
                required_markers=EMPLOYEE_RESULT_MARKERS,
            )
            ensure_workflow_not_cancelled(task_id)
            if rework_answer == EMPTY_ANSWER_MESSAGE:
                raise OllamaResponseFormatError(
                    "재작업 응답이 역할 형식을 충족하지 못했습니다."
                )
            combined_output = (
                f"[초안]\n{first_answer}\n\n"
                f"[1차 검수 후 재작업본]\n{rework_answer}"
            )
            finish_employee_result(
                result_id,
                "completed",
                output=combined_output,
            )
            mark_review_targets_resubmitted(
                task_id,
                employee_id,
                rework_answer,
            )
            add_handoff(
                task_id,
                employee_id,
                ACTIVE_EMPLOYEE_ID,
                rework_answer,
            )
            results_by_employee_id[employee_id] = (
                employee,
                rework_answer,
                result_id,
            )
            reworked_employee_ids.add(employee_id)
            set_employee_activity(
                project_id,
                employee_id,
                "completed",
                "재작업 제출 완료",
                task_id,
            )
        except WorkflowCancelled:
            raise
        except Exception as error:
            failed_employee_names.append(employee["name"])
            set_employee_activity(
                project_id,
                employee_id,
                "error",
                workflow_error_detail("재작업", error)[:180],
                task_id,
            )

    successful_results = [
        results_by_employee_id[employee["id"]]
        for employee, _, _ in successful_results
    ]

    final_review_results: list[tuple[dict, str, int]] = []
    for reviewer, first_review_answer, review_result_id in first_review_results:
        ensure_workflow_not_cancelled(task_id)
        if review_verdict(first_review_answer) == "passed":
            final_review_results.append(
                (reviewer, first_review_answer, review_result_id)
            )
            continue

        original_target_ids = review_targets_by_reviewer.get(
            reviewer["id"],
            set(),
        )
        missing_rework_ids = original_target_ids - reworked_employee_ids
        current_reports = "\n\n".join(
            f"[{employee['name']} 보고 | ID: {employee['id']}]\n{answer}"
            for employee, answer, _ in successful_results
        ) or "직원 결과 없음"
        second_review_input = (
            f"[사용자 요청]\n{user_message['content']}\n\n"
            f"[팀장 계획]\n{manager_message['content']}\n\n"
            f"[팀 회의 기록]\n{meeting_context or '회의 미진행'}\n\n"
            f"[1차 검수]\n{first_review_answer}\n\n"
            f"[재작업 후 전체 직원 결과]\n{current_reports}\n\n"
            "1차 검수에서 지적한 문제가 실제로 해결됐는지 다시 확인한다. "
            "새로운 치명적 오류가 발견되면 해당 직원 ID를 대상으로 지정한다."
        )
        try:
            set_employee_activity(
                project_id,
                reviewer["id"],
                "reviewing",
                "2차 검수 중",
                task_id,
            )
            if missing_rework_ids:
                missing_ids = ", ".join(sorted(missing_rework_ids))
                second_review_answer = (
                    "검수 결과: 재작업\n"
                    f"재작업 대상 ID: {missing_ids}\n"
                    "사용자 확인 필요: 없음\n"
                    "2차 검수에 필요한 재작업 결과가 제출되지 않아 통과할 수 없습니다."
                )
            else:
                for employee, employee_answer, _ in successful_results:
                    if employee["id"] in original_target_ids:
                        add_handoff(
                            task_id,
                            employee["id"],
                            reviewer["id"],
                            employee_answer,
                        )
                add_handoff(
                    task_id,
                    ACTIVE_EMPLOYEE_ID,
                    reviewer["id"],
                    second_review_input,
                )
                second_review_response = optimized_chat(
                    model=MODEL_NAME,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                build_project_context(project)
                                + source_context
                                + memory_context
                                + build_employee_system_prompt(
                                    reviewer,
                                    reviewer["department_name"],
                                )
                                + "너는 1차 검수를 수행했던 동일한 검수 담당자다. "
                                "재작업본이 기존 지적사항을 실제로 해결했는지 2차 검수한다. "
                                "첫 줄은 '검수 결과: 통과' 또는 '검수 결과: 재작업'으로 쓴다. "
                                "둘째 줄은 통과라면 '재작업 대상 ID: 없음', 재작업이라면 "
                                "입력에 표시된 정확한 직원 ID를 쓴다. 문서 검토와 실제 장치 "
                                "시험 완료를 구분하고, 해결된 항목과 남은 항목을 구체적으로 쓴다. "
                                "셋째 줄은 반드시 '사용자 확인 필요: 없음' 또는 "
                                "'사용자 확인 필요: 질문 내용'으로 쓴다. 직원 재작업으로 해결 가능한 "
                                "누락과 대회 규정, 목표 성능, 실제 보유 부품처럼 사용자 정보가 "
                                "필요한 항목을 구분한다. 사용자 정보가 없으면 같은 재작업을 반복시키지 "
                                "말고 구체적인 질문을 남긴다. 계획서 요청에는 실제 제작 완료를 "
                                "통과 조건으로 요구하지 않는다. "
                                "질문은 사용자의 원래 요청을 완료하는 데 반드시 필요한 정보로만 제한한다. 원래 요청과 무관한 자동 복구, 내부 모니터링, 외부 API, 데이터 소스, 메시지 큐, 추가 시스템 구조를 새로 요구하지 않는다. 최종 답변에서 '미확인'으로 표시할 수 있는 정보는 사용자에게 묻지 말고 '사용자 확인 필요: 없음'으로 판정한다. "
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"{second_review_input}\n\n/no_think",
                        },
                    ],
                    think=False,
                    stream=False,
                    answer_prefix="검수 결과: ",
                )
                ensure_workflow_not_cancelled(task_id)
                second_review_answer = remove_thinking(
                    second_review_response.message.content
                )
                if (
                    not second_review_answer
                    or not has_valid_review_contract(
                        second_review_answer,
                        successful_results,
                    )
                    or not is_korean_answer(second_review_answer)
                ):
                    second_review_retry = optimized_chat(
                        model=MODEL_NAME,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "너는 2차 안전·품질 검수 담당자다. 반드시 한국어로 답한다. "
                                    "첫 줄은 '검수 결과: 통과' 또는 '검수 결과: 재작업', "
                                    "둘째 줄은 '재작업 대상 ID: 없음' 또는 정확한 직원 ID로 쓴다. "
                                    "셋째 줄은 '사용자 확인 필요: 없음' 또는 사용자가 답해야 할 "
                                    "구체적인 질문으로 쓴다. 직원 누락과 외부 정보 부재를 구분한다. "
                                    "질문은 사용자의 원래 요청을 완료하는 데 반드시 필요한 정보로만 제한한다. 원래 요청과 무관한 자동 복구, 내부 모니터링, 외부 API, 데이터 소스, 메시지 큐, 추가 시스템 구조를 새로 요구하지 않는다. 최종 답변에서 '미확인'으로 표시할 수 있는 정보는 사용자에게 묻지 말고 '사용자 확인 필요: 없음'으로 판정한다. "
                                    "1차 지적이 해결됐는지 근거와 함께 판정하고 사고 과정은 쓰지 않는다. "
                                    "/no_think"
                                ),
                            },
                            {
                                "role": "user",
                                "content": (
                                    "다음 재작업 결과를 2차 검수하세요.\n\n"
                                    f"{second_review_input[-14000:]}\n\n/no_think"
                                ),
                            },
                        ],
                        think=False,
                        stream=False,
                        answer_prefix="검수 결과: ",
                    )
                    ensure_workflow_not_cancelled(task_id)
                    second_review_answer = remove_thinking(
                        second_review_retry.message.content
                    )
                if (
                    not second_review_answer
                    or not has_valid_review_contract(
                        second_review_answer,
                        successful_results,
                    )
                    or not is_korean_answer(second_review_answer)
                ):
                    fallback_ids = ", ".join(sorted(original_target_ids))
                    second_review_answer = (
                        "검수 결과: 재작업\n"
                        f"재작업 대상 ID: {fallback_ids}\n"
                        "사용자 확인 필요: 없음\n"
                        "2차 검수 응답 형식을 확인하지 못해 자동 통과를 중단했습니다."
                    )

            second_review_answer = normalize_review_for_user_policy(
                second_review_answer,
                user_message["content"],
            )
            second_verdict = review_verdict(second_review_answer)
            second_target_ids = (
                original_target_ids
                if second_verdict == "passed"
                else review_target_employee_ids(
                    second_review_answer,
                    successful_results,
                ) or original_target_ids
            )
            combined_review_output = (
                f"[1차 검수]\n{first_review_answer}\n\n"
                f"[2차 검수]\n{second_review_answer}"
            )
            finish_employee_result(
                review_result_id,
                "completed",
                output=combined_review_output,
            )
            second_review_id = add_review(
                task_id,
                reviewer["id"],
                2,
                second_verdict,
                second_review_answer,
            )
            add_review_targets(
                second_review_id,
                task_id,
                second_target_ids,
                "passed" if second_verdict == "passed" else "unresolved",
            )
            add_handoff(
                task_id,
                reviewer["id"],
                ACTIVE_EMPLOYEE_ID,
                second_review_answer,
            )
            final_review_results.append(
                (reviewer, second_review_answer, review_result_id)
            )

            if second_verdict == "passed":
                set_employee_activity(
                    project_id,
                    reviewer["id"],
                    "completed",
                    "2차 검수 통과",
                    task_id,
                )
                for employee_id in original_target_ids:
                    if employee_id not in unresolved_review_employee_ids:
                        set_employee_activity(
                            project_id,
                            employee_id,
                            "completed",
                            "2차 검수 통과",
                            task_id,
                        )
            else:
                unresolved_review_employee_ids.update(second_target_ids)
                set_employee_activity(
                    project_id,
                    reviewer["id"],
                    "error",
                    "2차 검수 미통과",
                    task_id,
                )
                for employee_id in second_target_ids:
                    set_employee_activity(
                        project_id,
                        employee_id,
                        "error",
                        "2차 검수 미통과",
                        task_id,
                    )
        except WorkflowCancelled:
            raise
        except Exception as error:
            failed_employee_names.append(reviewer["name"])
            unresolved_review_employee_ids.update(original_target_ids)
            fallback_ids = ", ".join(sorted(original_target_ids)) or "없음"
            error_detail = workflow_error_detail("2차 검수", error)
            failed_second_review = (
                "검수 결과: 재작업\n"
                f"재작업 대상 ID: {fallback_ids}\n"
                "사용자 확인 필요: 없음\n"
                f"{error_detail[:180]}"
            )
            try:
                finish_employee_result(
                    review_result_id,
                    "completed",
                    output=(
                        f"[1차 검수]\n{first_review_answer}\n\n"
                        f"[2차 검수]\n{failed_second_review}"
                    ),
                )
                failed_review_id = add_review(
                    task_id,
                    reviewer["id"],
                    2,
                    "failed",
                    failed_second_review,
                )
                add_review_targets(
                    failed_review_id,
                    task_id,
                    original_target_ids,
                    "unresolved",
                )
            except sqlite3.Error:
                pass
            final_review_results.append(
                (reviewer, failed_second_review, review_result_id)
            )
            set_employee_activity(
                project_id,
                reviewer["id"],
                "error",
                error_detail[:180],
                task_id,
            )

    ensure_workflow_not_cancelled(task_id)
    review_results = final_review_results
    missing_required_review = bool(successful_results) and not review_results
    has_unresolved_reviews = missing_required_review or bool(
        unresolved_review_employee_ids
    ) or any(
        review_verdict(answer) != "passed"
        for _, answer, _ in review_results
    )
    clarification_items = [
        (reviewer, review_clarification_questions(answer, user_message["content"]))
        for reviewer, answer, _ in review_results
        if review_verdict(answer) != "passed"
        and review_clarification_questions(answer, user_message["content"])
    ]
    waiting_for_user = bool(clarification_items)
    if waiting_for_user:
        clarification_text = "\n\n".join(
            f"[{reviewer['name']} 확인 요청]\n{questions}"
            for reviewer, questions in clarification_items
        )
        create_or_get_clarification_request(
            project_id,
            task_id,
            clarification_items[0][0]["id"],
            clarification_text,
        )
        update_task_control_state(task_id, "waiting_for_user")
    pre_report_failures = sorted(set(failed_employee_names))
    if has_unresolved_reviews or pre_report_failures:
        unresolved_names = ", ".join(
            results_by_employee_id[employee_id][0]["name"]
            for employee_id in sorted(unresolved_review_employee_ids)
            if employee_id in results_by_employee_id
        )
        blocking_reasons: list[str] = []
        if missing_required_review:
            blocking_reasons.append("저장된 최종 검수 결과 없음")
        if unresolved_names:
            blocking_reasons.append(f"추가 수정 필요: {unresolved_names}")
        if pre_report_failures:
            blocking_reasons.append(
                f"실행 오류 확인 필요: {', '.join(pre_report_failures)}"
            )
        add_message(
            project_id,
            "assistant",
            (
                "검수와 업무 실행 조건을 모두 충족하지 못해 최종 보고서 생성을 "
                "보류했습니다.\n\n"
                + "\n".join(f"- {reason}" for reason in blocking_reasons)
                + "\n\n"
                + (
                    "검수 담당자가 사용자 확인이 필요한 정보를 질문으로 정리했습니다. "
                    "대화 화면의 보완 질문에 답하면 같은 프로젝트에서 후속 업무를 이어갑니다."
                    if waiting_for_user
                    else "검수 기록과 재작업본을 확인한 뒤 새 업무로 보완 요청해주세요."
                )
            ),
            ACTIVE_EMPLOYEE_ID,
        )

    return ReviewExecutionResult(
        successful_results=successful_results,
        review_results=review_results,
        failed_employee_names=failed_employee_names,
        unresolved_review_employee_ids=unresolved_review_employee_ids,
        missing_required_review=missing_required_review,
        has_unresolved_reviews=has_unresolved_reviews,
        waiting_for_user=waiting_for_user,
        pre_report_failures=pre_report_failures,
    )

