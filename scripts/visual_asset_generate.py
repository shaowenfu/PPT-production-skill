#!/usr/bin/env python
"""Generate visual assets using various image generation models.

This is Program 6 in the PPT workflow. It reads prompts from prompts.json,
calls image generation API to generate full-slide images, and creates an asset manifest.

Supported models:
    - gemini: Google Gemini (gemini-3.1-flash-image-preview)
    - doubao: 火山引擎 Doubao (volcengine/doubao-seedream-5.0-lite)

Usage:
    python scripts/visual_asset_generate.py --project-dir PPT/03 [--target-pages p1,p2] [--model gemini|doubao]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from google import genai
from openai import OpenAI
from PIL import Image

from pptflow.cli import run_cli
from pptflow.errors import InputError, UpstreamServiceError
from pptflow.json_io import read_json, write_json
from pptflow.schemas import AssetItem, AssetManifest, PromptDocument
from pptflow.state_store import (
    append_transition,
    assert_state_has_artifact,
    load_state,
    save_state,
    set_artifact,
)

TOOL_NAME = "visual_asset_generate"

# 支持的模型类型
ImageModel = Literal["gemini", "doubao"]

# 模型配置
MODEL_CONFIG = {
    "gemini": {
        "provider": "google",
        "model_name": "gemini-3.1-flash-image-preview",
        "env_key": "GOOGLE_API_KEY",
    },
    "doubao": {
        "provider": "volcengine",
        "model_name": "volcengine/doubao-seedream-5.0-lite",
        "env_key": "OFOX_API_KEY",
        "base_url": "https://api.ofox.ai/v1",
    },
}

def _add_script_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--target-pages", default=None, help="目标页面ID (逗号分隔)")
    parser.add_argument("--output-json", action="store_true", default=False, help="结果输出到 stdout")
    parser.add_argument("--overwrite", action="store_true", default=False, help="覆盖现有图片")
    parser.add_argument(
        "--model",
        choices=["gemini", "doubao"],
        default="gemini",
        help="图像生成模型: gemini (Google Gemini) 或 doubao (火山引擎豆包)"
    )
    return parser

def _generate_with_gemini(client: genai.Client, prompt: str, output_path: Path, model_config: dict) -> tuple[bool, dict | None]:
    """使用 Google Gemini 生成图像"""
    try:
        response = client.models.generate_content(
            model=model_config["model_name"],
            contents=[prompt],
        )

        for part in response.parts:
            if part.inline_data is not None:
                img = part.as_image()
                img.save(output_path)

                # 获取图片实际尺寸
                with Image.open(output_path) as pil_img:
                    width, height = pil_img.size

                return True, {"width": width, "height": height}

        return False, None
    except Exception as e:
        raise e


def _generate_with_doubao(client: OpenAI, prompt: str, output_path: Path, model_config: dict) -> tuple[bool, dict | None]:
    """使用火山引擎 Doubao 生成图像"""
    try:
        response = client.images.generate(
            model=model_config["model_name"],
            prompt=prompt,
            size="1792x1024",
        )

        first_data = response.data[0]

        # 优先使用 b64_json，否则使用 url
        if hasattr(first_data, 'b64_json') and first_data.b64_json:
            # 从 base64 解码并保存
            img_data = base64.b64decode(first_data.b64_json)
            with open(output_path, 'wb') as f:
                f.write(img_data)
        elif hasattr(first_data, 'url') and first_data.url:
            # 从 URL 下载
            urllib.request.urlretrieve(first_data.url, output_path)
        else:
            return False, None

        # 获取图片实际尺寸
        with Image.open(output_path) as pil_img:
            width, height = pil_img.size

        return True, {"width": width, "height": height}
    except Exception as e:
        raise e


def handle_generate(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = Path(args.project_dir).expanduser().resolve()

    # 1. 获取模型配置
    model_choice: ImageModel = args.model
    model_config = MODEL_CONFIG[model_choice]

    # 2. 验证环境与 API Key
    api_key = os.getenv(model_config["env_key"])
    if not api_key:
        raise InputError(f"环境变量 {model_config['env_key']} 未设置")

    # 初始化客户端
    if model_choice == "gemini":
        client = genai.Client(api_key=api_key)
    elif model_choice == "doubao":
        client = OpenAI(
            base_url=model_config["base_url"],
            api_key=api_key,
        )

    # 3. 加载状态与提示词
    state = load_state(project_dir)
    prompts_path = project_dir / "prompts" / "prompts.json"
    if not prompts_path.exists():
        raise InputError("提示词文件缺失，请先执行生成提示词步骤")

    prompt_doc = PromptDocument(**read_json(prompts_path))
    target_ids = [p.strip() for p in args.target_pages.split(",")] if args.target_pages else None

    # 4. 准备生成列表
    items_to_generate = prompt_doc.items
    if target_ids:
        items_to_generate = [i for i in items_to_generate if i.page_id in target_ids]

    assets_dir = project_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    # 尝试加载已有的清单以支持断点续传
    manifest_path = assets_dir / "manifest.json"
    generated_items_dict = {}
    if manifest_path.exists():
        try:
            old_manifest = AssetManifest(**read_json(manifest_path))
            for item in old_manifest.items:
                generated_items_dict[item.page_id] = item
        except:
            pass

    failed_pages = []

    # 5. 循环调用图像生成 API
    for item in items_to_generate:
        output_path = assets_dir / f"{item.page_id}.png"

        # 如果图片已存在且不需要覆盖，则跳过并保留清单记录
        if output_path.exists() and not args.overwrite:
            if item.page_id not in generated_items_dict:
                # 如果清单里没有但文件有，则补充清单记录
                generated_items_dict[item.page_id] = AssetItem(
                    page_id=item.page_id,
                    file_path=f"assets/{item.page_id}.png",
                    width=1024, height=1024,  # 默认参考值
                    provider=model_config["provider"],
                    model=model_config["model_name"]
                )
            print(f"跳过已存在的页面: {item.page_id}")
            continue

        try:
            print(f"正在为页面 {item.page_id} 生成图像 ({model_config['provider']}/{model_config['model_name']})...")

            if model_choice == "gemini":
                success, dims = _generate_with_gemini(client, item.prompt, output_path, model_config)
            elif model_choice == "doubao":
                success, dims = _generate_with_doubao(client, item.prompt, output_path, model_config)
            else:
                raise InputError(f"不支持的模型: {model_choice}")

            if success and dims:
                generated_items_dict[item.page_id] = AssetItem(
                    page_id=item.page_id,
                    file_path=f"assets/{item.page_id}.png",
                    width=dims["width"],
                    height=dims["height"],
                    provider=model_config["provider"],
                    model=model_config["model_name"]
                )
            else:
                failed_pages.append({"page_id": item.page_id, "error": "API response contained no image data"})

        except Exception as e:
            failed_pages.append({"page_id": item.page_id, "error": str(e)})

    # 6. 更新资产清单 (manifest.json)
    final_items = sorted(generated_items_dict.values(), key=lambda x: x.page_id)
    if final_items:
        manifest = AssetManifest(project_id=state["project_id"], items=final_items)
        write_json(manifest_path, manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict())

    # 7. 更新状态
    state = set_artifact(state, "assets_manifest", "assets/manifest.json", exists=True)
    state["current_state"] = "AssetsGenerated"
    state["last_completed_step"] = TOOL_NAME

    append_transition(state, {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_state": state.get("current_state", "PlanConfirmed"),
        "to_state": "AssetsGenerated",
        "trigger": "tool_success",
        "step": TOOL_NAME,
        "note": f"{model_config['provider']} ({model_config['model_name']}) generated {len(final_items)} total images."
    })
    save_state(project_dir, state)

    return {
        "project_id": state["project_id"],
        "model": model_choice,
        "images_generated": len(final_items),
        "failed_pages": failed_pages,
        "artifacts": ["assets/manifest.json"]
    }

def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    _add_script_args(parser)
    return run_cli(handle_generate, tool=TOOL_NAME, parser=parser)

if __name__ == "__main__":
    raise SystemExit(main())
