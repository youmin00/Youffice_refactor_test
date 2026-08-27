# YOUFFICE 데이터베이스 지도

`database.py` 전체를 읽기 전에 작업 도메인과 함수 이름을 이 문서에서 먼저 찾는다.
줄 번호는 현재 탐색용이며, 코드를 옮길 때는 함수 이름을 기준으로 검색한다.

## 공통 규칙

- 실제 운영 DB는 `data/youffice.db` 하나다.
- 테스트는 반드시 별도의 임시 `database_path`를 전달한다.
- 모든 연결은 외래키 검사를 활성화하며 프로젝트 경계를 넘는 참조를 차단한다.
- UI에서 제거된 시작일·완료일·예산 열은 기존 데이터 호환을 위해 스키마에 유지한다.
- 스키마 변경과 함수 이동을 한 작업에서 동시에 수행하지 않는다.

## 도메인별 함수 위치

| 도메인 | 현재 범위 | 공개 함수 |
|---|---:|---|
| 연결·스키마 | 12–507 | `initialize_database` |
| 프로젝트 저장·삭제 | 520–578 | `create_project`, `delete_project` |
| 대화 저장·삭제 | 579–638 | `add_message`, `clear_project_messages` |
| 프로젝트·대화 조회 | `database_project_queries.py` | `list_projects`, `get_project`, `list_messages` — `database.py`가 기존 공개 API를 유지하는 연결 창구 |
| 팀 업무·제어·보완 질문 저장·변경 | 650–879 | `create_team_task`, `update_team_task_status`, `create_task_control`, `update_task_control_state`, `create_or_get_clarification_request`, `answer_clarification_request` |
| 팀 업무·제어·보완 질문 조회 | `database_workflow_queries.py` | `get_task_for_source_message`, `get_team_task`, `get_task_control`, `get_pending_clarification_request` |
| 직원 상태·결과·인수인계 저장 | 887–1008 | `set_employee_activity`, `clear_employee_activities`, `add_handoff`, `start_employee_result`, `finish_employee_result` |
| 직원 활동·업무 이력 조회 | `database_activity_queries.py` | `list_employee_activities`, `list_team_tasks`, `list_employee_results`, `list_handoffs` — `database.py`가 기존 공개 API를 유지하는 연결 창구 |
| 팀 회의 저장·종료 | 1023–1104 | `create_team_meeting`, `add_meeting_turn`, `finish_team_meeting` |
| 팀 회의 조회 | `database_meeting_queries.py` | `get_team_meeting`, `list_meeting_turns` — `database.py`가 기존 공개 API를 유지하는 연결 창구 |
| 자료·사실 근거 | 1182–1467 | `add_source`, `add_fact_record`, `list_fact_records`, `update_fact_record_source`, `delete_fact_record`, `list_sources`, `update_source_status`, `delete_source` |
| 팀장 계획 승인 | 1468–1535 | `create_or_get_approval`, `update_approval` |
| 검수·재작업 저장 | 1477–1562 | `add_review`, `add_review_targets`, `mark_review_targets_resubmitted` |
| 검수·재작업 조회 | `database_review_queries.py` | `list_review_targets`, `list_reviews` — `database.py`가 기존 공개 API를 유지하는 연결 창구 |
| 장기 기억·결정·오류 저장·변경 | 1587–1712 | `add_memory`, `delete_memory`, `add_project_record`, `update_project_record_status`, `delete_project_record` |
| 장기 기억·결정·오류 조회 | `database_context_queries.py` | `list_memories`, `list_project_records` |
| 보고서·구조화 항목·승인 저장·수정 | 1713–1981 | `add_report`, `save_report_structured_data`, `create_or_get_report_approval`, `update_report_approval` |
| 보고서·구조화 항목·승인 조회 | `database_report_queries.py` | `list_reports`, `get_report_structured_data`, `list_report_approvals` — `database.py`가 기존 공개 API를 유지하는 연결 창구 |

## 주요 소비 모듈

| 목적 | 먼저 볼 소비 모듈 |
|---|---|
| 프로젝트와 대화 조립 | `app.py`, `ui/projects.py` |
| 프로젝트 자료·기억·사실 | `ui/project_records.py` |
| 직원 실행 | `workflow/employee_execution.py` |
| 팀 회의 | `workflow/meeting.py` |
| 검수·재작업 | `workflow/review_execution.py` |
| 최종 보고 저장 | `workflow/final_report_execution.py` |
| 중단 복구·보완 질문 | `workflow/recovery.py` |
| 보고서 생성·수정 | `workflow/reporting.py`, `ui/report_revision.py` |
| 오피스 조회 화면 | `ui/office.py`, `ui/office_dialogs.py` |

## 분리 전 안전 조건

1. `tools/test_database_api_contract.py`에서 공개 API 시그니처를 유지한다.
2. `tools/test_reference_integrity.py`에서 프로젝트 간 잘못된 연결을 계속 차단한다.
3. 운영 DB 대신 임시 DB로 생성·조회·수정·삭제 흐름을 검사한다.
4. 첫 분리 후보는 스키마가 아니라 조회 전용 함수 묶음이다.
5. `database.py`는 당분간 기존 함수의 호환 진입점으로 유지한다.
