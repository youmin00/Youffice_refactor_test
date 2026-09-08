"""유키의 프로젝트 공동 설계 대화와 팀 계획 전환 지침."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from conversation.response_formats import MANAGER_PLAN_MARKERS


MANAGER_EMPLOYEE_ID = "project_manager"
MAX_GUIDED_QUESTIONS = 3
SUPPLEMENTAL_QUESTION_REQUEST_MARKER = "[선택형 보충 질문 요청]"


def _project_name(project: dict[str, Any]) -> str:
    return str(project.get("name") or "새 프로젝트").strip()


def build_idea_conversation_start_prompt(project: dict[str, Any]) -> str:
    """프로젝트 목표를 바탕으로 자연스러운 첫 공동 설계 대화를 시작합니다."""

    return (
        f"'{_project_name(project)}' 프로젝트를 나와 함께 구체화해 줘. "
        "아직 부품이나 구현 방법을 잘 몰라도 시작할 수 있게, 현재 프로젝트 목표에서 "
        "가장 먼저 정해야 할 중요한 질문 하나를 쉬운 말로 물어봐 줘. "
        "내가 모른다고 하면 가능한 선택지와 차이를 알려주고 네 추천도 함께 말해 줘. "
        "핵심 질문은 전체 대화에서 최대 3개까지만 하고, 그 전에 충분한 정보가 모이면 "
        "질문을 멈추고 현재 정보·기본 가정·미확인 사항을 정리해 줘. "
        "지금은 직원 배정 계획을 만들지 말고 제작 준비를 돕는 프로젝트 코치처럼 대화해 줘."
    )


def build_next_idea_question_prompt() -> str:
    """앞선 대화를 이어 다음 설계 결정을 하나만 요청합니다."""

    return (
        "지금까지 대화에서 확정된 내용과 아직 정하지 않은 내용을 짧게 구분해 줘. "
        "그다음 프로젝트를 구체화하기 위해 지금 가장 중요한 질문 하나만 이어서 해 줘. "
        "내가 모를 수 있으니 선택지별 차이와 추천도 쉬운 말로 알려 줘. "
        "이미 핵심 질문을 3개 했다면 새 질문을 하지 말고 현재 내용으로 제작 준비 초안을 제시해 줘."
    )


def build_supplemental_question_prompt(project: dict[str, Any]) -> str:
    """초안 뒤 사용자가 선택한 경우에만 중요한 보충 질문 하나를 요청합니다."""

    return (
        f"{SUPPLEMENTAL_QUESTION_REQUEST_MARKER} '{_project_name(project)}' 프로젝트의 지금까지 대화를 바탕으로 "
        "먼저 제작 준비 초안을 확정된 내용·기본 가정·미확인 항목으로 짧게 보여 줘. "
        "그다음 결과물의 방향, 안전, 비용 또는 구현 가능성을 실제로 바꿀 미확인 항목이 있을 때만 "
        "가장 중요한 보충 질문 하나를 해 줘. 질문 전에 왜 지금 필요한지와 답에 따라 무엇이 달라지는지 설명해 줘. "
        "선택지는 이해하기 쉬운 2~3개로 제한하고 추천 항목을 표시해 줘. "
        "'모르겠음·기본 가정 사용'도 가능한 답으로 안내하고, 중요 미확인 항목이 없다면 새 질문을 만들지 말고 "
        "현재 내용으로 제작 준비 계획을 만들 수 있다고 말해 줘. 사용자가 원하면 이 과정을 필요한 만큼 반복할 수 있게 안내해 줘."
    )


def build_team_plan_request_prompt(
    project: dict[str, Any],
    *,
    use_default_assumptions: bool = False,
) -> str:
    """대화 내용을 승인 가능한 제작 준비 계획으로 전환하도록 요청합니다."""

    assumption_instruction = (
        "정하지 않은 비핵심 항목은 합리적인 기본 가정으로 표시해 진행하고, 안전·비용·필수 요구처럼 "
        "임의로 정하면 위험한 항목만 사용자 확인 필요로 남겨 줘. "
        if use_default_assumptions
        else "정하지 않은 항목은 계획을 막는 질문으로 되돌리지 말고 기본 가정 또는 사용자 확인 필요로 구분해 줘. "
    )
    return (
        f"지금까지 나눈 대화를 바탕으로 '{_project_name(project)}' 프로젝트의 "
        "승인용 제작 준비 계획을 만들어 줘. 확정된 내용, 제안, 미확인 사항을 구분하고 "
        + assumption_instruction
        + "요구사항 정리, 근거 조사, 선택지 비교, 기술 검토, 위험 점검, 테스트 계획과 외부 도구로 넘길 일을 "
        "작은 단계로 나눈 뒤 각 직원의 담당과 순서를 정해 줘. "
        "AI가 실제 구매·CAD 도면 작성·조립·코드 실행·성능 시험을 완료한다고 표현하지 마. "
        "계획을 승인하면 직원들이 제작 준비 자료를 작성하고 검토할 수 있는 형식으로 작성해 줘."
    )


def build_manager_collaboration_instruction() -> str:
    """팀 계획 전 단계에서 유키가 따를 자연 대화 규칙을 반환합니다."""

    markers = ", ".join(MANAGER_PLAN_MARKERS)
    return (
        "\n너는 사용자의 프로젝트 코치이자 팀장 유키다. 먼저 사용자의 마지막 말에 직접 답하고, "
        "한 답변에서 질문은 최대 1개, 첫 아이디어 구체화 과정의 핵심 질문은 최대 3개까지만 한다. "
        "정보가 완벽해질 때까지 묻지 말고, 충분한 정보가 모이거나 사용자가 모르겠다고 하면 질문을 멈춘다. "
        "그때는 확정된 내용·기본 가정·미확인 사항·다음 행동을 담은 초안을 먼저 보여 주고 제작 준비 계획으로 넘어갈 수 있게 안내한다. "
        "초안 뒤에는 자동으로 질문을 이어가지 않는다. 사용자가 '중요한 항목만 더 질문'을 선택한 경우에만 "
        "결과에 실제 영향을 주는 보충 질문을 횟수 제한 없이 한 번에 하나씩 한다. 각 보충 질문에는 필요한 이유와 "
        "답에 따라 달라지는 점을 먼저 밝히고, 2~3개 선택지·추천·'모르겠음 또는 기본 가정' 선택을 함께 제시한다. "
        "사용자가 질문·비교·설명을 요청하면 그 질문에 먼저 직접 답한다. 사용자 질문을 유키가 주도하는 핵심 질문으로 세지 않고, "
        "답변만으로 충분하면 되묻지 않는다. 결정에 꼭 필요한 정보가 없을 때만 이유를 밝힌 후속 질문 하나를 할 수 있다. "
        "질문이 필요할 때는 하나의 작은 결정을 함께 정하되 그 이유·차이·주의점은 생략하지 않는다. "
        "초보 학생도 알 수 있게 쉬운 문장과 일상 예시를 쓰며, 처음 나오는 전문 용어는 괄호로 뜻을 덧붙인다. "
        "답변은 '핵심 답변 → 왜 그런지 → 선택할 때 볼 점 → 다음에 정할 한 가지' 순서로 충분히 설명한다. "
        "두세 문장으로 성급하게 끝내거나 설명 없이 결론만 말하지 말고, 길어질 때는 소제목과 목록으로 읽기 쉽게 나눈다. "
        "사용자가 새 아이디어를 꺼냈다면 기존 내용을 회의록처럼 다시 쓰지 않는다. 현실적으로 다른 접근 2~3가지를 먼저 넓혀 보고, "
        "각 접근이 필요한 부품·구현 난이도·사용 경험에 어떤 차이를 만드는지 설명한다. "
        "모르는 사실·가격·호환성은 지어내지 말고 '아직 확인 필요'로 표시한다. "
        "필요한 경우에만 선택지 2개와 추천 이유·각 선택의 주의점을 제시하며, 같은 인사·설명·질문을 "
        "직전 답변과 반복하지 않는다. 실제 가격·재고·상품은 화면의 검색 도구로 확인하도록 안내한다. "
        "AI가 실제 구매·CAD 도면 작성·조립·코드 실행·성능 시험을 했다고 주장하지 않는다. "
        "대신 요구사항, 선택 근거, 제작 전 체크리스트, 테스트 계획과 외부 도구로 넘길 작업을 만든다. "
        "아이디어가 충분히 구체화되거나 핵심 질문 3개를 마치면 '중요한 항목만 더 질문', '팀 의견 받기', "
        "'현재 내용으로 제작 준비 계획 만들기', '기본 가정으로 진행'을 안내한다. "
        f"명시적인 계획 생성 단계가 아니므로 {markers} 표시는 사용하지 않는다. "
        "생각 과정을 노출하지 않는다. "
    )


def manager_guided_turn_count(messages: list[dict[str, Any]]) -> int:
    """사용자 질문 답변을 제외하고 유키가 주도한 초기 설계 대화만 셉니다."""

    count = 0
    latest_user_text = ""
    for message in messages:
        if message.get("role") == "user":
            latest_user_text = str(message.get("content") or "")
            continue
        if (
            message.get("role") != "assistant"
            or message.get("employee_id") != MANAGER_EMPLOYEE_ID
        ):
            continue
        if is_manager_plan_content(message.get("content")):
            count = 0
            latest_user_text = ""
            continue
        if (
            is_explicit_supplemental_question_request(latest_user_text)
            or is_user_information_request(latest_user_text)
        ):
            continue
        count += 1
    return count


def supplemental_question_count(messages: list[dict[str, Any]]) -> int:
    """마지막 팀 계획 뒤 사용자가 요청한 선택형 보충 질문 수를 셉니다."""

    count = 0
    for message in reversed(messages):
        if (
            message.get("role") == "assistant"
            and message.get("employee_id") == MANAGER_EMPLOYEE_ID
            and is_manager_plan_content(message.get("content"))
        ):
            break
        if message.get("role") != "user":
            continue
        content = str(message.get("content") or "")
        if (
            SUPPLEMENTAL_QUESTION_REQUEST_MARKER in content
            or is_explicit_supplemental_question_request(content)
        ):
            count += 1
    return count


def is_explicit_supplemental_question_request(text: object) -> bool:
    """사용자가 초안 뒤 중요한 보충 질문을 명시적으로 원하는지 판별합니다."""

    normalized = re.sub(r"[\s.,!?~·]+", "", str(text or "").lower())
    return any(
        phrase in normalized
        for phrase in (
            "중요한항목만더질문",
            "중요한것만더물어",
            "보충질문",
            "필요한질문만더",
            "세부적으로같이설계",
        )
    )


def is_user_information_request(text: object) -> bool:
    """사용자가 유키에게 답·설명·비교를 요구하는 메시지인지 판별합니다."""

    raw_text = str(text or "").strip().lower()
    if not raw_text:
        return False
    if (
        SUPPLEMENTAL_QUESTION_REQUEST_MARKER in raw_text
        or "프로젝트를 나와 함께 구체화해 줘" in raw_text
        or "지금까지 대화에서 확정된 내용" in raw_text
        or is_explicit_plan_request(raw_text)
    ):
        return False

    normalized = re.sub(r"[\s.,!?~·]+", "", raw_text)
    if "?" in raw_text:
        return True
    if normalized.startswith(("왜", "어떻게", "뭐", "무엇", "어떤", "얼마")):
        return True
    return normalized.endswith(
        (
            "알려줘",
            "설명해줘",
            "비교해줘",
            "찾아줘",
            "추천해줘",
            "괜찮아",
            "가능해",
            "될까",
            "되나",
        )
    )


def is_explicit_plan_request(text: object) -> bool:
    """사용자가 질문을 멈추고 준비 계획을 원한다는 표현을 판별합니다."""

    normalized = re.sub(r"[\s.,!?~]+", "", str(text or "").lower())
    return any(
        phrase in normalized
        for phrase in (
            "팀계획만들",
            "준비계획만들",
            "제작준비계획",
            "현재내용으로초안",
            "기본가정으로진행",
            "질문그만",
            "팀에맡기",
        )
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
