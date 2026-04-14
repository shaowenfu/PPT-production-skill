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
from pptflow.schemas import AssetItem, AssetManifest, PromptDocument, SlidePlanDocument
from pptflow.state_store import (
    append_transition,
    load_state,
    save_state,
    set_artifact,
)

TOOL_NAME = "visual_asset_generate"
MAX_RATE_LIMIT_RETRIES = 3
RATE_LIMIT_RETRY_DELAY_SECONDS = 2.0
DEFAULT_TEXT_RENDERING_SUFFIX = (
    " Text rendering constraints: render only the exact text explicitly specified in this prompt, without deleting, rewriting, paraphrasing, summarizing, adding, or expanding any text. Do not render any other visible text beyond the following content.; "
    "ensure Chinese text is clear, accurate, and readable; maintain crisp edges, accurate glyph shapes, and stable spacing; " \
    "Text alignment should be centered or left-aligned, avoid right-alignment; "
    "line breaks must preserve whole words and intended phrases; never split a single word, token, or short fixed phrase across two lines; " \
)
DEFAULT_DARK_BACKGROUND_SUFFIX = (
    " Background constraints: use a dark background only; prefer deep dark tones and low-luminance presentation-safe lighting; "
    "do not use light backgrounds, white backgrounds, bright canvases, or pale gradients."
)
DEFAULT_MASTER_STYLE_SUFFIX = (
    " Visual Style: High-end corporate AI training presentation, dark mode, deep navy blue (#0B0F19) gradient background, "
    "subtle neon cyan (#00F0FF) and glowing purple accents. Elements should use isometric 3D glassmorphism (毛玻璃质感) "
    "and clean vector UI/UX components. Flat design, professional, minimalist, strictly unified color palette across all slides. "
    "No random color noise."
)
DEFAULT_NEGATIVE_CONSTRAINTS_SUFFIX = (
    " Negative constraints: NO photorealistic humans, NO complex landscapes, NO cartoon styles, NO watercolor, "
    "NO chaotic multiple colors, strictly maintain the dark tech corporate theme."
)
DEFAULT_PAGE_CATEGORY = "B"
A_PAGE_LAYOUT_SUFFIX = (
    " page layout constraints: make text the dominant communication layer; keep the title and bullet points visually primary; "
    "icons, symbols, and decorative graphics may appear only as supporting accents and must not overpower the text block."
)
B_PAGE_LAYOUT_SUFFIX = (
    " page quote constraints: preserve the approved text exactly as provided; do not add markdown, bullets, quote marks, dashes, or extra symbols. "
    "For multi-line quotes or parallel statements, maintain parallel emphasis by ensuring all lines use identical font sizes and weights; "
    "do not create artificial hierarchy between these lines. Keep the text block centered both horizontally and vertically."
)


def _preferred_image_extension(image_provider: str) -> str:
    if image_provider == "google":
        return ".jpg"
    return ".png"


def _candidate_output_paths(assets_dir: Path, page_id: str, image_provider: str) -> list[Path]:
    preferred_suffix = _preferred_image_extension(image_provider)
    suffixes = [preferred_suffix]
    for legacy_suffix in (".png", ".jpg"):
        if legacy_suffix not in suffixes:
            suffixes.append(legacy_suffix)
    return [assets_dir / f"{page_id}{suffix}" for suffix in suffixes]


def _preferred_output_path(assets_dir: Path, page_id: str, image_provider: str) -> Path:
    return assets_dir / f"{page_id}{_preferred_image_extension(image_provider)}"


def _normalize_page_category(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"A", "B"}:
            return normalized
    return DEFAULT_PAGE_CATEGORY


def _load_page_category_map(project_dir: Path) -> dict[str, str]:
    plan_path = project_dir / "plan" / "plan.json"
    if not plan_path.exists():
        return {}

    try:
        raw_plan = read_json(plan_path)
    except Exception:
        return {}

    if not isinstance(raw_plan, dict):
        return {}

    raw_pages = raw_plan.get("pages")
    if not isinstance(raw_pages, list):
        return {}

    page_category_map: dict[str, str] = {}
    for raw_page in raw_pages:
        if not isinstance(raw_page, dict):
            continue
        raw_page_id = raw_page.get("page_id")
        if not isinstance(raw_page_id, str) or not raw_page_id.strip():
            continue
        page_category_map[raw_page_id.strip()] = _normalize_page_category(raw_page.get("category"))
    return page_category_map


def _page_category_suffix(page_category: str) -> str:
    if _normalize_page_category(page_category) == "B":
        return B_PAGE_LAYOUT_SUFFIX
    return A_PAGE_LAYOUT_SUFFIX


def _compose_final_image_prompt(
    base_prompt: str,
    master_style_prompt: str | None = None,
    page_category: str = DEFAULT_PAGE_CATEGORY,
) -> str:
    parts: list[str] = []
    prompt = base_prompt.strip()
    if prompt:
        parts.append(prompt)
    if master_style_prompt and master_style_prompt.strip():
        parts.append(master_style_prompt.strip())
    parts.extend(
        [
            _page_category_suffix(page_category),
            DEFAULT_MASTER_STYLE_SUFFIX,
            DEFAULT_DARK_BACKGROUND_SUFFIX,
            DEFAULT_NEGATIVE_CONSTRAINTS_SUFFIX,
            DEFAULT_TEXT_RENDERING_SUFFIX,
        ]
    )
    return "\n\n".join(parts)


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
        with Image.open(output_path) as saved_image:
            width, height = saved_image.size
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
    master_style_prompt: str | None,
    page_category: str,
    output_path: Path,
    semaphore: asyncio.Semaphore,
) -> tuple[str, AssetItem | None, dict[str, Any] | None]:
    async with semaphore:
        try:
            print_stderr(f"正在为页面 {item.page_id} 生成图像 ({settings.image_provider}/{settings.image_model})...")
            final_prompt = _compose_final_image_prompt(
                item.prompt,
                master_style_prompt,
                page_category=page_category,
            )
            success, dims = await _generate_image(
                client=client,
                settings=settings,
                prompt=final_prompt,
                output_path=output_path,
            )
            if success and dims:
                return (
                    item.page_id,
                    AssetItem(
                        page_id=item.page_id,
                        file_path=f"assets/{output_path.name}",
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
    requests: list[tuple[Any, Path, str]],
    master_style_prompt: str | None,
    parallel: int,
) -> list[tuple[str, AssetItem | None, dict[str, Any] | None]]:
    semaphore = asyncio.Semaphore(parallel)
    tasks = [
        _generate_asset_item(
            client=client,
            settings=settings,
            item=item,
            master_style_prompt=master_style_prompt,
            page_category=page_category,
            output_path=output_path,
            semaphore=semaphore,
        )
        for item, output_path, page_category in requests
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
    plan_path = project_dir / "plan" / "plan.json"
    master_style_prompt: str | None = None
    page_category_map: dict[str, str] = _load_page_category_map(project_dir)
    if plan_path.exists():
        try:
            plan_doc = SlidePlanDocument(**read_json(plan_path))
            master_style_prompt = plan_doc.master_style_prompt
        except Exception:
            master_style_prompt = None
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
    requests_to_run: list[tuple[Any, Path, str]] = []
    for item in items_to_generate:
        output_path = _preferred_output_path(assets_dir, item.page_id, settings.image_provider)
        page_category = page_category_map.get(item.page_id, DEFAULT_PAGE_CATEGORY)
        existing_output_path = next(
            (path for path in _candidate_output_paths(assets_dir, item.page_id, settings.image_provider) if path.exists()),
            None,
        )

        # 如果图片已存在且不需要覆盖，则跳过并保留清单记录
        if existing_output_path is not None and not args.overwrite:
            if item.page_id not in generated_items_dict:
                with Image.open(existing_output_path) as existing_image:
                    width, height = existing_image.size
                generated_items_dict[item.page_id] = AssetItem(
                    page_id=item.page_id,
                    file_path=f"assets/{existing_output_path.name}",
                    width=width,
                    height=height,
                    provider=settings.image_provider,
                    model=settings.image_model,
                )
            print_stderr(f"跳过已存在的页面: {item.page_id}")
            continue

        requests_to_run.append((item, output_path, page_category))

    if requests_to_run:
        for page_id, asset_item, failure in asyncio.run(
            _run_asset_generation(
                client=client,
                settings=settings,
                requests=requests_to_run,
                master_style_prompt=master_style_prompt,
                parallel=parallel,
            )
        ):
            if asset_item is not None:
                generated_items_dict[page_id] = asset_item
                active_filename = Path(asset_item.file_path).name
                for candidate_path in _candidate_output_paths(assets_dir, page_id, settings.image_provider):
                    if candidate_path.name == active_filename or not candidate_path.exists():
                        continue
                    candidate_path.unlink()
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
