-- Decision analytics over the long-format observation table.
--   observations(series_id, entity_id, observed_at, captured_at, metric,
--                value, unit, source_id, raw_ref, parser_version)
-- Run with: python examples/load_observations.py
-- Or in DuckDB, straight off GitHub with no credentials:
--   SELECT * FROM read_csv_auto('https://raw.githubusercontent.com/q3dresearch/wss-openrouter/main/derived/observations/*.csv')

-- EVERY query starts by deduplicating. Several sources restate the same
-- observed_at on each capture -- the task mix describes a trailing 7-day
-- window, so three captures produce three rows for the same week. That is
-- deliberate (it is how a revision becomes visible) but it means a naive
-- filter returns duplicates. `latest` keeps the most recent statement of
-- each fact, which is what almost every question wants.

-- Cost versus capability: what a point of intelligence costs, per model.
-- Which model to default to, and which "premium" model buys you nothing.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
newest AS (SELECT MAX(observed_at) AS t FROM latest WHERE metric = 'intelligence_index'),
score AS (
  SELECT entity_id AS slug, CAST(value AS REAL) AS index_score
  FROM latest, newest WHERE metric = 'intelligence_index' AND observed_at = newest.t
),
slug AS (SELECT entity_id AS model_id, value AS slug FROM latest WHERE metric = 'canonical_slug'),
price AS (SELECT entity_id AS model_id, CAST(value AS REAL) AS usd FROM latest WHERE metric = 'price_prompt_usd_per_mtok')
SELECT slug.model_id, score.index_score, price.usd AS usd_per_mtok,
       ROUND(score.index_score / NULLIF(price.usd, 0), 1) AS points_per_dollar
FROM score
JOIN slug ON slug.slug = score.slug
JOIN price ON price.model_id = slug.model_id
WHERE price.usd > 0
ORDER BY points_per_dollar DESC;

-- Who owns each workload, and how firmly. A leader holding 25% is a defended
-- position; one holding 7% is contested and worth entering.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
newest AS (SELECT MAX(observed_at) AS t FROM latest WHERE metric = 'token_share'),
task AS (
  SELECT substr(entity_id, 6) AS tag, CAST(value AS REAL) AS token_share
  FROM latest, newest
  WHERE metric = 'token_share' AND observed_at = newest.t
    AND entity_id LIKE 'task:%' AND entity_id NOT LIKE '%/model:%'
),
leader AS (
  SELECT substr(entity_id, 6, instr(entity_id, '/model:') - 6) AS tag,
         substr(entity_id, instr(entity_id, '/model:') + 7)    AS model,
         CAST(value AS REAL) AS within_task,
         ROW_NUMBER() OVER (
           PARTITION BY substr(entity_id, 6, instr(entity_id, '/model:') - 6)
           ORDER BY CAST(value AS REAL) DESC) AS rn
  FROM latest, newest
  WHERE metric = 'tag_token_share' AND observed_at = newest.t
)
SELECT task.tag,
       ROUND(task.token_share * 100, 1)   AS pct_of_all_tokens,
       leader.model                       AS leading_model,
       ROUND(leader.within_task * 100, 1) AS leader_pct_of_task
FROM task JOIN leader ON leader.tag = task.tag AND leader.rn = 1
ORDER BY task.token_share DESC;

-- Demand composition: what people use models for, independent of which wins.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
)
SELECT substr(entity_id, 7) AS macro_category,
       ROUND(CAST(value AS REAL) * 100, 1) AS pct_of_tokens
FROM latest
WHERE metric = 'token_share' AND entity_id LIKE 'macro:%'
  AND observed_at = (SELECT MAX(observed_at) FROM latest WHERE metric = 'token_share')
ORDER BY pct_of_tokens DESC;

-- What one agent session actually costs, by session length. A cheap
-- per-token model that needs fifty turns can cost more than an expensive one
-- that finishes in two. `newest` keeps one date: this series restates the
-- same rolling window on every capture, so without it the same cell appears
-- once per capture.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
newest AS (SELECT MAX(observed_at) AS t FROM latest WHERE metric = 'median_session_cost')
SELECT substr(entity_id, 5, instr(entity_id, '/turns:') - 5) AS app,
       substr(entity_id, instr(entity_id, '/turns:') + 7,
              instr(entity_id, '/model:') - instr(entity_id, '/turns:') - 7) AS turn_range,
       substr(entity_id, instr(entity_id, '/model:') + 7) AS model,
       ROUND(CAST(value AS REAL), 4) AS median_usd
FROM latest, newest
WHERE metric = 'median_session_cost' AND observed_at = newest.t
ORDER BY app, median_usd DESC;

-- The spread at the longest published session: the cost decision the
-- session-cost chart draws. `turn_order` makes the text ranges sortable.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
newest AS (SELECT MAX(observed_at) AS t FROM latest WHERE metric = 'median_session_cost'),
cost AS (
  SELECT substr(entity_id, 5, instr(entity_id, '/turns:') - 5) AS app,
         substr(entity_id, instr(entity_id, '/turns:') + 7,
                instr(entity_id, '/model:') - instr(entity_id, '/turns:') - 7) AS turn_range,
         substr(entity_id, instr(entity_id, '/model:') + 7) AS model,
         CAST(value AS REAL) AS usd,
         CASE substr(entity_id, instr(entity_id, '/turns:') + 7,
                     instr(entity_id, '/model:') - instr(entity_id, '/turns:') - 7)
           WHEN '1-turn' THEN 1 WHEN '2-9-turns' THEN 2
           WHEN '10-49-turns' THEN 3 WHEN '50-plus-turns' THEN 4 END AS turn_order
  FROM latest, newest
  WHERE metric = 'median_session_cost' AND observed_at = newest.t
),
-- The chart draws a line only when a model has two or more turn ranges.
-- Match that here, or Hermes Agent's spread includes a one-point model and
-- reads 8.9× where the chart says 4.3×.
model_ranges AS (
  SELECT app, model, COUNT(DISTINCT turn_order) AS n
  FROM cost GROUP BY app, model
),
cost_lines AS (
  SELECT c.* FROM cost c
  JOIN model_ranges m ON m.app = c.app AND m.model = c.model
  WHERE m.n >= 2
),
last_range AS (SELECT app, MAX(turn_order) AS turn_order FROM cost_lines GROUP BY app),
at_last AS (
  SELECT c.app, c.turn_range, MIN(c.usd) AS low_usd, MAX(c.usd) AS high_usd
  FROM cost_lines c JOIN last_range l
    ON l.app = c.app AND l.turn_order = c.turn_order
  GROUP BY c.app, c.turn_range
)
SELECT app, turn_range,
       ROUND(low_usd, 4) AS low_usd,
       ROUND(high_usd, 4) AS high_usd,
       ROUND(high_usd / NULLIF(low_usd, 0), 1) AS spread
FROM at_last
ORDER BY spread DESC;

-- What the provider directory says about physical location. Most providers
-- name no datacenter; the empty rows are the finding.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
provider AS (
  SELECT substr(entity_id, 10) AS provider, metric, value
  FROM latest
  WHERE series_id = 'openrouter.providers.directory'
    AND entity_id NOT LIKE '%/datacenter:%'
)
SELECT provider,
       MAX(CASE WHEN metric = 'headquarters' THEN value END) AS headquarters,
       MAX(CASE WHEN metric = 'datacenter_count' THEN CAST(value AS INTEGER) END) AS datacenters,
       MAX(CASE WHEN metric = 'status_page_url' THEN value END) AS status_page
FROM provider
GROUP BY provider
ORDER BY datacenters DESC, provider;

-- OpenCode's latest complete week: model share, spend proxy and retention.
-- The final daily row is a partial UTC day (the page recomputes hourly), so
-- `complete` keeps dates strictly before the maximum total-token date. The
-- seven-day window is therefore seven complete days, not eight minus one.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
oc AS (SELECT * FROM latest WHERE series_id = 'opencode.data.usage'),
total_days AS (
  SELECT substr(observed_at, 1, 10) AS day, CAST(value AS REAL) AS tokens
  FROM oc WHERE entity_id = 'total' AND metric = 'tokens'
),
max_day AS (SELECT MAX(day) AS day FROM total_days),
complete AS (
  SELECT total_days.day AS day FROM total_days, max_day
  WHERE total_days.day < max_day.day
    AND total_days.day >= date(max_day.day, '-7 days')
),
week_total AS (
  SELECT SUM(t.tokens) AS tokens
  FROM total_days t JOIN complete c ON c.day = t.day
),
week_model AS (
  SELECT substr(o.entity_id, 7) AS model,
         SUM(CASE WHEN o.metric = 'tokens' THEN CAST(o.value AS REAL) ELSE 0 END) AS tokens,
         SUM(CASE WHEN o.metric = 'unique_users' THEN CAST(o.value AS REAL) ELSE 0 END) AS user_days
  FROM oc o JOIN complete c ON c.day = substr(o.observed_at, 1, 10)
  WHERE o.entity_id LIKE 'model:%'
  GROUP BY model
),
attrs AS (
  SELECT substr(entity_id, 7) AS model,
         MAX(CASE WHEN metric = 'model_name' THEN value END) AS model_name,
         MAX(CASE WHEN metric = 'model_lab' THEN value END) AS lab,
         MAX(CASE WHEN metric = 'retention_pct' THEN CAST(value AS REAL) END) AS retention_pct,
         MAX(CASE WHEN metric = 'session_cost_usd' THEN CAST(value AS REAL) END) AS session_usd,
         MAX(CASE WHEN metric = 'tokens_per_session' THEN CAST(value AS REAL) END) AS tokens_per_session,
         MAX(CASE WHEN metric = 'price_input_usd_per_mtok' THEN CAST(value AS REAL) END) AS usd_per_mtok
  FROM oc WHERE entity_id LIKE 'model:%' GROUP BY model
),
spend AS (
  SELECT SUM(w.tokens * a.usd_per_mtok / 1000000.0) AS usd,
         SUM(CASE WHEN a.usd_per_mtok IS NOT NULL THEN w.tokens ELSE 0 END) AS priced_tokens
  FROM week_model w JOIN attrs a ON a.model = w.model
)
SELECT w.model, a.model_name, a.lab,
       ROUND(w.tokens / 1000000000000.0, 2) AS tokens_t,
       ROUND(w.tokens / t.tokens, 4) AS token_share,
       ROUND(w.user_days, 0) AS user_days,
       ROUND(a.retention_pct, 1) AS retention_pct,
       ROUND(a.session_usd, 4) AS session_usd,
       ROUND(w.tokens * a.usd_per_mtok / 1000000.0, 2) AS input_spend_usd,
       ROUND((w.tokens * a.usd_per_mtok / 1000000.0) / s.usd, 4) AS spend_share,
       ROUND(s.priced_tokens / t.tokens, 4) AS priced_coverage
FROM week_model w
JOIN attrs a ON a.model = w.model
CROSS JOIN week_total t CROSS JOIN spend s
WHERE w.tokens > 0
ORDER BY w.tokens DESC
LIMIT 15;

-- Which labs gained or lost share across OpenCode's visible window? The
-- publisher keeps only 56 days, so "first" is the first day this repo can see,
-- not the first day of the product. The daily share is already a percentage;
-- the change is in percentage points.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
oc AS (SELECT * FROM latest WHERE series_id = 'opencode.data.usage'),
total_days AS (
  SELECT substr(observed_at, 1, 10) AS day
  FROM oc WHERE entity_id = 'total' AND metric = 'tokens'
),
max_day AS (SELECT MAX(day) AS day FROM total_days),
complete AS (
  SELECT total_days.day AS day FROM total_days, max_day
  WHERE total_days.day < max_day.day
),
lab_days AS (
  SELECT substr(o.observed_at, 1, 10) AS day,
         substr(o.entity_id, 5) AS lab,
         CAST(o.value AS REAL) AS pct
  FROM oc o JOIN complete c ON c.day = substr(o.observed_at, 1, 10)
  WHERE o.metric = 'share_pct' AND o.entity_id LIKE 'lab:%'
),
bounds AS (SELECT MIN(day) AS first_day, MAX(day) AS last_day FROM lab_days),
first AS (
  SELECT l.lab, b.first_day AS day, l.pct
  FROM lab_days l CROSS JOIN bounds b WHERE l.day = b.first_day
),
last AS (
  SELECT l.lab, b.last_day AS day, l.pct
  FROM lab_days l CROSS JOIN bounds b WHERE l.day = b.last_day
)
SELECT f.lab,
       f.day AS first_day, ROUND(f.pct, 1) AS first_pct,
       l.day AS last_day, ROUND(l.pct, 1) AS last_pct,
       ROUND(l.pct - f.pct, 1) AS change_pts
FROM first f JOIN last l ON l.lab = f.lab
ORDER BY l.pct DESC
LIMIT 12;

-- OpenCode session cost is not a per-token price. The publisher reports the
-- average cost and tokens for one session, separately from list prices, so a
-- cheap model can still be a long session.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
model AS (
  SELECT substr(entity_id, 7) AS model,
         MAX(CASE WHEN metric = 'model_name' THEN value END) AS model_name,
         MAX(CASE WHEN metric = 'model_lab' THEN value END) AS lab,
         MAX(CASE WHEN metric = 'session_cost_usd' THEN CAST(value AS REAL) END) AS session_usd,
         MAX(CASE WHEN metric = 'tokens_per_session' THEN CAST(value AS REAL) END) AS tokens_per_session,
         MAX(CASE WHEN metric = 'retention_pct' THEN CAST(value AS REAL) END) AS retention_pct,
         MAX(CASE WHEN metric = 'price_input_usd_per_mtok' THEN CAST(value AS REAL) END) AS usd_per_mtok
  FROM latest
  WHERE series_id = 'opencode.data.usage' AND entity_id LIKE 'model:%'
  GROUP BY model
)
SELECT model, model_name, lab,
       ROUND(session_usd, 4) AS session_usd,
       ROUND(tokens_per_session / 1000000.0, 2) AS tokens_per_session_m,
       ROUND(retention_pct, 1) AS retention_pct,
       ROUND(usd_per_mtok, 3) AS input_usd_per_mtok
FROM model
WHERE session_usd IS NOT NULL AND tokens_per_session IS NOT NULL
ORDER BY session_usd;

-- ONCE SEVERAL WEEKS EXIST -- the questions only history can answer.

-- Is a workload growing or shrinking? (needs >= 2 distinct observed_at)
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
)
SELECT substr(entity_id, 6) AS tag,
       MIN(observed_at) AS first_seen,
       MAX(observed_at) AS last_seen,
       ROUND((MAX(CAST(value AS REAL)) - MIN(CAST(value AS REAL))) * 100, 2) AS share_swing_pts
FROM latest
WHERE metric = 'token_share' AND entity_id LIKE 'task:%' AND entity_id NOT LIKE '%/model:%'
GROUP BY tag
HAVING COUNT(DISTINCT observed_at) > 1
ORDER BY ABS(MAX(CAST(value AS REAL)) - MIN(CAST(value AS REAL))) DESC;

-- Quiet price cuts: a model whose price fell between two captures.
WITH latest AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY series_id, entity_id, metric, observed_at
      ORDER BY captured_at DESC) AS rn
    FROM observations
  ) WHERE rn = 1
),
p AS (SELECT entity_id, observed_at, CAST(value AS REAL) AS usd FROM latest WHERE metric = 'price_prompt_usd_per_mtok')
SELECT a.entity_id, a.observed_at AS from_date, a.usd AS from_price,
       b.observed_at AS to_date, b.usd AS to_price,
       ROUND((b.usd - a.usd) * 100.0 / NULLIF(a.usd, 0), 1) AS pct_change
FROM p a JOIN p b ON b.entity_id = a.entity_id AND b.observed_at > a.observed_at
WHERE a.usd <> b.usd
ORDER BY pct_change ASC;
