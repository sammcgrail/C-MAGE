"""Prepare the next batch of N images for a blind Sonnet reading, and score the reply.

Two subcommands, because the model call happens in between and is not mine to make
from here:

    next N   -- pick the next N unread images, copy them to anonymised paths, print
                the paths. Writes nothing to the results.
    score    -- take the model's JSON answers, score them against the SAME
                references and the SAME rule as every other arm, and append.
    defer    -- after a content-filter refusal, move named images of a claim to the
                end of the pool (deferred.jsonl). gate_and_score.py calls it.
    release  -- drop a claim without scoring it, so its images return to the pool.

A CONTENT-FILTER REFUSAL SENDS IMAGES TO THE END OF THE POOL, or the next claim takes
the same image and trips again. The filter judges the whole conversation, not the image
on screen: on 16 Sep it fired while the reader was writing up brevicidine, the image
after brevetoxin B. So a reader refused before it finishes has EVERY image it had opened
deferred, and the images it never reached go back in line. Deferred images are claimed
only when nothing fresh is left, and then ONE PER CLAIM, so a refusing image can only
take down its own reading. An image refused even when read alone is not claimed again.

STATE IS THE RESULTS FILE, not a separate ledger. `done` is derived by reading
results.jsonl, so a crash between "prepared" and "scored" costs one batch and
cannot leave the ledger claiming work that was never recorded.

ANONYMISATION IS NOT COSMETIC. The corpus names images after their compounds --
`lactic_acid_cid612.png` -- so a model handed the real path can answer from the
string without looking at the drawing, and would score well for entirely the wrong
reason. It goes through /tmp/blind with numbered names every time.
"""
import glob
import json
import os
import shutil
import sys
import time
from pathlib import Path

WORK = Path("/root/cmage-work/sonnet")
RESULTS = WORK / "results.jsonl"
# Each concurrent worker gets its OWN blind directory and its own pending file.
# A single shared /tmp/blind_batch would let two workers overwrite each other's
# images between prepare and read, and the scoring would then attribute one
# worker's answers to the other's compounds -- silently, since both are valid
# SMILES for real molecules.
def blind_dir(slot: str) -> Path:
    return Path(f"/tmp/blind_{slot}")


def pending_path(slot: str) -> Path:
    return WORK / f"pending_{slot}.json"
WALL = Path("/root/C-MAGE/benchmarks/wall")


def corpus() -> list[dict]:
    d = json.load(open(WALL / "images.json"))
    return sorted(d["rows"], key=lambda r: r["k"])


def done_keys() -> set[str]:
    if not RESULTS.exists():
        return set()
    return {json.loads(l)["k"] for l in open(RESULTS) if l.strip()}


def image_index() -> dict[str, str]:
    idx = {}
    for dd in sorted(glob.glob("/root/cmage-work/cmage-img*/corpus_rdkit_1500")):
        for p in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(p), p)
    return idx


def deferred_path() -> Path:
    return WORK / "deferred.jsonl"


def deferred() -> dict[str, dict]:
    """Key -> its latest deferral. A deferred image that has since been scored is simply
    done; nothing needs to clear it from this file."""
    p = deferred_path()
    if not p.exists():
        return {}
    out = {}
    for line in open(p):
        if line.strip():
            d = json.loads(line)
            out[d["k"]] = d
    return out


def pool(rows: list[dict], have: set[str], claimed: set[str], dfr: dict[str, dict],
         n: int) -> list[dict]:
    """The next claim: fresh images first, in corpus order. Deferred images only once no
    fresh image is left, one per claim, and never one already refused when read alone."""
    open_rows = [r for r in rows if r["k"] not in have and r["k"] not in claimed]
    fresh = [r for r in open_rows if r["k"] not in dfr]
    if fresh:
        return fresh[:n]
    return [r for r in open_rows if not dfr[r["k"]].get("alone")][:1]


def cmd_next(n: int, slot: str = "a") -> int:
    rows, have, idx = corpus(), done_keys(), image_index()
    # Skip anything another worker has already claimed but not yet scored, or two
    # workers started at the same moment read the same ten images.
    claimed = set()
    for pp in WORK.glob("pending_*.json"):
        try:
            claimed |= {b["k"] for b in json.load(open(pp))}
        except Exception:
            pass
    dfr = {k: d for k, d in deferred().items() if k not in have}
    todo = pool(rows, have, claimed, dfr, n)
    if not todo:
        blocked = sorted(k for k, d in dfr.items() if d.get("alone"))
        print("NOTHING LEFT" + (f"  ({len(blocked)} refused by the content filter even when "
                                f"read alone: {', '.join(blocked)})" if blocked else ""))
        return 0
    BLIND = blind_dir(slot)
    shutil.rmtree(BLIND, ignore_errors=True)
    BLIND.mkdir(parents=True)
    WORK.mkdir(parents=True, exist_ok=True)
    batch = []
    for i, r in enumerate(todo, 1):
        src = idx.get(r["k"] + ".png")
        if not src:
            continue
        dst = BLIND / f"img{i:02d}.png"
        shutil.copy(src, dst)
        batch.append({"slot": f"img{i:02d}", "k": r["k"], "truth": r.get("t"),
                      "name": r["n"], "ocr_smiles": r["s"], "ocr_verdict": r["v"],
                      "ocr_conf": r["c"]})
    json.dump(batch, open(pending_path(slot), "w"), indent=1)
    leak = [b for b in batch if any(t in b["slot"].lower() for t in ("cid", "acid", "_"))]
    assert not leak, f"anonymisation failed: {leak}"
    print(f"[{slot}] prepared {len(batch)}  done {len(have)}  claimed-elsewhere {len(claimed)}  remaining {len(rows)-len(have)-len(claimed)-len(batch)}"
          f"  deferred {len(dfr)}")
    for b in batch:
        print(f"  {BLIND}/{b['slot']}.png")
    return 0


def cmd_defer(slot: str, reader: str, imgs: list[str]) -> int:
    """Send images of an open claim to the end of the pool after a content-filter refusal."""
    claim = json.load(open(pending_path(slot)))
    by_slot = {b["slot"]: b for b in claim}
    unknown = [i for i in imgs if i not in by_slot]
    if unknown or not imgs:
        raise SystemExit(f"[{slot}] cannot defer {imgs}: not in the open claim {sorted(by_slot)}")
    alone = len(claim) == 1
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(deferred_path(), "a") as fh:
        for i in imgs:
            b = by_slot[i]
            fh.write(json.dumps({"k": b["k"], "name": b["name"], "slot": i, "claim_size": len(claim),
                                 "reader": reader, "reason": "content-filter refusal",
                                 "alone": alone, "at": at}) + "\n")
    for i in imgs:
        print(f"[{slot}] deferred {i} {by_slot[i]['name']}"
              + ("  (refused when read alone: not claimed again)" if alone else "  (to the end of the pool)"))
    return 0


def cmd_release(slot: str) -> int:
    """Drop an open claim without scoring it; its images return to the pool."""
    p = pending_path(slot)
    if not p.exists():
        print(f"[{slot}] no open claim to release")
        return 0
    n = len(json.load(open(p)))
    p.unlink()
    print(f"[{slot}] released the claim of {n}; nothing scored")
    return 0


def cmd_score(answers_path: str, slot: str = "a") -> int:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    batch = json.load(open(pending_path(slot)))
    ans = {a["img"]: a for a in json.load(open(answers_path))}

    # The answers file lives at a FIXED path per slot and is overwritten each round.
    # Scoring a STALE one against a fresh claim is silent and total: every row gets a
    # valid SMILES for a real molecule, just the wrong one, and the batch reads as a
    # catastrophic model failure rather than a bookkeeping error. It happened once --
    # round 4's answers scored against round 5's images, so aspirin came back "wrong"
    # holding a macrocyclic peptide and atenolol came back "wrong" holding anthracene.
    # The answers must postdate the claim they are being scored against.
    if os.path.getmtime(answers_path) < os.path.getmtime(pending_path(slot)):
        raise SystemExit(
            f"[{slot}] REFUSING: {answers_path} is OLDER than the claim it would be "
            f"scored against ({pending_path(slot)}).\n"
            f"  answers  {time.strftime('%F %T', time.localtime(os.path.getmtime(answers_path)))}\n"
            f"  claim    {time.strftime('%F %T', time.localtime(os.path.getmtime(pending_path(slot))))}\n"
            f"  The reader for this slot has not written yet, or wrote elsewhere. "
            f"Scoring now would attribute one batch's answers to another batch's images.")

    def canon(s, stereo=True):
        if not s:
            return None
        m = Chem.MolFromSmiles(s)
        return None if m is None else Chem.MolToSmiles(m, isomericSmiles=stereo)

    s_ex = o_ex = 0
    with open(RESULTS, "a") as fh:
        for b in batch:
            a = ans.get(b["slot"], {})
            pred, t = a.get("smiles"), b["truth"]
            if canon(pred) is None:
                v = "invalid"
            elif canon(pred) == canon(t):
                v = "exact"
            elif canon(pred, False) == canon(t, False):
                v = "stereo"
            else:
                v = "wrong"
            s_ex += v == "exact"
            o_ex += b["ocr_verdict"] == "exact"
            fh.write(json.dumps(dict(b, sonnet_smiles=pred, sonnet_verdict=v,
                                     sonnet_conf=a.get("confidence"),
                                     sonnet_name=a.get("name_if_recognised"))) + "\n")
    pending_path(slot).unlink(missing_ok=True)     # release the claim
    tot = len(done_keys())
    print(f"[{slot}] sonnet {s_ex}/{len(batch)}  cxmolscribe {o_ex}/{len(batch)}   cumulative {tot}")
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "defer":        # defer <slot> <reader-agent-id> <imgNN> [imgNN ...]
        sys.exit(cmd_defer(sys.argv[2], sys.argv[3], sys.argv[4:]))
    if sys.argv[1] == "release":      # release <slot>
        sys.exit(cmd_release(sys.argv[2]))
    if sys.argv[1] == "next":
        sys.exit(cmd_next(int(sys.argv[2]) if len(sys.argv) > 2 else 10,
                          sys.argv[3] if len(sys.argv) > 3 else "a"))
    sys.exit(cmd_score(sys.argv[2] if len(sys.argv) > 2 else "/tmp/sonnet_answers.json",
                       sys.argv[3] if len(sys.argv) > 3 else "a"))
