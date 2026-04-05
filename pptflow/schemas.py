"""Pydantic models for the PPT workflow shared data contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, root_validator, validator


class ContractModel(BaseModel):
    class Config:
        extra = "forbid"


PageCategory = Literal["A", "B"]
SlideIntent = Literal["cover", "content", "quote", "transition", "summary"]
PageContentMode = Literal["generated", "locked"]
class SlideDraftSlide(ContractModel):
    page_id: str
    content: str  # 专注于深度的业务逻辑、技术分析或案例详情描述


class SlideDraftDocument(ContractModel):
    project_id: str
    slides: List[SlideDraftSlide] = Field(default_factory=list)

    @validator("slides")
    def slides_must_have_unique_page_ids(cls, value: List[SlideDraftSlide]) -> List[SlideDraftSlide]:
        page_ids = [slide.page_id for slide in value]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("slide page_id values must be unique")
        if not value:
            raise ValueError("slide draft must contain at least one slide")
        return value


class PlanPage(ContractModel):
    page_id: str
    title: Optional[str] = None
    content_hint: Optional[str] = None  # 大纲内容片段或要点
    category: PageCategory
    layout_type: str
    content_mode: PageContentMode = "generated"
    source_text: Optional[str] = None

    @root_validator(skip_on_failure=True)
    def validate_content_contract(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        content_mode = values.get("content_mode") or "generated"
        content_hint = values.get("content_hint")
        source_text = values.get("source_text")

        normalized_content_hint = content_hint.strip() if isinstance(content_hint, str) else None
        normalized_source_text = source_text.strip() if isinstance(source_text, str) else None
        values["content_hint"] = normalized_content_hint or None
        values["source_text"] = normalized_source_text or None

        if content_mode == "generated":
            if not normalized_content_hint:
                raise ValueError("generated page must define non-empty content_hint")
            if normalized_source_text is not None:
                raise ValueError("generated page must not define source_text")
            return values

        if not normalized_source_text:
            raise ValueError("locked page must define non-empty source_text")
        return values


class SlidePlanDocument(ContractModel):
    project_id: str
    pages: List[PlanPage] = Field(default_factory=list)
    target_b_ratio: float = 0.3
    actual_b_ratio: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("pages")
    def pages_must_be_unique_and_non_empty(cls, value: List[PlanPage]) -> List[PlanPage]:
        page_ids = [page.page_id for page in value]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("plan page_id values must be unique")
        if not value:
            raise ValueError("slide plan must contain at least one page")
        return value


class PromptItem(ContractModel):
    page_id: str
    prompt: str


class PromptDocument(ContractModel):
    project_id: str
    items: List[PromptItem] = Field(default_factory=list)

    @validator("items")
    def items_must_be_unique_and_non_empty(cls, value: List[PromptItem]) -> List[PromptItem]:
        page_ids = [item.page_id for item in value]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("prompt page_id values must be unique")
        if not value:
            raise ValueError("prompt document must contain at least one item")
        return value


class ScreenTextItem(ContractModel):
    page_id: str
    text: str


class ScreenTextDocument(ContractModel):
    project_id: str
    items: List[ScreenTextItem] = Field(default_factory=list)

    @validator("items")
    def items_must_be_unique_and_non_empty(cls, value: List[ScreenTextItem]) -> List[ScreenTextItem]:
        page_ids = [item.page_id for item in value]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("screen text page_id values must be unique")
        if not value:
            raise ValueError("screen text document must contain at least one item")
        return value


class AssetItem(ContractModel):
    page_id: str
    file_path: str
    width: int
    height: int
    provider: Optional[str] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("width", "height")
    def dimensions_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("asset dimensions must be positive")
        return value


class AssetManifest(ContractModel):
    project_id: str
    items: List[AssetItem] = Field(default_factory=list)

    @validator("items")
    def items_must_be_unique_and_non_empty(cls, value: List[AssetItem]) -> List[AssetItem]:
        page_ids = [item.page_id for item in value]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("asset page_id values must be unique")
        if not value:
            raise ValueError("asset manifest must contain at least one item")
        return value


__all__ = [
    "AssetItem",
    "AssetManifest",
    "ContractModel",
    "PageContentMode",
    "PageCategory",
    "PlanPage",
    "PromptDocument",
    "PromptItem",
    "ScreenTextDocument",
    "ScreenTextItem",
    "SlideDraftDocument",
    "SlideDraftSlide",
    "SlideIntent",
    "SlidePlanDocument",
]
