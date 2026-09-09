# Six real documents, scored against ground truth built from the documents

`ground_truth/pdf_manifest_round34.json` is new: 75 distinct compounds across six
documents, resolved from the PDFs themselves (PubChem CID by printed name, plus a
reading of the drawing, required to agree). 43 further drawn compounds are recorded
as unresolved rather than guessed — see `ROUND34_GROUNDTRUTH_NOTES.md`.

These six had finished pipeline runs sitting on disk for a day with no manifest that
carried a SMILES. This is the first time they have been scored.

## All six

| metric | strict | graded |
|---|---|---|
| precision | 35/160 = 21.9% | 83/160 = 51.9% |
| recall | 25/75 = 33.3% | 52/75 = 69.3% |

Of the 116 structures the strict metric calls `wrong`, **50 (43%) are the drawn
molecule written differently**; 64 are genuinely a different molecule.

## Excluding the PMC review

`PMC10180415_approved2022_aa_fluorine` draws 84 compounds; the manifest resolves 41.
A correctly-read structure that is not among those 41 scores `wrong`, not `no-truth`,
so **its precision is a lower bound**. Over the other five documents:

| metric | strict | graded |
|---|---|---|
| precision | 22/56 = 39.3% | 39/56 = 69.6% |
| recall | 12/34 = 35.3% | 17/34 = 50.0% |

## Per document

| group | drawn | emitted | strict exact | recovered (strict) |
|---|---|---|---|---|
| ntp_roc_pahs | 15 | 6 | 6 | 6 |
| CN108503621B_vonoprazan | 12 | 37 | 16 | 6 |
| PMC10180415 (partial manifest) | 41 | 104 | 13 | 13 |
| ntp_roc_heterocyclicamines | 4 | 8 | 0 | 0 |
| DE60100786T2_citalopram_german | 2 | 4 | 0 | 0 |
| ntp_roc_cisplatin | 1 | 1 | 0 | 0 |

`ntp_roc_pahs` is the clean case: every structure it emitted was exact. It also shows
the other half of the problem — 15 compounds are drawn and 6 came back, because two
of its three figures produced no segments at all.

## Reference caveats that change how to read this

Carried from `ROUND34_GROUNDTRUTH_NOTES.md`, all recorded in the manifest entries:

- **cisplatin** — PubChem's record is disconnected (`N.N.Cl[Pt]Cl`); the drawing is
  bonded cis square-planar Pt. A bonded reading is a different InChIKey, and neither
  form encodes cis vs trans. A miss here is a representation mismatch, not a misread.
- **vonoprazan** — the fumarate is drawn as a two-component salt, so a segmenter that
  splits it emits two structures matching *different* manifest rows than the salt row.
- **citalopram_german** — 5 drawings are 3 distinct things; one is a Markush formula
  with no SMILES by construction, and the ionic liquid's drawn charge placement gives
  a different canonical SMILES from PubChem's despite the same InChIKey.
- **pahs** — the fine isomer assignment rests on the printed CAS number; the drawing
  confirms only ring count, size and topology.

Scored run: `/root/cmage-work/scored/round34/`.
