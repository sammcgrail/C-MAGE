# patches/

Source patches applied to code vendored in this repository. Each patch is
already applied in-tree; the `.patch` file is the reviewable record. Apply
to a pristine checkout with `git apply patches/<name>.patch` from the
repository root, or regenerate after editing with the command listed under
the patch.

## 0001-molscribe-indigo-aarch64-fallback.patch

Files: `cxmolscribe-wd/MolScribe/molscribe/dataset.py` (2 import lines),
`cxmolscribe-wd/MolScribe/molscribe/indigo_compat.py` (new).

### Problem

MolScribe vendors a *modified* EPAM Indigo under `molscribe/indigo/` (the
Python binding plus native libraries). The only native libraries shipped are
Linux x86_64 builds (`molscribe/indigo/lib/Linux/x64/*.so`). Its loader keys
on `platform.architecture()`, which is `"64bit"` on every 64-bit Linux, so on
aarch64 it walks into `lib/Linux/x64` and dlopen rejects the x86_64 objects at
the first `Indigo()`:

    OSError: .../molscribe/indigo/lib/Linux/x64/libindigo.so:
    cannot open shared object file: No such file or directory

`dataset.py` imports Indigo at module level, `interface.py` imports
`dataset.py`, so this sits on the import path of `from molscribe import
MolScribe`. The import itself succeeds (the library is only loaded on
instantiation); what fails on aarch64 is `generate_indigo_image()` --
training-time synthetic rendering (`TrainDataset` with `--dynamic_indigo`).
Inference never instantiates Indigo.

### What the patch does

`dataset.py` now imports `Indigo`/`IndigoRenderer` from
`molscribe/indigo_compat.py`, which picks, in order:

1. **vendored binding** -- when the vendored library is built for this
   machine (Linux x86_64, the only case where it ever worked). Behaviour
   there is unchanged; verified by simulating `platform.machine() ==
   "x86_64"`.
2. **`epam.indigo` from PyPI** (pinned `1.46.0` in
   `envs/uv/stage3-cxmolscribe.txt`) -- same toolkit, API-compatible binding,
   wheels for Linux aarch64 and macOS arm64. Two compatibility shims on this
   path:
   - `render-font-family` is skipped in `setOption` (explicit allow-list;
     any other undefined option still raises). Indigo dropped that option
     between the vendored 1.4.3 and 1.6.0, the *first* release with aarch64
     wheels, so no aarch64-capable version has it (bisected on PyPI).
   - `IndigoObject.coords()` raises `NotImplementedError` with an
     explanation. It is not Indigo API: it is MolScribe's own addition (C
     entry point `indigoCoords`, present only in the vendored x86_64
     `libindigo.so`). `get_graph()` calls it when `pseudo_coords=False`.
3. **placeholders** that raise `ImportError` at instantiation when neither
   is usable, so `from molscribe import MolScribe` works for inference with
   no Indigo at all.

### Trade-offs, stated plainly

- Inference (`MolScribe.predict_image_file`, what C-MAGE stage 3 calls) is
  unaffected on every platform; it never touches Indigo.
- On aarch64, Indigo-rendered training data works only with
  `--pseudo_coords` (`get_graph` then uses `atom.xyz()`). Verified: 48/48
  augmented renders with `mol_augment=True`. Upstream's pinned recipe
  (`scripts/train_uspto_joint_chartok_1m680k.sh`) uses `--dynamic_indigo
  --mol_augment` *without* `--pseudo_coords`; reproducing it exactly on
  aarch64 would need MolScribe's modified Indigo rebuilt for aarch64
  (source not in this repo). Without `--pseudo_coords` every dynamic sample
  fails inside `generate_indigo_image`'s `except Exception` and is skipped
  (`success=False`), which is upstream's existing behaviour for render
  failures; `debug=True` surfaces the `NotImplementedError` in the chained
  traceback.
- Renders from Indigo 1.46.0 differ cosmetically from the vendored 1.4.3
  (fonts, default styling), so synthetic training images on aarch64 are not
  pixel-identical to the paper's. The random font choice is a no-op.
- `epam.indigo` becomes a dependency of the stage 3 environment. On x86_64
  it is installed but unused.

### Regenerate

    # against upstream, NOT the index: a bare `git diff` compares the worktree
    # to the index and emits an empty patch as soon as the change is committed.
    { git diff upstream/main -- cxmolscribe-wd/MolScribe/molscribe/dataset.py;
      git diff --no-index /dev/null cxmolscribe-wd/MolScribe/molscribe/indigo_compat.py; } \
      > patches/0001-molscribe-indigo-aarch64-fallback.patch
    git apply --check --reverse patches/0001-molscribe-indigo-aarch64-fallback.patch

---

## 0002-decimer-guard-weights-download.patch

**What:** `decimer_segmentation.load_model()` used to do
`open(path,'wb').write(requests.get(url).content)` with no check of any kind.

**Why it matters more than a normal download bug.** On 2026-09-08 Zenodo was
down and answered with a 92-byte HTML error page under HTTP 504. That page was
written to `~/.cache/decimer/mask_rcnn_molecule.h5`. The download only runs when
the file is ABSENT, so from then on every import failed with

    OSError: Unable to open file (file signature not found)

which names neither Zenodo nor the cache. A failed download costs you an
afternoon; a **poisoned cache** costs you the same afternoon repeatedly and
points at the wrong thing while it does. Note also that `import
decimer_segmentation` calls `load_model()` at module scope, so merely importing
the package is enough to plant the bad file.

**The patch:** four checks, cheapest first — HTTP status, content-type is not
HTML, payload starts with the HDF5 magic `\x89HDF\r\n\x1a\n`, payload is
plausibly large (the real file is ~260 MB) — then write to `.part` and
`os.replace()` into position, so nothing partial or rejected is ever visible at
the cache path. Failure raises `RuntimeError` naming what arrived and which path
to delete.

**Verified, not assumed.** `tests/test_weights_download_guard.py` drives all
four failure branches with fake responses and asserts both that each is refused
and that **nothing is left in the cache**, plus a positive control that a valid
HDF5 payload is still accepted — without that control the test would pass just
as well on a guard that refuses everything.

    python3 tests/test_weights_download_guard.py

**Trade-off:** the size floor (8 MB) is a heuristic. If upstream ever ships
genuinely smaller weights it would need lowering; it is set well below the real
260 MB and well above any error page.
