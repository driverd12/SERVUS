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
        if not dry_run:
            self.notifier.notify_start(
                self.wf.name,
                user_email,
                trigger_source=trigger_source,
                request_id=request_id,
            )

        for index, step in enumerate(self.wf.steps, start=1):
            self.log.info(f"[{'DRY' if dry_run else 'RUN'}] {step.id}: {step.description} :: {step.action or 'manual'}")
            if not dry_run:
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
                    failures.append({"step_id": step.id, "reason": "missing-action"})
                    failed_steps += 1
                    if not dry_run:
                        self.notifier.notify_step_result(
                            self.wf.name,
                            user_email,
                            step.id,
                            index,
                            step_total,
                            "failed",
                            detail="Step is type 'action' but no action was defined.",
                            trigger_source=trigger_source,
                            request_id=request_id,
                        )
                    continue
                
                # Look up the function in our registry
                func = ACTIONS.get(step.action)
                if not func:
                    self.log.error(f"Action '{step.action}' not found in registry (Check servus/actions.py imports).")
                    failures.append({"step_id": step.id, "reason": "action-not-found"})
                    failed_steps += 1
                    if not dry_run:
                        self.notifier.notify_step_result(
                            self.wf.name,
                            user_email,
                            step.id,
                            index,
                            step_total,
                            "failed",
                            detail=f"Action '{step.action}' not found in registry.",
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
                        if not dry_run:
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
                        if not dry_run:
                            failures.append({"step_id": step.id, "reason": "action-returned-false"})
                            failed_steps += 1
                            self.notifier.notify_step_result(
                                self.wf.name,
                                user_email,
                                step.id,
                                index,
                                step_total,
                                "failed",
                                detail=action_detail or "Action returned a failure outcome.",
                                trigger_source=trigger_source,
                                request_id=request_id,
                            )
                            self.notifier.notify_failure(
                                self.wf.name,
                                user_email,
                                step.id,
                                action_detail or "Action returned failure",
                                trigger_source=trigger_source,
                                request_id=request_id,
                            )
                            # We continue for now, but in a strict mode we might break.

                except Exception as e:
                    failures.append({"step_id": step.id, "reason": str(e)})
                    self.log.error(f"   ❌ Exception: {str(e)}")
                    if not dry_run:
                        failed_steps += 1
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
                        self.notifier.notify_failure(
                            self.wf.name,
                            user_email,
                            step.id,
                            str(e),
                            trigger_source=trigger_source,
                            request_id=request_id,
                        )

        success = len(failures) == 0
        self.log.info(f"Workflow Complete. success={success}")
        summary = (
            f"steps_total={step_total}, steps_succeeded={successful_steps}, "
            f"steps_failed={failed_steps}"
        )
        if not dry_run:
             if success:
                 self.notifier.notify_success(
                     self.wf.name,
                     user_email,
                     summary=summary,
                     trigger_source=trigger_source,
                     request_id=request_id,
                 )
             else:
                 summary = "; ".join(f"{f['step_id']} ({f['reason']})" for f in failures[:3])
                 self.notifier.notify_failure(
                     self.wf.name,
                     user_email,
                     "workflow",
                     summary,
                     summary=f"steps_total={step_total}, steps_succeeded={successful_steps}, steps_failed={failed_steps}",
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
