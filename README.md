# riskmonitor

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

A **multi-asset risk-appetite monitor** that pulls equity, breadth, credit, liquidity, crypto, commodities, volatility and sentiment data into a single composite "risk-on / risk-off" score.

Runs as a one-shot CLI report, a recurring scheduled job, or an interactive Streamlit dashboard. Optional Telegram bot delivery for daily / 4-hour digests.

> **Status:** personal / educational project, single maintainer. The composite score is a heuristic for orientation — not a trading signal and not financial advice.

---

## What it monitors

| Section | What's tracked | Source |
|---|---|---|
| Equity indices | US (SPX, NDX, RUT), Europe (SX5E, FTSE), Asia (Nikkei, HSI) | yfinance |
| Market breadth | A/D line, % stocks above 50/200-day MA, new highs/lows | yfinance |
| Credit | HY OAS, IG OAS, HY–IG differential | FRED |
| Global liquidity | US M2, China M2, ECB & BOJ balance sheets, Fed WALCL | FRED |
| Crypto | BTC, ETH, alt basket, BTC dominance, alt-season index, Fear & Greed, ETF flows | yfinance + alternative.me |
| Commodities | Gold, silver, copper, oil, copper/gold and gold/silver ratios | yfinance |
| Volatility | VIX spot + VIX term structure | yfinance |
| Sentiment | CBOE Put/Call ratio, news flow + sentiment / "Trump-effect" tagging | CBOE + RSS / Yahoo Finance news |

Each section produces sub-scores (-5 → +5) that are weighted into a **composite risk-appetite score** with percentile rankings against its own rolling history.

## Install

Requires Python 3.10+.

```bash
git clone https://github.com/mral78-stack/riskmonitor.git
cd riskmonitor
pip install -r requirements.txt
```

## Run

```bash
# One-shot console report
python riskmonitor.py

# Recurring (every 4 hours, console-only)
python riskmonitor.py --schedule

# One-shot + Telegram digest
python riskmonitor.py --telegram

# Recurring + Telegram digest
python riskmonitor.py --schedule --telegram

# Streamlit dashboard
streamlit run app.py
```

## Configuration

Optional environment variables — none are required for the console report.

| Variable | Purpose |
|---|---|
| `FRED_API_KEY` | Higher rate limits for FRED series (free key at https://fred.stlouisfed.org/docs/api/api_key.html) |
| `TELEGRAM_BOT_TOKEN` | Required for `--telegram` mode |
| `TELEGRAM_CHAT_ID` | Required for `--telegram` mode |

## Composite score

The composite blends the eight sections with hand-tuned weights and emits one of five regimes:

| Score range | Regime | Reading |
|---|---|---|
| ≥ +3.0 | Risk-On | Broad participation, tight spreads, expanding liquidity |
| +1.0 → +3.0 | Constructive | Mixed but tilted positive |
| –1.0 → +1.0 | Neutral | No dominant signal |
| –3.0 → –1.0 | Defensive | Tightening credit, narrow breadth, defensive rotation |
| ≤ –3.0 | Risk-Off | Stress: wide spreads, vol expansion, liquidity drain |

Each section also reports percentile ranks against its own rolling history so the absolute score is contextualized against regime history.

## Files

```
.
├── riskmonitor.py        # CLI entrypoint, scheduler, Telegram dispatcher, scoring engine
├── app.py                # Streamlit dashboard
├── app_enhanced.py       # Streamlit dashboard with extra charts (gauges, sparklines)
└── requirements.txt
```

## Contributing

PRs and issues welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).
