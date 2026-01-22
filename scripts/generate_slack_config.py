import csv
import yaml
import os

# CONFIGURATION
CSV_PATH = "channels_T03K49RUF_20260122-122051_1.csv" # Ensure this matches your filename
OUTPUT_PATH = "servus/data/slack_channels.yaml"

# DEFINE YOUR MAPPING HERE
# Map your Department names (from Onboarding.md) to text found in Slack Channel Names
# Example: If dept is "Engineering", look for channels containing "eng-"
KEYWORD_MAP = {
    "engineering": "eng-",
    "sales": "sales-",
    "marketing": "marketing-",
    "people": "people-",
    "it": "it-",
    "finance": "finance-",
    "legal": "legal-"
}

# Channels everyone should be in
GLOBAL_KEYWORDS = ["announcements-global", "social-dogs", "boom-global"]

def main():
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: Could not find {CSV_PATH}")
        return

    data = {"global": [], "departments": {k: [] for k in KEYWORD_MAP.keys()}}
    
    print(f"Reading {CSV_PATH}...")
    
    with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Adjust these keys based on your actual CSV headers
            # Looking at standard Slack exports, usually 'name' and 'id'
            c_name = row.get('name', '').lower()
            c_id = row.get('id', '')

            if not c_id or not c_name: continue

            # 1. Check Global
            for g in GLOBAL_KEYWORDS:
                if g in c_name:
                    if c_id not in data["global"]:
                        data["global"].append(c_id)
                        print(f"  [Global] Found {c_name} ({c_id})")

            # 2. Check Departments
            for dept, keyword in KEYWORD_MAP.items():
                if keyword in c_name:
                    if c_id not in data["departments"][dept]:
                        data["departments"][dept].append(c_id)
                        # print(f"  [{dept}] Found {c_name}")

    # Write YAML
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)
    
    print(f"\n✅ Success! Generated {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
