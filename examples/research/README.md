# Research figures

These are the long-view figures the weekly capture cannot make by itself.

They adapt the methods in
[`cookbook/recipes/openrouter-lab-share`](https://github.com/q3dresearch/cookbook/tree/main/recipes/openrouter-lab-share)
to this repo's data:

- **OpenRouter** already keeps its own daily archive and app ranking windows,
  so `--fetch` queries them and caches them locally. Those bytes are never
  committed to `raw/`, `manifest/` or `derived/`; re-archiving a publisher's
  archive is exactly what `wss validate` rejects.
- **OpenCode** keeps only a rolling 56-day window, so the weekly captures in
  `derived/` are the archive. The current figures use those rows. Historical
  country and retention snapshots are backfilled from the Internet Archive into
  `work/opencode/`; they are research context, not repo captures.

## Run

```bash
# once, with OPENROUTER_API_KEY in .env.local
# (also backfills OpenCode history from the Internet Archive)
python examples/research/run.py --fetch

# all figures (OpenRouter + OpenCode)
python examples/research/run.py

# OpenCode only; no OpenRouter key or cache
# (the country/retention trend panels need the OpenCode archive backfill)
python examples/research/run.py --opencode
```

The cache lives in `examples/research/work/` and is gitignored. The charts are
written to `examples/charts/` so `wss datapage` picks them up with the weekly
figures.

On GitHub this runs monthly as the `research` workflow, after the first weekly
derive of the month. It checks out the sparse Hugging Face raw captures, fetches
the publisher archives, renders the figures and commits only `examples/charts/`
and `docs/`. The cache is never committed. Trigger it by hand when the archive
has moved:

```bash
gh workflow run research.yml -R q3dresearch/wss-openrouter
```

## What each figure asks

**OpenRouter**

| figure | question | caveat |
| --- | --- | --- |
| `or-lab-share.svg` | Did the market grow, and who took the growth? | A falling share is not a falling lab. Monthly totals; current month excluded. |
| `or-app-mix.svg` | Who routes, and did the shape of a request change? | 21 monthly windows; top 50 apps per window, so share is within that top list, not a platform census. |
| `or-tokens-vs-spend.svg` | Does the biggest server also take the most money? | Input list price only; covers the tokens that join to a price. |
| `or-capability-vs-usage.svg` | Does being better make you used? | Benchmark index is independent; usage is one router. |
| `or-downloads-vs-use.svg` | Do downloads predict use? | Open-weight models only; closed models have no Hugging Face presence. The rolling panel uses eight weekly HF captures; each point joins a 30-day download window to the same OpenRouter window. |
| `or-model-shelf-life.svg` | How long is a model at the top? | 7-day mean; share is relative in a growing market. |

**OpenCode**

| figure | question | caveat |
| --- | --- | --- |
| `opencode-lab-share.svg` | Did one lab take the client? | One coding client, not the market; 56 days. |
| `opencode-model-share.svg` | How fast can a model displace another? | The window is too short to measure shelf life; it shows displacement. |
| `opencode-tokens-vs-spend.svg` | Do tokens and spend pick the same winner? | Input list price, 97% coverage; publisher's model mix. |
| `opencode-session-cost.svg` | What does a session cost? | Publisher averages, not recomputed from list prices. |
| `opencode-retention-vs-usage.svg` | Does retention predict use? | Six models; a small correlation is not a relationship. The trend panel uses three retention snapshots (two Internet Archive, one repo capture) and a trailing 28-day usage window, so n=4–6. Effective price is session cost per 1M tokens; no promotional-discount field exists. |
| `opencode-geography.svg` | Where do the tokens come from, and is the mix moving? | Country inferred by the publisher; not a census. Three snapshots only: two Internet Archive copies and the first repo capture; future weekly captures extend the trend. |
| `opencode-vs-openrouter.svg` | Does router traffic predict client traffic? | Two different populations and windows; not a market comparison. Scatter is 28 days on both sides. The rolling line is rank-weighted (each matched model once), with a coarser lab-level cross-check; token weights would be dominated by DeepSeek and dollar weights are unavailable. |

## Why these are not in `visualize.py`

`visualize.py` reads only `derived/observations/` and never touches the network.
These figures need either the publisher's archive (OpenRouter) or a different
window/lens (OpenCode). Keeping them separate makes the reproducibility contract
clear: `visualize.py` is the weekly capture; `research/` is the longer view.
