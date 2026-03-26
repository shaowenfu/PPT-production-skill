from __future__ import annotations

import pytest

from pptflow.errors import InvalidJSONOutputError
from pptflow.llm_json import parse_llm_json


def test_parse_llm_json_accepts_plain_json_object() -> None:
    payload = parse_llm_json('{"project_id":"demo","slides":[{"page_id":"p1","content":"x"}]}')
    assert payload["project_id"] == "demo"


def test_parse_llm_json_extracts_json_from_code_fence_and_prefix_suffix() -> None:
    raw = """
    下面是结果：

    ```json
    {
      "project_id": "demo",
      "slides": [{"page_id": "p1", "content": "x"}]
    }
    ```

    请查收。
    """
    payload = parse_llm_json(raw)
    assert payload["slides"][0]["page_id"] == "p1"


def test_parse_llm_json_repairs_trailing_commas() -> None:
    raw = '{"project_id":"demo","slides":[{"page_id":"p1","content":"x",},],}'
    payload = parse_llm_json(raw)
    assert payload["project_id"] == "demo"


def test_parse_llm_json_repairs_simple_truncation() -> None:
    raw = '{"project_id":"demo","slides":[{"page_id":"p1","content":"x"}]'
    payload = parse_llm_json(raw)
    assert payload["slides"][0]["content"] == "x"


def test_parse_llm_json_rejects_non_object_top_level_json() -> None:
    with pytest.raises(InvalidJSONOutputError):
        parse_llm_json('[{"page_id":"p1"}]')


def test_parse_llm_json_rejects_unrecoverable_text() -> None:
    with pytest.raises(InvalidJSONOutputError):
        parse_llm_json("这不是 JSON，也没有可提取的对象。")
