"""프로젝트 대화의 현재 단계를 짧고 일관되게 판단합니다."""

from __future__ import annotations

from typing import Any


_SHORT_AGREEMENTS = (
    "응",
    "응응",
    "네",
    "넵",
    "좋아",
    "좋아요",
    "그래",
    "해줘",
    "진행해",
    "오케이",
)
_RESEARCH_WORDS = (
    "검색",
    "찾아",
    "가격",
    "구매",
    "디바이스마트",
    "비교",
    "자료",
)
_CHOICE_WORDS = (
    "뭘",
    "무엇",
    "어떤",
    "선택",
    "추천",
    "필요",
    "모르겠",
)


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content") or "").strip()
    return ""


def _is_short_agreement(text: str) -> bool:
    normalized = text.replace(" ", "").replace("!", "").replace("~", "")
    return normalized in _SHORT_AGREEMENTS or (
        len(normalized) <= 8
        and any(agreement in normalized for agreement in _SHORT_AGREEMENTS)
    )


def determine_dialogue_state(
    messages: list[dict[str, Any]],
    *,
    has_running_task: bool = False,
    plan_request_pending: bool = False,
) -> str:
    """메시지와 실행 상태를 바탕으로 현재 대화 단계를 반환합니다."""

    if has_running_task:
        return "execution"
    if plan_request_pending:
        return "planning"

    latest_user_text = _latest_user_text(messages).lower()
    if _is_short_agreement(latest_user_text):
        return "continue_previous"
    if any(word in latest_user_text for word in _RESEARCH_WORDS):
        return "research"
    if any(word in latest_user_text for word in _CHOICE_WORDS):
        return "decision"
    return "discovery"


def build_dialogue_state_instruction(
    messages: list[dict[str, Any]],
    *,
    has_running_task: bool = False,
    plan_request_pending: bool = False,
) -> str:
    """현재 단계에만 맞는 짧은 팀장 응답 지침을 만듭니다."""

    state = determine_dialogue_state(
        messages,
        has_running_task=has_running_task,
        plan_request_pending=plan_request_pending,
    )
    instructions = {
        "discovery": (
            "[대화 단계: 아이디어 찾기] 사용자가 말한 목표와 현재 막힌 이유를 쉬운 말로 다시 정리한다. "
            "그 선택이 프로젝트에 왜 중요한지 짧은 예시로 설명한 뒤, 다음에 정할 질문은 하나만 이어간다."
        ),
        "decision": (
            "[대화 단계: 선택 돕기] 답부터 추천하고, 필요한 선택지만 2개까지 보여 준다. "
            "각 선택지가 무엇이 다른지, 언제 고르면 좋은지, 초보자가 놓치기 쉬운 점을 쉬운 말로 설명한 뒤 하나를 고르게 돕는다."
        ),
        "research": (
            "[대화 단계: 정보 찾기] 지금 확인해야 할 조건과 그 이유를 먼저 짚고, "
            "실제 가격·재고·상품은 검색 도구에서 확인해야 한다고 분명히 말한다. 용어를 나열하지 말고 무엇을 검색해야 하는지 예시를 든다."
        ),
        "continue_previous": (
            "[대화 단계: 이전 대화 이어가기] 짧은 동의는 새 주제가 아니다. 직전의 질문·추천을 "
            "받아 왜 그다음 행동이 필요한지 한 번 연결해 설명하고, 처음 설명 전체를 그대로 반복하지 않는다."
        ),
        "planning": (
            "[대화 단계: 실행 계획] 사용자가 팀 작업을 요청했다. 확정·제안·미확인을 구분한 "
            "실행 계획을 작성한다."
        ),
        "execution": (
            "[대화 단계: 작업 진행] 이미 팀이 작업 중이다. 새 계획을 만들지 말고 진행 상태와 "
            "사용자가 지금 확인할 한 가지를 안내한다."
        ),
    }
    return "\n" + instructions[state] + "\n"
