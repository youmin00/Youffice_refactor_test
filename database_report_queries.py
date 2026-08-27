"""보고서와 승인 기록의 읽기 전용 SQLite 조회를 모읍니다."""

import json
import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path


ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def list_reports(
    connect: ConnectionFactory, project_id: int, database_path: Path
) -> list[dict]:
    """프로젝트의 보고서를 최신순으로 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM reports WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_report_approvals(
    connect: ConnectionFactory, project_id: int, database_path: Path
) -> list[dict]:
    """프로젝트에 속한 보고서 승인 기록을 최신순으로 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM report_approvals WHERE project_id = ? ORDER BY id DESC",
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_report_structured_data(
    connect: ConnectionFactory, report_id: int, database_path: Path
) -> dict | None:
    """구조화 보고서 데이터와 JSON 목록을 안전하게 복원합니다."""

    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM report_structured_data WHERE report_id = ?",
            (report_id,),
        ).fetchone()
    if row is None:
        return None

    result = dict(row)
    for source_key, target_key in (
        ("proposals_json", "proposals"),
        ("unverified_json", "unverified"),
        ("limitations_json", "limitations"),
    ):
        try:
            value = json.loads(result.get(source_key) or "[]")
        except (TypeError, json.JSONDecodeError):
            value = []
        result[target_key] = value if isinstance(value, list) else []
    return result
