from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.execute_step import _decide_auto_action


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_args(project_dir: Path, *, target_pages: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        step="auto",
        project_dir=str(project_dir),
        project_id=None,
        ppt_root=None,
        project_name=None,
        page_ids=None,
        target_pages=target_pages,
        batch_size=5,
        parallel=1,
        overwrite=False,
    )


def test_auto_routes_fixed_content_project_directly_to_prompt(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    _write_json(
        project_dir / "state.json",
        {
            "schema_version": "1.0",
            "project_id": "demo",
            "project_name": "demo",
            "current_state": "Initialized",
            "last_completed_step": None,
            "last_failed_step": None,
            "status": "active",
            "artifacts": {
                "outline": {"path": "outline/outline.json", "exists": False, "updated_at": None},
                "draft": {"path": "draft/slide_draft.json", "exists": False, "updated_at": None},
                "plan": {"path": "plan/plan.json", "exists": True, "updated_at": None},
                "screen_text": {"path": "prompts/screen_text.json", "exists": False, "updated_at": None},
                "prompts": {"path": "prompts/prompts.json", "exists": False, "updated_at": None},
                "assets_manifest": {"path": "assets/manifest.json", "exists": False, "updated_at": None},
                "deck": {"path": "deck/deck.pptx", "exists": False, "updated_at": None},
                "export_final": {"path": "exports/final.pptx", "exists": False, "updated_at": None},
            },
            "feedback_history": [],
            "transition_history": [],
            "retry_count": {
                "project_init": 0,
                "outline_ingest": 0,
                "slide_draft_generate": 0,
                "slide_plan_generate": 0,
                "visual_prompt_design": 0,
                "visual_asset_generate": 0,
                "ppt_assemble": 0,
                "final_approve": 0,
            },
            "context": {},
            "updated_at": "2026-04-04T12:00:00+08:00",
            "created_at": "2026-04-04T12:00:00+08:00",
        },
    )
    _write_json(
        project_dir / "plan" / "plan.json",
        {
            "project_id": "demo",
            "pages": [
                {
                    "page_id": "p1",
                    "title": "封面",
                    "category": "B",
                    "layout_type": "cover",
                    "content_mode": "locked",
                    "source_text": "固定文案",
                    "copy_locked": True,
                }
            ],
            "target_b_ratio": 0.3,
            "actual_b_ratio": 1.0,
            "metadata": {},
        },
    )

    command, ready_summary = _decide_auto_action(_build_args(project_dir))

    assert ready_summary is None
    assert command is not None
    assert command[1].endswith("visual_prompt_design.py")
    assert "--target-pages" in command
    assert command[-1] == "p1"


def test_auto_routes_generated_pages_to_draft_when_missing(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    _write_json(
        project_dir / "state.json",
        {
            "schema_version": "1.0",
            "project_id": "demo",
            "project_name": "demo",
            "current_state": "Initialized",
            "last_completed_step": None,
            "last_failed_step": None,
            "status": "active",
            "artifacts": {
                "outline": {"path": "outline/outline.json", "exists": False, "updated_at": None},
                "draft": {"path": "draft/slide_draft.json", "exists": False, "updated_at": None},
                "plan": {"path": "plan/plan.json", "exists": True, "updated_at": None},
                "screen_text": {"path": "prompts/screen_text.json", "exists": False, "updated_at": None},
                "prompts": {"path": "prompts/prompts.json", "exists": False, "updated_at": None},
                "assets_manifest": {"path": "assets/manifest.json", "exists": False, "updated_at": None},
                "deck": {"path": "deck/deck.pptx", "exists": False, "updated_at": None},
                "export_final": {"path": "exports/final.pptx", "exists": False, "updated_at": None},
            },
            "feedback_history": [],
            "transition_history": [],
            "retry_count": {
                "project_init": 0,
                "outline_ingest": 0,
                "slide_draft_generate": 0,
                "slide_plan_generate": 0,
                "visual_prompt_design": 0,
                "visual_asset_generate": 0,
                "ppt_assemble": 0,
                "final_approve": 0,
            },
            "context": {},
            "updated_at": "2026-04-04T12:00:00+08:00",
            "created_at": "2026-04-04T12:00:00+08:00",
        },
    )
    _write_json(
        project_dir / "plan" / "plan.json",
        {
            "project_id": "demo",
            "pages": [
                {
                    "page_id": "p1",
                    "title": "正文",
                    "content_hint": "需要扩写",
                    "category": "A",
                    "layout_type": "bullet_points",
                }
            ],
            "target_b_ratio": 0.3,
            "actual_b_ratio": 0.0,
            "metadata": {},
        },
    )

    command, ready_summary = _decide_auto_action(_build_args(project_dir))

    assert ready_summary is None
    assert command is not None
    assert command[1].endswith("slide_draft_generate.py")
    assert "--page-ids" in command
    assert command[-1] == "p1"
