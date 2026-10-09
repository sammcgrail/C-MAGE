#!/usr/bin/env python3
"""Build the NOVEL STRUCTURES section of /sonnet-compare: Sonnet 5.5 on molecules it cannot have
memorised (tools/novel_set.py), beside its corpus accuracy and CXMolScribe on the same images.

    build_novel.py record-run <agent-id>     credit a nov-lane reader (ledger benchmarks/novel_runs.json)
    build_novel.py                           rebuild wall/sonnet_novel.json + 480 px tiles

HOW A ROW GETS HERE. SONNET_ARM=nov sonnet_batch.py claim <slot> <keys>, a reader spawned by
spawn_reader.sh claude-sonnet-5-5 on the corpus lane's prompt (reader_prompt_s55c.txt, placeholders
filled), gate_and_score.py (answer-key scan, served model exactly claude-sonnet-5-5, no delegation,
every answer in the transcript) scores it into /root/cmage-work/sonnet-nov/results.jsonl with
sonnet_batch.verdict. This script only READS that, the set, and the s55c corpus results. Its own
payload and tiles, so the corpus lane's builds (build_sonnet55.py / build_sonnet55c.py, run by the
cadence) never touch it and it never touches their counts.

AUTOCORRECTED TO PARENT. For a kind-A row, the answer is scored a second time against the PARENT
drug with the same verdict function. exact-vs-parent means the reader drew the famous molecule it
remembered, not the edit on the page: the memorisation failure this set exists to catch.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "benchmarks"))

import build_wall  # noqa: E402
from build_wall import WALL, render_pred, thumb, relate, tool_read_keys  # noqa: E402
import sonnet_batch as B  # noqa: E402
from build_sonnet55 import run_record, transcript, contains, load_jsonl, num_conf  # noqa: E402
from novel_set import OUT as SET, IMG  # noqa: E402

build_wall.TILE = 480
RESULTS = Path("/root/cmage-work/sonnet-nov/results.jsonl")
CORPUS_RESULTS = Path("/root/cmage-work/sonnet-s55c/results.jsonl")
LEDGER = HERE.parent / "benchmarks" / "novel_runs.json"
OUT = WALL / "sonnet_novel.json"
MODEL = "claude-sonnet-5-5"


def failure(a: dict, truth: str, parent: str) -> str:
    """What a miss was, in words: drew the parent, stereo only, or an atom/connectivity error."""
    from rdkit import Chem
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    if B.verdict(a["s"], parent) == "exact":
        return "autocorrected to the parent"
    if a["v"] == "invalid":
        return "unparseable SMILES"
    if a["v"] == "stereo":
        n = (a.get("r") or {}).get("stereo")
        return "stereo only" + (f": {n[0]} of {n[1]} stereocentres differ" if n else "")
    m, t = Chem.MolFromSmiles(a["s"]), Chem.MolFromSmiles(truth)
    if CalcMolFormula(m) != CalcMolFormula(t):
        d = m.GetNumHeavyAtoms() - t.GetNumHeavyAtoms()
        return f"atoms: formula differs ({d:+d} heavy)" if d else "atoms: wrong elements"
    return "same formula, wrong connectivity"


def ledger() -> dict:
    d = json.load(open(LEDGER)) if LEDGER.exists() else {}
    d.setdefault("runs", {})
    return d


def cmd_record_run(aid: str) -> int:
    d = ledger()
    raw = open(transcript(aid), errors="replace").read()
    mine = [r["k"] for r in load_jsonl(RESULTS) if contains(raw, r.get("sonnet_smiles"))]
    if not mine:
        raise SystemExit(f"no nov-lane row's answer appears in {aid}'s transcript; nothing recorded")
    other = {k: a for a, r in d["runs"].items() if a != aid for k in r["keys"]}
    # A reader of an EDIT may print its PARENT's SMILES while checking (the reader of the edited
    # morphine did), so containment also hits the parent row another reader answered. A row already
    # credited stays with its reader; record the fresh-parent reader first.
    dup = [k for k in mine if k in other]
    if dup:
        print(f"  {aid}: skipping rows already credited to another run: {[(k, other[k]) for k in dup]}")
        mine = [k for k in mine if k not in other]
        if not mine:
            raise SystemExit(f"{aid}: every matching row is credited elsewhere; nothing recorded")
    run = run_record(aid, mine)
    if run["models"] != [MODEL]:
        raise SystemExit(f"{aid} was served by {run['models']}, not {MODEL}")
    d["runs"][aid] = run
    LEDGER.write_text(json.dumps(d, indent=1, sort_keys=True) + "\n")
    print(f"recorded {aid}: {len(mine)} images, ${run['cost_usd']:.2f}, {run['duration_s']} s")
    return 0


def build() -> int:
    S = {r["k"]: r for r in json.load(open(SET))["rows"]}
    lane = {r["k"]: r for r in load_jsonl(RESULTS)}
    if not lane:
        raise SystemExit(f"no rows in {RESULTS}")
    d = ledger()
    run_of = {k: a for a, r in d["runs"].items() for k in r["keys"]}
    unrun = [k for k in lane if k not in run_of]
    if unrun:
        raise SystemExit(f"rows not credited to a recorded run (record-run first): {unrun}")
    corpus = load_jsonl(CORPUS_RESULTS)
    c_by_k = {r["k"]: r for r in corpus}
    dirs = {x: WALL / x for x in ("novel", "novel_pred", "novel_cx")}
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    rows = []
    corpus_rows = {r["k"]: r for r in json.load(open(WALL.parent / "corpus_rows.json"))["rows"]}   # private copy, with references
    fresh = {S[k]["of"]: lane[k] for k in S if S[k]["kind"] == "P" and k in lane}
    # A parent drug's corpus reference is served only once a tool-using reader has read that parent's
    # corpus drawing (a corpus lane, or this lane's fresh P read of the same drawing), the same rule
    # as wall/images.json. Until then the page says it is withheld.
    parent_read_keys = tool_read_keys() | {S[k]["parent_key"] for k in S if S[k]["kind"] == "P" and k in lane}
    for k in sorted(S):
        s = S[k]
        if k not in lane or s["kind"] == "P":
            continue
        r = lane[k]
        if r["truth"] != s["t"]:
            raise SystemExit(f"{k}: lane truth and set truth disagree")
        thumb(IMG / f"{k}.png", dirs["novel"] / f"{k}.png")
        for sub, smi in (("novel_pred", r.get("sonnet_smiles")), ("novel_cx", s.get("s"))):
            (dirs[sub] / f"{k}.png").unlink(missing_ok=True)   # answers can change on a re-read
        run = d["runs"][run_of[k]]
        a55 = {"s": r.get("sonnet_smiles") or "", "v": r["sonnet_verdict"], "conf": r.get("sonnet_conf"),
               "name": r.get("sonnet_name"), "r": relate(r.get("sonnet_smiles") or "", s["t"]),
               "p": 1 if render_pred(r.get("sonnet_smiles"), dirs["novel_pred"] / f"{k}.png") else 0}
        cx = {"s": s.get("s") or "", "v": s.get("v"), "conf": s.get("c"),
              "p": 1 if s.get("s") and render_pred(s["s"], dirs["novel_cx"] / f"{k}.png") else 0}
        row = {"k": k, "kind": s["kind"], "n": s["n"], "t": s["t"], "heavy": s["heavy"],
               "stereocentres": s["stereocentres"], "pubchem": s["pubchem"]["cids"][:3],
               "s55": a55, "cx": cx, "run": run["agent"], "slot": r["slot"]}
        if s["kind"] in ("A", "C"):
            pc = c_by_k.get(s["parent_key"])
            row.update(parent=s["parent"], parent_t=s["parent_t"], edit=s["edit"],
                       auto=B.verdict(r.get("sonnet_smiles"), s["parent_t"]) == "exact",
                       cx_auto=B.verdict(s.get("s"), s["parent_t"]) == "exact",
                       named_parent=s["parent"].lower() in (r.get("sonnet_name") or "").lower(),
                       parent_corpus=pc["sonnet_verdict"] if pc else None)
            if s["parent_key"] not in parent_read_keys:
                row.pop("parent_t", None)
                row["parent_tw"] = 1
        else:
            row["fragments"] = s["fragments"]
        if s["kind"] == "C":
            # The parent's own reading by Sonnet 5.5 on the corpus image: the s55c corpus lane's row
            # when that lane has read it (same prompt file and gate), else this lane's fresh P row.
            fr = fresh.get(s["k"].replace("novel_", ""))
            src = pc if pc else fr
            row["stereo_only_edit"] = s["stereo_only_edit"]
            row["parent_read"] = None if not src else {
                "v": src["sonnet_verdict"], "s": src.get("sonnet_smiles"), "conf": src.get("sonnet_conf"),
                "source": "corpus lane" if pc else "fresh read"}
            row["parent_cx"] = corpus_rows[s["parent_key"]]["v"]
            row["fail"] = failure(row["s55"], s["t"], s["parent_t"]) if row["s55"]["v"] != "exact" else None
        rows.append(row)

    def tally(xs):
        return {"n": len(xs), "s55": sum(x["s55"]["v"] == "exact" for x in xs),
                "cx": sum(x["cx"]["v"] == "exact" for x in xs),
                "stereo": sum(x["s55"]["v"] == "stereo" for x in xs),
                "auto": sum(bool(x.get("auto")) for x in xs),
                "conf_mean": round(sum(num_conf(x["s55"]["conf"]) or 0 for x in xs) / len(xs), 1) if xs else None}
    A = [x for x in rows if x["kind"] == "A"]
    Bk = [x for x in rows if x["kind"] == "B"]
    Ck = [x for x in rows if x["kind"] == "C"]
    withp = [x for x in Ck if x.get("parent_read")]
    ok = lambda v: v == "exact"
    kindc = {**tally(Ck),
             "stereo_agnostic": sum(x["s55"]["v"] in ("exact", "stereo") for x in Ck),
             "cx_stereo_agnostic": sum(x["cx"]["v"] in ("exact", "stereo") for x in Ck),
             "stereo_only_edits": sum(bool(x.get("stereo_only_edit")) for x in Ck),
             "cx_auto": sum(bool(x.get("cx_auto")) for x in Ck),
             "paired": len(withp),
             "parent_s55": sum(ok(x["parent_read"]["v"]) for x in withp),
             "edit_s55": sum(ok(x["s55"]["v"]) for x in withp),
             "parent_cx": sum(ok(x["parent_cx"]) for x in Ck),
             "parent_from_corpus": sum(x["parent_read"]["source"] == "corpus lane" for x in withp),
             "edit_only": [x["n"] for x in withp if ok(x["s55"]["v"]) and not ok(x["parent_read"]["v"])],
             "parent_only": [x["n"] for x in withp if ok(x["parent_read"]["v"]) and not ok(x["s55"]["v"])],
             "fails": [{"k": x["k"], "parent": x["parent"], "edit": x["edit"], "fail": x["fail"],
                        "conf": x["s55"]["conf"]} for x in Ck if x["fail"]]}
    b_, c_ = len(kindc["edit_only"]), len(kindc["parent_only"])
    from build_sonnet55 import mcnemar_exact
    kindc["p"] = float(f"{mcnemar_exact(b_, c_):.3g}")
    runs = sorted(d["runs"].values(), key=lambda x: x["started"])
    # Cost per set, so the kind A/B note is not inflated by the hard set's readers (a hard image
    # costs ~5x an easy one) and "readers of N images each" stays a whole number per set.
    kind_of = {k: s["kind"] for k, s in S.items()}

    def spend(kinds):
        rs = [r for r in runs if all(kind_of.get(k) in kinds for k in r["keys"])]
        return {"cost": round(sum(r["cost_usd"] for r in rs), 2), "seconds": sum(r["duration_s"] for r in rs),
                "images": sum(r["images"] for r in rs), "readers": len(rs),
                "sizes": sorted({r["images"] for r in rs})}
    right = [c for c in (num_conf(x["s55"]["conf"]) for x in Ck if ok(x["s55"]["v"])) if c is not None]
    wrong = [c for c in (num_conf(x["s55"]["conf"]) for x in Ck if not ok(x["s55"]["v"])) if c is not None]
    kindc.update(conf_right=round(sum(right) / len(right), 1) if right else None,
                 conf_wrong=round(sum(wrong) / len(wrong), 1) if wrong else None,
                 conf_wrong_max=max(wrong) if wrong else None,
                 cx_conf_mean=round(sum(x["cx"]["conf"] or 0 for x in Ck) / len(Ck), 1) if Ck else None)
    parents = [x for x in A if x.get("parent_corpus")]
    out = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "A": tally(A), "B": tally(Bk), "C": kindc, "all": tally(A + Bk),
        "corpus": {"n": len(corpus), "s55": sum(r["sonnet_verdict"] == "exact" for r in corpus),
                   "cx": sum(r.get("ocr_verdict") == "exact" for r in corpus)},
        "parents": {"n": len(parents), "s55": sum(x["parent_corpus"] == "exact" for x in parents)},
        "named_parent": sum(bool(x.get("named_parent")) for x in A),
        "cost": round(sum(r["cost_usd"] for r in runs), 2),
        "seconds": sum(r["duration_s"] for r in runs),
        "images": sum(r["images"] for r in runs),
        "spend": {"AB": spend("AB"), "C": spend("C"), "P": spend("P")},
        "runs": [{k2: v for k2, v in r.items() if k2 not in ("keys", "prompt")} for r in runs],
        "prompt": runs[-1]["prompt"] if runs else "",
        "rows": rows,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size/1e3:.1f} KB): kind A 5.5 {out['A']['s55']}/{out['A']['n']} "
          f"(autocorrected {out['A']['auto']}), kind B 5.5 {out['B']['s55']}/{out['B']['n']}; "
          f"CX A {out['A']['cx']}/{out['A']['n']} B {out['B']['cx']}/{out['B']['n']}; "
          f"kind C 5.5 {kindc['s55']}/{kindc['n']} (auto {kindc['auto']}, stereo-agnostic {kindc['stereo_agnostic']}), "
          f"CX {kindc['cx']}/{kindc['n']}; parents 5.5 {kindc['parent_s55']}/{kindc['paired']} vs edits {kindc['edit_s55']}/{kindc['paired']}; "
          f"corpus 5.5 {out['corpus']['s55']}/{out['corpus']['n']}; ${out['cost']}, {out['seconds']} s")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["record-run"] and len(a) == 2:
        sys.exit(cmd_record_run(a[1]))
    if not a:
        sys.exit(build())
    raise SystemExit(__doc__)
