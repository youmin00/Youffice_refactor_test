"""프로젝트 장기 기억과 결정·오류 기록의 읽기 전용 조회를 모읍니다."""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def list_memories(connect: ConnectionFactory, project_id: int, limit: int, database_path: Path) -> list[dict]:
    with connect(database_path) as connection:
        rows = connection.execute("SELECT * FROM memories WHERE project_id = ? ORDER BY id DESC LIMIT ?", (project_id, limit)).fetchall()
    return [dict(row) for row in rows]


def list_project_records(connect: ConnectionFactory, project_id: int, database_path: Path) -> list[dict]:
    with connect(database_path) as connection:
        rows = connection.execute("SELECT * FROM project_records WHERE project_id = ? ORDER BY id DESC", (project_id,)).fetchall()
    return [dict(row) for row in rows]
