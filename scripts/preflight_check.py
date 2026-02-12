import sys
import logging
import requests
import argparse
from servus.config import CONFIG
from servus.integrations.google_gam import run_gam
from servus.integrations.linear import LinearClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("preflight")

def check_google_groups():
    """Checks if critical Google groups exist."""
    required_groups = ["all-hands@boom.aero", "engineering-all@boom.aero"]
    results = []
    
    for group in required_groups:
        success, stdout, stderr = run_gam(["info", "group", group])
        if success:
            results.append((f"Google Group: {group}", "✅ Found"))
        else:
            # In preflight, we might not have GAM installed or configured, so handle that gracefully
            detail = stderr.strip() or "GAM command failed"
            results.append((f"Google Group: {group}", f"❌ Not Found ({detail})"))
            
    return results

def check_slack_scopes():
    """Checks Slack token validity."""
    token = CONFIG.get("SLACK_TOKEN")
    if not token:
        return [("Slack Token", "❌ Missing SLACK_TOKEN")]
        
    try:
        response = requests.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5
        )
        data = response.json()
        
        if data.get("ok"):
            user = data.get("user")
            team = data.get("team")
            return [("Slack Auth", f"✅ Authenticated as {user} ({team})")]
        else:
            return [("Slack Auth", f"❌ Failed: {data.get('error')}")]
            
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
    """Checks Brivo SQS Queue configuration."""
    queue_url = CONFIG.get("SQS_BADGE_QUEUE_URL")
    if not queue_url:
        return [("Brivo Queue", "❌ Missing SQS_BADGE_QUEUE_URL")]
        
    if queue_url.startswith("https://sqs.") and "amazonaws.com" in queue_url:
        return [("Brivo Queue", f"✅ Configured: {queue_url}")]
    else:
        return [("Brivo Queue", f"❌ Invalid URL format: {queue_url}")]

def main():
    parser = argparse.ArgumentParser(description="SERVUS Integration Preflight Check")
    parser.add_argument("--strict", action="store_true", help="Fail with non-zero exit code if any check fails")
    args = parser.parse_args()
    
    print("🚀 SERVUS Integration Preflight Check\n")
    print(f"{'Check':<40} | {'Status'}")
    print("-" * 90)
    
    # Run checks
    checks = [
        check_google_groups,
        check_slack_scopes,
        check_linear_connectivity,
        check_brivo_queue
    ]
    
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
