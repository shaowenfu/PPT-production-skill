#!/usr/bin/env python
"""Assemble final PPTX from AI-generated slide images."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_project

bootstrap_project(__file__)

from pptflow.cli import run_cli
from pptflow.errors import InputError
from pptflow.json_io import read_json
from pptflow.paths import resolve_project_dir
from pptflow.ppt_builder import (
    SLIDE_HEIGHT,
    SLIDE_WIDTH,
    add_speaker_notes,
    create_presentation,
    get_blank_layout,
)
from pptflow.schemas import AssetManifest, SlideDraftDocument, SlidePlanDocument
from pptflow.state_store import append_transition, load_state, save_state, set_artifact

TOOL_NAME = "ppt_assemble"


def _add_script_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--project-dir", required=True, help="项目目录")
    return parser


def _save_presentation(
    *,
    output_pptx: Path,
    plan: SlidePlanDocument,
    draft_map: dict[str, Any],
    asset_map: dict[str, Path],
) -> int:
    prs = create_presentation()
    blank_layout = get_blank_layout(prs)

    images_count = 0
    for page in plan.pages:
        slide = prs.slides.add_slide(blank_layout)
        image_path = asset_map.get(page.page_id)

        if image_path and image_path.exists():
            slide.shapes.add_picture(str(image_path), 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT)
            images_count += 1

        if page.page_id in draft_map:
            add_speaker_notes(slide, draft_map[page.page_id].content)

    prs.save(str(output_pptx))
    return images_count


def handle_assemble(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = resolve_project_dir(args.project_dir, create=False)
    state = load_state(project_dir)
    project_id = state["project_id"]

    plan_path = project_dir / "plan" / "plan.json"
    manifest_path = project_dir / "assets" / "manifest.json"
    draft_path = project_dir / "draft" / "slide_draft.json"

    if not plan_path.exists() or not manifest_path.exists():
        raise InputError("规划文件或资产清单缺失，请先执行前面的步骤")

    plan = SlidePlanDocument(**read_json(plan_path))
    manifest = AssetManifest(**read_json(manifest_path))

    if draft_path.exists():
        draft = SlideDraftDocument(**read_json(draft_path))
        draft_map = {slide.page_id: slide for slide in draft.slides}
    else:
        draft_map = {}

    asset_map = {item.page_id: project_dir / item.file_path for item in manifest.items}

    deck_dir = project_dir / "deck"
    deck_dir.mkdir(exist_ok=True)
    output_pptx = deck_dir / "deck.pptx"
    images_count = _save_presentation(
        output_pptx=output_pptx,
        plan=plan,
        draft_map=draft_map,
        asset_map=asset_map,
    )
    if not output_pptx.exists():
        raise InputError("PPT 装配失败：未能生成输出文件")

    output_size_bytes = output_pptx.stat().st_size

    previous_state = state["current_state"]
    state = set_artifact(state, "deck", "deck/deck.pptx", exists=True)
    state["current_state"] = "DeckAssembled"
    state["last_completed_step"] = TOOL_NAME
    state = append_transition(
        state,
        {
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "from_state": previous_state,
            "to_state": "DeckAssembled",
            "trigger": "tool_success",
            "step": TOOL_NAME,
            "note": (
                f"Assembled {len(plan.pages)} slides using {images_count} full-page images. "
                f"size_bytes={output_size_bytes}."
            ),
        },
    )
    save_state(project_dir, state)

    return {
        "project_id": project_id,
        "artifacts": ["deck/deck.pptx"],
        "metrics": {
            "total_slides": len(plan.pages),
            "images_inserted": images_count,
            "output_size_bytes": output_size_bytes,
        },
        "output_file": "deck/deck.pptx",
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    _add_script_args(parser)
    return run_cli(handle_assemble, tool=TOOL_NAME, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
