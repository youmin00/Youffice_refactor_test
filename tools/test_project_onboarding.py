"""대화형 프로젝트 시작 단계의 네트워크 없는 회귀 검사."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conversation.project_collaboration import (
    MAX_GUIDED_QUESTIONS,
    SUPPLEMENTAL_QUESTION_REQUEST_MARKER,
    build_idea_conversation_start_prompt,
    build_manager_collaboration_instruction,
    build_supplemental_question_prompt,
    build_team_plan_request_prompt,
    is_explicit_plan_request,
    is_explicit_supplemental_question_request,
    is_user_information_request,
    is_manager_plan_content,
    is_substantially_repeated_reply,
    manager_guided_turn_count,
    supplemental_question_count,
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
    assert "최대 3개" in idea_prompt
    assert "프로젝트 코치" in idea_prompt

    supplemental_prompt = build_supplemental_question_prompt(project)
    assert SUPPLEMENTAL_QUESTION_REQUEST_MARKER in supplemental_prompt
    assert "왜 지금 필요한지" in supplemental_prompt
    assert "무엇이 달라지는지" in supplemental_prompt
    assert "2~3개" in supplemental_prompt
    assert "기본 가정" in supplemental_prompt

    plan_prompt = build_team_plan_request_prompt(project)
    assert "자동 화분 프로젝트" in plan_prompt
    assert "미확인" in plan_prompt
    assert "승인" in plan_prompt
    assert "실제 구매" in plan_prompt
    default_plan_prompt = build_team_plan_request_prompt(
        project,
        use_default_assumptions=True,
    )
    assert "합리적인 기본 가정" in default_plan_prompt
    assert "임의로 정하면 위험한 항목" in default_plan_prompt

    collaboration_instruction = build_manager_collaboration_instruction()
    assert "최대 1개" in collaboration_instruction
    assert "최대 3개" in collaboration_instruction
    assert "초안을 먼저" in collaboration_instruction
    assert "보충 질문을 횟수 제한 없이" in collaboration_instruction
    assert "사용자가 질문·비교·설명을 요청하면" in collaboration_instruction
    assert "CAD 도면 작성" in collaboration_instruction
    assert is_explicit_plan_request("질문 그만하고 계획 만들어줘")
    assert is_explicit_plan_request("모르는 건 기본 가정으로 진행해줘")
    assert not is_explicit_plan_request("센서 선택지를 비교해줘")
    assert is_explicit_supplemental_question_request("중요한 항목만 더 질문해줘")
    assert is_explicit_supplemental_question_request("세부적으로 같이 설계하자")
    assert not is_explicit_supplemental_question_request("바로 계획 만들어줘")
    assert is_user_information_request("초음파 센서가 야외에서도 괜찮아?")
    assert is_user_information_request("두 센서의 차이를 비교해줘")
    assert not is_user_information_request("실내에서 사용할 거야")
    assert not is_user_information_request(idea_prompt)

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
    capped_messages: list[dict] = []
    for index in range(MAX_GUIDED_QUESTIONS):
        capped_messages.extend(
            [
                {"role": "user", "content": f"답변 {index + 1}"},
                {
                    "role": "assistant",
                    "employee_id": "project_manager",
                    "content": f"핵심 질문 {index + 1}",
                },
            ]
        )
    assert manager_guided_turn_count(capped_messages) == MAX_GUIDED_QUESTIONS
    assert supplemental_question_count(capped_messages) == 0
    assert project_onboarding_stage(capped_messages, None) == "draft_ready"
    capped_messages.append(
        {
            "role": "user",
            "content": build_supplemental_question_prompt(project),
        }
    )
    assert supplemental_question_count(capped_messages) == 1
    assert project_onboarding_stage(capped_messages, None) == "waiting_for_yuki"
    capped_messages.append(
        {
            "role": "assistant",
            "employee_id": "project_manager",
            "content": "현재 초안과 보충 질문 하나",
        }
    )
    assert project_onboarding_stage(capped_messages, None) == "draft_ready"

    user_question_messages = [
        {"role": "user", "content": "학교 복도에서 사용할 거야"},
        {
            "role": "assistant",
            "employee_id": "project_manager",
            "content": "첫 핵심 질문",
        },
        {"role": "user", "content": "초음파 센서는 왜 쓰는 거야?"},
        {
            "role": "assistant",
            "employee_id": "project_manager",
            "content": "사용자의 센서 질문에 대한 답변",
        },
        {"role": "user", "content": "사람을 감지하려는 거야"},
        {
            "role": "assistant",
            "employee_id": "project_manager",
            "content": "두 번째 핵심 질문",
        },
    ]
    assert manager_guided_turn_count(user_question_messages) == 2
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
