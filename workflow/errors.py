"""업무 단계에서 공통으로 사용하는 오류 표시 도구입니다."""

from conversation.ollama_client import describe_ollama_failure


def workflow_error_detail(stage: str, error: BaseException) -> str:
    """분류 가능한 Ollama 오류는 사용자용 문구로, 나머지는 원인과 함께 표시합니다."""

    failure = describe_ollama_failure(error)
    if failure is not None:
        return f"{stage}: {failure.message}"
    return f"{stage} 오류: {type(error).__name__}: {error}"
