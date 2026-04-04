#!/usr/bin/env python
"""Visual Prompt Design Script (The Visual Director).

This is Step 5 in the PPT workflow. It reads plan.json and optional draft.json
to generate high-impact visual prompts and user-confirmable on-slide copy
using the configured text provider.

Usage:
    python scripts/visual_prompt_design.py --project-dir PPT/03 [--batch-size 5]
"""

from __future__ import annotations

import argparse
import asyncio
import time
from datetime import datetime
from typing import Any

from _bootstrap import bootstrap_project

bootstrap_project(__file__)

from google import genai
from openai import AsyncOpenAI, RateLimitError

from pptflow.cli import print_stderr, run_cli
from pptflow.config import load_settings
from pptflow.errors import InputError, OutputValidationError
from pptflow.json_io import read_json, write_json
from pptflow.llm_json import parse_llm_json
from pptflow.paths import resolve_project_dir
from pptflow.prompt_design_contracts import build_page_specs, normalize_screen_text, validate_locked_page_output
from pptflow.schemas import (
    PlanPage,
    PromptDocument,
    PromptItem,
    ScreenTextDocument,
    ScreenTextItem,
    SlideDraftDocument,
    SlidePlanDocument,
)
from pptflow.state_store import append_transition, load_state, save_state, set_artifact

TOOL_NAME = "visual_prompt_design"
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_RETRY_DELAY_SECONDS = 2.0


def _is_google_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    class_name = exc.__class__.__name__.lower()
    return (
        "429" in message
        or "rate limit" in message
        or "resource_exhausted" in message
        or "quota" in message
        or "ratelimit" in class_name
    )


def _extract_google_text(response: Any) -> str:
    response_text = getattr(response, "text", None)
    if response_text:
        return response_text

    parts = getattr(response, "parts", None) or []
    text_parts = [part.text for part in parts if getattr(part, "text", None)]
    return "\n".join(text_parts).strip()


async def _generate_json_text_with_deepseek(
    client: AsyncOpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
) -> dict[str, Any]:
    """调用 LLM 生成 JSON 响应"""
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            break
        except RateLimitError as exc:
            if attempt >= MAX_RATE_LIMIT_RETRIES:
                raise InputError(f"LLM 调用失败: {exc}") from exc
            delay = RATE_LIMIT_RETRY_DELAY_SECONDS * (attempt + 1)
            print_stderr(f"触发 429，{delay:.0f} 秒后重试...")
            await asyncio.sleep(delay)
        except Exception as exc:
            raise InputError(f"LLM 调用失败: {exc}") from exc

    content = response.choices[0].message.content
    return parse_llm_json(content, source="visual_prompt_design 模型响应")


def _generate_json_text_with_google(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
) -> dict[str, Any]:
    combined_prompt = (
        f"System Instructions:\n{system_prompt}\n\n"
        f"User Task:\n{user_prompt}\n\n"
        "Return JSON only."
    )

    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=combined_prompt,
                config={"temperature": temperature},
            )
            break
        except Exception as exc:
            if not _is_google_rate_limit_error(exc) or attempt >= MAX_RATE_LIMIT_RETRIES:
                raise InputError(f"LLM 调用失败: {exc}") from exc
            delay = RATE_LIMIT_RETRY_DELAY_SECONDS * (attempt + 1)
            print_stderr(f"Google 文本生成触发 429，{delay:.0f} 秒后重试...")
            time.sleep(delay)

    content = _extract_google_text(response)
    if not content:
        raise InputError("LLM 调用失败: Google 模型未返回文本内容")
    return parse_llm_json(content, source="visual_prompt_design Google 模型响应")


async def _generate_json_text(
    *,
    client: AsyncOpenAI | None,
    settings: Any,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
) -> dict[str, Any]:
    if settings.text_provider == "google":
        return await asyncio.to_thread(
            _generate_json_text_with_google,
            api_key=settings.google_api_key,
            model=settings.text_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
    if settings.text_provider == "deepseek":
        if client is None:
            raise InputError("DeepSeek 客户端未初始化")
        return await _generate_json_text_with_deepseek(
            client=client,
            model=settings.text_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )
    raise InputError(f"不支持的文本 Provider: {settings.text_provider}")


def _build_page_brief(plan_page: PlanPage, content_input: str) -> str:
    title = plan_page.title or ""
    content_hint = plan_page.content_hint or ""
    source_text = plan_page.source_text or ""
    return (
        f"Page ID: {plan_page.page_id}\n"
        f"Content Mode: {plan_page.content_mode}\n"
        f"Copy Locked: {plan_page.copy_locked}\n"
        f"Category: {plan_page.category}\n"
        f"Layout Type: {plan_page.layout_type}\n"
        f"Title: {title}\n"
        f"Content Hint: {content_hint}\n"
        f"Source Text: {source_text}\n"
        f"Content Input: {content_input}\n"
    )


def _build_system_prompt() -> str:
    return """你是 production-grade PPT 视觉总监。你的职责是先理解页面内容与页面用途，再独立完成视觉设计决策，为图像模型生成可执行、贴合主题、页间有节奏差异的页面提示词。。

## 你的工作方式
你不是 prompt 拼接器，也不是固定模板执行器。你要像真正的视觉导演一样工作：
1. 先理解这页要表达什么。
2. 判断这页是应该偏信息表达、偏叙事冲击、偏结构解释，还是偏案例证据。
3. 自主决定最适合的：
   - visual concept
   - visual metaphor or imagery
   - style direction
   - composition
   - text placement
   - information hierarchy
4. 最终同时输出“最终上屏文字”和一个可以直接交给图像模型的 prompt。

## 内容来源契约
1. 每页都有 `Content Mode`。
2. 如果 `Content Mode = locked` 或 `Copy Locked = true`，那么 `Source Text` 就是该页最终上屏文案的唯一真相。
3. 对 locked 页面，你不得改写、删减、润色、重组或翻译 `Source Text`。
4. 对 locked 页面，你输出的 `text` 必须与 `Source Text` 完全一致。
5. 对 locked 页面，`prompt` 中所有需要渲染的中文文案也必须与 `Source Text` 完全一致。
6. 只有 `Content Mode = generated` 的页面，你才可以根据 `Content Input` 提炼上屏文案。

## 语言规则
1. `prompt` 的描述性部分必须使用英文。
2. 幻灯片上真正要渲染的业务文案必须保持中文，并放在英文指令中的引号里。
3. 不要把中文业务文案翻译成英文再渲染。
4. 不要在 prompt 中混入未被引号包裹的中文说明文字。

## 页面设计原则
1. 设计必须贴合当前页面主题，而不是套用固定的“科技感”模板。
2. 整套 deck 要统一，但每页都应有合理差异。相邻页面不要重复相同的视觉母题、构图套路或主物体。
3. 视觉必须服务表达，不要用空泛的艺术词替代真实设计。
4. 如果页面适合极简，就做极简；如果适合叙事画面，就做叙事；如果适合结构化信息版式，就做结构化信息版式。

## Dark-first rule
1. 全部页面默认优先使用深色、低亮度、投影友好的背景。
2. 背景基准可理解为：`dark navy radial glow background, subtle top-center blue illumination`。
3. 优先使用深蓝、深海军蓝、深炭黑、低饱和冷色背景，而不是大面积高亮底色。
4. 明确禁止：`light background`, `white background`, `bright canvas`, `pale gradient`。
5. 即使页面需要更强视觉冲击，也应在深色基底上完成，而不是切换成浅色底。

## Design intent 优先
1. 不规定必须出现什么固定图像或固定关键词。
2. 如果页面内容与现实业务世界接轨，例如案例背景、行业痛点、业务现场、客户触点、运营环境、组织协作、门店/工厂/办公室/城市空间等，请优先考虑能够体现文字语境的真实场景元素。
3. 这些场景元素可以是写实的、伪实拍的、电影感的、概念化但仍有现实语义锚点的。
4. 能具体时就具体；适合抽象时再抽象。不要默认退化成空泛的抽象科技光效图。

## Scene richness
1. 对背景页、痛点页、案例页、场景页，优先采用有真实业务语境的场景化画面，而不是只有单一抽象背景。
2. 必要时可加入次级视觉元素来丰富层次，例如辅助场景、局部细节、环境线索、信息卡片感元素，但不要堆砌。
3. 在 prompt 的英文描述中，优先体现这类方向：
   - `industry context`
   - `real-world environment`
   - `scene-based composition`
   - `supporting visual details`
4. 这些方向是设计引导，不是机械模板；要结合页面主题自行决定具体呈现方式。

## A/B 页原则
1. `A` 类页是 information-led slide。重点是清晰结构、可读的中文标题和中文要点、服务信息表达的版式。
2. `B` 类页是 impact-led slide。可以更有情绪和画面张力，但仍必须与页面主题强相关，不能只是空洞海报。同时金句要用大号字体，强烈视觉效果，位于视觉中心的焦点位置，不要被复杂画面淹没了。

## Typography and hierarchy
1. 文字层级属于设计决策的一部分，不要机械套用固定模板。
2. 根据页面类型、文字量、信息复杂度和表达重点，自主决定使用 1 层、2 层或 3 层文字层级。
3. `B` 类页通常不需要复杂层级，往往 1 层或 2 层就足够；信息更丰富、结构更复杂的 `A` 类页可以使用更明确的层级组织。
4. 一级标题通常应更醒目，优先使用 `bold` 或更强字重；标题颜色不要被固定死，应由你根据页面气质和深色背景自行选择协调、清晰、不过分违和的亮色或高对比颜色。
5. 二级和三级文字应通过字重、字号、颜色、间距来拉开层次，但保持同一套 clean sans-serif Chinese typography，不要做花哨字体拼贴。
6. 如果页面文字较少，不要为了形式感强行做三层级；如果页面文字较多且层次丰富，应优先保证层级清楚、阅读路径自然。

## layout_type 约束
- `cover`: 建立全局主题与第一印象。
- `section_header`: 用于章节转场，强调章节气质。
- `bullet_points`: 标题 + 精炼要点，强调清晰与阅读效率。
- `comparison`: 强调左右、前后、旧新、问题与方案等对照关系。
- `process_flow`: 强调步骤、路径、链路、阶段推进。
- `framework`: 强调层次、模块、框架和结构关系。
- `case_study`: 强调案例背景、方案、结果或复盘逻辑。
- `data_evidence`: 强调指标、趋势、证据、对照。
- `image_only`: 适合主张强、信息少、画面主导的页面。
- `summary`: 用于总结、收束、路线图或行动指向。

## 内容蒸馏规则
1. 对 `generated` 页面，从 `Content Input` 中提炼适合上屏的中文文案，不要把整段讲稿直接搬进图里。
2. 对 `generated` 页，`A` 页通常输出 1 个中文标题 + 2 至 4 个中文要点。
3. 对 `generated` 页，`B` 页通常输出 1 个中文“金句”；必要时可加 1 个短副标题。
4. 对 `generated` 页面，中文文案必须短、准、可上屏，避免长句讲稿化。
5. 对 `locked` 页面，禁止执行任何蒸馏，直接原样使用 `Source Text`。

## 禁止事项
1. 禁止出现 watermark, logo, copyright mark, AI generated mark，“AI生成”类似的水印。
2. 禁止出现无意义伪文字。
3. 禁止把 prompt 写成空洞的艺术评论。
4. 禁止反复使用固定风格口头禅、固定材质、固定主物体、固定镜头模板。

## 输出要求
输出必须是 JSON 对象，包含 `items` 数组。
每个项只包含：
- `page_id`
- `text`
- `prompt`

其中：
1. `text` 是最终上屏的中文文字成稿，只保留用户会在 PPT 页面上看到的内容。
2. `A` 页的 `text` 用多行纯文本表达：第一行标题，后续每行一个要点，使用 `- ` 开头。
3. `B` 页的 `text` 默认只写 1 行金句；如果确实需要副标题，可放在第二行。
4. `prompt` 必须是紧凑、具体、可执行的英文指令，内部可用引号包含需要渲染的中文标题或中文要点，而且这些中文内容必须与 `text` 保持一致。
5. 如果页面是 locked，`text` 与 `prompt` 的中文渲染内容都必须逐字忠实于 `Source Text`。"""


def _build_user_prompt(plan: SlidePlanDocument, page_batch: list[dict[str, Any]]) -> str:
    plan_overview = "\n".join(
        [
            (
                f"- {p.page_id}: title={p.title or ''}; category={p.category}; "
                f"layout_type={p.layout_type}; content_mode={p.content_mode}"
            )
            for p in plan.pages
        ]
    )
    page_map = {page.page_id: page for page in plan.pages}
    batch_sections: list[str] = []
    for page_spec in page_batch:
        plan_page = page_map.get(page_spec["page_id"])
        if plan_page is None:
            continue
        batch_sections.append(_build_page_brief(plan_page, page_spec["content_input"]))

    batch_detail = "\n---\n".join(batch_sections)

    return f"""Deck Overview:
{plan_overview}

Current Batch:
{batch_detail}

Additional Directives:
- Generate one design item per page in the current batch.
- Keep the deck visually coherent but not repetitive.
- Use different compositions across adjacent pages.
- Make independent design decisions for each page based on its theme, category, and layout type.
- Respect `Content Mode` strictly. Locked pages must reuse `Source Text` exactly.
- Prefer dark, low-luminance, projection-friendly backgrounds across the deck.
- Use `dark navy radial glow background, subtle top-center blue illumination` as the default background direction unless the page strongly requires another dark treatment.
- Never use light background, white background, bright canvas, or pale gradient.
- When the page is grounded in real-world business context, prefer scene-based composition with real-world environment cues rather than generic abstract technology imagery.
- When helpful, enrich those pages with supporting visual details instead of relying on a single abstract object.
- For A pages, prioritize readable Chinese information layout over theatrical visual effects.
- For B pages, prioritize a strong thematic image derived from the page topic, not generic sci-fi.
- Treat typography hierarchy as a page-specific design decision. Use one, two, or three levels only when the content actually benefits from it.
- For text-heavy structured A pages, clearer hierarchy is usually beneficial; for B pages, avoid forcing overly complex hierarchy.
- Make primary headings more prominent, usually with bolder weight. Let the heading color be chosen by the design itself so it fits the page and remains clear on the dark background.
- The `text` field is the final on-slide copy for user review.
- The descriptive prompt language must be English.
- Any text to render on the slide must remain Chinese inside quotes.
- Do not output explanations. Output JSON only."""


async def _generate_prompt_batch(
    *,
    client: AsyncOpenAI | None,
    settings: Any,
    plan: SlidePlanDocument,
    page_batch: list[dict[str, Any]],
    start_index: int,
    semaphore: asyncio.Semaphore,
) -> tuple[list[PromptItem], list[ScreenTextItem]]:
    async with semaphore:
        print_stderr(
            f"使用 {settings.text_provider}/{settings.text_model} 导演第 {start_index + 1} 至 {start_index + len(page_batch)} 页的视觉设计..."
        )
        payload = await _generate_json_text(
            client=client,
            settings=settings,
            system_prompt=_build_system_prompt(),
            user_prompt=_build_user_prompt(plan, page_batch),
            temperature=0.4,
        )

    expected_page_ids = [page_spec["page_id"] for page_spec in page_batch]
    received_items = payload.get("items", [])
    received_page_ids = [item.get("page_id") for item in received_items]
    if sorted(received_page_ids) != sorted(expected_page_ids):
        raise OutputValidationError(
            "模型返回的页面集合与请求不一致",
            details={
                "expected_page_ids": expected_page_ids,
                "received_page_ids": received_page_ids,
            },
        )

    page_spec_map = {page_spec["page_id"]: page_spec for page_spec in page_batch}
    prompt_items: list[PromptItem] = []
    screen_text_items: list[ScreenTextItem] = []
    for item in received_items:
        page_id = item["page_id"]
        text = _normalize_screen_text(item["text"])
        prompt = item["prompt"].strip()
        page = page_spec_map[page_id]["page"]
        if page.content_mode == "locked":
            validate_locked_page_output(page, text, prompt)
        screen_text_items.append(ScreenTextItem(page_id=page_id, text=text))
        prompt_items.append(PromptItem(page_id=page_id, prompt=prompt))
    return prompt_items, screen_text_items


async def _run_batches(
    *,
    client: AsyncOpenAI | None,
    settings: Any,
    plan: SlidePlanDocument,
    page_specs: list[dict[str, Any]],
    batch_size: int,
    parallel: int,
) -> tuple[list[PromptItem], list[ScreenTextItem]]:
    semaphore = asyncio.Semaphore(parallel)
    tasks = []
    for i in range(0, len(page_specs), batch_size):
        batch_specs = page_specs[i:i + batch_size]
        tasks.append(
            _generate_prompt_batch(
                client=client,
                settings=settings,
                plan=plan,
                page_batch=batch_specs,
                start_index=i,
                semaphore=semaphore,
            )
        )

    results = await asyncio.gather(*tasks)
    all_prompts: list[PromptItem] = []
    all_screen_texts: list[ScreenTextItem] = []
    for batch_prompts, batch_screen_texts in results:
        all_prompts.extend(batch_prompts)
        all_screen_texts.extend(batch_screen_texts)
    return all_prompts, all_screen_texts


def handle_visual_prompt_design(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = resolve_project_dir(args.project_dir, create=False)
    settings = load_settings()
    state = load_state(project_dir)

    # 1. 初始化兼容客户端
    client: AsyncOpenAI | None = None
    if settings.text_provider == "deepseek":
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )

    # 2. 读取上下文
    plan_path = project_dir / "plan" / "plan.json"
    draft_path = project_dir / "draft" / "slide_draft.json"

    plan = SlidePlanDocument(**read_json(plan_path))
    draft: SlideDraftDocument | None = None
    if draft_path.exists():
        draft = SlideDraftDocument(**read_json(draft_path))

    target_ids = [p.strip() for p in args.target_pages.split(",") if p.strip()] if args.target_pages else None
    page_specs = build_page_specs(plan, draft, target_ids)
    if not page_specs:
        return {
            "project_id": state["project_id"],
            "warnings": [f"没有找到匹配的页面: {args.target_pages}"] if target_ids else ["plan 中没有可处理页面"],
            "metrics": {"total_prompts": 0},
            "provider": settings.text_provider,
            "model": settings.text_model,
        }

    # 3. 分批并发生成
    batch_size = max(1, args.batch_size)
    parallel = max(1, args.parallel)
    all_prompts, all_screen_texts = asyncio.run(
        _run_batches(
            client=client,
            settings=settings,
            plan=plan,
            page_specs=page_specs,
            batch_size=batch_size,
            parallel=parallel,
        )
    )

    # 4. 写入结果
    screen_text_file = project_dir / "prompts" / "screen_text.json"
    prompt_file = project_dir / "prompts" / "prompts.json"
    prompt_file.parent.mkdir(exist_ok=True)
    if screen_text_file.exists():
        existing_screen_doc = ScreenTextDocument(**read_json(screen_text_file))
        screen_text_map = {item.page_id: item for item in existing_screen_doc.items}
        for item in all_screen_texts:
            screen_text_map[item.page_id] = item
        merged_screen_items = sorted(screen_text_map.values(), key=lambda x: int(x.page_id[1:]))
    else:
        merged_screen_items = all_screen_texts

    if prompt_file.exists():
        existing_doc = PromptDocument(**read_json(prompt_file))
        prompt_map = {item.page_id: item for item in existing_doc.items}
        for item in all_prompts:
            prompt_map[item.page_id] = item
        merged_items = sorted(prompt_map.values(), key=lambda x: int(x.page_id[1:]))
    else:
        merged_items = all_prompts

    screen_text_doc = ScreenTextDocument(project_id=state["project_id"], items=merged_screen_items)
    prompt_doc = PromptDocument(project_id=state["project_id"], items=merged_items)
    write_json(screen_text_file, screen_text_doc.model_dump())
    write_json(prompt_file, prompt_doc.model_dump())

    # 5. 更新状态
    previous_state = state["current_state"]
    state = set_artifact(state, "screen_text", "prompts/screen_text.json", exists=True)
    state = set_artifact(state, "prompts", "prompts/prompts.json", exists=True)
    state["current_state"] = "PromptsGenerated"
    state["last_completed_step"] = TOOL_NAME
    state = append_transition(state, {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_state": previous_state,
        "to_state": "PromptsGenerated",
        "trigger": "tool_success",
        "step": TOOL_NAME,
        "note": f"Generated {len(all_prompts)} visual prompts and screen text"
    })
    save_state(project_dir, state)

    return {
        "project_id": state["project_id"],
        "artifacts": ["prompts/screen_text.json", "prompts/prompts.json"],
        "metrics": {
            "total_prompts": len(all_prompts),
            "total_screen_text_items": len(all_screen_texts),
        },
        "provider": settings.text_provider,
        "model": settings.text_model,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--target-pages", default=None, help="目标页面ID (逗号分隔)")
    parser.add_argument("--batch-size", type=int, default=5, help="每批生成的页面数量")
    parser.add_argument("--parallel", type=int, default=1, help="并发批次数量")
    return run_cli(handle_visual_prompt_design, tool=TOOL_NAME, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
