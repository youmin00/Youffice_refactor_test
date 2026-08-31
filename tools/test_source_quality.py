"""Regression checks for relevance, content URLs, and model link guards."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflow.idea_scout import _is_relevant_result, _verify_source_page  # noqa: E402
from workflow.source_quality import (  # noqa: E402
    is_non_content_url,
    sanitize_unverified_links,
    verified_urls_from_source_context,
)


class _FakePage:
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url: str, body: str) -> None:
        self.url = url
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, size: int) -> bytes:
        return self.body.encode("utf-8")[:size]

    def geturl(self) -> str:
        return self.url


def run_regression() -> None:
    generic_query = "대학생 실시간 협업 도구 사용성"
    relevant_result = {
        "title": "대학생을 위한 실시간 협업 도구 사용성 연구",
        "url": "https://example.org/articles/collaboration-usability",
        "content": "팀 협업 도구의 사용성을 비교한 연구",
    }
    assert _is_relevant_result(relevant_result, generic_query)

    opened = []

    def fake_opener(request, timeout):
        opened.append(request.full_url)
        return _FakePage(
            request.full_url,
            "<html><body>대학생 팀의 실시간 협업 도구 사용성을 비교한 연구 본문</body></html>",
        )

    checked = _verify_source_page(relevant_result, generic_query, opener=fake_opener)
    assert checked is not None
    assert checked["url"].endswith("/articles/collaboration-usability")

    assert is_non_content_url("https://example.org/")
    assert is_non_content_url("https://example.org/search?q=collaboration")
    assert is_non_content_url("https://github.com/example-user")
    assert not is_non_content_url("https://github.com/example-user/useful-project")
    assert not is_non_content_url("https://example.org/articles/collaboration-usability")
    assert _verify_source_page(
        {**relevant_result, "url": "https://example.org/"},
        generic_query,
        opener=fake_opener,
    ) is None

    source_context = (
        "- 공식 사양 | 상태: 확인됨 | 주소: https://example.org/spec | 메모: 없음\n"
        "- 후보 자료 | 상태: 미확인 | 주소: https://wrong.example/home | 메모: 없음"
    )
    allowed = verified_urls_from_source_context(source_context)
    cleaned = sanitize_unverified_links(
        "[공식](https://example.org/spec)와 [가짜](https://wrong.example/home) "
        "그리고 https://invented.example/item",
        allowed,
    )
    assert "https://example.org/spec" in cleaned
    assert "wrong.example" not in cleaned
    assert "invented.example" not in cleaned
    assert cleaned.count("검증되지 않은 외부 링크 제거") == 2


if __name__ == "__main__":
    run_regression()
    print("SOURCE_QUALITY_REGRESSION_OK")
