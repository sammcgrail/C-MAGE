# C-MAGE

C-MAGE extracts chemical structures from the figures in a paper and translates them
into machine-readable CXSMILES.

![C-MAGE](details/pipeline.png)

| Stage | Component | Input → Output |
|---|---|---|
| 1 | VisualHeist | PDF pages → Figure/table Images |
| 2 | DECIMER Image Segmentation | Figures/tables → Individual Structure Images |
| 3 | CXMolScribe | Individual Structure Images → CXSMILES |

## How it works

Three specialised models in a row, because "read the chemistry out of this paper"
is really three unrelated problems: *find the pictures*, *cut out each molecule*,
*read the molecule*. One end-to-end model would have to be good at all three.

```mermaid
flowchart LR
    A[PDF pages] -->|VisualHeist<br/>Florence-2| B[figure images]
    B -->|DECIMER<br/>Mask R-CNN + mask expansion| C[one image<br/>per structure]
    C -->|MolScribe<br/>Swin encoder + graph decoder| D[CXSMILES<br/>+ confidence]
    B -.->|upload an image<br/>and stage 1 is skipped| C
```

### Stage 1 — VisualHeist: find the figures

Pages are rasterised and passed to **Florence-2**, a vision-language model, which
is asked to locate figures and tables. Output is a cropped image per figure. This
is a *layout* problem, not a chemistry one — nothing here knows what a molecule is.

### Stage 2 — DECIMER: cut out each structure

A figure may hold one structure or twenty in a grid. **Mask R-CNN** proposes a
rough mask per structure — and then the interesting part, which is not the neural
network at all:

```mermaid
flowchart TD
    M[Mask R-CNN mask<br/>roughly right, edges ragged] --> B[binarize the page<br/>threshold 0.72]
    B --> E[expand the mask along<br/>CONNECTED dark pixels]
    E --> X{hits an exclusion<br/>region?}
    X -->|no| E
    X -->|yes: long vertical/horizontal<br/>lines = table rules| S[stop, emit crop]
```

The mask is grown outward through connected ink until it frames the whole drawing,
so a box that clipped a substituent recovers it. An **exclusion mask** built from
long straight-line detection stops the growth escaping along a table border and
swallowing the page.

That expansion is the cleverest idea in the pipeline **and its main failure mode**.
When it stops early you get a structure with a ring or a substituent missing — and
see [Accuracy](#accuracy--read-this-before-trusting-the-confidence-split), because
nothing downstream can tell that it happened.

### Stage 3 — MolScribe: read the structure

The part people usually get wrong about this stage: **it does not caption the image
into a SMILES string.** It predicts a *molecular graph*, then builds SMILES from it.

```mermaid
flowchart LR
    I[structure image] --> S[Swin Transformer<br/>encoder]
    S --> D[decoder]
    D --> N[atom symbols<br/>+ 2D coordinates]
    D --> E[edge matrix:<br/>bond type for every atom pair]
    N --> G[molecular graph]
    E --> G
    G -->|RDKit reconstruction| O[CXSMILES]
    N -.->|per-atom scores| C[confidence]
```

Three things fall out of predicting a graph rather than a string, and together they
are the actual secret sauce:

- **Per-atom confidence.** Scores attach to nodes, so the model can say *which part*
  it was unsure about. A string-captioning model can only score the whole sequence.
- **R-groups survive.** A node may carry a label like `R1` instead of an element.
  Plain SMILES cannot express that, which is why the output is **CXSMILES** —
  extended SMILES that carries the labels alongside the structure. For a patent
  Markush drawing this is the difference between a usable answer and none.
- **The output is chemically checkable.** A graph either reconstructs into a valid
  molecule or it does not. A generated string can be confidently malformed.

### Why three environments and not one

Not fussiness — an irreducible conflict. Stage 2's TensorFlow 2.12 requires
`numpy < 1.24`; the PyTorch stages require `>= 1.24`. No single environment
satisfies both, so each stage runs under its own interpreter and the runner shells
between them.

*(The stage 1 package is named MERMaid, which is unrelated to the Mermaid diagrams
above — a coincidence that will confuse exactly one person per team.)*

## Install

Needs ~7 GB of disk. A GPU is optional. Three ways in — pick one:

| | Needs | Best for |
|---|---|---|
| **[Docker](docs/DOCKER.md)** | docker | one command, nothing installed on the host |
| **[uv](docs/ARM64.md)** | [uv](https://docs.astral.sh/uv/) | fast, no conda, **works on ARM64** |
| conda | conda | the original path; required for a **CUDA** box |

Platform support: Linux x86_64, **Linux aarch64/ARM64** (added via the uv path),
Windows, and macOS 12+ on Apple Silicon. Intel Macs cannot run it — PyTorch has
published no macOS x86_64 wheels since 2.2.2.

### Docker — one container, everything baked in

```bash
docker build -f Dockerfile.allinone -t cmage .
docker run --rm -v "$PWD/pdfs:/in" -v "$PWD/out:/out" cmage --pdfs /in --out /out
```

Details and image-size trade-offs: [docs/DOCKER.md](docs/DOCKER.md).

### uv — no conda required

```bash
./install-uv.sh                    # three venvs, same pins as the conda specs
python3 tools/fetch_weights.py     # stage 2 weights, checksum-verified
./run_pipeline.sh --device cpu
```

`install-uv.sh` builds the same three environments from `envs/uv/*.txt`, which
carry the identical version pins and reasoning as `envs/*.yml`. Only the two
things pip cannot express differ: **poppler** comes from your system package
manager (`apt install poppler-utils`), and `cudatoolkit`/`cudnn` are dropped
because the uv path is CPU-only — **on a CUDA machine use `./install.sh`**, where
conda pins the exact CUDA/cuDNN pair TensorFlow 2.12 needs.

There are still three environments under uv, for the same irreducible reason:
stage 2's TensorFlow 2.12 requires `numpy < 1.24` and the PyTorch stages require
`>= 1.24`.

ARM64 notes, including two corrections to the platform claims below and why
MolScribe's x86-only Indigo does not block inference:
[docs/ARM64.md](docs/ARM64.md).

### conda

```bash
git clone https://github.com/AlexTaylor54/C-MAGE.git
cd C-MAGE
./install.sh
```

That builds all three environments and installs everything.

## Run

1. Upload PDFs in `MERMaid/pdfdir/`.
2. Run:
```bash
./run_pipeline.sh
```

The first run downloads ~2.4 GB of models. `./run_pipeline.sh --help` lists alternative run
options — a different input folder, running only some stages, forcing CPU, and having unseparated translation results

## Windows

`install.sh` and `run_pipeline.sh` are bash, so Windows needs the environments
built by hand. From the repository folder in Anaconda Prompt:

```
conda env create -f envs\cmage-visualheist.yml
conda activate cmage-visualheist
pip install -e .\MERMaid --no-deps
conda deactivate
```

Repeat for the other two, changing the spec and the package each time:

| Spec | Package |
|---|---|
| `envs\cmage-decimer.yml` | `.\cxmolscribe-wd\DECIMER-Image-Segmentation` |
| `envs\cmage-cxmolscribe.yml` | `.\cxmolscribe-wd\MolScribe` |

Then run the pipeline with the Python entry point instead:

```
python run_pipeline.py
```

It takes the same options as `run_pipeline.sh`.

## Results

Each run gets its own timestamped folder:

```
results/run_20260814-134947/03_CXMS_Results/
├── Completed_HighConfidence_CMAGE.xlsx    Structures with High Confidence
├── Completed_LowConfidence_CMAGE.xlsx     Structures with Low Confidence
├── highconfidence_images/
└── lowconfidence_images/
```

The split is on CXMolScribe's confidence at a threshold of 0.8431. Each row in the
spreadsheet shows the DECIMER-Image-Segmentation input next to the predicted CXSMILES and a
rendering of that CXSMILES, so an incorrect prediction is visible at a glance. The raw 
confidence value is also present in this row.

## Accuracy — read this before trusting the confidence split

The confidence threshold sorts results into two spreadsheets, and it is easy to
read that as "high confidence = correct". It is not.

**The score measures how faithfully the model read the image it was given. It
cannot see that the image was clipped.** If stage 2's segmentation crops a
structure — cutting off a fused ring, or a substituent at the frame edge — stage 3
reads the truncated drawing accurately, reports high confidence, and renders a
check-image that matches its own wrong SMILES perfectly. The side-by-side
rendering that normally makes an error obvious at a glance agrees with itself in
exactly this case.

Observed on this repository's own `Validation/test_page.pdf`: five structures,
all five classified high confidence, two of them the wrong molecule — caffeine
missing its fused imidazole ring, and paracetamol's hydroxyl read as iodine after
being clipped at the crop boundary. Mask expansion (`expand=True`) was already
enabled, so this is a segmentation accuracy limit rather than a misconfiguration.

Treat the split as triage, not a correctness guarantee, and give structures near
figure edges a human look. Measured numbers against a ground-truth corpus are in
[benchmarks/](benchmarks/).

## Post Pipeline Processing

Once a dataset's Excel sheet has been annotated it can be organized into segmentation classifications by `cxmolscribe-wd/organize_category.py`.  This can be done for any Excel sheet by running the following command.

```bash
python cxmolscribe-wd/organize_category.py --input NAME_OF_EXCEL.xlsx
```

Within this script, there are marked locations which will need to be modified based on which classification the user desires to sort.

To generate statistics on an annotated and graded C-MAGE output, run: 

```bash
python cxmolscribe-wd/analyze_database.py --input NAME_OF_EXCEL.xlsx
```


## Uninstall

```bash
rm -rf C-MAGE
conda env remove -n cmage-visualheist
conda env remove -n cmage-decimer
conda env remove -n cmage-cxmolscribe
```

The models are cached outside the repository and survive the above, so they are
not downloaded again if you reinstall. To remove them too (~2.4 GB):

```bash
rm -rf ~/.cache/huggingface/hub/models--shixuanleong--visualheist-base \
       ~/.cache/huggingface/hub/models--yujieq--MolScribe \
       ~/.cache/decimer
```

---

`MERMaid/` and `cxmolscribe-wd/DECIMER-Image-Segmentation/` are vendored copies
of [MERMaid](https://github.com/aspuru-guzik-group/MERMaid) and
[DECIMER](https://github.com/Kohulan/DECIMER-Image-Segmentation).
