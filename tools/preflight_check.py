from __future__ import annotations

import builtins
import dis
import importlib
import inspect
import py_compile
import sys
from pathlib import Path
from types import CodeType, ModuleType


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EXPECTED_DATABASE_PATH = (ROOT / "data" / "youffice.db").resolve()

PROJECT_PYTHON_LOCATIONS = [
    ROOT / "app.py",
    ROOT / "database.py",
    ROOT / "database_activity_queries.py",
    ROOT / "database_project_queries.py",
    ROOT / "database_meeting_queries.py",
    ROOT / "database_review_queries.py",
    ROOT / "database_report_queries.py",
    ROOT / "database_source_queries.py",
    ROOT / "database_workflow_queries.py",
    ROOT / "database_context_queries.py",
    ROOT / "conversation",
    ROOT / "workflow",
    ROOT / "ui",
    ROOT / "animation",
    ROOT / "tools",
]

MODULES_TO_IMPORT = [
    "database",
    "database_activity_queries",
    "database_project_queries",
    "database_meeting_queries",
    "database_review_queries",
    "database_report_queries",
    "database_source_queries",
    "database_workflow_queries",
    "database_context_queries",
    "conversation.employee_prompts",
    "conversation.dialogue_state",
    "conversation.ollama_client",
    "conversation.project_collaboration",
    "conversation.prompts",
    "conversation.response_formats",
    "conversation.response_recovery",
    "conversation.response_validator",
    "animation.lab",
    "animation.staff_specs",
    "ui.styles",
    "ui.chat",
    "ui.sidebar",
    "ui.console",
    "ui.office",
    "ui.project_onboarding",
    "ui.project_tools",
    "ui.projects",
    "workflow.assignment",
    "workflow.employee_execution",
    "workflow.errors",
    "workflow.final_report_execution",
    "workflow.meeting",
    "workflow.review",
    "workflow.review_execution",
    "workflow.engine",
    "workflow.external_review",
    "workflow.idea_scout",
    "workflow.web_search",
    "workflow.team_consultation",
    "workflow.recovery",
    "workflow.reporting",
    "workflow.report_revision",
    "workflow.report_revision_classifier",
    "workflow.report_revision_service",
    "workflow.structured_classifier",
    "workflow.structured_report",
]

REQUIRED_NAMES_BY_MODULE = {
    "database": [
        "DATABASE_PATH",
        "add_memory",
        "add_handoff",
        "add_message",
        "start_employee_result",
        "finish_employee_result",
        "update_team_task_status",
    ],
    "database_activity_queries": [
        "list_employee_activities",
        "list_team_tasks",
        "list_employee_results",
        "list_handoffs",
    ],
    "database_project_queries": [
        "list_projects",
        "get_project",
        "list_messages",
    ],
    "database_meeting_queries": [
        "get_team_meeting",
        "list_meeting_turns",
    ],
    "database_review_queries": [
        "list_review_targets",
        "list_reviews",
    ],
    "database_report_queries": [
        "list_reports",
        "get_report_structured_data",
        "list_report_approvals",
    ],
    "database_source_queries": [
        "list_fact_records",
        "list_sources",
    ],
    "database_workflow_queries": [
        "get_task_for_source_message",
        "get_team_task",
        "get_task_control",
        "get_pending_clarification_request",
    ],
    "database_context_queries": ["list_memories", "list_project_records"],
    "workflow.engine": [
        "execute_team_workflow_background",
        "start_team_workflow_background",
    ],
    "workflow.external_review": [
        "external_review_status",
        "run_external_cross_review",
    ],
    "workflow.idea_scout": [
        "collect_idea_scout_brief",
        "should_auto_explore_idea",
    ],
    "workflow.web_search": [
        "search_free_web",
    ],
    "workflow.team_consultation": [
        "select_team_consultants",
        "start_team_consultation_background",
        "recover_stale_team_consultation_activities",
    ],
    "workflow.employee_execution": [
        "ThreadPoolExecutor",
        "as_completed",
        "EMPLOYEE_WORKSTREAM_LABELS",
        "add_memory",
        "run_employee_workstreams",
    ],
    "workflow.meeting": [
        "run_team_meeting",
    ],
    "workflow.review_execution": [
        "run_review_cycle",
    ],
    "workflow.final_report_execution": [
        "run_final_report",
    ],
    "workflow.reporting": [
        "generate_project_report",
        "retry_task_synthesis",
    ],
    "workflow.report_revision_service": [
        "ReportRevisionResult",
        "revise_report_safely",
    ],
    "workflow.structured_report": [
        "StructuredReportAIData",
        "is_structured_final_report",
        "render_structured_final_report",
    ],
}


def database_isolation_failures(database_module: ModuleType | None) -> list[str]:
    """활성 DB와 백업 DB가 같은 실행 경로에 섞이지 않았는지 확인합니다."""

    failures: list[str] = []
    if database_module is None:
        return failures

    configured_path = Path(database_module.DATABASE_PATH).resolve()
    if configured_path != EXPECTED_DATABASE_PATH:
        failures.append(
            "활성 DB 경로 불일치: "
            f"{configured_path} (예상: {EXPECTED_DATABASE_PATH})"
        )

    data_directory = EXPECTED_DATABASE_PATH.parent
    unexpected_databases = sorted(
        path.name
        for path in data_directory.glob("*.db")
        if path.resolve() != EXPECTED_DATABASE_PATH
    )
    if unexpected_databases:
        failures.append(
            "활성 데이터 폴더에 백업·테스트 DB가 섞여 있음: "
            + ", ".join(unexpected_databases)
        )

    return failures


def project_python_files() -> list[Path]:
    files: set[Path] = set()

    for location in PROJECT_PYTHON_LOCATIONS:
        if location.is_file():
            files.add(location)
        elif location.is_dir():
            files.update(
                path
                for path in location.rglob("*.py")
                if "__pycache__" not in path.parts
            )

    return sorted(files)


def nested_code_objects(code: CodeType):
    yield code
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            yield from nested_code_objects(constant)


def module_owned_functions(module: ModuleType):
    for value in vars(module).values():
        if inspect.isfunction(value) and value.__module__ == module.__name__:
            yield value
        elif inspect.isclass(value) and value.__module__ == module.__name__:
            for member in vars(value).values():
                if isinstance(member, (staticmethod, classmethod)):
                    member = member.__func__
                if inspect.isfunction(member) and member.__module__ == module.__name__:
                    yield member


def undefined_global_references(module: ModuleType) -> list[str]:
    missing: set[str] = set()

    for function in module_owned_functions(module):
        available_names = set(function.__globals__) | set(dir(builtins))
        for code in nested_code_objects(function.__code__):
            for instruction in dis.get_instructions(code):
                if (
                    instruction.opname == "LOAD_GLOBAL"
                    and instruction.argval not in available_names
                ):
                    missing.add(str(instruction.argval))

    return sorted(missing)


def main() -> int:
    failures: list[str] = []

    python_files = project_python_files()

    for path in python_files:
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as error:
            failures.append(f"문법 오류: {path.relative_to(ROOT)} → {error}")

    loaded_modules = {}

    for module_name in MODULES_TO_IMPORT:
        try:
            loaded_modules[module_name] = importlib.import_module(module_name)
        except Exception as error:
            failures.append(f"모듈 불러오기 오류: {module_name} → {error}")

    for module_name, module in loaded_modules.items():
        for name in undefined_global_references(module):
            failures.append(f"미정의 전역 참조: {module_name}.{name}")

    for module_name, required_names in REQUIRED_NAMES_BY_MODULE.items():
        module = loaded_modules.get(module_name)
        if module is None:
            continue
        for name in required_names:
            if not hasattr(module, name):
                failures.append(f"핵심 진입점 누락: {module_name}.{name}")

    failures.extend(database_isolation_failures(loaded_modules.get("database")))

    if failures:
        print("\nPRECHECK_FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(f"PRECHECK_OK: Python 파일 {len(python_files)}개 점검 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
