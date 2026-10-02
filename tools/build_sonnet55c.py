#!/usr/bin/env python3
"""The Sonnet 5.5 tab: Sonnet 5.5 reading the WHOLE corpus, in corpus order, paired image for
image with the Sonnet 5 arm.

    build_sonnet55c.py record-run <agent-id> <batch>   credit a lane reader with its rows
    build_sonnet55c.py batch-note <batch> <text>       say how a batch came about (shown on the page)
    build_sonnet55c.py                                 rebuild wall/sonnet55.json + 240 px tiles

WHY A SECOND LANE (s55c) AND NOT s55. s55 holds 28 images hand-picked on Sonnet 5's failures.
`sonnet_batch.py next` skips anything already in a lane's results, so running the corpus through
s55 would silently drop those 28 from the corpus arm AND mix a selected sample into an unselected
one. s55c starts at the first corpus key and takes the next ten each time, which is the order the
Sonnet 5 arm read the corpus (sorted keys), excluding nothing. The hand-picked set stays on the
compare page (build_sonnet55.py), which also pairs this lane with Sonnet 5 automatically.

HOW A ROW GETS HERE. A usage-block cadence (site-specific, so kept outside the fork), or a hand run
of the same steps: claim with
SONNET_ARM=s55c, one reader on tools/spawn_reader.sh claude-sonnet-5-5 with the fixed prompt
tools/reader_prompt_s55c.txt, gate_and_score.py (answer-key scan, every request served by exactly
claude-sonnet-5-5, no delegation, every answer in the transcript), then `record-run` and a rebuild.
Nothing here is hand-edited, and this script only READS the lane's results.jsonl.

The payload has the Sonnet tab's shape (index.html renders both with one code path), plus a third
headline side for Sonnet 5 on the same images and each row's Sonnet 5 reading.
"""
import glob
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "benchmarks"))

import build_wall  # noqa: E402
from build_wall import WALL, THRESHOLD, render_pred, thumb, relate  # noqa: E402

_TILE = build_wall.TILE
import build_sonnet55 as B55  # noqa: E402  (shared ledger helpers: run_record, contains, mcnemar)
build_wall.TILE = _TILE     # build_sonnet55 draws its cards at 480 px; this tab is wall tiles

LANE = "s55c"
LANE_MODEL = "claude-sonnet-5-5"
LANE_RESULTS = Path(f"/root/cmage-work/sonnet-{LANE}/results.jsonl")
S5_RESULTS = Path("/root/cmage-work/sonnet/results.jsonl")
LEDGER = HERE.parent / "benchmarks" / "sonnet55c_runs.json"
PROMPT = HERE / "reader_prompt_s55c.txt"
OUT = WALL / "sonnet55.json"
DIR = "sonnet55c"          # tiles: wall/sonnet55c/, wall/sonnet55c_pred/, wall/sonnet55c_ocr/


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def ledger() -> dict:
    d = json.load(open(LEDGER)) if LEDGER.exists() else {}
    d.setdefault("runs", {})
    d.setdefault("batches", {})
    return d


def save(d: dict) -> None:
    LEDGER.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")


def cmd_record_run(aid: str, batch: str) -> int:
    """Credit a lane reader with the lane rows whose answer is in its transcript -- the same
    containment test the gate applied before scoring them. Rows already credited to another run
    are never re-credited, so a SMILES two readers share (benzene) cannot move between runs."""
    d = ledger()
    raw = open(B55.transcript(aid), errors="replace").read()
    credited = {k for a, r in d["runs"].items() if a != aid for k in r["keys"]}
    mine = [r["k"] for r in load_jsonl(LANE_RESULTS)
            if r["k"] not in credited and B55.contains(raw, r.get("sonnet_smiles"))]
    if not mine:
        raise SystemExit(f"no uncredited {LANE} row's answer appears in {aid}'s transcript; nothing recorded")
    run = B55.run_record(aid, mine)
    if run["models"] != [LANE_MODEL]:
        raise SystemExit(f"{aid} was served by {run['models']}, not {LANE_MODEL}; not a {LANE} run")
    run["batch"] = B55.batch_no(batch)
    d["runs"][aid] = run
    save(d)
    print(f"recorded {aid}: batch {run['batch']}, {len(mine)} images, {run['models']}, "
          f"effort {run['effort']}, ${run['cost_usd']:.2f}, {run['duration_s']} s")
    return 0


def cmd_batch_note(batch: str, text: str) -> int:
    d = ledger()
    d["batches"][str(B55.batch_no(batch))] = text
    save(d)
    print(f"batch {batch}: {text}")
    return 0


def paired(lane: list[dict], s5: dict[str, dict]) -> dict:
    """5.5 against Sonnet 5 on every lane image the Sonnet 5 arm has also read."""
    xs = [r for r in lane if r["k"] in s5]
    ok55 = lambda r: r["sonnet_verdict"] == "exact"
    ok5 = lambda r: s5[r["k"]]["sonnet_verdict"] == "exact"
    b = sum(1 for r in xs if ok55(r) and not ok5(r))
    c = sum(1 for r in xs if ok5(r) and not ok55(r))
    return {"n": len(xs), "s55": sum(map(ok55, xs)), "s5": sum(map(ok5, xs)),
            "ahead": b, "behind": c, "p": float(f"{B55.mcnemar_exact(b, c):.3g}")}


def method() -> list[dict]:
    return [
        {"h": "What this tab is", "points": [
            "Sonnet 5.5 reading the whole image corpus, ten images per Claude usage block, in the same "
            "order the Sonnet 5 arm read it (sorted by compound key). Nothing is skipped or hand-picked, "
            "so every image here pairs with the Sonnet 5 reading of the same drawing.",
            "Scored exactly like the Sonnet 5 tab: RDKit canonical SMILES against the PubChem reference, "
            "exact / stereo-only / wrong / unparseable, and CXMolScribe's reading of the same image beside it.",
        ]},
        {"h": "Blind, and checked", "points": [
            "Images are handed over under anonymised names (fig01…), because the corpus files are named "
            "after their compounds.",
            "Every reader is spawned on the exact model id and every API response in its transcript must be "
            "stamped claude-sonnet-5-5. A reader that hands work to a sub-agent is refused, because the "
            "sub-agent runs on a different model.",
            "Each transcript is scanned for lookups (network requests, reads of the answer files) and every "
            "answer must appear in it before a single row is scored.",
        ]},
        {"h": "What differs from the Sonnet 5 arm", "points": [
            "One fixed prompt, shown below, for every batch. The Sonnet 5 arm's prompt changed over its "
            "weeks of batches, so a pair can differ by prompt as well as by model.",
            "Ten images per reader, one reader per usage block, at max effort.",
        ]},
    ]


def build() -> int:
    d = ledger()
    lane = load_jsonl(LANE_RESULTS)
    s5 = {r["k"]: r for r in load_jsonl(S5_RESULTS)}
    run_of = {k: a for a, r in d["runs"].items() for k in r["keys"]}
    unrun = [r["k"] for r in lane if r["k"] not in run_of]
    if unrun:
        raise SystemExit(f"{LANE} rows not credited to any recorded run (record-run first): {unrun}")

    idx = {}
    for dd in sorted(glob.glob("/root/cmage-work/cmage-img*/corpus_rdkit_1500")):
        for p in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(p), p)
    img, pred, ocr = (WALL / DIR, WALL / f"{DIR}_pred", WALL / f"{DIR}_ocr")
    for p in (img, pred, ocr):
        p.mkdir(parents=True, exist_ok=True)

    rows = []
    for r in lane:
        k = r["k"]
        thumb(Path(idx[k + ".png"]), img / f"{k}.png")
        has = render_pred(r.get("sonnet_smiles") or "", pred / f"{k}.png")
        has_ocr = render_pred(r.get("ocr_smiles") or "", ocr / f"{k}.png")
        sv, ov = r["sonnet_verdict"] == "exact", r["ocr_verdict"] == "exact"
        run = d["runs"][run_of[k]]
        row = {
            "k": k, "n": r["name"], "v": r["sonnet_verdict"], "g": r["sonnet_verdict"],
            "o": "both" if sv and ov else "sonnet" if sv else "cxms" if ov else "neither",
            "c": None, "s": r.get("sonnet_smiles") or "", "t": r["truth"], "p": 1 if has else 0,
            "r": relate(r.get("sonnet_smiles") or "", r["truth"]),
            "ocr": r["ocr_smiles"], "ocrv": r["ocr_verdict"], "ocrc": r["ocr_conf"],
            "cx": 1 if "|$" in (r.get("ocr_smiles") or "") else 0, "po": 1 if has_ocr else 0,
            "sconf": r.get("sonnet_conf"), "batch": run["batch"],
            "rc": round(run["cost_usd"] / run["images"], 3), "rt": round(run["duration_s"] / run["images"]),
            "bc": run["cost_usd"], "bs": run["duration_s"], "bn": run["images"],
        }
        o = s5.get(k)
        if o:
            if o["truth"] != r["truth"]:
                raise SystemExit(f"{k}: {LANE} and Sonnet 5 rows disagree on the truth")
            row["s5"] = {"s": o.get("sonnet_smiles") or "", "v": o["sonnet_verdict"], "conf": o.get("sonnet_conf")}
        rows.append(row)

    n = len(rows)
    if not n:
        raise SystemExit(f"no rows in {LANE_RESULTS}")
    s_ex = sum(1 for r in rows if r["v"] == "exact")
    o_ex = sum(1 for r in rows if r["ocrv"] == "exact")
    P = paired(lane, s5)
    runs = sorted(d["runs"].values(), key=lambda x: x["started"])
    cost = sum(r["cost_usd"] for r in runs)
    secs = sum(r["duration_s"] for r in runs)
    imgs = sum(r["images"] for r in runs)
    pct = lambda a, b: round(a / b * 100, 1) if b else 0.0
    corpus_n = len(json.load(open(WALL / "images.json"))["rows"])
    classes = []
    if n >= 100:     # per-bucket rates on a few dozen images are noise; the Sonnet tab shows them at 1,000+
        try:
            import classify_structures
            classes = classify_structures.classes(lane)
        except Exception as e:
            print(f"  WARNING structure classes not computed: {e}")
    import build_sonnet
    out = {
        "arm": "Sonnet 5.5", "dir": DIR, "reader": "Sonnet 5.5", "rows": rows,
        "compare": {
            "n": n, "corpus": corpus_n,
            "sides": [
                {"label": "Sonnet 5.5", "exact": s_ex, "n": n, "pct": pct(s_ex, n)},
                {"label": "Sonnet 5", "exact": P["s5"], "n": P["n"], "pct": pct(P["s5"], P["n"])},
                {"label": "CXMolScribe", "exact": o_ex, "n": n, "pct": pct(o_ex, n)},
            ],
            "agree": sum(1 for r in rows if r["o"] == "both"),
            "either": sum(1 for r in rows if r["o"] != "neither"),
            "paired": P,
            "cost": {"usd": round(cost, 2), "reads": imgs, "perImage": round(cost / imgs, 2) if imgs else None,
                     "note": (f"Estimated API cost at list price: ${cost:,.2f} for the {imgs} Sonnet 5.5 reads "
                              f"shown, about ${cost / imgs:.2f} and {round(secs / imgs)} s per image.") if imgs else ""},
            "breakdown": [
                {"key": "both", "label": "Both right", "n": sum(1 for r in rows if r["o"] == "both")},
                {"key": "sonnet", "label": "Sonnet 5.5 only", "n": sum(1 for r in rows if r["o"] == "sonnet")},
                {"key": "cxms", "label": "CXMolScribe only", "n": sum(1 for r in rows if r["o"] == "cxms")},
                {"key": "neither", "label": "Neither", "n": sum(1 for r in rows if r["o"] == "neither")},
            ],
        },
        "xlink": {"href": "/sonnet-compare",
                  "text": "Every reading on this tab is Sonnet 5.5, in the Sonnet 5 arm's order.",
                  "bold": "Sonnet 5 vs 5.5, image for image →"},
        "prompt": PROMPT.read_text(),
        "workflow": build_sonnet.WORKFLOW, "examples": [], "classes": classes,
        "method": method(),
        "cx": sum(1 for r in rows if r.get("cx")), "cxLabel": "CXMolScribe returned CXSMILES",
        "stats": {"n": n, "exact": s_ex, "strict_pct": pct(s_ex, n)},
        "threshold": round(THRESHOLD * 100),
        "batches": {str(r["batch"]): d["batches"].get(str(r["batch"]), "") for r in runs},
        "runs": [{k2: v for k2, v in r.items() if k2 not in ("keys", "prompt")} for r in runs],
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "headline": ("Sonnet 5.5 reading the same drawings as the Sonnet 5 tab, in the same order, ten per "
                     "Claude usage block. The same agent loop with a Python interpreter and RDKit, spawned on "
                     "the exact model id and scored by the same rule."),
        "footer": (f"n={n} of {corpus_n}, growing by ten per usage block. Corpus order, nothing skipped, so "
                   f"every image pairs with the Sonnet 5 arm's reading of it: on these {P['n']}, Sonnet 5.5 "
                   f"{P['s55']} and Sonnet 5 {P['s5']} exact, 5.5 ahead on {P['ahead']} and behind on "
                   f"{P['behind']} (exact McNemar p={P['p']}). Filenames anonymised; ground truth is PubChem."),
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.1f} KB): {n} rows; Sonnet 5.5 {s_ex}/{n}, "
          f"CXMolScribe {o_ex}/{n}; paired with Sonnet 5 on {P['n']}: 5.5 {P['s55']} vs 5 {P['s5']}, "
          f"ahead {P['ahead']} behind {P['behind']} p={P['p']}; ${cost:.2f} over {imgs} reads")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["record-run"] and len(a) == 3:
        sys.exit(cmd_record_run(a[1], a[2]))
    if a[:1] == ["batch-note"] and len(a) == 3:
        sys.exit(cmd_batch_note(a[1], a[2]))
    if not a:
        rc = build()
        if rc == 0:
            # The tab's "How the readers work" section (wall/technique.json), rebuilt with the tab
            # so it follows the cadence. It must never block the tab: the cadence halts on a
            # non-zero exit here, and a technique chart is not worth a halted benchmark.
            try:
                import build_technique
                build_technique.build()
            except Exception as e:  # noqa: BLE001
                print(f"technique build skipped: {e!r}", file=sys.stderr)
        sys.exit(rc)
    raise SystemExit(__doc__)
