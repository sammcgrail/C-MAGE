#!/usr/bin/env python3
"""Build the Sonnet 5.5 page: each image the s55 lane has read, beside the Sonnet 5 arm's
reading of the SAME image, scored by the same rule.

    build_sonnet55.py record-run <agent-id> <batch>     add a lane reader's run to the ledger
    build_sonnet55.py record-side <label> <agent-id> <pending.json> <answers.json> <batch>
                                                        add an extra reading (e.g. a re-run) to show
                                                        beside the two arms, scored the same way
    build_sonnet55.py batch-note <batch> <text>         say how a batch's images were picked (shown
                                                        on the page)
    build_sonnet55.py                                   rebuild wall/sonnet55.json + tiles

BATCHES. Every run and side reading carries the batch it belongs to (an integer, required on
record: a default would silently mislabel the next batch). Side readings with the same LABEL
are one arm: two Sonnet 5 re-run readers of ten images each are one "Sonnet 5 re-run" over
twenty. The headline compares Sonnet 5.5 with the first side label ("Sonnet 5 re-run") on every
image both read, with an exact McNemar test on the discordant pairs.

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
    d.setdefault("batches", {})     # batch -> how its images were picked
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
    delegated = [b.get("input", {}).get("subagent_type") for r in recs if r.get("type") == "assistant"
                 for b in ((r.get("message") or {}).get("content") or [])
                 if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")]
    if delegated:
        raise SystemExit(f"{aid} delegated to {len(delegated)} sub-agent(s) {delegated}: its answers are not "
                         f"all its own model's, so it cannot be recorded as that model's reading")
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


def batch_no(b: str) -> int:
    if not str(b).isdigit() or int(b) < 1:
        raise SystemExit(f"batch must be a positive integer, got {b!r}")
    return int(b)


def cmd_batch_note(batch: str, text: str) -> int:
    d = ledger()
    d["batches"][str(batch_no(batch))] = text
    save(d)
    print(f"batch {batch}: {text}")
    return 0


def cmd_record_run(aid: str, batch: str) -> int:
    """Credit a lane reader with the lane rows whose answer is in its transcript -- the same
    containment test the gate applied before scoring them."""
    d = ledger()
    rec_path = transcript(aid)
    raw = open(rec_path, errors="replace").read()
    rows = load_jsonl(LANE_RESULTS)
    mine = [r["k"] for r in rows if contains(raw, r.get("sonnet_smiles"))]
    if not mine:
        raise SystemExit(f"no lane row's answer appears in {aid}'s transcript; nothing recorded")
    already = {k: a for a, r in d["runs"].items() if a != aid for k in r["keys"]}
    dup = [k for k in mine if k in already]
    if dup:
        raise SystemExit(f"{aid}: rows already credited to another run: {[(k, already[k]) for k in dup]}")
    run = run_record(aid, mine)
    if run["models"] != [LANE_MODEL]:
        raise SystemExit(f"{aid} was served by {run['models']}, not {LANE_MODEL}; not a lane run")
    run["batch"] = batch_no(batch)
    d["runs"][aid] = run
    save(d)
    print(f"recorded {aid}: {len(mine)} images, {run['models']}, effort {run['effort']}, "
          f"${run['cost_usd']:.2f}, {run['duration_s']} s")
    return 0


def cmd_record_side(label: str, aid: str, pending: str, answers: str, batch_arg: str) -> int:
    """An extra reading of lane images, scored with the lane's verdict function. Used for the
    Sonnet 5 re-run on the identical 8-image prompt: the only way to tell a model difference
    from run-to-run noise on a sample this small."""
    import sonnet_batch as B
    batch_no(batch_arg)
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
    if set(ans) != {b["slot"] for b in batch}:
        raise SystemExit(f"answers {sorted(ans)} do not cover the claim {sorted(b['slot'] for b in batch)}")
    run = run_record(aid, list(reads))
    d["side"] = [x for x in d["side"] if x["agent"] != aid] + [dict(label=label, agent=aid, run=run, reads=reads,
                                                                    batch=batch_no(batch_arg))]
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


def num_conf(c):
    """A reader's confidence as a number 0-100, or None. The prompt asks for 0-100; older Sonnet 5
    rows carry words ("high"), which have no place on a numeric calibration table."""
    try:
        x = float(c)
    except (TypeError, ValueError):
        return None
    return x if 0 <= x <= 100 else None


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p: under 'no difference' each discordant pair is a fair coin, so
    p = 2 * P(X <= min(b, c)), X ~ Binomial(b + c, 1/2), capped at 1."""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def compare(rows: list[dict], base: str) -> dict:
    """Sonnet 5.5 against the `base` side label on the rows both read, plus the published run."""
    xs = [r for r in rows if base in r["sidev"]]
    ok55 = lambda r: r["s55"]["v"] == "exact"
    okb = lambda r: r["sidev"][base]["v"] == "exact"
    b = sum(1 for r in xs if ok55(r) and not okb(r))
    c = sum(1 for r in xs if okb(r) and not ok55(r))
    return {"n": len(xs), "s55": sum(map(ok55, xs)), "base": sum(map(okb, xs)),
            "published": sum(1 for r in xs if r["s5"]["v"] == "exact"),
            "ahead": b, "behind": c, "p": float(f"{mcnemar_exact(b, c):.3g}"),
            "ahead_names": [r["n"] for r in xs if ok55(r) and not okb(r)],
            "behind_names": [r["n"] for r in xs if okb(r) and not ok55(r)]}


LOW_CONF = 60   # a Sonnet 5 exact read below this confidence counts as a "low-confidence right"
BINS = [(90, 101, "90-100"), (80, 90, "80-89"), (60, 80, "60-79"), (0, 60, "under 60")]


def calibration(reads: list[dict]) -> dict:
    """Is confidence higher when right? Mean confidence right vs wrong, and exact-rate per bin."""
    num = [(num_conf(x["conf"]), x["v"] == "exact") for x in reads]
    right = [c for c, ok in num if c is not None and ok]
    wrong = [c for c, ok in num if c is not None and not ok]
    mean = lambda v: round(sum(v) / len(v), 1) if v else None
    bins = []
    for lo, hi, lab in BINS:
        inb = [ok for c, ok in num if c is not None and lo <= c < hi]
        bins.append({"bin": lab, "n": len(inb), "exact": sum(inb)})
    both = [(c, ok) for c, ok in num if c is not None]
    brier = round(sum((c / 100 - ok) ** 2 for c, ok in both) / len(both), 3) if both else None
    return {"n": len(reads), "numeric": len(both), "right_n": len(right), "wrong_n": len(wrong),
            "right_mean": mean(right), "wrong_mean": mean(wrong),
            "right_min": min(right) if right else None, "wrong_max": max(wrong) if wrong else None,
            "brier": brier, "bins": bins}


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
    nobatch = [a for a, r in d["runs"].items() if "batch" not in r] + [x["agent"] for x in d["side"] if "batch" not in x]
    if nobatch:
        raise SystemExit(f"runs/side readings with no batch recorded: {nobatch}")
    # Side readings sharing a label are one arm (two re-run readers of ten = one re-run of twenty).
    labels = list(dict.fromkeys(x["label"] for x in d["side"]))
    for lab in labels:
        seen: dict[str, str] = {}
        for x in d["side"]:
            if x["label"] != lab:
                continue
            for k in x["reads"]:
                if k in seen:
                    raise SystemExit(f"side label {lab!r} reads {k} twice ({seen[k]}, {x['agent']})")
                seen[k] = x["agent"]

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
        sidev = {}
        for x in d["side"]:
            if k in x["reads"]:
                sidev[x["label"]] = {"label": x["label"], "model": x["run"]["models"][0], "batch": x["batch"],
                                     "cost": round(x["run"]["cost_usd"] / x["run"]["images"], 3),
                                     "time": round(x["run"]["duration_s"] / x["run"]["images"]),
                                     **x["reads"][k]}
        rows.append({
            "k": k, "n": r["name"], "t": t, "batch": run["batch"],
            "role": "control" if o["sonnet_verdict"] == "exact" else "failure",
            "type": failure_type(o["sonnet_verdict"], a5),
            "cx": {"s": r["ocr_smiles"], "v": r["ocr_verdict"]},
            "s5": a5, "s55": a55, "sidev": sidev,
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
    base = labels[0] if labels else None
    batches = sorted({x["batch"] for x in rows})
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
        "batches": batches,
    }
    stats = None
    if base:
        groups = [("All images", rows)]
        groups += [(f"Batch {b}", [x for x in rows if x["batch"] == b]) for b in batches]
        # The rights split by how sure Sonnet 5 was: batch 2 picked the least sure on purpose,
        # batch 1's two controls were read at 92-95, and pooling them would hide which is which.
        low = lambda x: (num_conf(x["s5"]["conf"]) if num_conf(x["s5"]["conf"]) is not None else 100) < LOW_CONF
        groups += [("Sonnet 5 misses", fail),
                   (f"Sonnet 5 right, confidence under {LOW_CONF}", [x for x in ctrl if low(x)]),
                   (f"Sonnet 5 right, confidence {LOW_CONF}+", [x for x in ctrl if not low(x)])]
        groups = [g for g in groups if g[1]]
        stats = {
            "base": base,
            "overall": compare(rows, base),
            "groups": [dict(label=g, **compare(xs, base)) for g, xs in groups],
            # Run-to-run noise of Sonnet 5 alone: how often a same-prompt re-run disagrees with
            # the published reading, split by what the published reading was.
            "noise": {
                "published_miss_rerun_right": sum(1 for x in fail if base in x["sidev"] and x["sidev"][base]["v"] == "exact"),
                "published_miss_n": sum(1 for x in fail if base in x["sidev"]),
                "published_right_rerun_miss": sum(1 for x in ctrl if base in x["sidev"] and x["sidev"][base]["v"] != "exact"),
                "published_right_n": sum(1 for x in ctrl if base in x["sidev"]),
            },
            "calibration": {
                "Sonnet 5.5": calibration([x["s55"] for x in rows if base in x["sidev"]]),
                base: calibration([x["sidev"][base] for x in rows if base in x["sidev"]]),
            },
        }
        # Per READER, because a reader reads its batch in one context: its images are not
        # independent draws, which the McNemar p assumes. If every 5.5 reader beats every re-run
        # reader, the result does not hang on that assumption.
        stats["readers"] = {
            "Sonnet 5.5": [{"agent": a, "batch": r["batch"], "n": len(r["keys"]),
                            "exact": sum(1 for x in rows if x["k"] in r["keys"] and x["s55"]["v"] == "exact")}
                           for a, r in sorted(d["runs"].items(), key=lambda t: t[1]["started"])],
            base: [{"agent": x["agent"], "batch": x["batch"], "n": len(x["reads"]),
                    "exact": sum(1 for v in x["reads"].values() if v["v"] == "exact")}
                   for x in sorted(d["side"], key=lambda x: x["run"]["started"]) if x["label"] == base],
        }
        # The same-model agreement where two independent re-runs exist (batch 1): the noise floor.
        if len(labels) > 1:
            both = [x for x in rows if labels[0] in x["sidev"] and labels[1] in x["sidev"]]
            e = lambda x, l: x["sidev"][l]["v"] == "exact"
            stats["rerun_vs_rerun"] = {"labels": labels[:2], "n": len(both),
                                       "agree": sum(1 for x in both if e(x, labels[0]) == e(x, labels[1]))}
    side = []
    for lab in labels:
        xs = [x for x in d["side"] if x["label"] == lab]
        reads = {k2: v for x in xs for k2, v in x["reads"].items()}
        side.append({"label": lab, "model": sorted({m for x in xs for m in x["run"]["models"]}),
                     "n": len(reads), "exact": sum(1 for v in reads.values() if v["v"] == "exact"),
                     "fixed": sum(1 for k2, v in reads.items() if v["v"] == "exact" and s5[k2]["sonnet_verdict"] != "exact"),
                     "cost": round(sum(x["run"]["cost_usd"] for x in xs), 4),
                     "seconds": sum(x["run"]["duration_s"] for x in xs),
                     "batches": sorted({x["batch"] for x in xs}),
                     "effort": sorted({e2 for x in xs for e2 in x["run"]["effort"]}),
                     "cli": ", ".join(sorted({x["run"]["cli"] for x in xs})),
                     "runs": [{"agent": x["agent"], "batch": x["batch"], "images": x["run"]["images"],
                               "started": x["run"]["started"], "models": x["run"]["models"],
                               "effort": x["run"]["effort"], "cli": x["run"]["cli"],
                               "cost_usd": x["run"]["cost_usd"], "duration_s": x["run"]["duration_s"]}
                              for x in sorted(xs, key=lambda x: x["run"]["started"])]})
    for x in rows:
        x["side"] = [x["sidev"][lab] for lab in labels if lab in x["sidev"]]
        del x["sidev"]
    out = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": summary, "stats": stats, "rows": rows, "side": side,
        "batches": {b: d["batches"].get(str(b), "") for b in batches},
        "runs": [{k2: v for k2, v in r.items() if k2 not in ("keys",)} for r in runs],
        "s5runs": [{k2: s5r.get(k2) for k2 in ("models", "effort", "cli", "agent_type", "images",
                                                  "duration_s", "cost_usd", "started", "for")} for s5r in s5_used],
        "price": {"per_mtok": __import__("sonnet_cost").PRICE_PER_MTOK,
                  "source": "https://platform.claude.com/docs/en/about-claude/pricing",
                  "checked": "2026-09-28",
                  "note": "Sonnet 5.5 and Sonnet 5 list at the same per-token prices."},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    o = (stats or {}).get("overall") or {}
    print(f"wrote {OUT} ({OUT.stat().st_size/1e3:.1f} KB): {len(rows)} rows in batches {batches}, "
          f"published Sonnet 5 {summary['s5_exact']}/{len(rows)}, Sonnet 5.5 {summary['s55_exact']}/{len(rows)}"
          + (f"; vs {base}: 5.5 {o['s55']}/{o['n']}, re-run {o['base']}/{o['n']}, "
             f"5.5 ahead {o['ahead']}, behind {o['behind']}, McNemar exact p={o['p']}" if o else ""))
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["record-run"] and len(a) == 3:
        sys.exit(cmd_record_run(a[1], a[2]))
    if a[:1] == ["record-side"] and len(a) == 6:
        sys.exit(cmd_record_side(*a[1:]))
    if a[:1] == ["batch-note"] and len(a) == 3:
        sys.exit(cmd_batch_note(a[1], a[2]))
    if not a:
        sys.exit(build())
    raise SystemExit(__doc__)
