"""Parser for schema opencode-usage.v1 — OpenCode's own usage telemetry.

Shape verified against https://opencode.ai/data/index.json on 2026-10-26.

The page is a live view, not an archive: it recomputes hourly and keeps a
rolling 56-day daily window. The snapshot sections (leaderboard, retention,
session cost, prices, cache ratio, geography) describe the moment named by
`updatedAt`; the daily sections carry their own dates. Those two clocks are
kept apart by setting `observed_at` from the payload rather than letting the
capture time stand in.

Entities are namespaced so the series joins cleanly:

  model:<slug>     per-model daily tokens/users and the snapshot sections
  bucket:other     the publisher's residual bucket, not a model
  lab:<slug>       market share by lab (display name reduced to a slug)
  country:<ISO>    geography
  total            the all-model daily total

`summary` is prose and is deliberately not parsed; the numbers behind it are
already in the structured sections. Model display names and lab slugs are
carried as `ref` observations, because OpenCode's model slugs are not
OpenRouter permaslugs and a name is what makes the two sides joinable.
"""

import json
import re

from wss import derive

PARSER_VERSION = "1"

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def _model_entity(slug: str) -> str:
    """A model slug, except the publisher's residual bucket."""
    return "bucket:other" if slug.lower() == "other" else f"model:{slug}"


def _lab_entity(name: str) -> str:
    """`Zhipu AI` -> `lab:zhipu-ai`; display names are not join keys."""
    return "lab:" + _NON_SLUG.sub("-", name.lower()).strip("-")


def parse(body: bytes, ctx: derive.ParseContext):
    payload = json.loads(body)
    snapshot_at = payload.get("updatedAt")

    leaderboard = payload.get("leaderboard") or {}
    retention = payload.get("weeklyRetention", [])

    # Display names and lab slugs appear in different sections. Keep the first
    # spelling seen and emit each ref once per snapshot, not once per section.
    names: dict[str, str] = {}
    labs: dict[str, str] = {}
    for row in leaderboard.get("pastWeek", []) + leaderboard.get("pastDay", []):
        if row.get("name"):
            names.setdefault(row["model"], row["name"])
        if row.get("lab"):
            labs.setdefault(row["model"], row["lab"])
    for row in retention:
        if row.get("name"):
            names.setdefault(row["model"], row["name"])

    for slug, name in sorted(names.items()):
        yield derive.Observation(
            entity_id=_model_entity(slug),
            metric="model_name",
            value=name,
            unit="ref",
            observed_at=snapshot_at,
        )
    for slug, lab in sorted(labs.items()):
        yield derive.Observation(
            entity_id=_model_entity(slug),
            metric="model_lab",
            value=lab,
            unit="ref",
            observed_at=snapshot_at,
        )

    # --- daily series: each row carries its own UTC date -----------------
    for row in payload.get("dailyTokens", []):
        observed_at = f"{row['date']}T00:00:00Z"
        if row.get("total") is not None:
            yield derive.Observation(
                entity_id="total",
                metric="tokens",
                value=row["total"],
                unit="tokens",
                observed_at=observed_at,
            )
        for slug, value in (row.get("models") or {}).items():
            if value is not None:
                yield derive.Observation(
                    entity_id=_model_entity(slug),
                    metric="tokens",
                    value=value,
                    unit="tokens",
                    observed_at=observed_at,
                )

    for row in payload.get("dailyUniqueUsers", []):
        observed_at = f"{row['date']}T00:00:00Z"
        if row.get("total") is not None:
            yield derive.Observation(
                entity_id="total",
                metric="unique_users",
                value=row["total"],
                unit="count",
                observed_at=observed_at,
            )
        for slug, value in (row.get("models") or {}).items():
            if value is not None:
                yield derive.Observation(
                    entity_id=_model_entity(slug),
                    metric="unique_users",
                    value=value,
                    unit="count",
                    observed_at=observed_at,
                )

    # --- leaderboards: trailing 7-day and 1-day windows -------------------
    for row in leaderboard.get("pastWeek", []):
        entity_id = _model_entity(row["model"])
        if row.get("tokens") is not None:
            yield derive.Observation(
                entity_id=entity_id,
                metric="tokens_past_week",
                value=row["tokens"],
                unit="tokens",
                observed_at=snapshot_at,
            )
        if row.get("rank") is not None:
            yield derive.Observation(
                entity_id=entity_id,
                metric="rank_past_week",
                value=row["rank"],
                unit="rank",
                observed_at=snapshot_at,
            )
        if row.get("changePercent") is not None:
            yield derive.Observation(
                entity_id=entity_id,
                metric="tokens_change_pct_past_week",
                value=row["changePercent"],
                unit="percent",
                observed_at=snapshot_at,
            )

    for row in leaderboard.get("pastDay", []):
        entity_id = _model_entity(row["model"])
        if row.get("tokens") is not None:
            yield derive.Observation(
                entity_id=entity_id,
                metric="tokens_past_day",
                value=row["tokens"],
                unit="tokens",
                observed_at=snapshot_at,
            )
        if row.get("rank") is not None:
            yield derive.Observation(
                entity_id=entity_id,
                metric="rank_past_day",
                value=row["rank"],
                unit="rank",
                observed_at=snapshot_at,
            )

    # --- weekly retention -------------------------------------------------
    for row in retention:
        entity_id = _model_entity(row["model"])
        for key, metric, unit in (
            ("retentionPercent", "retention_pct", "percent"),
            ("eligibleUserWeeks", "eligible_user_weeks", "user-weeks"),
            ("retainedUserWeeks", "retained_user_weeks", "user-weeks"),
            ("rank", "retention_rank", "rank"),
        ):
            if row.get(key) is not None:
                yield derive.Observation(
                    entity_id=entity_id,
                    metric=metric,
                    value=row[key],
                    unit=unit,
                    observed_at=snapshot_at,
                )

    # --- average session cost and tokens per session ----------------------
    for row in payload.get("sessionCost", []):
        entity_id = _model_entity(row["model"])
        for key, metric, unit in (
            ("costPerSessionUsd", "session_cost_usd", "USD/session"),
            ("tokensPerSession", "tokens_per_session", "tokens"),
        ):
            if row.get(key) is not None:
                yield derive.Observation(
                    entity_id=entity_id,
                    metric=metric,
                    value=row[key],
                    unit=unit,
                    observed_at=snapshot_at,
                )

    # --- list prices, USD per million tokens ------------------------------
    for row in payload.get("tokenPricesUsdPer1M", []):
        entity_id = _model_entity(row["model"])
        for key, metric in (
            ("input", "price_input_usd_per_mtok"),
            ("output", "price_output_usd_per_mtok"),
            ("cachedInput", "price_cached_input_usd_per_mtok"),
        ):
            if row.get(key) is not None:
                yield derive.Observation(
                    entity_id=entity_id,
                    metric=metric,
                    value=row[key],
                    unit="USD/Mtok",
                    observed_at=snapshot_at,
                )

    # --- cache hit rate and the token counts behind it --------------------
    for row in payload.get("cacheRatio", []):
        entity_id = _model_entity(row["model"])
        for key, metric, unit in (
            ("cachedInputPercent", "cached_input_pct", "percent"),
            ("cachedInputTokens", "cached_input_tokens", "tokens"),
            ("uncachedInputTokens", "uncached_input_tokens", "tokens"),
        ):
            if row.get(key) is not None:
                yield derive.Observation(
                    entity_id=entity_id,
                    metric=metric,
                    value=row[key],
                    unit=unit,
                    observed_at=snapshot_at,
                )

    # --- market share by lab, daily --------------------------------------
    # The per-day `tokens` total is not re-emitted: dailyTokens already owns
    # the entity `total`, and duplicating the same fact would double-count
    # under any naive group-by.
    for day in payload.get("marketShare", []):
        observed_at = f"{day['date']}T00:00:00Z"
        for lab in day.get("labs", []):
            entity_id = _lab_entity(lab["lab"])
            if lab.get("tokens") is not None:
                yield derive.Observation(
                    entity_id=entity_id,
                    metric="tokens",
                    value=lab["tokens"],
                    unit="tokens",
                    observed_at=observed_at,
                )
            if lab.get("sharePercent") is not None:
                yield derive.Observation(
                    entity_id=entity_id,
                    metric="share_pct",
                    value=lab["sharePercent"],
                    unit="percent",
                    observed_at=observed_at,
                )

    # --- geography --------------------------------------------------------
    for row in payload.get("countries", []):
        entity_id = f"country:{row['country']}"
        for key, metric, unit in (
            ("tokens", "tokens", "tokens"),
            ("sharePercent", "share_pct", "percent"),
        ):
            if row.get(key) is not None:
                yield derive.Observation(
                    entity_id=entity_id,
                    metric=metric,
                    value=row[key],
                    unit=unit,
                    observed_at=snapshot_at,
                )


derive.register("opencode-usage.v1", parse, PARSER_VERSION)
