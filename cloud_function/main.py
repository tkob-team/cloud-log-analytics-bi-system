import base64
import json
import os
import logging

# Google Cloud BigQuery client for database operations
from google.cloud import bigquery
# Google Cloud Natural Language API client for sentiment analysis
from google.cloud import language_v1
# CloudEvents SDK for Pub/Sub trigger (Gen 2)
import functions_framework

# Configure logging for the application
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for BigQuery dataset and table
DATASET_ID = os.getenv("DATASET_ID", "analytics_ds")
TABLE_ID = os.getenv("TABLE_ID", "website_logs")

# Global variables for lazy-initialized clients
_bq_client = None
_nlp_client = None


def get_bq_client():
    """
    Lazily initialize and return a BigQuery client.
    Ensures the client is created only once per function instance (improves performance).
    """
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client()
    return _bq_client


def get_nlp_client():
    """
    Lazily initialize and return a Natural Language API client.
    Ensures the client is created only once per function instance (improves performance).
    """
    global _nlp_client
    if _nlp_client is None:
        _nlp_client = language_v1.LanguageServiceClient()
    return _nlp_client


@functions_framework.cloud_event
def process_logs(cloud_event):
    """
    Entry point for the Cloud Function (Gen 2) triggered by Pub/Sub via Eventarc.
    Receives a CloudEvent wrapping the Pub/Sub message, performs sentiment analysis
    if feedback exists, and inserts the processed log into BigQuery.

    Args:
        cloud_event: CloudEvent object containing the Pub/Sub message in cloud_event.data.
    """

    # Step 1: Decode the Pub/Sub message from the CloudEvent envelope
    try:
        message_data = cloud_event.data["message"]["data"]
        raw = base64.b64decode(message_data).decode("utf-8")
        data = json.loads(raw)
    except Exception as e:
        logger.error(f"Failed to decode Pub/Sub CloudEvent message: {e}")
        return  # Returning without raising → Pub/Sub won't retry (bad message)

    logger.info(f"Processing log: user={data.get('user_id')} action={data.get('action')}")

    # Step 2: Perform sentiment analysis if feedback is present
    sentiment_score = None
    feedback_text = data.get("feedback")

    if feedback_text:
        try:
            sentiment_score = analyze_sentiment(feedback_text)
            logger.info(f"Sentiment score: {sentiment_score:.4f}")
        except Exception as e:
            # If NLP API fails, log warning and proceed with NULL sentiment
            logger.warning(f"NLP API failed, inserting NULL sentiment: {e}")
            sentiment_score = None

    # Step 3: Build the row to insert into BigQuery
    row = {
        "timestamp": data.get("timestamp"),                # Event timestamp (ISO format)
        "user_id": data.get("user_id"),                    # User identifier
        "action": data.get("action"),                      # User action (e.g., view, click)
        "page": data.get("page"),                          # Page where the action occurred
        "response_time_ms": data.get("response_time_ms"),  # Response time in milliseconds
        "feedback": feedback_text,                         # Optional user feedback text
        "sentiment_score": sentiment_score,                # Sentiment score [0.0, 1.0] or None
    }

    # Step 4: Insert the row into BigQuery
    bq = get_bq_client()
    table_ref = f"{bq.project}.{DATASET_ID}.{TABLE_ID}"
    errors = bq.insert_rows_json(table_ref, [row])

    if errors:
        logger.error(f"BigQuery insert errors: {errors}")
        raise RuntimeError(f"BigQuery insert failed: {errors}")  # Raise → Pub/Sub will retry

    logger.info(f"Inserted row | user={row['user_id']} | sentiment={sentiment_score}")


def analyze_sentiment(text: str) -> float:
    """
    Analyze the sentiment of the given text using Google Cloud Natural Language API.

    Args:
        text (str): The feedback text to analyze.
    Returns:
        float: Sentiment score normalized to [0.0, 1.0] for BI visualization.
               (Raw NLP score is -1.0 to +1.0; normalized = (raw + 1) / 2)
    """
    client = get_nlp_client()
    document = language_v1.Document(
        content=text,
        type_=language_v1.Document.Type.PLAIN_TEXT,
    )
    response = client.analyze_sentiment(request={"document": document})
    raw_score = response.document_sentiment.score  # Range: -1.0 (negative) to +1.0 (positive)
    # Normalize to [0, 1] for Looker Studio gauge/chart compatibility
    return (raw_score + 1) / 2