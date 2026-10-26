# Data shape

*Generated 2026-10-26T10:38:04Z by `wss schema` from the derived rows. Do not hand-edit — regenerate after any derive.*

**You should not need to download anything to read this.**

- **48,908 observations** across 3 partition(s), in **7 series**
  - `opencode.data.usage` — 2,889 rows, **273 entities**
  - `openrouter.benchmarks.artificial-analysis` — 2,583 rows, **169 entities**
  - `openrouter.benchmarks.design-arena` — 2,700 rows, **177 entities**
  - `openrouter.benchmarks.openrouter` — 2,395 rows, **139 entities**
  - `openrouter.classifications.task` — 6,336 rows, **693 entities**
  - `openrouter.models.catalog` — 28,711 rows, **527 entities**
  - `openrouter.sessions.cost` — 3,294 rows, **501 entities**
- Raw: 89 file(s), 3,180,464 bytes on disk, 10 capture date(s), 2026-09-01 → 2026-10-26

## Sources

| source | cadence | endpoints | storage | personal data | licence |
| --- | --- | ---: | --- | --- | --- |
| `opencode.data.usage` | weekly | 1 | git | none | No explicit licence stated. Publisher requests citation: Cit |
| `openrouter.benchmarks.artificial-analysis` | weekly | 1 | git | none | CC BY 4.0 via OpenRouter; scores originate with Artificial A |
| `openrouter.benchmarks.design-arena` | weekly | 1 | git | none | CC BY 4.0 via OpenRouter; scores originate with Design Arena |
| `openrouter.benchmarks.openrouter` | weekly | 1 | git | none | CC BY 4.0 via OpenRouter; scores originate with OpenRouter's |
| `openrouter.classifications.task` | weekly | 1 | git | none | CC BY 4.0 — cite: Source: OpenRouter (openrouter.ai/rankings |
| `openrouter.models.catalog` | weekly | 1 | git | none | public API; see https://openrouter.ai/terms |
| `openrouter.providers.directory` | weekly | 1 | git | none | public API; see https://openrouter.ai/terms |
| `openrouter.sessions.cost` | weekly | 4 | git | none | CC BY 4.0 — cite: Source: OpenRouter Data API, as of <as_of> |

## Columns

```
series_id, entity_id, observed_at, captured_at, metric, value, unit, source_id, raw_ref, parser_version
```

`entity_id` looks like: **opencode.data.usage** `bucket:other`, `country:AD`, `country:AE`; **openrouter.benchmarks.artificial-analysis** `anthropic/claude-3.5-sonnet`, `anthropic/claude-3.5-sonnet-20240620`, `anthropic/claude-4-sonnet-20250522`; **openrouter.benchmarks.design-arena** `anthropic/claude-4.6-opus-20260205/arena:models/3d`, `anthropic/claude-4.6-opus-20260205/arena:models/codecategories`, `anthropic/claude-4.6-opus-20260205/arena:models/dataviz`; **openrouter.benchmarks.openrouter** `amazon/nova-micro-v1/bench:gpqa_diamond`, `anthropic/claude-4-sonnet-20250522/bench:gpqa_diamond`, `anthropic/claude-4.5-haiku-20251001/bench:gpqa_diamond`; **openrouter.classifications.task** `macro:agent`, `macro:code`, `macro:data`; **openrouter.models.catalog** `aion-labs/aion-2.0`, `aion-labs/aion-3.0`, `aion-labs/aion-3.0-mini`; **openrouter.sessions.cost** `app:claude-code/turns:1-turn/model:anthropic/claude-3-haiku`, `app:claude-code/turns:1-turn/model:anthropic/claude-4.5-haiku-20251001`, `app:claude-code/turns:1-turn/model:anthropic/claude-4.5-sonnet-20250929`

## Metrics

| metric | series | rows | entities | type | unit | distinct | range / samples |
| --- | --- | ---: | ---: | --- | --- | ---: | --- |
| `accuracy` | openrouter.benchmarks.openrouter | 800 | 139 | number | fraction | 497 | `0.6167045282805429` … `0.964646` |
| `agentic_index` | openrouter.benchmarks.artificial-analysis | 793 | 122 | number | index | 239 | `0.1` … `59.2` |
| `avg_cost_per_task` | openrouter.benchmarks.openrouter | 795 | 137 | number | USD | 528 | `0.001158979797979798` … `1.148739303030303` |
| `avg_generation_time` | openrouter.benchmarks.design-arena | 900 | 177 | number | ms | 831 | `10976` … `1071985` |
| `cached_input_pct` | opencode.data.usage | 10 | 10 | number | percent | 9 | `82.7` … `97.2` |
| `cached_input_tokens` | opencode.data.usage | 10 | 10 | number | tokens | 10 | `894600000000` … `106339000000000` |
| `canonical_slug` | openrouter.models.catalog | 5,707 | 527 | text | ref | 417 | `aion-labs/aion-2.0-20260`, `aion-labs/aion-3.0-20260`, `aion-labs/aion-3.0-mini-` |
| `category_token_share` | openrouter.classifications.task | 261 | 29 | number | share | 152 | `0.006` … `0.783` |
| `category_usage_share` | openrouter.classifications.task | 261 | 29 | number | share | 156 | `0.002` … `0.809` |
| `coding_index` | openrouter.benchmarks.artificial-analysis | 875 | 128 | number | index | 120 | `4.8` … `81.6` |
| `context_length` | openrouter.models.catalog | 5,707 | 527 | number | tokens | 49 | `4095` … `2000000` |
| `eligible_user_weeks` | opencode.data.usage | 15 | 15 | number | user-weeks | 15 | `179` … `413293` |
| `elo` | openrouter.benchmarks.design-arena | 900 | 177 | number | rating | 143 | `1298` … `1491` |
| `hugging_face_id` | openrouter.models.catalog | 2,316 | 211 | text | ref | 173 | `ByteDance-Seed/UI-TARS-1`, `CohereForAI/c4ai-command`, `CohereLabs/North-Mini-Co` |
| `intelligence_index` | openrouter.benchmarks.artificial-analysis | 915 | 165 | number | index | 270 | `3.8` … `63.1` |
| `median_session_cost` | openrouter.sessions.cost | 3,294 | 501 | text | USD/session | 2777 | `0.000102`, `0.00010325`, `0.00011016667` |
| `model_lab` | opencode.data.usage | 20 | 20 | text | ref | 12 | `anthropic`, `deepseek`, `meituan` |
| `model_name` | opencode.data.usage | 25 | 25 | text | ref | 25 | `Beam 1.0 501B A23B`, `Claude Haiku 5.5`, `DeepSeek V4 Flash` |
| `price_cache_read_usd_per_mtok` | openrouter.models.catalog | 3,567 | 350 | number | USD/Mtok | 138 | `0.0016` … `7.5` |
| `price_cached_input_usd_per_mtok` | opencode.data.usage | 8 | 8 | number | USD/Mtok | 7 | `0.002` … `0.04` |
| `price_completion_usd_per_mtok` | openrouter.models.catalog | 5,707 | 527 | number | USD/Mtok | 210 | `-1000000` … `600` |
| `price_input_usd_per_mtok` | opencode.data.usage | 8 | 8 | number | USD/Mtok | 6 | `0.1` … `0.4` |
| `price_output_usd_per_mtok` | opencode.data.usage | 8 | 8 | number | USD/Mtok | 5 | `0.2` … `1.2` |
| `price_prompt_usd_per_mtok` | openrouter.models.catalog | 5,707 | 527 | number | USD/Mtok | 190 | `-1000000` … `150` |
| `rank_past_day` | opencode.data.usage | 18 | 18 | number | rank | 18 | `1` … `18` |
| `rank_past_week` | opencode.data.usage | 18 | 18 | number | rank | 18 | `1` … `18` |
| `retained_user_weeks` | opencode.data.usage | 15 | 15 | number | user-weeks | 15 | `113` … `286039` |
| `retention_pct` | opencode.data.usage | 15 | 15 | number | percent | 14 | `62.5` … `77.7` |
| `retention_rank` | opencode.data.usage | 15 | 15 | number | rank | 15 | `1` … `15` |
| `session_cost_usd` | opencode.data.usage | 6 | 6 | number | USD/session | 6 | `0.0016` … `0.0335` |
| `share_pct` | opencode.data.usage | 699 | 246 | number | percent | 200 | `0` … `81` |
| `tag_token_share` | openrouter.classifications.task | 2,610 | 660 | number | share | 266 | `0` … `0.708` |
| `tag_usage_share` | openrouter.classifications.task | 2,610 | 660 | number | share | 243 | `0.006` … `0.723` |
| `token_share` | openrouter.classifications.task | 297 | 33 | number | share | 103 | `0.002` … `0.378` |
| `tokens` | opencode.data.usage | 1,315 | 257 | number | tokens | 1100 | `0` … `169205100000000` |
| `tokens_change_pct_past_week` | opencode.data.usage | 16 | 16 | number | percent | 15 | `-77` … `55` |
| `tokens_past_day` | opencode.data.usage | 18 | 18 | number | tokens | 16 | `18000000000` … `7424000000000` |
| `tokens_past_week` | opencode.data.usage | 18 | 18 | number | tokens | 18 | `300000000000` … `111450000000000` |
| `tokens_per_session` | opencode.data.usage | 6 | 6 | number | tokens | 6 | `1177246` … `5055659` |
| `total_tasks` | openrouter.benchmarks.openrouter | 800 | 139 | number | count | 183 | `120` … `5742` |
| `uncached_input_tokens` | opencode.data.usage | 10 | 10 | number | tokens | 10 | `37200000000` … `4476200000000` |
| `unique_users` | opencode.data.usage | 616 | 11 | number | count | 451 | `0` … `412180` |
| `usage_share` | openrouter.classifications.task | 297 | 33 | number | share | 111 | `0.001` … `0.592` |
| `win_rate` | openrouter.benchmarks.design-arena | 900 | 177 | number | percent | 208 | `47.4` … `79.2` |

## Partitions

- `derived/observations/2026-08.csv.gz`
- `derived/observations/2026-09.csv.gz`
- `derived/observations/2026-10.csv.gz`
