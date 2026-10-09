#!/usr/bin/env python3
"""The "Superatoms" tab: CXMolScribe vs Sonnet 5.5 (API) on the SAME drawings with TEXT SUPERATOMS
(OMe, Boc, CF3, CO2Et, OTBS ...).

  Sonnet 5.5 (API)  one plain Messages API call per image (tools/api_reader_set.py, the published
                    prompt, max_tokens 64,000, streamed, no tools).
  CXMolScribe       C-MAGE's stage-3 recogniser alone (benchmarks/run_stage3_only.sh), on the same
                    image files; its spreadsheets are copied into RUN/cxmolscribe/.

Two kinds of drawing, never pooled:
  built  RDKit-condensed drawings (tools/superatoms/): truth = the original full molecule, exact by
         construction. Every reference is served (the reader transcript screen is the protection).
  real   published drawings from the MolScribe real-image benchmarks (USPTO, CLEF-2012, UOB, ACS)
         that show text superatoms; truth = the benchmark's SMILES. UOB and ACS are licence-restricted:
         neither shown nor counted.

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
SECTION = {"synth": "Built drawings", "big": "Real, big (≥50 atoms)"}
# MolScribe TRAINING-set images (src "USPTO-train", the big set's PROTACs and peptides): CXMolScribe has
# probably seen them, so its numbers on them are reported only inside their own section, flagged, and
# never pooled into a CXMolScribe total (agreed with Sam, 9 Oct).
TRAIN_SRC = {"USPTO-train"}
TRAIN_NOTE = "CXMolScribe was trained on these images"
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


# The tool-using lanes that may read superatom drawings (a backfill job keys them by the superatom id,
# sa_NNNN / rs_*, with an explicit "arm": "s5" or "s55"). A lane's default arm covers rows without one.
SA_LANES = {"/root/cmage-work/sonnet/results.jsonl": "s5", "/root/cmage-work/sonnet-s55c/results.jsonl": "s55"}
SA_LANE_GLOB = "/root/cmage-work/sonnet-*sa*/results.jsonl"
ARM_OF = {"s5": "s5", "": "s5", "s55": "s55", "s55c": "s55"}


def is_sa(k: str) -> bool:
    return k.startswith("sa_") or k.startswith("rs_")


def sa_tool_reads() -> dict:
    """arm ("s5" | "s55") -> superatom key -> that lane's row. Tolerant of a half-written last line."""
    import glob
    out = {"s5": {}, "s55": {}}
    for p in list(SA_LANES) + sorted(glob.glob(SA_LANE_GLOB)):
        if not Path(p).exists():
            continue
        for line in open(p):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not is_sa(r.get("k", "")):
                continue
            arm = ARM_OF.get(r.get("arm") or "", None) if r.get("arm") else SA_LANES.get(p)
            if arm in out:
                out[arm][r["k"]] = r
    return out


def sections() -> list:
    """Every run dir with a set.json: the built set first, then the real sets, then anything added later."""
    ds = [d for d in RUN.iterdir() if (d / "set.json").exists()]
    return sorted(ds, key=lambda d: (d.name != "synth", d.name))


def scored_rows():
    """Every superatom drawing that was read, scored by both readers. Returns (rows, excluded, failed,
    read_n, cost). Each row carries `show` (False for a licence-restricted source); the caller decides
    what to do with those. Shared by this tab and the LLM vs OCR tab (build_llmocr)."""
    cxp = cx_preds()
    rows, failed, excluded, read_n, cost, pending = [], [], [], {}, 0.0, []
    for d in sections():
        sec = d.name
        meta = {x["id"]: x for x in json.load(open(d / "set.json"))}
        cost += sum((x.get("cost_usd") or 0) for x in load_jsonl(d / "ledger.jsonl") + load_jsonl(d / "retries.jsonl"))
        fr = final_rows(d)
        read_n[sec] = len(fr)
        for k, (r, r0, rets) in fr.items():
            m = meta[k]
            if k in EXCLUDE.get(sec, {}):
                excluded.append(k)
                continue
            if r is None:
                failed.append(k)
                continue
            if k not in cxp:          # read by the API, not yet by CXMolScribe: not a pair yet, so not shown
                pending.append(k)
                continue
            s = parse_smiles(r.get("text")) or ""
            cs, cc = cxp.get(k, (None, None))
            craw, cexp, cex = cx_score(cs, m["truth"])
            u = r.get("usage") or {}
            think = (u.get("output_tokens_details") or {}).get("thinking_tokens")
            rows.append({
                "k": k, "sec": sec, "built": sec == "synth", "big": sec == "big",
                "trained": m.get("src") in TRAIN_SRC, "cls": m.get("cls"), "src": "Built" if sec == "synth" else m["src"],
                "labs": m.get("labels") or [], "truth": m["truth"], "png": m["png"], "show": m.get("show", True),
                "name": m["name"] if sec == "synth" else f"{m['src']} {m['orig_id']}", "pk": m.get("plain_key"),
                "s": s, "v": verdict(s, m["truth"]), "text": r.get("text") or "",
                "rc": round(sum((x.get("cost_usd") or 0) for x in [r0] + rets), 4),
                "rt": round((r0.get("latency_s") or 0) + sum(x.get("latency_s") or 0 for x in rets if x["status"] == "ok"), 1),
                "mt": r0.get("max_tokens"), "stop": r.get("stop_reason"), "stop0": r0.get("stop_reason"),
                "retried": r is not r0, "itok": u.get("input_tokens", 0), "otok": u.get("output_tokens", 0),
                "ttok": think, "cx_raw_smiles": cs, "cx": cex or cs or "", "cxv": cexp, "cxraw": craw,
                "cxc": None if cc is None else round(cc * 100)})
    scored_rows.pending = pending
    return rows, excluded, failed, read_n, cost


def truth_visible(row: dict, reads: dict, corpus_read: set) -> bool:
    """Retired 9 Oct (Sam): every reference is served; the reader transcript screen
    (scan_reader_transcript.ANSWER_PATH) is the protection. Always True."""
    return True
    """A superatom drawing's reference is served once BOTH tool lanes have read that image, or when it is
    a corpus molecule a tool lane has already read (its reference is public on the corpus tabs)."""
    return (row["k"] in reads["s5"] and row["k"] in reads["s55"]) or bool(row.get("pk") and row["pk"] in corpus_read)


def build() -> int:
    """Serialised with the other wall builders (build_superatoms / build_llmocr): the cadence and the
    superatom step can both rebuild, and two runs would race on the same .json.tmp."""
    import fcntl
    with open("/tmp/cmage-wall-build.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        return _build()


def _build() -> int:
    img, pred, txt, ocr = WALL / DIR, WALL / f"{DIR}_pred", WALL / f"{DIR}_txt", WALL / f"{DIR}_ocr"
    for p in (img, pred, txt, ocr):
        p.mkdir(parents=True, exist_ok=True)
    allrows, excluded, failed, read_n, cost = scored_rows()
    # Only what can be shown is counted: a licence-restricted drawing, an excluded one or a failed call
    # is in no number on the tab (Sam, 9 Oct: "the totals equal what is shown").
    hidden = [r for r in allrows if not r["show"]]
    reads = sa_tool_reads()
    corpus_read = build_wall.tool_read_keys()
    rows = []
    for x in allrows:
        if not x["show"]:
            continue
        k, s, labs = x["k"], x["s"], x["labs"]
        row = {"k": k, "sec": x["sec"], "src": x["src"], "labs": labs, "v": x["v"], "g": x["v"], "c": None,
               "s": s, "t": x["truth"], "bn": 1, "rc": x["rc"], "rt": x["rt"], "cxv": x["cxv"], "cxraw": x["cxraw"],
               "ocr": x["cx_raw_smiles"] or "(no answer)", "ocrv": x["cxv"], "ocrc": x["cxc"],
               "tl": [["Sonnet 5.5", s, x["v"]], [CXM, x["cx"], x["cxv"]]]}
        row["n"] = f"{k} · {x['name']}"
        row["d"] = SECTION["synth"] if x["built"] else SECTION["big"] if x["big"] else f"Real: {x['src']}"
        if x["trained"]:
            row["trained"] = 1
        if x.get("cls"):
            row["cls"] = x["cls"]
        row["rnote"] = (f"superatoms drawn: {', '.join(labs)} · one API call, no tools · max_tokens "
                        f"{(x['mt'] or 0):,} · stop_reason {x['stop0']} · "
                        f"{x['itok']:,} in / {x['otok']:,} out tokens · "
                        f"CXMolScribe on the same image: {x['cxv']} with its labels expanded"
                        + (f" ({x['cx']})" if x["cx"] and x["cx"] != x["cx_raw_smiles"] else "")
                        + f"; {x['cxraw']} with its own abbreviation table only")
        if x.get("pk"):
            row["pk"] = x["pk"]
        thumb(Path(x["png"]), img / f"{k}.png")
        row["p"] = 1 if render_pred(s, pred / f"{k}.png") else 0
        row["po"] = 1 if render_pred(x["cx"], ocr / f"{k}.png") else 0
        row["r"] = relate(s, x["truth"])
        tf = txt / f"{k}.txt"
        if not tf.exists() or tf.read_text() != x["text"]:
            tf.write_text(x["text"])
        row["tx"] = 1
        if not truth_visible(x, reads, corpus_read):
            row["tw"] = 1
            if x.get("pk"):
                row["n"] = k      # a corpus molecule's name is a lookup away from its structure
            for f in build_wall.TRUTH_FIELDS:
                row.pop(f, None)
        rows.append(row)
    gated = [r for r in rows if r.get("tw")]

    syn = [r for r in rows if r["sec"] == "synth"]
    real = [r for r in rows if r["sec"] not in ("synth", "big")]
    big = [r for r in rows if r["sec"] == "big"]
    big_held = [r for r in big if not r.get("trained")]
    big_train = [r for r in big if r.get("trained")]
    S, C = (lambda r: r["v"]), (lambda r: r["cxv"])
    nl = lambda r: len(r["labs"])
    real_names = " + ".join(sorted({r["src"] for r in real}))
    groups = [("Built drawings", syn), (f"Real drawings ({real_names})", real),
              ("Real, 1 superatom label", [r for r in real if nl(r) == 1]),
              ("Real, 2 superatom labels", [r for r in real if nl(r) == 2]),
              ("Real, 3 or more labels", [r for r in real if nl(r) >= 3]),
              # Held-out = every big row CXMolScribe cannot have trained on: MolScribe's USPTO test images
              # and post-2016 USPTO grants (src USPTO-ODP). Only USPTO-train carries the caveat.
              (SECTION["big"] + ", held-out", big_held)]
    odp = [r for r in big_held if r["src"] == "USPTO-ODP"]
    for cls, lab in (("protac", "PROTACs"), ("peptide", "peptides"), ("macrocycle", "macrocycles")):
        groups.append((f"{SECTION['big']}, {lab} (USPTO 2017+)", [r for r in odp if r.get("cls") == cls]))
    groups.append((SECTION["big"] + ", USPTO training set", big_train))
    c2rows = [{"label": lab, "note": f"n={len(rs)}" + (f" · {TRAIN_NOTE}" if rs is big_train else ""),
               "a": side(rs, S), "b": side(rs, C)} for lab, rs in groups if rs]
    # Headline totals: every shown image for the API arm; for CXMolScribe, every image except the ones
    # it was trained on.
    cx_rows = [r for r in rows if not r.get("trained")]
    c2_total = {"a": side(rows, S), "b": side(cx_rows, C), "b_note": (f"excludes {len(big_train)} images it was trained on"
                                                                    if big_train else None)}

    fmt = lambda x: f"{x['pct']}% ({x['exact']}/{x['n']})"
    tests = []
    for lab, rs in groups:
        if rs:
            a, b, p = mcnemar(rs, S, C)
            tests.append(f"{lab}: right only for {SON} {a}, only for {CXM} {b}; exact McNemar p={p}")
    own = [f"{lab}: {fmt(side(rs, lambda r: r['cxraw']))}" for lab, rs in groups if rs]
    srcs = collections.Counter(r["src"] for r in hidden)
    not_counted = ([f"{n} real drawings from {s_} (licence)" for s_, n in sorted(srcs.items())]
                   + ([f"{len(excluded)} built drawing{'s' if len(excluded) != 1 else ''} whose label is ambiguous"]
                      if excluded else [])
                   + ([f"{len(failed)} failed call{'s' if len(failed) != 1 else ''}"] if failed else []))
    more = {"h": "Paired test and scoring", "groups": [
        {"h": "Exact McNemar, same images", "rows": tests},
        {"h": f"{CXM} with only its own abbreviation table (labels it lacks, e.g. CO2Me, NHMe, OTBS, stay unexpanded)",
         "rows": own}] + ([{"h": "Read but not shown or counted", "rows": not_counted}] if not_counted else [])}
    docs = []
    for name in [SECTION["synth"]] + sorted({r["d"] for r in rows if r["sec"] != "synth"}, key=lambda n: (n == SECTION["big"], n)):
        x = [r for r in rows if r["d"] == name]
        if x:
            docs.append({"name": name, "found": sum(r["v"] == "exact" for r in x), "expected": len(x)})
    cnt = lambda key: sum(1 for r in rows if r["v"] == key)
    real_src = sorted(collections.Counter(r["src"] for r in real).items())
    count_line = (f"{len(rows)} images: {len(syn)} built + {len(real)} real ("
                  + ", ".join(f"{s_} {n}" for s_, n in real_src) + ")"
                  + (f" + {len(big)} big, ≥50 atoms ("
                     + ", ".join(f"{s_} {n}" for s_, n in sorted(collections.Counter(r["src"] for r in big).items()))
                     + (f"; {len(big_train)} from MolScribe's training set" if big_train else "") + ")" if big else "")
                  + ".")
    assert len(rows) == len(syn) + len(real) + len(big) == sum(x["a"]["n"] for x in c2rows[:2]) + len(big)
    assert len(big) == len(big_held) + len(big_train)
    out = {
        "arm": "Superatoms", "countLine": count_line, "dir": DIR, "reader": SON, "rows": rows, "tileText": 1,
        "title": f"Superatoms: {CXM} vs {SON}",
        "headline": (f"Same images for both. {SON}: one API call per image, no tools. Exact = the reference molecule "
                     "after RDKit canonicalisation, stereo included. Tiles: ✓ exact, ≈ stereo only, ✗ wrong, – no answer."),
        "c2": {"a": SON, "b": CXM, "as": "5.5 API", "bs": "CXMolScribe", "rows": c2rows, "total": c2_total}, "more": more,
        "breakdown": [{"key": "matched", "label": f"{SON} exact", "n": cnt("exact")},
                      {"key": "stereo", "label": "Stereo only", "n": cnt("stereo")},
                      {"key": "misread", "label": "Wrong", "n": cnt("wrong")},
                      {"key": "unreadable", "label": "None", "n": cnt("invalid")}],
        "docs": docs, "docsLabel": "section",
        "runNote": f"{SON}, one call, at list price",
        "stats": {"n": len(rows), "built": side(syn, S), "built_cx": side(syn, C), "real": side(real, S),
                  "real_cx": side(real, C), "shown": len(rows)},
        "threshold": 101,
        "prompt": (RUN / "prompt_v2.txt").read_text().strip(),
        "method": [{"h": "Scoring", "points": [
            "Both readers scored with the same function: RDKit canonical SMILES against the full molecule.",
            f"{CXM} writes superatoms as CXSMILES labels; each label is expanded before scoring, with its own "
            "abbreviation table plus the labels these drawings use. A label in neither stays unexpanded and scores wrong."]}],
        "footer": count_line,
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT}: {count_line} " + "; ".join(f"{x['label']} {x['a']['exact']}/{x['a']['n']} vs {x['b']['exact']}/{x['b']['n']}"
                                                   for x in c2rows) + f"; ${cost:.2f}; withheld {len(gated)}; not counted: {not_counted}")
    for t in tests:
        print("  " + t)
    return 0


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    sys.exit(build())
