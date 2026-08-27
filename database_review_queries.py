"""검수와 재작업 대상의 읽기 전용 SQLite 조회를 모읍니다."""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path


ConnectionFactory = Callable[[Path], AbstractContextManager[sqlite3.Connection]]


def list_review_targets(
    connect: ConnectionFactory, task_id: int, database_path: Path
) -> list[dict]:
    """검수 차수·검수자와 연결된 대상 직원 및 재작업본을 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT review_targets.*, reviews.reviewer_employee_id,
                   reviews.review_round, reviews.verdict, reviews.feedback
            FROM review_targets
            JOIN reviews ON reviews.id = review_targets.review_id
            WHERE review_targets.task_id = ?
            ORDER BY reviews.review_round ASC, review_targets.id ASC
            """,
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_reviews(
    connect: ConnectionFactory, task_id: int, database_path: Path
) -> list[dict]:
    """팀 업무의 검수 기록을 반환합니다."""

    with connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT * FROM reviews
            WHERE task_id = ?
            ORDER BY review_round ASC, id ASC
            """,
            (task_id,),
        ).fetchall()
    return [dict(row) for row in rows]
