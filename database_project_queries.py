"""프로젝트와 대화의 읽기 전용 SQLite 조회를 모읍니다.

공개 API는 계속 database.py가 제공합니다. 이 모듈은 database.py가 전달하는
연결 생성기만 사용하므로 스키마·트랜잭션 정책·운영 DB 경로를 자체적으로 결정하지
않습니다.
"""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path


ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def list_projects(
    connect: ConnectionFactory,
    database_path: Path,
) -> list[dict]:
    """최근에 수정된 프로젝트부터 목록으로 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM projects
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_project(
    connect: ConnectionFactory,
    project_id: int,
    database_path: Path,
) -> dict | None:
    """선택한 프로젝트 한 건을 반환합니다."""

    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_messages(
    connect: ConnectionFactory,
    project_id: int,
    database_path: Path,
) -> list[dict]:
    """선택한 프로젝트의 대화를 오래된 순서대로 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT id AS message_id, role, content, employee_id, created_at
            FROM messages
            WHERE project_id = ?
            ORDER BY id ASC
            """,
            (project_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_latest_message_id(
    connect: ConnectionFactory,
    project_id: int,
    database_path: Path,
) -> int:
    """Return a lightweight cursor for detecting project chat changes."""

    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(id), 0) AS message_id FROM messages WHERE project_id = ?",
            (project_id,),
        ).fetchone()
    return int(row["message_id"])
