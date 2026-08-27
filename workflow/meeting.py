"""직원 결과를 연결하는 순차 팀 회의와 팀장 결론을 실행합니다."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from conversation.employee_prompts import build_employee_system_prompt
from conversation.ollama_client import MODEL_NAME, OllamaResponseFormatError, optimized_chat
from conversation.prompts import build_project_context
from conversation.response_formats import (
    MEETING_CONCLUSION_MARKERS,
    MEETING_OPINION_MARKERS,
)
from conversation.response_recovery import EMPTY_ANSWER_MESSAGE, final_answer_with_retry
from database import (
    add_fact_record,
    add_handoff,
    add_meeting_turn,
    create_team_meeting,
    finish_team_meeting,
    set_employee_activity,
)
from workflow.assignment import ACTIVE_EMPLOYEE_ID
from workflow.errors import workflow_error_detail
from workflow.review import WorkflowCancelled, ensure_workflow_not_cancelled


@dataclass(frozen=True)
class TeamMeetingResult:
    """검수·보고 단계에 넘길 회의 기록과 실패 신호입니다."""

    context: str = ""
    warning_names: tuple[str, ...] = ()
    manager_failed: bool = False


def compact_context_text(text: str, max_chars: int) -> str:
    """긴 직원 결과의 앞뒤 핵심을 남겨 회의 입력 크기를 제한합니다."""

    normalized = (text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    head_chars = max(1, int(max_chars * 0.75))
    tail_chars = max(1, max_chars - head_chars)
    return (
        normalized[:head_chars].rstrip()
        + "\n\n…(긴 내용 일부 생략)…\n\n"
        + normalized[-tail_chars:].lstrip()
    )


def run_team_meeting(
    *,
    task_id: int,
    project_id: int,
    project: dict,
    user_message: dict,
    manager_message: dict,
    manager_profile: dict,
    manager_department: str,
    successful_results: list[tuple[dict, str, int]],
    review_employees: list[tuple[dict, str]],
    report_employees: list[tuple[dict, str]],
    source_message_id: int,
) -> TeamMeetingResult:
    """두 명 이상의 직원 결과를 순차 회의로 연결하고 팀장 결론을 저장합니다."""

    if len(successful_results) < 2:
        return TeamMeetingResult()

    meeting_id = create_team_meeting(task_id)
    meeting_turns: list[tuple[dict, str]] = []
    warning_names: list[str] = []
    report_char_limit = max(
        1200,
        min(2400, 8400 // len(successful_results)),
    )
    compact_reports = "\n\n".join(
        (
            f"[{employee['name']} 담당 결과 | ID: {employee['id']}]\n"
            f"{compact_context_text(answer, report_char_limit)}"
        )
        for employee, answer, _ in successful_results
    )
    meeting_opinion_instruction = (
        "팀 회의에 참여한 직원으로서 다른 직원의 실제 결과와 앞선 발언을 읽고 "
        "자기 전문 역할의 관점에서 연결점, 충돌, 위험과 수정 제안을 말한다. "
        "담당 결과를 처음부터 다시 작성하거나 모두 잘했다고만 말하지 않는다. "
        "다른 직원 결과에서 확인한 구체적인 항목을 이름과 함께 언급한다. "
        "반드시 [확인한 연결점], [쟁점·위험], [제안], [합의 여부] 네 구역을 "
        "이 순서로 모두 쓰고 자연스러운 한국어로 간결하게 답한다. "
        "[합의 여부]에는 동의, 조건부 동의, 이견 중 하나와 이유를 쓴다. "
        "내부 사고 과정은 출력하지 않는다. /no_think"
    )
    previous_speaker: dict | None = None
    for turn_order, (employee, _, _) in enumerate(successful_results, start=1):
        ensure_workflow_not_cancelled(task_id)
        prior_discussion = "\n\n".join(
            f"[{speaker['name']}의 앞선 회의 발언]\n{opinion}"
            for speaker, opinion in meeting_turns
        ) or "아직 앞선 회의 발언이 없음"
        meeting_input = (
            f"[사용자 요청]\n{user_message['content']}\n\n"
            f"[승인된 팀장 계획]\n{manager_message['content']}\n\n"
            f"[직원별 담당 결과]\n{compact_reports}\n\n"
            f"[앞선 회의 발언]\n{compact_context_text(prior_discussion, 5000)}\n\n"
            f"지금은 {employee['name']} 직원의 발언 차례입니다. "
            "자신의 담당 결과뿐 아니라 동료 결과와 앞선 발언에 실제로 반응하세요."
        )
        try:
            set_employee_activity(
                project_id,
                employee["id"],
                "working",
                "팀 회의 발언 준비 중",
                task_id,
            )
            if previous_speaker is not None:
                add_handoff(
                    task_id,
                    previous_speaker["id"],
                    employee["id"],
                    f"[팀 회의 앞선 발언]\n{meeting_turns[-1][1]}",
                )
            meeting_response = optimized_chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            build_project_context(project)
                            + build_employee_system_prompt(
                                employee,
                                employee["department_name"],
                                conversation_partner=(
                                    previous_speaker["name"]
                                    if previous_speaker is not None
                                    else None
                                ),
                                situation="회의",
                            )
                            + meeting_opinion_instruction
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"{meeting_input}\n\n/no_think",
                    },
                ],
                think=False,
                stream=False,
                options={"temperature": 0.25, "num_predict": 460},
                answer_prefix="[확인한 연결점]\n",
            )
            ensure_workflow_not_cancelled(task_id)
            meeting_opinion = final_answer_with_retry(
                meeting_response.message.content,
                meeting_input,
                output_instruction=meeting_opinion_instruction,
                required_markers=MEETING_OPINION_MARKERS,
            )
            ensure_workflow_not_cancelled(task_id)
            if meeting_opinion == EMPTY_ANSWER_MESSAGE:
                raise OllamaResponseFormatError(
                    "회의 발언 형식을 확인하지 못했습니다."
                )
            add_meeting_turn(
                meeting_id,
                employee["id"],
                turn_order,
                "opinion",
                meeting_opinion,
            )
            add_handoff(
                task_id,
                employee["id"],
                ACTIVE_EMPLOYEE_ID,
                f"[팀 회의 의견 · {employee['name']}]\n{meeting_opinion}",
            )
            meeting_turns.append((employee, meeting_opinion))
            previous_speaker = employee
            set_employee_activity(
                project_id,
                employee["id"],
                "completed",
                "회의 의견 전달 완료",
                task_id,
            )
        except WorkflowCancelled:
            raise
        except Exception as error:
            warning_names.append(employee["name"])
            set_employee_activity(
                project_id,
                employee["id"],
                "error",
                workflow_error_detail("회의 의견", error)[:180],
                task_id,
            )

    meeting_transcript = "\n\n".join(
        f"[{speaker['name']} 회의 의견]\n{opinion}"
        for speaker, opinion in meeting_turns
    ) or "제출된 직원 회의 의견 없음"
    meeting_conclusion_instruction = (
        "너는 팀 회의를 진행하는 프로젝트 팀장이다. 직원별 담당 결과와 실제 회의 "
        "발언만 근거로 합의된 내용, 충돌한 내용, 검수에 넘길 위험을 결정한다. "
        "새로운 기술 사실이나 완료되지 않은 시험 결과를 만들어내지 않는다. "
        "반드시 [회의 결론], [합의 사항], [조정 사항], [검수 전달] 네 구역을 "
        "이 순서로 모두 쓴다. 조정이 필요한 직원은 이름과 수정 내용을 명확히 쓰고, "
        "이견이 남으면 합의됐다고 꾸미지 않는다. 자연스러운 한국어 최종 결론만 "
        "출력하고 내부 사고 과정은 쓰지 않는다. /no_think"
    )
    conclusion_input = (
        f"[사용자 요청]\n{user_message['content']}\n\n"
        f"[승인된 팀장 계획]\n{manager_message['content']}\n\n"
        f"[직원별 담당 결과]\n{compact_reports}\n\n"
        f"[순차 팀 회의 발언]\n{compact_context_text(meeting_transcript, 7000)}"
    )
    try:
        ensure_workflow_not_cancelled(task_id)
        set_employee_activity(
            project_id,
            ACTIVE_EMPLOYEE_ID,
            "working",
            "팀 회의 결론 정리 중",
            task_id,
        )
        conclusion_response = optimized_chat(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        build_project_context(project)
                        + build_employee_system_prompt(
                            manager_profile,
                            manager_department,
                        )
                        + meeting_conclusion_instruction
                    ),
                },
                {
                    "role": "user",
                    "content": f"{conclusion_input}\n\n/no_think",
                },
            ],
            think=False,
            stream=False,
            options={"temperature": 0.2, "num_predict": 700},
            answer_prefix="[회의 결론]\n",
        )
        ensure_workflow_not_cancelled(task_id)
        meeting_conclusion = final_answer_with_retry(
            conclusion_response.message.content,
            conclusion_input,
            output_instruction=meeting_conclusion_instruction,
            required_markers=MEETING_CONCLUSION_MARKERS,
        )
        ensure_workflow_not_cancelled(task_id)
        if meeting_conclusion == EMPTY_ANSWER_MESSAGE:
            raise OllamaResponseFormatError(
                "팀장 회의 결론 형식을 확인하지 못했습니다."
            )
        add_meeting_turn(
            meeting_id,
            ACTIVE_EMPLOYEE_ID,
            len(successful_results) + 1,
            "conclusion",
            meeting_conclusion,
        )
        meeting_status = "partial" if warning_names else "completed"
        finish_team_meeting(
            meeting_id,
            meeting_status,
            meeting_conclusion,
        )
        add_fact_record(
            project_id,
            "proposal",
            f"팀 업무 #{task_id} 회의 결론: {meeting_conclusion}",
            origin="ai",
            source_message_id=source_message_id,
            task_id=task_id,
        )
        for target_employee, _ in review_employees + report_employees:
            add_handoff(
                task_id,
                ACTIVE_EMPLOYEE_ID,
                target_employee["id"],
                f"[팀 회의 결론]\n{meeting_conclusion}",
            )
        meeting_context = (
            f"[순차 팀 회의 발언]\n{meeting_transcript}\n\n"
            f"[팀장 회의 결론]\n{meeting_conclusion}"
        )
        set_employee_activity(
            project_id,
            ACTIVE_EMPLOYEE_ID,
            "completed",
            "회의 결론 전달 완료",
            task_id,
        )
        return TeamMeetingResult(
            context=meeting_context,
            warning_names=tuple(warning_names),
        )
    except WorkflowCancelled:
        raise
    except Exception as error:
        fallback_conclusion = (
            "[회의 결론]\n팀장 결론 생성에 실패해 합의를 확정하지 못했습니다.\n\n"
            "[합의 사항]\n확정된 합의 없음\n\n"
            "[조정 사항]\n직원 원본 결과와 제출된 회의 의견을 직접 비교해야 합니다.\n\n"
            "[검수 전달]\n회의 결론 생성 오류를 포함해 검수하고 자동 통과하지 마세요."
        )
        try:
            add_meeting_turn(
                meeting_id,
                ACTIVE_EMPLOYEE_ID,
                len(successful_results) + 1,
                "conclusion",
                fallback_conclusion,
            )
            finish_team_meeting(meeting_id, "failed", fallback_conclusion)
        except sqlite3.Error:
            pass
        meeting_context = (
            f"[순차 팀 회의 발언]\n{meeting_transcript}\n\n"
            f"[팀장 회의 결론]\n{fallback_conclusion}"
        )
        set_employee_activity(
            project_id,
            ACTIVE_EMPLOYEE_ID,
            "error",
            workflow_error_detail("회의 결론", error)[:180],
            task_id,
        )
        return TeamMeetingResult(
            context=meeting_context,
            warning_names=tuple(warning_names),
            manager_failed=True,
        )
