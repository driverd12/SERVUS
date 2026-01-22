from __future__ import annotations
import time
from typing import Any
from tenacity import retry, stop_after_attempt, wait_fixed

from .workflow import Workflow
from .state import RunState, StepResult, utc_now
from .actions import ACTIONS

class Orchestrator:
    def __init__(self, wf: Workflow, ctx: dict[str, Any], state: RunState, logger):
        self.wf = wf
        self.ctx = ctx
        self.state = state
        self.log = logger

    def _deps_ok(self, step) -> bool:
        for dep in step.requires:
            st = self.state.get_status(dep)
            if st not in ("OK","MANUAL","SKIPPED"):
                return False
        return True

    def run(self, dry_run: bool = False) -> None:
        self.log.info(f"Workflow: {self.wf.name} v{self.wf.version} | dry_run={dry_run}")
        for step in self.wf.steps:
            if self.state.get_status(step.id) == "OK":
                self.log.info(f"[SKIP] {step.id} already OK")
                continue

            if not self._deps_ok(step):
                raise RuntimeError(f"Dependencies not satisfied for step {step.id}")

            if step.mode.upper() == "MANUAL":
                self.log.info(f"[MANUAL] {step.name}")
                self.state.set(step.id, StepResult(status="MANUAL", started_at=utc_now(), finished_at=utc_now(), detail={"note": step.name}))
                continue

            fn = ACTIONS.get(step.action)
            if not fn:
                raise RuntimeError(f"Unknown action: {step.action}")

            started = utc_now()
            self.state.set(step.id, StepResult(status="RUNNING", started_at=started))
            self.log.info(f"[RUN] {step.id}: {step.name} :: {step.action}")

            if dry_run:
                self.state.set(step.id, StepResult(status="SKIPPED", started_at=started, finished_at=utc_now(), detail={"dry_run": True}))
                self.log.info(f"[DRY] skipped execution for {step.id}")
                continue

            # execute with simple retry loop
            last_err = None
            for attempt in range(step.retries + 1):
                try:
                    out = fn(self.ctx)
                    self.log.info(f"[OK] {step.id} executed")
                    # verify previous step if configured
                    if step.verify:
                        vfn = ACTIONS.get(step.verify)
                        if not vfn:
                            raise RuntimeError(f"Unknown verify action: {step.verify}")
                        vout = vfn(self.ctx)
                        self.log.info(f"[VERIFIED] {step.id}")
                        out = {"action": out, "verify": vout}
                    self.state.set(step.id, StepResult(status="OK", started_at=started, finished_at=utc_now(), detail=out))
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    self.log.error(f"[ERR] {step.id} attempt {attempt+1}/{step.retries+1}: {e}")
                    if attempt < step.retries:
                        time.sleep(step.retry_wait_seconds)

            if last_err:
                self.state.set(step.id, StepResult(status="FAILED", started_at=started, finished_at=utc_now(), detail={"error": str(last_err)}))
                raise last_err
