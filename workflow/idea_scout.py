"""Automatic, evidence-aware research support for idea conversations."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from workflow.internet_research import TavilySearchError, search_tavily
from workflow.source_quality import is_non_content_url
from workflow.web_search import FreeWebSearchError, search_free_web


_EXPLORATION_SIGNALS = (
    "만들", "아이디어", "어떻게", "무엇", "어떤", "추천", "방법", "기능",
    "부품", "센서", "모터", "자동", "시스템", "로봇", "검색", "논문", "자료",
    "근거", "조사", "찾아",
)
_QUERY_STOP_WORDS = {
    "학생", "사용자", "프로젝트", "아이디어", "만들", "만들고", "싶어",
    "위해", "사용", "설계", "방식", "어떻게", "선택", "기준", "주의",
    "정보", "알려", "정리", "관련", "추천", "무엇", "어떤",
}
_TERM_ALIASES = {
    "거치대": ("monitor stand", "monitor mount", "display stand", "screen stand"),
    "화면": ("monitor", "display", "screen"),
    "컴퓨터": ("computer", "monitor", "display"),
    "시선": ("eye tracking", "gaze", "head pose", "eye position"),
    "눈": ("eye tracking", "gaze", "eye position"),
    "높이": ("height", "vertical", "lift", "linear actuator"),
    "높낮이": ("height", "vertical", "lift", "linear actuator"),
    "자동": ("automatic", "motorized", "automation"),
    "조절": ("adjust", "adjustment", "control", "actuator"),
    "모터": ("motor", "actuator", "servo", "stepper"),
    "카메라": ("camera", "computer vision", "webcam"),
    "센서": ("sensor", "distance sensor", "time of flight"),
}
_DIRECT_RELEVANCE_PHRASES = (
    "monitor stand", "monitor mount", "eye tracking", "head pose",
    "computer vision", "linear actuator", "time of flight sensor",
)
_TOPIC_CONCEPTS = {
    "mount": ("거치대", "stand", "mount", "holder"),
    "vision": ("시선", "눈", "eye tracking", "gaze", "head pose", "eye position"),
    "height_motion": ("높이", "높낮이", "lift", "vertical", "linear actuator"),
    "motor": ("모터", "motor", "actuator", "stepper", "servo"),
    "camera": ("카메라", "camera", "webcam", "computer vision"),
    "sensor": ("센서", "sensor", "distance sensor", "time of flight"),
}

# These sites are common search leads, but are not suitable as automatically
# verified evidence for a student's engineering decision.
_UNSUITABLE_SOURCE_HOSTS = (
    "instagram.com", "facebook.com", "tiktok.com", "pinterest.com",
    "fliphtml5.com", "youtube.com",
)
_ACADEMIC_SOURCE_HOSTS = (
    "arxiv.org", "doi.org", "ieeexplore.ieee.org", "dl.acm.org",
    "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov", "ntrs.nasa.gov",
    "dbpia.co.kr", "kci.go.kr", "scienceon.kisti.re.kr", "riss.kr", "kiss.kstudy.com",
    "koreascience.kr",
)
_DBPIA_DOMAIN = "dbpia.co.kr"
_ACADEMIC_FALLBACK_DOMAINS = (
    "kci.go.kr",
    "scienceon.kisti.re.kr",
    "riss.kr",
    "kiss.kstudy.com",
    "koreascience.kr",
)
_OFFICIAL_TECHNICAL_SOURCE_HOSTS = (
    "docs.arduino.cc", "arduino.cc", "raspberrypi.com", "sparkfun.com",
    "adafruit.com", "pololu.com", "orientalmotor.com", "linak.com",
    "thorlabs.com", "devicemart.co.kr", "patents.google.com",
)


@dataclass(frozen=True)
class IdeaScoutBrief:
    """Research memo passed to the model and the user-visible source list."""

    prompt_context: str
    sources: tuple[dict[str, str], ...] = ()
    web_used: bool = False
    error_message: str = ""
    source_provider: str = ""

    def source_markdown(self) -> str:
        if not self.sources:
            return ""
        provider = f" · {self.source_provider}" if self.source_provider else ""
        lines = ["", f"[열림·관련성 확인을 마친 참고 자료{provider}]"]
        for source in self.sources:
            label = f" · {source['source_type']}" if source.get("source_type") else ""
            lines.append(f"- [{source['title']}]({source['url']}){label}")
        lines.append(
            "  - 실제로 열리는지와 현재 질문과의 관련성을 확인한 공개 자료만 표시합니다. "
            "구매·제작 전에는 원문과 최신 사양을 다시 확인하세요."
        )
        return "\n".join(lines)


def should_auto_explore_idea(
    user_text: object,
    *,
    is_manager_chat: bool,
    is_plan_request: bool,
) -> bool:
    """Search only for substantive Yuki idea conversations."""

    if not is_manager_chat or is_plan_request:
        return False
    normalized = re.sub(r"\s+", "", str(user_text or "")).lower()
    return len(normalized) >= 5 and any(signal in normalized for signal in _EXPLORATION_SIGNALS)


def _local_ideation_instruction() -> str:
    return """
[아이디어 탐색 모드]
지금은 문서 양식을 채우는 단계가 아닙니다. 사용자의 말을 다시 요약하지 말고,
실제로 가능한 선택지 2~3개를 제안하세요. 각 선택지마다 작동 방식, 장점, 초보자가
조심할 점, 다음에 확인할 한 가지를 쉬운 말로 설명하세요.

물리적으로 맞지 않는 센서 설명은 금지합니다. IR 거리 센서는 사람까지의 거리만
잴 뿐 시선 방향을 직접 알 수 없습니다. 거치대에 붙인 기울기 센서는 거치대의
기울기만 알 수 있고 사용자의 머리 기울기를 측정하지 못합니다. 카메라로 눈이나
머리 위치를 판단하려면 Arduino만으로는 부족하며 PC 또는 Raspberry Pi 같은 영상
처리 장치가 필요합니다.

움직이는 거치대라면 모터 이름만 말하지 말고 이동 방식(리드스크루/리니어 액추에이터),
끝단 스위치, 전원, 끼임 방지와 수동 정지 방법을 함께 확인하세요. 확인하지 않은
가격·사양·호환성은 사실처럼 말하지 마세요. 웹 조사 메모가 없으면 출처를 만들지 마세요.
"""


def build_idea_scout_query(project: dict[str, Any], user_text: object) -> str:
    """Build a concise query; excessive chat history causes poor web matches."""

    goal = str(project.get("goal") or "").strip()
    field = str(project.get("field") or "").strip()
    request = str(user_text or "").strip()
    return f"{field} {goal} {request} 구현 방법 설계 선택 기준 안전".strip()


def _read_tavily_api_key() -> str:
    """Read the current process or Windows user key without displaying it."""

    process_key = os.getenv("TAVILY_API_KEY", "").strip()
    if process_key:
        return process_key
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            stored_key, _ = winreg.QueryValueEx(key, "TAVILY_API_KEY")
    except (ImportError, OSError):
        return ""
    return str(stored_key or "").strip()


def _relevance_groups(query: str) -> list[tuple[str, ...]]:
    words = re.findall(r"[가-힣A-Za-z0-9]{2,}", query.lower())
    groups: list[tuple[str, ...]] = []
    for word in words:
        if word in _QUERY_STOP_WORDS:
            continue
        aliases = (word, *_TERM_ALIASES.get(word, ()))
        if aliases not in groups:
            groups.append(aliases)
    return groups[:12]


def _topic_groups(query: str) -> list[tuple[str, ...]]:
    """Extract the specific engineering concepts, including Korean suffix forms."""

    normalized = query.lower()
    groups: list[tuple[str, ...]] = []
    for aliases in _TOPIC_CONCEPTS.values():
        if any(alias in normalized for alias in aliases):
            groups.append(aliases)
    return groups


def _matched_topic_count(text: str, query: str) -> tuple[int, int]:
    groups = _topic_groups(query)
    normalized_text = text.lower()
    matched = sum(
        any(alias.lower() in normalized_text for alias in group)
        for group in groups
    )
    return matched, len(groups)


def _is_relevant_result(result: dict[str, Any], query: str) -> bool:
    text = " ".join(
        str(result.get(field) or "") for field in ("title", "url", "content", "body")
    ).lower()
    if not text:
        return False
    matched_groups, available_groups = _matched_topic_count(text, query)
    if available_groups == 0:
        lexical_groups = _relevance_groups(query)
        matched_groups = sum(
            any(alias.lower() in text for alias in group)
            for group in lexical_groups
        )
        available_groups = len(lexical_groups)
    # A multi-condition request (for example, monitor stand + eye position +
    # height movement) must match at least two independent conditions.  This
    # stops a page that merely mentions one fashionable keyword from passing.
    required_matches = 2 if available_groups >= 3 else 1
    return matched_groups >= required_matches


def _has_unsuitable_host(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(host == domain or host.endswith(f".{domain}") for domain in _UNSUITABLE_SOURCE_HOSTS)


def _source_type(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if any(host == domain or host.endswith(f".{domain}") for domain in _ACADEMIC_SOURCE_HOSTS):
        return "학술·연구 자료"
    if any(host == domain or host.endswith(f".{domain}") for domain in _OFFICIAL_TECHNICAL_SOURCE_HOSTS):
        return "공식 기술·제품 자료"
    return "제작 참고 자료"


def _source_rank(result: dict[str, Any]) -> tuple[int, float]:
    label = _source_type(str(result.get("url") or ""))
    quality = {"학술·연구 자료": 3, "공식 기술·제품 자료": 2, "제작 참고 자료": 1}[label]
    try:
        score = float(result.get("score") or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    return quality, score


def _page_text_is_relevant(
    page_sample: bytes,
    content_type: str,
    result: dict[str, Any],
    query: str,
) -> bool:
    """Check page text as well as the search engine's title/snippet."""

    if "pdf" in content_type:
        # PDF text needs a dedicated extractor.  Its title/snippet has already
        # passed the strict topic check, so only verify that this is a live PDF.
        return True
    decoded = page_sample.decode("utf-8", errors="ignore")
    if not decoded:
        return False
    visible_text = re.sub(r"<[^>]+>", " ", decoded)
    page_result = {
        # Do not trust the search result's title or snippet a second time.
        # This decision is deliberately based on the retrieved page itself.
        "title": "",
        "url": "",
        "content": visible_text,
    }
    return _is_relevant_result(page_result, query)


def _verify_source_page(
    result: dict[str, Any],
    query: str,
    *,
    opener: Any = urlopen,
) -> dict[str, Any] | None:
    """Return only publicly reachable HTML/PDF/JSON source pages.

    The check reads only a small sample and never stores page content.  It
    prevents stale search results, 404 pages, social posts, and image-only
    links from being presented as verified project references.
    """

    original_url = str(result.get("url") or result.get("href") or "").strip()
    if (
        not original_url.startswith(("https://", "http://"))
        or _has_unsuitable_host(original_url)
        or is_non_content_url(original_url)
    ):
        return None
    request = Request(
        original_url,
        headers={"User-Agent": "YOUFFICE/1.0 (reference check)"},
        method="GET",
    )
    try:
        with opener(request, timeout=7) as response:
            status = getattr(response, "status", None)
            if status is None and hasattr(response, "getcode"):
                status = response.getcode()
            if status is not None and not 200 <= int(status) < 300:
                return None
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if content_type and not (
                content_type.startswith("text/") or "pdf" in content_type or "json" in content_type
            ):
                return None
            page_sample = response.read(16384)
            if not page_sample:
                return None
            resolved_url = str(response.geturl() or original_url).strip()
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return None

    if (
        not resolved_url.startswith(("https://", "http://"))
        or _has_unsuitable_host(resolved_url)
        or is_non_content_url(resolved_url)
    ):
        return None
    if not _page_text_is_relevant(page_sample, content_type, result, query):
        return None
    return {**result, "url": resolved_url, "source_type": _source_type(resolved_url)}


def _verified_relevant_results(
    results: list[dict[str, Any]], query: str, *, opener: Any = urlopen
) -> list[dict[str, Any]]:
    candidates = [
        result for result in results if isinstance(result, dict) and _is_relevant_result(result, query)
    ]
    candidates.sort(key=_source_rank, reverse=True)
    verified: list[dict[str, Any]] = []
    for candidate in candidates[:5]:
        checked = _verify_source_page(candidate, query, opener=opener)
        if checked is not None:
            verified.append(checked)
        if len(verified) == 3:
            break
    trusted = [
        result
        for result in verified
        if result.get("source_type") != "제작 참고 자료"
    ]
    return trusted or verified


def _search_academic_idea_sources(
    query: str,
    api_key: str,
    *,
    searcher: Any = search_tavily,
    verifier: Any = _verified_relevant_results,
) -> tuple[list[dict[str, Any]], str, str]:
    """Find verifiable papers, using DBpia before alternate academic indexes."""

    academic_query = f"{query} 논문 연구"
    attempts = (
        ("DBpia", [_DBPIA_DOMAIN]),
        ("대체 학술 색인 (KCI · ScienceON · RISS 등)", list(_ACADEMIC_FALLBACK_DOMAINS)),
    )
    errors: list[str] = []
    for provider, domains in attempts:
        try:
            response = searcher(
                academic_query,
                api_key,
                max_results=4,
                include_domains=domains,
            )
        except (ValueError, TavilySearchError) as error:
            errors.append(str(error))
            continue
        results = verifier(list(response.get("results") or []), academic_query)
        if results:
            return results, provider, ""
        errors.append(f"{provider}에서 열림·관련성 확인을 통과한 논문이 없습니다.")

    return [], "", errors[-1] if errors else "학술 자료를 찾지 못했습니다."


def _search_free_academic_idea_sources(
    query: str,
    *,
    searcher: Any = search_free_web,
    verifier: Any = _verified_relevant_results,
) -> tuple[list[dict[str, Any]], str, str]:
    """Use the key-free search path with the same DBpia-first policy."""

    academic_query = f"{query} 논문 연구"
    alternate_sites = " OR ".join(
        f"site:{domain}" for domain in _ACADEMIC_FALLBACK_DOMAINS
    )
    attempts = (
        ("DBpia", f"site:{_DBPIA_DOMAIN} {academic_query}"),
        ("대체 학술 색인 (KCI · ScienceON · RISS 등)", f"({alternate_sites}) {academic_query}"),
    )
    errors: list[str] = []
    for provider, search_query in attempts:
        try:
            results = verifier(searcher(search_query, max_results=4), academic_query)
        except (ValueError, FreeWebSearchError) as error:
            errors.append(str(error))
            continue
        if results:
            return results, provider, ""
        errors.append(f"{provider}에서 열림·관련성 확인을 통과한 논문이 없습니다.")

    return [], "", errors[-1] if errors else "학술 자료를 찾지 못했습니다."


def _merge_idea_sources(
    academic_results: list[dict[str, Any]], web_results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Keep the answer compact while showing both academic and web evidence."""

    merged: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    def add_from(group: list[dict[str, Any]], limit: int) -> None:
        for result in group:
            if len(merged) >= limit:
                return
            url = str(result.get("url") or result.get("href") or "").strip()
            if not url or url in seen_urls:
                continue
            merged.append(result)
            seen_urls.add(url)

    # Reserve the first two slots for one paper and one web reference when both
    # are available; then fill the final slot by academic quality first.
    add_from(academic_results, 1)
    add_from(web_results, 2)
    for group in (academic_results, web_results):
        for result in group:
            url = str(result.get("url") or result.get("href") or "").strip()
            if not url or url in seen_urls:
                continue
            merged.append(result)
            seen_urls.add(url)
            if len(merged) == 3:
                return merged

    return merged


def _search_idea_sources(query: str) -> tuple[list[dict[str, Any]], str, str]:
    """Combine verified web references with DBpia-first academic references."""

    api_key = _read_tavily_api_key()
    tavily_error = ""
    web_results: list[dict[str, Any]] = []
    web_provider = ""
    academic_results: list[dict[str, Any]] = []
    academic_provider = ""
    academic_error = ""
    if api_key:
        try:
            response = search_tavily(query, api_key, max_results=5)
            web_results = _verified_relevant_results(list(response.get("results") or []), query)
            if web_results:
                web_provider = "Tavily 웹 검색"
            else:
                tavily_error = "Tavily 후보 중 실제로 열리고 현재 질문과 맞는 자료가 없었습니다."
        except (ValueError, TavilySearchError) as error:
            tavily_error = str(error)

        academic_results, academic_provider, academic_error = _search_academic_idea_sources(
            query,
            api_key,
        )

    if not academic_results:
        academic_results, academic_provider, free_academic_error = _search_free_academic_idea_sources(
            query,
        )
        if not academic_error:
            academic_error = free_academic_error

    if not web_results:
        try:
            web_results = _verified_relevant_results(search_free_web(query, max_results=5), query)
            if web_results:
                web_provider = "무료 웹 검색"
        except (ValueError, FreeWebSearchError) as error:
            if not tavily_error:
                tavily_error = str(error)

    combined = _merge_idea_sources(academic_results, web_results)
    providers = [provider for provider in (academic_provider, web_provider) if provider]
    if combined:
        return combined, " · ".join(providers), ""

    return [], "", academic_error or tavily_error or (
        "현재 질문에 맞고 실제로 열리는 공개 자료를 찾지 못했습니다."
    )


def collect_idea_scout_brief(project: dict[str, Any], user_text: object) -> IdeaScoutBrief:
    """Collect only verified source snippets and add them to the model context."""

    base_instruction = _local_ideation_instruction()
    raw_results, provider, error_message = _search_idea_sources(
        build_idea_scout_query(project, user_text)
    )
    if not raw_results:
        return IdeaScoutBrief(prompt_context=base_instruction, error_message=error_message)

    sources: list[dict[str, str]] = []
    source_lines: list[str] = []
    for result in raw_results:
        title = str(result.get("title") or "").strip()
        url = str(result.get("url") or result.get("href") or "").strip()
        content = str(result.get("content") or result.get("body") or "").strip()
        if not title or not url.startswith(("https://", "http://")):
            continue
        source_type = str(result.get("source_type") or "제작 참고 자료")
        sources.append({"title": title, "url": url, "source_type": source_type})
        source_lines.append(f"- {title} [{source_type}]: {content[:700]} (원문: {url})")

    if not source_lines:
        return IdeaScoutBrief(prompt_context=base_instruction, error_message="확인 가능한 참고 자료가 없습니다.")

    return IdeaScoutBrief(
        prompt_context=(
            base_instruction
            + "\n[자동 웹·논문 조사 메모]\n"
            + "\n".join(source_lines)
            + "\n위 메모는 실제로 열리는 관련 자료의 검색 요약입니다. 메모에 없는 수치·사양·사실은 만들지 말고, "
            "선택 기준을 설명할 때만 사용하세요.\n"
        ),
        sources=tuple(sources),
        web_used=True,
        source_provider=provider,
    )
