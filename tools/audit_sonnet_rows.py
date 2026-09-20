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
# What a reading touches. The first batch used /tmp/blind10/, later ones /tmp/blind_<slot>/.
READER_MARK = re.compile(r"/tmp/blind\w*/img\d\d\.png|/tmp/sonnet_answers\w*\.json")


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


def pairs(text: str) -> list[tuple[str, str]]:
    """(slot, SMILES) for every answer written in this text. The reader prompt's own template
    carries "smiles": "...", which is not an answer."""
    out = []
    for a in ANSWER.finditer(text):
        try:
            smi = json.loads(a.group(2))
        except ValueError:
            continue
        if smi and smi.strip("."):
            out.append((a.group(1), smi))
    return out


def reader_transcripts(skip: set[str]) -> dict[str, tuple[list, str]]:
    """Every subagent transcript since the arm began that did a reading.

    Recognised two ways. An answer array in what the model itself wrote is a reader, whatever
    else the transcript holds. But a reader that BUILDS its answers file in code never types
    the array, so nothing of it appears in the model's own output: on 17 Sep that made a whole
    batch invisible here, its rows came back UNTRACED though the gate had verified every one,
    and it blocked every commit until the rows were removed. So a transcript that opened a
    blind image or wrote the answers file counts too — if it was Sonnet-served, because a row
    written by anything else is exactly what an untraced row is meant to catch — and its
    answers are then read from the WHOLE transcript, tool output included, the same place
    gate_and_score.py looks.
    """
    since = time.mktime(time.strptime(ARM_START, "%Y-%m-%d"))
    out = {}
    for dp, _, fn in os.walk(S.PROJECTS):
        for f in fn:
            m = re.fullmatch(r"agent-(\w+)\.jsonl", f)
            p = os.path.join(dp, f)
            if not m or m.group(1) in skip or os.path.getmtime(p) < since:
                continue
            raw = open(p, errors="replace").read()
            parts, every, models = [], [], set()
            for line in raw.splitlines():
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                content = (r.get("message") or {}).get("content")
                every.extend(strings(content))
                if r.get("type") == "assistant":
                    parts.extend(strings(content))
                    models.add((r.get("message") or {}).get("model"))
            text = "\n".join(parts)
            found = pairs(text)
            # Trace containment against the WHOLE transcript, not just the model's prose: a
            # reader that canonicalises its answer with RDKit emits the final SMILES in tool
            # output (a non-assistant record), so it is genuinely this reader's reading but is
            # absent from the assistant text. gate_and_score.py verifies the same way.
            if found:
                out[p] = (found, raw)
                continue
            real = {x for x in models if x and x != "<synthetic>"}
            if READER_MARK.search(text) and real and all("sonnet" in x for x in real):
                # Decoded record strings, not the raw JSONL: an array quoted inside a tool
                # result has every quote backslash-escaped and matches no answer pattern.
                out[p] = (pairs("\n".join(every)), raw)
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

    # Every character that can appear INSIDE a SMILES. A raw-transcript hit only counts as
    # this reader's answer when both edges fall outside that set -- i.e. the string stands
    # alone, rather than sitting inside a larger molecule or a blob of base64.
    SMILES_CHAR = re.compile(r"[A-Za-z0-9@+\-\[\]()=#/\\%.*]")

    collapsed_cache: dict[int, str] = {}

    def _collapse(text):
        """Backslash-run-collapsed copy of a transcript, made at most once per transcript.

        Keyed by id() of the raw string the caller already holds, and capped at four, so a
        2 GB corpus of transcripts is never duplicated wholesale.
        """
        key = id(text)
        if key not in collapsed_cache:
            if len(collapsed_cache) >= 4:
                collapsed_cache.pop(next(iter(collapsed_cache)))
            collapsed_cache[key] = re.sub(r"\\+", "\\\\", text)
        return collapsed_cache[key]

    def standalone(smi, text):
        """Is `smi` present as a whole token, not as a substring of something bigger?

        Plain `in` is catastrophic for SHORT answers. A refused reader on 20 Sep implicated
        three published rows it never touched: C1CC1 (cyclopropane) matched a cyclopropyl
        group inside an unrelated drug 15 times, CC(=O)O (acetic acid) matched an acetate
        fragment, and NCCS (cysteamine) matched inside BASE64 IMAGE DATA. None had ever
        been a complete answer value. Refusing one reader was damaging rows at random.
        """
        # A cis bond IS a backslash, and it reaches the transcript with any number of them:
        # once as written, twice through JSONL escaping (fluvoxamine appears ONLY that way),
        # and seven times when a reader checks its answer through a shell-quoted python -c
        # (friulimicin B). Try the two cheap spellings first, then -- only for an answer that
        # actually contains a backslash, so the cost is paid by 44 rows out of 1056 -- compare
        # with runs of backslashes collapsed on both sides. Collapsing loosens nothing: every
        # other character must still match, and the token boundaries are still enforced.
        for spelling in (smi, smi.replace("\\", "\\\\")):
            if _bounded(spelling, text):
                return True
        if "\\" not in smi:
            return False
        flat = _collapse(text)
        return _bounded(re.sub(r"\\+", "\\\\", smi), flat)

    def _bounded(smi, text):
        i = text.find(smi)
        while i != -1:
            j = i + len(smi)
            before = text[i - 1] if i else ""
            after = text[j] if j < len(text) else ""
            # The text is raw JSONL, so a real answer is usually followed by an ESCAPE:
            # ...cc1\" ending a JSON string, or ...cc1\n ending a line. A lone backslash is
            # also a legitimate cis bond, which is why a trailing \\ does NOT count -- that
            # may be a real bond continuing into a larger molecule.
            esc = after == "\\" and text[j + 1: j + 2] in ('"', "n", "r", "t")
            if (not SMILES_CHAR.fullmatch(before or " ")
                    and (esc or not SMILES_CHAR.fullmatch(after or " "))):
                return True
            i = text.find(smi, i + 1)
        return False

    def holds(p, smi):
        return bool(smi) and (p in by_smiles.get(smi, ()) or standalone(smi, readers[p][1]))

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
