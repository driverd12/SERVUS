from __future__ import annotations
import time
from typing import Any
from .models import UserProfile

def noop(ctx: dict[str, Any], **kwargs) -> dict[str, Any]:
    return {"ok": True}

def wait(ctx: dict[str, Any], seconds: int = 5, **kwargs) -> dict[str, Any]:
    time.sleep(seconds)
    return {"waited": seconds}

def manual(ctx: dict[str, Any], note: str = "", **kwargs) -> dict[str, Any]:
    return {"manual": True, "note": note}

def validate_profile(ctx: dict[str, Any], **kwargs) -> dict[str, Any]:
    p: UserProfile = ctx["profile"]
    if not p.first_name or not p.last_name or not p.work_email:
        raise ValueError("Profile missing required identity fields.")
    if p.is_service_account:
        # service accounts should be explicit and minimal
        if p.worker_type not in ("CON","SUP","FTE","INT","MRG"):
            raise ValueError("Invalid worker_type for service account.")
    return {"validated": True}
