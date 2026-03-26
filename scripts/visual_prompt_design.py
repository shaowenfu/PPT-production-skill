#!/usr/bin/env python
"""Visual Prompt Design Script (The Visual Director).

This is Step 5 in the PPT workflow. It reads plan.json and draft.json
to generate high-impact visual prompts for image models using DeepSeek.

Usage:
    python scripts/visual_prompt_design.py --project-dir PPT/03 [--batch-size 5]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from typing import Any

from _bootstrap import bootstrap_project

bootstrap_project(__file__)

from openai import OpenAI

from pptflow.cli import print_stderr, run_cli
from pptflow.config import load_settings
from pptflow.errors import InputError, OutputValidationError
from pptflow.json_io import read_json, write_json
from pptflow.paths import resolve_project_dir
from pptflow.schemas import SlideDraftDocument, SlidePlanDocument, PromptDocument, PromptItem
from pptflow.state_store import append_transition, load_state, save_state, set_artifact

TOOL_NAME = "visual_prompt_design"


def _generate_json_text(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.8,
) -> dict[str, Any]:
    """调用 LLM 生成 JSON 响应"""
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise InputError(f"LLM 调用失败: {exc}") from exc

    content = response.choices[0].message.content
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise OutputValidationError("模型响应不是有效的 JSON") from exc
    return payload


def _build_system_prompt() -> str:
    return """你是一个具备顶级美学修养的 PPT 视觉总监 (Art Director)。
你的任务是将深度文案 (Draft Content) 转化为极致视觉表现力的图像提示词 (Visual Prompt)。

## 核心设计法则：视觉对比 (Contrast)
遵循《非设计师设计指南》，通过以下手段产生"高级感"：
1. **材质对比 (Texture Contrast)**：硬质实体 (3D Metal) 与 软质背景 (Particles/Fog) 的冲突。
2. **光影对比 (Lighting Contrast)**：冷色调背景 (Midnight Blue) 与 暖色调主光源 (Amber/Gold) 的对撞。
3. **虚实对比 (Depth Contrast)**：模糊的背景网格 (Grid/Bokeh) 与 极其锋利的 3D 文字边缘 (Relief)。

## 差异化信息密度策略 (Density Differentiation)

**A 类 (信息型/架构型)**：
- **目标**：重内容，保信息。
- **文案蒸馏**：从内容中提炼"1个核心标题 + 3至5个逻辑要点"。
- **视觉层级**：文字是主角。背景应是 Clean UI Dashboard 或 Frosted Glass Cards。
- **Typography Layer**: 必须写在半透明毛玻璃卡片上，确保绝对易读。

**B 类 (情绪型/金句型)**：
- **目标**：重冲击，保金句。
- **文案蒸馏**：从内容中提取"唯一且极具灵魂的金句"。
- **视觉层级**：画面是主角。采用 Cinematic 叙事、Surreal Metaphor (视觉隐喻)。
- **Typography Layer**: 文字要像 Monumental Typography (纪念碑)，具有极强的物理体积和阴影。

## 严苛视觉禁令 (CRITICAL NEGATIVE CONSTRAINTS)
1. **禁止文字污染**：严禁在 prompt 中出现“AI生成”、“AI Generated”、“Made by AI”、“水印”、“Logo”或任何版权标识。
2. **禁止描述性文字误入**：prompt 必须是纯粹的视觉描述，不要包含“这是一张...的照片”等废话。
3. **纯净画面**：除非 `refined_text` 中明确要求渲染的标题，否则画面中不得出现任何杂乱字符或无意义的伪文字。

## 提示词四层结构 (Four-Layer Structure)
1. **[Environment]**: 环境基调、对比色板（Color Palette）。
2. **[Typography Layer]**: 文字材质、物理坐标（如 Upper 40%）、留白保护区。**必须严格仅渲染 `refined_text` 中的内容。**
3. **[Visual Anchor]**: 与文案语义呼应的 3D 视觉中心（如：断裂的齿轮、发光的灯塔）。
4. **[Render & Quality]**: Octane render, 8k, Unreal Engine 5 style, hyper-realistic, **No Watermark, No AI text signatures**.

## 输出格式
输出必须是一个 JSON 对象，包含 `prompts` 数组。每个项必须包含：
- `page_id`
- `prompt`: 完整的、面向主流图像生成模型的英文指令。
- `refined_text`: JSON 对象，包含标题和列表（用于记录蒸馏后的文字）。

注意：禁止在 prompt 中包含任何中文文字。若涉及文字渲染，必须使用英文指令指定：Render text "指定文字" in high-quality 3D relief style. 严禁渲染任何非业务相关的标注词。"""



def _build_user_prompt(plan: SlidePlanDocument, draft_batch: list[dict[str, Any]]) -> str:
    plan_overview = "\n".join([f"- {p.page_id}: {p.title} ({p.category})" for p in plan.pages])
    batch_detail = ""
    for d in draft_batch:
        p_info = next((p for p in plan.pages if p.page_id == d["page_id"]), None)
        batch_detail += f"--- Page {d['page_id']} ---\n"
        batch_detail += f"Category: {p_info.category if p_info else 'A'}\n"
        batch_detail += f"Draft Content: {d['content']}\n\n"

    return f"""全局幻灯片规划概要：
{plan_overview}

当前批次待设计的页面内容：
{batch_detail}

请根据视觉导演法则和对比原则，为每页生成最终的提示词。输出 JSON 必须包含 `prompts` 数组。"""


def handle_visual_prompt_design(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = resolve_project_dir(args.project_dir, create=False)
    settings = load_settings()
    state = load_state(project_dir)

    # 1. 初始化 DeepSeek 客户端
    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )

    # 2. 读取上下文
    plan_path = project_dir / "plan" / "plan.json"
    draft_path = project_dir / "draft" / "slide_draft.json"

    plan = SlidePlanDocument(**read_json(plan_path))
    draft = SlideDraftDocument(**read_json(draft_path))

    # 3. 分批异步生成
    batch_size = args.batch_size
    all_prompts = []

    for i in range(0, len(draft.slides), batch_size):
        batch_slides = draft.slides[i:i+batch_size]
        draft_batch = [s.model_dump() for s in batch_slides]

        print_stderr(
            f"使用 DeepSeek/{settings.text_model} 导演第 {i + 1} 至 {i + len(batch_slides)} 页的视觉设计..."
        )

        payload = _generate_json_text(
            client=client,
            model=settings.text_model,
            system_prompt=_build_system_prompt(),
            user_prompt=_build_user_prompt(plan, draft_batch),
            temperature=0.8
        )

        for item in payload.get("prompts", []):
            all_prompts.append(PromptItem(page_id=item["page_id"], prompt=item["prompt"]))

    # 4. 写入结果
    prompt_file = project_dir / "prompts" / "prompts.json"
    prompt_file.parent.mkdir(exist_ok=True)
    prompt_doc = PromptDocument(project_id=state["project_id"], items=all_prompts)
    write_json(prompt_file, prompt_doc.model_dump())

    # 5. 更新状态
    previous_state = state["current_state"]
    state = set_artifact(state, "prompts", "prompts/prompts.json", exists=True)
    state["current_state"] = "AssetsGenerated"
    state["last_completed_step"] = TOOL_NAME
    state = append_transition(state, {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_state": previous_state,
        "to_state": "AssetsGenerated",
        "trigger": "tool_success",
        "step": "visual_prompt_generate",
        "note": f"Generated {len(all_prompts)} visual prompts"
    })
    save_state(project_dir, state)

    return {
        "project_id": state["project_id"],
        "artifacts": ["prompts/prompts.json"],
        "metrics": {"total_prompts": len(all_prompts)},
        "model": settings.text_model,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--batch-size", type=int, default=5, help="每批生成的页面数量")
    return run_cli(handle_visual_prompt_design, tool=TOOL_NAME, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
