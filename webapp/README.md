# C-MAGE web app

A small web front end for the C-MAGE pipeline: upload a PDF or a figure image,
get back every chemical structure it contains as SMILES, with the cropped
image, a rendering of the prediction and the pipeline's own confidence.

* **Extract** — upload, watch the three stages run, browse the results, copy a
  SMILES or download the whole set as CSV. A PDF runs all three stages; an
  image skips stage 1 (VisualHeist only turns pages into figures), so a single
  cropped structure comes back in seconds.
* **Gallery** — every completed run on this server, persisted on disk, so
  accuracy can be judged across many documents rather than one upload at a time.
* **Benchmark** — runs over a corpus with known answers, each prediction
  compared with the true molecule using RDKit canonical SMILES (with and
  without stereochemistry), with the pipeline's confidence beside the verdict.

The UI never presents "high confidence" as "correct". The score measures how
faithfully a *crop* was read; when the segmenter clips a ring or a substituent,
the reading of the clipped image is confident and wrong. Every results page
says so and lets you open the source figure to compare.

## Running it

The pipeline image comes first (it holds the three stage environments and the
model weights), then this image on top of it:

```bash
docker build -t cmage:allinone -f Dockerfile.allinone .       # from the repository root
docker compose -f webapp/docker-compose.yml up --build -d     # web app on http://localhost:8080
```

Without Docker, from a checkout where `./install-uv.sh` has built the three
environments:

```bash
cd webapp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8080 --workers 1
```

Exactly one worker process: the job queue lives in memory. One pipeline runs
at a time; further uploads queue.

## Configuration

Every deploy-specific value is an environment variable with a local default.
Put your own values in the environment (or a compose override) rather than in
this repository.

| Variable | Default | Meaning |
|---|---|---|
| `CMAGE_ROOT` | the checkout this file lives in | where `run_pipeline.py` and `.venvs/` are |
| `CMAGE_DATA` | `webapp/data` | jobs, results, gallery index (must be writable) |
| `CMAGE_PORT` | `8080` | port published by the compose file |
| `CMAGE_BASE_URL` | derived from the request | absolute links in the CSV export |
| `CMAGE_MAX_PDF_MB` | `20` | upload size limit (PDF and image) |
| `CMAGE_MAX_PAGES` | `40` | PDF page limit — pages are the cost driver on CPU |
| `CMAGE_MAX_QUEUE` | `5` | uploads waiting behind the running job |
| `CMAGE_MAX_JOBS_PER_CLIENT` | `2` | unfinished jobs per client address |
| `CMAGE_CLIENT_IP_HEADER` | unset | header carrying the real client address behind a proxy/CDN (else `X-Forwarded-For`) |
| `CMAGE_JOB_TIMEOUT_S` | `3600` | a job is killed after this |
| `CMAGE_FAILED_TTL_HOURS` | `24` | failed/cancelled jobs are swept after this; completed runs are kept |
| `CMAGE_MAX_GALLERY_RUNS` | `500` | oldest completed runs are pruned beyond this |
| `CMAGE_KEEP_PDFS` | off | keep the uploaded file after a successful run |
| `CMAGE_DEVICE` | `cpu` | torch / tensorflow device passed to the pipeline |
| `CMAGE_ADMIN_TOKEN` | unset | enables `DELETE /api/runs/{id}` with header `X-Admin-Token` |
| `CMAGE_SAMPLE_PDF` | the repo's `Validation/test_page.pdf` | the "try the sample" document |
| `CMAGE_BENCHMARK_DIR` | `<repo>/benchmarks` | directory scanned for benchmark runs |
| `CMAGE_BENCHMARK_MANIFEST` | `<benchmark dir>/manifest.json` | expected molecules per benchmark PDF |

## Data layout

```
<CMAGE_DATA>/runs.json                     gallery index (derived; rebuilt at start-up)
<CMAGE_DATA>/jobs/<id>/job.json            one record per upload
<CMAGE_DATA>/jobs/<id>/out/run_*/          exactly what run_pipeline.py wrote
<CMAGE_DATA>/jobs/<id>/pipeline.log        the pipeline's output for that job
```

Seed the gallery with a run made elsewhere:

```bash
CMAGE_DATA=/path/to/data webapp/tools/import_run.py --results /path/to/03_CXMS_Results \
    --segments /path/to/02_DIS_Segments --figures /path/to/01_VH_Figures \
    --filename paper.pdf --pages 12 --note "what is known to be wrong in this run"
```

The running server adopts it the next time the gallery is opened.

## Benchmark data

Any directory under `CMAGE_BENCHMARK_DIR` that holds a standard run
(`01_VH_Figures/`, `02_DIS_Segments/`, `03_CXMS_Results/`) is one benchmark run.
Structures are attributed to a PDF by the stem that prefixes their figure name
(`test_common_drugs_1_image_2` → `test_common_drugs_1.pdf`). The manifest lists
what each PDF was generated from:

```json
{
  "name": "Known-answer corpus",
  "description": "PDFs generated from molecules with known structures.",
  "pdfs": [
    {"file": "test_common_drugs_1.pdf", "title": "Common drugs (set 1)",
     "molecules": [{"key": "aspirin", "label": "Aspirin", "smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"}]}
  ]
}
```

Verdicts: `match` (same molecule, stereo included), `stereo` (same molecule
ignoring stereochemistry), `wrong`, `invalid`. Canonicalisation runs in the
pipeline's own stage-3 environment (`server/canon.py`), so the comparison uses
the same RDKit build that produced the predictions. A run may ship its own
`verdicts.json` (see `server/benchmark.py`), in which case that is used as-is.

## API

```
POST   /api/jobs                 multipart "file" (PDF or PNG/JPEG/TIFF/WebP/BMP) → 202 {id, status, …}
POST   /api/jobs/sample          run the bundled sample page
GET    /api/jobs/{id}            status, stage, live counts, results when done
DELETE /api/jobs/{id}            cancel
GET    /api/jobs/{id}/results.csv
GET    /api/jobs/{id}/log
GET    /api/jobs/{id}/img/{segment|render|figure}/{name}
GET    /api/runs                 gallery
DELETE /api/runs/{id}            needs X-Admin-Token
GET    /api/benchmark
GET    /api/health               weights and environments present, queue state
```

Uploads are classified by content, not extension: an HTML error page saved as
`.png` is refused before anything is queued.
