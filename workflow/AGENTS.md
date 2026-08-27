# Workflow 담당 규칙

이 폴더는 업무 배정, 직원 실행, 회의, 검수, 보고 흐름만 담당한다.

수정 가능:
- assignment.py
- engine.py
- employee_execution.py
- meeting.py
- errors.py
- review.py
- review_execution.py
- final_report_execution.py
- recovery.py
- reporting.py

필수 원칙:
- 예외 내용을 숨기지 않는다.
- 실패 상태를 DB에 기록한다.
- 중복 실행을 막는다.
- 작업 중 서버 종료 후 남은 상태를 복구한다.
- database.py 함수는 존재 여부와 인자를 확인한 뒤 사용한다.

수정 금지:
- UI 디자인
- 캐릭터 리소스
- 직원 성격과 프롬프트의 대규모 변경
