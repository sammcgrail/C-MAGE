# Running C-MAGE on an ARM64 server

Upstream supports Linux x86_64, Windows and Apple Silicon. This fork adds
**Linux aarch64** (not macOS arm64 — see the platform note below), and replaces conda with [uv]. Every version pin is unchanged;
only the two things pip cannot express moved.

Verified end to end on: Ubuntu aarch64, 8 CPU cores, 15 GB RAM, **no GPU**.

## Reproduce it

```bash
git clone https://github.com/<your-fork>/C-MAGE.git && cd C-MAGE
./install-uv.sh                       # three venvs, ~10 min, ~4 GB
python3 tools/fetch_weights.py        # DECIMER weights, 260 MB, checksum-pinned
cp your.pdf MERMaid/pdfdir/
./run_pipeline.sh --device cpu
```

Results in `results/run_<timestamp>/03_CXMS_Results/`.

## What changed from upstream, and why

| Change | Reason |
|---|---|
| `envs/uv/*.txt` + `install-uv.sh` | conda not required. Same pins, same comments. |
| poppler → `apt install poppler-utils` | conda-only dep; `pdf2image` shells out to `pdftoppm` |
| `cudatoolkit` / `cudnn` dropped | this path is CPU-only. **A CUDA box should still use `install.sh`**, where conda pins the exact pair TF 2.12 needs. |
| 2 lines in `run_pipeline.{sh,py}` | they find an env by probing `<root>/<name>/bin/python`; `install-uv.sh` symlinks the uv venvs into `.venvs/` under the conda names, so one extra root is the whole diff |
| `patches/0001` | MolScribe's vendored Indigo is x86_64-only |
| `patches/0002` | DECIMER cached an HTTP error page as its model weights |
| `tools/fetch_weights.py` | the weights had a single point of failure |

**Still three environments.** The conflict is irreducible: stage 2's TensorFlow
2.12 requires `numpy < 1.24`, the torch stages require `>= 1.24`.

## Two corrections to the upstream platform notes

- *"plain `tensorflow` has no arm64 wheel at 2.12"* — true on **macOS**, false on
  **Linux**. `tensorflow-2.12.0-cp310-cp310-manylinux_2_17_aarch64.whl` exists, so
  Linux ARM needs no macOS-style workaround. (The wheel is a shim that pulls
  `tensorflow-cpu-aws`.)
- *`torchtext==0.5.0` "has no wheel and builds from an sdist, so this is the
  slowest part of the install"* — it ships `torchtext-0.5.0-py3-none-any.whl`,
  a pure-Python universal wheel. Nothing compiles.

## Indigo does not block inference

Worth stating plainly, because it looks like a blocker and is not: MolScribe's
vendored Indigo ships x86_64 `.so` files only, and `molscribe/dataset.py` does
`from .indigo import Indigo` at import. But the library is only `dlopen`'d when
an `Indigo()` object is **constructed**, which happens solely in training-time
augmentation. `from molscribe import MolScribe` and full inference work on ARM
with no patch at all. `patches/0001` exists so the augmentation path also works
(via `epam.indigo`'s aarch64 wheel); it is not needed to run C-MAGE.

Reproducing upstream's exact *training* recipe is **not** possible on ARM: it
needs `indigoCoords`, a function present only in MolScribe's own modified Indigo
binaries, whose source is not published. Train with `--pseudo_coords`.

## The weights are a single point of failure

`load_model()` downloads ~260 MB from one Zenodo URL, at **import time**. On
2026-09-08 Zenodo served 503 for hours; there is no official mirror, upstream
still points at the same URL, and the file is not on HuggingFace or PyPI.

Worse than the outage: the old code wrote `requests.get().content` to the cache
with no check, so the error page was cached **as the model**, and since the
download only runs when the file is absent, every later import then died with

```
OSError: Unable to open file (file signature not found)
```

naming neither Zenodo nor the cache. `patches/0002` validates before caching;
`tools/fetch_weights.py` adds retries, mirrors and an offline escape hatch:

```bash
DECIMER_WEIGHTS=/path/to/mask_rcnn_molecule.h5 tools/fetch_weights.py   # local copy
DECIMER_WEIGHTS_MIRRORS=https://your.mirror/w.h5 tools/fetch_weights.py
tools/fetch_weights.py --wait 3600                                     # ride out an outage
tools/fetch_weights.py --check                                         # ~1 s, verifies the cache
```

**Keep a local copy and point at it — do not re-fetch while iterating.** Zenodo
returned 504 three separate times in one day during this work. Once you have the
file, adopt it and never reach for the network again:

```bash
mkdir -p ~/cmage-models/decimer
ln -f ~/.cache/decimer/mask_rcnn_molecule.h5 ~/cmage-models/decimer/   # hardlink: no extra disk
export DECIMER_WEIGHTS=~/cmage-models/decimer/mask_rcnn_molecule.h5
```

A hardlink rather than a copy because it costs nothing and keeps the data alive
even if `~/.cache` is swept. For the slim Docker image, mount it:
`-v ~/cmage-models:/opt/cmage/models:ro`. A build or test that depends on a third
party being up is a test that fails for reasons unrelated to your change.

Known-good file: **272,650,600 bytes**, sha256
`329120facb69e88add819a3216db0fbfef57e9a37d6b6db0f6149819a11d46a5` (pinned).

## Accuracy note that is NOT ARM-specific — read before trusting output

On the repo's own `cxmolscribe-wd/DECIMER-Image-Segmentation/Validation/test_page.pdf`, the full pipeline produced 5
structures, all of them classified **high confidence**, and **two were the wrong
molecule**:

| Figure | Truth | Pipeline output | |
|---|---|---|---|
| 1 | caffeine | `C=C1NC(NC)=C(NC)C(=O)N1C` | wrong |
| 2 | paracetamol | `CC(=O)Nc1ccc(I)cc1` | wrong — OH read as iodine |
| 3 | ibuprofen | `CC(C)Cc1ccc(C(C)C(=O)O)cc1` | correct |

**The cause is stage 2, and the mechanism is erasure, not clipping.** It is
worth being precise, because the obvious reading — "the crop cut the molecule
off at the edge" — points at the wrong fix.

`apply_mask()` multiplies the page by the segmentation mask, thresholds the
result into an alpha channel, forces every non-mask pixel to white, and only
then crops to the mask's bounding box. So ink the mask failed to cover is
**deleted**, and what reaches stage 3 is a mutilated drawing sitting inside a
crop with clean, ink-free borders. Caffeine loses part of its fused imidazole
ring; paracetamol loses the O of its hydroxyl, leaving a bond that terminates in
nothing, which MolScribe resolves as `I`.

Two observations rule out the alternatives. The same stage 3 reads the
*uncropped* stage-1 figures correctly (caffeine 0.897990, paracetamol 0.894638),
so the recogniser is not the problem. And the failure persists at 300 dpi and at
3x upscale, so it is not resolution either.

That points at a fix, and this fork ships it as an opt-in:

```bash
DECIMER_BBOX_PAD=0.15 ./run_pipeline.sh --stages 2,3 --figures FIGS
```

It crops the **original** pixels at the mask bounding box plus a padding
fraction, instead of erasing everything outside the mask. Measured on the four
figures of the test page, same models, same stage 3, one variable:

| | default (`DECIMER_BBOX_PAD=0`) | `DECIMER_BBOX_PAD=0.15` |
|---|---|---|
| caffeine | `C=C1NC(NC)=C(NC)C(=O)N1C` **wrong**, 0.889446 | `Cn1c(=O)c2c(ncn2C)n(C)c1=O` **correct**, 0.901154 |
| paracetamol | `CC(=O)Nc1ccc(I)cc1` **wrong**, 0.898833 | `CC(=O)Nc1ccc(O)cc1` **correct**, 0.922076 |
| ibuprofen | correct, 0.898307 | correct, 0.900629 |
| recovered | 1 of 3 | **3 of 3** |

### Where this behaviour comes from — it is not this fork, and not really C-MAGE

Worth tracing, because the natural assumption is that a port broke something.

`git diff upstream/main HEAD` on `decimer_segmentation.py` deletes exactly three
lines, all of them the unguarded Zenodo download. The masking and cropping code
is untouched. So the behaviour is identical in unmodified C-MAGE.

It is not C-MAGE's invention either. C-MAGE vendors DECIMER-Image-Segmentation,
and current upstream DECIMER does the same thing in `_apply_single_mask`:

```python
rgba[alpha == 0] = [255, 255, 255, 255]      # every non-mask pixel -> white
```

There is one difference, and it does not favour the vendored copy. Upstream
DECIMER derives alpha **directly from the mask** (`alpha = (mask_roi * 255)`).
The copy vendored here is an older variant that first converts the masked image
to grayscale and applies an **Otsu threshold**, then derives alpha from *that*:

```python
im_gray = cv2.cvtColor(masked_image, cv2.COLOR_RGB2GRAY)
_, im_bw = cv2.threshold(im_gray, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
_, alpha = cv2.threshold(im_bw, 0, 255, cv2.THRESH_BINARY)
```

That is an extra lossy step upstream DECIMER no longer has, and it can remove
more than the mask alone would. In short: the erasure design is DECIMER's, and
the vendored copy is a stale variant of it. `DECIMER_BBOX_PAD` sidesteps the
whole chain by never consulting the alpha channel at all.

**It is off by default on purpose.** Padding can pull a neighbouring structure's
ink into the crop on a densely packed figure, which is the thing masking exists
to prevent — and default behaviour here is byte-identical to upstream. Turn it
on for sparse figures where accuracy matters more than isolation, and check the
segments.

The consequence for how you read confidence stands either way:

> **A high-confidence result can still be the wrong molecule.** The confidence
> score measures image→SMILES fidelity. It cannot see that a substituent was
> erased before it ever saw the image, so a mutilated structure scores *high*
> and its rendered check-image matches the wrong SMILES perfectly — which
> defeats the "an incorrect prediction is visible at a glance" property the
> confidence split is sold on. Both wrong molecules above scored ~0.89.

Anything downstream should treat the confidence split as a triage aid, not a
correctness guarantee, and structures near figure edges deserve a human look.

## Fidelity — does this fork still compute what upstream computes?

The point of a port is that only the *installation* changes. Here is the whole
argument, each step checkable:

**1. Four upstream code files are modified, plus the README.**
`git diff upstream/main HEAD --name-status` reports 17 files: 12 added and 5
modified. Of the 12 added, eleven are docs, `envs/uv/`, `patches/`, `tools/` and
`tests/`, which cannot execute during a run — the twelfth, `indigo_compat.py`,
**does** run, on every stage-3 import, and is covered in point 2. The modified
code files are:

| File | Change | Can it alter output? |
|---|---|---|
| `run_pipeline.{sh,py}` | one extra env-discovery root | No — decides *which interpreter* launches a stage, not what it computes |
| `decimer_segmentation.py` | the **only** deleted lines are the three unguarded download lines; everything else is added | No — the guard runs before the model exists |
| `molscribe/dataset.py` | one import line, `.indigo` → `.indigo_compat` | See 2 |

**2. The Indigo swap cannot reach inference.** `indigo_compat` prefers the
vendored binding on **Linux x86_64** — upstream's primary platform — so there the
import resolves to exactly the same object. (On macOS and Windows the vendored
tree ships no matching `.so`, so the name binds to `_IndigoUnavailable`;
behaviourally identical, because nothing on the inference path touches it.) On
ARM it falls back to `epam.indigo`. Either way it only matters if something
*constructs* an `Indigo()`, and nothing on the inference path does:

- the sole construction site is `dataset.py:275`, inside `generate_indigo_image()`
- which is called only from `TrainDataset.__getitem__` under `self.dynamic_indigo`
- and `interface.py`, the inference entry point, imports only `get_transforms`

Verified by tripwire rather than by counting: replacing `dataset.Indigo` and
`IndigoRenderer` with a class that **raises on construction**, then running a
real stage-3 prediction, completes normally and reproduces all five rows
byte-identically.

> A note on how *not* to check this, because the first attempt here got it
> wrong. Patching `indigo_compat.Indigo` after import counts nothing: `dataset.py`
> does `from .indigo_compat import Indigo`, binding its own name at import time,
> so the patched attribute is never consulted and the counter reads **0 whether
> or not Indigo is used**. A check whose failure is indistinguishable from its
> success is not evidence. Patch `molscribe.dataset.Indigo`, or use a tripwire
> that must raise.

**3. The weights are upstream's, byte for byte.** `mask_rcnn_molecule.h5` is
272,650,600 bytes with md5 `edd1e6e469cfff7efa6bf8c38441a529` — **the checksum
Zenodo publishes** for record 10663579, not merely the one we happened to
receive. The MolScribe checkpoint is `yujieq/MolScribe`'s own
`swin_base_char_aux_1m.pth` from HuggingFace, unmodified.

**4. Inference is deterministic here.** The same segment predicted twice returns
an identical SMILES and an identical confidence to six decimal places.

### The honest limit of that argument

All of the above shows this fork does not *itself* change the computation. It
does **not** prove bit-identical agreement with the same pipeline on x86_64,
because no x86_64 machine was available to compare against. Different CPU
architectures can differ in the last bits of floating-point kernels, and a
confidence that lands either side of the 0.8431 threshold could in principle
classify differently. If exact cross-architecture agreement matters to you, run
the ground-truth corpus on both and diff — the harness in [`../benchmarks/`](../benchmarks/)
does exactly that and is the right tool for it.

## Timings (8 CPU cores, no GPU)

| Stage | Work | Time |
|---|---|---|
| 1 VisualHeist | 1-page PDF → 4 figures | 30 s (+1.1 GB model, first run) |
| 2 DECIMER | 4 figures → 5 segments | 24 s (+260 MB model) |
| 3 MolScribe | 5 segments → 5 CXSMILES | 10 s (+1.1 GB model) |

Those are all figure-BEARING pages. Do not extrapolate them to a whole document:
stage 1 runs Florence-2 with `num_beams=3, max_new_tokens=1024` per page, so a page
with **nothing to emit** runs the beam search on toward the token limit — 11 min 43 s
measured on one text page, against 36-64 s for a page with figures. The expensive
pages are the ones with no chemistry on them, which is the opposite of the intuition.
A 14-page patent is therefore **hours, not minutes**, unless you drop the text-only
pages first or skip stage 1 with `--stages 2,3 --figures DIR`. Per-page measurements
in [`DOCKER.md`](DOCKER.md).

[uv]: https://docs.astral.sh/uv/
