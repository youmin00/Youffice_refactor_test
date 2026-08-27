"""업무·검수·보고서 참조 무결성 회귀 검사입니다."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import (  # noqa: E402
    add_fact_record,
    add_memory,
    add_message,
    add_report,
    add_review,
    add_review_targets,
    add_source,
    answer_clarification_request,
    clear_project_messages,
    create_or_get_approval,
    create_or_get_clarification_request,
    create_or_get_report_approval,
    create_project,
    create_team_task,
    delete_project,
    delete_source,
    get_report_structured_data,
    initialize_database,
    list_employee_activities,
    list_fact_records,
    list_reports,
    save_report_structured_data,
    set_employee_activity,
    update_report_approval,
    update_fact_record_source,
    update_source_status,
)
from workflow.reporting import resolve_report_task_id  # noqa: E402


def _expect_value_error(action) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("프로젝트 경계를 넘는 참조를 차단하지 못했습니다.")


def run_regression() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "reference_integrity.db"
        initialize_database(database_path)

        project_one = create_project(
            "첫 번째 프로젝트",
            "테스트",
            "참조 무결성 확인",
            "2026-08-18",
            "2026-08-31",
            "",
            "",
            database_path,
        )
        project_two = create_project(
            "두 번째 프로젝트",
            "테스트",
            "프로젝트 경계 확인",
            "2026-08-18",
            "2026-08-31",
            "",
            "",
            database_path,
        )
        message_one = add_message(
            project_one,
            "user",
            "첫 번째 요청",
            database_path=database_path,
        )
        message_two = add_message(
            project_two,
            "user",
            "두 번째 요청",
            database_path=database_path,
        )
        task_one = create_team_task(
            project_one,
            message_one,
            "첫 번째 업무",
            "첫 번째 계획",
            database_path,
        )
        task_two = create_team_task(
            project_two,
            message_two,
            "두 번째 업무",
            "두 번째 계획",
            database_path,
        )
        followup_message_one = add_message(
            project_one,
            "user",
            "첫 번째 후속 요청",
            database_path=database_path,
        )
        followup_task_one = create_team_task(
            project_one,
            followup_message_one,
            "첫 번째 후속 업무",
            "첫 번째 후속 계획",
            database_path,
        )
        second_message_one = add_message(
            project_one,
            "user",
            "첫 번째 프로젝트의 별도 요청",
            database_path=database_path,
        )
        second_task_one = create_team_task(
            project_one,
            second_message_one,
            "첫 번째 프로젝트의 별도 업무",
            "첫 번째 프로젝트의 별도 계획",
            database_path,
        )

        unverified_source_one = add_source(
            project_one,
            "첫 번째 프로젝트의 미확인 자료",
            "https://example.com/unverified",
            "기사",
            "미확인 핵심 내용",
            database_path,
        )
        verified_source_one = add_source(
            project_one,
            "첫 번째 프로젝트의 확인 자료",
            "https://example.com/verified",
            "공식 문서",
            "확인된 핵심 내용",
            database_path,
        )
        source_two = add_source(
            project_two,
            "두 번째 프로젝트 자료",
            "https://example.com/second",
            "공식 문서",
            "두 번째 프로젝트 자료",
            database_path,
        )
        update_source_status(verified_source_one, "verified", database_path)

        confirmed_fact_id = add_fact_record(
            project_one,
            "confirmed_fact",
            "확인된 첫 번째 프로젝트 사실",
            source_id=verified_source_one,
            source_message_id=message_one,
            task_id=task_one,
            origin="user",
            database_path=database_path,
        )
        assert confirmed_fact_id is not None
        _expect_value_error(
            lambda: add_fact_record(
                project_one,
                "confirmed_fact",
                "다른 프로젝트 출처를 연결한 사실",
                source_id=source_two,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: add_fact_record(
                project_one,
                "confirmed_fact",
                "미확인 출처를 확정 사실로 저장",
                source_id=unverified_source_one,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: update_fact_record_source(
                confirmed_fact_id,
                source_two,
                database_path,
            )
        )
        _expect_value_error(
            lambda: update_source_status(
                verified_source_one,
                "unverified",
                database_path,
            )
        )
        _expect_value_error(
            lambda: delete_source(verified_source_one, database_path)
        )
        direct_decision_id = add_fact_record(
            project_one,
            "user_decision",
            "사용자가 직접 입력한 결정",
            origin="user",
            database_path=database_path,
        )
        assert direct_decision_id is not None
        fact_records = list_fact_records(project_one, database_path=database_path)
        assert {fact_record["id"] for fact_record in fact_records} >= {
            confirmed_fact_id,
            direct_decision_id,
        }

        _expect_value_error(
            lambda: create_team_task(
                project_one,
                message_two,
                "잘못된 업무",
                "잘못된 계획",
                database_path,
            )
        )

        clarification = create_or_get_clarification_request(
            project_one,
            task_one,
            "reviewer",
            "첫 번째 프로젝트의 보완 질문",
            database_path,
        )
        _expect_value_error(
            lambda: create_or_get_clarification_request(
                project_one,
                task_two,
                "reviewer",
                "다른 프로젝트 업무의 보완 질문",
                database_path,
            )
        )
        _expect_value_error(
            lambda: answer_clarification_request(
                clarification["id"],
                "답변",
                task_two,
                database_path,
            )
        )
        answer_clarification_request(
            clarification["id"],
            "답변",
            followup_task_one,
            database_path,
        )

        set_employee_activity(
            project_one,
            "planner",
            "working",
            task_id=task_one,
            database_path=database_path,
        )
        _expect_value_error(
            lambda: set_employee_activity(
                project_one,
                "planner",
                "working",
                task_id=task_two,
                database_path=database_path,
            )
        )
        activities = list_employee_activities(project_one, database_path)
        assert activities[0]["task_id"] == task_one

        create_or_get_approval(
            project_one,
            message_one,
            "첫 번째 계획",
            database_path,
        )
        _expect_value_error(
            lambda: create_or_get_approval(
                project_one,
                message_two,
                "잘못된 프로젝트의 계획",
                database_path,
            )
        )

        add_memory(
            project_one,
            "첫 번째 프로젝트 기억",
            source_message_id=message_one,
            database_path=database_path,
        )
        _expect_value_error(
            lambda: add_memory(
                project_one,
                "잘못된 프로젝트의 기억",
                source_message_id=message_two,
                database_path=database_path,
            )
        )

        report_id = add_report(
            project_one,
            "reporter",
            "첫 번째 최종 보고서",
            "[최종 결론]\n정상 연결\n\n[핵심 산출물]\n참조 저장",
            task_id=task_one,
            message_id=message_one,
            database_path=database_path,
        )
        report = list_reports(project_one, database_path)[0]
        assert report["task_id"] == task_one
        assert report["message_id"] == message_one
        assert report["parent_report_id"] is None
        assert report["version_number"] == 1

        save_report_structured_data(
            report_id,
            project_one,
            ["제안 항목"],
            ["미확인 항목"],
            ["한계 항목"],
            database_path,
        )
        structured_data = get_report_structured_data(report_id, database_path)
        assert structured_data is not None
        assert structured_data["proposals"] == ["제안 항목"]
        assert structured_data["unverified"] == ["미확인 항목"]
        assert structured_data["limitations"] == ["한계 항목"]
        report_fact_records = [
            fact_record
            for fact_record in list_fact_records(project_one, database_path=database_path)
            if fact_record["report_id"] == report_id
        ]
        assert {
            fact_record["fact_type"] for fact_record in report_fact_records
        } == {"proposal", "unverified", "limitation"}
        assert all(fact_record["origin"] == "ai" for fact_record in report_fact_records)
        assert all(fact_record["source_id"] is None for fact_record in report_fact_records)

        save_report_structured_data(
            report_id,
            project_one,
            ["새 제안 항목"],
            [],
            ["새 한계 항목"],
            database_path,
        )
        refreshed_structured_data = get_report_structured_data(report_id, database_path)
        assert refreshed_structured_data is not None
        assert refreshed_structured_data["proposals"] == ["새 제안 항목"]
        assert refreshed_structured_data["unverified"] == []
        assert refreshed_structured_data["limitations"] == ["새 한계 항목"]
        refreshed_report_fact_records = [
            fact_record
            for fact_record in list_fact_records(project_one, database_path=database_path)
            if fact_record["report_id"] == report_id
        ]
        assert {
            (fact_record["fact_type"], fact_record["content"])
            for fact_record in refreshed_report_fact_records
        } == {
            ("proposal", "새 제안 항목"),
            ("limitation", "새 한계 항목"),
        }

        _expect_value_error(
            lambda: add_report(
                project_one,
                "reporter",
                "잘못된 업무 보고서",
                "내용",
                task_id=task_two,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: add_report(
                project_one,
                "reporter",
                "잘못된 메시지 보고서",
                "내용",
                message_id=message_two,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: save_report_structured_data(
                report_id,
                project_two,
                [],
                [],
                [],
                database_path,
            )
        )

        report_two = add_report(
            project_two,
            "reporter",
            "두 번째 최종 보고서",
            "두 번째 프로젝트 보고서",
            task_id=task_two,
            message_id=message_two,
            database_path=database_path,
        )
        same_project_other_task_report = add_report(
            project_one,
            "reporter",
            "다른 업무의 보고서",
            "첫 번째 프로젝트의 다른 업무 보고서",
            task_id=second_task_one,
            message_id=second_message_one,
            database_path=database_path,
        )
        same_task_unlinked_report = add_report(
            project_one,
            "reporter",
            "같은 업무의 독립 보고서",
            "수정본 계보에 속하지 않는 보고서",
            task_id=task_one,
            message_id=message_one,
            database_path=database_path,
        )
        _expect_value_error(
            lambda: add_report(
                project_one,
                "reporter",
                "다른 프로젝트 원본을 가리키는 수정본",
                "내용",
                task_id=task_one,
                parent_report_id=report_two,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: add_report(
                project_one,
                "reporter",
                "다른 업무 원본을 가리키는 수정본",
                "내용",
                task_id=task_one,
                parent_report_id=same_project_other_task_report,
                database_path=database_path,
            )
        )
        replacement_report = add_report(
            project_one,
            "reporter",
            "첫 번째 최종 보고서 수정본",
            "첫 번째 프로젝트의 정상 수정본",
            task_id=task_one,
            message_id=message_one,
            parent_report_id=report_id,
            database_path=database_path,
        )
        replacement_report_row = next(
            report
            for report in list_reports(project_one, database_path)
            if report["id"] == replacement_report
        )
        assert replacement_report_row["parent_report_id"] == report_id
        assert replacement_report_row["version_number"] == 2
        second_replacement_report = add_report(
            project_one,
            "reporter",
            "첫 번째 최종 보고서 2차 수정본",
            "첫 번째 프로젝트의 두 번째 정상 수정본",
            task_id=task_one,
            message_id=message_one,
            parent_report_id=replacement_report,
            database_path=database_path,
        )
        second_replacement_row = next(
            report
            for report in list_reports(project_one, database_path)
            if report["id"] == second_replacement_report
        )
        assert second_replacement_row["parent_report_id"] == replacement_report
        assert second_replacement_row["version_number"] == 3
        report_approval = create_or_get_report_approval(
            project_one,
            report_id,
            database_path,
        )
        _expect_value_error(
            lambda: update_report_approval(
                report_approval["id"],
                "revision_requested",
                replacement_report_id=report_two,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: update_report_approval(
                report_approval["id"],
                "revision_requested",
                replacement_report_id=report_id,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: update_report_approval(
                report_approval["id"],
                "revision_requested",
                replacement_report_id=same_project_other_task_report,
                database_path=database_path,
            )
        )
        _expect_value_error(
            lambda: update_report_approval(
                report_approval["id"],
                "revision_requested",
                replacement_report_id=same_task_unlinked_report,
                database_path=database_path,
            )
        )
        update_report_approval(
            report_approval["id"],
            "revision_requested",
            replacement_report_id=replacement_report,
            database_path=database_path,
        )
        assert resolve_report_task_id(None, task_one) == task_one
        assert resolve_report_task_id({"task_id": task_one}, second_task_one) == task_one
        assert resolve_report_task_id({"task_id": None}, second_task_one) is None

        review_one = add_review(
            task_one,
            "reviewer",
            1,
            "passed",
            "통과",
            database_path,
        )
        review_two = add_review(
            task_two,
            "reviewer",
            1,
            "passed",
            "통과",
            database_path,
        )
        add_review_targets(review_one, task_one, {"worker"}, "passed", database_path)
        _expect_value_error(
            lambda: add_review_targets(
                review_two,
                task_one,
                {"worker"},
                "passed",
                database_path,
            )
        )

        connection = sqlite3.connect(database_path)
        try:
            mismatch_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM review_targets
                JOIN reviews ON reviews.id = review_targets.review_id
                WHERE review_targets.task_id != reviews.task_id
                """
            ).fetchone()[0]
        finally:
            connection.close()
        assert mismatch_count == 0

        message_fact_id = add_fact_record(
            project_one,
            "proposal",
            "대화 초기화 참조 확인",
            origin="user",
            source_message_id=message_one,
            database_path=database_path,
        )
        assert message_fact_id is not None
        clear_project_messages(project_one, database_path)

        connection = sqlite3.connect(database_path)
        try:
            assert connection.execute(
                "SELECT COUNT(*) FROM messages WHERE project_id = ?",
                (project_one,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM messages WHERE project_id = ?",
                (project_two,),
            ).fetchone()[0] > 0
            for table in ("team_tasks", "approvals", "memories"):
                remaining_count, linked_count = connection.execute(
                    f"""
                    SELECT COUNT(*), COUNT(source_message_id)
                    FROM {table}
                    WHERE project_id = ?
                    """,
                    (project_one,),
                ).fetchone()
                assert remaining_count > 0
                assert linked_count == 0
            report_count, linked_report_count = connection.execute(
                """
                SELECT COUNT(*), COUNT(message_id)
                FROM reports
                WHERE project_id = ?
                """,
                (project_one,),
            ).fetchone()
            assert report_count > 0
            assert linked_report_count == 0
            assert connection.execute(
                "SELECT source_message_id FROM fact_records WHERE id = ?",
                (message_fact_id,),
            ).fetchone()[0] is None
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            connection.close()

        delete_project(project_one, database_path)
        connection = sqlite3.connect(database_path)
        try:
            assert connection.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?",
                (project_one,),
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?",
                (project_two,),
            ).fetchone()[0] == 1
            for table in (
                "messages",
                "team_tasks",
                "employee_activities",
                "sources",
                "fact_records",
                "approvals",
                "memories",
                "project_records",
                "reports",
                "report_structured_data",
                "report_approvals",
                "clarification_requests",
            ):
                assert connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE project_id = ?",
                    (project_one,),
                ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM reviews WHERE task_id IN (?, ?)",
                (task_one, second_task_one),
            ).fetchone()[0] == 0
            assert connection.execute(
                "SELECT COUNT(*) FROM review_targets WHERE task_id IN (?, ?)",
                (task_one, second_task_one),
            ).fetchone()[0] == 0
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            connection.close()


if __name__ == "__main__":
    run_regression()
    print("REFERENCE_INTEGRITY_REGRESSION_OK")
