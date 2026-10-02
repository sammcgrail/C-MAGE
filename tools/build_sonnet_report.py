#!/usr/bin/env python3
"""The Sonnet 5.5 findings report: one payload, wall/sonnet_report.json, rendered by
webapp/static/sonnet-report.html at /sonnet-report.

    build_sonnet_report.py            rebuild the payload from the live data

Every number on the report page comes from this script, which READS (never writes) the same
files the other pages are built from:

    /root/cmage-work/sonnet-s55c/results.jsonl   Sonnet 5.5 corpus lane (the snapshot row count)
    /root/cmage-work/sonnet/results.jsonl        Sonnet 5 arm, paired by compound key
    wall/sonnet55.json                           the corpus tab payload (runs, cost per reader)
    wall/sonnet_compare.json                     hand-picked 28 and its same-prompt re-run
    wall/sonnet_novel.json                       novel structures, kinds A, B, C
    wall/technique.json                          tool-call classification of every reader
    benchmarks/sonnet_report_fable.json          the one Fable 5.1 reading (cethromycin)

and, if present, the cadence's own state and log (site-specific, outside the fork; the report
just omits the block figures when they are missing).

THE E/Z CLASSIFIER. sonnet_batch.verdict() calls a reading "stereo" when it matches the reference
once ALL stereo is dropped, which also drops isotope labels. That lumps four different things
together. Each "stereo" verdict is split here by which strip makes the two molecules equal:
double-bond geometry only, tetrahedral centres only, isotope labels only, or a mix. Double-bond
cases are then compared bond by bond (atoms mapped by substructure match, which is exact because
the stereo-free graphs are identical): E/Z the reading ADDED where the reference leaves it
unspecified, E/Z it OMITTED where the reference specifies it, and E/Z it FLIPPED. The E/Z-aware
score forgives only the first: a reading that is exact once the bonds the reference leaves
unspecified are ignored.
"""
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "benchmarks"))

from sonnet_batch import verdict  # noqa: E402  (THE scoring rule, one copy)
import reader_protocol  # noqa: E402  (images per reader, and from which row)
from rdkit import Chem, DataStructs, RDLogger  # noqa: E402
from rdkit.Chem import rdFingerprintGenerator  # noqa: E402

RDLogger.DisableLog("rdApp.*")

BENCH = HERE.parent / "benchmarks"
WALL = BENCH / "wall"
OUT = WALL / "sonnet_report.json"
LANE = Path("/root/cmage-work/sonnet-s55c/results.jsonl")
S5 = Path("/root/cmage-work/sonnet/results.jsonl")
CADENCE_STATE = Path("/root/cmage-work/sonnet-s55c/cadence_state.json")
CADENCE_LOG = Path("/root/cmage-work/sonnet-s55c/cadence.log")
FABLE = BENCH / "sonnet_report_fable.json"


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def pct(a, b, nd=1):
    return round(100.0 * a / b, nd) if b else None


def mcnemar(b: int, c: int) -> float:
    from build_sonnet55 import mcnemar_exact
    return float(f"{mcnemar_exact(b, c):.3g}")


# ---------------------------------------------------------------- E/Z classification
_EZ = {Chem.BondStereo.STEREOE: "E", Chem.BondStereo.STEREOZ: "Z",
       Chem.BondStereo.STEREOTRANS: "E", Chem.BondStereo.STEREOCIS: "Z"}


def _strip(m, db=False, tet=False, iso=False) -> str:
    m = Chem.Mol(m)
    if iso:
        for a in m.GetAtoms():
            a.SetIsotope(0)
        m = Chem.RemoveHs(m)   # [2H] is an explicit H atom; zeroing the label alone is not enough
    if tet:
        for a in m.GetAtoms():
            a.SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
    if db:
        for b in m.GetBonds():
            if b.GetBondType() == Chem.BondType.DOUBLE:
                b.SetStereo(Chem.BondStereo.STEREONONE)
            if b.GetBondDir() in (Chem.BondDir.ENDUPRIGHT, Chem.BondDir.ENDDOWNRIGHT):
                b.SetBondDir(Chem.BondDir.NONE)
    return Chem.MolToSmiles(m)


def classify(pred: str, truth: str) -> dict:
    """What a 'stereo' verdict actually differs in. Only meaningful when verdict() said stereo."""
    t, p = Chem.MolFromSmiles(truth), Chem.MolFromSmiles(pred)
    if _strip(t, db=True) == _strip(p, db=True):
        match = p.GetSubstructMatch(t)
        added = omitted = flipped = 0
        for b in t.GetBonds():
            if b.GetBondType() != Chem.BondType.DOUBLE:
                continue
            pb = p.GetBondBetweenAtoms(match[b.GetBeginAtomIdx()], match[b.GetEndAtomIdx()])
            lt, lp = _EZ.get(b.GetStereo()), _EZ.get(pb.GetStereo())
            if lt == lp:
                continue
            if lt is None:
                added += 1
            elif lp is None:
                omitted += 1
            else:
                flipped += 1
        sub = ("added" if added and not omitted and not flipped else
               "omitted" if omitted and not added and not flipped else
               "flipped" if flipped and not added and not omitted else "mixed")
        return {"cls": "ez", "sub": sub, "added": added, "omitted": omitted, "flipped": flipped}
    if _strip(t, tet=True) == _strip(p, tet=True):
        return {"cls": "tet"}
    if _strip(t, iso=True) == _strip(p, iso=True):
        return {"cls": "iso"}
    return {"cls": "mixed"}


def ez_arm(label: str, items: list[tuple]) -> dict:
    """items: (key, name, pred, truth, stored_verdict). Re-derives every verdict with verdict()
    and refuses to go on if the stored one disagrees, so the split is of the SAME verdicts the
    pages show."""
    n = len(items)
    v = Counter()
    split = Counter()
    sub = Counter()
    rows = []
    ok_aware = set()
    ok_agn = set()
    for k, name, pred, truth, stored in items:
        vv = verdict(pred, truth)
        if vv != stored:
            raise SystemExit(f"{label} {k}: stored verdict {stored} but verdict() says {vv}")
        v[vv] += 1
        if vv == "exact":
            ok_aware.add(k)
            ok_agn.add(k)
        if vv != "stereo":
            continue
        c = classify(pred, truth)
        split[c["cls"]] += 1
        if c["cls"] == "ez":
            sub[c["sub"]] += 1
            ok_agn.add(k)
            if c["sub"] == "added":
                ok_aware.add(k)
        rows.append({"k": k, "n": name, **c})
    return {"label": label, "n": n, "verdicts": dict(v), "exact": v["exact"],
            "stereo": v["stereo"], "split": {x: split.get(x, 0) for x in ("ez", "tet", "iso", "mixed")},
            "ez_sub": {x: sub.get(x, 0) for x in ("added", "omitted", "flipped", "mixed")},
            "aware": len(ok_aware), "agnostic": len(ok_agn),
            "aware_pct": pct(len(ok_aware), n), "agnostic_pct": pct(len(ok_agn), n),
            "exact_pct": pct(v["exact"], n), "rows": rows,
            "_ok": {"aware": ok_aware}}


# ---------------------------------------------------------------- sections
def corpus_section(lane, s5, s55json):
    xs = [r for r in lane if r["k"] in s5]
    ok55 = {r["k"] for r in xs if r["sonnet_verdict"] == "exact"}
    ok5 = {r["k"] for r in xs if s5[r["k"]]["sonnet_verdict"] == "exact"}
    okcx = {r["k"] for r in xs if r["ocr_verdict"] == "exact"}
    keys = {r["k"] for r in xs}
    runs = s55json.get("runs", [])
    cost = sum(r["cost_usd"] for r in runs)
    secs = sum(r["duration_s"] for r in runs)
    imgs = sum(r["images"] for r in runs)
    return {
        "n": len(xs), "unpaired": len(lane) - len(xs), "corpus": s55json["compare"]["corpus"],
        "s55": len(ok55), "s5": len(ok5), "cx": len(okcx),
        "s55_pct": pct(len(ok55), len(xs)), "s5_pct": pct(len(ok5), len(xs)), "cx_pct": pct(len(okcx), len(xs)),
        "vs_s5": {"ahead": len(ok55 - ok5), "behind": len(ok5 - ok55), "p": mcnemar(len(ok55 - ok5), len(ok5 - ok55))},
        "vs_cx": {"ahead": len(ok55 - okcx), "behind": len(okcx - ok55), "p": mcnemar(len(ok55 - okcx), len(okcx - ok55))},
        "neither_s55_cx": len(keys - ok55 - okcx), "all_three": len(ok55 & ok5 & okcx),
        "cost": {"usd": round(cost, 2), "images": imgs, "readers": len(runs),
                 "per_image": round(cost / imgs, 3) if imgs else None,
                 "secs_per_image": round(secs / imgs) if imgs else None},
        "first": xs[0]["name"] if xs else None, "last": xs[-1]["name"] if xs else None,
    }


def ez_section(lane, s5):
    xs = [r for r in lane if r["k"] in s5]
    arms = [
        ez_arm("Sonnet 5.5", [(r["k"], r["name"], r["sonnet_smiles"], r["truth"], r["sonnet_verdict"]) for r in xs]),
        ez_arm("Sonnet 5", [(r["k"], r["name"], s5[r["k"]]["sonnet_smiles"], r["truth"],
                             s5[r["k"]]["sonnet_verdict"]) for r in xs]),
        ez_arm("CXMolScribe", [(r["k"], r["name"], r["ocr_smiles"], r["truth"], r["ocr_verdict"]) for r in xs]),
    ]
    a55, a5, acx = (a["_ok"]["aware"] for a in arms)
    for a in arms:
        a.pop("_ok")
    mc = {"vs_s5": {"ahead": len(a55 - a5), "behind": len(a5 - a55), "p": mcnemar(len(a55 - a5), len(a5 - a55))},
          "vs_cx": {"ahead": len(a55 - acx), "behind": len(acx - a55), "p": mcnemar(len(a55 - acx), len(acx - a55))}}
    s55 = arms[0]
    by_k = {r["k"]: r for r in xs}
    for row in s55["rows"]:
        r = by_k[row["k"]]
        row["conf"] = r.get("sonnet_conf")
        row["read_name"] = r.get("sonnet_name")
    # Sanity: the classifier must see a planted tetrahedral flip as NOT E/Z-only.
    ceth = next((r for r in xs if r["k"].startswith("cethromycin")), None)
    teeth = None
    if ceth:
        m = ceth["sonnet_smiles"].replace("CC[C@H]1", "CC[C@@H]1", 1)
        teeth = {"planted_centre_flip_is_ez": classify(m, ceth["truth"])["cls"] == "ez",
                 "cethromycin": classify(ceth["sonnet_smiles"], ceth["truth"])}
        if teeth["planted_centre_flip_is_ez"]:
            raise SystemExit("classifier teeth failed: a flipped tetrahedral centre classed as E/Z-only")
    return {"arms": arms, "mcnemar_aware": mc, "teeth": teeth}


def batching_section(tech, lane, s5):
    rs = tech["readers"]
    out = {}
    for ln in ("s5", "s55c"):
        g = [r for r in rs if r["lane"] == ln]
        for flag in (True, False):
            sel = [r for r in g if r.get("read_all_first") is flag]
            out[f"{ln}_{'first' if flag else 'not'}"] = {
                "readers": len(sel), "images": sum(r["n"] for r in sel), "exact": sum(r["exact"] for r in sel),
                "pct": pct(sum(r["exact"] for r in sel), sum(r["n"] for r in sel))}
    # Alphabetical neighbours: does an image with a close relative in its OWN reader's batch
    # score better? Morgan r2 Tanimoto >= 0.7 between reference structures.
    truth = {r["k"]: r["truth"] for r in lane}
    ok = {"s55c": {r["k"] for r in lane if r["sonnet_verdict"] == "exact"},
          "s5": {k for k, r in s5.items() if r["sonnet_verdict"] == "exact"}}
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fpc = {}

    def fp(k):
        if k not in fpc:
            m = Chem.MolFromSmiles(truth[k])
            fpc[k] = gen.GetFingerprint(m) if m else None
        return fpc[k]

    sib = {}
    batches = {}
    for ln in ("s5", "s55c"):
        bs = [[i[2] for i in r["img"] if i[2] in truth] for r in rs if r["lane"] == ln]
        batches[ln] = [set(b) for b in bs if b]
        has, no = [], []
        for b in bs:
            for k in b:
                best = max([DataStructs.TanimotoSimilarity(fp(k), fp(k2)) for k2 in b
                            if k2 != k and fp(k) and fp(k2)] or [0])
                (has if best >= 0.7 else no).append(k)
        sib[ln] = {"images": len(has) + len(no), "with": len(has),
                   "with_exact": len([k for k in has if k in ok[ln]]),
                   "without_exact": len([k for k in no if k in ok[ln]]), "without": len(no)}
        sib[ln]["with_pct"] = pct(sib[ln]["with_exact"], sib[ln]["with"])
        sib[ln]["without_pct"] = pct(sib[ln]["without_exact"], sib[ln]["without"])
    over = sorted(max(len(b & c) for c in batches["s5"]) for b in batches["s55c"])
    same = sum(1 for b in batches["s55c"] if any(b == c for c in batches["s5"]))
    out["siblings"] = sib
    out["overlap"] = {"s55c_batches": len(over), "identical": same,
                      "median_shared": over[len(over) // 2] if over else None}
    return out


def technique_section(tech):
    L = tech["lanes"]
    keys = ("readers", "images", "exact_pct", "calls_per_image", "crops_img_mean", "read_all_first_pct",
            "secs_per_image", "cost_per_image", "out_tok_per_image", "img_with_crop_pct", "img_drawn_pct")
    lanes = {ln: {k: L[ln].get(k) for k in keys} for ln in ("s5", "s55c")}
    for ln in lanes:
        lanes[ln]["rdkit_readers_pct"] = L[ln]["used_pct"]["rdkit"]
        lanes[ln]["by_size"] = L[ln]["by_size"]
        lanes[ln]["crop_vs_exact"] = next(x for x in L[ln]["vs_exact"] if x["key"] == "crop")
    return {"lanes": lanes, "paired": tech["paired"],
            "speed_ratio": round(L["s5"]["secs_per_image"] / L["s55c"]["secs_per_image"], 1),
            "cost_ratio": round(L["s5"]["cost_per_image"] / L["s55c"]["cost_per_image"], 1),
            "built": tech["built"]}


def cadence_section(s55json, corpus_n, corpus_total):
    runs = sorted(s55json.get("runs", []), key=lambda r: r["finished"])
    if not runs:
        return None
    last = dt.datetime.fromisoformat(runs[-1]["finished"].replace("Z", "+00:00"))
    since = last - dt.timedelta(hours=72)
    recent = [r for r in runs if dt.datetime.fromisoformat(r["finished"].replace("Z", "+00:00")) > since]
    per_day = round(sum(r["images"] for r in recent) / 3.0)
    cost_img = sum(r["cost_usd"] for r in runs) / max(1, sum(r["images"] for r in runs))
    left = corpus_total - corpus_n
    out = {"images_per_day_72h": per_day, "left": left,
           "days_left_at_72h_pace": round(left / per_day, 1) if per_day else None,
           "list_cost_left": round(left * cost_img), "cost_per_image": round(cost_img, 3)}
    if CADENCE_STATE.exists():
        st = json.load(open(CADENCE_STATE))
        forced = set()
        if CADENCE_LOG.exists():
            for line in open(CADENCE_LOG, errors="replace"):
                m = re.search(r'tick RUN: forced \{"mode": "(\w+)", "block": "([^"]+)"', line)
                if m:
                    forced.add(m.group(2))
        normal = [(k, b) for k, b in sorted(st.get("blocks", {}).items())
                  if k >= "2026-09-30T05:00Z" and k not in forced and b.get("batches")]
        if normal:
            sp = sum(b["spent"] for _, b in normal)
            nb = sum(b["batches"] for _, b in normal)
            out["normal_blocks"] = {"blocks": len(normal), "batches": nb, "spent_pct": sp,
                                    "pct_per_batch": round(sp / nb, 1),
                                    "batches_per_block": round(nb / len(normal), 1),
                                    "images_per_block": round(10 * nb / len(normal))}
            ipb = 10 * nb / len(normal)
            out["blocks_left_at_budget"] = round(left / ipb)
            out["days_left_at_budget"] = round(left / ipb / (24 / 5), 1)
        out["forced_blocks"] = sorted(forced)
        out["scan_refused"] = sum(b.get("scan_refused", 0) for b in st.get("blocks", {}).values())
    if CADENCE_LOG.exists():
        kinds = Counter()
        for line in open(CADENCE_LOG, errors="replace"):
            if "DISCARDED" not in line or "scan refused" not in line:
                continue
            if "unvetted-tool Monitor" in line:
                kinds["a Monitor call"] += 1
            elif "unvetted-tool TaskStop" in line:
                kinds["TaskStop on its own task"] += 1
            elif "/tasks/" in line or ".output" in line or "/tmp/claude-0/" in line:
                kinds["reading its own background job's output"] += 1
            else:
                kinds["other"] += 1
        out["discards_after_jail"] = dict(kinds)
    return out


def main() -> int:
    lane = load_jsonl(LANE)
    s5 = {r["k"]: r for r in load_jsonl(S5)}
    s55json = json.load(open(WALL / "sonnet55.json"))
    cmp_ = json.load(open(WALL / "sonnet_compare.json"))
    nov = json.load(open(WALL / "sonnet_novel.json"))
    tech = json.load(open(WALL / "technique.json"))
    fable = json.load(open(FABLE)) if FABLE.exists() else None

    # The cadence appends rows while this runs; pin the snapshot to the rows read above and make
    # every other payload agree with it, or say that it does not.
    corpus = corpus_section(lane, s5, s55json)
    snap = {"rows": len(lane), "last_key": lane[-1]["k"] if lane else None,
            "last_name": lane[-1]["name"] if lane else None,
            "tab_rows": s55json["compare"]["n"], "tab_built": s55json.get("built"),
            "technique_images": tech["lanes"]["s55c"]["images"]}
    s = cmp_["stats"]
    hp = {"n": s["overall"]["n"], "s55": s["overall"]["s55"], "rerun": s["overall"]["base"],
          "published": s["overall"]["published"], "ahead": s["overall"]["ahead"],
          "behind": s["overall"]["behind"], "p": s["overall"]["p"], "groups": s["groups"],
          "noise": s["noise"], "calibration": s["calibration"],
          "summary": cmp_["summary"], "rerun_cost": round(cmp_["side"][0]["cost"], 2),
          "rerun_seconds": cmp_["side"][0]["seconds"]}
    novel = {k: nov[k] for k in ("A", "B", "C", "spend", "cost", "images", "built")}
    payload = {
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot": snap,
        "corpus": corpus,
        "handpicked": hp,
        "novel": novel,
        "ez": ez_section(lane, s5),
        "fable": fable,
        "technique": technique_section(tech),
        "batching": batching_section(tech, lane, s5),
        "cadence": cadence_section(s55json, corpus["n"], corpus["corpus"]),
        "protocol": reader_protocol.summary(len(lane), len(s5)),
    }
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    e = payload["ez"]["arms"]
    print(f"wrote {OUT}: {snap['rows']} rows (tab {snap['tab_rows']}); "
          + "; ".join(f"{a['label']} {a['exact']} -> {a['aware']} E/Z-aware" for a in e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
