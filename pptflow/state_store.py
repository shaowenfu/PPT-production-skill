from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .errors import ProjectResolutionError, StateStoreError
from .json_io import read_json, write_json
from .paths import resolve_project_dir
from .validators import (
    DEFAULT_ARTIFACT_KEYS,
    DEFAULT_STEP_KEYS,
    normalize_project_id,
    validate_artifact_name,
    validate_workflow_state,
)


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_artifact_path(name: str) -> str:
    mapping = {
        "outline": "outline/outline.json",
        "draft": "draft/slide_draft.json",
        "plan": "plan/plan.json",
        "screen_text": "prompts/screen_text.json",
        "prompts": "prompts/prompts.json",
        "assets_manifest": "assets/manifest.json",
        "deck": "deck/deck.pptx",
        "export_final": "exports/final.pptx",
    }
    return mapping[validate_artifact_name(name)]


def _default_artifacts() -> dict[str, dict[str, Any]]:
    timestamp = None
    return {
        name: {"path": _default_artifact_path(name), "exists": False, "updated_at": timestamp}
        for name in DEFAULT_ARTIFACT_KEYS
    }


def default_workflow_state(project_id: str, project_name: str | None = None) -> dict[str, Any]:
    normalized_project_id = normalize_project_id(project_id)
    now = _now_iso()
    return {
        "schema_version": "1.0",
        "project_id": normalized_project_id,
        "project_name": project_name.strip() if isinstance(project_name, str) and project_name.strip() else None,
        "current_state": "Initialized",
        "last_completed_step": None,
        "last_failed_step": None,
        "status": "active",
        "artifacts": _default_artifacts(),
        "feedback_history": [],
        "transition_history": [],
        "retry_count": {step: 0 for step in DEFAULT_STEP_KEYS},
        "context": {},
        "updated_at": now,
        "created_at": now,
    }


def _state_file(project_dir: Path) -> Path:
    return Path(project_dir).expanduser().resolve() / "state.json"


def _ensure_project_dir(project_dir: Path | str) -> Path:
    return resolve_project_dir(project_dir, create=False)


def load_state(project_dir: Path | str) -> dict[str, Any]:
    resolved_project_dir = _ensure_project_dir(project_dir)
    state_path = _state_file(resolved_project_dir)
    if not state_path.exists():
        raise StateStoreError(f"state file does not exist: {state_path}")
    try:
        raw_state = read_json(state_path)
    except FileNotFoundError as exc:
        raise StateStoreError(f"state file does not exist: {state_path}") from exc
    except Exception as exc:
        raise StateStoreError(f"failed to read state file: {state_path}") from exc

    state = validate_workflow_state(raw_state)
    expected_project_id = resolved_project_dir.name
    if state["project_id"] != expected_project_id:
        raise StateStoreError(
            f"state project_id {state['project_id']!r} does not match project directory {expected_project_id!r}"
        )
    return state


def save_state(project_dir: Path | str, state: Mapping[str, Any]) -> dict[str, Any]:
    resolved_project_dir = _ensure_project_dir(project_dir)
    normalized_state = validate_workflow_state(state)
    expected_project_id = resolved_project_dir.name
    if normalized_state["project_id"] != expected_project_id:
        raise StateStoreError(
            f"state project_id {normalized_state['project_id']!r} does not match project directory {expected_project_id!r}"
        )

    normalized_state = dict(normalized_state)
    normalized_state["updated_at"] = _now_iso()
    write_json(_state_file(resolved_project_dir), normalized_state)
    return normalized_state


def assert_state_has_artifact(state: Mapping[str, Any], artifact_name: str) -> dict[str, Any]:
    normalized_state = validate_workflow_state(state)
    key = validate_artifact_name(artifact_name)
    artifact = normalized_state["artifacts"].get(key)
    if artifact is None:
        raise StateStoreError(f"state does not define artifact {key!r}")
    if not artifact.get("exists"):
        raise StateStoreError(f"artifact {key!r} is not marked as existing")
    return artifact


def set_artifact(
    state: Mapping[str, Any],
    artifact_name: str,
    relative_path: str,
    *,
    exists: bool = True,
    updated_at: str | None = None,
) -> dict[str, Any]:
    normalized_state = validate_workflow_state(state)
    key = validate_artifact_name(artifact_name)
    artifact_record = {
        "path": relative_path,
        "exists": exists,
        "updated_at": updated_at or _now_iso(),
    }
    from .validators import validate_artifact_record

    artifact_record = validate_artifact_record(artifact_record, artifact_name=key)
    normalized_state = dict(normalized_state)
    artifacts = dict(normalized_state["artifacts"])
    artifacts[key] = artifact_record
    normalized_state["artifacts"] = artifacts
    normalized_state["updated_at"] = _now_iso()
    return validate_workflow_state(normalized_state)


def append_transition(state: Mapping[str, Any], transition_record: Mapping[str, Any]) -> dict[str, Any]:
    from .validators import validate_transition_record

    normalized_state = validate_workflow_state(state)
    normalized_state = dict(normalized_state)
    normalized_state["transition_history"] = list(normalized_state["transition_history"]) + [
        validate_transition_record(transition_record)
    ]
    normalized_state["updated_at"] = _now_iso()
    return validate_workflow_state(normalized_state)
