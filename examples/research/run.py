#!/usr/bin/env python3
"""Build the research figures.

    python examples/research/run.py --fetch       # once: cache external archives
    python examples/research/run.py               # OpenRouter + OpenCode figures
    python examples/research/run.py --opencode    # no OpenRouter cache needed
    python examples/research/run.py --openrouter  # only the archive-backed figures

External archives are cached under `examples/research/work/` and are
gitignored. OpenCode figures read the weekly captures in `derived/`; historical
country and retention snapshots are backfilled from the Internet Archive and
read from the same local cache.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import data  # noqa: E402
import opencode  # noqa: E402
import openrouter  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fetch", action="store_true",
                    help="fetch OpenRouter's archive and OpenCode's historical snapshots")
    ap.add_argument("--openrouter", action="store_true", help="render only the OpenRouter figures")
    ap.add_argument("--opencode", action="store_true", help="render only the OpenCode figures")
    ap.add_argument("--start", default="2025-01-01", help="archive start for --fetch")
    ap.add_argument("--end", default=None, help="archive end for --fetch (default: today)")
    args = ap.parse_args()

    data.CHARTS.mkdir(parents=True, exist_ok=True)
    if args.fetch:
        data.fetch_openrouter(args.start, args.end)
        data.fetch_opencode_archives()

    run_or = not args.opencode or args.openrouter
    run_oc = not args.openrouter or args.opencode
    if not args.openrouter and not args.opencode:
        run_or = run_oc = True

    if run_oc:
        print("OpenCode")
        for line in opencode.render_all():
            print(f"  {line}")
    if run_or:
        print("OpenRouter research")
        if not (data.WORK / "rankings-daily.csv").exists():
            print("  skipped: no archive cache; run with --fetch once (needs OPENROUTER_API_KEY)")
        else:
            for line in openrouter.render_all():
                print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
