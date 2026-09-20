#!/usr/bin/env python3
"""Gate one Sonnet reader and score it, or refuse with a reason. Used for the ad-hoc batches.

    gate_and_score.py <slot> <agent-id>

First, a content-filter refusal. If the API refused (stop_reason "refusal", or the synthetic
"can't help with this" error) and the reader did NOT go on to write every answer, nothing is
scored: every image it had opened before the refusal is removed from the pool for good, the claim
is released so the rest go back in line, and the exit code is 4. The filter judges the whole
conversation, so the image on screen at the refusal is not necessarily the one that tripped it
(see sonnet_batch.py). A reader that was refused but still wrote every answer is gated as normal.

Every check must pass before a single row is scored:
  1. scan_reader_transcript finds no answer-key access for this slot's claim (exit 0).
  2. Every assistant message was served by a Sonnet model (no silent demote to another model).
  3. The answers file covers exactly the images handed to the reader (/tmp/blind_<slot>/imgNN.png,
     usually ten) and postdates the claim (the mtime guard also enforces this).
  4. Every answer SMILES appears verbatim somewhere in THIS agent's transcript, so the file on
     disk really is this reader's output. Whole transcript, not just the model's prose: a SMILES
     the reader canonicalised with RDKit shows up in tool output, not in what it typed.

On success it calls sonnet_batch.py score, which appends to results.jsonl and releases the claim.
Exits non-zero and scores nothing on any failure: 1 = a check refused, 4 = content-filter refusal
handled (opened images removed, claim released).
"""
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scan_reader_transcript as S  # noqa: E402

MS_PY = str(HERE.parent / ".venv-ms" / "bin" / "python")
WORK = Path("/root/cmage-work/sonnet")


def fail(msg: str) -> None:
    print(f"REFUSE [{msg}]")
    raise SystemExit(1)


REFUSAL_TEXT = ("can't help with this", "legal/aup")


def load_records(raw: str) -> list[dict]:
    out = []
    for line in raw.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def first_refusal(records: list[dict]) -> int | None:
    """Index of the first record where the API refused on content grounds, else None."""
    for i, r in enumerate(records):
        if r.get("type") != "assistant":
            continue
        m = r.get("message") or {}
        if m.get("stop_reason") == "refusal":
            return i
        if m.get("model") == "<synthetic>":
            text = " ".join(b.get("text", "") for b in (m.get("content") or []) if isinstance(b, dict))
            if any(t in text for t in REFUSAL_TEXT):
                return i
    return None


def opened_before(records: list[dict], upto: int, slot: str, expected: list[str]) -> list[str]:
    """Blind images a tool call touched before record `upto`. A computed or wildcard path into
    the blind directory (img*.png, img{i:02d}.png) counts as touching every image."""
    exact = re.compile(rf"/tmp/blind_{re.escape(slot)}/(img\d\d)")
    computed = re.compile(rf"/tmp/blind_{re.escape(slot)}/img(?!\d\d)")
    seen: set[str] = set()
    for r in records[:upto]:
        if r.get("type") != "assistant":
            continue
        for b in (r.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                s = json.dumps(b.get("input"))
                if computed.search(s):
                    return list(expected)
                seen.update(exact.findall(s))
    return sorted(seen & set(expected))


def slot_id(x) -> str:
    """An answer's slot, however the reader spelled it.

    Readers are handed paths and some label their answers img01.png, or even the full
    /tmp/blind_a/img01.png, rather than img01 -- a labelling difference with no bearing on
    the reading, which nonetheless refused a clean 10-image batch outright (slot a, 20 Sep).
    Normalising is safe because the SET still has to match the blind directory exactly;
    this cannot let a missing or extra answer through.
    """
    return re.sub(r"\.png$", "", str(x).rsplit("/", 1)[-1])


def answers_complete(ans_path: Path, claim: Path, expected: list[str]) -> bool:
    try:
        got = sorted(slot_id(a["img"]) for a in json.load(open(ans_path)))
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return got == expected and os.path.getmtime(ans_path) > os.path.getmtime(claim)


def handle_refusal(slot: str, aid: str, records: list[dict], at: int, expected: list[str]) -> int:
    import sonnet_batch as B
    opened = opened_before(records, at, slot, expected)
    print(f"REFUSED BY CONTENT FILTER [{slot}] at record {at}, before the reader wrote every answer. "
          f"Nothing is scored. The {len(opened)} image(s) it had opened are removed from the pool; "
          f"the other {len(expected) - len(opened)} go back in line.")
    if opened:
        B.cmd_remove(slot, aid, opened)
    B.cmd_release(slot)
    return 4


def main(slot: str, aid: str) -> int:
    claim = WORK / f"pending_{slot}.json"
    ans_path = Path(f"/tmp/sonnet_answers_{slot}.json")
    if not claim.exists():
        fail(f"no open claim pending_{slot}.json")

    tps = glob.glob(f"/root/.claude/projects/*/*/subagents/agent-{aid}.jsonl")
    if len(tps) != 1:
        fail(f"expected one transcript for {aid}, found {len(tps)}")
    tp = tps[0]
    raw = open(tp, encoding="utf-8", errors="replace").read()
    records = load_records(raw)

    # The expected slots are the images the claim put in the blind directory, not a fixed
    # ten: a manual batch can be any size. The claim file itself cannot be the reference,
    # because an exclusion removes slots from it after the reader has answered them.
    blind = Path(f"/tmp/blind_{slot}")
    expected = sorted(p.stem for p in blind.glob("img*.png") if re.fullmatch(r"img\d{2}", p.stem))
    if not expected:
        fail(f"no img*.png in {blind}; cannot tell which slots were handed to the reader")

    # 0. content-filter refusal
    refused = first_refusal(records)
    if refused is not None:
        if not answers_complete(ans_path, claim, expected):
            return handle_refusal(slot, aid, records, refused, expected)
        print(f"  note: content-filter refusal at record {refused}, but the reader went on to write "
              f"every answer; gating as normal")

    if not ans_path.exists():
        fail(f"no answers file {ans_path}")

    # 1. answer-key scan
    rows = S.row_ids(S.load_rows([str(claim)]))
    findings, calls = S.scan_file(Path(tp), rows)
    if calls == 0:
        fail("transcript has zero tool calls")
    if findings:
        for f in findings:
            print(f"  L{f['line']} {f['kind']} {f['target'][:120]} -> {f['informs'] or 'UNMAPPED'}")
        fail(f"{len(findings)} scan finding(s); exclude the named slots before scoring")

    # 2. served model + 4. whole-transcript containment
    models: dict[str, int] = {}
    for r in records:
        if r.get("type") == "assistant":
            m = (r.get("message") or {}).get("model")
            if m:
                models[m] = models.get(m, 0) + 1
    real = {m: n for m, n in models.items() if m != "<synthetic>"}
    if not real or not all("sonnet" in m for m in real):
        fail(f"not served entirely by Sonnet: {models}")

    # 3. answers shape + mtime
    ans = json.load(open(ans_path))
    got = {slot_id(a["img"]): a.get("smiles") for a in ans}
    claimed = {b["slot"] for b in json.load(open(claim))}
    if sorted(got) != expected:
        fail(f"answers file slots {sorted(got)} do not match the {len(expected)} images in {blind}")
    if not claimed or not claimed <= set(expected):
        fail(f"claim slots {sorted(claimed)} are not a non-empty subset of the images in {blind}")
    if os.path.getmtime(ans_path) <= os.path.getmtime(claim):
        fail("answers file is not newer than the claim")

    # A cis bond is a BACKSLASH, and a reader that checks its answer through a shell-quoted
    # python -c can multiply it: /C=C\ reached the transcript as /C=C\\\\\\\ while the answers
    # file held the single one. The prefix matched for 136 of 161 characters and the gate
    # refused the batch for "file may not be this reader's". Comparing with runs of
    # backslashes collapsed fixes that without loosening anything -- every other character
    # must still match exactly, so no unrelated SMILES can slip through.
    flat = lambda x: re.sub(r"\\+", "\\\\", x)
    flat_raw = flat(raw)
    missing = [img for img, smi in got.items()
               if smi and smi not in raw and smi.replace("\\", "\\\\") not in raw
               and flat(smi) not in flat_raw]
    if missing:
        fail(f"answer SMILES absent from this transcript (file may not be this reader's): {missing}")

    print(f"slot {slot}: PASS — {calls} calls, no findings, {models}, "
          f"{len(got)} answers all present in transcript")
    return subprocess.call([MS_PY, str(HERE / "sonnet_batch.py"), "score", str(ans_path), slot])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
