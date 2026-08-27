"""Safe, exact-text revision helpers for saved project reports."""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportEdit:
    old_text: str
    new_text: str


def parse_report_revision_json(
    raw_text: str | None,
) -> tuple[ReportEdit, ...]:
    """Parse exact replacement operations proposed by the AI."""

    text = (raw_text or "").strip()

    if not text:
        raise ValueError("EMPTY_REPORT_REVISION")

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("REPORT_REVISION_JSON_NOT_FOUND")

    payload = json.loads(text[start:end + 1])

    if not isinstance(payload, dict):
        raise ValueError("REPORT_REVISION_JSON_NOT_OBJECT")

    raw_edits = payload.get("edits")

    if not isinstance(raw_edits, list):
        raise ValueError("REPORT_REVISION_EDITS_NOT_LIST")

    edits: list[ReportEdit] = []

    for item in raw_edits:
        if not isinstance(item, dict):
            continue

        old_text = str(
            item.get("old_text") or ""
        ).strip()

        new_text = str(
            item.get("new_text") or ""
        ).strip()

        if not old_text:
            continue

        if old_text == new_text:
            continue

        edits.append(
            ReportEdit(
                old_text=old_text,
                new_text=new_text,
            )
        )

    return tuple(edits)


def _protected_project_values(
    project: dict,
) -> tuple[str, ...]:
    """Values that a report revision must never rewrite."""

    values: list[str] = []

    for key in (
        "name",
        "field",
        "goal",
        "start_date",
        "target_date",
        "budget",
        "skills",
    ):
        value = str(
            project.get(key) or ""
        ).strip()

        if value:
            values.append(value)

    return tuple(values)


def edit_touches_protected_fact(
    edit: ReportEdit,
    project: dict,
) -> bool:
    """Return True when an edit touches DB- or code-owned report content."""

    old_normalized = " ".join(
        edit.old_text.split()
    )

    # Exact registered project values are code-owned.
    if any(
        value in old_normalized
        for value in _protected_project_values(project)
        if len(value) >= 2
    ):
        return True

    # Protect lines whose meaning is explicitly a registered project field.
    protected_line_prefixes = (
        "\ud504\ub85c\uc81d\ud2b8\uba85",
        "\ud504\ub85c\uc81d\ud2b8 \uc774\ub984",
        "\ubd84\uc57c",
        "\ubaa9\ud45c",
        "\uae30\uac04",
        "\uc2dc\uc791\uc77c",
        "\uc885\ub8cc\uc77c",
        "\ubaa9\ud45c\uc77c",
        "\uc608\uc0b0",
        "\ubcf4\uc720 \uae30\uc220",
        "\ubcf4\uc720 \ub3c4\uad6c",
        "\ucd5c\uc885 \uac80\uc218 \uc0c1\ud0dc",
        "[\ub2e4\uc74c \ud589\ub3d9]",
    )

    for line in edit.old_text.splitlines():
        cleaned = line.strip().lstrip("#*- ").strip()

        if any(
            cleaned.startswith(prefix)
            for prefix in protected_line_prefixes
        ):
            return True

    # These values/actions are created by workflow code rather than AI.
    code_owned_fragments = (
        "\ucd5c\uc885 \uac80\uc218 \ud1b5\uacfc",
        "\ucd5c\uc885 \uac80\uc218 \uc2e4\ud328",
        "\ucd5c\uc885 \uac80\uc218 \uc7ac\uc791\uc5c5 \ud544\uc694",
        "\uac80\uc218 \uae30\ub85d \uc5c6\uc74c",
        (
            "\ubbf8\ud655\uc778 \ud56d\ubaa9\uc740 \ubbf8\ud655\uc778 \uc0c1\ud0dc\ub85c "
            "\uc720\uc9c0\ud558\uace0, \ud604\uc7ac \ud655\uc778\ub41c \uc815\ubcf4 \ubc94\uc704\uc5d0\uc11c "
            "\ub2e4\uc74c \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
        ),
        (
            "\ud604\uc7ac \uac80\uc218\ub41c \uacb0\uacfc\ub97c \uae30\uc900\uc73c\ub85c "
            "\ub2e4\uc74c \ud504\ub85c\uc81d\ud2b8 \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
        ),
        (
            "\ud604\uc7ac \uac80\uc218 \uc0c1\ud0dc\ub97c \uae30\uc900\uc73c\ub85c "
            "\ud544\uc694\ud55c \ud6c4\uc18d \uc791\uc5c5\uc744 \uc9c4\ud589\ud569\ub2c8\ub2e4."
        ),
    )

    return any(
        fragment in old_normalized
        for fragment in code_owned_fragments
    )


def apply_report_edits(
    report_content: str,
    edits: tuple[ReportEdit, ...],
    project: dict,
) -> tuple[str, tuple[ReportEdit, ...]]:
    """Apply only exact, non-protected replacements.

    Returns the revised report and the operations that were actually applied.
    """

    result = report_content
    applied: list[ReportEdit] = []

    for edit in edits:
        if edit_touches_protected_fact(
            edit,
            project,
        ):
            continue

        # AI may only edit text that actually exists in the source report.
        if edit.old_text not in result:
            continue

        # Avoid ambiguous replacements when the same source fragment occurs
        # more than once. The AI must provide a more specific span instead.
        if result.count(edit.old_text) != 1:
            continue

        result = result.replace(
            edit.old_text,
            edit.new_text,
            1,
        )

        applied.append(edit)

    return result, tuple(applied)


REPORT_REVISION_JSON_INSTRUCTION = r"""
You edit an existing report according to the user's revision request.

Do NOT rewrite the whole report in your response.
Return exactly one valid JSON object and nothing else.

Schema:
{
  "edits": [
    {
      "old_text": "exact text copied from the existing report",
      "new_text": "replacement text"
    }
  ]
}

Rules:
- old_text MUST be copied exactly from the existing report.
- Change only content necessary for the user's request.
- Leave unrelated report content untouched.
- Never alter project name, field, goal, dates, budget, registered tools,
  or saved review status.
- Do not invent facts.
- If the user asks for a broad rewrite, return multiple targeted edits
  instead of one uncontrolled full-report rewrite.
- If nothing can safely be changed, return {"edits":[]}.
"""


__all__ = [
    "REPORT_REVISION_JSON_INSTRUCTION",
    "ReportEdit",
    "apply_report_edits",
    "edit_touches_protected_fact",
    "parse_report_revision_json",
]
