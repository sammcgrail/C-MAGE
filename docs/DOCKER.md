# C-MAGE in Docker: two images from one Dockerfile

`Dockerfile.allinone` builds two variants of the same image. They share
every layer but the last ones, so they cannot drift apart:

| | `cmage:allinone` (default target) | `cmage:slim` (`--target slim`) |
|---|---|---|
| Models | baked in (~2.4 GB) | from a directory mounted at `/opt/cmage/models` |
| Network at run time | none, ever | none for the pipeline; once for `fetch-models` |
| Size | **3.73 GB compressed** (pull/save), **7.8 GB unpacked**; `docker images` on a containerd-store host shows 11.5 GB (blobs + unpacked) | **1.49 GB compressed** (pull/save), **5.2 GB unpacked**; `docker images` on a containerd-store host shows 6.81 GB (blobs + unpacked) |
| Pick it when | you want *reproduce it with `docker run`* to be literally true | several containers share one model directory, you already have the weights, or the registry/transfer cost of 2.4 GB per image matters |

Both were verified by running them, not by building them; the runs and their
actual output are at the bottom of this page.

```bash
# Baked. Nothing else to do.
docker build -f Dockerfile.allinone -t cmage:allinone .
docker run --rm -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone

# Slim. Fill a model directory once (network), then run offline against it.
docker build -f Dockerfile.allinone --target slim -t cmage:slim .
docker run --rm -v "$PWD/models:/opt/cmage/models" cmage:slim fetch-models
docker run --rm -v "$PWD/models:/opt/cmage/models" -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:slim
```

| | |
|---|---|
| Platform verified | linux/arm64 (8 cores, no GPU, 16 GB RAM), Docker 29.6 / BuildKit 0.31 |
| Base image | `debian:bookworm-slim` |
| Verified images | `cmage:allinone` = `ebe7011b3f4c`, `cmage:slim` = `0090f27c0d2d`, built 2026-09-08 from this Dockerfile at commit `b08ae61` (all 151 tracked files inside the image sha256-match that tree). Later commits: `6869e2b` touched only `docs/ARM64.md` (not in the image); `1d5ca05` touched `tools/check_links.py`, a documentation link checker that is copied into `/opt/cmage/tools` but plays no part in the pipeline -- so the images differ from HEAD by that one non-pipeline file |
| Build time | ~9 min cold; ~4 min for slim with the environments taken from a previous image (the venv layers are copied, not rebuilt; see Building), 160 s for allinone on top of the slim image (one 2.4 GB layer plus the offline check); ~30 s for a rebuild that only touches the final stages |

## Which one, and why

**Reproducibility is a property of the artefact, not of the instructions.**
`cmage:allinone` carries everything, so `docker run` on any arm64 machine
does the same thing on the day it is pulled and five years later, with no
network and no third party in the loop. It was proved with `--network none`.
That is the one to cite and the one to archive (`docker save`).

`cmage:slim` is the same code with the weights moved to a directory you
control. It costs a one-time `fetch-models` (network, ~2.4 GB) or a copy of
a cache you already have, and in exchange the image is 2.4 GB smaller, a
dozen containers can share one model directory, and swapping weights does not
mean rebuilding. It refuses to start without the weights -- in under a second,
with instructions -- rather than dying four minutes in with an h5py traceback.

If in doubt: allinone.

## What is inside (both variants)

| Path | What |
|---|---|
| `/opt/cmage` | the repository, pipeline paths only (`MERMaid/`, `cxmolscribe-wd/`, `envs/`, `tools/`, `patches/`, `tests/`, `examples/`, the runners), copied from the build context |
| `/opt/cmage/.venv-vh`, `.venv-decimer`, `.venv-ms` | the three environments, built by `./install-uv.sh` exactly as on a bare machine (31 + 86 + 92 packages) |
| `/opt/cmage/.venvs/cmage-*` | the conda-named symlinks `run_pipeline.sh` probes for (also made by `install-uv.sh`) |
| `/opt/python` | uv-managed CPython 3.10.20 (stages 1, 2) and 3.11.15 (stage 3) |
| `/opt/cmage/models/` | the model directory: `huggingface/` (`HF_HOME`: `shixuanleong/visualheist-base`, Florence-2, 1.08 GB; `yujieq/MolScribe`, 1.13 GB) and `decimer/mask_rcnn_molecule.h5` (260 MB). Filled in allinone; a mount point in slim |
| `…/decimer_segmentation/mask_rcnn_molecule.h5` | a symlink into the model directory: `load_model()` checks next to its own source before `~/.cache`, so stage 2 finds the weights whatever `HOME` is (root, `--user`, anything) |
| `/usr/local/bin/cmage` | the entrypoint |
| `/usr/local/bin/cmage-fetch-models` | the fetch script, used by the build's download stage and by `cmage fetch-models` -- one implementation, one set of pins |

Still three environments, not one. Stage 2's TensorFlow 2.12 needs
`numpy < 1.24`; the torch stages need `>= 1.24`. That conflict is irreducible
(`envs/README.md`), so "one container" means one *image*, not one venv.
`uv` itself is not in the image: there is nothing to install at run time.

Not inside: the sample patents in `MERMaid/pdfdir/`, DECIMER's 98 MB
validation tarball, `.git`, any host venv. The `.dockerignore` at the
repository root lists it all; the Dockerfile also `COPY`s explicit paths
rather than `.`, so what is in the image is what is listed in it.

### The entrypoint

`/usr/local/bin/cmage` has three jobs:

| Invocation | Does |
|---|---|
| `cmage [run_pipeline.sh options]` | runs the pipeline. `--help` is `run_pipeline.sh`'s own help |
| `cmage fetch-models [DIR]` | fills DIR (default `/opt/cmage/models`) with the three models at the pinned revisions |
| `cmage check-models [--stages LIST]` | are the models the requested stages need present and plausible? Exit 0 or 3 |

The pipeline path is deliberately thin. It adds container-shaped defaults
and hands everything else to `run_pipeline.sh` unchanged:

- `/in` mounted and no `--pdfs` given → `--pdfs /in`
- `/out` mounted and no `--out` given → `--out /out` (with a warning if neither: results would die with the container)
- `--local` always: there is no batch queue inside a container
- no `/in`, no `--pdfs`, no `--figures` → exit 2 with a message saying what to mount
- **before running, the same check as `check-models`, scoped to `--stages`** → exit 3 with instructions if anything is missing

The check is cheap (a few `stat`s and eight bytes of the DECIMER file, well
under a second) and it is what turns a missing volume from a 4-minute
traceback into an immediate, actionable failure. It verifies what the stage
scripts will actually ask for: `model.safetensors` at the commit
`methods_visualheist.py` hard-codes, the processor files at the commit
`refs/main` names, `swin_base_char_aux_1m.pth` at MolScribe's `refs/main`,
and for DECIMER a non-empty file of at least 8 MB that starts with the HDF5
signature -- the same three tests `patches/0002` added, so a cached error
page is refused here too.

### Environment set in the image

| Variable | Value | Why |
|---|---|---|
| `HF_HOME` | `/opt/cmage/models/huggingface` | where the hub cache is (or will be mounted) |
| `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` | `1` | never *attempt* a connection: a container without network behaves identically to one with it. `fetch-models` flips them for its own process |
| `HF_MODULES_CACHE` | `/tmp/cmage/hf-modules` | Florence-2 loads with `trust_remote_code` and transformers copies the model's `.py` files here. Under `/tmp` so it works when the image tree is not writable (`--user`) |
| `MPLCONFIGDIR` | `/tmp/cmage/matplotlib` | same reason |
| `DECIMER_CACHE` | `/opt/cmage/models/decimer/mask_rcnn_molecule.h5` | read only by `tools/fetch_weights.py` (its default `--dest`), so `--check` reports the real file. Stage 2 never reads it |
| `CMAGE_VH_MODEL_REV`, `CMAGE_VH_PROC_REV`, `CMAGE_MOLSCRIBE_REV` | the Hugging Face pins | exported so the entrypoint check and `fetch-models` agree with the build |
| `DECIMER_ALLOW_UNPINNED` | empty | `tools/fetch_weights.py` pins the DECIMER file by sha256, exact size and Zenodo's published md5; `1` accepts other weights (build arg of the same name at build time) |
| `CMAGE_VARIANT` | `allinone` / `slim` | only changes the wording of the missing-models message |
| `CMAGE_MODELS` | unset (= `/opt/cmage/models`) | where the check and `fetch-models` look; only worth changing together with `HF_HOME` |
| `CMAGE_DEVICE` | `cpu` | the aarch64 torch wheels are CPU-only builds; `--device` still overrides |
| `PYTHONUNBUFFERED`, `PYTHONDONTWRITEBYTECODE` | `1` | logs stream; nothing is written into the image tree (bytecode was compiled at build) |

## Models: baked or mounted -- the trade-off

The weights have exactly one source each, and one of them is fragile. The
DECIMER file lives at a single Zenodo URL with no mirror; on 2026-09-08
Zenodo answered 503/504 for hours, and it did so again during this image's
own download test. The two Hugging Face repositories are healthier, but the
stage scripts load two of the three artefacts from `main`, which can move.

**allinone** removes every one of those dependencies from the run. Every
weight is pinned by *content*: the Hugging Face repos by git commit
(`e36203e6…` for the Florence-2 model, which `methods_visualheist.py`
hard-codes; `0e4464d1…` for its processor and `a0189776…` for MolScribe,
which the scripts load from `main` -- the image writes `refs/main` to those
commits so an offline load of "main" resolves to exactly them whatever `main`
means later), and the Zenodo file by `tools/fetch_weights.py`'s own pins:
sha256 `329120fa…`, the exact byte count, and the md5 Zenodo publishes for
the record, checked whenever the file is fetched or `--check`ed (Zenodo
records are immutable; `DECIMER_ALLOW_UNPINNED=1` is the one opt-out). Two
people building this a year apart get the same weights or a failed build,
never a silently different model. The price is ~2.4 GB of image.

**slim** keeps the same pins but moves the download to your side of the
line, once, into a directory you keep. The pipeline then runs offline against
it exactly as allinone does. What you take on: the first `fetch-models` needs
the network and Zenodo (with `tools/fetch_weights.py`'s retries, mirrors and
local-file adoption to fall back on), and the directory is yours to keep
complete -- which is what the startup check is for.

There is no third option where the pipeline quietly downloads during a run.
An interrupted download in the middle of a run is exactly how a cache gets
poisoned (`patches/0002`), and "reproduce it with `docker run`" should not
carry an unwritten "…and have network, and hope Zenodo is up".

## The model directory (slim)

Layout, the same as `~/.cache/huggingface` plus `~/.cache/decimer` on a
machine that has run the pipeline:

```
models/
├── huggingface/hub/
│   ├── version.txt
│   ├── models--shixuanleong--visualheist-base/{blobs,refs/main,snapshots/<commit>/…}
│   └── models--yujieq--MolScribe/{blobs,refs/main,snapshots/<commit>/swin_base_char_aux_1m.pth}
└── decimer/mask_rcnn_molecule.h5
```

Three ways to fill it:

```bash
# 1. Fetch (network). Idempotent; re-running verifies and fetches only what is missing.
docker run --rm -v "$PWD/models:/opt/cmage/models" cmage:slim fetch-models

# 2. Copy a cache you already have (no network).
mkdir -p models/huggingface/hub models/decimer
cp -a ~/.cache/huggingface/hub/models--shixuanleong--visualheist-base models/huggingface/hub/
cp -a ~/.cache/huggingface/hub/models--yujieq--MolScribe               models/huggingface/hub/
cp    ~/.cache/decimer/mask_rcnn_molecule.h5                            models/decimer/

# 3. Fetch, but adopt a DECIMER file you already have (Zenodo down, air gap for that file).
docker run --rm -v "$PWD/models:/opt/cmage/models" -v /path/mask_rcnn_molecule.h5:/w.h5:ro \
    -e DECIMER_WEIGHTS=/w.h5 cmage:slim fetch-models
```

`fetch-models` is `tools/fetch_weights.py` for the DECIMER file (local file →
`DECIMER_WEIGHTS_MIRRORS` → Zenodo with backoff for `DECIMER_FETCH_WAIT`
seconds, default 1800 → a clear failure), validated -- HDF5 signature, exact
size, pinned sha256 -- before it is put in place, with the md5 Zenodo
publishes reported alongside; and `huggingface_hub`'s
`snapshot_download` at the pinned commits for the other two, with `refs/main`
written and `version.txt` added. It ends by running `check-models` against
the directory it filled. All of it also runs at build time for allinone, so
the build and the volume are produced by the same code.

Then ask, offline, whether a directory is complete:

```bash
docker run --rm --network none -v "$PWD/models:/opt/cmage/models" cmage:slim check-models
```

Practicalities: the directory is written by the container's user (root by
default; `--user "$(id -u):$(id -g)"` if you want it owned by you, in which
case it must be writable by that uid). It can be mounted read-only (`:ro`)
for pipeline runs. `HF_HUB_OFFLINE=1` stays on: a complete directory needs no
network, and an incomplete one is reported by the check, not repaired
silently at run time.

## Building

### Default: download the models during the build

```bash
docker build -f Dockerfile.allinone -t cmage:allinone .                  # baked, the default target
docker build -f Dockerfile.allinone --target slim -t cmage:slim .        # no download stage runs
```

Network is used for apt, the `uv` binary, two CPython builds, the pinned
wheels and, for allinone, the two Hugging Face repositories and the Zenodo
file. `uv`'s wheel cache is a BuildKit cache mount, so a rebuild after a code
change reinstalls from local cache in about two minutes. Build both from the
same checkout and slim's layers are a prefix of allinone's: pulling the
second costs only the model layer. (Verified on the images above: all 19 of
`cmage:slim`'s layers are the first 19 of `cmage:allinone`'s 21; the other
two are the weights and the offline check.)

| Build arg | Default | Meaning |
|---|---|---|
| `DECIMER_FETCH_WAIT` | `1800` | seconds to keep retrying while Zenodo answers 5xx |
| `DECIMER_WEIGHTS_MIRRORS` | empty | comma-separated URLs tried *before* Zenodo |
| `DECIMER_ALLOW_UNPINNED` | empty | `1` lets `tools/fetch_weights.py` accept a DECIMER file that does not match its pinned sha256/size |
| `VH_MODEL_REV`, `VH_PROC_REV`, `MOLSCRIBE_REV` | see Dockerfile | Hugging Face commits to pin |
| `MODELS_SRC` | `/` | path of the weights inside a `--build-context models=…` override (see below) |
| `PY_STAGE12`, `PY_STAGE3` | `3.10.20`, `3.11.15` | interpreter builds |
| `UV_VERSION` | `0.11.29` | uv release |
| `GIT_SHA` | `unknown` | stamped into the `org.opencontainers.image.revision` label |

### From weights you already have

A directory laid out as above replaces the download stage:

```bash
docker build -f Dockerfile.allinone -t cmage:allinone --build-context models=./models .
```

`tools/fetch_weights.py --check` and the offline resolution check still run,
so a wrong or truncated local file fails the build rather than the run.

### From a previous image (skip the 9-minute venv build)

The environments depend only on `envs/uv/*.txt`, `install-uv.sh` and the
three packages' metadata. When those have not changed, a previous image can
supply them, and can supply the weights too:

```bash
# slim: environments from the previous image, everything else from the checkout
docker build -f Dockerfile.allinone --target slim -t cmage:slim \
    --build-context builder=docker-image://cmage:allinone-prev .
# allinone: FROM the slim image just built, weights from the previous image
docker build -f Dockerfile.allinone -t cmage:allinone \
    --build-context slim=docker-image://cmage:slim \
    --build-context models=docker-image://cmage:allinone-prev --build-arg MODELS_SRC=/opt/cmage/models .
```

This is safe because the runtime stage takes only `/opt/python` and the
three venvs from `builder`; the code always comes from the build context, and
the editable installs point at `/opt/cmage/<package>` by path, so the checkout
is what runs. The second command overrides the `slim` *stage* with the slim
*image*, which is the strongest form of "allinone is slim plus the weights":
the lower layers are not merely equivalent, they are the same layers. It is
how the verified images on this page were built (the inputs to
`install-uv.sh` were sha256-identical to the image they came from), and it
costs no builder cache: about 4 minutes for slim and 160 s for allinone on
this host, against ~9 minutes and ~12 GB of cache for a cold build.

Keep the context reference spelled the same way between builds
(`cmage:allinone-prev` every time, not once by tag and once by ID): BuildKit
keys the cache on it, and a different spelling re-copies the 4.6 GB of venv
layers.

### Disk, and a trap

Budget ~25 GB free for a cold build: the BuildKit cache grows to ~12 GB
(venvs, the copied tree, the models stage, the wheel-cache mount) on top of
the image, and a containerd-store host keeps the compressed blobs too.
Reusing a previous image (above) needs only the new layers. That cache is
what makes rebuilds take 30 s instead of 9 min, but it stays on disk until
you remove it, and each `--target models --output type=local` experiment adds
another 2.5 GB record. When you are done iterating:

```bash
docker builder prune -f                    # dangling build cache
docker builder prune -f --filter id=<ID>   # one record; IDs from: docker buildx du --verbose
```

On 2026-09-08 this image's build cycle took a shared host to 96 % disk before
the cache was pruned. Do not iterate on this Dockerfile on a box that cannot
spare the space, and never prune images on a host that is serving from them.

### What the build verifies, and what it cannot

Both targets end with a `RUN --network=none` step. For slim: every
environment imports its stage's package; `--help` prints; the missing-models
check *fires* (exit 3, with the `fetch-models` hint) and, as the positive
control, *passes* on a complete layout faked in place and removed again. For
allinone, additionally: the five files the stage scripts request resolve
from the hub cache offline; the DECIMER file passes `tools/fetch_weights.py
--check` (signature, exact size, pinned sha256, Zenodo's md5 reported);
`check-models` passes. A build that fails this is not worth
running. A build that passes it can still have a broken pipeline, which is
why the verified-runs section exists.

## Running

```bash
# allinone: everything, PDFs from ./pdfs, results into ./out
docker run --rm -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone

# slim: the same, plus the model directory
docker run --rm -v "$PWD/models:/opt/cmage/models:ro" -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:slim

# Any run_pipeline.sh flag works. Stages 2 and 3 only, from existing figure images:
docker run --rm -v "$PWD/figs:/figs:ro" -v "$PWD/out:/out" cmage:allinone --stages 2,3 --figures /figs

# One spreadsheet instead of the high/low confidence split:
docker run --rm -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone --separated no

# Prove to yourself it needs no network:
docker run --rm --network none -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone

# Results owned by you rather than root (the output directory must be writable by that uid):
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone
```

Output lands in `out/run_<timestamp>/` with the same layout as a bare-metal
run (`01_VH_Figures/`, `02_DIS_Segments/`, `03_CXMS_Results/`, `logs/`).
Mounting `~/.cache/huggingface` or `~/.cache/decimer` at their default paths
is unnecessary and ignored: `HF_HOME` points at `/opt/cmage/models`.

Two smoke-test inputs ship in the image, so it can be exercised with no input
of your own: a one-page PDF for all three stages, and three figure images for
stages 2 and 3:

```bash
docker run --rm -v "$PWD/out:/out" cmage:allinone \
    --pdfs /opt/cmage/cxmolscribe-wd/DECIMER-Image-Segmentation/Validation
docker run --rm -v "$PWD/out:/out" cmage:allinone \
    --stages 2,3 --figures /opt/cmage/examples/stage2_input
```

### An accuracy lever: `DECIMER_BBOX_PAD`

Stage 2's `apply_mask` erases every pixel the Mask R-CNN mask did not cover
before it crops, so ink the mask missed is deleted, not merely cropped, and
stage 3 then reads a mutilated drawing with high confidence. The repository
ships an opt-in fix (`decimer_segmentation.py`, `DECIMER_BBOX_PAD`): keep the
original pixels inside the mask's bounding box padded by that fraction. It is
off by default because padding can pull in a neighbour's ink on a dense
figure. It is an ordinary environment variable, so it passes straight through
`docker run`:

```bash
docker run --rm -e DECIMER_BBOX_PAD=0.15 -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone
```

On the one-page test PDF the default path gets one of its three known
molecules right (ibuprofen) and misreads the other two at high confidence --
paracetamol as `CC(=O)Nc1ccc(I)cc1` (OH read as I) and caffeine as
`C=C1NC(NC)=C(NC)C(=O)N1C`; with `0.15` all three come back correct (caffeine 0.901154, paracetamol 0.922076, ibuprofen 0.900629), one padded crop picks up a neighbour's stray fragment, and the page's fifth structure drops to the low-confidence sheet. The full A/B, read from the workbooks of this image, is under Verified runs.

Resources: the stages run one after another, each loading one model. Peak
container memory observed was 3.9 GiB (stage 1); stages 2 and 3 stayed under
2.5 GiB. All cores are used (`--cpus` limits it); the default `/dev/shm` was
enough for every run below.

**Stage 1 on CPU is the slow part, and it is data-dependent.** VisualHeist
runs Florence-2 with `num_beams=3, max_new_tokens=1024` per page. The one-page
vector test PDF (4 figures) took 36 s including the model load. On a 300-dpi
scanned patent the front page, with 2 figures, took 64 s including the load,
and the next page, a text page on which the model found nothing, took 11 min
43 s: with nothing to emit, the beam search runs on towards the token limit.
Fourteen such pages is hours, not minutes. If you have a GPU anywhere, run
stage 1 there and feed the container `--stages 2,3 --figures DIR`; stages 2
and 3 are fast on CPU.

## Verified runs

All on this arm64 host, from the images in the table at the top. Timings are
wall clock on 8 CPU cores. "Cold start" is from `docker run` to the first
line the pipeline prints, or to the failure.

### slim, without its models: the failure you will see

```bash
docker run --rm --network none -v "$PWD/empty:/opt/cmage/models" -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:slim
```

Exit 3 in 0.35 s, nothing written to `/out`, no stage started. Verbatim:

```
cmage: model files missing for the requested stages (1,2,3):
  stage 1 VisualHeist:  /opt/cmage/models/huggingface/hub/models--shixuanleong--visualheist-base/snapshots/e36203e67a05b9dd66d1310fd3a217e8b334ab30/model.safetensors
  stage 1 VisualHeist:  /opt/cmage/models/huggingface/hub/models--shixuanleong--visualheist-base/refs/main -> snapshots/<commit>/preprocessor_config.json
  stage 2 DECIMER:      /opt/cmage/models/decimer/mask_rcnn_molecule.h5  (a valid HDF5 file, ~260 MB)
  stage 3 CXMolScribe:  /opt/cmage/models/huggingface/hub/models--yujieq--MolScribe/refs/main -> snapshots/<commit>/swin_base_char_aux_1m.pth
This is cmage:slim: the weights are not in the image. Either
  1. mount a directory that already holds them
     (layout: huggingface/hub/models--*, decimer/mask_rcnn_molecule.h5):
       -v /path/to/models:/opt/cmage/models
  2. fetch them into such a directory once (network, ~2.4 GB; Zenodo is retried
     with backoff, DECIMER_WEIGHTS=/file adopts a local copy):
       docker run --rm -v /path/to/models:/opt/cmage/models cmage:slim fetch-models
  3. or use cmage:allinone, which has them baked in and needs no network.
```

Without any `-v` for the model directory the result is the same (exit 3):
the image's own directory is empty. `cmage:slim --help` takes 0.44 s.

### slim, `fetch-models`, then the pipeline offline against the result

```bash
docker run --rm -v "$PWD/models:/opt/cmage/models" cmage:slim fetch-models
```

What actually happened on 2026-09-08: the two Hugging Face repositories
(2.1 GB) arrived in about half a minute; Zenodo then answered **HTTP 504 on
all six attempts** spread over the 600-second window this run allowed
(`-e DECIMER_FETCH_WAIT=600`; the default keeps trying for 1800 s), and
`fetch-models` exited 1 with `tools/fetch_weights.py`'s instructions. That is
the outage the baked variant exists for, reproduced on demand. Tier 1 of the
same tool then finished the job in 3.5 s from a local copy:

```bash
docker run --rm -e DECIMER_WEIGHTS=/w.h5 -v /path/mask_rcnn_molecule.h5:/w.h5:ro \
    -v "$PWD/models:/opt/cmage/models" cmage:slim fetch-models
```

```
[fetch_weights] adopting local weights from /w.h5 (272650600 bytes)
[fetch_weights] sha256 329120facb69e88add819a3216db0fbfef57e9a37d6b6db0f6149819a11d46a5
[fetch_weights] OK    /opt/cmage/models/decimer/mask_rcnn_molecule.h5  (272650600 bytes)
[fetch_weights] sha256 329120facb69e88add819a3216db0fbfef57e9a37d6b6db0f6149819a11d46a5
[fetch_weights] md5    edd1e6e469cfff7efa6bf8c38441a529  == the md5 Zenodo publishes
==> 2.4G in /opt/cmage/models
cmage: models present for stages 1,2,3 (slim)
```

Then, with the network off and the directory mounted read-only:

```bash
docker run --rm --network none -v "$PWD/models:/opt/cmage/models:ro" cmage:slim check-models
# cmage: models present for stages 1,2,3 (slim)          exit 0
docker run --rm --network none -v "$PWD/models:/opt/cmage/models:ro" \
    -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:slim
```

Exit 0 in 132.6 s on the one-page test PDF: VisualHeist 25.9 s → 4 figures;
DECIMER 28.2 s → 5 segments; MolScribe 37.8 s → 5 high-confidence SMILES,
identical to the baked run below (same weights, same code, same answers).

### allinone, `--network none`, only `/in` and `/out` mounted

```bash
docker run --rm --network none -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone
```

A network-dependent image cannot pass this. Exit 0 in 133.8 s on the
one-page test PDF -- VisualHeist 27.4 s → 4 figures, DECIMER 26.8 s → 5
segments, MolScribe 40.4 s → 5 high-confidence rows, 0 low. The rows of
`Completed_HighConfidence_CMAGE.xlsx`, read back from the workbook rather
than counted as files (three empty workbooks would pass a file count):

| Segment | Confidence | Predicted SMILES |
|---|---|---|
| `test_page_image_1_molecule_0` | 0.889446 | `C=C1NC(NC)=C(NC)C(=O)N1C` (caffeine, misread) |
| `test_page_image_2_molecule_0` | 0.898833 | `CC(=O)Nc1ccc(I)cc1` (paracetamol, OH read as I) |
| `test_page_image_3_molecule_0` | 0.893522 | `CC(C)Cc1ccc(C(C)C(=O)O)cc1` (ibuprofen) |
| `test_page_image_3_molecule_1` | 0.898307 | `CC(C)Cc1ccc(C(C)C(=O)O)cc1` (ibuprofen) |
| `test_page_image_4_molecule_0` | 0.878107 | `CC(C)Cc1ccc(C(C)C(=O)OC[C@@H]2…)cc1` (an ibuprofen glycoside ester) |

Those values, including the two known-wrong reads, are identical to six
decimal places to a bare-metal run of the same commit on the same host, and
to the slim run above. The container is not merely functional offline; it is
faithful to the host pipeline, which is the claim that matters.

Cold start on this image: `--help` 0.48 s; `check-models` 0.38 s. And the
negative control on the baked image itself -- an empty directory mounted
over the weights must be refused with the allinone wording, not silently
"work" from some other cache:

```
This is cmage:allinone, which ships the weights inside the image, so something
is mounted over /opt/cmage/models that does not contain them. Drop that -v mount, or
point it at a complete directory.
```

(exit 3)

### allinone, the same page with `-e DECIMER_BBOX_PAD=0.15`

```bash
docker run --rm --network none -e DECIMER_BBOX_PAD=0.15 -v "$PWD/pdfs:/in:ro" -v "$PWD/out:/out" cmage:allinone
```

Exit 0 in 114.8 s, same 4 figures and 5 segments. Read back from the
workbooks:

| Segment | Default | With `0.15` |
|---|---|---|
| `…image_1_molecule_0` (caffeine) | `C=C1NC(NC)=C(NC)C(=O)N1C` 0.889446, wrong | `Cn1c(=O)c2c(ncn2C)n(C)c1=O` 0.901154, **right** |
| `…image_2_molecule_0` (paracetamol) | `CC(=O)Nc1ccc(I)cc1` 0.898833, wrong | `CC(=O)Nc1ccc(O)cc1` 0.922076, **right** |
| `…image_3_molecule_0` (ibuprofen) | right, 0.893522 | `CC(C)Cc1ccc(C(C)C(=O)O)cc1.CI` 0.886082: right, plus a stray fragment from a neighbour's ink |
| `…image_3_molecule_1` (ibuprofen) | right, 0.898307 | right, 0.900629 |
| `…image_4_molecule_0` (glycoside ester) | high sheet, 0.878107 | low sheet, 0.812624 |

Three of the page's three known molecules right instead of one. The lever is
real, and so is its stated risk: the padded crop of one ibuprofen took in the
`.CI` of something next to it. Off by default for that reason; worth turning
on for sparse figures.




## Dockerfile versus image: settled

The first baked image (`023466d15b13`, now also tagged
`cmage:allinone-prev`) was built from an earlier revision of this file. Two
lines were added afterwards without a rebuild, and the question was whether
they made the tag lie. They did not, and that is provable rather than
asserted:

- `ENV DECIMER_CACHE=…` -- the variable is read by exactly one thing,
  `tools/fetch_weights.py` (`grep -rn DECIMER_CACHE` over the tree finds no
  other reader; `decimer_segmentation.load_model()` resolves its own path).
  It changes what `--check` reports inside a container, nothing the pipeline
  computes.
- the `rmtree` of huggingface_hub's `xet/` log directory -- runs only inside
  the download stage, which that image never executed (its weights came from
  a local directory), and touches no file any stage reads.

So `023466d15b13` did not need a rebuild *for those lines*. It was rebuilt
anyway, for a different reason: this revision of the Dockerfile changed what
both variants share -- the entrypoint (the startup model check,
`fetch-models`, `check-models`), the relative venv links and completion
stamps, the removal of a personal identifier from the labels -- and the
whole point of one Dockerfile is that `cmage:allinone` and `cmage:slim` are
built from the same revision of it. The rebuild took the environments from
`023466d15b13` (`--build-context builder=docker-image://cmage:allinone-prev`;
every input to `install-uv.sh` was sha256-identical between the two
checkouts) and the weights from the same image
(`--build-context models=docker-image://cmage:allinone-prev
--build-arg MODELS_SRC=/opt/cmage/models`), so the bytes that matter are the
verified ones and the build cost no cold stage and no new model download.
`docker image inspect` shows the same `CMAGE_*_REV` values and the same
`tools/fetch_weights.py --check` digest line in both.

## Limitations

- **arm64 only, CPU only, as verified.** Nothing in the Dockerfile is
  arm-specific, but on x86_64 the pinned `torch==2.8.0` / `2.7.1` wheels from
  PyPI are CUDA builds (several GB of `nvidia-*` packages) and nothing here was
  tested there. A CPU x86_64 image would want the torch lines in
  `envs/uv/*.txt` pointed at the `https://download.pytorch.org/whl/cpu` index.
- **Both images are big.** ~4.2 GB of environments is the floor; allinone adds
  ~2.4 GB of weights. `docker save cmage:allinone | zstd > cmage.tar.zst`
  moves it to an air-gapped machine.
- **Stage 1 is slow on CPU for dense scanned pages** (see Running). That is
  the model, not the container.
- `fetch-models` needs the network even when the directory is already
  complete (it confirms the pinned file lists with Hugging Face);
  `check-models` is the offline question.
- The stage scripts print TensorFlow's usual CUDA-library warnings on a CPU
  box, plus a few `FutureWarning`s from OpenNMT and huggingface_hub. They are
  noise, not errors, and are left as-is so the logs match a bare-metal run.
- Results are written as root unless `--user` is given (see Running).
