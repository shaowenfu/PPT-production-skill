#!/usr/bin/env python
"""Assemble final PPTX from AI-generated slide images.

This is Program 7 in the PPT workflow. It reads the slide plan and assets
to assemble the final PowerPoint presentation by inserting each generated
image as a full-page slide.

Usage:
    python scripts/ppt_assemble.py --project-dir PPT/03
"""

from __future__ import annotations

import argparse
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_project

bootstrap_project(__file__)

from PIL import Image, ImageOps

from pptflow.cli import run_cli
from pptflow.errors import InputError
from pptflow.json_io import read_json
from pptflow.paths import resolve_project_dir
from pptflow.ppt_builder import (
    create_presentation,
    get_blank_layout,
    SLIDE_WIDTH,
    SLIDE_HEIGHT,
    add_speaker_notes
)
from pptflow.schemas import AssetManifest, SlidePlanDocument, SlideDraftDocument
from pptflow.state_store import (
    append_transition,
    load_state,
    save_state,
    set_artifact,
)

TOOL_NAME = "ppt_assemble"
MAX_PPTX_SIZE_BYTES = 25 * 1024 * 1024
MB = 1024 * 1024
COMPRESSION_PROFILES = (
    {"name": "original", "max_width": None, "quality": None},
    {"name": "w2560_q92", "max_width": 2560, "quality": 92},
    {"name": "w2304_q88", "max_width": 2304, "quality": 88},
    {"name": "w2048_q84", "max_width": 2048, "quality": 84},
    {"name": "w1920_q80", "max_width": 1920, "quality": 80},
    {"name": "w1600_q76", "max_width": 1600, "quality": 76},
    {"name": "w1440_q72", "max_width": 1440, "quality": 72},
    {"name": "w1280_q68", "max_width": 1280, "quality": 68},
    {"name": "w1024_q62", "max_width": 1024, "quality": 62},
)

def _add_script_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--project-dir", required=True, help="项目目录")
    return parser


def _compress_image_to_jpeg(
    source_path: Path,
    output_path: Path,
    *,
    max_width: int,
    quality: int,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        if image.width > max_width:
            resized_height = max(1, round(image.height * max_width / image.width))
            image = image.resize((max_width, resized_height), Image.Resampling.LANCZOS)
        image = image.convert("RGB")
        image.save(
            output_path,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
        )


def _build_asset_map_for_profile(
    *,
    asset_map: dict[str, Path],
    work_dir: Path,
    profile: dict[str, Any],
) -> tuple[dict[str, Path], int]:
    if profile["quality"] is None or profile["max_width"] is None:
        return dict(asset_map), 0

    profile_dir = work_dir / profile["name"]
    profile_dir.mkdir(parents=True, exist_ok=True)

    compressed_map: dict[str, Path] = {}
    compressed_count = 0
    for page_id, source_path in asset_map.items():
        if not source_path.exists():
            compressed_map[page_id] = source_path
            continue
        output_path = profile_dir / f"{page_id}.jpg"
        _compress_image_to_jpeg(
            source_path,
            output_path,
            max_width=profile["max_width"],
            quality=profile["quality"],
        )
        compressed_map[page_id] = output_path
        compressed_count += 1
    return compressed_map, compressed_count


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
            slide.shapes.add_picture(
                str(image_path),
                0, 0,
                SLIDE_WIDTH, SLIDE_HEIGHT
            )
            images_count += 1

        if page.page_id in draft_map:
            add_speaker_notes(slide, draft_map[page.page_id].content)

    prs.save(str(output_pptx))
    return images_count


def _format_size_mb(size_bytes: int) -> float:
    return round(size_bytes / MB, 2)

def handle_assemble(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = resolve_project_dir(args.project_dir, create=False)
    
    # 1. 加载状态与路径
    state = load_state(project_dir)
    project_id = state["project_id"]
    
    # 2. 读取规划与资产清单
    plan_path = project_dir / "plan" / "plan.json"
    manifest_path = project_dir / "assets" / "manifest.json"
    draft_path = project_dir / "draft" / "slide_draft.json"
    
    if not plan_path.exists() or not manifest_path.exists():
        raise InputError("规划文件或资产清单缺失，请先执行前面的步骤")

    plan = SlidePlanDocument(**read_json(plan_path))
    manifest = AssetManifest(**read_json(manifest_path))
    
    # 可选：读取文案用于填充演讲者备注
    draft = None
    if draft_path.exists():
        draft = SlideDraftDocument(**read_json(draft_path))
        draft_map = {s.page_id: s for s in draft.slides}
    else:
        draft_map = {}

    # 3. 构建资产映射
    asset_map = {item.page_id: project_dir / item.file_path for item in manifest.items}

    # 4. 逐档尝试装配，确保最终 PPT 小于 25MB
    deck_dir = project_dir / "deck"
    deck_dir.mkdir(exist_ok=True)
    output_pptx = deck_dir / "deck.pptx"
    chosen_profile: dict[str, Any] | None = None
    final_size_bytes = 0
    images_count = 0
    recompressed_images = 0

    with tempfile.TemporaryDirectory(prefix="assemble_", dir=deck_dir) as temp_dir:
        temp_root = Path(temp_dir)
        for profile in COMPRESSION_PROFILES:
            profile_asset_map, compressed_count = _build_asset_map_for_profile(
                asset_map=asset_map,
                work_dir=temp_root,
                profile=profile,
            )
            images_count = _save_presentation(
                output_pptx=output_pptx,
                plan=plan,
                draft_map=draft_map,
                asset_map=profile_asset_map,
            )
            final_size_bytes = output_pptx.stat().st_size
            chosen_profile = profile
            recompressed_images = compressed_count
            if final_size_bytes <= MAX_PPTX_SIZE_BYTES:
                break

    if chosen_profile is None:
        raise InputError("PPT 装配失败：未能生成输出文件")
    if final_size_bytes > MAX_PPTX_SIZE_BYTES:
        raise InputError(
            "PPT 超过 25MB，已尝试所有压缩档位仍未满足传输限制",
            details={
                "output_size_mb": _format_size_mb(final_size_bytes),
                "max_size_mb": _format_size_mb(MAX_PPTX_SIZE_BYTES),
                "last_profile": chosen_profile["name"],
            },
        )

    # 5. 更新状态
    previous_state = state["current_state"]
    state = set_artifact(state, "deck", "deck/deck.pptx", exists=True)
    state["current_state"] = "DeckAssembled"
    state["last_completed_step"] = TOOL_NAME
    
    state = append_transition(state, {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_state": previous_state,
        "to_state": "DeckAssembled",
        "trigger": "tool_success",
        "step": TOOL_NAME,
        "note": (
            f"Assembled {len(plan.pages)} slides using {images_count} full-page images. "
            f"Profile={chosen_profile['name']}, size={_format_size_mb(final_size_bytes)}MB."
        ),
    })
    save_state(project_dir, state)

    return {
        "project_id": project_id,
        "artifacts": ["deck/deck.pptx"],
        "metrics": {
            "total_slides": len(plan.pages),
            "images_inserted": images_count,
            "output_size_mb": _format_size_mb(final_size_bytes),
            "size_limit_mb": _format_size_mb(MAX_PPTX_SIZE_BYTES),
            "compression_profile": chosen_profile["name"],
            "recompressed_images": recompressed_images,
        },
        "output_file": "deck/deck.pptx",
    }

def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    _add_script_args(parser)
    return run_cli(handle_assemble, tool=TOOL_NAME, parser=parser)

if __name__ == "__main__":
    raise SystemExit(main())
