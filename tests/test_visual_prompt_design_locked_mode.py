from __future__ import annotations

import pytest

from pptflow.errors import InputError
from pptflow.prompt_design_contracts import build_page_specs, normalize_screen_text
from pptflow.schemas import SlideDraftDocument, SlidePlanDocument


def _build_locked_plan() -> SlidePlanDocument:
    return SlidePlanDocument(
        project_id="demo",
        pages=[
            {
                "page_id": "p1",
                "title": "封面",
                "category": "B",
                "layout_type": "cover",
                "content_mode": "locked",
                "source_text": "AI 中台建设\n- 统一能力底座",
            }
        ],
    )


def test_normalize_screen_text_trims_outer_whitespace() -> None:
    assert normalize_screen_text("  标题  \n- 要点一  \n") == "标题\n- 要点一"


def test_build_page_specs_requires_draft_only_for_generated_pages() -> None:
    plan = SlidePlanDocument(
        project_id="demo",
        pages=[
            {
                "page_id": "p1",
                "title": "封面",
                "category": "B",
                "layout_type": "cover",
                "content_mode": "locked",
                "source_text": "固定文案",
            },
            {
                "page_id": "p2",
                "title": "正文",
                "category": "A",
                "layout_type": "bullet_points",
                "content_hint": "需要扩写",
            },
        ],
    )

    with pytest.raises(InputError, match="缺少 draft"):
        build_page_specs(plan, None, None)

    draft = SlideDraftDocument(project_id="demo", slides=[{"page_id": "p2", "content": "正文扩写"}])
    specs = build_page_specs(plan, draft, None)
    assert [spec["page_id"] for spec in specs] == ["p1", "p2"]
    assert specs[0]["content_input"] == "固定文案"
    assert specs[1]["content_input"] == "正文扩写"
