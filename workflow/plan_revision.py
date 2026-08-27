"""사용자 피드백을 반영해 팀장 작업 계획을 다시 생성합니다."""

from __future__ import annotations

from dataclasses import dataclass

from conversation.employee_prompts import build_employee_system_prompt
from conversation.ollama_client import (
    MODEL_NAME,
    OllamaResponseFormatError,
    describe_ollama_failure,
    optimized_chat,
)
from conversation.prompts import build_project_context, build_source_context
from conversation.response_formats import MANAGER_PLAN_MARKERS
from conversation.response_recovery import EMPTY_ANSWER_MESSAGE, final_answer_with_retry
from database import add_message, update_approval
from workflow.assignment import (
    ACTIVE_EMPLOYEE_ID,
    build_manager_delegation_instruction,
    normalize_manager_plan_project_name,
)


@dataclass(frozen=True)
class PlanRevisionResult:
    """팀장 계획 수정 결과와 새 메시지 ID."""

    succeeded: bool
    content: str = ""
    message_id: int | None = None
    error: str = ""


def revise_manager_plan(
    *,
    approval: dict,
    project: dict,
    sources: list[dict],
    user_message: dict,
    manager_profile: dict,
    manager_department: str,
    supporting_employees: list[tuple[dict, str]],
    feedback: str,
) -> PlanRevisionResult:
    """승인 대기 계획을 사용자 의견에 맞게 재생성하고 저장합니다."""

    cleaned_feedback = feedback.strip()
    if not cleaned_feedback:
        return PlanRevisionResult(False, error="수정할 내용을 입력해주세요.")

    try:
        delegation_instruction = build_manager_delegation_instruction(
            supporting_employees
        )
        update_approval(
            approval["id"],
            "revision_requested",
            user_feedback=cleaned_feedback,
        )
        revision_response = optimized_chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        build_project_context(project)
                        + build_source_context(sources)
                        + build_employee_system_prompt(
                            manager_profile,
                            manager_department,
                            supporting_employees,
                        )
                        + "사용자의 수정 의견을 반영해 승인받을 작업 계획을 다시 작성한다. "
                        + delegation_instruction
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"원래 요청:\n{user_message['content']}\n\n"
                        f"현재 계획:\n{approval['plan_content']}\n\n"
                        f"사용자 수정 의견:\n{cleaned_feedback}\n\n/no_think"
                    ),
                },
            ],
            think=False,
            stream=False,
            answer_prefix="[업무 접수]\n",
        )
        revised_plan = final_answer_with_retry(
            revision_response.message.content,
            (
                f"원래 요청:\n{user_message['content']}\n\n"
                f"현재 계획:\n{approval['plan_content']}\n\n"
                f"사용자 수정 의견:\n{cleaned_feedback}"
            ),
            output_instruction=delegation_instruction,
            required_markers=MANAGER_PLAN_MARKERS,
        )
        if revised_plan == EMPTY_ANSWER_MESSAGE:
            raise OllamaResponseFormatError(
                "수정된 업무 배정 계획의 형식을 확인하지 못했습니다."
            )
        revised_plan = normalize_manager_plan_project_name(
            revised_plan,
            project["name"],
        )
        revised_message_id = add_message(
            project["id"],
            "assistant",
            revised_plan,
            ACTIVE_EMPLOYEE_ID,
        )
        update_approval(
            approval["id"],
            "pending",
            plan_content=revised_plan,
            user_feedback=cleaned_feedback,
            increment_revision=True,
        )
    except Exception as error:
        failure = describe_ollama_failure(error)
        return PlanRevisionResult(
            False,
            error=(
                failure.message
                if failure is not None
                else f"계획을 수정하지 못했습니다: {error}"
            ),
        )

    return PlanRevisionResult(
        True,
        content=revised_plan,
        message_id=revised_message_id,
    )
