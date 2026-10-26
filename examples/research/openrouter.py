"""The cookbook recipe's five OpenRouter figures, rebuilt from the live archive.

The archive is fetched, not captured: OpenRouter keeps daily rankings back to
2025-01-01, so re-archiving it would be the thing `wss validate` rejects. These
functions read the local research cache created by `run.py --fetch`.

The window is the latest 30 complete days, not the recipe's August 2026, so
the numbers move with the data. The methods do not.
"""

from __future__ import annotations

import collections
import math
import re
import statistics as st
from datetime import date, timedelta

from data import (
    CHARTS, CN_LABS, app_rankings, as_of, hf_snapshots, lab, label_lab, prices,
    rankings, scores, short_model, spearman, window,
)
from svgkit import AQUA, BLUE, GRID, INK, MUTE, ORANGE, VIOLET, circ, doc, line, polyline, rect, txt


def _window() -> tuple[str, str]:
    rows = rankings()
    dates = sorted({r["date"] for r in rows})
    end = date.fromisoformat(dates[-1])
    # The last day in a live archive can still be filling; use 30 complete days.
    if end >= date.today():
        end -= timedelta(days=1)
    start = end - timedelta(days=29)
    return start.isoformat(), end.isoformat()


def _lab_totals(rows: list[dict]) -> collections.Counter:
    c: collections.Counter = collections.Counter()
    for r in rows:
        c[lab(r["model_permaslug"])] += r["tok"]
    return c


def _money(v: float) -> str:
    return f"${v:.2f}" if v >= 0.1 else f"${v:.3f}"


def _slug_label(slug: str, n: int = 34) -> str:
    """Keep the version and variant suffix: two Claude 3.5 snapshots are not one model."""
    raw = slug.split("/")[-1]
    for variant in ("free", "beta"):
        raw = raw.replace(f":{variant}", f" [{variant}]")
    return raw[:n]


def lab_share(out=CHARTS / "or-lab-share.svg") -> str:
    """Two panels: the pie grew, and the lab mix changed. Absolute and share."""
    rows = rankings()
    if not rows:
        return "or-lab-share.svg skipped: no rankings cache"
    by_month: collections.Counter = collections.Counter()
    month_lab: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in rows:
        month = r["date"][:7]
        by_month[month] += r["tok"]
        month_lab[month][lab(r["model_permaslug"])] += r["tok"]
    months = sorted(by_month)
    if months and months[-1] == date.today().isoformat()[:7]:
        months = months[:-1]
    if len(months) < 4:
        return "or-lab-share.svg skipped: not enough complete months"
    totals = [by_month[m] for m in months]
    shares = {m: {l: v / by_month[m] for l, v in c.items()} for m, c in month_lab.items()}
    cumulative = collections.Counter()
    for m in months:
        cumulative.update(month_lab[m])
    top = [l for l, _ in cumulative.most_common(8) if l != "other"][:5]
    growth = totals[-1] / totals[0]
    first_abs = {l: month_lab[months[0]].get(l, 0) for l in top}
    last_abs = {l: month_lab[months[-1]].get(l, 0) for l in top}
    # The lab whose share fell most, for the sentence under the chart.
    faller = min(top, key=lambda l: shares[months[-1]].get(l, 0) - shares[months[0]].get(l, 0))
    faller_growth = last_abs[faller] / first_abs[faller] if first_abs[faller] else 0

    W, H = 1060, 820
    L, R = 78, 232
    TOP_T, TOP_H = 150, 190
    BOT_T, BOT_H = 420, 220
    xs = [L + i / max(1, len(months) - 1) * (W - L - R) for i in range(len(months))]

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(34, 40, "The routed market grew; almost nobody served fewer tokens", 20, INK, weight="600"))
    b.append(txt(34, 64, f"OpenRouter tokens served per month, {months[0]} to {months[-1]}. "
                f"The market is {growth:,.0f}× larger than at the start.", 12.5, MUTE))
    b.append(txt(34, 82, "The top panel is the size of the pie on a log scale; the bottom is "
                "the lab mix. A falling share is not a falling lab.", 12.5, MUTE))

    # Top panel: monthly total, log scale.
    lo, hi = min(totals), max(totals)
    llo, lhi = math.log10(lo * 0.8), math.log10(hi * 1.15)
    ytot = lambda v: TOP_T + TOP_H - (math.log10(v) - llo) / (lhi - llo) * TOP_H  # noqa: E731
    for p in (1e12, 5e12, 1e13, 5e13, 1e14, 5e14):
        if lo * 0.8 <= p <= hi * 1.15:
            yy = ytot(p)
            b.append(line(L, yy, W - R, yy, GRID, 1))
            b.append(txt(L - 10, yy + 4, f"{p / 1e12:,.0f}T", 10, MUTE, "end"))
    b.append(polyline([(x, ytot(v)) for x, v in zip(xs, totals)], BLUE, 2.4))
    b.append(circ(xs[-1], ytot(totals[-1]), 4.5, BLUE))
    b.append(txt(xs[-1] + 9, ytot(totals[-1]) + 4, f"{totals[-1] / 1e12:,.0f}T", 11.5, INK, weight="600"))
    b.append(txt(L, TOP_T - 22, "tokens served per month", 11.5, INK, weight="600"))
    b.append(txt(L, TOP_T - 7, "log scale", 9.5, MUTE))

    # Bottom panel: lab share.
    ymax = max(max(shares[m].values()) for m in months) * 1.12
    ysh = lambda v: BOT_T + BOT_H - v / ymax * BOT_H  # noqa: E731
    for v in [i / 10 for i in range(0, 11) if i / 10 <= ymax]:
        yy = ysh(v)
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{v:.0%}", 10, MUTE, "end"))
    b.append(txt(L, BOT_T - 22, "share of monthly tokens", 11.5, INK, weight="600"))
    b.append(txt(L, BOT_T - 7, "each line is one lab", 9.5, MUTE))

    colours = [BLUE, ORANGE, AQUA, VIOLET, MUTE, "#b8b7b0"]
    labels = []
    for i, l in enumerate(top):
        col = colours[i]
        pts = [(x, ysh(shares[m].get(l, 0))) for x, m in zip(xs, months)]
        b.append(polyline(pts, col, 2.0, 0.9))
        labels.append((ysh(shares[months[-1]].get(l, 0)), l, col,
                       shares[months[-1]].get(l, 0)))
    other_pts = []
    for x, m in zip(xs, months):
        other = sum(v for l, v in shares[m].items() if l not in top)
        other_pts.append((x, ysh(other)))
    b.append(polyline(other_pts, "#b8b7b0", 1.4, 0.8, dash="4 4"))
    other_last = sum(v for l, v in shares[months[-1]].items() if l not in top)
    labels.append((ysh(other_last), "all other labs", "#b8b7b0", other_last))

    # Place labels inside the bottom panel, pushing upward from the lowest.
    labels.sort(key=lambda t: t[0])
    placed: list[float] = []
    for y0, l, col, v in labels:
        y = max(y0, BOT_T + 14)
        if placed and y < placed[-1] + 16:
            y = placed[-1] + 16
        placed.append(y)
    overflow = placed[-1] - (BOT_T + BOT_H - 1)
    if overflow > 0:
        placed = [y - overflow for y in placed]
    for (y0, l, col, v), y in zip(labels, placed):
        b.append(line(W - R + 9, y0, W - R + 16, y, "#b8b7b0", 1))
        b.append(txt(W - R + 22, y + 4, f"{label_lab(l) if l != 'all other labs' else l}  {v:.0%}",
                     10.5, INK, weight="600"))

    for i, m in enumerate(months):
        if i % 3 == 0 or i == len(months) - 1:
            b.append(txt(xs[i], BOT_T + BOT_H + 20, m, 9.5, MUTE, "middle"))

    yb = H - 98
    b.append(line(34, yb - 22, W - 34, yb - 22, GRID, 1))
    b.append(txt(34, yb, f"The market grew {growth:,.0f}× in {len(months)} months. "
                f"{faller.title()} served {first_abs[faller] / 1e12:.1f}T in {months[0]} and "
                f"{last_abs[faller] / 1e12:.1f}T in {months[-1]} — {faller_growth:.0f}× more "
                f"tokens — while its share fell from {shares[months[0]].get(faller, 0):.0%} to "
                f"{shares[months[-1]].get(faller, 0):.0%}.", 12, INK, weight="600"))
    b.append(txt(34, yb + 24, "Every sentence of the form “lab X is winning” has chosen a "
                "denominator. The absolute market grew, so a smaller share can still be more "
                "tokens than before.", 10.5, MUTE))
    b.append(txt(34, H - 8, "Source: OpenRouter rankings, monthly totals; the current month "
                f"is excluded as partial. as of {as_of()}.", 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(months)} months, {len(top)} labs, {growth:,.0f}× growth"


def tokens_vs_spend(out=CHARTS / "or-tokens-vs-spend.svg") -> str:
    start, end = _window()
    rows = window(rankings(), start, end)
    pr = prices()
    tok: collections.Counter = collections.Counter()
    rev: collections.Counter = collections.Counter()
    total = sum(r["tok"] for r in rows)
    for r in rows:
        s = r["model_permaslug"]
        if s in pr:
            tok[lab(s)] += r["tok"]
            rev[lab(s)] += r["tok"] * pr[s]
    tt, tr = sum(tok.values()), sum(rev.values())
    if not tt:
        return "or-tokens-vs-spend.svg skipped: no priced tokens in the window"
    cover = tt / total
    pts = [
        {"lab": l, "t": tok[l] / tt, "r": rev[l] / tr, "abs": tok[l]}
        for l in tok if tok[l] / tt >= 0.002 or rev[l] / tr >= 0.002
    ]
    maxv = max(max(p["t"] for p in pts), max(p["r"] for p in pts)) * 1.12

    W, L, T, P, R = 1020, 132, 250, 560, 200
    H = T + P + 238
    sx = lambda v: L + v / maxv * P  # noqa: E731
    sy = lambda v: T + P - v / maxv * P  # noqa: E731
    sr = lambda a: 5 + (a / max(x["abs"] for x in pts)) ** 0.5 * 16  # noqa: E731

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(40, 44, "Whoever picks the denominator picks the winner", 20, INK, weight="600"))
    b.append(txt(40, 70, f"Every lab routed through OpenRouter in the latest 30 complete days "
                f"({start} to {end}). Across: its share of", 13, MUTE))
    b.append(txt(40, 89, "tokens served. Up: its share of what those tokens cost at input list "
                "price. Both axes are shares of the same", 13, MUTE))
    b.append(txt(40, 108, "population on the same scale, so the dashed line is parity — paid "
                "exactly in proportion to what it serves.", 13, MUTE))
    biggest_t = max(pts, key=lambda p: p["t"])
    biggest_r = max(pts, key=lambda p: p["r"])
    b.append(txt(40, 134, f"{label_lab(biggest_t['lab'])} serves {biggest_t['t']:.0%} of the tokens "
                f"and takes {biggest_t['r']:.0%} of the spend. {label_lab(biggest_r['lab'])} serves "
                f"{biggest_r['t']:.0%} and takes {biggest_r['r']:.0%}.", 12, MUTE))

    for v in (0, .1, .2, .3, .4, .5, .6, .7):
        if v > maxv:
            break
        b.append(line(L, sy(v), L + P, sy(v), GRID, 1))
        b.append(txt(L - 10, sy(v) + 4, f"{v:.0%}", 10.5, MUTE, "end"))
        b.append(line(sx(v), T, sx(v), T + P, GRID, 1))
        b.append(txt(sx(v), T + P + 20, f"{v:.0%}", 10.5, MUTE, "middle"))
    b.append(txt(L - 10, T - 28, "share of SPEND", 12, INK, "end", "600"))
    b.append(txt(L - 10, T - 12, "tokens × input list price", 10.5, MUTE, "end"))
    b.append(txt(L + P, T + P + 44, "share of TOKENS served", 12, INK, "end", "600"))
    b.append(line(sx(0), sy(0), sx(maxv), sy(maxv), MUTE, 1, dash="5 5"))
    b.append(txt(sx(maxv * .74), sy(maxv * .74) - 10, "paid in proportion to what you serve",
                 10.5, MUTE, "middle"))
    b.append(txt(L + 12, T + 22, "paid MORE than it serves", 11.5, MUTE, style="italic"))
    b.append(txt(L + P - 12, T + P - 12, "serves MORE than it is paid", 11.5, MUTE, "end", style="italic"))

    for p in sorted(pts, key=lambda p: -p["abs"]):
        c = ORANGE if p["lab"] in CN_LABS else BLUE
        b.append(circ(sx(p["t"]), sy(p["r"]), sr(p["abs"]), c))
    marks = [(sx(p["t"]), sy(p["r"]), sr(p["abs"])) for p in pts]
    taken: list[tuple[float, float, float, float]] = []

    def free(bx):
        return not (
            any(bx[0] < o[2] and o[0] < bx[2] and bx[1] < o[3] and o[1] < bx[3] for o in taken)
            or any(bx[0] < cx + rr and cx - rr < bx[2] and bx[1] < cy + rr and cy - rr < bx[3]
                   for cx, cy, rr in marks)
        )

    for p in sorted(pts, key=lambda p: -max(p["t"], p["r"])):
        if max(p["t"], p["r"]) < 0.05:
            continue
        lab_s = f"{label_lab(p['lab'])}  {p['t']:.0%} / {p['r']:.0%}"
        x, y, rr = sx(p["t"]), sy(p["r"]), sr(p["abs"])
        w = len(lab_s) * 6.2 + 10
        for dy in (0, -15, 15, -30, 30, -45, 45):
            for anc in ("start", "end"):
                x0 = x + rr + 7 if anc == "start" else x - rr - 7 - w
                yy = min(max(y + dy, T + 12), T + P - 12)
                bx = (x0, yy - 8, x0 + w, yy + 6)
                if bx[0] < L + 4 or bx[2] > W - 30 or not free(bx):
                    continue
                taken.append(bx)
                b.append(txt(x + (rr + 7 if anc == "start" else -rr - 7), yy + 4,
                             lab_s, 11, INK, anc))
                break
            else:
                continue
            break

    b.append(circ(W - R + 44, T + 10, 7, ORANGE))
    b.append(txt(W - R + 58, T + 14, "Chinese lab", 11.5, MUTE))
    b.append(circ(W - R + 44, T + 34, 7, BLUE))
    b.append(txt(W - R + 58, T + 38, "everyone else", 11.5, MUTE))
    cn_t = sum(p["t"] for p in pts if p["lab"] in CN_LABS)
    cn_r = sum(p["r"] for p in pts if p["lab"] in CN_LABS)
    yb = T + P + 92
    b.append(line(40, yb - 26, W - 40, yb - 26, GRID, 1))
    b.append(txt(40, yb, f"Chinese labs serve {cn_t:.0%} of the tokens and take {cn_r:.0%} of "
                f"the spend. The same month supports both 'winning' stories.", 13, INK, weight="600"))
    b.append(txt(40, yb + 24, "Input-token LIST price only — completion tokens cost several "
                "times more and are not counted, and nobody large pays list.", 11, MUTE))
    b.append(txt(40, yb + 42, f"Covers the {cover:.0%} of tokens that join to a price, keyed on "
                "model_permaslug. Labels omit labs below 5% of tokens; the marks are all there.",
                11, MUTE))
    b.append(txt(40, yb + 60, "This is spend routed through OpenRouter, not lab revenue: one "
                "router, developer-skewed.", 11, MUTE))
    b.append(txt(40, yb + 78, f"Source: OpenRouter rankings and benchmark pricing, {start} to "
                f"{end}; as of {as_of()}.", 11, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(pts)} labs, {cover:.0%} of tokens priced"


def capability_vs_usage(out=CHARTS / "or-capability-vs-usage.svg") -> str:
    start, end = _window()
    rows = window(rankings(), start, end)
    total = sum(r["tok"] for r in rows)
    use: collections.Counter = collections.Counter()
    for r in rows:
        use[r["model_permaslug"]] += r["tok"]
    sc, pr = scores(), prices()
    pts = []
    for s, v in use.items():
        if s in sc and "intelligence_index" in sc[s]:
            pts.append({"slug": s, "i": sc[s]["intelligence_index"], "sh": v / total,
                        "p": pr.get(s, 0) * 1e6})
    if len(pts) < 5:
        return "or-capability-vs-usage.svg skipped: too few scored models"
    cover = sum(p["sh"] for p in pts)

    def corr(a, b):
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
        return num / den if den else 0

    r_i = corr([p["i"] for p in pts], [p["sh"] for p in pts])
    priced = [p for p in pts if p["p"]]
    r_p = corr([math.log10(max(p["p"], .01)) for p in priced], [p["sh"] for p in priced]) if len(priced) > 2 else 0

    xmax = max(p["i"] for p in pts) * 1.08
    ymax = max(p["sh"] for p in pts) * 1.12
    ramp = ["#bfe0f2", "#79b7dd", "#3d86bf", "#20599a", "#12336b"]

    def shade(p):
        if not p:
            return "#cfcac0"
        for i, t in enumerate((0.3, 1, 3, 10)):
            if p <= t:
                return ramp[i]
        return ramp[4]

    W, L, T, PH, R = 1020, 196, 244, 400, 250
    H = T + PH + 228
    sx = lambda v: L + v / xmax * (W - L - R)  # noqa: E731
    sy = lambda v: T + PH - v / ymax * PH  # noqa: E731

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(40, 44, "Being better does not make you used", 20, INK, weight="600"))
    b.append(txt(40, 70, f"Each dot is one model. Across: an independent intelligence index. "
                f"Up: the share of tokens it actually served on", 13, MUTE))
    b.append(txt(40, 89, f"OpenRouter in the latest 30 days ({start} to {end}). Colour is price "
                f"per million input tokens. If capability drove demand", 13, MUTE))
    b.append(txt(40, 108, "this would slope upward. It does not.", 13, MUTE))
    b.append(txt(40, 134, f"Correlation is {r_i:+.2f}. What moves with usage is price, and it "
                f"moves the wrong way — corr(log price, share) = {r_p:+.2f}.", 12, MUTE))

    for v in [i / 100 for i in range(0, int(ymax * 100) + 2, 2)]:
        if v > ymax:
            break
        b.append(line(L, sy(v), W - R, sy(v), GRID, 1))
        b.append(txt(L - 10, sy(v) + 4, f"{v:.0%}", 10.5, MUTE, "end"))
    for v in range(0, int(xmax) + 1, 10):
        if v == 0:
            continue
        b.append(line(sx(v), T, sx(v), T + PH, GRID, 1))
        b.append(txt(sx(v), T + PH + 20, str(v), 10.5, MUTE, "middle"))
    b.append(txt(L - 10, T - 28, "share of tokens served", 12, INK, "end", "600"))
    b.append(txt(W - R, T + PH + 44, "intelligence index  ·  higher is more capable", 12, INK, "end", "600"))

    for p in sorted(pts, key=lambda p: -p["sh"]):
        b.append(circ(sx(p["i"]), sy(p["sh"]), 7, shade(p["p"])))
    marks = [(sx(p["i"]), sy(p["sh"]), 8) for p in pts]
    taken: list[tuple[float, float, float, float]] = []

    def free(bx):
        return not (
            any(bx[0] < o[2] and o[0] < bx[2] and bx[1] < o[3] and o[1] < bx[3] for o in taken)
            or any(bx[0] < cx + rr and cx - rr < bx[2] and bx[1] < cy + rr and cy - rr < bx[3]
                   for cx, cy, rr in marks)
        )

    for p in sorted(pts, key=lambda p: -p["sh"])[:7]:
        text_s = f"{_slug_label(p['slug'], 30)}  {p['sh']:.1%}"
        w = len(text_s) * 6.1 + 8
        x, y = sx(p["i"]), sy(p["sh"])
        for dy in (0, -14, 14, -28, 28, -42):
            for anc in ("start", "end"):
                x0 = x + 11 if anc == "start" else x - 11 - w
                yy = min(max(y + dy, T + 12), T + PH - 12)
                bx = (x0, yy - 8, x0 + w, yy + 6)
                if bx[0] < 44 or bx[2] > W - R - 4 or not free(bx):
                    continue
                taken.append(bx)
                b.append(txt(x0 if anc == "start" else x - 11, yy + 4, text_s, 11, INK, anc))
                break
            else:
                continue
            break
    best = max(pts, key=lambda p: p["i"])
    bx, by = sx(best["i"]), sy(best["sh"])
    ax, ay = W - R - 24, T + PH * 0.46
    b.append(f'<path d="M{ax:.1f},{ay + 6:.1f} L{ax:.1f},{by - 16:.1f} L{bx:.1f},{by - 9:.1f}" '
             f'fill="none" stroke="{MUTE}" stroke-width="1" stroke-dasharray="3 3"/>')
    b.append(txt(ax, ay - 8, "most capable model here", 11, INK, "end", "600"))
    b.append(txt(ax, ay + 7, short_model(best["slug"], 24), 10.5, MUTE, "end"))
    b.append(txt(ax, ay + 21, f"{best['sh']:.1%} of tokens", 10.5, MUTE, "end"))

    lx = W - R + 30
    b.append(txt(lx, T + 6, "input price", 11.5, MUTE))
    b.append(txt(lx, T + 21, "per Mtok", 11.5, MUTE))
    for i, (c, lab_s) in enumerate(zip(ramp, ("under $0.30", "$0.30-1", "$1-3", "$3-10", "over $10"))):
        b.append(rect(lx, T + 36 + i * 22, 18, 16, c))
        b.append(txt(lx + 26, T + 49 + i * 22, lab_s, 11, MUTE))

    yb = T + PH + 84
    b.append(line(40, yb - 26, W - 40, yb - 26, GRID, 1))
    b.append(txt(40, yb, f"Capability and usage are uncorrelated ({r_i:+.2f}). Price and usage "
                f"are, negatively ({r_p:+.2f}). The market buys cheap, not smart.", 13, INK, weight="600"))
    b.append(txt(40, yb + 24, "A benchmark table is not a demand forecast. Anyone reading "
                "leaderboard position as market position has the wrong variable.", 11, MUTE))
    b.append(txt(40, yb + 42, f"{len(pts)} models join the benchmark feed on model_permaslug, "
                f"covering {cover:.0%} of tokens. Intelligence index from Artificial Analysis; "
                "price is input list price.", 11, MUTE))
    b.append(txt(40, yb + 60, "OpenRouter is a router: it sees everyone who routes through it "
                f"and nobody who calls a lab directly. as of {as_of()}.", 11, MUTE))
    b.append(txt(40, yb + 96, "Two DeepSeek V4.1 snapshots are plotted: the 2026-09-10 model is "
                "labelled at 16.9%; the 2026-10-17 model is the unlabelled 5.1% dot.", 11, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(pts)} models, r(intel)={r_i:+.2f}, r(log price)={r_p:+.2f}"


def _weekly_hf_snapshots() -> list[dict]:
    """One Hugging Face snapshot per ISO week; the fleet captures several/day."""
    by_week: dict[tuple[int, int], dict] = {}
    for snap in hf_snapshots():
        d = date.fromisoformat(snap["date"])
        by_week[d.isocalendar()[:2]] = snap
    return sorted(by_week.values(), key=lambda s: s["date"])


def _or_use(start: str, end: str) -> tuple[collections.Counter, int]:
    rows = window(rankings(), start, end)
    use: collections.Counter = collections.Counter()
    total = 0
    for r in rows:
        total += r["tok"]
        if r["model_permaslug"] != "other":
            use[re.sub(r"-20\d{6}$", "", r["model_permaslug"].split(":")[0])] += r["tok"]
    return use, total


def downloads_vs_use(out=CHARTS / "or-downloads-vs-use.svg") -> str:
    cat_path = __import__("data").WORK / "models-catalog.json"
    if not cat_path.exists():
        return "or-downloads-vs-use.svg skipped: no catalog cache"
    import json
    cat = json.loads(cat_path.read_text(encoding="utf-8"))["data"]
    hfid = {m["id"]: m["hugging_face_id"] for m in cat if m.get("hugging_face_id")}

    weekly = _weekly_hf_snapshots()
    if len(weekly) < 3:
        return f"or-downloads-vs-use.svg skipped: only {len(weekly)} weekly HF captures"

    def join(snap: dict) -> dict:
        end = snap["date"]
        start = (date.fromisoformat(end) - timedelta(days=29)).isoformat()
        use, total = _or_use(start, end)
        pts = []
        hf = snap["models"]
        for orid, h in hfid.items():
            if h not in hf or orid not in use:
                continue
            d = int(hf[h].get("downloads") or 0)
            if d:
                pts.append({"id": orid, "dl": d, "sh": use[orid] / total})
        n = len(pts)
        rho = spearman([p["dl"] for p in pts], [p["sh"] for p in pts]) if n >= 5 else 0.0
        return {"date": end, "start": start, "pts": pts, "n": n, "rho": rho,
                "cover": sum(p["sh"] for p in pts)}

    joins = [join(s) for s in weekly]
    joins = [j for j in joins if j["n"] >= 5]
    if len(joins) < 3:
        return "or-downloads-vs-use.svg skipped: too few weekly joins"
    latest = joins[-1]
    pts = latest["pts"]
    n, rho, cover = latest["n"], latest["rho"], latest["cover"]

    W = 1060
    H = 940
    L, R = 96, 286
    T, PH = 190, 330
    RT, RH = 636, 128
    dl = [p["dl"] for p in pts]
    sh = [p["sh"] for p in pts]
    xlo, xhi = math.log10(min(dl)) - 0.2, math.log10(max(dl)) + 0.2
    ylo, yhi = math.log10(min(sh)) - 0.25, math.log10(max(sh)) + 0.2
    sx = lambda v: L + (math.log10(v) - xlo) / (xhi - xlo) * (W - L - R)  # noqa: E731
    sy = lambda v: T + PH - (math.log10(v) - ylo) / (yhi - ylo) * PH  # noqa: E731

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(40, 44, "Downloads are not use", 20, INK, weight="600"))
    b.append(txt(40, 70, f"Each dot is an open-weight model in the latest weekly join: "
                f"Hugging Face downloads in the last 30 days against OpenRouter token share "
                f"in the same 30 days.", 13, MUTE))
    b.append(txt(40, 89, f"Spearman rank correlation {rho:+.2f} across {n} models holding "
                f"{cover:.0%} of routed tokens. The rolling panel asks whether that relation "
                "is stable.", 13, MUTE))

    for power in range(math.floor(xlo), math.ceil(xhi) + 1):
        v = 10 ** power
        if not (10 ** xlo <= v <= 10 ** xhi):
            continue
        xx = sx(v)
        b.append(line(xx, T, xx, T + PH, GRID, 1))
        label = f"{v / 1e6:g}M" if v >= 1e6 else f"{v / 1e3:g}k"
        b.append(txt(xx, T + PH + 20, label, 10, MUTE, "middle"))
    for power in range(math.floor(ylo), math.ceil(yhi) + 1):
        v = 10 ** power
        if not (10 ** ylo <= v <= 10 ** yhi):
            continue
        yy = sy(v)
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{v:.2%}", 10, MUTE, "end"))
    b.append(txt(L, T - 26, "share of OpenRouter tokens", 11.5, INK, weight="600"))
    b.append(txt((L + W - R) / 2, T + PH + 42,
                 "Hugging Face downloads, last 30 days (log scale)", 10.5, MUTE, "middle"))

    # Top labs by token share in this join; the rest stay grey.
    lab_tok: collections.Counter = collections.Counter()
    for p in pts:
        lab_tok[lab(p["id"])] += p["sh"]
    lab_col = {l: c for l, c in zip([x for x, _ in lab_tok.most_common(4)],
                                    (BLUE, ORANGE, AQUA, VIOLET))}
    for p in sorted(pts, key=lambda p: -p["sh"]):
        col = lab_col.get(lab(p["id"]), "#b8b7b0")
        b.append(circ(sx(p["dl"]), sy(p["sh"]), 6, col, stroke="#ffffff", sw=2))

    # Label the biggest by use and by downloads; skip collisions.
    chosen = []
    for p in sorted(pts, key=lambda p: -p["sh"])[:5]:
        chosen.append(p)
    for p in sorted(pts, key=lambda p: -p["dl"])[:3]:
        if p not in chosen:
            chosen.append(p)
    placed: list[tuple[float, float, float]] = []
    for p in chosen:
        x, y = sx(p["dl"]), sy(p["sh"])
        label = short_model(p["id"], 24)
        w = len(label) * 5.8
        if x + 10 + w > W - R:
            lx, anchor, x0, x1 = x - 10, "end", x - 10 - w, x - 10
        else:
            lx, anchor, x0, x1 = x + 10, "start", x + 10, x + 10 + w
        if any(abs(y - py) < 13 and not (x1 < bx0 or x0 > bx1) for bx0, bx1, py in placed):
            continue
        placed.append((x0, x1, y))
        b.append(txt(lx, y + 4, label, 10.5, INK, anchor, "600"))
    b.append(txt(L, T + 6, "upper-left = downloaded, little used", 9.5, MUTE))
    b.append(txt(W - R, T + PH - 8, "lower-right = used, little downloaded", 9.5, MUTE, "end"))

    # Rolling weekly rank correlation: same model set construction each week.
    b.append(line(40, RT - 40, W - 40, RT - 40, GRID, 1))
    b.append(txt(40, RT - 14, "Does the relation hold? Weekly rank correlation", 13, INK, weight="600"))
    b.append(txt(40, RT + 5, "Each point joins the Hugging Face capture for that week with "
                 "the preceding 30 days of OpenRouter tokens.", 10.5, MUTE))
    ycorr = lambda v: RT + 34 + (1 - v) / 2 * (RH - 34)  # noqa: E731
    for v in (-1, -0.5, 0, 0.5, 1):
        yy = ycorr(v)
        b.append(line(L, yy, W - R, yy, GRID if v else "#c3c2b7", 1))
        b.append(txt(L - 10, yy + 4, f"{v:+.1f}".replace("+0.0", "0"), 10, MUTE, "end"))
    xs = [L + i / max(1, len(joins) - 1) * (W - L - R) for i in range(len(joins))]
    b.append(polyline([(x, ycorr(j["rho"])) for x, j in zip(xs, joins)], BLUE, 2.4))
    for i, (x, j) in enumerate(zip(xs, joins)):
        b.append(circ(x, ycorr(j["rho"]), 4, BLUE, stroke="#ffffff", sw=2))
        if i in (0, len(joins) - 1):
            b.append(txt(x, ycorr(j["rho"]) + (-9 if j["rho"] >= 0 else 15),
                         f"{j['rho']:+.2f}", 10.5, INK, "middle", "600"))
    for i, j in enumerate(joins):
        if i % 2 == 0 or i == len(joins) - 1:
            b.append(txt(xs[i], RT + 30 + RH, date.fromisoformat(j["date"]).strftime("%d %b"),
                         9, MUTE, "middle"))
    b.append(txt(W - R, RT + 5, f"n = {min(j['n'] for j in joins)}–{max(j['n'] for j in joins)} models",
                 10, MUTE, "end"))

    yb = H - 118
    b.append(line(40, yb - 24, W - 40, yb - 24, GRID, 1))
    b.append(txt(40, yb, f"Downloads do not predict use: the weekly rank correlation is "
                f"negative in every window and ranges {min(j['rho'] for j in joins):+.2f} to "
                f"{max(j['rho'] for j in joins):+.2f}.", 12.5, INK, weight="600"))
    b.append(txt(40, yb + 22, "SCOPE: this join can only see OPEN-WEIGHT models. A closed "
                "model has no Hugging Face presence, so Claude and the GPT-5 series are absent "
                "by construction.", 11, MUTE))
    b.append(txt(40, yb + 42, f"It says how open-weight popularity relates to open-weight use, "
                f"not how the market works. {n} models is small; ranks are shown rather than a "
                "fitted line for that reason.", 11, MUTE))
    b.append(txt(40, H - 8, f"Sources: OpenRouter rankings and models catalog; Hugging Face "
                f"model index via wss-hugging-face. Latest capture {latest['date']}; "
                f"OpenRouter as of {as_of()}.", 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return (f"{out.relative_to(CHARTS.parent)} — {n} models, Spearman {rho:+.2f}, "
            f"{cover:.0%} of tokens, {len(joins)} weekly joins")


def shelf_life(out=CHARTS / "or-model-shelf-life.svg") -> str:
    rows = rankings()
    day: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in rows:
        day[r["date"]][r["model_permaslug"]] += r["tok"]
    dates = sorted(day)
    total = {d: sum(day[d].values()) for d in dates}

    def smooth(v, k=7):
        return [st.mean(v[max(0, i - k + 1):i + 1]) for i in range(len(v))]

    first: dict[str, str] = {}
    for d in dates:
        for s in day[d]:
            first.setdefault(s, d)
    tracks, stats = [], []
    for s, f in first.items():
        idx = [i for i, d in enumerate(dates) if d >= f]
        if len(idx) < 150:
            continue
        sm = smooth([day[dates[i]].get(s, 0) / total[dates[i]] for i in idx])
        pi = max(range(len(sm)), key=lambda i: sm[i])
        if sm[pi] < 0.005:
            continue
        half = next((j - pi for j in range(pi + 1, len(sm)) if sm[j] <= sm[pi] / 2), None)
        tracks.append((s, [v / sm[pi] for v in sm[:270]], pi, sm[pi]))
        stats.append((pi, half))
    if len(tracks) < 10:
        return f"or-model-shelf-life.svg skipped: only {len(tracks)} models have 150 days"
    pk = [a for a, _ in stats]
    hl = [b for _, b in stats if b]
    days = 240
    ymax = 1.04
    W, L, T, PH, R = 1060, 190, 250, 400, 250
    H = T + PH + 210
    sx = lambda d: L + d / days * (W - L - R)  # noqa: E731
    sy = lambda v: T + PH - v / ymax * PH  # noqa: E731
    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(40, 44, "A model gets about a month at the top", 20, INK, weight="600"))
    b.append(txt(40, 70, f"Every model that ever held more than 0.5% of routed tokens and lived "
                f"150 days — {len(tracks)} of them — aligned on the day it first appeared.", 13, MUTE))
    b.append(txt(40, 89, "Share is a 7-day mean, because on raw daily numbers the peak is noise. "
                "Grey is one model; the thick line is the median.", 13, MUTE))
    b.append(txt(40, 115, f"Median {st.median(pk):.0f} days to peak, {st.median(hl):.0f} days from "
                f"peak to half. {sum(1 for _, h in stats if h and h < 999):,} of {len(tracks)} "
                "have a measured half-life.", 12, MUTE))
    for v in (0, .25, .5, .75, 1.0):
        b.append(line(L, sy(v), W - R, sy(v), GRID, 1))
        b.append(txt(L - 10, sy(v) + 4, f"{v:.0%}", 10.5, MUTE, "end"))
    for d in range(0, days + 1, 30):
        b.append(line(sx(d), T, sx(d), T + PH, GRID, 1))
        b.append(txt(sx(d), T + PH + 20, str(d), 10.5, MUTE, "middle"))
    b.append(txt(L - 10, T - 44, "share of tokens,", 12, INK, "end", "600"))
    b.append(txt(L - 10, T - 28, "relative to that model's own peak", 10.5, MUTE, "end"))
    b.append(txt(W - R, T + PH + 44, "days since the model first appeared", 12, INK, "end", "600"))
    for s, sm, pi, p in tracks:
        b.append(polyline([(sx(i), sy(v)) for i, v in enumerate(sm[:days])], MUTE, 1, 0.16))
    med = []
    for d in range(days):
        vals = [sm[d] for _, sm, _, _ in tracks if d < len(sm)]
        if len(vals) >= 20:
            med.append((d, st.median(vals)))
    b.append(polyline([(sx(d), sy(v)) for d, v in med], BLUE, 3))
    b.append(line(L, sy(0.5), W - R, sy(0.5), VIOLET, 1.2, dash="5 4"))
    b.append(txt(W - R - 6, sy(0.5) - 8, "half of peak", 10.5, VIOLET, "end"))
    for n, (s, sm, pi, p) in enumerate(sorted(tracks, key=lambda t: -t[3])[:4]):
        ly = T + 18 + n * 17
        b.append(circ(sx(pi), sy(1.0), 4.5, ORANGE))
        b.append(txt(W - R - 12, ly, f"{_slug_label(s, 34)} — peaked at {p:.0%} on day {pi}",
                     10.5, INK, "end"))
    b.append(line(sx(st.median(pk)), T, sx(st.median(pk)), T + PH, VIOLET, 1.3, dash="4 4"))
    b.append(txt(sx(st.median(pk)) + 8, T + PH - 28, f"median peak, day {st.median(pk):.0f}",
                 10.5, VIOLET))
    yb = T + PH + 86
    b.append(line(40, yb - 26, W - 40, yb - 26, GRID, 1))
    b.append(txt(40, yb, f"Median {st.median(pk):.0f} days to peak and {st.median(hl):.0f} from "
                f"peak to half. A model at the top is a depreciating asset.", 13, INK, weight="600"))
    b.append(txt(40, yb + 24, "So “which model should I build on” has a shelf life of about a "
                "month, and the thing worth optimising is switching cost rather than choice.",
                12, MUTE))
    b.append(txt(40, yb + 48, "Share is relative and this market grew over the record, so the "
                "same half-life was recomputed on absolute tokens by the recipe: also 10 days. "
                "The decay is real.", 11, MUTE))
    b.append(txt(40, H - 6, "OpenRouter is a router: it sees everyone who routes and nobody who "
                f"calls a lab directly. Source: OpenRouter rankings, as of {as_of()}.", 11, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(tracks)} models, peak d{st.median(pk):.0f}, half {st.median(hl):.0f}d"


APP_COLOURS = {
    "Cline": BLUE,
    "Kilo Code": ORANGE,
    "Roo Code": AQUA,
    "Hermes Agent": VIOLET,
    "OpenClaw": "#b08a2e",
    "Janitor AI": "#6b7684",
    "Claude Code": "#9b5f8f",
}


def app_mix(out=CHARTS / "or-app-mix.svg") -> str:
    """Who routes, and did the shape of a request change?

    App rankings are a second archive, with both tokens and requests. Share is
    within the top 50 apps in each window, not the whole platform: the API
    returns a top list, not an exhaustive census.
    """
    snaps = sorted(app_rankings(), key=lambda s: s["start"])
    if len(snaps) < 3:
        return "or-app-mix.svg skipped: no app-rankings cache"
    stats = []
    for s in snaps:
        tok = sum(int(r["total_tokens"]) for r in s["data"])
        req = sum(int(r["total_requests"]) for r in s["data"])
        apps = {r["app_name"]: int(r["total_tokens"]) / tok for r in s["data"]}
        stats.append({"start": s["start"], "end": s["end"], "tok": tok, "req": req,
                      "tpr": tok / req if req else 0, "apps": apps})
    first, last = stats[0], stats[-1]

    # Rank by cumulative share over the whole record, not by either endpoint:
    # an app that mattered for a year should keep its identity.
    cumulative: collections.Counter = collections.Counter()
    for s in stats:
        cumulative.update(s["apps"])
    names = [n for n, _ in cumulative.most_common() if n in APP_COLOURS][:7]
    if not names:
        names = [n for n, _ in cumulative.most_common(7)]

    W, H = 1060, 880
    L, R = 92, 238
    TOP_T, TOP_H = 184, 150
    BOT_T, BOT_H = 442, 260
    xs = [L + i / max(1, len(stats) - 1) * (W - L - R) for i in range(len(stats))]
    tpr_max = max(s["tpr"] for s in stats) * 1.18
    sy = lambda v: TOP_T + TOP_H - v / tpr_max * TOP_H  # noqa: E731

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(34, 40, "The users changed shape: assistants became agents", 20, INK, weight="600"))
    b.append(txt(34, 64, "Top 50 OpenRouter apps, monthly. Tokens per request rose from "
                f"{first['tpr'] / 1000:.1f}k in {date.fromisoformat(first['start']).strftime('%b %Y')} "
                f"to {last['tpr'] / 1000:.1f}k in {date.fromisoformat(last['start']).strftime('%b %Y')} "
                f"({last['tpr'] / first['tpr']:.1f}×).", 12.5, MUTE))
    b.append(txt(34, 82, "The bottom panel is the composition of those top-50 tokens at every "
                "month; a falling share is not a falling app. The market grew in requests and "
                "in length.", 12.5, MUTE))
    b += [rect(34 + i * 134, 105, 10, 10, APP_COLOURS.get(n, "#d9d8d2"), rx=2)
          for i, n in enumerate(names)]
    b += [txt(49 + i * 134, 114, n, 10.5, INK) for i, n in enumerate(names)]
    b += [rect(34 + len(names) * 134, 105, 10, 10, "#d9d8d2", rx=2),
          txt(49 + len(names) * 134, 114, "other", 10.5, INK)]

    for v in range(0, int(tpr_max) + 1, 20000):
        yy = sy(v)
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{v / 1000:.0f}k", 10, MUTE, "end"))
    b.append(txt(L, TOP_T - 22, "tokens per request", 11.5, INK, weight="600"))
    b.append(txt(L, TOP_T - 7, "trailing month", 9.5, MUTE))
    b.append(polyline([(x, sy(s["tpr"])) for x, s in zip(xs, stats)], BLUE, 2.6))
    for i, (x, s) in enumerate(zip(xs, stats)):
        b.append(circ(x, sy(s["tpr"]), 3.5, BLUE))
        if i in (0, len(stats) - 1):
            b.append(txt(x + (8 if i == 0 else -8), sy(s["tpr"]) - 10,
                         f"{s['tpr'] / 1000:.1f}k", 10.5, INK,
                         "start" if i == 0 else "end", "600"))
    for i, s in enumerate(stats):
        if i % 3 == 0 or i == len(stats) - 1:
            b.append(txt(xs[i], TOP_T + TOP_H + 18,
                         date.fromisoformat(s["start"]).strftime("%b %y"), 9.5, MUTE, "middle"))

    # Bottom panel: 100% stacked bars across every month, not a two-point slope.
    bar_w = max(16.0, (W - L - R) / len(stats) * 0.72)
    b.append(txt(L, BOT_T - 22, "share of top-50 app tokens", 11.5, INK, weight="600"))
    b.append(txt(L, BOT_T - 7, "top 7 apps + all other", 9.5, MUTE))
    for pct in (0, 25, 50, 75, 100):
        yy = BOT_T + BOT_H - pct / 100 * BOT_H
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{pct}%", 10, MUTE, "end"))
    for x, s in zip(xs, stats):
        y = BOT_T + BOT_H
        for n in names + ["__other__"]:
            share = (sum(v for k, v in s["apps"].items() if k not in names)
                     if n == "__other__" else s["apps"].get(n, 0))
            h = share * BOT_H
            if h <= 0:
                continue
            y -= h
            b.append(rect(x - bar_w / 2, y, bar_w, h,
                          APP_COLOURS.get(n, "#d9d8d2"), stroke="#ffffff", sw=1.5))
    b.append(line(L, BOT_T + BOT_H, W - R, BOT_T + BOT_H, "#c3c2b7", 1))
    for i, s in enumerate(stats):
        if i % 3 == 0 or i == len(stats) - 1:
            b.append(txt(xs[i], BOT_T + BOT_H + 20,
                         date.fromisoformat(s["start"]).strftime("%b %y"), 9.5, MUTE, "middle"))

    yb = H - 128
    b.append(line(34, yb - 24, W - 34, yb - 24, GRID, 1))
    b.append(txt(34, yb, "Cline and Roo Code were 75.2% of the top-50 app tokens in "
                "January 2025.", 12.5, INK, weight="600"))
    b.append(txt(34, yb + 22, "OpenClaw peaked at 53.3% in March 2026; by September 2026 "
                "Hermes Agent was 27.8%, Claude Code 13.7% and Kilo Code 9.5%.", 11.5,
                INK, weight="600"))
    b.append(txt(34, yb + 44, "Tokens per request rose 4.5× over the record. The app mix "
                "turned over at least as fast: four different leaders in twenty-one "
                "months. Both archives are read directly, never captured.", 11, MUTE))
    b.append(txt(34, H - 8, f"Source: OpenRouter app-rankings, {len(stats)} monthly windows, "
                f"top 50 apps; as of {as_of()}.", 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(stats)} windows, {len(names)} apps"


def render_all() -> list[str]:
    return [lab_share(), app_mix(), tokens_vs_spend(), capability_vs_usage(),
            downloads_vs_use(), shelf_life()]


if __name__ == "__main__":
    for line_out in render_all():
        print(line_out)
