from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .errors import (
    ExitCode,
    OutputValidationError,
    PPTWorkflowError,
    error_payload_for_exception,
    exit_code_for_exception,
)


def add_common_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--project-dir")
    parser.add_argument("--ppt-root")
    parser.add_argument("--project-id")
    parser.add_argument("--output-json", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    parser.add_argument("--overwrite", action="store_true", default=False)
    parser.add_argument("--revision-instruction")
    return parser


def _coerce_string_path(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def build_success_summary(
    tool: str,
    *,
    project_id: str | None = None,
    project_dir: str | None = None,
    artifacts: Sequence[str] | None = None,
    metrics: Mapping[str, Any] | None = None,
    warnings: Sequence[str] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "ok": True,
        "tool": tool,
        "project_id": project_id,
        "project_dir": project_dir,
        "artifacts": list(artifacts or []),
        "metrics": dict(metrics or {}),
        "warnings": list(warnings or []),
    }
    if extra:
        for key, value in extra.items():
            if key not in summary:
                summary[key] = value
    return summary


def build_error_summary(
    tool: str,
    error: Exception,
    *,
    project_id: str | None = None,
    project_dir: str | None = None,
) -> dict[str, Any]:
    error_payload = error_payload_for_exception(error)
    return {
        "ok": False,
        "tool": tool,
        "project_id": project_id,
        "project_dir": project_dir,
        "artifacts": [],
        "metrics": {},
        "warnings": [],
        "error": error_payload,
    }


def print_json_summary(summary: Mapping[str, Any], *, stream: Any = None) -> None:
    target = sys.stdout if stream is None else stream
    print(json.dumps(summary, ensure_ascii=False, indent=2), file=target, flush=True)


def print_error_message(error: Exception, *, stream: Any = None) -> None:
    target = sys.stderr if stream is None else stream
    print(f"{error.__class__.__name__}: {error}", file=target, flush=True)


def print_stderr(message: str, *, stream: Any = None) -> None:
    target = sys.stderr if stream is None else stream
    print(message, file=target, flush=True)


def _drain_captured_stdout(buffer: io.StringIO, *, stream: Any = None) -> None:
    target = sys.stderr if stream is None else stream
    captured = buffer.getvalue()
    if not captured:
        return
    if captured.endswith("\n"):
        target.write(captured)
    else:
        target.write(f"{captured}\n")
    target.flush()


def exit_code_for_error(error: Exception) -> int:
    return int(exit_code_for_exception(error))


def normalize_result(
    tool: str,
    result: Any,
    *,
    args: argparse.Namespace | None = None,
) -> dict[str, Any]:
    if result is None:
        payload: dict[str, Any] = {}
    elif isinstance(result, Mapping):
        payload = dict(result)
    else:
        raise OutputValidationError("CLI handler must return a mapping or None")

    project_id = payload.pop("project_id", None)
    if project_id is None and args is not None:
        project_id = getattr(args, "project_id", None)
    project_dir = payload.pop("project_dir", None)
    if project_dir is None and args is not None:
        project_dir = getattr(args, "project_dir", None)

    summary = build_success_summary(
        tool,
        project_id=_coerce_string_path(project_id),
        project_dir=_coerce_string_path(project_dir),
        artifacts=payload.pop("artifacts", None),
        metrics=payload.pop("metrics", None),
        warnings=payload.pop("warnings", None),
        extra=payload,
    )
    return summary


def run_cli(
    handler: Callable[[argparse.Namespace], Any],
    *,
    tool: str,
    parser: argparse.ArgumentParser | None = None,
    argv: Sequence[str] | None = None,
) -> int:
    effective_parser = parser or add_common_args(argparse.ArgumentParser(prog=tool))
    args = effective_parser.parse_args(argv)
    captured_stdout = io.StringIO()

    try:
        with contextlib.redirect_stdout(captured_stdout):
            result = handler(args)
        summary = normalize_result(tool, result, args=args)
        print_json_summary(summary)
        _drain_captured_stdout(captured_stdout)
        return 0
    except PPTWorkflowError as exc:
        summary = build_error_summary(
            tool,
            exc,
            project_id=_coerce_string_path(getattr(args, "project_id", None)),
            project_dir=_coerce_string_path(getattr(args, "project_dir", None)),
        )
        print_json_summary(summary)
        _drain_captured_stdout(captured_stdout)
        print_error_message(exc)
        return exit_code_for_error(exc)
    except Exception as exc:  # pragma: no cover - defensive fallback
        summary = build_error_summary(
            tool,
            exc,
            project_id=_coerce_string_path(getattr(args, "project_id", None)),
            project_dir=_coerce_string_path(getattr(args, "project_dir", None)),
        )
        print_json_summary(summary)
        _drain_captured_stdout(captured_stdout)
        print_error_message(exc)
        return int(ExitCode.OUTPUT_VALIDATION_ERROR)
