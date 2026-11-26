"""Cost per run, from the token counts the API returns (usageMetadata), not from estimates.

Prices are USD per 1M tokens, Gemini Developer API, Standard paid tier, read from
https://aistudio.google.com/docs/pricing on 26 Nov 2026. Output price includes thinking tokens.
The free tier bills nothing; the paid price is what matters at 1,000 runs a day.
"""

from __future__ import annotations

import csv
import datetime as dt
import os

# model id prefix -> (input $/1M, output $/1M)
PRICES = {
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.8-flash": (0.75, 3.75),      # introductory price through 31 Dec 2026; $1.50 / $7.50 from 1 Jan 2027
    "gemini-flash-lite-latest": (0.30, 2.50),   # alias; priced as the Flash-Lite it points to
}
DEFAULT_PRICE = (0.75, 3.75)               # unknown model: assume the dearer Flash price, never under-count
LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs.csv")


def price_for(model: str) -> tuple[float, float]:
    for prefix, p in PRICES.items():
        if model.startswith(prefix):
            return p
    return DEFAULT_PRICE


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = price_for(model)
    return tokens_in / 1e6 * pin + tokens_out / 1e6 * pout


def log_run(row: dict) -> None:
    """Append one line per run so cost and latency can be checked later (runs.csv in the project root)."""
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["time", "url", "model", "tokens_in", "tokens_out", "cost_usd",
                                          "seconds", "source", "grounded"])
        if new:
            w.writeheader()
        w.writerow({"time": dt.datetime.now().isoformat(timespec="seconds"), **row})
