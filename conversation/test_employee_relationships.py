"""직원 관계 맥락의 선택 주입 회귀 테스트."""

import unittest

from conversation.employee_prompts import (
    MAKO_PERSONA_INSTRUCTIONS,
    RELATIONSHIP_PROFILES,
    build_employee_system_prompt,
    build_relationship_context,
)


class EmployeeRelationshipTests(unittest.TestCase):
    def test_default_prompt_does_not_receive_relationship_context(self):
        prompt = build_employee_system_prompt(
            {"name": "유키", "title": "팀장", "role_description": "팀 방향 조율"},
            "기획",
        )

        self.assertNotIn("현재 대화에 필요한 직원 관계 맥락", prompt)

    def test_two_person_context_selects_only_requested_pair(self):
        context = build_relationship_context(
            "리오",
            conversation_partner="미츠리",
            present_employee_names=["유키", "레비"],
            situation="회의",
        )

        self.assertIn("쌍둥이 자매", context)
        self.assertIn("유키", context)
        self.assertIn("레비", context)
        self.assertIn("현재 상황(회의) 원칙", context)

    def test_report_context_preserves_accuracy_rule(self):
        prompt = build_employee_system_prompt(
            {"name": "마코", "title": "보고서 부장", "role_description": "최종 보고서 작성"},
            "보고",
            conversation_partner="레비",
            situation="최종 보고서",
        )

        self.assertIn(MAKO_PERSONA_INSTRUCTIONS, prompt)
        self.assertIn("최종 보고서 본문", prompt)
        self.assertIn("관계 설정과 캐릭터식 농담을 보고서 본문과 사실 데이터에 넣지 않고", prompt)

    def test_relationship_catalog_has_all_fifteen_pairs(self):
        self.assertEqual(len(RELATIONSHIP_PROFILES), 15)


if __name__ == "__main__":
    unittest.main()
