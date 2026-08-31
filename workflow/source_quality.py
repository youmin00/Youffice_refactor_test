"""Shared guards for reference URLs shown in AI-generated answers."""

from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import parse_qs, urlparse


_URL_PATTERN = re.compile(r"https?://[^\s<>\"'\]\)]+", re.IGNORECASE)
_MARKDOWN_LINK_PATTERN = re.compile(
    r"\[([^\]]+)\]\((https?://[^\s<>\"'\)]+)\)",
    re.IGNORECASE,
)
_NON_CONTENT_PATHS = {
    "",
    "/",
    "/home",
    "/index",
    "/index.html",
    "/ko",
    "/ko/",
    "/en",
    "/en/",
}
_SEARCH_PATH_SUFFIXES = (
    "/search",
    "/search/",
    "/search-results",
    "/search-results/",
)
_PROFILE_HOSTS = {"github.com", "www.github.com"}


def normalize_reference_url(url: object) -> str:
    """Normalize only the safe comparison surface without rewriting the link."""

    return str(url or "").strip().rstrip(".,;:!?/)").casefold()


def is_non_content_url(url: object) -> bool:
    """Reject site homepages and generic search-result pages."""

    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return True
    path = parsed.path.casefold()
    if path in _NON_CONTENT_PATHS:
        return True
    if path.endswith(_SEARCH_PATH_SUFFIXES):
        return True
    path_parts = [part for part in path.split("/") if part]
    if parsed.netloc.casefold() in _PROFILE_HOSTS and len(path_parts) == 1:
        return True
    query_keys = {key.casefold() for key in parse_qs(parsed.query)}
    if path.rstrip("/").endswith(("/find", "/results")) and query_keys & {
        "q",
        "query",
        "keyword",
        "search",
    }:
        return True
    return False


def verified_source_urls(sources: Iterable[dict]) -> set[str]:
    """Return URLs that the user has explicitly marked as verified."""

    return {
        normalize_reference_url(source.get("url"))
        for source in sources
        if source.get("verification_status") == "verified"
        and str(source.get("url") or "").strip()
    }


def verified_urls_from_source_context(source_context: object) -> set[str]:
    """Read verified registered URLs from the source context given to workers."""

    urls: set[str] = set()
    for line in str(source_context or "").splitlines():
        if "상태: 확인됨" not in line:
            continue
        for match in _URL_PATTERN.findall(line):
            urls.add(normalize_reference_url(match))
    return urls


def reference_urls_in_text(text: object) -> set[str]:
    """Return normalized URLs already present in a trusted upstream result."""

    return {
        normalize_reference_url(match)
        for match in _URL_PATTERN.findall(str(text or ""))
    }


def sanitize_unverified_links(text: object, allowed_urls: Iterable[str] = ()) -> str:
    """Remove links invented by a model while retaining the surrounding claim."""

    answer = str(text or "")
    allowed = {normalize_reference_url(url) for url in allowed_urls if str(url or "").strip()}

    def replace_markdown(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if normalize_reference_url(url) in allowed:
            return match.group(0)
        return f"{label} (검증되지 않은 외부 링크 제거)"

    answer = _MARKDOWN_LINK_PATTERN.sub(replace_markdown, answer)

    def replace_plain(match: re.Match[str]) -> str:
        url = match.group(0)
        if normalize_reference_url(url) in allowed:
            return url
        return "[검증되지 않은 외부 링크 제거]"

    return _URL_PATTERN.sub(replace_plain, answer)
