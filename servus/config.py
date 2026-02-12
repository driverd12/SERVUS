import os
import logging
import json
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load .env file immediately (Local Fallback)
load_dotenv()

logger = logging.getLogger("servus.config")


def _as_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

def fetch_aws_secrets():
    """
    Fetches secrets from AWS Secrets Manager.
    Returns a dict of secrets or empty dict if failed/not configured.
    """
    secret_name = os.getenv("SERVUS_AWS_SECRET_ID", "prod/servus/config")
    region_name = os.getenv("SERVUS_AWS_REGION", "us-east-1")
    
    # Check if we are likely in AWS (simple heuristic or env var)
    # or if the user explicitly wants to use AWS secrets
    if not os.getenv("SERVUS_USE_AWS_SECRETS"):
        return {}

    logger.info(f"🔐 Attempting to fetch secrets from AWS ({secret_name})...")
    
    try:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        
        if 'SecretString' in get_secret_value_response:
            return json.loads(get_secret_value_response['SecretString'])
    except ClientError as e:
        logger.warning(f"⚠️  Could not fetch AWS Secrets: {e}")
    except Exception as e:
        logger.warning(f"⚠️  AWS Secrets Error: {e}")
        
    return {}

def fetch_gam_oauth_to_shm():
    """
    Fetches GAM oauth2.txt from Secrets Manager and writes it to /dev/shm.
    Returns the path to the file.
    """
    secret_name = os.getenv("SERVUS_GAM_SECRET_ID", "prod/servus/gam_oauth")
    region_name = os.getenv("SERVUS_AWS_REGION", "us-east-1")
    
    if not os.getenv("SERVUS_USE_AWS_SECRETS"):
        return None

    logger.info(f"🔐 Fetching GAM OAuth token to memory...")
    
    try:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager', region_name=region_name)
        resp = client.get_secret_value(SecretId=secret_name)
        
        if 'SecretString' in resp:
            # Write to /dev/shm (Linux shared memory)
            # This ensures secrets are never written to disk
            shm_path = "/dev/shm/oauth2.txt"
            with open(shm_path, "w") as f:
                f.write(resp['SecretString'])
            return shm_path
            
    except Exception as e:
        logger.warning(f"⚠️  Could not fetch GAM OAuth: {e}")
    
    return None

# 1. Load Local Env
env_config = dict(os.environ)

# 2. Overlay AWS Secrets (if enabled)
aws_secrets = fetch_aws_secrets()
env_config.update(aws_secrets)

# 3. Handle GAM Token (Production Mode)
if os.getenv("SERVUS_USE_AWS_SECRETS"):
    shm_token_path = fetch_gam_oauth_to_shm()
    if shm_token_path:
        # GAM expects oauth2.txt in the same dir as client_secrets.json usually,
        # or we can try to point it via env var if supported, or symlink.
        # GAM_OAUTH2_TXT is supported by some versions, or we just rely on GAM_PATH
        # pointing to a dir where we symlinked it.
        pass

# 4. Build Global CONFIG
CONFIG = {
    # Infrastructure
    "AD_HOST": env_config.get("SERVUS_AD_HOST", "10.1.0.3"),
    "AD_USER": env_config.get("SERVUS_AD_USERNAME"),
    "AD_PASS": env_config.get("SERVUS_AD_PASSWORD"),
    
    # Okta
    "OKTA_DOMAIN": env_config.get("SERVUS_OKTA_DOMAIN", "boom.okta.com"),
    "OKTA_TOKEN": env_config.get("SERVUS_OKTA_TOKEN"),
    "OKTA_APP_AD": env_config.get("SERVUS_OKTA_DIRINTEGRATION_AD_IMPORT", "0oacrzpehXApFBO95696"),
    "OKTA_GROUP_CONTRACTORS": env_config.get("SERVUS_OKTA_GROUP_CONTRACTORS"),
    "OKTA_APP_SLACK": env_config.get("SERVUS_OKTA_APP_SLACK"),
    
    # Integrations
    "SLACK_TOKEN": env_config.get("SERVUS_SLACK_ADMIN_TOKEN"),
    "GAM_PATH": env_config.get("GAM_PATH", "/Users/dan.driver/bin/gam7/gam"),
    
    # Freshservice
    "FRESHSERVICE_DOMAIN": env_config.get("SERVUS_FRESHSERVICE_DOMAIN"),
    "FRESHSERVICE_API_KEY": env_config.get("SERVUS_FRESHSERVICE_API_KEY"),
    
    # Rippling
    "RIPPLING_API_TOKEN": env_config.get("SERVUS_RIPPLING_API_TOKEN"),
    
    # AD Structure
    "AD_BASE_DN": env_config.get("AD_BASE_DN", "DC=boom,DC=local"),
    "AD_USERS_ROOT": env_config.get("AD_USERS_ROOT", "OU=Boom Users"),

    # Brivo Structure
    "BRIVO_API_KEY": env_config.get("SERVUS_BRIVO_API_KEY"),
    "BRIVO_USERNAME": env_config.get("SERVUS_BRIVO_USERNAME"),
    "BRIVO_PASSWORD": env_config.get("SERVUS_BRIVO_PASSWORD"),

    # AWS SQS (Badge Printing)
    "SQS_BADGE_QUEUE_URL": env_config.get("SERVUS_SQS_BADGE_QUEUE_URL"),
    "AWS_REGION": env_config.get("SERVUS_AWS_REGION", "us-east-1"),
    "SQS_ENDPOINT_URL": env_config.get("SERVUS_SQS_ENDPOINT_URL"),
    
    # Offboarding
    "OFFBOARDING_ADMIN_EMAIL": env_config.get("SERVUS_OFFBOARDING_ADMIN", "admin-wolverine@boom.aero"),

    # Notifications
    "SLACK_WEBHOOK_URL": env_config.get("SERVUS_SLACK_WEBHOOK_URL"),
    "SLACK_NOTIFICATION_MODE": env_config.get("SERVUS_SLACK_NOTIFICATION_MODE", "summary"),

    # New SaaS
    "LINEAR_API_KEY": env_config.get("SERVUS_LINEAR_API_KEY"),
    "ZOOM_ACCOUNT_ID": env_config.get("SERVUS_ZOOM_ACCOUNT_ID"),
    "ZOOM_CLIENT_ID": env_config.get("SERVUS_ZOOM_CLIENT_ID"),
    "ZOOM_CLIENT_SECRET": env_config.get("SERVUS_ZOOM_CLIENT_SECRET"),
    "RAMP_API_KEY": env_config.get("SERVUS_RAMP_API_KEY"),

    # Scheduler / Manual Override Queue
    "ONBOARDING_OVERRIDE_CSV": env_config.get(
        "SERVUS_ONBOARDING_OVERRIDE_CSV", "servus_state/manual_onboarding_overrides.csv"
    ),
    "SCHEDULER_STATE_FILE": env_config.get(
        "SERVUS_SCHEDULER_STATE_FILE", "servus_state/scheduler_state.json"
    ),
    "MANUAL_OVERRIDE_ENFORCE_START_DATE": _as_bool(
        env_config.get("SERVUS_MANUAL_OVERRIDE_ENFORCE_START_DATE"),
        default=True,
    ),
    "MANUAL_OVERRIDE_ALLOW_EARLY_GLOBAL": _as_bool(
        env_config.get("SERVUS_MANUAL_OVERRIDE_ALLOW_EARLY_GLOBAL"),
        default=False,
    ),
    "PREFLIGHT_STRICT": _as_bool(
        env_config.get("SERVUS_PREFLIGHT_STRICT"),
        default=False,
    ),
}

def load_config():
    """
    Validation helper to ensure critical keys exist.
    """
    critical_keys = ["AD_USER", "AD_PASS", "OKTA_TOKEN"]
    missing = [k for k in critical_keys if not CONFIG.get(k)]
    
    if missing:
        logging.warning(f"⚠️  Missing critical config keys. Check mapping in config.py vs .env: {', '.join(missing)}")
    
    return CONFIG
