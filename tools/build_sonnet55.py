#!/usr/bin/env python3
"""Build the Sonnet 5.5 page: each image the s55 lane has read, beside the Sonnet 5 arm's
reading of the SAME image, scored by the same rule.

    build_sonnet55.py record-run <agent-id>             add a lane reader's run to the ledger
    build_sonnet55.py record-side <label> <agent-id> <pending.json> <answers.json>
                                                        add an extra reading (e.g. a re-run) to show
                                                        beside the two arms, scored the same way
    build_sonnet55.py                                   rebuild wall/sonnet55.json + tiles

HOW A ROW GETS HERE. The lane is sonnet_batch.py with SONNET_ARM=s55: claim named keys, a reader
answers, gate_and_score.py gates it (answer-key scan, every request served by claude-sonnet-5-5,
answers in the transcript) and scores it into /root/cmage-work/sonnet-s55/results.jsonl. This
script only READS that file and the Sonnet 5 arm's results.jsonl. Appending a run is: claim, read,
gate, `record-run`, rebuild. Nothing here is hand-edited.

WHAT "SAME PIPELINE" MEANS, AND WHERE IT DOES NOT HOLD. Same images (byte-identical copies from
corpus_rdkit_1500), same reader prompt as the Sonnet 5 batches the images came from (the text is
stored per run and shown on the page), same agent body and effort (max), same verdict function
(sonnet_batch.verdict). It differs in batch size (the lane's claim, not ten), image names (figNN,
so the Sonnet 5 audit and cost tally cannot mistake a lane reader for one of theirs) and CLI
version. The ledger records each, and the page says so.

COST is the API list price of the tokens the reader actually used, from its transcript, priced by
sonnet_cost.py (Sonnet 5.5 and Sonnet 5 have identical list prices, checked 2026-09-28). A run
reads its batch in one shared context, so per-image cost and time are the run's total over its
images -- an even split, the same estimate the Sonnet tab uses.
"""
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "benchmarks"))

import build_wall  # noqa: E402
from build_wall import WALL, render_pred, thumb, relate  # noqa: E402

# This page shows each image at card width, not as a 104 px wall tile, so it draws at twice the
# wall's tile size. thumb() and render_pred() read build_wall.TILE when called, so setting it
# here changes only this script's output (its own directories), never the wall's.
build_wall.TILE = 480

LANE_RESULTS = Path("/root/cmage-work/sonnet-s55/results.jsonl")
S5_RESULTS = Path("/root/cmage-work/sonnet/results.jsonl")
LEDGER = HERE.parent / "benchmarks" / "sonnet55_runs.json"
OUT = WALL / "sonnet55.json"
LANE_MODEL = "claude-sonnet-5-5"
S5_MODEL = "claude-sonnet-5"


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def ledger() -> dict:
    d = json.load(open(LEDGER)) if LEDGER.exists() else {}
    d.setdefault("runs", {})        # lane reader runs, by agent id
    d.setdefault("s5_runs", {})     # the Sonnet 5 reader runs the same images came from
    d.setdefault("s5_source", {})   # key -> Sonnet 5 agent id
    d.setdefault("side", [])        # extra readings shown beside the arms
    return d


def save(d: dict) -> None:
    LEDGER.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")


def transcript(aid: str) -> str:
    hits = glob.glob(f"/root/.claude/projects/*/*/subagents/agent-{aid}.jsonl")
    if len(hits) != 1:
        raise SystemExit(f"expected one transcript for {aid}, found {len(hits)}")
    return hits[0]


def run_record(aid: str, keys: list[str]) -> dict:
    """Tokens, cost, wall-clock and the SERVED model of one reader, from its own transcript."""
    import sonnet_cost
    path = transcript(aid)
    t, models, dur = sonnet_cost.reader_usage(path)
    recs = [json.loads(l) for l in open(path, errors="replace") if l.strip()]
    efforts = sorted({r.get("effort") for r in recs if r.get("type") == "assistant" and r.get("effort")})
    first = next(r for r in recs if r.get("type") == "user")
    c = first["message"]["content"]
    prompt = c if isinstance(c, str) else "".join(b.get("text", "") for b in c if isinstance(b, dict))
    meta = json.load(open(path[:-len(".jsonl")] + ".meta.json"))
    stamps = [r["timestamp"] for r in recs if isinstance(r.get("timestamp"), str)]
    return {
        "agent": aid, "models": sorted(m for m in models if m), "effort": efforts,
        "cli": first.get("version"), "agent_type": meta.get("agentType"),
        "started": min(stamps)[:19] + "Z", "finished": max(stamps)[:19] + "Z",
        "duration_s": dur, "images": len(keys), "keys": sorted(keys),
        "tokens": {k: t[k] for k in sonnet_cost.TOKEN_KEYS}, "requests": t["requests"],
        "cost_usd": round(sonnet_cost.cost_of(t), 4), "prompt": prompt,
    }


def contains(raw: str, smiles: str) -> bool:
    """gate_and_score's containment test. A cis bond is a backslash and the transcript is JSON,
    so the backslash sits in it escaped (doubled, or more after shell quoting): plain `in` missed
    exactly the everolimus row. Runs of backslashes are collapsed on both sides."""
    flat = lambda x: re.sub(r"\\+", r"\\\\", x)
    return bool(smiles) and (smiles in raw or smiles.replace("\\", "\\\\") in raw
                             or flat(smiles) in flat(raw))


def holders(smiles: str, raw_by_path: dict[str, str]) -> list[str]:
    return [p for p, raw in raw_by_path.items() if contains(raw, smiles)]


def cmd_record_run(aid: str) -> int:
    """Credit a lane reader with the lane rows whose answer is in its transcript -- the same
    containment test the gate applied before scoring them."""
    d = ledger()
    rec_path = transcript(aid)
    raw = open(rec_path, errors="replace").read()
    rows = load_jsonl(LANE_RESULTS)
    mine = [r["k"] for r in rows if contains(raw, r.get("sonnet_smiles"))]
    if not mine:
        raise SystemExit(f"no lane row's answer appears in {aid}'s transcript; nothing recorded")
    run = run_record(aid, mine)
    if run["models"] != [LANE_MODEL]:
        raise SystemExit(f"{aid} was served by {run['models']}, not {LANE_MODEL}; not a lane run")
    d["runs"][aid] = run
    save(d)
    print(f"recorded {aid}: {len(mine)} images, {run['models']}, effort {run['effort']}, "
          f"${run['cost_usd']:.2f}, {run['duration_s']} s")
    return 0


def cmd_record_side(label: str, aid: str, pending: str, answers: str) -> int:
    """An extra reading of lane images, scored with the lane's verdict function. Used for the
    Sonnet 5 re-run on the identical 8-image prompt: the only way to tell a model difference
    from run-to-run noise on a sample this small."""
    import sonnet_batch as B
    d = ledger()
    batch = json.load(open(pending))
    ans = {re.sub(r"\.png$", "", str(a["img"]).rsplit("/", 1)[-1]): a for a in json.load(open(answers))}
    raw = open(transcript(aid), errors="replace").read()
    reads = {}
    for b in batch:
        a = ans.get(b["slot"], {})
        smi = a.get("smiles")
        if smi and not contains(raw, smi):
            raise SystemExit(f"{b['slot']} answer is not in {aid}'s transcript; refusing")
        reads[b["k"]] = {"s": smi or "", "v": B.verdict(smi, b["truth"]), "conf": a.get("confidence")}
    run = run_record(aid, list(reads))
    d["side"] = [x for x in d["side"] if x["agent"] != aid] + [dict(label=label, agent=aid, run=run, reads=reads)]
    save(d)
    print(f"recorded side reading '{label}' ({run['models']}): "
          f"{sum(r['v'] == 'exact' for r in reads.values())}/{len(reads)} exact")
    return 0


def s5_sources(keys: list[str], s5_rows: dict[str, dict], d: dict) -> None:
    """Which Sonnet 5 reader produced each key's published reading. Found once by the audit's own
    reader search, then kept in the ledger so a rebuild does not need the transcripts."""
    todo = [k for k in keys if k not in d["s5_source"]]
    if not todo:
        return
    import audit_sonnet_rows as A
    raw_by_path = {p: raw for p, (_, raw) in A.reader_transcripts(set()).items()}
    for k in todo:
        hs = holders(s5_rows[k].get("sonnet_smiles"), raw_by_path)
        if not hs:
            print(f"  WARNING: no Sonnet 5 transcript holds {k}'s reading; no cost/time for it")
            continue
        p = max(hs, key=os.path.getmtime)
        aid = Path(p).stem.removeprefix("agent-")
        d["s5_source"][k] = aid
        if aid not in d["s5_runs"]:
            # images = the distinct slots this reader answered, i.e. its batch size
            n = len({s for s, _ in A.pairs(raw_by_path[p])}) or 10
            run = run_record(aid, [])
            run["images"] = n
            run.pop("keys")
            run["prompt_chars"] = len(run.pop("prompt"))
            d["s5_runs"][aid] = run


def failure_type(v: str, g: dict) -> str:
    """g is a reading() dict: `formula` is the graded ladder's formula_match, `heavy` its heavy_delta."""
    if v == "exact":
        return "Control: Sonnet 5 read it exactly"
    if v == "stereo":
        return "Stereochemistry only"
    if v == "invalid":
        return "Unparseable SMILES"
    if g.get("formula") is False:
        hd = g.get("heavy") or 0
        return (f"Atom count off ({hd:+d} heavy atom{'s' if abs(hd) != 1 else ''})".replace("-", "\u2212")
                if hd else "Wrong elements")
    return "Right atoms, wrong connectivity"


def reading(smi: str, truth: str, v: str, conf, name: str, graded) -> dict:
    refs = [(name, graded.ref_forms(truth))]
    g = graded.grade_prediction(smi, refs) if smi else {}
    return {"s": smi or "", "v": v, "conf": conf, "g": g.get("grade") or v,
            "formula": g.get("formula_match"), "heavy": g.get("heavy_delta"),
            "r": relate(smi or "", truth)}


def build() -> int:
    import graded
    d = ledger()
    lane = load_jsonl(LANE_RESULTS)
    if not lane:
        raise SystemExit(f"no lane rows in {LANE_RESULTS}")
    s5 = {r["k"]: r for r in load_jsonl(S5_RESULTS)}
    missing = [r["k"] for r in lane if r["k"] not in s5]
    if missing:
        raise SystemExit(f"lane rows with no Sonnet 5 reading to compare against: {missing}")
    keys = [r["k"] for r in lane]
    s5_sources(keys, s5, d)
    save(d)
    run_of = {k: aid for aid, run in d["runs"].items() for k in run["keys"]}
    unrun = [k for k in keys if k not in run_of]
    if unrun:
        raise SystemExit(f"lane rows not credited to any recorded run (record-run first): {unrun}")

    idx = {}
    for dd in sorted(glob.glob("/root/cmage-work/cmage-img*/corpus_rdkit_1500")):
        for p in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(p), p)
    dirs = {x: WALL / x for x in ("sonnet55", "sonnet55_s5", "sonnet55_pred")}
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)

    rows = []
    for r in lane:
        k, t = r["k"], r["truth"]
        o = s5[k]
        if o["truth"] != t:
            raise SystemExit(f"{k}: lane and Sonnet 5 rows disagree on the truth")
        thumb(Path(idx[k + ".png"]), dirs["sonnet55"] / f"{k}.png")
        a5 = reading(o.get("sonnet_smiles"), t, o["sonnet_verdict"], o.get("sonnet_conf"), r["name"], graded)
        a55 = reading(r.get("sonnet_smiles"), t, r["sonnet_verdict"], r.get("sonnet_conf"), r["name"], graded)
        # Did the reader NAME the compound? The prompt allows recognising a molecule and
        # cross-checking, and every image here is a known drug, so a right answer can be recall
        # as much as reading. Stated per row so the page can say how much of each there was.
        a5["named"] = bool((o.get("sonnet_name") or "").strip())
        a55["named"] = bool((r.get("sonnet_name") or "").strip())
        a5["p"] = 1 if render_pred(a5["s"], dirs["sonnet55_s5"] / f"{k}.png") else 0
        a55["p"] = 1 if render_pred(a55["s"], dirs["sonnet55_pred"] / f"{k}.png") else 0
        src = d["s5_runs"].get(d["s5_source"].get(k, ""), {})
        run = d["runs"][run_of[k]]
        a5.update(cost=round(src["cost_usd"] / src["images"], 3) if src else None,
                  time=round(src["duration_s"] / src["images"]) if src else None,
                  model=(src.get("models") or [None])[0], run=src.get("started"))
        a55.update(cost=round(run["cost_usd"] / run["images"], 3),
                   time=round(run["duration_s"] / run["images"]), model=run["models"][0], run=run["started"])
        side = [{"label": x["label"], "model": x["run"]["models"][0], **x["reads"][k]}
                for x in d["side"] if k in x["reads"]]
        rows.append({
            "k": k, "n": r["name"], "t": t,
            "role": "control" if o["sonnet_verdict"] == "exact" else "failure",
            "type": failure_type(o["sonnet_verdict"], a5),
            "cx": {"s": r["ocr_smiles"], "v": r["ocr_verdict"]},
            "s5": a5, "s55": a55, "side": side,
            "delta": int(a55["v"] == "exact") - int(a5["v"] == "exact"),
        })
    rows.sort(key=lambda x: (x["role"] != "failure", x["n"].lower()))

    fail = [x for x in rows if x["role"] == "failure"]
    ctrl = [x for x in rows if x["role"] == "control"]
    ex = lambda xs, arm: sum(1 for x in xs if x[arm]["v"] == "exact")
    runs = sorted(d["runs"].values(), key=lambda x: x["started"])
    name = {x["k"]: x["n"] for x in rows}
    s5_used = sorted(({**d["s5_runs"][a], "for": sorted(name[k] for k in keys if d["s5_source"].get(k) == a)}
                      for a in {d["s5_source"][k] for k in keys if k in d["s5_source"]}),
                     key=lambda x: x["started"])
    summary = {
        "n": len(rows), "failures": len(fail), "controls": len(ctrl),
        "s5_exact": ex(rows, "s5"), "s55_exact": ex(rows, "s55"),
        "fixed": sum(1 for x in rows if x["delta"] > 0), "broke": sum(1 for x in rows if x["delta"] < 0),
        "fixed_of_failures": ex(fail, "s55"), "kept_of_controls": ex(ctrl, "s55"),
        "s5_named": sum(1 for x in rows if x["s5"]["named"]), "s55_named": sum(1 for x in rows if x["s55"]["named"]),
        "s5_named_wrong": sum(1 for x in rows if x["s5"]["named"] and x["s5"]["v"] != "exact"),
        "s55_cost": round(sum(r["cost_usd"] for r in runs), 2),
        "s55_seconds": sum(r["duration_s"] for r in runs),
        "s55_cost_per_image": round(sum(r["cost_usd"] for r in runs) / max(1, sum(r["images"] for r in runs)), 2),
        "s5_cost_per_image": round(sum(x["s5"]["cost"] or 0 for x in rows) / len(rows), 2),
        "s55_time_per_image": round(sum(r["duration_s"] for r in runs) / max(1, sum(r["images"] for r in runs))),
        "s5_time_per_image": round(sum(x["s5"]["time"] or 0 for x in rows) / len(rows)),
    }
    side = [{"label": x["label"], "model": x["run"]["models"][0], "n": len(x["reads"]),
             "exact": sum(1 for v in x["reads"].values() if v["v"] == "exact"),
             "fixed": sum(1 for k2, v in x["reads"].items() if v["v"] == "exact" and s5[k2]["sonnet_verdict"] != "exact"),
             "cost": x["run"]["cost_usd"], "seconds": x["run"]["duration_s"],
             "effort": x["run"]["effort"], "cli": x["run"]["cli"]} for x in d["side"]]
    out = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": summary, "rows": rows, "side": side,
        "runs": [{k2: v for k2, v in r.items() if k2 not in ("keys",)} for r in runs],
        "s5runs": [{k2: s5r.get(k2) for k2 in ("models", "effort", "cli", "agent_type", "images",
                                                  "duration_s", "cost_usd", "started", "for")} for s5r in s5_used],
        "price": {"per_mtok": __import__("sonnet_cost").PRICE_PER_MTOK,
                  "source": "https://platform.claude.com/docs/en/about-claude/pricing",
                  "checked": "2026-09-28",
                  "note": "Sonnet 5.5 and Sonnet 5 list at the same per-token prices."},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size/1e3:.1f} KB): {len(rows)} rows, "
          f"Sonnet 5 {summary['s5_exact']}/{len(rows)} exact, Sonnet 5.5 {summary['s55_exact']}/{len(rows)}, "
          f"fixed {summary['fixed']}, broke {summary['broke']}")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["record-run"] and len(a) == 2:
        sys.exit(cmd_record_run(a[1]))
    if a[:1] == ["record-side"] and len(a) == 5:
        sys.exit(cmd_record_side(*a[1:]))
    if not a:
        sys.exit(build())
    raise SystemExit(__doc__)
