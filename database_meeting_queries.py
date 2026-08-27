"""팀 회의의 읽기 전용 SQLite 조회를 모읍니다.

공개 API는 계속 database.py가 제공합니다. 이 모듈은 database.py가 전달하는
연결 생성기만 사용하므로 스키마·트랜잭션 정책·운영 DB 경로를 자체적으로 결정하지
않습니다.
"""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path


ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def get_team_meeting(
    connect: ConnectionFactory,
    task_id: int,
    database_path: Path,
) -> dict | None:
    """업무에 연결된 팀 회의 한 건을 반환합니다."""

    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM team_meetings WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def list_meeting_turns(
    connect: ConnectionFactory,
    meeting_id: int,
    database_path: Path,
) -> list[dict]:
    """회의 발언과 결론을 실제 발언 순서대로 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM meeting_turns
            WHERE meeting_id = ?
            ORDER BY turn_order ASC, id ASC
            """,
            (meeting_id,),
        ).fetchall()
    return [dict(row) for row in rows]
