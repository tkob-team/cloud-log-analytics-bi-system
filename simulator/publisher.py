import json
import time
import random
from datetime import datetime
from google.cloud import pubsub_v1

# ============================================================
# CONFIGURATION — Cập nhật PROJECT_ID trước khi chạy!
# ============================================================
PROJECT_ID = "your-project-id"   # TODO: đổi thành PROJECT_ID thật
TOPIC_ID = "website-logs"        # Không thay đổi
# ============================================================

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

# Sample feedback (30% logs sẽ có feedback text)
FEEDBACK_SAMPLES = [
    "I love the new interface!",
    "The checkout process is really confusing.",
    "Great product selection, very happy.",
    "Website is way too slow to load.",
    "Amazing shopping experience overall!",
    "I cannot find the search button anywhere.",
    "Fast delivery and great support!",
    "The cart keeps losing my items.",
    "Prices are very competitive.",
    "Navigation is unclear and frustrating.",
]

PAGES = ["/home", "/cart", "/product", "/checkout", "/about"]
ACTIONS = ["view", "click", "add_to_cart", "purchase"]


def run_simulator():
    """Publish fake website log events to Cloud Pub/Sub."""
    print(f"🚀 Starting simulator...")
    print(f"   Topic: {topic_path}")
    print(f"   Press Ctrl+C to stop.\n")

    count = 0
    try:
        while True:
            # 30% chance of leaving feedback
            has_feedback = random.random() < 0.30
            feedback = random.choice(FEEDBACK_SAMPLES) if has_feedback else None

            data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "user_id": f"USER_{random.randint(1, 50):03d}",
                "action": random.choice(ACTIONS),
                "page": random.choice(PAGES),
                "response_time_ms": random.randint(50, 800),
                "feedback": feedback
            }

            payload = json.dumps(data).encode("utf-8")
            future = publisher.publish(topic_path, payload)
            future.result()  # block until confirmed

            count += 1
            feedback_indicator = "💬" if feedback else "  "
            print(f"[{count:04d}] {feedback_indicator} Sent: {data['user_id']} | {data['action']:12s} | {data['page']}")

            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n⏹ Stopped. Total messages sent: {count}")


if __name__ == "__main__":
    run_simulator()
