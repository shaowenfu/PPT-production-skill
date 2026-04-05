from __future__ import annotations

from typing import Any

from .errors import InputError, OutputValidationError
from .schemas import SlideDraftDocument, SlidePlanDocument


def normalize_screen_text(text: str) -> str:
    if not isinstance(text, str):
        raise OutputValidationError("screen_text 必须是字符串")
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def build_page_specs(
    plan: SlidePlanDocument,
    draft: SlideDraftDocument | None,
    target_ids: list[str] | None,
) -> list[dict[str, Any]]:
    draft_map = {slide.page_id: slide.content for slide in draft.slides} if draft is not None else {}
    plan_pages = [page for page in plan.pages if target_ids is None or page.page_id in target_ids]
    if not plan_pages:
        return []

    missing_generated_pages: list[str] = []
    page_specs: list[dict[str, Any]] = []
    for page in plan_pages:
        if page.content_mode == "locked":
            content_input = page.source_text or ""
        else:
            content_input = draft_map.get(page.page_id, "")
            if not content_input.strip():
                missing_generated_pages.append(page.page_id)
                continue
        page_specs.append(
            {
                "page_id": page.page_id,
                "page": page,
                "content_input": content_input,
            }
        )

    if missing_generated_pages:
        raise InputError(
            "存在 generated 页面缺少 draft 内容，请先执行 draft 步骤",
            details={"missing_page_ids": missing_generated_pages},
        )
    return page_specs
