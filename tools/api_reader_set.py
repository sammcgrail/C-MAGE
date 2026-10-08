#!/usr/bin/env python3
"""api_reader.py over an arbitrary image SET instead of the corpus zips (the superatom runs).

    api_reader_set.py --set SET.json [--spend-glob GLOB ...] [--cap 150] [--org-cap 195]
                      [--org-ledger DIR ...] -- <api_reader.py run arguments>

SET.json is a list of {"id", "png", "truth"}: id becomes the ledger key AND the ledger "name"
(neutral, e.g. sa_0001), png is a local path, truth the reference SMILES. Nothing but the image and
the prompt is sent, exactly as api_reader.py does for the corpus.

Spend guard (a watchdog thread; api_reader.py itself stops on --budget and on DIR/STOP):
  - our total = every ledger/retries file matched by --spend-glob, plus --extra-spent (e.g. the
    Haiku screening calls), must stay below --cap;
  - the org's month = our total + each --org-ledger run's spend so far + that run's projected
    remainder (its mean cost x images it still has to read, from --org-remaining) must stay below
    --org-cap.
When either would be crossed, the watchdog writes DIR/STOP: no new calls start, in-flight ones land.
"""
import argparse
import glob
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import api_reader as R  # noqa: E402


def spent_in(paths):
    t = 0.0
    for p in paths:
        for l in open(p):
            if l.strip():
                try:
                    t += json.loads(l).get("cost_usd") or 0
                except ValueError:
                    pass
    return t


def org_run(d: str, total_n: int) -> tuple[float, float]:
    d = Path(d)
    L = R.load(d / "ledger.jsonl")
    s = spent_in([p for p in (d / "ledger.jsonl", d / "retries.jsonl") if p.exists()])
    mean = s / len(L) if L else 0.0
    return s, mean * max(0, total_n - len(L))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--spend-glob", action="append", default=[])
    ap.add_argument("--extra-spent", type=float, default=0.0)
    ap.add_argument("--cap", type=float, default=150.0)
    ap.add_argument("--org-cap", type=float, default=195.0)
    ap.add_argument("--org-ledger", action="append", default=[])
    ap.add_argument("--org-remaining", type=int, action="append", default=[],
                    help="images the matching --org-ledger run reads in total")
    a, rest = ap.parse_known_args()
    if rest and rest[0] == "--":
        rest = rest[1:]
    items = json.load(open(a.set))
    rows = [{"key": x["id"], "name": x["id"], "truth_smiles": x["truth"], "png": x["png"]} for x in items]
    R.pick = lambda n: rows[:n] if n <= len(rows) else rows
    R.png_of = lambda row: Path(row["png"]).read_bytes()
    out = Path(rest[rest.index("--out") + 1])

    def guard():
        while True:
            ours = spent_in(sorted({p for g in a.spend_glob for p in glob.glob(g)})) + a.extra_spent
            org = ours + sum(sum(org_run(d, n)) for d, n in zip(a.org_ledger, a.org_remaining))
            if ours >= a.cap or org >= a.org_cap:
                msg = f"spend guard: ours ${ours:.2f} (cap ${a.cap}), org month projected ${org:.2f} (cap ${a.org_cap})"
                if not (out / "STOP").exists():
                    (out / "STOP").write_text(msg + "\n")
                    print("STOP " + msg, flush=True)
            time.sleep(20)

    threading.Thread(target=guard, daemon=True).start()
    sys.argv = ["api_reader.py"] + rest
    ns = argparse.Namespace()
    p = argparse.ArgumentParser()
    for f, kw in [("--out", {}), ("--env-file", {}), ("--model", {"default": "claude-sonnet-5-5"}),
                  ("--n", {"type": int, "default": 10 ** 6}), ("--conc", {"type": int, "default": 4}),
                  ("--budget", {"type": float, "default": 15.0}), ("--max-tokens", {"type": int, "default": 0}),
                  ("--prompt-file", {}), ("--prompt-version", {"default": "v1"}),
                  ("--max-consec-fail", {"type": int, "default": 5}), ("--publish-every", {"type": int, "default": 0}),
                  ("--publish-cmd", {})]:
        p.add_argument(f, **kw)
    ns = p.parse_args(rest)
    return R.cmd_run(ns)


if __name__ == "__main__":
    sys.exit(main())
