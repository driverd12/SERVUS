import re

TICKET_BODY = """
( https://rippling.com )

A new employee - Mark Loiseau has been added to Rippling with a start date of: 2/2/26

© 2026 Rippling.com
430 California St, 11th Floor, SF, CA 94104
"""

def parse_text(text):
    print("--- PARSING START ---")
    
    # 1. Regex to find the Name
    # Look for text between "employee - " and " has been"
    name_match = re.search(r"employee - (.*?) has been", text)
    
    # 2. Regex to find the Date
    # Look for text after "start date of: " until the end of the line
    date_match = re.search(r"start date of: (.*?)\s*$", text, re.MULTILINE)

    if name_match:
        full_name = name_match.group(1).strip()
        print(f"✅ Found Name: [{full_name}]")
        
        # Split into First/Last for API lookup
        parts = full_name.split(" ")
        print(f"   -> First: {parts[0]}")
        print(f"   -> Last:  {' '.join(parts[1:])}")
    else:
        print("❌ Could not find name pattern.")

    if date_match:
        print(f"✅ Found Date: [{date_match.group(1).strip()}]")
    else:
        print("❌ Could not find date pattern.")

    print("--- PARSING END ---")

if __name__ == "__main__":
    parse_text(TICKET_BODY)
