"""Canonical employee action sheets generated one action at a time.

Each action can use either four or eight horizontal 512x512 frames.  When an
8-frame sheet exists it is selected automatically; otherwise the current
4-frame sheet remains active.  The normalization pipeline fixes the body
center at x=256 and the soles at y=488, so neither the app nor the animation
lab needs asset-specific crop guesses.
"""

from functools import lru_cache
from pathlib import Path


ACTION_LABEL_TO_KEY = {
    "대기": "idle",
    "생각 중": "thinking",
    "작업 중": "working",
    "대화 중": "talking",
    "자료 전달": "handoff",
    "업무 완료": "complete",
    "오류·재작업": "rework",
}

ACTION_FPS = {
    "idle": 1,
    "thinking": 2,
    "working": 2,
    "talking": 2,
    "handoff": 2,
    "complete": 2,
    "rework": 2,
}

ACTION_DURATIONS = {
    "idle": 4.0,
    "thinking": 2.4,
    "working": 2.0,
    "talking": 2.0,
    "handoff": 2.0,
    "complete": 2.2,
    "rework": 2.4,
}

STAFF = {
    "yuki": {"id": "project_manager", "name": "유키"},
    "heejeong": {
        "id": "employee_258c2afdab634c0482e657eddaeddeca",
        "name": "희정",
    },
    "leo": {
        "id": "employee_6b1b55c815ab4954b4ee8f677485ce17",
        "name": "레오",
    },
    "matsuri": {
        "id": "employee_037752c7b73248eb9a92e42924cfa81c",
        "name": "마츠리",
    },
    "levi": {
        "id": "employee_9369af7654824819a7f462d39bd60d0b",
        "name": "레비",
    },
    "miko": {
        "id": "employee_45548ccdc9e14ed3bbcfd99aedcb311f",
        "name": "미코",
    },
}

FRAME_SIZE = 512
DEFAULT_FRAME_COUNT = 4
SUPPORTED_FRAME_COUNTS = (8, 4)
CONTENT_HEIGHT = 468
BASELINE = 488
BODY_CENTER = FRAME_SIZE / 2
CONTENT_BOX = (0, 0, FRAME_SIZE, FRAME_SIZE)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANIMATION_ROOT = PROJECT_ROOT / "static" / "animation_v2"


def resolve_action_sheet(slug: str, action: str) -> tuple[str, int]:
    """Return the highest supported frame-count sheet currently available."""

    for frame_count in SUPPORTED_FRAME_COUNTS:
        filename = f"{slug}_{action}_{frame_count}f.png"
        if (ANIMATION_ROOT / slug / filename).exists():
            return f"animation_v2/{slug}/{filename}", frame_count
    fallback = f"{slug}_{action}_{DEFAULT_FRAME_COUNT}f.png"
    return f"animation_v2/{slug}/{fallback}", DEFAULT_FRAME_COUNT


@lru_cache(maxsize=1)
def build_staff_app_specs() -> dict[tuple[str, str], dict[str, object]]:
    """Build the shared app animation catalog once per Python process.

    The office screen, app entry point, and animation lab all consume this
    immutable-by-convention catalog.  Caching avoids repeating the same asset
    existence checks and dictionary construction during Streamlit reruns.
    """

    specs: dict[tuple[str, str], dict[str, object]] = {}
    for slug, staff in STAFF.items():
        for action in ACTION_LABEL_TO_KEY.values():
            path, frame_count = resolve_action_sheet(slug, action)
            specs[(str(staff["id"]), action)] = {
                "path": path,
                "relative_to_static": True,
                "frame_count": frame_count,
                "sheet_size": (FRAME_SIZE * frame_count, FRAME_SIZE),
                "grid_rows": 1,
                "row_index": 0,
                "content_height": CONTENT_HEIGHT,
                "baseline": BASELINE,
                "baselines": (BASELINE,) * frame_count,
                "body_centers": (BODY_CENTER,) * frame_count,
                "content_boxes": (CONTENT_BOX,) * frame_count,
                "frame_sequence": tuple(range(frame_count)),
                "animation_duration": ACTION_DURATIONS[action],
                "loop": True,
            }
    return specs


def build_staff_lab_specs(
    project_root: Path,
) -> dict[str, dict[str, dict[str, object]]]:
    app_specs = build_staff_app_specs()
    lab_specs: dict[str, dict[str, dict[str, object]]] = {}
    for _, staff in STAFF.items():
        employee_specs: dict[str, dict[str, object]] = {}
        for action_label, action in ACTION_LABEL_TO_KEY.items():
            spec = app_specs[(str(staff["id"]), action)]
            employee_specs[action_label] = {
                "path": project_root / "static" / str(spec["path"]),
                "fps": ACTION_FPS[action],
                "frame_count": spec["frame_count"],
                "alignment": {
                    "content_height": spec["content_height"],
                    "baseline": spec["baseline"],
                    "baselines": spec["baselines"],
                    "body_centers": spec["body_centers"],
                    "content_boxes": spec["content_boxes"],
                    "grid_rows": spec["grid_rows"],
                    "row_index": spec["row_index"],
                    "frame_sequence": spec["frame_sequence"],
                    "loop": spec["loop"],
                },
            }
        lab_specs[str(staff["name"])] = employee_specs
    return lab_specs
