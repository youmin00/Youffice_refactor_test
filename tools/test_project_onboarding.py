"""대화형 프로젝트 시작 단계의 네트워크 없는 회귀 검사."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conversation.project_collaboration import (
    build_idea_conversation_start_prompt,
    build_manager_collaboration_instruction,
    build_team_plan_request_prompt,
    is_manager_plan_content,
    is_substantially_repeated_reply,
)
from ui.project_onboarding import project_onboarding_stage
from ui.projects import new_project_session_updates


def main() -> None:
    project = {
        "id": 101,
        "name": "자동 화분 프로젝트",
        "goal": "흙이 마르면 물을 주는 화분을 만들고 싶다.",
    }
    idea_prompt = build_idea_conversation_start_prompt(project)
    assert "자동 화분 프로젝트" in idea_prompt
    assert "질문 하나" in idea_prompt
    assert "직원 배정 계획을 만들지 말고" in idea_prompt

    plan_prompt = build_team_plan_request_prompt(project)
    assert "자동 화분 프로젝트" in plan_prompt
    assert "미확인" in plan_prompt
    assert "승인" in plan_prompt

    collaboration_instruction = build_manager_collaboration_instruction()
    assert "최대 1개" in collaboration_instruction
    assert "웹 자료 찾기" in collaboration_instruction
    assert "디바이스마트 부품 찾기" in collaboration_instruction

    valid_plan = "\n".join(
        ("[업무 접수]", "[직원별 배정]", "[작업 순서]", "[승인 요청]")
    )
    assert is_manager_plan_content(valid_plan)
    assert not is_manager_plan_content("자연스러운 아이디어 대화")
    assert not is_manager_plan_content("[업무 접수]\n[직원별 배정]")
    repeated_answer = "좋아요. 이제 실제로 시스템을 만들 준비가 되었어요. 필요한 부품도 도와드릴게요."
    assert is_substantially_repeated_reply(
        repeated_answer,
        repeated_answer,
    )
    assert not is_substantially_repeated_reply(
        "좋아요. 먼저 센서가 필요한지 정해볼까요?",
        repeated_answer,
    )

    assert project_onboarding_stage([], None) == "project_created"
    assert project_onboarding_stage(
        [{"role": "user", "content": "시작해줘"}], None
    ) == "waiting_for_yuki"
    assert project_onboarding_stage(
        [
            {"role": "user", "content": "시작해줘"},
            {
                "role": "assistant",
                "employee_id": "employee_other",
                "content": "다른 직원 답변",
            },
        ],
        None,
    ) == "waiting_for_yuki"
    assert project_onboarding_stage(
        [
            {"role": "user", "content": "아이디어부터 이야기하자"},
            {
                "role": "assistant",
                "employee_id": "project_manager",
                "content": "어디에서 사용할 장치인가요?",
            },
        ],
        None,
    ) == "idea_conversation"
    assert project_onboarding_stage(
        [
            {"role": "user", "content": "계획을 만들어줘"},
            {
                "role": "assistant",
                "employee_id": "project_manager",
                "content": valid_plan,
            },
        ],
        None,
    ) == "plan_ready"
    assert project_onboarding_stage([], {"id": 1, "status": "running"}) == "work_started"

    session_updates = new_project_session_updates(101)
    assert session_updates["current_project_id"] == 101
    assert session_updates["loaded_project_id"] == 101
    assert session_updates["messages"] == []
    assert session_updates["workspace_view_request"] == "💬 대화"
    assert session_updates["chat_employee_request"] == "project_manager"
    assert session_updates["new_project_onboarding_id"] == 101

    print("PROJECT_ONBOARDING_REGRESSION_OK")


if __name__ == "__main__":
    main()
