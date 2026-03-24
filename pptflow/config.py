"""Configuration loading for the PPT workflow toolchain."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional

from .errors import EnvironmentError as WorkflowEnvironmentError


_CONFIG_DIR = Path(__file__).resolve().parent


def _candidate_env_files(explicit: Optional[Path]) -> list[Path]:
    candidates: list[Path] = []
    repo_env = _CONFIG_DIR.parent / ".env"
    if repo_env not in candidates:
        candidates.append(repo_env)
    cwd_env = Path.cwd() / ".env"
    if cwd_env not in candidates:
        candidates.append(cwd_env)
    if explicit is not None and explicit not in candidates:
        candidates.append(explicit)
    return candidates


def _parse_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
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
        values[key] = value
    return values


def _load_env_files(explicit: Optional[Path]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for path in _candidate_env_files(explicit):
        if path.exists() and path.is_file():
            merged.update(_parse_env_file(path))
    return merged


def _pick_setting(
    env: Dict[str, str],
    names: Iterable[str],
    default: Optional[str] = None,
) -> Optional[str]:
    for name in names:
        if name in os.environ and os.environ[name] != "":
            return os.environ[name]
    for name in names:
        if name in env and env[name] != "":
            return env[name]
    return default


def _normalize_base_url(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_base_url: Optional[str] = None
    text_model: str = "gemini-3-flash-preview"
    planning_model: Optional[str] = None
    prompt_model: Optional[str] = None
    image_model: str = "gemini-3.1-flash-image-preview"
    default_language: str = "zh-CN"
    default_aspect_ratio: str = "16:9"
    request_timeout_seconds: float = 120.0
    # Indicates if we're using Gemini API (for response_format handling)
    is_gemini: bool = False

    def model_for(self, purpose: str) -> str:
        normalized = purpose.strip().lower()
        if normalized in {"text", "draft"}:
            return self.text_model
        if normalized == "plan":
            return self.planning_model or self.text_model
        if normalized == "prompt":
            return self.prompt_model or self.text_model
        if normalized == "image":
            return self.image_model
        raise ValueError(f"unsupported model purpose: {purpose}")


def load_settings(env_file: Optional[Path] = None) -> Settings:
    env_values = _load_env_files(env_file)

    # Priority: GEMINI_API_KEY > OPENAI_API_KEY (with fallback)
    # This allows Gemini to be the primary choice while maintaining backward compatibility
    api_key = _pick_setting(
        env_values,
        ("GEMINI_API_KEY", "OPENAI_API_KEY", "PPT_OPENAI_API_KEY"),
    )
    if not api_key:
        raise WorkflowEnvironmentError(
            "GEMINI_API_KEY or OPENAI_API_KEY is required"
        )

    # Detect if using Gemini by checking for GEMINI_API_KEY
    is_gemini = _pick_setting(env_values, ("GEMINI_API_KEY",)) is not None

    # Base URL: GEMINI_BASE_URL for Gemini, OPENAI_BASE_URL for OpenAI
    # Gemini default: https://generativelanguage.googleapis.com/v1beta/openai/
    if is_gemini:
        base_url = _normalize_base_url(
            _pick_setting(
                env_values,
                ("GEMINI_BASE_URL", "PPT_GEMINI_BASE_URL"),
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            )
        )
    else:
        base_url = _normalize_base_url(
            _pick_setting(env_values, ("OPENAI_BASE_URL", "PPT_OPENAI_BASE_URL"))
        )

    # Default models based on provider
    default_text_model = "gemini-3-flash-preview" if is_gemini else "gpt-4.1-mini"
    default_image_model = "gemini-2.5-flash-image" if is_gemini else "gpt-image-1"

    text_model = _pick_setting(
        env_values,
        ("PPT_TEXT_MODEL", "PPT_LLM_MODEL", "OPENAI_TEXT_MODEL"),
        default_text_model,
    )
    planning_model = _pick_setting(
        env_values,
        ("PPT_PLANNING_MODEL", "PPT_PLAN_MODEL"),
        text_model,
    )
    prompt_model = _pick_setting(
        env_values,
        ("PPT_PROMPT_MODEL", "PPT_VISUAL_PROMPT_MODEL"),
        text_model,
    )
    image_model = _pick_setting(
        env_values,
        ("PPT_IMAGE_MODEL", "OPENAI_IMAGE_MODEL"),
        default_image_model,
    )
    default_language = _pick_setting(
        env_values,
        ("PPT_DEFAULT_LANGUAGE", "LANGUAGE"),
        "zh-CN",
    )
    default_aspect_ratio = _pick_setting(
        env_values,
        ("PPT_DEFAULT_ASPECT_RATIO",),
        "16:9",
    )
    timeout_raw = _pick_setting(
        env_values,
        ("PPT_REQUEST_TIMEOUT_SECONDS", "OPENAI_TIMEOUT"),
        "120.0",
    )
    try:
        request_timeout_seconds = float(timeout_raw) if timeout_raw is not None else 120.0
    except ValueError as exc:
        raise WorkflowEnvironmentError("PPT_REQUEST_TIMEOUT_SECONDS must be numeric") from exc

    return Settings(
        openai_api_key=api_key,
        openai_base_url=base_url,
        text_model=text_model or default_text_model,
        planning_model=planning_model,
        prompt_model=prompt_model,
        image_model=image_model or default_image_model,
        default_language=default_language or "zh-CN",
        default_aspect_ratio=default_aspect_ratio or "16:9",
        request_timeout_seconds=request_timeout_seconds,
        is_gemini=is_gemini,
    )


__all__ = ["Settings", "load_settings"]
