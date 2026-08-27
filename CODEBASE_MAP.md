# YOUFFICE 코드 지도

전체 폴더를 검색하기 전에 아래에서 작업 영역을 먼저 고른다.

| 작업 종류 | 먼저 볼 파일 |
|---|---|
| 앱 조립·세션·사이드바 연결 | `app.py` |
| 프로젝트 생성·삭제·요약 화면 | `ui/projects.py` |
| 프로젝트 생성 후 대화형 공동 설계·팀 계획 전환 안내 | `ui/project_onboarding.py` |
| 프로젝트 자료·출처·기억·사실 관리 화면 | `ui/project_records.py` |
| 초보자용 웹·부품 검색 진입과 고급 자료 관리 | `ui/project_tools.py` |
| 직원·부서 설정과 조직 프로필 파일 | `ui/organization.py` |
| 채팅 표시 | `ui/chat.py` |
| 오피스 화면 | `ui/office.py` |
| 오피스 직원·회의·인수인계 dialog | `ui/office_dialogs.py` |
| 저장·채팅 최종 보고서 수정 dialog | `ui/report_revision.py` |
| 업무 기록 상세·팀장 계획 수정 화면 | `ui/team_work.py` |
| 전체 스타일 | `ui/styles.py` |
| Tavily·ChatGPT 조사 화면 | `ui/internet_research.py` |
| 조사·부품 호환 판정 | `workflow/internet_research.py` |
| 팀 업무 실행 | `workflow/engine.py` |
| 실행 전 두 직원 의견 요청·유키 요약 | `workflow/team_consultation.py` |
| Gemini 조건 정리·Claude 교차 검토 | `workflow/external_review.py` |
| 직원별 독립 실행·단계별 병렬 실행 | `workflow/employee_execution.py` |
| 순차 팀 회의·팀장 회의 결론 | `workflow/meeting.py` |
| 1차 검수·재작업·2차 검수 실행 | `workflow/review_execution.py` |
| 검수 완료 결과의 최종 보고 생성·저장 | `workflow/final_report_execution.py` |
| 보고서 생성·재시도 | `workflow/reporting.py` |
| 업무 배정 | `workflow/assignment.py` |
| 팀장 계획 수정·저장 | `workflow/plan_revision.py` |
| 업무 단계 공통 오류 표시 | `workflow/errors.py` |
| AI 프로젝트 문맥 | `conversation/prompts.py` |
| 유키 아이디어 대화·명시적 팀 계획 전환 규칙 | `conversation/project_collaboration.py` |
| 대화 단계 판별·단계별 짧은 응답 지침 | `conversation/dialogue_state.py` |
| AI 응답 복구·사실 보호 | `conversation/response_recovery.py` |
| DB 도메인·함수 위치 안내 | `DATABASE_MAP.md` |
| DB 스키마·호환 진입점 | `database.py` |
| 직원 활동·업무 이력 읽기 전용 SQL | `database_activity_queries.py` |
| 프로젝트·대화 읽기 전용 SQL | `database_project_queries.py` |
| 팀 회의 읽기 전용 SQL | `database_meeting_queries.py` |
| 검수·재작업 읽기 전용 SQL | `database_review_queries.py` |
| 보고서·구조화 항목·승인 읽기 전용 SQL | `database_report_queries.py` |
| 출처·사실 읽기 전용 SQL | `database_source_queries.py` |
| 팀 업무·제어·보완 질문 읽기 전용 SQL | `database_workflow_queries.py` |
| 장기 기억·결정·오류 읽기 전용 SQL | `database_context_queries.py` |
| 표준 실행·시작 전 점검 | `tools/start_youffice.ps1` |
| 외부 AI 키·모델명 안전 설정 | `EXTERNAL_AI_SETUP.md` |
| Windows 실행 바로가기 | `YOUFFICE_실행.vbs` |
| 점검 도구 | `tools/` |
| 회의→검수→보고 순서 회귀 검사 | `tools/test_workflow_stage_order.py` |
| DB 공개 API·임시 DB 흐름 검사 | `tools/test_database_api_contract.py` |
| 프로젝트 생성→아이디어 대화→팀 계획→승인 단계 검사 | `tools/test_project_onboarding.py` |
| 웹·디바이스마트 검색 진입·대화 맥락 자동 채움 검사 | `tools/test_project_tools.py` |

## 기본 검색 범위

코드 검색에서는 보통 다음 폴더를 제외한다.

```text
data/**
.venv/**
Youffice_stage5_success_backup_20260807_0222/**
assets/**
static/**
```

백업은 `data/codex_backups/`, 이미지·애니메이션은 `assets/`와 `static/`에 있다.
해당 작업이 아니면 열지 않는다.

## 현재 유지할 핵심 파일

1. `workflow/engine.py`: 업무 시작·단계 호출·상태 마감 조정 역할로 유지
2. `database.py`: 연결·스키마·저장·수정·삭제와 기존 공개 API의 호환 진입점으로 유지
3. `ui/styles.py`: 공통 CSS만 담고 있으며 스타일 작업 외에는 읽지 않는다

## 실행 파일 역할

- 실제 실행 로직은 `tools/start_youffice.ps1` 한 곳에서 관리한다. 이 스크립트는
  현재 폴더의 `.venv`를 직접 사용하고, 사전 점검 후에만 `127.0.0.1:8501`을 연다.
- `YOUFFICE_실행.vbs`는 더블클릭 실행을 위한 얇은 바로가기이며, 별도의 앱 실행
  로직을 갖지 않는다. 실행 로그를 직접 볼 필요가 있을 때는 PowerShell에서
  `tools/start_youffice.ps1`을 직접 실행한다.
- 8501이 이미 사용 중이면 실행 중인 프로세스를 자동 종료하지 않고 PID를 알려 준다.
  종료할 대상과 경로를 확인한 뒤에만 사용자가 다시 실행한다.

한 번에 하나만 분리하고 매번 문법 → import → AppTest → 임시 서버 검사를 한다.
