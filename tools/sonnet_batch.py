"""Prepare the next batch of N images for a blind Sonnet reading, and score the reply.

Two subcommands, because the model call happens in between and is not mine to make
from here:

    next N   -- pick the next N unread images, copy them to anonymised paths, print
                the paths. Writes nothing to the results.
    score    -- take the model's JSON answers, score them against the SAME
                references and the SAME rule as every other arm, and append.

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
    todo = [r for r in rows if r["k"] not in have and r["k"] not in claimed][:n]
    if not todo:
        print("NOTHING LEFT")
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
    print(f"[{slot}] prepared {len(batch)}  done {len(have)}  claimed-elsewhere {len(claimed)}  remaining {len(rows)-len(have)-len(claimed)-len(batch)}")
    for b in batch:
        print(f"  {BLIND}/{b['slot']}.png")
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
    if sys.argv[1] == "next":
        sys.exit(cmd_next(int(sys.argv[2]) if len(sys.argv) > 2 else 10,
                          sys.argv[3] if len(sys.argv) > 3 else "a"))
    sys.exit(cmd_score(sys.argv[2] if len(sys.argv) > 2 else "/tmp/sonnet_answers.json",
                       sys.argv[3] if len(sys.argv) > 3 else "a"))
