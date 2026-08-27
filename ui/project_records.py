"""프로젝트 자료·출처·기억·사실 기록을 관리하는 Streamlit UI."""

from __future__ import annotations

import re
import sqlite3

import streamlit as st

from database import (
    add_fact_record,
    add_memory,
    add_project_record,
    add_source,
    delete_fact_record,
    delete_memory,
    delete_project_record,
    delete_source,
    update_fact_record_source,
    update_project_record_status,
    update_source_status,
)


@st.dialog("프로젝트 자료 및 출처 관리", width="large")
def show_source_manager(project_id: int, sources: list[dict]) -> None:
    """프로젝트별 출처를 추가하고 확인 상태를 관리합니다."""

    add_tab, manage_tab = st.tabs(["자료 추가", f"등록 자료 ({len(sources)})"])
    with add_tab:
        st.caption(
            "로컬 AI가 웹페이지를 직접 열지는 못합니다. 주소와 함께 핵심 내용을 "
            "메모에 적어두면 직원들이 프로젝트 근거로 활용합니다."
        )
        with st.form(f"source_add_form_{project_id}"):
            title = st.text_input("자료명", max_chars=150)
            url = st.text_input(
                "웹 주소 (선택)",
                max_chars=1000,
                placeholder="https://...",
            )
            source_type = st.selectbox(
                "자료 유형",
                ["공식 문서", "논문", "제품 사양", "기사", "영상", "사용자 메모", "기타"],
            )
            notes = st.text_area(
                "핵심 내용 및 활용 메모",
                height=150,
                max_chars=3000,
            )
            submitted = st.form_submit_button("자료 저장", use_container_width=True)

        if submitted:
            normalized_url = url.strip()
            if not title.strip():
                st.error("자료명을 입력해주세요.")
            elif normalized_url and not re.match(r"^https?://", normalized_url, re.I):
                st.error("웹 주소는 http:// 또는 https://로 시작해야 합니다.")
            elif not normalized_url and not notes.strip():
                st.error("웹 주소가 없다면 핵심 내용을 메모에 입력해주세요.")
            else:
                try:
                    add_source(
                        project_id,
                        title.strip(),
                        normalized_url,
                        source_type,
                        notes.strip(),
                    )
                except sqlite3.Error as error:
                    st.error(f"자료를 저장하지 못했습니다: {error}")
                else:
                    st.rerun()

    with manage_tab:
        if not sources:
            st.info("등록된 자료가 없습니다.")
        status_options = ["unverified", "verified", "rejected"]
        status_labels = {
            "unverified": "미확인",
            "verified": "확인됨",
            "rejected": "사용 제외",
        }
        for source in sources:
            with st.container(border=True):
                st.markdown(f"**{source['title']}** · {source['source_type']}")
                if source["url"]:
                    st.caption(source["url"])
                if source["notes"]:
                    st.write(source["notes"])
                status_column, save_column, delete_column = st.columns(
                    [0.52, 0.24, 0.24], vertical_alignment="bottom"
                )
                with status_column:
                    selected_status = st.selectbox(
                        "확인 상태",
                        status_options,
                        index=status_options.index(source["verification_status"]),
                        format_func=lambda status: status_labels[status],
                        key=f"source_status_{source['id']}",
                    )
                with save_column:
                    if st.button(
                        "상태 저장",
                        key=f"source_status_save_{source['id']}",
                        use_container_width=True,
                    ):
                        try:
                            update_source_status(source["id"], selected_status)
                        except (sqlite3.Error, ValueError) as error:
                            st.error(f"자료 상태를 저장하지 못했습니다: {error}")
                        else:
                            st.rerun()
                with delete_column:
                    if st.button(
                        "삭제",
                        key=f"source_delete_{source['id']}",
                        use_container_width=True,
                    ):
                        try:
                            delete_source(source["id"])
                        except (sqlite3.Error, ValueError) as error:
                            st.error(f"자료를 삭제하지 못했습니다: {error}")
                        else:
                            st.rerun()


@st.dialog("프로젝트 기록 관리", width="large")
def show_record_manager(
    project_id: int,
    sources: list[dict],
    memories: list[dict],
    records: list[dict],
    fact_records: list[dict],
) -> None:
    """장기 기억·기록과 근거가 연결된 사실을 프로젝트별로 관리합니다."""

    add_tab, memory_tab, record_tab, fact_tab = st.tabs(
        [
            "기록 추가",
            f"장기 기억 ({len(memories)})",
            f"결정·오류 ({len(records)})",
            f"사실·근거 ({len(fact_records)})",
        ]
    )
    with add_tab:
        with st.form(f"project_record_add_{project_id}"):
            record_kind = st.selectbox("기록 종류", ["장기 기억", "결정", "오류"])
            title = st.text_input(
                "제목",
                max_chars=150,
                placeholder="예: 카메라 설치 높이",
            )
            content = st.text_area(
                "기록 내용",
                height=150,
                max_chars=3000,
                placeholder="나중에도 직원들이 기억해야 할 내용을 적어주세요.",
            )
            submitted = st.form_submit_button("기록 저장", use_container_width=True)
        if submitted:
            if not title.strip() or not content.strip():
                st.error("제목과 기록 내용을 모두 입력해주세요.")
            else:
                try:
                    if record_kind == "장기 기억":
                        add_memory(
                            project_id,
                            f"{title.strip()}: {content.strip()}",
                            category="general",
                        )
                    else:
                        add_project_record(
                            project_id,
                            "decision" if record_kind == "결정" else "error",
                            title.strip(),
                            content.strip(),
                        )
                except sqlite3.Error as error:
                    st.error(f"기록을 저장하지 못했습니다: {error}")
                else:
                    st.rerun()

    with memory_tab:
        if not memories:
            st.info("저장된 장기 기억이 없습니다.")
        for memory in memories:
            with st.container(border=True):
                st.write(memory["content"])
                st.caption(f"분류: {memory['category']} · {memory['created_at']}")
                if st.button(
                    "기억 삭제",
                    key=f"memory_delete_{memory['id']}",
                ):
                    delete_memory(memory["id"])
                    st.rerun()

    with record_tab:
        if not records:
            st.info("저장된 결정·오류 기록이 없습니다.")
        type_labels = {"decision": "결정", "error": "오류"}
        status_labels = {"open": "진행 중", "resolved": "해결됨"}
        for record in records:
            with st.container(border=True):
                st.markdown(
                    f"**[{type_labels[record['record_type']]}] {record['title']}**"
                )
                st.write(record["content"])
                st.caption(status_labels[record["status"]])
                status_column, delete_column = st.columns(2)
                with status_column:
                    next_status = "resolved" if record["status"] == "open" else "open"
                    next_label = "해결됨으로 표시" if next_status == "resolved" else "다시 열기"
                    if st.button(
                        next_label,
                        key=f"record_status_{record['id']}",
                        use_container_width=True,
                    ):
                        update_project_record_status(record["id"], next_status)
                        st.rerun()
                with delete_column:
                    if st.button(
                        "기록 삭제",
                        key=f"record_delete_{record['id']}",
                        use_container_width=True,
                    ):
                        delete_project_record(record["id"])
                        st.rerun()

    with fact_tab:
        st.caption(
            "확정 사실·사용자 결정·제안·미확인을 분리해 저장합니다. "
            "출처는 같은 프로젝트에 등록된 자료만 연결할 수 있습니다."
        )
        source_by_id = {source["id"]: source for source in sources}
        source_options = [None, *source_by_id]
        source_status_labels = {
            "unverified": "미확인",
            "verified": "확인됨",
            "rejected": "사용 제외",
        }
        fact_type_labels = {
            "confirmed_fact": "확정 사실",
            "user_decision": "사용자 결정",
            "proposal": "제안",
            "unverified": "미확인",
            "limitation": "한계",
        }

        def source_option_label(source_id: int | None) -> str:
            if source_id is None:
                return "직접 입력(별도 출처 없음)"
            source = source_by_id[source_id]
            status = source_status_labels.get(
                source["verification_status"],
                "미확인",
            )
            return f"{source['title']} · {status}"

        with st.form(f"fact_record_add_{project_id}"):
            fact_type = st.selectbox(
                "분류",
                list(fact_type_labels),
                format_func=lambda value: fact_type_labels[value],
            )
            fact_content = st.text_area(
                "내용",
                height=130,
                max_chars=3000,
                placeholder="예: 시연은 9월 첫째 주에 진행한다.",
            )
            selected_source_id = st.selectbox(
                "근거 자료 (선택)",
                source_options,
                format_func=source_option_label,
            )
            fact_submitted = st.form_submit_button(
                "사실·근거 저장",
                use_container_width=True,
            )
        if fact_submitted:
            try:
                add_fact_record(
                    project_id,
                    fact_type,
                    fact_content,
                    origin="user",
                    source_id=selected_source_id,
                )
            except (sqlite3.Error, ValueError) as error:
                st.error(f"사실·근거를 저장하지 못했습니다: {error}")
            else:
                st.rerun()

        if not fact_records:
            st.info("근거가 연결된 사실 기록이 없습니다.")
        for fact_record in fact_records:
            with st.container(border=True):
                fact_label = fact_type_labels.get(fact_record["fact_type"], "기록")
                origin_label = {
                    "user": "사용자",
                    "ai": "AI 분류",
                    "system": "시스템",
                }.get(fact_record["origin"], "알 수 없음")
                st.markdown(f"**[{fact_label}]** · {origin_label}")
                st.write(fact_record["content"])
                current_source_id = fact_record.get("source_id")
                if current_source_id in source_by_id:
                    source_caption = source_option_label(current_source_id)
                elif current_source_id is None:
                    source_caption = "직접 입력(별도 출처 없음)"
                else:
                    source_caption = "연결된 출처 정보를 찾을 수 없음"
                st.caption(f"현재 근거: {source_caption}")
                source_index = (
                    source_options.index(current_source_id)
                    if current_source_id in source_options
                    else 0
                )
                source_column, save_column, delete_column = st.columns(
                    [0.56, 0.22, 0.22]
                )
                with source_column:
                    next_source_id = st.selectbox(
                        "근거 자료",
                        source_options,
                        index=source_index,
                        format_func=source_option_label,
                        key=f"fact_source_{fact_record['id']}",
                    )
                with save_column:
                    if st.button(
                        "근거 저장",
                        key=f"fact_source_save_{fact_record['id']}",
                        use_container_width=True,
                    ):
                        try:
                            update_fact_record_source(
                                fact_record["id"],
                                next_source_id,
                            )
                        except (sqlite3.Error, ValueError) as error:
                            st.error(f"근거를 저장하지 못했습니다: {error}")
                        else:
                            st.rerun()
                with delete_column:
                    if st.button(
                        "사실 삭제",
                        key=f"fact_delete_{fact_record['id']}",
                        use_container_width=True,
                    ):
                        delete_fact_record(fact_record["id"])
                        st.rerun()
