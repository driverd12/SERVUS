import boto3
import json
import logging
from servus.config import CONFIG

logger = logging.getLogger("servus.badge_queue")

def get_sqs_client():
    region = CONFIG.get("AWS_REGION", "us-east-1")
    endpoint_url = CONFIG.get("SQS_ENDPOINT_URL") # Optional: For LocalStack
    
    # Assumes AWS credentials are in env vars or ~/.aws/credentials
    if endpoint_url:
        # LocalStack requires dummy creds to stop boto3 from searching for real ones
        return boto3.client("sqs", 
            region_name=region, 
            endpoint_url=endpoint_url,
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )
    else:
        return boto3.client("sqs", region_name=region)

def send_print_job(user_data):
    """
    Sends a badge print job to the SQS queue.
    user_data: dict containing 'first_name', 'last_name', 'email', 'brivo_id'
    """
    queue_url = CONFIG.get("SQS_BADGE_QUEUE_URL")
    if not queue_url:
        logger.warning("⚠️ SQS_BADGE_QUEUE_URL not set. Skipping remote print job.")
        return False

    sqs = get_sqs_client()
    
    payload = {
        "action": "print_badge",
        "user": user_data,
        "timestamp": str(user_data.get("timestamp", ""))
    }

    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload)
        )
        logger.info(f"✅ Sent Badge Print Job to Queue: {response.get('MessageId')}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send SQS message: {e}")
        return False
