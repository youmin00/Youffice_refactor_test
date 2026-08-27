"""팀 의견 요청이 두 직원 의견과 유키 요약으로 끝나는지 모의 실행합니다."""

from __future__ import annotations

from types import SimpleNamespace
import time

import workflow.team_consultation as consultation


def _employee(employee_id: str, name: str, title: str) -> tuple[dict, str]:
    return (
        {
            "id": employee_id,
            "name": name,
            "title": title,
            "role_description": "",
        },
        "프로젝트팀",
    )


def run() -> None:
    saved_messages: list[tuple] = []
    activities: list[tuple] = []
    original_chat = consultation.optimized_chat
    original_add_message = consultation.add_message
    original_set_activity = consultation.set_employee_activity

    def fake_chat(*_args, **_kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(
                content=(
                    "[의견]\n필요한 조건을 먼저 정해야 합니다.\n"
                    "[추천]\n가장 간단한 방식부터 고르세요.\n"
                    "[확인 필요]\n사용 장소를 확인해 주세요."
                )
            )
        )

    consultation.optimized_chat = fake_chat
    consultation.add_message = lambda *args: saved_messages.append(args) or len(saved_messages)
    consultation.set_employee_activity = lambda *args: activities.append(args)
    try:
        manager, manager_department = _employee("project_manager", "유키", "프로젝트 팀장")
        supporting = [
            _employee("planner", "리오", "기획 담당"),
            _employee("engineer", "미츠리", "기술 설계 담당"),
        ]
        started, _ = consultation.start_team_consultation_background(
            991,
            {"name": "테스트", "goal": "화면 밝기 조절", "field": "메이커"},
            "센서를 써야 할지 모르겠어",
            manager,
            manager_department,
            supporting,
        )
        assert started
        deadline = time.time() + 2
        while consultation.is_team_consultation_running(991) and time.time() < deadline:
            time.sleep(0.01)
        assert not consultation.is_team_consultation_running(991)
        assert [message[3] for message in saved_messages] == ["engineer", "planner", "project_manager"] or [message[3] for message in saved_messages] == ["planner", "engineer", "project_manager"]
        assert any(activity[2] == "working" for activity in activities)
        assert any(activity[2] == "completed" for activity in activities)
    finally:
        consultation.optimized_chat = original_chat
        consultation.add_message = original_add_message
        consultation.set_employee_activity = original_set_activity


if __name__ == "__main__":
    run()
    print("team consultation flow checks passed")
