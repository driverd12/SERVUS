import re
import logging
import requests
import urllib.parse
from datetime import datetime, timedelta
from servus.config import CONFIG
from servus.models import UserProfile
# Import the new client
from servus.integrations.rippling import RipplingClient

logger = logging.getLogger("servus.freshservice")

def fetch_ticket_data(ticket_id):
    """
    Fetches ticket from Freshservice, parses body, and enriches with Rippling data.
    """
    domain = CONFIG.get("FRESHSERVICE_DOMAIN")
    api_key = CONFIG.get("FRESHSERVICE_API_KEY")
    
    if not domain or not api_key:
        logger.error("Freshservice config missing.")
        return None

    url = f"https://{domain}/api/v2/tickets/{ticket_id}"
    
    try:
        resp = requests.get(url, auth=(api_key, "X"))
        if resp.status_code != 200:
            logger.error(f"Freshservice API Error: {resp.status_code}")
            return None
            
        ticket = resp.json().get("ticket", {})
        description = ticket.get("description_text", "")
        
        # 1. Regex Parse (The "New Hire" Email format)
        # Matches: "employee - [Name] has been"
        name_match = re.search(r"employee - (.*?) has been", description)
        date_match = re.search(r"start date of: (.*?)\s*$", description, re.MULTILINE)
        
        if not name_match:
            logger.error("Could not parse Employee Name from ticket description.")
            return None
            
        full_name = name_match.group(1).strip()
        start_date = date_match.group(1).strip() if date_match else "Unknown"
        
        # Split Name
        parts = full_name.split(" ")
        first_name = parts[0]
        last_name = " ".join(parts[1:])
        
        # 2. Enrichment (The Circuit Breaker)
        # Use the shared RipplingClient
        rippling_client = RipplingClient()
        # Try to guess email from name
        guessed_email = f"{first_name}.{last_name}@boom.aero".lower()
        
        # Try finding by email
        rippling_profile = rippling_client.find_user_by_email(guessed_email)
        
        if rippling_profile:
            logger.info(f"✅ Found match in Rippling: {rippling_profile.email}")
            # Use the robust profile data
            return rippling_profile
        else:
            logger.warning(f"⚠️  Could not find {guessed_email} in Rippling. Falling back to Ticket Data.")
            # Fallback: Construct Profile from Ticket Data + Defaults
            return UserProfile(
                first_name=first_name,
                last_name=last_name,
                work_email=guessed_email,
                personal_email="pending@example.com",
                department="Engineering", # Default
                title="Unknown",
                employment_type="Full-Time", # Default
                start_date=start_date,
                location="US"
            )

    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {e}")
        return None

def scan_for_onboarding_tickets(minutes_lookback=60):
    """
    Scans Freshservice for recent tickets matching 'Employee Onboarding'.
    Returns a list of ticket IDs.
    """
    domain = CONFIG.get("FRESHSERVICE_DOMAIN")
    api_key = CONFIG.get("FRESHSERVICE_API_KEY")
    
    if not domain or not api_key: return []

    # Calculate time window
    # Freshservice API requires ISO format: YYYY-MM-DDTHH:MM:SSZ
    start_time = (datetime.utcnow() - timedelta(minutes=minutes_lookback)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Query: created_at > start_time AND subject/type contains 'Onboarding'
    # Note: Freshservice query syntax can be tricky. We'll fetch recent and filter.
    url = f"https://{domain}/api/v2/tickets?updated_since={start_time}&order_by=created_at&order_type=desc"
    
    logger.info(f"🔍 Freshservice: Scanning for tickets updated since {start_time}...")
    
    matches = []
    try:
        resp = requests.get(url, auth=(api_key, "X"))
        if resp.status_code == 200:
            tickets = resp.json().get("tickets", [])
            for t in tickets:
                subject = t.get("subject", "").lower()
                # Heuristic: Look for "Onboarding" or "New Hire"
                if "onboard" in subject or "new hire" in subject:
                    logger.info(f"   found candidate ticket: #{t['id']} - {t['subject']}")
                    matches.append(t['id'])
    except Exception as e:
        logger.error(f"❌ Freshservice Scan Error: {e}")
        
    return matches

def _fetch_rippling_data(first, last):
    """
    Deprecated: Use RipplingClient.find_user_by_email instead.
    """
    return {}
