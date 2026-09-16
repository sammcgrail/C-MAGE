"""The Sonnet arm: a general vision model reading the same drawings, scored the same way.

The comparison is only worth anything if it is fair, so three things are fixed:

  * The SAMPLE is a deterministic stride over the sorted corpus, not a hand-pick.
    A curated ten is a claim about the curator.
  * The FILENAMES are anonymised. The corpus names images `testosterone_cid6013`,
    so a model given the path could answer from the string without looking at the
    picture at all, and would score well for the wrong reason.
  * The SCORING is identical: RDKit canonical isomeric SMILES equality for exact,
    equality after dropping stereochemistry for stereo. Same function, same
    references, no separate leniency for either reader.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/root/C-MAGE/tools")
from build_wall import WALL, THRESHOLD, render_pred, thumb, relate     # noqa: E402


PROMPT_TEXT = """Read ten chemical structure drawings and give the SMILES for each.

Images (use the Read tool on each — they render as images):
/tmp/blind_<slot>/img01.png … img10.png

For each, write the SMILES for the structure depicted. Stereochemistry where the
drawing shows it (wedge/hash, E/Z). All fragments if more than one is drawn
(salts, counter-ions), dot-separated.

RULES:
- Work from the DRAWING. If you recognise the molecule you may cross-check, but
  the drawing is the authority — say so if they conflict.
- COUNT THE ATOMS EXPLICITLY before writing. An earlier batch read a chain with
  one extra CH2, turning lactic acid into 3-hydroxybutyric acid, at high stated
  confidence. Count ring vertices and chain carbons.
- Exactly one SMILES per image. UNREADABLE rather than a guess, with a reason.
- Do NOT use RDKit or any cheminformatics tool to canonicalise or improve your
  answer. I want your reading.

OUTPUT — a JSON array:
[{"img": "img01", "smiles": "...", "name_if_recognised": "...",
  "confidence": "high|medium|low"}, ...]
All ten, in order."""

WORKFLOW = {
    "intro": ("Each reader is Sonnet in an agent loop, not a single vision call. It looks at the "
              "image, then writes and runs code to test what it sees, and iterates until its own "
              "re-drawing of the structure matches the source."),
    "tools": [
        {"t": "Read (vision)", "d": "Opens each PNG. The model's own eyes do the recognition; "
         "every atom, bond and wedge is read from the picture."},
        {"t": "Bash + Pillow / OpenCV", "d": "Crops and upscales dense regions 2–4x and overlays a "
         "pixel-coordinate grid, so bond vertices and wedge/hash directions are read off by "
         "position instead of guessed by eye."},
        {"t": "RDKit", "d": "Parses and valence-checks each SMILES, computes the molecular formula "
         "to cross-check a by-hand atom count, builds a molblock from measured coordinates so the "
         "CIP engine assigns R/S and E/Z from geometry rather than reasoning, and re-renders the "
         "structure to diff against the crop."},
        {"t": "OSRA", "d": "A separate optical structure-recognition engine, run as an independent "
         "second opinion. Where a reader leans on it, the reading is the model orchestrating "
         "another recogniser — noted, not hidden."},
        {"t": "numpy / scipy", "d": "Vertex and connected-component detection on the raw pixels, "
         "used to count long chains and pin label positions in crowded cores."},
    ],
    "steps": [
        "Read the whole image; identify the rings, chains and labels.",
        "Crop to each dense region and upscale it.",
        "Overlay a coordinate grid; read exact vertex positions and which bonds carry wedges or hashes.",
        "Build the molecule atom by atom, counting ring vertices and chain carbons explicitly.",
        "Let RDKit assign stereochemistry from the measured geometry.",
        "Re-render the SMILES and compare it to the crop; iterate on any mismatch.",
    ],
}

# Verified against results.jsonl on 2026-09-16 (the tile a card links to shows the reading).
EXAMPLES = [
    {"k": "carumonam_cid6540466", "outcome": "success", "title": "Carumonam — read exactly",
     "body": "A monobactam with an (Z)-oxime and two ring stereocentres. The reader measured the "
             "wedge geometry off the drawing, built a molblock, and let RDKit assign the "
             "configuration; the re-render matched the source. Scored exact."},
    {"k": "cabozantinib_cid25102847", "outcome": "success", "title": "Cabozantinib — read exactly",
     "body": "A quinoline diaryl-ether with a cyclopropane-1,1-dicarboxamide. Read cleanly in one "
             "pass, both amides and the two methoxy groups placed correctly. Scored exact."},
    {"k": "buprenorphine_cid644073", "outcome": "miss", "title": "Buprenorphine — under-read a dense cage",
     "body": "A bridged opioid cage. In the crowded bridge the reader traced a smaller ring system "
             "(formula C20 against the real C29), reported it as drawn under the drawing-is-authority "
             "rule, and flagged low confidence. It did not match the reference — the failure mode is "
             "a dense polycyclic core, not a careless read."},
    {"k": "brivaracetam_cid9837243", "outcome": "miss", "title": "Brivaracetam — right molecule, wrong stereo",
     "body": "The reader read both ring substituents as wedges (2S,4S) where the reference is 2S,4R. "
             "Correct connectivity, one stereocentre inverted — scored as a stereo-only miss."},
    {"k": "buserelin_cid50225", "outcome": "miss", "title": "Buserelin — a guanidine tautomer",
     "body": "A nonapeptide built residue by residue; the formula matched, but the arginine guanidine "
             "was drawn in a different tautomer than the reference, so the canonical strings differ. "
             "The kind of near-miss the strict whole-string score is meant to catch."},
]


def method_sections(excluded_n: int) -> list[dict]:
    """The method note as titled sections of bullets, so the page renders structure rather
    than one wall of prose. Kept to claims that hold at any batch size — no stale per-run
    tallies. `excluded_n` is read from the exclusion log at build time."""
    return [
        {"h": "Blinding",
         "points": [
             "Image filenames are anonymised before the model sees them. The corpus names each "
             "file after its compound (lactic_acid_cid612.png), so a real path would let the model "
             "answer from the string instead of the drawing.",
         ]},
        {"h": "What this arm is",
         "points": [
             "Sonnet running inside Claude Code with a shell, Python and RDKit — an agent with "
             "tools, not one vision API call.",
             "Readers routinely used RDKit to canonicalise their SMILES, to assign stereochemistry "
             "from coordinates they measured off the drawing, and to re-render and diff against the "
             "source. Some also ran OSRA (a second structure-recognition engine), OpenCV for bond "
             "angles, and OPSIN for names.",
             "So read it as 'an agent with chemistry tools', not 'the model'. CXMolScribe answers "
             "in one pass with no chance to repair its output, and round-tripping through RDKit "
             "turns some near-misses into exact matches. A bare single-call arm would score "
             "differently and cost less.",
         ]},
        {"h": "Self-reports are not trusted",
         "points": [
             "Reader summaries have been wrong in both directions: one claimed it used no "
             "cheminformatics tool while its working directory held dozens of RDKit scripts; "
             "another disclosed a PubChem lookup its transcript shows it never made.",
             "Tool use and exclusions are decided from the transcript, never from the reader's own "
             "account.",
         ]},
        {"h": "Answer-key access is excluded",
         "points": [
             "The reference answers are PubChem SMILES, so a reader that looks the compound up "
             "copies the key instead of reading the drawing.",
             "Every reader transcript is scanned for network requests to any host and for reads of "
             "the answer files; a flagged reading is excluded and the image is re-read blind.",
             f"{excluded_n} readings have been excluded this way and re-read. Every excluded reading "
             "that had already been published had scored exact — which is what a copied key looks "
             "like.",
         ]},
        {"h": "Content-filter refusals",
         "points": [
             "The image set includes toxins. On one batch the Sonnet API returned a content-policy "
             "refusal (a [bio] block) triggered by a marine neurotoxin (brevetoxin B).",
             "That reader had already completed and written all ten readings before the refusal, "
             "and its transcript was clean and Sonnet-served, so the batch still counts.",
             "A batch that refused before finishing would be dropped, not guessed.",
         ]},
    ]


def cost_note(cost, published):
    """The page's one-line cost estimate, over the published reads only, or None before any cost
    has been recorded. A reading excluded for a lookup was re-run, and the re-run is what the
    page shows, so the excluded reading's share of its run's cost is not in this figure."""
    if not cost or not cost.get("reads"):
        return None
    if cost["reads"] != published:
        print(f"  WARNING cost covers {cost['reads']} published reads, the payload has {published}")
    return {
        "usd": cost["cost_usd"], "reads": cost["reads"], "perImage": cost["per_image_usd"],
        "note": (f"Estimated API cost at list price: ${cost['cost_usd']:,.0f} for the {cost['reads']} "
                 f"Sonnet reads shown — about ${cost['per_image_usd']:.2f} per image."),
    }

def main() -> int:
    # Read the append-only results file, not a snapshot. The batch harness appends
    # to it, so the tab reflects every batch scored so far with no separate step to
    # forget.
    src = Path("/root/cmage-work/sonnet/results.jsonl")
    rows_in = [json.loads(l) for l in open(src) if l.strip()]
    img = WALL / "sonnet"
    pred = WALL / "sonnet_pred"
    ocr = WALL / "sonnet_ocr"
    for dd in (img, pred, ocr):
        dd.mkdir(parents=True, exist_ok=True)

    import glob
    idx = {}
    for dd in sorted(glob.glob("/root/cmage-work/cmage-img*/corpus_rdkit_1500")):
        for pth in glob.glob(dd + "/*.png"):
            idx.setdefault(os.path.basename(pth), pth)

    rows = []
    for r in rows_in:
        k = r["k"]
        src_img = idx.get(k + ".png")
        if not src_img:
            continue
        thumb(Path(src_img), img / f"{k}.png")
        has = render_pred(r.get("sonnet_smiles") or "", pred / f"{k}.png")
        # Draw the PIPELINE's answer as well. On this corpus the two readers
        # disagree in ways a SMILES string hides: CXMolScribe returns iodine as a
        # `J` abbreviation label here, which is invisible in the text and obvious
        # the moment it is drawn beside the input.
        has_ocr = render_pred(r.get("ocr_smiles") or "", ocr / f"{k}.png")
        # The tile's colour is the OUTCOME, not Sonnet's verdict alone. "Sonnet was
        # wrong" and "Sonnet was wrong where the pipeline was right" are different
        # facts, and the second is the one this tab exists to show.
        sv = r["sonnet_verdict"] == "exact"
        ov = r["ocr_verdict"] == "exact"
        outcome = ("both" if sv and ov else
                   "sonnet" if sv else
                   "cxms" if ov else "neither")
        rows.append({
            "k": k, "n": r["name"], "v": r["sonnet_verdict"], "g": r["sonnet_verdict"],
            "o": outcome,
            "c": None, "s": r.get("sonnet_smiles") or "", "t": r["truth"],
            "p": 1 if has else 0,
            "r": relate(r.get("sonnet_smiles") or "", r["truth"]),
            # Both readings travel with the row so the sheet can show them together.
            "ocr": r["ocr_smiles"], "ocrv": r["ocr_verdict"], "ocrc": r["ocr_conf"],
            # On this tab the extension block comes from the PIPELINE's string --
            # Sonnet was asked for SMILES and returned SMILES, so it has none.
            "cx": 1 if "|$" in (r.get("ocr_smiles") or "") else 0,
            "po": 1 if has_ocr else 0,
            "sconf": r.get("sonnet_conf"),
        })

    n = len(rows)
    s_ex = sum(1 for r in rows if r["v"] == "exact")
    o_ex = sum(1 for r in rows if r["ocrv"] == "exact")
    both = sum(1 for r in rows if r["v"] == "exact" and r["ocrv"] == "exact")
    either = sum(1 for r in rows if r["v"] == "exact" or r["ocrv"] == "exact")
    corpus_n = len(json.load(open(WALL / "images.json"))["rows"])
    # Cost at API list prices, from the tokens the readers used. It is recomputed from the
    # transcripts on every build, so the note keeps up with new batches. If that fails, the
    # saved per-reader costs are used; a costing problem must never block publishing results.
    try:
        import sonnet_cost
        cost = sonnet_cost.update()
    except Exception as e:
        print(f"  WARNING cost not refreshed: {e}")
        cp = WALL.parent / "sonnet_cost.json"
        cost = json.load(open(cp)) if cp.exists() else None
    # Attach the producing run's cost and wall-clock to each row, for the modal. One run reads
    # a batch in a single shared context, so cost/time are per batch and rc/rt are its per-image
    # share. Rows with no attributable run (e.g. an empty SMILES) simply carry no figures.
    per_key = (cost or {}).get("per_key", {})
    for r in rows:
        rc = per_key.get(r["k"])
        if rc:
            r["rc"], r["rt"] = rc["cost"], rc["secs"]
            r["bc"], r["bs"], r["bn"] = rc["batch_cost"], rc["batch_secs"], rc["batch"]
    d = {
        "arm": "Sonnet", "dir": "sonnet", "rows": rows,
        # Two readers, one denominator, shown at the same size. A single big
        # percentage with the other reader's score in prose underneath reads as a
        # headline plus a footnote; the point here is that they are comparable.
        "compare": {
            "n": n, "corpus": corpus_n,
            "sides": [
                {"label": "Sonnet + tools", "exact": s_ex, "pct": round(s_ex / n * 100, 1)},
                {"label": "CXMolScribe", "exact": o_ex, "pct": round(o_ex / n * 100, 1)},
            ],
            "agree": both, "either": either,
            "cost": cost_note(cost, n),
            # Ordered worst-understood to best so the stacked bar reads left to
            # right as "who got it": both, then each alone, then neither.
            "breakdown": [
                {"key": "both", "label": "Both right",
                 "n": sum(1 for r in rows if r["o"] == "both")},
                {"key": "sonnet", "label": "Sonnet only",
                 "n": sum(1 for r in rows if r["o"] == "sonnet")},
                {"key": "cxms", "label": "CXMolScribe only",
                 "n": sum(1 for r in rows if r["o"] == "cxms")},
                {"key": "neither", "label": "Neither",
                 "n": sum(1 for r in rows if r["o"] == "neither")},
            ],
        },
        "prompt": PROMPT_TEXT,
        "workflow": WORKFLOW, "examples": EXAMPLES,
        "method": method_sections(sum(1 for l in open(WALL.parent / "sonnet_excluded.jsonl") if l.strip())
                                  if (WALL.parent / "sonnet_excluded.jsonl").exists() else 0),
        "cx": sum(1 for r in rows if r.get("cx")),
        "cxLabel": "CXMolScribe returned CXSMILES",
        "stats": {"n": n, "exact": s_ex, "strict_pct": round(s_ex / n * 100, 1)},
        "heroLabel": f"of {n} — against CXMolScribe's {o_ex} on the same {n}",
        "threshold": round(THRESHOLD * 100),
        "headline": ("A general vision model reading the same drawings, scored by the same "
                     "rule as the pipeline. Not a bare model call: it runs in an agent loop "
                     "with a Python interpreter and RDKit, and it used them — see the method "
                     "below."),
        "footer": (
            "Sample is a deterministic stride over the sorted corpus, not a hand-pick. "
            "Filenames were anonymised before the model saw them, because the corpus names "
            "images after their compounds and a model given the path could answer without "
            "looking. Scored with the same RDKit canonical comparison as every other arm. "
            f"n={n}: this is a probe, not a benchmark, and no percentage from it should be "
            "quoted as if it were one."),
    }
    json.dump(d, open(WALL / "sonnet.json", "w"), separators=(",", ":"))
    print(f"  sonnet {s_ex}/{n}  cxmolscribe {o_ex}/{n}  both {both}  either {either}")
    print(f"  payload {os.path.getsize(WALL/'sonnet.json')/1e3:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
