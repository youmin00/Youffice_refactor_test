"""사용자가 요청했을 때만 Gemini·Claude의 교차 검토를 호출합니다."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib import error, parse, request


GEMINI_KEY_ENV = "GEMINI_API_KEY"
GEMINI_MODEL_ENV = "YOUFFICE_GEMINI_MODEL"
CLAUDE_KEY_ENV = "ANTHROPIC_API_KEY"
CLAUDE_MODEL_ENV = "YOUFFICE_CLAUDE_MODEL"
_TIMEOUT_SECONDS = 45


class ExternalReviewError(RuntimeError):
    """외부 검토를 안전하게 화면에 알리기 위한 오류입니다."""


def external_review_status() -> dict[str, str | bool]:
    """비밀값을 노출하지 않고 외부 검토 준비 상태만 반환합니다."""

    missing: list[str] = []
    if not os.getenv(GEMINI_KEY_ENV):
        missing.append(GEMINI_KEY_ENV)
    if not os.getenv(GEMINI_MODEL_ENV):
        missing.append(GEMINI_MODEL_ENV)
    if not os.getenv(CLAUDE_KEY_ENV):
        missing.append(CLAUDE_KEY_ENV)
    if not os.getenv(CLAUDE_MODEL_ENV):
        missing.append(CLAUDE_MODEL_ENV)
    return {
        "ready": not missing,
        "message": (
            "Gemini와 Claude 교차 검토 준비 완료"
            if not missing
            else "설정 필요: " + ", ".join(missing)
        ),
    }


def _post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ExternalReviewError(f"외부 AI 요청 오류({exc.code}): {detail}") from exc
    except error.URLError as exc:
        raise ExternalReviewError("외부 AI 서버에 연결하지 못했습니다.") from exc


def _json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match is None:
            raise ExternalReviewError("Gemini가 조건 정리 형식으로 응답하지 않았습니다.")
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise ExternalReviewError("Gemini 조건 정리를 읽지 못했습니다.") from exc
    if not isinstance(value, dict):
        raise ExternalReviewError("Gemini 조건 정리 형식이 올바르지 않습니다.")
    return value


def _project_text(project: dict[str, Any], recent_messages: list[dict[str, Any]]) -> str:
    conversation = "\n".join(
        f"{'학생' if message.get('role') == 'user' else '유키'}: {str(message.get('content') or '')[:900]}"
        for message in recent_messages[-10:]
        if message.get("role") in {"user", "assistant"}
    )
    return (
        f"프로젝트명: {project.get('name') or '미정'}\n"
        f"분야: {project.get('field') or '미정'}\n"
        f"목표: {project.get('goal') or '미정'}\n"
        f"최근 대화:\n{conversation or '대화 없음'}"
    )


def _gemini_conditions(project_text: str) -> dict[str, Any]:
    key = os.environ[GEMINI_KEY_ENV]
    model = os.environ[GEMINI_MODEL_ENV]
    prompt = (
        "너는 학생 프로젝트의 조건을 정리하는 분석가다. 아래 기록만 근거로 삼고, "
        "가격·호환성·기술 사실을 지어내지 마라. Markdown 없이 다음 JSON만 반환한다. "
        '{"confirmed": ["확정된 것"], "proposals": ["제안"], '
        '"unknowns": ["아직 모르는 것"], "checks": ["구매·안전·호환 확인 항목"], '
        '"next_question": "학생에게 물을 질문 하나"}\n\n'
        + project_text
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{parse.quote(model, safe='')}:generateContent?key={parse.quote(key, safe='')}"
    )
    response = _post_json(
        url,
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        },
        {},
    )
    try:
        text = response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalReviewError("Gemini 응답에서 조건 정리를 찾지 못했습니다.") from exc
    return _json_object(str(text))


def _claude_review(project_text: str, conditions: dict[str, Any]) -> str:
    key = os.environ[CLAUDE_KEY_ENV]
    model = os.environ[CLAUDE_MODEL_ENV]
    prompt = (
        "너는 학생 프로젝트의 독립 검수자다. 아래 기록과 Gemini 조건 정리를 보고 "
        "계획의 허점, 과한 가정, 안전·호환성 확인 항목만 짧게 검토해라. "
        "확인되지 않은 사실은 반드시 '확인 필요'라고 표시하고, 학생이 지금 정할 한 가지를 마지막에 적어라.\n\n"
        f"[프로젝트 기록]\n{project_text}\n\n[Gemini 조건 정리]\n"
        f"{json.dumps(conditions, ensure_ascii=False)}"
    )
    response = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "model": model,
            "max_tokens": 700,
            "system": "한국어로 간결하고 근거 중심으로 답한다. 사고 과정을 노출하지 않는다.",
            "messages": [{"role": "user", "content": prompt}],
        },
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    try:
        return str(response["content"][0]["text"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ExternalReviewError("Claude 응답에서 검토 의견을 찾지 못했습니다.") from exc


def _lines(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()][:4]
    return []


def run_external_cross_review(project: dict[str, Any], recent_messages: list[dict[str, Any]]) -> str:
    """Gemini 조건 분석 뒤 Claude 독립 검수를 수행하고 유키용 요약을 반환합니다."""

    status = external_review_status()
    if not status["ready"]:
        raise ExternalReviewError(str(status["message"]))
    project_text = _project_text(project, recent_messages)
    conditions = _gemini_conditions(project_text)
    claude_review = _claude_review(project_text, conditions)
    confirmed = _lines(conditions.get("confirmed"))
    unknowns = _lines(conditions.get("unknowns"))
    checks = _lines(conditions.get("checks"))
    next_question = str(conditions.get("next_question") or "다음에 정할 조건을 하나 골라보세요.").strip()
    confirmed_lines = [f"- {item}" for item in confirmed] or ["- 아직 확정된 내용이 없어요."]
    check_lines = [f"- {item}" for item in (unknowns + checks)[:5]] or [
        "- 현재 기록에서 확인할 항목을 찾지 못했어요."
    ]
    return "\n".join(
        [
            "[외부 AI 교차 검토]",
            "Gemini는 대화에서 조건을 정리했고, Claude는 그 조건을 독립적으로 검토했어요.",
            "[현재 확인된 것]",
            *confirmed_lines,
            "[먼저 확인할 것]",
            *check_lines,
            "[Claude의 검토]",
            claude_review[:1800] or "- 검토 의견을 완성하지 못했습니다.",
            "[유키와 다음에 정할 한 가지]",
            f"- {next_question}",
        ]
    )
