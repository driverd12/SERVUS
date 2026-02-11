import boto3
import logging
import sys
import json
from servus.config import CONFIG

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup_sqs")

def setup_badge_queue():
    """
    Configures the SQS Queue with production resiliency parameters.
    """
    queue_url = CONFIG.get("SQS_BADGE_QUEUE_URL")
    region = CONFIG.get("AWS_REGION", "us-east-1")
    endpoint_url = CONFIG.get("SQS_ENDPOINT_URL")
    
    if not queue_url:
        logger.error("SQS_BADGE_QUEUE_URL not set.")
        return

    logger.info(f"🔧 Configuring SQS Queue: {queue_url}")

    # Create Client
    if endpoint_url:
        sqs = boto3.client("sqs", region_name=region, endpoint_url=endpoint_url,
                          aws_access_key_id="test", aws_secret_access_key="test")
    else:
        sqs = boto3.client("sqs", region_name=region)

    # 1. Create DLQ (Dead Letter Queue)
    dlq_name = "badge-queue-dlq"
    try:
        logger.info(f"   Creating DLQ: {dlq_name}...")
        dlq_resp = sqs.create_queue(QueueName=dlq_name)
        dlq_url = dlq_resp['QueueUrl']
        
        # Get DLQ ARN
        dlq_attrs = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=['QueueArn'])
        dlq_arn = dlq_attrs['Attributes']['QueueArn']
        logger.info(f"   ✅ DLQ Created: {dlq_arn}")
    except Exception as e:
        logger.error(f"   ❌ Failed to create DLQ: {e}")
        return

    # 2. Configure Main Queue
    # Extract Queue Name from URL for API call if needed, but set_queue_attributes takes URL
    
    attributes = {
        'VisibilityTimeout': '300', # 5 minutes (allow time for printer to warm up/process)
        'MessageRetentionPeriod': '604800', # 7 days
        'RedrivePolicy': json.dumps({
            'deadLetterTargetArn': dlq_arn,
            'maxReceiveCount': '5' # Retry 5 times before DLQ
        })
    }
    
    try:
        sqs.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes=attributes
        )
        logger.info("   ✅ Queue Attributes Updated (Visibility=300s, Retention=7d, DLQ=Enabled)")
    except Exception as e:
        logger.error(f"   ❌ Failed to update queue attributes: {e}")

if __name__ == "__main__":
    setup_badge_queue()
