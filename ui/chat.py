"""YOUFFICE 프로젝트 대화 내용을 표시합니다."""

import base64
from functools import lru_cache
from pathlib import Path
import html
import re

import markdown as markdown_renderer
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = PROJECT_ROOT / "static"


EMPLOYEE_ASSIGNMENT_HEADER_PATTERN = re.compile(
    r"(?P<opening><li(?:\s+[^>]*)?>\s*(?:<p>\s*)?)"
    r"<strong>\s*(?P<name>[^<\n()]{1,40}?)\s*"
    r"\((?P<title>[^<\n()]{1,40}?)\)\s*[:：]?\s*</strong>\s*[:：]?",
    flags=re.IGNORECASE,
)
EMPLOYEE_ASSIGNMENT_LINE_PATTERN = re.compile(
    r"^\s*[-*•]?\s*(?:\*\*)?\s*"
    r"(?P<name>[^()\n:*：]{1,40}?)\s*"
    r"\((?P<title>[^()\n]{1,40}?)\)\s*[:：]?\s*(?:\*\*)?\s*$"
)
MARKDOWN_BULLET_PATTERN = re.compile(r"^\s*[-*•]\s*(?P<body>.+?)\s*$")
SECTION_MARKER_PATTERN = re.compile(r"^\s*\[[^\]\n]{1,40}\]\s*$")
CHOICE_TITLE_PATTERN = re.compile(r"^(?P<number>\d+)\.\s+(?P<title>.+?)\s*$")
DETAIL_LABEL_HTML_PATTERN = re.compile(
    r"(?P<opening><li(?:\s+[^>]*)?>\s*(?:<p>\s*)?)"
    r"<strong>\s*(?P<label>차이|추천 이유|확정된 것|제안|아직 모르는 것)\s*[:：]\s*</strong>",
    flags=re.IGNORECASE,
)
CHOICE_CARD_HTML_PATTERN = re.compile(
    r"(?P<heading><h3>\s*(?P<number>\d+)\.\s*.*?</h3>)"
    r"(?P<details>\s*<ul>.*?</ul>)",
    flags=re.DOTALL,
)
CAUTION_TEXT_HTML_PATTERN = re.compile(
    r"(?P<caution>단,\s*[^<]+)",
)

READABILITY_SECTION_LABELS = {
    "선택지와 차이, 추천 이유",
    "선택지와 차이 및 추천 이유",
    "확정된 것",
    "제안",
    "아직 모르는 것",
    "다음으로 정할 것",
}


def profile_avatar_content(employee: dict) -> str:
    """직원 카드와 채팅에서 함께 사용할 프로필 이미지를 반환합니다."""

    image_data = employee["image_data"]
    allowed_image_prefixes = (
        "data:image/jpeg;base64,",
        "data:image/png;base64,",
        "data:image/webp;base64,",
    )
    if isinstance(image_data, str) and image_data.startswith(allowed_image_prefixes):
        mime_extensions = {
            "data:image/jpeg;base64,": "jpg",
            "data:image/png;base64,": "png",
            "data:image/webp;base64,": "webp",
        }
        prefix = next(
            prefix for prefix in allowed_image_prefixes
            if image_data.startswith(prefix)
        )
        extension = mime_extensions[prefix]
        static_profile = STATIC_DIR / "profiles" / f"{employee['id']}.{extension}"
        image_source = image_data
        if static_profile.exists():
            image_source = (
                f"/app/static/profiles/{employee['id']}.{extension}"
                f"?v={static_profile.stat().st_mtime_ns}"
            )
        return (
            f'<img src="{html.escape(image_source, quote=True)}" '
            'alt="프로필 사진">'
        )
    return html.escape(str(employee["emoji"]))


@lru_cache(maxsize=256)
def chat_message_html(content: str) -> str:
    """신뢰할 수 없는 메시지를 이스케이프한 뒤 말풍선용 HTML로 변환합니다."""

    rendered = markdown_renderer.markdown(
        html.escape(format_readable_chat_markdown(content)),
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )
    return format_detail_label_html(rendered)


def format_readable_chat_markdown(content: str) -> str:
    """대화형 답변의 선택지·구역을 읽기 쉬운 Markdown 구조로 보정합니다."""

    formatted_lines: list[str] = []
    in_choice_section = False

    for line in str(content).splitlines():
        stripped = line.strip()
        plain_label = stripped.replace("**", "").strip().rstrip(":：").strip()

        if SECTION_MARKER_PATTERN.fullmatch(stripped):
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
            formatted_lines.extend((f"## {stripped}", ""))
            in_choice_section = False
            continue

        if plain_label in READABILITY_SECTION_LABELS:
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
            formatted_lines.extend((f"### {plain_label}", ""))
            in_choice_section = plain_label.startswith("선택지")
            continue

        choice_match = (
            CHOICE_TITLE_PATTERN.fullmatch(stripped)
            if in_choice_section
            else None
        )
        if choice_match:
            if formatted_lines and formatted_lines[-1] != "":
                formatted_lines.append("")
            formatted_lines.extend(
                (
                    f"### {choice_match.group('number')}. "
                    f"{choice_match.group('title')}",
                    "",
                )
            )
            continue

        formatted_lines.append(line)

    return "\n".join(formatted_lines)


def format_detail_label_html(rendered_content: str) -> str:
    """선택지 카드와 비교·추천·주의 정보에 의미 클래스를 부여합니다."""

    label_variants = {
        "차이": "difference",
        "추천 이유": "recommendation",
        "확정된 것": "confirmed",
        "제안": "proposal",
        "아직 모르는 것": "unknown",
    }

    def replace_detail_label(match: re.Match) -> str:
        label = match.group("label").strip()
        variant = label_variants.get(label, "default")
        opening = re.sub(
            r"<li(?=[\s>])",
            f'<li class="chat-detail-item chat-detail-item-{variant}"',
            match.group("opening"),
            count=1,
        )
        return (
            f'{opening}<span class="chat-detail-label '
            f'chat-detail-label-{variant}">{label}</span>'
        )

    rendered = DETAIL_LABEL_HTML_PATTERN.sub(replace_detail_label, rendered_content)

    def replace_choice_card(match: re.Match) -> str:
        return (
            '<section class="chat-choice-card">'
            f'{match.group("heading")}'
            f'<div class="chat-choice-details">{match.group("details")}</div>'
            "</section>"
        )

    rendered = CHOICE_CARD_HTML_PATTERN.sub(replace_choice_card, rendered)
    return CAUTION_TEXT_HTML_PATTERN.sub(
        r'<span class="chat-caution">\g<caution></span>',
        rendered,
    )


def normalize_employee_assignment_markdown(content: str) -> str:
    """형식이 느슨한 직원 배정 문장을 계층형 Markdown 목록으로 보정합니다."""

    normalized_lines: list[str] = []
    in_assignment_section = False
    has_employee_header = False

    for line in str(content).splitlines():
        stripped = line.strip()

        if stripped == "[직원별 배정]":
            if normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            normalized_lines.extend((stripped, ""))
            in_assignment_section = True
            has_employee_header = False
            continue

        if (
            in_assignment_section
            and stripped
            and SECTION_MARKER_PATTERN.fullmatch(stripped)
        ):
            if normalized_lines and normalized_lines[-1] != "":
                normalized_lines.append("")
            normalized_lines.append(stripped)
            in_assignment_section = False
            has_employee_header = False
            continue

        if in_assignment_section and stripped:
            header_match = EMPLOYEE_ASSIGNMENT_LINE_PATTERN.fullmatch(stripped)
            if header_match:
                name = header_match.group("name").strip()
                title = header_match.group("title").strip()
                normalized_lines.append(f"- **{name} ({title}):**")
                has_employee_header = True
                continue

            bullet_match = MARKDOWN_BULLET_PATTERN.fullmatch(stripped)
            if has_employee_header and bullet_match:
                normalized_lines.append(f"  - {bullet_match.group('body').strip()}")
                continue

        normalized_lines.append(line)

    return "\n".join(normalized_lines)


def manager_context_html(content: str) -> str:
    """팀장 배정안에서 직원 표제와 세부 업무를 시각적으로 분리합니다."""

    rendered_content = chat_message_html(
        normalize_employee_assignment_markdown(str(content))
    )

    def replace_employee_header(match: re.Match) -> str:
        opening = re.sub(
            r"<li(?=[\s>])",
            '<li class="employee-assignment-heading"',
            match.group("opening"),
            count=1,
        )
        name = match.group("name").strip()
        title = match.group("title").strip()
        return (
            f'{opening}<span class="employee-assignment-badge">'
            f'<span class="employee-assignment-name">{name}</span>'
            f'<span class="employee-assignment-role">{title}</span>'
            "</span>"
        )

    return EMPLOYEE_ASSIGNMENT_HEADER_PATTERN.sub(
        replace_employee_header,
        rendered_content,
    )


def render_manager_context(content: str) -> None:
    """직원 상세 화면에서도 팀장 배정안을 같은 가독성으로 표시합니다."""

    st.markdown(
        f'<div class="manager-context-body">{manager_context_html(content)}</div>',
        unsafe_allow_html=True,
    )


def render_assistant_copy_button(content: str, message_index: int) -> None:
    """Render a browser-side copy button for an AI employee response."""

    encoded_content = base64.b64encode(
        str(content).encode("utf-8")
    ).decode("ascii")
    button_id = f"assistant-message-copy-{message_index}"

    st.html(
        f"""
        <div style="display:flex; justify-content:flex-end; margin:-0.55rem 0 0.85rem;">
            <button
                id="{button_id}"
                type="button"
                style="background:#272a35; border:1px solid #464a59; border-radius:6px;
                       color:#f2f3f7; cursor:pointer; font-size:0.78rem; padding:0.32rem 0.72rem;"
            >복사</button>
        </div>
        <script>
        (() => {{
            const button = document.getElementById("{button_id}");
            if (!button) return;
            const encoded = "{encoded_content}";
            const content = new TextDecoder().decode(
                Uint8Array.from(atob(encoded), character => character.charCodeAt(0))
            );

            const copyWithFallback = () => {{
                const textarea = document.createElement("textarea");
                textarea.value = content;
                textarea.style.position = "fixed";
                textarea.style.opacity = "0";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                textarea.remove();
            }};

            button.addEventListener("click", async () => {{
                try {{
                    if (navigator.clipboard && window.isSecureContext) {{
                        await navigator.clipboard.writeText(content);
                    }} else {{
                        copyWithFallback();
                    }}
                    button.textContent = "복사됨";
                    window.setTimeout(() => {{ button.textContent = "복사"; }}, 1600);
                }} catch (_) {{
                    copyWithFallback();
                    button.textContent = "복사됨";
                    window.setTimeout(() => {{ button.textContent = "복사"; }}, 1600);
                }}
            }});
        }})();
        </script>
        """,
        unsafe_allow_javascript=True,
    )


def render_chat_message(
    message: dict,
    message_index: int,
    employee: dict,
) -> None:
    """메시지 하나를 높이 계산이 독립된 단일 말풍선으로 표시합니다."""

    rendered_content = manager_context_html(str(message["content"]))
    if message["role"] == "user":
        st.markdown(
            f"""
            <div class="messenger-row messenger-row-user" data-message-index="{message_index}">
                <div class="messenger-bubble messenger-bubble-user">
                    {rendered_content}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f"""
        <div class="messenger-row messenger-row-employee" data-message-index="{message_index}">
            <div class="messenger-avatar">{profile_avatar_content(employee)}</div>
            <div class="messenger-bubble messenger-bubble-employee">
                <div class="messenger-employee-name">{html.escape(str(employee["name"]))}</div>
                {rendered_content}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_assistant_copy_button(message["content"], message_index)
