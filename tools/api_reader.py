#!/usr/bin/env python3
"""Plain-API arm: Sonnet 5.5 reads corpus images in ONE Messages API call each, with no tools.

Every other Sonnet reading on the site comes from an agent (Read, Bash, RDKit, OSRA, crops, a
re-render round trip). This arm asks what the model does with the image and a fixed prompt alone:
one request per image, no tools, no shared context, the image as base64 and the prompt as text, and
the answer taken from a final `SMILES: <smiles>` line.

    api_reader.py run   --out DIR --env-file FILE [--n 50] [--conc 4] [--budget 15]
                        [--prompt-file prompt_v2.txt --prompt-version v2]
                        [--max-consec-fail 5] [--publish-every 100 --publish-cmd CMD]
    api_reader.py status --out DIR

Stops STARTING calls (in-flight ones land) on any of: the budget (spent + what the calls in flight
are expected to cost reaches --budget), --max-consec-fail failures in a row, or a file DIR/STOP.
--publish-cmd runs every --publish-every new ledger rows and once at the end; it is site-specific,
so it lives outside this repo.

Images are the FIRST n rows of corpus_images/manifest.csv (manifest order), read straight out of the
three zips; a row whose PNG is missing from them is skipped and the next one taken. The key is read
from ANTHROPIC_CREDITS_KEY in --env-file and sent as x-api-key; it is never printed or written.

DIR/ledger.jsonl is the state: one line per finished image (ok or failed). A restart skips every
key already in it, so a crash costs at most the requests in flight. DIR/raw/<key>.json holds the
full response body. Scoring is NOT done here: the tab builder scores every answer with
sonnet_batch.verdict(), the one scoring function for every Sonnet reading.
"""
import argparse
import base64
import csv
import json
import random
import re
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus_images"
MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 16000
URL = "https://api.anthropic.com/v1/messages"
# $ per MTok: input, output, 5 min cache write, cache read (Sonnet 5.5 list price)
PRICE = (2.0, 10.0, 2.50, 0.20)
PROMPT_NAME = "prompt.txt"
SMILES_RE = re.compile(r"^\s*\**\s*SMILES\s*\**\s*:\s*\**\s*`?([^`\s]+)`?\s*\**\s*$", re.M)

TAG_RE = re.compile(r"^<smiles>(.*)</smiles>$", re.I)

LOCK = threading.Lock()


def cost(u: dict) -> float:
    return ((u.get("input_tokens") or 0) * PRICE[0] + (u.get("output_tokens") or 0) * PRICE[1]
            + (u.get("cache_creation_input_tokens") or 0) * PRICE[2]
            + (u.get("cache_read_input_tokens") or 0) * PRICE[3]) / 1e6


def parse_smiles(text: str) -> str | None:
    """The last `SMILES: ...` line. The prompt writes the slot as `SMILES: <smiles>`, and some replies
    copy the placeholder's brackets as tags (`SMILES: <smiles>CCO</smiles>`); those are unwrapped
    here, and the builder counts and shows how many answers needed it."""
    m = SMILES_RE.findall(text or "")
    return unwrap(m[-1]) if m else None


def unwrap(s: str) -> str:
    w = TAG_RE.match(s)
    return w.group(1) if w else s


def read_key(env_file: Path) -> str:
    for line in env_file.read_text().splitlines():
        if line.startswith("ANTHROPIC_CREDITS_KEY="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if v:
                return v
    raise SystemExit(f"ANTHROPIC_CREDITS_KEY not set in {env_file}")


def pick(n: int) -> list[dict]:
    rows = list(csv.DictReader(open(CORPUS / "manifest.csv")))
    zips = {p: zipfile.ZipFile(CORPUS / f"cmage_corpus_part{p}of3.zip") for p in ("1", "2", "3")}
    out, skipped = [], []
    for r in rows:
        if len(out) >= n:
            break
        name = f"cmage_corpus/{r['file']}"
        z = zips.get(r["zip_part"])
        try:
            data = z.read(name) if z else None
        except KeyError:
            data = None
        if not data:
            skipped.append(r["key"])
            continue
        out.append(dict(r, png=data))
    if skipped:
        print(f"skipped (missing from the zips): {skipped}", flush=True)
    return out


def ledger(out: Path) -> list[dict]:
    p = out / "ledger.jsonl"
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def call(key: str, prompt: str, png: bytes) -> tuple[int, dict | None, str, float, str | None]:
    body = {"model": MODEL, "max_tokens": MAX_TOKENS, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": base64.b64encode(png).decode()}},
        {"type": "text", "text": prompt}]}]}
    hdr = {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    t0 = time.time()
    try:
        r = requests.post(URL, headers=hdr, json=body, timeout=900)
    except requests.RequestException as e:
        return -1, None, f"{type(e).__name__}: {e}", time.time() - t0, None
    dt = time.time() - t0
    try:
        j = r.json()
    except ValueError:
        j = None
    return r.status_code, j, (r.text[:500] if r.status_code != 200 else ""), dt, r.headers.get("retry-after")


def read_one(row: dict, key: str, prompt: str, out: Path, state: dict) -> dict:
    attempts, other_errors, log = 0, 0, []
    while True:
        if state["stop"]:
            return {}
        attempts += 1
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        code, j, err, dt, ra = call(key, prompt, row["png"])
        if code == 200 and j:
            u = j.get("usage") or {}
            text = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
            (out / "raw").mkdir(exist_ok=True)
            (out / "raw" / f"{row['key']}.json").write_text(json.dumps(j, indent=1))
            return {"k": row["key"], "name": row["name"], "truth": row["truth_smiles"], "status": "ok",
                    "prompt": state["pv"],
                    "model": j.get("model"), "id": j.get("id"), "stop_reason": j.get("stop_reason"),
                    "stop_details": j.get("stop_details"), "text": text, "smiles": parse_smiles(text),
                    "usage": u, "latency_s": round(dt, 2), "cost_usd": round(cost(u), 5),
                    "attempts": attempts, "errors": log, "started": started,
                    "ended": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        log.append({"http": code, "err": (err or json.dumps(j))[:300], "t": started})
        if code in (429, 529):
            if attempts >= 12:
                break
            wait = float(ra) if ra and ra.replace(".", "", 1).isdigit() else min(120, 5 * 2 ** min(attempts, 5))
            wait += random.uniform(0, 3)
            print(f"  {row['key']}: HTTP {code}, backing off {wait:.0f} s", flush=True)
            time.sleep(wait)
            continue
        other_errors += 1
        print(f"  {row['key']}: error {code} {(err or '')[:160]}", flush=True)
        if other_errors >= 2:
            break
        time.sleep(5)
    return {"k": row["key"], "name": row["name"], "truth": row["truth_smiles"], "status": "failed",
            "prompt": state["pv"],
            "attempts": attempts, "errors": log, "cost_usd": 0.0,
            "ended": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def cmd_run(a) -> int:
    import subprocess
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prompt = (Path(a.prompt_file) if a.prompt_file else out / PROMPT_NAME).read_text()
    key = read_key(Path(a.env_file))
    rows = pick(a.n)
    L0 = ledger(out)
    done = {r["k"] for r in L0}
    todo = [r for r in rows if r["key"] not in done]
    spent = sum(r.get("cost_usd") or 0 for r in L0)
    print(f"{len(rows)} picked, {len(done)} already in the ledger, {len(todo)} to read; ${spent:.4f} spent so far; "
          f"prompt {a.prompt_version}, budget ${a.budget:.2f}, {a.conc} in flight", flush=True)
    state = {"stop": None, "spent": spent, "pv": a.prompt_version, "fly": 0, "consec": 0,
             "n_ok": sum(1 for r in L0 if r["status"] == "ok"), "since_pub": 0}

    def avg() -> float:
        return state["spent"] / state["n_ok"] if state["n_ok"] else 0.02

    def check_stop() -> None:      # caller holds LOCK
        if state["stop"]:
            return
        if (out / "STOP").exists():
            state["stop"] = f"STOP file {out / 'STOP'}"
        elif state["spent"] + state["fly"] * avg() >= a.budget:
            state["stop"] = (f"budget: ${state['spent']:.2f} spent + {state['fly']} in flight x ${avg():.3f} "
                             f">= ${a.budget:.2f}")
        elif state["consec"] >= a.max_consec_fail:
            state["stop"] = f"{state['consec']} failures in a row"

    def task(row):
        with LOCK:
            check_stop()
            if state["stop"]:
                return None
            state["fly"] += 1
        try:
            rec = read_one(row, key, prompt, out, state)
        finally:
            with LOCK:
                state["fly"] -= 1
        if not rec:
            return None
        with LOCK:
            with open(out / "ledger.jsonl", "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            state["spent"] += rec.get("cost_usd") or 0
            if rec["status"] == "ok":
                state["n_ok"] += 1
                state["consec"] = 0
            else:
                state["consec"] += 1
            state["since_pub"] += 1
            u = rec.get("usage") or {}
            print(f"{rec['k']}: {rec['status']} stop={rec.get('stop_reason')} smiles={rec.get('smiles')!r} "
                  f"in={u.get('input_tokens')} out={u.get('output_tokens')} {rec.get('latency_s')} s "
                  f"${rec.get('cost_usd')}  total ${state['spent']:.4f}", flush=True)
            check_stop()
        return rec

    def publish(final: bool) -> None:
        if not a.publish_cmd:
            return
        print(f"PUBLISH ({'final' if final else 'periodic'}): {a.publish_cmd}", flush=True)
        r = subprocess.run(a.publish_cmd, shell=True)
        print(f"PUBLISH exit {r.returncode}", flush=True)

    with ThreadPoolExecutor(max_workers=a.conc) as ex:
        futs = [ex.submit(task, r) for r in todo]
        for f in as_completed(futs):
            f.result()
            if a.publish_every and state["since_pub"] >= a.publish_every and not state["stop"]:
                with LOCK:
                    state["since_pub"] = 0
                publish(False)       # workers keep reading while this runs
            if state["stop"]:
                for g in futs:
                    g.cancel()
    L = ledger(out)
    ok = [r for r in L if r["status"] == "ok"]
    print(f"DONE: {len(ok)} ok, {len(L) - len(ok)} failed, ${sum(r.get('cost_usd') or 0 for r in L):.4f}"
          + (f"; STOPPED: {state['stop']}" if state["stop"] else ""), flush=True)
    publish(True)
    return 3 if state["stop"] and not state["stop"].startswith("budget") else 0


def cmd_status(a) -> int:
    L = ledger(Path(a.out))
    ok = [r for r in L if r["status"] == "ok"]
    print(f"{len(L)} in ledger, {len(ok)} ok, ${sum(r.get('cost_usd') or 0 for r in L):.4f}, "
          f"max_tokens {sum(1 for r in ok if r.get('stop_reason') == 'max_tokens')}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--env-file", required=True)
    r.add_argument("--n", type=int, default=50)
    r.add_argument("--conc", type=int, default=4)
    r.add_argument("--budget", type=float, default=15.0)
    r.add_argument("--prompt-file")
    r.add_argument("--prompt-version", default="v1")
    r.add_argument("--max-consec-fail", type=int, default=5)
    r.add_argument("--publish-every", type=int, default=0)
    r.add_argument("--publish-cmd")
    s = sp.add_parser("status")
    s.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.exit(cmd_run(a) if a.cmd == "run" else cmd_status(a))
