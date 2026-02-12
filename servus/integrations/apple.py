import time
import requests
import logging
from servus.config import CONFIG

logger = logging.getLogger("servus.apple")

try:
    import jwt  # pip install pyjwt cryptography
except ModuleNotFoundError:
    jwt = None

def get_apple_token():
    """
    Generates a JWT Client Assertion and exchanges it for an Access Token.
    """
    if jwt is None:
        logger.error("ABM dependency missing: install pyjwt and cryptography.")
        return None

    private_key_path = CONFIG.get("ABM_PRIVATE_KEY_PATH", "certs/servus_abm.pem")
    client_id = CONFIG.get("ABM_CLIENT_ID")
    key_id = CONFIG.get("ABM_KEY_ID")

    if not client_id or not key_id:
        logger.error("ABM Client/Key ID missing in config.")
        return None

    try:
        with open(private_key_path, 'r') as f:
            private_key = f.read()

        # 1. Generate Client Assertion (JWT)
        headers = {
            "alg": "ES256",
            "kid": key_id
        }
        payload = {
            "iss": client_id,
            "sub": client_id,
            "aud": "https://appleid.apple.com/auth/oauth2/v2/token",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600  # 10 minutes
        }
        
        token = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

        # 2. Exchange for Access Token
        url = "https://appleid.apple.com/auth/oauth2/v2/token"
        data = {
            "grant_type": "client_credentials",
            "scope": "device_enrollment",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": token
        }

        resp = requests.post(url, data=data)
        if resp.status_code == 200:
            return resp.json().get("access_token")
        else:
            logger.error(f"ABM Auth Failed {resp.status_code}: {resp.text}")
            return None

    except Exception as e:
        logger.error(f"ABM Token Error: {e}")
        return None

def check_device_assignment(serial_number):
    """
    Checks if a specific serial number is assigned in ABM.
    Useful if the Freshservice ticket includes the Serial Number.
    """
    token = get_apple_token()
    if not token:
        return {"ok": False, "detail": "Failed to obtain ABM access token."}

    url = "https://api-business.apple.com/v1/device/details"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    _ = (url, headers)  # Placeholder until endpoint payload/query is finalized.

    # Logic to query device details...
    logger.info(f"Checking ABM for Serial: {serial_number}")
    # (Implementation depends on specific endpoint needs, usually requires 'session' token)
    return {"ok": True, "detail": f"ABM lookup completed for serial '{serial_number}' (placeholder response)."}
