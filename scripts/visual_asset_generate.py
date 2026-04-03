#!/usr/bin/env python
"""Generate visual assets using the configured image generation provider.

This is Program 6 in the PPT workflow. It reads prompts from prompts.json,
calls the configured image provider to generate full-slide images, and creates
an asset manifest.

Usage:
    python scripts/visual_asset_generate.py --project-dir PPT/03 [--target-pages p1,p2] [--overwrite]
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from _bootstrap import bootstrap_project

bootstrap_project(__file__)

from google import genai
from google.genai import types
from openai import AsyncOpenAI, RateLimitError
from PIL import Image

from pptflow.cli import print_stderr, run_cli
from pptflow.config import load_settings
from pptflow.errors import InputError
from pptflow.json_io import read_json, write_json
from pptflow.paths import resolve_project_dir
from pptflow.schemas import AssetItem, AssetManifest, PromptDocument
from pptflow.state_store import (
    append_transition,
    load_state,
    save_state,
    set_artifact,
)

TOOL_NAME = "visual_asset_generate"
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_RETRY_DELAY_SECONDS = 2.0


def _add_script_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.add_argument("--project-dir", required=True, help="项目目录")
    parser.add_argument("--target-pages", default=None, help="目标页面ID (逗号分隔)")
    parser.add_argument("--overwrite", action="store_true", default=False, help="覆盖现有图片")
    return parser


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


async def _generate_image_with_doubao(
    client: AsyncOpenAI,
    model: str,
    prompt: str,
    output_path: Path,
) -> tuple[bool, dict | None]:
    """Doubao 图像生成函数。"""
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            response = await client.images.generate(
                model=model,
                prompt=prompt,
                size="1792x1024",
            )
            break
        except RateLimitError as exc:
            if attempt >= MAX_RATE_LIMIT_RETRIES:
                raise InputError(f"图像生成失败: {exc}") from exc
            delay = RATE_LIMIT_RETRY_DELAY_SECONDS * (attempt + 1)
            print_stderr(f"页面图像触发 429，{delay:.0f} 秒后重试...")
            await asyncio.sleep(delay)
        except Exception as exc:
            raise InputError(f"图像生成失败: {exc}") from exc

    first_data = response.data[0]

    # 优先使用 b64_json，否则使用 url
    if hasattr(first_data, "b64_json") and first_data.b64_json:
        img_data = base64.b64decode(first_data.b64_json)
        await asyncio.to_thread(output_path.write_bytes, img_data)
    elif hasattr(first_data, "url") and first_data.url:
        await asyncio.to_thread(urllib.request.urlretrieve, first_data.url, output_path)
    else:
        return False, None

    def _read_image_size() -> tuple[int, int]:
        with Image.open(output_path) as pil_img:
            return pil_img.size

    width, height = await asyncio.to_thread(_read_image_size)

    return True, {"width": width, "height": height}


def _generate_image_with_google(
    *,
    api_key: str,
    model: str,
    prompt: str,
    output_path: Path,
    aspect_ratio: str,
) -> tuple[bool, dict[str, int] | None]:
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["Image"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size="2K",
                    ),
                ),
            )
            break
        except Exception as exc:
            if not _is_google_rate_limit_error(exc) or attempt >= MAX_RATE_LIMIT_RETRIES:
                raise InputError(f"图像生成失败: {exc}") from exc
            delay = RATE_LIMIT_RETRY_DELAY_SECONDS * (attempt + 1)
            print_stderr(f"Google 图像生成触发 429，{delay:.0f} 秒后重试...")
            time.sleep(delay)

    for part in getattr(response, "parts", None) or []:
        if getattr(part, "inline_data", None) is None:
            continue
        image = part.as_image()
        image.save(output_path)
        width, height = image.size
        return True, {"width": width, "height": height}

    return False, None


async def _generate_image(
    *,
    client: AsyncOpenAI | None,
    settings: Any,
    prompt: str,
    output_path: Path,
) -> tuple[bool, dict | None]:
    if settings.image_provider == "google":
        return await asyncio.to_thread(
            _generate_image_with_google,
            api_key=settings.google_api_key,
            model=settings.image_model,
            prompt=prompt,
            output_path=output_path,
            aspect_ratio=settings.default_aspect_ratio,
        )
    if settings.image_provider == "doubao":
        if client is None:
            raise InputError("Doubao 客户端未初始化")
        return await _generate_image_with_doubao(
            client=client,
            model=settings.image_model,
            prompt=prompt,
            output_path=output_path,
        )
    raise InputError(f"不支持的图像 Provider: {settings.image_provider}")


async def _generate_asset_item(
    *,
    client: AsyncOpenAI | None,
    settings: Any,
    item: Any,
    output_path: Path,
    semaphore: asyncio.Semaphore,
) -> tuple[str, AssetItem | None, dict[str, Any] | None]:
    async with semaphore:
        try:
            print_stderr(f"正在为页面 {item.page_id} 生成图像 ({settings.image_provider}/{settings.image_model})...")
            success, dims = await _generate_image(
                client=client,
                settings=settings,
                prompt=item.prompt,
                output_path=output_path,
            )
            if success and dims:
                return (
                    item.page_id,
                    AssetItem(
                        page_id=item.page_id,
                        file_path=f"assets/{item.page_id}.png",
                        width=dims["width"],
                        height=dims["height"],
                        provider=settings.image_provider,
                        model=settings.image_model,
                    ),
                    None,
                )
            return item.page_id, None, {"page_id": item.page_id, "error": "API response contained no image data"}
        except Exception as exc:
            return item.page_id, None, {"page_id": item.page_id, "error": str(exc)}


async def _run_asset_tasks(tasks: list[Any]) -> list[tuple[str, AssetItem | None, dict[str, Any] | None]]:
    return await asyncio.gather(*tasks)


async def _run_asset_generation(
    *,
    client: AsyncOpenAI | None,
    settings: Any,
    requests: list[tuple[Any, Path]],
    parallel: int,
) -> list[tuple[str, AssetItem | None, dict[str, Any] | None]]:
    semaphore = asyncio.Semaphore(parallel)
    tasks = [
        _generate_asset_item(
            client=client,
            settings=settings,
            item=item,
            output_path=output_path,
            semaphore=semaphore,
        )
        for item, output_path in requests
    ]
    return await _run_asset_tasks(tasks)


def handle_generate(args: argparse.Namespace) -> dict[str, Any]:
    project_dir = resolve_project_dir(args.project_dir, create=False)

    # 1. 加载设置与环境
    settings = load_settings()
    state = load_state(project_dir)

    # 2. 初始化兼容客户端
    client: AsyncOpenAI | None = None
    if settings.image_provider == "doubao":
        client = AsyncOpenAI(
            base_url=settings.ofox_base_url,
            api_key=settings.ofox_api_key,
        )

    # 3. 加载提示词
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
        except Exception:
            pass

    failed_pages = []

    # 5. 并发调用图像生成 API
    parallel = max(1, args.parallel)
    requests_to_run: list[tuple[Any, Path]] = []
    for item in items_to_generate:
        output_path = assets_dir / f"{item.page_id}.png"

        # 如果图片已存在且不需要覆盖，则跳过并保留清单记录
        if output_path.exists() and not args.overwrite:
            if item.page_id not in generated_items_dict:
                with Image.open(output_path) as existing_image:
                    width, height = existing_image.size
                generated_items_dict[item.page_id] = AssetItem(
                    page_id=item.page_id,
                    file_path=f"assets/{item.page_id}.png",
                    width=width,
                    height=height,
                    provider=settings.image_provider,
                    model=settings.image_model,
                )
            print_stderr(f"跳过已存在的页面: {item.page_id}")
            continue

        requests_to_run.append((item, output_path))

    if requests_to_run:
        for page_id, asset_item, failure in asyncio.run(
            _run_asset_generation(
                client=client,
                settings=settings,
                requests=requests_to_run,
                parallel=parallel,
            )
        ):
            if asset_item is not None:
                generated_items_dict[page_id] = asset_item
            if failure is not None:
                failed_pages.append(failure)

    # 6. 更新资产清单 (manifest.json)
    final_items = sorted(generated_items_dict.values(), key=lambda x: x.page_id)
    if final_items:
        manifest = AssetManifest(project_id=state["project_id"], items=final_items)
        write_json(manifest_path, manifest.model_dump() if hasattr(manifest, 'model_dump') else manifest.dict())

    # 7. 更新状态
    previous_state = state["current_state"]
    state = set_artifact(state, "assets_manifest", "assets/manifest.json", exists=True)
    state["current_state"] = "AssetsGenerated"
    state["last_completed_step"] = TOOL_NAME

    state = append_transition(state, {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "from_state": previous_state,
        "to_state": "AssetsGenerated",
        "trigger": "tool_success",
        "step": TOOL_NAME,
        "note": f"{settings.image_provider} ({settings.image_model}) generated {len(final_items)} total images."
    })
    save_state(project_dir, state)

    return {
        "project_id": state["project_id"],
        "artifacts": ["assets/manifest.json"],
        "metrics": {"images_generated": len(final_items), "images_failed": len(failed_pages)},
        "provider": settings.image_provider,
        "model": settings.image_model,
        "failed_pages": failed_pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog=TOOL_NAME)
    _add_script_args(parser)
    parser.add_argument("--parallel", type=int, default=1, help="并发生成图片数量")
    return run_cli(handle_generate, tool=TOOL_NAME, parser=parser)


if __name__ == "__main__":
    raise SystemExit(main())
