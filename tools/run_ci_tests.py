"""Local and GitHub Actions reporting for PCCOM's offline unittest suite."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import time
import traceback
import unittest


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def detail(err):
    return "".join(traceback.format_exception(*err))


class RecordingResult(unittest.TextTestResult):
    """Keep the parent method outcome separate from its individual subtests."""

    def __init__(self, *args, loader_errors=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.methods = []
        self.suite_events = []
        self.current = None
        self.record = None
        self.loader_errors = loader_errors

    def startTest(self, test):
        super().startTest(test)
        # A loader error can be scheduled as a synthetic test by unittest.
        if self.loader_errors and type(test).__module__ == unittest.loader.__name__:
            return
        self.current = test
        self.record = dict(id=test.id(), outcome=None, details=[], subtests=[])
        self.methods.append(self.record)

    def stopTest(self, test):
        if self.current is test:
            if self.record["outcome"] is None:
                subs = self.record["subtests"]
                self.record["outcome"] = "SKIPPED" if subs and all(
                    s["outcome"] == "SKIPPED" for s in subs
                ) else "ERROR"
            self.current = self.record = None
        super().stopTest(test)

    def outcome(self, test, status, message=None):
        if test is not self.current:
            self.suite_events.append(dict(id=test.id(), outcome=status, detail=message))
            return
        severity = {None: -1, "PASS": 0, "SKIPPED": 1, "EXPECTED FAILURE": 1,
                    "UNEXPECTED SUCCESS": 2, "FAIL": 3, "ERROR": 4}
        if severity[status] >= severity[self.record["outcome"]]:
            self.record["outcome"] = status
        if message:
            self.record["details"].append(message)

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcome(test, "PASS")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.outcome(test, "FAIL", detail(err))

    def addError(self, test, err):
        super().addError(test, err)
        self.outcome(test, "ERROR", detail(err))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.current is not None and test is not self.current:
            self.record["subtests"].append(dict(id=test.id(), outcome="SKIPPED", detail=reason))
        else:
            self.outcome(test, "SKIPPED", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.outcome(test, "EXPECTED FAILURE", detail(err))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.outcome(test, "UNEXPECTED SUCCESS")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        status = "PASS"
        message = None
        if err is not None:
            status = "FAIL" if issubclass(err[0], test.failureException) else "ERROR"
            message = detail(err)
        self.record["subtests"].append(dict(id=subtest.id(), outcome=status, detail=message))
        self.outcome(test, status)


def execute_tests(directory, start="tests"):
    started, clock = timestamp(), time.monotonic()
    loader = unittest.TestLoader()
    suite_error = None
    try:
        suite = loader.discover(start, pattern="test_*.py")
    except Exception as exc:
        suite_error = detail((type(exc), exc, exc.__traceback__))
        suite = unittest.TestSuite()
    runner = unittest.TextTestRunner(
        verbosity=2, resultclass=lambda *args: RecordingResult(*args, loader_errors=loader.errors)
    )
    result = runner.run(suite)
    errors = list(loader.errors)
    if suite_error:
        errors.append(suite_error)
    if result.testsRun == 0 and not result.suite_events and not errors:
        errors.append("Discovery returned zero tests.")
    ok = result.wasSuccessful() and not errors and all(
        row["outcome"] != "ERROR" for row in result.methods
    )
    report = dict(start=started, end=timestamp(), duration_seconds=time.monotonic()-clock,
                  tests_run=result.testsRun, method_counts=dict(Counter(
                      row["outcome"] for row in result.methods)), methods=result.methods,
                  suite_events=result.suite_events, discovery_errors=errors,
                  subtest_counts=dict(Counter(sub["outcome"] for row in result.methods
                                              for sub in row["subtests"])),
                  success=ok, exit_code=int(not ok))
    (directory / "test_results.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                 encoding="utf-8")
    return report["exit_code"]


def preflight():
    from jsonschema import Draft7Validator, Draft202012Validator, FormatChecker
    from referencing import Registry
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    for validator in (Draft7Validator, Draft202012Validator):
        validator.check_schema({})
        if not validator({}, registry=Registry()).is_valid(None):
            raise RuntimeError("Offline validator initialization failed")
    checker = FormatChecker(formats=["date-time"])
    if not checker.conforms("2026-01-01T00:00:00Z", "date-time") or checker.conforms(
        "2026-02-30T00:00:00Z", "date-time"
    ):
        raise RuntimeError("date-time control failed")
    ZoneInfo("UTC")
    try:
        ZoneInfo("Example/Unknown")
    except ZoneInfoNotFoundError:
        print("Offline dialect, date-time and IANA timezone controls passed.")
        return
    raise RuntimeError("Unknown zone was accepted")


def capture(directory, log, args):
    command = [sys.executable if args[0] == "python" else args[0], *args[1:]]
    with (directory / log).open("a", encoding="utf-8") as out:
        out.write(f"$ {shlex.join(command)}\nstart={timestamp()}\n")
        out.flush()
        process = subprocess.run(command, stdout=out, stderr=subprocess.STDOUT,
                                 env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        out.write(f"\nend={timestamp()} exit={process.returncode}\n")
    print(f"{log}: exit={process.returncode}")
    return process.returncode


def environment():
    print("Python", sys.version, sys.executable, platform.platform(), platform.machine(), sep="\n")
    for key in ("GITHUB_REPOSITORY", "GITHUB_WORKFLOW", "GITHUB_EVENT_NAME", "GITHUB_RUN_ID",
                "GITHUB_RUN_ATTEMPT", "GITHUB_JOB", "GITHUB_SHA", "GITHUB_REF", "PR_HEAD_SHA",
                "RUNNER_OS", "ImageOS", "ImageVersion"):
        print(f"{key}={os.environ.get(key) or 'UNAVAILABLE'}")


def summary(directory):
    steps = ("checkout", "setup", "install", "environment", "dependencies", "syntax", "tests", "lint")
    states = {key: os.environ.get("STEP_" + key.upper(), "UNAVAILABLE") for key in steps}
    local = not os.environ.get("GITHUB_RUN_ID")
    checks = steps[2:] if local else steps
    overall = "PASS" if all(states[key] == "success" for key in checks) else "INCOMPLETE"
    if "failure" in states.values():
        overall = "FAIL"
    lines = ["## PCCOM local verification" if local else "## PCCOM CI", "", f"Checks: {overall}", "",
             f"Python: {platform.python_version()}",
             f"Checked-out SHA: {subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()}",
             f"Run: {os.environ.get('GITHUB_RUN_ID', 'local')} · "
             f"Artifact configured: {os.environ.get('ARTIFACT_NAME', 'N/A')}", ""]
    labels = {"success": "PASS", "failure": "FAIL", "skipped": "NOT RUN", "cancelled": "BLOCKED"}
    for key, value in states.items():
        status = labels.get(value, value)
        if key == "tests" and value == "skipped" and states["dependencies"] != "success":
            status = "BLOCKED"
        lines.append(f"- {key}: {status}")
    path = directory / "test_results.json"
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        groups = {"test_contract_schema_candidates": "Draft 2020-12",
                  "test_normalized_schema_candidates": "Draft-07",
                  "test_ci_test_runner": "Reporting infrastructure"}
        counts = {}
        for row in report["methods"]:
            group = groups.get(row["id"].split(".")[0], "Project/unit")
            counts.setdefault(group, Counter())[row["outcome"]] += 1
        lines += ["", f"Unittest: {report['method_counts']}; subtests: {report['subtest_counts']}",
                  f"Suite events: {len(report['suite_events'])}, discovery errors: {len(report['discovery_errors'])}"]
        lines.extend(f"- {key}: {dict(value)}" for key, value in counts.items())
    else:
        lines.append("\nUnittest report: UNAVAILABLE")
    body = "\n".join(lines) + "\n"
    (directory / "execution_summary.md").write_text(body, encoding="utf-8")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(body)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=Path("ci-evidence"))
    subs = parser.add_subparsers(dest="action", required=True)
    tests = subs.add_parser("tests")
    tests.add_argument("--start", default="tests")
    for name in ("preflight", "environment", "summary", "syntax"):
        subs.add_parser(name)
    record = subs.add_parser("capture")
    record.add_argument("log")
    record.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    if args.action == "tests":
        return execute_tests(args.directory, args.start)
    if args.action == "capture":
        return capture(args.directory, args.log, args.command)
    if args.action == "preflight":
        preflight()
    elif args.action == "environment":
        environment()
    elif args.action == "syntax":
        json.loads(Path("docs/data_contracts/schemas.json").read_text(encoding="utf-8"))
        print("JSON syntax OK")
    else:
        summary(args.directory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
