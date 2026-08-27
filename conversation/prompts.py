"""YOUFFICE 프로젝트·자료·기억 프롬프트 생성."""


BEGINNER_GUIDANCE_MARKER = "[단계별 안내]"


def build_project_context(project: dict) -> str:
    """현재 프로젝트 정보를 AI가 이해할 수 있는 지시문으로 만듭니다."""

    context_parts = [
        "현재 작업 중인 프로젝트 정보는 다음과 같다.",
        f"프로젝트명: {project['name']}.",
    ]

    field = str(project.get("field") or "").strip()
    if field:
        context_parts.append(f"분야: {field}.")

    context_parts.append(f"만들고 싶은 것: {project['goal']}.")

    project_notes = str(project.get("skills") or "").strip()
    if project_notes.startswith(BEGINNER_GUIDANCE_MARKER):
        project_notes = project_notes.removeprefix(BEGINNER_GUIDANCE_MARKER).strip()
        context_parts.append(
            "진행 방식: 아직 설계가 완성되지 않았을 수 있다. "
            "현재 단계에서 꼭 필요한 질문만 쉬운 말로 한 번에 1~2개씩 묻고, "
            "사용자가 모르는 선택에는 간단한 예시와 추천 이유를 함께 설명한다."
        )
    if project_notes:
        context_parts.append(f"현재 알고 있거나 보유한 내용: {project_notes}.")

    context_parts.append(
        "날짜와 예산을 임의로 전제하지 말고, 모든 답변은 이 프로젝트의 목표와 "
        "사용자가 지금까지 알려준 조건을 우선하여 작성한다."
    )
    return " ".join(context_parts) + " "


def build_source_context(sources: list[dict]) -> str:
    """등록된 출처를 AI가 과장 없이 활용하도록 지시문으로 만듭니다."""

    if not sources:
        return (
            "현재 프로젝트에 등록된 자료나 출처가 없다. "
            "외부 자료를 확인했다고 주장하거나 출처를 만들어내지 않는다. "
        )

    status_labels = {
        "unverified": "미확인",
        "verified": "확인됨",
        "rejected": "사용 제외",
    }

    source_lines = []
    for source in sources:
        source_lines.append(
            f"- {source['title']} | 유형: {source['source_type']} | "
            f"상태: {status_labels.get(source['verification_status'], '미확인')} | "
            f"주소: {source['url'] or '없음'} | 메모: {source['notes'] or '없음'}"
        )

    return (
        "현재 프로젝트에 사용자가 등록한 자료와 출처는 다음과 같다.\n"
        + "\n".join(source_lines)
        + "\n주소의 실제 본문을 직접 열어 읽었다고 주장하지 않는다. "
        "'확인됨' 자료와 사용자가 입력한 메모만 확정 근거처럼 사용할 수 있다. "
        "'미확인'은 참고 후보로 표시하고 '사용 제외'는 근거로 사용하지 않는다. "
    )
def build_memory_context(
    memories: list[dict],
    records: list[dict],
    fact_records: list[dict] | None = None,
) -> str:
    """프로젝트 기억·기록과 근거가 연결된 사실을 AI 지시문으로 만듭니다."""

    memory_lines = [
        f"- [{memory['category']}] {memory['content']}"
        for memory in reversed(memories[:20])
    ]

    record_lines = [
        f"- [{record['record_type']}/{record['status']}] "
        f"{record['title']}: {record['content']}"
        for record in reversed(records[:20])
    ]

    fact_type_labels = {
        "confirmed_fact": "확정 사실",
        "proposal": "제안",
        "unverified": "미확인",
        "user_decision": "사용자 결정",
        "limitation": "한계",
    }
    source_status_labels = {
        "unverified": "미확인",
        "verified": "확인됨",
        "rejected": "사용 제외",
    }
    fact_lines = []
    for fact_record in reversed((fact_records or [])[:30]):
        source_title = fact_record.get("source_title")
        if source_title:
            source_status = source_status_labels.get(
                fact_record.get("source_verification_status"),
                "미확인",
            )
            provenance = f"근거: {source_title} ({source_status})"
        elif fact_record.get("source_message_id"):
            provenance = "근거: 프로젝트 대화 메시지"
        elif fact_record.get("report_id"):
            provenance = "근거: 보고서 분류 결과"
        else:
            provenance = "근거: 사용자 직접 입력"
        fact_lines.append(
            f"- [{fact_type_labels.get(fact_record['fact_type'], '기록')}] "
            f"{fact_record['content']} ({provenance})"
        )

    if not memory_lines and not record_lines and not fact_lines:
        return "현재 프로젝트에 별도로 저장된 장기 기억·기록·근거 연결 사실이 없다. "

    return (
        "현재 프로젝트의 장기 기억, 기존 기록과 근거 연결 정보는 다음과 같다.\n"
        + ("장기 기억:\n" + "\n".join(memory_lines) + "\n" if memory_lines else "")
        + ("기존 결정 및 오류 기록:\n" + "\n".join(record_lines) + "\n" if record_lines else "")
        + ("사실·결정·제안 분류:\n" + "\n".join(fact_lines) + "\n" if fact_lines else "")
        + "[확정 사실]과 [사용자 결정]만 확정 조건으로 사용한다. "
        + "[제안], [미확인], [한계]는 확정 사실처럼 바꾸지 말고 상태를 유지한다. "
        + "근거가 '사용 제외'인 항목은 근거로 사용하지 않으며, 오래된 기록과 새 요청이 충돌하면 사용자에게 확인한다. "
    )
