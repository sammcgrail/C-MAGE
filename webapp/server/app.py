"""HTTP API for the C-MAGE web app.

    GET  /                                   the single-page UI
    GET  /api/health                         liveness + which model caches are present
    GET  /api/limits                         upload limits, for the UI to display
    POST /api/jobs            multipart file  PDF or image -> {id, token}
                              + publish=1 to list the finished run publicly
    POST /api/jobs/sample                    the one canonical demo run, reused
    GET  /api/jobs/{id}                      status, progress, results when done
    DELETE /api/jobs/{id}                    cancel a queued or running job
    POST /api/jobs/{id}/publish              list / unlist a finished run
    GET  /api/jobs/{id}/log                  the pipeline's own output
    GET  /api/jobs/{id}/results.csv          every structure as CSV
    GET  /api/jobs/{id}/img/{kind}/{name}    segment | render | figure images
    GET  /api/runs                           the gallery (PUBLISHED runs only)
    DELETE /api/runs/{id}                    remove a run (owner token or admin)
    GET  /api/benchmark                      known-answer corpus results
    GET  /api/benchmark/{run}/img/{kind}/{name}

Run with exactly one worker process: the queue lives in memory.

UPLOADS ARE PRIVATE BY DEFAULT. A finished run is reachable at its own
unguessable id; it is listed in the gallery only if the uploader ticks the box.
Ownership is proved by the token returned once by POST /api/jobs, or -- for a
run that was never listed -- by knowing its id at all, since nothing else
publishes it. Every owner can delete their own run without an operator token.
"""
from __future__ import annotations

import csv
import io
import re
import secrets
import shutil
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import benchmark, config, jobs, results, uploads

app = FastAPI(title="C-MAGE", docs_url=None, redoc_url=None, openapi_url=None)
store = jobs.JobStore()

_ID = re.compile(r"[A-Za-z0-9_-]{6,40}")
_MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
          ".tif": "image/tiff", ".tiff": "image/tiff", ".bmp": "image/bmp"}


def _client(request: Request) -> str:
    for name in (config.CLIENT_IP_HEADER, "x-forwarded-for", "x-real-ip"):
        value = request.headers.get(name, "") if name else ""
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _base_url(request: Request) -> str:
    if config.BASE_URL:
        return config.BASE_URL
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def _job_or_404(job_id: str) -> jobs.Job:
    if not _ID.fullmatch(job_id or ""):
        raise HTTPException(404, "No such job.")
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "No such job. Results are kept for a while, but not forever.")
    return job


def _image_response(path: Path) -> FileResponse:
    return FileResponse(path, media_type=_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
                        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"})


# ---------------------------------------------------------------------------- pages
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html", media_type="text/html",
                        headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
def icon() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "favicon.png", media_type="image/png",
                        headers={"Cache-Control": "public, max-age=604800"})


# ---------------------------------------------------------------------------- meta
@app.get("/api/health")
def health() -> dict:
    hf = Path(__import__("os").environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"
    decimer = Path.home() / ".cache" / "decimer" / "mask_rcnn_molecule.h5"
    legacy = config.CMAGE_ROOT / "cxmolscribe-wd" / "DECIMER-Image-Segmentation" / "decimer_segmentation" / "mask_rcnn_molecule.h5"
    return {
        "ok": True, "version": config.VERSION, "queue": store.queue_state(),
        "weights": {
            "visualheist": any(hf.glob("models--*visualheist*")),
            "molscribe": any(hf.glob("models--*MolScribe*")),
            "decimer": decimer.is_file() or legacy.is_file(),
        },
        "envs": {n: (config.CMAGE_ROOT / ".venvs" / n / "bin" / "python").exists()
                 for n in ("cmage-visualheist", "cmage-decimer", "cmage-cxmolscribe")},
    }


@app.get("/api/limits")
def limits() -> dict:
    return {"max_mb": config.MAX_PDF_MB, "max_pages": config.MAX_PAGES, "max_queue": config.MAX_QUEUE,
            "threshold": config.CONFIDENCE_THRESHOLD,
            "sample": config.SAMPLE_PDF.is_file() or store.canonical_sample() is not None,
            "publish_default": config.PUBLISH_UPLOADS_DEFAULT,
            "upload_ttl_hours": config.UPLOAD_TTL_HOURS,
            "version": config.VERSION}


def _is_admin(request: Request) -> bool:
    token = request.headers.get("x-admin-token", "")
    return bool(config.ADMIN_TOKEN) and secrets.compare_digest(token, config.ADMIN_TOKEN)


def _may_manage(job: jobs.Job, request: Request, *, unlisting: bool) -> bool:
    """May this caller delete or unlist this run?

    The operator always may. Otherwise the caller must hold the owner token from
    the upload response -- except while the run is unlisted, where knowing the id
    is itself proof of ownership, because nothing has ever published it. Once a
    run IS listed its id is on a public page, so `unlisting` demands the token.
    """
    if _is_admin(request):
        return True
    if unlisting:
        token = request.headers.get("x-job-token", "")
        return bool(token and job.token and secrets.compare_digest(token, job.token))
    return store.owns(job, request.headers.get("x-job-token", ""))


# ---------------------------------------------------------------------------- jobs
def _admit(request: Request) -> str:
    client = _client(request)
    free_mb = shutil.disk_usage(config.DATA_DIR).free // (1024 * 1024)
    if free_mb < config.MIN_FREE_DISK_MB:
        raise HTTPException(503, "This server is low on disk space; uploads are paused.")
    if store.active_for(client) >= config.MAX_JOBS_PER_CLIENT:
        raise HTTPException(429, f"You already have {config.MAX_JOBS_PER_CLIENT} jobs in flight; wait for one to finish.")
    return client


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _start(request: Request, info: dict, filename: str, origin: str,
           publish: bool = False, sample: bool = False) -> JSONResponse:
    client = _admit(request)
    job, why = store.submit(kind=info["kind"], filename=filename, size=len(info["bytes"]),
                            pages=info["pages"], client=client, origin=origin,
                            public=publish, sample=sample)
    if job is None:
        raise HTTPException(429, why, headers={"Retry-After": "120"})
    try:
        (job.dir / "input" / f"{info['stem']}{info['ext']}").write_bytes(info["bytes"])
    except OSError as exc:
        store.discard(job)
        raise HTTPException(500, f"Could not store the upload: {exc}") from exc
    store.enqueue(job)
    # The owner token is returned HERE and nowhere else. It is what lets the
    # uploader delete or unlist the run afterwards without an operator.
    return JSONResponse(dict(store.public(job), token=job.token), status_code=202)


@app.post("/api/jobs")
def create_job(request: Request, file: UploadFile = File(...),
               publish: str = Form(default="")) -> JSONResponse:
    buf = bytearray()
    while True:
        chunk = file.file.read(1 << 20)
        if not chunk:
            break
        buf += chunk
        if len(buf) > config.MAX_PDF_BYTES:
            raise HTTPException(413, f"That file is over the {config.MAX_PDF_MB:g} MB limit.")
    try:
        info = uploads.classify(bytes(buf), file.filename or "")
    except uploads.Rejected as exc:
        raise HTTPException(400, str(exc)) from exc
    display = (file.filename or "").strip()[:120] or (f"{info['stem']}{info['ext']}")
    wants_public = _truthy(publish) if publish != "" else config.PUBLISH_UPLOADS_DEFAULT
    return _start(request, info, display, "upload", publish=wants_public)


@app.post("/api/jobs/sample")
def create_sample(request: Request) -> JSONResponse:
    """Show the demo. The SAME finished run every time.

    Re-running it per click cost ~90 s of six-core CPU and left a permanent
    gallery entry, so the button was an unauthenticated way to burn the box and
    flood the listing; three duplicates accumulated in an hour of casual use.
    The pipeline is deterministic on a fixed input, so a second run adds nothing
    a visitor could see. It is executed once, only if no sample exists yet.
    """
    existing = store.canonical_sample()
    if existing is not None:
        return JSONResponse(store.public(existing), status_code=200)
    if not config.SAMPLE_PDF.is_file():
        raise HTTPException(404, "No sample document is installed on this server.")
    data = config.SAMPLE_PDF.read_bytes()
    try:
        info = uploads.classify(data, config.SAMPLE_PDF.name)
    except uploads.Rejected as exc:
        raise HTTPException(500, f"The bundled sample is unusable: {exc}") from exc
    return _start(request, info, config.SAMPLE_PDF.name, "sample", publish=True, sample=True)


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str) -> dict:
    return store.public(_job_or_404(job_id))


@app.delete("/api/jobs/{job_id}")
def job_cancel(job_id: str) -> dict:
    job = _job_or_404(job_id)
    if not store.cancel(job.id):
        raise HTTPException(409, "That job has already finished.")
    return store.public(job)


@app.post("/api/jobs/{job_id}/publish")
def job_publish(job_id: str, request: Request, publish: str = Form(default="1")) -> dict:
    """List or unlist a finished run. Owner or operator only."""
    job = _job_or_404(job_id)
    if job.status != "done":
        raise HTTPException(409, "Only a finished run can be listed.")
    wanted = _truthy(publish)
    if not _may_manage(job, request, unlisting=(job.public and not wanted)):
        raise HTTPException(403, "Only the person who uploaded this run can change whether it is listed.")
    store.set_public(job.id, wanted)
    return {"id": job.id, "public": wanted}


@app.get("/api/jobs/{job_id}/log")
def job_log(job_id: str) -> PlainTextResponse:
    job = _job_or_404(job_id)
    log = job.dir / "pipeline.log"
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else "(no log yet)"
    return PlainTextResponse(text[-200_000:])


@app.get("/api/jobs/{job_id}/img/{kind}/{name}")
def job_image(job_id: str, kind: str, name: str) -> FileResponse:
    job = _job_or_404(job_id)
    run_dir = job.run_path()
    path = results.image_path(run_dir, kind, name) if run_dir else None
    if path is None:
        raise HTTPException(404, "No such image.")
    return _image_response(path)


_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def _csv_cell(value):
    """Neutralise spreadsheet formula injection.

    Excel, LibreOffice and Sheets execute a cell that begins `= + - @`, and this
    file is assembled from strings a stranger chose: the uploaded FILE NAME goes
    straight into the `document` column. A file named `=2*21` really did land as
    a live formula in an export. Prefixing an apostrophe is the standard fix and
    is what a spreadsheet strips again on display.
    """
    text = value if isinstance(value, str) else str(value)
    return "'" + text if text[:1] in _FORMULA_LEAD else value


def _csv_row(cells: list) -> list:
    return [_csv_cell(c) for c in cells]


@app.get("/api/jobs/{job_id}/results.csv")
def job_csv(job_id: str, request: Request) -> Response:
    job = _job_or_404(job_id)
    if job.status != "done" or not job.results:
        raise HTTPException(409, "This job has no results yet.")
    base = _base_url(request)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["n", "confidence_tier", "confidence", "smiles", "valid", "source", "figure", "structure",
                "segment_image", "rendered_image", "figure_image", "document", "job"])
    for i, s in enumerate(job.results["structures"], 1):
        img = lambda kind, name: f"{base}/api/jobs/{job.id}/img/{kind}/{name}" if name else ""  # noqa: E731
        w.writerow(_csv_row([i, s["tier"], "" if s["confidence"] is None else f"{s['confidence']:.6f}", s["smiles"],
                             int(bool(s["valid"])), s["source"], s["figure"], "" if s["molecule"] is None else s["molecule"],
                             img("segment", s["segment_image"]), img("render", s["rendered_image"]),
                             img("figure", s["figure_image"]), job.filename, job.id]))
    return Response(out.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="cmage-{job.id}.csv"'})


# ---------------------------------------------------------------------------- gallery
@app.get("/api/runs")
def gallery() -> dict:
    return {"runs": store.gallery(), "threshold": config.CONFIDENCE_THRESHOLD, "generated": time.time()}


@app.delete("/api/runs/{job_id}")
def gallery_delete(job_id: str, request: Request) -> dict:
    """Remove a run and everything on disk behind it.

    Previously this required CMAGE_ADMIN_TOKEN, which is unset on most
    deployments -- so it answered 403 to everyone, including the operator, and
    there was no way to withdraw an upload at all. An owner can now always
    delete their own run; the admin token is only the operator's override for
    somebody else's.
    """
    job = _job_or_404(job_id)
    if not _may_manage(job, request, unlisting=bool(job.public)):
        raise HTTPException(403, "Only the person who uploaded this run, or the operator, can delete it.")
    if not store.delete(job.id):
        raise HTTPException(409, "That job is still running; cancel it first.")
    return {"deleted": job.id}


# ---------------------------------------------------------------------------- benchmark
@app.get("/api/benchmark")
def benchmark_view() -> dict:
    data = dict(benchmark.build())
    data.pop("_runs", None)
    return data


@app.get("/api/benchmark/{run_id}/img/{kind}/{name}")
def benchmark_image(run_id: str, kind: str, name: str) -> FileResponse:
    benchmark.build()
    run_dir = benchmark.run_path(run_id) if re.fullmatch(r"[0-9a-f]{10}", run_id or "") else None
    path = results.image_path(run_dir, kind, name) if run_dir else None
    if path is None:
        raise HTTPException(404, "No such image.")
    return _image_response(path)


app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
