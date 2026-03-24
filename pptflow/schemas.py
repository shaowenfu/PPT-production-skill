"""Pydantic models for the PPT workflow shared data contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, root_validator, validator


class ContractModel(BaseModel):
    class Config:
        extra = "forbid"


WorkflowStateName = Literal[
    "Initialized",
    "OutlineImported",
    "DraftGenerated",
    "PlanConfirmed",
    "AssetsGenerated",
    "DeckAssembled",
    "FinalApproved",
    "Blocked",
]

ProjectStatus = Literal["active", "waiting_user", "failed", "completed", "archived"]
FeedbackScope = Literal["outline", "draft", "plan", "asset", "assembly", "final"]
PageCategory = Literal["A", "B"]
SlideIntent = Literal["cover", "content", "quote", "transition", "summary"]
PromptStrategy = Literal["simple_background", "emotional_visual"]


class ArtifactRecord(ContractModel):
    path: str
    exists: bool
    updated_at: Optional[datetime] = None


class FeedbackRecord(ContractModel):
    feedback_id: str
    timestamp: datetime
    from_state: WorkflowStateName
    target_scope: FeedbackScope
    target_pages: List[str] = Field(default_factory=list)
    summary: str
    action: str


class TransitionRecord(ContractModel):
    timestamp: datetime
    from_state: WorkflowStateName
    to_state: WorkflowStateName
    trigger: Literal["tool_success", "user_feedback", "manual_recover", "retry_success", "rollback"]
    step: str
    note: Optional[str] = None


class WorkflowState(ContractModel):
    schema_version: str = "1.0"
    project_id: str
    project_name: Optional[str] = None
    current_state: WorkflowStateName
    last_completed_step: Optional[str] = None
    last_failed_step: Optional[str] = None
    status: ProjectStatus = "active"
    artifacts: Dict[str, ArtifactRecord] = Field(default_factory=dict)
    feedback_history: List[FeedbackRecord] = Field(default_factory=list)
    transition_history: List[TransitionRecord] = Field(default_factory=list)
    retry_count: Dict[str, int] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime
    created_at: datetime

    @validator("project_id")
    def project_id_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("project_id must not be empty")
        return value

    @validator("retry_count")
    def retry_counts_must_be_non_negative(cls, value: Dict[str, int]) -> Dict[str, int]:
        for step, count in value.items():
            if count < 0:
                raise ValueError(f"retry_count[{step}] must be non-negative")
        return value


class OutlineSourceFile(ContractModel):
    path: str
    type: Literal["docx", "pdf", "txt", "md"]


class OutlineSection(ContractModel):
    id: str
    title: str
    level: int
    content: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @validator("level")
    def level_must_be_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("section level must be >= 1")
        return value


class OutlineDocument(ContractModel):
    project_id: str
    source_files: List[OutlineSourceFile] = Field(default_factory=list)
    title: Optional[str] = None
    sections: List[OutlineSection] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @root_validator(skip_on_failure=True)
    def outline_must_have_title_or_sections(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        title = values.get("title")
        sections = values.get("sections") or []
        if not title and not sections:
            raise ValueError("outline must have a title or at least one section")
        return values


class SlideDraftSlide(ContractModel):
    page_id: str
    source_section: Optional[str] = None
    title: str
    slide_text: List[str] = Field(default_factory=list)
    quote: Optional[str] = None
    speaker_note: Optional[str] = None
    intent: SlideIntent = "content"
    metadata: Dict[str, Any] = Field(default_factory=dict)


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
    prompt_strategy: PromptStrategy
    style_tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


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
    negative_prompt: str
    aspect_ratio: str = "16:9"
    style_tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


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
    "ArtifactRecord",
    "AssetItem",
    "AssetManifest",
    "ContractModel",
    "FeedbackRecord",
    "FeedbackScope",
    "OutlineDocument",
    "OutlineSection",
    "OutlineSourceFile",
    "PageCategory",
    "PlanPage",
    "PromptDocument",
    "PromptItem",
    "PromptStrategy",
    "ProjectStatus",
    "SlideDraftDocument",
    "SlideDraftSlide",
    "SlideIntent",
    "SlidePlanDocument",
    "TransitionRecord",
    "WorkflowState",
    "WorkflowStateName",
]
