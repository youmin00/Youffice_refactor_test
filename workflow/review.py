"""YOUFFICE 업무 결과의 검수 규칙을 제공합니다."""

import re

from database import get_task_control


def review_verdict(review_text: str) -> str:
    """검수 답변을 통과 또는 재작업 판정으로 변환합니다."""

    explicit_result = re.search(
        r"검수\s*결과\s*[:：]\s*(통과|재작업)",
        review_text,
        flags=re.IGNORECASE,
    )
    if explicit_result:
        return "passed" if explicit_result.group(1) == "통과" else "rework_requested"
    # 형식을 지키지 않은 검수는 임의로 통과시키지 않습니다.
    return "rework_requested"


def has_explicit_review_verdict(review_text: str) -> bool:
    """검수 답변 첫 부분에 명시적인 한국어 판정이 있는지 확인합니다."""

    return bool(
        re.search(
            r"^\s*검수\s*결과\s*[:：]\s*(통과|재작업)\b",
            review_text,
            flags=re.IGNORECASE,
        )
    )


def has_explicit_review_targets(review_text: str) -> bool:
    """검수 답변에 재작업 대상 ID 줄이 있는지 확인합니다."""

    return bool(
        re.search(
            r"^\s*재작업\s*대상\s*ID\s*[:：]\s*.+$",
            review_text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    )


def review_target_employee_ids(
    review_text: str,
    employee_results: list[tuple[dict, str, int]],
) -> set[str]:
    """검수 답변의 대상 줄에서 실제 실행 직원 ID를 안전하게 추출합니다."""

    target_match = re.search(
        r"^\s*재작업\s*대상\s*ID\s*[:：]\s*(.+?)\s*$",
        review_text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if target_match is None:
        return set()

    target_text = target_match.group(1).strip()
    available_employees = {
        employee["id"]: employee
        for employee, _, _ in employee_results
    }
    if any(word in target_text for word in ("전체", "전원", "모든 직원")):
        return set(available_employees)
    if "없음" in target_text:
        return set()

    normalized_target = target_text.casefold()
    return {
        employee_id
        for employee_id, employee in available_employees.items()
        if employee_id.casefold() in normalized_target
        or str(employee["name"]).casefold() in normalized_target
    }


def has_valid_review_contract(
    review_text: str,
    employee_results: list[tuple[dict, str, int]],
) -> bool:
    """판정과 재작업 대상이 서로 모순되지 않는 검수 응답인지 확인합니다."""

    if not has_explicit_review_verdict(review_text):
        return False
    if not has_explicit_review_targets(review_text):
        return False
    targets = review_target_employee_ids(review_text, employee_results)
    if review_verdict(review_text) == "passed":
        return not targets
    return bool(targets)



def normalize_review_for_user_policy(
    review_text: str,
    user_request: str,
) -> str:
    """Normalize a review when the user explicitly allows unknown items."""

    if not user_allows_unverified_progress(user_request):
        return review_text

    if review_verdict(review_text) != "rework_requested":
        return review_text

    normalized = review_text or ""

    hard_failure_signals = (
        "\uadfc\uac70 \uc5c6\ub294 \uc218\uce58",
        "\uc784\uc758\ub85c \uac00\uc815",
        "\uc0ac\uc6a9\uc790 \uc81c\uacf5 \uc815\ubcf4\uc640 \ubd88\uc77c\uce58",
        "\uc608\uc0b0 \ubaa8\uc21c",
        "\ub17c\ub9ac\uc801 \ubaa8\uc21c",
        "\uc694\uccad \ubc94\uc704 \uc704\ubc18",
        "\ucf54\ub4dc \uc624\ub958",
        "\uc2e4\ud589 \uc624\ub958",
        "\uc548\uc804 \uc704\ud5d8",
        "\ud5c8\uc704",
        "\uc0ac\uc2e4\uacfc \ub2e4\ub984",
    )

    if any(signal in normalized for signal in hard_failure_signals):
        return review_text

    unverified_signals = (
        "\ubbf8\ud655\uc778",
        "\uc0ac\uc6a9\uc790 \ud655\uc778",
        "\uc815\ubcf4\uac00 \ubd80\uc871",
        "\uc815\ubcf4 \ubd80\uc871",
        "\uad6c\uccb4\uc801\uc778 \uc815\ubcf4",
        "\uad6c\uccb4\uc801\uc778 \uc815\uc758",
        "\ud15c\ud50c\ub9bf",
        "\ubcf4\uace0\uc11c \ud615\uc2dd",
        "\uacc4\ud68d\uc11c \ud615\uc2dd",
        "\uac80\uc218 \uae30\uc900",
        "\uc5ed\ud560 \ubd84\ub2f4 \ubc29\uc2dd",
        "\uc790\ub3d9\ud654 \ub3c4\uad6c",
        "\uc678\ubd80 API",
        "\uc131\ub2a5 \uc218\uce58",
        "\uc2dc\uc2a4\ud15c \uad6c\uc870",
        "\uc5f0\ub3d9 \ubc29\uc2dd",
    )

    if not any(signal in normalized for signal in unverified_signals):
        return review_text

    lines = normalized.splitlines()

    verdict_prefix = "\uac80\uc218 \uacb0\uacfc"
    target_prefix = "\uc7ac\uc791\uc5c5 \ub300\uc0c1 ID"
    user_check_prefix = "\uc0ac\uc6a9\uc790 \ud655\uc778 \ud544\uc694"

    for index, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith(verdict_prefix):
            lines[index] = "\uac80\uc218 \uacb0\uacfc: \ud1b5\uacfc"

        elif stripped.startswith(target_prefix):
            lines[index] = "\uc7ac\uc791\uc5c5 \ub300\uc0c1 ID: \uc5c6\uc74c"

        elif stripped.startswith(user_check_prefix):
            lines[index] = "\uc0ac\uc6a9\uc790 \ud655\uc778 \ud544\uc694: \uc5c6\uc74c"

    normalized = "\n".join(lines)

    normalized += (
        "\n\n[\uc815\ucc45 \uc801\uc6a9] "
        "\uc0ac\uc6a9\uc790\uac00 \ubbf8\uc81c\uacf5 \uc815\ubcf4\ub97c "
        "\ubbf8\ud655\uc778\uc73c\ub85c \ud45c\uc2dc\ud558\uace0 "
        "\uc9c4\ud589\ud558\ub3c4\ub85d \uc694\uccad\ud588\uc73c\ubbc0\ub85c, "
        "\ubbf8\ud655\uc778 \uc0c1\ud0dc \uc790\uccb4\ub294 "
        "\uc7ac\uc791\uc5c5 \uc0ac\uc720\ub85c \uc0ac\uc6a9\ud558\uc9c0 "
        "\uc54a\uc2b5\ub2c8\ub2e4."
    )

    return normalized


class WorkflowCancelled(RuntimeError):
    """사용자가 실행 중인 팀 업무의 안전 중단을 요청했습니다."""


def ensure_workflow_not_cancelled(task_id: int) -> None:
    """DB의 중단 신호를 확인하고 다음 협업 단계 진입을 막습니다."""

    control = get_task_control(task_id)
    if control is not None and control["state"] in {"cancel_requested", "cancelled"}:
        raise WorkflowCancelled("사용자가 작업 중단을 요청했습니다.")



def user_allows_unverified_progress(user_request: str) -> bool:
    """Detect whether the user wants unknowns preserved without blocking progress."""

    normalized = "".join((user_request or "").split()).lower()

    unverified_policy_signals = (
        "\ubbf8\ud655\uc778\uc73c\ub85c\ud45c\uc2dc",
        "\ubbf8\ud655\uc778\ud56d\ubaa9\uc73c\ub85c",
        "\ubbf8\ud655\uc778\uc73c\ub85c\uad6c\ubd84",
        "\ubbf8\ud655\uc778\uc0c1\ud0dc\ub85c\uc720\uc9c0",
        "\ubbf8\ud655\uc778\uc73c\ub85c\uc720\uc9c0",
        "\ubbf8\ud655\uc778\uc0c1\ud0dc\ub97c\uc720\uc9c0",
        "\ubbf8\ud655\uc778\uc73c\ub85c\ub0a8\uaca8",
        "\ubbf8\ud655\uc778\ucc44\ub85c",
    )

    no_guess_signals = (
        "\uc784\uc758\ub85c\uac00\uc815\ud558\uc9c0",
        "\ucd94\uce21\ud558\uc9c0",
        "\uc81c\uacf5\ud558\uc9c0\uc54a\uc740",
        "\uc0c8\ub85c\uc6b4\uc0ac\uc2e4\uc744\ucd94\uac00\ud558\uc9c0",
    )

    continue_without_clarification_signals = (
        "\ucd94\uac00\ud655\uc778\uc744\uc694\uccad\ud558\uc9c0",
        "\ucd94\uac00\ud655\uc778\uc694\uccad\ud558\uc9c0",
        "\ucd94\uac00\ud655\uc778\uc5c6\uc774",
        "\ud655\uc778\uc694\uccad\ud558\uc9c0",
        "\uc0ac\uc6a9\uc790\ud655\uc778\uc5c6\uc774",
        "\ud604\uc7ac\ud655\uc778\ub41c\uc815\ubcf4\ubc94\uc704",
        "\ud655\uc778\ub41c\uc815\ubcf4\ubc94\uc704\uc5d0\uc11c",
        "\ubbf8\ud655\uc778\uc0c1\ud0dc\ub85c\uc720\uc9c0\ud55c\ucc44",
    )

    keeps_unknowns = any(
        signal in normalized
        for signal in unverified_policy_signals
    )

    avoids_guessing = any(
        signal in normalized
        for signal in no_guess_signals
    )

    allows_progress = any(
        signal in normalized
        for signal in continue_without_clarification_signals
    )

    return keeps_unknowns and (
        avoids_guessing
        or allows_progress
    )


def review_clarification_questions(review_text: str, user_request: str = "") -> str:
    """검수 결과에서 사용자가 제공해야 하는 정보나 선택 사항을 추출합니다."""

    if user_allows_unverified_progress(user_request):
        return ""

    marker = re.search(
        r"사용자\s*확인\s*필요\s*[:：]\s*(.+?)(?=\n\s*(?:\*\*)?"
        r"(?:해결된\s*항목|남은\s*항목|추가\s*검수\s*요구|검수\s*근거)"
        r"(?:\*\*)?\s*[:：]|\Z)",
        review_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if marker is not None:
        questions = marker.group(1).strip()
        if questions and not questions.startswith("없음"):
            return questions

    remaining = re.search(
        r"(?:\*\*)?남은\s*항목(?:\*\*)?\s*[:：]\s*(.+?)(?=\n\s*(?:\*\*)?(?:추가\s*)?검수\s*요구|\Z)",
        review_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if remaining is None:
        return ""
    remaining_text = remaining.group(1).strip()
    remaining_text = re.sub(
        r"^\s*\*{2,}\s*$",
        "",
        remaining_text,
        flags=re.MULTILINE,
    ).strip()
    if not remaining_text:
        return ""
    return (
        "다음 미확인 정보가 필요합니다. 알고 있는 내용을 입력하고, 모르는 항목은 "
        "'기본 가정으로 계획 진행'이라고 적어주세요.\n\n"
        f"{remaining_text}"
    )
