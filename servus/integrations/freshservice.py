import re
import logging
import requests
import urllib.parse
from servus.config import CONFIG
from servus.models import UserProfile

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
        rippling_data = _fetch_rippling_data(first_name, last_name)
        
        # 3. Construct Profile (Merge Ticket Data + Rippling Data)
        return UserProfile(
            first_name=first_name,
            last_name=last_name,
            work_email=rippling_data.get("email", f"{first_name}.{last_name}@boom.aero".lower()),
            personal_email="pending@example.com", # Placeholder
            department=rippling_data.get("department", "Engineering"), # Default to Eng if API fails
            title=rippling_data.get("title", "Unknown"),
            employment_type=rippling_data.get("employment_type", "Full-Time"),
            start_date=start_date,
            location="US"
        )

    except Exception as e:
        logger.error(f"Error processing ticket {ticket_id}: {e}")
        return None

def _fetch_rippling_data(first, last):
    """
    Tries to get details from Rippling. Returns defaults on failure (502/403).
    """
    token = CONFIG.get("RIPPLING_API_TOKEN")
    if not token:
        return {}

    logger.info(f"🔍 Asking Rippling about {first} {last}...")
    
    # Try Step 1: Get ID
    target_email = f"{first}.{last}@boom.aero".lower()
    query = urllib.parse.quote(f"work_email eq '{target_email}'")
    url = f"https://rest.ripplingapis.com/workers?filter={query}"
    
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=10) # 10s timeout to avoid hanging
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                worker_id = results[0].get("id")
                # Step 2: Get Details
                return _fetch_worker_details(worker_id, headers)
            else:
                logger.warning("Rippling: User not found.")
        else:
            logger.warning(f"Rippling API failed ({resp.status_code}). Using defaults.")
            
    except Exception as e:
        logger.warning(f"Rippling Connection Error: {e}")
        
    return {}

def _fetch_worker_details(worker_id, headers):
    url = f"https://rest.ripplingapis.com/workers/{worker_id}?expand=department,employment_type"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            # Safe Parsing
            dept = (data.get("department") or {}).get("name", "Engineering")
            
            emp_type_obj = data.get("employment_type")
            if isinstance(emp_type_obj, dict):
                e_type = emp_type_obj.get("label") or "Full-Time"
            else:
                e_type = "Full-Time"

            return {
                "email": data.get("work_email"),
                "department": dept,
                "title": (data.get("title") or {}).get("name"),
                "employment_type": e_type
            }
    except Exception:
        pass
    return {}
