from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stderr, redirect_stdout

import pytest

from pptflow.cli import run_cli


def test_run_cli_keeps_stdout_machine_readable_and_redirects_progress_to_stderr() -> None:
    def handler(args: argparse.Namespace) -> dict[str, object]:
        print("progress-line")
        return {
            "project_id": "demo_project",
            "project_dir": "/tmp/demo_project",
            "artifacts": ["state.json"],
            "metrics": {"directories_initialized": 7},
        }

    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(handler, tool="project_init", parser=argparse.ArgumentParser(prog="project_init"), argv=[])

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["tool"] == "project_init"
    assert payload["metrics"] == {"directories_initialized": 7}
    assert stderr.getvalue() == "progress-line\n"


def test_run_cli_returns_structured_error_when_handler_returns_invalid_payload() -> None:
    def handler(args: argparse.Namespace) -> int:
        return 123

    stdout = io.StringIO()
    stderr = io.StringIO()

    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = run_cli(handler, tool="project_init", parser=argparse.ArgumentParser(prog="project_init"), argv=[])

    payload = json.loads(stdout.getvalue())
    assert exit_code == 60
    assert payload["ok"] is False
    assert payload["tool"] == "project_init"
    assert payload["error"]["code"] == "OUTPUT_VALIDATION_ERROR"
    assert "mapping or None" in payload["error"]["message"]
    assert "OutputValidationError" in stderr.getvalue()
