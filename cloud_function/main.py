import base64
import json
import os
import logging

# Google Cloud BigQuery client for database operations
from google.cloud import bigquery
# Google Cloud Natural Language API client for sentiment analysis
from google.cloud import language_v1
# Flask Request object for HTTP handling (Cloud Function Gen 2)
from flask import Request

# Configure logging for the application
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables for BigQuery dataset and table
DATASET_ID = os.getenv("DATASET_ID")
TABLE_ID = os.getenv("TABLE_ID")

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

def process_logs(request: Request):
    """
    Entry point for the Cloud Function (Gen 2) triggered via HTTP (Pub/Sub Push).
    Parses the incoming Pub/Sub message, performs sentiment analysis if feedback exists,
    and inserts the processed log into BigQuery.
    Args:
        request (Request): Flask HTTP request object containing the Pub/Sub message.
    Returns:
        Tuple[str, int]: Response message and HTTP status code.
    """

    # Step 1: Parse the Pub/Sub envelope from the HTTP request
    envelope = request.get_json(silent=True)
    if not envelope or "message" not in envelope:
        logger.error("Invalid Pub/Sub envelope")
        return "Bad Request: missing message", 400

    pubsub_message = envelope["message"]

    try:
        # Decode the base64-encoded Pub/Sub data field
        raw = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        # Parse the JSON payload into a Python dictionary
        data = json.loads(raw)
    except Exception as e:
        logger.error(f"Failed to decode message: {e}")
        return "Bad Request: decode error", 400

    logger.info(f"Processing log: user={data.get('user_id')} action={data.get('action')}")

    # Step 2: Perform sentiment analysis if feedback is present
    sentiment_score = None
    feedback_text = data.get("feedback")

    if feedback_text:
        try:
            # Analyze sentiment of the feedback text
            sentiment_score = analyze_sentiment(feedback_text)
            logger.info(f"Sentiment score: {sentiment_score:.4f}")
        except Exception as e:
            # If NLP API fails, log warning and proceed with NULL sentiment
            logger.warning(f"NLP API failed, inserting NULL: {e}")
            sentiment_score = None

    # Step 3: Build the row to insert into BigQuery
    row = {
        "timestamp": data.get("timestamp"),           # Event timestamp (ISO format)
        "user_id": data.get("user_id"),               # User identifier
        "action": data.get("action"),                 # User action (e.g., view, click)
        "page": data.get("page"),                     # Page where the action occurred
        "response_time_ms": data.get("response_time_ms"), # Response time in milliseconds
        "feedback": feedback_text,                      # Optional user feedback
        "sentiment_score": sentiment_score,             # Sentiment score (float or None)
    }

    # Step 4: Insert the row into BigQuery
    bq = get_bq_client()
    table_ref = f"{bq.project}.{DATASET_ID}.{TABLE_ID}"
    errors = bq.insert_rows_json(table_ref, [row])
    if errors:
        # Log and return error if insertion fails
        logger.error(f"BigQuery insert errors: {errors}")
        return f"BigQuery insert failed: {errors}", 500

    logger.info(f"Inserted row | user={row['user_id']} | sentiment={sentiment_score}")
    return "OK", 200


def analyze_sentiment(text: str) -> float:
    """
    Analyze the sentiment of the given text using Google Cloud Natural Language API.
    Args:
        text (str): The feedback text to analyze.
    Returns:
        float: Sentiment score normalized to [0.0, 1.0].
    """
    client = get_nlp_client()
    # Create a document object for the API
    document = language_v1.Document(
        content=text,
        type_=language_v1.Document.Type.PLAIN_TEXT,
    )
    # Call the API to analyze sentiment
    response = client.analyze_sentiment(request={"document": document})
    raw_score = response.document_sentiment.score  # Range: -1.0 (negative) to +1.0 (positive)
    # Normalize score to [0, 1] for easier BI visualization
    return (raw_score + 1) / 2