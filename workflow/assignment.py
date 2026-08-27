"""YOUFFICE 사용자 요청을 직원별 업무로 배정합니다."""

ACTIVE_EMPLOYEE_ID = "project_manager"


def is_review_employee(employee: dict) -> bool:
    """직원 프로필에서 안전·품질 검수 담당 여부를 판단합니다."""

    profile_text = " ".join(
        str(employee.get(field, ""))
        for field in ("name", "title", "role_description")
    ).lower()
    return any(
        keyword in profile_text
        for keyword in ("검수", "품질", "안전", "review", "qa")
    )


def is_memory_employee(employee: dict) -> bool:
    """장기 기억을 담당하는 직원인지 프로필 지침으로 판단합니다."""

    profile_text = " ".join(
        str(employee.get(field, ""))
        for field in ("name", "title", "role_description")
    ).lower()
    return any(
        keyword in profile_text
        for keyword in ("기억", "메모", "비서", "memory")
    )


def is_report_employee(employee: dict) -> bool:
    """최종 보고서 담당 직원인지 프로필 지침으로 판단합니다."""

    profile_text = " ".join(
        str(employee.get(field, ""))
        for field in ("name", "title", "role_description")
    ).lower()
    return any(keyword in profile_text for keyword in ("보고서", "보고", "report"))


EMPLOYEE_WORKSTREAM_LABELS = {
    "manager": "팀장·업무 배정",
    "memory": "기억·요구사항 확인",
    "planning": "기획·일정",
    "technical": "기술 설계·구현",
    "review": "안전·품질 검수",
    "report": "최종 보고",
    "general": "프로필 지정 업무",
}


EMPLOYEE_ASSIGNMENT_CONTRACTS = {
    "memory": {
        "objective": "현재 요청과 관련된 과거 요구사항, 결정, 제약과 충돌 항목만 확인한다.",
        "deliverables": (
            "확인된 이전 요구사항과 결정",
            "현재 요청에 적용할 제약 조건",
            "기억에 없거나 사용자 확인이 필요한 항목",
        ),
        "forbidden": (
            "새 일정·예산·기술 설계 만들기",
            "전체 개발 계획이나 최종 결론 대신 작성하기",
        ),
    },
    "planning": {
        "objective": "무엇을 어떤 순서와 기준으로 완료할지 프로젝트 범위를 기획한다.",
        "deliverables": (
            "사용자가 제공한 요구사항과 우선순위",
            "현재 요청을 위한 업무 분해와 진행 순서",
            "확인된 정보만 사용한 완료 기준과 반드시 필요한 사용자 확인 사항",
        ),
        "forbidden": (
            "회로·코드·부품 연결의 상세 설계",
            "검수 통과 판정이나 최종 보고서 작성",
        ),
    },
    "technical": {
        "objective": "확인된 요구사항과 기획 결과를 실제 구현 가능한 기술 구조로 변환한다.",
        "deliverables": (
            "사용자 요청에 필요하고 현재 자료로 확인된 기술 구성",
            "확인된 부품·소프트웨어·연결 방식과 제어 흐름",
            "현재 요청 범위에서 필요한 구현·검증 항목. 미제공 정보는 임의로 채우지 말고 미확인으로 표시",
        ),
        "forbidden": (
            "프로젝트 전체 일정과 예산 다시 작성하기",
            "자기 결과를 검수 통과시키거나 최종 보고서 작성하기",
        ),
    },
    "review": {
        "objective": "직원 결과의 오류, 누락, 위험과 논리적 모순을 독립적으로 검수한다.",
        "deliverables": (
            "통과 또는 재작업 판정",
            "판정 근거와 수정이 필요한 항목",
            "안전 조건과 확인되지 않은 주장",
        ),
        "forbidden": (
            "검수 대상 결과를 처음부터 대신 작성하기",
            "근거 없는 통과 판정이나 최종 보고서 작성",
        ),
    },
    "report": {
        "objective": "직원 결과와 검수 기록을 중복 없이 사용자용 최종 보고로 통합한다.",
        "deliverables": (
            "요청에 대한 결론과 직원별 핵심 결과",
            "실행 순서, 주의점과 미확인 사항",
            "검수 결과가 반영된 자연스러운 한국어 보고",
        ),
        "forbidden": (
            "제공되지 않은 수치·부품·기술 사실 새로 만들기",
            "내부 사고 과정이나 직원 간 원문을 그대로 반복하기",
        ),
    },
    "general": {
        "objective": "프로필에 지정된 담당 업무만 수행한다.",
        "deliverables": (
            "프로필 역할에 맞는 결과",
            "결과의 근거와 가정",
            "다음 담당자에게 전달할 사항",
        ),
        "forbidden": (
            "다른 직원의 전문 영역 대신 작성하기",
            "전체 답변이나 최종 보고서 대신 작성하기",
        ),
    },
}


def employee_workstream(employee: dict, department: str = "") -> str:
    """직원 이름이 아닌 부서·직책·역할 지침으로 실제 작업 단계를 구분합니다."""

    if employee.get("id") == ACTIVE_EMPLOYEE_ID:
        return "manager"

    title_and_department = " ".join(
        (department, str(employee.get("title", "")))
    ).lower()
    profile_text = " ".join(
        (
            title_and_department,
            str(employee.get("name", "")),
            str(employee.get("role_description", "")),
        )
    ).lower()

    # 직책과 부서에 명시된 역할을 설명문 속 보조 키워드보다 우선합니다.
    if any(keyword in title_and_department for keyword in ("보고서", "보고", "report")):
        return "report"
    if any(
        keyword in title_and_department
        for keyword in ("검수", "품질", "안전", "qa", "review")
    ):
        return "review"
    if any(
        keyword in title_and_department
        for keyword in ("비서", "기억", "메모", "memory")
    ):
        return "memory"
    if any(
        keyword in title_and_department
        for keyword in (
            "기술",
            "설계",
            "구현",
            "시스템",
            "아키텍처",
            "회로",
            "하드웨어",
            "소프트웨어",
            "개발",
        )
    ):
        return "technical"
    if any(
        keyword in title_and_department
        for keyword in ("기획", "일정", "예산", "요구사항", "계획", "wbs")
    ):
        return "planning"
    if any(keyword in profile_text for keyword in ("보고서", "report")):
        return "report"
    if any(
        keyword in profile_text
        for keyword in ("검수", "품질", "안전", "qa", "review")
    ):
        return "review"
    if any(keyword in profile_text for keyword in ("비서", "기억", "메모", "memory")):
        return "memory"
    if any(
        keyword in profile_text
        for keyword in (
            "기술",
            "설계",
            "구현",
            "시스템",
            "아키텍처",
            "회로",
            "하드웨어",
            "소프트웨어",
            "개발",
        )
    ):
        return "technical"
    if any(
        keyword in profile_text
        for keyword in ("기획", "일정", "예산", "요구사항", "계획", "wbs")
    ):
        return "planning"
    return "general"


def assignment_contract(workstream: str) -> dict:
    """알 수 없는 역할도 일반 직원 계약으로 안전하게 처리합니다."""

    return EMPLOYEE_ASSIGNMENT_CONTRACTS.get(
        workstream,
        EMPLOYEE_ASSIGNMENT_CONTRACTS["general"],
    )


def build_employee_assignment(employee: dict, department: str) -> str:
    """한 직원에게만 적용되는 담당 범위와 금지 범위를 만듭니다."""

    workstream = employee_workstream(employee, department)
    contract = assignment_contract(workstream)
    deliverables = "\n".join(
        f"- {deliverable}" for deliverable in contract["deliverables"]
    )
    forbidden = "\n".join(
        f"- {forbidden_item}" for forbidden_item in contract["forbidden"]
    )
    return (
        f"담당자 ID: {employee['id']}\n"
        f"담당자: {employee['name']} / {department} / {employee['title']}\n"
        f"업무 유형: {EMPLOYEE_WORKSTREAM_LABELS[workstream]}\n"
        f"담당 목표: {contract['objective']}\n"
        f"필수 산출물:\n{deliverables}\n"
        f"담당하지 않을 범위:\n{forbidden}\n"
        "범위를 벗어난 항목은 임의로 작성하지 말고 '다른 담당자 확인 필요'로 표시한다."
    )


def build_employee_output_instruction(employee: dict, department: str) -> str:
    """재시도하더라도 직원이 전체 최종 답변을 대신 쓰지 않게 고정합니다."""

    return (
        f"너는 {employee['name']}이며 {build_employee_assignment(employee, department)}\n"
        "반드시 맡은 범위만 한국어로 작성한다. 출력 형식은 다음 네 항목으로 제한한다.\n"
        "[담당 결과]\n[근거·가정]\n[미확인 사항]\n[다음 직원 전달]\n"
        "다른 직원의 업무나 전체 최종 보고를 대신 작성하지 않는다. /no_think"
    )


def normalize_manager_plan_project_name(
    plan_text: str,
    project_name: str,
) -> str:
    """Keep the exact DB project name in a manager delegation plan."""

    if not plan_text or not project_name:
        return plan_text

    project_label = "\ud504\ub85c\uc81d\ud2b8\uba85"
    receipt_marker = "[\uc5c5\ubb34 \uc811\uc218]"

    lines = plan_text.splitlines()
    found = False

    for index, line in enumerate(lines):
        stripped = line.strip()

        if project_label not in stripped:
            continue

        label_pos = stripped.find(project_label)
        remainder = stripped[label_pos + len(project_label):]

        if ":" not in remainder and "\uff1a" not in remainder:
            continue

        indent = line[: len(line) - len(line.lstrip())]
        bullet = "- " if stripped.startswith("- ") else ""

        lines[index] = (
            f"{indent}{bullet}{project_label}: {project_name}"
        )
        found = True

    if not found:
        exact_line = f"{project_label}: {project_name}"

        try:
            marker_index = lines.index(receipt_marker)
            lines.insert(marker_index + 1, exact_line)
        except ValueError:
            lines.insert(0, exact_line)

    return "\n".join(lines)


def build_manager_delegation_instruction(
    supporting_employees: list[tuple[dict, str]],
) -> str:
    """유키가 해결책을 혼자 쓰지 않고 승인용 업무 배정만 작성하게 합니다."""

    assignment_lines = []
    for employee, department in supporting_employees:
        workstream = employee_workstream(employee, department)
        contract = assignment_contract(workstream)
        assignment_lines.append(
            f"- {employee['name']} [{employee['id']}] / {department} / "
            f"{employee['title']}: {contract['objective']} "
            f"산출물은 {', '.join(contract['deliverables'])}."
        )
    roster = "\n".join(assignment_lines) or "- 현재 배정 가능한 활성 직원 없음"
    return (
        "\n지금 단계에서 너는 프로젝트 팀장으로서 직접 해결안을 작성하지 않는다. "
        "아래 활성 직원의 프로필 역할에 맞춰 사용자 승인용 업무 배정 계획만 작성한다.\n"
        f"{roster}\n"
        "출력은 반드시 다음 순서를 사용한다.\n"
        "[업무 접수] 요청 목적과 확인할 조건\n"
        "[직원별 배정] 각 직원의 담당 범위와 산출물\n"
        "직원별 배정에서는 직원마다 `- **이름 (직책):**`를 독립된 한 줄에 쓰고, "
        "해당 직원의 업무와 산출물은 바로 아래에 네 칸 들여쓴 `    -` 하위 목록으로 작성한다. "
        "직원 이름과 업무 내용을 같은 단계의 목록으로 섞지 않는다.\n"
        "[작업 순서] 기억 확인 → 기획 → 기술 설계 → 검수 → 최종 보고의 전달 순서\n"
        "[승인 요청] 사용자가 승인하면 실제 직원 AI 호출을 시작한다는 안내\n"
        "승인 전에는 구체적인 부품 목록, 코드, 완성 설계, 검수 결과 또는 최종 답을 "
        "미리 만들지 않는다. 없는 수치나 조건을 추정하지 않는다. /no_think\n"
    )
