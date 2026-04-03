"""Configuration loading for the PPT workflow toolchain.

简化配置：
- 默认文本生成：Google Gemini
- 默认图像生成：Google Gemini Image
- 兼容切换：DeepSeek / Doubao
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .errors import InvalidEnvironmentError, MissingAPIKeyError

DEFAULT_TEXT_PROVIDER = "google"
DEFAULT_IMAGE_PROVIDER = "google"
DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_OFOX_BASE_URL = "https://api.ofox.ai/v1"
DEFAULT_GOOGLE_TEXT_MODEL = "gemini-3-flash-preview"
DEFAULT_DEEPSEEK_TEXT_MODEL = "deepseek-chat"
DEFAULT_GOOGLE_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_DOUBAO_IMAGE_MODEL = "volcengine/doubao-seedream-5.0-lite"
DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0


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
        google_api_key: Google API Key（默认文本/图像生成）

    可选：
        deepseek_api_key: DeepSeek API Key（文本生成兼容切换）
        ofox_api_key: Ofox API Key（图像生成兼容切换）
        text_provider: 文本生成 Provider
        image_provider: 图像生成 Provider
        deepseek_base_url: DeepSeek API 地址
        ofox_base_url: Ofox API 地址
        text_model: 文本生成模型名称
        image_model: 图像生成模型名称
        default_language: 默认语言
        default_aspect_ratio: 默认宽高比
        request_timeout_seconds: 请求超时时间
    """
    google_api_key: str = ""
    deepseek_api_key: str = ""
    ofox_api_key: str = ""
    text_provider: str = DEFAULT_TEXT_PROVIDER
    image_provider: str = DEFAULT_IMAGE_PROVIDER
    deepseek_base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    ofox_base_url: str = DEFAULT_OFOX_BASE_URL
    text_model: str = DEFAULT_GOOGLE_TEXT_MODEL
    image_model: str = DEFAULT_GOOGLE_IMAGE_MODEL
    default_language: str = DEFAULT_LANGUAGE
    default_aspect_ratio: str = DEFAULT_ASPECT_RATIO
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS


def _default_text_model(provider: str) -> str:
    if provider == "google":
        return DEFAULT_GOOGLE_TEXT_MODEL
    if provider == "deepseek":
        return DEFAULT_DEEPSEEK_TEXT_MODEL
    raise InvalidEnvironmentError(
        "不支持的文本 Provider",
        details={"provider": provider, "supported": ["google", "deepseek"]},
    )


def _default_image_model(provider: str) -> str:
    if provider == "google":
        return DEFAULT_GOOGLE_IMAGE_MODEL
    if provider == "doubao":
        return DEFAULT_DOUBAO_IMAGE_MODEL
    raise InvalidEnvironmentError(
        "不支持的图像 Provider",
        details={"provider": provider, "supported": ["google", "doubao"]},
    )


def read_settings_values(env_file: Optional[Path] = None) -> dict[str, str]:
    _load_dotenv(env_file)
    return {
        "GOOGLE_API_KEY": (
            os.environ.get("GOOGLE_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        ),
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


def _required_secret_env_vars(*, text_provider: str, image_provider: str) -> tuple[str, ...]:
    required: list[str] = []
    if text_provider == "google" or image_provider == "google":
        required.append("GOOGLE_API_KEY")
    if text_provider == "deepseek":
        required.append("DEEPSEEK_API_KEY")
    if image_provider == "doubao":
        required.append("OFOX_API_KEY")
    return tuple(dict.fromkeys(required))


def _missing_required_secret_env_vars(
    raw_values: Mapping[str, str],
    *,
    text_provider: str,
    image_provider: str,
) -> list[str]:
    required_env_vars = _required_secret_env_vars(
        text_provider=text_provider,
        image_provider=image_provider,
    )
    return [env_var for env_var in required_env_vars if not raw_values.get(env_var, "").strip()]


def validate_settings(raw_values: Mapping[str, str]) -> Settings:
    text_provider = DEFAULT_TEXT_PROVIDER
    image_provider = DEFAULT_IMAGE_PROVIDER
    missing = _missing_required_secret_env_vars(
        raw_values,
        text_provider=text_provider,
        image_provider=image_provider,
    )
    if missing:
        raise MissingAPIKeyError(
            f"缺少必需的 API Key: {', '.join(missing)}",
            details={
                "missing": missing,
                "text_provider": text_provider,
                "image_provider": image_provider,
            },
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
        google_api_key=raw_values.get("GOOGLE_API_KEY", ""),
        deepseek_api_key=raw_values["DEEPSEEK_API_KEY"],
        ofox_api_key=raw_values["OFOX_API_KEY"],
        text_provider=text_provider,
        image_provider=image_provider,
        deepseek_base_url=raw_values.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
        ofox_base_url=raw_values.get("OFOX_BASE_URL") or DEFAULT_OFOX_BASE_URL,
        text_model=raw_values.get("PPT_TEXT_MODEL") or _default_text_model(text_provider),
        image_model=raw_values.get("PPT_IMAGE_MODEL") or _default_image_model(image_provider),
        default_language=raw_values.get("PPT_DEFAULT_LANGUAGE") or DEFAULT_LANGUAGE,
        default_aspect_ratio=raw_values.get("PPT_DEFAULT_ASPECT_RATIO") or DEFAULT_ASPECT_RATIO,
        request_timeout_seconds=request_timeout_seconds,
    )


def settings_status(env_file: Optional[Path] = None) -> dict[str, Any]:
    raw_values = read_settings_values(env_file)
    text_provider = DEFAULT_TEXT_PROVIDER
    image_provider = DEFAULT_IMAGE_PROVIDER
    missing = _missing_required_secret_env_vars(
        raw_values,
        text_provider=text_provider,
        image_provider=image_provider,
    )
    return {
        "configured": not missing,
        "missing": missing,
        "present": {
            env_var: bool(raw_values.get(env_var))
            for env_var in ("GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "OFOX_API_KEY")
        },
        "defaults": {
            "text_provider": text_provider,
            "image_provider": image_provider,
            "deepseek_base_url": raw_values.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
            "ofox_base_url": raw_values.get("OFOX_BASE_URL") or DEFAULT_OFOX_BASE_URL,
            "text_model": raw_values.get("PPT_TEXT_MODEL") or _default_text_model(text_provider),
            "image_model": raw_values.get("PPT_IMAGE_MODEL") or _default_image_model(image_provider),
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
