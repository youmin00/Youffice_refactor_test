"""출처와 사실 기록의 읽기 전용 SQLite 조회를 모읍니다."""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def list_fact_records(connect: ConnectionFactory, project_id: int, limit: int, database_path: Path) -> list[dict]:
    with connect(database_path) as connection:
        rows = connection.execute(
            """SELECT fact_records.*, sources.title AS source_title,
                      sources.verification_status AS source_verification_status
               FROM fact_records LEFT JOIN sources ON sources.id = fact_records.source_id
               WHERE fact_records.project_id = ? ORDER BY fact_records.id DESC LIMIT ?""",
            (project_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def list_sources(connect: ConnectionFactory, project_id: int, database_path: Path) -> list[dict]:
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM sources WHERE project_id = ? ORDER BY id DESC", (project_id,)
        ).fetchall()
    return [dict(row) for row in rows]
