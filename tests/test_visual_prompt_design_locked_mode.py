from __future__ import annotations

import pytest

from pptflow.errors import InputError, OutputValidationError
from pptflow.prompt_design_contracts import build_page_specs, validate_locked_page_output
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
                "copy_locked": True,
            }
        ],
    )


def test_locked_page_output_must_match_source_text() -> None:
    plan = _build_locked_plan()
    page = plan.pages[0]

    validate_locked_page_output(
        page,
        "AI 中台建设\n- 统一能力底座",
        'cinematic presentation slide, render "AI 中台建设" and "- 统一能力底座"',
    )

    with pytest.raises(OutputValidationError, match="text 未严格使用 source_text"):
        validate_locked_page_output(
            page,
            "AI 中台建设\n- 改写后的要点",
            'cinematic presentation slide, render "AI 中台建设" and "- 改写后的要点"',
        )


def test_locked_page_prompt_must_include_source_text() -> None:
    plan = _build_locked_plan()
    page = plan.pages[0]

    with pytest.raises(OutputValidationError, match="prompt 未完整包含锁定文案"):
        validate_locked_page_output(
            page,
            "AI 中台建设\n- 统一能力底座",
            'cinematic presentation slide with abstract lighting only',
        )


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
                "copy_locked": True,
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
