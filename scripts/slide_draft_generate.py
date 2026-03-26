#!/usr/bin/env python
"""Generate slide draft content from planning in batches.

This is Program 3 in the PPT workflow. It reads the outline.md and plan.json
and generates content for specific page IDs using DeepSeek LLM.

Usage:
    python scripts/slide_draft_generate.py --project-dir PPT/03 --page-ids p1,p2,p3 [--output-json]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openai import OpenAI

from pptflow.cli import run_cli
from pptflow.config import load_settings
from pptflow.errors import InputError, OutputValidationError
from pptflow.json_io import read_json, write_json
from pptflow.schemas import SlideDraftDocument, SlideDraftSlide, SlidePlanDocument
from pptflow.state_store import append_transition, load_state, save_state, set_artifact

TOOL_NAME = "slide_draft_generate"


def _generate_json_text(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
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
    if not isinstance(payload, dict):
        raise OutputValidationError("模型响应 JSON 必须是对象")
    return payload


def _add_script_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--page-ids", required=True, help="本批次要生成的 Page IDs (逗号分隔)")
    parser.add_argument("--output-json", action="store_true", default=False, help="结果输出到 stdout")
    return parser


def _build_system_prompt() -> str:
    return """你是一个专业的 PPT 领域内容专家与资深研究员。
你的任务是根据 PPT 的分页规划 (plan.json)，为每页 PPT 撰写深度、逻辑严密的业务或技术分析内容。

## 核心任务：内容扩写 (Content Expansion)

你的输出将作为后续视觉设计的核心知识库 (Knowledge Base)。

1. **深度化**：不要复述标题，而是根据 `content_hint` 和全局大纲，扩充为 200-400 字的详细内容。
2. **逻辑性**：阐述因果关系、技术路径、痛点成因或解决方案细节。
3. **专业性**：使用准确的行业术语。

## 差异化处理 (A/B Category)
- **A 类 (信息型)**：提供详实的数据逻辑、流程细节或多维度分析。
- **B 类 (情绪型)**：挖掘文案背后的冲突点、愿景或核心情感价值，为视觉隐喻提供素材。

## 严苛输出约束 (CRITICAL)
1. 输出必须是一个 JSON 对象。
2. 包含且仅包含两个顶层字段：`project_id` (字符串) 和 `slides` (数组)。
3. `slides` 数组中的每个对象仅允许包含 `page_id` 和 `content` 两个字段。
4. 确保 JSON 格式合法，无截断。

## 示例格式 (必须严格遵守)
{
  "project_id": "ai_telecom",
  "slides": [
    {
      "page_id": "p1",
      "content": "这里是针对 p1 深度扩写的内容..."
    }
  ]
}
"""


def _build_user_prompt(outline_text: str, plan_batch: list[dict[str, Any]], language: str) -> str:
    batch_info = "\n".join([
        f"- Page [{p['page_id']}]: {p.get('title', '未命名')}\n"
        f"  - 内容提示: {p.get('content_hint', '无')}\n"
        f"  - 类别: {p.get('category', 'A')}\n"
        f"  - 布局: {p.get('layout_type', 'bullet_list')}"
        for p in plan_batch
    ])
    return f"""全局大纲内容：
---
{outline_text}
---

当前批次生成的页面规划：
{batch_info}

目标语言：{language}

请严格按照 system prompt 的格式输出。不要在 content 中包含 Markdown 标题。"""


def handle_slide_draft_generate(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = Path(args.project_dir).expanduser().resolve()
    target_page_ids = [p.strip() for p in args.page_ids.split(",") if p.strip()]

    # 1. 加载设置与环境
    settings = load_settings()
    state = load_state(project_dir)

    # 2. 初始化 DeepSeek 客户端
    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )

    # 3. 读取上下文
    outline_path = project_dir / "outline" / "outline.md"
    plan_path = project_dir / "plan" / "plan.json"
    if not outline_path.exists() or not plan_path.exists():
        raise InputError("大纲文件或规划文件缺失")

    outline_text = outline_path.read_text(encoding="utf-8")
    plan_data = read_json(plan_path)
    plan = SlidePlanDocument(**plan_data)

    # 4. 准备批次数据
    plan_batch = [p.dict() for p in plan.pages if p.page_id in target_page_ids]
    if not plan_batch:
        return {"ok": True, "message": "没有找到需要生成的 Page IDs"}

    # 5. 调用 LLM
    sys_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(outline_text, plan_batch, "简体中文")
    
    payload = _generate_json_text(client, settings.text_model, sys_prompt, user_prompt)
    
    # 强制注入 project_id
    payload["project_id"] = plan.project_id
    
    # 6. 验证并保存
    try:
        draft_doc = SlideDraftDocument(**payload)
    except Exception as exc:
        raise OutputValidationError(f"Pydantic 校验失败: {exc}")

    draft_path = project_dir / "draft" / "slide_draft.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 合并已有内容
    if draft_path.exists():
        existing_data = read_json(draft_path)
        existing_slides = {s["page_id"]: s for s in existing_data.get("slides", [])}
        for slide in draft_doc.slides:
            existing_slides[slide.page_id] = slide.dict()
        
        final_slides = sorted(existing_slides.values(), key=lambda x: int(x["page_id"][1:]))
        write_json(draft_path, {"project_id": plan.project_id, "slides": final_slides})
    else:
        write_json(draft_path, draft_doc.dict())

    # 7. 更新状态
    set_artifact(state, "slide_draft", str(draft_path.relative_to(project_dir)))
    state["current_state"] = "DraftGenerated"
    state = append_transition(state, {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_state": "Initialized",
        "to_state": "DraftGenerated",
        "trigger": "tool_success",
        "step": "slide_draft_generate",
        "note": f"Generated draft for pages: {args.page_ids}"
    })
    save_state(project_dir, state)

    return {
        "ok": True,
        "tool": TOOL_NAME,
        "project_id": plan.project_id,
        "artifacts": ["draft/slide_draft.json"],
        "metrics": {"pages_generated": len(target_page_ids)}
    }


if __name__ == "__main__":
    parser = _add_script_args(argparse.ArgumentParser(prog=TOOL_NAME))
    run_cli(handle_slide_draft_generate, tool=TOOL_NAME, parser=parser)
