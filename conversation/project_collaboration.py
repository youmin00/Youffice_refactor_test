"""유키의 프로젝트 공동 설계 대화와 팀 계획 전환 지침."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from conversation.response_formats import MANAGER_PLAN_MARKERS


def _project_name(project: dict[str, Any]) -> str:
    return str(project.get("name") or "새 프로젝트").strip()


def build_idea_conversation_start_prompt(project: dict[str, Any]) -> str:
    """프로젝트 목표를 바탕으로 자연스러운 첫 공동 설계 대화를 시작합니다."""

    return (
        f"'{_project_name(project)}' 프로젝트를 나와 함께 구체화해 줘. "
        "아직 부품이나 구현 방법을 잘 몰라도 시작할 수 있게, 현재 프로젝트 목표에서 "
        "가장 먼저 정해야 할 중요한 질문 하나를 쉬운 말로 물어봐 줘. "
        "내가 모른다고 하면 가능한 선택지와 차이를 알려주고 네 추천도 함께 말해 줘. "
        "지금은 직원 배정 계획을 만들지 말고 프로젝트 팀원처럼 대화를 이어가 줘."
    )


def build_next_idea_question_prompt() -> str:
    """앞선 대화를 이어 다음 설계 결정을 하나만 요청합니다."""

    return (
        "지금까지 대화에서 확정된 내용과 아직 정하지 않은 내용을 짧게 구분해 줘. "
        "그다음 프로젝트를 구체화하기 위해 지금 가장 중요한 질문 하나만 이어서 해 줘. "
        "내가 모를 수 있으니 선택지별 차이와 추천도 쉬운 말로 알려 줘."
    )


def build_team_plan_request_prompt(project: dict[str, Any]) -> str:
    """대화로 구체화한 내용을 승인 가능한 팀 계획으로 전환하도록 요청합니다."""

    return (
        f"지금까지 나눈 대화를 바탕으로 '{_project_name(project)}' 프로젝트의 "
        "승인용 팀 업무 계획을 만들어 줘. 확정된 내용, 제안, 미확인 사항을 구분하고 "
        "필요한 일을 작은 단계로 나눈 뒤 각 직원의 담당과 작업 순서를 정해 줘. "
        "계획을 읽고 승인하면 실제 팀 작업을 시작할 수 있는 형식으로 작성해 줘."
    )


def build_manager_collaboration_instruction() -> str:
    """팀 계획 전 단계에서 유키가 따를 자연 대화 규칙을 반환합니다."""

    markers = ", ".join(MANAGER_PLAN_MARKERS)
    return (
        "\n너는 사용자의 프로젝트 팀원 유키다. 먼저 사용자의 마지막 말에 직접 답하고, "
        "한 번에 하나의 작은 결정을 함께 정한다. 다만 그 결정을 이해하는 데 필요한 이유·차이·주의점은 생략하지 않는다. "
        "초보 학생도 알 수 있게 쉬운 문장과 일상 예시를 쓰며, 처음 나오는 전문 용어는 괄호로 뜻을 덧붙인다. "
        "답변은 '핵심 답변 → 왜 그런지 → 선택할 때 볼 점 → 다음에 정할 한 가지' 순서로 충분히 설명한다. "
        "두세 문장으로 성급하게 끝내거나 설명 없이 결론만 말하지 말고, 길어질 때는 소제목과 목록으로 읽기 쉽게 나눈다. "
        "사용자가 새 아이디어를 꺼냈다면 기존 내용을 회의록처럼 다시 쓰지 않는다. 현실적으로 다른 접근 2~3가지를 먼저 넓혀 보고, "
        "각 접근이 필요한 부품·구현 난이도·사용 경험에 어떤 차이를 만드는지 설명한다. "
        "모르는 사실·가격·호환성은 지어내지 말고 '아직 확인 필요'로 표시한다. "
        "필요한 경우에만 선택지 2개와 추천 이유·각 선택의 주의점을 제시하며, 같은 인사·설명·질문을 "
        "직전 답변과 반복하지 않는다. 실제 가격·재고·상품은 화면의 검색 도구로 확인하도록 안내한다. "
        "아이디어가 충분히 구체화되면 '팀 의견 받기' 또는 '지금 내용으로 팀에 맡기기'를 "
        "안내할 수 있다. "
        f"명시적인 계획 생성 단계가 아니므로 {markers} 표시는 사용하지 않는다. "
        "생각 과정을 노출하지 않는다. "
    )


def is_substantially_repeated_reply(
    candidate: object,
    previous: object,
) -> bool:
    """직전 답변을 거의 그대로 다시 보냈는지 확인합니다."""

    def normalize(value: object) -> str:
        return re.sub(r"[\W_]+", "", str(value or "").lower())

    candidate_text = normalize(candidate)
    previous_text = normalize(previous)
    if candidate_text == previous_text and len(candidate_text) >= 12:
        return True
    if min(len(candidate_text), len(previous_text)) < 30:
        return False
    return SequenceMatcher(None, candidate_text, previous_text).ratio() >= 0.9


def is_manager_plan_content(content: object) -> bool:
    """유키 답변이 승인 가능한 팀 계획의 필수 구역을 모두 갖췄는지 확인합니다."""

    text = str(content or "")
    return all(marker in text for marker in MANAGER_PLAN_MARKERS)
