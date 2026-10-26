"""The same research questions, asked of OpenCode's own 56-day window.

OpenCode is a coding client, not a router. It publishes daily model and lab
shares, session cost, retention, cache ratio and geography. The window is short
and recomputes hourly, so these figures are about displacement and mechanism,
not shelf life.

Every daily chart drops the current UTC date: the source updates hourly, so the
final row is a partial day. Country and retention are live snapshots, not
daily series; the trend panels use Internet Archive copies of the same
first-party JSON as historical context, cached under `work/` and never committed.
"""

from __future__ import annotations

import collections
import math
import statistics as st
from datetime import date, timedelta

from data import (
    CHARTS,
    OC_TO_OR,
    CN_LABS,
    WORK,
    as_of,
    label_lab,
    opencode_daily,
    opencode_labs,
    opencode_archives,
    opencode_latest,
    opencode_names,
    opencode_payload_window,
    opencode_value,
    opencode_window_tokens,
    rankings,
    short_model,
    spearman,
)
from svgkit import AQUA, BLUE, GRID, INK, MUTE, ORANGE, VIOLET, circ, doc, line, polyline, rect, txt

LAB_COLOURS = {
    "deepseek": BLUE,
    "minimax": ORANGE,
    "meta": AQUA,
    "xiaomi": VIOLET,
    "zhipu": MUTE,
    "reflection": "#8f6bb3",
    "nvidia": "#8a9a5b",
    "other": "#b8b7b0",
}
MODEL_COLOURS = [BLUE, ORANGE, AQUA, VIOLET, MUTE]


def _date_ticks(dates: list[str], width: float, left: float, right: float) -> list[tuple[float, str]]:
    if not dates:
        return []
    n = len(dates)
    out = []
    for i, d in enumerate(dates):
        if i == 0 or i == n - 1 or d[8:10] == "01":
            out.append((left + i / max(1, n - 1) * (width - left - right), d))
    return out


def _fmt_t(v: float) -> str:
    if v >= 1e12:
        return f"{v / 1e12:,.1f}T"
    return f"{v / 1e9:,.0f}B"


def _fmt_date(d: str) -> str:
    return date.fromisoformat(d).strftime("%d %b")


def _legend(items: list[tuple[str, str]], y: float, width: float, x0: float = 34) -> list[str]:
    """One or two rows of swatch + label, wrapped at the canvas edge."""
    out, x, row = [], x0, 0
    for label, colour in items:
        w = len(label) * 6.2 + 30
        if x + w > width - 30:
            x, row = x0, row + 1
        out.append(rect(x, y + row * 18 - 9, 10, 10, colour, rx=2))
        out.append(txt(x + 15, y + row * 18, label, 10.5, MUTE))
        x += w
    return out


def _label_ends(items: list[tuple[float, str, str, str]], W: float, R: float) -> list[str]:
    """Place end labels down the right margin without overlaps.

    items: (y, text, colour, subtext)
    """
    out = []
    items = sorted(items, key=lambda t: t[0])
    placed: list[float] = []
    for y0, text_s, col, sub in items:
        y = y0
        while any(abs(y - p) < 16 for p in placed):
            y += 16
        placed.append(y)
        out.append(line(W - R + 8, y0, W - R + 17, y, "#c9c7bf", 1))
        out.append(txt(W - R + 22, y - 2, text_s, 10.5, INK, weight="600"))
        if sub:
            out.append(txt(W - R + 22, y + 11, sub, 9.5, MUTE))
    return out


def lab_share(out=CHARTS / "opencode-lab-share.svg") -> str:
    daily = opencode_daily()
    dates = daily["dates"]
    labs = opencode_labs()
    if len(dates) < 10 or not labs:
        return "opencode-lab-share.svg skipped: too few OpenCode days"
    peak = collections.Counter()
    for d in dates:
        for l, v in labs.get(d, {}).items():
            peak[l] = max(peak[l], v)
    top = [l for l, _ in peak.most_common() if l != "other"][:5]
    if "deepseek" not in top:
        top = ["deepseek"] + top[:4]
    totals = [daily["total"].get(d, 0) for d in dates]
    first, last = dates[0], dates[-1]
    first_deep = labs.get(first, {}).get("deepseek", 0)
    last_deep = labs.get(last, {}).get("deepseek", 0)
    growth = totals[-1] / totals[0] if totals[0] else 0

    W, H = 1060, 760
    L, R = 78, 228
    TOP_T, TOP_H = 160, 170
    BOT_T, BOT_H = 400, 200
    xs = [L + i / max(1, len(dates) - 1) * (W - L - R) for i in range(len(dates))]

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(34, 40, f"One lab took the client: DeepSeek {first_deep:.0f}% to {last_deep:.0f}%",
                 20, INK, weight="600"))
    b.append(txt(34, 64, f"Share of OpenCode tokens by lab, daily, {_fmt_date(first)} to "
                 f"{_fmt_date(last)} 2026. The current day is partial and excluded.", 12.5, MUTE))
    b.append(txt(34, 82, f"Total volume went from {_fmt_t(totals[0])} to {_fmt_t(totals[-1])} "
                 f"({growth:.1f}×) despite a four-day spike to {_fmt_t(max(totals))} in October.",
                 12.5, MUTE))
    b += _legend([(label_lab(l), LAB_COLOURS.get(l, MODEL_COLOURS[i % len(MODEL_COLOURS)]))
                  for i, l in enumerate(top)] + [("all other labs", "#b8b7b0")], 112, W)

    # total tokens
    tmax = max(totals) * 1.10
    ytot = lambda v: TOP_T + TOP_H - v / tmax * TOP_H  # noqa: E731
    for v in range(0, int(tmax / 1e12) + 1, 10):
        yy = ytot(v * 1e12)
        if yy >= TOP_T:
            b.append(line(L, yy, W - R, yy, GRID, 1))
            b.append(txt(L - 10, yy + 4, f"{v}T", 10, MUTE, "end"))
    b.append(polyline([(x, ytot(v)) for x, v in zip(xs, totals)], BLUE, 2.2))
    b.append(circ(xs[-1], ytot(totals[-1]), 4.5, BLUE))
    b.append(txt(xs[-1] + 9, ytot(totals[-1]) + 4, _fmt_t(totals[-1]), 11, INK, weight="600"))
    b.append(txt(L, TOP_T - 22, "tokens per day", 11.5, INK, weight="600"))
    b.append(txt(L, TOP_T - 7, "all models", 9.5, MUTE))

    # lab share
    ymax = max(peak.values()) * 1.08
    ysh = lambda v: BOT_T + BOT_H - v / ymax * BOT_H  # noqa: E731
    for v in range(0, int(ymax) + 1, 20):
        yy = ysh(v)
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{v:.0f}%", 10, MUTE, "end"))
    b.append(txt(L, BOT_T - 22, "share of daily tokens", 11.5, INK, weight="600"))
    b.append(txt(L, BOT_T - 7, "each line is one lab", 9.5, MUTE))

    for i, l in enumerate(top):
        col = LAB_COLOURS.get(l, MODEL_COLOURS[i % len(MODEL_COLOURS)])
        pts = [(x, ysh(labs.get(d, {}).get(l, 0))) for x, d in zip(xs, dates)]
        b.append(polyline(pts, col, 2.0))
    other_pts = []
    for x, d in zip(xs, dates):
        other = sum(v for l, v in labs.get(d, {}).items() if l not in top)
        other_pts.append((x, ysh(other)))
    b.append(polyline(other_pts, "#b8b7b0", 1.4, 0.8, dash="4 4"))

    # Direct labels only where they carry the story; the legend carries the rest.
    for l, dx, dy, anchor in (("deepseek", 9, 4, "start"), ("meta", 9, 4, "start")):
        y = ysh(labs.get(last, {}).get(l, 0))
        b.append(circ(xs[-1], y, 4.5, LAB_COLOURS[l]))
        b.append(txt(xs[-1] + dx, y + dy, f"{label_lab(l)} {labs.get(last, {}).get(l, 0):.0f}%",
                     10.5, INK, anchor, "600"))
    mini = [(d, labs.get(d, {}).get("minimax", 0)) for d in dates]
    md, mv = max(mini, key=lambda kv: kv[1])
    mx = xs[dates.index(md)]
    b.append(circ(mx, ysh(mv), 4.5, ORANGE))
    b.append(txt(mx + 8, ysh(mv) - 8, f"MiniMax peaked at {mv:.0f}%", 10.5, INK, weight="600"))

    for x, d in _date_ticks(dates, W, L, R):
        b.append(txt(x, BOT_T + BOT_H + 20, _fmt_date(d), 9.5, MUTE, "middle"))

    yb = H - 78
    b.append(line(34, yb - 18, W - 34, yb - 18, GRID, 1))
    b.append(txt(34, yb + 2, f"DeepSeek went from {first_deep:.0f}% to {last_deep:.0f}% in eight "
                 f"weeks; Meta fell from {labs.get(first, {}).get('meta', 0):.0f}% to "
                 f"{labs.get(last, {}).get('meta', 0):.0f}%.", 12, INK, weight="600"))
    b.append(txt(34, yb + 22, "OpenCode is one coding client, not the market. A lab share here "
                 "is who that client's users route to, not who is winning.", 10.5, MUTE))
    b.append(txt(34, H - 6, f"Source: OpenCode Data (opencode.ai/data), snapshot {as_of()}.",
                 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(dates)} days, {len(top)} labs, deepseek {first_deep:.0f}%→{last_deep:.0f}%"


def model_share(out=CHARTS / "opencode-model-share.svg") -> str:
    daily = opencode_daily()
    dates = daily["dates"]
    if len(dates) < 14:
        return "opencode-model-share.svg skipped: too few OpenCode days"
    names, _ = opencode_names(opencode_latest())
    # 7-day trailing mean share, so a single launch day does not define a peak.
    smooth: dict[str, list[float]] = {}
    for i in range(6, len(dates)):
        window = dates[i - 6:i + 1]
        tot = sum(daily["total"].get(d, 0) for d in window)
        if not tot:
            continue
        models = set()
        for d in window:
            models.update(daily["model_tokens"].get(d, {}))
        for m in models:
            smooth.setdefault(m, [0.0] * (len(dates) - 6))
            smooth[m][i - 6] = sum(daily["model_tokens"].get(d, {}).get(m, 0) for d in window) / tot
    if not smooth:
        return "opencode-model-share.svg skipped: no model series"
    # top by peak, with the residual bucket kept separate
    peak = {m: max(v) for m, v in smooth.items() if m != "other"}
    top = [m for m, _ in sorted(peak.items(), key=lambda kv: -kv[1])][:5]
    show_dates = dates[6:]
    W, H = 1060, 660
    L, R = 78, 228
    T, PH = 170, 350
    xs = [L + i / max(1, len(show_dates) - 1) * (W - L - R) for i in range(len(show_dates))]
    ymax = max(peak.values()) * 1.10
    sy = lambda v: T + PH - v / ymax * PH  # noqa: E731
    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(34, 40, "A new model can take the client in weeks", 20, INK, weight="600"))
    b.append(txt(34, 64, f"Seven-day mean share of OpenCode tokens, {_fmt_date(show_dates[0])} to "
                 f"{_fmt_date(show_dates[-1])} 2026. The 56-day window is too short to measure",
                 12.5, MUTE))
    b.append(txt(34, 82, "shelf life; it is long enough to see displacement.", 12.5, MUTE))
    b += _legend([(names.get(m, short_model(m, 24)), MODEL_COLOURS[i % len(MODEL_COLOURS)])
                  for i, m in enumerate(top)] + [("all other models", "#b8b7b0")], 112, W)
    for v in range(0, int(ymax * 100) + 1, 20):
        yy = sy(v / 100)
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{v:.0f}%", 10, MUTE, "end"))
    b.append(txt(24, T - 28, "share of tokens", 12, INK, weight="600"))
    b.append(txt(24, T - 13, "7-day mean", 10, MUTE))
    for i, m in enumerate(top):
        col = MODEL_COLOURS[i % len(MODEL_COLOURS)]
        pts = [(x, sy(v)) for x, v in zip(xs, smooth[m])]
        b.append(polyline(pts, col, 2.1))
    other = []
    for j in range(len(show_dates)):
        other.append(sum(smooth[m][j] for m in smooth if m not in top and m != "other"))
    b.append(polyline([(x, sy(v)) for x, v in zip(xs, other)], "#b8b7b0", 1.4, 0.8, dash="4 4"))
    if "other" in smooth:
        b.append(polyline([(x, sy(v)) for x, v in zip(xs, smooth["other"])], "#d2d0c8", 1.2, 0.7, dash="2 4"))

    # The story labels: the end of the leader, and the peak of the challenger.
    lead = top[0]
    b.append(circ(xs[-1], sy(smooth[lead][-1]), 4.5, MODEL_COLOURS[0]))
    b.append(txt(xs[-1] + 9, sy(smooth[lead][-1]) + 4,
                 f"{names.get(lead, short_model(lead, 26))} {smooth[lead][-1]:.0%}",
                 10.5, INK, weight="600"))
    mini = smooth.get("minimax-m3.1-flash", [])
    if mini:
        mi = max(range(len(mini)), key=lambda i: mini[i])
        b.append(circ(xs[mi], sy(mini[mi]), 4.5, ORANGE))
        b.append(txt(xs[mi] + 8, sy(mini[mi]) - 8, f"MiniMax peaked at {mini[mi]:.0%}",
                     10.5, INK, weight="600"))
    muse = smooth.get("muse-spark-1.3-contributor", [])
    if muse:
        mi = max(range(len(muse)), key=lambda i: muse[i])
        b.append(circ(xs[mi], sy(muse[mi]), 4.5, AQUA))
        b.append(txt(xs[mi] + 8, sy(muse[mi]) - 8, f"Muse peaked at {muse[mi]:.0%}",
                     10.5, INK, weight="600"))

    for x, d in _date_ticks(show_dates, W, L, R):
        b.append(txt(x, T + PH + 20, _fmt_date(d), 9.5, MUTE, "middle"))
    yb = H - 82
    b.append(line(34, yb - 18, W - 34, yb - 18, GRID, 1))
    top_now = max(top, key=lambda m: smooth[m][-1])
    mini_peak = max(smooth.get("minimax-m3.1-flash", [0]))
    b.append(txt(34, yb + 2, f"{names.get(top_now, short_model(top_now, 26))} ends the window at "
                 f"{smooth[top_now][-1]:.0%} of tokens; MiniMax's spike peaked at "
                 f"{mini_peak:.0%} on a 7-day mean.", 12, INK, weight="600"))
    b.append(txt(34, yb + 22, "A model can arrive, peak and fade inside eight weeks. That is a "
                 "switching-cost finding, not a forecast of shelf life.", 10.5, MUTE))
    b.append(txt(34, H - 6, f"Source: OpenCode Data (opencode.ai/data), snapshot {as_of()}.",
                 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(top)} models, {len(show_dates)} days"


def tokens_vs_spend(out=CHARTS / "opencode-tokens-vs-spend.svg") -> str:
    tok, start, end = opencode_window_tokens(28)
    latest = opencode_latest()
    _, labs = opencode_names(latest)
    if not tok:
        return "opencode-tokens-vs-spend.svg skipped: no OpenCode tokens"
    tok_lab: collections.Counter = collections.Counter()
    rev_lab: collections.Counter = collections.Counter()
    total = sum(tok.values())
    priced = 0.0
    for m, v in tok.items():
        p = opencode_value(latest, f"model:{m}", "price_input_usd_per_mtok")
        if p is None or p <= 0:
            continue
        l = labs.get(m, m)
        tok_lab[l] += v
        rev_lab[l] += v * p
        priced += v
    if not tok_lab:
        return "opencode-tokens-vs-spend.svg skipped: no priced OpenCode models"
    tt, tr = sum(tok_lab.values()), sum(rev_lab.values())
    pts = [{"lab": l, "t": tok_lab[l] / tt, "r": rev_lab[l] / tr, "abs": tok_lab[l]} for l in tok_lab]
    maxv = max(max(p["t"] for p in pts), max(p["r"] for p in pts)) * 1.12
    W, L, T, P, R = 1000, 132, 238, 520, 190
    H = T + P + 210
    sx = lambda v: L + v / maxv * P  # noqa: E731
    sy = lambda v: T + P - v / maxv * P  # noqa: E731
    sr = lambda a: 5 + (a / max(x["abs"] for x in pts)) ** 0.5 * 15  # noqa: E731
    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(40, 44, "Tokens are not money, even inside one client", 20, INK, weight="600"))
    b.append(txt(40, 70, f"Every lab in OpenCode's latest 28 complete days ({start} to {end}). "
                 "Across: its share of tokens. Up: its share of", 13, MUTE))
    b.append(txt(40, 89, "what those tokens cost at input list price. The dashed line is parity: "
                 "paid exactly in proportion to what it serves.", 13, MUTE))
    bt = max(pts, key=lambda p: p["t"])
    below = max((p for p in pts if p["r"] < p["t"]), key=lambda p: p["r"], default=bt)
    b.append(txt(40, 115, f"{label_lab(bt['lab'])} serves {bt['t']:.0%} of the tokens and takes "
                 f"{bt['r']:.0%} of the spend. {label_lab(below['lab'])} serves {below['t']:.0%} "
                 f"and takes {below['r']:.0%}.", 12, MUTE))
    for v in [i / 10 for i in range(0, 11) if i / 10 <= maxv]:
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
    marks = [(sx(p["t"]), sy(p["r"]), sr(p["abs"])) for p in pts]
    for p in sorted(pts, key=lambda p: -p["abs"]):
        col = ORANGE if p["lab"] in CN_LABS else BLUE
        b.append(circ(sx(p["t"]), sy(p["r"]), sr(p["abs"]), col))
    taken: list[tuple[float, float, float, float]] = []

    def free(bx):
        return not (
            any(bx[0] < o[2] and o[0] < bx[2] and bx[1] < o[3] and o[1] < bx[3] for o in taken)
            or any(bx[0] < cx + rr and cx - rr < bx[2] and bx[1] < cy + rr and cy - rr < bx[3]
                   for cx, cy, rr in marks)
        )

    for p in sorted(pts, key=lambda p: -max(p["t"], p["r"])):
        if max(p["t"], p["r"]) < 0.03:
            continue
        lab_s = f"{label_lab(p['lab'])}  {p['t']:.0%} / {p['r']:.0%}"
        x, y, rr = sx(p["t"]), sy(p["r"]), sr(p["abs"])
        w = len(lab_s) * 6.2 + 10
        for dy in (0, -15, 15, -30, 30, -45, 45):
            for anc in ("start", "end"):
                x0 = x + rr + 7 if anc == "start" else x - rr - 7 - w
                bx = (x0, y + dy - 8, x0 + w, y + dy + 6)
                if bx[0] < 44 or bx[2] > W - 30 or not free(bx):
                    continue
                taken.append(bx)
                b.append(txt(x + (rr + 7 if anc == "start" else -rr - 7), y + dy + 4,
                             lab_s, 11, INK, anc))
                break
            else:
                continue
            break
    b.append(circ(W - R + 44, T + 10, 7, ORANGE))
    b.append(txt(W - R + 58, T + 14, "Chinese lab", 11.5, MUTE))
    b.append(circ(W - R + 44, T + 34, 7, BLUE))
    b.append(txt(W - R + 58, T + 38, "everyone else", 11.5, MUTE))
    yb = T + P + 88
    b.append(line(40, yb - 26, W - 40, yb - 26, GRID, 1))
    b.append(txt(40, yb, f"DeepSeek is the only big lab above parity: it serves {bt['t']:.0%} of "
                 f"tokens and takes {bt['r']:.0%} of spend. The cheap models serve more than they "
                 "are paid.", 12.5, INK, weight="600"))
    b.append(txt(40, yb + 24, f"Input-token list price only, on the {priced / total:.0%} of tokens "
                 "that join to a price. Completion tokens cost more and are not counted; nobody "
                 "large pays list.", 11, MUTE))
    b.append(txt(40, yb + 42, "This is OpenCode's own traffic, not the market: one coding client, "
                 "developer-skewed, and its own model mix.", 11, MUTE))
    b.append(txt(40, H - 6, f"Source: OpenCode Data (opencode.ai/data), {start} to {end}; "
                 f"snapshot {as_of()}.", 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(pts)} labs, {priced / total:.0%} of tokens priced"


def session_cost(out=CHARTS / "opencode-session-cost.svg") -> str:
    tok, start, end = opencode_window_tokens(28)
    latest = opencode_latest()
    names, labs = opencode_names(latest)
    pts = []
    total = sum(tok.values())
    for m, v in tok.items():
        cost = opencode_value(latest, f"model:{m}", "session_cost_usd")
        tps = opencode_value(latest, f"model:{m}", "tokens_per_session")
        if cost is None or tps is None or cost <= 0 or tps <= 0 or v <= 0:
            continue
        pts.append({"m": m, "cost": cost, "tps": tps, "sh": v / total,
                    "lab": labs.get(m, ""), "name": names.get(m, short_model(m, 22))})
    if len(pts) < 3:
        return "opencode-session-cost.svg skipped: too few session-cost models"
    pts.sort(key=lambda p: p["cost"])
    W, H = 980, 660
    L, R, T, B = 120, 280, 160, 130
    xlo = min(p["tps"] for p in pts) * 0.75
    xhi = max(p["tps"] for p in pts) * 1.30
    ylo = min(p["cost"] for p in pts) * 0.65
    yhi = max(p["cost"] for p in pts) * 1.55
    plot_bottom = H - B
    lx = lambda v: L + (math.log10(v) - math.log10(xlo)) / (math.log10(xhi) - math.log10(xlo)) * (W - L - R)  # noqa: E731
    ly = lambda v: plot_bottom - (math.log10(v) - math.log10(ylo)) / (math.log10(yhi) - math.log10(ylo)) * (plot_bottom - T)  # noqa: E731
    b = [rect(0, 0, W, H, "#ffffff")]
    spread = max(p["cost"] for p in pts) / min(p["cost"] for p in pts)
    b.append(txt(34, 40, f"One session costs {spread:,.0f}× across {len(pts)} models", 20, INK, weight="600"))
    b.append(txt(34, 64, "Published average cost and tokens per OpenCode session. Both axes are log "
                 "scales; bubble area is share of tokens.", 12.5, MUTE))
    b.append(txt(34, 82, "A cheap per-token price and a cheap session are not the same thing.", 12.5, MUTE))
    for p in (0.001, 0.002, 0.005, 0.01, 0.02, 0.05):
        if ylo <= p <= yhi:
            yy = ly(p)
            b.append(line(L, yy, W - R, yy, GRID, 1))
            b.append(txt(L - 10, yy + 4, f"${p:g}", 10, MUTE, "end"))
    for p in (1e6, 2e6, 5e6, 1e7):
        if xlo <= p <= xhi:
            xx = lx(p)
            b.append(line(xx, T, xx, plot_bottom, GRID, 1))
            b.append(txt(xx, plot_bottom + 20, f"{p / 1e6:.0f}M", 10, MUTE, "middle"))
    b.append(txt(L - 10, T - 28, "cost per session", 12, INK, "end", "600"))
    b.append(txt((L + W - R) / 2, plot_bottom + 44, "tokens per session", 12, INK, "middle", "600"))
    for p in sorted(pts, key=lambda p: -p["sh"]):
        col = ORANGE if p["lab"] in CN_LABS else BLUE
        r = 6 + (p["sh"] / max(x["sh"] for x in pts)) ** 0.5 * 14
        b.append(circ(lx(p["tps"]), ly(p["cost"]), r, col, "#ffffff", 2))

    # Right-hand labels, clamped into the plot and spaced against each other.
    labels = sorted(((ly(p["cost"]), p) for p in pts), key=lambda t: t[0])
    placed: list[float] = []
    for y0, p in labels:
        y = min(max(y0, T + 12), plot_bottom - 16)
        while any(abs(y - q) < 30 for q in placed):
            y += 30
        if y > plot_bottom - 16:
            y = y0
        placed.append(y)
        b.append(line(lx(p["tps"]) + 10, y0, W - R + 14, y, "#c9c7bf", 1))
        b.append(txt(W - R + 20, y - 3, p["name"], 10.5, INK, weight="600"))
        b.append(txt(W - R + 20, y + 10, f"${p['cost']:.4f} · {p['tps'] / 1e6:.2f}M tokens · "
                     f"{p['sh']:.0%} of tokens", 9.5, MUTE))

    b.append(line(34, plot_bottom + 66, W - 34, plot_bottom + 66, GRID, 1))
    b.append(txt(34, plot_bottom + 88, f"The cheapest session is {pts[0]['name']} at "
                 f"${pts[0]['cost']:.4f}; the dearest is {pts[-1]['name']} at "
                 f"${pts[-1]['cost']:.4f}. The dearest also carries "
                 f"{pts[-1]['tps'] / 1e6:.1f}M tokens.", 12, INK, weight="600"))
    b.append(txt(34, plot_bottom + 108, "These are publisher averages, not recomputed from list "
                 "prices. Session length and cache mix differ; this is not a quality ranking.",
                 10.5, MUTE))
    b.append(txt(34, H - 8, f"Source: OpenCode Data (opencode.ai/data), snapshot {as_of()}.",
                 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(pts)} models, {spread:,.0f}× spread"


def retention_vs_usage(out=CHARTS / "opencode-retention-vs-usage.svg") -> str:
    tok, start, end = opencode_window_tokens(28)
    latest = opencode_latest()
    names, labs = opencode_names(latest)
    total = sum(tok.values())
    pts = []
    for m, v in tok.items():
        ret = opencode_value(latest, f"model:{m}", "retention_pct")
        if ret is None or v <= 0:
            continue
        cost = opencode_value(latest, f"model:{m}", "session_cost_usd")
        tps = opencode_value(latest, f"model:{m}", "tokens_per_session")
        eff = cost / tps * 1e6 if cost and tps else None
        pts.append({
            "m": m, "ret": ret, "sh": v / total,
            "eff": eff, "lab": labs.get(m, "other"),
            "name": names.get(m, short_model(m, 22)),
        })
    if len(pts) < 4:
        return "opencode-retention-vs-usage.svg skipped: too few models with retention"

    def corr(a, b):
        n = len(a)
        ma, mb = sum(a) / n, sum(b) / n
        return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(
            sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))

    r = corr([p["ret"] for p in pts], [p["sh"] for p in pts])
    rho = spearman([p["ret"] for p in pts], [p["sh"] for p in pts])
    price_pts = [p for p in pts if p["eff"]]
    rp = spearman([p["ret"] for p in price_pts], [p["eff"] for p in price_pts]) if len(price_pts) >= 3 else 0

    snapshots = []
    for snap in opencode_archives():
        shares, lo, hi = opencode_payload_window(snap["payload"], 28)
        rets = {}
        for row in snap["payload"].get("weeklyRetention") or []:
            try:
                rets[row["model"]] = float(row["retentionPercent"])
            except (TypeError, ValueError, KeyError):
                continue
        common = [m for m in shares if m in rets and m != "Other" and shares[m] > 0]
        if len(common) >= 3:
            snapshots.append({
                "date": snap["date"],
                "updated_at": snap["updated_at"],
                "source": snap["source"],
                "n": len(common),
                "rho": spearman([rets[m] for m in common], [shares[m] for m in common]),
            })
    snapshots.sort(key=lambda s: s["date"])

    W, H = 1060, 1010
    L1, R1 = 100, 100
    L2, R2 = 640, 100
    T, PH = 180, 300
    plot_bottom = T + PH
    BOT_T, BOT_H = 640, 190
    bot_bottom = BOT_T + BOT_H
    xlo, xhi = 60, 82
    yhi = max(p["sh"] for p in pts) * 1.16
    sx = lambda v: L1 + (v - xlo) / (xhi - xlo) * (470 - L1)  # noqa: E731
    sy = lambda v: plot_bottom - v / yhi * (plot_bottom - T)  # noqa: E731
    plo, phi = 0.0002, 0.03
    lx = lambda v: L2 + (math.log10(v) - math.log10(plo)) / (math.log10(phi) - math.log10(plo)) * (960 - L2)  # noqa: E731
    py = lambda v: plot_bottom - (v - 58) / (82 - 58) * (plot_bottom - T)  # noqa: E731

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(34, 40, "Retention does not pick the winner either", 20, INK, weight="600"))
    b.append(txt(34, 64, f"{len(pts)} models with both a retention and a token series. Across: "
                 "weekly retention. Up: share of OpenCode tokens.", 12.5, MUTE))
    b.append(txt(34, 82, f"Correlation is {r:+.2f} (Pearson), rank rho={rho:+.2f}. A model can be "
                 "sticky and small; a model can be leaky and huge.", 12.5, MUTE))
    b.append(txt(L1, T - 46, "Retention vs usage", 12, INK, weight="600"))
    b.append(txt(L2, T - 46, "Retention vs effective price", 12, INK, weight="600"))
    b.append(txt(L2, T - 9, f"session cost per 1M tokens · rho={rp:+.2f}, n={len(price_pts)}",
                 9.5, MUTE))

    for v in range(60, 83, 5):
        xx = sx(v)
        b.append(line(xx, T, xx, plot_bottom, GRID, 1))
        b.append(txt(xx, plot_bottom + 20, f"{v}%", 10, MUTE, "middle"))
    for v in range(0, int(yhi * 100) + 1, 10):
        yy = sy(v / 100)
        b.append(line(L1, yy, 470, yy, GRID, 1))
        b.append(txt(L1 - 10, yy + 4, f"{v}%", 10, MUTE, "end"))
    b.append(txt(24, T - 28, "share of tokens", 11.5, INK, weight="600"))
    b.append(txt((L1 + 470) / 2, plot_bottom + 44, "weekly retention", 11.5, INK,
                 "middle", "600"))
    for p in sorted(pts, key=lambda p: -p["sh"]):
        b.append(circ(sx(p["ret"]), sy(p["sh"]), 7,
                      LAB_COLOURS.get(p["lab"], MODEL_COLOURS[0])))
    for p in sorted(pts, key=lambda p: -p["sh"]):
        x, y = sx(p["ret"]), sy(p["sh"])
        if p["name"].startswith("GLM"):
            b.append(txt(x - 11, y - 4, f"{p['name']}  {p['sh']:.0%}", 10.5, INK, "end"))
        elif p["name"].startswith("Beam"):
            b.append(txt(x + 11, y + 12, f"{p['name']}  {p['sh']:.0%}", 10.5, INK))
        else:
            b.append(txt(x + 11, y + 4, f"{p['name']}  {p['sh']:.0%}", 10.5, INK))

    # Price panel: the closest thing to a discount-adjusted price in this feed.
    for v in (0.0003, 0.001, 0.003, 0.01, 0.03):
        xx = lx(v)
        b.append(line(xx, T, xx, plot_bottom, GRID, 1))
        b.append(txt(xx, plot_bottom + 20, f"${v:g}", 9.5, MUTE, "middle"))
    for v in range(60, 81, 5):
        yy = py(v)
        b.append(line(L2, yy, 960, yy, GRID, 1))
        b.append(txt(L2 - 10, yy + 4, f"{v}%", 10, MUTE, "end"))
    b.append(txt(L2 - 14, T - 28, "weekly retention", 11.5, INK, "end", "600"))
    b.append(txt((L2 + 960) / 2, plot_bottom + 44, "effective price per 1M tokens (log)",
                 11.5, INK, "middle", "600"))
    price_labels = {
        "minimax-m3.1-flash": "MiniMax",
        "mimo-v2.6-flash": "MiMo",
        "muse-spark-1.3-contributor": "Muse",
        "deepseek-v4.1-flash": "DS V4.1",
        "glm-5.3-flash": "GLM-5.3",
    }
    for p in sorted(price_pts, key=lambda p: p["eff"]):
        x, y = lx(p["eff"]), py(p["ret"])
        col = LAB_COLOURS.get(p["lab"], MODEL_COLOURS[0])
        b.append(circ(x, y, 6, col))
        label = price_labels.get(p["m"], short_model(p["m"], 14))
        if p["m"] in {"muse-spark-1.3-contributor", "glm-5.3-flash"}:
            b.append(txt(x - 9, y + 4, label, 9.5, INK, "end"))
        else:
            b.append(txt(x + 9, y + 4, label, 9.5, INK))

    if len(snapshots) >= 2:
        b.append(txt(L1, BOT_T - 30, "The retention–usage correlation is not stable", 12,
                     INK, weight="600"))
        b.append(txt(L1, BOT_T - 12, "Retention snapshot × trailing 28-day usage; one point per "
                     f"archived snapshot. n={min(s['n'] for s in snapshots)}–{max(s['n'] for s in snapshots)}.",
                     10.5, MUTE))
        for v in (-1, -0.5, 0, 0.5, 1):
            yy = bot_bottom - (v + 1) / 2 * BOT_H
            b.append(line(L1, yy, W - R1, yy, GRID, 1))
            b.append(txt(L1 - 10, yy + 4, f"{v:+.1f}", 10, MUTE, "end"))
        b.append(txt(L1 - 14, BOT_T - 8, "rank corr", 11.5, INK, "end", "600"))
        d0 = date.fromisoformat(snapshots[0]["date"])
        d1 = date.fromisoformat(snapshots[-1]["date"])
        span = max(1, (d1 - d0).days)
        xs = [L1 + (date.fromisoformat(s["date"]) - d0).days / span * (W - L1 - R1)
              for s in snapshots]
        ys = [bot_bottom - (s["rho"] + 1) / 2 * BOT_H for s in snapshots]
        b.append(polyline(list(zip(xs, ys)), BLUE, 2.2))
        b.append(line(L1, bot_bottom - BOT_H / 2, W - R1, bot_bottom - BOT_H / 2, "#c9c7bf", 1))
        for s, x, y in zip(snapshots, xs, ys):
            b.append(circ(x, y, 4.5, BLUE, "#ffffff", 1.5))
            b.append(txt(x, y - 10, f"{s['rho']:+.2f}", 10, INK, "middle", "600"))
            b.append(txt(x, bot_bottom + 20, _fmt_date(s["date"]), 9.5, MUTE, "middle"))
    else:
        b.append(txt(L1, BOT_T - 20, "Rolling correlation skipped: need at least two archived "
                     "OpenCode snapshots.", 11, MUTE))

    yb = 880
    b.append(line(34, yb, W - 34, yb, GRID, 1))
    b.append(txt(34, yb + 22, f"The highest-retention model is not the most-used, and the "
                 f"most-used is not the stickiest. n={len(pts)}; a correlation this small is not "
                 "evidence.", 12, INK, weight="600"))
    b.append(txt(34, yb + 44, "No promotional-discount field exists in OpenCode's feed. Effective "
                 "price is session cost ÷ tokens per session: it includes cache and token mix, "
                 "not a discount.", 10.5, MUTE))
    if snapshots:
        src = ", ".join(f"{_fmt_date(s['date'])}" for s in snapshots)
        b.append(txt(34, yb + 64, f"Retention snapshots: {src}; historical points are Internet "
                     "Archive copies, not repo captures.", 10.5, MUTE))
    stamp = snapshots[-1]["updated_at"] if snapshots else as_of()
    b.append(txt(34, H - 8, f"Source: OpenCode Data (opencode.ai/data), snapshot {stamp}; "
                 "historical snapshots: Internet Archive.", 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(pts)} models, r={r:+.2f}, rho={rho:+.2f}, price rho={rp:+.2f}"


COUNTRY_NAMES = {
    "CN": "China", "US": "United States", "IN": "India", "DE": "Germany",
    "BR": "Brazil", "JP": "Japan", "ID": "Indonesia", "SG": "Singapore",
    "FR": "France", "RU": "Russia", "ES": "Spain", "GB": "United Kingdom",
    "NL": "Netherlands", "VN": "Vietnam", "TR": "Türkiye", "HK": "Hong Kong",
    "CA": "Canada", "EG": "Egypt", "KR": "South Korea", "IT": "Italy",
}


def geography(out=CHARTS / "opencode-geography.svg") -> str:
    snapshots = opencode_archives()
    if len(snapshots) < 2:
        return "opencode-geography.svg skipped: need at least two OpenCode snapshots"
    shares = []
    for snap in snapshots:
        cs = {}
        for row in snap["payload"].get("countries") or []:
            try:
                cs[row["country"]] = float(row["sharePercent"])
            except (TypeError, ValueError, KeyError):
                continue
        shares.append((snap, cs))
    latest = shares[-1][1]
    top = [c for c, _ in sorted(latest.items(), key=lambda kv: -kv[1])[:6]]
    if len(top) < 5:
        return "opencode-geography.svg skipped: too few countries"

    W, H = 1060, 760
    L, R, T, PH = 90, 230, 170, 400
    plot_bottom = T + PH
    vmax = max(cs.get(c, 0) for _, cs in shares for c in top) * 1.18
    span = W - L - R
    d0 = date.fromisoformat(snapshots[0]["date"])
    d1 = date.fromisoformat(snapshots[-1]["date"])
    days = max(1, (d1 - d0).days)
    xs = [L + (date.fromisoformat(s["date"]) - d0).days / days * span for s, _ in shares]
    y_of = lambda v: plot_bottom - v / vmax * PH  # noqa: E731
    colours = [BLUE, ORANGE, AQUA, VIOLET, MUTE, "#8f6bb3"]
    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(34, 40, "The country mix barely moved in October", 20, INK, weight="600"))
    b.append(txt(34, 64, "Share of OpenCode tokens by inferred country, three snapshots: "
                 f"{_fmt_date(snapshots[0]['date'])}, {_fmt_date(snapshots[1]['date'])}, "
                 f"{_fmt_date(snapshots[-1]['date'])} 2026.", 12.5, MUTE))
    first, last = shares[0][1], shares[-1][1]
    b.append(txt(34, 82, f"China {first.get('CN', 0):.1f}% to {last.get('CN', 0):.1f}%; United "
                 f"States {first.get('US', 0):.1f}% to {last.get('US', 0):.1f}%; India "
                 f"{first.get('IN', 0):.1f}% to {last.get('IN', 0):.1f}%.", 12.5, MUTE))
    for v in range(0, int(vmax) + 1, 5):
        yy = y_of(v)
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{v}%", 10, MUTE, "end"))
    b.append(txt(24, T - 28, "share of tokens", 12, INK, weight="600"))
    for i, c in enumerate(top):
        pts = [(x, y_of(cs.get(c, 0))) for x, (_, cs) in zip(xs, shares)]
        b.append(polyline(pts, colours[i % len(colours)], 2.0))
        for x, y in pts:
            b.append(circ(x, y, 4.0, colours[i % len(colours)], "#ffffff", 1.2))
    ends = [(y_of(latest.get(c, 0)), f"{COUNTRY_NAMES.get(c, c)}  {latest.get(c, 0):.1f}%",
             colours[i % len(colours)], "") for i, c in enumerate(top)]
    b += _label_ends(ends, W, R)
    for x, snap in zip(xs, snapshots):
        b.append(txt(x, plot_bottom + 20, _fmt_date(snap["date"]), 10, MUTE, "middle"))
    b.append(line(34, plot_bottom + 48, W - 34, plot_bottom + 48, GRID, 1))
    b.append(txt(34, plot_bottom + 72, "Top six shown; the remaining countries are a "
                 f"{100 - sum(latest.get(c, 0) for c in top):.0f}% long tail. Country is inferred "
                 "by the publisher; not a user census.", 11.5, INK, weight="600"))
    b.append(txt(34, plot_bottom + 94, "Only three snapshots exist: 2 Oct and 15 Oct are Internet "
                 "Archive copies of the publisher's live JSON; 26 Oct is the first repo capture. "
                 "Future weekly captures extend this series.", 10.5, MUTE))
    b.append(txt(34, H - 8, f"Source: OpenCode Data (opencode.ai/data), snapshot "
                 f"{snapshots[-1]['updated_at']}; historical snapshots: Internet Archive.",
                 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return f"{out.relative_to(CHARTS.parent)} — {len(top)} countries, {len(snapshots)} snapshots"


def vs_openrouter(out=CHARTS / "opencode-vs-openrouter.svg") -> str:
    """Scatter the same models two ways, then roll the rank correlation.

    The scatter uses 28 complete days on both sides. The rolling panel uses a
    28-day window and averages ranks rather than tokens: a token-weighted
    correlation would be a restatement of DeepSeek's share, not a test of
    whether the two audiences agree. Dollar weighting is unavailable because
    OpenCode publishes session cost, not per-model revenue.
    """
    if not (WORK / "rankings-daily.csv").exists():
        return "opencode-vs-openrouter.svg skipped: no OpenRouter archive cache"
    rows = rankings()
    or_dates = sorted({r["date"] for r in rows})
    if not or_dates:
        return "opencode-vs-openrouter.svg skipped: no OpenRouter cache"
    end = date.fromisoformat(or_dates[-1])
    if end >= date.today():
        end = end - timedelta(days=1)
    start = (end - timedelta(days=27)).isoformat()
    or_by_date: dict[str, dict[str, int]] = collections.defaultdict(dict)
    for r in rows:
        or_by_date[r["date"]][r["model_permaslug"]] = r["tok"]

    daily = opencode_daily()
    oc_dates = daily["dates"]
    if len(oc_dates) < 28:
        return "opencode-vs-openrouter.svg skipped: too few OpenCode days"
    names, labs = opencode_names(opencode_latest())
    oc_window = oc_dates[-28:]
    oc_total = sum(daily["total"].get(d, 0) for d in oc_window)
    oc_tot: collections.Counter = collections.Counter()
    for d in oc_window:
        for m, v in daily["model_tokens"].get(d, {}).items():
            oc_tot[m] += v

    or_window = [r for r in rows if start <= r["date"] <= end.isoformat()]
    or_total = sum(r["tok"] for r in or_window)
    or_counts: collections.Counter = collections.Counter()
    for r in or_window:
        if r["model_permaslug"] != "other":
            or_counts[r["model_permaslug"]] += r["tok"]

    def or_value(ors: str) -> int:
        base = ors.split(":")[0]
        return sum(v for s, v in or_counts.items() if s == ors or s.split(":")[0] == base)

    pts = []
    for oc, ors in OC_TO_OR.items():
        if oc not in oc_tot:
            continue
        orv = or_value(ors)
        if not orv:
            continue
        pts.append({"oc": oc, "or": ors, "orv": orv, "ocv": oc_tot[oc],
                    "orsh": orv / or_total if or_total else 0,
                    "ocsh": oc_tot[oc] / oc_total if oc_total else 0,
                    "lab": labs.get(oc, "other")})
    if len(pts) < 4:
        return f"opencode-vs-openrouter.svg skipped: only {len(pts)} models match"
    n = len(pts)
    rho = spearman([p["ocsh"] for p in pts], [p["orsh"] for p in pts])

    W = 1060
    H = 980
    L, R = 104, 300
    T, PH = 222, 330
    RT, RH = 650, 138
    lo = min(min(p["ocsh"] for p in pts), min(p["orsh"] for p in pts))
    hi = max(max(p["ocsh"] for p in pts), max(p["orsh"] for p in pts))
    xlo, xhi = math.log10(lo) - 0.25, math.log10(hi) + 0.15
    ylo, yhi = xlo, xhi
    sx = lambda v: L + (math.log10(v) - xlo) / (xhi - xlo) * (W - L - R)  # noqa: E731
    sy = lambda v: T + PH - (math.log10(v) - ylo) / (yhi - ylo) * PH  # noqa: E731

    b = [rect(0, 0, W, H, "#ffffff")]
    b.append(txt(34, 40, "OpenRouter's traffic does not predict OpenCode's", 20, INK, weight="600"))
    b.append(txt(34, 64, "The same matched models by share of tokens. Axes are log scales; the "
                 "diagonal is equal share. Above it, a model is bigger on OpenRouter than on "
                 "OpenCode.", 12.5, MUTE))
    b.append(txt(34, 82, f"Scatter: OpenRouter's latest 28 complete days ({start} to {end}) "
                 f"against OpenCode's latest 28 complete days ({oc_window[0]} to {oc_window[-1]}).",
                 12.5, MUTE))
    b.append(txt(34, 104, f"Spearman rank correlation {rho:+.2f} across {n} matched models. "
                 "The rolling panel asks whether that agreement is stable.", 12.5, MUTE))

    for power in range(math.floor(xlo), math.ceil(xhi) + 1):
        v = 10 ** power
        if not (10 ** xlo <= v <= 10 ** xhi):
            continue
        xx = sx(v)
        b.append(line(xx, T, xx, T + PH, GRID, 1))
        b.append(txt(xx, T + PH + 20, f"{v:.1%}" if v < 1 else f"{v:.0%}", 10, MUTE, "middle"))
        yy = sy(v)
        b.append(line(L, yy, W - R, yy, GRID, 1))
        b.append(txt(L - 10, yy + 4, f"{v:.1%}" if v < 1 else f"{v:.0%}", 10, MUTE, "end"))
    b.append(txt(L, T - 26, "OpenRouter share", 11.5, INK, weight="600"))
    b.append(txt((L + W - R) / 2, T + PH + 42, "OpenCode share (log scale)", 10.5, MUTE, "middle"))
    b.append(txt(L - 10, T - 10, "log", 9, MUTE, "end"))

    b.append(line(sx(10 ** xlo), sy(10 ** xlo), sx(10 ** xhi), sy(10 ** xhi),
                  "#c3c2b7", 1.2, dash="5 4"))
    b.append(txt(W - R, T + 16, "equal share", 9.5, MUTE, "end"))

    lab_tok: collections.Counter = collections.Counter()
    for p in pts:
        lab_tok[p["lab"]] += p["ocsh"]
    lab_col = {l: c for l, c in zip([x for x, _ in lab_tok.most_common(4)],
                                    (BLUE, ORANGE, AQUA, VIOLET))}
    for p in sorted(pts, key=lambda p: -p["ocsh"]):
        b.append(circ(sx(p["ocsh"]), sy(p["orsh"]), 6.5,
                      lab_col.get(p["lab"], "#b8b7b0"), stroke="#ffffff", sw=2))

    placed: list[tuple[float, float, float]] = []
    for p in sorted(pts, key=lambda p: -max(p["ocsh"], p["orsh"])):
        x, y = sx(p["ocsh"]), sy(p["orsh"])
        label = names.get(p["oc"], short_model(p["oc"], 26))
        w = len(label) * 5.8
        if x + 10 + w > W - R:
            lx, anchor, x0, x1 = x - 10, "end", x - 10 - w, x - 10
        else:
            lx, anchor, x0, x1 = x + 10, "start", x + 10, x + 10 + w
        ly = y
        while any(abs(ly - py) < 13 and not (x1 < bx0 or x0 > bx1) for bx0, bx1, py in placed):
            ly += 13
        placed.append((x0, x1, ly))
        b.append(txt(lx, ly + 4, label, 10.5, INK, anchor, "600"))

    # Rolling 28-day rank correlation, model and lab level.
    or_all: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in rows:
        if r["model_permaslug"] != "other":
            or_all[r["date"]][r["model_permaslug"]] += r["tok"]
    oc_labs = opencode_labs()
    model_roll, lab_roll = [], []
    for i in range(27, len(oc_dates)):
        end_d = oc_dates[i]
        win = oc_dates[i - 27:i + 1]
        oc_counts: collections.Counter = collections.Counter()
        for d in win:
            for m, v in daily["model_tokens"].get(d, {}).items():
                oc_counts[m] += v
        oc_win_total = sum(daily["total"].get(d, 0) for d in win)
        or_counts: collections.Counter = collections.Counter()
        for d in win:
            for m, v in or_all.get(d, {}).items():
                or_counts[m] += v
        or_win_total = sum(sum(or_all.get(d, {}).values()) for d in win)
        model_pts = []
        for oc, ors in OC_TO_OR.items():
            ocv = oc_counts.get(oc, 0)
            base = ors.split(":")[0]
            orv = sum(v for s, v in or_counts.items() if s == ors or s.split(":")[0] == base)
            if ocv > 0 and orv > 0:
                model_pts.append((ocv / oc_win_total, orv / or_win_total))
        if len(model_pts) >= 4:
            model_roll.append((end_d, len(model_pts),
                               spearman([p[0] for p in model_pts],
                                        [p[1] for p in model_pts])))

        oc_lab: collections.Counter = collections.Counter()
        for d in win:
            tot = daily["total"].get(d, 0)
            for l, pct in oc_labs.get(d, {}).items():
                oc_lab[l] += pct / 100 * tot
        or_lab: collections.Counter = collections.Counter()
        for model, v in or_counts.items():
            name = model.split("/")[0]
            or_lab["zhipu" if name == "z-ai" else name] += v
        common = [l for l in oc_lab if l in or_lab and l != "other"]
        if len(common) >= 4:
            lab_roll.append((end_d, len(common),
                             spearman([oc_lab[l] for l in common],
                                      [or_lab[l] for l in common])))

    b.append(line(34, RT - 46, W - 34, RT - 46, GRID, 1))
    b.append(txt(34, RT - 18, "Does the agreement persist? Rolling 28-day rank correlation",
                 13, INK, weight="600"))
    b.append(txt(34, RT + 1, "Model line: eight hand-matched models, equal weight. "
                 "Lab line: common labs, equal weight. Both are rank correlations.", 10.5, MUTE))
    ycorr = lambda v: RT + 30 + (1 - v) / 2 * (RH - 30)  # noqa: E731
    for v in (-1, -0.5, 0, 0.5, 1):
        yy = ycorr(v)
        b.append(line(L, yy, W - R, yy, GRID if v else "#c3c2b7", 1))
        b.append(txt(L - 10, yy + 4, f"{v:+.1f}".replace("+0.0", "0"), 10, MUTE, "end"))

    def roll_line(items, colour, dash=None):
        if not items:
            return
        xs = [L + idx / max(1, len(model_roll) - 1) * (W - L - R)
              for idx in range(len(items))]
        b.append(polyline([(x, ycorr(r)) for x, (_, _, r) in zip(xs, items)],
                          colour, 2.2, dash=dash))
        for x, (_, _, r) in zip(xs, items):
            b.append(circ(x, ycorr(r), 3.2, colour, stroke="#ffffff", sw=1.5))

    roll_line(model_roll, BLUE)
    roll_line(lab_roll, ORANGE, dash="5 4")
    if model_roll:
        for idx, (d, _, _) in enumerate(model_roll):
            if idx % 5 == 0 or idx == len(model_roll) - 1:
                x = L + idx / max(1, len(model_roll) - 1) * (W - L - R)
                b.append(txt(x, RT + 30 + RH, date.fromisoformat(d).strftime("%d %b"),
                             9, MUTE, "middle"))
    med = sorted(r for _, _, r in model_roll)[len(model_roll) // 2] if model_roll else 0
    b.append(txt(W - R, RT + 1,
                 f"models n={min((x[1] for x in model_roll), default=0)}–"
                 f"{max((x[1] for x in model_roll), default=0)}"
                 f" · labs n={max((x[1] for x in lab_roll), default=0)}", 10, MUTE, "end"))
    ly = RT + 20
    b.append(line(W - R - 142, ly - 4, W - R - 122, ly - 4, BLUE, 2.2))
    b.append(txt(W - R - 116, ly, f"models {model_roll[-1][2]:+.2f}" if model_roll else "models —",
                 10, BLUE, weight="600"))
    b.append(line(W - R - 56, ly - 4, W - R - 36, ly - 4, ORANGE, 2.2, dash="5 4"))
    b.append(txt(W - R - 30, ly, f"labs {lab_roll[-1][2]:+.2f}" if lab_roll else "labs —",
                 10, ORANGE, weight="600"))

    yb = H - 136
    b.append(line(34, yb - 24, W - 34, yb - 24, GRID, 1))
    b.append(txt(34, yb, f"Router traffic and client traffic do not move together. The latest "
                 f"rank correlation is {rho:+.2f}; the model-level rolling median is {med:+.2f} "
                 f"and the sign changes.", 12.5, INK, weight="600"))
    b.append(txt(34, yb + 22, "Rank-weighted on purpose: each matched model counts once. "
                 "Token-weighting would be dominated by DeepSeek, which is the thing being tested.",
                 10.5, MUTE))
    b.append(txt(34, yb + 40, "Dollar weights are unavailable because OpenCode publishes session "
                 "cost, not per-model revenue. The lab line is a coarser cross-check, not a law.",
                 10.5, MUTE))
    b.append(txt(34, yb + 58, f"Matched by hand across OpenCode slugs and OpenRouter permaslugs; "
                 f"{n} models. Free and paid variants of the same base model are aggregated.",
                 10.5, MUTE))
    b.append(txt(34, H - 8, f"Sources: OpenRouter rankings, as of {as_of()}; OpenCode Data "
                 f"(opencode.ai/data).", 9.5, MUTE))
    out.write_text(doc(W, H, b), encoding="utf-8")
    return (f"{out.relative_to(CHARTS.parent)} — {n} models, rho={rho:+.2f}, "
            f"rolling median {med:+.2f}")


def render_all() -> list[str]:
    return [lab_share(), model_share(), tokens_vs_spend(), session_cost(),
            retention_vs_usage(), geography(), vs_openrouter()]


if __name__ == "__main__":
    for line_out in render_all():
        print(line_out)
