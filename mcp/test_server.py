"""Tests for the C-MAGE MCP server, run through FastMCP's in-memory client.

    mcp/.venv/bin/python -m pytest mcp/test_server.py -q

The live tests each need something external, and skip without it:
- molscribe: the repo's .venv-ms and cached MolScribe weights
- cmage roundtrip: the webapp at CMAGE_URL. It uploads a private job, waits for it, and
  deletes it.
- sonnet: ANTHROPIC_API_KEY or OPENROUTER_API_KEY. It makes one real call, costing a
  fraction of a cent.
"""
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402

ASPIRIN = next(Path("/root/cmage-work").glob("cmage-img*/corpus_rdkit_1500/aspirin_cid2244.png"), None)
ASPIRIN_CANONICAL = "CC(=O)Oc1ccccc1C(=O)O"
IN_FLIGHT = {"queued", "pending", "running", "processing", "starting"}


async def _call(name, args, raise_on_error=True):
    async with Client(server.mcp) as client:
        return await client.call_tool(name, args, raise_on_error=raise_on_error)


def call(name, args, raise_on_error=True):
    return asyncio.run(_call(name, args, raise_on_error))


def data(res):
    if getattr(res, "data", None) is not None:
        return res.data
    if getattr(res, "structured_content", None):
        return res.structured_content
    return json.loads(text(res))


def text(res):
    return "".join(getattr(b, "text", "") for b in res.content)


def canonical(smiles):
    """RDKit lives in .venv-ms, not in the server's venv, so canonicalise there."""
    code = ("import sys;from rdkit import Chem,RDLogger;RDLogger.DisableLog('rdApp.*');"
            "m=Chem.MolFromSmiles(sys.argv[1]);print(Chem.MolToSmiles(m) if m else '')")
    return subprocess.run([server.MS_PYTHON, "-c", code, smiles], capture_output=True, text=True).stdout.strip() or None


def cmage_up():
    try:
        return httpx.get(f"{server.CMAGE_URL}/api/health", timeout=5).status_code == 200
    except httpx.HTTPError:
        return False


# --------------------------------------------------------------------------- offline
def test_tools_listed():
    async def go():
        async with Client(server.mcp) as client:
            return {t.name for t in await client.list_tools()}
    assert asyncio.run(go()) == {"cmage_upload", "cmage_job", "cmage_delete", "molscribe_read", "sonnet_read"}


def test_needs_exactly_one_input():
    res = call("molscribe_read", {}, raise_on_error=False)
    assert res.is_error and "exactly one" in text(res)


def test_rejects_a_pdf_where_an_image_is_needed():
    res = call("sonnet_read", {"content_base64": base64.b64encode(b"%PDF-1.7 not an image").decode()},
               raise_on_error=False)
    assert res.is_error and "one image" in text(res)


def test_http_transport_refuses_paths(monkeypatch):
    monkeypatch.setattr(server, "ALLOW_PATHS", False)
    res = call("molscribe_read", {"path": "/etc/passwd"}, raise_on_error=False)
    assert res.is_error and "disabled" in text(res)


def test_job_id_cannot_walk_the_url():
    res = call("cmage_job", {"job_id": "../../etc"}, raise_on_error=False)
    assert res.is_error and "job id" in text(res)


def test_answer_parsing_takes_the_last_json():
    reply = 'Counting... {"smiles": "CC"}\nOn reflection:\n{"smiles": "CCO", "name_if_recognised": "ethanol", "confidence": "high"}'
    assert server._parse_answer(reply)["smiles"] == "CCO"
    assert server._parse_answer("no json here") == {}


@pytest.mark.skipif(ASPIRIN is None, reason="needs a corpus image")
def test_sonnet_cost_and_fields_with_a_stubbed_call(monkeypatch):
    monkeypatch.setattr(server, "_sonnet_call", lambda *a, **k: {
        "text": 'ok\n{"smiles": "CCO", "name_if_recognised": "", "confidence": "high"}',
        "backend": "stub", "model": "stub", "input_tokens": 1000, "output_tokens": 200})
    out = data(call("sonnet_read", {"path": str(ASPIRIN)}))
    assert out["smiles"] == "CCO" and out["confidence"] == "high"
    assert out["est_cost_usd"] == pytest.approx(0.004)        # 1000 x $2/M + 200 x $10/M


# --------------------------------------------------------------------------- live
@pytest.mark.skipif(ASPIRIN is None or not Path(server.MS_PYTHON).exists(), reason="needs .venv-ms and a corpus image")
def test_molscribe_reads_aspirin():
    out = data(call("molscribe_read", {"path": str(ASPIRIN)}))
    assert out["valid"] and out["canonical_smiles"] == ASPIRIN_CANONICAL, out
    assert out["tier"] in ("high", "low") and 0 <= out["confidence"] <= 1


@pytest.mark.skipif(ASPIRIN is None or not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENROUTER_API_KEY")),
                    reason="needs an API key")
def test_sonnet_reads_aspirin():
    out = data(call("sonnet_read", {"path": str(ASPIRIN)}))
    assert out["smiles"], out["raw_text"][-400:]
    assert out["usage"]["input_tokens"] > 0 and out["est_cost_usd"] > 0
    got = canonical(out["smiles"])
    assert got is not None, f"not a valid SMILES: {out['smiles']}"
    print(f"\nsonnet_read via {out['backend']} ({out['model']}): {out['smiles']} "
          f"-> {'matches' if got == ASPIRIN_CANONICAL else 'DIFFERS from'} aspirin, "
          f"{out['usage']}, ${out['est_cost_usd']}")


@pytest.mark.skipif(ASPIRIN is None or not cmage_up(), reason="needs the C-MAGE webapp")
def test_cmage_upload_poll_and_delete():
    up = data(call("cmage_upload", {"path": str(ASPIRIN)}))
    assert up["job_id"] and up["owner_token"] and up["job"].get("public") is not True
    deadline = time.time() + 480
    job = {"status": up["status"]}
    try:
        while True:
            job = data(call("cmage_job", {"job_id": up["job_id"]}))
            if job["status"] not in IN_FLIGHT:
                break
            assert time.time() < deadline, f"job still {job['status']} after 8 minutes"
            time.sleep(10)
        assert job["status"] == "done", job
        first = job["structures"][0]
        print(f"\ncmage pipeline: {first['cxsmiles']} (confidence {first['confidence']}, tier {first['confidence_tier']})")
        assert canonical(first["smiles"]) == ASPIRIN_CANONICAL, first
    finally:
        if job["status"] not in IN_FLIGHT:
            gone = data(call("cmage_delete", {"job_id": up["job_id"], "owner_token": up["owner_token"]}))
            assert gone == {"deleted": up["job_id"]}
