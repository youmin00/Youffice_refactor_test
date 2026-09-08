"""사용자 DB를 건드리지 않고 전체 Streamlit 앱의 초기 렌더링을 검사합니다."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import tempfile

from streamlit.testing.v1 import AppTest

import database


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
LIVE_DATABASE = ROOT / "data" / "youffice.db"


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _redirect_database_defaults(temporary_database: Path) -> None:
    """이미 import된 공개 DB 함수의 기본 경로를 임시 복사본으로 바꿉니다."""

    original_database = database.DATABASE_PATH
    database.DATABASE_PATH = temporary_database
    for value in vars(database).values():
        defaults = getattr(value, "__defaults__", None)
        if defaults:
            value.__defaults__ = tuple(
                temporary_database if item == original_database else item
                for item in defaults
            )
        keyword_defaults = getattr(value, "__kwdefaults__", None)
        if keyword_defaults:
            value.__kwdefaults__ = {
                key: temporary_database if item == original_database else item
                for key, item in keyword_defaults.items()
            }


def run() -> None:
    live_hash_before = _sha256(LIVE_DATABASE)
    with tempfile.TemporaryDirectory(prefix="youffice_direction_smoke_") as temp_dir:
        temporary_database = Path(temp_dir) / "youffice.db"
        if LIVE_DATABASE.exists():
            shutil.copy2(LIVE_DATABASE, temporary_database)
        _redirect_database_defaults(temporary_database)

        app = AppTest.from_file(str(APP_FILE), default_timeout=30)
        app.run(timeout=30)
        assert not app.exception, [str(error) for error in app.exception]

    assert _sha256(LIVE_DATABASE) == live_hash_before
    print("APP_DIRECTION_SMOKE_OK")


if __name__ == "__main__":
    run()
