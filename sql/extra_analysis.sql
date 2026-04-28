-- ============================================================
-- Extra Analysis SQL (Pro-tip: Run these for full score)
-- ============================================================

-- 1. Check sentiment distribution by action type
SELECT
  action,
  COUNT(*) AS total_logs,
  AVG(sentiment_score) AS avg_sentiment,
  COUNTIF(sentiment_score > 0.6) AS positive_count,
  COUNTIF(sentiment_score < 0.4) AS negative_count
FROM `analytics_ds.website_logs`
WHERE sentiment_score IS NOT NULL
GROUP BY action
ORDER BY avg_sentiment DESC;

-- ============================================================

-- 2. Test the trained model with ML.PREDICT
SELECT
  user_id,
  action,
  sentiment_score,
  response_time_ms,
  predicted_is_purchase
FROM ML.PREDICT(
  MODEL `analytics_ds.purchase_prediction`,
  (
    SELECT user_id, action, sentiment_score, response_time_ms
    FROM `analytics_ds.website_logs`
    WHERE sentiment_score IS NOT NULL
    LIMIT 20
  )
);

-- ============================================================

-- 3. Verify: count rows ready for BQML training
SELECT
  COUNT(*) AS total_rows,
  COUNTIF(sentiment_score IS NOT NULL) AS rows_with_sentiment,
  COUNTIF(sentiment_score IS NULL) AS rows_without_sentiment
FROM `analytics_ds.website_logs`;
