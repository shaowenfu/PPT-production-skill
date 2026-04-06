from __future__ import annotations

import pytest

from pptflow.schemas import SlidePlanDocument


def test_slide_plan_accepts_generated_page_by_default() -> None:
    plan = SlidePlanDocument(
        project_id="demo",
        pages=[
            {
                "page_id": "p1",
                "title": "封面",
                "content_hint": "建立主题",
                "category": "B",
                "layout_type": "cover",
            }
        ],
    )

    page = plan.pages[0]
    assert page.content_mode == "generated"
    assert page.source_text is None


def test_slide_plan_requires_source_text_for_locked_page() -> None:
    with pytest.raises(ValueError, match="source_text"):
        SlidePlanDocument(
            project_id="demo",
            pages=[
                {
                    "page_id": "p1",
                    "title": "封面",
                    "category": "B",
                    "layout_type": "cover",
                    "content_mode": "locked",
                }
            ],
        )


def test_slide_plan_rejects_source_text_on_generated_page() -> None:
    with pytest.raises(ValueError, match="must not define source_text"):
        SlidePlanDocument(
            project_id="demo",
            pages=[
                {
                    "page_id": "p1",
                    "title": "封面",
                    "content_hint": "建立主题",
                    "category": "B",
                    "layout_type": "cover",
                    "source_text": "已锁定文案",
                }
            ],
        )


def test_slide_plan_accepts_locked_page() -> None:
    plan = SlidePlanDocument(
        project_id="demo",
        master_style_prompt="dark corporate ai deck",
        pages=[
            {
                "page_id": "p1",
                "title": "封面",
                "category": "B",
                "layout_type": "cover",
                "content_mode": "locked",
                "source_text": "确定性标题\n- 要点一",
            }
        ],
    )

    page = plan.pages[0]
    assert plan.master_style_prompt == "dark corporate ai deck"
    assert page.source_text == "确定性标题\n- 要点一"
