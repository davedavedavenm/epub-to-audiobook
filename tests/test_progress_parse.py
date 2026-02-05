import re
import unittest


class ProgressParseTests(unittest.TestCase):
    def test_chunk_regex_matches(self):
        s = (
            "Processing chapter-1_Some_Title_chunk_23_of_115, length=1733\n"
            "Processing chapter-1_Some_Title_chunk_24_of_115, length=1730\n"
        )
        m = re.findall(r"Processing chapter-(\d+)_.*?_chunk_(\d+)_of_(\d+)", s)
        self.assertEqual(m[-1], ("1", "24", "115"))


if __name__ == "__main__":
    unittest.main()
