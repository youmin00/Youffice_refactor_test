"""Safe orchestration for user-requested project report revisions."""

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any

from workflow.report_revision import (
    ReportEdit,
    apply_report_edits,
)
from workflow.report_revision_classifier import (
    classify_report_revision,
)


@dataclass(frozen=True)
class ReportRevisionResult:
    content: str
    proposed_edits: tuple[ReportEdit, ...]
    applied_edits: tuple[ReportEdit, ...]

    @property
    def changed(self) -> bool:
        return self.content != "" and bool(self.applied_edits)


def revise_report_safely(
    report_content: str,
    revision_request: str,
    project: dict,
    *,
    chat_func: Callable[..., Any] | None = None,
) -> ReportRevisionResult:
    """Revise only exact, non-protected spans of an existing report.

    If AI classification fails or every proposed edit is rejected,
    the original report is returned unchanged.
    """

    original = report_content or ""

    edits = classify_report_revision(
        original,
        revision_request,
        chat_func=chat_func,
    )

    revised, applied = apply_report_edits(
        original,
        edits,
        project,
    )

    if not applied:
        revised = original

    return ReportRevisionResult(
        content=revised,
        proposed_edits=edits,
        applied_edits=applied,
    )


__all__ = [
    "ReportRevisionResult",
    "revise_report_safely",
]
