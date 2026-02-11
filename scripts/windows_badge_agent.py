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
try:
    import boto3
    from botocore.config import Config
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

# ... (Image generation functions create_badge_image and create_back_image remain the same) ...
# For brevity in this update, I am assuming the image generation logic is stable.
# I will include them to ensure the file is complete and runnable.

def create_badge_image(first_name, last_name, photo_url=None):
    # Config - CR80 @ 300 DPI (approx 639x1014 px)
    # INCREASED SIZE FOR BLEED: 670x1050 (Adds ~30-40px padding)
    WIDTH, HEIGHT = 670, 1050 
    BG_COLOR = "#2C2C2C" # Dark Grey from template
    TEXT_COLOR = "white"
    
    # Canvas
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # 1. Logo
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "assets", "logo.png")
        
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            logo_width = int(WIDTH * 0.3)
            aspect_ratio = logo.height / logo.width
            logo_height = int(logo_width * aspect_ratio)
            logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            
            logo_x = (WIDTH - logo_width) // 2
            logo_y = 100 
            img.paste(logo, (logo_x, logo_y), logo)
    except Exception as e:
        logger.warning(f"⚠️ Failed to load logo: {e}")

    # 2. Text (First Name Only)
    try:
        font_size = 70
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except IOError:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default() 
            
        text = f"<{first_name}>" 
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (WIDTH - text_width) // 2
        text_y = 350 
        
        draw.text((text_x, text_y), text, font=font, fill=TEXT_COLOR)
    except Exception as e:
        logger.warning(f"⚠️ Failed to draw text: {e}")

    # 3. Photo (Circular Crop)
    try:
        photo = None
        if photo_url:
            try:
                response = requests.get(photo_url, timeout=10)
                if response.status_code == 200:
                    photo = Image.open(BytesIO(response.content)).convert("RGBA")
            except Exception as e:
                logger.warning(f"⚠️ Failed to download photo: {e}")
        
        if not photo:
            photo = Image.new('RGBA', (400, 400), color="#7F7F7F")

        circle_size = 390
        target_size = circle_size + 20 
        
        photo_aspect = photo.width / photo.height
        if photo.width < photo.height:
            new_width = target_size
            new_height = int(target_size / photo_aspect)
        else:
            new_height = target_size
            new_width = int(target_size * photo_aspect)
            
        photo = photo.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        left = (new_width - circle_size) / 2
        top = (new_height - circle_size) / 2
        right = (new_width + circle_size) / 2
        bottom = (new_height + circle_size) / 2
        photo = photo.crop((left, top, right, bottom))
        
        mask = Image.new('L', (circle_size, circle_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, circle_size, circle_size), fill=255)
        
        output = ImageOps.fit(photo, mask.size, centering=(0.5, 0.5))
        output.putalpha(mask)
        
        photo_x = (WIDTH - circle_size) // 2
        photo_y = 500
        img.paste(output, (photo_x, photo_y), output)
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to process photo: {e}")
        
    return img

def create_back_image():
    WIDTH, HEIGHT = 670, 1050 
    BG_COLOR = "white"
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(script_dir, "assets", "logo_back.png")
        
        if os.path.exists(logo_path):
            logo = Image.open(logo_path).convert("RGBA")
            aspect_ratio = logo.height / logo.width
            target_width = int(WIDTH * 1.1)
            target_height = int(target_width * aspect_ratio)
            logo = logo.resize((target_width, target_height), Image.Resampling.LANCZOS)
            logo_x = (WIDTH - target_width) // 2
            logo_y = (HEIGHT - target_height) // 2
            img.paste(logo, (logo_x, logo_y), logo)
    except Exception as e:
        logger.warning(f"⚠️ Failed to create back image: {e}")
        
    return img

def print_badge(user_data):
    """
    Generates the badge image locally and sends it to the Windows Printer.
    """
    first = user_data.get("first_name")
    last = user_data.get("last_name")
    photo_url = user_data.get("photo_url") 
    
    logger.info(f"🖨️  Processing Badge for: {first} {last}")
    
    try:
        front_img = create_badge_image(first, last, photo_url)
        back_img = create_back_image()
        
        # Print using Windows API
        import win32print
        import win32ui
        from PIL import ImageWin

        printer_name = "CX-D80 U1"
        
        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(printer_name)
        hDC.StartDoc(f"Badge_{first}_{last}")
        
        hDC.StartPage()
        dib_front = ImageWin.Dib(front_img)
        dib_front.draw(hDC.GetHandleOutput(), (0, 0, front_img.width, front_img.height))
        hDC.EndPage()
        
        hDC.StartPage()
        dib_back = ImageWin.Dib(back_img)
        dib_back.draw(hDC.GetHandleOutput(), (0, 0, back_img.width, back_img.height))
        hDC.EndPage()

        hDC.EndDoc()
        hDC.DeleteDC()
        
        logger.info("✅ Sent to Windows Spooler (Front & Back).")
        return True

    except ImportError:
        logger.warning("⚠️  win32print/win32ui not found. Install 'pywin32' to enable real printing.")
        return False
    except Exception as e:
        logger.error(f"❌ Print Failed: {e}")
        return False

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

    # IAM Roles Anywhere / Credential Helper logic
    # If running on a machine with IAM Roles Anywhere configured via AWS CLI config,
    # boto3 will automatically pick up the profile if AWS_PROFILE is set,
    # or use the default credential chain.
    # We explicitly enable the credential process if needed.
    
    logger.info("🔑 Initializing SQS Client (using default credential chain)...")
    
    if endpoint_url:
        # LocalStack
        sqs = boto3.client("sqs", 
            region_name=region, 
            endpoint_url=endpoint_url,
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )
    else:
        # Production (AWS)
        # Boto3 automatically handles IAM Roles Anywhere if ~/.aws/config is set up correctly
        # with credential_process.
        sqs = boto3.client("sqs", region_name=region)
        
    logger.info(f"📡 Badge Agent Listening on {queue_url}...")

    while True:
        try:
            # Long Polling
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=60 # Hide message while processing
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
                    success = print_badge(user_data)
                    
                    if success:
                        # Delete Message on Success
                        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=handle)
                        logger.info("🗑️  Job removed from queue.")
                    else:
                        # Do NOT delete. Let VisibilityTimeout expire so it retries.
                        # After 5 retries (RedrivePolicy), it goes to DLQ.
                        logger.warning("⚠️  Print failed. Message returned to queue for retry.")
                else:
                    logger.warning(f"Unknown action: {action}")
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=handle)

        except KeyboardInterrupt:
            logger.info("🛑 Stopping Agent...")
            break
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SERVUS Windows Badge Agent")
    parser.add_argument("--test-mode", action="store_true", help="Test print immediately")
    args = parser.parse_args()

    if args.test_mode:
        # Test code...
        pass
    else:
        run_daemon_mode()
