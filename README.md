# Cloud Log Analytics & BI System

> CSC11006 – Introduction to Cloud Computing | Project 1

End-to-end serverless pipeline on GCP: Python Simulator → Pub/Sub → Cloud Function + NLP API → BigQuery → BigQuery ML → Looker Studio.

## Architecture

```
[Python Simulator]
      │
      ▼
[Cloud Pub/Sub - website-logs]
      │
      ▼
[Cloud Function - process_logs]  ←→  [Natural Language API]
      │
      ▼
[BigQuery - analytics_ds.website_logs]
      │
      ▼
[BigQuery ML - purchase_prediction]
      │
      ▼
[Looker Studio Dashboard]
```

## Project Structure

```
├── simulator/
│   └── publisher.py          # Log simulator (Appendix A)
├── cloud_function/
│   ├── main.py               # Cloud Function triggered by Pub/Sub
│   └── requirements.txt
├── sql/
│   ├── create_bqml_model.sql # Train logistic regression model (Appendix B)
│   └── extra_analysis.sql    # Additional SQL analysis
└── docs/
    ├── public/               # Team documentation
    └── private/              # Leader-only docs
```

## Quick Start

### 1. Prerequisites
```bash
# Python 3.12
python --version

# Google Cloud SDK
gcloud --version
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Run Simulator
```bash
pip install google-cloud-pubsub
python simulator/publisher.py
```

### 3. Deploy Cloud Function
```bash
cd cloud_function/
gcloud functions deploy process_logs \
  --runtime python312 \
  --trigger-topic website-logs \
  --entry-point process_logs \
  --service-account cloud-function-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars PROJECT_ID=YOUR_PROJECT_ID \
  --region us-central1
```

### 4. Train BQML Model
Run `sql/create_bqml_model.sql` in BigQuery Console after simulator has produced 50+ rows with `sentiment_score IS NOT NULL`.

## Resource Naming (Fixed — Do Not Change)

| Resource | Name |
|----------|------|
| Pub/Sub Topic | `website-logs` |
| BigQuery Dataset | `analytics_ds` |
| BigQuery Table | `analytics_ds.website_logs` |
| BQML Model | `analytics_ds.purchase_prediction` |
| Cloud Function | `process_logs` |
| Service Account | `cloud-function-sa` |