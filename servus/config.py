import os
import logging
from dotenv import load_dotenv

# Load .env file immediately
load_dotenv()

# Define the global configuration dictionary
CONFIG = {
    # Infrastructure
    "AD_HOST": os.getenv("SERVUS_AD_HOST", "10.1.0.3"),
    "AD_USER": os.getenv("SERVUS_AD_USERNAME"),
    "AD_PASS": os.getenv("SERVUS_AD_PASSWORD"),
    
    # Okta
    "OKTA_DOMAIN": os.getenv("SERVUS_OKTA_DOMAIN", "boom.okta.com"),
    "OKTA_TOKEN": os.getenv("SERVUS_OKTA_TOKEN"),
    "OKTA_APP_AD": os.getenv("SERVUS_OKTA_DIRINTEGRATION_AD_IMPORT", "0oacrzpehXApFBO95696"),
    
    # Integrations
    "SLACK_TOKEN": os.getenv("SERVUS_SLACK_ADMIN_TOKEN"),
    "GAM_PATH": os.getenv("GAM_PATH", "/Users/dan.driver/bin/gam7/gam"),
    
    # Freshservice (The Missing Piece)
    "FRESHSERVICE_DOMAIN": os.getenv("SERVUS_FRESHSERVICE_DOMAIN"),
    "FRESHSERVICE_API_KEY": os.getenv("SERVUS_FRESHSERVICE_API_KEY"),
    
    # Rippling
    "RIPPLING_API_TOKEN": os.getenv("SERVUS_RIPPLING_API_TOKEN"),
    
    # AD Structure
    "AD_BASE_DN": os.getenv("AD_BASE_DN", "DC=boom,DC=local"),
    "AD_USERS_ROOT": os.getenv("AD_USERS_ROOT", "OU=Boom Users"),

    # Brivo Structure
    "BRIVO_API_KEY": os.getenv("SERVUS_BRIVO_API_KEY"),
    "BRIVO_USERNAME": os.getenv("SERVUS_BRIVO_USERNAME"),
    "BRIVO_PASSWORD": os.getenv("SERVUS_BRIVO_PASSWORD"),

    # AWS SQS (Badge Printing)
    "SQS_BADGE_QUEUE_URL": os.getenv("SERVUS_SQS_BADGE_QUEUE_URL"),
    "AWS_REGION": os.getenv("SERVUS_AWS_REGION", "us-east-1"),
    "SQS_ENDPOINT_URL": os.getenv("SERVUS_SQS_ENDPOINT_URL"),
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
