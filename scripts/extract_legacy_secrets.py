#!/usr/bin/env python3
import re, sys, pathlib

if len(sys.argv) != 2:
    print("Usage: extract_legacy_secrets.py /path/to/provision_user.py", file=sys.stderr)
    sys.exit(2)

p = pathlib.Path(sys.argv[1]).read_text(errors="ignore")
def grab(name):
    m = re.search(rf"^{name}\s*=\s*'([^']*)'\s*$", p, re.M)
    return m.group(1) if m else ""

ad_host = grab("AD_HOST")
ad_user = grab("AD_USER")
ad_pass = grab("AD_PASS")
okta_domain = grab("OKTA_DOMAIN")
okta_token = grab("OKTA_TOKEN")

print(f"SERVUS_AD_HOST={ad_host}")
print(f"SERVUS_AD_USERNAME={ad_user}")
print(f"SERVUS_AD_PASSWORD={ad_pass}")
print(f"SERVUS_OKTA_DOMAIN={okta_domain}")
print(f"SERVUS_OKTA_TOKEN={okta_token}")
