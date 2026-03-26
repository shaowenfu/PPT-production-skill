from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .errors import InputError, ProjectResolutionError
from .validators import normalize_project_id


@dataclass(frozen=True)
class ProjectPaths:
    repo_root: Path
    ppt_root: Path
    project_id: str
    project_dir: Path

    @property
    def state_file(self) -> Path:
        return self.project_dir / "state.json"

    @property
    def outline_dir(self) -> Path:
        return self.project_dir / "outline"

    @property
    def draft_dir(self) -> Path:
        return self.project_dir / "draft"

    @property
    def plan_dir(self) -> Path:
        return self.project_dir / "plan"

    @property
    def prompts_dir(self) -> Path:
        return self.project_dir / "prompts"

    @property
    def assets_dir(self) -> Path:
        return self.project_dir / "assets"

    @property
    def deck_dir(self) -> Path:
        return self.project_dir / "deck"

    @property
    def exports_dir(self) -> Path:
        return self.project_dir / "exports"

    @property
    def outline_file(self) -> Path:
        return self.outline_dir / "outline.json"

    @property
    def draft_file(self) -> Path:
        return self.draft_dir / "slide_draft.json"

    @property
    def plan_file(self) -> Path:
        return self.plan_dir / "plan.json"

    @property
    def prompts_file(self) -> Path:
        return self.prompts_dir / "prompts.json"

    @property
    def assets_manifest_file(self) -> Path:
        return self.assets_dir / "manifest.json"

    @property
    def deck_file(self) -> Path:
        return self.deck_dir / "deck.pptx"

    @property
    def export_final_file(self) -> Path:
        return self.exports_dir / "final.pptx"


def _as_path(value: Path | str | None) -> Path:
    if value is None:
        return Path.cwd()
    return Path(value).expanduser()


def resolve_project_dir(project_dir: Path | str, *, create: bool = False) -> Path:
    resolved = Path(project_dir).expanduser().resolve()
    normalize_project_id(resolved.name)
    if resolved.exists():
        if not resolved.is_dir():
            raise ProjectResolutionError(f"project directory is not a directory: {resolved}")
        return resolved
    if create:
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved
    raise ProjectResolutionError(f"project directory does not exist: {resolved}")


def resolve_project_dir_input(
    *,
    project_dir: Path | str | None = None,
    project_id: str | None = None,
    repo_root: Path | str | None = None,
    ppt_root: Path | str | None = None,
    create_ppt_root: bool = False,
    create_project_dir: bool = False,
) -> Path:
    if project_dir is not None:
        resolved_project_dir = resolve_project_dir(project_dir, create=create_project_dir)
        if project_id is not None:
            normalized_project_id = normalize_project_id(project_id)
            if resolved_project_dir.name != normalized_project_id:
                raise InputError(
                    "project_dir 与 project_id 不一致",
                    details={
                        "project_dir": str(resolved_project_dir),
                        "project_id": normalized_project_id,
                    },
                )
        return resolved_project_dir

    if project_id is None:
        raise InputError("必须提供 project_dir 或 project_id")

    return resolve_project_paths(
        project_id,
        repo_root=repo_root,
        ppt_root=ppt_root,
        create_ppt_root=create_ppt_root,
        create_project_dir=create_project_dir,
    ).project_dir


def find_repo_root(start: Path | str | None = None) -> Path:
    candidate = _as_path(start)
    if candidate.is_file():
        candidate = candidate.parent
    candidate = candidate.resolve()

    for current in (candidate, *candidate.parents):
        if (current / ".git").exists():
            return current

    raise ProjectResolutionError(f"cannot locate repository root from {candidate}")


def locate_ppt_root(repo_root: Path | str | None = None, *, create: bool = False) -> Path:
    root = find_repo_root(repo_root) if repo_root is not None else find_repo_root()
    ppt_root = root / "PPT"
    if ppt_root.exists():
        if not ppt_root.is_dir():
            raise ProjectResolutionError(f"{ppt_root} exists but is not a directory")
        return ppt_root
    if create:
        ppt_root.mkdir(parents=True, exist_ok=True)
        return ppt_root
    raise ProjectResolutionError(f"cannot locate PPT workspace root at {ppt_root}")


def project_dir_for(ppt_root: Path | str, project_id: str, *, create: bool = False) -> Path:
    normalized_project_id = normalize_project_id(project_id)
    root = Path(ppt_root).expanduser().resolve()
    if not root.exists():
        if create:
            root.mkdir(parents=True, exist_ok=True)
        else:
            raise ProjectResolutionError(f"ppt root does not exist: {root}")
    if not root.is_dir():
        raise ProjectResolutionError(f"ppt root is not a directory: {root}")

    project_dir = root / normalized_project_id
    if project_dir.exists():
        if not project_dir.is_dir():
            raise ProjectResolutionError(f"project path exists but is not a directory: {project_dir}")
        return project_dir
    if create:
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    return project_dir


def resolve_project_paths(
    project_id: str,
    *,
    repo_root: Path | str | None = None,
    ppt_root: Path | str | None = None,
    create_ppt_root: bool = False,
    create_project_dir: bool = False,
) -> ProjectPaths:
    normalized_project_id = normalize_project_id(project_id)

    if ppt_root is not None:
        ppt_root_path = Path(ppt_root).expanduser().resolve()
        if not ppt_root_path.exists():
            if create_ppt_root:
                ppt_root_path.mkdir(parents=True, exist_ok=True)
            else:
                raise ProjectResolutionError(f"ppt root does not exist: {ppt_root_path}")
        if not ppt_root_path.is_dir():
            raise ProjectResolutionError(f"ppt root is not a directory: {ppt_root_path}")
        repo_root_path = find_repo_root(repo_root) if repo_root is not None else find_repo_root(ppt_root_path)
    else:
        repo_root_path = find_repo_root(repo_root)
        ppt_root_path = locate_ppt_root(repo_root_path, create=create_ppt_root)

    project_dir = project_dir_for(ppt_root_path, normalized_project_id, create=create_project_dir)
    return ProjectPaths(
        repo_root=repo_root_path,
        ppt_root=ppt_root_path,
        project_id=normalized_project_id,
        project_dir=project_dir,
    )
