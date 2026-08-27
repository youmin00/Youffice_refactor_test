"""Deterministic structured final report support for YOUFFICE."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


STRUCTURED_REPORT_JSON_INSTRUCTION = (
    "\ub108\ub294 \ucd5c\uc885 \ubcf4\uace0\uc11c\ub97c \uc791\uc131\ud558\ub294 \uc5ed\ud560\uc774 \uc544\ub2c8\ub77c "
    "\uc9c1\uc6d0 \ubcf4\uace0\uc640 \uac80\uc218 \uae30\ub85d\uc744 \ubd84\ub958\ud558\ub294 \uc5ed\ud560\uc774\ub2e4.\n"
    "\ubc18\ub4dc\uc2dc JSON \uac1d\uccb4 \ud558\ub098\ub9cc \ucd9c\ub825\ud55c\ub2e4. "
    "\ub9c8\ud06c\ub2e4\uc6b4, \ucf54\ub4dc \ud39c\uc2a4, \uc124\uba85 \ubb38\uc7a5\uc740 \ucd9c\ub825\ud558\uc9c0 \uc54a\ub294\ub2e4.\n"
    "\ud5c8\uc6a9\ub41c \ud544\ub4dc\ub294 proposals, unverified, limitations \uc138 \uac1c\ubfd0\uc774\ub2e4.\n"
    "\uac01 \ud544\ub4dc\uc758 \uac12\uc740 \ubb38\uc790\uc5f4 \ubc30\uc5f4\uc774\ub2e4.\n"
    "confirmed_facts, project_name, budget, skills \ub4f1 \ud655\uc815 \uc0ac\uc2e4 \ud544\ub4dc\ub294 "
    "\uc808\ub300 \uc0dd\uc131\ud558\uc9c0 \uc54a\ub294\ub2e4. \ud655\uc815 \uc0ac\uc2e4\uc740 \ud504\ub85c\uadf8\ub7a8\uc774 \uc9c1\uc811 \ucd94\uac00\ud55c\ub2e4.\n"
    "\uc0ac\uc6a9\uc790\uac00 \uc81c\uacf5\ud558\uc9c0 \uc54a\uc740 API, \uc2dc\uc2a4\ud15c \uad6c\uc870, "
    "\uc544\ud0a4\ud14d\ucc98, \uc81c\uc5b4 \ud750\ub984, \uc131\ub2a5 \uc218\uce58, \uad6c\ud604 \uc644\ub8cc \uc5ec\ubd80\ub294 "
    "\ud655\uc815 \uc0ac\uc2e4\ub85c \ubd84\ub958\ud558\uc9c0 \uc54a\ub294\ub2e4.\n"
    "\uc9c1\uc6d0\uc774 \uc81c\uc548\ud55c \uacc4\ud68d\uc774\ub098 \uae30\uc220\uc801 \uc544\uc774\ub514\uc5b4\ub294 proposals\uc5d0 \ub123\ub294\ub2e4.\n"
    "\ud655\uc778\ud560 \uadfc\uac70\uac00 \uc5c6\ub294 \ud56d\ubaa9\uc740 unverified\uc5d0 \ub123\ub294\ub2e4.\n"
    "\ubb38\uc11c \uac80\ud1a0\uc758 \ud55c\uacc4\ub294 limitations\uc5d0 \ub123\ub294\ub2e4.\n"
    "\ub2e4\uc74c \ud589\ub3d9\uc740 AI\uac00 \uc791\uc131\ud558\uc9c0 \uc54a\uc73c\uba70 \ud504\ub85c\uadf8\ub7a8\uc774 \uc9c1\uc811 \uacb0\uc815\ud55c\ub2e4."
)


@dataclass(frozen=True)
class StructuredReportAIData:
    proposals: tuple[str, ...] = ()
    unverified: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


def _clean_item(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _normalize_key(value: str) -> str:
    return "".join(_clean_item(value).lower().split())


def _sanitize_items(
    values: Any,
    *,
    max_items: int = 12,
) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()

    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not isinstance(value, str):
            continue

        cleaned = _clean_item(value)

        if not cleaned:
            continue

        if len(cleaned) > 500:
            cleaned = cleaned[:500].rstrip()

        key = _normalize_key(cleaned)

        if not key or key in seen:
            continue

        seen.add(key)
        result.append(cleaned)

        if len(result) >= max_items:
            break

    return tuple(result)


def parse_structured_report_json(
    raw_text: str | None,
) -> StructuredReportAIData:
    """Parse only the AI-controlled non-fact report fields."""

    text = (raw_text or "").strip()

    if not text:
        raise ValueError("EMPTY_STRUCTURED_REPORT")

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("STRUCTURED_REPORT_JSON_NOT_FOUND")

    payload = json.loads(text[start:end + 1])

    if not isinstance(payload, dict):
        raise ValueError("STRUCTURED_REPORT_JSON_NOT_OBJECT")

    proposals = _sanitize_items(
        payload.get("proposals"),
    )
    unverified = _sanitize_items(
        payload.get("unverified"),
    )
    limitations = _sanitize_items(
        payload.get("limitations"),
    )
    # When an exact item appears in both categories,
    # unverified wins over proposal.
    unknown_keys = {
        _normalize_key(item)
        for item in unverified
    }

    proposals = tuple(
        item
        for item in proposals
        if _normalize_key(item) not in unknown_keys
    )

    return StructuredReportAIData(
        proposals=proposals,
        unverified=unverified,
        limitations=limitations,
    )


def _project_value(
    project: dict,
    key: str,
    fallback: str,
) -> str:
    value = project.get(key)

    if value is None:
        return fallback

    cleaned = str(value).strip()
    return cleaned or fallback


def confirmed_project_fact_lines(
    project: dict,
) -> tuple[str, ...]:
    """Return facts controlled only by the project database."""

    start_date = _project_value(
        project,
        "start_date",
        "\uc785\ub825\ub418\uc9c0 \uc54a\uc74c",
    )
    target_date = _project_value(
        project,
        "target_date",
        "\uc785\ub825\ub418\uc9c0 \uc54a\uc74c",
    )

    return (
        f"- \ud504\ub85c\uc81d\ud2b8\uba85: "
        f"{_project_value(project, 'name', '\uc785\ub825\ub418\uc9c0 \uc54a\uc74c')}",
        f"- \ubd84\uc57c: "
        f"{_project_value(project, 'field', '\uc785\ub825\ub418\uc9c0 \uc54a\uc74c')}",
        f"- \ubaa9\ud45c: "
        f"{_project_value(project, 'goal', '\uc785\ub825\ub418\uc9c0 \uc54a\uc74c')}",
        f"- \uae30\uac04: {start_date} ~ {target_date}",
        f"- \uc608\uc0b0: "
        f"{_project_value(project, 'budget', '\ubbf8\uc815')}",
        f"- \ubcf4\uc720 \uae30\uc220 \ubc0f \ub3c4\uad6c: "
        f"{_project_value(project, 'skills', '\uc785\ub825\ub418\uc9c0 \uc54a\uc74c')}",
    )


def _requires_user_confirmation(value: str) -> bool:
    signals = (
        "\uc0ac\uc6a9\uc790 \ud655\uc778",
        "\ud655\uc778 \uc694\uccad",
        "\ucd94\uac00 \ud655\uc778",
        "\ucd94\uac00 \uc815\ubcf4",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \uc9c8\ubb38",
        "\uc2b9\uc778 \uc694\uccad",
        "\ub3d9\uc758 \uc694\uccad",
    )

    return any(
        signal in value
        for signal in signals
    )


def _is_internal_report_instruction(value: str) -> bool:
    """Reject classifier/schema instructions that leaked into report content."""

    normalized = " ".join(
        (value or "").lower().split()
    )

    signals = (
        "confirmed_facts",
        "proposals",
        "unverified",
        "next_actions",
        "json",
        "\uc2a4\ud0a4\ub9c8",
        "\ud544\ub4dc",
        "\ud504\ub85c\uadf8\ub7a8\uc774 \uc9c1\uc811",
        "\ud504\ub85c\uadf8\ub7a8\uc5d0\uc11c \uc9c1\uc811",
        "\ubd84\ub958\ud574\uc57c",
        "\ubd84\ub958\ud558\uc9c0",
        "\ub123\uc5b4\uc57c",
        "\ucd94\uac00\ud574\uc57c",
        "\ud655\uc815 \uc0ac\uc2e4\ub85c \ubd84\ub958",
        "\ud655\uc815 \uc0ac\uc2e4\uc740 \ud504\ub85c\uadf8\ub7a8",
    )

    return any(
        signal in normalized
        for signal in signals
    )


def _requires_confirmation_dependency(
    value: str,
) -> bool:
    """Detect AI instructions that make progress depend on extra confirmation."""

    normalized = "".join(
        (value or "").lower().split()
    )

    signals = (
        "\ud655\uc778\ud544\uc694",
        "\ud655\uc778\uc694\uccad",
        "\ucd94\uac00\ud655\uc778",
        "\uc0ac\uc6a9\uc790\ud655\uc778",
        "\ub2f4\ub2f9\uc790\ud655\uc778",
        "\ub2e4\ub978\ub2f4\ub2f9\uc790\ud655\uc778",
        "\ud655\uc778\uc808\ucc28",
        "\uc2b9\uc778\uc694\uccad",
        "\ub3d9\uc758\uc694\uccad",
    )

    return any(
        signal in normalized
        for signal in signals
    )


def _neutralize_unverified_item(
    value: str,
) -> str:
    """Keep the unknown topic while removing instructions for resolving it."""

    cleaned = _clean_item(value)

    if not cleaned:
        return ""

    resolution_markers = (
        "\uc0ac\uc6a9\uc790 \ud655\uc778",
        "\ub2f4\ub2f9\uc790 \ud655\uc778",
        "\ub2e4\ub978 \ub2f4\ub2f9\uc790 \ud655\uc778",
        "\ucd94\uac00 \ud655\uc778",
        "\ud655\uc778 \uc694\uccad",
        "\ud655\uc778 \ud544\uc694",
        "\ud655\uc778 \uc808\ucc28",
        "\uc2b9\uc778 \uc694\uccad",
        "\ub3d9\uc758 \uc694\uccad",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \uc9c8\ubb38",
    )

    positions = [
        cleaned.find(marker)
        for marker in resolution_markers
        if marker in cleaned
    ]

    if positions:
        cleaned = cleaned[:min(positions)].rstrip(
            " ,.:;-"
        )

        # A removed confirmation clause can leave fragments such as
        # "... ?" or "...? ??". Remove only those trailing fragments.
        trailing_fragments = (
            "\uc5d0 \ub300\ud55c",
            "\uc5d0\ub300\ud55c",
            "\ub300\ud55c",
            "\ubc0f",
            "\ub610\ub294",
            "\uad00\ub828",
        )

        changed = True

        while cleaned and changed:
            changed = False

            for suffix in trailing_fragments:
                if cleaned.endswith(suffix):
                    cleaned = cleaned[:-len(suffix)].rstrip(
                        " ,.:;-"
                    )
                    changed = True
                    break

        # Remove a dangling Korean particle only after a clause was cut.
        for suffix in (
            "\uc740",
            "\ub294",
            "\uc774",
            "\uac00",
            "\uc744",
            "\ub97c",
        ):
            if (
                cleaned.endswith(suffix)
                and len(cleaned) > len(suffix) + 1
            ):
                cleaned = cleaned[:-len(suffix)].rstrip()
                break

    return cleaned


def sanitize_structured_report_ai_data(
    data: StructuredReportAIData,
    *,
    allow_unverified_progress: bool = False,
) -> StructuredReportAIData:
    """Validate AI-controlled report data before deterministic rendering."""

    proposals: list[str] = []

    for item in data.proposals:
        if _is_internal_report_instruction(item):
            continue

        if (
            allow_unverified_progress
            and _requires_confirmation_dependency(item)
        ):
            continue

        proposals.append(item)

    unverified: list[str] = []

    for item in data.unverified:
        if _is_internal_report_instruction(item):
            continue

        cleaned = (
            _neutralize_unverified_item(item)
            if allow_unverified_progress
            else _clean_item(item)
        )

        if cleaned:
            unverified.append(cleaned)

    limitations: list[str] = []

    for item in data.limitations:
        if _is_internal_report_instruction(item):
            continue

        if (
            allow_unverified_progress
            and _requires_confirmation_dependency(item)
        ):
            continue

        limitations.append(item)

    # Reuse the normal sanitizer for dedupe/length limits.
    proposals = list(_sanitize_items(proposals))
    unverified = list(_sanitize_items(unverified))
    limitations = list(_sanitize_items(limitations))

    unknown_keys = {
        _normalize_key(item)
        for item in unverified
    }

    proposals = [
        item
        for item in proposals
        if _normalize_key(item) not in unknown_keys
    ]

    return StructuredReportAIData(
        proposals=tuple(proposals),
        unverified=tuple(unverified),
        limitations=tuple(limitations),
    )


def _confirmed_project_values(
    project: dict,
) -> tuple[str, ...]:
    """Return non-empty values that came directly from project registration."""

    values = []

    for key in (
        "name",
        "field",
        "goal",
        "start_date",
        "target_date",
        "budget",
        "skills",
    ):
        value = str(project.get(key) or "").strip()

        if value:
            values.append(value)

    skills = str(project.get("skills") or "").strip()

    if skills:
        for item in skills.split(","):
            cleaned = item.strip()

            if cleaned:
                values.append(cleaned)

    return tuple(values)


def _contradicts_confirmed_project_source(
    value: str,
    project: dict,
) -> bool:
    """Reject AI claims that deny the source of registered project facts."""

    normalized = " ".join(
        (value or "").lower().split()
    )

    if not normalized:
        return False

    denial_signals = (
        "\uc0ac\uc6a9\uc790 \uc81c\uacf5 \uc815\ubcf4\uac00 \uc544\ub2cc",
        "\uc0ac\uc6a9\uc790 \uc81c\uacf5 \uc815\ubcf4\uc5d0 \ud3ec\ud568\ub418\uc9c0 \uc54a",
        "\uc0ac\uc6a9\uc790\uac00 \uc81c\uacf5\ud558\uc9c0 \uc54a\uc740",
        "\uc0ac\uc6a9\uc790\uac00 \uc81c\uacf5\ud55c \uc815\ubcf4\uac00 \uc544\ub2cc",
        "\ub4f1\ub85d\ub418\uc9c0 \uc54a\uc740",
        "\ud504\ub85c\uc81d\ud2b8 \uc815\ubcf4\uc5d0 \uc5c6\ub294",
        "\ud655\uc778\ub418\uc9c0 \uc54a\uc740 \ub3c4\uad6c",
        "\ubbf8\uc81c\uacf5 \ub3c4\uad6c",
        "\ud300\uc7a5 \uacc4\ud68d\uc11c\uc5d0\uc11c \uc81c\uc2dc\ub41c",
        "\uc9c1\uc6d0 \uacc4\ud68d\uc5d0\uc11c \uc81c\uc2dc\ub41c",
    )

    if not any(
        signal in normalized
        for signal in denial_signals
    ):
        return False

    confirmed_values = _confirmed_project_values(project)

    return any(
        confirmed.lower() in normalized
        for confirmed in confirmed_values
        if len(confirmed) >= 2
    )


def _filter_unverified_against_project_facts(
    items: list[str],
    project: dict,
) -> list[str]:
    """Do not let AI mark registered project fields themselves as unknown."""

    normalized_project = {
        key: str(project.get(key) or "").strip()
        for key in (
            "name",
            "field",
            "goal",
            "start_date",
            "target_date",
            "budget",
            "skills",
        )
    }

    protected_domains: list[tuple[str, ...]] = []

    if normalized_project["name"]:
        protected_domains.append(
            (
                "\ud504\ub85c\uc81d\ud2b8\uba85",
                "\ud504\ub85c\uc81d\ud2b8 \uc774\ub984",
            )
        )

    if normalized_project["field"]:
        protected_domains.append(
            (
                "\ud504\ub85c\uc81d\ud2b8 \ubd84\uc57c",
                "\ubd84\uc57c",
            )
        )

    if normalized_project["goal"]:
        protected_domains.append(
            (
                "\ud504\ub85c\uc81d\ud2b8 \ubaa9\ud45c",
                "\ubaa9\ud45c",
            )
        )

    if (
        normalized_project["start_date"]
        and normalized_project["target_date"]
    ):
        protected_domains.append(
            (
                "\ud504\ub85c\uc81d\ud2b8 \uae30\uac04",
                "\uae30\uac04",
                "\uc2dc\uc791\uc77c",
                "\uc885\ub8cc\uc77c",
                "\ubaa9\ud45c\uc77c",
                "\ud504\ub85c\uc81d\ud2b8 \uc77c\uc815",
            )
        )

    if normalized_project["budget"]:
        protected_domains.append(
            (
                "\ud504\ub85c\uc81d\ud2b8 \uc608\uc0b0",
                "\uc608\uc0b0",
            )
        )

    if normalized_project["skills"]:
        protected_domains.append(
            (
                "\ubcf4\uc720 \uae30\uc220 \ubc0f \ub3c4\uad6c",
                "\ubcf4\uc720 \uae30\uc220",
                "\ubcf4\uc720 \ub3c4\uad6c",
            )
        )

    # These words mean the item is asking about details beyond
    # the registered high-level fact, so it may remain unknown.
    detail_signals = (
        "\uc138\ubd80",
        "\uad6c\uccb4",
        "\ub0b4\uc5ed",
        "\ubc30\ubd84",
        "\ub2e8\uacc4\ubcc4",
        "\ub9c8\uc77c\uc2a4\ud1a4",
        "\uc0c1\uc138",
    )

    result: list[str] = []

    for item in items:
        normalized = " ".join(
            (item or "").lower().split()
        )

        if not normalized:
            continue

        is_detail = any(
            signal in normalized
            for signal in detail_signals
        )

        conflicts = any(
            any(
                alias in normalized
                for alias in aliases
            )
            for aliases in protected_domains
        )

        if conflicts and not is_detail:
            continue

        result.append(item)

    return result


def _render_actionable_project_guidance(
    project: dict,
    final_review_status: str,
    ai_data: StructuredReportAIData,
    *,
    allow_unverified_progress: bool,
) -> str:
    """설계 단계의 결과를 사용자가 바로 행동할 수 있는 안내로 렌더링합니다."""

    review_status = _clean_item(final_review_status) or "팀 문서 검토 상태 미확인"
    sanitized = sanitize_structured_report_ai_data(
        ai_data,
        allow_unverified_progress=allow_unverified_progress,
    )
    proposals = [
        item
        for item in sanitized.proposals
        if not _contradicts_confirmed_project_source(item, project)
    ]
    unverified = _filter_unverified_against_project_facts(
        [
            item
            for item in sanitized.unverified
            if not _contradicts_confirmed_project_source(item, project)
        ],
        project,
    )
    limitations = [
        item
        for item in sanitized.limitations
        if not _contradicts_confirmed_project_source(item, project)
    ]
    decisions = unverified or proposals
    first_decision = decisions[0] if decisions else "다음 설계 조건"

    lines = [
        "[현재 단계 결론]",
        (
            "지금은 제품을 완성한 단계가 아니라, 무엇을 만들지와 어떤 순서로 확인할지를 정하는 설계 단계입니다. "
            f"현재 상태는 '{review_status}'입니다. 이는 팀이 작성한 문서의 누락·모순을 검토한 결과이며, "
            "실제 거치대 제작, 부품 구매, 센서 성능, 안전성 시험이 끝났다는 뜻은 아닙니다."
        ),
        "",
        "[팀이 제안한 방향]",
        "아래 내용은 확정된 사양이 아니라, 다음 결정을 돕기 위한 제안입니다.",
    ]
    if proposals:
        lines.extend(f"- {item}" for item in proposals)
    else:
        lines.append("- 아직 구체적인 제안이 없습니다. 먼저 아래 결정부터 정하면 팀이 제안을 만들 수 있어요.")

    lines.extend([
        "",
        "[지금 결정할 한 가지]",
        f"- 먼저 **{first_decision}**을 정해보세요.",
        "- 이 조건이 정해져야 필요한 부품·기능·구조를 과하게 사거나 서로 맞지 않게 고르는 일을 줄일 수 있어요.",
        "- 선택지가 낯설다면 유키에게 '이 항목의 선택지와 차이를 학생도 이해하게 비교해줘'라고 말하면 됩니다.",
    ])
    if len(decisions) > 1:
        lines.extend(f"- 그다음 결정: {item}" for item in decisions[1:3])

    lines.extend([
        "",
        "[결정 후 팀이 할 일]",
        "1. 선택한 조건을 프로젝트 요구사항으로 기록합니다.",
        "2. 그 조건에 맞는 부품·도구·호환 조건을 조사하고, 필요하면 디바이스마트 검색 결과를 비교합니다.",
        "3. 작동 방식과 안전·시험 기준을 정리한 뒤, 그때 승인용 팀 업무 계획을 만듭니다.",
        "",
        "[검토 범위와 남은 확인]",
        f"- 팀 문서 검토 상태: {review_status}",
        "- 실제 제작·구매·조립·성능 시험은 아직 진행된 것으로 처리하지 않습니다.",
    ])
    if limitations:
        lines.append("- 추가로 확인할 점:")
        lines.extend(f"  - {item}" for item in limitations)
    else:
        lines.append("- 위의 첫 결정을 실제 조사 또는 대화로 확정해야 다음 단계로 갈 수 있어요.")
    return "\n".join(lines)


def render_structured_final_report(
    project: dict,
    final_review_status: str,
    ai_data: StructuredReportAIData,
    *,
    allow_unverified_progress: bool = False,
) -> str:
    """Render the final report without allowing AI to rewrite facts."""

    return _render_actionable_project_guidance(
        project,
        final_review_status,
        ai_data,
        allow_unverified_progress=allow_unverified_progress,
    )

    review_status = (
        _clean_item(final_review_status)
        or "\uac80\uc218 \uc0c1\ud0dc \ubbf8\ud655\uc778"
    )

    sanitized_ai_data = sanitize_structured_report_ai_data(
        ai_data,
        allow_unverified_progress=allow_unverified_progress,
    )

    proposals = [
        item
        for item in sanitized_ai_data.proposals
        if not _contradicts_confirmed_project_source(
            item,
            project,
        )
    ]

    unverified = _filter_unverified_against_project_facts(
        [
            item
            for item in sanitized_ai_data.unverified
            if not _contradicts_confirmed_project_source(
                item,
                project,
            )
        ],
        project,
    )

    limitations = [
        item
        for item in sanitized_ai_data.limitations
        if not _contradicts_confirmed_project_source(
            item,
            project,
        )
    ]

    # The final next action is owned by code, not by the language model.
    if "\ud1b5\uacfc" in review_status:
        if allow_unverified_progress and unverified:
            next_actions = [
                "\ubbf8\ud655\uc778 \ud56d\ubaa9은 \ubbf8\ud655\uc778 \uc0c1\ud0dc로 "
                "\uc720지하고, \ud604\uc7ac \ud655\uc778\ub41c \uc815\ubcf4 "
                "\ubc94\uc704\uc5d0서 \ub2e4\uc74c \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
            ]
        else:
            next_actions = [
                "\ud604\uc7ac \uac80\uc218\ub41c \uacb0\uacfc\ub97c \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc74c \ud504\ub85c\uc81d\ud2b8 \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
            ]
    else:
        next_actions = [
            "\ud604\uc7ac \uac80\uc218 \uc0c1\ud0dc\ub97c \uae30\uc900\uc73c\ub85c "
            "\ud544\uc694\ud55c \ud6c4\uc18d \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
        ]

    lines: list[str] = [
        "[\ucd5c\uc885 \uacb0\ub860]",
        (
            "\ub4f1\ub85d\ub41c \ud504\ub85c\uc81d\ud2b8 \uc815\ubcf4\uc640 "
            "\uc2e4\uc81c \uc6cc\ud06c\ud50c\ub85c \uac80\uc218 \uae30\ub85d\uc744 "
            "\uae30\uc900\uc73c\ub85c \ucd5c\uc885 \uacb0\uacfc\ub97c \uc815\ub9ac\ud588\uc2b5\ub2c8\ub2e4. "
            f"\ucd5c\uc885 \uac80\uc218 \uc0c1\ud0dc\ub294 '{review_status}'\uc785\ub2c8\ub2e4. "
            "\uacc4\ud68d\u00b7\uc81c\uc548\uacfc \ubbf8\ud655\uc778 \ud56d\ubaa9\uc740 "
            "\ud655\uc815 \uc0ac\uc2e4\uacfc \uad6c\ubd84\ud588\uc2b5\ub2c8\ub2e4."
        ),
        "",
        "[\ud575\uc2ec \uc0b0\ucd9c\ubb3c]",
    ]

    lines.extend(
        confirmed_project_fact_lines(project)
    )

    lines.extend([
        "",
        "- \uacc4\ud68d\u00b7\uc81c\uc548:",
    ])

    if proposals:
        lines.extend(
            f"  - {item}"
            for item in proposals
        )
    else:
        lines.append("  - \uc5c6\uc74c")

    lines.extend([
        "",
        "- \ubbf8\ud655\uc778 \uc0ac\ud56d:",
    ])

    if unverified:
        lines.extend(
            f"  - {item}"
            for item in unverified
        )
    else:
        lines.append("  - \uc5c6\uc74c")

    lines.extend([
        "",
        "[\uac80\uc218 \ubc0f \ud55c\uacc4]",
        f"- \ucd5c\uc885 \uac80\uc218 \uc0c1\ud0dc: {review_status}",
    ])

    if limitations:
        lines.append("- \ud55c\uacc4:")
        lines.extend(
            f"  - {item}"
            for item in limitations
        )
    else:
        lines.append("- \ud55c\uacc4: \ubcc4\ub3c4\ub85c \ubd84\ub958\ub41c \ud56d\ubaa9 \uc5c6\uc74c")

    lines.extend([
        "",
        "[\ub2e4\uc74c \ud589\ub3d9]",
    ])

    lines.extend(
        f"- {item}"
        for item in next_actions
    )

    return "\n".join(lines)


__all__ = [
    "STRUCTURED_REPORT_JSON_INSTRUCTION",
    "StructuredReportAIData",
    "confirmed_project_fact_lines",
    "parse_structured_report_json",
    "sanitize_structured_report_ai_data",
    "render_structured_final_report",
]

def is_structured_final_report(text: str | None) -> bool:
    """Return True only for rendered Structured Final Report messages."""

    if not text:
        return False

    cleaned = text.strip()

    return (
        (
            cleaned.startswith("[\ucd5c\uc885 \uacb0\ub860]")
            and "[\ud575\uc2ec \uc0b0\ucd9c\ubb3c]" in cleaned
        )
        or (
            cleaned.startswith("[\ud604\uc7ac \ub2e8\uacc4 \uacb0\ub860]")
            and "[\uc9c0\uae08 \uacb0\uc815\ud560 \ud55c \uac00\uc9c0]" in cleaned
        )
    )

