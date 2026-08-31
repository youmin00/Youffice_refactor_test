"""database.py 공개 API와 핵심 저장 흐름의 호환 계약 검사입니다."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import database  # noqa: E402


EXPECTED_PARAMETERS = {
    "initialize_database": ("database_path",),
    "create_project": (
        "name", "field", "goal", "start_date", "target_date", "budget",
        "skills", "database_path",
    ),
    "list_projects": ("database_path",),
    "get_project": ("project_id", "database_path"),
    "get_latest_message_id": ("project_id", "database_path"),
    "delete_project": ("project_id", "database_path"),
    "add_message": (
        "project_id", "role", "content", "employee_id", "database_path",
    ),
    "list_messages": ("project_id", "database_path"),
    "clear_project_messages": ("project_id", "database_path"),
    "create_team_task": (
        "project_id", "source_message_id", "request", "manager_context",
        "database_path",
    ),
    "get_task_for_source_message": (
        "project_id", "source_message_id", "database_path",
    ),
    "update_team_task_status": ("task_id", "status", "database_path"),
    "get_team_task": ("task_id", "database_path"),
    "create_task_control": ("task_id", "database_path"),
    "get_task_control": ("task_id", "database_path"),
    "update_task_control_state": ("task_id", "state", "database_path"),
    "create_or_get_clarification_request": (
        "project_id", "task_id", "asked_by_employee_id", "questions",
        "database_path",
    ),
    "get_pending_clarification_request": ("project_id", "database_path"),
    "answer_clarification_request": (
        "request_id", "answer", "followup_task_id", "database_path",
    ),
    "set_employee_activity": (
        "project_id", "employee_id", "status", "detail", "task_id",
        "database_path",
    ),
    "list_employee_activities": ("project_id", "database_path"),
    "clear_employee_activities": ("project_id", "database_path"),
    "add_handoff": (
        "task_id", "from_employee_id", "to_employee_id", "content",
        "database_path",
    ),
    "start_employee_result": (
        "task_id", "employee_id", "input_context", "database_path",
    ),
    "finish_employee_result": (
        "result_id", "status", "output", "error", "database_path",
    ),
    "list_team_tasks": ("project_id", "limit", "database_path"),
    "list_employee_results": ("task_id", "database_path"),
    "list_handoffs": ("task_id", "database_path"),
    "create_team_meeting": ("task_id", "database_path"),
    "add_meeting_turn": (
        "meeting_id", "employee_id", "turn_order", "turn_type", "content",
        "database_path",
    ),
    "finish_team_meeting": (
        "meeting_id", "status", "conclusion", "database_path",
    ),
    "get_team_meeting": ("task_id", "database_path"),
    "list_meeting_turns": ("meeting_id", "database_path"),
    "add_source": (
        "project_id", "title", "url", "source_type", "notes",
        "database_path",
    ),
    "add_fact_record": (
        "project_id", "fact_type", "content", "origin", "source_id",
        "source_message_id", "task_id", "report_id", "database_path",
    ),
    "list_fact_records": ("project_id", "limit", "database_path"),
    "update_fact_record_source": (
        "fact_record_id", "source_id", "database_path",
    ),
    "delete_fact_record": ("fact_record_id", "database_path"),
    "list_sources": ("project_id", "database_path"),
    "update_source_status": (
        "source_id", "verification_status", "database_path",
    ),
    "delete_source": ("source_id", "database_path"),
    "create_or_get_approval": (
        "project_id", "source_message_id", "plan_content", "database_path",
    ),
    "update_approval": (
        "approval_id", "status", "plan_content", "user_feedback",
        "increment_revision", "database_path",
    ),
    "add_review": (
        "task_id", "reviewer_employee_id", "review_round", "verdict",
        "feedback", "database_path",
    ),
    "add_review_targets": (
        "review_id", "task_id", "target_employee_ids", "status",
        "database_path",
    ),
    "mark_review_targets_resubmitted": (
        "task_id", "target_employee_id", "rework_output", "database_path",
    ),
    "list_review_targets": ("task_id", "database_path"),
    "list_reviews": ("task_id", "database_path"),
    "add_memory": (
        "project_id", "content", "category", "employee_id",
        "source_message_id", "database_path",
    ),
    "list_memories": ("project_id", "limit", "database_path"),
    "delete_memory": ("memory_id", "database_path"),
    "add_project_record": (
        "project_id", "record_type", "title", "content", "database_path",
    ),
    "list_project_records": ("project_id", "database_path"),
    "update_project_record_status": ("record_id", "status", "database_path"),
    "delete_project_record": ("record_id", "database_path"),
    "add_report": (
        "project_id", "employee_id", "title", "content", "task_id",
        "message_id", "parent_report_id", "database_path",
    ),
    "list_reports": ("project_id", "database_path"),
    "save_report_structured_data": (
        "report_id", "project_id", "proposals", "unverified", "limitations",
        "database_path",
    ),
    "get_report_structured_data": ("report_id", "database_path"),
    "create_or_get_report_approval": (
        "project_id", "report_id", "database_path",
    ),
    "list_report_approvals": ("project_id", "database_path"),
    "update_report_approval": (
        "approval_id", "status", "user_feedback", "replacement_report_id",
        "database_path",
    ),
}


def _assert_public_signatures() -> None:
    for name, expected_parameters in EXPECTED_PARAMETERS.items():
        function = getattr(database, name, None)
        assert callable(function), f"database.{name} 함수가 없습니다."
        actual_parameters = tuple(inspect.signature(function).parameters)
        assert actual_parameters == expected_parameters, (
            f"database.{name} 인자 변경: "
            f"예상={expected_parameters}, 실제={actual_parameters}"
        )
        assert "database_path" in actual_parameters

    public_functions = {
        name
        for name, value in vars(database).items()
        if inspect.isfunction(value)
        and value.__module__ == "database"
        and not name.startswith("_")
    }
    assert public_functions == set(EXPECTED_PARAMETERS), (
        "database.py 공개 함수 목록이 계약과 다릅니다: "
        f"누락={sorted(set(EXPECTED_PARAMETERS) - public_functions)}, "
        f"미등록={sorted(public_functions - set(EXPECTED_PARAMETERS))}"
    )


def _assert_consumer_imports_exist() -> None:
    consumer_paths = [
        PROJECT_ROOT / "app.py",
        *(PROJECT_ROOT / "ui").glob("*.py"),
        *(PROJECT_ROOT / "workflow").glob("*.py"),
    ]
    for path in consumer_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module != "database":
                continue
            for alias in node.names:
                assert hasattr(database, alias.name), (
                    f"{path.relative_to(PROJECT_ROOT)}가 없는 DB 함수 "
                    f"database.{alias.name}를 import합니다."
                )


def _assert_temporary_database_flow() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "contract.db"
        database.initialize_database(database_path)

        project_id = database.create_project(
            "계약 테스트",
            "로봇",
            "DB 공개 API 확인",
            "",
            "",
            "",
            "Python",
            database_path,
        )
        message_id = database.add_message(
            project_id,
            "user",
            "테스트 요청",
            database_path=database_path,
        )
        task_id = database.create_team_task(
            project_id,
            message_id,
            "테스트 요청",
            "승인된 계획",
            database_path,
        )
        database.create_task_control(task_id, database_path)
        database.set_employee_activity(
            project_id,
            "worker",
            "working",
            "테스트 중",
            task_id,
            database_path,
        )
        result_id = database.start_employee_result(
            task_id,
            "worker",
            "입력 문맥",
            database_path,
        )
        database.finish_employee_result(
            result_id,
            "completed",
            output="직원 결과",
            database_path=database_path,
        )
        database.add_handoff(
            task_id,
            "worker",
            "reviewer",
            "검수 요청",
            database_path,
        )

        meeting_id = database.create_team_meeting(task_id, database_path)
        database.add_meeting_turn(
            meeting_id,
            "worker",
            1,
            "opinion",
            "회의 의견",
            database_path,
        )
        database.finish_team_meeting(
            meeting_id,
            "completed",
            "회의 결론",
            database_path,
        )

        review_id = database.add_review(
            task_id,
            "reviewer",
            1,
            "passed",
            "검수 통과",
            database_path,
        )
        database.add_review_targets(
            review_id,
            task_id,
            set(),
            "passed",
            database_path,
        )

        source_id = database.add_source(
            project_id,
            "공식 자료",
            "https://example.com/spec",
            "공식 문서",
            "사양 확인",
            database_path,
        )
        database.update_source_status(source_id, "verified", database_path)
        fact_id = database.add_fact_record(
            project_id,
            "confirmed_fact",
            "확인된 사양",
            origin="user",
            source_id=source_id,
            source_message_id=message_id,
            task_id=task_id,
            database_path=database_path,
        )
        assert fact_id is not None
        memory_id = database.add_memory(
            project_id,
            "중요 조건",
            source_message_id=message_id,
            database_path=database_path,
        )
        assert memory_id is not None
        record_id = database.add_project_record(
            project_id,
            "decision",
            "결정",
            "테스트 기준 유지",
            database_path,
        )
        assert record_id > 0

        report_message_id = database.add_message(
            project_id,
            "assistant",
            "최종 보고",
            "reporter",
            database_path,
        )
        report_id = database.add_report(
            project_id,
            "reporter",
            "계약 테스트 보고서",
            "최종 보고",
            task_id=task_id,
            message_id=report_message_id,
            database_path=database_path,
        )
        database.save_report_structured_data(
            report_id,
            project_id,
            ["제안"],
            [],
            ["한계"],
            database_path,
        )
        report_approval = database.create_or_get_report_approval(
            project_id,
            report_id,
            database_path,
        )

        assert database.get_project(project_id, database_path)["name"] == "계약 테스트"
        assert database.get_latest_message_id(project_id, database_path) == report_message_id
        assert database.get_team_task(task_id, database_path)["id"] == task_id
        assert database.get_team_meeting(task_id, database_path)["id"] == meeting_id
        assert len(database.list_meeting_turns(meeting_id, database_path)) == 1
        assert len(database.list_employee_results(task_id, database_path)) == 1
        assert len(database.list_reviews(task_id, database_path)) == 1
        assert len(database.list_sources(project_id, database_path)) == 1
        assert len(database.list_fact_records(project_id, database_path=database_path)) >= 1
        assert len(database.list_memories(project_id, database_path=database_path)) == 1
        assert len(database.list_project_records(project_id, database_path)) == 1
        assert database.get_report_structured_data(report_id, database_path) is not None
        assert report_approval["report_id"] == report_id


def run_contract_test() -> None:
    _assert_public_signatures()
    _assert_consumer_imports_exist()
    _assert_temporary_database_flow()


if __name__ == "__main__":
    run_contract_test()
    print("DATABASE_API_CONTRACT_OK")
