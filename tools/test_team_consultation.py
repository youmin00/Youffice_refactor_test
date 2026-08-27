"""팀 의견 담당자 선택 규칙을 외부 AI 호출 없이 확인합니다."""

from workflow.team_consultation import select_team_consultants


def _employee(employee_id: str, title: str) -> tuple[dict, str]:
    return ({"id": employee_id, "name": employee_id, "title": title, "role_description": ""}, "프로젝트팀")


def run() -> None:
    employees = [
        _employee("planner", "기획 담당"),
        _employee("engineer", "기술 설계 담당"),
        _employee("reviewer", "품질 검수 담당"),
        _employee("reporter", "보고서 담당"),
    ]
    hardware = select_team_consultants({"goal": ""}, "모터와 센서를 골라야 해", employees)
    assert [employee[0]["id"] for employee in hardware] == ["engineer", "planner"]
    research = select_team_consultants({"goal": ""}, "디바이스마트 가격을 비교하고 싶어", employees)
    assert [employee[0]["id"] for employee in research] == ["planner", "reviewer"]
    general = select_team_consultants({"goal": "아이디어 정리"}, "어떻게 시작하면 좋을까", employees)
    assert [employee[0]["id"] for employee in general] == ["planner", "engineer"]


if __name__ == "__main__":
    run()
    print("team consultation checks passed")
