import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import json

from database_activity_queries import (
    list_employee_activities as _list_employee_activities,
    list_employee_results as _list_employee_results,
    list_handoffs as _list_handoffs,
    list_team_tasks as _list_team_tasks,
)
from database_project_queries import (
    get_project as _get_project,
    list_messages as _list_messages,
    list_projects as _list_projects,
)
from database_meeting_queries import (
    get_team_meeting as _get_team_meeting,
    list_meeting_turns as _list_meeting_turns,
)
from database_review_queries import (
    list_review_targets as _list_review_targets,
    list_reviews as _list_reviews,
)
from database_report_queries import (
    get_report_structured_data as _get_report_structured_data,
    list_report_approvals as _list_report_approvals,
    list_reports as _list_reports,
)
from database_source_queries import (
    list_fact_records as _list_fact_records,
    list_sources as _list_sources,
)
from database_workflow_queries import (
    get_pending_clarification_request as _get_pending_clarification_request,
    get_task_control as _get_task_control,
    get_task_for_source_message as _get_task_for_source_message,
    get_team_task as _get_team_task,
)
from database_context_queries import (
    list_memories as _list_memories,
    list_project_records as _list_project_records,
)


DATABASE_PATH = Path(__file__).resolve().parent / "data" / "youffice.db"


@contextmanager
def _connect(
    database_path: Path = DATABASE_PATH,
) -> Iterator[sqlite3.Connection]:
    """YOUFFICE SQLite 데이터베이스 연결을 생성합니다."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def _ensure_project_reference(
    connection: sqlite3.Connection,
    table_name: str,
    reference_id: int,
    project_id: int,
    reference_label: str,
) -> None:
    """참조 행이 존재하며 같은 프로젝트에 속하는지 확인합니다."""

    row = connection.execute(
        f"SELECT project_id FROM {table_name} WHERE id = ?",
        (reference_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"{reference_label}를 찾을 수 없습니다.")
    if int(row["project_id"]) != project_id:
        raise ValueError(f"{reference_label}가 현재 프로젝트에 속하지 않습니다.")


def initialize_database(database_path: Path = DATABASE_PATH) -> None:
    """프로젝트와 대화 저장에 필요한 기본 테이블을 준비합니다."""

    with _connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                field TEXT NOT NULL,
                goal TEXT NOT NULL,
                start_date TEXT NOT NULL,
                target_date TEXT NOT NULL,
                budget TEXT NOT NULL DEFAULT '',
                skills TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'planning',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                employee_id TEXT,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_project_id
            ON messages(project_id, id);

            CREATE TABLE IF NOT EXISTS team_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                source_message_id INTEGER,
                request TEXT NOT NULL,
                manager_context TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL,
                UNIQUE (project_id, source_message_id)
            );

            CREATE TABLE IF NOT EXISTS handoffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                from_employee_id TEXT NOT NULL,
                to_employee_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS employee_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                employee_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'failed')),
                input_context TEXT NOT NULL,
                output TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE CASCADE,
                UNIQUE (task_id, employee_id)
            );

            CREATE INDEX IF NOT EXISTS idx_team_tasks_project_id
            ON team_tasks(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_employee_results_task_id
            ON employee_results(task_id, id);

            CREATE INDEX IF NOT EXISTS idx_handoffs_task_id
            ON handoffs(task_id, id);

            CREATE TABLE IF NOT EXISTS team_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'partial', 'failed')),
                conclusion TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS meeting_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                employee_id TEXT NOT NULL,
                turn_order INTEGER NOT NULL,
                turn_type TEXT NOT NULL
                    CHECK (turn_type IN ('opinion', 'conclusion')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES team_meetings(id) ON DELETE CASCADE,
                UNIQUE (meeting_id, turn_order)
            );

            CREATE INDEX IF NOT EXISTS idx_meeting_turns_meeting_id
            ON meeting_turns(meeting_id, turn_order);

            CREATE TABLE IF NOT EXISTS employee_activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                employee_id TEXT NOT NULL,
                task_id INTEGER,
                status TEXT NOT NULL DEFAULT 'waiting'
                    CHECK (status IN (
                        'waiting', 'assigned', 'working', 'reviewing',
                        'reworking', 'synthesizing', 'completed',
                        'error', 'inactive'
                    )),
                detail TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE SET NULL,
                UNIQUE (project_id, employee_id)
            );

            CREATE INDEX IF NOT EXISTS idx_employee_activities_project_id
            ON employee_activities(project_id, updated_at);

            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT '기타',
                notes TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'unverified'
                    CHECK (verification_status IN ('unverified', 'verified', 'rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS fact_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                fact_type TEXT NOT NULL
                    CHECK (fact_type IN (
                        'confirmed_fact', 'proposal', 'unverified',
                        'user_decision', 'limitation'
                    )),
                content TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'user'
                    CHECK (origin IN ('user', 'ai', 'system')),
                source_id INTEGER,
                source_message_id INTEGER,
                task_id INTEGER,
                report_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT,
                FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE SET NULL,
                FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
                UNIQUE (report_id, fact_type, content)
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                source_message_id INTEGER,
                plan_content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'revision_requested')),
                user_feedback TEXT NOT NULL DEFAULT '',
                revision_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                decided_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL,
                UNIQUE (project_id, source_message_id)
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                reviewer_employee_id TEXT NOT NULL,
                review_round INTEGER NOT NULL DEFAULT 1,
                verdict TEXT NOT NULL
                    CHECK (verdict IN ('passed', 'rework_requested', 'failed')),
                feedback TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS review_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                target_employee_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'rework_requested'
                    CHECK (status IN (
                        'rework_requested', 'resubmitted', 'passed', 'unresolved'
                    )),
                rework_output TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE CASCADE,
                UNIQUE (review_id, target_employee_id)
            );

            CREATE INDEX IF NOT EXISTS idx_sources_project_id
            ON sources(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_fact_records_project_id
            ON fact_records(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_fact_records_source_id
            ON fact_records(source_id, id);

            CREATE INDEX IF NOT EXISTS idx_fact_records_report_id
            ON fact_records(report_id, id);

            CREATE INDEX IF NOT EXISTS idx_approvals_project_id
            ON approvals(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_reviews_task_id
            ON reviews(task_id, id);

            CREATE INDEX IF NOT EXISTS idx_review_targets_task_id
            ON review_targets(task_id, target_employee_id, id);

            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                employee_id TEXT,
                source_message_id INTEGER,
                category TEXT NOT NULL DEFAULT 'general'
                    CHECK (category IN ('general', 'requirement', 'decision', 'constraint', 'preference', 'lesson')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL,
                UNIQUE (project_id, employee_id, source_message_id)
            );

            CREATE TABLE IF NOT EXISTS project_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                record_type TEXT NOT NULL
                    CHECK (record_type IN ('decision', 'error')),
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'resolved')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER,
                message_id INTEGER,
                parent_report_id INTEGER,
                version_number INTEGER NOT NULL DEFAULT 1
                    CHECK (version_number >= 1),
                employee_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE SET NULL,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE SET NULL,
                FOREIGN KEY (parent_report_id) REFERENCES reports(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS report_structured_data (
                report_id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                proposals_json TEXT NOT NULL DEFAULT '[]',
                unverified_json TEXT NOT NULL DEFAULT '[]',
                limitations_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS report_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                report_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'revision_requested')),
                user_feedback TEXT NOT NULL DEFAULT '',
                replacement_report_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                decided_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (report_id) REFERENCES reports(id) ON DELETE CASCADE,
                FOREIGN KEY (replacement_report_id) REFERENCES reports(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS task_controls (
                task_id INTEGER PRIMARY KEY,
                state TEXT NOT NULL DEFAULT 'active'
                    CHECK (state IN (
                        'active', 'cancel_requested', 'cancelled', 'waiting_for_user'
                    )),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS clarification_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL UNIQUE,
                asked_by_employee_id TEXT NOT NULL,
                questions TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'answered')),
                answer TEXT NOT NULL DEFAULT '',
                followup_task_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                answered_at TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (task_id) REFERENCES team_tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (followup_task_id) REFERENCES team_tasks(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_project_id
            ON memories(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_project_records_project_id
            ON project_records(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_reports_project_id
            ON reports(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_report_approvals_project_id
            ON report_approvals(project_id, id);

            CREATE INDEX IF NOT EXISTS idx_clarification_requests_project_id
            ON clarification_requests(project_id, status, id);
            """
        )
        report_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(reports)").fetchall()
        }
        if "message_id" not in report_columns:
            connection.execute(
                """
                ALTER TABLE reports
                ADD COLUMN message_id INTEGER
                REFERENCES messages(id) ON DELETE SET NULL
                """
            )
        if "parent_report_id" not in report_columns:
            connection.execute(
                """
                ALTER TABLE reports
                ADD COLUMN parent_report_id INTEGER
                REFERENCES reports(id) ON DELETE SET NULL
                """
            )
        if "version_number" not in report_columns:
            connection.execute(
                """
                ALTER TABLE reports
                ADD COLUMN version_number INTEGER NOT NULL DEFAULT 1
                CHECK (version_number >= 1)
                """
            )
        # 기존 승인 데이터에 명시적으로 저장된 대체 관계만 보고서 계보로 옮깁니다.
        # 같은 프로젝트·업무이고 더 나중에 생성된 단일 대체 보고서인 경우만 연결해
        # 제목이나 생성 시각만으로 원본을 추측하지 않습니다.
        connection.execute(
            """
            UPDATE reports
            SET parent_report_id = (
                SELECT report_approvals.report_id
                FROM report_approvals
                JOIN reports AS parent_report
                  ON parent_report.id = report_approvals.report_id
                WHERE report_approvals.replacement_report_id = reports.id
                  AND parent_report.project_id = reports.project_id
                  AND parent_report.task_id IS reports.task_id
                  AND parent_report.id < reports.id
                GROUP BY report_approvals.replacement_report_id
                HAVING COUNT(*) = 1
            )
            WHERE parent_report_id IS NULL
              AND id IN (
                  SELECT report_approvals.replacement_report_id
                  FROM report_approvals
                  JOIN reports AS parent_report
                    ON parent_report.id = report_approvals.report_id
                  JOIN reports AS replacement_report
                    ON replacement_report.id = report_approvals.replacement_report_id
                  WHERE replacement_report.project_id = parent_report.project_id
                    AND replacement_report.task_id IS parent_report.task_id
                    AND parent_report.id < replacement_report.id
                  GROUP BY report_approvals.replacement_report_id
                  HAVING COUNT(*) = 1
              )
            """
        )
        connection.execute("UPDATE reports SET version_number = 1")
        connection.execute(
            """
            WITH RECURSIVE report_versions(id, version_number) AS (
                SELECT id, 1
                FROM reports
                WHERE parent_report_id IS NULL
                UNION ALL
                SELECT child.id, report_versions.version_number + 1
                FROM reports AS child
                JOIN report_versions
                  ON child.parent_report_id = report_versions.id
            )
            UPDATE reports
            SET version_number = COALESCE(
                (
                    SELECT report_versions.version_number
                    FROM report_versions
                    WHERE report_versions.id = reports.id
                ),
                1
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reports_message_id
            ON reports(message_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reports_parent_report_id
            ON reports(parent_report_id)
            """
        )
        connection.execute("PRAGMA user_version = 12")


def create_project(
    name: str,
    field: str,
    goal: str,
    start_date: str,
    target_date: str,
    budget: str,
    skills: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """새 프로젝트를 저장하고 생성된 프로젝트 ID를 반환합니다."""

    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO projects (
                name, field, goal, start_date, target_date, budget, skills
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                field,
                goal,
                start_date,
                target_date,
                budget,
                skills,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("프로젝트 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def list_projects(database_path: Path = DATABASE_PATH) -> list[dict]:
    """최근에 수정된 프로젝트부터 목록으로 반환합니다."""

    return _list_projects(_connect, database_path)


def get_project(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """선택한 프로젝트 한 건을 반환합니다."""

    return _get_project(_connect, project_id, database_path)


def delete_project(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """프로젝트와 연결된 모든 프로젝트별 기록을 삭제합니다."""

    with _connect(database_path) as connection:
        connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def add_message(
    project_id: int,
    role: str,
    content: str,
    employee_id: str | None = None,
    database_path: Path = DATABASE_PATH,
) -> int:
    """프로젝트 대화 메시지를 저장합니다."""

    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO messages (project_id, employee_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, employee_id, role, content),
        )
        connection.execute(
            """
            UPDATE projects
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (project_id,),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("메시지 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def list_messages(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """선택한 프로젝트의 대화를 오래된 순서대로 반환합니다."""

    return _list_messages(_connect, project_id, database_path)


def clear_project_messages(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """선택한 프로젝트의 대화만 삭제합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            "DELETE FROM messages WHERE project_id = ?",
            (project_id,),
        )
        connection.execute(
            """
            UPDATE projects
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (project_id,),
        )


def create_team_task(
    project_id: int,
    source_message_id: int,
    request: str,
    manager_context: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """사용자 요청을 팀 업무로 등록합니다."""

    with _connect(database_path) as connection:
        _ensure_project_reference(
            connection,
            "messages",
            source_message_id,
            project_id,
            "업무 원본 메시지",
        )
        cursor = connection.execute(
            """
            INSERT INTO team_tasks (
                project_id, source_message_id, request, manager_context
            ) VALUES (?, ?, ?, ?)
            """,
            (project_id, source_message_id, request, manager_context),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("팀 업무 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def get_task_for_source_message(
    project_id: int,
    source_message_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """같은 사용자 메시지로 이미 생성한 팀 업무가 있는지 확인합니다."""

    return _get_task_for_source_message(_connect, project_id, source_message_id, database_path)


def update_team_task_status(
    task_id: int,
    status: str,
    database_path: Path = DATABASE_PATH,
) -> None:
    """팀 업무의 진행 상태를 변경합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE team_tasks
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, task_id),
        )


def get_team_task(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """팀 업무 한 건을 ID로 반환합니다."""

    return _get_team_task(_connect, task_id, database_path)


def create_task_control(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """업무 중단과 사용자 확인 대기 상태를 저장할 제어 행을 준비합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO task_controls (task_id) VALUES (?)",
            (task_id,),
        )
        row = connection.execute(
            "SELECT * FROM task_controls WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("업무 제어 상태를 생성하지 못했습니다.")
    return dict(row)


def get_task_control(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """업무의 중단·사용자 대기 상태를 반환합니다."""

    return _get_task_control(_connect, task_id, database_path)


def update_task_control_state(
    task_id: int,
    state: str,
    database_path: Path = DATABASE_PATH,
) -> None:
    """업무 제어 상태를 변경합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO task_controls (task_id, state)
            VALUES (?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                state = excluded.state,
                updated_at = CURRENT_TIMESTAMP
            """,
            (task_id, state),
        )


def create_or_get_clarification_request(
    project_id: int,
    task_id: int,
    asked_by_employee_id: str,
    questions: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """자료 부족으로 사용자에게 물어볼 보완 질문을 저장합니다."""

    with _connect(database_path) as connection:
        _ensure_project_reference(
            connection,
            "team_tasks",
            task_id,
            project_id,
            "보완 질문 업무",
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO clarification_requests (
                project_id, task_id, asked_by_employee_id, questions
            ) VALUES (?, ?, ?, ?)
            """,
            (project_id, task_id, asked_by_employee_id, questions),
        )
        row = connection.execute(
            "SELECT * FROM clarification_requests WHERE task_id = ?",
            (task_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("사용자 확인 요청을 생성하지 못했습니다.")
    return dict(row)


def get_pending_clarification_request(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """프로젝트의 최신 업무에 연결된 미답변 보완 질문만 반환합니다."""

    return _get_pending_clarification_request(_connect, project_id, database_path)


def answer_clarification_request(
    request_id: int,
    answer: str,
    followup_task_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """사용자 답변과 이어서 시작한 후속 업무를 연결합니다."""

    with _connect(database_path) as connection:
        request = connection.execute(
            "SELECT project_id FROM clarification_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if request is None:
            raise ValueError("보완 질문 기록을 찾을 수 없습니다.")
        _ensure_project_reference(
            connection,
            "team_tasks",
            followup_task_id,
            int(request["project_id"]),
            "보완 질문의 후속 업무",
        )
        connection.execute(
            """
            UPDATE clarification_requests
            SET status = 'answered',
                answer = ?,
                followup_task_id = ?,
                updated_at = CURRENT_TIMESTAMP,
                answered_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (answer, followup_task_id, request_id),
        )


def set_employee_activity(
    project_id: int,
    employee_id: str,
    status: str,
    detail: str = "",
    task_id: int | None = None,
    database_path: Path = DATABASE_PATH,
) -> None:
    """직원의 현재 업무 상태를 프로젝트별로 저장합니다."""

    with _connect(database_path) as connection:
        if task_id is not None:
            _ensure_project_reference(
                connection,
                "team_tasks",
                task_id,
                project_id,
                "직원 활동 업무",
            )
        connection.execute(
            """
            INSERT INTO employee_activities (
                project_id, employee_id, task_id, status, detail
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id, employee_id) DO UPDATE SET
                task_id = excluded.task_id,
                status = excluded.status,
                detail = excluded.detail,
                updated_at = CURRENT_TIMESTAMP
            """,
            (project_id, employee_id, task_id, status, detail),
        )


def list_employee_activities(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """현재 프로젝트에 저장된 직원별 최신 상태를 반환합니다."""

    return _list_employee_activities(_connect, project_id, database_path)


def clear_employee_activities(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """프로젝트의 직원 실시간 상태를 초기화합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            "DELETE FROM employee_activities WHERE project_id = ?",
            (project_id,),
        )


def add_handoff(
    task_id: int,
    from_employee_id: str,
    to_employee_id: str,
    content: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """직원 간 업무 전달 내용을 저장합니다."""

    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO handoffs (
                task_id, from_employee_id, to_employee_id, content
            ) VALUES (?, ?, ?, ?)
            """,
            (task_id, from_employee_id, to_employee_id, content),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("업무 전달 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def start_employee_result(
    task_id: int,
    employee_id: str,
    input_context: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """직원의 독립 업무 실행을 시작 상태로 저장합니다."""

    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO employee_results (
                task_id, employee_id, input_context
            ) VALUES (?, ?, ?)
            """,
            (task_id, employee_id, input_context),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("직원 업무 결과 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def finish_employee_result(
    result_id: int,
    status: str,
    output: str = "",
    error: str = "",
    database_path: Path = DATABASE_PATH,
) -> None:
    """직원 업무 결과를 완료 또는 실패 상태로 저장합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE employee_results
            SET status = ?, output = ?, error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, output, error, result_id),
        )


def list_team_tasks(
    project_id: int,
    limit: int = 10,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """현재 프로젝트의 최근 팀 업무를 반환합니다."""

    return _list_team_tasks(_connect, project_id, limit, database_path)


def list_employee_results(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """팀 업무에 참여한 직원별 결과를 반환합니다."""

    return _list_employee_results(_connect, task_id, database_path)


def list_handoffs(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """팀 업무의 직원 간 전달 기록을 반환합니다."""

    return _list_handoffs(_connect, task_id, database_path)


def create_team_meeting(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> int:
    """업무별 팀 회의를 만들고 회의 ID를 반환합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO team_meetings (task_id)
            VALUES (?)
            ON CONFLICT(task_id) DO UPDATE SET
                status = 'running',
                conclusion = '',
                updated_at = CURRENT_TIMESTAMP
            """,
            (task_id,),
        )
        row = connection.execute(
            "SELECT id FROM team_meetings WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("팀 회의 ID를 생성하지 못했습니다.")
        return int(row["id"])


def add_meeting_turn(
    meeting_id: int,
    employee_id: str,
    turn_order: int,
    turn_type: str,
    content: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """직원의 회의 발언 또는 팀장의 회의 결론을 순서대로 저장합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO meeting_turns (
                meeting_id, employee_id, turn_order, turn_type, content
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(meeting_id, turn_order) DO UPDATE SET
                employee_id = excluded.employee_id,
                turn_type = excluded.turn_type,
                content = excluded.content
            """,
            (meeting_id, employee_id, turn_order, turn_type, content),
        )
        row = connection.execute(
            """
            SELECT id
            FROM meeting_turns
            WHERE meeting_id = ? AND turn_order = ?
            """,
            (meeting_id, turn_order),
        ).fetchone()
        if row is None:
            raise RuntimeError("팀 회의 발언을 저장하지 못했습니다.")
        return int(row["id"])


def finish_team_meeting(
    meeting_id: int,
    status: str,
    conclusion: str = "",
    database_path: Path = DATABASE_PATH,
) -> None:
    """팀 회의를 완료, 일부 완료 또는 실패 상태로 마칩니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE team_meetings
            SET status = ?, conclusion = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, conclusion, meeting_id),
        )


def get_team_meeting(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """업무에 연결된 팀 회의 한 건을 반환합니다."""

    return _get_team_meeting(_connect, task_id, database_path)


def list_meeting_turns(
    meeting_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """회의 발언과 결론을 실제 발언 순서대로 반환합니다."""

    return _list_meeting_turns(_connect, meeting_id, database_path)


def add_source(
    project_id: int,
    title: str,
    url: str,
    source_type: str,
    notes: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """프로젝트에서 참고할 자료나 출처를 저장합니다."""

    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO sources (project_id, title, url, source_type, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, title, url, source_type, notes),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("출처 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


_FACT_TYPES = {
    "confirmed_fact",
    "proposal",
    "unverified",
    "user_decision",
    "limitation",
}
_FACT_ORIGINS = {"user", "ai", "system"}


def _validate_fact_type_and_origin(fact_type: str, origin: str) -> None:
    """사실 기록의 분류와 작성 주체를 명확한 값으로 제한합니다."""

    if fact_type not in _FACT_TYPES:
        raise ValueError("지원하지 않는 사실 기록 분류입니다.")
    if origin not in _FACT_ORIGINS:
        raise ValueError("지원하지 않는 사실 기록 작성 주체입니다.")


def _ensure_confirmed_fact_source(
    connection: sqlite3.Connection,
    fact_type: str,
    source_id: int | None,
) -> None:
    """확정 사실은 확인된 출처만 근거로 연결되도록 확인합니다."""

    if fact_type != "confirmed_fact" or source_id is None:
        return

    source = connection.execute(
        "SELECT verification_status FROM sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    if source is None:
        raise ValueError("사실 기록의 출처를 찾을 수 없습니다.")
    if source["verification_status"] != "verified":
        raise ValueError("확정 사실에는 확인됨 상태의 출처만 연결할 수 있습니다.")


def add_fact_record(
    project_id: int,
    fact_type: str,
    content: str,
    *,
    origin: str = "user",
    source_id: int | None = None,
    source_message_id: int | None = None,
    task_id: int | None = None,
    report_id: int | None = None,
    database_path: Path = DATABASE_PATH,
) -> int | None:
    """사실·제안·미확인·사용자 결정을 근거와 함께 저장합니다."""

    normalized_content = content.strip()
    if not normalized_content:
        raise ValueError("사실 기록 내용을 입력해주세요.")
    _validate_fact_type_and_origin(fact_type, origin)

    with _connect(database_path) as connection:
        if source_id is not None:
            _ensure_project_reference(
                connection,
                "sources",
                source_id,
                project_id,
                "사실 기록의 출처",
            )
        if source_message_id is not None:
            _ensure_project_reference(
                connection,
                "messages",
                source_message_id,
                project_id,
                "사실 기록의 원본 메시지",
            )
        if task_id is not None:
            _ensure_project_reference(
                connection,
                "team_tasks",
                task_id,
                project_id,
                "사실 기록의 업무",
            )
        if report_id is not None:
            _ensure_project_reference(
                connection,
                "reports",
                report_id,
                project_id,
                "사실 기록의 보고서",
            )
        _ensure_confirmed_fact_source(connection, fact_type, source_id)
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO fact_records (
                project_id, fact_type, content, origin, source_id,
                source_message_id, task_id, report_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                fact_type,
                normalized_content,
                origin,
                source_id,
                source_message_id,
                task_id,
                report_id,
            ),
        )
        return int(cursor.lastrowid) if cursor.rowcount else None


def list_fact_records(
    project_id: int,
    limit: int = 100,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """프로젝트의 사실 기록과 연결된 출처 상태를 최근순으로 반환합니다."""

    return _list_fact_records(_connect, project_id, limit, database_path)


def update_fact_record_source(
    fact_record_id: int,
    source_id: int | None,
    database_path: Path = DATABASE_PATH,
) -> None:
    """저장된 사실 기록의 출처를 같은 프로젝트 범위에서만 변경합니다."""

    with _connect(database_path) as connection:
        fact_record = connection.execute(
            "SELECT project_id, fact_type FROM fact_records WHERE id = ?",
            (fact_record_id,),
        ).fetchone()
        if fact_record is None:
            raise ValueError("사실 기록을 찾을 수 없습니다.")
        project_id = int(fact_record["project_id"])
        if source_id is not None:
            _ensure_project_reference(
                connection,
                "sources",
                source_id,
                project_id,
                "사실 기록의 출처",
            )
        _ensure_confirmed_fact_source(
            connection,
            fact_record["fact_type"],
            source_id,
        )
        connection.execute(
            """
            UPDATE fact_records
            SET source_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (source_id, fact_record_id),
        )


def delete_fact_record(
    fact_record_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """선택한 사실 기록만 삭제합니다."""

    with _connect(database_path) as connection:
        connection.execute("DELETE FROM fact_records WHERE id = ?", (fact_record_id,))


def list_sources(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """프로젝트에 등록된 출처를 최근 등록 순서로 반환합니다."""

    return _list_sources(_connect, project_id, database_path)


def update_source_status(
    source_id: int,
    verification_status: str,
    database_path: Path = DATABASE_PATH,
) -> None:
    """출처의 확인 상태를 변경합니다."""

    allowed_statuses = {"unverified", "verified", "rejected"}
    if verification_status not in allowed_statuses:
        raise ValueError("지원하지 않는 출처 확인 상태입니다.")

    with _connect(database_path) as connection:
        source = connection.execute(
            "SELECT id FROM sources WHERE id = ?",
            (source_id,),
        ).fetchone()
        if source is None:
            raise ValueError("출처를 찾을 수 없습니다.")
        if verification_status != "verified":
            confirmed_fact = connection.execute(
                """
                SELECT id FROM fact_records
                WHERE source_id = ? AND fact_type = 'confirmed_fact'
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
            if confirmed_fact is not None:
                raise ValueError(
                    "이 출처는 확정 사실의 근거로 연결되어 있어 확인 상태를 낮출 수 없습니다."
                )
        connection.execute(
            """
            UPDATE sources
            SET verification_status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (verification_status, source_id),
        )


def delete_source(
    source_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """선택한 출처를 삭제합니다."""

    with _connect(database_path) as connection:
        fact_record = connection.execute(
            "SELECT id FROM fact_records WHERE source_id = ? LIMIT 1",
            (source_id,),
        ).fetchone()
        if fact_record is not None:
            raise ValueError(
                "이 출처는 사실 기록의 근거로 연결되어 있어 먼저 사실 기록에서 연결을 해제해야 합니다."
            )
        connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))


def create_or_get_approval(
    project_id: int,
    source_message_id: int,
    plan_content: str,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """사용자 요청에 대한 계획 승인 기록을 생성하거나 기존 기록을 반환합니다."""

    with _connect(database_path) as connection:
        _ensure_project_reference(
            connection,
            "messages",
            source_message_id,
            project_id,
            "계획 승인 원본 메시지",
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO approvals (
                project_id, source_message_id, plan_content
            ) VALUES (?, ?, ?)
            """,
            (project_id, source_message_id, plan_content),
        )
        row = connection.execute(
            """
            SELECT * FROM approvals
            WHERE project_id = ? AND source_message_id = ?
            """,
            (project_id, source_message_id),
        ).fetchone()
    if row is None:
        raise RuntimeError("승인 기록을 생성하지 못했습니다.")
    return dict(row)


def update_approval(
    approval_id: int,
    status: str,
    plan_content: str | None = None,
    user_feedback: str = "",
    increment_revision: bool = False,
    database_path: Path = DATABASE_PATH,
) -> None:
    """계획 승인 상태, 수정 의견과 최신 계획을 저장합니다."""

    decided_at_expression = (
        "CURRENT_TIMESTAMP" if status == "approved" else "NULL"
    )
    revision_expression = (
        "revision_count + 1" if increment_revision else "revision_count"
    )
    with _connect(database_path) as connection:
        connection.execute(
            f"""
            UPDATE approvals
            SET status = ?,
                plan_content = COALESCE(?, plan_content),
                user_feedback = ?,
                revision_count = {revision_expression},
                updated_at = CURRENT_TIMESTAMP,
                decided_at = {decided_at_expression}
            WHERE id = ?
            """,
            (status, plan_content, user_feedback, approval_id),
        )


def add_review(
    task_id: int,
    reviewer_employee_id: str,
    review_round: int,
    verdict: str,
    feedback: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """검수 직원의 판정과 피드백을 저장합니다."""

    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO reviews (
                task_id, reviewer_employee_id, review_round, verdict, feedback
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, reviewer_employee_id, review_round, verdict, feedback),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("검수 기록 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def add_review_targets(
    review_id: int,
    task_id: int,
    target_employee_ids: set[str] | list[str] | tuple[str, ...],
    status: str,
    database_path: Path = DATABASE_PATH,
) -> None:
    """검수 기록과 실제 재작업 대상 직원을 개별 행으로 연결합니다."""

    unique_employee_ids = sorted(
        {employee_id.strip() for employee_id in target_employee_ids if employee_id.strip()}
    )
    if not unique_employee_ids:
        return
    with _connect(database_path) as connection:
        review = connection.execute(
            "SELECT task_id FROM reviews WHERE id = ?",
            (review_id,),
        ).fetchone()
        if review is None:
            raise ValueError("검수 기록을 찾을 수 없습니다.")
        if int(review["task_id"]) != task_id:
            raise ValueError("검수 기록과 재작업 대상 업무가 일치하지 않습니다.")
        connection.executemany(
            """
            INSERT INTO review_targets (
                review_id, task_id, target_employee_id, status
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(review_id, target_employee_id) DO UPDATE SET
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            [
                (review_id, task_id, employee_id, status)
                for employee_id in unique_employee_ids
            ],
        )


def mark_review_targets_resubmitted(
    task_id: int,
    target_employee_id: str,
    rework_output: str,
    database_path: Path = DATABASE_PATH,
) -> None:
    """1차 검수 대상 직원이 제출한 실제 재작업본을 대상 기록에 저장합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE review_targets
            SET status = 'resubmitted',
                rework_output = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
              AND target_employee_id = ?
              AND status = 'rework_requested'
            """,
            (rework_output, task_id, target_employee_id),
        )


def list_review_targets(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """검수 차수·검수자와 연결된 대상 직원 및 재작업본을 반환합니다."""

    return _list_review_targets(_connect, task_id, database_path)


def list_reviews(
    task_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """팀 업무의 검수 기록을 반환합니다."""

    return _list_reviews(_connect, task_id, database_path)


def add_memory(
    project_id: int,
    content: str,
    category: str = "general",
    employee_id: str | None = None,
    source_message_id: int | None = None,
    database_path: Path = DATABASE_PATH,
) -> int | None:
    """프로젝트 장기 기억을 저장합니다. 같은 직원·원본 메시지는 중복 저장하지 않습니다."""

    with _connect(database_path) as connection:
        if source_message_id is not None:
            _ensure_project_reference(
                connection,
                "messages",
                source_message_id,
                project_id,
                "기억 원본 메시지",
            )
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO memories (
                project_id, employee_id, source_message_id, category, content
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (project_id, employee_id, source_message_id, category, content),
        )
        return int(cursor.lastrowid) if cursor.rowcount else None


def list_memories(
    project_id: int,
    limit: int = 30,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """프로젝트의 최근 장기 기억을 반환합니다."""

    return _list_memories(_connect, project_id, limit, database_path)


def delete_memory(
    memory_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """선택한 장기 기억을 삭제합니다."""

    with _connect(database_path) as connection:
        connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))


def add_project_record(
    project_id: int,
    record_type: str,
    title: str,
    content: str,
    database_path: Path = DATABASE_PATH,
) -> int:
    """프로젝트의 결정 또는 오류 기록을 저장합니다."""

    with _connect(database_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO project_records (project_id, record_type, title, content)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, record_type, title, content),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("프로젝트 기록 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def list_project_records(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """프로젝트의 결정과 오류 기록을 반환합니다."""

    return _list_project_records(_connect, project_id, database_path)


def update_project_record_status(
    record_id: int,
    status: str,
    database_path: Path = DATABASE_PATH,
) -> None:
    """결정·오류 기록의 상태를 변경합니다."""

    with _connect(database_path) as connection:
        connection.execute(
            """
            UPDATE project_records
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, record_id),
        )


def delete_project_record(
    record_id: int,
    database_path: Path = DATABASE_PATH,
) -> None:
    """선택한 결정·오류 기록을 삭제합니다."""

    with _connect(database_path) as connection:
        connection.execute("DELETE FROM project_records WHERE id = ?", (record_id,))


def add_report(
    project_id: int,
    employee_id: str,
    title: str,
    content: str,
    task_id: int | None = None,
    message_id: int | None = None,
    parent_report_id: int | None = None,
    database_path: Path = DATABASE_PATH,
) -> int:
    """보고서와 선택적 메시지·업무·직전 버전 참조를 저장합니다."""

    with _connect(database_path) as connection:
        if task_id is not None:
            _ensure_project_reference(
                connection,
                "team_tasks",
                task_id,
                project_id,
                "보고서 업무",
            )
        if message_id is not None:
            _ensure_project_reference(
                connection,
                "messages",
                message_id,
                project_id,
                "보고서 채팅 메시지",
            )
        version_number = 1
        if parent_report_id is not None:
            parent_report = connection.execute(
                """
                SELECT project_id, task_id, version_number
                FROM reports
                WHERE id = ?
                """,
                (parent_report_id,),
            ).fetchone()
            if parent_report is None:
                raise ValueError("원본 보고서를 찾을 수 없습니다.")
            if int(parent_report["project_id"]) != project_id:
                raise ValueError("원본 보고서가 현재 프로젝트에 속하지 않습니다.")
            if parent_report["task_id"] != task_id:
                raise ValueError("수정본은 원본 보고서와 같은 업무에 연결되어야 합니다.")
            version_number = int(parent_report["version_number"] or 1) + 1
        cursor = connection.execute(
            """
            INSERT INTO reports (
                project_id, task_id, message_id, parent_report_id,
                version_number, employee_id, title, content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                task_id,
                message_id,
                parent_report_id,
                version_number,
                employee_id,
                title,
                content,
            ),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("보고서 ID를 생성하지 못했습니다.")
        return int(cursor.lastrowid)


def list_reports(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """프로젝트의 보고서를 최신순으로 반환합니다."""

    return _list_reports(_connect, project_id, database_path)


def save_report_structured_data(
    report_id: int,
    project_id: int,
    proposals: list[str] | tuple[str, ...],
    unverified: list[str] | tuple[str, ...],
    limitations: list[str] | tuple[str, ...],
    database_path: Path = DATABASE_PATH,
) -> None:
    """보고서의 AI 분류 결과를 구조화 데이터와 사실 기록으로 저장합니다."""

    proposals_json = json.dumps(
        list(proposals),
        ensure_ascii=False,
    )
    unverified_json = json.dumps(
        list(unverified),
        ensure_ascii=False,
    )
    limitations_json = json.dumps(
        list(limitations),
        ensure_ascii=False,
    )

    with _connect(database_path) as connection:
        _ensure_project_reference(
            connection,
            "reports",
            report_id,
            project_id,
            "구조화 데이터의 보고서",
        )
        connection.execute(
            """
            INSERT INTO report_structured_data (
                report_id,
                project_id,
                proposals_json,
                unverified_json,
                limitations_json
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(report_id) DO UPDATE SET
                project_id = excluded.project_id,
                proposals_json = excluded.proposals_json,
                unverified_json = excluded.unverified_json,
                limitations_json = excluded.limitations_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                report_id,
                project_id,
                proposals_json,
                unverified_json,
                limitations_json,
            ),
        )
        # 같은 보고서를 다시 분류하면 이전 AI 분류 결과는 최신 구조화 정보와
        # 함께 교체합니다. 사용자가 별도로 연결한 사실 기록은 보존합니다.
        connection.execute(
            """
            DELETE FROM fact_records
            WHERE report_id = ?
              AND origin = 'ai'
              AND fact_type IN ('proposal', 'unverified', 'limitation')
            """,
            (report_id,),
        )
        report_fact_rows: list[tuple[int, str, str, str, int]] = []
        for fact_type, values in (
            ("proposal", proposals),
            ("unverified", unverified),
            ("limitation", limitations),
        ):
            for value in values:
                content = str(value).strip()
                if content:
                    report_fact_rows.append(
                        (project_id, fact_type, content, "ai", report_id)
                    )
        if report_fact_rows:
            connection.executemany(
                """
                INSERT OR IGNORE INTO fact_records (
                    project_id, fact_type, content, origin, report_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                report_fact_rows,
            )


def get_report_structured_data(
    report_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict | None:
    """저장된 구조화 보고서 데이터를 반환합니다."""
    return _get_report_structured_data(_connect, report_id, database_path)


def create_or_get_report_approval(
    project_id: int,
    report_id: int,
    database_path: Path = DATABASE_PATH,
) -> dict:
    """보고서의 사용자 승인 기록을 생성하거나 기존 기록을 반환합니다."""

    with _connect(database_path) as connection:
        _ensure_project_reference(
            connection,
            "reports",
            report_id,
            project_id,
            "승인할 보고서",
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO report_approvals (project_id, report_id)
            VALUES (?, ?)
            """,
            (project_id, report_id),
        )
        row = connection.execute(
            """
            SELECT * FROM report_approvals
            WHERE project_id = ? AND report_id = ?
            """,
            (project_id, report_id),
        ).fetchone()
    if row is None:
        raise RuntimeError("보고서 승인 기록을 생성하지 못했습니다.")
    return dict(row)


def list_report_approvals(
    project_id: int,
    database_path: Path = DATABASE_PATH,
) -> list[dict]:
    """프로젝트에 속한 보고서 승인 기록을 최신순으로 반환합니다."""

    return _list_report_approvals(_connect, project_id, database_path)


def update_report_approval(
    approval_id: int,
    status: str,
    user_feedback: str = "",
    replacement_report_id: int | None = None,
    database_path: Path = DATABASE_PATH,
) -> None:
    """보고서 승인, 수정 요청과 새 수정 보고서 연결을 저장합니다."""

    decided_at_expression = (
        "CURRENT_TIMESTAMP" if status == "approved" else "NULL"
    )
    with _connect(database_path) as connection:
        approval = connection.execute(
            """
            SELECT
                report_approvals.project_id,
                report_approvals.report_id,
                reports.task_id AS report_task_id
            FROM report_approvals
            JOIN reports ON reports.id = report_approvals.report_id
            WHERE report_approvals.id = ?
            """,
            (approval_id,),
        ).fetchone()
        if approval is None:
            raise ValueError("보고서 승인 기록을 찾을 수 없습니다.")
        if replacement_report_id is not None:
            _ensure_project_reference(
                connection,
                "reports",
                replacement_report_id,
                int(approval["project_id"]),
                "수정본 보고서",
            )
            if int(approval["report_id"]) == replacement_report_id:
                raise ValueError("수정본 보고서는 원본 보고서와 달라야 합니다.")
            replacement_report = connection.execute(
                "SELECT task_id, parent_report_id FROM reports WHERE id = ?",
                (replacement_report_id,),
            ).fetchone()
            if replacement_report is None:
                raise ValueError("수정본 보고서를 찾을 수 없습니다.")
            if replacement_report["task_id"] != approval["report_task_id"]:
                raise ValueError("수정본 보고서는 원본 보고서와 같은 업무에 연결되어야 합니다.")
            if replacement_report["parent_report_id"] != approval["report_id"]:
                raise ValueError("수정본 보고서가 승인 대상 원본에 직접 연결되어야 합니다.")
        connection.execute(
            f"""
            UPDATE report_approvals
            SET status = ?,
                user_feedback = ?,
                replacement_report_id = ?,
                updated_at = CURRENT_TIMESTAMP,
                decided_at = {decided_at_expression}
            WHERE id = ?
            """,
            (status, user_feedback, replacement_report_id, approval_id),
        )
