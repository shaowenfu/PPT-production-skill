"""Configuration loading for the PPT workflow toolchain.

简化配置：
- 文本生成：统一使用 DeepSeek (deepseek-chat)
- 图像生成：统一使用 Ofox/Doubao (volcengine/doubao-seedream-5.0-lite)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .errors import InvalidEnvironmentError, MissingAPIKeyError

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_OFOX_BASE_URL = "https://api.ofox.ai/v1"
DEFAULT_TEXT_MODEL = "deepseek-chat"
DEFAULT_IMAGE_MODEL = "volcengine/doubao-seedream-5.0-lite"
DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0

REQUIRED_SECRET_ENV_VARS = (
    "DEEPSEEK_API_KEY",
    "OFOX_API_KEY",
)


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
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    ofox_base_url: str = DEFAULT_OFOX_BASE_URL
    text_model: str = DEFAULT_TEXT_MODEL
    image_model: str = DEFAULT_IMAGE_MODEL
    default_language: str = DEFAULT_LANGUAGE
    default_aspect_ratio: str = DEFAULT_ASPECT_RATIO
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS


def read_settings_values(env_file: Optional[Path] = None) -> dict[str, str]:
    _load_dotenv(env_file)
    return {
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY", "").strip(),
        "OFOX_API_KEY": os.environ.get("OFOX_API_KEY", "").strip(),
        "DEEPSEEK_BASE_URL": os.environ.get("DEEPSEEK_BASE_URL", "").strip(),
        "OFOX_BASE_URL": os.environ.get("OFOX_BASE_URL", "").strip(),
        "PPT_TEXT_MODEL": os.environ.get("PPT_TEXT_MODEL", "").strip(),
        "PPT_IMAGE_MODEL": os.environ.get("PPT_IMAGE_MODEL", "").strip(),
        "PPT_DEFAULT_LANGUAGE": os.environ.get("PPT_DEFAULT_LANGUAGE", "").strip(),
        "PPT_DEFAULT_ASPECT_RATIO": os.environ.get("PPT_DEFAULT_ASPECT_RATIO", "").strip(),
        "PPT_REQUEST_TIMEOUT_SECONDS": os.environ.get("PPT_REQUEST_TIMEOUT_SECONDS", "").strip(),
    }


def _missing_required_secret_env_vars(raw_values: Mapping[str, str]) -> list[str]:
    return [env_var for env_var in REQUIRED_SECRET_ENV_VARS if not raw_values.get(env_var, "").strip()]


def validate_settings(raw_values: Mapping[str, str]) -> Settings:
    missing = _missing_required_secret_env_vars(raw_values)
    if missing:
        raise MissingAPIKeyError(
            f"缺少必需的 API Key: {', '.join(missing)}",
            details={"missing": missing},
        )

    timeout_raw = raw_values.get("PPT_REQUEST_TIMEOUT_SECONDS", "").strip()
    try:
        request_timeout_seconds = float(timeout_raw) if timeout_raw else DEFAULT_REQUEST_TIMEOUT_SECONDS
    except ValueError as exc:
        raise InvalidEnvironmentError(
            "PPT_REQUEST_TIMEOUT_SECONDS 必须是数字",
            details={"env_var": "PPT_REQUEST_TIMEOUT_SECONDS", "value": timeout_raw},
        ) from exc

    return Settings(
        deepseek_api_key=raw_values["DEEPSEEK_API_KEY"],
        ofox_api_key=raw_values["OFOX_API_KEY"],
        deepseek_base_url=raw_values.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
        ofox_base_url=raw_values.get("OFOX_BASE_URL") or DEFAULT_OFOX_BASE_URL,
        text_model=raw_values.get("PPT_TEXT_MODEL") or DEFAULT_TEXT_MODEL,
        image_model=raw_values.get("PPT_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL,
        default_language=raw_values.get("PPT_DEFAULT_LANGUAGE") or DEFAULT_LANGUAGE,
        default_aspect_ratio=raw_values.get("PPT_DEFAULT_ASPECT_RATIO") or DEFAULT_ASPECT_RATIO,
        request_timeout_seconds=request_timeout_seconds,
    )


def settings_status(env_file: Optional[Path] = None) -> dict[str, Any]:
    raw_values = read_settings_values(env_file)
    missing = _missing_required_secret_env_vars(raw_values)
    return {
        "configured": not missing,
        "missing": missing,
        "present": {env_var: bool(raw_values.get(env_var)) for env_var in REQUIRED_SECRET_ENV_VARS},
        "defaults": {
            "deepseek_base_url": raw_values.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
            "ofox_base_url": raw_values.get("OFOX_BASE_URL") or DEFAULT_OFOX_BASE_URL,
            "text_model": raw_values.get("PPT_TEXT_MODEL") or DEFAULT_TEXT_MODEL,
            "image_model": raw_values.get("PPT_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL,
            "default_language": raw_values.get("PPT_DEFAULT_LANGUAGE") or DEFAULT_LANGUAGE,
            "default_aspect_ratio": raw_values.get("PPT_DEFAULT_ASPECT_RATIO") or DEFAULT_ASPECT_RATIO,
        },
    }


def load_settings(env_file: Optional[Path] = None) -> Settings:
    """加载配置

    Args:
        env_file: 可选的 .env 文件路径，默认为项目根目录下的 .env

    Returns:
        Settings 实例

    Raises:
        MissingAPIKeyError: 缺少必需的 API Key
    """
    return validate_settings(read_settings_values(env_file))


__all__ = [
    "Settings",
    "load_settings",
    "read_settings_values",
    "settings_status",
    "validate_settings",
]
