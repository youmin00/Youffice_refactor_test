"""중단된 YOUFFICE 업무와 보완 질문 흐름을 복구합니다."""

import re

from database import (
    add_message,
    answer_clarification_request,
    create_or_get_clarification_request,
    create_task_control,
    get_pending_clarification_request,
    get_task_control,
    get_task_for_source_message,
    get_team_task,
    list_messages,
    list_reviews,
    list_team_tasks,
    update_task_control_state,
)
from workflow.assignment import ACTIVE_EMPLOYEE_ID
from workflow.engine import start_team_workflow_background
from workflow.review import review_clarification_questions


def ensure_failed_task_clarification(
    project_id: int,
    latest_task: dict | None,
) -> dict | None:
    """기존 2차 검수 실패도 사용자 보완 질문 흐름으로 안전하게 복구합니다."""

    if latest_task is None or latest_task["status"] != "failed":
        return get_pending_clarification_request(project_id)
    existing_request = get_pending_clarification_request(project_id)
    if existing_request is not None:
        return existing_request
    control = get_task_control(latest_task["id"])
    if control is not None and control["state"] in {"cancel_requested", "cancelled"}:
        return None
    failed_second_reviews = [
        review
        for review in list_reviews(latest_task["id"])
        if review["review_round"] == 2 and review["verdict"] != "passed"
    ]
    clarification_items = [
        (review, review_clarification_questions(review["feedback"], latest_task.get("request", "")))
        for review in failed_second_reviews
        if review_clarification_questions(review["feedback"], latest_task.get("request", ""))
    ]
    if not clarification_items:
        return None
    questions = "\n\n".join(
        f"[검수 담당 확인 요청]\n{question}"
        for _, question in clarification_items
    )
    request = create_or_get_clarification_request(
        project_id,
        latest_task["id"],
        clarification_items[0][0]["reviewer_employee_id"],
        questions,
    )
    if control is None:
        create_task_control(latest_task["id"])
    update_task_control_state(latest_task["id"], "waiting_for_user")
    return request


def employee_names_in_text(text: str, employees: list[dict]) -> str:
    """사용자 화면에 내부 직원 ID 대신 직원 이름을 표시합니다."""

    readable = text
    for employee in sorted(employees, key=lambda item: len(item["id"]), reverse=True):
        readable = readable.replace(employee["id"], employee["name"])
    return re.sub(r"^\s*\*{2,}\s*$", "", readable, flags=re.MULTILINE).strip()


def resume_workflow_from_clarification(
    clarification: dict,
    answer: str,
    project: dict,
    manager_profile: dict,
    manager_department: str,
    supporting_employees: list[tuple[dict, str]],
) -> tuple[bool, str]:
    """사용자 답변을 원래 요청에 연결한 후속 팀 업무를 시작합니다."""

    normalized_answer = answer.strip()
    if not normalized_answer:
        return False, "보완 질문에 대한 답변을 입력해주세요."
    running_task = next(
        (
            task
            for task in list_team_tasks(project["id"], limit=100)
            if task["status"] == "running"
        ),
        None,
    )
    if running_task is not None:
        return False, f"현재 팀 업무 #{running_task['id']}가 끝난 뒤 다시 시도해주세요."
    original_task = get_team_task(clarification["task_id"])
    if original_task is None:
        return False, "원래 업무 기록을 찾지 못했습니다."

    followup_content = (
        f"[이전 업무 #{original_task['id']} 보완 답변]\n"
        f"원래 요청:\n{original_task['request']}\n\n"
        f"검수 담당 질문:\n{clarification['questions']}\n\n"
        f"사용자 답변:\n{normalized_answer}\n\n"
        "위 답변을 확정 정보로 반영하고, 모르는 항목은 합리적인 기본 가정을 명시한 뒤 "
        "이전 검수의 남은 항목을 해결하여 완성된 산출물과 최종 보고서를 작성해주세요."
    )
    source_message_id = add_message(project["id"], "user", followup_content)
    manager_content = (
        "[업무 접수]\n이전 검수에서 멈춘 업무를 사용자 보완 답변과 함께 다시 접수했습니다.\n\n"
        "[요청 분석]\n사용자가 제공한 확정 정보와 기본 가정 허용 범위를 구분해 남은 항목만 보완합니다.\n\n"
        "[직원별 업무 배정]\n관련 기획·기술 담당자는 답변을 반영해 산출물을 수정하고, "
        "검수 담당자는 이전 미확인 항목이 해결됐는지 다시 확인하며, 보고 담당자는 통과한 결과만 종합합니다.\n\n"
        "[작업 순서]\n보완 정보 반영 → 담당 결과 작성 → 팀 회의 → 검수·재작업 → 최종 보고 순서로 진행합니다.\n\n"
        "[완료 기준]\n질문의 각 항목이 답변 또는 명시된 기본 가정으로 추적 가능하고, 검수 통과 후 최종 보고서가 생성되어야 합니다."
    )
    manager_message_id = add_message(
        project["id"],
        "assistant",
        manager_content,
        ACTIVE_EMPLOYEE_ID,
    )
    user_message = {
        "message_id": source_message_id,
        "role": "user",
        "content": followup_content,
    }
    manager_message = {
        "message_id": manager_message_id,
        "role": "assistant",
        "content": manager_content,
        "employee_id": ACTIVE_EMPLOYEE_ID,
        "employee_name": manager_profile["name"],
    }
    workflow_started, workflow_message = start_team_workflow_background(
        project["id"],
        project,
        user_message,
        manager_message,
        manager_profile,
        manager_department,
        supporting_employees,
        list_messages(project["id"]),
    )
    if not workflow_started:
        return False, workflow_message
    followup_task = get_task_for_source_message(project["id"], source_message_id)
    if followup_task is not None:
        answer_clarification_request(
            clarification["id"],
            normalized_answer,
            followup_task["id"],
        )
        update_task_control_state(clarification["task_id"], "active")
    return True, "보완 답변을 반영한 후속 팀 업무를 시작했습니다."
