"""Configuration loading for the PPT workflow toolchain.

简化配置：
- 文本生成：统一使用 DeepSeek (deepseek-chat)
- 图像生成：统一使用 Ofox/Doubao (volcengine/doubao-seedream-5.0-lite)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .errors import EnvironmentError as WorkflowEnvironmentError


def _load_dotenv(env_file: Optional[Path] = None) -> None:
    """简单的 .env 文件加载，直接更新 os.environ"""
    if env_file is None:
        env_file = Path(__file__).resolve().parent.parent / ".env"

    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        # 仅在环境变量未设置时才覆盖
        if key not in os.environ or os.environ[key] == "":
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    """PPT 工作流配置

    必需：
        deepseek_api_key: DeepSeek API Key（用于文本生成）
        ofox_api_key: Ofox API Key（用于图像生成）

    可选：
        deepseek_base_url: DeepSeek API 地址
        ofox_base_url: Ofox API 地址
        text_model: 文本生成模型名称
        image_model: 图像生成模型名称
        default_language: 默认语言
        default_aspect_ratio: 默认宽高比
        request_timeout_seconds: 请求超时时间
    """
    deepseek_api_key: str
    ofox_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    ofox_base_url: str = "https://api.ofox.ai/v1"
    text_model: str = "deepseek-chat"
    image_model: str = "volcengine/doubao-seedream-5.0-lite"
    default_language: str = "zh-CN"
    default_aspect_ratio: str = "16:9"
    request_timeout_seconds: float = 120.0


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """加载配置

    Args:
        env_file: 可选的 .env 文件路径，默认为项目根目录下的 .env

    Returns:
        Settings 实例

    Raises:
        WorkflowEnvironmentError: 缺少必需的 API Key
    """
    _load_dotenv(env_file)

    deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not deepseek_api_key:
        raise WorkflowEnvironmentError("DEEPSEEK_API_KEY 未设置")

    ofox_api_key = os.environ.get("OFOX_API_KEY", "").strip()
    if not ofox_api_key:
        raise WorkflowEnvironmentError("OFOX_API_KEY 未设置")

    deepseek_base_url = os.environ.get("DEEPSEEK_BASE_URL", "").strip() or "https://api.deepseek.com"
    ofox_base_url = os.environ.get("OFOX_BASE_URL", "").strip() or "https://api.ofox.ai/v1"

    text_model = os.environ.get("PPT_TEXT_MODEL", "").strip() or "deepseek-chat"
    image_model = os.environ.get("PPT_IMAGE_MODEL", "").strip() or "volcengine/doubao-seedream-5.0-lite"
    default_language = os.environ.get("PPT_DEFAULT_LANGUAGE", "").strip() or "zh-CN"
    default_aspect_ratio = os.environ.get("PPT_DEFAULT_ASPECT_RATIO", "").strip() or "16:9"

    timeout_raw = os.environ.get("PPT_REQUEST_TIMEOUT_SECONDS", "120.0").strip()
    try:
        request_timeout_seconds = float(timeout_raw) if timeout_raw else 120.0
    except ValueError as exc:
        raise WorkflowEnvironmentError("PPT_REQUEST_TIMEOUT_SECONDS 必须是数字") from exc

    return Settings(
        deepseek_api_key=deepseek_api_key,
        ofox_api_key=ofox_api_key,
        deepseek_base_url=deepseek_base_url,
        ofox_base_url=ofox_base_url,
        text_model=text_model,
        image_model=image_model,
        default_language=default_language,
        default_aspect_ratio=default_aspect_ratio,
        request_timeout_seconds=request_timeout_seconds,
    )


__all__ = ["Settings", "load_settings"]
