import yaml
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("servus.workflow")

class WorkflowStep(BaseModel):
    id: str
    description: str
    type: str  # "action", "manual", "trigger"
    action: Optional[str] = None
    verify: Optional[str] = "manual"  # "auto", "manual", "none"
    params: Dict[str, Any] = Field(default_factory=dict)

class Workflow(BaseModel):
    name: str
    description: str
    steps: List[WorkflowStep]

def load_workflow(yaml_path: str) -> Workflow:
    """
    Parses the YAML workflow file into a strict Pydantic model.
    Handles 'name' vs 'id' mismatch automatically.
    """
    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f)

    steps = []
    for s in raw.get("steps", []):
        # 🛠️ FIX: If 'id' is missing, use 'name' as the ID
        step_id = s.get("id") or s.get("name")
        
        if not step_id:
            logger.error(f"Step missing 'id' or 'name': {s}")
            continue

        # Ensure we pass 'id' to the model even if the YAML had 'name'
        s_data = s.copy()
        s_data["id"] = step_id
        
        # 'name' is not a field in WorkflowStep, so we remove it to avoid validation error
        if "name" in s_data:
            del s_data["name"]
        
        steps.append(WorkflowStep(**s_data))

    return Workflow(
        name=raw["name"],
        description=raw["description"],
        steps=steps
    )
