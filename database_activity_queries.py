"""직원 활동과 업무 이력의 읽기 전용 SQLite 조회를 모읍니다.

공개 API는 계속 database.py가 제공합니다. 이 모듈은 database.py가 전달하는
연결 생성기만 사용하므로 스키마·트랜잭션 정책·운영 DB 경로를 자체적으로 결정하지
않습니다.
"""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path


ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def list_employee_activities(
    connect: ConnectionFactory,
    project_id: int,
    database_path: Path,
) -> list[dict]:
    """현재 프로젝트에 저장된 직원별 최신 상태를 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM employee_activities
            WHERE project_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_team_tasks(
    connect: ConnectionFactory,
    project_id: int,
    limit: int,
    database_path: Path,
) -> list[dict]:
    """현재 프로젝트의 최근 팀 업무를 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM team_tasks
            WHERE project_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_employee_results(
    connect: ConnectionFactory,
    task_id: int,
    database_path: Path,
) -> list[dict]:
    """팀 업무에 참여한 직원별 결과를 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM employee_results
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_handoffs(
    connect: ConnectionFactory,
    task_id: int,
    database_path: Path,
) -> list[dict]:
    """팀 업무의 직원 간 전달 기록을 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM handoffs
            WHERE task_id = ?
            ORDER BY id ASC
            """,
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]
