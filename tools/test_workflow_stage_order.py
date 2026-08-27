"""팀 회의 → 검수 → 최종 보고 단계 순서와 차단 조건 회귀 검사입니다."""

from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
from itertools import count
from pathlib import Path
from types import SimpleNamespace
import sys
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import workflow.engine as engine  # noqa: E402
import workflow.employee_execution as employee_execution  # noqa: E402
import workflow.final_report_execution as final_report_execution  # noqa: E402
import workflow.meeting as meeting  # noqa: E402
import workflow.review_execution as review_execution  # noqa: E402


EMPLOYEE_RESULT = (
    "[담당 결과]\n요청한 산출물을 작성했습니다.\n\n"
    "[근거·가정]\n승인된 계획을 기준으로 작성했습니다.\n\n"
    "[미확인 사항]\n없음\n\n"
    "[다음 직원 전달]\n검수 담당자에게 전달합니다."
)
MEETING_OPINION = (
    "[확인한 연결점]\n두 직원 결과가 연결됩니다.\n\n"
    "[쟁점·위험]\n추가 위험은 없습니다.\n\n"
    "[제안]\n현재 결과를 함께 검수합니다.\n\n"
    "[합의 여부]\n동의"
)
MEETING_CONCLUSION = (
    "[회의 결론]\n두 결과를 함께 검수합니다.\n\n"
    "[합의 사항]\n직원 결과를 통합합니다.\n\n"
    "[조정 사항]\n없음\n\n"
    "[검수 전달]\n근거와 누락 여부를 확인합니다."
)
PASSED_REVIEW = (
    "검수 결과: 통과\n"
    "재작업 대상 ID: 없음\n"
    "사용자 확인 필요: 없음\n"
    "회의 결론과 직원 산출물이 일치합니다."
)
REWORK_REVIEW = (
    "검수 결과: 재작업\n"
    "재작업 대상 ID: planner\n"
    "사용자 확인 필요: 없음\n"
    "기획 결과의 근거를 보완해야 합니다."
)
FINAL_REPORT = "[최종 결론]\n검수를 통과한 결과만 정리한 최종 보고서입니다."


def _employee(employee_id: str, name: str) -> dict:
    return {
        "id": employee_id,
        "name": name,
        "title": "담당자",
        "role_description": "배정된 업무를 수행합니다.",
        "department_name": "테스트팀",
    }


def _run_workflow(
    *,
    fail_review: bool,
    fail_conclusion: bool = False,
    request_rework: bool = False,
    fail_report: bool = False,
    fail_employee: bool = False,
) -> dict:
    events: list[str] = []
    task_statuses: list[str] = []
    meeting_turn_types: list[str] = []
    employee_inputs: dict[str, str] = {}
    assistant_messages: list[str] = []
    rework_inputs: list[str] = []
    report_approvals: list[tuple] = []
    result_ids = count(100)
    review_call_count = 0

    workers = [
        (_employee("planner", "기획"), "기획팀"),
        (_employee("builder", "제작"), "기술팀"),
    ]
    reviewer = _employee("reviewer", "검수")
    reporter = _employee("reporter", "보고")
    supporting_employees = workers + [
        (reviewer, "검수팀"),
        (reporter, "보고팀"),
    ]

    def workstream(employee: dict, _department: str) -> str:
        return {
            "planner": "planning",
            "builder": "technical",
            "reviewer": "review",
            "reporter": "report",
        }[employee["id"]]

    def optimized_chat(**kwargs):
        nonlocal review_call_count
        prefix = kwargs.get("answer_prefix")
        messages = kwargs.get("messages") or []
        if messages:
            user_content = str(messages[-1].get("content") or "")
            if "[1차 검수 수정 요청]" in user_content:
                rework_inputs.append(user_content)
        else:
            user_content = ""
        if (
            fail_employee
            and prefix == "[담당 결과]\n"
            and "기획 전담 업무" in user_content
        ):
            raise RuntimeError("기획 직원 모델 오류")
        if prefix == "검수 결과: ":
            review_call_count += 1
            if fail_review:
                raise RuntimeError("검수 모델 오류")
            content = (
                REWORK_REVIEW
                if request_rework and review_call_count == 1
                else PASSED_REVIEW
            )
        elif prefix == "[회의 결론]\n" and fail_conclusion:
            raise RuntimeError("팀장 회의 결론 모델 오류")
        else:
            content = "형식화 전 응답"
        return SimpleNamespace(message=SimpleNamespace(content=content))

    def final_answer_with_retry(_content: str, _request: str, **kwargs) -> str:
        markers = tuple(kwargs.get("required_markers") or ())
        if markers and markers[0] == "[담당 결과]":
            return EMPLOYEE_RESULT
        if markers and markers[0] == "[확인한 연결점]":
            return MEETING_OPINION
        if markers and markers[0] == "[회의 결론]":
            return MEETING_CONCLUSION
        raise AssertionError(f"예상하지 못한 응답 형식: {markers}")

    def start_employee_result(_task_id: int, employee_id: str, content: str) -> int:
        employee_inputs[employee_id] = content
        return next(result_ids)

    def create_team_meeting(_task_id: int) -> int:
        events.append("meeting")
        return 400

    def add_meeting_turn(
        _meeting_id: int,
        _employee_id: str,
        _turn_order: int,
        turn_type: str,
        _content: str,
    ) -> int:
        meeting_turn_types.append(turn_type)
        return next(result_ids)

    def add_review(
        _task_id: int,
        _employee_id: str,
        _round_number: int,
        verdict: str,
        _content: str,
    ) -> int:
        events.append(f"review:{verdict}")
        return 500

    def add_message(
        _project_id: int,
        role: str,
        content: str,
        _employee_id: str | None = None,
    ) -> int:
        if role == "assistant":
            assistant_messages.append(content)
        return 600

    def add_report(*_args, **_kwargs) -> int:
        events.append("report")
        return 700

    def update_team_task_status(_task_id: int, status: str) -> None:
        task_statuses.append(status)

    def classify_report(_text: str):
        if fail_report:
            raise RuntimeError("구조화 보고 생성 오류")
        return structured_data

    def create_report_approval(*args):
        report_approvals.append(args)
        return {"id": 800}

    structured_data = SimpleNamespace(
        proposals=["결과 적용"],
        unverified=[],
        limitations=[],
    )
    engine_no_op_names = (
        "clear_employee_activities",
        "create_task_control",
        "set_employee_activity",
        "update_task_control_state",
    )
    meeting_no_op_names = (
        "add_fact_record",
        "add_handoff",
        "finish_team_meeting",
        "set_employee_activity",
    )
    employee_no_op_names = (
        "add_handoff",
        "add_memory",
        "finish_employee_result",
        "set_employee_activity",
    )
    review_no_op_names = (
        "add_handoff",
        "add_review_targets",
        "create_or_get_clarification_request",
        "finish_employee_result",
        "mark_review_targets_resubmitted",
        "set_employee_activity",
        "update_task_control_state",
    )
    final_report_no_op_names = (
        "add_handoff",
        "finish_employee_result",
        "save_report_structured_data",
        "set_employee_activity",
    )

    with ExitStack() as stack:
        for name in engine_no_op_names:
            stack.enter_context(patch.object(engine, name, return_value=None))
        for name in meeting_no_op_names:
            stack.enter_context(patch.object(meeting, name, return_value=None))
        for name in employee_no_op_names:
            stack.enter_context(
                patch.object(employee_execution, name, return_value=None)
            )
        for name in review_no_op_names:
            stack.enter_context(
                patch.object(review_execution, name, return_value=None)
            )
        for name in final_report_no_op_names:
            stack.enter_context(
                patch.object(final_report_execution, name, return_value=None)
            )
        engine_replacements = {
            "list_sources": lambda _project_id: [],
            "list_memories": lambda _project_id: [],
            "list_project_records": lambda _project_id: [],
            "list_fact_records": lambda _project_id: [],
            "list_employee_activities": lambda _project_id: [],
            "build_source_context": lambda _sources: "",
            "build_memory_context": lambda *_args: "",
            "employee_workstream": workstream,
            "ensure_workflow_not_cancelled": lambda _task_id: None,
            "add_message": add_message,
            "update_team_task_status": update_team_task_status,
            "review_verdict": (
                lambda text: "passed" if text == PASSED_REVIEW else "failed"
            ),
        }
        meeting_replacements = {
            "build_project_context": lambda _project: "",
            "build_employee_system_prompt": lambda *_args, **_kwargs: "",
            "ensure_workflow_not_cancelled": lambda _task_id: None,
            "optimized_chat": optimized_chat,
            "final_answer_with_retry": final_answer_with_retry,
            "create_team_meeting": create_team_meeting,
            "add_meeting_turn": add_meeting_turn,
        }
        employee_replacements = {
            "build_project_context": lambda _project: "",
            "build_employee_system_prompt": lambda *_args, **_kwargs: "",
            "build_employee_assignment": (
                lambda employee, _department: f"{employee['name']} 전담 업무"
            ),
            "build_employee_output_instruction": lambda *_args: "결과 형식",
            "employee_workstream": workstream,
            "ensure_workflow_not_cancelled": lambda _task_id: None,
            "optimized_chat": optimized_chat,
            "final_answer_with_retry": final_answer_with_retry,
            "start_employee_result": start_employee_result,
        }
        review_replacements = {
            "build_project_context": lambda _project: "",
            "build_employee_system_prompt": lambda *_args, **_kwargs: "",
            "build_employee_output_instruction": lambda *_args: "결과 형식",
            "ensure_workflow_not_cancelled": lambda _task_id: None,
            "optimized_chat": optimized_chat,
            "final_answer_with_retry": final_answer_with_retry,
            "start_employee_result": start_employee_result,
            "add_review": add_review,
            "add_message": add_message,
            "remove_thinking": lambda text: text,
            "has_valid_review_contract": lambda *_args: True,
            "is_korean_answer": lambda _text: True,
            "normalize_review_for_user_policy": lambda text, _request: text,
            "review_verdict": (
                lambda text: (
                    "passed"
                    if text == PASSED_REVIEW
                    else (
                        "rework_requested"
                        if text == REWORK_REVIEW
                        else "failed"
                    )
                )
            ),
            "review_target_employee_ids": (
                lambda text, *_args: {"planner"}
                if text == REWORK_REVIEW
                else set()
            ),
            "review_clarification_questions": lambda *_args: "",
        }
        final_report_replacements = {
            "build_employee_assignment": (
                lambda employee, _department: f"{employee['name']} 전담 업무"
            ),
            "ensure_workflow_not_cancelled": lambda _task_id: None,
            "start_employee_result": start_employee_result,
            "add_message": add_message,
            "add_report": add_report,
            "review_verdict": (
                lambda text: "passed" if text == PASSED_REVIEW else "failed"
            ),
            "classify_structured_report": classify_report,
            "render_structured_final_report": lambda *_args, **_kwargs: FINAL_REPORT,
            "user_allows_unverified_progress": lambda _text: False,
            "create_or_get_report_approval": create_report_approval,
        }
        for name, replacement in engine_replacements.items():
            stack.enter_context(patch.object(engine, name, side_effect=replacement))
        for name, replacement in meeting_replacements.items():
            stack.enter_context(patch.object(meeting, name, side_effect=replacement))
        for name, replacement in employee_replacements.items():
            stack.enter_context(
                patch.object(employee_execution, name, side_effect=replacement)
            )
        for name, replacement in review_replacements.items():
            stack.enter_context(
                patch.object(review_execution, name, side_effect=replacement)
            )
        for name, replacement in final_report_replacements.items():
            stack.enter_context(
                patch.object(final_report_execution, name, side_effect=replacement)
            )

        engine.execute_team_workflow_background(
            task_id=10,
            project_id=20,
            project={
                "id": 20,
                "name": "단계 순서 테스트",
                "goal": "안전한 업무 흐름 확인",
            },
            user_message={"message_id": 30, "content": "결과를 작성해주세요."},
            manager_message={"message_id": 31, "content": "직원별 계획"},
            manager_profile=_employee(engine.ACTIVE_EMPLOYEE_ID, "팀장"),
            manager_department="총괄팀",
            supporting_employees=supporting_employees,
            recent_messages=[],
        )

    return {
        "events": events,
        "task_statuses": task_statuses,
        "meeting_turn_types": meeting_turn_types,
        "employee_inputs": employee_inputs,
        "assistant_messages": assistant_messages,
        "rework_inputs": rework_inputs,
        "report_approvals": report_approvals,
    }


def run_regression() -> None:
    success = _run_workflow(fail_review=False)
    assert success["events"] == ["meeting", "review:passed", "report"]
    assert success["meeting_turn_types"] == ["opinion", "opinion", "conclusion"]
    assert "[팀장 회의 결론]" in success["employee_inputs"]["reviewer"]
    assert "팀 문서 검토 상태:\n팀 문서 검토 통과" in success["employee_inputs"]["reporter"]
    assert success["task_statuses"][-1] == "completed"
    assert success["assistant_messages"][-1] == FINAL_REPORT
    assert len(success["report_approvals"]) == 1

    reworked = _run_workflow(fail_review=False, request_rework=True)
    assert reworked["events"] == [
        "meeting",
        "review:rework_requested",
        "review:passed",
        "report",
    ]
    assert reworked["rework_inputs"]
    assert "[1차 검수 수정 요청]" in reworked["rework_inputs"][0]
    assert reworked["task_statuses"][-1] == "completed"

    failed_review = _run_workflow(fail_review=True)
    assert failed_review["events"] == ["meeting", "review:failed"]
    assert "report" not in failed_review["events"]
    assert failed_review["task_statuses"][-1] == "failed"
    assert any(
        "최종 보고서 생성을 보류했습니다" in message
        for message in failed_review["assistant_messages"]
    )

    failed_conclusion = _run_workflow(
        fail_review=False,
        fail_conclusion=True,
    )
    assert failed_conclusion["events"] == ["meeting", "review:passed"]
    assert "report" not in failed_conclusion["events"]
    assert failed_conclusion["meeting_turn_types"] == [
        "opinion",
        "opinion",
        "conclusion",
    ]
    assert failed_conclusion["task_statuses"][-1] == "failed"

    failed_report = _run_workflow(fail_review=False, fail_report=True)
    assert failed_report["events"] == ["meeting", "review:passed"]
    assert failed_report["task_statuses"][-1] == "failed"
    assert not failed_report["report_approvals"]

    expected_error_output = StringIO()
    with redirect_stdout(expected_error_output), redirect_stderr(
        expected_error_output
    ):
        failed_employee = _run_workflow(fail_review=False, fail_employee=True)
    assert failed_employee["events"] == ["review:passed"]
    assert failed_employee["task_statuses"][-1] == "failed"
    assert not failed_employee["report_approvals"]


if __name__ == "__main__":
    run_regression()
    print("WORKFLOW_STAGE_ORDER_REGRESSION_OK")
