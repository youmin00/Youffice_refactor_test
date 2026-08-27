"""직원·부서 설정과 조직 프로필 파일 관리를 담당합니다."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from uuid import uuid4

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMPLOYEE_DATA_FILE = PROJECT_ROOT / "data" / "employees.json"
STATIC_DIR = PROJECT_ROOT / "static"
ACTIVE_EMPLOYEE_ID = "project_manager"
MAX_PROFILE_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_PROFILE_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def load_organization() -> tuple[list[dict], list[dict]]:
    """프로젝트 폴더에 저장된 부서와 직원 프로필을 불러옵니다."""

    data = json.loads(EMPLOYEE_DATA_FILE.read_text(encoding="utf-8"))
    departments = data.get("departments")
    employees = data.get("employees")
    if not isinstance(departments, list) or not departments:
        raise ValueError("departments 목록이 없거나 비어 있습니다.")
    if not isinstance(employees, list) or not employees:
        raise ValueError("employees 목록이 없거나 비어 있습니다.")

    department_ids = set()
    for department in departments:
        if not isinstance(department, dict):
            raise ValueError("부서 정보 형식이 올바르지 않습니다.")
        if not {"id", "name"}.issubset(department):
            raise ValueError("부서 정보에 필요한 항목이 누락되었습니다.")
        department_ids.add(department["id"])

    required_fields = {
        "id",
        "enabled",
        "name",
        "department_id",
        "title",
        "role_description",
        "emoji",
        "image_data",
    }
    for employee in employees:
        if not isinstance(employee, dict):
            raise ValueError("직원 정보 형식이 올바르지 않습니다.")
        if not required_fields.issubset(employee):
            raise ValueError("직원 정보에 필요한 항목이 누락되었습니다.")
        if employee["department_id"] not in department_ids:
            raise ValueError("직원에게 지정된 부서를 찾을 수 없습니다.")

    if not any(employee["id"] == ACTIVE_EMPLOYEE_ID for employee in employees):
        raise ValueError("현재 대화 담당 직원 정보가 없습니다.")

    return departments, employees


def save_organization(
    departments: list[dict],
    employees: list[dict],
) -> None:
    """부서와 직원 프로필을 UTF-8 JSON 파일에 안전하게 저장합니다."""

    EMPLOYEE_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = EMPLOYEE_DATA_FILE.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(
            {"departments": departments, "employees": employees},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temporary_file.replace(EMPLOYEE_DATA_FILE)
    sync_static_profile_images(employees)


def sync_static_profile_images(employees: list[dict]) -> None:
    """프로필 사진을 브라우저 캐시가 가능한 정적 파일로 동기화합니다."""

    profile_directory = STATIC_DIR / "profiles"
    profile_directory.mkdir(parents=True, exist_ok=True)
    mime_extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }
    for employee in employees:
        image_data = employee.get("image_data", "")
        if not isinstance(image_data, str) or ";base64," not in image_data:
            continue
        header, encoded = image_data.split(",", 1)
        mime_type = header.removeprefix("data:").removesuffix(";base64")
        extension = mime_extensions.get(mime_type)
        if extension is None:
            continue
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            continue
        (profile_directory / f"{employee['id']}.{extension}").write_bytes(
            image_bytes
        )


def department_name(department_id: str, departments: list[dict]) -> str:
    """부서 ID에 해당하는 화면 표시 이름을 반환합니다."""

    for department in departments:
        if department["id"] == department_id:
            return department["name"]
    return "미지정 부서"


def create_employee(
    name: str,
    department_id: str,
    title: str,
    role_description: str,
) -> dict:
    """조직도에 저장할 새 직원 기본 프로필을 만듭니다."""

    return {
        "id": f"employee_{uuid4().hex}",
        "enabled": False,
        "name": name,
        "department_id": department_id,
        "title": title,
        "role_description": role_description,
        "emoji": "👤",
        "image_data": "",
    }


def delete_employee(employees: list[dict], employee_id: str) -> list[dict]:
    """현재 대화 담당자를 보호하면서 선택한 직원을 목록에서 제거합니다."""

    if employee_id == ACTIVE_EMPLOYEE_ID:
        raise ValueError("현재 대화 담당 직원은 삭제할 수 없습니다.")
    if not any(employee["id"] == employee_id for employee in employees):
        raise ValueError("삭제할 직원을 찾을 수 없습니다.")
    return [
        employee
        for employee in employees
        if employee["id"] != employee_id
    ]


def profile_image_data(uploaded_file) -> str:
    """업로드된 이미지를 JSON에 저장할 수 있는 데이터 주소로 변환합니다."""

    image_bytes = uploaded_file.getvalue()
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{uploaded_file.type};base64,{encoded_image}"


@st.dialog("직원 프로필 설정", width="large")
def show_profile_editor(
    employee: dict,
    employees: list[dict],
    departments: list[dict],
) -> None:
    """직원별 프로필 설정 대화상자를 표시하고 변경 내용을 저장합니다."""

    st.caption(f"{employee['name']}의 표시 정보와 AI 업무 지침을 설정합니다.")
    department_ids = [department["id"] for department in departments]
    current_department_index = department_ids.index(employee["department_id"])
    department_names = {
        department["id"]: department["name"] for department in departments
    }

    with st.form(f"profile_form_{employee['id']}"):
        new_enabled = st.toggle(
            "직원 활성화",
            value=employee["enabled"],
            disabled=employee["id"] == ACTIVE_EMPLOYEE_ID,
            help=(
                "활성화하면 조직도에 초록색으로 표시되고, 역할 설명이 "
                "현재 팀장의 지원 직원 지시문에 반영됩니다."
            ),
        )
        if employee["id"] == ACTIVE_EMPLOYEE_ID:
            st.caption("현재 대화 담당 직원은 항상 활성 상태로 유지됩니다.")

        name_column, department_column = st.columns(2)
        with name_column:
            new_name = st.text_input(
                "이름",
                value=employee["name"],
                max_chars=40,
            )
        with department_column:
            new_department_id = st.selectbox(
                "부서",
                options=department_ids,
                index=current_department_index,
                format_func=lambda department_id: department_names[department_id],
            )

        new_title = st.text_input(
            "직책",
            value=employee["title"],
            max_chars=40,
        )
        new_role_description = st.text_area(
            "역할 설명 및 업무 지침",
            value=employee["role_description"],
            max_chars=1000,
            height=150,
            help=(
                "이 직원이 어떤 역할을 맡고, 어떤 기준으로 작업해야 하는지 "
                "자연어로 작성해주세요. 현재 대화 담당 직원의 AI 지시문에 반영됩니다."
            ),
        )

        image_column, remove_column = st.columns([0.65, 0.35])
        with image_column:
            uploaded_image = st.file_uploader(
                "프로필 사진",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"profile_image_{employee['id']}",
                help="JPG, PNG 또는 WEBP 이미지를 2MB 이하로 올려주세요.",
                max_upload_size=2,
            )
        with remove_column:
            remove_image = st.checkbox(
                "현재 사진 삭제",
                value=False,
                disabled=not bool(employee["image_data"]),
            )

        submitted = st.form_submit_button(
            "프로필 저장",
            use_container_width=True,
        )

    if not submitted:
        return

    if not new_name.strip() or not new_title.strip():
        st.error("이름과 직책은 비워둘 수 없습니다.")
        return
    if not new_role_description.strip():
        st.error("역할 설명 및 업무 지침을 입력해주세요.")
        return

    if uploaded_image is not None:
        if uploaded_image.type not in ALLOWED_PROFILE_IMAGE_TYPES:
            st.error("JPG, PNG 또는 WEBP 이미지만 사용할 수 있습니다.")
            return
        if uploaded_image.size > MAX_PROFILE_IMAGE_BYTES:
            st.error("프로필 사진은 2MB 이하만 사용할 수 있습니다.")
            return

    updated_employee = dict(employee)
    updated_employee.update(
        {
            "enabled": (
                True if employee["id"] == ACTIVE_EMPLOYEE_ID else new_enabled
            ),
            "name": new_name.strip(),
            "department_id": new_department_id,
            "title": new_title.strip(),
            "role_description": new_role_description.strip(),
        }
    )
    if remove_image:
        updated_employee["image_data"] = ""
    if uploaded_image is not None:
        updated_employee["image_data"] = profile_image_data(uploaded_image)

    updated_employees = [
        updated_employee if item["id"] == employee["id"] else item
        for item in employees
    ]
    try:
        save_organization(departments, updated_employees)
    except OSError as error:
        st.error(f"프로필을 저장하지 못했습니다: {error}")
        return

    st.rerun()


@st.dialog("회사 조직도 설정", width="large")
def show_organization_editor(
    departments: list[dict],
    employees: list[dict],
) -> None:
    """부서 이름 변경과 직원 추가·삭제 기능을 제공합니다."""

    department_tab, add_employee_tab, delete_employee_tab = st.tabs(
        ["부서 관리", "직원 추가", "직원 삭제"]
    )
    department_names = {
        department["id"]: department["name"] for department in departments
    }

    with department_tab:
        st.caption("변경한 이름은 조직도와 직원 프로필의 부서 목록에 함께 반영됩니다.")
        with st.form("department_form"):
            changed_names = {}
            for department in departments:
                changed_names[department["id"]] = st.text_input(
                    f"{department['name']} 이름",
                    value=department["name"],
                    max_chars=40,
                    key=f"department_name_{department['id']}",
                )
            department_submitted = st.form_submit_button(
                "부서 이름 저장",
                use_container_width=True,
            )

        if department_submitted:
            normalized_names = [name.strip() for name in changed_names.values()]
            if any(not name for name in normalized_names):
                st.error("부서 이름은 비워둘 수 없습니다.")
            elif len({name.casefold() for name in normalized_names}) != len(
                normalized_names
            ):
                st.error("부서 이름은 서로 다르게 입력해주세요.")
            else:
                updated_departments = [
                    {
                        **department,
                        "name": changed_names[department["id"]].strip(),
                    }
                    for department in departments
                ]
                try:
                    save_organization(updated_departments, employees)
                except OSError as error:
                    st.error(f"부서 이름을 저장하지 못했습니다: {error}")
                else:
                    st.rerun()

    with add_employee_tab:
        st.caption("새 직원의 기본 프로필과 소속 부서를 지정합니다.")
        with st.form("add_employee_form"):
            new_name = st.text_input(
                "직원 이름",
                max_chars=40,
                placeholder="예: AI 구매 담당",
            )
            new_department_id = st.selectbox(
                "소속 부서",
                options=list(department_names),
                format_func=lambda department_id: department_names[department_id],
            )
            new_title = st.text_input(
                "직책",
                max_chars=40,
                placeholder="예: 구매 담당",
            )
            new_role_description = st.text_area(
                "역할 설명 및 업무 지침",
                max_chars=1000,
                height=150,
                placeholder=(
                    "이 직원이 담당할 업무와 반드시 지켜야 할 기준을 입력하세요."
                ),
            )
            employee_add_submitted = st.form_submit_button(
                "직원 추가",
                use_container_width=True,
            )

        if employee_add_submitted:
            normalized_name = new_name.strip()
            normalized_title = new_title.strip()
            normalized_role = new_role_description.strip()
            existing_names = {
                employee["name"].strip().casefold() for employee in employees
            }

            if not normalized_name or not normalized_title or not normalized_role:
                st.error("직원 이름, 직책, 역할 설명을 모두 입력해주세요.")
            elif normalized_name.casefold() in existing_names:
                st.error("같은 이름의 직원이 이미 있습니다.")
            else:
                new_employee = create_employee(
                    normalized_name,
                    new_department_id,
                    normalized_title,
                    normalized_role,
                )
                try:
                    save_organization(departments, [*employees, new_employee])
                except OSError as error:
                    st.error(f"직원을 추가하지 못했습니다: {error}")
                else:
                    st.rerun()

    with delete_employee_tab:
        deletable_employees = [
            employee
            for employee in employees
            if employee["id"] != ACTIVE_EMPLOYEE_ID
        ]
        st.caption("현재 대화를 담당하는 직원은 삭제할 수 없습니다.")

        if not deletable_employees:
            st.info("삭제할 수 있는 직원이 없습니다.")
        else:
            deletable_employee_ids = [
                employee["id"] for employee in deletable_employees
            ]
            deletable_employee_map = {
                employee["id"]: employee for employee in deletable_employees
            }
            with st.form("delete_employee_form"):
                employee_to_delete_id = st.selectbox(
                    "삭제할 직원",
                    options=deletable_employee_ids,
                    format_func=lambda employee_id: (
                        f"{deletable_employee_map[employee_id]['name']} · "
                        f"{department_names[deletable_employee_map[employee_id]['department_id']]}"
                    ),
                )
                delete_confirmed = st.checkbox(
                    "선택한 직원과 프로필 정보를 삭제하는 것에 동의합니다."
                )
                employee_delete_submitted = st.form_submit_button(
                    "선택한 직원 삭제",
                    use_container_width=True,
                )

            if employee_delete_submitted:
                if not delete_confirmed:
                    st.error("삭제하려면 확인 항목을 선택해주세요.")
                else:
                    try:
                        updated_employees = delete_employee(
                            employees,
                            employee_to_delete_id,
                        )
                        save_organization(departments, updated_employees)
                    except (OSError, ValueError) as error:
                        st.error(f"직원을 삭제하지 못했습니다: {error}")
                    else:
                        st.rerun()
