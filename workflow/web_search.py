"""키 없이도 사용할 수 있는 읽기 전용 웹 원문 검색 도우미입니다."""

from __future__ import annotations

from typing import Any

from ddgs import DDGS


class FreeWebSearchError(RuntimeError):
    """무료 검색 서비스의 일시적 오류를 사용자에게 안전하게 전달합니다."""


def search_free_web(
    query: str,
    *,
    max_results: int = 3,
) -> list[dict[str, str]]:
    """DDGS 결과를 제목·주소·짧은 원문 요약만 가진 공통 형태로 정리합니다."""

    normalized_query = str(query or "").strip()
    if not normalized_query:
        raise ValueError("검색할 내용을 입력해주세요.")

    result_limit = max(1, min(int(max_results), 5))
    try:
        raw_results = DDGS(timeout=12).text(
            normalized_query,
            max_results=result_limit,
        )
    except Exception as error:
        raise FreeWebSearchError(
            "무료 웹 검색에 잠시 연결하지 못했습니다. 잠시 뒤 다시 시도해주세요."
        ) from error

    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in raw_results or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()[:300]
        url = str(item.get("href") or item.get("url") or "").strip()[:2000]
        content = str(item.get("body") or item.get("content") or "").strip()[:1200]
        if not title or not url.startswith(("https://", "http://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        results.append({"title": title, "url": url, "content": content})

    if not results:
        raise FreeWebSearchError(
            "관련된 공개 웹 자료를 찾지 못했습니다. 표현을 조금 바꿔 다시 시도해주세요."
        )
    return results
