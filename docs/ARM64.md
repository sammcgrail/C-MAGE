# Running C-MAGE on an ARM64 server

Upstream supports Linux x86_64, Windows and Apple Silicon. This fork adds
**Linux aarch64**, and replaces conda with [uv]. Every version pin is unchanged;
only the two things pip cannot express moved.

Verified end to end on: Ubuntu aarch64, 8 CPU cores, 15 GB RAM, **no GPU**.

## Reproduce it

```bash
git clone https://github.com/sammcgrail/C-MAGE.git && cd C-MAGE
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
DECIMER_WEIGHTS=/mnt/mask_rcnn_molecule.h5 tools/fetch_weights.py   # local copy
DECIMER_WEIGHTS_MIRRORS=https://your.mirror/w.h5 tools/fetch_weights.py
```

Known-good file: **272,650,600 bytes**, sha256
`329120facb69e88add819a3216db0fbfef57e9a37d6b6db0f6149819a11d46a5` (pinned).

## Accuracy note that is NOT ARM-specific — read before trusting output

On the repo's own `Validation/test_page.pdf`, the full pipeline produced 5
structures, all of them classified **high confidence**, and **two were the wrong
molecule**:

| Figure | Truth | Pipeline output | |
|---|---|---|---|
| 1 | caffeine | `C=C1NC(NC)=C(NC)C(=O)N1C` | wrong |
| 2 | paracetamol | `CC(=O)Nc1ccc(I)cc1` | wrong — OH read as iodine |
| 3 | ibuprofen | `CC(C)Cc1ccc(C(C)C(=O)O)cc1` | correct |

**The cause is stage 2, not stage 3.** Inspecting the segment images DECIMER
handed to MolScribe: caffeine's crop has the fused imidazole ring cut off, and
paracetamol's crop has the OH clipped at the image edge, leaving a bond running
off the frame that MolScribe reasonably resolved as a terminal `I`. MolScribe
read both crops *faithfully*. Mask expansion (`expand=True`) is already enabled
in `pipeline_dis.py`, so this is a segmentation accuracy limit, not a
misconfiguration.

The consequence matters for how you use the tool:

> **A high-confidence result can still be the wrong molecule.** The confidence
> score measures image→SMILES fidelity. It cannot see that the image it was
> given was clipped, so a truncated structure scores *high* and its rendered
> check-image matches the wrong SMILES perfectly — which defeats the "an
> incorrect prediction is visible at a glance" property the confidence split is
> sold on.

Anything downstream should treat the confidence split as a triage aid, not a
correctness guarantee, and structures near figure edges deserve a human look.

## Fidelity — does this fork still compute what upstream computes?

The point of a port is that only the *installation* changes. Here is the whole
argument, each step checkable:

**1. Only three upstream code files are modified at all.**
`git diff upstream/main HEAD` touches 16 files; 13 are new (docs, `envs/uv/`,
`patches/`, `tools/`, `tests/`) and cannot execute during a run. The three are:

| File | Change | Can it alter output? |
|---|---|---|
| `run_pipeline.{sh,py}` | one extra env-discovery root | No — decides *which interpreter* launches a stage, not what it computes |
| `decimer_segmentation.py` | the **only** deleted lines are the three unguarded download lines; everything else is added | No — the guard runs before the model exists |
| `molscribe/dataset.py` | one import line, `.indigo` → `.indigo_compat` | See 2 |

**2. The Indigo swap provably cannot reach inference.** `indigo_compat` prefers
the vendored binding on x86_64, so on upstream's own platform the import
resolves to exactly the same object. On ARM it falls back — but that only
matters if something *constructs* an `Indigo()`. Measured, by subclassing
`indigo_compat.Indigo` to count constructions and running a real prediction:

```
Indigo objects constructed during inference: 0
```

Indigo is used only by `generate_indigo_image()`, a training-time augmentation.

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

A 14-page patent takes minutes; budget accordingly.

[uv]: https://docs.astral.sh/uv/
