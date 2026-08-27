"""오피스 직원·회의·인수인계 기록을 보여주는 Streamlit dialog."""

from __future__ import annotations

import html

import streamlit as st

from conversation.response_validator import is_korean_answer
from database import (
    get_team_meeting,
    list_employee_activities,
    list_employee_results,
    list_handoffs,
    list_meeting_turns,
    list_memories,
    list_review_targets,
    list_reviews,
)
from ui.chat import profile_avatar_content, render_manager_context
from ui.console import render_console_handoff_list
from ui.office import (
    employee_sprite_data,
    meeting_room_background_data,
    office_room_background_data,
)
from ui.organization import ACTIVE_EMPLOYEE_ID, load_organization


def employee_dialogue_text(
    employee: dict,
    action: str,
    state_label: str,
    project: dict,
    latest_task: dict | None,
) -> str:
    """선택한 메뉴에 맞는 직원의 즉시 대사를 만듭니다."""

    employee_name = employee["name"]
    if action == "status":
        if latest_task is None:
            return (
                f"현재는 {state_label}이에요. 새 업무가 들어오면 제 역할에 맞춰 "
                f"{project['name']} 프로젝트를 지원할게요."
            )
        return (
            f"현재 상태는 ‘{state_label}’이에요. 최근 업무는 "
            f"‘{latest_task['request'][:160]}’입니다."
        )
    if action == "role":
        return (
            f"저는 {employee['title']}으로 일하고 있어요. "
            f"제 업무 지침은 다음과 같습니다.\n\n{employee['role_description']}"
        )
    if action == "memory":
        memories = list_memories(project["id"], limit=3)
        if not memories:
            return "아직 이 프로젝트에 저장된 장기 기억이 없어요. 중요한 결정은 기록으로 남겨주세요."
        memory_lines = "\n".join(
            f"• {memory['content'][:180]}"
            for memory in memories
        )
        return f"이 프로젝트에서 최근에 기억하고 있는 내용이에요.\n\n{memory_lines}"
    if action == "result":
        if latest_task is None:
            return "아직 확인할 업무 결과가 없어요. 먼저 유키에게 프로젝트 업무를 요청해주세요."
        employee_result = next(
            (
                result
                for result in list_employee_results(latest_task["id"])
                if result["employee_id"] == employee["id"]
            ),
            None,
        )
        if employee_result is None:
            if employee["id"] == ACTIVE_EMPLOYEE_ID:
                return (
                    "저는 팀원들의 결과를 모아 최종 방향을 정리해요. "
                    "자세한 내용은 대화 화면의 마지막 종합 답변에서 확인할 수 있어요."
                )
            return "최근 업무에서 제가 별도로 작성한 결과는 아직 없어요."
        result_content = employee_result["output"] or employee_result["error"]
        if not result_content:
            return "업무 결과를 작성하고 있어요. 조금만 기다려주세요."
        if not is_korean_answer(result_content):
            return "최근 결과가 영어 중심으로 생성되어 여기에는 표시하지 않았어요. 다시 작업이 필요해요."
        return f"최근에 제가 정리한 결과의 일부예요.\n\n{result_content[:1600]}"

    if "회의" in state_label:
        return (
            f"{employee_name}이에요. 동료들의 실제 결과와 앞선 의견을 읽고 "
            "제 역할에서 필요한 연결점과 이견을 정리하고 있어요."
        )
    if "작업" in state_label or "조율" in state_label:
        return f"{employee_name}이에요. 지금 맡은 업무에 집중하고 있어요!"
    if "검수" in state_label or "재작업" in state_label:
        return f"{employee_name}입니다. 놓친 위험이 없는지 꼼꼼하게 확인하고 있어요."
    if "완료" in state_label or "통과" in state_label:
        return f"{employee_name}이에요. 맡은 업무를 마쳤어요. 결과를 확인해보시겠어요?"
    if "오류" in state_label or "확인 필요" in state_label:
        return f"{employee_name}입니다. 작업 중 확인이 필요한 문제가 생겼어요."
    if state_label == "비활성":
        return f"{employee_name}이에요. 지금은 비활성 상태라 업무를 수행하지 않고 있어요."
    return f"안녕하세요! {employee_name}이에요. 오늘은 어떤 프로젝트를 함께 진행할까요?"


def employee_work_console_data(
    project_id: int,
    employee_id: str,
    latest_task: dict | None,
) -> dict:
    """직원 대화창에서 사용할 최근 업무·전달·결과·검수 기록을 조립합니다."""

    activity = next(
        (
            item
            for item in list_employee_activities(project_id)
            if item["employee_id"] == employee_id
        ),
        None,
    )
    console = {
        "activity": activity,
        "received_handoffs": [],
        "sent_handoffs": [],
        "result": None,
        "reviews": [],
        "review_targets": [],
        "targeted_reviews": [],
        "rework_handoffs": [],
    }
    if latest_task is None:
        return console

    handoffs = list_handoffs(latest_task["id"])
    console["received_handoffs"] = [
        handoff
        for handoff in handoffs
        if handoff["to_employee_id"] == employee_id
    ]
    console["sent_handoffs"] = [
        handoff
        for handoff in handoffs
        if handoff["from_employee_id"] == employee_id
    ]
    console["rework_handoffs"] = [
        handoff
        for handoff in console["received_handoffs"]
        if "재작업" in handoff["content"] or "수정" in handoff["content"]
    ]
    console["result"] = next(
        (
            result
            for result in list_employee_results(latest_task["id"])
            if result["employee_id"] == employee_id
        ),
        None,
    )
    console["reviews"] = [
        review
        for review in list_reviews(latest_task["id"])
        if review["reviewer_employee_id"] == employee_id
    ]
    console["review_targets"] = list_review_targets(latest_task["id"])
    console["targeted_reviews"] = [
        target
        for target in console["review_targets"]
        if target["target_employee_id"] == employee_id
    ]
    return console


def clear_office_employee_dialog() -> None:
    """직원 대화창의 선택 상태를 정리합니다."""

    st.session_state.pop("office_selected_employee_id", None)
    st.session_state.pop("office_dialog_action", None)


@st.dialog(
    "직원 업무 콘솔",
    width="large",
    dismissible=True,
    on_dismiss=clear_office_employee_dialog,
)
def show_office_employee_dialog(
    employee: dict,
    department: str,
    state: tuple[str, str],
    project: dict,
    latest_task: dict | None,
) -> None:
    """직원의 대화 장면과 실제 업무·전달·결과 기록을 함께 표시합니다."""

    state_class, state_label = state
    action = st.session_state.get("office_dialog_action", "greeting")
    dialogue = employee_dialogue_text(
        employee,
        action,
        state_label,
        project,
        latest_task,
    )
    dialog_character = profile_avatar_content(employee)
    dialog_background = office_room_background_data(employee["id"])
    console = employee_work_console_data(
        project["id"],
        employee["id"],
        latest_task,
    )
    employees_by_id = {
        item["id"]: item for item in load_organization()[1]
    }
    st.markdown(
        f"""
        <div class="agent-console-header">
            <span>AGENT BRAIN CONSOLE</span>
            <strong>{html.escape(employee['name'])} · {html.escape(employee['title'])}</strong>
            <em>{html.escape(state_label)}</em>
        </div>
        <div class="visual-novel-scene state-{state_class}" style="background-image:url('{dialog_background}')">
            <div class="visual-novel-profile">
                <div class="visual-novel-portrait">{dialog_character}</div>
                <div class="visual-novel-department">{html.escape(department)}</div>
                <div class="visual-novel-role">{html.escape(employee['title'])}</div>
            </div>
            <div class="visual-novel-info">
                <div class="visual-novel-kicker">YOUFFICE EMPLOYEE</div>
                <div class="visual-novel-name">{html.escape(employee['name'])}</div>
                <div class="visual-novel-state"><span></span>{html.escape(state_label)}</div>
                <div class="visual-novel-project">현재 프로젝트 · {html.escape(project['name'])}</div>
            </div>
        </div>
        <div class="visual-novel-dialogue">
            <div class="visual-novel-speaker">{html.escape(employee['name'])}</div>
            <div class="visual-novel-line">{html.escape(dialogue)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    (
        current_work_tab,
        received_tab,
        result_tab,
        sent_tab,
        review_tab,
        direct_chat_tab,
    ) = st.tabs(
        [
            "현재 업무",
            "받은 자료",
            "작성 결과",
            "보낸 자료",
            "검수·재작업",
            "직접 대화",
        ]
    )

    with current_work_tab:
        activity = console["activity"]
        activity_detail = (
            activity["detail"]
            if activity is not None and activity["detail"]
            else state_label
        )
        task_status_labels = {
            "pending": "승인 대기",
            "running": "진행 중",
            "completed": "완료",
            "failed": "확인 필요",
        }
        status_column, detail_column = st.columns([0.32, 0.68])
        with status_column:
            st.metric("현재 상태", state_label)
        with detail_column:
            st.markdown("**직원 상태 상세**")
            st.write(activity_detail)
        if latest_task is None:
            st.info("아직 시작된 팀 업무가 없습니다. 유키에게 새 업무를 요청해주세요.")
        else:
            st.caption(
                f"최근 팀 업무 #{latest_task['id']} · "
                f"{task_status_labels.get(latest_task['status'], latest_task['status'])}"
            )
            with st.container(border=True):
                st.markdown("**사용자가 요청한 프로젝트 업무**")
                st.write(latest_task["request"])
            employee_result = console["result"]
            if employee_result is not None and employee_result.get("input_context"):
                with st.expander("이 직원에게 전달된 실제 업무 지시"):
                    st.markdown(employee_result["input_context"])
            elif employee["id"] == ACTIVE_EMPLOYEE_ID:
                with st.expander("팀장이 작성한 업무 배분 문맥"):
                    render_manager_context(latest_task["manager_context"])

    with received_tab:
        received_handoffs = console["received_handoffs"]
        st.caption(f"최근 팀 업무에서 받은 자료 {len(received_handoffs)}건")
        render_console_handoff_list(
            received_handoffs,
            employees_by_id,
            "received",
        )

    with result_tab:
        employee_result = console["result"]
        result_status_labels = {
            "running": "작성 중",
            "completed": "작성 완료",
            "failed": "작성 오류",
        }
        if employee_result is None:
            if latest_task is not None and employee["id"] == ACTIVE_EMPLOYEE_ID:
                st.caption("팀장이 작성한 최근 업무 배분 및 조율 내용")
                with st.container(border=True):
                    render_manager_context(latest_task["manager_context"])
            else:
                st.info("최근 팀 업무에서 이 직원이 별도로 저장한 결과가 없습니다.")
        else:
            st.caption(
                f"상태: {result_status_labels.get(employee_result['status'], employee_result['status'])} · "
                f"최근 갱신: {employee_result['updated_at']}"
            )
            result_content = employee_result["output"] or employee_result["error"]
            with st.container(border=True):
                st.markdown(result_content or "결과를 작성하고 있습니다.")

    with sent_tab:
        sent_handoffs = console["sent_handoffs"]
        st.caption(f"최근 팀 업무에서 보낸 자료 {len(sent_handoffs)}건")
        render_console_handoff_list(
            sent_handoffs,
            employees_by_id,
            "sent",
        )

    with review_tab:
        reviews = console["reviews"]
        review_targets = console["review_targets"]
        targeted_reviews = console["targeted_reviews"]
        rework_handoffs = console["rework_handoffs"]
        verdict_labels = {
            "passed": "통과",
            "rework_requested": "재작업 요청",
            "failed": "검수 실패",
        }
        target_status_labels = {
            "rework_requested": "재작업 요청됨",
            "resubmitted": "수정본 제출됨",
            "passed": "2차 검수 통과",
            "unresolved": "2차 검수 미통과",
        }
        if not reviews and not targeted_reviews and not rework_handoffs:
            st.info("이 직원과 직접 연결된 검수 또는 재작업 기록이 없습니다.")
        if targeted_reviews:
            st.markdown("**이 직원의 결과에 대한 검수 기록**")
            for target_index, target in enumerate(targeted_reviews):
                reviewer = employees_by_id.get(target["reviewer_employee_id"])
                reviewer_name = (
                    reviewer["name"] if reviewer else target["reviewer_employee_id"]
                )
                target_state = target_status_labels.get(
                    target["status"],
                    target["status"],
                )
                with st.expander(
                    f"{target['review_round']}차 · {reviewer_name} · {target_state}",
                    expanded=target_index == len(targeted_reviews) - 1,
                ):
                    st.markdown(target["feedback"] or "저장된 검수 의견이 없습니다.")
                    if target.get("rework_output"):
                        st.markdown("**제출한 재작업본**")
                        st.markdown(target["rework_output"])
                    st.caption(f"기록 시간: {target['updated_at']}")
        if reviews:
            st.markdown("**이 직원이 수행한 검수 기록**")
        for review in reviews:
            verdict_label = verdict_labels.get(review["verdict"], review["verdict"])
            target_names = [
                employees_by_id.get(target["target_employee_id"], {}).get(
                    "name",
                    target["target_employee_id"],
                )
                for target in review_targets
                if target["review_id"] == review["id"]
            ]
            target_summary = ", ".join(target_names) or "대상 없음"
            with st.expander(
                f"{review['review_round']}차 검수 · {verdict_label} · {target_summary}",
                expanded=review is reviews[-1],
            ):
                st.markdown(review["feedback"] or "저장된 검수 의견이 없습니다.")
                st.caption(f"기록 시간: {review['created_at']}")
        if rework_handoffs and not targeted_reviews:
            st.markdown("**이전 방식으로 저장된 재작업 전달**")
            render_console_handoff_list(
                rework_handoffs,
                employees_by_id,
                "received",
            )

    with direct_chat_tab:
        st.markdown("**역할 설명 및 업무 지침**")
        st.write(employee["role_description"])
        first_row = st.columns(3)
        actions = [
            ("인사하기", "greeting"),
            ("현재 상태", "status"),
            ("역할 확인", "role"),
        ]
        for column, (label, action_key) in zip(first_row, actions):
            with column:
                if st.button(
                    label,
                    key=f"dialog_{action_key}_{employee['id']}",
                    use_container_width=True,
                ):
                    st.session_state.office_dialog_action = action_key
                    st.rerun()

        second_row = st.columns(3)
        actions = [
            ("기억 확인", "memory"),
            ("최근 결과", "result"),
        ]
        for column, (label, action_key) in zip(second_row[:2], actions):
            with column:
                if st.button(
                    label,
                    key=f"dialog_{action_key}_{employee['id']}",
                    use_container_width=True,
                ):
                    st.session_state.office_dialog_action = action_key
                    st.rerun()
        with second_row[2]:
            if st.button(
                "직접 대화하기",
                key=f"dialog_chat_{employee['id']}",
                type="primary",
                use_container_width=True,
            ):
                clear_office_employee_dialog()
                st.session_state.chat_employee_request = employee["id"]
                st.session_state.workspace_view_request = "💬 대화"
                st.rerun()


def clear_office_meeting_dialog() -> None:
    """회의실 대화상자의 선택 상태를 정리합니다."""

    st.session_state.pop("office_meeting_room_open", None)


@st.dialog(
    "팀 회의실",
    width="large",
    dismissible=True,
    on_dismiss=clear_office_meeting_dialog,
)
def show_office_meeting_dialog(
    project: dict,
    employees: list[dict],
    latest_task: dict | None,
) -> None:
    """현재 프로젝트의 실제 저장된 팀 회의 기록을 보여줍니다."""

    employees_by_id = {employee["id"]: employee for employee in employees}
    participant_html: list[str] = []
    for employee in employees:
        if not employee["enabled"]:
            continue
        sprite = employee_sprite_data(employee["id"])
        participant = (
            f'<img src="{sprite}" alt="{html.escape(employee["name"], quote=True)}">'
            if sprite
            else profile_avatar_content(employee)
        )
        participant_html.append(
            f'<div><i>{participant}</i><span>{html.escape(employee["name"])}</span></div>'
        )

    background = meeting_room_background_data()
    st.markdown(
        f"""
        <div class="meeting-dialog-hero" style="background-image:url('{background}')">
            <div class="meeting-dialog-shade"></div>
            <div class="meeting-dialog-title">
                <span>YOUFFICE TEAM CONFERENCE</span>
                <strong>{html.escape(project['name'])}</strong>
                <p>각 직원의 실제 결과와 저장된 발언을 확인하는 회의실입니다.</p>
            </div>
            <div class="meeting-dialog-participants">{''.join(participant_html)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if latest_task is None:
        st.info("아직 시작된 팀 업무가 없습니다. 유키에게 업무를 요청하면 회의 기록이 이곳에 표시됩니다.")
        return

    meeting = get_team_meeting(latest_task["id"])
    if meeting is None:
        st.info("최근 업무에서는 아직 팀 회의가 시작되지 않았습니다.")
        return

    meeting_status_labels = {
        "running": "회의 진행 중",
        "completed": "회의 완료",
        "partial": "일부 의견 확인 필요",
        "failed": "회의 결과 확인 필요",
    }
    turns = list_meeting_turns(meeting["id"])
    st.caption(
        f"상태: {meeting_status_labels.get(meeting['status'], meeting['status'])} · "
        f"저장된 발언 {len(turns)}건"
    )
    if not turns:
        st.info("회의가 시작되었지만 아직 저장된 직원 발언은 없습니다.")
        return

    for turn in turns:
        speaker = employees_by_id.get(turn["employee_id"])
        speaker_name = speaker["name"] if speaker else turn["employee_id"]
        turn_label = "회의 결론" if turn["turn_type"] == "conclusion" else "직원 의견"
        with st.container(border=True):
            st.markdown(f"**{speaker_name} · {turn_label}**")
            st.markdown(turn["content"])


def clear_office_handoff_dialog() -> None:
    """업무 전달 자료 대화상자의 선택 상태를 정리합니다."""

    st.session_state.pop("office_selected_handoff_id", None)


@st.dialog(
    "전달 자료 확인",
    width="large",
    dismissible=True,
    on_dismiss=clear_office_handoff_dialog,
)
def show_office_handoff_dialog(
    handoff: dict,
    employees: list[dict],
    project: dict,
) -> None:
    """직원 사이에 실제로 저장된 최근 전달 내용을 바로 표시합니다."""

    employees_by_id = {employee["id"]: employee for employee in employees}
    sender = employees_by_id.get(handoff["from_employee_id"])
    receiver = employees_by_id.get(handoff["to_employee_id"])
    sender_name = sender["name"] if sender else handoff["from_employee_id"]
    receiver_name = receiver["name"] if receiver else handoff["to_employee_id"]
    sender_avatar = profile_avatar_content(sender) if sender else "📤"
    receiver_avatar = profile_avatar_content(receiver) if receiver else "📥"

    st.markdown(
        f"""
        <div class="handoff-dialog-route">
            <div class="handoff-dialog-person">
                <i>{sender_avatar}</i><strong>{html.escape(sender_name)}</strong><span>보낸 직원</span>
            </div>
            <div class="handoff-dialog-arrow"><b>문서 전달</b><span>→</span></div>
            <div class="handoff-dialog-person">
                <i>{receiver_avatar}</i><strong>{html.escape(receiver_name)}</strong><span>받은 직원</span>
            </div>
        </div>
        <div class="handoff-dialog-project">현재 프로젝트 · {html.escape(project['name'])}</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("#### 전달된 내용")
    with st.container(border=True):
        st.markdown(handoff["content"] or "전달된 내용이 비어 있습니다.")
    if handoff.get("created_at"):
        st.caption(f"전달 기록 시간: {handoff['created_at']}")

    if receiver is not None and st.button(
        f"{receiver_name}에게 바로 물어보기",
        key=f"handoff_chat_{handoff['id']}",
        type="primary",
        use_container_width=True,
    ):
        clear_office_handoff_dialog()
        st.session_state.chat_employee_request = receiver["id"]
        st.session_state.workspace_view_request = "💬 대화"
        st.rerun()
