import argparse
import time
import json
import logging
import sys
import os
import random

# Add project root to path to allow imports if running from scripts/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from servus.config import CONFIG
from servus.integrations.brivo import BrivoClient
try:
    import boto3
except ImportError:
    print("Error: boto3 is required. pip install boto3")
    sys.exit(1)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("badge_agent")

from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests
from io import BytesIO

def create_badge_image(first_name, last_name, photo_url=None):
    # Config - CR80 @ 300 DPI (approx 639x1014 px)
    WIDTH, HEIGHT = 639, 1014 
    BG_COLOR = "#2C2C2C" # Dark Grey from template
    TEXT_COLOR = "white"
    
    # Canvas
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # 1. Logo
    try:
        # Load logo from assets folder relative to script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "assets", "logo.png")
        
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            # Resize logo (approx 30% width)
            logo_width = int(WIDTH * 0.3)
            aspect_ratio = logo.height / logo.width
            logo_height = int(logo_width * aspect_ratio)
            logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            
            # Center horizontally, place near top (adjust Y as needed)
            logo_x = (WIDTH - logo_width) // 2
            logo_y = 100 
            img.paste(logo, (logo_x, logo_y), logo)
    except Exception as e:
        logger.warning(f"⚠️ Failed to load logo: {e}")

    # 2. Text (First Name Only)
    try:
        # Use a bold sans-serif font. Arial Bold is standard on Windows.
        font_size = 70
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except IOError:
            font = ImageFont.load_default() # Fallback
            
        text = f"<{first_name}>" # Using format from screenshot
        
        # Calculate text size to center it
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (WIDTH - text_width) // 2
        text_y = 350 # Below logo
        
        draw.text((text_x, text_y), text, font=font, fill=TEXT_COLOR)
    except Exception as e:
        logger.warning(f"⚠️ Failed to draw text: {e}")

    # 3. Photo (Circular Crop)
    try:
        photo = None
        if photo_url:
            response = requests.get(photo_url)
            if response.status_code == 200:
                photo = Image.open(BytesIO(response.content)).convert("RGBA")
        
        # Fallback placeholder if no photo
        if not photo:
            # Grey circle placeholder
            photo = Image.new('RGBA', (400, 400), color="#7F7F7F")

        # Resize photo to fit circle area
        circle_size = 450
        photo = photo.resize((circle_size, circle_size), Image.Resampling.LANCZOS)
        
        # Create circular mask
        mask = Image.new('L', (circle_size, circle_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, circle_size, circle_size), fill=255)
        
        # Apply mask
        output = ImageOps.fit(photo, mask.size, centering=(0.5, 0.5))
        output.putalpha(mask)
        
        # Center horizontally, place at bottom
        photo_x = (WIDTH - circle_size) // 2
        photo_y = 500
        img.paste(output, (photo_x, photo_y), output)
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to process photo: {e}")
        
    return img

def print_badge(user_data):
    """
    Generates the badge image locally and sends it to the Windows Printer.
    """
    first = user_data.get("first_name")
    last = user_data.get("last_name")
    email = user_data.get("email")
    photo_url = user_data.get("photo_url") # Ensure this is passed in payload
    
    logger.info(f"🖨️  Processing Badge for: {first} {last}")
    
    try:
        # 1. Generate Image
        badge_img = create_badge_image(first, last, photo_url)
        
        # Save temp file for debugging/printing
        temp_filename = f"badge_{first}_{last}.png"
        badge_img.save(temp_filename)
        logger.info(f"   Generated badge image: {temp_filename}")

        # 2. Print using Windows API
        import win32print
        import win32ui
        from PIL import ImageWin

        printer_name = "CX-D80 U1"
        
        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(printer_name)
        
        # Calculate scaling to fit page (CR80)
        # For simplicity, we assume the printer driver is set to CR80 paper size
        # and we just draw the image to fill the DC.
        
        hDC.StartDoc(f"Badge_{first}_{last}")
        hDC.StartPage()

        dib = ImageWin.Dib(badge_img)
        
        # Get printable area
        # horz_res = hDC.GetDeviceCaps(110) # HORZRES
        # vert_res = hDC.GetDeviceCaps(111) # VERTRES
        
        # Draw image (0,0 to width,height)
        dib.draw(hDC.GetHandleOutput(), (0, 0, badge_img.width, badge_img.height))

        hDC.EndPage()
        hDC.EndDoc()
        hDC.DeleteDC()
        
        logger.info("✅ Sent to Windows Spooler.")
        
        # Cleanup
        # os.remove(temp_filename) 

    except ImportError:
        logger.warning("⚠️  win32print/win32ui not found. Install 'pywin32' to enable real printing.")
    except Exception as e:
        logger.error(f"❌ Print Failed: {e}")

    time.sleep(2)
    logger.info("✅ JOB COMPLETE.")

def run_test_mode():
    """
    Bypasses SQS. Creates a random test user in Brivo, then prints.
    """
    logger.info("🧪 STARTING TEST MODE")
    
    # 1. Generate Dummy Data
    rand_id = random.randint(1000, 9999)
    test_user = {
        "first_name": "Test",
        "last_name": f"BadgeUser_{rand_id}",
        "email": f"test.badge.{rand_id}@boom.aero"
    }
    
    logger.info(f"   Generated Test User: {test_user['email']}")
    
    # 2. Create in Brivo
    client = BrivoClient()
    logger.info("   Connecting to Brivo...")
    if client.create_user(test_user["first_name"], test_user["last_name"], test_user["email"]):
        logger.info("   ✅ Brivo User Created.")
    else:
        logger.error("   ❌ Failed to create Brivo user. Aborting.")
        return

    # 3. Print
    print_badge(test_user)
    logger.info("🧪 TEST MODE COMPLETE")

def run_daemon_mode():
    """
    Polls SQS for print jobs.
    """
    queue_url = CONFIG.get("SQS_BADGE_QUEUE_URL")
    region = CONFIG.get("AWS_REGION", "us-east-1")
    endpoint_url = CONFIG.get("SQS_ENDPOINT_URL")
    
    if not queue_url:
        logger.error("❌ SQS_BADGE_QUEUE_URL not set in .env")
        return

    if endpoint_url:
        # LocalStack requires dummy creds to stop boto3 from searching for real ones
        sqs = boto3.client("sqs", 
            region_name=region, 
            endpoint_url=endpoint_url,
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )
    else:
        sqs = boto3.client("sqs", region_name=region)
        
    logger.info(f"📡 Badge Agent Listening on {queue_url}...")

    while True:
        try:
            # Long Polling
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20
            )

            messages = response.get("Messages", [])
            for msg in messages:
                body = json.loads(msg["Body"])
                handle = msg["ReceiptHandle"]
                
                action = body.get("action")
                if action == "print_badge":
                    user_data = body.get("user", {})
                    logger.info(f"📨 Received Print Job: {user_data.get('email')}")
                    
                    # Execute Print
                    print_badge(user_data)
                    
                    # Delete Message
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=handle)
                    logger.info("🗑️  Job removed from queue.")
                else:
                    logger.warning(f"Unknown action: {action}")

        except KeyboardInterrupt:
            logger.info("🛑 Stopping Agent...")
            break
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SERVUS Windows Badge Agent")
    parser.add_argument("--test-mode", action="store_true", help="Create a test user in Brivo and print immediately (Bypasses Queue)")
    args = parser.parse_args()

    if args.test_mode:
        run_test_mode()
    else:
        run_daemon_mode()
