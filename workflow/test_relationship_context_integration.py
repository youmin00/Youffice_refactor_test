"""팀 회의 관계 맥락 연결 회귀 테스트."""

import ast
import inspect
import textwrap
import unittest

from workflow.engine import execute_team_workflow_background


class RelationshipContextIntegrationTests(unittest.TestCase):
    def test_only_team_meeting_passes_relationship_situation(self):
        source = textwrap.dedent(
            inspect.getsource(execute_team_workflow_background)
        )
        tree = ast.parse(source)
        relationship_calls = []

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
                relationship_calls.append(keywords)

        self.assertEqual(len(relationship_calls), 1)
        self.assertEqual(
            relationship_calls[0]["situation"].value,
            "회의",
        )
        self.assertIn("conversation_partner", relationship_calls[0])


if __name__ == "__main__":
    unittest.main()
