#!/usr/bin/env python3
"""How the Sonnet readers actually work: every tool call of every scored reader, classified.

    build_technique.py            rebuild benchmarks/wall/technique.json
    build_technique.py --no-cache re-parse every transcript (the cache only skips unchanged files)

Each Sonnet reader is a headless agent that reads ten blind images and writes SMILES. Its
transcript records every tool call, so HOW it read can be measured, not asked about (readers'
own accounts of what they used are wrong in both directions; see scan_reader_transcript.py).

WHAT IS COUNTED. Every tool_use block, in order, gets exactly one kind for the tool mix:

    R  Read of a blind source image (the whole drawing)
    C  a command that crops or zooms (PIL .crop/.resize, ImageMagick -crop/-resize)
    c  a Read of an image a crop command made (a crop viewed)
    D  a command that renders a molecule to a picture (RDKit MolDraw2D / MolToImage / Draw.*)
    d  a Read of an image a render command made (the answer drawn back and LOOKED AT)
    K  RDKit used without drawing: MolFromSmiles, canonical SMILES, formula, atom counts
    O  OSRA (or another local OCSR tool) actually run on an image
    W  the answers file written or edited
    X  anything else: setup, installs, `identify`, notes, reads of text files

A command often does several of these. The mix takes the first that applies in the order
O, D, C, W, K, X; the per-reader flags (used RDKit, drew back, ...) look at every label, so a
render script that also canonicalises counts as RDKit use too.

SCRIPTS. Readers write helpers (`cat > check.py << EOF`, or the Write tool) and call them
later (`python check.py 3 'CCO'`, `from check import render`). The call has none of the code in
it, so each helper's text is remembered and a call is classified by its own text PLUS every
helper it invokes, transitively.

WHICH IMAGE. A call belongs to image N when it names exactly one blind image (`fig05`, `img05`,
`/tmp/.../fig05.png`), or, for a Read of a derived picture, when the file name starts with a
two-digit image number (`c05_a.png`, `ov02.png`). A call that names several images (a loop over
all ten, the answers file) is batch-level. A call that names none inherits the image the reader
was last working on, because readers work one image at a time. "Calls per image" and "crops per
image" count only attributed calls.

THINKING is redacted in transcripts (only its signature is kept), so its length is not
measurable. Output tokens, which include thinking, are reported instead.

TOKENS are deduplicated by message id (one record per content block repeats the usage) and
priced at list rates, which are the same for Sonnet 5 and 5.5 (sonnet_cost.py).

CACHE. Parsing ~1.2 GB of transcripts takes a while, so each reader's parse is cached in
/root/cmage-work/technique_cache.json keyed by size and mtime; a new lane reader costs one
transcript. A reader whose transcript has gone keeps its cached parse, even across a
PARSER_VERSION bump.

This script only reads: results files, ledgers and transcripts. It never writes anything a
scorer reads.
"""
import glob
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent / "benchmarks"
OUT = BENCH / "wall" / "technique.json"
CACHE = Path("/root/cmage-work/technique_cache.json")
PARSER_VERSION = 10          # bump when the classification changes: invalidates the cache

PRICE = {"input": 2.00, "output": 10.00, "cache_write_5m": 2.50, "cache_write_1h": 4.00,
         "cache_read": 0.20}
KINDS = [  # code, label, shown in the mix
    ("R", "Read the whole image"),
    ("C", "Crop / zoom command"),
    ("c", "Viewed a crop"),
    ("K", "RDKit check (no drawing)"),
    ("D", "Render answer"),
    ("d", "Viewed the render"),
    ("O", "OSRA run"),
    ("W", "Write answers"),
    ("X", "Other"),
]
# The mix groups the nine codes into seven: a crop command and the crop it produced are one
# technique, and so are a render and looking at it.
GROUPS = [("read", "Read whole image", "R"), ("crop", "Crop & zoom", "Cc"),
          ("rdkit", "RDKit check", "K"), ("draw", "Draw back & compare", "Dd"),
          ("osra", "OSRA", "O"), ("write", "Write answers", "W"), ("other", "Other", "X")]

RX_CROP = re.compile(r"\.crop\(|\s-crop\s|gridcrop|\bcrop\(|\.resize\(|\s-resize\s|\s-scale\s"
                     r"|LANCZOS|BICUBIC|\.thumbnail\(", re.I)
RX_RENDER = re.compile(r"MolDraw2D|MolToImage|MolToFile|Draw\.Mol|MolsToGridImage|DrawMolecule"
                       r"|rdMolDraw2D|Draw\.MolToImage|ReactionToImage")
RX_RDKIT = re.compile(r"MolFromSmiles|MolToSmiles|CalcMolFormula|rdMolDescriptors|Descriptors\."
                      r"|GetNumAtoms|GetNumHeavyAtoms|MolFromMolBlock|FindMolChiralCenters"
                      r"|AssignStereochemistry|MolToInchi|InchiToInchiKey|Chem\.\w+\(")
RX_OCSR = re.compile(r"\b(osra|decimer|molscribe|imago_console|molvec|img2mol)\b", re.I)
RX_PROBE = re.compile(r"\b(which|whereis|type|command -v|apt|apt-get|apt-cache|dpkg|pip3?|uv)\b"
                      r"[^\n;|&]*\b(osra|decimer|molscribe|imago|molvec)\b|--help|--version|-h\b", re.I)
RX_PIXCMP = re.compile(r"ImageChops|absdiff|np\.abs\(|\.difference\(|overlay|blend|IoU|iou\b", re.I)
RX_ANSWERS = re.compile(r"/tmp/(?:sonnet_answers|answers)\w*\.json")
RX_PNG = re.compile(r"[\w\-.%{}]+\.png")
RX_HEREDOC = re.compile(r"(?:cat|tee)\s*>{1,2}\s*([^\s<>;|&]+)\s*<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n\s*\2\s*(?:\n|$)",
                        re.S)
ANSWER_PAIR = re.compile(r"""["']img["']\s*:\s*["']((?:img|fig)\d\d)["']\s*,\s*["']smiles["']\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|null|None)""")


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def ts(s):
    try:
        return time.mktime(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ one transcript
def parse(path: str) -> dict:
    recs = []
    with open(path, errors="replace") as fh:
        for line in fh:
            try:
                recs.append(json.loads(line))
            except ValueError:
                pass
    prompt = ""
    for r in recs:
        if r.get("type") == "user":
            c = (r.get("message") or {}).get("content")
            prompt = c if isinstance(c, str) else " ".join(
                b.get("text", "") for b in (c or []) if isinstance(b, dict))
            break
    blind = re.findall(r"(/tmp/blind\w*/)((?:img|fig))(\d\d)\.png", prompt)
    stem = blind[0][1] if blind else "img"
    n_img = len({b[2] for b in blind}) or 10
    rx_ref = re.compile(r"(?<![A-Za-z0-9])" + stem + r"_?(\d{2})(?!\d)")
    rx_loop = re.compile(stem + r"(?:%02d|\{|\$\{?i|\$i|\*)")
    rx_blind = re.compile(r"/tmp/blind\w*/" + stem + r"(\d\d)\.png")

    scripts: dict[str, str] = {}      # basename -> text
    produced: dict[str, str] = {}     # png basename -> "C" | "D"
    last_img_kind = None
    focus = 0
    steps = []                        # [code, img, t]
    seen_msg = {}
    models, efforts = set(), set()
    t0 = t1 = None
    thinking = 0
    flags = Counter()
    every = []

    used_scripts: set = set()

    def expand(text: str) -> str:
        used_scripts.clear()
        out, todo, done = [text], [text], set()
        while todo:
            t = todo.pop()
            for name, body in scripts.items():
                if name in done:
                    continue
                mod = name[:-3] if name.endswith(".py") else name
                # RUN, not mentioned: `python x.py`, `./x.py`, `bash x.sh`, `from x import`,
                # `exec(open('x.py'`. A note that names a helper is not a call to it.
                if re.search(r"(?:python[\w.]*|bash|sh|exec\(open\()\s*[^\n;|&]*?\b" + re.escape(name)
                             + r"\b|(?:^|[\s;&|])\./?\S*" + re.escape(name) + r"\b", t) or (
                        name.endswith(".py") and re.search(
                            r"^\s*(?:from\s+" + re.escape(mod) + r"\s+import|import\s+" + re.escape(mod) + r"\b)",
                            t, re.M)):
                    done.add(name)
                    used_scripts.add(name)
                    out.append(body)
                    todo.append(body)
        return "\n".join(out)

    def refs(text: str) -> set:
        nums = {int(m) for m in rx_ref.findall(text)}
        nums = {n for n in nums if 1 <= n <= n_img}
        if rx_loop.search(text):
            nums |= {-1}
        return nums

    for r in recs:
        stamp = ts(r.get("timestamp"))
        if r.get("type") == "user":
            every.extend(strings((r.get("message") or {}).get("content")))
            continue
        if r.get("type") != "assistant":
            continue
        m = r.get("message") or {}
        mdl = m.get("model")
        if mdl and mdl != "<synthetic>":
            models.add(mdl)
        if r.get("effort"):
            efforts.add(r["effort"])
        if stamp:
            t0 = stamp if t0 is None else min(t0, stamp)
            t1 = stamp if t1 is None else max(t1, stamp)
        u = m.get("usage")
        if u and m.get("id") and mdl != "<synthetic>":
            seen_msg[m["id"]] = u
        for b in m.get("content") or []:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "thinking":
                thinking += 1
                continue
            if b.get("type") != "tool_use":
                continue
            every.extend(strings(b.get("input")))
            name, inp = b.get("name"), b.get("input") or {}
            t = round(stamp - t0) if (stamp and t0) else 0
            code, img = "X", 0
            if name == "Read":
                fp = str(inp.get("file_path", ""))
                base = os.path.basename(fp)
                mb = rx_blind.search(fp)
                if mb:
                    code, img = "R", int(mb.group(1))
                elif base.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    code = produced.get(base) or last_img_kind or "X"
                    code = code.lower() if code in "CD" else "X"
                    nums = refs(fp)
                    if len(nums) == 1 and -1 not in nums:
                        img = nums.pop()
                    else:
                        mm = re.match(r"^[A-Za-z]{0,10}?_?(\d{2})(?:[_\-.a-zA-Z]|$)", base)
                        if mm and 1 <= int(mm.group(1)) <= n_img:
                            img = int(mm.group(1))
                else:
                    code = "X"
                    nums = refs(fp)
                    if len(nums) == 1 and -1 not in nums:
                        img = nums.pop()
                if code == "c":
                    flags["crop"] += 1
                if code == "d":
                    flags["drawback_viewed"] += 1
            elif name in ("Bash", "Write", "Edit", "MultiEdit", "NotebookEdit"):
                defined = set()
                if name == "Bash":
                    text = str(inp.get("command", ""))
                    if re.search(r"\b(pip3?|uv pip|uv venv|python3? -m venv|conda)\b[^\n]*\b(install|venv|create)\b", text):
                        flags["install"] += 1
                    for hd in RX_HEREDOC.finditer(text):
                        defined.add(os.path.basename(hd.group(1)))
                        scripts[os.path.basename(hd.group(1))] = hd.group(3)
                else:
                    fp = str(inp.get("file_path", ""))
                    body = str(inp.get("content", "")) + str(inp.get("new_string", ""))
                    if fp.endswith((".py", ".sh")):
                        if name == "Write":
                            scripts[os.path.basename(fp)] = body
                        else:
                            scripts[os.path.basename(fp)] = scripts.get(os.path.basename(fp), "") + "\n" + body
                    text = fp + "\n" + body
                full = expand(text)
                if used_scripts - defined:
                    flags["helper_reuse"] += 1
                lab = set()
                if RX_OCSR.search(full) and not RX_PROBE.search(text) and (
                        ".png" in full or "subprocess" in full or "$" in text):
                    lab.add("O")
                if RX_RENDER.search(full):
                    lab.add("D")
                if RX_CROP.search(full) and (".png" in full or "Image" in full or "convert" in full):
                    lab.add("C")
                if RX_ANSWERS.search(text):
                    lab.add("W")
                if RX_RDKIT.search(full):
                    lab.add("K")
                for code_ in ("O", "D", "C", "W", "K"):
                    if code_ in lab:
                        code = code_
                        break
                if "K" in lab or "D" in lab:
                    flags["rdkit"] += 1
                if "D" in lab:
                    flags["drawback"] += 1
                    if RX_PIXCMP.search(full) and rx_blind.search(full) or (
                            RX_PIXCMP.search(full) and "Image.open" in full):
                        flags["pixel_compare"] += 1
                if "C" in lab:
                    flags["crop_cmd"] += 1
                if "ImageDraw" in full and re.search(r"grid", full, re.I):
                    flags["grid"] += 1
                if "O" in lab:
                    flags["osra"] += 1
                if "C" in lab or "D" in lab:
                    kind = "D" if "D" in lab else "C"
                    for png in RX_PNG.findall(full):
                        if not rx_blind.search("/tmp/blind/" + png):
                            produced[os.path.basename(png)] = kind
                    last_img_kind = kind
                nums = refs(text if name == "Bash" else inp.get("file_path", "") + text)
                if len(nums) == 1 and -1 not in nums:
                    img = nums.pop()
                elif nums:
                    img = -1            # batch-level: several images at once
            elif name in ("Agent", "Task"):
                flags["delegated"] += 1
            if img == 0 and focus and code != "W":
                img = focus
            if img > 0:
                focus = img
            steps.append([code, img, t])

    tok = Counter()
    for u in seen_msg.values():
        tok["input"] += u.get("input_tokens", 0) or 0
        tok["output"] += u.get("output_tokens", 0) or 0
        tok["cache_read"] += u.get("cache_read_input_tokens", 0) or 0
        cc = u.get("cache_creation") or {}
        if cc:
            tok["cache_write_5m"] += cc.get("ephemeral_5m_input_tokens", 0) or 0
            tok["cache_write_1h"] += cc.get("ephemeral_1h_input_tokens", 0) or 0
        else:
            tok["cache_write_5m"] += u.get("cache_creation_input_tokens", 0) or 0
    cost = sum(tok[k] * PRICE[k] for k in PRICE) / 1e6

    answers = defaultdict(list)
    for s in every:
        if "smiles" not in s:
            continue
        for a in ANSWER_PAIR.finditer(s):
            raw = a.group(2)
            if raw in ("null", "None"):
                continue
            try:
                smi = json.loads(raw) if raw[0] == '"' else raw[1:-1].encode().decode("unicode_escape")
            except ValueError:
                continue
            if smi and smi not in answers[a.group(1)]:
                answers[a.group(1)].append(smi)

    low = prompt.lower()
    return {
        "path": path, "stem": stem, "n_img": n_img, "steps": steps,
        "models": sorted(models), "effort": sorted(efforts),
        "t0": t0, "secs": round(t1 - t0) if (t0 and t1) else None,
        "tokens": dict(tok), "requests": len(seen_msg), "cost": round(cost, 4),
        "thinking_blocks": thinking, "flags": dict(flags), "answers": dict(answers),
        "prompt_asks": {"crop": bool(re.search(r"\bcrop|zoom", low)),
                        "render": bool(re.search(r"render|draw (it|your answer|the smiles) back|visually (diff|compare)", low)),
                        "osra": "osra" in low},
    }


# ------------------------------------------------------------------ who read what
def load_jsonl(p):
    p = Path(p)
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def jload(p, default=None):
    p = Path(p)
    return json.load(open(p)) if p.exists() else default


def lanes() -> dict:
    """lane -> {aid: {"batch": .., "rows": [ {k, v, conf, slot|None, s} ]}}"""
    out = {}
    # Sonnet 5 arm: the published rows, credited to readers by sonnet_cost's per-key map.
    cost = jload(BENCH / "sonnet_cost.json", {})
    readers = [r["agent"] for r in cost.get("readers", [])]
    by_prefix = {a[:8]: a for a in readers}
    s5 = defaultdict(lambda: {"rows": []})
    for i, r in enumerate(load_jsonl("/root/cmage-work/sonnet/results.jsonl")):
        pk = (cost.get("per_key") or {}).get(r["k"])
        aid = by_prefix.get((pk or {}).get("reader", ""))
        if not aid:
            continue
        s5[aid]["rows"].append({"k": r["k"], "v": r.get("sonnet_verdict"), "conf": r.get("sonnet_conf"),
                                "s": r.get("sonnet_smiles"), "slot": None, "truth": r.get("truth"),
                                "ocr": r.get("ocr_verdict")})
        s5[aid]["batch"] = (pk or {}).get("batch")
    out["s5"] = dict(s5)

    def ledger_lane(lane, ledger_path, results_path, key="runs"):
        led = (jload(ledger_path, {}) or {}).get(key, {})
        rows = {r["k"]: r for r in load_jsonl(results_path)}
        d = {}
        for aid, run in led.items():
            rr = []
            for k in run.get("keys", []):
                r = rows.get(k)
                if r:
                    rr.append({"k": k, "v": r.get("sonnet_verdict"), "conf": r.get("sonnet_conf"),
                               "s": r.get("sonnet_smiles"), "slot": r.get("slot"), "truth": r.get("truth"),
                               "ocr": r.get("ocr_verdict")})
            if rr:
                d[aid] = {"rows": rr, "batch": run.get("batch")}
        out[lane] = d

    ledger_lane("s55c", BENCH / "sonnet55c_runs.json", "/root/cmage-work/sonnet-s55c/results.jsonl")
    ledger_lane("s55", BENCH / "sonnet55_runs.json", "/root/cmage-work/sonnet-s55/results.jsonl")
    ledger_lane("nov", BENCH / "novel_runs.json", "/root/cmage-work/sonnet-nov/results.jsonl")
    # Same-prompt Sonnet 5 re-runs of the hand-picked images (side readings on /sonnet-compare).
    side = defaultdict(lambda: {"rows": []})
    s55rows = {r["k"]: r for r in load_jsonl("/root/cmage-work/sonnet-s55/results.jsonl")}
    for sd in (jload(BENCH / "sonnet55_runs.json", {}) or {}).get("side", []):
        for k, rd in (sd.get("reads") or {}).items():
            side[sd["agent"]]["rows"].append({"k": k, "v": rd.get("v"), "conf": rd.get("conf"), "s": rd.get("s"),
                                              "slot": None, "truth": (s55rows.get(k) or {}).get("truth"),
                                              "ocr": (s55rows.get(k) or {}).get("ocr_verdict")})
            side[sd["agent"]]["batch"] = sd.get("batch")
    out["s5r"] = dict(side)
    return out


LANE_META = {
    "s5": {"label": "Sonnet 5", "model": "claude-sonnet-5", "note": "the published Sonnet 5 arm, whole corpus"},
    "s55c": {"label": "Sonnet 5.5", "model": "claude-sonnet-5-5", "note": "the corpus lane, in corpus order"},
    "s55": {"label": "Sonnet 5.5, hand-picked", "model": "claude-sonnet-5-5",
            "note": "28 images picked on Sonnet 5's failures"},
    "nov": {"label": "Sonnet 5.5, novel", "model": "claude-sonnet-5-5", "note": "20 edited or new molecules"},
    "s5r": {"label": "Sonnet 5, re-run", "model": "claude-sonnet-5",
            "note": "same prompt and images as the hand-picked 5.5 readers"},
}


# ------------------------------------------------------------------ helpers
_HA = {}
try:
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")
except Exception:
    pass


def heavy_atoms(smi):
    if smi in _HA:
        return _HA[smi]
    n = None
    try:
        from rdkit import Chem, RDLogger
        RDLogger.DisableLog("rdApp.*")
        m = Chem.MolFromSmiles(smi or "")
        n = m.GetNumHeavyAtoms() if m else None
    except Exception:
        n = None
    _HA[smi] = n
    return n


def canon(smi):
    try:
        from rdkit import Chem
        m = Chem.MolFromSmiles(smi or "")
        return Chem.MolToSmiles(m) if m else None
    except Exception:
        return None


def slot_rows(rec: dict, rows: list) -> None:
    """Give each row its image number. Lane rows carry a slot; Sonnet 5 rows are matched to the
    reader's own answers by SMILES (as written, then canonical)."""
    stem = rec["stem"]
    for r in rows:
        if r.get("slot"):
            r["img"] = int(r["slot"][-2:])
    todo = [r for r in rows if not r.get("img")]
    if not todo:
        return
    ans = rec.get("answers") or {}
    by_smi = defaultdict(set)
    for slot, smis in ans.items():
        for s in smis:
            by_smi[s].add(int(slot[-2:]))
    taken = {r["img"] for r in rows if r.get("img")}
    for r in todo:
        c = by_smi.get(r.get("s") or "", set()) - taken
        if len(c) == 1:
            r["img"] = c.pop()
            taken.add(r["img"])
    todo = [r for r in rows if not r.get("img")]
    if todo:
        canon_map = defaultdict(set)
        for slot, smis in ans.items():
            for s in smis:
                cs = canon(s)
                if cs:
                    canon_map[cs].add(int(slot[-2:]))
        for r in todo:
            c = canon_map.get(canon(r.get("s")) or "", set()) - taken
            if len(c) == 1:
                r["img"] = c.pop()
                taken.add(r["img"])
    todo = [r for r in rows if not r.get("img") and r.get("s") and len(r["s"]) >= 4
            and r["s"].upper() != "UNREADABLE"]
    if not todo:
        return
    # Last resort, for readers that built the answers file in code: find the SMILES itself in
    # the transcript and take the image named closest before it. Cached per SMILES.
    hints = rec.setdefault("hints", {})
    need = [r["s"] for r in todo if r["s"] not in hints]
    if need and rec.get("path") and os.path.exists(rec["path"]):
        rx = re.compile(r"(?<![A-Za-z0-9])" + stem + r"_?(\d{2})(?!\d)")
        votes = defaultdict(Counter)
        for line in open(rec["path"], errors="replace"):
            if not any(s[:40] in line for s in need):
                continue
            try:
                r_ = json.loads(line)
            except ValueError:
                continue
            for text in strings((r_.get("message") or {}).get("content")):
                for s in need:
                    pos = text.find(s)
                    while pos >= 0:
                        before = list(rx.finditer(text, max(0, pos - 400), pos))
                        if before:
                            votes[s][int(before[-1].group(1))] += 1
                        pos = text.find(s, pos + 1)
        for s in need:
            hints[s] = votes[s].most_common(1)[0][0] if votes[s] else None
    for r in todo:
        i = hints.get(r["s"])
        if i and i not in taken:
            r["img"] = i
            taken.add(i)


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def pct(a, b):
    return round(100 * a / b, 1) if b else None


def quart(xs):
    xs = sorted(xs)
    if not xs:
        return None
    q = lambda p: xs[min(len(xs) - 1, max(0, int(round(p * (len(xs) - 1)))))]
    return [q(0.25), q(0.5), q(0.75)]


# ------------------------------------------------------------------ build
def build(use_cache=True) -> int:
    idx = {}
    for p in glob.glob("/root/.claude/projects/*/*/subagents/agent-*.jsonl"):
        idx[os.path.basename(p)[6:-6]] = p
    cache = {}
    if use_cache and CACHE.exists():
        try:
            cache = json.load(open(CACHE))
        except ValueError:
            cache = {}
        if cache.get("_v") != PARSER_VERSION:
            # Keep the parse of any reader whose transcript has since been deleted: an old
            # classification beats losing the reader.
            cache = {a: c for a, c in cache.items() if a != "_v" and a not in idx}

    L = lanes()
    readers, image_rows = [], []
    parsed_new = 0
    missing = []
    for lane, group in L.items():
        for aid, info in group.items():
            p = idx.get(aid)
            c = cache.get(aid)
            if not p and not c:
                missing.append(aid)
                continue
            st = os.stat(p) if p else None
            stamp = f"{st.st_size}:{int(st.st_mtime)}" if st else None
            if c and (c.get("_stamp") == stamp or not p):
                rec = c
            else:
                rec = parse(p)
                rec["_stamp"] = stamp
                cache[aid] = rec
                parsed_new += 1
            rows = [dict(r) for r in info["rows"]]
            slot_rows(rec, rows)
            steps = rec["steps"]
            n = rec["n_img"]
            per = defaultdict(Counter)
            # OSRA is almost always run over every image in one loop, so a batch-level run
            # counts for each image.
            osra_all = any(code == "O" and img == -1 for code, img, _t in steps)
            for code, img, _t in steps:
                if img and img > 0:
                    per[img][code] += 1
            imgs_out = []
            for r in rows:
                i = r.get("img")
                pc = per.get(i, Counter()) if i else Counter()
                ha = heavy_atoms(r.get("truth"))
                imgs_out.append({
                    "k": r["k"], "img": i, "v": r.get("v"), "exact": r.get("v") == "exact",
                    "conf": r.get("conf"), "ha": ha, "ocr": r.get("ocr"),
                    "calls": sum(pc.values()) if i else None,
                    "crops": pc["c"] if i else None, "crop_cmds": pc["C"] if i else None,
                    "rdkit": (pc["K"] + pc["D"] + pc["d"]) > 0 if i else None,
                    "drawn": (pc["D"] + pc["d"]) > 0 if i else None,
                    "viewed_render": pc["d"] > 0 if i else None,
                    "osra": (pc["O"] > 0 or osra_all) if i else None,
                    "reads": pc["R"] if i else None,
                })
            mix = Counter(code for code, _i, _t in steps)
            att = sum(1 for _c, i, _t in steps if i and i > 0)
            batch_lvl = sum(1 for _c, i, _t in steps if i == -1)
            fl = rec["flags"]
            exact = sum(1 for r in imgs_out if r["exact"])
            # first-phase shape: did it read every image before doing anything else?
            first_reads = 0
            for code, img, _t in steps:
                if code == "R":
                    first_reads += 1
                else:
                    break
            seq_codes = "".join(s[0] for s in steps)
            seq_imgs = [s[1] for s in steps]
            seq_t = [s[2] for s in steps]
            readers.append({
                "aid": aid, "lane": lane, "batch": info.get("batch"),
                "models": rec["models"], "effort": rec["effort"],
                "n_img": len(imgs_out), "exact": exact,
                "calls": len(steps), "attributed": att, "batch_level": batch_lvl,
                "mix": {k: mix.get(k, 0) for k, _ in KINDS},
                "secs": rec["secs"], "cost": rec["cost"], "tokens": rec["tokens"],
                "requests": rec["requests"], "thinking_blocks": rec["thinking_blocks"],
                "used": {"crop": fl.get("crop", 0) > 0 or fl.get("crop_cmd", 0) > 0,
                         "crop_viewed": fl.get("crop", 0) > 0,
                         "rdkit": fl.get("rdkit", 0) > 0,
                         "drawback": fl.get("drawback", 0) > 0,
                         "drawback_viewed": fl.get("drawback_viewed", 0) > 0,
                         "pixel_compare": fl.get("pixel_compare", 0) > 0,
                         "grid": fl.get("grid", 0) > 0,
                         "install": fl.get("install", 0) > 0,
                         "helper": fl.get("helper_reuse", 0) > 0,
                         "osra": fl.get("osra", 0) > 0},
                "prompt_asks": rec["prompt_asks"],
                "read_all_first": first_reads >= n,
                "t0": rec["t0"],
                "seq": seq_codes, "seq_img": seq_imgs, "seq_t": seq_t,
                "images": imgs_out,
            })
    cache["_v"] = PARSER_VERSION
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".tmp")
        json.dump(cache, open(tmp, "w"))
        os.replace(tmp, CACHE)
    except OSError as e:
        print(f"cache not written: {e}", file=sys.stderr)

    payload = summarise(readers)
    payload["missing_transcripts"] = missing
    tmp = OUT.with_suffix(".tmp")
    json.dump(payload, open(tmp, "w"), separators=(",", ":"))
    os.replace(tmp, OUT)
    s = payload["lanes"]
    print(f"technique: {len(readers)} readers ({parsed_new} parsed, rest cached), "
          + ", ".join(f"{k} {v['readers']}r/{v['images']}i" for k, v in s.items())
          + f"; {OUT.stat().st_size // 1024} KB")
    if missing:
        print(f"  no transcript and no previous record: {len(missing)} ({', '.join(missing[:5])})")
    return 0


def lane_stats(rs: list) -> dict:
    imgs = [i for r in rs for i in r["images"]]
    att = [i for i in imgs if i["img"]]
    mix = Counter()
    for r in rs:
        mix.update(r["mix"])
    tot = sum(mix.values())
    g = {}
    for key, label, codes in GROUPS:
        g[key] = sum(mix[c] for c in codes)
    n_img = sum(r["n_img"] for r in rs)
    used = {k: sum(1 for r in rs if r["used"][k]) for k in rs[0]["used"]} if rs else {}
    calls_img = [i["calls"] for i in att]
    crops_img = [i["crops"] for i in att]
    out = {
        "readers": len(rs), "images": n_img, "exact": sum(i["exact"] for i in imgs),
        "exact_pct": pct(sum(i["exact"] for i in imgs), n_img),
        "calls": tot, "calls_per_image": round(tot / n_img, 1) if n_img else None,
        "mix": g, "mix_pct": {k: pct(v, tot) for k, v in g.items()},
        "mix_per_image": {k: round(v / n_img, 2) if n_img else None for k, v in g.items()},
        "codes": dict(mix),
        "attributed_images": len(att),
        "attributed_share": pct(sum(r["attributed"] for r in rs), tot),
        "calls_img_q": quart(calls_img), "crops_img_q": quart(crops_img),
        "crops_img_mean": round(sum(crops_img) / len(crops_img), 2) if crops_img else None,
        "img_with_crop_pct": pct(sum(1 for c in crops_img if c), len(crops_img)),
        "img_drawn_pct": pct(sum(1 for i in att if i["drawn"]), len(att)),
        "img_viewed_render_pct": pct(sum(1 for i in att if i["viewed_render"]), len(att)),
        "img_osra_pct": pct(sum(1 for i in att if i["osra"]), len(att)),
        "used": used, "used_pct": {k: pct(v, len(rs)) for k, v in used.items()},
        "read_all_first_pct": pct(sum(1 for r in rs if r["read_all_first"]), len(rs)),
        "secs_per_image": round(sum(r["secs"] or 0 for r in rs) / n_img) if n_img else None,
        "cost_per_image": round(sum(r["cost"] or 0 for r in rs) / n_img, 3) if n_img else None,
        "out_tok_per_image": round(sum((r["tokens"] or {}).get("output", 0) for r in rs) / n_img) if n_img else None,
        "reader_minutes_q": quart([round((r["secs"] or 0) / 60, 1) for r in rs]),
        "prompt_asks_render_pct": pct(sum(1 for r in rs if r["prompt_asks"]["render"]), len(rs)),
        "prompt_asks_crop_pct": pct(sum(1 for r in rs if r["prompt_asks"]["crop"]), len(rs)),
    }
    o_steps = [(c, i) for r in rs for c, i in zip(r["seq"], r["seq_img"]) if c == "O"]
    out["osra_batch_pct"] = pct(sum(1 for _c, i in o_steps if i == -1), len(o_steps))
    firstw = [r["seq"].find("W") / len(r["seq"]) for r in rs if "W" in r["seq"]]
    out["answers_late_pct"] = pct(sum(1 for x in firstw if x >= 0.8), len(firstw))
    out["calls_hist"] = hist(calls_img, [(0, 2), (3, 5), (6, 10), (11, 20), (21, 40), (41, 10 ** 9)])
    out["crops_hist"] = hist(crops_img, [(0, 0), (1, 1), (2, 2), (3, 5), (6, 10), (11, 10 ** 9)])
    return out


def hist(xs, bins):
    res = []
    for lo, hi in bins:
        n = sum(1 for x in xs if lo <= x <= hi)
        lab = (f"{lo}" if lo == hi else f"{lo}+" if hi > 10 ** 8 else f"{lo}–{hi}")
        res.append({"bin": lab, "n": n, "pct": pct(n, len(xs))})
    return res


SIZE_BINS = [("small", "under 25 heavy atoms", 0, 24), ("medium", "25–44", 25, 44), ("large", "45 or more", 45, 10 ** 6)]


def technique_vs_exact(rs: list) -> list:
    """Exact rate with and without a technique on the SAME image, within size bins, so a
    technique that hard images attract is not mistaken for one that fails."""
    imgs = [i for r in rs for i in r["images"] if i["img"] and i["ha"] is not None]
    out = []
    tests = [("crop", "Cropped at least once", lambda i: (i["crops"] or 0) > 0),
             ("crop3", "Three or more crops", lambda i: (i["crops"] or 0) >= 3),
             ("drawn", "Answer drawn back", lambda i: bool(i["drawn"])),
             ("viewed", "Render looked at", lambda i: bool(i["viewed_render"])),
             ("osra", "OSRA run on it", lambda i: bool(i["osra"]))]
    for key, label, f in tests:
        row = {"key": key, "label": label, "bins": []}
        for bk, blabel, lo, hi in SIZE_BINS:
            sub = [i for i in imgs if lo <= i["ha"] <= hi]
            yes = [i for i in sub if f(i)]
            no = [i for i in sub if not f(i)]
            row["bins"].append({"bin": bk, "label": blabel,
                                "yes_n": len(yes), "yes_exact": sum(i["exact"] for i in yes),
                                "yes_pct": pct(sum(i["exact"] for i in yes), len(yes)),
                                "no_n": len(no), "no_exact": sum(i["exact"] for i in no),
                                "no_pct": pct(sum(i["exact"] for i in no), len(no))})
        yes = [i for i in imgs if f(i)]
        no = [i for i in imgs if not f(i)]
        row["all"] = {"yes_n": len(yes), "yes_pct": pct(sum(i["exact"] for i in yes), len(yes)),
                      "no_n": len(no), "no_pct": pct(sum(i["exact"] for i in no), len(no)),
                      "yes_ha": median([i["ha"] for i in yes]), "no_ha": median([i["ha"] for i in no])}
        out.append(row)
    return out


def size_effort(rs: list) -> list:
    """Calls and crops per image by drawing size: effort follows difficulty."""
    imgs = [i for r in rs for i in r["images"] if i["img"] and i["ha"] is not None]
    res = []
    for bk, blabel, lo, hi in SIZE_BINS:
        sub = [i for i in imgs if lo <= i["ha"] <= hi]
        res.append({"bin": bk, "label": blabel, "n": len(sub),
                    "calls_med": median([i["calls"] for i in sub]),
                    "crops_mean": round(sum(i["crops"] for i in sub) / len(sub), 2) if sub else None,
                    "exact_pct": pct(sum(i["exact"] for i in sub), len(sub))})
    return res


def reader_level(rs: list) -> list:
    res = []
    for key, label in [("crop_viewed", "viewed a crop"), ("drawback_viewed", "looked at its answer drawn back"),
                       ("pixel_compare", "diffed render against source in code"), ("osra", "ran OSRA")]:
        yes = [r for r in rs if r["used"][key]]
        no = [r for r in rs if not r["used"][key]]
        f = lambda xs: pct(sum(r["exact"] for r in xs), sum(r["n_img"] for r in xs))
        res.append({"key": key, "label": label, "yes_n": len(yes), "yes_pct": f(yes),
                    "no_n": len(no), "no_pct": f(no)})
    return res


def paired(by_lane: dict) -> dict | None:
    """Sonnet 5 and 5.5 on the SAME images: effort per image with difficulty held fixed."""
    a = {i["k"]: i for r in by_lane.get("s5", []) for i in r["images"] if i["img"]}
    b = {i["k"]: i for r in by_lane.get("s55c", []) for i in r["images"] if i["img"]}
    ks = sorted(set(a) & set(b))
    if not ks:
        return None
    more_calls = sum(1 for k in ks if b[k]["calls"] > a[k]["calls"])
    fewer_calls = sum(1 for k in ks if b[k]["calls"] < a[k]["calls"])
    return {"n": len(ks),
            "s5_calls_med": median([a[k]["calls"] for k in ks]),
            "s55_calls_med": median([b[k]["calls"] for k in ks]),
            "s5_crops_mean": round(sum(a[k]["crops"] for k in ks) / len(ks), 2),
            "s55_crops_mean": round(sum(b[k]["crops"] for k in ks) / len(ks), 2),
            "s5_crop_pct": pct(sum(1 for k in ks if a[k]["crops"]), len(ks)),
            "s55_crop_pct": pct(sum(1 for k in ks if b[k]["crops"]), len(ks)),
            "s5_drawn_pct": pct(sum(1 for k in ks if a[k]["drawn"]), len(ks)),
            "s55_drawn_pct": pct(sum(1 for k in ks if b[k]["drawn"]), len(ks)),
            "s5_viewed_pct": pct(sum(1 for k in ks if a[k]["viewed_render"]), len(ks)),
            "s55_viewed_pct": pct(sum(1 for k in ks if b[k]["viewed_render"]), len(ks)),
            "s5_exact": sum(a[k]["exact"] for k in ks), "s55_exact": sum(b[k]["exact"] for k in ks),
            "s55_more_calls": more_calls, "s55_fewer_calls": fewer_calls}


def typical(rs: list, st: dict) -> list:
    """What most runs do, step by step, in words built from the numbers so it stays true as
    readers land. Phrasing switches on the measured majority, never on the lane name."""
    if not rs:
        return []
    u = st["used_pct"]
    raf = st["read_all_first_pct"]
    sz = {b["bin"]: b for b in st["by_size"]}
    sm, lg = sz.get("small") or {}, sz.get("large") or {}
    fmt = lambda x: ("%g" % round(x, 1)) if x is not None else "?"
    lines = []
    if raf >= 50:
        lines.append(f"Opens every image back to back before using any tool ({raf:.0f}% of readers).")
    else:
        lines.append(f"Opens the first image and works it to an answer before opening the next "
                     f"({100 - raf:.0f}% of readers).")
    setup = []
    if u.get("install", 0) >= 20:
        setup.append(f"installs RDKit or a venv itself ({u['install']:.0f}%)")
    if u.get("helper", 0) >= 50:
        setup.append(f"writes a small Python helper once and re-runs it per image ({u['helper']:.0f}%)")
    if u.get("grid", 0) >= 30:
        setup.append(f"lays a pixel grid over the drawing to read coordinates ({u['grid']:.0f}%)")
    if setup:
        lines.append("Sets up: " + "; ".join(setup) + ".")
    lines.append(f"Small drawings (under 25 heavy atoms) take a median {fmt(sm.get('calls_med'))} tool "
                 f"call{'' if sm.get('calls_med') == 1 else 's'} each; "
                 f"from 45 atoms up, {fmt(lg.get('calls_med'))}, with {fmt(lg.get('crops_mean'))} crops viewed per "
                 f"image against {fmt(sm.get('crops_mean'))} on small ones.")
    lines.append(f"Checks the SMILES with RDKit ({u['rdkit']:.0f}% of readers) and draws it back on "
                 f"{st['img_drawn_pct']:.0f}% of images, looking at the render on {st['img_viewed_render_pct']:.0f}%"
                 + (f"; {u['pixel_compare']:.0f}% of readers also diff render and source in code"
                    if u.get("pixel_compare", 0) >= 5 else "") + ".")
    ob = st.get("osra_batch_pct") or 0
    lines.append(f"OSRA is a side check at most: {u['osra']:.0f}% of readers ran it"
                 + (", nearly always once over every image" if ob >= 75 else
                    ", as often on one image as over all of them" if ob >= 35 else ", one image at a time")
                 + ".")
    lines.append(f"Writes the answers file at the end ({st.get('answers_late_pct') or 0:.0f}% of readers first write it "
                 f"in the last fifth of their steps). About {st['secs_per_image'] // 60} min "
                 f"{st['secs_per_image'] % 60:02d} s, {st['out_tok_per_image'] // 1000}k output tokens and "
                 f"${st['cost_per_image']:.2f} per image at list price.")
    return lines


def summarise(readers: list) -> dict:
    by_lane = defaultdict(list)
    for r in readers:
        by_lane[r["lane"]].append(r)
    lanes_out = {}
    for lane in LANE_META:
        rs = by_lane.get(lane) or []
        if not rs:
            continue
        st = lane_stats(rs)
        st.update(LANE_META[lane])
        st["vs_exact"] = technique_vs_exact(rs)
        st["by_size"] = size_effort(rs)
        st["reader_level"] = reader_level(rs)
        st["typical"] = typical(rs, st)
        lanes_out[lane] = st
    slim = []
    for r in sorted(readers, key=lambda r: (list(LANE_META).index(r["lane"]), r.get("t0") or 0)):
        slim.append({
            "aid": r["aid"], "lane": r["lane"], "batch": r["batch"], "n": r["n_img"], "exact": r["exact"],
            "calls": r["calls"], "att": r["attributed"], "mix": r["mix"],
            "min": round((r["secs"] or 0) / 60, 1), "cost": r["cost"],
            "out": (r["tokens"] or {}).get("output", 0), "req": r["requests"],
            "used": r["used"], "asks": r["prompt_asks"], "t0": r.get("t0"),
            "crops": sum(i["crops"] or 0 for i in r["images"]),
            "seq": r["seq"], "si": r["seq_img"], "st": r["seq_t"],
            "img": [[i["img"], i["v"], i["k"], i["crops"], i["calls"], i["ha"]] for i in r["images"]],
            "read_all_first": r["read_all_first"],
        })
    return {
        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kinds": [{"code": c, "label": l} for c, l in KINDS],
        "groups": [{"key": k, "label": l, "codes": c} for k, l, c in GROUPS],
        "lanes": lanes_out,
        "paired": paired(by_lane),
        "size_bins": [{"key": k, "label": l} for k, l, _a, _b in SIZE_BINS],
        "readers": slim,
        "method": [
            "Every tool call in every scored reader's transcript, classified by what it did. A command that "
            "crops and renders counts once in the mix (render wins) but sets both flags.",
            "A call belongs to an image when it names exactly one blind image or a file named after one; a call "
            "naming none inherits the image the reader was last on. Calls naming several images are batch-level.",
            "Thinking is redacted in transcripts, so output tokens (which include it) stand in for it.",
            "Correlation, not causation: harder drawings attract more cropping and more checking, so every "
            "technique-vs-accuracy figure is split by drawing size.",
            "The two models had different prompts. The Sonnet 5.5 prompt names cropping with PIL and an RDKit "
            "parse check; it does not ask for the answer to be drawn back. Most Sonnet 5 prompts did ask for a "
            "re-render.",
        ],
    }


if __name__ == "__main__":
    a = sys.argv[1:]
    if a in ([], ["--no-cache"]):
        sys.exit(build(use_cache=not a))
    raise SystemExit(__doc__)
