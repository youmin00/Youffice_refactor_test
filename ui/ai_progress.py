"""User-visible, truthful progress messages for chat replies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass
class ChatProgress:
    panel: Any
    name: str

    def _update(self, label: str, detail: str, *, state: str = "running") -> None:
        self.panel.update(label=label, state=state, expanded=state != "complete")
        self.panel.write(detail)

    def context_ready(self) -> None:
        self._update(
            f"{self.name}가 필요한 대화 내용을 정리했어요",
            "최근 대화와 프로젝트 기록을 확인했어요.",
        )

    def researching_ideas(self) -> None:
        self._update(
            f"{self.name}가 관련 자료와 선택 기준을 찾고 있어요",
            "🔄 검색 결과를 바로 쓰지 않고, 현재 질문에 맞는지와 페이지가 실제로 열리는지 확인하고 있어요.",
        )

    def research_ready(self, source_count: int) -> None:
        self._update(
            f"{self.name}가 아이디어 조사 자료를 정리했어요",
            f"✅ 열림·관련성 확인을 마친 참고 자료 {source_count}개만 답변에 넣어요. 이제 이 근거를 바탕으로 새로운 방향을 비교해볼게요.",
        )

    def research_unavailable(self, reason: str) -> None:
        self._update(
            f"{self.name}가 웹 자료를 답변에서 제외했어요",
            "⚠️ 실제로 열리고 현재 질문과 맞는 공개 자료를 찾지 못했어요. 확인되지 않은 링크는 출처로 보여주지 않고, "
            f"일반 설계 안내만 드릴게요. 사유: {reason}",
        )

    def generating(self) -> None:
        self._update(
            f"{self.name}가 답변 초안을 작성하고 있어요",
            "지금은 AI가 설명을 만들고 있어요. 이 단계가 오래 지속되면 응답이 지연된 상태예요.",
        )

    def checking_format(self) -> None:
        self._update(
            f"{self.name}가 답변을 확인하고 있어요",
            "답변이 사용자 요청에 맞고, 계획과 필요한 항목이 빠지지 않았는지 확인하고 있어요.",
        )

    def regenerating(self, attempt: int) -> None:
        self._update(
            f"{self.name}가 답변 형식을 다시 고치고 있어요",
            f"초안에 필요한 항목이 비어 있어 {attempt}번째로 다시 정리하고 있어요.",
        )

    def retrying_repetition(self) -> None:
        self._update(
            f"{self.name}가 반복된 답변을 고치고 있어요",
            "바로 전 답변과 너무 비슷하지 않도록 사용자의 최신 요청에 맞춰 다시 작성하고 있어요.",
        )

    def complete(self) -> None:
        self._update(
            f"{self.name}의 답변 준비가 끝났어요",
            "답변이 대화에 추가되고 있어요.",
            state="complete",
        )

    def fail(self) -> None:
        self._update(
            f"{self.name}의 답변 준비가 멈췄어요",
            "이번 답변은 대화에 추가하지 않았어요. 화면의 안내를 확인한 뒤 다시 시도할 수 있어요.",
            state="error",
        )


def start_chat_progress(name: str, *, is_plan_request: bool) -> ChatProgress:
    label = f"{name}가 팀 계획을 준비하고 있어요" if is_plan_request else f"{name}가 요청을 확인하고 있어요"
    panel = st.status(label, expanded=True)
    panel.write("요청을 받았어요.")
    return ChatProgress(panel=panel, name=name)
