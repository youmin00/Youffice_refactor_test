"""프로젝트 대화의 현재 단계를 짧고 일관되게 판단합니다."""

from __future__ import annotations

from typing import Any

from conversation.project_collaboration import (
    MAX_GUIDED_QUESTIONS,
    is_explicit_plan_request,
    is_explicit_supplemental_question_request,
    is_user_information_request,
    manager_guided_turn_count,
)


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
    if is_explicit_plan_request(latest_user_text):
        return "planning"
    guided_turns = manager_guided_turn_count(messages)
    if (
        guided_turns >= MAX_GUIDED_QUESTIONS
        and is_explicit_supplemental_question_request(latest_user_text)
    ):
        return "supplemental"
    if any(word in latest_user_text for word in _RESEARCH_WORDS):
        return "research"
    if any(word in latest_user_text for word in _CHOICE_WORDS):
        return "decision"
    if is_user_information_request(latest_user_text):
        return "user_question"
    if _is_short_agreement(latest_user_text):
        if guided_turns >= MAX_GUIDED_QUESTIONS:
            return "draft_ready"
        return "continue_previous"
    if guided_turns >= MAX_GUIDED_QUESTIONS:
        return "draft_ready"
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
            "그 선택이 프로젝트에 왜 중요한지 짧은 예시로 설명한 뒤, 아직 꼭 필요한 경우에만 질문 하나를 이어간다. "
            "선택 가능한 기본값이 있으면 질문 대신 추천과 가정을 제시한다."
        ),
        "decision": (
            "[대화 단계: 사용자 질문에 답하며 선택 돕기] 사용자가 물은 내용에 먼저 답하고 추천한다. 필요한 선택지만 2개까지 보여 준다. "
            "각 선택지가 무엇이 다른지, 언제 고르면 좋은지, 초보자가 놓치기 쉬운 점을 쉬운 말로 설명한다. "
            "답변만으로 충분하면 되묻지 않고, 결정에 꼭 필요한 정보가 없을 때만 그 이유를 밝힌 질문 하나를 한다."
        ),
        "research": (
            "[대화 단계: 사용자 조사 질문에 답하기] 사용자가 요청한 정보에 먼저 답하고, 지금 확인해야 할 조건과 그 이유를 짚는다. "
            "실제 가격·재고·상품은 검색 도구에서 확인해야 한다고 분명히 말한다. 용어를 나열하지 말고 무엇을 검색해야 하는지 예시를 든다. "
            "답변 뒤 새로운 질문을 자동으로 이어가지 말고 원래 구체화 흐름이나 제작 준비 계획으로 돌아갈 선택지를 제시한다."
        ),
        "user_question": (
            "[대화 단계: 사용자 질문 우선 답변] 사용자가 유키에게 물은 내용에 먼저 직접 답한다. 이 메시지를 유키의 핵심 질문에 대한 답으로 취급하지 않는다. "
            "쉬운 설명과 필요한 근거를 제공하고, 답변만으로 충분하면 질문을 덧붙이지 않는다. "
            "정확한 답이나 중요한 결정에 꼭 필요한 정보가 없을 때만 왜 필요한지 설명한 뒤 후속 질문 하나를 한다. "
            "마지막에는 원래 주제로 돌아가거나 이 항목을 더 구체화하거나 현재 내용으로 계획을 만들 수 있다고 짧게 안내한다."
        ),
        "continue_previous": (
            "[대화 단계: 이전 대화 이어가기] 짧은 동의는 새 주제가 아니다. 직전의 질문·추천을 "
            "수락한 것으로 처리해 다음 결과를 제시한다. 처음 설명이나 같은 질문을 반복하지 않는다."
        ),
        "draft_ready": (
            "[대화 단계: 제작 준비 초안] 자동으로 새 질문을 이어가지 않는다. 지금까지 확정된 내용, 합리적인 기본 가정, "
            "아직 확인할 항목과 사용자가 바로 할 다음 행동을 짧게 정리해 초안을 먼저 보여 준다. 실제 제작을 완료했다고 말하지 말고, "
            "현재 내용으로 제작 준비 계획을 만들거나, 사용자가 원할 때만 중요한 항목을 더 확인할 수 있다고 안내한다."
        ),
        "supplemental": (
            "[대화 단계: 선택형 보충 질문] 먼저 현재 제작 준비 초안을 확정된 내용·기본 가정·미확인 항목으로 짧게 보여 준다. "
            "그 뒤 방향·안전·비용·구현 가능성을 실제로 바꿀 미확인 항목 하나만 고른다. "
            "'왜 지금 필요한가'와 '답에 따라 무엇이 달라지는가'를 설명하고, 쉬운 선택지 2~3개와 추천을 제시한 뒤 질문은 하나만 한다. "
            "사용자가 모르면 기본 가정을 쓸 수 있다고 안내한다. 중요한 미확인 항목이 없다면 억지로 질문하지 말고 준비 계획으로 넘어가도록 한다. "
            "사용자가 원하면 다른 항목도 같은 방식으로 계속 구체화할 수 있다고 안내한다."
        ),
        "planning": (
            "[대화 단계: 제작 준비 계획] 사용자가 질문을 멈추고 계획 작성을 요청했다. 추가 질문 없이 "
            "확정·기본 가정·미확인을 구분한 제작 준비 계획을 작성한다."
        ),
        "execution": (
            "[대화 단계: 준비 작업 진행] 이미 팀이 조사·설계 검토 자료를 작성 중이다. 새 계획을 만들지 말고 진행 상태와 "
            "사용자가 지금 확인할 한 가지를 안내한다."
        ),
    }
    return "\n" + instructions[state] + "\n"
