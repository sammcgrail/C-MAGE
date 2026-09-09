"""Job queue, pipeline runner and the persistent gallery index.

One worker thread runs one pipeline at a time (the stages are CPU-bound and
already use every core). Each job owns a directory:

    <data>/jobs/<id>/job.json         the record below, rewritten atomically
    <data>/jobs/<id>/input/           the uploaded PDF or image (deleted after
                                      a successful run unless CMAGE_KEEP_PDFS)
    <data>/jobs/<id>/out/run_*/       what run_pipeline.py wrote
    <data>/jobs/<id>/pipeline.log     the runner's combined stdout/stderr

Completed jobs are the gallery. <data>/runs.json is a derived index of them,
rebuilt from the job directories at start-up so it can never be stale.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import config, results

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_STAGE = re.compile(r"==> Stage (\d)/3\s+(.*)")

STAGE_NAMES = {0: "Queued", 1: "Extracting figures from pages",
               2: "Segmenting structures out of figures", 3: "Reading structures into SMILES"}
STAGE_HINTS = {1: "10-30 s to load the model, then a few seconds per page",
               2: "about 5 s per figure",
               3: "about 3 s per structure"}
TERMINAL = {"done", "failed", "cancelled"}


@dataclass
class Job:
    id: str
    kind: str                      # "pdf" | "image"
    filename: str                  # display name of the upload
    size: int
    pages: int                     # PDF pages, or 1 for an image
    created: float
    origin: str = "upload"         # upload | sample | import
    status: str = "queued"         # queued | running | done | failed | cancelled
    stage: int = 0
    stage_started: float | None = None
    started: float | None = None
    finished: float | None = None
    error: str | None = None
    client: str = ""
    label: str = ""                # free text shown in the gallery (imports)
    run_dir: str | None = None     # relative to the job dir
    results: dict | None = None
    note: str = ""                 # standing caveat text attached by an importer
    public: bool = False           # listed in the gallery. NEVER default true for
                                   # an upload: this tool is pointed at unpublished
                                   # manuscripts and draft patents, and the figure
                                   # images a run exposes are the pages themselves.
    token: str = ""                # owner capability, handed to the uploader once
                                   # in the response that created the job and never
                                   # served again. Proves "I am the person who
                                   # uploaded this" for unlisting and deleting.
    sample: bool = False           # the one canonical demo run, reused by every
                                   # visitor instead of re-running the pipeline

    @property
    def dir(self) -> Path:
        return config.JOBS_DIR / self.id

    def run_path(self) -> Path | None:
        if self.run_dir:
            p = self.dir / self.run_dir
            return p if p.is_dir() else None
        return results.find_run_dir(self.dir / "out") if (self.dir / "out").is_dir() else None


def _now() -> float:
    return time.time()


def _atomic_write(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    os.replace(tmp, path)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._pending: list[str] = []
        self._procs: dict[str, subprocess.Popen] = {}
        self._cancel: set[str] = set()
        self._cv = threading.Condition()
        self.current: str | None = None
        config.JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self._load()
        threading.Thread(target=self._worker, name="cmage-worker", daemon=True).start()
        threading.Thread(target=self._sweeper, name="cmage-sweeper", daemon=True).start()

    # ------------------------------------------------------------------ persistence
    def _load(self) -> None:
        for jd in sorted(config.JOBS_DIR.iterdir()):
            rec = jd / "job.json"
            if not rec.is_file():
                continue
            try:
                data = json.loads(rec.read_text())
                job = Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})
            except Exception:  # noqa: BLE001 - one corrupt record must not block start-up
                continue
            if job.status == "running":
                job.status, job.error, job.finished = "failed", "The server restarted while this job was running.", _now()
                self._save(job)
            self._jobs[job.id] = job
        for job in sorted(self._jobs.values(), key=lambda j: j.created):
            if job.status == "queued" and (job.dir / "input").is_dir():
                self._pending.append(job.id)
        self._write_index()

    def _save(self, job: Job) -> None:
        job.dir.mkdir(parents=True, exist_ok=True)
        _atomic_write(job.dir / "job.json", asdict(job))

    def _listed(self, job: "Job") -> bool:
        """In the gallery? Completed AND explicitly published. Anything else is
        reachable only by its own unguessable id, which only the uploader has."""
        return job.status == "done" and bool(job.public)

    def _write_index(self) -> None:
        done = [self.summary(j) for j in self._jobs.values() if self._listed(j)]
        done.sort(key=lambda s: s["finished"] or 0, reverse=True)
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _atomic_write(config.INDEX_FILE, {"version": 1, "updated": _now(), "runs": done})

    # ------------------------------------------------------------------ public API
    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def refresh(self) -> int:
        """Adopt completed job directories written by tools/import_run.py while
        the server is running. Returns how many were added."""
        added = 0
        with self._cv:
            known = set(self._jobs)
        for jd in config.JOBS_DIR.iterdir():
            if jd.name in known or not (jd / "job.json").is_file():
                continue
            try:
                data = json.loads((jd / "job.json").read_text())
                job = Job(**{k: v for k, v in data.items() if k in Job.__dataclass_fields__})
            except Exception:  # noqa: BLE001
                continue
            if job.status == "done":
                with self._cv:
                    self._jobs.setdefault(job.id, job)
                added += 1
        if added:
            self._write_index()
        return added

    def gallery(self) -> list[dict]:
        self.refresh()
        done = [self.summary(j) for j in self._jobs.values() if self._listed(j)]
        done.sort(key=lambda s: s["finished"] or 0, reverse=True)
        return done

    def queue_state(self) -> dict:
        with self._cv:
            return {"queued": len(self._pending), "running": self.current}

    def active_for(self, client: str) -> int:
        return sum(1 for j in self._jobs.values() if j.client == client and j.status not in TERMINAL)

    def submit(self, *, kind: str, filename: str, size: int, pages: int, client: str,
               origin: str = "upload", public: bool = False, sample: bool = False
               ) -> tuple[Job | None, str | None]:
        """Reserve a job directory. The caller writes the input file, then calls enqueue()."""
        with self._cv:
            if len(self._pending) >= config.MAX_QUEUE:
                return None, "The queue is full right now — try again in a few minutes."
        job = Job(id=secrets.token_urlsafe(9), kind=kind, filename=filename, size=size, pages=pages,
                  created=_now(), origin=origin, client=client, public=public, sample=sample,
                  token=secrets.token_urlsafe(16))
        (job.dir / "input").mkdir(parents=True, exist_ok=False)
        self._save(job)
        with self._cv:
            self._jobs[job.id] = job
        return job, None

    def enqueue(self, job: Job) -> None:
        with self._cv:
            self._pending.append(job.id)
            self._cv.notify()

    def discard(self, job: Job) -> None:
        """Drop a reserved job whose input never arrived."""
        with self._cv:
            self._jobs.pop(job.id, None)
        shutil.rmtree(job.dir, ignore_errors=True)

    def cancel(self, job_id: str) -> bool:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None or job.status in TERMINAL:
                return False
            if job.status == "queued":
                if job_id in self._pending:
                    self._pending.remove(job_id)
                job.status, job.finished, job.error = "cancelled", _now(), "Cancelled before it started."
                self._save(job)
                return True
            self._cancel.add(job_id)
            proc = self._procs.get(job_id)
        if proc is not None:
            self._kill(proc)
        return True

    def delete(self, job_id: str) -> bool:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None or job.status not in TERMINAL:
                return False
            self._jobs.pop(job_id, None)
        shutil.rmtree(job.dir, ignore_errors=True)
        self._write_index()
        return True

    def owns(self, job: Job, token: str) -> bool:
        """Is the caller the person who uploaded this run?

        Two ways to prove it, and they cover different situations:
          * the owner token minted at upload and returned exactly once, or
          * knowing the id of a run that is NOT listed anywhere.
        A listed run's id is public by construction, so id-knowledge stops
        counting the moment it is published.

        The id-knowledge arm is DELIBERATELY WEAK: an unlisted id also travels
        in a shared results link, in the `job` column of an exported CSV and in
        every image URL, so holding one does not establish consent. Callers must
        therefore only accept it for actions that REDUCE exposure -- deleting or
        unlisting. Anything that increases exposure must demand the token; see
        `_may_manage(require_token=...)` in app.py.
        """
        return bool(token and job.token and secrets.compare_digest(token, job.token)) or not job.public

    def set_public(self, job_id: str, public: bool) -> bool:
        with self._cv:
            job = self._jobs.get(job_id)
            if job is None or job.status != "done":
                return False
            job.public = bool(public)
            self._save(job)
        self._write_index()
        return True

    def canonical_sample(self) -> Job | None:
        """The single demo run every visitor is shown.

        Without this, "Try the one-page sample" spends ~90 s of CPU and leaves a
        permanent gallery entry on EVERY click -- an unauthenticated way to fill
        the disk and flood the listing. The oldest completed sample wins so the
        choice is stable across restarts.
        """
        with self._cv:
            cands = [j for j in self._jobs.values() if j.sample and j.status == "done"]
        return min(cands, key=lambda j: j.finished or j.created) if cands else None

    def register_import(self, job: Job) -> None:
        """Adopt a job directory prepared by tools/import_run.py."""
        with self._cv:
            self._jobs[job.id] = job
        self._write_index()

    def position(self, job_id: str) -> int | None:
        with self._cv:
            return self._pending.index(job_id) + 1 if job_id in self._pending else None

    # ------------------------------------------------------------------ views
    def summary(self, job: Job) -> dict:
        counts = (job.results or {}).get("counts") or {}
        structs = (job.results or {}).get("structures") or []
        return {
            "id": job.id, "kind": job.kind, "filename": job.filename, "label": job.label,
            "origin": job.origin, "pages": job.pages, "created": job.created, "finished": job.finished,
            "duration_s": (job.finished - job.started) if job.started and job.finished else None,
            "counts": counts, "note": job.note, "public": bool(job.public),
            "thumbs": [s["segment_image"] for s in structs if s.get("segment_image")][:6],
        }

    def public(self, job: Job) -> dict:
        now = _now()
        run_dir = job.run_path()
        d = {
            "id": job.id, "kind": job.kind, "filename": job.filename, "label": job.label, "origin": job.origin,
            "public": bool(job.public), "sample": bool(job.sample),
            "pages": job.pages, "size": job.size, "status": job.status, "created": job.created,
            "started": job.started, "finished": job.finished, "error": job.error, "note": job.note,
            "stage": job.stage, "stage_name": STAGE_NAMES.get(job.stage, ""), "stage_hint": STAGE_HINTS.get(job.stage, ""),
            "skips_stage1": job.kind == "image",
            "elapsed_s": ((job.finished or now) - job.started) if job.started else 0,
            "stage_elapsed_s": ((job.finished or now) - job.stage_started) if job.stage_started else 0,
            "queue_position": self.position(job.id),
            "progress": results.progress(run_dir) if job.status == "running" else None,
        }
        if job.status == "done":
            d["results"] = job.results
        return d

    # ------------------------------------------------------------------ worker
    def _worker(self) -> None:
        while True:
            with self._cv:
                while not self._pending:
                    self._cv.wait()
                job_id = self._pending.pop(0)
                job = self._jobs.get(job_id)
                if job is None:
                    continue
                self.current = job_id
            try:
                self._run(job)
            except Exception as exc:  # noqa: BLE001 - the worker must survive anything
                job.status, job.error, job.finished = "failed", f"Internal error: {exc}"[:500], _now()
                self._save(job)
            finally:
                with self._cv:
                    self.current = None
                    self._procs.pop(job_id, None)
                    self._cancel.discard(job_id)
                self._write_index()

    def _run(self, job: Job) -> None:
        job.status, job.started, job.stage, job.stage_started = "running", _now(), 0, None
        self._save(job)

        in_dir, out_dir = job.dir / "input", job.dir / "out"
        out_dir.mkdir(exist_ok=True)
        cmd = [sys.executable, str(config.CMAGE_ROOT / "run_pipeline.py"), "--out", str(out_dir), "--device", config.DEVICE]
        if job.kind == "image":
            cmd += ["--stages", "2,3", "--figures", str(in_dir)]
        else:
            cmd += ["--stages", "1,2,3", "--pdfs", str(in_dir)]
        env = dict(os.environ, CMAGE_DEVICE=config.DEVICE, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1, cwd=str(config.CMAGE_ROOT),
                                env=env, start_new_session=True)
        with self._cv:
            self._procs[job.id] = proc
        timed_out = threading.Event()

        def _timeout() -> None:
            timed_out.set()
            self._kill(proc)

        timer = threading.Timer(config.JOB_TIMEOUT_S, _timeout)
        timer.start()
        tail: list[str] = []
        try:
            with open(job.dir / "pipeline.log", "w", encoding="utf-8") as log:
                for raw in proc.stdout:
                    line = _ANSI.sub("", raw)
                    log.write(line)
                    log.flush()
                    if line.strip():
                        tail.append(line.rstrip())
                        del tail[:-40]
                    m = _STAGE.search(line)
                    if m and "skipped" not in line:
                        job.stage, job.stage_started = int(m.group(1)), _now()
                        self._save(job)
            code = proc.wait()
        finally:
            timer.cancel()

        job.finished = _now()
        if job.id in self._cancel:
            job.status, job.error = "cancelled", "Cancelled."
        elif timed_out.is_set():
            job.status, job.error = "failed", f"Gave up after {config.JOB_TIMEOUT_S // 60} minutes."
        elif code != 0:
            job.status, job.error = "failed", self._explain(code, tail)
        else:
            run_dir = results.find_run_dir(out_dir)
            if run_dir is None:
                job.status, job.error = "failed", "The pipeline finished but wrote no run directory."
            else:
                if job.kind == "image":
                    # Stage 1 was skipped, so the input image *is* the figure; keep a copy
                    # in the standard place so the source can be shown beside each crop.
                    fig_dir = run_dir / results.SUBDIRS["figure"]
                    fig_dir.mkdir(exist_ok=True)
                    for f in in_dir.iterdir():
                        if f.is_file():
                            shutil.copy2(f, fig_dir / f.name)
                job.run_dir = str(run_dir.relative_to(job.dir))
                job.results = results.parse_run(run_dir)
                job.status = "done"
                if not config.KEEP_PDFS:
                    shutil.rmtree(in_dir, ignore_errors=True)
        self._save(job)

    @staticmethod
    def _explain(code: int, tail: list[str]) -> str:
        text = "\n".join(tail)
        if "No PDFs found" in text:
            return "The upload was not a readable PDF."
        if "weights download failed" in text or "mask_rcnn_molecule" in text:
            return "Stage 2 could not load its segmentation weights on this server."
        if "MemoryError" in text or "Killed" in text or code == -9:
            return "The pipeline ran out of memory on this server. Try a smaller document."
        m = re.search(r"Stage (\d) failed", text)
        if m:
            return f"Stage {m.group(1)} failed. See the log for details."
        return f"The pipeline exited with status {code}. See the log for details."

    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            time.sleep(3)
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    # ------------------------------------------------------------------ housekeeping
    def _sweeper(self) -> None:
        while True:
            time.sleep(600)
            try:
                self.sweep()
            except Exception:  # noqa: BLE001
                pass

    def sweep(self) -> None:
        now = _now()
        ttl = config.FAILED_TTL_HOURS * 3600
        doomed = []
        upload_ttl = config.UPLOAD_TTL_HOURS * 3600
        with self._cv:
            for job in self._jobs.values():
                age = now - (job.finished or job.created)
                if job.status in ("failed", "cancelled") and age > ttl:
                    doomed.append(job.id)
                # An upload nobody published is somebody's private document. Keep it
                # long enough to be useful, then stop holding it.
                elif (job.status == "done" and job.origin == "upload" and not job.public
                      and not job.sample and upload_ttl > 0 and age > upload_ttl):
                    doomed.append(job.id)
            done = sorted((j for j in self._jobs.values() if j.status == "done"), key=lambda j: j.finished or 0)
            for job in done[:max(0, len(done) - config.MAX_GALLERY_RUNS)]:
                doomed.append(job.id)
        for jid in doomed:
            self.delete(jid)
        # A job directory with no record (crash between mkdir and save) is litter.
        for jd in config.JOBS_DIR.iterdir():
            if jd.is_dir() and not (jd / "job.json").exists() and jd.stat().st_mtime < now - 3600:
                shutil.rmtree(jd, ignore_errors=True)
