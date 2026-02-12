import logging
import requests
import urllib.parse
from datetime import datetime, timedelta
from servus.config import CONFIG
from servus.models import UserProfile

logger = logging.getLogger("servus.rippling")

class RipplingClient:
    def __init__(self):
        self.token = CONFIG.get("RIPPLING_API_TOKEN")
        self.base_url = "https://rest.ripplingapis.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

    def get_new_hires(self, start_date=None):
        """
        Fetches workers with a specific start_date.
        If start_date is None, defaults to TODAY.
        """
        if not self.token:
            logger.error("❌ Rippling Token missing.")
            return []

        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"🔍 Rippling: Scanning for new hires starting {start_date}...")
        
        # Rippling API v1 doesn't support complex date filtering easily in one go,
        # so we fetch recent workers and filter client-side or use the 'start_date' filter if supported.
        # Based on docs, we can filter by updated_at, but let's try scanning recent adds.
        # A more robust way is to fetch all active and filter, but that's heavy.
        # Let's try the /workers endpoint with a limit and filter manually for safety, 
        # or use the filter param if we trust it.
        
        # NOTE: In audit_new_hires.py we saw that we had to scan.
        # Let's implement a scan of the last 100 workers to be safe.
        
        url = f"{self.base_url}/workers?limit=100" 
        new_hires = []
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                logger.error(f"❌ Rippling API Error: {resp.status_code}")
                return []
                
            data = resp.json()
            results = data.get("results", [])
            
            for w in results:
                if w.get("start_date") == start_date:
                    # Found one! Fetch full details.
                    profile = self._build_profile(w.get("id"))
                    if profile:
                        new_hires.append(profile)
                        
            return new_hires
            
        except Exception as e:
            logger.error(f"❌ Rippling Connection Error: {e}")
            return []

    def get_departures(self, end_date=None):
        """
        Fetches workers with a specific end_date (termination).
        """
        if not self.token: return []
        
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
            
        logger.info(f"🔍 Rippling: Scanning for departures on {end_date}...")
        
        # Similar scan logic
        url = f"{self.base_url}/workers?limit=100" 
        departures = []
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200: return []
            
            results = resp.json().get("results", [])
            for w in results:
                # Check for end_date
                if w.get("end_date") == end_date:
                    profile = self._build_profile(w.get("id"))
                    if profile:
                        departures.append(profile)
                        
            return departures
        except Exception as e:
            logger.error(f"❌ Rippling Error: {e}")
            return []

    def find_user_by_email(self, email):
        """
        Finds a user by work email and returns their profile.
        """
        if not self.token: return None

        target_email = (email or "").strip().lower()
        logger.info(f"🔍 Rippling: Looking up {target_email}...")

        try:
            # Strategy 1: direct API filter by work_email.
            query = urllib.parse.quote(f"work_email eq '{target_email}'")
            url = f"{self.base_url}/workers?filter={query}"
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    return self._build_profile(results[0].get("id"))
            else:
                logger.warning(
                    "⚠️ Rippling worker lookup (work_email filter) failed: status=%s detail=%s",
                    resp.status_code,
                    _response_detail(resp),
                )

            # Strategy 2: alternate filter key fallback.
            query_alt = urllib.parse.quote(f"email eq '{target_email}'")
            url_alt = f"{self.base_url}/workers?filter={query_alt}"
            resp_alt = requests.get(url_alt, headers=self.headers, timeout=10)
            if resp_alt.status_code == 200:
                results_alt = resp_alt.json().get("results", [])
                if results_alt:
                    return self._build_profile(results_alt[0].get("id"))
            else:
                logger.warning(
                    "⚠️ Rippling worker lookup (email filter) failed: status=%s detail=%s",
                    resp_alt.status_code,
                    _response_detail(resp_alt),
                )

            # Strategy 3: scan fallback for case/schema drift.
            scan_url = f"{self.base_url}/workers?limit=200"
            scan_resp = requests.get(scan_url, headers=self.headers, timeout=10)
            if scan_resp.status_code == 200:
                for worker in scan_resp.json().get("results", []):
                    worker_email = str(worker.get("work_email") or worker.get("email") or "").strip().lower()
                    if worker_email != target_email:
                        continue
                    profile = self._build_profile(worker.get("id"))
                    if profile and not profile.start_date:
                        # Preserve key fields seen in list payload if detail call is sparse.
                        profile.start_date = worker.get("start_date")
                    return profile
            else:
                logger.warning(
                    "⚠️ Rippling worker scan fallback failed: status=%s detail=%s",
                    scan_resp.status_code,
                    _response_detail(scan_resp),
                )
        except Exception as e:
            logger.error(f"❌ Rippling Lookup Error: {e}")
            
        return None


def _response_detail(response):
    try:
        payload = response.json()
        if isinstance(payload, dict):
            return payload.get("detail") or str(payload)
        return str(payload)
    except Exception:
        return (response.text or "").strip()[:300]

    def _build_profile(self, worker_id):
        """
        Fetches full worker details and maps to UserProfile.
        """
        url = f"{self.base_url}/workers/{worker_id}?expand=department,employment_type"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200: return None
            
            data = resp.json()
            
            # Safe Parsing
            dept = (data.get("department") or {}).get("name", "Unknown")
            emp_type_obj = data.get("employment_type")
            e_type = emp_type_obj.get("label") if isinstance(emp_type_obj, dict) else "Full-Time"

            title_value = data.get("title")
            if isinstance(title_value, dict):
                title = title_value.get("name", "Unknown")
            elif isinstance(title_value, str):
                title = title_value
            else:
                title = "Unknown"

            manager_email = None
            manager_value = data.get("manager") or data.get("manager_email")
            if isinstance(manager_value, dict):
                manager_email = (
                    manager_value.get("work_email")
                    or manager_value.get("email")
                    or manager_value.get("manager_email")
                )
            elif isinstance(manager_value, str):
                manager_email = manager_value

            personal_email = data.get("personal_email")
            location = data.get("location") or "US"
            
            return UserProfile(
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                work_email=data.get("work_email"),
                personal_email=personal_email,
                department=dept,
                title=title,
                manager_email=manager_email,
                employment_type=e_type,
                start_date=data.get("start_date"),
                location=location,
                preferred_first_name=data.get("preferred_first_name"),
                # Rippling doesn't always expose photo URL in API v1 easily, 
                # but we can try to map it if we find the field.
                profile_picture_url=data.get("photo") 
            )
        except Exception as e:
            logger.error(f"❌ Error building profile for {worker_id}: {e}")
            return None
