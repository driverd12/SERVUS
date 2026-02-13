#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REPO_ROOT="${SERVUS_REPO_ROOT:-${REPO_ROOT_DEFAULT}}"
PYTHON_BIN="${SERVUS_PYTHON_BIN:-/usr/bin/python3}"
RUN_USER="${SERVUS_RUN_USER:-servus}"
OUTPUT_PATH="${SERVUS_SYSTEMD_OUTPUT:-${REPO_ROOT}/servus-scheduler.service}"

usage() {
  cat <<'EOF'
Usage:
  scripts/render_scheduler_systemd.sh [--repo-root PATH] [--python-bin PATH] [--run-user USER] [--output PATH]

Output:
  - Renders a systemd unit file suitable for a dedicated SERVUS host.
  - Does not require root; prints install commands at the end.
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
    --run-user)
      RUN_USER="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
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

TEMPLATE="${REPO_ROOT}/ops/systemd/servus-scheduler.service.template"
if [[ ! -f "${TEMPLATE}" ]]; then
  echo "Template not found: ${TEMPLATE}" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUTPUT_PATH}")"
sed \
  -e "s|__REPO_ROOT__|${REPO_ROOT}|g" \
  -e "s|__PYTHON_BIN__|${PYTHON_BIN}|g" \
  -e "s|__RUN_USER__|${RUN_USER}|g" \
  "${TEMPLATE}" > "${OUTPUT_PATH}"

echo "Rendered systemd unit: ${OUTPUT_PATH}"
echo ""
echo "Install on target host:"
echo "  sudo cp \"${OUTPUT_PATH}\" /etc/systemd/system/servus-scheduler.service"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now servus-scheduler.service"
echo "  sudo systemctl status servus-scheduler.service --no-pager"
