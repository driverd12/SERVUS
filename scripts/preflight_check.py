#!/usr/bin/env python3

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

# Allow running as `python3 scripts/preflight_check.py` or by absolute path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from servus.config import CONFIG
from servus.integrations.google_gam import run_gam
from servus.integrations.linear import LinearClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("preflight")

REQUIRED_SLACK_SCOPES = {"users:read.email"}
SLACK_INVITE_SCOPE_OPTIONS = {"conversations:write", "channels:write", "groups:write"}
GOOGLE_GROUP_POLICY_FILE = REPO_ROOT / "servus" / "data" / "google_groups.yaml"
SLACK_CHANNELS_FILE = REPO_ROOT / "servus" / "data" / "slack_channels.yaml"


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _collect_strings(raw_value):
    values = []
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        if normalized:
            values.append(normalized)
        return values
    if isinstance(raw_value, list):
        for item in raw_value:
            values.extend(_collect_strings(item))
        return values
    if isinstance(raw_value, dict):
        for item in raw_value.values():
            values.extend(_collect_strings(item))
        return values
    return values


def _load_yaml(path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except Exception as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return {}


def _configured_google_groups():
    policy = _load_yaml(GOOGLE_GROUP_POLICY_FILE)
    groups = set()
    groups.update(_collect_strings(policy.get("global", {})))
    groups.update(_collect_strings(policy.get("departments", {})))
    return sorted(group for group in groups if group)


def _configured_slack_channel_targets():
    policy = _load_yaml(SLACK_CHANNELS_FILE)
    channels = set()
    channels.update(_collect_strings(policy.get("global", [])))
    channels.update(_collect_strings(policy.get("departments", {})))
    channels.update(_collect_strings(policy.get("employment_type", {})))
    return sorted(channel for channel in channels if channel)


def check_google_groups():
    """Checks if configured Google groups exist."""
    configured_groups = _configured_google_groups()
    if not configured_groups:
        return [("Google Groups", "✅ No Google group targets configured; check skipped.")]

    results = []

    for group in configured_groups:
        success, stdout, stderr = run_gam(["info", "group", group])
        if success:
            results.append((f"Google Group: {group}", "✅ Found"))
        else:
            # In preflight, we might not have GAM installed or configured, so handle that gracefully
            detail = stderr.strip() or "GAM command failed"
            results.append((f"Google Group: {group}", f"❌ Not Found ({detail})"))

    return results


def check_slack_scopes():
    """Checks Slack token validity and required scopes for onboarding channel adds."""
    configured_channels = _configured_slack_channel_targets()
    if not configured_channels:
        return [("Slack Channels", "✅ No Slack channel targets configured; scope check skipped.")]

    token = CONFIG.get("SLACK_TOKEN")
    if not token:
        return [("Slack Token", "❌ Missing SLACK_TOKEN")]

    try:
        response = requests.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        data = response.json()

        if not data.get("ok"):
            return [("Slack Auth", f"❌ Failed: {data.get('error')}")]

        scopes = _parse_scopes_header(response.headers.get("x-oauth-scopes", ""))
        if not scopes:
            return [
                (
                    "Slack Scopes",
                    "❌ Could not read token scopes from Slack response headers.",
                )
            ]

        missing_base = sorted(REQUIRED_SLACK_SCOPES - scopes)
        has_invite_scope = bool(scopes & SLACK_INVITE_SCOPE_OPTIONS)

        if missing_base or not has_invite_scope:
            issues = []
            if missing_base:
                issues.append(f"missing={missing_base}")
            if not has_invite_scope:
                issues.append(
                    "missing invite scope (need one of conversations:write/channels:write/groups:write)"
                )
            return [("Slack Scopes", f"❌ {', '.join(issues)}")]

        user = data.get("user")
        team = data.get("team")
        return [
            (
                "Slack Scopes",
                f"✅ Authenticated as {user} ({team}); required scopes present",
            )
        ]

    except Exception as e:
        return [("Slack Connectivity", f"❌ Error: {str(e)}")]


def check_linear_connectivity():
    """Checks Linear API connectivity."""
    client = LinearClient()
    if not client.api_key:
        return [("Linear Token", "❌ Missing LINEAR_API_KEY")]

    query = "{ viewer { id email } }"
    result = client._query(query)

    if result and "data" in result and "viewer" in result["data"]:
        viewer = result["data"]["viewer"]
        return [("Linear API", f"✅ Connected as {viewer.get('email')}")]
    else:
        # Check if result is None (API key missing handled above, but maybe connection error)
        if result is None:
            return [("Linear API", "❌ Connection Failed (Check logs)")]

        errors = result.get("errors") if result else "Unknown error"
        return [("Linear API", f"❌ Failed: {errors}")]


def check_brivo_queue():
    """Checks Brivo SQS Queue configuration and endpoint reachability."""
    queue_required = _as_bool(CONFIG.get("BRIVO_QUEUE_REQUIRED"), default=False)
    queue_url = CONFIG.get("SQS_BADGE_QUEUE_URL")
    if not queue_url:
        if queue_required:
            return [("Brivo Queue", "❌ Missing SQS_BADGE_QUEUE_URL")]
        return [("Brivo Queue", "⚠️ Missing SQS_BADGE_QUEUE_URL; manual badge fallback is active.")]

    parsed_queue = urlparse(queue_url)
    if parsed_queue.scheme not in {"http", "https"} or not parsed_queue.netloc:
        if queue_required:
            return [("Brivo Queue", f"❌ Invalid queue URL format: {queue_url}")]
        return [("Brivo Queue", f"⚠️ Invalid queue URL format: {queue_url}; manual badge fallback is active.")]

    endpoint_override = str(CONFIG.get("SQS_ENDPOINT_URL") or "").strip()
    if endpoint_override:
        probe_target = endpoint_override
    else:
        probe_target = f"{parsed_queue.scheme}://{parsed_queue.netloc}"

    parsed_probe = urlparse(probe_target)
    if parsed_probe.scheme not in {"http", "https"} or not parsed_probe.netloc:
        if queue_required:
            return [("Brivo Queue", f"❌ Invalid endpoint URL format: {probe_target}")]
        return [("Brivo Queue", f"⚠️ Invalid endpoint URL format: {probe_target}; manual badge fallback is active.")]

    try:
        # Any HTTP response indicates network reachability; auth errors (403/401) are acceptable here.
        response = requests.get(probe_target, timeout=5)
        return [
            ("Brivo Queue URL", f"✅ Configured: {queue_url}"),
            (
                "Brivo Queue Reachability",
                f"✅ Reachable endpoint={probe_target} (status={response.status_code})",
            ),
        ]
    except Exception as e:
        if queue_required:
            reachability = f"❌ Unreachable endpoint={probe_target}: {str(e)}"
        else:
            reachability = f"⚠️ Unreachable endpoint={probe_target}: {str(e)}; manual badge fallback is active."
        return [
            ("Brivo Queue URL", f"✅ Configured: {queue_url}"),
            ("Brivo Queue Reachability", reachability),
        ]


def _parse_scopes_header(raw_header):
    scopes = set()
    for value in str(raw_header or "").split(","):
        scope = value.strip()
        if scope:
            scopes.add(scope)
    return scopes


def main():
    parser = argparse.ArgumentParser(description="SERVUS Integration Preflight Check")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code if any check fails")
    args = parser.parse_args()

    print("🚀 SERVUS Integration Preflight Check\n")
    print(f"{'Check':<40} | {'Status'}")
    print("-" * 90)

    # Run checks
    checks = [check_google_groups, check_slack_scopes, check_linear_connectivity, check_brivo_queue]

    failure_count = 0

    for check in checks:
        try:
            results = check()
            for name, status in results:
                print(f"{name:<40} | {status}")
                if "❌" in status:
                    failure_count += 1
        except Exception as e:
            print(f"{check.__name__:<40} | ❌ Exception: {e}")
            failure_count += 1

    print("-" * 90)

    if failure_count > 0:
        print(f"\n⚠️  Found {failure_count} issues.")
        if args.strict:
            sys.exit(1)
    else:
        print("\n✅ All checks passed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
