"""python3 -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

from grader import config, judge, submission
from grader.checks import dynamic
from grader.config import ConfigError

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
PY = sys.executable


def grade_dir(config_name, fixture_dir):
    cfg = config.load(ROOT / "assignments" / config_name)
    judge.prepare(cfg, PY)
    return {
        g.sub.filename: g
        for g in (judge.grade(s, cfg, PY) for s in submission.discover(FIXTURES / fixture_dir))
    }


class TestFirstAssignment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = grade_dir("01_print.yaml", "01")

    def assertStatus(self, filename, status, code=None):
        g = self.results[filename]
        self.assertEqual(g.status, status, [i.code for i in g.issues])
        if code:
            self.assertTrue(any(i.code.startswith(code) for i in g.issues), [i.code for i in g.issues])

    def real(self, prefix):
        return self.results[next(f for f in self.results if f.startswith(prefix))]

    def test_auto_pass(self):
        for g in [self.real("t99001tt"), self.real("g99002gg")]:
            self.assertEqual(g.status, judge.AUTO_PASS)
        for f in ["spaced_comment.py", "bom.py", "fstring.py"]:
            self.assertStatus(f, judge.AUTO_PASS)

    def test_student_id_extracted(self):
        self.assertEqual(self.real("t99001tt").sub.student_id, "t99001tt")
        self.assertEqual(self.real("t99001tt").sub.submission_no, "9999001")
        self.assertEqual(self.real("g99002gg").sub.student_id, "g99002gg")
        self.assertEqual(self.results["print3.py"].sub.student_id, "")

    def test_needs_review(self):
        cases = {
            "print3.py": "MISSING:add",
            "print_str.py": "MISSING:add",
            "name_error.py": "RUNTIME_ERROR:NameError",
            "empty.py": "EMPTY_FILE",
            "syntax_error.py": "SYNTAX_ERROR",
            "extra_output.py": "WRONG_OUTPUT",
            "cp932.py": "ENCODING_CP932",
            "readme.txt": "NOT_PY",
            "random_ok.py": "NONDETERMINISTIC",
        }
        for f, code in cases.items():
            with self.subTest(f=f):
                self.assertStatus(f, judge.NEEDS_REVIEW, code)

    def test_safety(self):
        self.assertStatus("infinite_loop.py", judge.NEEDS_REVIEW, "TIMEOUT")
        self.assertStatus("big_output.py", judge.NEEDS_REVIEW, "OUTPUT_TOO_LARGE")
        self.assertStatus("input_wait.py", judge.NEEDS_REVIEW, "RUNTIME_ERROR:EOFError")
        self.assertStatus("import_os.py", judge.NEEDS_REVIEW, "NOT_EXECUTED:os")
        self.assertEqual(self.results["import_os.py"].records, [])  # 実行されていない

    def test_unlearned_is_warning_only(self):
        g = self.results["fstring.py"]
        self.assertEqual(g.status, judge.AUTO_PASS)
        self.assertIn("fstring", g.unlearned)


class TestForSample(unittest.TestCase):
    def test_results(self):
        r = grade_dir("sample_for.yaml", "sample_for")
        self.assertEqual(r["good.py"].status, judge.AUTO_PASS)
        for f in ["hardcode.py", "for_unused.py", "off_by_one.py"]:
            self.assertEqual(r[f].status, judge.NEEDS_REVIEW, f)
        self.assertTrue(any(i.code.startswith("NOT_NESTED") for i in r["for_unused.py"].issues))


class TestConfig(unittest.TestCase):
    def write(self, text):
        import tempfile
        d = Path(tempfile.mkdtemp())
        (d / "a.yaml").write_text(text, encoding="utf-8")
        return d / "a.yaml"

    def test_numeric_stdin_rejected(self):
        with self.assertRaises(ConfigError):
            config.load(self.write('mode: stdin_stdout\ntests:\n  - stdin: 5\n    expected: "5"\n'))

    def test_unknown_concept_rejected(self):
        with self.assertRaises(ConfigError):
            config.load(self.write('tests:\n  - expected: "3"\nrequire: [fro]\n'))

    def test_unknown_key_rejected(self):
        with self.assertRaises(ConfigError):
            config.load(self.write('tests:\n  - expected: "3"\nrequires: [for]\n'))

    def test_model_answer_must_pass(self):
        p = self.write('tests:\n  - expected: "4"\nmodel_answer: m.py\n')
        (p.parent / "m.py").write_text("print(1+2)\n")
        with self.assertRaises(ConfigError):
            judge.prepare(config.load(p), PY)


class TestNormalize(unittest.TestCase):
    def test_trailing_whitespace_ignored(self):
        self.assertEqual(dynamic.normalize_output("3  \n\n"), dynamic.normalize_output("3"))

    def test_value_differences_kept(self):
        self.assertNotEqual(dynamic.normalize_output("3.0"), dynamic.normalize_output("3"))
        self.assertNotEqual(dynamic.normalize_output("３"), dynamic.normalize_output("3"))


if __name__ == "__main__":
    unittest.main()
