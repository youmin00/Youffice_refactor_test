"""Regression checks for the shared animation specification catalog."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from animation.staff_specs import (
    ACTION_LABEL_TO_KEY,
    STAFF,
    build_staff_app_specs,
)


class StaffSpecTests(unittest.TestCase):
    def test_app_specs_are_reused(self) -> None:
        self.assertIs(build_staff_app_specs(), build_staff_app_specs())

    def test_app_specs_cover_every_staff_action(self) -> None:
        specs = build_staff_app_specs()
        self.assertEqual(len(specs), len(STAFF) * len(ACTION_LABEL_TO_KEY))
        for staff in STAFF.values():
            for action in ACTION_LABEL_TO_KEY.values():
                spec = specs[(str(staff["id"]), action)]
                self.assertTrue(str(spec["path"]).endswith(".png"))
                self.assertGreater(int(spec["frame_count"]), 0)


if __name__ == "__main__":
    unittest.main()
