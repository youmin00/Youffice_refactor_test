"""Safe structured-report classifier with one retry and deterministic fallback."""

import logging
from collections.abc import Callable
from typing import Any

from conversation.ollama_client import MODEL_NAME, optimized_chat
from workflow.structured_report import (
    STRUCTURED_REPORT_JSON_INSTRUCTION,
    StructuredReportAIData,
    parse_structured_report_json,
)


logger = logging.getLogger(__name__)


STRICT_RETRY_INSTRUCTION = """
The previous classifier response could not be parsed.
Return exactly ONE valid JSON object and nothing else.
Do not use markdown fences.
Use only these keys:
- proposals
- unverified
- limitations
Every value must be an array of strings.
"""


def _empty_structured_report_data() -> StructuredReportAIData:
    """Return the safe fallback when AI classification cannot be recovered."""

    return StructuredReportAIData(
        proposals=(),
        unverified=(),
        limitations=(),
    )


def classify_structured_report(
    context: str,
    *,
    chat_func: Callable[..., Any] | None = None,
    model: str = MODEL_NAME,
) -> StructuredReportAIData:
    """Classify report material, retry once, then fall back safely."""

    caller = chat_func or optimized_chat

    for attempt in range(2):
        retry_instruction = (
            ""
            if attempt == 0
            else STRICT_RETRY_INSTRUCTION
        )

        try:
            response = caller(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            STRUCTURED_REPORT_JSON_INSTRUCTION
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

            return parse_structured_report_json(
                response.message.content
            )

        except Exception as error:
            logger.warning(
                "Structured report classifier attempt %s failed: %s",
                attempt + 1,
                error,
            )

    logger.error(
        "Structured report classifier failed twice; "
        "using safe empty AI classification."
    )

    return _empty_structured_report_data()


__all__ = [
    "classify_structured_report",
]
