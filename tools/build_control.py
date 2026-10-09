#!/usr/bin/env python3
"""RENDERER CONTROL: the same 150 corpus molecules, drawn by the corpus renderer (RDKit) and by a
different one (Indigo, tools/control_set.py), read by both Sonnet 5.5 arms. Writes
benchmarks/wall/control.json + 360 px tiles in wall/control/.

    build_control.py record <reader-run-log>    credit one jailed control reader (ledger: benchmarks/control_runs.json)
    build_control.py                             build the payload

WHY. Jailed readers hold RDKit, which IS the corpus renderer: many re-draw candidate SMILES and
pixel-match them against the image until the difference is zero. That is verification against the
generator, an oracle no real drawing offers. On the Indigo drawings it is gone. The API-only arm
(pixels, no tools) never had it, so its corpus-vs-control gap is the renderer's effect on reading;
the jailed arm's gap is that plus the oracle.

Every verdict is sonnet_batch.verdict(); the API replies are parsed with api_reader.parse_smiles and
picked the way build_sonnet55api picks them (control_set.api_scored). Pairs are by corpus key.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import control_set as CS  # noqa: E402
from api_reader import parse_smiles  # noqa: E402
from build_sonnet55 import mcnemar_exact  # noqa: E402
from sonnet_batch import verdict  # noqa: E402

WALL = REPO / "benchmarks" / "wall"
OUT = WALL / "control.json"
TILES = WALL / "control"
RUNS = REPO / "benchmarks" / "control_runs.json"
CTL_API = REPO / "benchmarks" / "published_runs" / "sonnet55_api_control"
CTL_JAIL = Path("/root/cmage-work/sonnet-ctl/results.jsonl")
S55C = Path("/root/cmage-work/sonnet-s55c/results.jsonl")


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def cmd_record(log: str) -> int:
    """Credit one control-lane reader from its run log (claim keys, launch dir, READER line)."""
    txt = open(log).read()
    m = re.search(r"^READER (a[0-9a-f]+) (\S+)$", txt, re.M)
    keys = re.search(r"^PROMPT \S+ (\[.*\])$", txt, re.M)
    wd = re.search(r"^LAUNCH_DIR (\S+)$", txt, re.M)
    if not (m and keys and wd):
        raise SystemExit(f"{log}: no READER / PROMPT / LAUNCH_DIR line; not a finished reader")
    aid, model = m.groups()
    cost = dur = None
    for line in open(Path(wd.group(1)) / "out.jsonl"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") == "result":
            cost, dur = r.get("total_cost_usd"), (r.get("duration_ms") or 0) / 1000
    net = load(Path(wd.group(1)) / "jail_net.jsonl")
    led = json.load(open(RUNS)) if RUNS.exists() else {"runs": {}}
    led["runs"][aid] = {"agent": aid, "model": model, "keys": json.loads(keys.group(1).replace("'", '"')),
                        "cost_usd": cost, "duration_s": dur, "launch_dir": wd.group(1),
                        "net_allowed": sum(1 for n in net if n.get("allowed")),
                        "net_denied": sorted({n["target"] for n in net if not n.get("allowed")}),
                        "recorded": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    RUNS.write_text(json.dumps(led, indent=1) + "\n")
    print(f"recorded {aid}: {len(led['runs'][aid]['keys'])} keys, ${cost}")
    return 0


def tile(src: str, dst: Path) -> None:
    from PIL import Image
    if dst.exists():
        return
    im = Image.open(src).convert("RGB")
    im.thumbnail((360, 360), Image.LANCZOS)
    im.quantize(colors=64).save(dst, optimize=True)


def arm(name: str, note: str, pairs: list[tuple[str, str]], cost: float | None) -> dict:
    cc, pc = Counter(c for _, c in pairs), Counter(p for p, _ in pairs)
    b = sum(1 for p, c in pairs if p == "exact" and c != "exact")
    c_ = sum(1 for p, c in pairs if p != "exact" and c == "exact")
    return {"arm": name, "note": note, "n": len(pairs), "corpus_exact": pc["exact"], "control_exact": cc["exact"],
            "corpus": dict(pc), "control": dict(cc), "lost": b, "gained": c_,
            "mcnemar_p": round(mcnemar_exact(b, c_), 4), "cost_usd": round(cost, 2) if cost is not None else None}


def main() -> int:
    doc = json.load(open(CS.JSON))
    ctl_api = CS.api_scored(load(CTL_API / "ledger.jsonl"), load(CTL_API / "retries.jsonl"))
    corp_api = CS.api_scored(load(CS.API_LEDGER), load(CS.API_RETRIES))
    s55c = {r["k"]: r for r in load(S55C)}
    jail = {r["k"]: r for r in load(CTL_JAIL)}
    runs = (json.load(open(RUNS)) if RUNS.exists() else {"runs": {}})["runs"]
    TILES.mkdir(parents=True, exist_ok=True)
    rows, api_pairs, jail_pairs = [], [], []
    for r in doc["rows"]:
        k, t = r["k"], r["t"]
        row = {"id": r["id"], "k": k, "n": r["n"]}
        if r["id"] in ctl_api and k in corp_api:
            a = (verdict(parse_smiles(corp_api[k].get("text")) or "", t),
                 verdict(parse_smiles(ctl_api[r["id"]].get("text")) or "", t))
            api_pairs.append(a)
            row["api"] = {"corpus": a[0], "control": a[1]}
        if k in jail and k in s55c:
            if jail[k]["truth"] != t or s55c[k]["truth"] != t:
                raise SystemExit(f"{k}: truth differs between the control set and a lane")
            j = (verdict(s55c[k].get("sonnet_smiles"), t), verdict(jail[k].get("sonnet_smiles"), t))
            jail_pairs.append(j)
            row["jail"] = {"corpus": j[0], "control": j[1], "smiles": jail[k].get("sonnet_smiles")}
        tile(r["png"], TILES / f"{r['id']}.png")
        rows.append(row)
    api_cost = sum(x.get("cost_usd") or 0 for x in load(CTL_API / "ledger.jsonl") + load(CTL_API / "retries.jsonl"))
    jail_cost = sum(v.get("cost_usd") or 0 for v in runs.values()) if runs else None
    led = json.load(open(RUNS)) if RUNS.exists() else {}
    discarded = sum(v.get("cost_usd") or 0 for v in led.get("discarded", {}).values())
    out = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "renderer": "EPAM Indigo 1.46, its own 2D layout, Kekule rings, 1500 px, pixels only",
           "set": len(doc["rows"]), "seed": doc.get("seed"),
           "arms": [arm("Sonnet 5.5 API only", "pixels in, SMILES out; no tools", api_pairs, api_cost),
                    arm("Sonnet 5.5 with tools", "jailed reader: RDKit, PIL, OSRA; no network", jail_pairs,
                        jail_cost)],
           "readers": len(runs),
           "discarded_readers": len(led.get("discarded", {})), "spent_usd": round(api_cost + (jail_cost or 0) + discarded, 2),
           "rows": rows}
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    tmp.replace(OUT)
    for a in out["arms"]:
        print(f"{a['arm']}: corpus {a['corpus_exact']}/{a['n']}, control {a['control_exact']}/{a['n']}, "
              f"lost {a['lost']} gained {a['gained']}, McNemar p {a['mcnemar_p']}, ${a['cost_usd']}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["record"]:
        sys.exit(cmd_record(sys.argv[2]))
    sys.exit(main())
