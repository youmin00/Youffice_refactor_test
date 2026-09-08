"""YOUFFICE 가상 오피스 UI를 표시합니다."""

from functools import lru_cache
from pathlib import Path
import base64
import html

import streamlit as st

from animation.staff_specs import build_staff_app_specs
from database import (
    get_task_control,
    get_team_meeting,
    list_employee_activities,
    list_employee_results,
    list_handoffs,
    list_meeting_turns,
    list_reviews,
    list_team_tasks,
)
from ui.chat import profile_avatar_content


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFICE_BACKGROUND_FILE = PROJECT_ROOT / "assets" / "youffice_pixel_office.png"
EMPLOYEE_SPRITE_DIR = PROJECT_ROOT / "assets" / "sprites"
OFFICE_ROOM_DIR = PROJECT_ROOT / "assets" / "rooms"
STATIC_DIR = PROJECT_ROOT / "static"

ACTIVE_EMPLOYEE_ID = "project_manager"
EMPLOYEE_ACTION_SPRITES = build_staff_app_specs()


def office_employee_states(
    project_id: int,
    employees: list[dict],
) -> tuple[dict[str, tuple[str, str]], dict | None]:
    """최근 팀 업무 기록으로 오피스 직원들의 표시 상태를 계산합니다."""

    states = {
        employee["id"]: (
            ("waiting", "대기 중") if employee["enabled"] else ("inactive", "비활성")
        )
        for employee in employees
    }
    saved_activities = {
        activity["employee_id"]: activity
        for activity in list_employee_activities(project_id)
    }
    activity_states = {
        "waiting": ("waiting", "대기 중"),
        "assigned": ("waiting", "준비 업무 배정됨"),
        "working": ("working", "자료 작성 중"),
        "reviewing": ("reviewing", "문서 검토 중"),
        "reworking": ("working", "자료 보완 중"),
        "synthesizing": ("working", "준비서 종합 중"),
        "completed": ("complete", "준비 자료 완료"),
        "error": ("error", "오류 확인 필요"),
        "inactive": ("inactive", "비활성"),
    }
    for employee_id, activity in saved_activities.items():
        if employee_id in states:
            state_class, default_label = activity_states.get(
                activity["status"],
                ("waiting", "대기 중"),
            )
            states[employee_id] = (
                state_class,
                activity["detail"] or default_label,
            )
    recent_tasks = list_team_tasks(project_id, limit=1)
    if not recent_tasks:
        if ACTIVE_EMPLOYEE_ID in states and ACTIVE_EMPLOYEE_ID not in saved_activities:
            states[ACTIVE_EMPLOYEE_ID] = ("ready", "아이디어 접수 중")
        return states, None

    latest_task = recent_tasks[0]
    task_status = latest_task["status"]
    task_control = get_task_control(latest_task["id"])
    task_control_state = task_control["state"] if task_control is not None else "active"
    if ACTIVE_EMPLOYEE_ID in states:
        if task_control_state == "waiting_for_user":
            states[ACTIVE_EMPLOYEE_ID] = ("waiting", "사용자 답변 대기")
        elif task_control_state == "cancel_requested":
            states[ACTIVE_EMPLOYEE_ID] = ("waiting", "중단 요청 처리 중")
        elif task_control_state == "cancelled":
            states[ACTIVE_EMPLOYEE_ID] = ("inactive", "사용자가 작업 중단")
    if ACTIVE_EMPLOYEE_ID in states and ACTIVE_EMPLOYEE_ID not in saved_activities:
        manager_states = {
            "pending": ("waiting", "준비 계획 승인 대기"),
            "running": ("working", "준비 업무 조율 중"),
            "completed": ("complete", "준비서 완료"),
            "failed": ("error", "결과 확인 필요"),
        }
        states[ACTIVE_EMPLOYEE_ID] = manager_states.get(
            task_status,
            ("ready", "아이디어 접수 중"),
        )
        if task_control_state == "waiting_for_user":
            states[ACTIVE_EMPLOYEE_ID] = ("waiting", "사용자 답변 대기")
        elif task_control_state == "cancel_requested":
            states[ACTIVE_EMPLOYEE_ID] = ("waiting", "중단 요청 처리 중")
        elif task_control_state == "cancelled":
            states[ACTIVE_EMPLOYEE_ID] = ("inactive", "사용자가 작업 중단")

    for result in list_employee_results(latest_task["id"]):
        if result["employee_id"] in saved_activities:
            continue
        result_states = {
            "running": ("working", "자료 작성 중"),
            "completed": ("complete", "준비 자료 완료"),
            "failed": ("error", "자료 작성 오류"),
        }
        states[result["employee_id"]] = result_states.get(
            result["status"],
            ("waiting", "대기 중"),
        )

    for review in list_reviews(latest_task["id"]):
        if review["reviewer_employee_id"] in saved_activities:
            continue
        states[review["reviewer_employee_id"]] = (
            ("complete", "검수 통과")
            if review["verdict"] == "passed"
            else ("reviewing", "재작업 검토")
        )
    return states, latest_task


def workflow_progress_percent(
    latest_task: dict | None,
    state_counts: dict[str, int],
    enabled_employee_count: int,
) -> int:
    """Return a success-progress value without treating a failed task as 100%."""

    if latest_task is None:
        return 0
    if latest_task["status"] == "completed":
        return 100

    weighted_progress = (
        state_counts.get("complete", 0)
        + state_counts.get("reviewing", 0) * 0.72
        + state_counts.get("working", 0) * 0.48
    )
    return max(
        6,
        min(94, round(weighted_progress / max(1, enabled_employee_count) * 100)),
    )


@lru_cache(maxsize=1)
def office_background_data() -> str:
    """브라우저가 캐시할 수 있는 픽셀 오피스 배경 주소를 반환합니다."""

    static_background = STATIC_DIR / "youffice_pixel_office.png"
    if static_background.exists():
        return "/app/static/youffice_pixel_office.png"
    encoded = base64.b64encode(OFFICE_BACKGROUND_FILE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=16)
def office_room_background_data(employee_id: str) -> str:
    """직원 고정 ID에 연결된 독립 사무실 배경 주소를 반환합니다."""

    filename = f"{employee_id}.png"
    static_background = STATIC_DIR / "rooms" / filename
    if static_background.exists():
        return f"/app/static/rooms/{filename}"
    room_background = OFFICE_ROOM_DIR / filename
    if room_background.exists():
        encoded = base64.b64encode(room_background.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    return office_background_data()


@lru_cache(maxsize=1)
def meeting_room_background_data() -> str:
    """팀 회의실 배경 주소를 반환합니다."""

    filename = "meeting_room.png"
    static_background = STATIC_DIR / "rooms" / filename
    if static_background.exists():
        return f"/app/static/rooms/{filename}"
    room_background = OFFICE_ROOM_DIR / filename
    if room_background.exists():
        encoded = base64.b64encode(room_background.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    return office_background_data()


@lru_cache(maxsize=32)
def employee_sprite_data(employee_id: str) -> str:
    """브라우저가 캐시할 수 있는 직원별 전신 캐릭터 주소를 반환합니다."""

    if employee_id == ACTIVE_EMPLOYEE_ID:
        yuki_pixel_master = (
            STATIC_DIR / "animation" / "yuki" / "yuki_pixel_master.png"
        )
        if yuki_pixel_master.exists():
            return (
                "/app/static/animation/yuki/yuki_pixel_master.png"
                f"?v={yuki_pixel_master.stat().st_mtime_ns}"
            )

    static_sprite = STATIC_DIR / "sprites" / f"{employee_id}.png"
    if static_sprite.exists():
        return f"/app/static/sprites/{employee_id}.png"
    sprite_path = EMPLOYEE_SPRITE_DIR / f"{employee_id}.png"
    if not sprite_path.exists():
        return ""
    encoded = base64.b64encode(sprite_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def employee_sprite_content(employee: dict) -> str:
    """오피스 캐릭터용 전신 스프라이트 HTML을 만듭니다."""

    sprite_data = employee_sprite_data(employee["id"])
    if sprite_data:
        return (
            f'<img class="office-sprite" src="{sprite_data}" '
            f'alt="{html.escape(employee["name"], quote=True)} 전신 캐릭터">'
        )
    return f'<div class="office-sprite-fallback">{profile_avatar_content(employee)}</div>'


@lru_cache(maxsize=64)
def employee_action_sprite_data(
    employee_id: str,
    action_name: str,
) -> dict[str, object] | None:
    """행동별 스프라이트 주소와 크기·중심 보정 정보를 반환합니다."""

    animation_spec = EMPLOYEE_ACTION_SPRITES.get((employee_id, action_name))
    if animation_spec is None:
        return None
    relative_path = str(animation_spec["path"])
    relative_to_static = bool(animation_spec.get("relative_to_static"))
    animation_path = (
        STATIC_DIR / relative_path
        if relative_to_static
        else STATIC_DIR / "animation" / relative_path
    )
    if not animation_path.exists():
        return None
    asset_url = (
        f"/app/static/{relative_path}"
        if relative_to_static
        else f"/app/static/animation/{relative_path}"
    )
    return {
        **animation_spec,
        "url": f"{asset_url}?v={animation_path.stat().st_mtime_ns}",
    }


def employee_animation_action(
    state_class: str,
    state_label: str,
    activity_detail: str,
    is_handoff_sender: bool = False,
) -> str:
    """업무 상태 문구를 실제 캐릭터 행동 이름으로 변환합니다."""

    if is_handoff_sender:
        return "handoff"
    if state_class == "complete":
        return "complete"
    if state_class == "error":
        return "rework"
    if state_class == "reviewing":
        return "thinking"
    if state_class in {"ready", "waiting", "inactive"}:
        return "idle"

    state_text = f"{state_label} {activity_detail}"
    if any(keyword in state_text for keyword in ("재작업", "수정", "오류")):
        return "rework"
    if any(keyword in state_text for keyword in ("회의", "대화", "의견")):
        return "talking"
    if any(
        keyword in state_text
        for keyword in ("생각", "검토", "조율", "종합", "계획", "확인", "분석")
    ):
        return "thinking"
    if state_class == "working":
        return "working"
    return "idle"


def render_pixel_office(
    project: dict,
    departments: list[dict],
    employees: list[dict],
) -> tuple[dict[str, tuple[str, str]], dict | None]:
    """현재 조직과 업무 상태를 픽셀 오피스 화면으로 표시합니다."""

    if not OFFICE_BACKGROUND_FILE.exists():
        st.error("픽셀 오피스 배경 파일을 찾지 못했습니다.")
        return {}, None

    background_data = office_background_data()
    states, latest_task = office_employee_states(project["id"], employees)
    task_is_running = latest_task is not None and latest_task["status"] == "running"
    room_positions = [
        [(19, 24), (34, 35), (22, 46), (39, 23)],
        [(65, 25), (79, 36), (66, 45), (83, 24)],
        [(19, 68), (35, 79), (22, 85), (41, 67)],
        [(65, 69), (80, 80), (66, 87), (84, 67)],
    ]
    department_colors = ["#6f8cff", "#f2ad3b", "#31b7ae", "#a978e8"]
    status_icons = {
        "ready": "💬",
        "waiting": "☕",
        "working": "⌨",
        "reviewing": "🔍",
        "complete": "✓",
        "error": "!",
        "inactive": "–",
    }

    room_labels: list[str] = []
    office_layout: list[tuple[dict, int, int, str, int]] = []
    employee_positions: dict[str, tuple[int, int]] = {}
    for department_index, department in enumerate(departments[:4]):
        room_label_positions = [(8, 7), (60, 7), (8, 55), (60, 55)]
        label_left, label_top = room_label_positions[department_index]
        room_labels.append(
            f'<div class="office-room-label" style="left:{label_left}%;top:{label_top}%;'
            f'--room-color:{department_colors[department_index]}">'
            f'{html.escape(department["name"])}</div>'
        )
        department_employees = [
            employee
            for employee in employees
            if employee["department_id"] == department["id"]
        ]
        for employee_index, employee in enumerate(department_employees[:4]):
            left, top = room_positions[department_index][employee_index]
            office_layout.append(
                (
                    employee,
                    left,
                    top,
                    department_colors[department_index],
                    employee_index,
                )
            )
            employee_positions[employee["id"]] = (left, top)

    active_handoffs: list[dict] = []
    if task_is_running:
        active_handoffs = list_handoffs(latest_task["id"])[-3:]
    latest_handoff = active_handoffs[-1] if active_handoffs else None
    employees_by_office_id = {
        employee["id"]: employee for employee in employees
    }
    handoff_paths: list[str] = []
    for handoff_index, handoff in enumerate(active_handoffs):
        start_position = employee_positions.get(handoff["from_employee_id"])
        end_position = employee_positions.get(handoff["to_employee_id"])
        if start_position is None or end_position is None:
            continue
        start_x, start_y = start_position
        end_x, end_y = end_position
        path_start_x = start_x * 10
        path_start_y = round(start_y * 5.625, 1)
        path_end_x = end_x * 10
        path_end_y = round(end_y * 5.625, 1)
        path_data = (
            f"M {path_start_x} {path_start_y} "
            f"L {path_end_x} {path_end_y}"
        )
        route_class = " latest" if handoff is latest_handoff else ""
        animation_delay = handoff_index * 0.16
        handoff_paths.append(
            f'<g class="office-handoff-route{route_class}">'
            f'<path class="office-handoff-line" d="{path_data}" pathLength="100" />'
            f'<circle class="office-handoff-point" cx="{path_start_x}" cy="{path_start_y}" r="5" />'
            f'<circle class="office-handoff-point" cx="{path_end_x}" cy="{path_end_y}" r="5" />'
            f'<g class="office-file-packet" style="animation-delay:{animation_delay}s">'
            f'<animateMotion dur="0.9s" begin="{animation_delay}s" '
            f'repeatCount="indefinite" path="{path_data}" />'
            f'<rect x="-9" y="-7" width="18" height="14" rx="3" />'
            f'<path d="M -4 -2 H 4 M -4 2 H 2" />'
            f'</g></g>'
        )

    latest_from_id = (
        latest_handoff["from_employee_id"] if latest_handoff is not None else None
    )
    latest_to_id = (
        latest_handoff["to_employee_id"] if latest_handoff is not None else None
    )
    agent_elements: list[str] = []
    for employee, left, top, agent_color, employee_index in office_layout:
        state_class, state_label = states.get(
            employee["id"],
            ("waiting", "대기 중"),
        )
        if state_class in {"complete", "error", "inactive"}:
            motion_class = "motion-still"
        elif state_class == "reviewing":
            motion_class = "motion-review"
        elif state_class == "working" and "재작업" in state_label:
            motion_class = "motion-rework"
        elif state_class == "working" and (
            "종합" in state_label
            or "조율" in state_label
            or "회의" in state_label
        ):
            motion_class = "motion-coordinate"
        elif state_class == "working":
            motion_class = "motion-work"
        else:
            motion_class = "motion-idle"

        route_endpoint_class = ""
        if employee["id"] == latest_from_id:
            route_endpoint_class = " handoff-sender"
        elif employee["id"] == latest_to_id:
            route_endpoint_class = " handoff-receiver"
        walk_x = 15 if employee_index % 2 == 0 else -15
        walk_y = 7 if employee_index < 2 else -7
        agent_elements.append(
            f'<a class="office-agent state-{state_class} {motion_class}'
            f'{route_endpoint_class}" '
            f'href="?employee={html.escape(employee["id"], quote=True)}" '
            f'target="_self" aria-label="{html.escape(employee["name"], quote=True)}와 대화" '
            f'style="left:{left}%;top:{top}%;--agent-color:'
            f'{agent_color};--walk-x:{walk_x}px;--walk-y:{walk_y}px;'
            f'--motion-delay:-{employee_index * 0.13}s">'
            f'<div class="office-status-bubble">'
            f'{status_icons[state_class]} {html.escape(state_label)}</div>'
            f'<div class="office-character">'
            f'{employee_sprite_content(employee)}'
            f'<div class="office-character-shadow"></div>'
            f'</div>'
            f'<div class="office-agent-name">{html.escape(employee["name"])}</div>'
            f'<div class="office-agent-title">{html.escape(employee["title"])}</div>'
            f'</a>'
        )

    if latest_handoff is not None:
        from_employee = employees_by_office_id.get(latest_handoff["from_employee_id"])
        to_employee = employees_by_office_id.get(latest_handoff["to_employee_id"])
        from_name = (
            from_employee["name"]
            if from_employee is not None
            else latest_handoff["from_employee_id"]
        )
        to_name = (
            to_employee["name"]
            if to_employee is not None
            else latest_handoff["to_employee_id"]
        )
        handoff_summary = f"📨 준비 자료 전달 중 · {from_name} → {to_name}"
    else:
        handoff_summary = "📭 새로운 준비 자료 대기 중"

    task_status_labels = {
        "pending": "승인 대기",
        "running": "제작 준비 협업 중",
        "completed": "최근 준비서 작성 완료",
        "failed": "확인 필요한 준비 업무 있음",
    }
    current_status = (
        task_status_labels.get(latest_task["status"], latest_task["status"])
        if latest_task is not None
        else "새 프로젝트 아이디어 대기 중"
    )
    latest_request = (
        latest_task["request"] if latest_task is not None else project["goal"]
    )
    enabled_employees = [employee for employee in employees if employee["enabled"]]
    state_counts: dict[str, int] = {}
    for state_class, _ in states.values():
        state_counts[state_class] = state_counts.get(state_class, 0) + 1
    progress = workflow_progress_percent(
        latest_task,
        state_counts,
        len(enabled_employees),
    )

    focus_employee = next(
        (
            employee
            for preferred_state in ("reviewing", "working", "error")
            for employee in enabled_employees
            if states.get(employee["id"], ("waiting", ""))[0] == preferred_state
        ),
        next(
            (
                employee for employee in enabled_employees
                if employee["id"] == ACTIVE_EMPLOYEE_ID
            ),
            enabled_employees[0] if enabled_employees else employees[0],
        ),
    )
    focus_state, focus_label = states.get(focus_employee["id"], ("waiting", "대기 중"))
    focus_sprite = employee_sprite_data(focus_employee["id"])
    team_cards: list[str] = []
    for employee in enabled_employees:
        state_class, state_label = states.get(employee["id"], ("waiting", "대기 중"))
        sprite_data = employee_sprite_data(employee["id"])
        sprite_html = (
            f'<img src="{sprite_data}" alt="">'
            if sprite_data
            else profile_avatar_content(employee)
        )
        team_cards.append(
            f'<a class="game-team-card state-{state_class}" '
            f'href="?employee={html.escape(employee["id"], quote=True)}" target="_self">'
            f'<div class="game-team-avatar">{sprite_html}</div>'
            f'<div class="game-team-copy"><strong>{html.escape(employee["name"])}</strong>'
            f'<span>{html.escape(employee["title"])}</span></div>'
            f'<div class="game-team-state"><i></i>{html.escape(state_label)}</div></a>'
        )

    map_html = f"""
        <div class="office-dashboard-header">
            <div>
                <div class="office-eyebrow">LIVE YOUFFICE WORKSPACE</div>
                <div class="office-project-name">{html.escape(project['name'])}</div>
            </div>
            <div class="office-live-status"><span></span>{html.escape(current_status)}</div>
        </div>
        <div class="game-stat-strip">
            <div><strong>{len(enabled_employees)}</strong><span>활성 직원</span></div>
            <div><strong>{state_counts.get('working', 0)}</strong><span>자료 작성 중</span></div>
            <div><strong>{state_counts.get('reviewing', 0)}</strong><span>문서 검토 중</span></div>
            <div><strong>{progress}%</strong><span>준비서 진행률</span></div>
        </div>
        <div class="pixel-office-stage" style="background-image:url('{background_data}')">
            {''.join(room_labels)}
            <svg class="office-handoff-layer" viewBox="0 0 1000 562.5" preserveAspectRatio="none" aria-hidden="true">{''.join(handoff_paths)}</svg>
            {''.join(agent_elements)}
        </div>
        <div class="office-activity-bar">
            <span class="office-activity-icon">▸</span>
            <div class="office-activity-copy"><strong>{html.escape(current_status)}</strong><br>
            <span>{html.escape(latest_request[:180])}</span>
            <div class="office-handoff-summary">{html.escape(handoff_summary)}</div></div>
        </div>
    """
    focus_sprite_html = (
        f'<img src="{focus_sprite}" alt="{html.escape(focus_employee["name"], quote=True)}">'
        if focus_sprite
        else profile_avatar_content(focus_employee)
    )
    panel_html = f"""
        <aside class="game-live-panel">
            <div class="game-panel-kicker">ACTIVE AGENT</div>
            <a class="game-focus-card state-{focus_state}" href="?employee={html.escape(focus_employee['id'], quote=True)}" target="_self">
                <div class="game-focus-portrait">{focus_sprite_html}</div>
                <div class="game-focus-copy">
                    <strong>{html.escape(focus_employee['name'])}</strong>
                    <span>{html.escape(focus_employee['title'])}</span>
                    <em><i></i>{html.escape(focus_label)}</em>
                </div>
            </a>
            <div class="game-progress-head"><span>제작 준비 진행률</span><strong>{progress}%</strong></div>
            <div class="game-progress-track"><span style="width:{progress}%"></span></div>
            <div class="game-panel-section-title">실시간 팀 현황</div>
            <div class="game-team-list">{''.join(team_cards)}</div>
            <div class="game-panel-tip">캐릭터를 누르면 직원 콘솔과 직접 대화 메뉴가 열립니다.</div>
        </aside>
    """
    map_column, panel_column = st.columns([4.5, 1.35], gap="medium")
    with map_column:
        st.markdown(map_html, unsafe_allow_html=True)
    with panel_column:
        st.markdown(panel_html, unsafe_allow_html=True)
    return states, latest_task


def render_employee_room_office(
    project: dict,
    departments: list[dict],
    employees: list[dict],
) -> tuple[dict[str, tuple[str, str]], dict | None]:
    """직원마다 독립 배경을 사용하는 6개 작업실 오피스를 표시합니다."""

    states, latest_task = office_employee_states(project["id"], employees)
    activities_by_id = {
        activity["employee_id"]: activity
        for activity in list_employee_activities(project["id"])
    }
    departments_by_id = {
        department["id"]: department["name"] for department in departments
    }
    employees_by_id = {employee["id"]: employee for employee in employees}
    enabled_employees = [employee for employee in employees if employee["enabled"]]

    latest_handoff = None
    if latest_task is not None:
        handoffs = list_handoffs(latest_task["id"])
        latest_handoff = handoffs[-1] if handoffs else None

    latest_from_id = (
        latest_handoff["from_employee_id"] if latest_handoff is not None else None
    )
    latest_to_id = (
        latest_handoff["to_employee_id"] if latest_handoff is not None else None
    )
    if latest_handoff is not None:
        from_employee = employees_by_id.get(latest_from_id)
        to_employee = employees_by_id.get(latest_to_id)
        from_name = from_employee["name"] if from_employee else latest_from_id
        to_name = to_employee["name"] if to_employee else latest_to_id
        handoff_summary = f"📨 최근 자료 전달 · {from_name} → {to_name}"
    else:
        handoff_summary = "📭 새로운 준비 자료 대기 중"

    task_status_labels = {
        "pending": "승인 대기",
        "running": "제작 준비 협업 중",
        "completed": "최근 준비서 작성 완료",
        "failed": "확인 필요한 준비 업무 있음",
    }
    current_status = (
        task_status_labels.get(latest_task["status"], latest_task["status"])
        if latest_task is not None
        else "새 프로젝트 아이디어 대기 중"
    )
    latest_request = (
        latest_task["request"] if latest_task is not None else project["goal"]
    )

    state_counts: dict[str, int] = {}
    for state_class, _ in states.values():
        state_counts[state_class] = state_counts.get(state_class, 0) + 1
    progress = workflow_progress_percent(
        latest_task,
        state_counts,
        len(enabled_employees),
    )

    room_labels = {
        "project_manager": "프로젝트 팀장실",
        "employee_258c2afdab634c0482e657eddaeddeca": "기억·자료실",
        "employee_6b1b55c815ab4954b4ee8f677485ce17": "기획실",
        "employee_037752c7b73248eb9a92e42924cfa81c": "기술 설계실",
        "employee_9369af7654824819a7f462d39bd60d0b": "안전·품질 검수실",
        "employee_45548ccdc9e14ed3bbcfd99aedcb311f": "프로젝트 준비서실",
    }
    room_accents = ["#7aa2ff", "#ff9bb5", "#f5b45b", "#7cc7d8", "#73a8ff", "#e2a46e"]
    status_icons = {
        "ready": "💬",
        "waiting": "☕",
        "working": "⌨",
        "reviewing": "🔍",
        "complete": "✓",
        "error": "!",
        "inactive": "–",
    }
    room_cards: list[str] = []
    for employee_index, employee in enumerate(employees):
        state_class, state_label = states.get(employee["id"], ("waiting", "대기 중"))
        activity = activities_by_id.get(employee["id"], {})
        activity_detail = (activity.get("detail") or state_label).strip()
        room_name = room_labels.get(
            employee["id"],
            f"{departments_by_id.get(employee['department_id'], '개인')} 작업실",
        )
        room_background = office_room_background_data(employee["id"])
        accent = room_accents[employee_index % len(room_accents)]
        handoff_class = ""
        handoff_badge = ""
        handoff_button = ""
        if employee["id"] == latest_from_id:
            handoff_class = " is-sending"
            handoff_badge = '<span class="employee-room-handoff">자료 전달 중</span>'
        elif employee["id"] == latest_to_id:
            handoff_class = " is-receiving"
            handoff_badge = '<span class="employee-room-handoff">새 자료 도착</span>'
            handoff_button = (
                f'<a class="employee-room-data-button" '
                f'href="?handoff_id={latest_handoff["id"]}" target="_self">'
                f'자료 확인</a>'
            )
        is_active_handoff_sender = (
            latest_task is not None
            and latest_task["status"] == "running"
            and employee["id"] == latest_from_id
        )
        animation_action = employee_animation_action(
            state_class,
            state_label,
            activity_detail,
            is_handoff_sender=is_active_handoff_sender,
        )
        action_sprite_spec = employee_action_sprite_data(
            employee["id"],
            animation_action,
        )
        character_class = ""
        if (
            action_sprite_spec
            and int(action_sprite_spec["frame_count"]) in {4, 8}
        ):
            character_class = f" has-frame-animation action-{animation_action}"
            frame_count = int(action_sprite_spec["frame_count"])
            sheet_width, sheet_height = action_sprite_spec["sheet_size"]
            body_centers = action_sprite_spec["body_centers"]
            content_boxes = action_sprite_spec["content_boxes"]
            content_height = float(action_sprite_spec["content_height"])
            baseline = float(action_sprite_spec["baseline"])
            baselines = tuple(
                float(value)
                for value in action_sprite_spec.get(
                    "baselines",
                    (baseline,) * frame_count,
                )
            )
            grid_rows = max(1, int(action_sprite_spec.get("grid_rows", 1)))
            row_index = min(
                grid_rows - 1,
                max(0, int(action_sprite_spec.get("row_index", 0))),
            )
            frame_starts = [
                round(frame_index * sheet_width / frame_count)
                for frame_index in range(frame_count + 1)
            ]
            row_starts = [
                round(grid_row * sheet_height / grid_rows)
                for grid_row in range(grid_rows + 1)
            ]
            row_start = row_starts[row_index]
            cell_height = row_starts[row_index + 1] - row_start
            frame_sequence = tuple(
                int(frame_index)
                for frame_index in action_sprite_spec.get(
                    "frame_sequence",
                    tuple(range(frame_count)),
                )
            )
            if len(frame_sequence) != frame_count:
                frame_sequence = tuple(range(frame_count))
            viewport_aspect = 0.75
            target_content_height = 0.92
            crop_padding = 3
            frame_layers = []
            for display_frame_index, source_frame_index in enumerate(frame_sequence):
                frame_start = frame_starts[source_frame_index]
                cell_width = (
                    frame_starts[source_frame_index + 1] - frame_start
                )
                box_x, box_y, box_width, box_height = content_boxes[
                    source_frame_index
                ]
                crop_x = max(0, int(box_x) - crop_padding)
                crop_y = max(0, int(box_y) - crop_padding)
                crop_right = min(
                    cell_width,
                    int(box_x) + int(box_width) + crop_padding,
                )
                crop_bottom = min(
                    cell_height,
                    int(box_y) + int(box_height) + crop_padding,
                )
                crop_width = max(1, crop_right - crop_x)
                crop_height = max(1, crop_bottom - crop_y)
                source_scale = target_content_height / content_height
                layer_width_percent = (
                    crop_width * source_scale / viewport_aspect * 100
                )
                layer_height_percent = crop_height * source_scale * 100
                layer_left_percent = 50 - (
                    (float(body_centers[source_frame_index]) - crop_x)
                    * source_scale
                    / viewport_aspect
                    * 100
                )
                layer_top_percent = 96 - (
                    (baselines[source_frame_index] - crop_y)
                    * source_scale
                    * 100
                )
                image_height_percent = float(sheet_height) / crop_height * 100
                image_left_percent = -(
                    float(frame_start + crop_x) / crop_width * 100
                )
                image_top_percent = -(
                    float(row_start + crop_y) / crop_height * 100
                )
                layer_style = (
                    f"left:{layer_left_percent:.3f}%;"
                    f"top:{layer_top_percent:.3f}%;"
                    f"width:{layer_width_percent:.3f}%;"
                    f"height:{layer_height_percent:.3f}%;"
                )
                image_style = (
                    f"left:{image_left_percent:.3f}%;"
                    f"top:{image_top_percent:.3f}%;"
                    f"height:{image_height_percent:.3f}%;"
                )
                frame_layers.append(
                    f'<span class="employee-animation-frame frame-index-{display_frame_index + 1}" '
                    f'style="{layer_style}">'
                    f'<img src="{action_sprite_spec["url"]}" style="{image_style}" '
                    f'alt="" aria-hidden="true">'
                    f'</span>'
                )
            animation_duration = action_sprite_spec.get("animation_duration")
            frame_style_parts = []
            if animation_duration is not None:
                frame_style_parts.append(
                    f"--frame-duration:{float(animation_duration):.2f}s"
                )
            if not bool(action_sprite_spec.get("loop", True)):
                frame_style_parts.append("--frame-iterations:1")
            duration_style = (
                f' style="{";".join(frame_style_parts)}"'
                if frame_style_parts
                else ""
            )
            character_html = (
                f'<span class="employee-frame-sprite frames-{frame_count}"{duration_style} '
                f'role="img" aria-label="{html.escape(employee["name"], quote=True)} '
                f'{html.escape(state_label, quote=True)} 애니메이션">'
                f'{"".join(frame_layers)}'
                f'</span>'
            )
        else:
            sprite = employee_sprite_data(employee["id"])
            character_html = (
                f'<img src="{sprite}" alt="{html.escape(employee["name"], quote=True)} 캐릭터">'
                if sprite
                else profile_avatar_content(employee)
            )
        room_cards.append(
            f'<article class="employee-room-card state-{state_class}{handoff_class}" '
            f'style="--room-accent:{accent};--room-delay:-{employee_index * 0.18}s">'
            f'<a class="employee-room-scene" '
            f'href="?employee={html.escape(employee["id"], quote=True)}" target="_self" '
            f'aria-label="{html.escape(employee["name"], quote=True)} 작업실 열기" '
            f'style="background-image:url(\'{room_background}\')">'
            f'<div class="employee-room-shade"></div>'
            f'<div class="employee-room-heading"><span>{html.escape(room_name)}</span>'
            f'<em>{html.escape(departments_by_id.get(employee["department_id"], ""))}</em></div>'
            f'<div class="employee-room-status">{status_icons.get(state_class, "•")} '
            f'{html.escape(state_label)}</div>{handoff_badge}'
            f'<div class="employee-room-character{character_class}">'
            f'{character_html}<i></i></div>'
            f'<div class="employee-room-working-light"></div>'
            f'</a>'
            f'<div class="employee-room-footer">'
            f'<div><strong>{html.escape(employee["name"])}</strong>'
            f'<span>{html.escape(employee["title"])}</span></div>'
            f'<p>{html.escape(activity_detail[:100])}</p>'
            f'<div class="employee-room-actions">{handoff_button}'
            f'<a class="employee-room-open-button" '
            f'href="?employee={html.escape(employee["id"], quote=True)}" target="_self">'
            f'작업실 →</a></div></div></article>'
        )

    meeting = get_team_meeting(latest_task["id"]) if latest_task is not None else None
    meeting_status_labels = {
        "running": "회의 진행 중",
        "completed": "회의 완료",
        "partial": "일부 의견 확인 필요",
        "failed": "회의 결과 확인 필요",
    }
    meeting_status = (
        meeting_status_labels.get(meeting["status"], meeting["status"])
        if meeting is not None
        else "다음 팀 회의 대기"
    )
    meeting_turn_count = len(list_meeting_turns(meeting["id"])) if meeting else 0
    meeting_state_class = " meeting-active" if meeting and meeting["status"] == "running" else ""
    participant_html: list[str] = []
    for employee in enabled_employees:
        sprite = employee_sprite_data(employee["id"])
        participant = (
            f'<img src="{sprite}" alt="{html.escape(employee["name"], quote=True)}">'
            if sprite
            else f'<span>{html.escape(employee.get("emoji", "AI"))}</span>'
        )
        participant_html.append(
            f'<i title="{html.escape(employee["name"], quote=True)}">{participant}</i>'
        )

    meeting_background = meeting_room_background_data()
    dashboard_html = f"""
        <div class="office-dashboard-header employee-office-header">
            <div>
                <div class="office-eyebrow">YOUFFICE · INDIVIDUAL WORKSPACES</div>
                <div class="office-project-name">{html.escape(project['name'])}</div>
            </div>
            <div class="office-live-status"><span></span>{html.escape(current_status)}</div>
        </div>
        <div class="game-stat-strip employee-office-stats">
            <div><strong>{len(enabled_employees)}</strong><span>활성 직원</span></div>
            <div><strong>{state_counts.get('working', 0)}</strong><span>자료 작성 중</span></div>
            <div><strong>{state_counts.get('reviewing', 0)}</strong><span>문서 검토 중</span></div>
            <div><strong>{progress}%</strong><span>준비서 진행률</span></div>
        </div>
        <div class="employee-room-grid">{''.join(room_cards)}</div>
        <a class="meeting-room-card{meeting_state_class}" href="?meeting_room=1" target="_self" aria-label="팀 회의실 열기">
            <div class="meeting-room-background" style="background-image:url('{meeting_background}')"></div>
            <div class="meeting-room-overlay"></div>
            <div class="meeting-room-copy">
                <span>TEAM CONFERENCE</span>
                <strong>팀 회의실</strong>
                <p>{html.escape(meeting_status)} · 저장된 발언 {meeting_turn_count}건</p>
                <b>회의 기록 확인 →</b>
            </div>
            <div class="meeting-room-participants">{''.join(participant_html)}</div>
        </a>
        <div class="office-activity-bar employee-office-activity">
            <span class="office-activity-icon">▸</span>
            <div class="office-activity-copy"><strong>{html.escape(current_status)}</strong><br>
            <span>{html.escape(latest_request[:200])}</span>
            <div class="office-handoff-summary">{html.escape(handoff_summary)}</div></div>
        </div>
    """
    st.markdown(dashboard_html, unsafe_allow_html=True)
    return states, latest_task


@st.fragment(run_every=1.0)
def render_live_pixel_office(
    project: dict,
    departments: list[dict],
    employees: list[dict],
) -> None:
    """AI 작업 중 SQLite 상태를 1초 간격으로 다시 읽어 표시합니다."""

    render_employee_room_office(project, departments, employees)
