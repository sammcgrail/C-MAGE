#!/usr/bin/env python3
"""Gate one Sonnet reader and score it, or refuse with a reason. Used for the ad-hoc batches.

    gate_and_score.py <slot> <agent-id>

Every check must pass before a single row is scored:
  1. scan_reader_transcript finds no answer-key access for this slot's claim (exit 0).
  2. Every assistant message was served by a Sonnet model (no silent demote to another model).
  3. The answers file covers exactly the images handed to the reader (/tmp/blind_<slot>/imgNN.png,
     usually ten) and postdates the claim (the mtime guard also enforces this).
  4. Every answer SMILES appears verbatim somewhere in THIS agent's transcript, so the file on
     disk really is this reader's output. Whole transcript, not just the model's prose: a SMILES
     the reader canonicalised with RDKit shows up in tool output, not in what it typed.

On success it calls sonnet_batch.py score, which appends to results.jsonl and releases the claim.
Exits non-zero and scores nothing on any failure.
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


def main(slot: str, aid: str) -> int:
    claim = WORK / f"pending_{slot}.json"
    ans_path = Path(f"/tmp/sonnet_answers_{slot}.json")
    if not claim.exists():
        fail(f"no open claim pending_{slot}.json")
    if not ans_path.exists():
        fail(f"no answers file {ans_path}")

    tps = glob.glob(f"/root/.claude/projects/*/*/subagents/agent-{aid}.jsonl")
    if len(tps) != 1:
        fail(f"expected one transcript for {aid}, found {len(tps)}")
    tp = tps[0]

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
    raw = open(tp, encoding="utf-8", errors="replace").read()
    models: dict[str, int] = {}
    for line in raw.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") == "assistant":
            m = (r.get("message") or {}).get("model")
            if m:
                models[m] = models.get(m, 0) + 1
    real = {m: n for m, n in models.items() if m != "<synthetic>"}
    if not real or not all("sonnet" in m for m in real):
        fail(f"not served entirely by Sonnet: {models}")

    # 3. answers shape + mtime
    # The expected slots are the images the claim put in the blind directory, not a fixed
    # ten: a manual batch can be any size. The claim file itself cannot be the reference,
    # because an exclusion removes slots from it after the reader has answered them.
    ans = json.load(open(ans_path))
    got = {a["img"]: a.get("smiles") for a in ans}
    blind = Path(f"/tmp/blind_{slot}")
    expected = sorted(p.stem for p in blind.glob("img*.png") if re.fullmatch(r"img\d{2}", p.stem))
    claimed = {b["slot"] for b in json.load(open(claim))}
    if not expected:
        fail(f"no img*.png in {blind}; cannot tell which slots were handed to the reader")
    if sorted(got) != expected:
        fail(f"answers file slots {sorted(got)} do not match the {len(expected)} images in {blind}")
    if not claimed or not claimed <= set(expected):
        fail(f"claim slots {sorted(claimed)} are not a non-empty subset of the images in {blind}")
    if os.path.getmtime(ans_path) <= os.path.getmtime(claim):
        fail("answers file is not newer than the claim")

    missing = [img for img, smi in got.items()
               if smi and smi not in raw and smi.replace("\\", "\\\\") not in raw]
    if missing:
        fail(f"answer SMILES absent from this transcript (file may not be this reader's): {missing}")

    print(f"slot {slot}: PASS — {calls} calls, no findings, {models}, "
          f"{len(got)} answers all present in transcript")
    return subprocess.call([MS_PY, str(HERE / "sonnet_batch.py"), "score", str(ans_path), slot])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
