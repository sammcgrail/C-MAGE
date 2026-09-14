#!/usr/bin/env python3
"""Trace every published Sonnet row to the reader transcript that produced it, and screen each.

Screening one reader at a time covers only the readers you remember to name. The first
full audit picked readers by the shape of their prompt and missed the very first batch,
whose prompt did not match. It still reported "all clean", exactly what it would have
said with full coverage. So this starts from the ROWS. Every row in results.jsonl must
trace, by the SMILES it was scored on, to a subagent transcript that wrote that answer,
and that transcript must be clean for that row.

A row that traces nowhere is itself a finding. Its answer did not come from any reader
transcript we can see: a main thread edited it, or the transcript is gone.

TWO RULES, each learned on a real run:

RE-READS. An excluded row goes back to the unread pool. The clean reader who reads it
again usually writes the SAME SMILES as the reader whose lookup got it excluded, because
it is the same drawing of the same molecule. Tracing by string then finds both
transcripts, and the old lookup appears to implicate the new reading. So a transcript is
set aside for a row when its own reading of that row is the one already excluded:
- its findings name the row
- the row's key is in excluded.jsonl
- it holds that excluded reading's SMILES
The row must still trace to another transcript, and that one must be clean.

UNMAPPED IS NOT CLEAN. A finding the scanner cannot tie to a slot fails every row its
transcript holds, unless benchmarks/sonnet_resolved_findings.json records how that exact
finding was resolved. A resolution is a reviewed claim, so it lives in the repo. It is
matched on agent id and the exact target, never on a prefix, which would wave through
the next lookup to the same host.

    audit_sonnet_rows.py [--skip <agent-id>]...
        exit 0  every row traced, none implicated, none resting on an unresolved finding
        exit 1  otherwise, with the rows listed
    --skip a reader that is still running; it is screened when its batch is scored.
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scan_reader_transcript as S  # noqa: E402

WORK = "/root/cmage-work/sonnet"
RESOLVED = os.path.join(HERE, "..", "benchmarks", "sonnet_resolved_findings.json")
ARM_START = "2026-09-09"      # no Sonnet reader predates the arm; older transcripts are skipped
ANSWER = re.compile(r'"img"\s*:\s*"(img\d\d)"\s*,\s*"smiles"\s*:\s*("(?:[^"\\]|\\.)*"|null)')


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def reader_transcripts(skip: set[str]) -> dict[str, tuple[list, str]]:
    """Every subagent transcript since the arm began that wrote an answer array."""
    since = time.mktime(time.strptime(ARM_START, "%Y-%m-%d"))
    out = {}
    for dp, _, fn in os.walk(S.PROJECTS):
        for f in fn:
            m = re.fullmatch(r"agent-(\w+)\.jsonl", f)
            p = os.path.join(dp, f)
            if not m or m.group(1) in skip or os.path.getmtime(p) < since:
                continue
            parts = []
            with open(p, errors="replace") as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("type") == "assistant":
                        parts.extend(strings((r.get("message") or {}).get("content")))
            blob = "\n".join(parts)
            found = []
            for a in ANSWER.finditer(blob):
                try:
                    found.append((a.group(1), json.loads(a.group(2))))
                except ValueError:
                    pass
            if found:
                out[p] = (found, blob)
    return out


def main(argv: list[str]) -> int:
    skip = {argv[i + 1] for i, a in enumerate(argv) if a == "--skip" and i + 1 < len(argv)}
    res = [json.loads(l) for l in open(f"{WORK}/results.jsonl") if l.strip()]
    exc = [json.loads(l) for l in open(f"{WORK}/excluded.jsonl") if l.strip()]
    resolved = {(x["agent"], x["target"]) for x in json.load(open(RESOLVED))}
    readers = reader_transcripts(skip)

    by_smiles = {}
    for p, (found, _) in readers.items():
        for _, smi in found:
            by_smiles.setdefault(smi, set()).add(p)

    def holds(p, smi):
        return bool(smi) and (p in by_smiles.get(smi, ()) or smi in readers[p][1])

    ids = S.row_ids(res + exc)
    scan, used = {}, set()
    for p in sorted(readers, key=os.path.getmtime):
        aid = os.path.basename(p)[6:-6]
        findings, _ = S.scan_file(p, ids)
        named = {lab.split("[")[-1].rstrip("]") for f in findings for lab in f["informs"]}
        unresolved = []
        for f in findings:
            if f["informs"]:
                continue
            if (aid, f["target"]) in resolved:
                used.add((aid, f["target"]))
            else:
                unresolved.append(f["target"])
        scan[p] = (aid, named, unresolved)
        if findings:
            print(f"  {aid}: {len(findings)} findings, {len(named)} rows named, "
                  f"unresolved unmapped: {[t[:90] for t in unresolved] or 'none'}")

    excluded_smiles = {}
    for e in exc:
        excluded_smiles.setdefault(e["k"], set()).add(e.get("sonnet_smiles"))

    untraced, implicated, unverified, set_aside = [], {}, {}, []
    for r in res:
        k, smi = r["k"], r.get("sonnet_smiles")
        live = []
        for p in readers:
            if not holds(p, smi):
                continue
            aid, named, _ = scan[p]
            if k in named and any(holds(p, s) for s in excluded_smiles.get(k, ())):
                set_aside.append((r["name"], aid))
                continue
            live.append(p)
        if not live:
            untraced.append(r)
        for p in live:
            aid, named, unresolved = scan[p]
            if k in named:
                implicated.setdefault(k, set()).add(aid)
            if unresolved:
                unverified.setdefault(k, set()).add(aid)

    print(f"reader transcripts: {len(readers)}  (skipped as running: {sorted(skip) or 'none'})")
    print(f"published rows: {len(res)}  traced: {len(res) - len(untraced)}  untraced: {len(untraced)}  "
          f"implicated: {len(implicated)}  unverified: {len(unverified)}")
    print(f"re-reads whose earlier excluded reading was set aside: {len(set_aside)}")
    for name, aid in set_aside:
        print(f"  set aside: {name} (excluded reading by {aid})")
    for stale in sorted(resolved - used):
        print(f"  NOTE resolution matched no finding: {stale}")
    for r in untraced:
        print(f"  UNTRACED: {r['name']} [{r['k']}] {str(r.get('sonnet_smiles'))[:60]}")
    for k, aids in sorted(implicated.items()):
        print(f"  IMPLICATED: {k} by {sorted(aids)}")
    for k, aids in sorted(unverified.items()):
        print(f"  UNVERIFIED: {k} rests on unresolved findings in {sorted(aids)}")
    return 1 if (untraced or implicated or unverified) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
