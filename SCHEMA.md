# Data shape

*Generated 2026-09-15T13:15:04Z by `wss schema` from the derived rows. Do not hand-edit — regenerate after any derive.*

**You should not need to download anything to read this.**

- **20,848 observations** across 2 partition(s), in **6 series**
  - `openrouter.benchmarks.artificial-analysis` — 1,079 rows, **124 entities**
  - `openrouter.benchmarks.design-arena` — 900 rows, **114 entities**
  - `openrouter.benchmarks.openrouter` — 598 rows, **103 entities**
  - `openrouter.classifications.task` — 2,112 rows, **407 entities**
  - `openrouter.models.catalog` — 14,907 rows, **434 entities**
  - `openrouter.sessions.cost` — 1,252 rows, **342 entities**
- Raw: 34 file(s), 2,581,099 bytes on disk, 3 capture date(s), 2026-09-01 → 2026-09-08

## Sources

| source | cadence | endpoints | storage | personal data | licence |
| --- | --- | ---: | --- | --- | --- |
| `openrouter.benchmarks.artificial-analysis` | weekly | 1 | git | none | CC BY 4.0 via OpenRouter; scores originate with Artificial A |
| `openrouter.benchmarks.design-arena` | weekly | 1 | git | none | CC BY 4.0 via OpenRouter; scores originate with Design Arena |
| `openrouter.benchmarks.openrouter` | weekly | 1 | git | none | CC BY 4.0 via OpenRouter; scores originate with OpenRouter's |
| `openrouter.classifications.task` | weekly | 1 | git | none | CC BY 4.0 — cite: Source: OpenRouter (openrouter.ai/rankings |
| `openrouter.models.catalog` | weekly | 1 | git | none | public API; see https://openrouter.ai/terms |
| `openrouter.sessions.cost` | weekly | 4 | git | none | CC BY 4.0 — cite: Source: OpenRouter Data API, as of <as_of> |

## Columns

```
series_id, entity_id, observed_at, captured_at, metric, value, unit, source_id, raw_ref, parser_version
```

`entity_id` looks like: **openrouter.benchmarks.artificial-analysis** `anthropic/claude-3.5-sonnet`, `anthropic/claude-3.5-sonnet-20240620`, `anthropic/claude-4-sonnet-20250522`; **openrouter.benchmarks.design-arena** `anthropic/claude-4.6-opus-20260205/arena:models/3d`, `anthropic/claude-4.6-opus-20260205/arena:models/codecategories`, `anthropic/claude-4.6-opus-20260205/arena:models/dataviz`; **openrouter.benchmarks.openrouter** `amazon/nova-micro-v1/bench:gpqa_diamond`, `anthropic/claude-4-sonnet-20250522/bench:gpqa_diamond`, `anthropic/claude-4.5-haiku-20251001/bench:gpqa_diamond`; **openrouter.classifications.task** `macro:agent`, `macro:code`, `macro:data`; **openrouter.models.catalog** `aion-labs/aion-2.0`, `aion-labs/aion-3.0`, `aion-labs/aion-3.0-mini`; **openrouter.sessions.cost** `app:claude-code/turns:1-turn/model:anthropic/claude-3-haiku`, `app:claude-code/turns:1-turn/model:anthropic/claude-4.5-haiku-20251001`, `app:claude-code/turns:1-turn/model:anthropic/claude-4.5-sonnet-20250929`

## Metrics

| metric | series | rows | entities | type | unit | distinct | range / samples |
| --- | --- | ---: | ---: | --- | --- | ---: | --- |
| `accuracy` | openrouter.benchmarks.openrouter | 200 | 103 | number | fraction | 167 | `0.6167045282805429` … `0.944444` |
| `agentic_index` | openrouter.benchmarks.artificial-analysis | 354 | 118 | number | index | 193 | `0.1` … `59.2` |
| `avg_cost_per_task` | openrouter.benchmarks.openrouter | 198 | 102 | number | USD | 171 | `0.0013303306908267274` … `0.8424239494949496` |
| `avg_generation_time` | openrouter.benchmarks.design-arena | 300 | 114 | number | ms | 264 | `10976` … `693336` |
| `canonical_slug` | openrouter.models.catalog | 2,966 | 434 | text | ref | 350 | `aion-labs/aion-2.0-20260`, `aion-labs/aion-3.0-20260`, `aion-labs/aion-3.0-mini-` |
| `category_token_share` | openrouter.classifications.task | 87 | 29 | number | share | 68 | `0.007` … `0.727` |
| `category_usage_share` | openrouter.classifications.task | 87 | 29 | number | share | 66 | `0.003` … `0.723` |
| `coding_index` | openrouter.benchmarks.artificial-analysis | 400 | 124 | number | index | 116 | `4.8` … `81.6` |
| `context_length` | openrouter.models.catalog | 2,966 | 434 | number | tokens | 45 | `4095` … `2000000` |
| `elo` | openrouter.benchmarks.design-arena | 300 | 114 | number | rating | 90 | `1298` … `1464` |
| `hugging_face_id` | openrouter.models.catalog | 1,248 | 182 | text | ref | 155 | `ByteDance-Seed/UI-TARS-1`, `CohereForAI/c4ai-command`, `CohereLabs/North-Mini-Co` |
| `intelligence_index` | openrouter.benchmarks.artificial-analysis | 325 | 118 | number | index | 187 | `3.8` … `63.1` |
| `median_session_cost` | openrouter.sessions.cost | 1,252 | 342 | text | USD/session | 740 | `0.00010325`, `0.00011183333`, `0.000259` |
| `price_cache_read_usd_per_mtok` | openrouter.models.catalog | 1,795 | 267 | number | USD/Mtok | 92 | `0.002` … `7.5` |
| `price_completion_usd_per_mtok` | openrouter.models.catalog | 2,966 | 434 | number | USD/Mtok | 152 | `-1000000` … `600` |
| `price_prompt_usd_per_mtok` | openrouter.models.catalog | 2,966 | 434 | number | USD/Mtok | 124 | `-1000000` … `150` |
| `tag_token_share` | openrouter.classifications.task | 870 | 374 | number | share | 180 | `0.001` … `0.387` |
| `tag_usage_share` | openrouter.classifications.task | 870 | 374 | number | share | 168 | `0.01` … `0.557` |
| `token_share` | openrouter.classifications.task | 99 | 33 | number | share | 56 | `0.002` … `0.378` |
| `total_tasks` | openrouter.benchmarks.openrouter | 200 | 103 | number | count | 85 | `120` … `5742` |
| `usage_share` | openrouter.classifications.task | 99 | 33 | number | share | 55 | `0.002` … `0.544` |
| `win_rate` | openrouter.benchmarks.design-arena | 300 | 114 | number | percent | 119 | `49.6` … `79.2` |

## Partitions

- `derived/observations/2026-08.csv.gz`
- `derived/observations/2026-09.csv.gz`
