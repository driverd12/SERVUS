#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REPO_ROOT="${SERVUS_REPO_ROOT:-${REPO_ROOT_DEFAULT}}"
PYTHON_BIN="${SERVUS_PYTHON_BIN:-$(command -v python3)}"
LAUNCHD_LABEL="${SERVUS_LAUNCHD_LABEL:-com.boom.servus.scheduler}"
DRY_RUN="false"

usage() {
  cat <<'EOF'
Usage:
  scripts/install_scheduler_launchd.sh [--repo-root PATH] [--python-bin PATH] [--label NAME] [--dry-run]

Notes:
  - Installs/updates a per-user launchd service in ~/Library/LaunchAgents.
  - Enables auto-restart and strict startup preflight.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-root)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    --label)
      LAUNCHD_LABEL="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

TEMPLATE="${REPO_ROOT}/ops/launchd/com.boom.servus.scheduler.plist.template"
TARGET="${HOME}/Library/LaunchAgents/${LAUNCHD_LABEL}.plist"

if [[ ! -f "${TEMPLATE}" ]]; then
  echo "Template not found: ${TEMPLATE}" >&2
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python binary not executable: ${PYTHON_BIN}" >&2
  exit 1
fi

mkdir -p "$(dirname "${TARGET}")"
sed \
  -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \
  -e "s|__PYTHON_BIN__|${PYTHON_BIN}|g" \
  "${TEMPLATE}" > "${TARGET}"

echo "Rendered launchd plist: ${TARGET}"

if [[ "${DRY_RUN}" == "true" ]]; then
  echo "Dry run complete. No launchctl changes applied."
  exit 0
fi

launchctl unload "${TARGET}" >/dev/null 2>&1 || true
launchctl load -w "${TARGET}"
echo "Loaded launchd service: ${LAUNCHD_LABEL}"
launchctl print "gui/$(id -u)/${LAUNCHD_LABEL}" | grep -E "state =|pid =|last exit code" || true
