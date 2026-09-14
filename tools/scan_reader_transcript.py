#!/usr/bin/env python3
"""Screen a Sonnet reader's transcript for answer-key access BEFORE its batch is scored.

The benchmark's reference answers are PubChem IsomericSMILES. A reader that fetches the
structure of the compound in front of it copies the key instead of reading the drawing,
and the row scores exact for the wrong reason. Readers have done this after being told
not to. Their own reports are wrong in BOTH directions: one denied using RDKit while
importing it in 107 of 110 scripts, and another disclosed a diminazene lookup that its
transcript shows it never made. Only the transcript is evidence.

The first screen was a grep for the PubChem domain. It was checked against a reader whose
five PubChem lookups were known and it recovered all five, yet it would still have passed
a reader that queried KEGG, and one reader had. A check validated only on the one
positive case you happen to have describes the search space too narrowly. So this lists:
- every network target, on any host
- network code that builds its URL at run time
- unvetted tools
- any touch of a path that holds reference answers
- recursive content searches

It does not rule on what is benign. Given the claim (--rows), it maps each finding to
the slots it could have informed, by name, CID, InChIKey skeleton or formula, all
computed from the data.

    scan_reader_transcript.py <agent-id>... [--rows pending_a.json]...
        exit 0  no findings
        exit 1  findings printed; exclude every slot they could inform BEFORE scoring
        exit 2  transcript missing, empty or unreadable; the batch cannot be verified
    scan_reader_transcript.py --selftest
        Every access planted in a synthetic transcript must be caught and mapped to its
        slot. The benign calls every reader makes must not be flagged: the repo's RDKit
        venv, a find for rdkit, reading its own blind images, writing its answers. Run it
        with an RDKit python.
"""
import json
import re
import sys
import tempfile
import urllib.parse
from pathlib import Path

PROJECTS = Path("/root/.claude/projects")
URL = re.compile(r"https?://[^\s\"'\\<>)]+")
NET_CODE = re.compile(r"\burlopen\b|urllib\.request|\brequests\.(?:get|post|Session)\b|http\.client"
                      r"|\bpubchempy\b|\bhttpx\b|\baiohttp\b|socket\.create_connection|chembl_webresource",
                      re.I)
# Where reference answers live on this box. Readers get their toolkit from the RDKit venv
# inside the repo, so the venv is carved out. The rest of the repo is not.
ANSWER_PATH = re.compile(r"/root/cmage-work|/root/C-MAGE(?!/\.venv)|(?:localhost|127\.0\.0\.1):20079"
                         r"|sebland\.com|\b(?:images|sonnet|pdfs)\.json\b|\bresults\.jsonl\b"
                         r"|\bexcluded\.jsonl\b|\bpending_\w*\.json\b")
CONTENT_SEARCH = re.compile(r"\b(?:grep|rg|ag)\b[^|;&\n]*\s-\w*[rR]")
VETTED = {"Bash", "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "ToolSearch", "TodoWrite"}
# URL and query words that name an API, never a compound.
STOP = {"https", "http", "rest", "pug", "pugview", "compound", "compounds", "name", "property", "json",
        "txt", "xml", "csv", "sdf", "png", "isomericsmiles", "canonicalsmiles", "connectivitysmiles",
        "molecularformula", "molecularweight", "iupacname", "inchikey", "inchi", "cids", "cid",
        "fastformula", "fastidentity", "fastsimilarity2d", "fastsubstructure", "smiles", "xrefs",
        "synonyms", "record", "description", "summary", "title", "view", "data", "image", "find",
        "drug", "get", "mol", "www", "api", "search", "query", "molecule", "chemical", "structure",
        "wiki", "index", "pubchemncbinlmnihgov", "restkeggjp", "wwwkeggjp", "wwwebiacuk",
        "cactusncinihgov", "opsinchcamacuk", "enwikipediaorg", "pypiorg", "githubcom"}


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def load_rows(paths: list[str]) -> list[dict]:
    rows = []
    for p in paths:
        text = Path(p).read_text()
        try:
            data = json.loads(text)
            rows += data if isinstance(data, list) else [data]
        except ValueError:
            rows += [json.loads(l) for l in text.splitlines() if l.strip()]
    return rows


def row_ids(rows: list[dict]) -> list[dict]:
    """Everything a lookup could have been keyed on, computed from the claim itself."""
    try:
        from rdkit import Chem, RDLogger
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        RDLogger.DisableLog("rdApp.*")
    except ImportError:
        Chem = None
        print("WARNING: no RDKit -- InChIKey and formula lookups will show as UNMAPPED", file=sys.stderr)
    out = []
    for r in rows:
        ids = {"label": f"{r.get('slot') or '-'} {r.get('name')} [{r.get('k')}]",
               "name": norm(r.get("name", "")), "cid": None, "ik14": set(), "formulas": set()}
        m = re.search(r"_cid(\d+)$", str(r.get("k", "")))
        ids["cid"] = m.group(1) if m else None
        mol = Chem.MolFromSmiles(r["truth"]) if Chem and r.get("truth") else None
        if mol is not None:
            for part in [mol, *Chem.GetMolFrags(mol, asMols=True)]:
                ids["formulas"].add(CalcMolFormula(part))
                ids["ik14"].add(Chem.MolToInchiKey(part)[:14])
        out.append(ids)
    return out


def informs(target: str, rows: list[dict], split_ws: bool = False) -> list[str]:
    t = urllib.parse.unquote(target)
    cids = {c for grp in re.findall(r"(?:/cid/|[?&]cids?=)([\d,]+)", t) for c in grp.split(",") if c}
    iks = set(re.findall(r"\b([A-Z]{14})-[A-Z]{10}-[A-Z]\b", t))
    fmls = set(re.findall(r"\b(C\d*H\d*(?:[A-Z][a-z]?\d*)*)\b", t))
    segs = {norm(s) for s in re.split(r"[\s/?&=,+]+" if split_ws else r"[/?&=,+]+", t)}
    segs = {s for s in segs if len(s) >= 3 and s not in STOP}
    hit = []
    for r in rows:
        n = r["name"]
        by_name = any(s == n or (len(s) >= 5 and len(n) >= 5 and (s in n or n in s)) for s in segs)
        if by_name or (r["cid"] and r["cid"] in cids) or r["ik14"] & iks or r["formulas"] & fmls:
            hit.append(r["label"])
    return hit


def tool_uses(path: Path):
    """Only the reader's own tool calls. The prompt names paths and hosts legitimately."""
    with open(path, errors="replace") as fh:
        for i, line in enumerate(fh, 1):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            content = (rec.get("message") or {}).get("content") if rec.get("type") == "assistant" else None
            for b in content if isinstance(content, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    yield i, b.get("name") or "?", b.get("input") or {}


def scan_file(path: Path, rows: list[dict]) -> tuple[list[dict], int]:
    findings, calls = [], 0
    for line, tool, inp in tool_uses(path):
        calls += 1
        is_cmd = tool == "Bash" and isinstance(inp.get("command"), str)
        text = inp["command"] if is_cmd else json.dumps(inp)

        def add(kind, target, split_ws=False):
            findings.append({"line": line, "tool": tool, "kind": kind, "target": target,
                             "informs": informs(target, rows, split_ws)})

        if tool == "WebFetch":
            add("network", str(inp.get("url")))
        elif tool == "WebSearch":
            add("network", f"search: {inp.get('query')}", split_ws=True)
        else:
            for u in dict.fromkeys(URL.findall(text)):
                add("network", u)
        if tool not in VETTED | {"WebFetch", "WebSearch"}:
            add("unvetted-tool", f"{tool} {json.dumps(inp)[:300]}", split_ws=True)
        if NET_CODE.search(text) and not URL.search(text):
            add("network-code", text[:300], split_ws=True)
        m = ANSWER_PATH.search(text)
        if m:
            add("answer-path", text[max(0, m.start() - 80): m.end() + 80])
        if (is_cmd and CONTENT_SEARCH.search(text)) or \
           (tool == "Grep" and not str(inp.get("path", "")).startswith("/tmp/")):
            add("content-search", text[:300], split_ws=True)
    return findings, calls


def main(argv: list[str]) -> int:
    if argv[1:2] == ["--selftest"]:
        return selftest()
    ids, row_paths, args = [], [], iter(argv[1:])
    for a in args:
        if a == "--rows":
            row_paths.append(next(args))
        elif re.fullmatch(r"\w+", a):
            ids.append(a)
        else:
            print(f"not an agent id: {a!r}")
            return 2
    if not ids:
        print(__doc__)
        return 2
    rows = row_ids(load_rows(row_paths)) if row_paths else []
    worst = 0
    for aid in ids:
        paths = sorted(PROJECTS.rglob(f"agent-{aid}.jsonl"))
        if not paths:
            print(f"[{aid}] NO TRANSCRIPT FOUND -- this batch cannot be verified; do not score it")
            worst = 2
        for p in paths:
            findings, calls = scan_file(p, rows)
            if calls == 0:
                print(f"[{aid}] {p}: zero tool calls -- a reader must at least write its answers, "
                      f"so this cannot be the whole transcript; do not score it")
                worst = 2
                continue
            print(f"[{aid}] {calls} tool calls scanned, {len(findings)} findings  ({p})")
            for f in findings:
                where = "; ".join(f["informs"]) or ("UNMAPPED" if rows else "(no --rows given)")
                print(f"  L{f['line']:<5} {f['kind']:<14} {f['tool']:<10} {f['target'][:170]}")
                print(f"        could inform: {where}")
            if findings:
                worst = max(worst, 1)
    return worst


def selftest() -> int:
    try:
        from rdkit import Chem
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    except ImportError:
        print("selftest needs RDKit: /root/C-MAGE/.venv-ms/bin/python")
        return 2
    raw = [
        {"slot": "img01", "k": "berberine_cid2353", "name": "Berberine",
         "truth": "COC1=C(C2=C[N+]3=C(C=C2C=C1)C4=CC5=C(C=C4CC3)OCO5)OC"},
        {"slot": "img02", "k": "berenil_cid65060", "name": "Berenil",
         "truth": "CC(=O)NCC(=O)O.C1=CC(=CC=C1C(=N)N)NN=NC2=CC=C(C=C2)C(=N)N"},
        {"slot": "img03", "k": "selftest_three", "name": "Aminorex", "truth": "NC1=NCC(O1)c1ccccc1"},
        {"slot": "img04", "k": "selftest_four", "name": "Betahistine", "truth": "CNCCc1ccccn1"},
        {"slot": "img05", "k": "selftest_five", "name": "Beta-Propiolactone", "truth": "O=C1CCO1"},
    ]
    rows = row_ids(raw)
    ik = Chem.MolToInchiKey(Chem.MolFromSmiles(raw[2]["truth"]))
    fml = CalcMolFormula(Chem.MolFromSmiles(raw[4]["truth"]))
    pc = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
    planted = [  # (tool, input, kind that must be reported, slot it must map to)
        ("WebFetch", {"url": f"{pc}/name/Berberine/property/IsomericSMILES/TXT", "prompt": "x"}, "network", "img01"),
        ("Bash", {"command": 'curl -s "https://rest.kegg.jp/find/drug/betahistine"'}, "network", "img04"),
        ("Bash", {"command": f'curl -s "{pc}/inchikey/{ik}/property/IUPACName/JSON"'}, "network", "img03"),
        ("Bash", {"command": f'curl -s "{pc}/fastformula/{fml}/cids/JSON"'}, "network", "img05"),
        ("WebFetch", {"url": f"{pc}/cid/65060/property/IsomericSMILES/TXT", "prompt": "x"}, "network", "img02"),
        ("WebSearch", {"query": "berenil structure smiles"}, "network", "img02"),
        ("Bash", {"command": "python3 -c \"import pubchempy as p; print(p.get_compounds(n, 'name'))\""},
         "network-code", None),
        ("Read", {"file_path": "/root/C-MAGE/benchmarks/wall/images.json"}, "answer-path", None),
        ("Bash", {"command": "grep -ri diminazene /root 2>/dev/null | head"}, "content-search", None),
        ("Grep", {"pattern": "berberine", "path": "/root"}, "content-search", "img01"),
        ("mcp__chem__lookup", {"name": "berberine"}, "unvetted-tool", "img01"),
    ]
    benign = [
        ("Bash", {"command": "/root/C-MAGE/.venv-ms/bin/python -c \"from rdkit import Chem; print(Chem.MolFromSmiles('CCO'))\""}),
        ("Bash", {"command": 'find / -iname "*rdkit*" -maxdepth 6 2>/dev/null | head -20'}),
        ("Bash", {"command": "pip list 2>/dev/null | grep -iE \"rdkit|osra\""}),
        ("Read", {"file_path": "/tmp/blind_a/img01.png"}),
        ("Write", {"file_path": "/tmp/sonnet_answers_a.json",
                   "content": '[{"img": "img01", "smiles": "CCO", "name_if_recognised": "berberine"}]'}),
        ("ToolSearch", {"query": "select:WebFetch"}),
    ]
    tmp = Path(tempfile.mkdtemp(prefix="scan_selftest_"))
    # The prompt line names answer paths and PubChem on purpose: it must not be scanned.
    prompt = {"type": "user", "message": {"content": "blind paths only; never /root/C-MAGE/benchmarks "
                                                     "or https://pubchem.ncbi.nlm.nih.gov"}}

    def transcript(name, records):
        p = tmp / name
        p.write_text("\n".join([json.dumps(prompt)] + [json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": t, "input": i}]}})
            for t, i in records]) + "\n")
        return p

    ok = True

    def check(cond, msg):
        nonlocal ok
        ok = ok and bool(cond)
        print(("  PASS  " if cond else "  FAIL  ") + msg)

    got, calls = scan_file(transcript("clean.jsonl", benign), rows)
    check(calls == len(benign), f"negative control: all {len(benign)} benign calls were read (read {calls})")
    check(not got, f"negative control: nothing flagged {[(f['kind'], f['target'][:60]) for f in got]}")
    mixed = [x for pair in zip(benign + [None] * len(planted), planted) for x in pair if x]
    got, calls = scan_file(transcript("dirty.jsonl", [m[:2] for m in mixed]), rows)
    check(calls == len(mixed), f"positive control: all {len(mixed)} calls were read (read {calls})")
    for idx, rec in enumerate(mixed):
        at = [f for f in got if f["line"] == idx + 2]
        if len(rec) == 2:
            check(not at, f"benign {rec[0]} not flagged {[(f['kind'], f['target'][:60]) for f in at]}")
            continue
        tool, _, kind, slot = rec
        hit = [f for f in at if f["kind"] == kind]
        check(hit, f"planted {kind:<14} via {tool} caught")
        if slot:
            check(any(l.startswith(slot + " ") for f in hit for l in f["informs"]),
                  f"planted {kind:<14} via {tool} mapped to {slot} {[f['informs'] for f in hit]}")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
