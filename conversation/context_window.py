"""채팅 모델에 전달할 최근 대화 범위를 작게 유지하는 도구."""

from __future__ import annotations

from typing import Any


DEFAULT_MAX_MESSAGES = 8
DEFAULT_MAX_CHARACTERS = 6_000


def select_recent_model_messages(
    messages: list[dict[str, Any]],
    employee_id: str,
    *,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    max_characters: int = DEFAULT_MAX_CHARACTERS,
) -> list[dict[str, str]]:
    """현재 대화 상대와의 최근 문맥만 모델용 role/content 형태로 반환합니다.

    프로젝트의 장기 결정은 별도 기억 문맥으로 전달합니다. 따라서 오래된 채팅까지
    모두 붙여 컨텍스트 한도를 넘기는 대신, 가장 최근에 이어진 대화만 남깁니다.
    """

    if max_messages <= 0 or max_characters <= 0:
        return []

    selected: list[dict[str, str]] = []
    used_characters = 0

    for message in reversed(messages):
        role = str(message.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        if role == "assistant" and message.get("employee_id") != employee_id:
            continue

        content = str(message.get("content") or "").strip()
        if not content:
            continue
        if selected and used_characters + len(content) > max_characters:
            break

        selected.append({"role": role, "content": content})
        used_characters += len(content)
        if len(selected) >= max_messages:
            break

    selected.reverse()
    return selected
