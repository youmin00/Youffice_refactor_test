"""Safe AI classifier for exact project-report revisions."""

import logging
from collections.abc import Callable
from typing import Any

from conversation.ollama_client import MODEL_NAME, optimized_chat
from workflow.report_revision import (
    REPORT_REVISION_JSON_INSTRUCTION,
    ReportEdit,
    parse_report_revision_json,
)


logger = logging.getLogger(__name__)


STRICT_REVISION_RETRY_INSTRUCTION = """
The previous revision response could not be parsed.

Return exactly ONE valid JSON object and nothing else.
Do not use Markdown fences.

Schema:
{
  "edits": [
    {
      "old_text": "exact text copied from the existing report",
      "new_text": "replacement text"
    }
  ]
}
"""


def classify_report_revision(
    report_content: str,
    revision_request: str,
    *,
    chat_func: Callable[..., Any] | None = None,
    model: str = MODEL_NAME,
) -> tuple[ReportEdit, ...]:
    """Create exact report edits, retry once, then return no edits safely."""

    caller = chat_func or optimized_chat

    context = (
        "[Existing report]\n"
        f"{report_content}\n\n"
        "[User revision request]\n"
        f"{revision_request}"
    )

    for attempt in range(2):
        retry_instruction = (
            ""
            if attempt == 0
            else STRICT_REVISION_RETRY_INSTRUCTION
        )

        try:
            response = caller(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            REPORT_REVISION_JSON_INSTRUCTION
                            + retry_instruction
                            + "\n/no_think"
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"{context}\n\n/no_think",
                    },
                ],
                think=False,
                stream=False,
                options={"temperature": 0.1},
            )

            return parse_report_revision_json(
                response.message.content
            )

        except Exception as error:
            logger.warning(
                "Report revision classifier attempt %s failed: %s",
                attempt + 1,
                error,
            )

    logger.error(
        "Report revision classifier failed twice; "
        "keeping the original report unchanged."
    )

    return ()


__all__ = [
    "classify_report_revision",
]
