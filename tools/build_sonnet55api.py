#!/usr/bin/env python3
"""The "Sonnet 5.5 API only" tab: Sonnet 5.5 reading corpus images in ONE plain Messages API call
each (no tools, no RDKit, no crops), from benchmarks/published_runs/sonnet55_api/ledger.jsonl
(written by tools/api_reader.py).

    build_sonnet55api.py        rebuild wall/sonnet55api.json + 240 px tiles

Every answer is scored with sonnet_batch.verdict(), the one scoring function for every Sonnet
reading. Where the regular Sonnet 5.5 corpus reader (the tool-using, sandboxed agent of the
Sonnet 5.5 tab, lane s55c) has read the same image, the two are compared on that overlap only.
The payload has the shape index.html already renders, plus `cards` and `vs` for this tab's hero.
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
from build_wall import WALL, render_pred, thumb, relate  # noqa: E402
_TILE = build_wall.TILE
import build_sonnet55 as B55  # noqa: E402
build_wall.TILE = _TILE
from sonnet_batch import verdict  # noqa: E402
from api_reader import SMILES_RE, parse_smiles  # noqa: E402

RUN = HERE.parent / "benchmarks" / "published_runs" / "sonnet55_api"
LEDGER = RUN / "ledger.jsonl"
PROMPTS = {"v1": RUN / "prompt.txt", "v2": RUN / "prompt_v2.txt"}   # row["prompt"] names one; absent = v1
PROMPT_NOTE = {"v1": "answer line written as SMILES: <smiles>", "v2": "answer line shown as SMILES: CCO"}
BUCKETS = [(0, 15, "up to 15"), (16, 30, "16-30"), (31, 50, "31-50"), (51, 80, "51-80"), (81, 10 ** 6, "81 or more")]
REG = Path("/root/cmage-work/sonnet-s55c/results.jsonl")   # the regular Sonnet 5.5 reader (tools)
OUT = WALL / "sonnet55api.json"
DIR = "sonnet55api"


def load_jsonl(p: Path, tolerant: bool = False) -> list[dict]:
    """tolerant: skip a line that does not parse. Used for the s55c results file, which another run
    appends to while this builds, so its last line can be half-written at the moment we read it."""
    if not p.exists():
        return []
    out = []
    for l in open(p):
        if not l.strip():
            continue
        try:
            out.append(json.loads(l))
        except ValueError:
            if not tolerant:
                raise
    return out


def heavy(smiles: str) -> int | None:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    m = Chem.MolFromSmiles(smiles)
    return m.GetNumHeavyAtoms() if m is not None else None


def build() -> int:
    led = load_jsonl(LEDGER)
    if not led:
        raise SystemExit(f"no rows in {LEDGER}")
    seen = set()
    for r in led:
        if r["k"] in seen:
            raise SystemExit(f"{r['k']} appears twice in {LEDGER}")
        seen.add(r["k"])
    reg = {r["k"]: r for r in load_jsonl(REG, tolerant=True)}

    idx = {}
    for dd in sorted(glob.glob("/root/cmage-work/cmage-img*/corpus_rdkit_1500")):
        for p in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(p), p)
    img, pred, ocr, txt = WALL / DIR, WALL / f"{DIR}_pred", WALL / f"{DIR}_ocr", WALL / f"{DIR}_txt"
    for p in (img, pred, ocr, txt):
        p.mkdir(parents=True, exist_ok=True)

    rows, failed = [], []
    for r in led:
        if r["status"] != "ok":
            failed.append(r["k"])
            continue
        # Parsed again from the stored reply, so a parser fix applies to every row the same way.
        k, s = r["k"], parse_smiles(r.get("text")) or ""
        last = SMILES_RE.findall(r.get("text") or "")
        wrapped = bool(last) and last[-1] != s
        v = verdict(s, r["truth"])
        thumb(Path(idx[k + ".png"]), img / f"{k}.png")
        has = render_pred(s, pred / f"{k}.png")
        u = r.get("usage") or {}
        think = (u.get("output_tokens_details") or {}).get("thinking_tokens")
        row = {"k": k, "n": r["name"], "v": v, "g": v, "c": None, "s": s, "t": r["truth"],
               "p": 1 if has else 0, "r": relate(s, r["truth"]),
               "rc": round(r["cost_usd"], 4), "rt": r["latency_s"], "bn": 1,
               "stop": r.get("stop_reason"), "otok": u.get("output_tokens"), "ttok": think,
               "itok": u.get("input_tokens"), "wrapped": 1 if wrapped else 0,
               "pv": r.get("prompt", "v1"), "ha": heavy(r["truth"])}
        # The full reply goes in its own file, fetched when the sheet's fold is opened: inline it
        # would put megabytes into the tab payload at corpus scale.
        tf = txt / f"{k}.txt"
        if not tf.exists():
            tf.write_text(r.get("text") or "")
        row["tx"] = 1
        row["rnote"] = (f"one API call, no tools · stop_reason {row['stop']} · {row['itok']:,} in / "
                        f"{row['otok']:,} out tokens" + (f" ({think:,} thinking)" if think else ""))
        g = reg.get(k)
        if g:
            if g["truth"] != r["truth"]:
                raise SystemExit(f"{k}: API ledger and s55c disagree on the truth")
            # Re-score the regular reading with the same function, so both sides use one scorer.
            gv = verdict(g.get("sonnet_smiles"), g["truth"])
            row["alt"] = {"s": g.get("sonnet_smiles") or "", "v": gv, "conf": g.get("sonnet_conf")}
            row["ocr"], row["ocrv"], row["ocrc"] = g["ocr_smiles"], g["ocr_verdict"], g["ocr_conf"]
            row["po"] = 1 if render_pred(g.get("ocr_smiles") or "", ocr / f"{k}.png") else 0
            row["cx"] = 1 if "|$" in (g.get("ocr_smiles") or "") else 0
        rows.append(row)

    n = len(rows)
    pct = lambda a, b: round(a / b * 100, 1) if b else 0.0
    ex = sum(1 for r in rows if r["v"] == "exact")
    cost = sum(r.get("cost_usd") or 0 for r in led)
    lat = [r["rt"] for r in rows]
    mt = sum(1 for r in rows if r["stop"] == "max_tokens")
    other_stop = sorted({r["stop"] for r in rows} - {"end_turn", "max_tokens"})
    no_line = sum(1 for r in rows if not r["s"])
    wrapped_n = sum(r["wrapped"] for r in rows)
    wrapped_raw_ex = sum(1 for r in rows if r["wrapped"] and r["v"] == "exact")

    xs = [r for r in rows if "alt" in r]
    vs = None
    if xs:
        a_ok = lambda r: r["v"] == "exact"
        b_ok = lambda r: r["alt"]["v"] == "exact"
        ahead = sum(1 for r in xs if a_ok(r) and not b_ok(r))
        behind = sum(1 for r in xs if b_ok(r) and not a_ok(r))
        vs = {"n": len(xs), "api": sum(map(a_ok, xs)), "reader": sum(map(b_ok, xs)),
              "ahead": ahead, "behind": behind, "p": float(f"{B55.mcnemar_exact(ahead, behind):.3g}"),
              "behind_names": [r["n"] for r in xs if b_ok(r) and not a_ok(r)],
              "ahead_names": [r["n"] for r in xs if a_ok(r) and not b_ok(r)]}
        vs["sides"] = [
            {"label": "API, no tools", "exact": vs["api"], "n": vs["n"], "pct": pct(vs["api"], vs["n"])},
            {"label": "Agent, with tools", "exact": vs["reader"], "n": vs["n"],
             "pct": pct(vs["reader"], vs["n"])}]
        vs["text"] = (f"Against the Sonnet 5.5 tab's tool-using reader on the same {vs['n']} images, same scorer: "
                      f"right only via the API {vs['ahead']}, right only with tools {vs['behind']} "
                      f"(exact McNemar p={vs['p']}).")

    cnt = lambda key: sum(1 for r in rows if r["v"] == key)
    by_v = {}
    for r in rows:
        by_v.setdefault(r["pv"], []).append(r)
    vsplit = [{"label": f"Prompt {v} ({PROMPT_NOTE.get(v, v)})", "n": len(rs),
               "pct": pct(sum(x["v"] == "exact" for x in rs), len(rs)),
               "text": f"{sum(x['v'] == 'exact' for x in rs)} of {len(rs)}"} for v, rs in sorted(by_v.items())]
    hsplit = []
    for lo, hi, lab in BUCKETS:
        rs = [r for r in rows if r["ha"] is not None and lo <= r["ha"] <= hi]
        if not rs:
            continue
        e = sum(x["v"] == "exact" for x in rs)
        ov = [x for x in rs if "alt" in x]
        t = f"{e} of {len(rs)}"
        if ov:
            t += (f" · with tools {sum(x['alt']['v'] == 'exact' for x in ov)} of {len(ov)}"
                  + ("" if len(ov) == len(rs) else f" (API {sum(x['v'] == 'exact' for x in ov)} on those)"))
        hsplit.append({"label": f"{lab} heavy atoms", "n": len(rs), "pct": pct(e, len(rs)), "text": t})
    splits = [{"h": "Exact by size (heavy atoms in the reference)", "rows": hsplit}]
    if len(vsplit) > 1:
        splits.insert(0, {"h": "Exact by prompt version", "rows": vsplit})
    vline = "; ".join(f"{x['label']}: {x['n']} images, {x['pct']}% exact" for x in vsplit)
    breakdown = [{"key": "matched", "label": "Exact", "n": cnt("exact")},
                 {"key": "stereo", "label": "Stereo only", "n": cnt("stereo")},
                 {"key": "misread", "label": "Wrong", "n": cnt("wrong")},
                 {"key": "unreadable", "label": "Unparseable or none", "n": cnt("invalid")}]
    cards = [
        {"label": "Exact", "value": f"{pct(ex, n)}%", "sub": f"{ex} of {n}"},
        {"label": "Images", "value": str(n), "sub": "first in manifest order" + (f", {len(failed)} failed" if failed else "")},
        {"label": "Total cost", "value": f"${cost:.2f}", "sub": f"${cost / n:.3f} per image"},
        {"label": "Avg latency", "value": f"{sum(lat) / n:.1f} s", "sub": f"max {max(lat):.0f} s"},
        {"label": "Hit max_tokens", "value": str(mt), "sub": "of 16,000"},
    ]
    models = sorted({r.get("model") for r in led if r["status"] == "ok"})
    out = {
        "arm": "Sonnet 5.5 API only", "dir": DIR, "reader": "Sonnet 5.5 API", "rows": rows,
        "cards": cards, "vs": vs, "breakdown": breakdown, "splits": splits,
        "altLabel": "Sonnet 5.5 reader with tools (Sonnet 5.5 tab)", "altShort": "Sonnet 5.5 + tools",
        "noAlt": "The tool-using Sonnet 5.5 reader has not read this image.",
        "runNote": "Sonnet 5.5 API call, at list price",
        "stats": {"n": n, "exact": ex, "strict_pct": pct(ex, n)},
        "threshold": 101,
        "prompt": "\n\n".join(f"Prompt {v} ({PROMPT_NOTE[v]}), {len(by_v[v])} images:\n\n{PROMPTS[v].read_text().strip()}"
                              for v in sorted(by_v)),
        "method": [
            {"h": "What this tab is", "points": [
                f"Sonnet 5.5 ({', '.join(models)}) reading the first {n} corpus images in manifest order, one "
                "Messages API call per image: the PNG as base64 and a fixed prompt (below). No tools, no "
                "code, no second look, no shared context between images.",
                "The answer is the last \"SMILES: ...\" line of the reply. Adaptive thinking at the API "
                "default; max_tokens 16,000.",
                "Scored exactly like the other Sonnet tabs: RDKit canonical SMILES against the PubChem "
                "reference, exact / stereo-only / wrong / unparseable.",
            ]},
            {"h": "Against the Sonnet 5.5 tab", "points": [
                "The Sonnet 5.5 tab's reader is an agent: it crops, runs RDKit, re-renders its answer and "
                "diffs it against the image. Compared here only on the images both have read."]},
        ],
        "headline": ("One API call per image, no tools. Cost at Sonnet 5.5 list price ($2 / $10 per MTok)."
                     + (f" {wrapped_n} prompt-v1 answers came wrapped in <smiles> tags and were unwrapped before scoring."
                        if wrapped_n else "")),
        "footer": (f"n={n}, the first {n} corpus images in manifest order. Prompt versions: {vline}. Exact {ex}/{n}; stereo only "
                   f"{cnt('stereo')}; wrong {cnt('wrong')}; unparseable or no SMILES line {cnt('invalid')}"
                   f" (no SMILES line: {no_line}). Stop reasons other than end_turn: max_tokens {mt}"
                   + (f", {', '.join(other_stop)}" if other_stop else "") + f". ${cost:.2f} in total."
                   + (f" {wrapped_n} replies wrote the answer as <smiles>...</smiles> (the prompt's placeholder "
                      f"taken literally); the tags are stripped before scoring, which moves {wrapped_raw_ex} "
                      f"from unparseable to exact." if wrapped_n else "")
                   + (f" Failed calls: {', '.join(failed)}." if failed else "")
                   + " Ground truth is PubChem."),
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.1f} KB): {n} rows, exact {ex}/{n}, ${cost:.4f}, "
          f"max_tokens {mt}, failed {len(failed)}, unwrapped {wrapped_n} ({wrapped_raw_ex} of them exact)"
          + (f"; vs tools reader on {vs['n']}: API {vs['api']} reader {vs['reader']} "
             f"ahead {vs['ahead']} behind {vs['behind']} p={vs['p']}" if vs else "; no overlap"))
    return 0


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    sys.exit(build())
