"""YOUFFICE AI 응답을 검증하고 안전하게 복구합니다."""

from collections.abc import Callable

from conversation.ollama_client import MODEL_NAME, optimized_chat
from conversation.prompts import BEGINNER_GUIDANCE_MARKER
from conversation.response_formats import (
    EMPLOYEE_RESULT_MARKERS,
    FINAL_REPORT_MARKERS,
    MANAGER_PLAN_MARKERS,
    MEETING_CONCLUSION_MARKERS,
    MEETING_OPINION_MARKERS,
)
from conversation.response_validator import is_korean_answer, remove_thinking


EMPTY_ANSWER_MESSAGE = (
    "AI 응답을 완성하지 못했습니다. "
    "잠시 후 다시 시도해주세요."
)


def _context_allows_unverified_progress(task_context: str) -> bool:
    """Return True when the user explicitly allows unknown items to remain unknown."""

    normalized = "".join((task_context or "").split()).lower()

    unverified_signals = (
        "\ubbf8\ud655\uc778\uc73c\ub85c\ud45c\uc2dc",
        "\ubbf8\ud655\uc778\ud56d\ubaa9\uc73c\ub85c",
        "\ubbf8\ud655\uc778\uc73c\ub85c\uad6c\ubd84",
    )

    no_guess_signals = (
        "\uc784\uc758\ub85c\uac00\uc815\ud558\uc9c0",
        "\ucd94\uce21\ud558\uc9c0",
        "\uc81c\uacf5\ud558\uc9c0\uc54a\uc740",
    )

    return (
        any(signal in normalized for signal in unverified_signals)
        and any(signal in normalized for signal in no_guess_signals)
    )


def normalize_final_report_next_actions(
    answer: str,
    task_context: str,
    required_markers: tuple[str, ...],
) -> str:
    """Remove contradictory user-confirmation actions from a final report."""

    if not answer:
        return answer

    if required_markers != FINAL_REPORT_MARKERS:
        return answer

    if not _context_allows_unverified_progress(task_context):
        return answer

    next_action_marker = "[\ub2e4\uc74c \ud589\ub3d9]"

    lines = answer.splitlines()

    try:
        section_start = next(
            index
            for index, line in enumerate(lines)
            if line.strip() == next_action_marker
        )
    except StopIteration:
        return answer

    contradictory_signals = (
        "\uc0ac\uc6a9\uc790 \ud655\uc778",
        "\ucd94\uac00 \ud655\uc778",
        "\ud655\uc778 \uc808\ucc28",
        "\ud655\uc778 \uc0ac\ud56d",
        "\ud655\uc778\uc744 \uc694\uccad",
        "\ucd94\uac00 \uc815\ubcf4",
        "\uc815\ubcf4 \uc81c\uacf5\uc744 \uc694\uccad",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \uc694\uccad",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \ud655\uc778",
        "\uc0ac\uc6a9\uc790\uc640\uc758 \ud611\uc758",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \uc9c8\ubb38",
    )

    kept_lines = lines[: section_start + 1]
    kept_action_count = 0

    for line in lines[section_start + 1:]:
        stripped = line.strip()

        # A later report section starts here.
        if (
            stripped.startswith("[")
            and stripped.endswith("]")
            and stripped != next_action_marker
        ):
            kept_lines.append(line)
            continue

        if any(signal in stripped for signal in contradictory_signals):
            continue

        kept_lines.append(line)

        if stripped:
            kept_action_count += 1

    if kept_action_count == 0:
        kept_lines.append(
            "- \ubbf8\ud655\uc778 \ud56d\ubaa9\uc740 "
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0\ud558\uace0, "
            "\ud604\uc7ac \ud655\uc778\ub41c \uc815\ubcf4 \ubc94\uc704\uc5d0\uc11c "
            "\ub2e4\uc74c \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
        )

    return "\n".join(kept_lines)


def normalize_final_report_unverified_policy(
    answer: str,
    task_context: str,
    required_markers: tuple[str, ...],
) -> str:
    """Keep unverified-progress policy consistent across the whole final report."""

    if not answer:
        return answer

    if required_markers != FINAL_REPORT_MARKERS:
        return answer

    if not _context_allows_unverified_progress(task_context):
        return answer

    replacements = (
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc774 \ud544\uc694\ud55c \ud56d\ubaa9\uc740",
            "\ubbf8\ud655\uc778 \ud56d\ubaa9\uc740",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc774 \ud544\uc694\ud55c \ud56d\ubaa9",
            "\ubbf8\ud655\uc778 \ud56d\ubaa9",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc774 \ud544\uc694\ud558\uba70",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0\ud558\uba70",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0\ud569\ub2c8\ub2e4",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc774 \ud544\uc694\ud558\ub2e4",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0\ud55c\ub2e4",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc774 \ud544\uc694\ud568",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778 \uc0ac\ud56d",
            "\ubbf8\ud655\uc778 \uc0ac\ud56d",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778 \uc808\ucc28",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc \uc720\uc9c0",
        ),
    )

    confirmation_route_replacements = (
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc744 \ud1b5\ud574 \uba85\ud655\ud654",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778 \ud6c4\uc5d0 \uba85\ud655\ud654",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778 \ud6c4 \uba85\ud655\ud654",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc744 \uac70\uccd0 \uba85\ud655\ud654",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0",
        ),
        (
            "\uc0ac\uc6a9\uc790 \ud655\uc778\uc73c\ub85c \uba85\ud655\ud654",
            "\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c \uc720\uc9c0",
        ),
    )

    confirmation_heading = "\uc0ac\uc6a9\uc790 \ud655\uc778 \uc0ac\ud56d"
    unverified_heading = "\ubbf8\ud655\uc778 \uc0ac\ud56d"

    request_signals = (
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \ud655\uc778 \uc694\uccad",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \ucd94\uac00 \ud655\uc778",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \uc9c8\ubb38",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \uc2b9\uc778 \uc694\uccad",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \ub3d9\uc758 \uc694\uccad",
        "\uc0ac\uc6a9\uc790\uc5d0\uac8c \ucd94\uac00 \uc815\ubcf4",
        "\uc0ac\uc6a9\uc790\uc640\uc758 \ud611\uc758 \ud6c4",
        "\ud655\uc778 \uc694\uccad",
        "\ucd94\uac00 \uc870\uc0ac \uc694\uccad",
        "\uc0ac\uc6a9\uc790 \ud655\uc778\uc744 \ud1b5\ud574",
        "\uc0ac\uc6a9\uc790 \ud655\uc778 \ud6c4",
        "\uc0ac\uc6a9\uc790 \ud655\uc778\uc744 \uac70\uccd0",
        "\uc0ac\uc6a9\uc790 \ud655\uc778\uc73c\ub85c",
    )

    negative_signals = (
        "\ud544\uc694 \uc5c6\uc74c",
        "\ud544\uc694\ud558\uc9c0 \uc54a",
        "\uc694\uad6c\ud558\uc9c0 \uc54a",
        "\ubb3b\uc9c0 \uc54a",
    )

    approval_suffixes = (
        "\uc5d0 \ub300\ud55c \ub3d9\uc758",
        "\uc5d0 \ub300\ud55c \ud655\uc778",
        "\uc5d0 \ub300\ud55c \uc2b9\uc778",
        "\uc758 \ub3d9\uc758",
        "\uc758 \ud655\uc778",
        "\uc758 \uc2b9\uc778",
    )

    lines = answer.splitlines()
    result = []
    inside_confirmation_block = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            inside_confirmation_block = False
            result.append(line)
            continue

        indent_size = len(line) - len(line.lstrip())
        label_text = stripped.lstrip("-* ").replace("**", "").strip()

        if label_text.startswith(confirmation_heading):
            indent = line[:indent_size]
            bullet = "- " if stripped.startswith(("-", "*")) else ""

            result.append(
                f"{indent}{bullet}{unverified_heading}:"
            )
            inside_confirmation_block = True
            continue

        if inside_confirmation_block:
            if (
                stripped.startswith(("-", "*"))
                and indent_size == 0
            ):
                inside_confirmation_block = False

            elif stripped.startswith(("-", "*")):
                indent = line[:indent_size]
                content = stripped[1:].strip()

                for suffix in approval_suffixes:
                    if content.endswith(suffix):
                        content = content[:-len(suffix)].strip()
                        break

                if content:
                    result.append(
                        f"{indent}- {content}"
                    )
                continue

            elif not stripped:
                result.append(line)
                continue

        normalized_line = line

        if "\uc0ac\uc6a9\uc790 \ud655\uc778 \ud544\uc694: \uc5c6\uc74c" not in normalized_line:
            for old, new in replacements:
                normalized_line = normalized_line.replace(
                    old,
                    new,
                )

            for old, new in confirmation_route_replacements:
                normalized_line = normalized_line.replace(
                    old,
                    new,
                )

        stripped_normalized = normalized_line.strip()

        if (
            any(
                signal in stripped_normalized
                for signal in request_signals
            )
            and not any(
                signal in stripped_normalized
                for signal in negative_signals
            )
        ):
            continue

        result.append(normalized_line)

    return "\n".join(result)


def normalize_final_report_provenance(
    answer: str,
    task_context: str,
    required_markers: tuple[str, ...],
) -> str:
    """Keep unconfirmed technical proposals from becoming confirmed facts."""

    if not answer:
        return answer

    if required_markers != FINAL_REPORT_MARKERS:
        return answer

    if not _context_allows_unverified_progress(task_context):
        return answer

    core_marker = "[\ud575\uc2ec \uc0b0\ucd9c\ubb3c]"
    next_marker = "[\ub2e4\uc74c \ud589\ub3d9]"

    risky_labels = (
        "\uae30\uc220 \uad6c\uc131",
        "\uae30\uc220 \uad6c\uc870",
        "\uae30\uc220 \uad6c\uc870 \uc124\uacc4",
        "\uad6c\ud604 \ubc0f \uac80\uc99d \ud56d\ubaa9",
        "\uc2dc\uc2a4\ud15c \uad6c\uc131",
        "\uc2dc\uc2a4\ud15c \uc5f0\uacb0 \ubc29\uc2dd",
        "\uc2dc\uc2a4\ud15c \uad6c\uc870",
        "\uc544\ud0a4\ud14d\ucc98",
        "\uc81c\uc5b4 \ud750\ub984",
        "\uad6c\ud604 \ud56d\ubaa9",
        "\uac80\uc99d \ud56d\ubaa9",
        "API",
    )

    already_unverified = (
        "\ubbf8\ud655\uc778",
        "\uc81c\uc548(\ubbf8\ud655\uc778)",
        "\uc0ac\uc6a9\uc790 \uc81c\uacf5",
        "\ud655\uc778\ub41c \uc0ac\uc2e4",
    )

    risky_action_signals = (
        "\uc678\ubd80 \uc5f0\ub3d9",
        "\ub370\uc774\ud130 \uc18c\uc2a4",
        "\uc0ac\uc6a9\uc790 \uc778\ud130\ud398\uc774\uc2a4 \ub514\uc790\uc778",
        "\uc694\uad6c \uc0ac\ud56d\uc5d0 \ub300\ud55c \uac80\ud1a0",
        "\uc0ac\uc6a9\uc790 \ud655\uc778",
        "\ucd94\uac00 \ud655\uc778",
        "API",
        "\uc2dc\uc2a4\ud15c \uad6c\uc870",
        "\uc544\ud0a4\ud14d\ucc98",
        "\uc131\ub2a5 \uc218\uce58",
        "\uad6c\ud604 \uc644\ub8cc",
        "\uc644\ub8cc \uc0c1\ud0dc \ud655\uc778",
    )

    lines = answer.splitlines()
    result = []
    section = ""
    kept_next_actions = 0

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
            result.append(line)
            continue

        if section == core_marker and stripped.startswith("-"):
            content = stripped[1:].strip()

            # Markdown bold/italic markers must not bypass provenance checks.
            plain_content = (
                content
                .replace("**", "")
                .replace("__", "")
                .strip()
            )

            changed = False

            for label in risky_labels:
                prefix = f"{label}:"

                if not plain_content.startswith(prefix):
                    continue

                value = plain_content[len(prefix):].strip()

                if any(
                    marker in value
                    for marker in already_unverified
                ):
                    break

                indent = line[: len(line) - len(line.lstrip())]

                if value:
                    result.append(
                        f"{indent}- {label}: "
                        f"\uc81c\uc548(\ubbf8\ud655\uc778) - {value}"
                    )
                else:
                    result.append(
                        f"{indent}- {label}: "
                        f"\uc81c\uc548(\ubbf8\ud655\uc778)"
                    )

                changed = True
                break

            if changed:
                continue

        if section == next_marker and stripped.startswith(("-", "*")):
            if any(
                signal in stripped
                for signal in risky_action_signals
            ):
                continue

            if stripped:
                kept_next_actions += 1

        result.append(line)

    if next_marker in [line.strip() for line in result]:
        next_index = next(
            i
            for i, line in enumerate(result)
            if line.strip() == next_marker
        )

        actions_after_marker = [
            line
            for line in result[next_index + 1:]
            if line.strip().startswith(("-", "*"))
        ]

        if not actions_after_marker:
            result.append(
                "- \ud604\uc7ac \ud655\uc778\ub41c \uc815\ubcf4\uc640 "
                "\ubbf8\ud655\uc778 \uad6c\ubd84\uc744 \uc720\uc9c0\ud55c \ucc44 "
                "\uacc4\ud68d\uc11c\ub97c \uae30\uc900\uc73c\ub85c "
                "\ub2e4\uc74c \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
            )

    return "\n".join(result)


def normalize_final_report_internal_consistency(
    answer: str,
    task_context: str,
    required_markers: tuple[str, ...],
) -> str:
    """Prevent an unverified topic from being promoted to a confirmed fact."""

    if not answer:
        return answer

    if required_markers != FINAL_REPORT_MARKERS:
        return answer

    if not _context_allows_unverified_progress(task_context):
        return answer

    unverified_heading = "\ubbf8\ud655\uc778 \uc0ac\ud56d"
    confirmed_heading = "\ud655\uc778\ub41c \uc0ac\uc2e4"

    certainty_signals = (
        "\uba85\ud655\ud788 \uc815\uc758",
        "\uc815\uc758\ub428",
        "\uc815\uc758\ub418",
        "\ud655\uc778\ub428",
        "\ud655\uc778\ub418",
        "\ud655\uc815\ub428",
        "\ud655\uc815\ub418",
        "\uac80\uc99d\ub428",
        "\uac80\uc99d\ub418",
        "\uc644\ub8cc\ub428",
        "\uc644\ub8cc\ub418",
        "\ud3ec\ud568\ub418\uc5b4\uc57c \ud568\uc774 \ud655\uc778",
        "\ud3ec\ud568\ub418\uc5b4\uc57c \ud568\uc744 \ud655\uc778",
    )

    employee_source_signals = (
        "\ub2f4\ub2f9 \uacb0\uacfc\uc5d0\uc11c",
        "\uc9c1\uc6d0 \uacb0\uacfc\uc5d0\uc11c",
        "\ud68c\uc758 \uacb0\uacfc\uc5d0\uc11c",
        "\uac80\uc218 \uacb0\uacfc\uc5d0\uc11c",
    )

    stop_tokens = {
        "\ubbf8\ud655\uc778",
        "\uc0ac\ud56d",
        "\uc0c1\ud0dc",
        "\uc720\uc9c0",
        "\uad6c\uccb4\uc801",
        "\ub0b4\uc6a9",
        "\ub300\ud55c",
        "\uad00\ub828",
        "\ud544\uc694",
        "\ud544\uc694\ud568",
        "\ubc0f",
        "\ub4f1",
    }

    def clean_markdown(value: str) -> str:
        return (
            value
            .replace("**", "")
            .replace("__", "")
            .replace("`", "")
            .strip()
        )

    def topic_tokens(value: str) -> set[str]:
        cleaned = clean_markdown(value)

        for char in (
            ":", ",", ".", "(", ")", "[", "]",
            "/", "\\", "-", "\u00b7",
        ):
            cleaned = cleaned.replace(char, " ")

        raw_tokens = cleaned.split()
        tokens = set()

        suffixes = (
            "\uc5d0\uc11c",
            "\uc73c\ub85c",
            "\ub85c",
            "\uc740",
            "\ub294",
            "\uc774",
            "\uac00",
            "\uc744",
            "\ub97c",
            "\uc758",
            "\uc5d0",
        )

        for token in raw_tokens:
            token = token.strip()

            for suffix in suffixes:
                if (
                    token.endswith(suffix)
                    and len(token) > len(suffix) + 1
                ):
                    token = token[:-len(suffix)]
                    break

            if (
                len(token) >= 2
                and token not in stop_tokens
            ):
                tokens.add(token.lower())

        return tokens

    def topics_overlap(
        line_text: str,
        topic_text: str,
    ) -> bool:
        line_tokens = topic_tokens(line_text)
        subject_tokens = topic_tokens(topic_text)

        common = line_tokens & subject_tokens

        if len(common) >= 2:
            return True

        strong_tokens = {
            "api",
            "\uc2dc\uc2a4\ud15c",
            "\uc544\ud0a4\ud14d\ucc98",
            "\uc131\ub2a5",
            "\uad6c\ud604",
            "\uac80\uc218",
            "\uc5ed\ud560",
            "\ubd84\ub2f4",
            "ui",
            "ux",
        }

        return bool(common & strong_tokens)

    lines = answer.splitlines()

    # -----------------------------------------------------
    # -----------------------------------------------------

    unknown_topics = []
    inside_unverified_block = False
    unverified_indent = 0

    for line in lines:
        stripped = line.strip()
        plain = clean_markdown(
            stripped.lstrip("-* ").strip()
        )

        if stripped.startswith("[") and stripped.endswith("]"):
            inside_unverified_block = False
            continue

        indent_size = len(line) - len(line.lstrip())

        if plain.startswith(unverified_heading):
            inside_unverified_block = True
            unverified_indent = indent_size
            continue

        if inside_unverified_block:
            if (
                stripped.startswith(("-", "*"))
                and indent_size > unverified_indent
            ):
                content = clean_markdown(
                    stripped[1:].strip()
                )

                if content:
                    unknown_topics.append(content)

                continue

            if (
                stripped
                and indent_size <= unverified_indent
            ):
                inside_unverified_block = False

        if "\ubbf8\ud655\uc778" in plain:
            topic = plain.split(
                "\ubbf8\ud655\uc778",
                1,
            )[0].strip(
                " :-"
            )

            if topic:
                unknown_topics.append(topic)

    # ?? ??
    unique_topics = []

    for topic in unknown_topics:
        if topic not in unique_topics:
            unique_topics.append(topic)

    if not unique_topics:
        return answer

    # -----------------------------------------------------
    # -----------------------------------------------------

    result = []
    inside_confirmed_block = False
    confirmed_indent = 0

    for line in lines:
        stripped = line.strip()
        plain = clean_markdown(
            stripped.lstrip("-* ").strip()
        )

        if stripped.startswith("[") and stripped.endswith("]"):
            inside_confirmed_block = False
            result.append(line)
            continue

        indent_size = len(line) - len(line.lstrip())

        if plain.startswith(confirmed_heading):
            inside_confirmed_block = True
            confirmed_indent = indent_size
            result.append(line)
            continue

        if inside_confirmed_block:
            if (
                stripped.startswith(("-", "*"))
                and indent_size > confirmed_indent
            ):
                related = any(
                    topics_overlap(plain, topic)
                    for topic in unique_topics
                )

                if related:
                    indent = line[:indent_size]
                    content = clean_markdown(
                        stripped[1:].strip()
                    )

                    result.append(
                        f"{indent}- "
                        f"\uc81c\uc548(\ubbf8\ud655\uc778): "
                        f"{content}"
                    )
                    continue

            elif (
                stripped
                and indent_size <= confirmed_indent
            ):
                inside_confirmed_block = False

        related_topic = next(
            (
                topic
                for topic in unique_topics
                if topics_overlap(plain, topic)
            ),
            None,
        )

        has_certainty = any(
            signal in plain
            for signal in certainty_signals
        )

        employee_claim = any(
            signal in plain
            for signal in employee_source_signals
        )

        if (
            "\ubbf8\ud655\uc778" in plain
            and has_certainty
        ):
            indent = line[:indent_size]
            bullet = "- " if stripped.startswith(("-", "*")) else ""

            topic_text = plain.split(
                "\ubbf8\ud655\uc778",
                1,
            )[0].strip(
                " :-"
            )

            if not topic_text:
                topic_text = "\ud574\ub2f9 \ud56d\ubaa9"

            result.append(
                f"{indent}{bullet}"
                f"{topic_text}: "
                f"\ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c "
                f"\uc720\uc9c0\ud569\ub2c8\ub2e4."
            )
            continue

        if (
            related_topic
            and has_certainty
        ):
            indent = line[:indent_size]
            bullet = "- " if stripped.startswith(("-", "*")) else ""

            result.append(
                f"{indent}{bullet}"
                f"\uc81c\uc548(\ubbf8\ud655\uc778): "
                f"{plain}"
            )
            continue

        if (
            related_topic
            and employee_claim
            and has_certainty
        ):
            indent = line[:indent_size]
            bullet = "- " if stripped.startswith(("-", "*")) else ""

            result.append(
                f"{indent}{bullet}"
                f"\uc81c\uc548(\ubbf8\ud655\uc778): "
                f"{plain}"
            )
            continue

        result.append(line)

    return "\n".join(result)


def _confirmed_project_fact_lines(
    project: dict | None,
) -> list[tuple[str, str]]:
    """Return canonical project facts registered by the user."""

    if not project:
        return []

    name = str(project.get("name") or "").strip()
    field = str(project.get("field") or "").strip()
    goal = str(project.get("goal") or "").strip()
    skills_raw = str(project.get("skills") or "").strip()
    uses_step_by_step_guidance = skills_raw.startswith(BEGINNER_GUIDANCE_MARKER)
    skills = skills_raw.removeprefix(BEGINNER_GUIDANCE_MARKER).strip()

    facts = [
        ("\ud504\ub85c\uc81d\ud2b8\uba85", name),
        ("\ubd84\uc57c", field),
        ("\ubaa9\ud45c", goal),
        ("\ud604\uc7ac \uc54c\uace0 \uc788\uac70\ub098 \ubcf4\uc720\ud55c \ub0b4\uc6a9", skills),
    ]
    if uses_step_by_step_guidance:
        facts.append(
            (
                "\uc9c4\ud589 \ubc29\uc2dd",
                "AI\uac00 \ud544\uc694\ud55c \uc9c8\ubb38\uc744 \uc27d\uac8c 1~2\uac1c\uc529 \ub098\ub204\uc5b4 \uc548\ub0b4",
            )
        )

    return [
        (label, value)
        for label, value in facts
        if value
    ]


def _confirmed_project_fact_rule(
    project: dict | None,
) -> str:
    """Build an AI instruction that distinguishes registered facts from proposals."""

    facts = _confirmed_project_fact_lines(project)

    if not facts:
        return ""

    lines = "\n".join(
        f"- {label}: {value}"
        for label, value in facts
    )

    return (
        "\ub2e4\uc74c\uc740 \uc0ac\uc6a9\uc790\uac00 "
        "\ud504\ub85c\uc81d\ud2b8\uc5d0 \uc9c1\uc811 \ub4f1\ub85d\ud55c "
        "\ud655\uc815 \uc0ac\uc2e4\uc774\ub2e4. "
        "\uac12\uc744 \ubc14\uafb8\uac70\ub098 \uc0ad\uc81c\ud558\uac70\ub098 "
        "\ubbf8\ud655\uc778\uc73c\ub85c \uc7ac\ubd84\ub958\ud558\uc9c0 \uc54a\ub294\ub2e4.\n"
        + lines
        + "\n\ub2e8, \ubcf4\uc720 \uae30\uc220\u00b7\ub3c4\uad6c\uac00 "
        "\ub4f1\ub85d\ub418\uc5b4 \uc788\ub2e4\ub294 \uc0ac\uc2e4\uacfc "
        "\uadf8 \ub3c4\uad6c\uc758 \uad6c\uccb4\uc801\uc778 \uc0ac\uc6a9 \ubc29\uc2dd\uc774 "
        "\ud655\uc815\ub418\uc5c8\ub2e4\ub294 \uc0ac\uc2e4\uc740 \uad6c\ubd84\ud55c\ub2e4."
    )


def normalize_confirmed_project_facts(
    answer: str,
    project: dict | None,
    required_markers: tuple[str, ...],
) -> str:
    """Protect user-registered project facts in final reports."""

    if not answer or not project:
        return answer

    if required_markers != FINAL_REPORT_MARKERS:
        return answer

    facts = _confirmed_project_fact_lines(project)

    if not facts:
        return answer

    core_marker = "[\ud575\uc2ec \uc0b0\ucd9c\ubb3c]"
    review_marker = "[\uac80\uc218 \ubc0f \ud55c\uacc4]"

    canonical_labels = {
        label
        for label, _ in facts
    }

    negative_registration_signals = (
        "\uc0ac\uc6a9\uc790 \uc81c\uacf5 \ubc94\uc704\uc5d0 \ud574\ub2f9\ud558\uc9c0",
        "\uc0ac\uc6a9\uc790\uac00 \uc81c\uacf5\ud558\uc9c0 \uc54a\uc740",
        "\uc0ac\uc6a9\uc790\uac00 \uc81c\uacf5\ud558\uc9c0\uc54a\uc740",
        "\uc81c\uacf5\ub418\uc9c0 \uc54a\uc740 \uae30\uc220",
        "\ub4f1\ub85d\ub418\uc9c0 \uc54a\uc740",
        "\ubbf8\uc81c\uacf5 \ub3c4\uad6c",
        "\ubcf4\uc720\ud558\uc9c0 \uc54a\uc740",
    )

    fact_values = [
        value
        for _, value in facts
        if value
    ]

    skills = str(project.get("skills") or "").strip()
    skill_items = [
        item.strip()
        for item in skills.split(",")
        if item.strip()
    ]

    lines = answer.splitlines()
    cleaned = []

    for line in lines:
        stripped = line.strip()

        mentioned_confirmed_fact = any(
            value in stripped
            for value in fact_values
        )

        mentioned_registered_tool = any(
            item in stripped
            for item in skill_items
        )

        contradicts_registration = any(
            signal in stripped
            for signal in negative_registration_signals
        )

        if (
            contradicts_registration
            and (
                mentioned_confirmed_fact
                or mentioned_registered_tool
            )
        ):
            continue

        cleaned.append(line)

    lines = cleaned

    try:
        core_index = next(
            index
            for index, line in enumerate(lines)
            if line.strip() == core_marker
        )
    except StopIteration:
        return "\n".join(lines)

    try:
        core_end = next(
            index
            for index in range(core_index + 1, len(lines))
            if lines[index].strip() == review_marker
        )
    except StopIteration:
        core_end = len(lines)

    retained_core = []

    for line in lines[core_index + 1:core_end]:
        stripped = line.strip()
        content = stripped

        if content.startswith(("-", "*")):
            content = content[1:].strip()

        content = content.replace("**", "")

        is_canonical_fact_line = any(
            content.startswith(f"{label}:")
            or content.startswith(f"{label} :")
            for label in canonical_labels
        )

        if is_canonical_fact_line:
            continue

        retained_core.append(line)

    canonical_block = [""]

    for label, value in facts:
        canonical_block.append(
            f"- {label}: {value}"
        )

    canonical_block.append("")

    lines = (
        lines[:core_index + 1]
        + canonical_block
        + retained_core
        + lines[core_end:]
    )

    return "\n".join(lines)


def final_answer_with_retry(
    raw_text: str | None,
    task_context: str,
    output_instruction: str = "",
    required_markers: tuple[str, ...] = (),
    required_literals: tuple[str, ...] = (),
    forbidden_phrases: tuple[str, ...] = (),
    confirmed_project_facts: dict | None = None,
    max_regenerations: int = 2,
    on_regeneration: Callable[[int], None] | None = None,
) -> str:
    """필터 결과가 비면 원래 업무 목적을 유지하며 한국어 답변을 다시 요청합니다."""

    if max_regenerations < 0:
        raise ValueError("max_regenerations must be zero or greater")

    answer = remove_thinking(raw_text)

    confirmed_fact_rule = _confirmed_project_fact_rule(
        confirmed_project_facts
    )

    if confirmed_fact_rule:
        output_instruction = (
            output_instruction
            + "\n\n"
            + confirmed_fact_rule
        )
    answer = normalize_final_report_next_actions(
        answer,
        task_context,
        required_markers,
    )
    answer = normalize_final_report_unverified_policy(
        answer,
        task_context,
        required_markers,
    )
    answer = normalize_final_report_provenance(
        answer,
        task_context,
        required_markers,
    )
    answer = normalize_final_report_internal_consistency(
        answer,
        task_context,
        required_markers,
    )
    answer = normalize_confirmed_project_facts(
        answer,
        confirmed_project_facts,
        required_markers,
    )

    if required_literals:
        literal_rule = (
            "\ud655\uc815 \ubb38\uc790\uc5f4\uc740 "
            "\uae00\uc790, \uc22b\uc790, \uacf5\ubc31\uc744 "
            "\ubc14\uafb8\uc9c0 \ub9d0\uace0 "
            "\uadf8\ub300\ub85c \ud3ec\ud568\ud55c\ub2e4.\n"
            + "\n".join(
                f"- {literal}"
                for literal in required_literals
            )
        )
        output_instruction = (
            output_instruction
            + "\n\n"
            + literal_rule
        )


    if forbidden_phrases:
        forbidden_rule = (
            "최종 보고서에서는 이미 "
            "검수를 통과한 결과를 "
            "다시 완성하기 위해 "
            "사용자에게 추가 질문, "
            "추가 확인, 추가 정보 제공을 "
            "요구하지 않는다. "
            "미확인으로 남겨도 되는 "
            "항목은 그대로 미확인으로 "
            "유지한다.\n"
            + "\n".join(
                f"- 금지 표현: {phrase}"
                for phrase in forbidden_phrases
            )
        )
        output_instruction = (
            output_instruction
            + "\n\n"
            + forbidden_rule
        )

    if (
        answer
        and is_korean_answer(answer)
        and all(marker in answer for marker in required_markers)
        and all(literal in answer for literal in required_literals)
        and not any(phrase in answer for phrase in forbidden_phrases)
    ):
        return answer

    if max_regenerations == 0:
        return EMPTY_ANSWER_MESSAGE

    if on_regeneration is not None:
        on_regeneration(1)

    if required_markers == MANAGER_PLAN_MARKERS:
        retry_answer_prefix = "[업무 접수]\n"
    elif required_markers == EMPLOYEE_RESULT_MARKERS:
        retry_answer_prefix = "[담당 결과]\n"
    elif required_markers == MEETING_OPINION_MARKERS:
        retry_answer_prefix = "[확인한 연결점]\n"
    elif required_markers == MEETING_CONCLUSION_MARKERS:
        retry_answer_prefix = "[회의 결론]\n"
    elif required_markers == FINAL_REPORT_MARKERS:
        retry_answer_prefix = "[최종 결론]\n"
    else:
        retry_answer_prefix = "# 최종 답변\n"

    try:
        retry_response = optimized_chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 추가 출력 지침에 지정된 YOUFFICE 직원의 응답을 복구하는 편집자다. "
                        "추가 출력 지침의 담당 범위와 금지 범위를 가장 우선한다. "
                        "반드시 자연스러운 한국어로 검증 가능한 응답만 작성한다. "
                        "제목, 본문, 표의 모든 설명을 "
                        "한국어로 쓴다. 기술 명칭 외에는 영어 문장을 한 줄도 쓰지 않는다. "
                        "내부 사고 과정, 영어 분석, "
                        "think 태그, 'Let me think' 문구는 절대 출력하지 않는다. "
                        "근거 없는 성능 수치나 비용 절감액은 확정 사실로 쓰지 않는다. "
                        f"추가 출력 지침:\n{output_instruction}\n"
                        "/no_think"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "아래 업무 내용을 학생도 이해할 수 있는 충분한 설명의 최종 답변으로 "
                        "다시 작성하세요. 핵심만 던지고 끝내지 말고, 필요한 이유·주의점·다음 행동을 쉬운 말로 풀되 소제목과 목록으로 읽기 쉽게 정리하세요.\n\n"
                        f"{task_context[:12000]}\n\n"
                        f"추가 출력 지침:\n{output_instruction}\n\n"
                        "반드시 지금부터 한국어 최종 답변만 출력하세요.\n/no_think"
                    ),
                },
            ],
            think=False,
            stream=False,
            options={"temperature": 0.2},
            answer_prefix=retry_answer_prefix,
        )
        retry_answer = remove_thinking(
            retry_response.message.content
        )
        retry_answer = normalize_final_report_next_actions(
            retry_answer,
            task_context,
            required_markers,
        )
        retry_answer = normalize_final_report_unverified_policy(
            retry_answer,
            task_context,
            required_markers,
        )
        retry_answer = normalize_final_report_provenance(
            retry_answer,
            task_context,
            required_markers,
        )
        retry_answer = normalize_final_report_internal_consistency(
            retry_answer,
            task_context,
            required_markers,
        )
        retry_answer = normalize_confirmed_project_facts(
            retry_answer,
            confirmed_project_facts,
            required_markers,
        )
        if (
            retry_answer
            and is_korean_answer(retry_answer)
            and all(marker in retry_answer for marker in required_markers)
        and all(literal in retry_answer for literal in required_literals)
        and not any(phrase in retry_answer for phrase in forbidden_phrases)
        ):
            return retry_answer

        if max_regenerations == 1:
            return EMPTY_ANSWER_MESSAGE

        if on_regeneration is not None:
            on_regeneration(2)

        second_retry = optimized_chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "너는 한국어 기술 문서 편집자다. 출력은 반드시 한국어여야 한다. "
                        "영어 문장을 번역하고, 근거 없는 수치·과장·약속은 제거한다. "
                        f"추가 출력 지침:\n{output_instruction}\n"
                        "내부 사고 과정 없이 완성된 답변만 출력한다. /no_think"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "아래 응답을 자연스러운 한국어 최종 답변으로 다시 작성하세요.\n\n"
                        f"{(retry_answer or answer or task_context)[:8000]}\n\n"
                        f"추가 출력 지침:\n{output_instruction}\n/no_think"
                    ),
                },
            ],
            think=False,
            stream=False,
            options={"temperature": 0.1},
            answer_prefix=retry_answer_prefix,
        )
        second_answer = remove_thinking(
            second_retry.message.content
        )
        second_answer = normalize_final_report_next_actions(
            second_answer,
            task_context,
            required_markers,
        )
        second_answer = normalize_final_report_unverified_policy(
            second_answer,
            task_context,
            required_markers,
        )
        second_answer = normalize_final_report_provenance(
            second_answer,
            task_context,
            required_markers,
        )
        second_answer = normalize_final_report_internal_consistency(
            second_answer,
            task_context,
            required_markers,
        )
        second_answer = normalize_confirmed_project_facts(
            second_answer,
            confirmed_project_facts,
            required_markers,
        )
        if (
            second_answer
            and is_korean_answer(second_answer)
            and all(marker in second_answer for marker in required_markers)
        and all(literal in second_answer for literal in required_literals)
        and not any(phrase in second_answer for phrase in forbidden_phrases)
        ):
            return second_answer
        return EMPTY_ANSWER_MESSAGE
    except Exception:
        return EMPTY_ANSWER_MESSAGE
