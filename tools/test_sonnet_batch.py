"""Selftest for sonnet_batch.py's integrity refusals (8 Oct). No model, no real lane: every path is
redirected into a temp dir. Must print SONNET_BATCH SELFTEST PASS.

    .venv-ms/bin/python tools/test_sonnet_batch.py
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.pop("SONNET_ARM", None)
import sonnet_batch as B  # noqa: E402
import png_clean  # noqa: E402
from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem.Draw import rdMolDraw2D  # noqa: E402

RDLogger.DisableLog("rdApp.*")
fails = 0


def check(name, ok):
    global fails
    print(("  ok   " if ok else "  FAIL ") + name)
    fails += 0 if ok else 1


def refuses(fn, *a):
    try:
        fn(*a)
    except SystemExit as e:
        return e.code not in (0, None)
    except Exception as e:          # a crash is not a refusal
        print(f"       ({type(e).__name__}: {e})")
        return False
    return False


def draw(smi, path, meta):
    d = rdMolDraw2D.MolDraw2DCairo(300, 300)
    if not meta:
        d.drawOptions().includeMetadata = False
    rdMolDraw2D.PrepareAndDrawMolecule(d, Chem.MolFromSmiles(smi))
    d.FinishDrawing()
    Path(path).write_bytes(d.GetDrawingText())


T = Path(tempfile.mkdtemp(prefix="sbself."))
rows = [{"k": "ethanol_cid1", "n": "Ethanol", "t": "CCO", "s": "CCO", "v": "exact", "c": 90},
        {"k": "propanol_cid2", "n": "Propanol", "t": "CCCO", "s": "CCC", "v": "wrong", "c": 50},
        {"k": "dirty_cid3", "n": "Dirty", "t": "CCN", "s": "CCN", "v": "exact", "c": 80}]
imgs = T / "imgs"
imgs.mkdir()
draw("CCO", imgs / "ethanol_cid1.png", False)
draw("CCCO", imgs / "propanol_cid2.png", False)
draw("CCN", imgs / "dirty_cid3.png", True)          # carries the answer in zTXt, like the old corpus
B.WORK = T / "work"
B.WORK.mkdir()
B.RESULTS = B.WORK / "results.jsonl"
B.corpus = lambda: rows
B.image_index = lambda: {p.name: str(p) for p in imgs.glob("*.png")}
B.blind_dir = lambda slot: T / f"blind_{slot}"
B.wipe_scratch = lambda slot: []

# 1. a source PNG with a text chunk is refused; nothing is claimed
check("control: the dirty source really carries text", bool(png_clean.text_chunks((imgs / "dirty_cid3.png").read_bytes())))
check("claim of a metadata-bearing image is REFUSED", refuses(B.cmd_claim, "s1", ["dirty_cid3"]))
# 2. a clean claim writes pixel-only blind copies with the same pixels
check("claim of clean images succeeds", B.cmd_claim("s2", ["ethanol_cid1", "propanol_cid2"]) == 0)
blind = sorted((T / "blind_s2").glob("*.png"))
check("two blind images written", len(blind) == 2)
check("blind copies are pixel-only", all(not png_clean.foreign_chunks(p.read_bytes()) for p in blind))
check("blind copy pixels == source pixels",
      png_clean.pixel_hash(blind[0].read_bytes()) == png_clean.pixel_hash((imgs / "ethanol_cid1.png").read_bytes()))
# 3. a slot holds one claim
check("second claim on an OPEN slot is REFUSED", refuses(B.cmd_claim, "s2", ["dirty_cid3"]))
check("next on an OPEN slot is REFUSED", refuses(B.cmd_next, 1, "s2"))
pend = json.load(open(B.pending_path("s2")))
check("the open claim was not overwritten", [b["k"] for b in pend] == ["ethanol_cid1", "propanol_cid2"])


def answers(obj):
    time.sleep(0.01)
    p = T / "ans.json"
    p.write_text(json.dumps(obj))
    os.utime(p, None)
    return str(p)


# 4. score refusals
check("duplicate answers for one image REFUSED",
      refuses(B.cmd_score, answers([{"img": "img01", "smiles": "CCO"}, {"img": "img01.png", "smiles": "CC"},
                                    {"img": "img02", "smiles": "CCCO"}]), "s2"))
check("list-valued answer REFUSED",
      refuses(B.cmd_score, answers([{"img": "img01", "smiles": ["CCO", "OCC"]}, {"img": "img02", "smiles": "CCCO"}]), "s2"))
check("'A or B' answer REFUSED",
      refuses(B.cmd_score, answers([{"img": "img01", "smiles": "CCO or CCCO"}, {"img": "img02", "smiles": "CCCO"}]), "s2"))
check("whitespace-only answer REFUSED",
      refuses(B.cmd_score, answers([{"img": "img01", "smiles": "  "}, {"img": "img02", "smiles": "CCCO"}]), "s2"))
check("number answer REFUSED",
      refuses(B.cmd_score, answers([{"img": "img01", "smiles": 42}, {"img": "img02", "smiles": "CCCO"}]), "s2"))
check("nothing was written by the refusals", not B.RESULTS.exists())
# a clean answers file scores; null = unreadable is allowed
check("clean answers score",
      B.cmd_score(answers([{"img": "img01", "smiles": "OCC"}, {"img": "img02", "smiles": None}]), "s2") == 0)
res = [json.loads(l) for l in open(B.RESULTS)]
check("verdicts: exact + invalid", [r["sonnet_verdict"] for r in res] == ["exact", "invalid"])
# 5. a key already scored cannot be scored again through a forged claim
B.pending_path("s3").write_text(json.dumps([dict(pend[0], slot="img01")]))
check("re-scoring an already-scored key REFUSED",
      refuses(B.cmd_score, answers([{"img": "img01", "smiles": "CCO"}]), "s3"))
check("results still hold 2 rows", sum(1 for _ in open(B.RESULTS)) == 2)

print("SONNET_BATCH SELFTEST " + ("PASS" if not fails else f"FAIL ({fails})"))
sys.exit(1 if fails else 0)
