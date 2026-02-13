#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${SERVUS_PYTHON_BIN:-$(command -v python3)}"

WORK_EMAIL=""
RIPPLING_WORKER_ID=""
FRESHSERVICE_TICKET_ID=""
REASON="Off-cycle onboarding"
REQUEST_ID=""
START_DATE=""
MODE="immediate"

usage() {
  cat <<'EOF'
Usage:
  scripts/offcycle_onboard.sh \
    --work-email <email> \
    --rippling-worker-id <worker-id> \
    --freshservice-ticket-id <ticket-id|INC-###|URL> \
    [--reason "<text>"] \
    [--request-id <id>] \
    [--start-date YYYY-MM-DD] \
    [--hold]

Defaults:
  - Immediate mode (READY + URGENT) is used unless --hold is provided.
  - Reason defaults to "Off-cycle onboarding".
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --work-email)
      WORK_EMAIL="${2:-}"
      shift 2
      ;;
    --rippling-worker-id)
      RIPPLING_WORKER_ID="${2:-}"
      shift 2
      ;;
    --freshservice-ticket-id)
      FRESHSERVICE_TICKET_ID="${2:-}"
      shift 2
      ;;
    --reason)
      REASON="${2:-}"
      shift 2
      ;;
    --request-id)
      REQUEST_ID="${2:-}"
      shift 2
      ;;
    --start-date)
      START_DATE="${2:-}"
      shift 2
      ;;
    --hold)
      MODE="hold"
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

if [[ -z "${WORK_EMAIL}" || -z "${RIPPLING_WORKER_ID}" || -z "${FRESHSERVICE_TICKET_ID}" ]]; then
  echo "Missing required args: --work-email, --rippling-worker-id, --freshservice-ticket-id" >&2
  usage
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python binary not executable: ${PYTHON_BIN}" >&2
  exit 1
fi

CMD=(
  "${PYTHON_BIN}"
  "${REPO_ROOT}/scripts/live_onboard_test.py"
  --work-email "${WORK_EMAIL}"
  --rippling-worker-id "${RIPPLING_WORKER_ID}"
  --freshservice-ticket-id "${FRESHSERVICE_TICKET_ID}"
  --reason "${REASON}"
)

if [[ -n "${REQUEST_ID}" ]]; then
  CMD+=(--request-id "${REQUEST_ID}")
fi

if [[ -n "${START_DATE}" ]]; then
  CMD+=(--start-date "${START_DATE}")
fi

if [[ "${MODE}" == "immediate" ]]; then
  CMD+=(--ready --urgent)
fi

echo "Running off-cycle onboarding helper (${MODE})..."
echo "Command: ${CMD[*]}"
"${CMD[@]}"
