from __future__ import annotations

import re
from typing import Any

from .errors import InputError, OutputValidationError
from .schemas import PlanPage, SlideDraftDocument, SlidePlanDocument

QUOTED_TEXT_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'')


def normalize_screen_text(text: str) -> str:
    if not isinstance(text, str):
        raise OutputValidationError("screen_text 必须是字符串")
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def extract_quoted_fragments(prompt: str) -> list[str]:
    fragments: list[str] = []
    for match in QUOTED_TEXT_PATTERN.finditer(prompt):
        fragment = match.group(1) or match.group(2) or ""
        normalized = fragment.strip()
        if normalized:
            fragments.append(normalized)
    return fragments


def validate_locked_page_output(page: PlanPage, text: str, prompt: str) -> None:
    expected_text = normalize_screen_text(page.source_text or "")
    actual_text = normalize_screen_text(text)
    if actual_text != expected_text:
        raise OutputValidationError(
            f"{page.page_id} 的 text 未严格使用 source_text",
            details={
                "page_id": page.page_id,
                "expected_text": expected_text,
                "actual_text": actual_text,
            },
        )

    quoted_fragments = extract_quoted_fragments(prompt)
    expected_lines = [line.strip() for line in expected_text.splitlines() if line.strip()]
    prompt_has_full_text = expected_text in prompt
    prompt_has_all_lines = all(line in prompt or line in quoted_fragments for line in expected_lines)
    if not (prompt_has_full_text or prompt_has_all_lines):
        raise OutputValidationError(
            f"{page.page_id} 的 prompt 未完整包含锁定文案",
            details={
                "page_id": page.page_id,
                "expected_lines": expected_lines,
                "quoted_fragments": quoted_fragments,
            },
        )


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
