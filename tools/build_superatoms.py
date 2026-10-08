#!/usr/bin/env python3
"""The "Superatoms (API)" tab: Sonnet 5.5 reading drawings with TEXT SUPERATOMS (OMe, Boc, CF3,
CO2Et, OTBS ...), one plain Messages API call per image (tools/api_reader_set.py, prompt v2,
max_tokens 64,000, streamed), in two sections reported apart:

  synthetic  RDKit-condensed drawings (CondenseMolAbbreviations, extended set) at the corpus
             renderer's settings; truth = the original full molecule, exact by construction.
             Corpus molecules among them are paired with the same molecule's PLAIN corpus drawing
             as read by the "Sonnet 5.5 API only" arm.
  real       published drawings from the MolScribe real-image benchmarks (USPTO, CLEF-2012, UOB,
             ACS) that show text superatoms; truth = the benchmark's SMILES. Sets whose licence does
             not allow republishing contribute metrics only, no tiles.

    build_superatoms.py      rebuild wall/superatoms.json + tiles

Every answer is scored with sonnet_batch.verdict(). A max_tokens reading is scored on its last
retry that finished, as on the API-only tab."""
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

RUN = HERE.parent / "benchmarks" / "published_runs" / "sonnet55_api_superatoms"
PLAIN = HERE.parent / "benchmarks" / "published_runs" / "sonnet55_api"
OUT = WALL / "superatoms.json"
DIR = "superatoms"
SECTION = {"synth": "Synthetic: RDKit-condensed", "real": "Real drawings"}
# Read, but not scored: a drawing whose label is ambiguous by convention, so no answer could be held to it.
EXCLUDE = {"synth": {"sa_0034": "RDKit's default 'NC' abbreviation is an ISOCYANIDE ([N+]#[C-]); the same two letters "
                                 "are the standard way to write a NITRILE pointing left, so the drawing does not "
                                 "determine the molecule (tosylmethyl isocyanide; read as the nitrile)"}}
KIND = {  # superatom label -> family, for the per-kind split
    **{k: "Protecting group (Boc, Cbz, Fmoc, Bn, Bz, PMB)" for k in
       ("Boc", "Cbz", "Fmoc", "Bn", "OBn", "Bz", "OBz", "OPMB", "CO2Bn", "CO2tBu")},
    **{k: "Silyl (TMS, TBS, TIPS, TBDPS)" for k in ("TMS", "OTMS", "TBS", "OTBS", "TIPS", "OTIPS", "TBDPS", "OTBDPS")},
    **{k: "Sulfonyl (Ts, Ms, Tf, SO2Me, SO3H)" for k in ("Ts", "OTs", "Ms", "OMs", "Tf", "OTf", "SO2Me", "SO3H")},
    **{k: "Acyl (Ac, OAc, NHAc, CHO)" for k in ("Ac", "OAc", "NHAc", "CHO")},
    **{k: "Ester or acid (CO2H, CO2Me, CO2Et, CO2-)" for k in ("CO2H", "COOH", "CO2Me", "CO2Et", "COOEt", "CO2-", "COO-")},
    **{k: "Alkyl (Et, iPr, tBu, nBu ...)" for k in ("Et", "nPr", "iPr", "nBu", "iBu", "sBu", "tBu", "nPent", "iPent",
                                                   "nHex", "nHept", "nOct", "nNon", "nDec")},
    **{k: "Ph" for k in ("Ph",)},
    **{k: "N, O, S groups (OMe, NMe2, NHMe, SMe, OEt, NEt2)" for k in
       ("OMe", "OEt", "OiBu", "NMe2", "NEt2", "NHMe", "SMe", "N(OH)CH3")},
    **{k: "CF3, OCF3, CCl3" for k in ("CF3", "OCF3", "CCl3")},
    **{k: "NO2, CN, NO, NC" for k in ("NO2", "CN", "NO", "NC")},
}


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def final_rows(d: Path) -> dict:
    """key -> (scored record, first record, all retries) for every ok row of a run dir."""
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


def pct(a, b):
    return round(a / b * 100, 1) if b else 0.0


def bar(label, rs, extra=""):
    e = sum(r["v"] == "exact" for r in rs)
    st = sum(r["v"] == "stereo" for r in rs)
    return {"label": label, "n": len(rs), "pct": pct(e, len(rs)),
            "text": f"{e} of {len(rs)}" + (f" ({e + st} ignoring stereo)" if st else "") + extra}


def build() -> int:
    img, pred, txt = WALL / DIR, WALL / f"{DIR}_pred", WALL / f"{DIR}_txt"
    for p in (img, pred, txt):
        p.mkdir(parents=True, exist_ok=True)
    plain = final_rows(PLAIN)
    rows, hidden, failed, excluded, cost = [], [], [], [], 0.0
    for sec in ("synth", "real"):
        d = RUN / sec
        if not (d / "set.json").exists():
            continue
        meta = {x["id"]: x for x in json.load(open(d / "set.json"))}
        led = final_rows(d)
        cost += sum((x.get("cost_usd") or 0) for x in load_jsonl(d / "ledger.jsonl") + load_jsonl(d / "retries.jsonl"))
        for k, (r, r0, rets) in led.items():
            m = meta[k]
            if k in EXCLUDE.get(sec, {}):
                excluded.append(f"{k} ({EXCLUDE[sec][k]})")
                continue
            if r is None:
                failed.append(k)
                continue
            s = parse_smiles(r.get("text")) or ""
            v = verdict(s, m["truth"])
            labs = m.get("labels") or []
            src = "Synthetic" if sec == "synth" else m["src"]
            u = r.get("usage") or {}
            row = {"k": k, "sec": sec, "src": src, "labs": labs, "v": v, "g": v, "c": None, "s": s, "t": m["truth"],
                   "rc": round(sum((x.get("cost_usd") or 0) for x in [r0] + rets), 4),
                   "rt": round((r0.get("latency_s") or 0) + sum(x.get("latency_s") or 0 for x in rets if x["status"] == "ok"), 1),
                   "bn": 1, "ha": m.get("heavy"), "stop0": r0.get("stop_reason"), "stop": r.get("stop_reason")}
            if sec == "synth":
                row["n"] = f"{k} · {m['name']}"
                row["d"] = SECTION["synth"]
            else:
                row["n"] = f"{k} · {m['src']} {m['orig_id']}"
                row["d"] = f"Real: {m['src']}"
            row["rnote"] = (f"superatoms drawn: {', '.join(labs) or 'none listed'} · no tools · max_tokens "
                            f"{r0.get('max_tokens'):,} · stop_reason {row['stop0']}"
                            + (f" · then {' + '.join(x['kind'] for x in rets)} retry, stop_reason {row['stop']}" if rets else "")
                            + f" · {u.get('input_tokens', 0):,} in / {u.get('output_tokens', 0):,} out tokens")
            if rets:
                row["rf"] = "retried (" + ", ".join(dict.fromkeys(x["kind"] for x in rets)) + ")"
            pk = m.get("plain_key")
            if pk and pk in plain and plain[pk][0] is not None:
                pr = plain[pk][0]
                ps = parse_smiles(pr.get("text")) or ""
                if pr["truth"] != m["truth"]:
                    raise SystemExit(f"{k}: plain ledger truth differs for {pk}")
                row["alt"] = {"s": ps, "v": verdict(ps, pr["truth"]), "conf": None, "pv": pr.get("prompt", "v1")}
            if not m.get("show", True):
                hidden.append(row)
                continue
            src_png = Path(m["png"])
            thumb(src_png, img / f"{k}.png")
            row["p"] = 1 if render_pred(s, pred / f"{k}.png") else 0
            row["r"] = relate(s, m["truth"])
            body = r.get("text") or ""
            tf = txt / f"{k}.txt"
            if not tf.exists() or tf.read_text() != body:
                tf.write_text(body)
            row["tx"] = 1
            rows.append(row)
    allr = rows + hidden
    syn = [r for r in allr if r["sec"] == "synth"]
    real = [r for r in allr if r["sec"] == "real"]
    cnt = lambda rs, key: sum(1 for r in rs if r["v"] == key)

    # paired: the same molecule, plain corpus drawing vs superatom drawing (both API, no tools)
    xs = [r for r in syn if "alt" in r]
    vs = None
    if xs:
        a_ok = lambda r: r["v"] == "exact"
        b_ok = lambda r: r["alt"]["v"] == "exact"
        ahead = sum(1 for r in xs if a_ok(r) and not b_ok(r))
        behind = sum(1 for r in xs if b_ok(r) and not a_ok(r))
        sa, pl = sum(map(a_ok, xs)), sum(map(b_ok, xs))
        pvs = collections.Counter(r["alt"]["pv"] for r in xs)
        vs = {"n": len(xs), "api": sa, "reader": pl, "ahead": ahead, "behind": behind,
              "p": float(f"{B55.mcnemar_exact(ahead, behind):.3g}"),
              "lost": [r["n"] for r in xs if b_ok(r) and not a_ok(r)],
              "gained": [r["n"] for r in xs if a_ok(r) and not b_ok(r)],
              "sides": [{"label": "Superatom drawing", "exact": sa, "n": len(xs), "pct": pct(sa, len(xs))},
                        {"label": "Plain drawing", "exact": pl, "n": len(xs), "pct": pct(pl, len(xs))}]}
        vs["text"] = (f"The same {len(xs)} corpus molecules, drawn twice and read by the same API call: exact only with "
                      f"superatoms {ahead}, exact only drawn plain {behind} (exact McNemar p={vs['p']}). The plain "
                      f"readings come from the Sonnet 5.5 API only tab ("
                      + ", ".join(f"prompt {k}: {n}" for k, n in sorted(pvs.items())) + ").")

    def by_label(rs):
        c = collections.defaultdict(list)
        for r in rs:
            for l in set(r["labs"]):
                c[l].append(r)
        return [bar(l, x) for l, x in sorted(c.items(), key=lambda t: (-len(t[1]), t[0])) if len(x) >= 5]

    def by_kind(rs):
        c = collections.defaultdict(list)
        for r in rs:
            for kd in {KIND.get(l, "Other") for l in r["labs"]}:
                c[kd].append(r)
        return [bar(kd, x) for kd, x in sorted(c.items(), key=lambda t: (-len(t[1]), t[0]))]

    def by_count(rs):
        out = []
        for lo, hi, lab in ((1, 1, "1 superatom"), (2, 2, "2 superatoms"), (3, 3, "3 superatoms"), (4, 99, "4 or more")):
            x = [r for r in rs if lo <= len(r["labs"]) <= hi]
            if x:
                out.append(bar(lab, x))
        return out

    splits = []
    if syn:
        splits += [{"h": "Synthetic: exact by superatom family (a molecule counts in every family it shows)", "rows": by_kind(syn)},
                   {"h": "Synthetic: exact by number of superatoms drawn", "rows": by_count(syn)},
                   {"h": "Synthetic: exact by superatom label (labels on 5 or more molecules)", "rows": by_label(syn)}]
    if real:
        srcs = collections.defaultdict(list)
        for r in real:
            srcs[r["src"]].append(r)
        splits += [{"h": "Real drawings: exact by source", "rows": [
                        bar(s, x, "" if any(y in rows for y in x) else " · metrics only (licence)")
                        for s, x in sorted(srcs.items())]},
                   {"h": "Real drawings: exact by number of superatoms (as screened)", "rows": by_count(real)},
                   {"h": "Real drawings: exact by superatom label (labels on 5 or more drawings)", "rows": by_label(real)}]
    ex_s, ex_r = cnt(syn, "exact"), cnt(real, "exact")
    cards = [{"label": "Synthetic exact", "value": f"{pct(ex_s, len(syn))}%", "sub": f"{ex_s} of {len(syn)}"}]
    if real:
        cards.append({"label": "Real exact", "value": f"{pct(ex_r, len(real))}%", "sub": f"{ex_r} of {len(real)}"})
    if vs:
        cards.append({"label": "Paired, drawn plain", "value": f"{vs['sides'][1]['pct']}%",
                      "sub": f"{vs['reader']} of {vs['n']}; {vs['api']} with superatoms"})
    cards.append({"label": "Total cost", "value": f"${cost:.2f}", "sub": f"${cost / max(1, len(allr)):.3f} per image"})
    lat = [r["rt"] for r in allr] or [0]
    cards.append({"label": "Avg latency", "value": f"{sum(lat) / len(lat):.1f} s", "sub": f"max {max(lat):.0f} s"})
    docs = []
    for name in [SECTION["synth"]] + sorted({r["d"] for r in rows if r["sec"] == "real"}):
        x = [r for r in rows if r["d"] == name]
        if x:
            docs.append({"name": name, "found": cnt(x, "exact"), "expected": len(x)})
    breakdown = [{"key": "matched", "label": "Exact", "n": cnt(allr, "exact")},
                 {"key": "stereo", "label": "Stereo only", "n": cnt(allr, "stereo")},
                 {"key": "misread", "label": "Wrong", "n": cnt(allr, "wrong")},
                 {"key": "unreadable", "label": "Unparseable or none", "n": cnt(allr, "invalid")}]
    real_meta = json.load(open(RUN / "real" / "sources.json")) if (RUN / "real" / "sources.json").exists() else {}
    out = {
        "arm": "Superatoms (API)", "dir": DIR, "reader": "Sonnet 5.5 API", "rows": rows,
        "cards": cards, "vs": vs, "breakdown": breakdown, "splits": splits, "docs": docs, "docsLabel": "section",
        "altLabel": "Same molecule drawn plain (Sonnet 5.5 API only tab)", "altShort": "Plain drawing",
        "noAlt": "Not a corpus molecule, or its plain drawing has not been read by the API arm yet.",
        "runNote": "Sonnet 5.5 API call, at list price",
        "stats": {"n": len(allr), "exact": ex_s + ex_r, "strict_pct": pct(ex_s + ex_r, len(allr)),
                  "synth": {"n": len(syn), "exact": ex_s}, "real": {"n": len(real), "exact": ex_r},
                  "hidden": len(hidden)},
        "threshold": 101,
        "prompt": (RUN / "prompt_v2.txt").read_text().strip(),
        "method": [
            {"h": "What this tab is", "points": [
                "Sonnet 5.5 reading drawings that use TEXT SUPERATOMS (OMe, Boc, CF3, CO2Et, OTBS, Ts ...), one plain "
                "Messages API call per image: the PNG and the fixed prompt v2 below, no tools, no shared context, "
                "max_tokens 64,000, streamed. Image files have neutral names (sa_0001 ...) and no metadata.",
                "Scored exactly like the other Sonnet tabs (sonnet_batch.verdict): RDKit canonical SMILES of the answer "
                "against the FULL molecule, every superatom expanded. Exact / stereo-only / wrong / unparseable.",
                "Synthetic and real drawings are separate sections with separate exact rates; never pool them."]},
            {"h": "Synthetic section", "points": [
                "Molecules where abbreviations genuinely apply: corpus molecules with at least two condensable groups "
                "(chosen for label variety, all already read plain by the API-only arm), plus PubChem compounds picked for "
                "protecting groups and common superatoms (Boc/Cbz/Fmoc amino acids, silyl ethers, tosylates and triflates, "
                "nitroarenes, CF3 drugs, esters, acetylated and benzylated sugars).",
                "Drawn with RDKit's CondenseMolAbbreviations (maxCoverage 0.8) over RDKit's defaults plus Boc, Cbz, Fmoc, "
                "TMS/TBS/TIPS/TBDPS (and their O- forms), Ts/OTs, Tf/OTf, OMs, SO2Me, Bn/OBn, Bz/OBz, OPMB, Ph, OCF3, "
                "CO2Me, CO2Bn, CO2tBu, NMe2, NEt2, NHMe. Boc, Cbz and Fmoc may only sit on N (a tert-butyl ester reads "
                "CO2tBu); RDKit's own 'iBu' (really sec-butyl) and 'iPent' are corrected.",
                "Same renderer settings as the corpus (1500 px, scaled type and strokes). Each drawing passed: at least "
                "two labels; the condensed molecule expands back to the original exactly (canonical isomeric SMILES); "
                "every label is drawn as text; no two labels overlap.",
                "The paired comparison uses each corpus molecule's plain corpus drawing, as read by the Sonnet 5.5 API "
                "only arm (same model, no tools)."]},
            {"h": "Real section", "points": [real_meta.get("method", "Not built yet.")]},
        ],
        "headline": ("Text superatoms, one API call per image, no tools. Synthetic and real drawings are reported apart. "
                     "Cost at Sonnet 5.5 list price ($2 / $10 per MTok)."),
        "footer": (f"Synthetic: {len(syn)} drawings, exact {ex_s}, stereo only {cnt(syn, 'stereo')}, wrong {cnt(syn, 'wrong')}, "
                   f"unparseable {cnt(syn, 'invalid')}. Real: {len(real)} drawings ({len(hidden)} of them metrics only, "
                   f"licence), exact {ex_r}, stereo only {cnt(real, 'stereo')}, wrong {cnt(real, 'wrong')}, unparseable "
                   f"{cnt(real, 'invalid')}." + (f" Read but not scored: {'; '.join(excluded)}." if excluded else "")
                   + (f" Failed calls: {', '.join(failed)}." if failed else "")
                   + f" ${cost:.2f} in total (Sonnet 5.5 readings; the Haiku 5.5 screening of the real benchmarks is "
                   f"{real_meta.get('screen_cost', 'not included')})."),
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT}: synth {ex_s}/{len(syn)}, real {ex_r}/{len(real)} ({len(hidden)} hidden), ${cost:.4f}"
          + (f"; paired n={vs['n']} superatom {vs['api']} plain {vs['reader']} ahead {vs['ahead']} behind {vs['behind']} p={vs['p']}" if vs else ""))
    return 0


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    sys.exit(build())
