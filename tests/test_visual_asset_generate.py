from __future__ import annotations

import sys
import types


google_module = types.ModuleType("google")
google_genai_module = types.ModuleType("google.genai")
google_genai_types_module = types.ModuleType("google.genai.types")
google_genai_module.types = google_genai_types_module
google_module.genai = google_genai_module
openai_module = types.ModuleType("openai")
openai_module.AsyncOpenAI = object


class _DummyRateLimitError(Exception):
    pass


openai_module.RateLimitError = _DummyRateLimitError
pil_module = types.ModuleType("PIL")
pil_image_module = types.ModuleType("PIL.Image")
pil_module.Image = pil_image_module
sys.modules.setdefault("google", google_module)
sys.modules.setdefault("google.genai", google_genai_module)
sys.modules.setdefault("google.genai.types", google_genai_types_module)
sys.modules.setdefault("openai", openai_module)
sys.modules.setdefault("PIL", pil_module)
sys.modules.setdefault("PIL.Image", pil_image_module)

from scripts.visual_asset_generate import _compose_final_image_prompt


def test_compose_final_image_prompt_appends_master_style_and_constraints() -> None:
    prompt = _compose_final_image_prompt(
        'Render the Chinese title "AI中台建设的核心价值".',
        "Deck-level style: restrained enterprise keynote.",
    )

    assert 'Render the Chinese title "AI中台建设的核心价值".' in prompt
    assert "Deck-level style: restrained enterprise keynote." in prompt
    assert "Visual Style: High-end corporate AI training presentation" in prompt
    assert "Background constraints: use a dark background only" in prompt
    assert "Negative constraints: NO photorealistic humans" in prompt
    assert "render only the exact text explicitly specified in this prompt" in prompt


def test_compose_final_image_prompt_without_base_prompt_still_keeps_global_constraints() -> None:
    prompt = _compose_final_image_prompt("", None)

    assert "Visual Style: High-end corporate AI training presentation" in prompt
    assert "Background constraints: use a dark background only" in prompt
    assert "render only the exact text explicitly specified in this prompt" in prompt
