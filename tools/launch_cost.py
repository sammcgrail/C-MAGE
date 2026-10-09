#!/usr/bin/env python3
"""What the blind readers really cost: every launch of tools/spawn_reader.sh, not only the readings
that reached a page.

The per-image figures on the Sonnet tabs price the READER transcripts of published rows. Two
things are spent beside them and were in no figure:

  * the LAUNCHER. spawn_reader.sh starts a headless Claude Code session on the reader's model
    whose only job is to spawn the reader and wait; it has its own transcript and its own usage
    (the reader is its sub-agent);
  * readers whose rows were NEVER PUBLISHED: stopped by the cost/time guard, refused or discarded
    by the gate's answer-key scan, rate-limited, failed.

Every launch leaves one project directory, /root/.claude/projects/-tmp-reader-launch-*/, holding the
launcher's transcript and the reader's (under <session>/subagents/). Each is priced exactly like
sonnet_cost.py prices a reader (same deduplication, same list prices). The lane is read from the
blind-image paths in the transcripts (/tmp/blinds55c_..., /tmp/blind_<slot>/imgNN.png, ...).

Results are cached in benchmarks/launch_costs.json by directory, keyed on the directory's file
sizes and mtimes, so a rebuild prices only new launches, and a launch whose transcripts are later
cleaned up keeps its recorded cost.

    launch_cost.py          refresh the cache; print totals per lane
"""
import glob
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sonnet_cost as SC  # noqa: E402

PROJECTS = Path("/root/.claude/projects")
CACHE = HERE.parent / "benchmarks" / "launch_costs.json"
# Order matters: the s55c pattern must win over s55's, and the Sonnet 5 arm's imgNN stems last.
LANES = [("s55c", re.compile(r"/tmp/blinds55c_")), ("s55", re.compile(r"/tmp/blinds55_")),
         ("nov", re.compile(r"/tmp/blindnov_")), ("ctl", re.compile(r"/tmp/blindctl_")),
         ("s5", re.compile(r"/tmp/blind_?\w*/img\d\d\.png"))]


def _sig(files: list[str]) -> str:
    return ";".join(f"{os.path.basename(p)}:{os.path.getsize(p)}:{int(os.path.getmtime(p))}" for p in sorted(files))


def _lane(files: list[str]) -> str:
    head = ""
    for p in files:
        with open(p, errors="replace") as fh:
            head += fh.read(400_000)
    return next((n for n, rx in LANES if rx.search(head)), "other")


def update() -> dict:
    cache = json.load(open(CACHE)) if CACHE.exists() else {"launches": {}}
    L = cache.setdefault("launches", {})
    for d in sorted(glob.glob(str(PROJECTS / "-tmp-reader-launch-*"))):
        mains = glob.glob(d + "/*.jsonl")
        subs = glob.glob(d + "/*/subagents/agent-*.jsonl")
        if not mains and not subs:
            continue
        name = os.path.basename(d)
        sig = _sig(mains + subs)
        if L.get(name, {}).get("sig") == sig:
            continue
        launcher, models = 0.0, set()
        for p in mains:
            t, m, _ = SC.reader_usage(p)
            launcher += SC.cost_of(t)
            models |= {x for x in m if x}
        readers = []
        for p in subs:
            t, m, dur = SC.reader_usage(p)
            readers.append({"agent": os.path.basename(p)[6:-6], "cost_usd": round(SC.cost_of(t), 4),
                            "models": sorted(x for x in m if x), "duration_s": dur})
        L[name] = {"sig": sig, "lane": _lane(mains + subs), "launcher_usd": round(launcher, 4),
                   "launcher_models": sorted(models), "readers": readers,
                   "finished": max(os.path.getmtime(p) for p in mains + subs)}
    cache["note"] = ("List-price cost of every spawn_reader.sh launch, from its transcripts: the launcher "
                     "session and its reader. Built by tools/launch_cost.py.")
    tmp = CACHE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, CACHE)
    return cache


def lane_total(lane: str, published: set[str], cache: dict | None = None) -> dict:
    """Spend of one lane over every launch: launcher sessions, readers whose rows were published
    (agent id in `published`), and readers whose rows never were."""
    cache = cache or (json.load(open(CACHE)) if CACHE.exists() else {"launches": {}})
    ls = [x for x in cache["launches"].values() if x["lane"] == lane]
    rs = [r for x in ls for r in x["readers"]]
    pub = [r for r in rs if r["agent"] in published]
    unpub = [r for r in rs if r["agent"] not in published]
    out = {"launches": len(ls), "launcher_usd": round(sum(x["launcher_usd"] for x in ls), 2),
           "readers": len(rs), "published_readers": len(pub),
           "published_usd": round(sum(r["cost_usd"] for r in pub), 2),
           "unpublished_readers": len(unpub), "unpublished_usd": round(sum(r["cost_usd"] for r in unpub), 2)}
    out["total_usd"] = round(out["launcher_usd"] + out["published_usd"] + out["unpublished_usd"], 2)
    return out


if __name__ == "__main__":
    c = update()
    lanes = sorted({x["lane"] for x in c["launches"].values()})
    for ln in lanes:
        print(ln, lane_total(ln, set(), c))
