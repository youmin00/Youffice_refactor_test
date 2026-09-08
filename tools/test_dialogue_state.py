"""대화 단계와 질문 종료 조건의 대표 흐름을 빠르게 확인합니다."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conversation.dialogue_state import (
    build_dialogue_state_instruction,
    determine_dialogue_state,
)
from conversation.project_collaboration import SUPPLEMENTAL_QUESTION_REQUEST_MARKER


def _messages(user_text: str) -> list[dict]:
    return [
        {"role": "assistant", "content": "이동 방식을 골라볼까요?"},
        {"role": "user", "content": user_text},
    ]


def _three_yuki_turns(user_text: str) -> list[dict]:
    messages: list[dict] = []
    for index in range(3):
        messages.extend(
            [
                {"role": "user", "content": f"답변 {index + 1}"},
                {
                    "role": "assistant",
                    "employee_id": "project_manager",
                    "content": f"핵심 질문 {index + 1}",
                },
            ]
        )
    messages.append({"role": "user", "content": user_text})
    return messages


def run() -> None:
    assert determine_dialogue_state(_messages("좋아")) == "continue_previous"
    assert determine_dialogue_state(_messages("모터는 어떤 걸 골라야 해?")) == "decision"
    assert determine_dialogue_state(_messages("디바이스마트에서 가격을 찾아줘")) == "research"
    assert determine_dialogue_state(_messages("학교 안전 도우미를 만들고 싶어")) == "discovery"
    assert determine_dialogue_state(_messages("응"), plan_request_pending=True) == "planning"
    assert determine_dialogue_state(_messages("응"), has_running_task=True) == "execution"
    assert determine_dialogue_state(_messages("질문 그만하고 계획 만들어줘")) == "planning"
    assert determine_dialogue_state(_three_yuki_turns("응")) == "draft_ready"
    assert determine_dialogue_state(_three_yuki_turns("다른 조건도 말할게")) == "draft_ready"
    assert determine_dialogue_state(
        _three_yuki_turns(f"{SUPPLEMENTAL_QUESTION_REQUEST_MARKER} 중요한 항목만 더 질문")
    ) == "supplemental"
    assert determine_dialogue_state(
        _three_yuki_turns("세부적으로 같이 설계해줘")
    ) == "supplemental"
    repeated_supplemental = _three_yuki_turns("중요한 항목만 더 질문")
    repeated_supplemental.extend(
        {"role": "user", "content": "보충 질문"} for _ in range(3)
    )
    assert determine_dialogue_state(repeated_supplemental) == "supplemental"
    assert determine_dialogue_state(
        _three_yuki_turns("왜 이 방식은 야외에서 오차가 생겨?")
    ) == "user_question"
    assert determine_dialogue_state(
        _three_yuki_turns("어떤 센서를 쓰는 게 좋아?")
    ) == "decision"
    assert determine_dialogue_state(_three_yuki_turns("가격을 찾아줘")) == "research"
    instruction = build_dialogue_state_instruction(_messages("응응"))
    assert "이전 대화 이어가기" in instruction
    draft_instruction = build_dialogue_state_instruction(_three_yuki_turns("좋아"))
    assert "자동으로 새 질문을 이어가지 않는다" in draft_instruction
    supplemental_instruction = build_dialogue_state_instruction(
        _three_yuki_turns("중요한 항목만 더 질문")
    )
    assert "왜 지금 필요한가" in supplemental_instruction
    assert "질문은 하나만" in supplemental_instruction
    user_question_instruction = build_dialogue_state_instruction(
        _three_yuki_turns("이 방식이 야외에서도 가능해?")
    )
    assert "먼저 직접 답한다" in user_question_instruction
    assert "핵심 질문에 대한 답으로 취급하지 않는다" in user_question_instruction


if __name__ == "__main__":
    run()
    print("dialogue state checks passed")
