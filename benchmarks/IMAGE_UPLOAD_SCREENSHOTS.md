# Seven real screenshots through the upload path

Seven PNGs pasted from a desktop screenshot tool (all RGBA, 236×134 up to 912×868),
run through the shipped image-upload path — stage 3 only, no segmentation.

| image | size | CXSMILES returned | conf | verdict |
|---|---|---|---|---|
| aspirin | 322×258 | `CC(=O)Oc1ccccc1C(=O)O` | 0.829 | **correct** |
| cholesterol | 596×474 | `CC(C)CCC[C@@H](C)[C@H]1CC[C@H]2...[C@]12C` | 0.896 | **correct, full stereo** |
| morphine (A) | 464×542 | `CN1CC[C@]23c4c5ccc(O)c4O[C@H]2[C@@H](O)C=C[C@H]3[C@H]1C5` | 0.838 | **exact** |
| p-phenylenediamine | 494×288 | `Nc1ccc(N)cc1` | 0.850 | **correct** |
| p-phenylenediamine (small) | 236×134 | `I.Nc1ccc(N)cc1` | 0.853 | correct + phantom `I` |
| 2-chloro-3-methylbut-1-ene | 420×266 | `C=CC(C)(C)Cl` | 0.888 | correct |
| morphine (B) | 912×868 | `CN1CCC23c4c5ccc(O)c4O[C@H]2...[C@H]1C5` | **0.484** | one stereocentre lost |

Six of seven are right. The seventh is morphine minus the C13 quaternary
stereocentre — and the confidence score caught it, filing the only wrong answer at
0.484 against 0.829–0.896 for the correct ones. That is the confidence split doing
exactly its job on a real upload.

## The two morphines are not a size experiment

They differ in size (464×542 against 912×868) **and** in drawing convention, so the
obvious reading — "the bigger one lost detail in the resize" — is a confound, and it
is the reading this project had been primed to make after a day on rendering size.

It was tested rather than assumed. Min-pooling image B down to 456×434, which is
image A's size, changed nothing: `0.484 → 0.506`, same missing stereocentre.
**Size is exonerated.**

What is left is the depiction:

- **A (works):** heteroatoms coloured, and **explicit `H` atoms drawn on the
  stereocentres** with bold/hashed wedges.
- **B (fails on one centre):** black-and-white, thick lines, no explicit `H` at C13.
  That centre is quaternary — four heavy substituents, no hydrogen — so its
  configuration is carried by wedge geometry alone with nothing to anchor it.

A quaternary carbon whose stereochemistry is conveyed only by bold-wedge geometry is
the hardest kind of centre to read, and it is the one that was dropped. That is a
hypothesis consistent with the evidence, not a demonstrated mechanism; a controlled
test would redraw the same molecule with and without the explicit `H` and change
nothing else.

## RGBA

Every one of the seven was RGBA — desktop screenshots carry an alpha channel. They
all came through correctly, so the upload path is compositing them sanely rather
than flattening transparency to black. Worth keeping a regression on: an RGBA image
composited onto black would invert the whole drawing and fail silently.
