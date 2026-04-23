import base64
import json
import os
import logging

from google.cloud import bigquery
from google.cloud import language_v1

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BigQuery table (set PROJECT_ID via env var at deploy time)
PROJECT_ID = os.environ.get("PROJECT_ID", "your-project-id")
TABLE_ID = f"{PROJECT_ID}.analytics_ds.website_logs"

# Lazy-init clients (reused across invocations in same instance)
_bq_client = None
_nlp_client = None


def get_bq_client():
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client()
    return _bq_client


def get_nlp_client():
    global _nlp_client
    if _nlp_client is None:
        _nlp_client = language_v1.LanguageServiceClient()
    return _nlp_client


def process_logs(event, context):
    """Cloud Function — triggered by Pub/Sub message on topic 'website-logs'.

    Args:
        event (dict): Pub/Sub event data with base64-encoded 'data' field.
        context (google.cloud.functions.Context): Cloud Function metadata.
    """
    # ── Step 1: Decode Pub/Sub message ──────────────────────────────────────
    try:
        raw = base64.b64decode(event["data"]).decode("utf-8")
        data = json.loads(raw)
    except Exception as e:
        logger.error(f"Failed to decode message: {e}")
        return  # Discard malformed messages

    logger.info(f"Processing log: user={data.get('user_id')} action={data.get('action')}")

    # ── Step 2: Sentiment analysis — ONLY when feedback exists ──────────────
    sentiment_score = None
    feedback_text = data.get("feedback")

    if feedback_text:                          # 30% of logs have feedback
        try:
            sentiment_score = analyze_sentiment(feedback_text)
            logger.info(f"Sentiment score: {sentiment_score:.4f}")
        except Exception as e:
            logger.warning(f"NLP API failed, inserting NULL: {e}")
            sentiment_score = None             # Graceful fallback — don't break pipeline

    # ── Step 3: Build BigQuery row ───────────────────────────────────────────
    row = {
        "timestamp": data.get("timestamp"),
        "user_id": data.get("user_id"),
        "action": data.get("action"),
        "page": data.get("page"),
        "response_time_ms": data.get("response_time_ms"),
        "feedback": feedback_text,
        "sentiment_score": sentiment_score,    # FLOAT or None (NULL in BQ)
    }

    # ── Step 4: Insert into BigQuery ─────────────────────────────────────────
    errors = get_bq_client().insert_rows_json(TABLE_ID, [row])
    if errors:
        logger.error(f"BigQuery insert errors: {errors}")
        raise RuntimeError(f"BigQuery insert failed: {errors}")

    logger.info(f"✅ Inserted row | user={row['user_id']} | sentiment={sentiment_score}")


def analyze_sentiment(text: str) -> float:
    """Call Google Natural Language API and return normalized sentiment score.

    Args:
        text: Feedback text string.

    Returns:
        float: Sentiment score normalized to [0.0, 1.0].
               (Raw API returns [-1.0, +1.0]; we normalize: (score + 1) / 2)
    """
    client = get_nlp_client()

    document = language_v1.Document(
        content=text,
        type_=language_v1.Document.Type.PLAIN_TEXT,
    )

    response = client.analyze_sentiment(request={"document": document})
    raw_score = response.document_sentiment.score  # range: -1.0 to +1.0

    # Normalize to [0, 1] for Looker Gauge chart
    return (raw_score + 1) / 2
