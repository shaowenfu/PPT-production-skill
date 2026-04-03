from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from .errors import (
    InputError,
    OutputValidationError,
    PPTWorkflowError,
    ProjectResolutionError,
    StateStoreError,
)


PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ARTIFACT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]*$")

ALLOWED_STATES = {
    "Initialized",
    "OutlineImported",
    "DraftGenerated",
    "PlanConfirmed",
    "PromptsGenerated",
    "AssetsGenerated",
    "DeckAssembled",
    "FinalApproved",
    "Blocked",
}

ALLOWED_STATUS = {
    "active",
    "waiting_user",
    "failed",
    "completed",
    "archived",
}

DEFAULT_STEP_KEYS = (
    "project_init",
    "outline_ingest",
    "slide_draft_generate",
    "slide_plan_generate",
    "visual_prompt_design",
    "visual_asset_generate",
    "ppt_assemble",
    "final_approve",
)

DEFAULT_ARTIFACT_KEYS = (
    "outline",
    "draft",
    "plan",
    "screen_text",
    "prompts",
    "assets_manifest",
    "deck",
    "export_final",
)


def normalize_project_id(project_id: str) -> str:
    if not isinstance(project_id, str):
        raise InputError("project_id must be a string")
    value = project_id.strip()
    if not value:
        raise InputError("project_id cannot be empty")
    if any(part in value for part in ("/", "\\", "..")):
        raise InputError("project_id cannot contain path separators or traversal markers")
    if not PROJECT_ID_PATTERN.fullmatch(value):
        raise InputError(
            "project_id must start with an alphanumeric character and contain only "
            "letters, digits, dots, underscores, or hyphens"
        )
    return value


def validate_artifact_name(name: str) -> str:
    if not isinstance(name, str):
        raise StateStoreError("artifact name must be a string")
    value = name.strip()
    if not value:
        raise StateStoreError("artifact name cannot be empty")
    if any(part in value for part in ("/", "\\", "..")):
        raise StateStoreError("artifact name cannot contain path separators or traversal markers")
    if not ARTIFACT_NAME_PATTERN.fullmatch(value):
        raise StateStoreError("artifact name contains invalid characters")
    return value


def validate_iso_datetime(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise StateStoreError(f"{field_name} must be an ISO 8601 string")
    candidate = value.strip()
    if not candidate:
        raise StateStoreError(f"{field_name} cannot be empty")
    try:
        datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StateStoreError(f"{field_name} must be an ISO 8601 timestamp") from exc
    return candidate


def validate_artifact_record(record: Any, *, artifact_name: str | None = None) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        label = artifact_name or "artifact"
        raise StateStoreError(f"{label} record must be a mapping")

    if "path" not in record or "exists" not in record or "updated_at" not in record:
        label = artifact_name or "artifact"
        raise StateStoreError(f"{label} record must contain path, exists, and updated_at")

    path = record["path"]
    if not isinstance(path, str):
        raise StateStoreError("artifact path must be a string")
    path = path.strip()
    if not path:
        raise StateStoreError("artifact path cannot be empty")
    if Path(path).is_absolute():
        raise StateStoreError("artifact path must be relative to the project directory")
    if any(part in path for part in ("..", "\\")):
        raise StateStoreError("artifact path cannot contain traversal markers")

    exists = record["exists"]
    if not isinstance(exists, bool):
        raise StateStoreError("artifact exists flag must be a boolean")

    updated_at = record["updated_at"]
    if updated_at is not None:
        updated_at = validate_iso_datetime(updated_at, field_name="artifact updated_at")

    result = dict(record)
    result["path"] = path
    result["exists"] = exists
    result["updated_at"] = updated_at
    return result


def validate_transition_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise StateStoreError("transition record must be a mapping")

    required = {"timestamp", "from_state", "to_state", "trigger", "step", "note"}
    missing = sorted(required - set(record))
    if missing:
        raise StateStoreError(f"transition record is missing fields: {', '.join(missing)}")

    timestamp = validate_iso_datetime(record["timestamp"], field_name="transition timestamp")
    from_state = record["from_state"]
    to_state = record["to_state"]
    trigger = record["trigger"]
    step = record["step"]
    note = record["note"]

    if not isinstance(from_state, str) or from_state not in ALLOWED_STATES:
        raise StateStoreError("transition from_state is invalid")
    if not isinstance(to_state, str) or to_state not in ALLOWED_STATES:
        raise StateStoreError("transition to_state is invalid")
    if not isinstance(trigger, str) or not trigger.strip():
        raise StateStoreError("transition trigger must be a non-empty string")
    if not isinstance(step, str) or not step.strip():
        raise StateStoreError("transition step must be a non-empty string")
    if not isinstance(note, str):
        raise StateStoreError("transition note must be a string")

    result = dict(record)
    result["timestamp"] = timestamp
    result["from_state"] = from_state
    result["to_state"] = to_state
    result["trigger"] = trigger.strip()
    result["step"] = step.strip()
    result["note"] = note.strip()
    return result


def validate_workflow_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, Mapping):
        raise StateStoreError("state must be a mapping")

    required = {
        "schema_version",
        "project_id",
        "current_state",
        "status",
        "artifacts",
        "feedback_history",
        "transition_history",
        "retry_count",
        "updated_at",
        "created_at",
    }
    missing = sorted(required - set(state))
    if missing:
        raise StateStoreError(f"state is missing fields: {', '.join(missing)}")

    normalized: dict[str, Any] = dict(state)
    normalized["schema_version"] = str(normalized["schema_version"]).strip()
    if not normalized["schema_version"]:
        raise StateStoreError("schema_version cannot be empty")
    normalized["project_id"] = normalize_project_id(str(normalized["project_id"]))

    current_state = normalized["current_state"]
    if not isinstance(current_state, str) or current_state.strip() not in ALLOWED_STATES:
        raise StateStoreError("current_state is invalid")
    normalized["current_state"] = current_state.strip()

    status = normalized["status"]
    if not isinstance(status, str) or status.strip() not in ALLOWED_STATUS:
        raise StateStoreError("status is invalid")
    normalized["status"] = status.strip()

    artifacts = normalized["artifacts"]
    if not isinstance(artifacts, Mapping):
        raise StateStoreError("artifacts must be a mapping")
    normalized["artifacts"] = {
        validate_artifact_name(name): validate_artifact_record(record, artifact_name=name)
        for name, record in artifacts.items()
    }

    feedback_history = normalized["feedback_history"]
    if not isinstance(feedback_history, list):
        raise StateStoreError("feedback_history must be a list")
    normalized["feedback_history"] = list(feedback_history)

    transition_history = normalized["transition_history"]
    if not isinstance(transition_history, list):
        raise StateStoreError("transition_history must be a list")
    normalized["transition_history"] = [validate_transition_record(item) for item in transition_history]

    retry_count = normalized["retry_count"]
    if not isinstance(retry_count, Mapping):
        raise StateStoreError("retry_count must be a mapping")
    normalized["retry_count"] = dict(retry_count)

    normalized["updated_at"] = validate_iso_datetime(normalized["updated_at"], field_name="updated_at")
    normalized["created_at"] = validate_iso_datetime(normalized["created_at"], field_name="created_at")

    project_name = normalized.get("project_name")
    if project_name is not None and (not isinstance(project_name, str) or not project_name.strip()):
        raise StateStoreError("project_name must be a non-empty string or null")
    if isinstance(project_name, str):
        normalized["project_name"] = project_name.strip()

    context = normalized.get("context", {})
    if context is None:
        context = {}
    if not isinstance(context, Mapping):
        raise StateStoreError("context must be a mapping when provided")
    normalized["context"] = dict(context)

    last_completed_step = normalized.get("last_completed_step")
    if last_completed_step is not None and (not isinstance(last_completed_step, str) or not last_completed_step.strip()):
        raise StateStoreError("last_completed_step must be a non-empty string or null")
    if isinstance(last_completed_step, str):
        normalized["last_completed_step"] = last_completed_step.strip()

    last_failed_step = normalized.get("last_failed_step")
    if last_failed_step is not None and (not isinstance(last_failed_step, str) or not last_failed_step.strip()):
        raise StateStoreError("last_failed_step must be a non-empty string or null")
    if isinstance(last_failed_step, str):
        normalized["last_failed_step"] = last_failed_step.strip()

    return normalized


__all__ = [
    "ALLOWED_STATES",
    "ALLOWED_STATUS",
    "DEFAULT_ARTIFACT_KEYS",
    "DEFAULT_STEP_KEYS",
    "InputError",
    "OutputValidationError",
    "PPTWorkflowError",
    "ProjectResolutionError",
    "StateStoreError",
    "normalize_project_id",
    "validate_artifact_name",
    "validate_artifact_record",
    "validate_iso_datetime",
    "validate_transition_record",
    "validate_workflow_state",
]
