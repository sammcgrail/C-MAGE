#!/usr/bin/env python3
"""What the Sonnet arm would have cost at API list prices, from the tokens it actually used.

The readers ran inside Claude Code on a subscription, so none of this was billed per token.
This answers "what would the same work cost on the API". Every reader transcript records
the API's own `usage` for each request, and those token counts are priced at Anthropic's
published rates.

THE TALLY COUNTS PUBLISHED READS ONLY. A reading excluded for a lookup was re-run clean,
and the re-run is the reading the page shows. So the cost of each run is split evenly
over the images it read, and the shares belonging to excluded readings are left out of
the headline figure. Even is an estimate: one reader works on all its images in a single
context, so nothing finer is recorded. Everything spent, excluded readings included,
stays in the JSON as cost_usd_all.

Three details decide whether the number is right:

- DEDUPLICATE BY MESSAGE ID. Claude Code writes one transcript record per content block,
  and every record of a response repeats that response's usage. Summing records counts a
  response once per block: for one reader, 391 records were 203 responses.
- CACHE READS ARE MOST OF IT. A reader re-sends its whole growing context on every tool
  call. Cache reads therefore outnumber all other tokens about 40 to 1, and are about 60%
  of the cost even at a tenth of the input price.
- THE TASK NOTIFICATION'S TOKEN COUNT IS NOT USAGE. "subagent_tokens: 214311" is the size
  of the reader's final context. That reader actually used 7.4M tokens.

Prices are per million tokens for claude-sonnet-5, from Anthropic's pricing page (checked
2026-09-14):
- input $2
- output $10
- 5-minute cache write $2.50
- 1-hour cache write $4
- cache read $0.20
Sonnet 5 bills its whole 1M context at standard rates, so requests past 200K tokens carry
no premium. The first-party API is global, so no regional 10% applies.

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
EXCLUDED = [Path("/root/cmage-work/sonnet/excluded.jsonl"), HERE.parent / "benchmarks" / "sonnet_excluded.jsonl"]
MODEL = "claude-sonnet-5"
PRICE_PER_MTOK = {"input": 2.00, "output": 10.00, "cache_write_5m": 2.50,
                  "cache_write_1h": 4.00, "cache_read": 0.20}
PRICE_SOURCE = "https://docs.claude.com/en/docs/about-claude/pricing"
PRICE_CHECKED = "2026-09-14"
TOKEN_KEYS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")


def _ts(rec: dict) -> float | None:
    s = rec.get("timestamp")
    if not isinstance(s, str):
        return None
    try:
        return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None


def reader_usage(path: str) -> tuple[dict, set, float]:
    last = {}
    stamps = []
    with open(path, errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            ts = _ts(r)
            if ts is not None:
                stamps.append(ts)
            m = r.get("message") or {}
            if r.get("type") != "assistant" or not m.get("usage") or m.get("model") == "<synthetic>":
                continue
            # The last record of a response carries its final usage.
            last[m.get("id") or r.get("requestId") or r.get("uuid")] = (m["usage"], m.get("model"))
    duration_s = round(max(stamps) - min(stamps)) if len(stamps) >= 2 else 0
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
    return t, models, duration_s


def cost_of(t: dict) -> float:
    return sum(t[k] * PRICE_PER_MTOK[k] for k in TOKEN_KEYS) / 1e6


def excluded_rows() -> list[dict]:
    for p in EXCLUDED:
        if p.exists():
            return [json.loads(l) for l in open(p) if l.strip()]
    return []


def update() -> dict:
    saved = json.load(open(OUT)) if OUT.exists() else {}
    readers = {r["agent"]: r for r in saved.get("readers", [])}
    holders, finished, raw_by_aid = {}, {}, {}
    for p, (found, raw) in A.reader_transcripts(set()).items():
        aid = os.path.basename(p)[6:-6]
        finished[aid] = os.path.getmtime(p)
        raw_by_aid[aid] = raw
        for _, smi in found:
            holders.setdefault(smi, set()).add(aid)
        t, models, duration_s = reader_usage(p)
        if not t["requests"]:
            continue
        other = sorted(str(m) for m in models if MODEL not in (m or ""))
        if other:
            raise ValueError(f"{os.path.basename(p)} was served by {other}, not {MODEL}; "
                             "these prices do not apply to it")
        readers[aid] = dict(agent=aid, images=len({img for img, _ in found}),
                            finished=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p))),
                            duration_s=duration_s, **t, cost_usd=round(cost_of(t), 4))

    # Which run produced each excluded reading. The exclusion log records it; for a row
    # logged before that field existed, the earliest transcript holding that answer is
    # the one, because a re-read can only follow an exclusion.
    excluded, unattributed = {}, []
    for e in excluded_rows():
        aid = e.get("reader")
        if not aid:
            h = holders.get(e.get("sonnet_smiles"), set())
            aid = min(h, key=lambda a: finished[a]) if h else None
        if aid in readers:
            excluded[aid] = excluded.get(aid, 0) + 1
        else:
            unattributed.append(e.get("k"))
    for r in readers.values():
        r["excluded"] = excluded.get(r["agent"], 0)
        r["published"] = max(0, r["images"] - r["excluded"])
        r["published_cost_usd"] = round(r["cost_usd"] * r["published"] / r["images"], 4) if r["images"] else 0.0

    # Per published image: the cost and wall-clock of the RUN that produced it, and that
    # run's per-image share. One run reads a batch (usually ten) in a single shared context,
    # so cost and time are per batch; the share is batch / images. The published reading of a
    # molecule is the most recent run whose transcript holds that SMILES (a re-read supersedes
    # an excluded earlier read).
    per_key = {}
    for r in (json.loads(l) for l in open(f"{A.WORK}/results.jsonl") if l.strip()):
        smi, k = r.get("sonnet_smiles"), r["k"]
        # A SMILES with E/Z bonds carries backslashes, which are doubled in the JSON transcript;
        # match both forms (same tolerance as audit_sonnet_rows).
        cands = [a for a in readers if smi and (smi in raw_by_aid.get(a, "")
                                                or smi.replace("\\", "\\\\") in raw_by_aid.get(a, ""))]
        if not cands:
            continue
        aid = max(cands, key=lambda a: finished.get(a, 0))
        rd = readers[aid]
        n = rd["images"] or 1
        per_key[k] = {"cost": round(rd["cost_usd"] / n, 4), "secs": round((rd.get("duration_s") or 0) / n),
                      "batch": n, "batch_cost": round(rd["cost_usd"], 2),
                      "batch_secs": rd.get("duration_s") or 0, "reader": aid[:8]}

    rows = sorted(readers.values(), key=lambda r: r["finished"])
    totals = {k: sum(r[k] for r in rows) for k in TOKEN_KEYS + ("requests", "images", "excluded", "published")}
    spent = sum(r["cost_usd"] for r in rows)
    shown = sum(r["published_cost_usd"] for r in rows)
    out = {
        "model": MODEL, "price_per_mtok": PRICE_PER_MTOK,
        "price_source": PRICE_SOURCE, "price_checked": PRICE_CHECKED,
        "note": ("API list-price estimate. The readers ran on a subscription; nothing here was billed per "
                 "token. cost_usd and per_image_usd cover published reads only, with each run's cost split "
                 "evenly over its images; cost_usd_all includes the readings excluded for lookups."),
        "reads": totals["published"],
        "cost_usd": round(shown, 2),
        "per_image_usd": round(shown / totals["published"], 3) if totals["published"] else None,
        "cost_usd_all": round(spent, 2),
        "cost_usd_excluded": round(spent - shown, 2),
        "unattributed_excluded": unattributed,
        "totals": totals, "readers": rows, "per_key": per_key,
    }
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    return out


if __name__ == "__main__":
    o = update()
    t = o["totals"]
    print(f"{len(o['readers'])} readers, {t['images']} images read, {t['excluded']} excluded, "
          f"{t['requests']:,} API requests")
    for k in TOKEN_KEYS:
        print(f"  {k:<15} {t[k]:>13,} tokens  ${t[k] * PRICE_PER_MTOK[k] / 1e6:>9,.2f}  (all runs)")
    print(f"  all runs ${o['cost_usd_all']:,.2f}; excluded readings ${o['cost_usd_excluded']:,.2f}")
    print(f"  published reads {o['reads']}: ${o['cost_usd']:,.2f}, per image ${o['per_image_usd']:.3f}")
    if o["unattributed_excluded"]:
        print(f"  WARNING excluded readings with no run found: {o['unattributed_excluded']}")
