#!/usr/bin/env python
"""Generate slide draft content from planning in batches.

This is Program 3 in the PPT workflow. It reads the outline.md and plan.json
and generates content for specific page IDs using an LLM.

Supported models:
    - gemini: Google Gemini (via OpenAI-compatible API)
    - deepseek: DeepSeek (deepseek-chat)

Usage:
    python scripts/slide_draft_generate.py --project-dir PPT/03 --page-ids p1,p2,p3 [--model gemini|deepseek] [--output-json]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import json

from openai import OpenAI

from pptflow.cli import run_cli
from pptflow.config import load_settings
from pptflow.errors import InputError, StateStoreError, OutputValidationError
from pptflow.json_io import read_json, write_json
from pptflow.schemas import SlideDraftDocument, SlideDraftSlide, SlidePlanDocument
from pptflow.state_store import append_transition, load_state, save_state, set_artifact

TOOL_NAME = "slide_draft_generate"

# 支持的文本模型类型
TextModel = Literal["gemini", "deepseek"]

# 模型配置
MODEL_CONFIG = {
    "gemini": {
        "provider": "google",
        "model_name": "gemini-2.5-flash",
        "env_key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    "deepseek": {
        "provider": "deepseek",
        "model_name": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
    },
}


def _generate_json_text(
    client,
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
    parser.add_argument(
        "--model",
        choices=["gemini", "deepseek"],
        default="gemini",
        help="文本生成模型: gemini (Google Gemini) 或 deepseek (DeepSeek)"
    )
    return parser

def _build_system_prompt() -> str:
    return """你是一个专业的 PPT 资深课件开发者，同时精通视觉设计。
你的任务是为 PPT 页面提供【文字内容】和【视觉风格描述】。

## 核心原则

### 1. 文字分离原则
- `slide_text`：直接画在图片上的极简文字（短语、标签、数字），绝对禁止长段落
- `speaker_note`：演讲备注，包含深度内容（100-200字），不在画面显示

### 2. 视觉风格描述（关键）
- `visual_style`：**英文描述**，供 AI 图像生成模型使用
- 必须包含：背景描述、色调、主要视觉元素、氛围关键词
- 禁止包含：具体中文文字（文字在 slide_text 中单独指定）
- 长度：50-100 英文单词

### 3. A/B 类页面视觉差异（必须严格遵守）

**A 类（信息型视觉页）**：
- 核心：强调结构化信息承载、文字可读性
- 背景：弱装饰背景、简洁纯色、轻微渐变、低干扰
- 色调：浅色系或中性色、柔和、易读
- 元素：简单图标、清晰分隔线、结构化布局
- 氛围：秩序感、清晰层次、专业、不抢眼

**B 类（情绪型/金句型视觉页）**：
- 核心：强调视觉冲击、意象、氛围与核心表达
- 背景：复杂渐变、光影效果、粒子/网格/电路等装饰、强背景画面
- 色调：深色系、高对比度、科技蓝/商务紫
- 元素：3D 图形、抽象几何、意象元素
- 氛围：冲击力、情绪渲染、未来感

**B 类占比约束（必须严格遵守）**：
- B 类页面占比必须在 **20% - 40%** 之间
- 禁止出现全是 A 类或全是 B 类的退化结果
- 典型分布：25 页 PPT 中，B 类应为 5-10 页

### 4. 视觉策略适配
- `simple_background`：简洁背景，文字为主，适合 A 类
- `emotional_visual`：情感化视觉，强调氛围，适合 B 类

### 5. 布局类型参考
- `cover`：封面风格，大标题居中，视觉冲击力强
- `section_divider`：章节分隔，强调视觉层次
- `bullet_list`：列表布局，清晰易读
- `comparison`：对比布局，左右分栏
- `flow_chart`：流程图，箭头连接
- `metrics_showcase`：数据展示，大数字突出
- `case_study`：案例展示，图文结合

## 输出格式

```json
{
  "slides": [
    {
      "page_id": "页面ID",
      "title": "极简标题",
      "slide_text": ["极简短语1", "极简短语2"],
      "quote": "简短金句(可选)",
      "visual_style": "English description: background, colors, elements, mood...",
      "speaker_note": "深度演讲内容（100-200字）",
      "intent": "cover|content|quote|transition|summary"
    }
  ]
}
```

## visual_style 编写规范

1. **必须用英文**：图像模型对英文理解更准确
2. **结构化描述**：
   - Background: [背景描述]
   - Color palette: [色调，如 dark blue gradient, warm orange]
   - Visual elements: [视觉元素，如 abstract network nodes, data charts]
   - Atmosphere: [氛围，如 professional, futuristic, energetic]
3. **禁止**：在 visual_style 中包含具体中文文字

## 示例

A 类信息页 visual_style：
"Clean minimalist slide with light gray (#F5F7FA) background. Color palette: soft blue accents (#4A90D9), dark gray text (#333333). Visual elements: simple bullet point icons, subtle divider lines, structured layout with clear hierarchy. Atmosphere: clear, professional, easy to read, organized."

B 类情绪页 visual_style：
"A modern technology-themed cover with deep blue gradient background featuring abstract network connection patterns and glowing data particles. Color palette: navy blue (#0A1628), electric blue (#00D4FF), white accents. Visual elements: floating geometric shapes, subtle grid lines, soft light rays. Atmosphere: professional, futuristic, high-tech, impactful."

注意：禁止输出多余字段。所有中文内容使用简体中文。"""

def _build_user_prompt(outline_text: str, plan_batch: list[dict[str, Any]], language: str) -> str:
    batch_info = "\n".join([
        f"- Page [{p['page_id']}]: {p.get('title', '未命名')}\n"
        f"  - 内容要点: {p.get('content_hint', '无')}\n"
        f"  - 页面类别: {p.get('category', 'A')} (A=信息型, B=情绪型/金句型)\n"
        f"  - 布局类型: {p.get('layout_type', 'bullet_list')}\n"
        f"  - 视觉策略: {p.get('prompt_strategy', 'simple_background')}\n"
        f"  - 风格标签: {', '.join(p.get('style_tags', [])) or '无'}"
        for p in plan_batch
    ])
    return f"""全局大纲内容：
---
{outline_text}
---

当前批次生成的页面规划：
{batch_info}

目标语言：{language}

请为上述页面生成详细文案，包括文字内容和视觉风格描述。
**重要**：根据每个页面的类别（A/B）、布局类型和视觉策略，生成差异化的 visual_style。
输出必须是一个 JSON 对象，包含 `slides` 数组。"""

def handle_slide_draft_generate(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = Path(args.project_dir).expanduser().resolve()
    target_page_ids = [p.strip() for p in args.page_ids.split(",") if p.strip()]

    # 1. 获取模型配置
    model_choice: TextModel = args.model
    model_config = MODEL_CONFIG[model_choice]

    # 2. 验证环境与 API Key
    api_key = os.getenv(model_config["env_key"])
    if not api_key:
        raise InputError(f"环境变量 {model_config['env_key']} 未设置")

    # 初始化客户端
    client = OpenAI(
        api_key=api_key,
        base_url=model_config["base_url"],
    )

    # 3. 加载状态
    state = load_state(project_dir)
    settings = load_settings()

    # 4. 读取上下文
    outline_path = project_dir / "outline" / "outline.md"
    plan_path = project_dir / "plan" / "plan.json"
    if not outline_path.exists() or not plan_path.exists():
        raise InputError("大纲文件或规划文件缺失")

    outline_text = outline_path.read_text(encoding="utf-8")
    plan_data = read_json(plan_path)
    plan = SlidePlanDocument(**plan_data)

    # 5. 提取批次规划
    plan_batch = [p.model_dump() for p in plan.pages if p.page_id in target_page_ids]
    if not plan_batch:
        raise InputError(f"在 plan.json 中未找到指定的 Page IDs: {target_page_ids}")

    # 6. 调用 LLM 生成批次文案
    print(f"使用模型 {model_config['provider']}/{model_config['model_name']} 生成文案...")
    response_data = _generate_json_text(
        client=client,
        model=model_config["model_name"],
        system_prompt=_build_system_prompt(),
        user_prompt=_build_user_prompt(outline_text, plan_batch, settings.default_language),
        temperature=0.7,
    )

    # 7. 增量更新 draft/slide_draft.json
    draft_file = project_dir / "draft" / "slide_draft.json"
    draft_file.parent.mkdir(exist_ok=True)

    # 构建页面元信息映射，用于填充 metadata
    plan_meta_map = {p["page_id"]: p for p in plan_batch}

    # intent 值映射：将 LLM 可能返回的非标准值映射到标准值
    INTENT_MAP = {
        "section_divider": "transition",
        "flow_chart": "content",
        "metrics_showcase": "content",
        "comparison": "content",
        "case_study": "content",
        "bullet_list": "content",
    }

    def build_slide_from_response(slide_data: dict[str, Any]) -> SlideDraftSlide:
        """从 LLM 响应构建 SlideDraftSlide，将 visual_style 存入 metadata"""
        page_id = slide_data.get("page_id", "")
        plan_info = plan_meta_map.get(page_id, {})

        # 构建 metadata，包含 visual_style 和 plan 中的元信息
        metadata = dict(slide_data.get("metadata", {}))
        if "visual_style" in slide_data:
            metadata["visual_style"] = slide_data["visual_style"]
        # 从 plan 继承元信息
        for key in ["category", "layout_type", "prompt_strategy", "style_tags"]:
            if key in plan_info:
                metadata[key] = plan_info[key]

        # 映射 intent 到有效值
        raw_intent = slide_data.get("intent", "content")
        intent = INTENT_MAP.get(raw_intent, raw_intent)
        # 确保最终值在允许范围内
        valid_intents = {"cover", "content", "quote", "transition", "summary"}
        if intent not in valid_intents:
            intent = "content"

        return SlideDraftSlide(
            page_id=page_id,
            source_section=slide_data.get("source_section"),
            title=slide_data.get("title", ""),
            slide_text=slide_data.get("slide_text", []),
            quote=slide_data.get("quote"),
            speaker_note=slide_data.get("speaker_note"),
            intent=intent,
            metadata=metadata,
        )

    if draft_file.exists():
        existing_draft = SlideDraftDocument(**read_json(draft_file))
        # 移除已存在的同 ID 页面（如有），然后添加新页面
        new_slides = [build_slide_from_response(s) for s in response_data.get("slides", [])]
        new_ids = {s.page_id for s in new_slides}
        merged_slides = [s for s in existing_draft.slides if s.page_id not in new_ids]
        merged_slides.extend(new_slides)
        # 保持 Page ID 顺序（按 plan.json 排序）
        order = {p.page_id: i for i, p in enumerate(plan.pages)}
        merged_slides.sort(key=lambda s: order.get(s.page_id, 999))
        draft_doc = SlideDraftDocument(project_id=state["project_id"], slides=merged_slides)
    else:
        draft_doc = SlideDraftDocument(
            project_id=state["project_id"],
            slides=[build_slide_from_response(s) for s in response_data.get("slides", [])]
        )

    write_json(draft_file, draft_doc.model_dump())

    # 8. 更新状态
    state = set_artifact(state, "draft", "draft/slide_draft.json", exists=True)
    state["current_state"] = "DraftGenerated"
    state["last_completed_step"] = "slide_draft_generate_batch"

    append_transition(state, {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_state": state["current_state"],
        "to_state": "DraftGenerated",
        "trigger": "tool_success",
        "step": "slide_draft_generate",
        "note": f"Batch generated for: {args.page_ids} (model: {model_choice})",
    })
    save_state(project_dir, state)

    return {
        "project_id": state["project_id"],
        "model": model_choice,
        "batch_pages": target_page_ids,
        "total_draft_pages": len(draft_doc.slides),
        "artifacts": ["draft/slide_draft.json"]
    }

def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    _add_script_args(parser)
    return run_cli(handle_slide_draft_generate, tool=TOOL_NAME, parser=parser)

if __name__ == "__main__":
    raise SystemExit(main())
