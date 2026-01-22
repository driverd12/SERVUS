from __future__ import annotations
from dataclasses import dataclass
import yaml

@dataclass
class Step:
    id: str
    name: str
    action: str
    requires: list[str]
    verify: str | None = None
    retries: int = 0
    retry_wait_seconds: int = 5
    mode: str = "AUTO"  # AUTO|MANUAL

@dataclass
class Workflow:
    name: str
    version: str
    steps: list[Step]

def load_workflow(path: str) -> Workflow:
    with open(path, "r", encoding="utf-8") as f:
        obj = yaml.safe_load(f)
    steps = []
    for s in obj.get("steps", []):
        steps.append(Step(
            id=s["id"],
            name=s.get("name", s["id"]),
            action=s.get("action", "builtin.noop"),
            requires=s.get("requires", []),
            verify=s.get("verify"),
            retries=int(s.get("retries", 0)),
            retry_wait_seconds=int(s.get("retry_wait_seconds", 5)),
            mode=s.get("mode", "AUTO"),
        ))
    return Workflow(name=obj.get("name","SERVUS Workflow"), version=str(obj.get("version","1")), steps=steps)
