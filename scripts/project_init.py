#!/usr/bin/env python
"""Initialize a new PPT project with the standard directory structure.

Usage:
    python scripts/project_init.py --project-dir /path/to/project [--project-name "课程名"]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pptflow.cli import run_cli
from pptflow.errors import ProjectResolutionError
from pptflow.state_store import default_workflow_state, save_state

TOOL_NAME = "project_init"

PROJECT_SUBDIRS = ["outline", "draft", "plan", "prompts", "assets", "deck", "exports"]


def handle_init(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = Path(args.project_dir).expanduser().resolve()
    project_name = args.project_name or project_dir.name

    if project_dir.exists() and not project_dir.is_dir():
        raise ProjectResolutionError(f"Path exists but is not a directory: {project_dir}")

    # 创建目录结构
    project_dir.mkdir(parents=True, exist_ok=True)
    for subdir in PROJECT_SUBDIRS:
        (project_dir / subdir).mkdir(exist_ok=True)

    # 初始化状态
    initial_state = default_workflow_state(project_dir.name, project_name=project_name)
    save_state(project_dir, initial_state)

    return {
        "project_id": project_dir.name,
        "project_dir": str(project_dir),
        "artifacts": ["state.json"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    parser.add_argument("--project-dir", required=True, help="项目目录完整路径")
    parser.add_argument("--project-name", default=None, help="项目名称（默认取目录名）")
    return run_cli(handle_init, tool=TOOL_NAME, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
