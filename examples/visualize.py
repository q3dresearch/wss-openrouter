#!/usr/bin/env python3
"""Render charts from derived/observations/*.csv as SVG.

    python examples/visualize.py

  price-capability.svg   cost vs benchmark score. Marker colour = model
                         family, marker area = share of tokens, line = the
                         efficient frontier
  task-mix.svg           what people ask models to do, by share of tokens
  task-leaders.svg       who leads each workload, ranked by their grip on it
  task-contest.svg       workload size against how locked up it is — where
                         the open doors are
  session-cost.svg       median USD per session, by app, turn range and model

Reads the derived table, never the raw archive. Stdlib only, deterministic.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape


def _open_partition(path):
    """Open a derived partition, gzipped or not.

    Engine v0.6.34 made `derived/observations/*.csv.gz` the written form. Every
    reader in this repo went on globbing `*.csv`, found nothing, and said "no
    observations yet -- run capture + derive first" over a full archive. Stdlib
    only, so `head`/`zcat` remain the only tools a reader needs.
    """
    import gzip
    import io
    if str(path).endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", newline="")
    return open(path, encoding="utf-8", newline="")

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "examples" / "charts"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
HUE = "#2a78d6"
HUE_SOFT = "#9ec5f4"
# Blue / orange / aqua / violet — verified with the palette validator under
# --pairs all (worst CVD dE 9.2, worst normal-vision dE 16.3), so this set is
# safe even on a scatter, where every colour must differ from every other.
# A fifth would fail, so anything past four is deliberately grey.
FAMILY_SLOTS = ("#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7")
FAMILY_OTHER = "#b8b7b0"

# Macro category is a fixed, small set, so its colours are pinned rather than
# ranked: "Code" is always blue, in every chart, forever.
CATEGORY_COLOUR = {"code": "#2a78d6", "agent": "#eb6834", "general": "#1baf7a", "data": "#4a3aa7"}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

MACRO_LABEL = {"code": "Code", "agent": "Agent", "data": "Data", "general": "General"}

# One grouping by hand, because the session-cost data does not carry a lab
# headquarters field. The same set the openrouter-lab-share recipe uses.
CN_LABS = {
    "deepseek", "tencent", "xiaomi", "z-ai", "minimax", "alibaba", "moonshotai",
    "qwen", "stepfun", "baidu", "01-ai", "inclusionai", "dots-studio",
}
CN_COLOUR = "#eb6834"


def rows() -> list[dict]:
    out: list[dict] = []
    for partition in sorted((REPO / "derived" / "observations").glob("*.csv*")):
        with _open_partition(partition) as fh:
            out.extend(csv.DictReader(fh))
    return out


def latest_by_entity(all_rows, series: str) -> dict:
    """Most recently observed value of every metric, per entity, in one series."""
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    for r in all_rows:
        if r["series_id"] != series:
            continue
        key = (r["entity_id"], r["metric"])
        if key not in seen or r["observed_at"] > seen[key][0]:
            seen[key] = (r["observed_at"], r["value"])
    out: dict[str, dict] = defaultdict(dict)
    for (entity, metric), (_, value) in seen.items():
        out[entity][metric] = value
    return out


def svg_text(x, y, text, *, size, fill, anchor="start", weight="normal", tabular=False) -> str:
    style = "font-variant-numeric: tabular-nums;" if tabular else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family=\'{FONT}\' font-size="{size}" '
        f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" style="{style}">{escape(text)}</text>'
    )


def wrap(width, height, title, desc, body) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">\n'
        f"<title>{escape(title)}</title>\n<desc>{escape(desc)}</desc>\n"
        f'<rect width="{width}" height="{height}" fill="{SURFACE}"/>\n' + "\n".join(body) + "\n</svg>\n"
    )


def hbar(x, y, w, h, colour, r=4) -> str:
    r = min(r, max(w / 2, 0.1), h / 2)
    return (
        f'<path d="M{x:.1f},{y:.1f} h{w - r:.1f} q{r},0 {r},{r} v{h - 2 * r:.1f} '
        f'q0,{r} -{r},{r} h-{w - r:.1f} z" fill="{colour}"/>'
    )


def short_model(model_id: str) -> str:
    """Drop the org prefix and the -YYYYMMDD stamp; the date is noise here."""
    return re.sub(r"-\d{8}$", "", model_id.split("/")[-1])


def pretty(tag: str) -> str:
    macro, _, rest = tag.partition(":")
    if not rest:
        macro, rest = "", tag
    words = rest.replace("_", " ")
    label = words[:1].upper() + words[1:]
    return f"{MACRO_LABEL.get(macro, macro.title())} · {label}" if macro else label


def macro_of(tag: str) -> str:
    """Which macro category a task tag belongs to; unprefixed tags are general."""
    head = tag.split(":", 1)[0] if ":" in tag else ""
    return head if head in CATEGORY_COLOUR else "general"


def company_colours(volume: dict) -> dict:
    """Company -> colour, ranked by measured volume, top four only.

    Ranked rather than pinned because the field of vendors changes; the legend
    carries identity, so colour never has to be remembered between charts.
    Shared by every chart that colours by company so they always agree.
    """
    by_company: dict[str, float] = defaultdict(float)
    for model_id, vol in volume.items():
        by_company[model_id.split("/")[0]] += vol
    ranked = [c for c, _ in sorted(by_company.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {c: FAMILY_SLOTS[i] for i, c in enumerate(ranked[:4])}


def legend(items, y: float, x0: float = 24.0) -> list[str]:
    """A legend is always present for two or more colours."""
    out, x = [], x0
    for label, colour in items:
        out.append(f'<circle cx="{x + 5}" cy="{y - 4}" r="5" fill="{colour}"/>')
        out.append(svg_text(x + 15, y, label, size=11, fill=INK2))
        x += 15 + len(label) * 6.6 + 18
    return out


def cite(as_of: str) -> str:
    return f"Source: OpenRouter (openrouter.ai/rankings), as of {as_of}. Licensed under CC BY 4.0."


# ── task data ────────────────────────────────────────────────────────────────

def task_data(all_rows):
    """(task share, per-task model shares, as_of) from the classifications series."""
    cls = [r for r in all_rows if r["series_id"] == "openrouter.classifications.task"]
    if not cls:
        return {}, {}, ""
    as_of = max(r["observed_at"] for r in cls)
    share, per_task = {}, defaultdict(dict)
    for r in cls:
        if r["observed_at"] != as_of:
            continue
        e = r["entity_id"]
        if e.startswith("task:") and "/model:" in e and r["metric"] == "tag_token_share":
            tag, model = e[5:].split("/model:", 1)
            per_task[tag][model] = float(r["value"])
        elif e.startswith("task:") and "/" not in e and r["metric"] == "token_share":
            share[e[5:]] = float(r["value"])
    return share, per_task, as_of[:10]


def model_volume(all_rows) -> dict:
    """Approximate share of all tokens per model.

    Σ over tasks of (task's share of all tokens × model's share of that task).
    A lower bound: only models listed in a task's top-N contribute, so a model
    spread thinly across many tasks is undercounted.
    """
    share, per_task, _ = task_data(all_rows)
    volume: dict[str, float] = defaultdict(float)
    for tag, models in per_task.items():
        for model, within in models.items():
            volume[model] += share.get(tag, 0.0) * within
    return volume


def task_timeline(all_rows) -> list[dict]:
    """One deduplicated snapshot per classification week.

    The endpoint restates the same `observed_at` on every capture. Keep the
    latest `captured_at` for each (date, entity, metric), then group.
    """
    best: dict[tuple[str, str, str], dict] = {}
    for r in all_rows:
        if r["series_id"] != "openrouter.classifications.task":
            continue
        key = (r["observed_at"], r["entity_id"], r["metric"])
        if key not in best or r["captured_at"] > best[key]["captured_at"]:
            best[key] = r
    by_date: dict[str, dict] = defaultdict(
        lambda: {"share": {}, "usage": {}, "per_task": defaultdict(dict), "macro": {}}
    )
    for r in best.values():
        d = r["observed_at"][:10]
        e, m = r["entity_id"], r["metric"]
        v = float(r["value"])
        if m == "tag_token_share" and "/model:" in e:
            tag, model = e[5:].split("/model:", 1)
            by_date[d]["per_task"][tag][model] = v
        elif m == "tag_usage_share" and "/model:" in e:
            tag, model = e[5:].split("/model:", 1)
            by_date[d].setdefault("per_task_usage", {}).setdefault(tag, {})[model] = v
        elif m == "token_share" and e.startswith("task:") and "/" not in e:
            by_date[d]["share"][e[5:]] = v
        elif m == "usage_share" and e.startswith("task:") and "/" not in e:
            by_date[d]["usage"][e[5:]] = v
        elif m == "token_share" and e.startswith("macro:"):
            by_date[d]["macro"][e[6:]] = v
    return [{"date": d, **by_date[d]} for d in sorted(by_date)]


# ── charts ───────────────────────────────────────────────────────────────────

def price_capability(out: Path, all_rows) -> str:
    catalog = latest_by_entity(all_rows, "openrouter.models.catalog")
    bench = latest_by_entity(all_rows, "openrouter.benchmarks.artificial-analysis")
    slug_to_id = {v["canonical_slug"]: e for e, v in catalog.items() if "canonical_slug" in v}
    volume = model_volume(all_rows)
    # volume is keyed by dated permaslug; catalogue ids are undated aliases
    vol_by_id = {slug_to_id[s]: v for s, v in volume.items() if s in slug_to_id}

    points = []
    for slug, b in bench.items():
        model_id = slug_to_id.get(slug)
        if not model_id or "intelligence_index" not in b:
            continue
        price = catalog[model_id].get("price_prompt_usd_per_mtok")
        if price is None or float(price) <= 0:
            continue
        points.append((model_id, float(price), float(b["intelligence_index"]), vol_by_id.get(model_id, 0.0)))
    if len(points) < 5:
        return "price-capability.svg skipped: too few joined models yet"

    frontier = []
    for p in sorted(points, key=lambda t: (t[1], -t[2])):
        if not frontier or p[2] > frontier[-1][2]:
            frontier.append(p)
    frontier_ids = {p[0] for p in frontier}

    colour_of = company_colours({m: v for m, _, _, v in points})

    as_of = max(r["observed_at"] for r in all_rows if r["metric"] == "intelligence_index")[:10]
    width, height = 960.0, 560.0
    left, right, top, bottom = 62.0, 214.0, 108.0, 58.0
    lo, hi = min(p[1] for p in points), max(p[1] for p in points)
    smin, smax = min(p[2] for p in points), max(p[2] for p in points)
    vmax = max((p[3] for p in points), default=0) or 1

    x_of = lambda pr: left + (math.log10(pr) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * (width - left - right)  # noqa: E731
    y_of = lambda sc: (height - bottom) - (sc - smin) / max(1e-9, smax - smin) * (height - bottom - top)  # noqa: E731
    r_of = lambda vol: 4.0 + 11.0 * math.sqrt(vol / vmax)  # area ∝ volume  # noqa: E731

    body = [
        svg_text(24, 30, "What a point of intelligence costs", size=16, fill=INK, weight="600"),
        svg_text(24, 50, f"{len(points)} models priced and scored · snapshot {as_of}", size=12, fill=INK2),
        svg_text(24, 68, "vertical = Artificial Analysis intelligence index · line = efficient frontier · marker area = share of measured tokens", size=11, fill=MUTED),
    ]
    body += legend([(c, colour_of[c]) for c in colour_of] + [("other", FAMILY_OTHER)], 92)

    d = 10 ** math.floor(math.log10(lo))
    while d <= hi * 1.001:
        if d >= lo:
            gx = x_of(d)
            body.append(f'<line x1="{gx:.1f}" y1="{top - 8}" x2="{gx:.1f}" y2="{height - bottom}" stroke="{GRID}" stroke-width="1"/>')
            body.append(svg_text(gx, height - bottom + 18, f"${d:g}" if d >= 1 else f"${d:.2f}".rstrip("0").rstrip("."), size=10, fill=MUTED, anchor="middle", tabular=True))
        d *= 10
    for s in range(int(smin // 10 * 10), int(smax) + 10, 10):
        if smin <= s <= smax:
            gy = y_of(s)
            body.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{width - right}" y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
            body.append(svg_text(left - 8, gy + 3.5, str(s), size=10, fill=MUTED, anchor="end", tabular=True))
    body.append(svg_text((left + width - right) / 2, height - 14, "input price, USD per million tokens (log scale)", size=10, fill=MUTED, anchor="middle"))
    body.append(f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="{BASELINE}" stroke-width="1"/>')

    fpts = " ".join(f"{x_of(p[1]):.1f},{y_of(p[2]):.1f}" for p in frontier)
    body.append(f'<polyline points="{fpts}" fill="none" stroke="{HUE}" stroke-width="2" stroke-linejoin="round" opacity="0.5"/>')

    # biggest markers first so small ones stay clickable on top
    for model_id, price, score, vol in sorted(points, key=lambda t: -t[3]):
        col = colour_of.get(model_id.split("/")[0], FAMILY_OTHER)
        body.append(
            f'<circle cx="{x_of(price):.1f}" cy="{y_of(score):.1f}" r="{r_of(vol):.1f}" '
            f'fill="{col}" fill-opacity="{0.9 if model_id in frontier_ids else 0.55}" '
            f'stroke="{SURFACE}" stroke-width="2"/>'
        )

    placed: list[float] = []
    for model_id, price, score, _ in sorted(frontier, key=lambda t: -t[2]):
        x, y = x_of(price), y_of(score)
        ly = y
        while any(abs(ly - p) < 13 for p in placed):
            ly += 13
        placed.append(ly)
        body.append(f'<line x1="{x + 8}" y1="{y:.1f}" x2="{x + 14}" y2="{ly - 3.5:.1f}" stroke="{BASELINE}" stroke-width="1"/>')
        body.append(svg_text(x + 17, ly + 3.5, f"{short_model(model_id)}  ${price:.3g}", size=10, fill=INK, weight="600"))

    body.append(svg_text(24, height - 4, cite(as_of) + " Scores: Artificial Analysis.", size=9, fill=MUTED))
    out.write_text(wrap(width, height, "What a point of intelligence costs",
                        "Scatter of model benchmark score against input price; colour is model family, marker area is token share, line is the efficient frontier.", body), encoding="utf-8")
    return f"{out.relative_to(REPO)} — {len(points)} models, {len(frontier)} on the frontier, {len(colour_of)} companies coloured"


def task_mix(out: Path, all_rows, top_n: int = 4) -> str:
    """Composition over time, split by macro category.

    A ranked bar chart hides the only question a weekly series can answer:
    is a workload growing or shrinking? Each panel keeps its own y scale and
    labels the current share at the right.
    """
    timeline = task_timeline(all_rows)
    if len(timeline) < 3:
        return "task-mix.svg skipped: fewer than three classification weeks"
    dates = [s["date"] for s in timeline]
    latest = timeline[-1]
    if not latest["share"]:
        return "task-mix.svg skipped: no classification observations yet"
    macros = [c for c in ("code", "agent", "general", "data") if c in CATEGORY_COLOUR]

    width, height = 1060.0, 820.0
    left, right = 72.0, 24.0
    gap = 34.0
    panel_w = (width - left - right - gap) / 2
    panel_h = 250.0
    row_y = (154.0, 456.0)
    plot_h = 176.0
    label_w = 132.0
    span = panel_w - 16 - label_w

    body = [
        svg_text(24, 30, "What people actually ask models to do", size=16, fill=INK, weight="600"),
        svg_text(24, 50, f"Share of all OpenRouter tokens over {len(timeline)} weekly captures, split by macro category",
                  size=12, fill=INK2),
        svg_text(24, 70, "Each line is one workload. The y scale differs by panel; the current share is labelled at the right.",
                  size=11, fill=MUTED),
        svg_text(24, 90, " · ".join(f"{MACRO_LABEL[k]} {latest['macro'].get(k, 0) * 100:.0f}%"
                                   for k in macros), size=12, fill=INK2, weight="600"),
    ]
    body += legend([(MACRO_LABEL[k], CATEGORY_COLOUR[k]) for k in macros], 114)

    for pi, macro in enumerate(macros):
        col, row = pi % 2, pi // 2
        x0, y0 = left + col * (panel_w + gap), row_y[row]
        plot_right = x0 + span
        tasks = sorted(((t, s) for t, s in latest["share"].items() if macro_of(t) == macro),
                       key=lambda kv: -kv[1])[:top_n]
        if not tasks:
            continue
        vmax = max(s["share"].get(tag, 0) for s in timeline for tag, _ in tasks) * 1.22
        if not vmax:
            continue
        y_of = lambda v: y0 + plot_h - v / vmax * plot_h  # noqa: E731
        body.append(svg_text(x0, y0 - 18, f"{MACRO_LABEL[macro]} · {latest['macro'].get(macro, 0) * 100:.1f}% of tokens",
                             size=13, fill=CATEGORY_COLOUR[macro], weight="600"))
        body.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + plot_h}" stroke="{BASELINE}" stroke-width="1"/>')
        body.append(f'<line x1="{x0}" y1="{y0 + plot_h}" x2="{plot_right}" y2="{y0 + plot_h}" stroke="{BASELINE}" stroke-width="1"/>')
        for f in (0.0, 0.5, 1.0):
            gy = y0 + plot_h - f * plot_h
            body.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{plot_right}" y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
            body.append(svg_text(x0 - 8, gy + 3.5, f"{vmax * f * 100:.1f}%", size=9.5, fill=MUTED,
                                 anchor="end", tabular=True))
        for i, d in enumerate(dates):
            gx = x0 + i / max(1, len(dates) - 1) * span
            body.append(f'<line x1="{gx:.1f}" y1="{y0}" x2="{gx:.1f}" y2="{y0 + plot_h}" stroke="{GRID}" stroke-width="1"/>')
        body.append(svg_text(x0 + span / 2, y0 + plot_h + 18, "trailing 7 days", size=9.5, fill=MUTED, anchor="middle"))

        ends = []
        for ti, (tag, _) in enumerate(tasks):
            pts = [(x0 + i / max(1, len(dates) - 1) * span, y_of(s["share"].get(tag, 0)))
                   for i, s in enumerate(timeline)]
            colour = CATEGORY_COLOUR[macro]
            body.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" '
                        f'fill="none" stroke="{colour}" stroke-width="2.1" stroke-opacity="{0.95 - ti * 0.16:.2f}" '
                        'stroke-linejoin="round" stroke-linecap="round"/>')
            body.append(f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3.4" fill="{colour}" '
                        f'stroke="{SURFACE}" stroke-width="1.5"/>')
            ends.append((pts[-1][1], f"{pretty(tag)[:25]}", latest["share"].get(tag, 0), ti))

        # Right-hand labels, pushed apart without hiding a series.
        placed = []
        for y1, label, val, ti in sorted(ends, key=lambda t: t[0]):
            y = max(y0 + 12, y1)
            if placed and y < placed[-1] + 15:
                y = placed[-1] + 15
            placed.append(y)
            overflow = placed[-1] - (y0 + plot_h - 2)
            if overflow > 0:
                placed = [yy - overflow for yy in placed]
        for (y1, label, val, ti), y in zip(sorted(ends, key=lambda t: t[0]), placed):
            lx = plot_right + 10
            body.append(f'<line x1="{plot_right + 2}" y1="{y1:.1f}" x2="{lx - 3}" y2="{y:.1f}" stroke="{BASELINE}" stroke-width="1"/>')
            body.append(svg_text(lx, y + 3.5, f"{label}  {val * 100:.1f}%", size=9.5, fill=INK2))
        if row == 1:
            for i, d in enumerate(dates):
                if i in (0, 2, 4, 6, len(dates) - 1):
                    gx = x0 + i / max(1, len(dates) - 1) * span
                    body.append(svg_text(gx, y0 + plot_h + 40, d[5:], size=9, fill=MUTED,
                                         anchor="middle", tabular=True))

    body.append(svg_text(24, height - 60,
                         f"Agent workflow execution is still the largest single workload at "
                         f"{latest['share'].get('agent:workflow_execution', 0) * 100:.1f}%. "
                         f"General tasks are {latest['macro'].get('general', 0) * 100:.0f}% of tokens; "
                         f"Data is {latest['macro'].get('data', 0) * 100:.0f}%.", size=11.5, fill=INK, weight="600"))
    body.append(svg_text(24, height - 38,
                         "A flat line is a finding: most workloads moved by a few points over the record. "
                         "The classification endpoint restates a trailing week, so the latest capture is the current view.",
                         size=10, fill=MUTED))
    body.append(svg_text(24, height - 8, cite(dates[-1]), size=9.5, fill=MUTED))
    out.write_text(wrap(width, height, "What people actually ask models to do",
                        "Small-multiple trend charts of OpenRouter token share by workload, split by macro category.",
                        body), encoding="utf-8")
    return f"{out.relative_to(REPO)} — {len(timeline)} weeks, {sum(min(top_n, len([t for t in latest['share'] if macro_of(t) == m])) for m in macros)} workloads"


def task_leaders(out: Path, all_rows, top_n: int = 3) -> str:
    """Leading model's grip over time, split by macro category.

    The old chart answered "who leads now". This one answers "how often does
    the answer change": every marker is a week's leader, coloured by lab, and
    the thin line is the workload's share of all tokens on a second axis.
    """
    timeline = task_timeline(all_rows)
    if len(timeline) < 3:
        return "task-leaders.svg skipped: fewer than three classification weeks"
    dates = [s["date"] for s in timeline]
    latest = timeline[-1]
    if not latest["per_task"]:
        return "task-leaders.svg skipped: no classification observations yet"
    macros = [c for c in ("code", "agent", "general", "data") if c in CATEGORY_COLOUR]
    colour_of = company_colours(model_volume(all_rows))

    def leader_at(snap, tag):
        models = snap["per_task"].get(tag, {})
        if not models:
            return None, 0.0
        model, share = max(models.items(), key=lambda kv: kv[1])
        return model, share

    changed = 0
    for tag in latest["share"]:
        seen = {leader_at(s, tag)[0] for s in timeline if leader_at(s, tag)[0]}
        if len(seen) > 1:
            changed += 1

    width, height = 1060.0, 1120.0
    left, right = 74.0, 276.0
    panel_h, gap = 170.0, 40.0
    first_y = 190.0
    span = width - left - right

    body = [
        svg_text(24, 30, "Who leads each workload — and how often the answer changes", size=16, fill=INK, weight="600"),
        svg_text(24, 50, f"Each line is a workload's leading-model share over {len(timeline)} weekly captures, grouped by macro category",
                 size=12, fill=INK2),
        svg_text(24, 70, "Marker fill = that week's leading lab. The thin, faint line is the workload's share of all tokens on a second axis.",
                 size=11, fill=MUTED),
        svg_text(24, 90, f"{changed} of {len([t for t in latest['share'] if latest['per_task'].get(t)])} workloads changed leader at least once; the top three per category are shown.",
                 size=12, fill=INK, weight="600"),
    ]
    seen_co = [c for c in colour_of]
    body += legend([(c, colour_of[c]) for c in seen_co] + [("other lab", FAMILY_OTHER)], 114)

    for pi, macro in enumerate(macros):
        y0 = first_y + pi * (panel_h + gap)
        tasks = sorted(((t, s) for t, s in latest["share"].items()
                        if macro_of(t) == macro and latest["per_task"].get(t)),
                       key=lambda kv: -kv[1])[:top_n]
        if not tasks:
            continue
        y2max = max(max(s["share"].get(t, 0) for s in timeline) for t, _ in tasks) * 1.3
        y1 = lambda v: y0 + panel_h - v * panel_h  # noqa: E731
        y2 = lambda v: y0 + panel_h - v / y2max * panel_h if y2max else y0 + panel_h  # noqa: E731
        body.append(svg_text(left, y0 - 26, f"{MACRO_LABEL[macro]} · {latest['macro'].get(macro, 0) * 100:.1f}% of all tokens",
                             size=13, fill=CATEGORY_COLOUR[macro], weight="600"))
        body.append(svg_text(width - right + 14, y0 + 12, f"thin: 0–{y2max * 100:.0f}% of tokens",
                             size=9, fill=MUTED, anchor="start"))
        body.append(f'<line x1="{left}" y1="{y0}" x2="{left}" y2="{y0 + panel_h}" stroke="{BASELINE}" stroke-width="1"/>')
        body.append(f'<line x1="{left}" y1="{y0 + panel_h}" x2="{left + span}" y2="{y0 + panel_h}" stroke="{BASELINE}" stroke-width="1"/>')
        for f in (0.0, 0.5, 1.0):
            gy = y1(f)
            body.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{left + span}" y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
            body.append(svg_text(left - 8, gy + 3.5, f"{f * 100:.0f}%", size=9.5, fill=MUTED,
                                 anchor="end", tabular=True))
        for i, d in enumerate(dates):
            gx = left + i / max(1, len(dates) - 1) * span
            body.append(f'<line x1="{gx:.1f}" y1="{y0}" x2="{gx:.1f}" y2="{y0 + panel_h}" stroke="{GRID}" stroke-width="1"/>')

        ends = []
        for ti, (tag, _) in enumerate(tasks):
            leader_pts = []
            for i, s in enumerate(timeline):
                model, share = leader_at(s, tag)
                if model:
                    leader_pts.append((left + i / max(1, len(dates) - 1) * span, y1(share), model, share))
            if not leader_pts:
                continue
            colour = CATEGORY_COLOUR[macro]
            body.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in leader_pts)}" '
                        f'fill="none" stroke="{colour}" stroke-width="{2.3 - ti * 0.22:.2f}" '
                        f'stroke-opacity="{0.95 - ti * 0.14:.2f}" stroke-linejoin="round" stroke-linecap="round"/>')
            # Thin y2 line for the workload's share of all tokens.
            thin = [(left + i / max(1, len(dates) - 1) * span, y2(s["share"].get(tag, 0)))
                    for i, s in enumerate(timeline)]
            body.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in thin)}" '
                        f'fill="none" stroke="{colour}" stroke-width="1" stroke-opacity="0.24" '
                        'stroke-linejoin="round" stroke-linecap="round"/>')
            for x, yy, model, share in leader_pts:
                body.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="3.7" '
                            f'fill="{colour_of.get(model.split("/")[0], FAMILY_OTHER)}" '
                            f'stroke="{SURFACE}" stroke-width="1.6"/>')
            model, share = leader_pts[-1][2], leader_pts[-1][3]
            ends.append((leader_pts[-1][1], tag, model, share, ti))

        placed = []
        for yy, tag, model, share, ti in sorted(ends, key=lambda t: t[0]):
            y = max(y0 + 14, yy)
            if placed and y < placed[-1] + 26:
                y = placed[-1] + 26
            placed.append(y)
            overflow = placed[-1] - (y0 + panel_h - 4)
            if overflow > 0:
                placed = [v - overflow for v in placed]
        for (yy, tag, model, share, ti), ly in zip(sorted(ends, key=lambda t: t[0]), placed):
            lx = width - right + 14
            body.append(f'<line x1="{left + span + 2}" y1="{yy:.1f}" x2="{lx - 3}" y2="{ly - 3:.1f}" '
                        f'stroke="{BASELINE}" stroke-width="1"/>')
            body.append(svg_text(lx, ly, f"{pretty(tag)[:25]}  {share * 100:.0f}%", size=9.5, fill=INK2))
            body.append(svg_text(lx, ly + 11, short_model(model)[:24], size=9, fill=MUTED))
        if pi == len(macros) - 1:
            for i, d in enumerate(dates):
                if i in (0, 2, 4, 6, len(dates) - 1):
                    gx = left + i / max(1, len(dates) - 1) * span
                    body.append(svg_text(gx, y0 + panel_h + 40, d[5:], size=9, fill=MUTED,
                                         anchor="middle", tabular=True))

    body.append(svg_text(24, height - 64,
                         "Every line is a leading model's share OF ITS OWN WORKLOAD, not a share of the whole market. "
                         "A flat, high line is a defended niche; a low, jumpy line is contested.", size=11, fill=INK, weight="600"))
    body.append(svg_text(24, height - 42,
                         "The thin line lets a shrinking workload keep a high leader share. Marker colours are a lab, not a model: "
                         "two DeepSeek snapshots are both blue.", size=10, fill=MUTED))
    body.append(svg_text(24, height - 8, cite(dates[-1]), size=9.5, fill=MUTED))
    out.write_text(wrap(width, height, "Who leads each workload",
                        "Small-multiple line charts of the leading model's share of each OpenRouter workload over time, with lab-coloured markers and workload token share on a second axis.",
                        body), encoding="utf-8")
    return f"{out.relative_to(REPO)} — {len(timeline)} weeks, {changed} workloads changed leader"


def task_contest(out: Path, all_rows) -> str:
    """Workload size against how locked up it is: the top-right is defended,
    the top-left is a big contested opening. Bubble area adds request length:
    token share ÷ usage share, indexed to the all-workload average.
    """
    share, per_task, as_of = task_data(all_rows)
    timeline = task_timeline(all_rows)
    usage = timeline[-1]["usage"] if timeline else {}
    pts = []
    for t, s in share.items():
        if not per_task.get(t) or s <= 0.005 or not usage.get(t):
            continue
        pts.append((t, s, max(per_task[t].values()), s / usage[t]))
    if len(pts) < 4:
        return "task-contest.svg skipped: too few tasks yet"

    width, height = 900.0, 520.0
    left, right, top, bottom = 128.0, 40.0, 148.0, 58.0
    xmax = max(p[2] for p in pts) * 1.12
    ymax = max(p[1] for p in pts) * 1.12
    amax = max(p[3] for p in pts) or 1
    x_of = lambda v: left + v / xmax * (width - left - right)  # noqa: E731
    y_of = lambda v: (height - bottom) - v / ymax * (height - bottom - top)  # noqa: E731
    r_of = lambda v: max(2.8, 15.0 * math.sqrt(v / amax))  # area ∝ tokens per request  # noqa: E731

    body = [
        svg_text(24, 30, "Where the open doors are", size=16, fill=INK, weight="600"),
        svg_text(24, 50, f"workload size against how much the leading model holds · trailing 7 days to {as_of}", size=12, fill=INK2),
        svg_text(24, 70, "up and to the LEFT = a big workload nobody owns · bubble area = tokens per request, indexed to the all-workload average",
                  size=11, fill=MUTED),
    ]
    body += legend([(MACRO_LABEL[k], CATEGORY_COLOUR[k]) for k in ("code", "agent", "general", "data")], 94)
    # Bubble-size key: area is proportional, so the radius key uses sqrt.
    bx = width - 190
    body.append(svg_text(bx, 90, "tokens per request", size=10, fill=MUTED))
    for i, v in enumerate((0.5, 1.0, 3.0)):
        cx = bx + 10 + i * 58
        body.append(f'<circle cx="{cx}" cy="112" r="{r_of(v):.1f}" fill="none" stroke="{MUTED}" stroke-width="1"/>')
        body.append(svg_text(cx, 132, f"{v:g}×", size=9.5, fill=MUTED, anchor="middle"))
    xstep = 0.05
    while xmax / xstep > 8:
        xstep *= 2
    ystep = 0.05
    while ymax / ystep > 8:
        ystep *= 2
    body.append(svg_text(left, height - bottom + 18, "0%", size=10, fill=MUTED, anchor="middle", tabular=True))
    frac = xstep
    while frac <= xmax:
        gx = x_of(frac)
        body.append(f'<line x1="{gx:.1f}" y1="{top - 8}" x2="{gx:.1f}" y2="{height - bottom}" stroke="{GRID}" stroke-width="1"/>')
        body.append(svg_text(gx, height - bottom + 18, f"{frac * 100:.0f}%", size=10, fill=MUTED, anchor="middle", tabular=True))
        frac += xstep
    frac = ystep
    while frac <= ymax:
        gy = y_of(frac)
        body.append(f'<line x1="{left}" y1="{gy:.1f}" x2="{width - right}" y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
        body.append(svg_text(left - 8, gy + 3.5, f"{frac * 100:.0f}%", size=10, fill=MUTED, anchor="end", tabular=True))
        frac += ystep
    body.append(svg_text(left - 8, top - 12, "share of all tokens", size=10, fill=MUTED, anchor="end"))
    body.append(svg_text((left + width - right) / 2, height - 14, "leading model's share of that workload (more locked up)", size=10, fill=MUTED, anchor="middle"))
    body.append(f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="{BASELINE}" stroke-width="1"/>')

    for tag, size, lead, avg in sorted(pts, key=lambda p: -p[3]):
        x, y = x_of(lead), y_of(size)
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r_of(avg):.1f}" fill="{CATEGORY_COLOUR[macro_of(tag)]}" '
                    f'fill-opacity="0.78" stroke="{SURFACE}" stroke-width="2"/>')

    # Label the biggest workloads only, and never clip a word: a half-written
    # label reads worse than none. The rest are carried by the legend.
    placed: list[tuple[float, float, float]] = []
    for tag, size, lead, avg in sorted(pts, key=lambda p: -p[1])[:10]:
        x, y = x_of(lead), y_of(size)
        label = pretty(tag)
        w = len(label) * 5.6
        if x + r_of(avg) + 9 + w > width - right:
            lx, anchor, x0, x1 = x - r_of(avg) - 9 - w, "end", x - r_of(avg) - 9 - w, x - r_of(avg) - 9
        else:
            lx, anchor, x0, x1 = x + r_of(avg) + 9, "start", x + r_of(avg) + 9, x + r_of(avg) + 9 + w
        if any(abs(y - py) < 12 and not (x1 < bx0 or x0 > bx1) for bx0, bx1, py in placed):
            continue
        body.append(svg_text(x - r_of(avg) - 9 if anchor == "end" else lx, y + 3.5, label, size=10, fill=INK2, anchor=anchor))
        placed.append((x0, x1, y))
    body.append(svg_text(24, height - 4, cite(as_of) + " Bubble is token share ÷ usage share; 1× is the all-workload average.", size=10, fill=MUTED))
    out.write_text(wrap(width, height, "Where the open doors are",
                        "Scatter of workload size against the leading model's share; bubble area is tokens per request indexed to the all-workload average.",
                        body), encoding="utf-8")
    return f"{out.relative_to(REPO)} — {len(pts)} workloads, {max(amax, 1):.1f}× longest"


TURN_ORDER = ["1-turn", "2-9-turns", "10-49-turns", "50-plus-turns"]
TURN_LABEL = {"1-turn": "1", "2-9-turns": "2–9", "10-49-turns": "10–49", "50-plus-turns": "50+"}
APP_ORDER = [("kilo-code", "Kilo Code"), ("codex", "Codex"),
             ("claude-code", "Claude Code"), ("hermes-agent", "Hermes Agent")]


def _session_cost_data(all_rows):
    """(app -> model -> turn range -> median USD, as_of) from one snapshot."""
    sc = [r for r in all_rows if r["series_id"] == "openrouter.sessions.cost"]
    if not sc:
        return {}, ""
    as_of = max(r["observed_at"] for r in sc)
    apps: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for r in sc:
        if r["observed_at"] != as_of:
            continue
        e = r["entity_id"]
        if not e.startswith("app:") or "/turns:" not in e or "/model:" not in e:
            continue
        app, rest = e[4:].split("/turns:", 1)
        turns, model = rest.split("/model:", 1)
        try:
            value = float(r["value"])
        except (TypeError, ValueError):
            continue
        if value > 0:
            apps[app][model][turns] = value
    return apps, as_of[:10]


def _usd(v: float) -> str:
    """Compact money labels: enough digits to keep the small end legible."""
    if v >= 1:
        return f"${v:,.2f}"
    if v >= 0.1:
        return f"${v:.3f}"
    if v >= 0.01:
        return f"${v:.4f}"
    return f"${v:.6f}"


def _axis_usd(v: float) -> str:
    return "$" + f"{v:.10f}".rstrip("0").rstrip(".")


def _spread(v: float) -> str:
    return f"{v:,.0f}×" if v >= 10 else f"{v:.1f}×"


def session_cost(out: Path, all_rows) -> str:
    """The spread list prices cannot show: one session, by model and length.

    Each line is a model inside one app. The right edge is where a long session
    lands, and the vertical distance there is the cost decision. Apps publish
    different turn ranges, so a panel with more points is not a better app.
    """
    apps, as_of = _session_cost_data(all_rows)
    panels = []
    for slug, name in APP_ORDER:
        models = apps.get(slug) or {}
        lines = {m: s for m, s in models.items() if len(s) >= 2}
        if not lines:
            continue
        ranges = [t for t in TURN_ORDER if any(t in s for s in lines.values())]
        if len(ranges) < 2:
            continue
        ends = [(s[ranges[-1]], m) for m, s in lines.items() if ranges[-1] in s]
        if not ends:
            continue
        lo_v, lo_m = min(ends)
        hi_v, hi_m = max(ends)
        panels.append((slug, name, lines, ranges, lo_v, lo_m, hi_v, hi_m, hi_v / lo_v))
    if not panels:
        return "session-cost.svg skipped: no session-cost observations yet"

    values = [v for _, _, lines, _, _, _, _, _, _ in panels
              for s in lines.values() for v in s.values() if v > 0]
    lo, hi = min(values) * 0.55, max(values) * 1.55
    log_lo, log_hi = math.log10(lo), math.log10(hi)

    width, panel_h, gap = 1260.0, 290.0, 44.0
    panel_w = 250.0
    total_w = len(panels) * panel_w + (len(panels) - 1) * gap
    left = max(76.0, (width - total_w) / 2)
    panel_top = 165.0
    panel_bottom = panel_top + panel_h
    height = 660.0

    y_of = lambda v: panel_bottom - (math.log10(v) - log_lo) / (log_hi - log_lo) * panel_h  # noqa: E731

    worst = max(panels, key=lambda p: p[8])
    title = f"At the longest published session, the model you pick changes the cost by up to {_spread(worst[8])}"
    body = [
        svg_text(24, 30, title, size=16, fill=INK, weight="600"),
        svg_text(24, 52, f"median USD per session · log scale · trailing 30-day window to {as_of} · each line is one model in one app", size=12, fill=INK2),
        svg_text(24, 72, "vertical distance at the right edge is the whole argument; apps publish different turn ranges, so compare within a panel", size=11, fill=MUTED),
    ]
    body += legend([("Chinese lab", CN_COLOUR), ("other lab", HUE)], 96)

    for i, (slug, name, lines, ranges, lo_v, lo_m, hi_v, hi_m, spread) in enumerate(panels):
        x0 = left + i * (panel_w + gap)
        x1 = x0 + panel_w
        x_of = lambda idx, x0=x0: x0 + 22 + (idx / max(1, len(ranges) - 1)) * (panel_w - 44)  # noqa: E731

        body.append(svg_text(x0, 132, name, size=12.5, fill=INK, weight="600"))
        body.append(svg_text(x0, 148, f"{len(lines)} models · {len(ranges)} turn ranges", size=10, fill=MUTED))

        p = 10 ** math.floor(math.log10(lo))
        while p <= hi * 1.001:
            if p >= lo:
                gy = y_of(p)
                body.append(f'<line x1="{x0:.1f}" y1="{gy:.1f}" x2="{x1:.1f}" y2="{gy:.1f}" stroke="{GRID}" stroke-width="1"/>')
                if i == 0:
                    body.append(svg_text(x0 - 8, gy + 3.5, _axis_usd(p), size=9.5, fill=MUTED, anchor="end", tabular=True))
            p *= 10
        body.append(f'<line x1="{x0:.1f}" y1="{panel_bottom}" x2="{x1:.1f}" y2="{panel_bottom}" stroke="{BASELINE}" stroke-width="1"/>')

        for idx, t in enumerate(ranges):
            gx = x_of(idx)
            body.append(f'<line x1="{gx:.1f}" y1="{panel_bottom}" x2="{gx:.1f}" y2="{panel_bottom - 4}" stroke="{BASELINE}" stroke-width="1"/>')
            body.append(svg_text(gx, panel_bottom + 17, TURN_LABEL[t], size=10, fill=MUTED, anchor="middle", tabular=True))
        body.append(svg_text(x0 + panel_w / 2, panel_bottom + 35, "turns in the session", size=9.5, fill=MUTED, anchor="middle"))

        for model, series in sorted(lines.items()):
            pts = [(x_of(ranges.index(t)), y_of(series[t])) for t in ranges if t in series and series[t] > 0]
            if len(pts) < 2:
                continue
            lab = model.split("/")[0]
            colour = CN_COLOUR if lab in CN_LABS else HUE
            points = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            body.append(f'<polyline points="{points}" fill="none" stroke="{colour}" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round" opacity="0.55"/>')

        last_x = x_of(len(ranges) - 1)
        for v, m, label_above in ((hi_v, hi_m, True), (lo_v, lo_m, False)):
            y = y_of(v)
            colour = CN_COLOUR if m.split("/")[0] in CN_LABS else HUE
            body.append(f'<circle cx="{last_x:.1f}" cy="{y:.1f}" r="5" fill="{colour}" stroke="{SURFACE}" stroke-width="2"/>')
            # Keep labels inside the panel and out of the title band.
            above = label_above and y - 28 > panel_top + 6
            if not label_above and y + 34 > panel_bottom - 4:
                above = True
            vy, my = (y - 18, y - 6) if above else (y + 15, y + 27)
            anchor = "start"
            lx = last_x + 9
            if lx + 92 > x1 - 4:
                anchor, lx = "end", last_x - 9
            body.append(svg_text(lx, vy, _usd(v), size=9.5, fill=INK, anchor=anchor, weight="600", tabular=True))
            body.append(svg_text(lx, my, short_model(m)[:22], size=9, fill=INK2, anchor=anchor))

        body.append(svg_text(x0 + panel_w / 2, panel_bottom + 54, f"{_spread(spread)} spread at {TURN_LABEL[ranges[-1]]} turns", size=10.5, fill=INK2, anchor="middle", weight="600"))

    short_ranges = [(name, TURN_LABEL[ranges[-1]]) for _, name, _, ranges, *_ in panels
                    if TURN_ORDER.index(ranges[-1]) < len(TURN_ORDER) - 1]
    short_note = ""
    if short_ranges:
        short_note = " " + "; ".join(f"{name} publishes only to {label} turns" for name, label in short_ranges) + ", so those spreads cover a shorter session."

    body += [
        f'<line x1="24" y1="{panel_bottom + 82}" x2="{width - 24}" y2="{panel_bottom + 82}" stroke="{BASELINE}" stroke-width="1"/>',
        svg_text(24, panel_bottom + 106, f"In {worst[1]} at {TURN_LABEL[worst[3][-1]]} turns, a session costs {_usd(worst[4])} on {short_model(worst[5])} and {_usd(worst[6])} on {short_model(worst[7])} — a {_spread(worst[8])} spread.", size=12, fill=INK, weight="600"),
        svg_text(24, panel_bottom + 126, "Median session cost at list price, for the models each app actually serves. Not a benchmark of the models and not a claim about quality.", size=10.5, fill=INK2),
        svg_text(24, panel_bottom + 144, "Orange marks a Chinese lab; the grouping is by lab headquarters, not by where the inference runs." + short_note, size=10.5, fill=MUTED),
        svg_text(24, height - 4, f"Source: OpenRouter Data API, as of {as_of}. Licensed under CC BY 4.0.", size=9.5, fill=MUTED),
    ]
    out.write_text(wrap(width, height, "What an agent session costs",
                        "Line chart of median session cost by app, model and turn range, on a log scale; the spread at the longest published turn range is the finding.", body), encoding="utf-8")
    return f"{out.relative_to(REPO)} — {len(panels)} apps, {sum(len(p[2]) for p in panels)} model lines"


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows = rows()
    if not all_rows:
        print("no observations yet — run capture + derive first")
        return 1
    print(price_capability(OUT_DIR / "price-capability.svg", all_rows))
    print(task_mix(OUT_DIR / "task-mix.svg", all_rows))
    print(task_leaders(OUT_DIR / "task-leaders.svg", all_rows))
    print(task_contest(OUT_DIR / "task-contest.svg", all_rows))
    print(session_cost(OUT_DIR / "session-cost.svg", all_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
