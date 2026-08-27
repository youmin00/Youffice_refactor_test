"""YOUFFICE 사이드바 UI를 표시합니다."""

import html

from ui.chat import profile_avatar_content


def employee_card_html(employee: dict, is_current_employee: bool) -> str:
    """사이드바에 표시할 직원 카드 HTML을 만듭니다."""

    active_class = " active" if employee["enabled"] else ""
    if is_current_employee:
        status = "활성 · 현재 대화 가능"
    elif employee["enabled"]:
        status = "활성 · 팀 지원 중"
    else:
        status = "비활성"
    return f"""
        <div class="employee-card{active_class}">
            <div class="employee-avatar">
                {profile_avatar_content(employee)}<span class="status-dot"></span>
            </div>
            <div class="employee-copy">
                <div class="employee-name">{html.escape(str(employee['name']))}</div>
                <div class="employee-status">
                    {html.escape(str(employee['title']))} · {status}
                </div>
            </div>
        </div>
    """
