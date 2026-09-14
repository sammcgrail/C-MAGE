#!/usr/bin/env python3
"""What the Sonnet arm would have cost at API list prices, from the tokens it actually used.

The readers ran inside Claude Code on a subscription, so none of this was billed per token.
This answers "what would the same work cost on the API". Every reader transcript records
the API's own `usage` for each request, and those token counts are priced at Anthropic's
published rates.

Three details decide whether the number is right:

- DEDUPLICATE BY MESSAGE ID. Claude Code writes one transcript record per content block,
  and every record of a response repeats that response's usage. Summing records counts a
  response once per block: for one reader, 391 records were 203 responses.
- CACHE READS ARE MOST OF IT. A reader re-sends its whole growing context on every tool
  call. Cache reads therefore outnumber all other tokens about 40 to 1, and are about 60%
  of the cost even at a tenth of the input price. Pricing the token total at the input
  rate would overstate the cost several-fold.
- THE TASK NOTIFICATION'S TOKEN COUNT IS NOT USAGE. "subagent_tokens: 214311" is the size
  of the reader's final context. That reader actually used 7.4M tokens.

Prices are per million tokens for claude-sonnet-5, from Anthropic's pricing page (checked
2026-09-14):
- input $2
- output $10
- 5-minute cache write $2.50
- 1-hour cache write $4
- cache read $0.20
The $2/$10 launch price became standard, and the increase to $3/$15 scheduled for 1 Sep
2026 was cancelled. Sonnet 5 bills its whole 1M context at standard rates, so requests past
200K tokens (these reached 576K) carry no premium. The first-party API is global, so no
regional 10% applies.

Results merge into benchmarks/sonnet_cost.json by agent id, so a reader whose transcript
is later cleaned up keeps its recorded cost.

    sonnet_cost.py      update the JSON from every reader transcript found; print totals
"""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit_sonnet_rows as A  # noqa: E402

OUT = HERE.parent / "benchmarks" / "sonnet_cost.json"
MODEL = "claude-sonnet-5"
PRICE_PER_MTOK = {"input": 2.00, "output": 10.00, "cache_write_5m": 2.50,
                  "cache_write_1h": 4.00, "cache_read": 0.20}
PRICE_SOURCE = "https://docs.claude.com/en/docs/about-claude/pricing"
PRICE_CHECKED = "2026-09-14"
TOKEN_KEYS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")


def reader_usage(path: str) -> tuple[dict, set]:
    last = {}
    with open(path, errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            m = r.get("message") or {}
            if r.get("type") != "assistant" or not m.get("usage") or m.get("model") == "<synthetic>":
                continue
            # The last record of a response carries its final usage.
            last[m.get("id") or r.get("requestId") or r.get("uuid")] = (m["usage"], m.get("model"))
    t = dict.fromkeys(TOKEN_KEYS, 0)
    t["requests"] = len(last)
    models = set()
    for u, model in last.values():
        models.add(model)
        t["input"] += u.get("input_tokens") or 0
        t["output"] += u.get("output_tokens") or 0
        cc = u.get("cache_creation") or {}
        if "ephemeral_5m_input_tokens" in cc or "ephemeral_1h_input_tokens" in cc:
            t["cache_write_5m"] += cc.get("ephemeral_5m_input_tokens") or 0
            t["cache_write_1h"] += cc.get("ephemeral_1h_input_tokens") or 0
        else:
            # A record that does not split the TTL is priced as a 5-minute write, the default.
            t["cache_write_5m"] += u.get("cache_creation_input_tokens") or 0
        t["cache_read"] += u.get("cache_read_input_tokens") or 0
    return t, models


def cost_of(t: dict) -> float:
    return sum(t[k] * PRICE_PER_MTOK[k] for k in TOKEN_KEYS) / 1e6


def update() -> dict:
    saved = json.load(open(OUT)) if OUT.exists() else {}
    readers = {r["agent"]: r for r in saved.get("readers", [])}
    for p, (found, _) in A.reader_transcripts(set()).items():
        t, models = reader_usage(p)
        if not t["requests"]:
            continue
        other = sorted(str(m) for m in models if MODEL not in (m or ""))
        if other:
            raise ValueError(f"{os.path.basename(p)} was served by {other}, not {MODEL}; "
                             "these prices do not apply to it")
        aid = os.path.basename(p)[6:-6]
        readers[aid] = dict(agent=aid, images=len({img for img, _ in found}),
                            finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p))),
                            **t, cost_usd=round(cost_of(t), 4))
    rows = sorted(readers.values(), key=lambda r: r["finished"])
    totals = {k: sum(r[k] for r in rows) for k in TOKEN_KEYS + ("requests", "images")}
    total = sum(r["cost_usd"] for r in rows)
    out = {
        "model": MODEL, "price_per_mtok": PRICE_PER_MTOK,
        "price_source": PRICE_SOURCE, "price_checked": PRICE_CHECKED,
        "note": "API list-price estimate. The readers ran on a subscription; nothing here was billed per token.",
        "cost_usd": round(total, 2),
        "per_image_usd": round(total / totals["images"], 3) if totals["images"] else None,
        "totals": totals, "readers": rows,
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    o = update()
    t = o["totals"]
    print(f"{len(o['readers'])} readers, {t['images']} images, {t['requests']:,} API requests")
    for k in TOKEN_KEYS:
        print(f"  {k:<15} {t[k]:>13,} tokens  ${t[k] * PRICE_PER_MTOK[k] / 1e6:>9,.2f}")
    print(f"  total ${o['cost_usd']:,.2f}   per image ${o['per_image_usd']:.3f}")
