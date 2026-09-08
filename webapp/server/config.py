"""Runtime configuration for the C-MAGE web app.

Everything that differs between a laptop, a CI box and a public server is an
environment variable with a localhost-friendly default. Nothing in here names a
host, a domain or a person: deploy-specific values belong in the environment of
the process (or the compose file / reverse proxy) that runs it, not in the repo.
"""
from __future__ import annotations

import os
from pathlib import Path

WEBAPP_DIR = Path(__file__).resolve().parents[1]

# The C-MAGE checkout that owns run_pipeline.py and the three .venvs. Defaults to
# the repository this file lives in, so a plain `uvicorn` from the checkout works.
CMAGE_ROOT = Path(os.environ.get("CMAGE_ROOT") or WEBAPP_DIR.parent).resolve()

# Where jobs, results and the gallery index are kept. Must be writable.
DATA_DIR = Path(os.environ.get("CMAGE_DATA") or WEBAPP_DIR / "data").resolve()
JOBS_DIR = DATA_DIR / "jobs"
INDEX_FILE = DATA_DIR / "runs.json"

# Public base URL, used only to write absolute links into the CSV export.
# Empty = derive it from the incoming request (works behind any reverse proxy
# that forwards Host and X-Forwarded-Proto).
BASE_URL = os.environ.get("CMAGE_BASE_URL", "").rstrip("/")

# Upload limits. This is a CPU pipeline: stage 1 is ~10-30 s per document plus a
# few seconds per page, stage 3 is ~2-3 s per structure, so page count is the
# real cost driver.
MAX_PDF_MB = float(os.environ.get("CMAGE_MAX_PDF_MB", "20"))
MAX_PDF_BYTES = int(MAX_PDF_MB * 1024 * 1024)
MAX_PAGES = int(os.environ.get("CMAGE_MAX_PAGES", "40"))
MAX_QUEUE = int(os.environ.get("CMAGE_MAX_QUEUE", "5"))          # jobs waiting, not counting the running one
MAX_JOBS_PER_CLIENT = int(os.environ.get("CMAGE_MAX_JOBS_PER_CLIENT", "2"))
# Request header that carries the real client address when a proxy or CDN sits
# in front (first comma-separated value is used). Falls back to X-Forwarded-For,
# X-Real-IP, then the socket peer.
CLIENT_IP_HEADER = os.environ.get("CMAGE_CLIENT_IP_HEADER", "").strip().lower()
JOB_TIMEOUT_S = int(os.environ.get("CMAGE_JOB_TIMEOUT_S", str(60 * 60)))
MIN_FREE_DISK_MB = int(os.environ.get("CMAGE_MIN_FREE_DISK_MB", "2048"))

# Failed / cancelled jobs are swept after this many hours, and so are completed
# uploads the uploader never published -- holding someone's unpublished figures
# on disk forever is a cost with no matching benefit. Published and imported runs
# (the gallery) are kept up to MAX_GALLERY_RUNS, oldest pruned first.
FAILED_TTL_HOURS = float(os.environ.get("CMAGE_FAILED_TTL_HOURS", "24"))
UPLOAD_TTL_HOURS = float(os.environ.get("CMAGE_UPLOAD_TTL_HOURS", "72"))
MAX_GALLERY_RUNS = int(os.environ.get("CMAGE_MAX_GALLERY_RUNS", "500"))
KEEP_PDFS = os.environ.get("CMAGE_KEEP_PDFS", "0") not in ("", "0", "false", "no")

# torch/tensorflow device for the pipeline. CPU unless you know better.
DEVICE = os.environ.get("CMAGE_DEVICE", "cpu")

# folder_ms.py's split. Displayed to the user; the split itself is the pipeline's.
CONFIDENCE_THRESHOLD = 0.8431

# Optional token that unlocks DELETE and unlisting on runs somebody else owns.
# Unset only removes the OPERATOR's override: an uploader can always delete or
# unlist their own run, because that path authenticates with the per-job owner
# token instead. Deletion is never globally disabled.
ADMIN_TOKEN = os.environ.get("CMAGE_ADMIN_TOKEN", "")

# Do uploads appear in the public gallery? NO, unless the person uploading ticks
# the box. The users of a structure-extraction tool are holding unpublished
# manuscripts and draft patents, and a run exposes the extracted figure regions,
# which for a PDF are the pages themselves. Opt-in is the only defensible default;
# set this only for a deployment where every upload is already public.
PUBLISH_UPLOADS_DEFAULT = os.environ.get("CMAGE_PUBLISH_UPLOADS_DEFAULT", "0") not in ("", "0", "false", "no")

# A small PDF shipped with the pipeline, offered as a one-tap demo.
SAMPLE_PDF = Path(os.environ.get("CMAGE_SAMPLE_PDF") or
                  CMAGE_ROOT / "cxmolscribe-wd" / "DECIMER-Image-Segmentation" / "Validation" / "test_page.pdf")

# Benchmark tab: a directory of pipeline run(s) over a corpus with known answers,
# plus one or more manifests mapping each document to the molecules it was made
# from. CMAGE_BENCHMARK_MANIFEST may list several paths separated by os.pathsep;
# left empty, <dir>/manifest.json and <dir>/ground_truth/*.json are used.
BENCHMARK_DIR = Path(os.environ.get("CMAGE_BENCHMARK_DIR") or CMAGE_ROOT / "benchmarks").resolve()
BENCHMARK_MANIFESTS = [Path(p).resolve() for p in os.environ.get("CMAGE_BENCHMARK_MANIFEST", "").split(os.pathsep) if p.strip()]
# Which run directories (relative to BENCHMARK_DIR) the tab shows. Empty = the
# conventional results/pdf_corpus/run if present, else every run found.
BENCHMARK_RUNS = [r.strip() for r in os.environ.get("CMAGE_BENCHMARK_RUNS", "").split(",") if r.strip()]

STATIC_DIR = WEBAPP_DIR / "static"
VERSION = "0.2.0"
