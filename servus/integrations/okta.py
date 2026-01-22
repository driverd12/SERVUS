from __future__ import annotations
from typing import Any
import time
import requests

DEFAULT_APP_IDS = {
    "AD_IMPORT": "0oacrzpehXApFBO95696",   # Active Directory Agent
    "GOOGLE":    "0oaiwzuzxPQydMdDa696",
    "SLACK":     "0oamjkpyxyj0o4msT697",
    "ZOOM":      "0oa3jgqlgrxD6OHzP697",
    "RAMP":      "0oasj7qk7dVE19GJU697",
}

def _headers(ctx: dict[str, Any]) -> dict[str, str]:
    token = ctx["config"].okta.token
    return {"Authorization": f"SSWS {token}", "Accept": "application/json", "Content-Type": "application/json"}

def _base(ctx: dict[str, Any]) -> str:
    return f"https://{ctx['config'].okta.domain}"

def trigger_ad_import(ctx: dict[str, Any]) -> dict[str, Any]:
    cfg = ctx["config"].okta
    ad_id = cfg.dirintegration_ad_import or DEFAULT_APP_IDS["AD_IMPORT"]
    url = f"{_base(ctx)}/api/v1/apps/{ad_id}/users/import"
    r = requests.post(url, headers=_headers(ctx))
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Okta AD import failed: {r.status_code} {r.text[:200]}")
    return {"triggered": True, "status": r.status_code}

def find_user(ctx: dict[str, Any]) -> dict[str, Any]:
    email = str(ctx["profile"].work_email)
    url = f"{_base(ctx)}/api/v1/users"
    r = requests.get(url, headers=_headers(ctx), params={"q": email})
    if r.status_code != 200:
        raise RuntimeError(f"Okta search failed: {r.status_code} {r.text[:200]}")
    users = r.json()
    if not users:
        raise RuntimeError("Okta user not found yet")
    u = users[0]
    ctx["okta_user_id"] = u["id"]
    return {"found": True, "user_id": u["id"], "status": u.get("status")}

def assign_apps(ctx: dict[str, Any]) -> dict[str, Any]:
    p = ctx["profile"]
    cfg = ctx["config"].okta

    user_id = ctx.get("okta_user_id")
    if not user_id:
        # attempt lookup
        find_user(ctx)
        user_id = ctx.get("okta_user_id")

    app_ids = {
        "GOOGLE": cfg.app_google or DEFAULT_APP_IDS["GOOGLE"],
        "SLACK": cfg.app_slack or DEFAULT_APP_IDS["SLACK"],
        "ZOOM": cfg.app_zoom or DEFAULT_APP_IDS["ZOOM"],
        "RAMP": cfg.app_ramp or DEFAULT_APP_IDS["RAMP"],
    }

    apps = ["GOOGLE", "SLACK"]
    if str(p.worker_type) == "FTE":
        apps += ["ZOOM", "RAMP"]

    results = []
    for a in apps:
        url = f"{_base(ctx)}/api/v1/apps/{app_ids[a]}/users"
        payload = {"id": user_id, "scope": "USER", "credentials": {"userName": str(p.work_email)}}
        r = requests.post(url, headers=_headers(ctx), json=payload)
        if r.status_code in (200, 201):
            results.append(a)
            continue
        if r.status_code == 400:
            # often means already assigned
            results.append(a)
            continue
        raise RuntimeError(f"Assign {a} failed: {r.status_code} {r.text[:200]}")
    return {"assigned": results}

def deactivate_user(ctx: dict[str, Any]) -> dict[str, Any]:
    # Deactivate Okta user; downstream SCIM expected
    user_id = ctx.get("okta_user_id")
    if not user_id:
        find_user(ctx)
        user_id = ctx.get("okta_user_id")
    url = f"{_base(ctx)}/api/v1/users/{user_id}/lifecycle/deactivate"
    r = requests.post(url, headers=_headers(ctx))
    if r.status_code not in (200, 202):
        raise RuntimeError(f"Deactivate failed: {r.status_code} {r.text[:200]}")
    return {"deactivated": True}
