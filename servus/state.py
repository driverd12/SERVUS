from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

@dataclass
class StepResult:
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    detail: dict[str, Any] | None = None

class RunState:
    def __init__(self, run_id: str):
        self.run_id = run_id
        os.makedirs("servus_state", exist_ok=True)
        self.path = os.path.join("servus_state", f"{run_id}.json")
        self.data: dict[str, Any] = {"run_id": run_id, "steps": {}}
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def get_status(self, step_id: str) -> str | None:
        return self.data.get("steps", {}).get(step_id, {}).get("status")

    def set(self, step_id: str, result: StepResult) -> None:
        self.data.setdefault("steps", {})[step_id] = asdict(result)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
