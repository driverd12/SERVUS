# SERVUS Operator Runbook Card

## 0) Open Repo + Env

```bash
cd /Users/dan.driver/Cursor_projects/python/SERVUS
source .venv/bin/activate
```

## 1) Preflight (Required at Shift Start)

```bash
python3 scripts/preflight_check.py --strict
```

## 2) Start Headless Scheduler

```bash
python3 scripts/scheduler.py
```

## 3) Queue Off-Cycle Onboarding (Fast Path)

```bash
scripts/offcycle_onboard.sh \
  --work-email "<user@boom.aero>" \
  --rippling-worker-id "<rippling-worker-id>" \
  --freshservice-ticket-id "<ticket-id-or-INC-###>" \
  --reason "Off-cycle onboarding"
```

## 4) Queue but HOLD (Needs Approval Later)

```bash
scripts/offcycle_onboard.sh \
  --work-email "<user@boom.aero>" \
  --rippling-worker-id "<rippling-worker-id>" \
  --freshservice-ticket-id "<ticket-id-or-INC-###>" \
  --reason "Off-cycle onboarding" \
  --hold
```

## 5) Approve HOLD Row to READY

```bash
python3 scripts/live_onboard_test.py \
  --request-id "<REQ-...>" \
  --work-email "<user@boom.aero>" \
  --rippling-worker-id "<rippling-worker-id>" \
  --freshservice-ticket-id "<ticket-id-or-INC-###>" \
  --allow-update \
  --ready
```

## 6) Watch Progress

```bash
tail -f servus_scheduler.log
```

```bash
tail -f servus_scheduler.log | rg -i "<user@boom.aero>"
```

## 7) Retry Failed Manual Request

```bash
python3 scripts/live_onboard_test.py \
  --request-id "<REQ-...>" \
  --work-email "<user@boom.aero>" \
  --rippling-worker-id "<rippling-worker-id>" \
  --freshservice-ticket-id "<ticket-id-or-INC-###>" \
  --reason "Retry after remediation" \
  --allow-update \
  --ready \
  --urgent
```

## 8) Stop Scheduler

```bash
pkill -f "python3 scripts/scheduler.py"
```
