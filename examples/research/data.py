"""Shared loaders for the research charts.

Two very different clocks live here:

* OpenRouter's archive is fetched on demand, because the publisher keeps it.
  It is cached under `examples/research/work/` (gitignored) and never committed.
* OpenCode's window is the rolling 56 days in `derived/observations/`, captured
  weekly because the publisher does not archive it.

No chart reads `raw/` directly. Stdlib only.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import re
import subprocess
import time
import urllib.parse
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHARTS = REPO / "examples" / "charts"
WORK = Path(os.environ.get("OR_WORK", REPO / "examples" / "research" / "work" / "openrouter"))
OC_ARCHIVE = WORK.parent / "opencode"
DERIVED = REPO / "derived" / "observations"
HF_ROOT = Path(os.environ.get(
    "HF_RAW",
    REPO.parent / "wss-hugging-face" / "raw" / "hf.models.text-generation",
))

# Labs headquartered in China, for the one grouping this research layer makes
# by hand. Same set as the cookbook recipe and examples/visualize.py.
CN_LABS = {
    "deepseek", "tencent", "xiaomi", "z-ai", "zhipu", "minimax", "alibaba",
    "moonshotai", "qwen", "stepfun", "baidu", "01-ai", "inclusionai",
    "dots-studio", "meituan",
}

LAB_LABEL = {
    "deepseek": "DeepSeek",
    "minimax": "MiniMax",
    "meta": "Meta",
    "xiaomi": "Xiaomi",
    "zhipu": "Zhipu",
    "reflection": "Reflection",
    "nvidia": "NVIDIA",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "z-ai": "Z.ai",
    "tencent": "Tencent",
    "moonshotai": "Moonshot",
    "qwen": "Qwen",
    "other": "other",
}


def label_lab(slug: str) -> str:
    return LAB_LABEL.get(slug, slug.replace("-", " ").title())


def short_model(slug: str, n: int = 24) -> str:
    return re.sub(r"-20\d{6}$", "", slug.split("/")[-1].split(":")[0])[:n]


def load_env() -> None:
    """Bring `.env.local` into the environment without printing credentials."""
    if os.environ.get("OPENROUTER_API_KEY"):
        return
    for name in (REPO / ".env.local", REPO / ".env"):
        if not name.exists():
            continue
        for line in name.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api_get(path: str, params: dict | None = None, *, auth: bool = True, timeout: int = 120) -> bytes:
    """Fetch JSON with curl.

    urllib stalled on the second large window in testing; curl did not. The
    fetch is an operator step, not a chart, so one external binary here is a
    better trade than a flaky network stack. The cookbook capture does the same.
    """
    load_env()
    url = "https://openrouter.ai/api/v1/" + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode(params)
    cmd = [
        "curl", "-sS", "--compressed", "--max-time", str(timeout),
        "-A", "q3dresearch-wss-openrouter/1.0 (+https://github.com/q3dresearch/wss-openrouter)",
    ]
    if auth:
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise SystemExit("OPENROUTER_API_KEY is not set; add it to .env.local")
        cmd += ["-H", f"Authorization: Bearer {key}"]
    cmd.append(url)
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{path}: curl timed out after {timeout}s") from exc
    if proc.returncode:
        raise RuntimeError(f"{path}: curl exited {proc.returncode}: {proc.stderr[:300]!r}")
    body = proc.stdout
    if not body:
        raise RuntimeError(f"{path}: empty response")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"{path}: API error: {str(payload['error'])[:300]}")
    return body


def _save(name: str, body: bytes, note: str) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / name
    path.write_bytes(body)
    man = WORK / "manifest.csv"
    new = not man.exists()
    with man.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["file", "bytes", "sha256_prefix", "fetched_at", "note"])
        import hashlib
        w.writerow([name, len(body), hashlib.sha256(body).hexdigest()[:16],
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), note])
    print(f"  fetched {name}: {len(body):,} bytes")
    return path


def _decode_json(raw: bytes):
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def _curl(url: str, timeout: int = 60) -> bytes:
    """Small download helper for the archive backfill.

    The OpenCode command is an operator step, not a chart. Keeping it in the
    same curl-based path as the OpenRouter fetch avoids adding a second network
    stack to the research layer.
    """
    cmd = [
        "curl", "-L", "-sS", "--compressed", "--max-time", str(timeout),
        "-A", "q3dresearch-wss-openrouter/1.0 (+https://github.com/q3dresearch/wss-openrouter)",
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"curl timed out after {timeout}s: {url}") from exc
    if proc.returncode:
        raise RuntimeError(f"curl exited {proc.returncode}: {proc.stderr[:300]!r}")
    if not proc.stdout:
        raise RuntimeError(f"empty response: {url}")
    return proc.stdout


def fetch_opencode_archives() -> None:
    """Backfill OpenCode snapshots from the Internet Archive.

    The publisher exposes only the current country table and the latest
    retention snapshot, so the repo's own weekly captures cannot answer a
    trend question yet. The Internet Archive has a handful of copies of the
    same first-party `index.json`; they are cached under `work/` like the
    OpenRouter archive and are never committed as raw captures.
    """
    OC_ARCHIVE.mkdir(parents=True, exist_ok=True)
    cdx = ("https://web.archive.org/cdx/search/cdx?url=opencode.ai/data/index.json"
           "&output=json&fl=timestamp,statuscode,digest&filter=statuscode:200"
           "&collapse=digest")
    try:
        rows = json.loads(_curl(cdx, timeout=45))
    except Exception as exc:
        print(f"  WARNING OpenCode archive index: {exc}", flush=True)
        return
    if not rows:
        return
    for row in rows[1:]:
        ts = row[0]
        path = OC_ARCHIVE / f"index-{ts}.json"
        if path.exists() and path.stat().st_size > 1000:
            print(f"  cached OpenCode archive {ts}", flush=True)
            continue
        try:
            raw = _curl(f"https://web.archive.org/web/{ts}id_/https://opencode.ai/data/index.json")
            payload = _decode_json(raw)
            path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            print(f"  fetched OpenCode archive {ts}: {len(raw):,} bytes", flush=True)
        except Exception as exc:
            print(f"  WARNING OpenCode archive {ts}: {exc}", flush=True)
        time.sleep(1.0)


def _date_windows(start: str, end: str, width: int = 180):
    from datetime import date, timedelta
    lo = date.fromisoformat(start)
    hi = date.fromisoformat(end)
    while lo <= hi:
        stop = min(lo + timedelta(days=width - 1), hi)
        yield lo.isoformat(), stop.isoformat()
        lo = stop + timedelta(days=1)


def _month_windows(start: str, end: str):
    """Calendar months, used for the app-ranking time series."""
    from datetime import date, timedelta
    lo = date.fromisoformat(start).replace(day=1)
    hi = date.fromisoformat(end).replace(day=1)
    while lo <= hi:
        stop = (lo.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        yield lo.isoformat(), stop.isoformat()
        lo = stop + timedelta(days=1)


def fetch_openrouter(start: str = "2025-01-01", end: str | None = None) -> None:
    """Fetch the archive the publisher keeps: rankings, benchmarks, catalog.

    We do **not** put these bytes in `raw/`, `manifest/` or `derived/`. That is
    the point of the repo's capture rule: a source that already keeps history is
    queried, not re-archived.
    """
    from datetime import date, timedelta
    end = end or date.today().isoformat()
    rows: list[dict] = []
    as_of = None
    for lo, hi in _date_windows(start, end):
        name = f"rankings-{lo}_{hi}.json"
        path = WORK / name
        if path.exists() and path.stat().st_size > 1000:
            print(f"  cached {name}", flush=True)
            body = path.read_bytes()
        else:
            print(f"  fetching rankings {lo}..{hi}", flush=True)
            body = api_get("datasets/rankings-daily", {"start_date": lo, "end_date": hi})
            _save(name, body, f"rankings {lo}..{hi}")
        payload = json.loads(body)
        chunk = payload.get("data") or []
        as_of = (payload.get("meta") or {}).get("as_of") or as_of
        rows += chunk
    with (WORK / "rankings-daily.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, ["date", "model_permaslug", "total_tokens"])
        w.writeheader()
        w.writerows({k: r.get(k) for k in w.fieldnames} for r in rows)

    # App rankings are a second archive: top-50 apps, tokens and requests,
    # any date window. The recipe reads four months; a monthly series is what
    # makes the app-mix panel a trend rather than two endpoints.
    last_complete = date.today().replace(day=1) - timedelta(days=1)
    for lo, hi in _month_windows("2025-01-01", last_complete.isoformat()):
        name = f"app-rankings-{lo}_{hi}.json"
        if (WORK / name).exists() and (WORK / name).stat().st_size > 1000:
            print(f"  cached {name}", flush=True)
            continue
        print(f"  fetching {name}", flush=True)
        body = api_get("datasets/app-rankings", {"start_date": lo, "end_date": hi}, timeout=60)
        _save(name, body, f"app rankings, {lo}..{hi}")
        time.sleep(0.6)  # 30 requests/minute

    for src in ("artificial-analysis", "openrouter", "design-arena"):
        name = f"benchmarks-{src}.json"
        if (WORK / name).exists() and (WORK / name).stat().st_size > 1000:
            print(f"  cached {name}", flush=True)
            continue
        print(f"  fetching {name}", flush=True)
        try:
            body = api_get("benchmarks", {"source": src, "max_results": 100}, timeout=60)
            _save(name, body, f"benchmark scores, {src}")
        except Exception as exc:  # a missing benchmark should not lose the rankings
            print(f"  WARNING {name}: {exc}", flush=True)
    name = "models-catalog.json"
    if not ((WORK / name).exists() and (WORK / name).stat().st_size > 1000):
        print(f"  fetching {name}", flush=True)
        body = api_get("models", auth=False, timeout=60)
        _save(name, body, "pricing, context length and hugging_face_id")
    (WORK / "as_of.txt").write_text(f"{as_of}\n", encoding="utf-8")
    print(f"  rankings: {len(rows):,} rows, as_of {as_of}")


def rankings() -> list[dict]:
    path = WORK / "rankings-daily.csv"
    if not path.exists():
        raise SystemExit(f"no OpenRouter cache at {path}; run `python examples/research/run.py --fetch`")
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for r in rows:
        r["tok"] = int(r["total_tokens"])
    return rows


def app_rankings() -> list[dict]:
    """Every cached monthly app-ranking window, oldest first."""
    out = []
    for path in sorted(WORK.glob("app-rankings-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        data = payload.get("data") or []
        if not data:
            continue
        meta = payload.get("meta") or {}
        out.append({
            "start": meta.get("start_date") or path.stem.split("-", 2)[-1][:10],
            "end": meta.get("end_date") or "",
            "data": data,
        })
    return out


def as_of() -> str:
    path = WORK / "as_of.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "unknown"


def prices() -> dict[str, float]:
    """Input list price per token from the benchmark feed, keyed on permaslug.

    Not from the current catalog: that is a snapshot against 21 months of
    history, so retired models are unpriceable. The benchmark feed keys on
    exactly the same `model_permaslug` as the rankings.
    """
    out: dict[str, float] = {}
    for src in ("artificial-analysis", "openrouter", "design-arena"):
        path = WORK / f"benchmarks-{src}.json"
        if not path.exists():
            continue
        for m in json.loads(path.read_text(encoding="utf-8")).get("data", []):
            p = m.get("pricing")
            if isinstance(p, dict) and p.get("prompt"):
                try:
                    out.setdefault(m["model_permaslug"], float(p["prompt"]))
                except (TypeError, ValueError):
                    pass
    return out


def scores(src: str = "artificial-analysis") -> dict[str, dict]:
    path = WORK / f"benchmarks-{src}.json"
    if not path.exists():
        return {}
    out = {}
    for m in json.loads(path.read_text(encoding="utf-8")).get("data", []):
        d = {}
        for k in ("intelligence_index", "coding_index", "agentic_index"):
            try:
                d[k] = float(m[k])
            except (TypeError, ValueError, KeyError):
                pass
        if d:
            out[m["model_permaslug"]] = d
    return out


def window(rows: list[dict], start: str, end: str | None = None) -> list[dict]:
    return [r for r in rows if r["date"] >= start and (end is None or r["date"] <= end)]


def lab(slug: str) -> str:
    return slug.split("/")[0] if "/" in slug else slug


def _read_hf(path: Path) -> dict[str, dict]:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return {m["id"]: m for m in json.loads(raw)}


def hf_latest() -> dict[str, dict]:
    snaps = hf_snapshots()
    if not snaps:
        raise SystemExit(f"no Hugging Face capture under {HF_ROOT}; set HF_RAW")
    return snaps[-1]["models"]


def hf_snapshots() -> list[dict]:
    """All distinct capture dates, latest file per date.

    The fleet captures several times a day around a run. Those are revisions of
    the same rolling window, not extra observations, so keep one per date.
    """
    by_date: dict[str, Path] = {}
    for path in sorted(p for p in HF_ROOT.glob("**/*") if p.is_file()):
        stamp = path.name[:8]
        if len(stamp) != 8 or not stamp.isdigit():
            continue
        if stamp not in by_date or path.name > by_date[stamp].name:
            by_date[stamp] = path
    out = []
    for stamp, path in sorted(by_date.items()):
        d = f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}"
        out.append({"date": d, "models": _read_hf(path)})
    return out


def rankdata(values: list[float]) -> list[float]:
    """Average ranks, so tied zeros do not become an arbitrary ordering."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    """Rank correlation with average ranks for ties."""
    if len(x) != len(y) or len(x) < 3:
        return 0.0
    rx, ry = rankdata(x), rankdata(y)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


# ── OpenCode: derived observations ──────────────────────────────────────────

def _open_partition(path: Path):
    if path.suffix == ".gz":
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", newline="")
    return path.open(encoding="utf-8", newline="")


def opencode_rows() -> list[dict]:
    """Latest statement of each OpenCode fact.

    The source restates a rolling window on every capture, so deduplicate on
    `(entity_id, metric, observed_at)` taking the latest `captured_at`.
    """
    latest: dict[tuple[str, str, str], dict] = {}
    for part in sorted(DERIVED.glob("*.csv*")):
        with _open_partition(part) as fh:
            for r in csv.DictReader(fh):
                if r["series_id"] != "opencode.data.usage":
                    continue
                key = (r["entity_id"], r["metric"], r["observed_at"])
                if key not in latest or r["captured_at"] > latest[key]["captured_at"]:
                    latest[key] = r
    return list(latest.values())


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def opencode_latest() -> dict[tuple[str, str], dict]:
    out = {}
    for r in opencode_rows():
        key = (r["entity_id"], r["metric"])
        if key not in out or r["observed_at"] > out[key]["observed_at"]:
            out[key] = r
    return out


def opencode_value(latest: dict, entity: str, metric: str):
    r = latest.get((entity, metric))
    return _num(r["value"]) if r else None


def opencode_ref(latest: dict, entity: str, metric: str):
    r = latest.get((entity, metric))
    return r["value"] if r else None


def _payload_file(path: Path) -> dict:
    return _decode_json(path.read_bytes())


def opencode_archives() -> list[dict]:
    """OpenCode snapshots with a country table: local captures + backfill.

    One entry per calendar date, latest `updatedAt` wins. The repo's own raw
    captures are preferred when they tie an archived copy. The archive cache is
    local-only; charts must still render from whatever captures exist.
    """
    out: dict[str, dict] = {}

    def add(path: Path, source: str) -> None:
        try:
            payload = _payload_file(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return
        updated = payload.get("updatedAt")
        if not updated or not payload.get("countries"):
            return
        day = updated[:10]
        old = out.get(day)
        priority = 1 if source == "capture" else 0
        if old is None:
            out[day] = {
                "date": day,
                "updated_at": updated,
                "source": source,
                "payload": payload,
                "_priority": priority,
            }
            return
        if (priority, updated) > (old["_priority"], old["updated_at"]):
            out[day] = {
                "date": day,
                "updated_at": updated,
                "source": source,
                "payload": payload,
                "_priority": priority,
            }

    raw_root = REPO / "raw" / "opencode.data.usage"
    for path in sorted(p for p in raw_root.glob("**/*") if p.is_file()):
        add(path, "capture")
    for path in sorted(OC_ARCHIVE.glob("index-*.json*")):
        add(path, "archive")
    return [{k: v for k, v in s.items() if k != "_priority"} for s in
            (out[k] for k in sorted(out))]


def opencode_payload_window(payload: dict, days: int = 28) -> tuple[dict[str, float], str, str]:
    """Model token shares over the last `days` complete days in a snapshot."""
    rows = sorted(payload.get("dailyTokens") or [], key=lambda r: r.get("date") or "")
    if not rows:
        return {}, "", ""
    rows = rows[:-1]  # the snapshot's current UTC day is partial
    rows = rows[-days:]
    if not rows:
        return {}, "", ""
    total = sum(float(r.get("total") or 0) for r in rows)
    if not total:
        return {}, rows[0]["date"], rows[-1]["date"]
    models: dict[str, float] = defaultdict(float)
    for row in rows:
        for model, value in (row.get("models") or {}).items():
            models[model] += float(value or 0)
    return {m: v / total for m, v in models.items()}, rows[0]["date"], rows[-1]["date"]


def opencode_daily() -> dict:
    """Complete daily series, without the partial current day.

    The page recomputes hourly, so the final date in a capture is incomplete.
    Every daily chart drops it and says so.
    """
    rows = opencode_rows()
    total: dict[str, float] = {}
    model_tok: dict[str, dict[str, float]] = defaultdict(dict)
    model_usr: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        d = r["observed_at"][:10]
        if r["metric"] == "tokens" and r["entity_id"] == "total":
            v = _num(r["value"])
            if v is not None:
                total[d] = v
        elif r["metric"] == "tokens" and r["entity_id"].startswith("model:"):
            v = _num(r["value"])
            if v is not None:
                model_tok[d][r["entity_id"][6:]] = v
        elif r["metric"] == "unique_users" and r["entity_id"].startswith("model:"):
            v = _num(r["value"])
            if v is not None:
                model_usr[d][r["entity_id"][6:]] = v
    dates = sorted(total)
    all_dates = list(dates)
    if dates:
        dates = dates[:-1]  # partial current UTC day
    return {
        "dates": dates,
        "dropped": all_dates[-1] if all_dates else None,
        "total": total,
        "model_tokens": model_tok,
        "model_users": model_usr,
    }


def opencode_labs() -> dict[str, dict[str, float]]:
    """Daily lab share, keyed by date, without the partial current day."""
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for r in opencode_rows():
        if r["metric"] != "share_pct" or not r["entity_id"].startswith("lab:"):
            continue
        v = _num(r["value"])
        if v is not None:
            out[r["observed_at"][:10]][r["entity_id"][4:]] = v
    dates = sorted(out)
    if dates:
        out.pop(dates[-1], None)
    return out


def opencode_names(latest: dict) -> tuple[dict[str, str], dict[str, str]]:
    names, labs = {}, {}
    for (e, m), r in latest.items():
        if not e.startswith("model:"):
            continue
        if m == "model_name":
            names[e[6:]] = r["value"]
        elif m == "model_lab":
            labs[e[6:]] = r["value"]
    return names, labs


def opencode_window_tokens(days: int = 28) -> tuple[dict[str, float], str, str]:
    """Model token totals over the last `days` complete days."""
    daily = opencode_daily()
    dates = daily["dates"][-days:]
    tot: dict[str, float] = defaultdict(float)
    for d in dates:
        for m, v in daily["model_tokens"].get(d, {}).items():
            tot[m] += v
    return dict(tot), dates[0], dates[-1]


# Explicit bridge from OpenCode's slugs to the OpenRouter permaslugs used by
# the rankings endpoint. Names are not stable; the pairs are checked against
# both catalogues and the mapping is small enough to audit.
OC_TO_OR = {
    "deepseek-v4.1-flash": "deepseek/deepseek-v4.1-flash-20260910",
    "deepseek-v4.1-flash-1017": "deepseek/deepseek-v4.1-flash-20261017",
    "minimax-m3.1-flash": "minimax/minimax-m3.1-flash-20261019",
    "glm-5.3-flash": "z-ai/glm-5.3-flash-20260826",
    "muse-spark-1.3-contributor": "meta/muse-spark-1.3-contributor-20260902",
    "mimo-v2.6-flash": "xiaomi/mimo-v2.6-flash-20260921",
    "nemotron-3-ultra": "nvidia/nemotron-3-ultra-550b-a55b-20260604:free",
    "nemotron-3.5-super-vl": "nvidia/nemotron-3.5-super-vl-20261015:free",
}
