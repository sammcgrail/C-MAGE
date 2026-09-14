#!/usr/bin/env python3
"""Trace every published Sonnet row to the reader transcript that produced it, and screen each.

Screening one reader at a time covers only the readers you remember to name. The first
full audit picked readers by the shape of their prompt, and it missed the very first
batch, whose prompt did not match. It still reported "all clean", exactly as it would
have with full coverage. So this starts from the ROWS instead. Every row in results.jsonl
must trace, by the SMILES it was scored on, to at least one subagent transcript that
wrote that answer. No scanner finding in any transcript holding that answer may name the
row.

A row that traces nowhere is itself a finding. Its answer did not come from any reader
transcript we can see: a main thread edited it, or the transcript is gone. Either way it
cannot be verified.

    audit_sonnet_rows.py [--skip <agent-id>]...
        exit 0  every row traced, none implicated
        exit 1  untraced or implicated rows, listed
    --skip a reader that is still running; it is screened when its batch is scored.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan_reader_transcript as S  # noqa: E402

WORK = "/root/cmage-work/sonnet"
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
    readers = reader_transcripts(skip)
    by_smiles = {}
    for p, (found, _) in readers.items():
        for _, smi in found:
            by_smiles.setdefault(smi, set()).add(p)

    holders, untraced, substring = {}, [], []
    for r in res:
        smi = r.get("sonnet_smiles")
        hits = set(by_smiles.get(smi, ())) if smi else set()
        if not hits and smi:
            hits = {p for p, (_, blob) in readers.items() if smi in blob}
            if hits:
                substring.append((r, hits))
        if not hits:
            untraced.append(r)
        for p in hits:
            holders.setdefault(p, set()).add(r["k"])

    ids = S.row_ids(res + exc)
    implicated = {}
    for p in sorted(readers, key=os.path.getmtime):
        findings, calls = S.scan_file(p, ids)
        aid = os.path.basename(p)[6:-6]
        named = {lab.split("[")[-1].rstrip("]") for f in findings for lab in f["informs"]}
        hit = named & holders.get(p, set())
        for k in hit:
            implicated.setdefault(k, set()).add(aid)
        if findings:
            unmapped = [f["target"][:70] for f in findings if not f["informs"]]
            print(f"  {aid}: {len(findings)} findings, published rows named {sorted(hit) or 'none'}, "
                  f"unmapped {unmapped or 'none'}")

    print(f"reader transcripts: {len(readers)}  (skipped as running: {sorted(skip) or 'none'})")
    print(f"published rows: {len(res)}  traced: {len(res) - len(untraced)}  "
          f"(by substring: {len(substring)})  untraced: {len(untraced)}  implicated: {len(implicated)}")
    for r, hits in substring:
        print(f"  traced by substring: {r['name']} [{r['k']}] in "
              f"{sorted(os.path.basename(h)[6:-6] for h in hits)}")
    for r in untraced:
        print(f"  UNTRACED: {r['name']} [{r['k']}] {str(r.get('sonnet_smiles'))[:60]}")
    for k, aids in sorted(implicated.items()):
        print(f"  IMPLICATED: {k} by {sorted(aids)}")
    return 1 if (untraced or implicated) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
