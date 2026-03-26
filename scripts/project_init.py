#!/usr/bin/env python
"""Initialize a new PPT project with the standard directory structure.

Usage:
    python scripts/project_init.py --project-dir /path/to/project [--project-name "课程名"]
"""

from __future__ import annotations

import argparse
from typing import Any

from _bootstrap import bootstrap_project

bootstrap_project(__file__)

from pptflow.cli import run_cli
from pptflow.paths import resolve_project_dir
from pptflow.state_store import default_workflow_state, save_state

TOOL_NAME = "project_init"

PROJECT_SUBDIRS = ["outline", "draft", "plan", "prompts", "assets", "deck", "exports"]


def handle_init(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = resolve_project_dir(args.project_dir, create=True)
    project_name = args.project_name or project_dir.name

    # 创建目录结构
    for subdir in PROJECT_SUBDIRS:
        (project_dir / subdir).mkdir(exist_ok=True)

    # 初始化状态
    initial_state = default_workflow_state(project_dir.name, project_name=project_name)
    save_state(project_dir, initial_state)

    return {
        "project_id": project_dir.name,
        "project_dir": str(project_dir),
        "artifacts": ["state.json"],
        "metrics": {"directories_initialized": len(PROJECT_SUBDIRS)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    parser.add_argument("--project-dir", required=True, help="项目目录完整路径")
    parser.add_argument("--project-name", default=None, help="项目名称（默认取目录名）")
    return run_cli(handle_init, tool=TOOL_NAME, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
