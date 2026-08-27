"""외부 API를 실제 호출하지 않고 교차 검토 흐름을 검사합니다."""

from __future__ import annotations

import os

import workflow.external_review as review


def run() -> None:
    original_post = review._post_json
    original_environment = dict(os.environ)
    os.environ.update(
        {
            review.GEMINI_KEY_ENV: "test-gemini-key",
            review.GEMINI_MODEL_ENV: "test-gemini-model",
            review.CLAUDE_KEY_ENV: "test-claude-key",
            review.CLAUDE_MODEL_ENV: "test-claude-model",
        }
    )
    responses = [
        {"candidates": [{"content": {"parts": [{"text": '{"confirmed":["교실에서 사용"],"proposals":[],"unknowns":["전원 방식"],"checks":["센서 호환성"],"next_question":"전원은 어디에서 받을까요?"}'}]}}]},
        {"content": [{"text": "확인 필요: 센서와 전원 연결 조건을 먼저 확인하세요."}]},
    ]
    review._post_json = lambda *_args, **_kwargs: responses.pop(0)
    try:
        result = review.run_external_cross_review(
            {"name": "테스트", "field": "메이커", "goal": "교실 안전 알림"},
            [{"role": "user", "content": "센서를 써서 만들고 싶어"}],
        )
        assert "[외부 AI 교차 검토]" in result
        assert "교실에서 사용" in result
        assert "전원은 어디에서 받을까요?" in result
        assert review.external_review_status()["ready"]
    finally:
        review._post_json = original_post
        os.environ.clear()
        os.environ.update(original_environment)


if __name__ == "__main__":
    run()
    print("external review checks passed")
