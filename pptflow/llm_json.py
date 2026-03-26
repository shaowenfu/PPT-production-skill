"""Helpers for normalizing and parsing LLM JSON responses."""

from __future__ import annotations

import json
import re
from typing import Any

from .errors import InvalidJSONOutputError

_CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        candidate = value.strip().lstrip("\ufeff")
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def _extract_code_fence_candidates(text: str) -> list[str]:
    return [match.group(1).strip() for match in _CODE_FENCE_PATTERN.finditer(text)]


def _extract_json_fragment(text: str) -> str | None:
    start = None
    for index, char in enumerate(text):
        if char in "{[":
            start = index
            break
    if start is None:
        return None

    stack: list[str] = []
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            stack.append("}")
            continue
        if char == "[":
            stack.append("]")
            continue
        if char in "}]":
            if not stack or stack[-1] != char:
                return text[start : index + 1]
            stack.pop()
            if not stack:
                return text[start : index + 1]

    return text[start:] if stack else None


def _remove_trailing_commas(text: str) -> str:
    chars = list(text)
    result: list[str] = []
    in_string = False
    escaped = False
    length = len(chars)

    for index, char in enumerate(chars):
        if in_string:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            result.append(char)
            continue

        if char == ",":
            next_index = index + 1
            while next_index < length and chars[next_index].isspace():
                next_index += 1
            if next_index < length and chars[next_index] in "}]":
                continue

        result.append(char)

    return "".join(result)


def _repair_simple_truncation(text: str) -> str:
    candidate = text.rstrip()
    if not candidate:
        return candidate

    while candidate and candidate[-1] in ",:":
        candidate = candidate[:-1].rstrip()

    stack: list[str] = []
    in_string = False
    escaped = False

    for char in candidate:
        if in_string:
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            stack.append("}")
            continue
        if char == "[":
            stack.append("]")
            continue
        if char in "}]":
            if stack and stack[-1] == char:
                stack.pop()

    if in_string:
        candidate += '"'
    if stack:
        candidate += "".join(reversed(stack))
    return candidate


def _candidate_variants(text: str) -> list[str]:
    fragment = _extract_json_fragment(text)
    variants = [text]
    if fragment:
        variants.append(fragment)

    derived: list[str] = []
    for candidate in variants:
        no_trailing_commas = _remove_trailing_commas(candidate)
        repaired = _repair_simple_truncation(candidate)
        repaired_no_trailing_commas = _remove_trailing_commas(repaired)
        derived.extend([candidate, no_trailing_commas, repaired, repaired_no_trailing_commas])
    return _dedupe_preserve_order(derived)


def parse_llm_json(text: str, *, source: str = "LLM 响应") -> dict[str, Any]:
    if not isinstance(text, str):
        raise InvalidJSONOutputError(
            f"{source} 不是字符串",
            details={"source": source, "type": type(text).__name__},
        )

    base_candidates = [text.strip()]
    base_candidates.extend(_extract_code_fence_candidates(text))

    attempts: list[dict[str, Any]] = []
    for candidate in _dedupe_preserve_order(base_candidates):
        for variant in _candidate_variants(candidate):
            try:
                payload = json.loads(variant)
            except json.JSONDecodeError as exc:
                attempts.append(
                    {
                        "candidate_preview": variant[:200],
                        "error": str(exc),
                    }
                )
                continue
            if not isinstance(payload, dict):
                raise InvalidJSONOutputError(
                    f"{source} 顶层 JSON 必须是对象",
                    details={"source": source, "top_level_type": type(payload).__name__},
                )
            return payload

    raise InvalidJSONOutputError(
        f"{source} 不是可修复的合法 JSON",
        details={"source": source, "attempts": attempts[:8]},
    )


__all__ = ["parse_llm_json"]
