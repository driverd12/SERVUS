import time
import logging
from .workflow import Workflow
from .state import StateManager
from .actions import ACTIONS
from .notifier import SlackNotifier

class Orchestrator:
    def __init__(self, wf: Workflow, context: dict, state: StateManager, logger: logging.Logger):
        self.wf = wf
        self.ctx = context
        self.state = state
        self.log = logger
        self.notifier = SlackNotifier()

    def run(self, dry_run=False):
        # 🛠️ FIX: Removed reference to self.wf.version
        self.log.info(f"Workflow: {self.wf.name} | dry_run={dry_run}")
        failures = []
        successful_steps = 0
        failed_steps = 0
        step_total = len(self.wf.steps)
        
        # Inject dry_run into context so actions can see it
        self.ctx['dry_run'] = dry_run
        user_email = self.ctx.get("user_profile").work_email if self.ctx.get("user_profile") else "Unknown"
        trigger_source = self.ctx.get("trigger_source")
        request_id = self.ctx.get("request_id")
        
        # Notify Start (Only if not dry run, to avoid spam during testing)
        if not dry_run and self.notifier.allow_start_notification():
            self.notifier.notify_start(
                self.wf.name,
                user_email,
                trigger_source=trigger_source,
                request_id=request_id,
            )

        for index, step in enumerate(self.wf.steps, start=1):
            self.log.info(f"[{'DRY' if dry_run else 'RUN'}] {step.id}: {step.description} :: {step.action or 'manual'}")
            if not dry_run and self.notifier.allow_step_notifications():
                self.notifier.notify_step_start(
                    self.wf.name,
                    user_email,
                    step.id,
                    step.description,
                    index,
                    step_total,
                    trigger_source=trigger_source,
                    request_id=request_id,
                )

            # 1. Handle Manual Steps
            if step.type == 'manual':
                # In dry run, we just log and skip
                if not dry_run:
                    input(f"   [MANUAL] Press Enter after completing: {step.description} > ")
                    self.notifier.notify_step_result(
                        self.wf.name,
                        user_email,
                        step.id,
                        index,
                        step_total,
                        "manual",
                        detail="Manual step acknowledged by operator.",
                        trigger_source=trigger_source,
                        request_id=request_id,
                    )
                    successful_steps += 1
                continue

            # 2. Handle Automated Actions
            if step.type == 'action':
                if not step.action:
                    self.log.error(f"Step {step.id} is type 'action' but has no action defined.")
                    failure_detail = "Step is type 'action' but no action was defined."
                    failures.append(
                        {"step_id": step.id, "reason": "missing-action", "detail": failure_detail}
                    )
                    failed_steps += 1
                    if not dry_run and self.notifier.allow_step_notifications():
                        self.notifier.notify_step_result(
                            self.wf.name,
                            user_email,
                            step.id,
                            index,
                            step_total,
                            "failed",
                            detail=failure_detail,
                            trigger_source=trigger_source,
                            request_id=request_id,
                        )
                    continue
                
                # Look up the function in our registry
                func = ACTIONS.get(step.action)
                if not func:
                    self.log.error(f"Action '{step.action}' not found in registry (Check servus/actions.py imports).")
                    failure_detail = f"Action '{step.action}' not found in registry."
                    failures.append(
                        {"step_id": step.id, "reason": "action-not-found", "detail": failure_detail}
                    )
                    failed_steps += 1
                    if not dry_run and self.notifier.allow_step_notifications():
                        self.notifier.notify_step_result(
                            self.wf.name,
                            user_email,
                            step.id,
                            index,
                            step_total,
                            "failed",
                            detail=failure_detail,
                            trigger_source=trigger_source,
                            request_id=request_id,
                        )
                    continue

                # Execute
                try:
                    # The action function handles dry_run internally if needed
                    result = func(self.ctx)
                    action_ok, action_detail = _normalize_action_result(result)

                    if action_ok:
                        self.log.info(f"   ✅ Success")
                        successful_steps += 1
                        if not dry_run and self.notifier.allow_step_notifications():
                            self.notifier.notify_step_result(
                                self.wf.name,
                                user_email,
                                step.id,
                                index,
                                step_total,
                                "success",
                                detail=action_detail,
                                trigger_source=trigger_source,
                                request_id=request_id,
                            )
                    else:
                        self.log.info("   ⚠️  Action returned failure")
                        failure_detail = action_detail or "Action returned a failure outcome."
                        failures.append(
                            {
                                "step_id": step.id,
                                "reason": "action-returned-false",
                                "detail": failure_detail,
                            }
                        )
                        if not dry_run:
                            failed_steps += 1
                            if self.notifier.allow_step_notifications():
                                self.notifier.notify_step_result(
                                    self.wf.name,
                                    user_email,
                                    step.id,
                                    index,
                                    step_total,
                                    "failed",
                                    detail=failure_detail,
                                    trigger_source=trigger_source,
                                    request_id=request_id,
                                )
                            # We continue for now, but in a strict mode we might break.

                except Exception as e:
                    failures.append({"step_id": step.id, "reason": str(e), "detail": str(e)})
                    self.log.error(f"   ❌ Exception: {str(e)}")
                    if not dry_run:
                        failed_steps += 1
                        if self.notifier.allow_step_notifications():
                            self.notifier.notify_step_result(
                                self.wf.name,
                                user_email,
                                step.id,
                                index,
                                step_total,
                                "failed",
                                detail=str(e),
                                trigger_source=trigger_source,
                                request_id=request_id,
                            )

        success = len(failures) == 0
        self.log.info(f"Workflow Complete. success={success}")
        if not dry_run:
            self.notifier.notify_run_summary(
                self.wf.name,
                user_email,
                success=success,
                step_total=step_total,
                step_succeeded=successful_steps,
                step_failed=failed_steps,
                failures=failures[:10],
                trigger_source=trigger_source,
                request_id=request_id,
            )

        return {
            "success": success,
            "failures": failures,
            "workflow": self.wf.name,
            "dry_run": dry_run,
        }


def _normalize_action_result(raw_result):
    """
    Normalize action return values into (ok: bool, detail: Optional[str]).
    Backward compatible with bool/None returns and supports structured dict outcomes.
    """
    detail = None

    if isinstance(raw_result, dict):
        if "detail" in raw_result:
            detail = str(raw_result.get("detail") or "").strip() or None
        if "ok" in raw_result:
            return bool(raw_result.get("ok")), detail
        if "success" in raw_result:
            return bool(raw_result.get("success")), detail
        status = str(raw_result.get("status") or "").strip().lower()
        if status in {"success", "ok", "done", "skipped"}:
            return True, detail or ("Skipped." if status == "skipped" else None)
        if status in {"failed", "error"}:
            return False, detail
        return bool(raw_result), detail

    # Historical behavior: only explicit False is treated as failure.
    if raw_result is False:
        return False, None
    return True, None
