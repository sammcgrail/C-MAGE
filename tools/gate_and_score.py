#!/usr/bin/env python3
"""Gate one Sonnet reader and score it, or refuse with a reason. Used for the ad-hoc batches.

    gate_and_score.py <slot> <agent-id>
    gate_and_score.py --selftest      (run with the RDKit python; must print GATE SELFTEST PASS)

First, a content-filter refusal. If the API refused (stop_reason "refusal", or the synthetic
"can't help with this" error) and the reader did NOT go on to write every answer, nothing is
scored: every image it had opened before the refusal is removed from the pool for good, the claim
is released so the rest go back in line, and the exit code is 4. The filter judges the whole
conversation, so the image on screen at the refusal is not necessarily the one that tripped it
(see sonnet_batch.py). A reader that was refused but still wrote every answer is gated as normal.

Before anything else, every blind image the claim lists (/tmp/blind<arm>_<slot>/<img>.png) and
every image in that directory must exist and be PIXELS ONLY (png_clean.assert_pixel_only): until
8 Oct every corpus PNG carried its own answer in zTXt chunks, so an image with any text or foreign
chunk means the reader was handed its key, whatever it did with it. Refused, nothing scored.

Every check must pass before a single row is scored:
  1. scan_reader_transcript finds no answer-key access for this slot's claim (exit 0). The kinds
     in S.NEVER_WAIVE (png-metadata, name-to-structure, nested-model, obfuscated-exec) are then
     re-checked by the scanner in a SEPARATE process, so a wrapper that monkeypatches scan_file to
     waive a reviewed finding (as for a Monitor call on 6 Oct) can never waive one of those.
  2. Every assistant message was served by exactly the lane's model id, and the reader called no
     sub-agent (a delegated image is read by the sub-agent's model, invisibly to check 2).
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
import png_clean as P  # noqa: E402
import scan_reader_transcript as S  # noqa: E402
import sonnet_batch as B  # noqa: E402  (paths come from here, so SONNET_ARM moves the gate too)

MS_PY = str(HERE.parent / ".venv-ms" / "bin" / "python")
WORK = B.WORK


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
    blind = re.escape(str(B.blind_dir(slot)))
    exact = re.compile(rf"{blind}/({B.STEM}\d\d)")
    computed = re.compile(rf"{blind}/{B.STEM}(?!\d\d)")
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


def delegations(records: list[dict]) -> list[str]:
    """The sub-agent types a reader handed work to (Agent/Task tool calls), one per call."""
    return [b.get("input", {}).get("subagent_type") or "?" for r in records if r.get("type") == "assistant"
            for b in ((r.get("message") or {}).get("content") or [])
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Agent", "Task")]


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


def blind_pixel_problems(blind: Path, claimed: list[str], present: list[str]) -> list[str]:
    """Why the images handed to the reader cannot be trusted: a claimed image that is missing,
    or any claimed or present image that is not a PNG or carries a chunk outside png_clean.KEEP.
    Empty list = every image is pixels only."""
    problems = []
    for stem in sorted(set(claimed) | set(present)):
        p = blind / f"{stem}.png"
        try:
            data = p.read_bytes()
        except OSError as e:
            problems.append(f"{p}: missing or unreadable ({e.__class__.__name__})")
            continue
        try:
            P.assert_pixel_only(data, str(p))
        except P.PngMetadataError as e:
            problems.append(str(e) if str(p) in str(e) else f"{p}: {e}")
    return problems


def hard_findings(tp: str, claim: Path) -> tuple[int, str]:
    """Re-scan for the never-waivable kinds in a separate process. (exit code, output)."""
    r = subprocess.run([MS_PY, str(HERE / "scan_reader_transcript.py"), "--path", str(tp),
                        "--rows", str(claim), "--only", ",".join(S.NEVER_WAIVE)],
                       capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def handle_refusal(slot: str, aid: str, records: list[dict], at: int, expected: list[str]) -> int:
    opened = opened_before(records, at, slot, expected)
    print(f"REFUSED BY CONTENT FILTER [{slot}] at record {at}, before the reader wrote every answer. "
          f"Nothing is scored. The {len(opened)} image(s) it had opened are removed from the pool; "
          f"the other {len(expected) - len(opened)} go back in line.")
    if opened:
        B.cmd_remove(slot, aid, opened)
    B.cmd_release(slot)
    return 4


def main(slot: str, aid: str) -> int:
    claim = B.pending_path(slot)
    ans_path = B.answers_path(slot)
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
    blind = B.blind_dir(slot)
    expected = sorted(p.stem for p in blind.glob(f"{B.STEM}*.png") if re.fullmatch(rf"{B.STEM}\d{{2}}", p.stem))
    if not expected:
        fail(f"no {B.STEM}*.png in {blind}; cannot tell which slots were handed to the reader")

    # -1. pixels only. Checked before anything else, the refusal path included: an image that
    # carried its answer voids the reading whatever the reader did with it.
    try:
        claimed_imgs = [b["slot"] for b in json.load(open(claim))]
    except (OSError, ValueError, KeyError, TypeError) as e:
        fail(f"claim {claim} unreadable: {e}")
    bad = blind_pixel_problems(blind, claimed_imgs, expected)
    if bad:
        for b in bad:
            print(f"  {b}")
        fail(f"{len(bad)} blind image(s) missing or carrying non-pixel chunks; the reader may have been "
             f"handed its answer key. Nothing scored")

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
            hard = "  [NEVER WAIVABLE]" if f["kind"] in S.NEVER_WAIVE else ""
            print(f"  L{f['line']} {f['kind']} {f['target'][:120]!r} -> {f['informs'] or 'UNMAPPED'}{hard}")
        fail(f"{len(findings)} scan finding(s); exclude the named slots before scoring")
    rc, out = hard_findings(tp, claim)
    if rc != 0:
        print(out)
        fail(f"separate-process re-scan found never-waivable finding(s) ({', '.join(S.NEVER_WAIVE)}) "
             f"or could not scan (exit {rc})")

    # 2. served model + 4. whole-transcript containment
    models: dict[str, int] = {}
    for r in records:
        if r.get("type") == "assistant":
            m = (r.get("message") or {}).get("model")
            if m:
                models[m] = models.get(m, 0) + 1
    real = {m: n for m, n in models.items() if m != "<synthetic>"}
    # EXACT id, every lane including the Sonnet 5 arm. It was `"sonnet" in m`, which also
    # passes claude-sonnet-5-5 -- and the "sonnet" alias moved to 5.5 on 28 Sep.
    want = B.ARM_MODEL[B.ARM]
    if set(real) != {want}:
        fail(f"lane {B.ARM or 'sonnet5'} needs every request served by exactly {want}, got {models}")

    # 2b. no delegation. A reader that hands images to its own sub-agents gets answers from
    # whatever model those sub-agents run on, and every record in ITS transcript still carries
    # the lane's model, so check 2 cannot see it. On 28 Sep a Sonnet 5 re-run reader passed 7
    # of its 10 images to three general-purpose-high sub-agents served by claude-opus-5-5.
    delegated = delegations(records)
    if delegated:
        fail(f"reader delegated to {len(delegated)} sub-agent(s) {delegated}; their answers are not this lane's model")

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


def selftest() -> int:
    """The pixel-only gate and the never-waivable re-scan, on synthetic files."""
    import tempfile
    from rdkit import Chem
    from rdkit.Chem.Draw import rdMolDraw2D
    ok = True

    def check(cond, msg):
        nonlocal ok
        ok = ok and bool(cond)
        print(("  PASS  " if cond else "  FAIL  ") + msg)

    d = rdMolDraw2D.MolDraw2DCairo(300, 300)
    rdMolDraw2D.PrepareAndDrawMolecule(d, Chem.MolFromSmiles("C[C@H](N)C(=O)O"))
    d.FinishDrawing()
    raw = d.GetDrawingText()                       # RDKit default: the molecule in zTXt chunks
    tmp = Path(tempfile.mkdtemp(prefix="gate_selftest_"))
    blind = tmp / "blind"
    blind.mkdir()
    (blind / "fig01.png").write_bytes(P.pixel_only(raw))
    check(P.text_chunks(raw), "control: the RDKit default render carries text chunks")
    check(blind_pixel_problems(blind, ["fig01"], ["fig01"]) == [], "a pixel-only image passes")
    (blind / "fig02.png").write_bytes(raw)
    bad = blind_pixel_problems(blind, ["fig01"], ["fig01", "fig02"])
    check(len(bad) == 1 and "fig02" in bad[0], f"an RDKit render with metadata refuses {bad}")
    (blind / "fig02.png").write_bytes(P.pixel_only(raw))
    bad = blind_pixel_problems(blind, ["fig01", "fig03"], ["fig01", "fig02"])
    check(len(bad) == 1 and "fig03" in bad[0] and "missing" in bad[0], f"a claimed image that is missing refuses {bad}")
    (blind / "fig04.png").write_bytes(b"GIF89a")
    bad = blind_pixel_problems(blind, ["fig01"], ["fig04"])
    check(len(bad) == 1 and "not a PNG" in bad[0], f"a non-PNG refuses {bad}")

    claim = tmp / "pending_x.json"
    claim.write_text(json.dumps([{"slot": "fig01", "k": "alanine_cid5950", "name": "Alanine",
                                  "truth": "C[C@@H](C(=O)O)N"}]))

    def transcript(name, cmd):
        p = tmp / name
        p.write_text(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": "t", "name": "Bash", "input": {"command": cmd}}]}}) + "\n")
        return p
    clean = transcript("agent-clean.jsonl", "/root/C-MAGE/.venv-ms/bin/python -c \"from PIL import Image; "
                                            "print(Image.open('/tmp/blinds55c_x/fig01.png').size)\"")
    rc, out = hard_findings(str(clean), claim)
    check(rc == 0, f"re-scan: a clean transcript passes (exit {rc})")
    for name, cmd, kind in [
        ("agent-png.jsonl", "python3 -c \"from rdkit import Chem; print(Chem.MolFromPNGFile('/tmp/blinds55c_x/fig01.png'))\"",
         "png-metadata"),
        ("agent-opsin.jsonl", "python3 -c \"from py2opsin import py2opsin; print(py2opsin('alanine'))\"", "name-to-structure"),
        ("agent-claude.jsonl", "claude -p 'read /tmp/blinds55c_x/fig01.png'", "nested-model")]:
        p = transcript(name, cmd)
        # A wrapper that waives findings in-process must not reach the separate process.
        real, S.scan_file = S.scan_file, (lambda *a, **k: ([], 1))
        try:
            rc, out = hard_findings(str(p), claim)
        finally:
            S.scan_file = real
        check(rc == 1 and kind in out, f"re-scan: {kind} refuses even with scan_file monkeypatched (exit {rc})")
    # A Monitor finding is waivable (it is not in NEVER_WAIVE), so the re-scan ignores other kinds.
    p = transcript("agent-curl.jsonl", "curl -s https://example.org/x")
    rc, _ = hard_findings(str(p), claim)
    check(rc == 0, "re-scan: a waivable kind (network) is left to the in-process scan")
    print("GATE SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if sys.argv[1:2] == ["--selftest"]:
        raise SystemExit(selftest())
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
