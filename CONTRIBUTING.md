# Contributing

Thanks for taking the time. This is a small project maintained in spare time, so the loop is intentionally lightweight.

## Reporting a bug

Open an issue with:

- the command you ran (e.g. `python riskmonitor.py --schedule`)
- which section misbehaved (equity / breadth / credit / liquidity / crypto / commodities / vol / sentiment)
- the full traceback or unexpected output
- Python version and OS

If the issue is "a FRED series stopped returning data," paste the series ID and the date you noticed — upstream changes happen and the monitor needs to adapt.

## Proposing a change

For small fixes (typo, single-section weight tweak, new ticker for an existing section), open a PR directly.

For larger changes (new section, new data provider, refactor of the composite scoring), open an issue first so we can discuss the approach before you write the code.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Code style

- Python 3.10+, type hints where they help readability.
- New sections are added as a fetcher + a processor + a weight entry; don't inline scoring into the fetcher.
- Network calls in sections must degrade gracefully: a failed fetch should leave the section unscored rather than crash the whole report.
- No hard-coded API keys or Telegram tokens. Read from env vars; document the variable name in `README.md`.

## What I'm unlikely to merge

- Anything that requires a paid data subscription as the *only* source.
- Trading-execution code. This monitor is read-only by design.
- Heavy ML/DL dependencies. The project should install from `requirements.txt` in under a minute on a fresh machine.
