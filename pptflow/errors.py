"""Shared exception types and exit-code mapping for the PPT workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, ClassVar, Dict, Mapping, Type


class ExitCode(IntEnum):
    SUCCESS = 0
    INPUT_ERROR = 10
    PROJECT_RESOLUTION_ERROR = 20
    STATE_STORE_ERROR = 30
    ENVIRONMENT_ERROR = 40
    UPSTREAM_SERVICE_ERROR = 50
    OUTPUT_VALIDATION_ERROR = 60


@dataclass
class PPTWorkflowError(Exception):
    """Base class for all workflow errors."""

    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    exit_code: ClassVar[ExitCode] = ExitCode.OUTPUT_VALIDATION_ERROR
    error_code: ClassVar[str] = "WORKFLOW_ERROR"

    def __post_init__(self) -> None:
        self.message = str(self.message).strip()
        super().__init__(self.message)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "code": type(self).error_code,
            "message": self.message,
            "details": self.details,
            "exit_code": int(type(self).exit_code),
        }


class InputError(PPTWorkflowError):
    exit_code = ExitCode.INPUT_ERROR
    error_code = "INPUT_ERROR"


class ProjectResolutionError(PPTWorkflowError):
    exit_code = ExitCode.PROJECT_RESOLUTION_ERROR
    error_code = "PROJECT_RESOLUTION_ERROR"


class StateStoreError(PPTWorkflowError):
    exit_code = ExitCode.STATE_STORE_ERROR
    error_code = "STATE_STORE_ERROR"


class EnvironmentError(PPTWorkflowError):
    exit_code = ExitCode.ENVIRONMENT_ERROR
    error_code = "ENVIRONMENT_ERROR"


class NeedsConfigError(EnvironmentError):
    error_code = "NEEDS_CONFIG"


class MissingAPIKeyError(NeedsConfigError):
    error_code = "MISSING_API_KEY"


class InvalidEnvironmentError(EnvironmentError):
    error_code = "INVALID_ENV"


class UpstreamServiceError(PPTWorkflowError):
    exit_code = ExitCode.UPSTREAM_SERVICE_ERROR
    error_code = "UPSTREAM_SERVICE_ERROR"


class UpstreamTimeoutError(UpstreamServiceError):
    error_code = "UPSTREAM_TIMEOUT"


class UpstreamBadResponseError(UpstreamServiceError):
    error_code = "UPSTREAM_BAD_RESPONSE"


class OutputValidationError(PPTWorkflowError):
    exit_code = ExitCode.OUTPUT_VALIDATION_ERROR
    error_code = "OUTPUT_VALIDATION_ERROR"


EXIT_CODE_BY_EXCEPTION: Mapping[Type[BaseException], ExitCode] = {
    InputError: ExitCode.INPUT_ERROR,
    ProjectResolutionError: ExitCode.PROJECT_RESOLUTION_ERROR,
    StateStoreError: ExitCode.STATE_STORE_ERROR,
    NeedsConfigError: ExitCode.ENVIRONMENT_ERROR,
    MissingAPIKeyError: ExitCode.ENVIRONMENT_ERROR,
    InvalidEnvironmentError: ExitCode.ENVIRONMENT_ERROR,
    EnvironmentError: ExitCode.ENVIRONMENT_ERROR,
    UpstreamTimeoutError: ExitCode.UPSTREAM_SERVICE_ERROR,
    UpstreamBadResponseError: ExitCode.UPSTREAM_SERVICE_ERROR,
    UpstreamServiceError: ExitCode.UPSTREAM_SERVICE_ERROR,
    OutputValidationError: ExitCode.OUTPUT_VALIDATION_ERROR,
    PPTWorkflowError: ExitCode.OUTPUT_VALIDATION_ERROR,
}


def exit_code_for_exception(exc: BaseException) -> ExitCode:
    """Return the workflow exit code for an exception instance."""

    for error_type, exit_code in EXIT_CODE_BY_EXCEPTION.items():
        if isinstance(exc, error_type):
            return exit_code
    return ExitCode.OUTPUT_VALIDATION_ERROR


def error_payload_for_exception(exc: BaseException) -> Dict[str, Any]:
    """Build a JSON-serializable error payload for CLI summaries."""

    if isinstance(exc, PPTWorkflowError):
        return exc.to_payload()
    return {
        "code": "UNHANDLED_ERROR",
        "message": str(exc),
        "details": {},
        "exit_code": int(ExitCode.OUTPUT_VALIDATION_ERROR),
    }


__all__ = [
    "EnvironmentError",
    "EXIT_CODE_BY_EXCEPTION",
    "ExitCode",
    "InvalidEnvironmentError",
    "InputError",
    "MissingAPIKeyError",
    "NeedsConfigError",
    "OutputValidationError",
    "PPTWorkflowError",
    "ProjectResolutionError",
    "StateStoreError",
    "UpstreamBadResponseError",
    "UpstreamServiceError",
    "UpstreamTimeoutError",
    "error_payload_for_exception",
    "exit_code_for_exception",
]
