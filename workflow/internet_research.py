"""Tavily 검색과 ChatGPT 검수 결과를 연결하는 인터넷 조사 도구입니다."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEVICEMART_DOMAIN = "devicemart.co.kr"
_SALE_PRICE_PATTERN = re.compile(
    r"(?:판매가|가격)\s*[:：]?\s*([1-9][0-9,]*)\s*원",
    re.IGNORECASE,
)


class TavilySearchError(RuntimeError):
    """Tavily 검색 요청을 안전한 사용자 메시지로 변환한 오류입니다."""


def _normalized_text(value: Any, *, limit: int = 4000) -> str:
    return str(value or "").strip()[:limit]


def search_tavily(
    query: str,
    api_key: str,
    *,
    max_results: int = 5,
    include_domains: list[str] | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Tavily에서 원문 후보만 검색하고 AI 생성 답변은 요청하지 않습니다."""

    normalized_query = query.strip()
    normalized_key = api_key.strip()
    if not normalized_query:
        raise ValueError("조사할 질문을 입력해주세요.")
    if not normalized_key:
        raise ValueError("Tavily API 키를 입력해주세요.")

    result_limit = max(1, min(int(max_results), 10))
    request_payload: dict[str, Any] = {
        "query": normalized_query,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
        "max_results": result_limit,
    }
    normalized_domains = [
        str(domain).strip().lower()
        for domain in (include_domains or [])
        if str(domain).strip()
    ]
    if normalized_domains:
        request_payload["include_domains"] = normalized_domains[:20]
    request_body = json.dumps(request_payload).encode("utf-8")
    request = Request(
        TAVILY_SEARCH_URL,
        data=request_body,
        headers={
            "Authorization": f"Bearer {normalized_key}",
            "Content-Type": "application/json",
            "User-Agent": "YOUFFICE/1.0",
        },
        method="POST",
    )

    try:
        with opener(request, timeout=25) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as error:
        if error.code == 401:
            message = "Tavily API 키가 올바른지 확인해주세요."
        elif error.code == 429:
            message = "Tavily 사용 한도에 도달했습니다. 잠시 후 사용량을 확인해주세요."
        else:
            message = f"Tavily 검색 요청이 실패했습니다(HTTP {error.code})."
        raise TavilySearchError(message) from error
    except (URLError, TimeoutError, OSError) as error:
        raise TavilySearchError(
            "Tavily에 연결하지 못했습니다. 인터넷 연결을 확인해주세요."
        ) from error

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as error:
        raise TavilySearchError("Tavily 응답을 읽을 수 없습니다.") from error

    normalized_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for raw_result in payload.get("results") or []:
        if not isinstance(raw_result, dict):
            continue
        url = _normalized_text(raw_result.get("url"), limit=2000)
        if not url.startswith(("http://", "https://")) or url in seen_urls:
            continue
        seen_urls.add(url)
        title = _normalized_text(raw_result.get("title"), limit=300)
        if not title:
            title = urlparse(url).netloc or "제목 없는 웹 자료"
        try:
            score = float(raw_result.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        normalized_results.append(
            {
                "title": title,
                "url": url,
                "content": _normalized_text(raw_result.get("content")),
                "score": max(0.0, min(score, 1.0)),
                "price_won": extract_price_won(raw_result.get("content")),
            }
        )

    if not normalized_results:
        raise TavilySearchError("관련 검색 결과를 찾지 못했습니다. 질문을 바꿔보세요.")

    return {
        "query": normalized_query,
        "results": normalized_results,
        "credits": int((payload.get("usage") or {}).get("credits") or 0),
        "queried_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def extract_price_won(text: Any) -> int | None:
    """검색 문맥에 명시된 첫 번째 판매가를 원 단위 정수로 읽습니다."""

    match = _SALE_PRICE_PATTERN.search(str(text or ""))
    if match is None:
        return None
    try:
        price = int(match.group(1).replace(",", ""))
    except ValueError:
        return None
    return price if price > 0 else None


def price_for_product(result: dict[str, Any], product_name: str) -> int | None:
    """상품명과 같은 검색 문맥 구간에 표시된 가격만 연결합니다."""

    normalized_name = product_name.strip().casefold()
    if not normalized_name:
        return None
    content = str(result.get("content") or "")
    content_index = content.casefold().find(normalized_name)
    if content_index >= 0:
        return extract_price_won(content[content_index : content_index + 1200])

    title = str(result.get("title") or "").casefold()
    if normalized_name in title or title in normalized_name:
        return extract_price_won(content)
    return None


def build_chatgpt_review_prompt(
    project: dict[str, Any],
    query: str,
    results: list[dict[str, Any]],
) -> str:
    """ChatGPT Plus에서 출처 비교·검수를 수행할 구조화 프롬프트를 만듭니다."""

    source_blocks = []
    for index, result in enumerate(results, start=1):
        source_blocks.append(
            "\n".join(
                [
                    f"[출처 {index}]",
                    f"제목: {result['title']}",
                    f"주소: {result['url']}",
                    f"검색 문맥: {result.get('content') or '제공되지 않음'}",
                ]
            )
        )

    return f"""당신은 프로젝트 자료 검수자입니다.
아래 Tavily 검색 결과만 근거로 사용하고, 검색 문맥에 없는 내용을 사실처럼 만들지 마세요.
각 주장에는 반드시 근거가 되는 출처 번호를 붙이세요. 서로 다른 출처가 충돌하면 확정하지 말고 conflicts에 넣으세요.

[프로젝트]
이름: {project.get('name') or '이름 없음'}
분야: {project.get('field') or '미입력'}
목표: {project.get('goal') or '미입력'}

[조사 질문]
{query.strip()}

[검색 결과]
{chr(10).join(source_blocks)}

반드시 설명 문장이나 Markdown 없이 아래 JSON 형식 하나만 출력하세요.
{{
  "summary": "전체 결과를 3문장 이내로 요약",
  "confirmed_candidates": [
    {{"content": "두 개 이상의 출처가 뒷받침하거나 원문이 명확한 사실 후보", "source_numbers": [1, 2]}}
  ],
  "conflicts": [
    {{"content": "출처끼리 충돌하는 내용", "source_numbers": [1, 3]}}
  ],
  "unverified": [
    {{"content": "근거가 부족하거나 추가 확인이 필요한 내용", "source_numbers": [2]}}
  ],
  "proposals": [
    {{"content": "사실이 아니라 프로젝트에 적용해볼 제안", "source_numbers": [1]}}
  ]
}}"""


def build_component_plan_prompt(
    project: dict[str, Any],
    need: str,
    *,
    budget: str = "",
    owned_parts: str = "",
    additional_answers: str = "",
) -> str:
    """상품 검색 전에 필요한 부품 종류와 조건을 정하는 GPT 프롬프트를 만듭니다."""

    return f"""당신은 전자·기계 프로젝트의 구매 전 설계 검토자입니다.
학생에게 특정 상품을 추천하거나 가격을 말하지 마세요. 먼저 시스템을 기능 블록으로 나누고 필요한 부품 종류와 최소 조건을 정하세요.
목표 속도, 하중, 크기, 사용 시간, 전원처럼 안전한 선정에 중요한 정보가 부족하면 status를 needs_input으로 하고 질문만 만드세요.

반드시 지킬 규칙:
1. 움직이거나 회전하는 장치라면 목표 속도와 필요한 토크를 함께 검토합니다.
2. 모터를 쓴다면 감속기 필요 여부를 반드시 판정합니다. 모르면 unknown으로 두고 질문합니다.
3. 모터 종류, 모터 전압, 정지 전류를 감당하는 드라이버, 전원 용량을 별도 블록으로 확인합니다.
4. 제어보드의 논리 전압, 센서 통신 방식, 커넥터, 축 지름, 장착 크기와 기구 부품을 확인합니다.
5. 각 블록에는 최소 요구조건, 서로 맞춰볼 호환 조건, 돈 낭비를 막는 과잉 사양 기준을 적습니다.
6. 중요한 수치가 없으면 억지로 ready를 만들지 마세요.
7. 이미 가진 부품도 사양이 확인되지 않으면 호환된다고 가정하지 마세요.

[프로젝트]
이름: {project.get('name') or '이름 없음'}
분야: {project.get('field') or '미입력'}
목표: {project.get('goal') or '미입력'}

[학생이 만들려는 것]
{need.strip()}

[희망 예산]
{budget.strip() or '정하지 않음'}

[이미 가지고 있는 부품]
{owned_parts.strip() or '없거나 모름'}

[추가 질문에 대한 학생 답변]
{additional_answers.strip() or '아직 없음'}

반드시 설명 문장이나 Markdown 없이 아래 JSON 형식 하나만 출력하세요.
{{
  "status": "needs_input 또는 ready",
  "summary": "현재 설계 판단 요약",
  "questions": [
    {{"id": "q1", "question": "학생에게 물어볼 쉬운 질문", "why": "이 정보가 필요한 이유"}}
  ],
  "gearbox_decision": {{
    "status": "required 또는 not_required 또는 unknown",
    "reason": "감속기 판단 근거"
  }},
  "components": [
    {{
      "id": "motor",
      "category": "부품 종류",
      "purpose": "이 부품이 하는 일",
      "required": true,
      "already_owned": false,
      "search_terms": ["디바이스마트에서 찾을 검색어"],
      "minimum_requirements": ["반드시 만족해야 할 최소 조건"],
      "compatibility_checks": ["다른 부품과 서로 맞춰볼 조건"],
      "overspec_avoidance": ["이 이상이면 불필요하게 비싸거나 과한 기준"]
    }}
  ],
  "global_checks": ["전체 조립 전에 확인할 전원·기구·통신 조건"]
}}"""


def _normalize_boolean(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {
        "true",
        "1",
        "yes",
        "필수",
        "보유",
    }


def parse_component_plan(text: str) -> dict[str, Any]:
    """GPT의 구매 전 부품 설계표를 안전한 구조로 정규화합니다."""

    payload = _find_json_object(text)
    status = str(payload.get("status") or "needs_input").strip().lower()
    if status not in {"needs_input", "ready"}:
        status = "needs_input"

    questions: list[dict[str, str]] = []
    raw_questions = payload.get("questions")
    if isinstance(raw_questions, list):
        for index, item in enumerate(raw_questions[:15], start=1):
            if not isinstance(item, dict):
                continue
            question = _normalized_text(item.get("question"), limit=1000)
            if question:
                questions.append(
                    {
                        "id": _normalized_text(item.get("id"), limit=100)
                        or f"q{index}",
                        "question": question,
                        "why": _normalized_text(item.get("why"), limit=1000),
                    }
                )

    components: list[dict[str, Any]] = []
    raw_components = payload.get("components")
    if isinstance(raw_components, list):
        for index, item in enumerate(raw_components[:20], start=1):
            if not isinstance(item, dict):
                continue
            category = _normalized_text(item.get("category"), limit=300)
            purpose = _normalized_text(item.get("purpose"), limit=1000)
            if not category or not purpose:
                continue
            components.append(
                {
                    "id": _normalized_text(item.get("id"), limit=100)
                    or f"component_{index}",
                    "category": category,
                    "purpose": purpose,
                    "required": _normalize_boolean(item.get("required")),
                    "already_owned": _normalize_boolean(
                        item.get("already_owned")
                    ),
                    "search_terms": _normalize_string_list(
                        item.get("search_terms")
                    ),
                    "minimum_requirements": _normalize_string_list(
                        item.get("minimum_requirements")
                    ),
                    "compatibility_checks": _normalize_string_list(
                        item.get("compatibility_checks")
                    ),
                    "overspec_avoidance": _normalize_string_list(
                        item.get("overspec_avoidance")
                    ),
                }
            )

    raw_gearbox = payload.get("gearbox_decision")
    gearbox_status = "unknown"
    gearbox_reason = ""
    if isinstance(raw_gearbox, dict):
        candidate_status = str(raw_gearbox.get("status") or "").strip().lower()
        if candidate_status in {"required", "not_required", "unknown"}:
            gearbox_status = candidate_status
        gearbox_reason = _normalized_text(raw_gearbox.get("reason"), limit=1500)

    return {
        "status": status,
        "summary": _normalized_text(payload.get("summary"), limit=3000),
        "questions": questions,
        "gearbox_decision": {
            "status": gearbox_status,
            "reason": gearbox_reason,
        },
        "components": components,
        "global_checks": _normalize_string_list(payload.get("global_checks")),
    }


_MOTION_TERMS = (
    "움직",
    "주행",
    "회전",
    "자동차",
    "로봇",
    "바퀴",
    "모터",
    "리니어",
)


def component_plan_issues(plan: dict[str, Any], need: str) -> list[str]:
    """불완전한 설계표가 상품 검색 단계로 넘어가는 것을 차단합니다."""

    issues: list[str] = []
    if plan.get("status") != "ready":
        issues.append("필수 정보가 부족해 부품 설계표가 아직 준비되지 않았습니다.")
    if plan.get("questions"):
        issues.append("답하지 않은 확인 질문이 남아 있습니다.")
    components = plan.get("components") or []
    if not components:
        issues.append("필요 부품 종류가 정리되지 않았습니다.")

    component_text = " ".join(
        f"{component.get('id', '')} {component.get('category', '')}".lower()
        for component in components
    )
    is_motion_project = any(term in need.lower() for term in _MOTION_TERMS)
    if is_motion_project:
        if "모터" not in component_text:
            issues.append("움직이는 프로젝트인데 모터 블록이 없습니다.")
        if not any(term in component_text for term in ("드라이버", "구동", "h-bridge", "h브리지")):
            issues.append("모터 전류를 담당할 드라이버 블록이 없습니다.")
        if not any(term in component_text for term in ("전원", "배터리", "어댑터")):
            issues.append("모터와 제어부에 전원을 공급할 블록이 없습니다.")
        gearbox = plan.get("gearbox_decision") or {}
        if gearbox.get("status") == "unknown" or not gearbox.get("reason"):
            issues.append("감속기 필요 여부와 판단 근거가 확정되지 않았습니다.")
        if gearbox.get("status") == "required" and not any(
            term in component_text for term in ("감속", "기어")
        ):
            issues.append("감속기가 필요하다고 판단했지만 구매 블록에 감속기가 없습니다.")

    for component in components:
        if not component.get("required") or component.get("already_owned"):
            continue
        category = component.get("category") or "이름 없는 부품"
        if not component.get("search_terms"):
            issues.append(f"{category}: 디바이스마트 검색어가 없습니다.")
        if not component.get("minimum_requirements"):
            issues.append(f"{category}: 최소 요구조건이 없습니다.")
        if not component.get("compatibility_checks"):
            issues.append(f"{category}: 호환성 확인 조건이 없습니다.")
        if not component.get("overspec_avoidance"):
            issues.append(f"{category}: 과잉 사양 방지 기준이 없습니다.")
    return list(dict.fromkeys(issues))


def build_component_search_query(plan: dict[str, Any], need: str) -> str:
    """승인된 설계표의 필수 부품과 검색어로 상품 검색 문장을 만듭니다."""

    terms: list[str] = []
    for component in plan.get("components") or []:
        if component.get("already_owned"):
            continue
        for term in [component.get("category"), *(component.get("search_terms") or [])]:
            normalized = _normalized_text(term, limit=150)
            if normalized and normalized not in terms:
                terms.append(normalized)
    return f"{need.strip()} 제작용 {' '.join(terms[:24])} 상품 사양 가격".strip()


def build_devicemart_review_prompt(
    project: dict[str, Any],
    need: str,
    results: list[dict[str, Any]],
    *,
    component_plan: dict[str, Any],
    budget: str = "",
    owned_parts: str = "",
) -> str:
    """초보자가 디바이스마트 검색 결과를 비교할 GPT 검수 프롬프트를 만듭니다."""

    source_blocks = []
    for index, result in enumerate(results, start=1):
        price = result.get("price_won")
        source_blocks.append(
            "\n".join(
                [
                    f"[상품 출처 {index}]",
                    f"페이지 제목: {result['title']}",
                    f"주소: {result['url']}",
                    f"검색 문맥 표시 가격: {price:,}원" if price else "검색 문맥 표시 가격: 확인되지 않음",
                    f"검색 문맥: {result.get('content') or '제공되지 않음'}",
                ]
            )
        )

    return f"""당신은 전자부품을 처음 구매하는 학생을 돕는 검수자입니다.
아래 디바이스마트 검색 결과만 사용하세요. 검색 결과에 없는 상품, 사양, 가격은 만들지 마세요.
학생의 제작 목적에 꼭 필요한 부품과 선택 부품을 구분하고, 전압·전류·통신 방식·커넥터 호환 위험을 쉬운 말로 설명하세요.
가격은 JSON에 쓰지 마세요. 가격은 YOUFFICE가 검색 문맥에서 직접 확인합니다.
부품 설계표의 component id와 상품을 정확히 연결하세요. 설계표에 없는 상품을 충동적으로 추가하지 마세요.
사양이 부족하면 compatible로 판정하지 말고 needs_confirmation으로 두세요.
목표보다 불필요하게 높은 사양과 가격이면 excessive로 판정하세요.

[프로젝트]
이름: {project.get('name') or '이름 없음'}
분야: {project.get('field') or '미입력'}
목표: {project.get('goal') or '미입력'}

[학생이 만들려는 것]
{need.strip()}

[희망 예산]
{budget.strip() or '정하지 않음'}

[이미 가지고 있는 부품]
{owned_parts.strip() or '없거나 모름'}

[승인된 구매 전 부품 설계표]
{json.dumps(component_plan, ensure_ascii=False, indent=2)}

[디바이스마트 검색 결과]
{chr(10).join(source_blocks)}

반드시 설명 문장이나 Markdown 없이 아래 JSON 형식 하나만 출력하세요.
{{
  "summary": "어떤 구성이 적합한지 3문장 이내로 설명",
  "recommended_products": [
    {{
      "product_name": "검색 결과에 실제로 나온 상품명",
      "component_id": "부품 설계표의 id",
      "purpose": "이 부품이 필요한 이유",
      "source_number": 1,
      "compatibility_status": "compatible 또는 needs_confirmation 또는 incompatible",
      "compatibility": "전압·전류·통신·커넥터·기구 호환 판단 근거",
      "overspec_status": "appropriate 또는 excessive 또는 unknown",
      "overspec_reason": "목표 대비 사양과 비용이 적절한지 판단 근거",
      "evidence": ["검색 문맥에서 그대로 복사한 짧은 사양 문구"],
      "missing_information": ["원문에서 확인하지 못한 핵심 사양"],
      "caution": "초보자가 구매 전에 확인할 점",
      "required": true
    }}
  ],
  "coverage": [
    {{"component_id": "부품 설계표의 id", "status": "selected 또는 owned 또는 missing", "note": "선정 상태 설명"}}
  ],
  "global_compatibility": {{
    "status": "compatible 또는 needs_confirmation 또는 incompatible",
    "issues": ["전체 조합에서 남은 문제"]
  }},
  "missing_categories": ["검색 결과가 부족해 추가 검색이 필요한 부품 종류"],
  "cautions": ["전체 구성에서 주의할 점"]
}}"""


def _find_json_object(text: str) -> dict[str, Any]:
    normalized = text.strip()
    if not normalized:
        raise ValueError("ChatGPT 답변을 붙여넣어 주세요.")
    start = normalized.find("{")
    end = normalized.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("ChatGPT 답변에서 JSON 형식을 찾지 못했습니다.")
    try:
        payload = json.loads(normalized[start : end + 1])
    except json.JSONDecodeError as error:
        raise ValueError(
            "ChatGPT 답변의 JSON 형식이 올바르지 않습니다. 답변 전체를 다시 복사해주세요."
        ) from error
    if not isinstance(payload, dict):
        raise ValueError("ChatGPT 답변의 최상위 형식은 JSON 객체여야 합니다.")
    return payload


def _normalize_claims(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    claims: list[dict[str, Any]] = []
    for item in value[:50]:
        if isinstance(item, str):
            content = item.strip()
            raw_source_numbers: Any = []
        elif isinstance(item, dict):
            content = _normalized_text(item.get("content"), limit=3000)
            raw_source_numbers = item.get("source_numbers") or []
        else:
            continue
        if not content:
            continue
        source_numbers: list[int] = []
        if isinstance(raw_source_numbers, list):
            for number in raw_source_numbers:
                try:
                    normalized_number = int(number)
                except (TypeError, ValueError):
                    continue
                if normalized_number > 0 and normalized_number not in source_numbers:
                    source_numbers.append(normalized_number)
        claims.append({"content": content, "source_numbers": source_numbers})
    return claims


def parse_chatgpt_review(text: str) -> dict[str, Any]:
    """ChatGPT가 반환한 JSON을 저장 가능한 검토 항목으로 정규화합니다."""

    payload = _find_json_object(text)
    return {
        "summary": _normalized_text(payload.get("summary"), limit=3000),
        "confirmed_candidates": _normalize_claims(
            payload.get("confirmed_candidates")
        ),
        "conflicts": _normalize_claims(payload.get("conflicts")),
        "unverified": _normalize_claims(payload.get("unverified")),
        "proposals": _normalize_claims(payload.get("proposals")),
    }


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value[:30]:
        normalized = _normalized_text(item, limit=1000)
        if normalized:
            items.append(normalized)
    return items


def parse_devicemart_review(text: str) -> dict[str, Any]:
    """ChatGPT의 부품 추천 JSON을 가격과 분리해 안전하게 정규화합니다."""

    payload = _find_json_object(text)
    products: list[dict[str, Any]] = []
    raw_products = payload.get("recommended_products")
    if isinstance(raw_products, list):
        for item in raw_products[:30]:
            if not isinstance(item, dict):
                continue
            product_name = _normalized_text(item.get("product_name"), limit=500)
            purpose = _normalized_text(item.get("purpose"), limit=1500)
            try:
                source_number = int(item.get("source_number") or 0)
            except (TypeError, ValueError):
                source_number = 0
            if not product_name or not purpose or source_number <= 0:
                continue
            compatibility_status = str(
                item.get("compatibility_status") or "needs_confirmation"
            ).strip().lower()
            if compatibility_status not in {
                "compatible",
                "needs_confirmation",
                "incompatible",
            }:
                compatibility_status = "needs_confirmation"
            overspec_status = str(
                item.get("overspec_status") or "unknown"
            ).strip().lower()
            if overspec_status not in {"appropriate", "excessive", "unknown"}:
                overspec_status = "unknown"
            products.append(
                {
                    "component_id": _normalized_text(
                        item.get("component_id"), limit=100
                    ),
                    "product_name": product_name,
                    "purpose": purpose,
                    "source_number": source_number,
                    "compatibility_status": compatibility_status,
                    "compatibility": _normalized_text(
                        item.get("compatibility"), limit=1500
                    ),
                    "overspec_status": overspec_status,
                    "overspec_reason": _normalized_text(
                        item.get("overspec_reason"), limit=1500
                    ),
                    "evidence": _normalize_string_list(item.get("evidence")),
                    "missing_information": _normalize_string_list(
                        item.get("missing_information")
                    ),
                    "caution": _normalized_text(item.get("caution"), limit=1500),
                    "required": _normalize_boolean(item.get("required")),
                }
            )

    coverage: list[dict[str, str]] = []
    raw_coverage = payload.get("coverage")
    if isinstance(raw_coverage, list):
        for item in raw_coverage[:30]:
            if not isinstance(item, dict):
                continue
            component_id = _normalized_text(item.get("component_id"), limit=100)
            coverage_status = str(item.get("status") or "missing").strip().lower()
            if coverage_status not in {"selected", "owned", "missing"}:
                coverage_status = "missing"
            if component_id:
                coverage.append(
                    {
                        "component_id": component_id,
                        "status": coverage_status,
                        "note": _normalized_text(item.get("note"), limit=1000),
                    }
                )

    raw_global = payload.get("global_compatibility")
    global_status = "needs_confirmation"
    global_issues: list[str] = []
    if isinstance(raw_global, dict):
        candidate_status = str(raw_global.get("status") or "").strip().lower()
        if candidate_status in {
            "compatible",
            "needs_confirmation",
            "incompatible",
        }:
            global_status = candidate_status
        global_issues = _normalize_string_list(raw_global.get("issues"))

    return {
        "summary": _normalized_text(payload.get("summary"), limit=3000),
        "recommended_products": products,
        "coverage": coverage,
        "global_compatibility": {
            "status": global_status,
            "issues": global_issues,
        },
        "missing_categories": _normalize_string_list(
            payload.get("missing_categories")
        ),
        "cautions": _normalize_string_list(payload.get("cautions")),
    }


def product_is_purchase_ready(product: dict[str, Any]) -> bool:
    """호환·사양·근거가 모두 확인된 상품만 구매 가능 후보로 인정합니다."""

    return bool(
        product.get("component_id")
        and product.get("compatibility_status") == "compatible"
        and product.get("compatibility")
        and product.get("overspec_status") == "appropriate"
        and product.get("overspec_reason")
        and product.get("evidence")
        and not product.get("missing_information")
    )


def product_has_supported_evidence(
    product: dict[str, Any],
    result: dict[str, Any],
) -> bool:
    """GPT가 제시한 사양 근거가 실제 검색 문맥에 존재하는지 확인합니다."""

    evidence_items = product.get("evidence") or []
    if not evidence_items:
        return False
    source_text = " ".join(
        [str(result.get("title") or ""), str(result.get("content") or "")]
    ).casefold()
    return all(str(evidence).strip().casefold() in source_text for evidence in evidence_items)


def component_recommendation_issues(
    review: dict[str, Any],
    component_plan: dict[str, Any],
    results: list[dict[str, Any]],
) -> list[str]:
    """빠진 부품·미확인 호환성·과잉 사양이 있는 구매 목록을 차단합니다."""

    issues: list[str] = []
    components = component_plan.get("components") or []
    component_by_id = {
        str(component.get("id") or ""): component
        for component in components
        if str(component.get("id") or "")
    }
    products = review.get("recommended_products") or []
    ready_component_ids: set[str] = set()
    for product in products:
        component_id = str(product.get("component_id") or "")
        product_name = product.get("product_name") or "이름 없는 상품"
        if component_id not in component_by_id:
            issues.append(f"{product_name}: 부품 설계표와 연결되지 않았습니다.")
            continue
        source_number = int(product.get("source_number") or 0)
        if not 1 <= source_number <= len(results):
            issues.append(f"{product_name}: 디바이스마트 원문 출처가 없습니다.")
            continue
        if product_is_purchase_ready(product) and product_has_supported_evidence(
            product,
            results[source_number - 1],
        ):
            ready_component_ids.add(component_id)
        elif product_is_purchase_ready(product):
            issues.append(
                f"{product_name}: GPT가 제시한 사양 근거가 검색 원문과 일치하지 않습니다."
            )

    for component_id, component in component_by_id.items():
        if not component.get("required") or component.get("already_owned"):
            continue
        if component_id not in ready_component_ids:
            issues.append(
                f"필수 부품 '{component.get('category')}'에 구매 가능한 호환 상품이 없습니다."
            )

    global_compatibility = review.get("global_compatibility") or {}
    if global_compatibility.get("status") != "compatible":
        issues.append("전체 부품 조합의 전원·통신·기구 호환성이 확정되지 않았습니다.")
    for issue in global_compatibility.get("issues") or []:
        issues.append(f"전체 조합 확인: {issue}")
    for missing in review.get("missing_categories") or []:
        issues.append(f"추가 검색 필요: {missing}")
    return list(dict.fromkeys(issues))


def persist_research_review(
    *,
    project_id: int,
    results: list[dict[str, Any]],
    selected_source_numbers: set[int],
    review: dict[str, Any],
    approved_candidate_indexes: set[int],
    existing_sources: list[dict[str, Any]],
    add_source: Callable[..., int],
    update_source_status: Callable[[int, str], None],
    add_fact_record: Callable[..., int | None],
    save_review_notes: bool = True,
) -> dict[str, int]:
    """사용자 선택에 따라 출처와 검토 결과를 기존 프로젝트 기록에 저장합니다."""

    source_ids_by_number: dict[int, int] = {}
    existing_by_url = {
        str(source.get("url") or "").strip(): source
        for source in existing_sources
        if str(source.get("url") or "").strip()
    }
    saved_source_count = 0
    for number in sorted(selected_source_numbers):
        if not 1 <= number <= len(results):
            continue
        result = results[number - 1]
        existing = existing_by_url.get(result["url"])
        if existing is not None:
            source_ids_by_number[number] = int(existing["id"])
            continue
        source_id = add_source(
            project_id,
            result["title"],
            result["url"],
            "인터넷 검색",
            f"Tavily 검색 문맥: {result.get('content') or '없음'}",
        )
        source_ids_by_number[number] = source_id
        saved_source_count += 1

    confirmed_count = 0
    review_note_count = 0
    candidates = review.get("confirmed_candidates") or []
    for index, claim in enumerate(candidates):
        referenced_ids = [
            source_ids_by_number[number]
            for number in claim.get("source_numbers") or []
            if number in source_ids_by_number
        ]
        if index in approved_candidate_indexes and referenced_ids:
            source_id = referenced_ids[0]
            update_source_status(source_id, "verified")
            add_fact_record(
                project_id,
                "confirmed_fact",
                claim["content"],
                origin="user",
                source_id=source_id,
            )
            confirmed_count += 1
        elif save_review_notes:
            add_fact_record(
                project_id,
                "unverified",
                claim["content"],
                origin="ai",
                source_id=referenced_ids[0] if referenced_ids else None,
            )
            review_note_count += 1

    if save_review_notes:
        for category, fact_type in (
            ("conflicts", "unverified"),
            ("unverified", "unverified"),
            ("proposals", "proposal"),
        ):
            for claim in review.get(category) or []:
                referenced_ids = [
                    source_ids_by_number[number]
                    for number in claim.get("source_numbers") or []
                    if number in source_ids_by_number
                ]
                add_fact_record(
                    project_id,
                    fact_type,
                    claim["content"],
                    origin="ai",
                    source_id=referenced_ids[0] if referenced_ids else None,
                )
                review_note_count += 1

    return {
        "sources": saved_source_count,
        "confirmed": confirmed_count,
        "review_notes": review_note_count,
    }


def persist_component_recommendations(
    *,
    project_id: int,
    results: list[dict[str, Any]],
    review: dict[str, Any],
    component_plan: dict[str, Any],
    selected_product_indexes: set[int],
    existing_sources: list[dict[str, Any]],
    add_source: Callable[..., int],
    add_fact_record: Callable[..., int | None],
    queried_at: str,
) -> dict[str, int]:
    """선택한 디바이스마트 상품을 미확인 출처와 구매 제안으로 저장합니다."""

    recommendation_issues = component_recommendation_issues(
        review,
        component_plan,
        results,
    )
    if recommendation_issues:
        raise ValueError(
            "구매 목록의 필수 부품과 호환성 검사가 끝나지 않았습니다: "
            + " / ".join(recommendation_issues[:5])
        )
    selected_products = [
        product
        for index, product in enumerate(review.get("recommended_products") or [])
        if index in selected_product_indexes
    ]
    selected_component_ids = {
        str(product.get("component_id") or "")
        for product in selected_products
        if product_is_purchase_ready(product)
    }
    missing_selected_categories = [
        component.get("category") or component.get("id") or "이름 없는 부품"
        for component in component_plan.get("components") or []
        if component.get("required")
        and not component.get("already_owned")
        and str(component.get("id") or "") not in selected_component_ids
    ]
    if missing_selected_categories:
        raise ValueError(
            "필수 구매 후보를 모두 선택해주세요: "
            + ", ".join(missing_selected_categories)
        )

    existing_by_url = {
        str(source.get("url") or "").strip(): source
        for source in existing_sources
        if str(source.get("url") or "").strip()
    }
    source_ids_by_number: dict[int, int] = {}
    saved_source_count = 0
    saved_proposal_count = 0
    products = review.get("recommended_products") or []

    for index, product in enumerate(products):
        if index not in selected_product_indexes:
            continue
        if not product_is_purchase_ready(product) or not product_has_supported_evidence(
            product,
            results[int(product.get("source_number") or 0) - 1],
        ):
            raise ValueError(
                f"{product.get('product_name') or '선택 상품'}은 호환성·과잉 사양 검사를 통과하지 못했습니다."
            )
        source_number = int(product.get("source_number") or 0)
        if not 1 <= source_number <= len(results):
            continue
        result = results[source_number - 1]
        source_id = source_ids_by_number.get(source_number)
        if source_id is None:
            existing = existing_by_url.get(result["url"])
            if existing is not None:
                source_id = int(existing["id"])
            else:
                price = price_for_product(result, product["product_name"])
                price_note = f"검색 문맥 표시 가격 {price:,}원" if price else "가격 원문 확인 필요"
                source_id = add_source(
                    project_id,
                    result["title"],
                    result["url"],
                    "디바이스마트 상품",
                    f"{price_note} · 조회 시각 {queried_at} · 구매 전 상품 페이지에서 재확인",
                )
                saved_source_count += 1
            source_ids_by_number[source_number] = source_id

        price = price_for_product(result, product["product_name"])
        price_text = f"{price:,}원(조회 시점)" if price else "원문에서 확인 필요"
        detail_parts = [
            f"구매 후보: {product['product_name']}",
            f"설계 블록: {product['component_id']}",
            f"용도: {product['purpose']}",
            f"가격: {price_text}",
        ]
        if product.get("compatibility"):
            detail_parts.append(f"호환성: {product['compatibility']}")
        if product.get("caution"):
            detail_parts.append(f"주의: {product['caution']}")
        add_fact_record(
            project_id,
            "proposal",
            " | ".join(detail_parts),
            origin="user",
            source_id=source_id,
        )
        saved_proposal_count += 1

    return {"sources": saved_source_count, "proposals": saved_proposal_count}
