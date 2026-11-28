"""Verify CI reporting in fresh subprocesses with isolated synthetic discovery trees."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "tools/run_ci_tests.py"


class CiReportingTests(unittest.TestCase):
    def simulate(self, source, expected_exit):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            suite = root / "suite"
            suite.mkdir()
            if source:
                (suite / "test_controls.py").write_text(textwrap.dedent(source), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(RUNNER), "--directory", "results", "tests", "--start", "suite"],
                cwd=root, capture_output=True,
            )
            self.assertEqual(process.returncode, expected_exit, process.stderr)
            data = json.loads((root / "results/test_results.json").read_text(encoding="utf-8"))
            self.assertEqual(data["exit_code"], expected_exit)
            self.assertEqual(data["success"], expected_exit == 0)
            return data

    def test_method_and_subtest_outcomes(self):
        report = self.simulate("""
            import unittest
            class Sample(unittest.TestCase):
                def test_ok(self): pass
                def test_fail(self): self.fail("control")
                def test_error(self): raise ValueError("control")
                @unittest.skip("control")
                def test_skip(self): pass
                @unittest.expectedFailure
                def test_expected(self): self.fail("control")
                @unittest.expectedFailure
                def test_unexpected(self): pass
                def test_multiple(self):
                    for n in (1, 2, 3):
                        with self.subTest(n=n): self.assertEqual(n, 1)
                def test_sub_error(self):
                    with self.subTest(n=1): raise ValueError("control")
                def test_sub_ok(self):
                    with self.subTest(n=1): pass
        """, 1)
        self.assertEqual(report["tests_run"], 9)
        self.assertEqual(report["method_counts"], {
            "PASS": 2, "FAIL": 2, "ERROR": 2, "SKIPPED": 1,
            "EXPECTED FAILURE": 1, "UNEXPECTED SUCCESS": 1,
        })
        self.assertEqual(report["subtest_counts"], {"PASS": 2, "FAIL": 2, "ERROR": 1})
        self.assertEqual(report["suite_events"], [])
        self.assertEqual(report["discovery_errors"], [])

    def test_class_setup_and_discovery_errors(self):
        report = self.simulate("""
            import unittest
            class Broken(unittest.TestCase):
                @classmethod
                def setUpClass(cls): raise RuntimeError("setup control")
                def test_body(self): pass
        """, 1)
        self.assertEqual(report["methods"], [])
        self.assertIn("setup control", report["suite_events"][0]["detail"])
        report = self.simulate("raise ImportError('discovery control')", 1)
        self.assertEqual(report["methods"], [])
        self.assertIn("discovery control", report["discovery_errors"][0])

    def test_empty_discovery(self):
        report = self.simulate("", 1)
        self.assertEqual(report["methods"], [])
        self.assertEqual(report["tests_run"], 0)
        self.assertTrue(report["discovery_errors"])

    def test_successful_exit(self):
        report = self.simulate("""
            import unittest
            class Sample(unittest.TestCase):
                def test_ok(self): pass
        """, 0)
        self.assertEqual(report["method_counts"], {"PASS": 1})
