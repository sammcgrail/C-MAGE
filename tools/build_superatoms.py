#!/usr/bin/env python3
"""The "Superatoms" tab: CXMolScribe vs Sonnet 5.5 (API) on the SAME drawings with TEXT SUPERATOMS
(OMe, Boc, CF3, CO2Et, OTBS ...).

  Sonnet 5.5 (API)  one plain Messages API call per image (tools/api_reader_set.py, the published
                    prompt, max_tokens 64,000, streamed, no tools).
  CXMolScribe       C-MAGE's stage-3 recogniser alone (benchmarks/run_stage3_only.sh), on the same
                    image files; its spreadsheets are copied into RUN/cxmolscribe/.

Two kinds of drawing, never pooled:
  built  RDKit-condensed drawings (tools/superatoms/): truth = the original full molecule, exact by
         construction. A corpus molecule's truth is served only once a tool-using lane has read it
         (build_wall.tool_read_keys, keyed on the corpus key).
  real   published drawings from the MolScribe real-image benchmarks (USPTO, CLEF-2012, UOB, ACS)
         that show text superatoms; truth = the benchmark's SMILES. UOB and ACS count in every number
         but are not shown (licence).

Scoring is sonnet_batch.verdict() for both readers. CXMolScribe emits CXSMILES, where a drawn OMe stays
a labelled dummy atom; compared as emitted, every superatom drawing fails by representation alone, so
its number expands the labels first (benchmarks/cxsmiles.expand) with its own table
(molscribe.constants.ABBREVIATIONS) plus the labels these drawings use (sa_abbrev, both orientations);
a label in neither stays unexpanded and scores wrong. The own-table-only rate is in the fold.

    build_superatoms.py      rebuild wall/superatoms.json + tiles
"""
import collections
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_wall  # noqa: E402
from build_wall import WALL, render_pred, thumb, relate  # noqa: E402
_TILE = build_wall.TILE
import build_sonnet55 as B55  # noqa: E402
build_wall.TILE = _TILE
from sonnet_batch import verdict  # noqa: E402
from api_reader import parse_smiles  # noqa: E402
sys.path.insert(0, str(HERE.parent / "benchmarks"))
import cxsmiles  # noqa: E402
sys.path.insert(0, str(HERE / "superatoms"))
import sa_abbrev  # noqa: E402

OWN = dict(cxsmiles.ABBREVIATIONS)


class _Ab:
    def __init__(self, smiles):
        self.smiles = smiles


def _drawn_labels() -> dict:
    """Every label these drawings use (RDKit's defaults + the extensions, both orientations, sub/sup
    tags stripped) -> its group, written with the attachment atom first, the form cxsmiles.expand reads."""
    import re
    from rdkit import Chem
    out = {}
    for d in sa_abbrev.ALL:
        smi = sa_abbrev.DEF_SMILES[d.label]
        # every definition is written "*" + the attachment atom first; drop the "*" and the
        # attachment atom's hydrogens are recomputed after the zip
        assert smi.startswith("*") and smi.count("*") == 1, smi
        frag = smi[1:]
        for lab in {d.label, re.sub(r"<[^>]+>", "", d.displayLabel), re.sub(r"<[^>]+>", "", d.displayLabelW)}:
            if lab and lab not in OWN:
                out[lab] = _Ab(frag)
    return out


FULL = {**_drawn_labels(), **OWN}       # its own entries win where both define a label

RUN = HERE.parent / "benchmarks" / "published_runs" / "sonnet55_api_superatoms"
CX = RUN / "cxmolscribe"
OUT = WALL / "superatoms.json"
DIR = "superatoms"
SON, CXM = "Sonnet 5.5 (API)", "CXMolScribe"
SECTION = {"synth": "Built drawings"}
# Read, but not scored: a drawing whose label is ambiguous by convention, so no answer could be held to it.
EXCLUDE = {"synth": {"sa_0034": "RDKit's default 'NC' abbreviation is an isocyanide; the same two letters are the "
                                 "standard way to write a nitrile pointing left, so the drawing does not determine "
                                 "the molecule"}}


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def final_rows(d: Path) -> dict:
    """key -> (scored record, first record, retries) for every row of a run dir."""
    rets = collections.defaultdict(list)
    for x in load_jsonl(d / "retries.jsonl"):
        rets[x["k"]].append(x)
    out = {}
    for r0 in load_jsonl(d / "ledger.jsonl"):
        if r0["status"] != "ok":
            out[r0["k"]] = (None, r0, [])
            continue
        rr = [x for x in rets.get(r0["k"], []) if x["status"] == "ok"]
        fin = [x for x in rr if x.get("stop_reason") != "max_tokens"]
        out[r0["k"]] = (fin[-1] if fin else rr[-1] if rr else r0, r0, rets.get(r0["k"], []))
    return out


def cx_preds() -> dict:
    """image id -> (CXSMILES or None, confidence) from the stage-3 spreadsheets."""
    import pandas as pd
    out = {}
    for f in ("Completed_HighConfidence_CMAGE.xlsx", "Completed_LowConfidence_CMAGE.xlsx"):
        if not (CX / f).exists():
            continue
        for r in pd.read_excel(CX / f).to_dict("records"):
            k = Path(r["File Path"]).stem
            if k in out:
                raise SystemExit(f"{k} predicted twice by CXMolScribe")
            sm = r["Predicted CXSMILES"]
            c = r["CXSMILES's Confidence Levels"]
            out[k] = (sm if isinstance(sm, str) else None, None if c != c else float(c))
    return out


def _expand(sm, table):
    cxsmiles.ABBREVIATIONS = table
    try:
        return cxsmiles.expand(sm)[0]
    except Exception:
        return None
    finally:
        cxsmiles.ABBREVIATIONS = OWN


def cx_score(sm, truth):
    """(verdict with its own table only, verdict with labels expanded by its own table plus the labels
    these drawings use, expanded SMILES). Both are verdict(); expansion never guesses a label."""
    if not sm:
        return "invalid", "invalid", None
    own, full = _expand(sm, OWN), _expand(sm, FULL)
    return (verdict(own, truth) if own else "invalid"), (verdict(full, truth) if full else "invalid"), full


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def side(rs, key):
    e = sum(1 for r in rs if key(r) == "exact")
    return {"exact": e, "n": len(rs), "pct": pct(e, len(rs))}


def mcnemar(rs, ka, kb):
    a = sum(1 for r in rs if ka(r) == "exact" and kb(r) != "exact")
    b = sum(1 for r in rs if kb(r) == "exact" and ka(r) != "exact")
    return a, b, float(f"{B55.mcnemar_exact(a, b):.3g}")


def build() -> int:
    img, pred, txt, ocr = WALL / DIR, WALL / f"{DIR}_pred", WALL / f"{DIR}_txt", WALL / f"{DIR}_ocr"
    for p in (img, pred, txt, ocr):
        p.mkdir(parents=True, exist_ok=True)
    cxp = cx_preds()
    rows, hidden, failed, excluded, cost = [], [], [], [], 0.0
    for sec in ("synth", "real"):
        d = RUN / sec
        if not (d / "set.json").exists():
            continue
        meta = {x["id"]: x for x in json.load(open(d / "set.json"))}
        cost += sum((x.get("cost_usd") or 0) for x in load_jsonl(d / "ledger.jsonl") + load_jsonl(d / "retries.jsonl"))
        for k, (r, r0, rets) in final_rows(d).items():
            m = meta[k]
            if k in EXCLUDE.get(sec, {}):
                excluded.append(k)
                continue
            if r is None:
                failed.append(k)
                continue
            s = parse_smiles(r.get("text")) or ""
            v = verdict(s, m["truth"])
            cs, cc = cxp.get(k, (None, None))
            craw, cexp, cex = cx_score(cs, m["truth"])
            labs = m.get("labels") or []
            u = r.get("usage") or {}
            row = {"k": k, "sec": sec, "src": "Built" if sec == "synth" else m["src"], "labs": labs,
                   "v": v, "g": v, "c": None, "s": s, "t": m["truth"], "bn": 1,
                   "rc": round(sum((x.get("cost_usd") or 0) for x in [r0] + rets), 4),
                   "rt": round((r0.get("latency_s") or 0) + sum(x.get("latency_s") or 0 for x in rets if x["status"] == "ok"), 1),
                   "cxv": cexp, "cxraw": craw,
                   "ocr": cs or "(no answer)", "ocrv": cexp, "ocrc": None if cc is None else round(cc * 100),
                   "tl": [["Sonnet 5.5", s, v], [CXM, cex or cs or "", cexp]]}
            row["n"] = f"{k} · {m['name']}" if sec == "synth" else f"{k} · {m['src']} {m['orig_id']}"
            row["d"] = SECTION["synth"] if sec == "synth" else f"Real: {m['src']}"
            row["rnote"] = (f"superatoms drawn: {', '.join(labs)} · one API call, no tools · max_tokens "
                            f"{r0.get('max_tokens'):,} · stop_reason {r0.get('stop_reason')} · "
                            f"{u.get('input_tokens', 0):,} in / {u.get('output_tokens', 0):,} out tokens · "
                            f"CXMolScribe on the same image: {cexp} with its labels expanded"
                            + (f" ({cex})" if cex and cex != cs else "") + f"; {craw} with its own abbreviation table only")
            pk = m.get("plain_key")
            if pk:
                row["pk"] = pk
            if not m.get("show", True):
                hidden.append(row)
                continue
            thumb(Path(m["png"]), img / f"{k}.png")
            row["p"] = 1 if render_pred(s, pred / f"{k}.png") else 0
            row["po"] = 1 if render_pred(cex or cs or "", ocr / f"{k}.png") else 0
            row["r"] = relate(s, m["truth"])
            body = r.get("text") or ""
            tf = txt / f"{k}.txt"
            if not tf.exists() or tf.read_text() != body:
                tf.write_text(body)
            row["tx"] = 1
            rows.append(row)

    # Truth gate (build_wall.gate_truth): a CORPUS molecule's reference is served only once a
    # tool-using reader lane has read it; the gate is keyed on the corpus key, not the sa_ id.
    read = build_wall.tool_read_keys()
    gated = [r for r in rows if r.get("pk") and r["pk"] not in read]
    for r in gated:
        r["tw"] = 1
        r["n"] = r["k"]           # the name is a lookup away from the structure: withheld too
        for f in build_wall.TRUTH_FIELDS:
            r.pop(f, None)
    allr = rows + hidden
    syn = [r for r in allr if r["sec"] == "synth"]
    real = [r for r in allr if r["sec"] == "real"]
    S, C = (lambda r: r["v"]), (lambda r: r["cxv"])
    nl = lambda r: len(r["labs"])
    groups = [("Built drawings", syn), ("Real drawings, all sources", real),
              ("Real, 1 superatom label", [r for r in real if nl(r) == 1]),
              ("Real, 2 superatom labels", [r for r in real if nl(r) == 2]),
              ("Real, 3 or more labels", [r for r in real if nl(r) >= 3])]
    c2rows = [{"label": lab, "note": f"n={len(rs)}", "a": side(rs, S), "b": side(rs, C)} for lab, rs in groups if rs]

    fmt = lambda x: f"{x['pct']}% ({x['exact']}/{x['n']})"
    tests = []
    for lab, rs in groups:
        if rs:
            a, b, p = mcnemar(rs, S, C)
            tests.append(f"{lab}: right only for {SON} {a}, only for {CXM} {b}; exact McNemar p={p}")
    own = [f"{lab}: {fmt(side(rs, lambda r: r['cxraw']))}" for lab, rs in groups if rs]
    more = {"h": "Paired test and scoring", "groups": [
        {"h": "Exact McNemar, same images", "rows": tests},
        {"h": f"{CXM} with only its own abbreviation table (labels it lacks, e.g. CO2Me, NHMe, OTBS, stay unexpanded)",
         "rows": own}]}
    docs = []
    for name in [SECTION["synth"]] + sorted({r["d"] for r in rows if r["sec"] == "real"}):
        x = [r for r in rows if r["d"] == name]
        if x:
            docs.append({"name": name, "found": sum(r["v"] == "exact" for r in x), "expected": len(x)})
    cnt = lambda key: sum(1 for r in rows if r["v"] == key)
    shown = collections.Counter(r["d"] for r in rows)
    real_shown = sorted((k[6:], n) for k, n in shown.items() if k.startswith("Real: "))
    out = {
        "arm": "Superatoms", "dir": DIR, "reader": SON, "rows": rows, "tileText": 1,
        "title": f"Superatoms: {CXM} vs {SON}",
        "headline": f"Same images for both. {SON}: one API call per image, no tools.",
        "c2": {"a": SON, "b": CXM, "rows": c2rows}, "more": more,
        "breakdown": [{"key": "matched", "label": f"{SON} exact", "n": cnt("exact")},
                      {"key": "stereo", "label": "Stereo only", "n": cnt("stereo")},
                      {"key": "misread", "label": "Wrong", "n": cnt("wrong")},
                      {"key": "unreadable", "label": "None", "n": cnt("invalid")}],
        "docs": docs, "docsLabel": "section",
        "withheld": {"n": len(gated), "note": build_wall.WITHHELD_NOTE},
        "runNote": f"{SON}, one call, at list price",
        "stats": {"n": len(allr), "built": side(syn, S), "built_cx": side(syn, C), "real": side(real, S),
                  "real_cx": side(real, C), "hidden": len(hidden), "shown": len(rows)},
        "threshold": 101,
        "prompt": (RUN / "prompt_v2.txt").read_text().strip(),
        "method": [{"h": "Scoring", "points": [
            "Both readers scored with the same function: RDKit canonical SMILES against the full molecule.",
            f"{CXM} writes superatoms as CXSMILES labels; each label is expanded before scoring, with its own "
            "abbreviation table plus the labels these drawings use. A label in neither stays unexpanded and scores wrong."]}],
        "footer": (f"{len(rows)} tiles: {shown[SECTION['synth']]} built + {sum(n for _, n in real_shown)} real ("
                   + ", ".join(f"{s} {n}" for s, n in real_shown) + f"). UOB and ACS ({len(hidden)}) count in the "
                   "numbers but aren't shown (licence)."),
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT}: " + "; ".join(f"{x['label']} {x['a']['exact']}/{x['a']['n']} vs {x['b']['exact']}/{x['b']['n']}"
                                       for x in c2rows) + f"; ${cost:.2f}; CX predictions {len(cxp)}")
    for t in tests:
        print("  " + t)
    return 0


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    sys.exit(build())
