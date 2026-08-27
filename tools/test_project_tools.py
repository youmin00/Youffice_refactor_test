"""초보자용 자료 검색 도구 진입 화면의 네트워크 없는 회귀 검사."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ui.internet_research import (
    COMPONENT_RESEARCH_MODE,
    GENERAL_RESEARCH_MODE,
    research_mode_session_key,
)
from ui.project_tools import build_research_prefill


def main() -> None:
    assert GENERAL_RESEARCH_MODE == "일반 인터넷 조사"
    assert COMPONENT_RESEARCH_MODE == "디바이스마트 부품 찾기"
    assert research_mode_session_key(42) == "internet_research_42_mode"
    project = {"goal": "교실의 온도와 습도를 기록하는 장치를 만든다."}
    messages = [
        {"role": "user", "content": "프로젝트를 나와 함께 구체화해 줘."},
        {"role": "assistant", "content": "사용 장소는 어디인가요?"},
        {"role": "user", "content": "교실 책상 위에서 일주일 동안 사용할 거야."},
    ]
    prefill = build_research_prefill(project, messages)
    assert "교실의 온도와 습도" in prefill
    assert "일주일 동안" in prefill
    assert "구체화해 줘" not in prefill

    assert build_research_prefill(project, []) == (
        "프로젝트 목표: 교실의 온도와 습도를 기록하는 장치를 만든다."
    )
    print("PROJECT_TOOLS_REGRESSION_OK")


if __name__ == "__main__":
    main()
