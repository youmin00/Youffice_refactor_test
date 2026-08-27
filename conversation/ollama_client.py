"""YOUFFICE의 Ollama 모델 호출 설정과 공통 함수."""

from dataclasses import dataclass

from ollama import RequestError, ResponseError, chat


MODEL_NAME = "qwen3:8b"

ANSWER_PREFILL_MODELS = {
    "qwen3:4b",
}

OLLAMA_RESPONSE_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.8,
    "top_k": 20,
    "num_predict": 1200,
    "num_ctx": 8192,
}


@dataclass(frozen=True)
class OllamaFailure:
    """사용자 안내에 쓸 수 있는 Ollama 오류 분류 결과입니다."""

    category: str
    message: str


class OllamaResponseFormatError(ValueError):
    """모델 응답이 YOUFFICE가 요구하는 형식을 충족하지 못한 경우입니다."""


_CONNECTION_ERROR_MARKERS = (
    "connection refused",
    "connection error",
    "connecterror",
    "all connection attempts failed",
    "failed to establish",
    "network is unreachable",
    "host is down",
    "service unavailable",
)

_TIMEOUT_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "deadline exceeded",
)


def describe_ollama_failure(error: BaseException) -> OllamaFailure | None:
    """연결·시간 초과·응답 형식 오류를 화면용 문구로 분리합니다."""

    error_text = str(getattr(error, "error", error) or "").lower()

    if isinstance(error, OllamaResponseFormatError):
        return OllamaFailure(
            "format",
            "AI 응답 형식을 확인하지 못했습니다. "
            "자동 완료 처리하지 않았습니다. 다시 시도해주세요.",
        )

    if isinstance(error, TimeoutError) or any(
        marker in error_text for marker in _TIMEOUT_ERROR_MARKERS
    ):
        return OllamaFailure(
            "timeout",
            "Ollama 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.",
        )

    if isinstance(error, (RequestError, ConnectionError)) or any(
        marker in error_text for marker in _CONNECTION_ERROR_MARKERS
    ):
        return OllamaFailure(
            "connection",
            "Ollama 연결에 실패했습니다. "
            "Ollama가 실행 중인지 확인한 뒤 다시 시도해주세요.",
        )

    if isinstance(error, ResponseError):
        return OllamaFailure(
            "request",
            "Ollama 요청을 처리하지 못했습니다. "
            "선택한 모델과 Ollama 상태를 확인한 뒤 다시 시도해주세요.",
        )

    return None


def optimized_chat(*args, **kwargs):
    """모델별 사고 출력 방식에 맞춰 Ollama 응답을 생성합니다."""

    answer_prefix = kwargs.pop("answer_prefix", None)
    selected_model = str(kwargs.get("model") or MODEL_NAME)

    use_answer_prefill = (
        answer_prefix is not None
        and selected_model in ANSWER_PREFILL_MODELS
    )

    if use_answer_prefill:
        messages = list(kwargs.get("messages", []))

        if not messages:
            raise ValueError(
                "answer_prefix를 사용할 때는 messages가 필요합니다."
            )

        messages.append(
            {
                "role": "assistant",
                "content": answer_prefix,
            }
        )
        kwargs["messages"] = messages

    options = dict(OLLAMA_RESPONSE_OPTIONS)
    options.update(kwargs.pop("options", {}) or {})

    kwargs["options"] = options
    kwargs.setdefault("keep_alive", "30m")

    response = chat(*args, **kwargs)

    if use_answer_prefill:
        response.message.content = (
            answer_prefix
            + (response.message.content or "")
        )

    return response
