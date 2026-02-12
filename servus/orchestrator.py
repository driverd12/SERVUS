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
        
        # Inject dry_run into context so actions can see it
        self.ctx['dry_run'] = dry_run
        
        # Notify Start (Only if not dry run, to avoid spam during testing)
        if not dry_run:
            user_email = self.ctx.get("user_profile").work_email if self.ctx.get("user_profile") else "Unknown"
            self.notifier.notify_start(self.wf.name, user_email)

        for step in self.wf.steps:
            self.log.info(f"[{'DRY' if dry_run else 'RUN'}] {step.id}: {step.description} :: {step.action or 'manual'}")

            # 1. Handle Manual Steps
            if step.type == 'manual':
                # In dry run, we just log and skip
                if not dry_run:
                    input(f"   [MANUAL] Press Enter after completing: {step.description} > ")
                continue

            # 2. Handle Automated Actions
            if step.type == 'action':
                if not step.action:
                    self.log.error(f"Step {step.id} is type 'action' but has no action defined.")
                    failures.append({"step_id": step.id, "reason": "missing-action"})
                    continue
                
                # Look up the function in our registry
                func = ACTIONS.get(step.action)
                if not func:
                    self.log.error(f"Action '{step.action}' not found in registry (Check servus/actions.py imports).")
                    failures.append({"step_id": step.id, "reason": "action-not-found"})
                    continue

                # Execute
                try:
                    # The action function handles dry_run internally if needed
                    result = func(self.ctx)
                    
                    if result:
                        self.log.info(f"   ✅ Success")
                    else:
                        # Some dry runs return 'None' or 'True', failure returns 'False'
                        status = "⚠️  Action returned False" if result is False else "✅ Dry Run / Done"
                        self.log.info(f"   {status}")
                        
                        # If a step explicitly returns False in LIVE mode, it's a failure.
                        if result is False and not dry_run:
                             failures.append({"step_id": step.id, "reason": "action-returned-false"})
                             user_email = self.ctx.get("user_profile").work_email if self.ctx.get("user_profile") else "Unknown"
                             self.notifier.notify_failure(self.wf.name, user_email, step.id, "Action returned False")
                             # We continue for now, but in a strict mode we might break.

                except Exception as e:
                    failures.append({"step_id": step.id, "reason": str(e)})
                    self.log.error(f"   ❌ Exception: {str(e)}")
                    if not dry_run:
                        user_email = self.ctx.get("user_profile").work_email if self.ctx.get("user_profile") else "Unknown"
                        self.notifier.notify_failure(self.wf.name, user_email, step.id, str(e))

        success = len(failures) == 0
        self.log.info(f"Workflow Complete. success={success}")
        if not dry_run:
             user_email = self.ctx.get("user_profile").work_email if self.ctx.get("user_profile") else "Unknown"
             if success:
                 self.notifier.notify_success(self.wf.name, user_email)
             else:
                 summary = "; ".join(f"{f['step_id']} ({f['reason']})" for f in failures[:3])
                 self.notifier.notify_failure(self.wf.name, user_email, "workflow", summary)

        return {
            "success": success,
            "failures": failures,
            "workflow": self.wf.name,
            "dry_run": dry_run,
        }
