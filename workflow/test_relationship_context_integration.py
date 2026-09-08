"""팀 회의 관계 맥락 연결 회귀 테스트."""

import ast
from pathlib import Path
import unittest


WORKFLOW_ROOT = Path(__file__).resolve().parent


class RelationshipContextIntegrationTests(unittest.TestCase):
    def test_only_team_meeting_passes_relationship_situation(self):
        relationship_calls = []

        for module_path in WORKFLOW_ROOT.glob("*.py"):
            if module_path.name.startswith("test_"):
                continue
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name):
                    continue
                if node.func.id != "build_employee_system_prompt":
                    continue
                keywords = {keyword.arg: keyword.value for keyword in node.keywords}
                situation = keywords.get("situation")
                if situation is not None:
                    relationship_calls.append((module_path.name, keywords))

        self.assertEqual(len(relationship_calls), 1)
        module_name, keywords = relationship_calls[0]
        self.assertEqual(module_name, "meeting.py")
        self.assertEqual(
            keywords["situation"].value,
            "회의",
        )
        self.assertIn("conversation_partner", keywords)


if __name__ == "__main__":
    unittest.main()
