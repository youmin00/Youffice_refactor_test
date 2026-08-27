"""대화 단계 판별의 대표 흐름을 빠르게 확인합니다."""

from conversation.dialogue_state import (
    build_dialogue_state_instruction,
    determine_dialogue_state,
)


def _messages(user_text: str) -> list[dict]:
    return [
        {"role": "assistant", "content": "이동 방식을 골라볼까요?"},
        {"role": "user", "content": user_text},
    ]


def run() -> None:
    assert determine_dialogue_state(_messages("좋아")) == "continue_previous"
    assert determine_dialogue_state(_messages("모터는 어떤 걸 골라야 해?")) == "decision"
    assert determine_dialogue_state(_messages("디바이스마트에서 가격을 찾아줘")) == "research"
    assert determine_dialogue_state(_messages("학교 안전 도우미를 만들고 싶어")) == "discovery"
    assert determine_dialogue_state(_messages("응"), plan_request_pending=True) == "planning"
    assert determine_dialogue_state(_messages("응"), has_running_task=True) == "execution"
    instruction = build_dialogue_state_instruction(_messages("응응"))
    assert "이전 대화 이어가기" in instruction


if __name__ == "__main__":
    run()
    print("dialogue state checks passed")
