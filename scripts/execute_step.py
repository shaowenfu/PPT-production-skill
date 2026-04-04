#!/usr/bin/env python
"""Thin dispatcher for platform-friendly workflow execution.

Usage:
    python scripts/execute_step.py --step project_init --project-dir PPT/demo
    python scripts/execute_step.py --step draft --project-id demo --page-ids p1,p2
    python scripts/execute_step.py --step auto --project-dir PPT/demo
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_project

REPO_ROOT = bootstrap_project(__file__)

from pptflow.cli import build_error_summary, build_success_summary, print_json_summary
from pptflow.errors import InputError, OutputValidationError, exit_code_for_exception
from pptflow.json_io import read_json
from pptflow.paths import locate_ppt_root, resolve_project_dir_input
from pptflow.schemas import AssetManifest, PromptDocument, ScreenTextDocument, SlideDraftDocument, SlidePlanDocument

TOOL_NAME = "execute_step"
STEP_SCRIPTS = {
    "project_init": "scripts/project_init.py",
    "slide_draft_generate": "scripts/slide_draft_generate.py",
    "visual_prompt_design": "scripts/visual_prompt_design.py",
    "visual_asset_generate": "scripts/visual_asset_generate.py",
    "ppt_assemble": "scripts/ppt_assemble.py",
}
STEP_ALIASES = {
    "init": "project_init",
    "draft": "slide_draft_generate",
    "prompt": "visual_prompt_design",
    "prompts": "visual_prompt_design",
    "assets": "visual_asset_generate",
    "assemble": "ppt_assemble",
    "auto": "auto",
}


def _add_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--step", required=True, help="要执行的步骤名或别名")
    parser.add_argument("--project-dir", help="项目目录")
    parser.add_argument("--project-id", help="项目 ID，可替代 project-dir")
    parser.add_argument("--ppt-root", help="PPT 工作区根目录")
    parser.add_argument("--project-name", help="初始化项目时使用的项目名")
    parser.add_argument("--page-ids", help="Draft 生成目标页面 ID，逗号分隔")
    parser.add_argument("--target-pages", help="Prompt/Asset 目标页面 ID，逗号分隔")
    parser.add_argument("--batch-size", type=int, default=5, help="Prompt 设计批大小")
    parser.add_argument("--parallel", type=int, default=1, help="Prompt/Asset 并发数量")
    parser.add_argument("--overwrite", action="store_true", default=False, help="覆盖已有产物")
    return parser


def _canonical_step(step_name: str) -> str:
    candidate = step_name.strip()
    if not candidate:
        raise InputError("step 不能为空")
    resolved = STEP_ALIASES.get(candidate, candidate)
    if resolved != "auto" and resolved not in STEP_SCRIPTS:
        raise InputError(
            f"不支持的 step: {candidate}",
            details={"step": candidate, "supported_steps": sorted([*STEP_SCRIPTS, "auto"])},
        )
    return resolved


def _parse_page_ids(raw_value: str | None) -> list[str] | None:
    if raw_value is None:
        return None
    page_ids = [value.strip() for value in raw_value.split(",") if value.strip()]
    return page_ids or None


def _resolve_project_dir_for_init(args: argparse.Namespace) -> Path:
    return resolve_project_dir_input(
        project_dir=args.project_dir,
        project_id=args.project_id,
        repo_root=REPO_ROOT,
        ppt_root=args.ppt_root,
        create_ppt_root=True,
        create_project_dir=True,
    )


def _resolve_project_dir_for_existing_step(args: argparse.Namespace) -> Path:
    return resolve_project_dir_input(
        project_dir=args.project_dir,
        project_id=args.project_id,
        repo_root=REPO_ROOT,
        ppt_root=args.ppt_root,
        create_ppt_root=False,
        create_project_dir=False,
    )


def _resolve_project_dir_for_auto(args: argparse.Namespace) -> Path:
    if args.project_dir:
        return Path(args.project_dir).expanduser().resolve()
    if not args.project_id:
        raise InputError("auto 模式必须提供 project_dir 或 project_id")
    ppt_root = Path(args.ppt_root).expanduser().resolve() if args.ppt_root else locate_ppt_root(REPO_ROOT, create=True)
    return ppt_root / args.project_id


def _build_step_command(args: argparse.Namespace, *, step: str | None = None) -> list[str]:
    canonical_step = step or _canonical_step(args.step)
    script_path = REPO_ROOT / STEP_SCRIPTS[canonical_step]
    command = [sys.executable, str(script_path)]

    if canonical_step == "project_init":
        project_dir = _resolve_project_dir_for_init(args)
        command.extend(["--project-dir", str(project_dir)])
        if args.project_name:
            command.extend(["--project-name", args.project_name])
        return command

    project_dir = _resolve_project_dir_for_existing_step(args)
    command.extend(["--project-dir", str(project_dir)])

    if canonical_step == "slide_draft_generate":
        if not args.page_ids:
            raise InputError("slide_draft_generate 需要 --page-ids")
        command.extend(["--page-ids", args.page_ids])
    elif canonical_step == "visual_prompt_design":
        command.extend(["--batch-size", str(args.batch_size)])
        command.extend(["--parallel", str(args.parallel)])
        if args.target_pages:
            command.extend(["--target-pages", args.target_pages])
    elif canonical_step == "visual_asset_generate":
        command.extend(["--parallel", str(args.parallel)])
        if args.target_pages:
            command.extend(["--target-pages", args.target_pages])
        if args.overwrite:
            command.append("--overwrite")

    return command


def _build_auto_command(
    args: argparse.Namespace,
    step: str,
    *,
    page_ids: list[str] | None = None,
) -> list[str]:
    routed_args = argparse.Namespace(**vars(args))
    routed_args.step = step
    if step == "slide_draft_generate":
        if not page_ids:
            raise InputError("auto 路由到 draft 时必须带 page_ids")
        routed_args.page_ids = ",".join(page_ids)
        routed_args.target_pages = None
    elif step in {"visual_prompt_design", "visual_asset_generate"}:
        routed_args.target_pages = ",".join(page_ids) if page_ids else None
        routed_args.page_ids = None
    else:
        routed_args.page_ids = None
        routed_args.target_pages = None
    return _build_step_command(routed_args, step=step)


def _scope_plan_pages(plan: SlidePlanDocument, target_page_ids: list[str] | None) -> list[Any]:
    if target_page_ids is None:
        return list(plan.pages)
    scoped_pages = [page for page in plan.pages if page.page_id in target_page_ids]
    if not scoped_pages:
        raise InputError("target_pages 未匹配到任何 plan 页面", details={"target_pages": target_page_ids})
    return scoped_pages


def _missing_draft_page_ids(project_dir: Path, scoped_pages: list[Any]) -> list[str]:
    generated_page_ids = [page.page_id for page in scoped_pages if page.content_mode == "generated"]
    if not generated_page_ids:
        return []

    draft_path = project_dir / "draft" / "slide_draft.json"
    if not draft_path.exists():
        return generated_page_ids

    draft_doc = SlideDraftDocument(**read_json(draft_path))
    drafted_page_ids = {slide.page_id for slide in draft_doc.slides}
    return [page_id for page_id in generated_page_ids if page_id not in drafted_page_ids]


def _missing_prompt_page_ids(project_dir: Path, scoped_pages: list[Any]) -> list[str]:
    expected_page_ids = [page.page_id for page in scoped_pages]
    screen_text_path = project_dir / "prompts" / "screen_text.json"
    prompts_path = project_dir / "prompts" / "prompts.json"
    if not screen_text_path.exists() or not prompts_path.exists():
        return expected_page_ids

    screen_text_doc = ScreenTextDocument(**read_json(screen_text_path))
    prompt_doc = PromptDocument(**read_json(prompts_path))
    screen_text_ids = {item.page_id for item in screen_text_doc.items}
    prompt_ids = {item.page_id for item in prompt_doc.items}
    return [page_id for page_id in expected_page_ids if page_id not in screen_text_ids or page_id not in prompt_ids]


def _missing_asset_page_ids(project_dir: Path, scoped_pages: list[Any]) -> list[str]:
    expected_page_ids = [page.page_id for page in scoped_pages]
    manifest_path = project_dir / "assets" / "manifest.json"
    if not manifest_path.exists():
        return expected_page_ids

    manifest = AssetManifest(**read_json(manifest_path))
    asset_map = {item.page_id: item for item in manifest.items}
    missing_page_ids: list[str] = []
    for page_id in expected_page_ids:
        asset_item = asset_map.get(page_id)
        if asset_item is None:
            missing_page_ids.append(page_id)
            continue
        if not (project_dir / asset_item.file_path).exists():
            missing_page_ids.append(page_id)
    return missing_page_ids


def _auto_ready_summary(project_dir: Path, scoped_pages: list[Any]) -> dict[str, Any]:
    return build_success_summary(
        TOOL_NAME,
        project_id=project_dir.name,
        project_dir=str(project_dir),
        artifacts=["deck/deck.pptx"],
        metrics={"scoped_pages": len(scoped_pages)},
        extra={
            "status": "ready",
            "next_step": None,
            "next_command": None,
        },
    )


def _decide_auto_action(args: argparse.Namespace) -> tuple[list[str] | None, dict[str, Any] | None]:
    project_dir = _resolve_project_dir_for_auto(args)
    if not project_dir.exists() or not (project_dir / "state.json").exists():
        command = _build_auto_command(args, "project_init")
        return command, None

    plan_path = project_dir / "plan" / "plan.json"
    if not plan_path.exists():
        raise InputError("auto 模式需要先准备 plan/plan.json")

    plan = SlidePlanDocument(**read_json(plan_path))
    target_page_ids = _parse_page_ids(args.target_pages)
    scoped_pages = _scope_plan_pages(plan, target_page_ids)

    missing_draft = _missing_draft_page_ids(project_dir, scoped_pages)
    if missing_draft:
        return _build_auto_command(args, "slide_draft_generate", page_ids=missing_draft), None

    missing_prompts = _missing_prompt_page_ids(project_dir, scoped_pages)
    if missing_prompts:
        return _build_auto_command(args, "visual_prompt_design", page_ids=missing_prompts), None

    missing_assets = _missing_asset_page_ids(project_dir, scoped_pages)
    if missing_assets:
        return _build_auto_command(args, "visual_asset_generate", page_ids=missing_assets), None

    deck_path = project_dir / "deck" / "deck.pptx"
    if not deck_path.exists():
        return _build_auto_command(args, "ppt_assemble"), None

    return None, _auto_ready_summary(project_dir, scoped_pages)


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
        canonical_step = _canonical_step(args.step)
        if canonical_step == "auto":
            command, ready_summary = _decide_auto_action(args)
            if command is None:
                print_json_summary(ready_summary or {})
                return 0
        else:
            command = _build_step_command(args, step=canonical_step)

        result = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        _write_stderr(result.stderr)
        child_step = Path(command[1]).stem
        summary = _parse_child_summary(result.stdout, step=child_step)
        if canonical_step == "auto":
            summary["routed_by"] = "auto"
            summary["requested_step"] = "auto"
            summary["next_command"] = " ".join(command)
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
