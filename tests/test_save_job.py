import re
import unittest
from pathlib import Path


class SaveJobTests(unittest.TestCase):
    def test_save_job_placeholder_count_regression(self):
        # Pure static check: importing `webapp/app.py` requires runtime deps on the test runner.
        app_py = Path(__file__).resolve().parents[1] / "webapp" / "app.py"
        src = app_py.read_text(encoding="utf-8", errors="replace")

        m = re.search(
            r"INSERT OR REPLACE INTO jobs\s*\((?P<cols>[^)]*?)\)\s*VALUES\s*\((?P<vals>[^)]*?)\)",
            src,
            flags=re.S,
        )
        self.assertIsNotNone(m, "Could not locate save_job INSERT statement")

        cols = [c.strip() for c in m.group("cols").split(",") if c.strip()]
        placeholders = m.group("vals").count("?")

        self.assertEqual(
            len(cols),
            placeholders,
            f"jobs INSERT columns ({len(cols)}) != placeholders ({placeholders})",
        )


if __name__ == "__main__":
    unittest.main()
