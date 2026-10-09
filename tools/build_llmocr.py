#!/usr/bin/env python3
"""The "LLM vs OCR" tab: four readers on the same corpus images, one scorer.

    build_llmocr.py        rebuild wall/llmocr.json (charts + one compact row per image)
                           and wall/llmocr_detail.json (every answer, fetched when a sheet opens)

Arms, each read from its own ledger and re-scored here with sonnet_batch.verdict():
  s55  Sonnet 5.5, tool-using reader   /root/cmage-work/sonnet-s55c/results.jsonl, cost benchmarks/sonnet55c_runs.json
  api  Sonnet 5.5, one plain API call  benchmarks/published_runs/sonnet55_api/ledger.jsonl (+ retries.jsonl)
  s5   Sonnet 5, tool-using reader     /root/cmage-work/sonnet/results.jsonl, cost from wall/sonnet.json rows
  cx   CXMolScribe (OCR)               benchmarks/corpus_rows.json (stage 3 on the corpus images)

Every chart is computed here, never in the page. The renderer-control chart is filled from
wall/control.json whenever that file exists, so it appears with no change to this script or the page.
The reference SMILES goes into the detail file only for images a tool-using reader has read
(build_wall.tool_read_keys), the same gate as every other payload.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "benchmarks"))

from build_wall import WALL, tool_read_keys, WITHHELD_NOTE  # noqa: E402
from sonnet_batch import verdict  # noqa: E402
from api_reader import parse_smiles  # noqa: E402
import control_set as CS  # noqa: E402

S55 = Path("/root/cmage-work/sonnet-s55c/results.jsonl")
S55_RUNS = REPO / "benchmarks" / "sonnet55c_runs.json"
S5 = Path("/root/cmage-work/sonnet/results.jsonl")
S5_REMOVED = Path("/root/cmage-work/sonnet/removed.jsonl")
S5_PAYLOAD = WALL / "sonnet.json"          # per-image cost (rc), traced by build_sonnet/sonnet_cost
API = REPO / "benchmarks" / "published_runs" / "sonnet55_api"
CORPUS = REPO / "benchmarks" / "corpus_rows.json"
HAND = Path("/root/cmage-work/sonnet-s55/results.jsonl")
HAND_LEDGER = REPO / "benchmarks" / "sonnet55_runs.json"
CONTROL = WALL / "control.json"
DUAL_STATE = Path("/root/cmage-work/dual/state.json")
OUT = WALL / "llmocr.json"
DETAIL = WALL / "llmocr_detail.json"

# Fixed display order and colour per arm (validated as an adjacent categorical set on the dark panel).
ARMS = [
    {"id": "s55", "label": "Sonnet 5.5 · tools", "short": "5.5 tools", "tag": "5.5", "kind": "llm",
     "color": "#3987e5", "pred": "sonnet55c_pred"},
    {"id": "api", "label": "Sonnet 5.5 · API", "short": "5.5 API", "tag": "API", "kind": "llm",
     "color": "#d55181", "pred": "sonnet55api_pred"},
    {"id": "s5", "label": "Sonnet 5 · tools", "short": "Sonnet 5", "tag": "5", "kind": "llm",
     "color": "#9085e9", "pred": "sonnet_pred"},
    {"id": "cx", "label": "CXMolScribe (OCR)", "short": "CXMolScribe", "tag": "OCR", "kind": "ocr",
     "color": "#d95926", "pred": "img_pred"},
]
IDS = [a["id"] for a in ARMS]
CODE = {"exact": "e", "stereo": "s", "wrong": "w", "invalid": "i"}
BUCKETS = [(0, 15, "≤15"), (16, 30, "16–30"), (31, 50, "31–50"), (51, 80, "51–80"), (81, 10 ** 6, "81+")]


def load_jsonl(p: Path) -> list[dict]:
    """Tolerant: a results file another run appends to can end in a half-written line."""
    out = []
    if not p.exists():
        return out
    for line in open(p):
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    return out


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def pct(a: int, b: int) -> float | None:
    return round(a / b * 100, 1) if b else None


def heavy(smiles: str) -> int | None:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    m = Chem.MolFromSmiles(smiles or "")
    return m.GetNumHeavyAtoms() if m is not None else None


def money(x: float) -> str:
    return f"${x:.3f}" if x < 0.1 else f"${x:.2f}"


def secs(x: float) -> str:
    x = round(x)
    return f"{x} s" if x < 90 else f"{x // 60} min {x % 60} s"


def kfmt(x: float) -> str:
    return f"{x / 1000:.1f}k" if x >= 1000 else f"{x:.0f}"


def prompts(s55_runs: list[dict], led: list[dict]) -> list[dict]:
    """The exact prompt and settings per arm, for the tab's Prompts sheet. Read from the files the
    readers were given and from the run ledgers, never typed here."""
    T = HERE
    multi = sum(1 for r in s55_runs if r["images"] > 1)
    s55_imgs = sum(r["images"] for r in s55_runs if r["images"] > 1)
    models = sorted({m for r in s55_runs for m in r.get("models") or []})
    efforts = sorted({e for r in s55_runs for e in (r.get("effort") or [])})
    agents = sorted({r.get("agent_type") for r in s55_runs if r.get("agent_type")})
    ok = [r for r in led if r.get("status") == "ok"]
    mt = sorted({r.get("max_tokens") for r in ok if r.get("max_tokens")})
    no_mt = sum(1 for r in ok if not r.get("max_tokens"))
    s5p = json.load(open(S5_PAYLOAD)) if S5_PAYLOAD.exists() else {"rows": []}
    s5_multi = sum(1 for r in s5p["rows"] if (r.get("bn") or 1) > 1)
    return [
        {"id": "s55", "model": ", ".join(models),
         "settings": [f"Claude Code agent ({', '.join(agents)}), effort {', '.join(efforts)}",
                      "Tools: Read (vision), Bash with Python, RDKit, PIL, OSRA",
                      "Lookups barred; every reader transcript screened before scoring",
                      "Images under anonymous names, pixels only",
                      f"{s55_imgs:,} images were read ten per reader with the ten-image wording ({multi} readers); "
                      "the rest one per reader with the prompt below"],
         "prompt": (T / "reader_prompt_s55c_single.txt").read_text().strip()},
        {"id": "api", "model": ", ".join(sorted({r.get("model") for r in ok})),
         "settings": ["One Messages API call per image: the PNG and the prompt, nothing else",
                      "No tools, no system prompt, no second turn",
                      "Thinking and effort at the API default; streamed",
                      f"max_tokens {', '.join(f'{m:,}' for m in mt)}"
                      + (f" ({no_mt} rows did not record it)" if no_mt else ""),
                      "Answer = the last \"SMILES:\" line of the reply"],
         "prompt": (API / "prompt_v2.txt").read_text().strip()},
        {"id": "s5", "model": "claude-sonnet-5",
         "settings": ["Claude Code agent; tools: Read (vision), Bash with Python, RDKit, PIL, OSRA",
                      "Lookups barred; every reader transcript screened before scoring",
                      "Images under anonymous names",
                      f"{s5_multi:,} of {len(s5p['rows']):,} images read ten (or fewer) per reader, the rest one per reader",
                      "The arm's prompt was reworded during its run; this is the final wording"],
         "prompt": (T / "reader_prompt_s5.txt").read_text().strip()},
        {"id": "cx", "model": "CXMolScribe (C-MAGE stage 3)",
         "settings": ["Stage 3 only on each 1500 px corpus PNG; no figure extraction or segmentation",
                      "CPU; output CXSMILES; confidence is the model's own score"],
         "prompt": None},
    ]


def removed_s5() -> list[dict]:
    """Sonnet 5 rows currently removed (the log is append-only; a later `restored` cancels)."""
    last: dict[str, dict] = {}
    for r in load_jsonl(S5_REMOVED):
        last[r["k"]] = r
    return [r for r in last.values() if not r.get("restored")]


def build() -> int:
    corpus = {r["k"]: r for r in json.load(open(CORPUS))["rows"]}
    truth = {k: r["t"] for k, r in corpus.items()}
    name = {k: r["n"] for k, r in corpus.items()}

    ans: dict[str, dict[str, dict]] = {a: {} for a in IDS}   # arm -> key -> {s, v, c}
    cost: dict[str, dict[str, float]] = {a: {} for a in IDS}
    facts: dict[str, dict[str, list[str]]] = {a: {} for a in IDS}   # arm -> key -> short facts for the sheet

    def put(arm, k, s, t, conf=None):
        if t != truth.get(k):
            raise SystemExit(f"{arm} {k}: ledger truth differs from corpus_rows.json")
        ans[arm][k] = {"s": s or "", "v": verdict(s, t), "c": conf}

    s55 = load_jsonl(S55)
    for r in s55:
        put("s55", r["k"], r.get("sonnet_smiles"), r["truth"], r.get("sonnet_conf"))
    s55_runs = list((json.load(open(S55_RUNS)).get("runs") or {}).values())
    for run in s55_runs:
        n_ = run["images"]
        tok = run.get("tokens") or {}
        for k in run["keys"]:
            cost["s55"][k] = run["cost_usd"] / n_
            facts["s55"][k] = [money(run["cost_usd"] / n_), secs(run["duration_s"] / n_),
                               f"{kfmt(tok.get('output', 0) / n_)} output tokens",
                               f"{kfmt(sum(tok.get(x, 0) for x in ('input', 'cache_read', 'cache_write_5m', 'cache_write_1h')) / n_)} input",
                               f"{run.get('requests', 0) / n_:.0f} model calls" if n_ == 1 else f"1 of {n_} images in one reader"]

    led = load_jsonl(API / "ledger.jsonl")
    bad = [r["k"] for r in led if r.get("prompt") != "v2"]
    if bad:
        raise SystemExit(f"{len(bad)} API rows not read with the published prompt v2: {bad[:5]}")
    rets = load_jsonl(API / "retries.jsonl")
    scored = CS.api_scored(led, rets)
    for r0 in led:
        k = r0["k"]
        if k not in scored:
            continue
        put("api", k, parse_smiles(scored[k].get("text")) or "", r0["truth"])
        rk = [x for x in rets if x["k"] == k]
        cost["api"][k] = (r0.get("cost_usd") or 0) + sum(x.get("cost_usd") or 0 for x in rk)
        u, r = scored[k].get("usage") or {}, scored[k]
        think = (u.get("output_tokens_details") or {}).get("thinking_tokens")
        facts["api"][k] = [money(cost["api"][k]),
                           secs((r0.get("latency_s") or 0) + sum(x.get("latency_s") or 0 for x in rk)),
                           f"{kfmt(u.get('output_tokens') or 0)} output tokens"
                           + (f" ({kfmt(think)} thinking)" if think else ""),
                           f"{kfmt(u.get('input_tokens') or 0)} input",
                           f"stop: {r.get('stop_reason')}" + (f", retried after {r0.get('stop_reason')}" if r is not r0 else "")]

    for r in load_jsonl(S5):
        put("s5", r["k"], r.get("sonnet_smiles"), r["truth"], r.get("sonnet_conf"))
    if S5_PAYLOAD.exists():
        for r in json.load(open(S5_PAYLOAD))["rows"]:
            if r.get("rc") is not None and r["k"] in ans["s5"]:
                cost["s5"][r["k"]] = r["rc"]
                bn = r.get("bn") or 1
                facts["s5"][r["k"]] = [money(r["rc"]), secs(r.get("rt") or 0)] + (
                    [f"1 of {bn} images in one reader"] if bn > 1 else ["one image per reader"])

    cx_drift = 0
    for k, r in corpus.items():
        put("cx", k, r.get("s"), r["t"], r.get("c"))
        facts["cx"][k] = ["local CPU, no API cost"]
        cx_drift += ans["cx"][k]["v"] != r.get("v")

    ok = lambda a, k: ans[a].get(k, {}).get("v") == "exact"
    has = lambda a, k: k in ans[a]

    # 1. Every arm on the images all four have read.
    shared = sorted(k for k in corpus if all(has(a, k) for a in IDS))
    n_sh = len(shared)
    share = []
    for a in ARMS:
        vs = [ans[a["id"]][k]["v"] for k in shared]
        share.append({"id": a["id"], "n": n_sh, "exact": vs.count("exact"), "stereo": vs.count("stereo"),
                      "wrong": vs.count("wrong"), "invalid": vs.count("invalid"),
                      "pct": pct(vs.count("exact"), n_sh)})

    # 2. Head-to-head on each pair's own overlap: who alone got it right.
    PAIRS = [("s55", "api"), ("s55", "s5"), ("api", "s5"), ("s55", "cx"), ("api", "cx"), ("s5", "cx")]
    pairs = []
    for x, y in PAIRS:
        ks = [k for k in corpus if has(x, k) and has(y, k)]
        b = sum(1 for k in ks if ok(x, k) and not ok(y, k))
        c = sum(1 for k in ks if ok(y, k) and not ok(x, k))
        both = sum(1 for k in ks if ok(x, k) and ok(y, k))
        pairs.append({"a": x, "b": y, "n": len(ks), "a_exact": both + b, "b_exact": both + c,
                      "a_pct": pct(both + b, len(ks)), "b_pct": pct(both + c, len(ks)),
                      "a_only": b, "b_only": c, "both": both, "neither": len(ks) - both - b - c,
                      "p": float(f"{mcnemar(b, c):.2g}")})
    # Any Sonnet arm vs the OCR, over every image the OCR and at least one Sonnet arm read.
    ks = [k for k in corpus if has("cx", k) and any(has(a, k) for a in ("s55", "api", "s5"))]
    llm = lambda k: any(ok(a, k) for a in ("s55", "api", "s5"))
    b = sum(1 for k in ks if llm(k) and not ok("cx", k))
    c = sum(1 for k in ks if ok("cx", k) and not llm(k))
    either = {"n": len(ks), "llm": sum(map(llm, ks)), "cx": sum(1 for k in ks if ok("cx", k)),
              "llm_only": b, "cx_only": c, "any": sum(1 for k in ks if llm(k) or ok("cx", k))}

    # 3. Exact by size (heavy atoms in the reference), shared set.
    ha = {k: heavy(truth[k]) for k in shared}
    size = []
    for lo, hi, lab in BUCKETS:
        ks = [k for k in shared if ha[k] is not None and lo <= ha[k] <= hi]
        if ks:
            size.append({"label": lab, "n": len(ks),
                         "arms": [{"id": a, "exact": sum(ok(a, k) for k in ks),
                                   "pct": pct(sum(ok(a, k) for k in ks), len(ks))} for a in IDS]})

    # 4. Cost per image, shared set, where it is known.
    costs = []
    for a in ARMS:
        cs = [cost[a["id"]][k] for k in shared if k in cost[a["id"]]]
        costs.append({"id": a["id"], "usd": round(sum(cs) / len(cs), 3) if cs else None, "n": len(cs),
                      "note": None if cs else "runs locally on CPU; no API cost"})

    # 5. The hand-picked set: 20 Sonnet 5 misses + 8 Sonnet 5 rights, read again by every arm.
    hand = None
    hrows = load_jsonl(HAND)
    if hrows and HAND_LEDGER.exists():
        side = json.load(open(HAND_LEDGER)).get("side") or []
        base = side[0]["label"] if side else None
        rr = {}
        for x in side:
            if x["label"] == base:
                for k, v in x["reads"].items():
                    rr[k] = verdict(v.get("s"), truth[k])
        hk = [r["k"] for r in hrows]
        s5pub = {k: verdict(r.get("sonnet_smiles"), truth[k]) for k, r in
                 ((r["k"], r) for r in load_jsonl(S5)) if k in hk}
        bars = [{"id": "s55", "label": "Sonnet 5.5 · tools",
                 "exact": sum(verdict(r.get("sonnet_smiles"), r["truth"]) == "exact" for r in hrows), "n": len(hrows)}]
        if rr:
            bars.append({"id": "s5", "label": "Sonnet 5 · tools, re-run on the same prompt", "short": "Sonnet 5 re-run",
                         "exact": sum(v == "exact" for v in rr.values()), "n": len(rr)})
        for a in ("api", "cx"):
            got = [k for k in hk if has(a, k)]
            bars.append({"id": a, "label": ARMS[IDS.index(a)]["label"], "exact": sum(ok(a, k) for k in got),
                         "n": len(got)})
        for x in bars:
            x["pct"] = pct(x["exact"], x["n"])
        miss = sum(1 for v in s5pub.values() if v != "exact")
        hand = {"n": len(hrows), "bars": bars,
                "note": f"{miss} images Sonnet 5 first got wrong plus {len(hk) - miss} it got right, read again by each arm."}

    # 6. Renderer control: the same molecules drawn by another renderer.
    control = None
    if CONTROL.exists():
        C = json.load(open(CONTROL))
        idmap = {"Sonnet 5.5 API only": "api", "Sonnet 5.5 with tools": "s55"}
        arms = [{"id": idmap.get(a["arm"], a["arm"]), "n": a["n"], "corpus": a["corpus_exact"],
                 "control": a["control_exact"], "corpus_pct": pct(a["corpus_exact"], a["n"]),
                 "control_pct": pct(a["control_exact"], a["n"]), "p": a.get("mcnemar_p")}
                for a in C.get("arms") or [] if a.get("n")]
        if arms:
            ren = (C.get("renderer") or "other renderer").split(",")[0]
            control = {"renderer": ren, "short": re.sub(r"^EPAM\s+|\s+[\d.]+$", "", ren), "set": C.get("set"),
                       "arms": arms}

    # Caveats: one line each, current state only.
    caveats = ["Tool readers can re-render their answer with RDKit, the corpus renderer; the API arm has no tools."]
    rem = removed_s5()
    if rem:
        caveats.append(f"{len(rem)} Sonnet 5 row{'' if len(rem) == 1 else 's'} excluded (name lookup): "
                       + ", ".join(name.get(r["k"], r["k"]) for r in rem) + "."
                       if all("name-to-structure" in (r.get("reason") or "") for r in rem) else
                       f"{len(rem)} Sonnet 5 rows excluded after audit: "
                       + ", ".join(name.get(r["k"], r["k"]) for r in rem) + ".")
    st = json.load(open(DUAL_STATE)) if DUAL_STATE.exists() else {}
    deferred = sorted(k for k in ((st.get("deferred") or {}).get("s55") or {}) if k not in ans["s55"])
    if deferred:
        caveats.append("Not yet read by Sonnet 5.5 · tools: " + ", ".join(name.get(k, k) for k in deferred) + ".")
    caveats.append("Exact = same molecule as the PubChem reference after RDKit canonicalisation, stereo included.")

    # Rows: one per corpus image any arm has read; verdict codes in ARMS order, "-" = not read.
    read = tool_read_keys()
    rows, detail = [], {}
    for k in sorted(corpus):
        code = "".join(CODE[ans[a][k]["v"]] if has(a, k) else "-" for a in IDS)
        rows.append([k, name[k], code])
        d = {a: [ans[a][k]["s"], ans[a][k]["c"], facts[a].get(k) or []] for a in IDS if has(a, k)}
        if k in read:
            d["t"] = truth[k]
        detail[k] = d
    missing = {a["id"]: sum(1 for k in ans[a["id"]] if ans[a["id"]][k]["s"]
                            and not (WALL / a["pred"] / f"{k}.png").exists()) for a in ARMS}

    out = {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "arms": [{**a, "read": len(ans[a["id"]])} for a in ARMS],
        "shared": {"n": n_sh, "arms": share},
        "pairs": pairs, "either": either, "size": size, "cost": costs, "hand": hand,
        "control": control, "caveats": caveats, "prompts": prompts(s55_runs, led),
        "withheld": {"n": sum(1 for k in detail if "t" not in detail[k]), "note": WITHHELD_NOTE},
        "rows": rows,
    }
    for p, obj in ((OUT, out), (DETAIL, detail)):
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
        os.replace(tmp, p)
    print(f"wrote {OUT.name} ({OUT.stat().st_size / 1e3:.0f} KB) and {DETAIL.name} "
          f"({DETAIL.stat().st_size / 1e3:.0f} KB): {len(rows)} images")
    print(f"  read: " + ", ".join(f"{a} {len(ans[a])}" for a in IDS) + f"; shared {n_sh}")
    for s in share:
        print(f"  shared {s['id']}: {s['exact']}/{n_sh} = {s['pct']}%")
    for p_ in pairs:
        print(f"  {p_['a']} vs {p_['b']} n={p_['n']}: {p_['a_exact']} vs {p_['b_exact']} "
              f"(only {p_['a_only']} / {p_['b_only']}, p={p_['p']})")
    print(f"  cost: " + ", ".join(f"{c['id']} {c['usd']} (n {c['n']})" for c in costs))
    print(f"  CXMolScribe verdicts that differ from corpus_rows.json: {cx_drift}; pred tiles missing: {missing}")
    print(f"  withheld references: {out['withheld']['n']}; caveats: {len(caveats)}; control: {bool(control)}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    sys.exit(build())
