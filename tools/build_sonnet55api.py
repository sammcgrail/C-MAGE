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
from build_wall import WALL, render_pred, thumb, relate, tool_read_keys, gate_truth, WITHHELD_NOTE  # noqa: E402
_TILE = build_wall.TILE
import build_sonnet55 as B55  # noqa: E402
build_wall.TILE = _TILE
from sonnet_batch import verdict  # noqa: E402
from api_reader import SMILES_RE, parse_smiles  # noqa: E402

RUN = HERE.parent / "benchmarks" / "published_runs" / "sonnet55_api"
LEDGER = RUN / "ledger.jsonl"
RETRIES = RUN / "retries.jsonl"      # max_tokens follow-ups (tools/api_reader.py followups)
PROMPT = RUN / "prompt_v2.txt"      # the one prompt every row was read with
ARCHIVE = RUN / "archive"           # superseded readings (re-read with PROMPT); their cost still counts
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

    rets = {}
    for x in load_jsonl(RETRIES):
        rets.setdefault(x["k"], []).append(x)
    rows, failed = [], []
    for r0 in led:
        if r0["status"] != "ok":
            failed.append(r0["k"])
            continue
        # A max_tokens reading is scored on its last retry that finished (else its last retry that
        # landed at all); both attempts stay in the ledgers and the row says it was retried.
        rr = [x for x in rets.get(r0["k"], []) if x["status"] == "ok"]
        fin = [x for x in rr if x.get("stop_reason") != "max_tokens"]
        r = fin[-1] if fin else rr[-1] if rr else r0
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
               "rc": round(r0["cost_usd"] + sum(x.get("cost_usd") or 0 for x in rets.get(r0["k"], [])), 4),
               "rt": round(r0["latency_s"] + sum(x.get("latency_s") or 0 for x in rr), 1), "bn": 1,
               "mt": r0.get("max_tokens", 16000), "stop0": r0.get("stop_reason"),
               "stop": r.get("stop_reason"), "otok": u.get("output_tokens"), "ttok": think,
               "itok": u.get("input_tokens"), "wrapped": 1 if wrapped else 0,
               "ha": heavy(r["truth"])}
        if r0.get("prompt") != "v2":
            raise SystemExit(f"{k}: read with prompt {r0.get('prompt')!r}, not the published prompt")
        # The full reply goes in its own file, fetched when the sheet's fold is opened: inline it
        # would put megabytes into the tab payload at corpus scale.
        tf = txt / f"{k}.txt"
        body = r.get("text") or ""
        if r is not r0:
            body = (f"[Scored reply: the {r['kind']} retry at max_tokens {r['max_tokens']:,}. The first reading, at "
                    f"max_tokens {row['mt']:,}, stopped on max_tokens; its visible text follows the scored reply.]\n\n"
                    + body + "\n\n---- first reading (cut off at max_tokens) ----\n\n" + (r0.get("text") or ""))
        if not tf.exists() or tf.read_text() != body:
            tf.write_text(body)
        row["tx"] = 1
        row["rnote"] = (f"no tools · max_tokens {row['mt']:,} · stop_reason {row['stop0']}"
                        + (f" · then {' + '.join(x['kind'] for x in rets[k])} retry at "
                           f"{rets[k][-1]['max_tokens']:,}, stop_reason {row['stop']}" if k in rets else "")
                        + f" · {row['itok']:,} in / {row['otok']:,} out tokens"
                        + (f" ({think:,} thinking)" if think else ""))
        if k in rets:
            row["rf"] = "retried (" + ", ".join(dict.fromkeys(x["kind"] for x in rets[k])) + ")"
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
    arch = [json.loads(l) for p in sorted(ARCHIVE.glob("*.jsonl")) for l in open(p) if l.strip()] if ARCHIVE.exists() else []
    arch_cost, arch_n = sum(r.get("cost_usd") or 0 for r in arch), len(arch)
    cost = arch_cost + sum(r.get("cost_usd") or 0 for r in led) + sum(x.get("cost_usd") or 0 for xs_ in rets.values() for x in xs_)
    lat = [r["rt"] for r in rows]
    mt = sum(1 for r in rows if r["stop0"] == "max_tokens")
    retried = [r for r in rows if r.get("rf")]
    rescued = sum(1 for r in retried if r["stop"] != "max_tokens")
    rescued_ex = sum(1 for r in retried if r["stop"] != "max_tokens" and r["v"] == "exact")
    by_b = {}
    for r in rows:
        by_b.setdefault(r["mt"], []).append(r)
    bsplit = [{"label": f"max_tokens {b:,}", "n": len(rs), "pct": pct(sum(x["v"] == "exact" for x in rs), len(rs)),
               "text": f"{sum(x['v'] == 'exact' for x in rs)} of {len(rs)}, "
                       f"{sum(x['stop0'] == 'max_tokens' for x in rs)} ran out"} for b, rs in sorted(by_b.items())]
    bline = "; ".join(f"{x['label']}: {x['n']} images" for x in bsplit)
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
    if len(bsplit) > 1:
        splits.insert(0, {"h": "Exact by output budget (first attempt)", "rows": bsplit})
    breakdown = [{"key": "matched", "label": "Exact", "n": cnt("exact")},
                 {"key": "stereo", "label": "Stereo only", "n": cnt("stereo")},
                 {"key": "misread", "label": "Wrong", "n": cnt("wrong")},
                 {"key": "unreadable", "label": "Unparseable or none", "n": cnt("invalid")}]
    cards = [
        {"label": "Exact", "value": f"{pct(ex, n)}%", "sub": f"{ex} of {n}"},
        {"label": "Images", "value": str(n), "sub": "first in manifest order" + (f", {len(failed)} failed" if failed else "")},
        {"label": "Total cost", "value": f"${cost:.2f}", "sub": f"${cost / n:.3f} per image"},
        {"label": "Avg latency", "value": f"{sum(lat) / n:.1f} s", "sub": f"max {max(lat):.0f} s"},
        {"label": "Hit max_tokens", "value": str(mt),
         "sub": (f"{rescued} finished on retry, {rescued_ex} exact" if retried else "first attempts")},
    ]
    models = sorted({r.get("model") for r in led if r["status"] == "ok"})
    # Same rule as wall/images.json: the reference (and what is computed from it) is served only
    # for images a tool-using Sonnet reader has already read. Every figure above was computed
    # before this, from the full rows; only the per-row payload loses the fields.
    withheld = gate_truth(rows, tool_read_keys())
    out = {
        "arm": "Sonnet 5.5 API only", "dir": DIR, "reader": "Sonnet 5.5 API", "rows": rows,
        "cards": cards, "vs": vs, "breakdown": breakdown, "splits": splits,
        "altLabel": "Sonnet 5.5 reader with tools (Sonnet 5.5 tab)", "altShort": "Sonnet 5.5 + tools",
        "noAlt": "The tool-using Sonnet 5.5 reader has not read this image.",
        "runNote": "Sonnet 5.5 API call, at list price",
        "stats": {"n": n, "exact": ex, "strict_pct": pct(ex, n)},
        **({"withheld": {"n": withheld, "note": WITHHELD_NOTE}} if withheld else {}),
        "threshold": 101,
        "prompt": PROMPT.read_text().strip(),
        "method": [
            {"h": "What this tab is", "points": [
                f"Sonnet 5.5 ({', '.join(models)}) reading the first {n} corpus images in manifest order, one "
                "Messages API call per image: the PNG as base64 and a fixed prompt (below). No tools, no "
                "code, no second look, no shared context between images.",
                "The answer is the last \"SMILES: ...\" line of the reply. Adaptive thinking at the API "
                f"default. Output budget: max_tokens 64,000, streamed, except {len(by_b.get(16000, []))} early rows read at 16,000; "
                "each row records its own.",
                "A reading that runs out of output is retried and scored on the retry, flagged on its tile "
                "(↻) and in its sheet: a row read at 16,000 is re-read once at 64,000; one that runs out at "
                "64,000 gets one retry with an added instruction to commit to an answer after one careful "
                "pass. Both attempts are kept and counted in the cost.",
                "Scored exactly like the other Sonnet tabs: RDKit canonical SMILES against the PubChem "
                "reference, exact / stereo-only / wrong / unparseable.",
            ]},
            {"h": "Against the Sonnet 5.5 tab", "points": [
                "The Sonnet 5.5 tab's reader is an agent: it crops, runs RDKit, re-renders its answer and "
                "diffs it against the image. Compared here only on the images both have read."]},
        ],
        "headline": "One API call per image, no tools. Cost at Sonnet 5.5 list price ($2 / $10 per MTok).",
        "footer": (f"n={n}, the first {n} corpus images in manifest order. Output budget per first attempt: {bline}"
                   + (f"; {len(retried)} max_tokens rows retried, {rescued} finished, {rescued_ex} exact" if retried else "")
                   + f". Exact {ex}/{n}; stereo only "
                   f"{cnt('stereo')}; wrong {cnt('wrong')}; unparseable or no SMILES line {cnt('invalid')}"
                   f" (no SMILES line: {no_line}). Stop reasons other than end_turn: max_tokens {mt}"
                   + (f", {', '.join(other_stop)}" if other_stop else "") + f". ${cost:.2f} in total" + (f", including ${arch_cost:.2f} for {arch_n} superseded readings of the first "
                                                     f"images, kept in archive/" if arch_n else "") + "."
                   + (f" {wrapped_n} replies wrote the answer as <smiles>...</smiles> (the prompt's placeholder "
                      f"taken literally); the tags are stripped before scoring, which moves {wrapped_raw_ex} "
                      f"from unparseable to exact." if wrapped_n else "")
                   + (f" Failed calls: {', '.join(failed)}." if failed else "")
                   + " Ground truth is PubChem."
                   + (f" The reference SMILES is withheld on {withheld:,} images no tool-using Sonnet reader has "
                      f"read yet (those readers have a network); verdicts are shown for all." if withheld else "")),
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":")))
    os.replace(tmp, OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.1f} KB): {n} rows, exact {ex}/{n}, ${cost:.4f}, "
          f"max_tokens {mt} (retried {len(retried)}, finished {rescued}, exact {rescued_ex}), failed {len(failed)}, unwrapped {wrapped_n} ({wrapped_raw_ex} of them exact)"
          + (f"; vs tools reader on {vs['n']}: API {vs['api']} reader {vs['reader']} "
             f"ahead {vs['ahead']} behind {vs['behind']} p={vs['p']}" if vs else "; no overlap"))
    return 0


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    sys.exit(build())
