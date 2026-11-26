"""Website in, 3-line cold-email opener out.

    python opener.py https://plausible.io
    python opener.py plausible.io --json

Needs GEMINI_API_KEY (free at aistudio.google.com). Logs every run to runs.csv with tokens and cost.
"""

from __future__ import annotations

import argparse
import json
import sys

from src.cost import cost_usd, log_run
from src.draft import draft_opener
from src.fetch import fetch_site_text


def run(url: str) -> dict:
    site = fetch_site_text(url)
    out = draft_opener(site)
    out["cost_usd"] = round(cost_usd(out["model"], out["tokens_in"], out["tokens_out"]), 6)
    out["site"] = {k: site[k] for k in ("final_url", "domain", "source", "chars")}
    log_run({"url": site["final_url"], "model": out["model"], "tokens_in": out["tokens_in"],
             "tokens_out": out["tokens_out"], "cost_usd": out["cost_usd"], "seconds": out["seconds"],
             "source": site["source"], "grounded": f"{out['grounded']}/2"})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--json", action="store_true", help="print the full JSON instead of the readable view")
    a = ap.parse_args()
    try:
        out = run(a.url)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print(f"\n{out.get('company') or out['site']['domain']}  ({out['site']['final_url']})")
    if out.get("founder_hint"):
        print(f"Founder named on site: {out['founder_hint']}")
    print("\nOPENER")
    for c in out["checks"]:
        flag = "" if c["grounded"] in (True, None) else "   [UNVERIFIED: not found on the page, check before sending]"
        print(f"  {c['line']}{flag}")
    print("\nEVIDENCE (quotes from the site)")
    for i, c in enumerate(out["checks"], 1):
        print(f"  {i}. {c['evidence'] if c['kind'] == 'fact' else '(bridge line about us, no site fact)'}")
    print(f"\nGrounded: {out['grounded']}/2 fact lines verified against the page text")
    if out.get("note"):
        print(f"\nNote: {out['note']}")
    print(f"\n{out['model']} | {out['tokens_in']} in + {out['tokens_out']} out tokens | "
          f"${out['cost_usd']:.5f} | {out['seconds']} s | text from {out['site']['source']} ({out['site']['chars']} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
