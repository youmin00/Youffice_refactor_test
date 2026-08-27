"""계획 승인 전, 두 팀원의 짧은 의견을 받아 유키가 정리하는 흐름입니다."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from typing import Any

from conversation.employee_prompts import build_employee_system_prompt
from conversation.ollama_client import MODEL_NAME, optimized_chat
from conversation.prompts import build_project_context
from conversation.response_validator import remove_thinking
from database import add_message, list_employee_activities, set_employee_activity
from workflow.assignment import ACTIVE_EMPLOYEE_ID, employee_workstream
from workflow.errors import workflow_error_detail


_CONSULTATION_LOCK = threading.Lock()
_RUNNING_PROJECT_IDS: set[int] = set()
_RESEARCH_SIGNALS = ("검색", "찾아", "가격", "구매", "비교", "자료", "디바이스마트")
_TECHNICAL_SIGNALS = (
    "부품",
    "모터",
    "센서",
    "회로",
    "전원",
    "아두이노",
    "기구",
    "카메라",
    "코드",
    "프로그램",
    "앱",
    "ai",
)


def select_team_consultants(
    project: dict[str, Any],
    user_request: str,
    supporting_employees: list[tuple[dict, str]],
) -> list[tuple[dict, str]]:
    """요청 성격에 따라 서로 다른 역할의 의견 담당 두 명을 고릅니다."""

    request_text = " ".join(
        (
            str(project.get("field") or ""),
            str(project.get("goal") or ""),
            user_request,
        )
    ).lower()
    if any(signal in request_text for signal in _RESEARCH_SIGNALS):
        preferred_workstreams = ("planning", "review", "technical", "general")
    elif any(signal in request_text for signal in _TECHNICAL_SIGNALS):
        preferred_workstreams = ("technical", "planning", "review", "general")
    else:
        preferred_workstreams = ("planning", "technical", "review", "general")

    ranked_employees: list[tuple[int, int, tuple[dict, str]]] = []
    for index, employee_data in enumerate(supporting_employees):
        employee, department = employee_data
        workstream = employee_workstream(employee, department)
        if workstream in {"manager", "memory", "report"}:
            continue
        try:
            rank = preferred_workstreams.index(workstream)
        except ValueError:
            rank = len(preferred_workstreams)
        ranked_employees.append((rank, index, employee_data))

    ranked_employees.sort(key=lambda item: (item[0], item[1]))
    return [employee_data for _, _, employee_data in ranked_employees[:2]]


def is_team_consultation_running(project_id: int) -> bool:
    """같은 프로젝트에서 의견 요청이 겹치지 않도록 현재 실행 상태를 확인합니다."""

    with _CONSULTATION_LOCK:
        return project_id in _RUNNING_PROJECT_IDS


def recover_stale_team_consultation_activities(project_id: int) -> None:
    """서버가 중간에 종료된 뒤 남은 의견 요청 상태만 대기 상태로 되돌립니다."""

    if is_team_consultation_running(project_id):
        return
    for activity in list_employee_activities(project_id):
        detail = str(activity.get("detail") or "")
        if detail.startswith("팀 의견") and activity.get("status") in {"working", "assigned"}:
            set_employee_activity(
                project_id,
                activity["employee_id"],
                "waiting",
                "팀 의견 요청이 중단되어 다시 요청 가능",
            )


def _clean_answer(raw_answer: object, fallback: str) -> str:
    answer = remove_thinking(str(raw_answer or "")).strip()
    return answer if answer else fallback


def _consult_employee(
    project_id: int,
    project: dict[str, Any],
    user_request: str,
    employee: dict[str, Any],
    department: str,
) -> tuple[dict[str, Any], str, str | None]:
    """한 명의 의견을 받고, 실패는 해당 직원 상태에만 남깁니다."""

    try:
        response = optimized_chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        build_project_context(project)
                        + build_employee_system_prompt(employee, department)
                        + "\n지금은 실행 업무가 아니라 팀 의견을 묻는 단계다. "
                        "사용자와 유키가 이미 정한 내용은 맞다고 다시 길게 설명하지 않는다. "
                        "네 전문 역할에서만, 학생이 다음 선택 전에 놓치기 쉬운 새 쟁점·위험·대안 중 실제로 도움이 되는 것을 찾는다. "
                        "새 쟁점마다 '무엇인지 → 왜 중요한지 → 지금 어떻게 확인하거나 결정하면 되는지'를 쉬운 말로 풀어 설명한다. "
                        "답변은 '[이미 정한 내용]', '[새로 살펴볼 점]', '[권장 방향과 이유]', '[확인 방법]' 네 부분으로 작성한다. "
                        "[이미 정한 내용]은 한 문장 이내로만 적고, [새로 살펴볼 점]에는 서로 다른 두 가지 관점을 담는다. "
                        "새로 보탤 사실이 없으면 억지로 바꾸지 말고 '새 쟁점 없음'과 그 이유를 쓴다. "
                        "확인하지 않은 가격, 재고, 호환성, 기술 사실을 만들어내지 않는다."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"사용자와 유키가 나눈 현재 요청은 다음과 같다.\n{user_request}\n\n"
                        "아래 대화에는 이미 정한 내용과 아직 결정하지 않은 내용이 함께 있을 수 있다. "
                        "이미 정한 내용을 반복하지 말고, 이 학생이 다음 선택을 하기 전에 새로 생각해야 할 점을 구체적으로 남겨줘. /no_think"
                    ),
                },
            ],
            think=False,
            stream=False,
            answer_prefix="",
        )
        answer = _clean_answer(
            response.message.content,
            "[이미 정한 내용]\n현재 대화의 결정은 그대로 참고합니다.\n"
            "[새로 살펴볼 점]\n의견을 완성하지 못해 새 쟁점을 확인하지 못했습니다.\n"
            "[권장 방향과 이유]\n유키와 현재 결정의 이유를 다시 확인해 주세요.\n"
            "[확인 방법]\n현재 정보가 부족합니다.",
        )
        add_message(project_id, "assistant", answer, employee["id"])
        set_employee_activity(
            project_id,
            employee["id"],
            "completed",
            "팀 의견 전달 완료",
        )
        return employee, answer, None
    except Exception as error:  # 백그라운드 한 명의 실패가 다른 의견을 막지 않게 합니다.
        error_detail = workflow_error_detail("팀 의견", error)
        print(f"[{employee.get('name')}] {error_detail}", flush=True)
        set_employee_activity(
            project_id,
            employee["id"],
            "error",
            error_detail[:180],
        )
        return employee, "", error_detail


def _summarize_consultation(
    project_id: int,
    project: dict[str, Any],
    user_request: str,
    manager_profile: dict[str, Any],
    manager_department: str,
    opinions: list[tuple[dict[str, Any], str]],
) -> None:
    """유키가 팀원의 원문을 복사하지 않고, 다음 선택을 쉽게 정리합니다."""

    opinion_context = "\n\n".join(
        f"[{employee['name']} 의견]\n{answer}"
        for employee, answer in opinions
    ) or "받을 수 있는 팀 의견이 없습니다."
    try:
        response = optimized_chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        build_project_context(project)
                        + build_employee_system_prompt(manager_profile, manager_department)
                        + "\n두 팀원의 의견을 받은 유키다. 실행 계획을 만들지 않는다. "
                        "학생이 이해하고 스스로 고를 수 있도록 충분히 설명하되, 직원 원문이나 이미 정한 결론을 반복하지 않는다. "
                        "답변은 '[이미 정한 내용]', '[팀이 새로 찾아낸 점]', '[유키의 추천과 이유]', '[다음 한 가지]', '[아직 확인할 점]' 다섯 부분으로 작성한다. "
                        "[이미 정한 내용]은 두 문장 이내로 현재 상태만 확인한다. [팀이 새로 찾아낸 점]에는 두 직원이 덧붙인 서로 다른 관점을 한 항목씩 쓰고, 왜 중요한지 쉬운 말로 설명한다. "
                        "[유키의 추천과 이유]에는 지금 추천하는 방향과 그 이유·주의점을 풀어 쓴다. [다음 한 가지]에는 학생이 답할 질문 또는 확인할 행동을 하나만 제시한다. "
                        "확인되지 않은 사실은 [아직 확인할 점]에 남기고, 새 내용이 없으면 없다고 솔직히 말한다."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"현재 사용자 요청:\n{user_request}\n\n"
                        f"팀원 의견:\n{opinion_context}\n\n/no_think"
                    ),
                },
            ],
            think=False,
            stream=False,
            answer_prefix="",
        )
        answer = _clean_answer(
            response.message.content,
            "[이미 정한 내용]\n현재 결정은 그대로 유지합니다.\n"
            "[팀이 새로 찾아낸 점]\n팀 의견을 모두 정리하지 못해 새 쟁점을 확인하지 못했습니다.\n"
            "[유키의 추천과 이유]\n확인된 내용부터 한 가지씩 정하는 것을 추천해요.\n"
            "[다음 한 가지]\n지금 가장 중요한 조건을 한 문장으로 알려주세요.\n"
            "[아직 확인할 점]\n현재 정보가 부족합니다.",
        )
        add_message(project_id, "assistant", answer, manager_profile["id"])
        set_employee_activity(
            project_id,
            manager_profile["id"],
            "completed",
            "팀 의견 정리 완료",
        )
    except Exception as error:
        error_detail = workflow_error_detail("팀 의견 정리", error)
        print(f"[{manager_profile.get('name')}] {error_detail}", flush=True)
        set_employee_activity(
            project_id,
            manager_profile["id"],
            "error",
            error_detail[:180],
        )
        add_message(
            project_id,
            "assistant",
            "팀 의견을 정리하는 중 문제가 생겼어요. 오피스 상태를 확인한 뒤 다시 요청해 주세요.",
            manager_profile["id"],
        )


def _run_team_consultation_background(
    project_id: int,
    project: dict[str, Any],
    user_request: str,
    manager_profile: dict[str, Any],
    manager_department: str,
    consultants: list[tuple[dict, str]],
) -> None:
    try:
        opinions: list[tuple[dict[str, Any], str]] = []
        with ThreadPoolExecutor(max_workers=len(consultants)) as executor:
            futures = [
                executor.submit(
                    _consult_employee,
                    project_id,
                    project,
                    user_request,
                    employee,
                    department,
                )
                for employee, department in consultants
            ]
            for future in as_completed(futures):
                employee, answer, error = future.result()
                if error is None and answer:
                    opinions.append((employee, answer))
        _summarize_consultation(
            project_id,
            project,
            user_request,
            manager_profile,
            manager_department,
            opinions,
        )
    finally:
        with _CONSULTATION_LOCK:
            _RUNNING_PROJECT_IDS.discard(project_id)


def start_team_consultation_background(
    project_id: int,
    project: dict[str, Any],
    user_request: str,
    manager_profile: dict[str, Any],
    manager_department: str,
    supporting_employees: list[tuple[dict, str]],
) -> tuple[bool, str]:
    """관련 직원 두 명의 짧은 의견 요청을 실제 백그라운드 작업으로 시작합니다."""

    consultants = select_team_consultants(project, user_request, supporting_employees)
    if len(consultants) < 2:
        return False, "팀 의견을 받으려면 기획·기술 등 활성 직원이 두 명 이상 필요합니다."

    with _CONSULTATION_LOCK:
        if project_id in _RUNNING_PROJECT_IDS:
            return False, "이미 팀 의견을 받고 있습니다. 잠시 후 대화에 정리 결과가 도착합니다."
        try:
            _RUNNING_PROJECT_IDS.add(project_id)
            set_employee_activity(project_id, manager_profile["id"], "working", "팀 의견 정리 중")
            for employee, _ in consultants:
                set_employee_activity(project_id, employee["id"], "working", "팀 의견 검토 중")
        except Exception as error:
            _RUNNING_PROJECT_IDS.discard(project_id)
            return False, f"팀 의견 요청을 시작하지 못했습니다: {error}"

    thread = threading.Thread(
        target=_run_team_consultation_background,
        kwargs={
            "project_id": project_id,
            "project": dict(project),
            "user_request": user_request,
            "manager_profile": dict(manager_profile),
            "manager_department": manager_department,
            "consultants": [(dict(employee), department) for employee, department in consultants],
        },
        daemon=True,
        name=f"youffice-consultation-{project_id}",
    )
    thread.start()
    consultant_names = "·".join(employee["name"] for employee, _ in consultants)
    return True, f"{consultant_names}에게 의견을 요청했습니다. 오피스에서 진행 상태를 확인할 수 있습니다."
