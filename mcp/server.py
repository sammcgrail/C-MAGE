#!/usr/bin/env python3
"""C-MAGE as an MCP server: chemical-structure recognition tools for any MCP client.

Tools
- cmage_upload, cmage_job, cmage_delete: the full C-MAGE pipeline through the webapp's own
  job API. Upload a PDF or image, poll it, then read the structures it found.
- molscribe_read: one image straight through MolScribe, with no figure extraction or
  segmentation around it. The model runs in a persistent worker under the repo's MolScribe
  venv, so torch never enters this server's environment and the weights load once, not per
  call.
- sonnet_read: one image through a single bare Messages API call to Sonnet, with no tools
  and no agent loop. This is the arm the benchmark page describes as "a bare API call would
  be a different and cheaper arm; it has not been run".

Transports
- stdio (default): `python server.py`. Local clients only, and path inputs are allowed.
- HTTP: `python server.py --http [--port 8799]`. It binds 127.0.0.1, has NO auth, and
  refuses path inputs, because a path argument on a network-reachable server is an
  arbitrary file read. Put real auth in front before exposing it anywhere.

Environment
- CMAGE_URL: webapp base URL (default http://127.0.0.1:20079)
- CMAGE_MS_PYTHON: python with molscribe + torch + rdkit (default: the repo's .venv-ms)
- ANTHROPIC_API_KEY: for sonnet_read. OPENROUTER_API_KEY works as a fallback.
- CMAGE_SONNET_MODEL: default claude-sonnet-5
"""
import argparse
import base64
import binascii
import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CMAGE_URL = os.environ.get("CMAGE_URL", "http://127.0.0.1:20079").rstrip("/")
MS_PYTHON = os.environ.get("CMAGE_MS_PYTHON", str(REPO / ".venv-ms" / "bin" / "python"))
SONNET_MODEL = os.environ.get("CMAGE_SONNET_MODEL", "claude-sonnet-5")
OPENROUTER_MODEL = os.environ.get("CMAGE_OPENROUTER_MODEL", "anthropic/" + SONNET_MODEL)
# Anthropic list price for Sonnet 5 per million tokens (docs.claude.com pricing, checked 2026-09-14).
SONNET_PRICE_PER_MTOK = {"input": 2.00, "output": 10.00}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_API_IMAGE_BYTES = 5 * 1024 * 1024          # the Messages API's per-image limit
MOLSCRIBE_CONFIDENT = 0.8431                   # C-MAGE's CI-3.0 cut for "high confidence"
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

ALLOW_PATHS = True   # switched off for the HTTP transport in main()

mcp = FastMCP(
    "cmage",
    instructions=(
        "Chemical structure recognition. molscribe_read and sonnet_read take one image of one "
        "structure and return a SMILES. cmage_upload runs the full C-MAGE pipeline on a PDF or "
        "image, which is asynchronous: poll cmage_job until status is done. Keep the owner_token "
        "that cmage_upload returns; deleting the run needs it."),
)


# --------------------------------------------------------------------------- inputs
def _read_input(path: str | None, content_base64: str | None, filename: str | None) -> tuple[bytes, str]:
    if bool(path) == bool(content_base64):
        raise ToolError("Pass exactly one of `path` or `content_base64`.")
    if path:
        if not ALLOW_PATHS:
            raise ToolError("Path inputs are disabled on the HTTP transport; send content_base64 instead.")
        p = Path(path).expanduser()
        if not p.is_file():
            raise ToolError(f"No such file: {p}")
        data, name = p.read_bytes(), filename or p.name
    else:
        try:
            data = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ToolError("`content_base64` is not valid base64.")
        name = filename or "upload"
    if not data:
        raise ToolError("The file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ToolError(f"The file is {len(data) / 1e6:.1f} MB; the limit is {MAX_UPLOAD_BYTES / 1e6:.0f} MB.")
    return data, name


def _image_type(data: bytes) -> str | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _require_image(data: bytes) -> str:
    kind = _image_type(data)
    if kind is None:
        raise ToolError("This tool reads one image (PNG, JPEG, GIF or WebP). For a PDF, use cmage_upload.")
    return kind


def _raise_for(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    try:
        detail = r.json().get("detail")
    except ValueError:
        detail = r.text[:300]
    raise ToolError(f"C-MAGE returned HTTP {r.status_code}: {detail}")


def _job_id(job_id: str) -> str:
    if not JOB_ID.match(job_id or ""):
        raise ToolError("That is not a C-MAGE job id.")
    return job_id


# --------------------------------------------------------------------------- C-MAGE pipeline
@mcp.tool
def cmage_upload(path: str | None = None, content_base64: str | None = None, filename: str | None = None,
                 segment: bool = False, publish: bool = False) -> dict:
    """Submit a PDF or an image to the full C-MAGE pipeline.

    It returns at once with a job id, because a PDF takes about a minute a page. Poll
    cmage_job until status is "done". Pass exactly one of `path` (local file) or
    `content_base64` (with `filename`). `segment` asks for segmentation of an image that
    holds several structures. `publish` lists the run in the public gallery; runs are
    private by default. Keep the returned owner_token: deleting the run needs it.
    """
    data, name = _read_input(path, content_base64, filename)
    with httpx.Client(timeout=120) as client:
        r = client.post(f"{CMAGE_URL}/api/jobs", files={"file": (name, data)},
                        data={"publish": "1" if publish else "0", "segment": "1" if segment else "0"})
    _raise_for(r)
    job = r.json()
    return {"job_id": job.get("id"), "status": job.get("status"), "owner_token": job.get("token"),
            "job": {k: v for k, v in job.items() if k != "token"}}


@mcp.tool
def cmage_job(job_id: str) -> dict:
    """Status of a C-MAGE job and, once it is done, every structure it found.

    Each structure carries cxsmiles (lossless, abbreviation labels kept), smiles, and
    expanded_smiles (abbreviations substituted). It also has a confidence and its tier,
    whether RDKit could parse it, and links to the segment and rendered images.
    """
    job_id = _job_id(job_id)
    with httpx.Client(timeout=60) as client:
        r = client.get(f"{CMAGE_URL}/api/jobs/{job_id}")
        _raise_for(r)
        job = r.json()
        out = {"job_id": job_id, "status": job.get("status"), "job": job}
        if job.get("status") == "done":
            rc = client.get(f"{CMAGE_URL}/api/jobs/{job_id}/results.csv")
            if rc.status_code == 200:
                out["structures"] = list(csv.DictReader(io.StringIO(rc.text)))
    return out


@mcp.tool
def cmage_delete(job_id: str, owner_token: str) -> dict:
    """Delete a finished C-MAGE run and everything stored for it. Needs the owner_token from cmage_upload."""
    job_id = _job_id(job_id)
    r = httpx.delete(f"{CMAGE_URL}/api/runs/{job_id}", headers={"X-Job-Token": owner_token}, timeout=60)
    _raise_for(r)
    return r.json()


# --------------------------------------------------------------------------- MolScribe
class _MolScribeWorker:
    """One long-lived MolScribe process, speaking one JSON object per line.

    The weights take seconds to load, and torch is heavy. A worker started once
    keeps the model warm, and keeps torch out of the server's own environment.
    """

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.seq = 0

    def _start(self) -> None:
        env = dict(os.environ)
        env.setdefault("HF_HUB_OFFLINE", "1")        # weights are cached; never stall on the network
        self.proc = subprocess.Popen(
            [MS_PYTHON, str(HERE / "molscribe_worker.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=open(Path(tempfile.gettempdir()) / "cmage-mcp-molscribe.log", "ab"), text=True, env=env)
        first = self.proc.stdout.readline()
        msg = json.loads(first) if first.strip() else {}
        if not msg.get("ready"):
            self.proc = None
            raise ToolError(f"MolScribe worker did not start: {msg.get('error') or 'no response'}")

    def predict(self, image_path: str) -> dict:
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            self.seq += 1
            self.proc.stdin.write(json.dumps({"id": self.seq, "path": image_path}) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
            if not line:
                self.proc = None
                raise ToolError("MolScribe worker exited mid-request.")
        return json.loads(line)


_molscribe = _MolScribeWorker()


@mcp.tool
def molscribe_read(path: str | None = None, content_base64: str | None = None,
                   filename: str | None = None) -> dict:
    """Read ONE chemical-structure image with MolScribe, C-MAGE's recogniser, with no pipeline around it.

    Returns:
    - smiles exactly as MolScribe emitted it (CXSMILES labels kept when present)
    - plain_smiles, with the extension block dropped
    - canonical_smiles, from RDKit
    - valid, and the confidence and its tier (high at >= 0.8431)
    Best on a clean, already cropped drawing; a page or a multi-structure figure belongs
    in cmage_upload.
    """
    data, _ = _read_input(path, content_base64, filename)
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}[_require_image(data)]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
    try:
        out = _molscribe.predict(tmp.name)
    finally:
        os.unlink(tmp.name)
    if out.get("error"):
        raise ToolError(f"MolScribe failed: {out['error']}")
    out.pop("id", None)
    conf = out.get("confidence")
    out["tier"] = None if conf is None else ("high" if conf >= MOLSCRIBE_CONFIDENT else "low")
    return out


# --------------------------------------------------------------------------- bare Sonnet
SONNET_PROMPT = """Read this chemical structure drawing and give its SMILES.

Write the SMILES for the structure depicted. Stereochemistry where the drawing shows it (wedge/hash, E/Z). All fragments if more than one is drawn (salts, counter-ions), dot-separated.

RULES:
- Work from the DRAWING. If you recognise the molecule you may cross-check, but the drawing is the authority.
- COUNT THE ATOMS EXPLICITLY before writing. Count ring vertices and chain carbons.
- Exactly one SMILES. UNREADABLE rather than a guess, with a reason.

Think it through, then END your reply with this JSON object on its own line:
{"smiles": "...", "name_if_recognised": "...", "confidence": "high|medium|low"}"""


def _sonnet_call(media_type: str, b64: str, max_tokens: int) -> dict:
    """One request, no tools. Anthropic's API when ANTHROPIC_API_KEY is set, else OpenRouter."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic
        resp = anthropic.Anthropic().messages.create(
            model=SONNET_MODEL, max_tokens=max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": SONNET_PROMPT}]}])
        text = "".join(getattr(b, "text", "") for b in resp.content)
        return {"text": text, "backend": "anthropic", "model": resp.model,
                "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    if os.environ.get("OPENROUTER_API_KEY"):
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions", timeout=300,
            headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"},
            json={"model": OPENROUTER_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                {"type": "text", "text": SONNET_PROMPT}]}]})
        if r.status_code >= 400:
            raise ToolError(f"OpenRouter returned HTTP {r.status_code}: {r.text[:300]}")
        j = r.json()
        usage = j.get("usage") or {}
        return {"text": j["choices"][0]["message"]["content"] or "", "backend": "openrouter",
                "model": j.get("model"), "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens")}
    raise ToolError("sonnet_read needs ANTHROPIC_API_KEY (or OPENROUTER_API_KEY) in the server's environment.")


def _parse_answer(text: str) -> dict:
    """The LAST JSON object in the reply that has a smiles key. Anything before it is the model's working."""
    for m in reversed(list(re.finditer(r"\{[^{}]*\"smiles\"[^{}]*\}", text))):
        try:
            return json.loads(m.group(0))
        except ValueError:
            continue
    return {}


@mcp.tool
def sonnet_read(path: str | None = None, content_base64: str | None = None, filename: str | None = None,
                max_tokens: int = 4096) -> dict:
    """Read ONE chemical-structure image with a single bare Sonnet API call: no tools, no agent loop, no lookups.

    Returns the SMILES, the name if Sonnet recognised the molecule, its self-rated
    confidence, the raw reply, token usage, and an estimated cost at Anthropic list price.
    """
    data, _ = _read_input(path, content_base64, filename)
    media_type = _require_image(data)
    if len(data) > MAX_API_IMAGE_BYTES:
        raise ToolError("The Messages API accepts images up to 5 MB; downscale it first.")
    call = _sonnet_call(media_type, base64.b64encode(data).decode(), max_tokens)
    answer = _parse_answer(call["text"])
    tin, tout = call.get("input_tokens") or 0, call.get("output_tokens") or 0
    return {
        "smiles": answer.get("smiles"), "name_if_recognised": answer.get("name_if_recognised"),
        "confidence": answer.get("confidence"), "raw_text": call["text"],
        "backend": call["backend"], "model": call["model"],
        "usage": {"input_tokens": tin, "output_tokens": tout},
        "est_cost_usd": round((tin * SONNET_PRICE_PER_MTOK["input"] + tout * SONNET_PRICE_PER_MTOK["output"]) / 1e6, 5),
    }


# --------------------------------------------------------------------------- entry point
def main() -> None:
    global ALLOW_PATHS
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--http", action="store_true", help="serve streamable HTTP on 127.0.0.1 instead of stdio")
    ap.add_argument("--port", type=int, default=8799)
    args = ap.parse_args()
    if args.http:
        ALLOW_PATHS = False
        mcp.run(transport="http", host="127.0.0.1", port=args.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
