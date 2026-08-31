"""Regression checks for automatic web and academic idea references."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from workflow.idea_scout import (  # noqa: E402
    _merge_idea_sources,
    _search_academic_idea_sources,
    _search_free_academic_idea_sources,
    should_auto_explore_idea,
)


def run_regression() -> None:
    assert should_auto_explore_idea(
        "관련 논문 찾아줘", is_manager_chat=True, is_plan_request=False
    )
    assert not should_auto_explore_idea(
        "관련 논문 찾아줘", is_manager_chat=False, is_plan_request=False
    )

    attempts: list[list[str]] = []

    def fake_searcher(query, api_key, *, max_results, include_domains):
        attempts.append(include_domains)
        return {
            "results": [
                {
                    "title": "학술 색인 논문",
                    "url": "https://scienceon.kisti.re.kr/article",
                    "content": "시선 추적 거치대 연구",
                    "score": 0.9,
                }
            ]
        }

    def fake_verifier(results, query):
        if attempts[-1] == ["dbpia.co.kr"]:
            return []
        return [{**results[0], "source_type": "학술·연구 자료"}]

    academic, provider, error = _search_academic_idea_sources(
        "시선 추적 모니터 거치대 구현",
        "tvly-test-key",
        searcher=fake_searcher,
        verifier=fake_verifier,
    )
    assert attempts[0] == ["dbpia.co.kr"]
    assert "scienceon.kisti.re.kr" in attempts[1]
    assert provider.startswith("대체 학술 색인")
    assert not error
    assert academic[0]["source_type"] == "학술·연구 자료"

    free_attempts: list[str] = []

    def fake_free_searcher(query, *, max_results):
        free_attempts.append(query)
        return [{"url": "https://kci.go.kr/article"}]

    def fake_free_verifier(results, query):
        if "site:dbpia.co.kr" in free_attempts[-1]:
            return []
        return [{**results[0], "source_type": "학술·연구 자료"}]

    academic, provider, error = _search_free_academic_idea_sources(
        "시선 추적 모니터 거치대 구현",
        searcher=fake_free_searcher,
        verifier=fake_free_verifier,
    )
    assert "site:dbpia.co.kr" in free_attempts[0]
    assert "site:scienceon.kisti.re.kr" in free_attempts[1]
    assert provider.startswith("대체 학술 색인")
    assert not error
    assert academic[0]["url"] == "https://kci.go.kr/article"

    merged = _merge_idea_sources(
        [
            {"url": "https://papers.example/1"},
            {"url": "https://papers.example/2"},
        ],
        [
            {"url": "https://web.example/1"},
            {"url": "https://web.example/2"},
        ],
    )
    assert [result["url"] for result in merged] == [
        "https://papers.example/1",
        "https://web.example/1",
        "https://papers.example/2",
    ]


if __name__ == "__main__":
    run_regression()
    print("IDEA_SCOUT_REGRESSION_OK")
