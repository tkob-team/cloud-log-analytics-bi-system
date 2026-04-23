-- ============================================================
-- Appendix B: Train BigQuery ML Logistic Regression Model
-- Purpose: Predict if a user will make a purchase
-- ============================================================
-- Prerequisites:
--   - Table analytics_ds.website_logs exists and has data
--   - At least 50 rows WHERE sentiment_score IS NOT NULL
-- ============================================================

CREATE OR REPLACE MODEL `analytics_ds.purchase_prediction`
OPTIONS(
  model_type = 'logistic_reg',
  input_label_cols = ['is_purchase']
) AS

SELECT
  -- Label: 1 if user purchased, 0 otherwise
  IF(action = 'purchase', 1, 0) AS is_purchase,

  -- Feature 1: User sentiment (only non-NULL rows used)
  sentiment_score,

  -- Feature 2: Page response time (proxy for UX quality)
  response_time_ms

FROM `analytics_ds.website_logs`
WHERE sentiment_score IS NOT NULL;   -- BQML needs non-NULL features
