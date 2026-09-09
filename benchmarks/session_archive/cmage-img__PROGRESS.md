# High-resolution PubChem corpus — progress log

## Batch 0 — API investigation (before any bulk download)

### PubChem PUG REST `/PNG` size parameters
| request | returned size | verdict |
|---|---|---|
| (no params) | 300x300 | default |
| `?image_size=large` | **300x300** | **SILENTLY IGNORED — trap** |
| `?width=1000&height=1000` | **300x300** | **SILENTLY IGNORED — trap** |
| `?image_size=800x800` | 800x800 | works |
| `?image_size=1000x1000` | 1000x1000 | works |
| `?image_size=1500x1500` | 1500x1500 | works |
| `?image_size=2000x2000` | 2000x2000 | works |
| `?image_size=4000x4000` | 4000x4000 | works — MAX |
| `?image_size=6000x6000` | HTTP 400 PUGREST.BadRequest | above max |

So `image_size=WxH` is the ONLY working form; max is 4000x4000.
`image_size=large` and `width=/height=` both return 300x300 with HTTP 200 —
exactly the silent-failure mode we were told to guard against.

### !!! BLOCKING FINDING: PubChem does NOT scale type with canvas
Connected-component measurement, aspirin CID 2244, glyph = compact ink blob:

| canvas | molecule ink bbox | atom-label glyph height | bond stroke width |
|---|---|---|---|
| 300x300 | 150x144 | **10 px** | 1-3 px |
| 1000x1000 | 528x505 | **10 px** | 1-3 px |
| 1500x1500 | 798x762 | **10 px** | 1-3 px |
| 2000x2000 | 1070x1020 | **10 px** | 1-3 px |
| 4000x4000 | 1734x1281 | **10 px** | 1-3 px |

The skeleton scales linearly with the canvas; the FONT AND STROKE DO NOT.
Atom labels are a fixed ~10 px tall at every canvas size 300..4000.
Ink fraction falls 1.03% -> 0.069% from 300 to 4000 for the same reason.

Consequence: a native PubChem 1500x1500 depiction has labels that are
*relatively 5x SMALLER* than the same labels in the 300x300 depiction. Any
recogniser that resizes to a fixed input (MolScribe 384, DECIMER ~512) will see
labels that are SUB-PIXEL. Native PubChem hi-res is predicted to be WORSE, not
better, than 300x300.

This is NOT what FINDINGS.md finding 2 tested. That test LANCZOS-upscaled the
300px source 4x, which preserves the label:canvas ratio and only adds smoothness.
Native-render and upscale are different interventions. Do not conflate them.

Next: probe other PubChem image endpoints (imgsrv.fcgi) for one that scales type.

### !!! SECOND BLOCKING FINDING: glyph size at the model input DECREASES with canvas size
MolScribe preprocessing (`molscribe/dataset.py:get_transforms`, `interface.py:42`):
`CropWhite(pad=5)` then `A.Resize(384, 384)`. Input is ALWAYS squashed to 384x384.

And `CropWhite` (augment.py:97) tests `img != (255,255,255)` **exactly**.
**PubChem PNG background is (245,245,245), not white** — verified on both a fresh
fetch and on the existing corpus (`abacavir_pubchem.png`). So `x.sum()` is nonzero
on every row and column and **CropWhite crops NOTHING on any PubChem image.**
The full canvas, margins and all, is resized to 384.

Measured, aspirin CID 2244, effective atom-label height in the 384px tensor the
model actually sees:

| PubChem canvas | ink bbox | glyph px | glyph px at 384 (no crop, = reality) | (if crop worked) |
|---|---|---|---|---|
| 100x100 | 51x48 | 5 | **19.2** | 37.6 |
| 150x150 | 68x66 | 7 | **17.9** | 39.5 |
| 200x200 | 95x92 | 8 | **15.4** | 32.3 |
| 250x250 | 123x118 | 8 | **12.3** | 25.0 |
| 300x300 | 151x145 | 10 | **12.8** | 25.4 |
| 500x500 | 259x248 | 10 | **7.7** | 14.8 |
| 1000x1000 | 529x506 | 10 | **3.8** | 7.3 |
| 1500x1500 | 798x762 | 10 | 2.6 | 4.8 |

Bigger PubChem canvas = STRICTLY SMALLER type at the model input. The hypothesis
as stated ("fetch bigger images from PubChem and the score goes up") is predicted
to be FALSE, and predicted to go the wrong way.

Also: `image_size=large` and `width=/height=` silently return 300x300 (HTTP 200).
imgsrv.fcgi ignores width/height too and returns a 100x100 thumbnail.
PUG REST /SVG is HTTP 400 — not offered.

### Why FINDINGS-2's 4x LANCZOS upscale DID work, then
Upscaling does not change the label:canvas ratio, so post-Resize geometry is
identical (12.8px glyph either way). What it changes is INTERPOLATION: 150->384
cv2 INTER_LINEAR upsampling of a 1px hairline drawing aliases badly; 600->384
downsampling of a LANCZOS-smoothed drawing is clean. The phantom I/[HH] atoms
look like an ALIASING artifact, not a resolution artifact. That distinction
predicts native hi-res will not reproduce the FINDINGS-2 win.

### Plan revision
PubChem cannot serve a genuinely higher-resolution DEPICTION (type and stroke are
pinned at ~10px / 1-3px at every canvas from 100 to 4000). To test the hypothesis
honestly, build aligned arms and let the pipeline decide:
  corpus_300/            PubChem native 300x300        (baseline, = existing run)
  corpus_hires/          PubChem native 1500x1500      (the literal ask)
  corpus_upscaled_1200/  300px LANCZOS x4              (FINDINGS-2 intervention at scale)
  corpus_rdkit_1500/     RDKit from PubChem SMILES     (TRUE hi-res: scaled type, white bg)
  corpus_rdkit_300/      RDKit at 300                  (depiction-style control)
All keyed by CID, one manifest each.

## Batch 1 — renderer comparison (measured, aspirin CID 2244)

RDKit MolDraw2DCairo with `maxFontSize=-1` + `scaleBondWidth=True` DOES scale type:

| renderer / canvas | bg | ink bbox | glyph px | glyph px in the 384 model tensor |
|---|---|---|---|---|
| PubChem 300 | 245 (grey) | 151x145 | 10 | 12.8 (CropWhite is a no-op) |
| PubChem 1500 | 245 (grey) | 798x762 | 10 | 2.6 |
| RDKit 300 | 255 (white) | 271x219 | 18 | 24.8 (CropWhite works) |
| RDKit 1000 | 255 | 901x723 | 56 | 24.1 |
| RDKit 1500 | 255 | 1351x1085 | 84 | 24.0 |
| RDKit 2000 | 255 | 1801x1445 | 113 | 24.1 |

RDKit holds effective glyph size constant while adding real pixels — that is what
"higher resolution" is supposed to mean. It also fills 90% of the canvas vs
PubChem's ~50%, and its background is pure white so MolScribe's CropWhite fires.

Even at 300x300, an RDKit depiction gives the model 24.8px type against PubChem's
12.8px — a ~2x effective-resolution gain with no extra pixels at all.

Corpus scripts written: /tmp/cmage-img/{pug.py,resolve_cids.py,select.py,build_corpus.py}
CID resolution running (1045 names: 764 from the drug corpus + 281 curated).

## Batch 2 — CID resolution + selection (done)
- 1045 names resolved via PUG REST name->cid (764 drug names from
  /root/ringleader/tests/pubchem_ground_truth.json + 281 curated across chemistry
  classes). 667/740 and 273/281 resolved; **831 unique CIDs**.
- Batch property fetch (POST, 100 CIDs/call): 831/831 returned. NOTE PubChem now
  returns the keys `SMILES` (isomeric) and `ConnectivitySMILES`; the legacy
  `IsomericSMILES`/`CanonicalSMILES` request names still work as aliases.
- 827 usable after RDKit validation (4 rejected: <2 heavy atoms).
- **560 selected** with rare classes quota-filled first. Tag counts:
  stereocentres 312 · small 272 · tiny 113 · medium 108 · acyclic 89 · charged 83 ·
  polycyclic_aromatic 78 · large 67 · peptide_like 59 · macrocycle 59 ·
  multicomponent 58 · organometallic 46 · double_bond_stereo 46 ·
  heteroatom_rich 34 · isotope 6.  422 from the drug corpus, 138 curated.
- Corpus build running: 5 arms x 560. Every PNG verified (magic + PIL decode +
  exact dimensions) or deleted and logged.

## Batch 3 — corpus BUILT and independently verified

560 compounds x 5 aligned arms = 2800 PNGs, **0 failures**.

Dimension audit run TWICE by different code paths: once by the builder (PIL
open + verify + load + exact-size assert, delete on failure) and once
independently with libmagic reading the PNG IHDR (`file`):

| arm | files | libmagic says | non-PNG |
|---|---|---|---|
| corpus_300 | 560 | 560 x "300 x 300" | 0 |
| corpus_hires | 560 | 560 x "1500 x 1500" | 0 |
| corpus_upscaled_1200 | 560 | 560 x "1200 x 1200" | 0 |
| corpus_rdkit_1500 | 560 | 560 x "1500 x 1500" | 0 |
| corpus_rdkit_300 | 560 | 560 x "300 x 300" | 0 |

**No image is secretly 300x300.** The size parameter was honoured on all 560.

Corpus-wide geometry (all 560 per arm, not a sample):

| arm | ink-bbox fill of canvas (median) | median ink fraction | background |
|---|---|---|---|
| corpus_300 | 0.817 | 1.613% | 245 |
| corpus_hires | 0.886 | 0.321% | 245 |
| corpus_upscaled_1200 | 0.819 | 2.056% | 245 |
| corpus_rdkit_1500 | 0.901 | 1.399% | **255** |
| corpus_rdkit_300 | 0.900 | 2.226% | **255** |

Effective atom-label height in MolScribe's 384x384 input tensor, median over 40
real molecules (this is the number that decides the experiment):

| arm | native glyph px | **glyph px at the model input** |
|---|---|---|
| corpus_300 | 10.0 | **12.8** |
| corpus_hires | 10.0 | **2.6**  <-- 5x WORSE |
| corpus_upscaled_1200 | 42.0 | **13.4** |
| corpus_rdkit_1500 | 43.0 | **12.2** |
| corpus_rdkit_300 | 10.5 | **14.9** |

Disk: 115 MB for all five arms (2.5 + 12 + 56 + 38 + 6.6). Budget was 500 MB.
`df -h /` unchanged at 81% / 28G free.

Files: manifest.json (score_run manifest for corpus_hires + arm index),
manifest_<arm>.json x5, manifest_smoke_<arm>.json x5, selected.json (560 records
with tags), build_state.json (per-file verified dims), cids.json, size_report.json,
glyph_report.json.

Smoke test running: 50 aligned images per arm x 5 arms, stage 3 only, CPU.
Subset = 16 of FINDINGS-2's 24 phantom offenders + 34 stratified over the tags.

## Batch 4 — smoke test, arm 1 of 5 (corpus_300, the baseline)
50 images, stage 3 only, CPU, 157s (3.1 s/image).

| metric | value |
|---|---|
| strict whole-SMILES exact | 3/50 = 6.0% |
| strict, stereo relaxed | 4/50 = 8.0% |
| **largest-fragment exact** | **29/50 = 58.0%** |
| largest-fragment, stereo relaxed | 31/50 = 62.0% |
| invalid | 11 |
| predictions with phantom fragments | 33/50 = 66.0% |
| worst single prediction | 106 fragments |
| high-confidence tier | 5 @ 80% correct |

This reproduces the existing 743-image run closely (62.2% largest-fragment,
68.5% phantom rate) on a deliberately harder corpus, so the baseline is sound
and the arms are comparable. Signature is identical, e.g.
`5-fluorouracil -> I.I.O=c1[nH]cc(F)c(=O)[nH]1.[HH]` (core exact).

## Batch 5 — two extra free arms added (single-variable, no new downloads)
The PubChem background is (245,245,245). MolScribe's `CropWhite` tests
`img != (255,255,255)` EXACTLY, so it crops nothing on any PubChem image and the
whole canvas — margins and all — is squashed to 384x384. Two corpus-side fixes
that cost nothing were therefore added as arms:

- `corpus_300_white/`      560 x 300x300, background 245 -> 255, nothing else.
                           CropWhite then crops to a bbox that is 0.805 of the
                           canvas (median of 40) = 1.24x free magnification.
- `corpus_white_up1200/`   560 x 1200x1200, the above then LANCZOS 4x.
                           Both corpus-side fixes at once.

Both verified 560/560 at the stated size with libmagic. Queued behind the main
smoke driver as arms 6 and 7. Disk now 82% (was 81%); corpus total ~175 MB.

## Batch 6 — !!! HEADLINE RESULT: corpus_hires (PubChem native 1500x1500)

Same 50 CIDs, same molecules, same pipeline, same scorer. ONLY the pixel size differs.

| metric | corpus_300 (300x300) | corpus_hires (1500x1500) |
|---|---|---|
| strict whole-SMILES exact | 3/50 = 6.0% | **0/50 = 0.0%** |
| **largest-fragment exact** | **29/50 = 58.0%** | **0/50 = 0.0%** |
| largest-fragment, stereo relaxed | 62.0% | 0.0% |
| invalid predictions | 11 | **28** |
| wrong | 8 | 22 |
| high-confidence tier | 5 (@80% correct) | **0** |
| predictions with phantom fragments | 33/50 = 66% | 8/50 = 16% |
| stage-3 wall clock | 157s | 199s |

**The hypothesis is refuted, and refuted hard.** Feeding PubChem's own
higher-resolution depiction does not close the gap; it takes largest-fragment
accuracy from 58% to zero. Every prediction fell to the low-confidence tier.

Note the trap in the last row: **the phantom-fragment rate improved, 66% -> 16%.**
Read alone that looks like the predicted win. It is not — the phantoms vanished
because the model stopped producing recognisable molecules at all. A metric whose
failure mode looks identical to its success mode.

Mechanism, measured beforehand and confirmed: PubChem pins atom-label type at
~10px at every canvas size, so a 1500x1500 depiction carries labels 2.6px tall
once MolScribe's mandatory `Resize(384,384)` has run, against 12.8px at 300x300.

## Batch 7 — corpus_upscaled_1200 (300px source, LANCZOS x4). FINDINGS-2 replicates.

| metric | corpus_300 | corpus_hires | **corpus_upscaled_1200** |
|---|---|---|---|
| strict whole-SMILES exact | 6.0% | 0.0% | **46.0%** |
| strict, stereo relaxed | 8.0% | 0.0% | **48.0%** |
| largest-fragment exact | 58.0% | 0.0% | **68.0%** |
| largest-fragment relaxed | 62.0% | 0.0% | **70.0%** |
| invalid | 11 | 28 | **7** |
| phantom-fragment rate | 66% | 16% | **32%** |

FINDINGS-2 replicates on a bigger, harder, independent sample — and the size of
the effect on the STRICT metric is the story: 6.0% -> 46.0%, a 7.7x lift, because
the phantom `I`/`[HH]` atoms that ruined the whole-string comparison are halved.

But note what this is NOT. LANCZOS upscaling adds no information. Geometrically
it is a no-op through MolScribe's `Resize(384,384)`: glyphs land at 13.4px against
12.8px for the raw 300px image. The ONLY thing that changed is INTERPOLATION
quality — a smooth downsample of a smoothed image, instead of cv2 INTER_LINEAR
upsampling a 1px hairline drawing.

**So the phantom fragments are an ALIASING artifact, not a resolution artifact.**
That is why native hi-res (which fixes resolution and wrecks scale) fails while
upscaling (which fixes nothing but aliasing) wins.

## Batch 8 — corpus_rdkit_1500 (TRUE high resolution: type and strokes scale, white bg)

| metric | corpus_300 | corpus_hires | corpus_upscaled_1200 | **corpus_rdkit_1500** |
|---|---|---|---|---|
| **strict whole-SMILES exact** | 6.0% | 0.0% | 46.0% | **84.0%** |
| largest-fragment exact | 58.0% | 0.0% | 68.0% | **76.0%** |
| invalid | 11 | 28 | 7 | **4** |
| phantom-fragment rate | 66% | 16% | 32% | **10%** |
| high-confidence tier n | 5 | 0 | — | **36** |

84% strict against a 6.0% baseline on the identical 50 molecules. High-confidence
count goes 5 -> 36 of 50.

NOTE an artifact worth reporting: strict (84%) is HIGHER than largest-fragment
(76%) here. That is not a scoring bug — 8 of the 50 ground truths are genuine
MULTI-COMPONENT species (salts, co-crystals). When the prediction is correctly
multi-component, taking the largest fragment DESTROYS a right answer. On a corpus
that deliberately includes salts, largest-fragment scoring has its own bias and
should not be quoted alone.

Still to separate: is this RESOLUTION or RENDERER STYLE + white background?
corpus_rdkit_300 (same renderer, 300x300) is the control that answers it.

## Batch 9 — corpus_rdkit_300 (renderer control at the SAME 300x300 as the baseline)

| metric | corpus_300 (PubChem 300) | **corpus_rdkit_300** | corpus_rdkit_1500 |
|---|---|---|---|
| strict whole-SMILES exact | 6.0% | **76.0%** | 84.0% |
| largest-fragment exact | 58.0% | **68.0%** | 76.0% |
| invalid | 11 | **2** | 4 |
| phantom-fragment rate | 66% | **14%** | 10% |
| high-confidence tier n | 5 | **29** | 36 |

### The decomposition
Same 50 molecules throughout; each step changes exactly one thing.

| step | strict exact | delta |
|---|---|---|
| PubChem 300x300 (baseline, = the existing benchmark) | 6.0% | — |
| -> PubChem 1500x1500 (MORE PIXELS, same depiction) | 0.0% | **-6 pp** |
| -> PubChem 300 upscaled 4x (aliasing fix only) | 46.0% | +40 pp |
| -> RDKit at the SAME 300x300 (renderer swap only) | 76.0% | **+70 pp** |
| -> RDKit at 1500x1500 (renderer + REAL resolution) | 84.0% | +8 pp |

**Resolution is worth about +8 pp of a ~78 pp gap — roughly a tenth.** The corpus
really is capping the score, and by a huge margin, but the cap is the DEPICTION
(hairline strokes, 10px type, (245,245,245) background, cv2 aliasing), not the
pixel count. Asking PubChem for more pixels makes it worse, not better.

## Batch 10 — FINAL: all 7 arms, 50 aligned images each, stage 3 only, CPU

| arm | pixels | strict exact | largest-frag exact | invalid | phantom preds | total frags | max frags | high-conf n |
|---|---|---|---|---|---|---|---|---|
| corpus_300 (baseline) | 300 | 6.0% | 58.0% | 11 | 66% | 261 | 106 | 5 |
| corpus_300_white | 300 | **56.0%** | 66.0% | 7 | 18% | 62 | 5 | 32 |
| corpus_upscaled_1200 | 1200 | 46.0% | 68.0% | 7 | 32% | 67 | 5 | 35 |
| corpus_white_up1200 | 1200 | 54.0% | 68.0% | 7 | 22% | 62 | 5 | 28 |
| corpus_hires | **1500** | **0.0%** | **0.0%** | 28 | 16% | 40 | 8 | **0** |
| corpus_rdkit_300 | 300 | 76.0% | 68.0% | 2 | 14% | 59 | 3 | 29 |
| corpus_rdkit_1500 | **1500** | **84.0%** | **76.0%** | 4 | 10% | 55 | 3 | **36** |

(strict = score_run.py whole-SMILES; largest-frag = rescore_fragments.py.
Only 1 of 350 predictions carried a CXSMILES abbreviation block, so abbreviation
expansion is not a confounder here.)

### Paired, same CID, McNemar exact
STRICT metric — every gain has ZERO regressions:

| arm | correct | improved | regressed | p |
|---|---|---|---|---|
| corpus_300 | 4/50 | — | — | — |
| corpus_300_white | 29/50 | 25 | **0** | 6.0e-08 |
| corpus_upscaled_1200 | 24/50 | 20 | **0** | 1.9e-06 |
| corpus_white_up1200 | 29/50 | 25 | **0** | 6.0e-08 |
| corpus_hires | **0/50** | 0 | 4 | 0.125 |
| corpus_rdkit_300 | 39/50 | 35 | **0** | 5.8e-11 |
| corpus_rdkit_1500 | 42/50 | 38 | **0** | 7.3e-12 |

LARGEST-FRAGMENT metric — the gains are NOT significant at n=50:
300_white +5/-1 p=0.22 · upscaled +4/-0 p=0.13 · white_up1200 +7/-1 p=0.070 ·
rdkit_300 +6/-2 p=0.29 · rdkit_1500 +9/-2 p=0.065 ·
**corpus_hires 0 up / 31 down, p=9.3e-10**.
That is expected: largest-fragment scoring already forgives the phantoms the
corpus fixes remove. The full 560 run is needed to call those +8..+18pp gains.

### Worst-offender trace (fragments, same molecule across arms)
| image | 300 | 300_white | upscaled_1200 | hires | rdkit_1500 |
|---|---|---|---|---|---|
| epinephrine | **106f** exact | 2f exact | 4f exact | 1f invalid | 1f exact |
| adenosine monophosphate | 8f exact | 5f exact | 5f exact | 1f invalid | 1f exact |
| dopamine | 7f exact | 2f exact | 2f exact | 2f wrong | 1f exact |
| gemfibrozil | 7f exact | 1f exact | 1f exact | 8f wrong | 1f exact |
| oxalic acid | 6f exact | 1f exact | 2f exact | 1f invalid | 1f exact |
Total fragments over the 50: 285 -> 74 (white bg) -> 62 (rdkit 1500) -> 78 (hires,
but only because it stopped emitting molecules).

### Ground-truth integrity
- RDKit InChIKey of the stored isomeric SMILES == PubChem's InChIKey: **560/560**
- RDKit formula (element counts) == PubChem's MolecularFormula: **560/560**

### Disk
`df -h /` 81% / 28G free before, **82% / 28G free after**. Corpora 185 MB,
cache 28 MB, run outputs 19 MB; 234 MB total, budget was 500 MB.

### VERDICT ON THE HYPOTHESIS
The corpus IS capping the score — by a very large margin — but **not through
resolution**. Asking PubChem for more pixels is actively harmful (58% -> 0%).
The cap is the DEPICTION: a (245,245,245) background that defeats MolScribe's
CropWhite, hairline 1-3px strokes, and 10px type that never grows.
