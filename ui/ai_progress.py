"""대화 중 AI가 실제로 수행 중인 단계를 보여 주는 상태판."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass
class ChatProgress:
    """한 번의 채팅 응답에 대한 사용자용 진행 상태를 갱신합니다."""

    panel: Any
    name: str

    def _update(self, label: str, detail: str, *, state: str = "running") -> None:
        self.panel.update(label=label, state=state, expanded=state != "complete")
        self.panel.write(detail)

    def context_ready(self) -> None:
        self._update(
            f"{self.name}가 답변에 필요한 내용을 정리했어요",
            "✅ 최근 대화와 프로젝트 기록을 확인했어요.",
        )

    def generating(self) -> None:
        self._update(
            f"{self.name}가 답변 초안을 작성하고 있어요",
            "🔄 지금은 AI가 문장을 만들고 있어요. 이 단계가 오래 지속되면 응답이 지연된 상태예요.",
        )

    def checking_format(self) -> None:
        self._update(
            f"{self.name}가 답변을 확인하고 있어요",
            "🔄 한국어 답변인지, 계획에 필요한 항목이 빠지지 않았는지 확인하고 있어요.",
        )

    def regenerating(self, attempt: int) -> None:
        self._update(
            f"{self.name}가 답변 형식을 한 번 다듬고 있어요",
            f"🔄 초안에 필요한 항목이 빠져 있어 {attempt}회차로 다시 정리하고 있어요.",
        )

    def retrying_repetition(self) -> None:
        self._update(
            f"{self.name}가 반복 답변을 고치고 있어요",
            "🔄 바로 앞 답변과 너무 비슷해, 사용자의 최신 요청에 맞춰 다시 작성하고 있어요.",
        )

    def complete(self) -> None:
        self._update(
            f"{self.name}의 답변 준비가 끝났어요",
            "✅ 답변을 대화에 저장하고 있어요.",
            state="complete",
        )

    def fail(self) -> None:
        self._update(
            f"{self.name}의 답변 준비가 멈췄어요",
            "⚠️ 답변을 저장하지 않았어요. 화면의 안내를 확인한 뒤 다시 시도할 수 있어요.",
            state="error",
        )


def start_chat_progress(name: str, *, is_plan_request: bool) -> ChatProgress:
    """채팅 요청이 시작됐음을 표시하고 갱신 가능한 상태판을 반환합니다."""

    label = (
        f"{name}가 승인용 팀 계획을 준비하고 있어요"
        if is_plan_request
        else f"{name}가 요청을 확인하고 있어요"
    )
    panel = st.status(label, expanded=True)
    panel.write("✅ 요청을 받았어요.")
    return ChatProgress(panel=panel, name=name)
