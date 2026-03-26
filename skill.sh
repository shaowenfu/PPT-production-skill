#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"
ACTIVATE_SCRIPT="${REPO_ROOT}/venv/bin/activate"

emit_error_json() {
  local code="$1"
  local message="$2"
  local exit_code="$3"
  printf '{\n'
  printf '  "ok": false,\n'
  printf '  "tool": "skill.sh",\n'
  printf '  "project_id": null,\n'
  printf '  "project_dir": null,\n'
  printf '  "artifacts": [],\n'
  printf '  "metrics": {},\n'
  printf '  "warnings": [],\n'
  printf '  "error": {\n'
  printf '    "code": "%s",\n' "${code}"
  printf '    "message": "%s",\n' "${message}"
  printf '    "details": {},\n'
  printf '    "exit_code": %s\n' "${exit_code}"
  printf '  }\n'
  printf '}\n'
}

if [[ ! -f "${ACTIVATE_SCRIPT}" ]]; then
  emit_error_json "ENVIRONMENT_ERROR" "缺少虚拟环境，请先创建 venv 并安装依赖" 40
  >&2 echo "missing virtual environment at ${ACTIVATE_SCRIPT}"
  exit 40
fi

# shellcheck disable=SC1091
source "${ACTIVATE_SCRIPT}"
exec python "${REPO_ROOT}/scripts/execute_step.py" "$@"
