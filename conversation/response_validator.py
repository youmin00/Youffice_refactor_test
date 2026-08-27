"""YOUFFICE AI 응답 검증 함수."""

import re


def is_korean_answer(text: str | None) -> bool:
    """최종 화면에 표시할 만큼 한국어 중심 응답인지 확인합니다."""

    if not text:
        return False

    hangul_count = sum(
        "가" <= character <= "힣"
        for character in text
    )

    latin_count = sum(
        character.isascii() and character.isalpha()
        for character in text
    )

    return hangul_count >= 5 and (
        latin_count == 0
        or hangul_count / latin_count >= 0.2
    )


def remove_thinking(text: str | None) -> str:
    """Qwen 응답에서 사고 과정은 버리고 최종 답변만 반환합니다."""

    if not text:
        return ""

    cleaned = text.strip()

    cleaned = re.sub(
        r"<think\b[^>]*>.*?</think\s*>\s*",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )

    closing_tags = list(
        re.finditer(
            r"</think\s*>",
            cleaned,
            flags=re.IGNORECASE,
        )
    )

    if closing_tags:
        cleaned = cleaned[closing_tags[-1].end():]

    opening_tag = re.search(
        r"<think\b[^>]*>",
        cleaned,
        flags=re.IGNORECASE,
    )

    if opening_tag:
        cleaned = cleaned[:opening_tag.start()]

    cleaned = re.sub(
        r"</?think\b[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    cleaned = cleaned.replace(
        "[다음 직员工 전달]",
        "[다음 직원 전달]",
    )

    thinking_prefix = re.match(
        r"(?:let me (?:think|reason|analy[sz]e)|"
        r"possible response\b|we need to\b|"
        r"the user (?:wants|asked)\b|"
        r"(?:first|wait),?\s+i\b|"
        r"okay,?\s+(?:let(?:'s| us)|i(?:'ll| will)|the user|we need)\b)",
        cleaned,
        flags=re.IGNORECASE,
    )

    if thinking_prefix:
        final_markers = list(
            re.finditer(
                r"^\s*(?:final answer|최종 답변)\s*[:：]\s*",
                cleaned,
                flags=re.IGNORECASE | re.MULTILINE,
            )
        )

        if not final_markers:
            return ""

        cleaned = cleaned[
            final_markers[-1].end():
        ].strip()

    return cleaned