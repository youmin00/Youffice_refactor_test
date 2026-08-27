"""팀 업무 진행 상태의 읽기 전용 SQLite 조회를 모읍니다."""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def get_task_for_source_message(connect: ConnectionFactory, project_id: int, source_message_id: int, database_path: Path) -> dict | None:
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM team_tasks WHERE project_id = ? AND source_message_id = ?", (project_id, source_message_id)).fetchone()
    return dict(row) if row is not None else None


def get_team_task(connect: ConnectionFactory, task_id: int, database_path: Path) -> dict | None:
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM team_tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row is not None else None


def get_task_control(connect: ConnectionFactory, task_id: int, database_path: Path) -> dict | None:
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM task_controls WHERE task_id = ?", (task_id,)).fetchone()
    return dict(row) if row is not None else None


def get_pending_clarification_request(connect: ConnectionFactory, project_id: int, database_path: Path) -> dict | None:
    with connect(database_path) as connection:
        row = connection.execute(
            """SELECT clarification_requests.* FROM clarification_requests
               WHERE clarification_requests.project_id = ?
                 AND clarification_requests.status = 'pending'
                 AND clarification_requests.task_id = (
                     SELECT MAX(team_tasks.id) FROM team_tasks
                     WHERE team_tasks.project_id = clarification_requests.project_id
                 ) ORDER BY id DESC LIMIT 1""",
            (project_id,),
        ).fetchone()
    return dict(row) if row is not None else None
