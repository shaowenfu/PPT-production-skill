#!/usr/bin/env python
"""Thin dispatcher for platform-friendly workflow execution.

Usage:
    python scripts/execute_step.py --step project_init --project-dir PPT/demo
    python scripts/execute_step.py --step draft --project-id demo --page-ids p1,p2
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

from _bootstrap import bootstrap_project

REPO_ROOT = bootstrap_project(__file__)

from pptflow.cli import build_error_summary, print_json_summary
from pptflow.errors import InputError, OutputValidationError, exit_code_for_exception
from pptflow.paths import resolve_project_dir_input

TOOL_NAME = "execute_step"

STEP_ALIASES = {
    "init": "project_init",
    "project_init": "project_init",
    "draft": "slide_draft_generate",
    "slide_draft_generate": "slide_draft_generate",
    "prompt": "visual_prompt_design",
    "prompts": "visual_prompt_design",
    "visual_prompt_design": "visual_prompt_design",
    "assets": "visual_asset_generate",
    "visual_asset_generate": "visual_asset_generate",
    "assemble": "ppt_assemble",
    "ppt_assemble": "ppt_assemble",
}

STEP_SCRIPTS = {
    "project_init": "project_init.py",
    "slide_draft_generate": "slide_draft_generate.py",
    "visual_prompt_design": "visual_prompt_design.py",
    "visual_asset_generate": "visual_asset_generate.py",
    "ppt_assemble": "ppt_assemble.py",
}


def _add_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--step", required=True, help="要执行的步骤名或别名")
    parser.add_argument("--project-dir", help="项目目录")
    parser.add_argument("--project-id", help="项目 ID，可替代 project-dir")
    parser.add_argument("--ppt-root", help="PPT 工作区根目录")
    parser.add_argument("--project-name", help="初始化项目时使用的项目名")
    parser.add_argument("--page-ids", help="Draft 生成目标页面 ID，逗号分隔")
    parser.add_argument("--target-pages", help="Asset 生成目标页面 ID，逗号分隔")
    parser.add_argument("--batch-size", type=int, default=5, help="Prompt 设计批大小")
    parser.add_argument("--overwrite", action="store_true", default=False, help="覆盖已有产物")
    return parser


def _canonical_step(step_name: str) -> str:
    candidate = step_name.strip()
    if not candidate:
        raise InputError("step 不能为空")
    canonical = STEP_ALIASES.get(candidate)
    if canonical is None:
        raise InputError(
            f"不支持的 step: {candidate}",
            details={"step": candidate, "supported_steps": sorted(STEP_SCRIPTS)},
        )
    return canonical


def _build_step_command(args: argparse.Namespace) -> list[str]:
    step = _canonical_step(args.step)
    script_name = STEP_SCRIPTS[step]
    script_path = REPO_ROOT / "scripts" / script_name
    command = [sys.executable, str(script_path)]

    if step == "project_init":
        project_dir = resolve_project_dir_input(
            project_dir=args.project_dir,
            project_id=args.project_id,
            repo_root=REPO_ROOT,
            ppt_root=args.ppt_root,
            create_ppt_root=True,
            create_project_dir=True,
        )
        command.extend(["--project-dir", str(project_dir)])
        if args.project_name:
            command.extend(["--project-name", args.project_name])
        return command

    project_dir = resolve_project_dir_input(
        project_dir=args.project_dir,
        project_id=args.project_id,
        repo_root=REPO_ROOT,
        ppt_root=args.ppt_root,
        create_ppt_root=False,
        create_project_dir=False,
    )
    command.extend(["--project-dir", str(project_dir)])

    if step == "slide_draft_generate":
        if not args.page_ids:
            raise InputError("slide_draft_generate 需要 --page-ids")
        command.extend(["--page-ids", args.page_ids])
    elif step == "visual_prompt_design":
        command.extend(["--batch-size", str(args.batch_size)])
    elif step == "visual_asset_generate":
        if args.target_pages:
            command.extend(["--target-pages", args.target_pages])
        if args.overwrite:
            command.append("--overwrite")

    return command


def _write_stderr(text: str) -> None:
    if not text:
        return
    sys.stderr.write(text)
    if not text.endswith("\n"):
        sys.stderr.write("\n")
    sys.stderr.flush()


def _parse_child_summary(stdout_text: str, *, step: str) -> dict[str, Any]:
    payload = stdout_text.strip()
    if not payload:
        raise OutputValidationError(
            "子步骤未输出 JSON summary",
            details={"step": step},
        )

    try:
        summary = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise OutputValidationError(
            "子步骤输出不是合法 JSON",
            details={"step": step, "stdout_preview": payload[:500]},
        ) from exc

    if not isinstance(summary, dict):
        raise OutputValidationError(
            "子步骤 JSON summary 必须是对象",
            details={"step": step},
        )
    return summary


def main() -> int:
    parser = _add_args(argparse.ArgumentParser(prog=TOOL_NAME))
    args = parser.parse_args()

    try:
        command = _build_step_command(args)
        result = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        _write_stderr(result.stderr)
        summary = _parse_child_summary(result.stdout, step=_canonical_step(args.step))
        print_json_summary(summary)
        return result.returncode
    except Exception as exc:
        summary = build_error_summary(
            TOOL_NAME,
            exc,
            project_id=getattr(args, "project_id", None),
            project_dir=getattr(args, "project_dir", None),
        )
        print_json_summary(summary)
        return int(exit_code_for_exception(exc))


if __name__ == "__main__":
    raise SystemExit(main())
