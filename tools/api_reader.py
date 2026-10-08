#!/usr/bin/env python3
"""Plain-API arm: a model reads corpus images in ONE Messages API call each, with no tools.

Every other Sonnet reading on the site comes from an agent (Read, Bash, RDKit, OSRA, crops, a
re-render round trip). This arm asks what the model does with the image and a fixed prompt alone:
one request per image, no tools, no shared context, the image as base64 and the prompt as text, and
the answer taken from a final `SMILES: ...` line.

    api_reader.py run     --out DIR --env-file FILE [--model claude-sonnet-5-5] [--n 50] [--conc 4]
                          [--budget 15] [--max-tokens N] [--prompt-file F --prompt-version vN]
                          [--max-consec-fail 5] [--publish-every 100 --publish-cmd CMD]
    api_reader.py status  --out DIR
    api_reader.py maxtok  --out DIR        diagnose every max_tokens hit and its retries

OUTPUT BUDGET. One uniform default for every model, max_tokens 64,000, so results compare across
models and the worst case per image is capped; it is lowered to the model's maximum output if that
is smaller (read from the Models API, GET /v1/models/<id> -> max_tokens: 128,000 for
claude-sonnet-5-5, -sonnet-5, -fable-5-1, -haiku-5-5 and -opus-5-5 on 2026-10-08). --max-tokens
overrides it. Every row records the max_tokens it ran with. Every call STREAMS, so a large budget
never meets the non-streaming request timeout.

MAX_TOKENS FOLLOW-UPS. A reading that stops on max_tokens is retried, each attempt kept in
DIR/retries.jsonl beside the original row. A row read below the default budget (the first rows of
the Sonnet 5.5 run went at 16,000) is first re-read once at the default ("budget"). A reading that
still runs out at the default gets ONE "commit" retry: same budget, the prompt plus COMMIT_SUFFIX
(make one careful pass, then commit to an answer). Retries ask for summarized thinking so the
reasoning can be inspected; display does not change what is generated or billed. The tab scores the
last retry that finished.

STOPS. New calls stop STARTING (in-flight ones land) when: spend reaches --budget (spend = actual
usage of every landed call and retry, plus the calls in flight at the mean cost so far), or
--max-consec-fail failures in a row, or a file DIR/STOP appears. Rate limits: 429/529 back off
(retry-after when given); each 429 also lowers the number of calls in flight by one, down to 1,
and the ledger keeps the output-token rate-limit headers of every call.

Images are the FIRST n rows of corpus_images/manifest.csv (manifest order), read straight out of the
three zips; a row whose PNG is missing from them is skipped. The key is read from
ANTHROPIC_CREDITS_KEY in --env-file and sent as x-api-key; it is never printed or written.

DIR/ledger.jsonl is the state: one line per finished image (ok or failed); a restart skips every
key in it. DIR/raw/<key>.json (and <key>__<kind>.json for retries) hold the full response. Scoring is
NOT done here: the tab builder scores every answer with sonnet_batch.verdict().
"""
import argparse
import base64
import csv
import json
import random
import re
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus_images"
URL = "https://api.anthropic.com/v1/messages"
HDR = {"anthropic-version": "2023-06-01", "content-type": "application/json"}
# $ per MTok: input, output, 5 min cache write, cache read. List prices (platform docs, as in
# /root/usage-style price tables): a model missing here is refused rather than costed by guess.
PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0, 2.50, 0.20),
    "claude-sonnet-5": (2.0, 10.0, 2.50, 0.20),
    "claude-opus-5-5": (4.0, 20.0, 5.00, 0.20),
    "claude-fable-5-1": (10.0, 50.0, 12.50, 0.25),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
}
DEFAULT_MAX_TOKENS = 64000
COMMIT_SUFFIX = ("\n\nKeep your reasoning bounded: make one careful pass over the drawing, check it once, and "
                 "then commit to your best answer. Do not re-derive the structure again and again; a best "
                 "answer on the final SMILES line beats running out of room before writing one.")
PROMPT_NAME = "prompt.txt"
SMILES_RE = re.compile(r"^\s*\**\s*SMILES\s*\**\s*:\s*\**\s*`?([^`\s]+)`?\s*\**\s*$", re.M)
TAG_RE = re.compile(r"^<smiles>(.*)</smiles>$", re.I)

LOCK = threading.Lock()


def cost(u: dict, model: str) -> float:
    p = PRICES[model]
    return ((u.get("input_tokens") or 0) * p[0] + (u.get("output_tokens") or 0) * p[1]
            + (u.get("cache_creation_input_tokens") or 0) * p[2]
            + (u.get("cache_read_input_tokens") or 0) * p[3]) / 1e6


def parse_smiles(text: str) -> str | None:
    """The last `SMILES: ...` line. Prompt v1 wrote the slot as `SMILES: <smiles>`, and some replies
    copied the placeholder's brackets as tags (`SMILES: <smiles>CCO</smiles>`); those are unwrapped
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


def model_cap(key: str, model: str) -> int:
    """The model's maximum output tokens, from the Models API (no guessing)."""
    r = requests.get(f"https://api.anthropic.com/v1/models/{model}", headers={"x-api-key": key, **HDR}, timeout=30)
    j = r.json() if r.ok else {}
    if not j.get("max_tokens"):
        raise SystemExit(f"Models API gave no max_tokens for {model} (HTTP {r.status_code}); pass --max-tokens")
    return int(j["max_tokens"])


def pick(n: int) -> list[dict]:
    rows = list(csv.DictReader(open(CORPUS / "manifest.csv")))
    zips = {p: zipfile.ZipFile(CORPUS / f"cmage_corpus_part{p}of3.zip") for p in ("1", "2", "3")}
    out, skipped = [], []
    for r in rows:
        if len(out) >= n:
            break
        z = zips.get(r["zip_part"])
        try:
            z.getinfo(f"cmage_corpus/{r['file']}")
        except (KeyError, AttributeError):
            skipped.append(r["key"])
            continue
        out.append(dict(r, zip=z))
    if skipped:
        print(f"skipped (missing from the zips): {skipped}", flush=True)
    return out


def png_of(row: dict) -> bytes:
    with LOCK:                       # ZipFile reads are not thread-safe on a shared handle
        return row["zip"].read(f"cmage_corpus/{row['file']}")


def load(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def ledger(out: Path) -> list[dict]:
    return load(out / "ledger.jsonl")


def retries(out: Path) -> list[dict]:
    return load(out / "retries.jsonl")


class Gate:
    """At most `limit` calls in flight; a 429 lowers the limit by one (never below 1)."""

    def __init__(self, limit: int):
        self.limit, self.active, self.cv = limit, 0, threading.Condition()
        self.events = []

    def __enter__(self):
        with self.cv:
            while self.active >= self.limit:
                self.cv.wait()
            self.active += 1

    def __exit__(self, *a):
        with self.cv:
            self.active -= 1
            self.cv.notify_all()

    def on_429(self, key: str) -> None:
        with self.cv:
            if self.limit > 1:
                self.limit -= 1
            self.events.append((time.strftime("%H:%M:%SZ", time.gmtime()), key, self.limit))
            print(f"  429 on {key}: concurrency now {self.limit}", flush=True)


def stream_call(key: str, body: dict):
    """One streamed Messages call. Returns (http_code, message_or_None, error_text, seconds,
    retry_after, rate_limit_headers). An error EVENT mid-stream maps to 529 (overloaded) or 429."""
    t0 = time.time()
    try:
        r = requests.post(URL, headers={"x-api-key": key, **HDR}, json=dict(body, stream=True),
                          stream=True, timeout=(30, 600))
    except requests.RequestException as e:
        return -1, None, f"{type(e).__name__}: {e}", time.time() - t0, None, {}
    rl = {k.lower(): v for k, v in r.headers.items()
          if k.lower().startswith(("anthropic-ratelimit-output", "anthropic-ratelimit-requests", "retry-after"))}
    if r.status_code != 200:
        txt = r.text[:500]
        return r.status_code, None, txt, time.time() - t0, r.headers.get("retry-after"), rl
    msg, blocks, usage = {}, [], {}
    try:
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            ev = json.loads(raw[5:].strip())
            t = ev.get("type")
            if t == "message_start":
                msg = ev["message"]
                usage.update(msg.get("usage") or {})
            elif t == "content_block_start":
                blocks.append(dict(ev["content_block"]))
            elif t == "content_block_delta":
                d, b = ev["delta"], blocks[ev["index"]]
                if d["type"] == "text_delta":
                    b["text"] = b.get("text", "") + d["text"]
                elif d["type"] == "thinking_delta":
                    b["thinking"] = b.get("thinking", "") + d["thinking"]
                elif d["type"] == "signature_delta":
                    b["signature"] = b.get("signature", "") + d["signature"]
            elif t == "message_delta":
                msg.update({k: v for k, v in ev.get("delta", {}).items()})
                usage.update(ev.get("usage") or {})
            elif t == "error":
                et = (ev.get("error") or {}).get("type", "")
                code = 529 if "overloaded" in et else 429 if "rate_limit" in et else 500
                return code, None, json.dumps(ev)[:500], time.time() - t0, None, rl
    except (requests.RequestException, ValueError) as e:
        return -1, None, f"stream broke: {type(e).__name__}: {e}", time.time() - t0, None, rl
    if not msg.get("stop_reason"):
        return -1, None, "stream ended without a stop_reason", time.time() - t0, None, rl
    msg["content"], msg["usage"] = blocks, usage
    return 200, msg, "", time.time() - t0, None, rl


def body_for(model: str, prompt: str, png: bytes, max_tokens: int, effort: str | None = None,
             summarized: bool = False) -> dict:
    b = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                     "data": base64.b64encode(png).decode()}},
        {"type": "text", "text": prompt}]}]}
    if summarized:
        b["thinking"] = {"type": "adaptive", "display": "summarized"}
    if effort:
        b["output_config"] = {"effort": effort}
    return b


def attempt(row: dict, key: str, body: dict, out: Path, st: dict, gate: Gate, kind: str) -> dict:
    """Call until success, a hard failure (2 non-rate-limit errors) or a stop. kind names the raw file."""
    tries, other, log = 0, 0, []
    while True:
        if st["stop"] and kind == "main":
            return {}
        tries += 1
        started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with gate:
            code, j, err, dt, ra, rl = stream_call(key, body)
        base = {"k": row["key"], "name": row["name"], "truth": row["truth_smiles"], "prompt": st["pv"],
                "model": body["model"], "max_tokens": body["max_tokens"], "stream": True,
                "effort": (body.get("output_config") or {}).get("effort"), "kind": kind, "rl": rl}
        if code == 200:
            u = j.get("usage") or {}
            text = "".join(b.get("text", "") for b in j["content"] if b.get("type") == "text")
            think = "".join(b.get("thinking", "") for b in j["content"] if b.get("type") == "thinking")
            (out / "raw").mkdir(exist_ok=True)
            name = row["key"] if kind == "main" else f"{row['key']}__{kind}"
            (out / "raw" / f"{name}.json").write_text(json.dumps(j, indent=1))
            return dict(base, status="ok", served=j.get("model"), id=j.get("id"),
                        stop_reason=j.get("stop_reason"), stop_details=j.get("stop_details"),
                        text=text, thinking_summary=think or None, smiles=parse_smiles(text), usage=u,
                        latency_s=round(dt, 2), cost_usd=round(cost(u, body["model"]), 5),
                        attempts=tries, errors=log, started=started,
                        ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        log.append({"http": code, "err": (err or "")[:300], "t": started, "rl": rl})
        if code in (429, 529):
            if code == 429:
                gate.on_429(row["key"])
                with LOCK:
                    st["n429"] += 1
            if tries >= 12:
                break
            wait = float(ra) if ra and ra.replace(".", "", 1).isdigit() else min(120, 5 * 2 ** min(tries, 5))
            wait += random.uniform(0, 3)
            print(f"  {row['key']} [{kind}]: HTTP {code}, backing off {wait:.0f} s", flush=True)
            time.sleep(wait)
            continue
        other += 1
        print(f"  {row['key']} [{kind}]: error {code} {(err or '')[:160]}", flush=True)
        if other >= 2:
            break
        time.sleep(5)
    return dict(base, status="failed", attempts=tries, errors=log, cost_usd=0.0,
                ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def followups(row: dict, first: dict, key: str, prompt: str, out: Path, st: dict, gate: Gate, mt: int) -> None:
    """Retry a max_tokens reading: once at the default budget if it ran below it, then ONE "commit"
    retry (prompt + COMMIT_SUFFIX) at the default budget if it still ran out."""
    prev = first
    plan = []
    if (first.get("max_tokens") or 16000) < mt:
        plan.append(("budget", prompt))
    plan.append(("commit", prompt + COMMIT_SUFFIX))
    for kind, p in plan:
        if prev.get("stop_reason") != "max_tokens":
            return
        rec = attempt(row, key, body_for(st["model"], p, png_of(row), mt, summarized=True), out, st, gate, kind)
        rec["of_max_tokens"] = prev.get("max_tokens") or 16000
        if kind == "commit":
            rec["prompt_suffix"] = COMMIT_SUFFIX
        with LOCK:
            with open(out / "retries.jsonl", "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            st["spent"] += rec.get("cost_usd") or 0
            u = rec.get("usage") or {}
            print(f"RETRY {row['key']} [{kind} max_tokens={mt}]: {rec['status']} stop={rec.get('stop_reason')} "
                  f"out={u.get('output_tokens')} smiles={rec.get('smiles')!r} ${rec.get('cost_usd')} "
                  f"total ${st['spent']:.4f}", flush=True)
        if rec["status"] != "ok":
            return
        prev = rec


def cmd_run(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.model not in PRICES:
        raise SystemExit(f"no list price for {a.model}; add it to PRICES first")
    prompt = (Path(a.prompt_file) if a.prompt_file else out / PROMPT_NAME).read_text()
    key = read_key(Path(a.env_file))
    cap = model_cap(key, a.model)
    mt = a.max_tokens or min(DEFAULT_MAX_TOKENS, cap)
    rows = pick(a.n)
    L0, R0 = ledger(out), retries(out)
    done = {r["k"] for r in L0}
    todo = [r for r in rows if r["key"] not in done]
    spent = sum(r.get("cost_usd") or 0 for r in L0 + R0)
    retried = {r["k"] for r in R0}
    owed = [r for r in L0 if r.get("stop_reason") == "max_tokens" and r["k"] not in retried]
    print(f"{len(rows)} picked, {len(done)} in the ledger, {len(todo)} to read, {len(owed)} max_tokens "
          f"follow-up(s) owed; ${spent:.4f} spent; model {a.model} (output cap {cap:,} from the Models API), "
          f"max_tokens {mt:,}, prompt {a.prompt_version}, budget ${a.budget:.2f}, {a.conc} in flight", flush=True)
    st = {"stop": None, "spent": spent, "pv": a.prompt_version, "model": a.model, "fly": 0, "consec": 0,
          "n_ok": sum(1 for r in L0 if r["status"] == "ok"), "since_pub": 0, "n429": 0}
    gate = Gate(a.conc)
    byk = {r["key"]: r for r in pick(len(list(csv.DictReader(open(CORPUS / "manifest.csv")))))}

    def avg() -> float:
        return st["spent"] / st["n_ok"] if st["n_ok"] else 0.02

    def check_stop() -> None:      # caller holds LOCK
        if st["stop"]:
            return
        if (out / "STOP").exists():
            st["stop"] = f"STOP file {out / 'STOP'}"
        elif st["spent"] + st["fly"] * avg() >= a.budget:
            st["stop"] = f"budget: ${st['spent']:.2f} spent + {st['fly']} in flight x ${avg():.3f} >= ${a.budget:.2f}"
        elif st["consec"] >= a.max_consec_fail:
            st["stop"] = f"{st['consec']} failures in a row"

    def owed_task(rec):
        with LOCK:
            check_stop()
            if st["stop"]:
                return None
            st["fly"] += 1
        try:
            followups(byk[rec["k"]], rec, key, prompt, out, st, gate, mt)
        finally:
            with LOCK:
                st["fly"] -= 1

    def task(row):
        with LOCK:
            check_stop()
            if st["stop"]:
                return None
            st["fly"] += 1
        try:
            rec = attempt(row, key, body_for(a.model, prompt, png_of(row), mt), out, st, gate, "main")
            if not rec:
                return None
            with LOCK:
                with open(out / "ledger.jsonl", "a") as fh:
                    fh.write(json.dumps(rec) + "\n")
                st["spent"] += rec.get("cost_usd") or 0
                if rec["status"] == "ok":
                    st["n_ok"] += 1
                    st["consec"] = 0
                else:
                    st["consec"] += 1
                st["since_pub"] += 1
                u = rec.get("usage") or {}
                print(f"{rec['k']}: {rec['status']} stop={rec.get('stop_reason')} smiles={rec.get('smiles')!r} "
                      f"in={u.get('input_tokens')} out={u.get('output_tokens')} {rec.get('latency_s')} s "
                      f"${rec.get('cost_usd')}  total ${st['spent']:.4f}", flush=True)
            if rec.get("stop_reason") == "max_tokens":
                followups(row, rec, key, prompt, out, st, gate, mt)
            with LOCK:
                check_stop()
            return rec
        finally:
            with LOCK:
                st["fly"] -= 1

    def publish(final: bool) -> None:
        if not a.publish_cmd:
            return
        print(f"PUBLISH ({'final' if final else 'periodic'}): {a.publish_cmd}", flush=True)
        r = subprocess.run(a.publish_cmd, shell=True)
        print(f"PUBLISH exit {r.returncode}", flush=True)

    # Workers = the starting concurrency; the Gate is what actually bounds calls in flight.
    with ThreadPoolExecutor(max_workers=a.conc) as ex:
        futs = [ex.submit(owed_task, r) for r in owed] + [ex.submit(task, r) for r in todo]
        for f in as_completed(futs):
            if f.cancelled():
                continue
            f.result()
            if a.publish_every and st["since_pub"] >= a.publish_every and not st["stop"]:
                with LOCK:
                    st["since_pub"] = 0
                publish(False)       # workers keep reading while this runs
            if st["stop"]:
                for g in futs:
                    g.cancel()
    L, R = ledger(out), retries(out)
    ok = [r for r in L if r["status"] == "ok"]
    print(f"DONE: {len(ok)} ok, {len(L) - len(ok)} failed, {len(R)} retries, "
          f"${sum(r.get('cost_usd') or 0 for r in L + R):.4f}; 429s {st['n429']}, concurrency now {gate.limit}"
          + (f"; STOPPED: {st['stop']}" if st["stop"] else ""), flush=True)
    publish(True)
    return 3 if st["stop"] and not st["stop"].startswith(("budget", "STOP")) else 0


def cmd_status(a) -> int:
    L, R = ledger(Path(a.out)), retries(Path(a.out))
    ok = [r for r in L if r["status"] == "ok"]
    print(f"{len(L)} in ledger, {len(ok)} ok, {len(R)} retries, ${sum(r.get('cost_usd') or 0 for r in L + R):.4f}, "
          f"max_tokens {sum(1 for r in ok if r.get('stop_reason') == 'max_tokens')}")
    return 0


REDERIVE = re.compile(r"\b(wait|actually|let me re|recount|re-count|hmm|on second thought|let me check again|"
                      r"let me redo|i miscounted|correction)\b", re.I)


def churn(text: str) -> dict:
    """Signs of looping in a reply or a thinking summary: re-derivation markers, repeated lines,
    how many distinct SMILES-looking candidates it wrote."""
    lines = [l.strip() for l in (text or "").splitlines() if len(l.strip()) > 25]
    rep = len(lines) - len(set(lines))
    cands = set(re.findall(r"SMILES[:\s]+`?([A-Za-z0-9@+\-\[\]\(\)=#$/\\%.]{12,})", text or ""))
    return {"chars": len(text or ""), "rederive_markers": len(REDERIVE.findall(text or "")),
            "repeated_lines": rep, "smiles_candidates": len(cands)}


def cmd_maxtok(a) -> int:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    out = Path(a.out)
    L, R = ledger(out), retries(out)
    hits = [r for r in L if r.get("stop_reason") == "max_tokens"]
    print(f"{len(hits)} max_tokens hit(s) in {len(L)} rows")
    for h in hits:
        m = Chem.MolFromSmiles(h["truth"])
        u = h["usage"]
        th = (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0
        print(f"\n{h['k']} ({h['name']}): {m.GetNumHeavyAtoms() if m else '?'} heavy atoms, "
              f"{m.GetRingInfo().NumRings() if m else '?'} rings, "
              f"{len(Chem.FindMolChiralCenters(m, includeUnassigned=True)) if m else '?'} stereocentres; "
              f"truth {len(h['truth'])} chars")
        print(f"  main: max_tokens {h.get('max_tokens', 16000):,}, output {u['output_tokens']:,} = thinking {th:,} "
              f"+ text ~{u['output_tokens'] - th:,}; reply churn {churn(h['text'])}; "
              f"ends: {h['text'][-80:]!r}")
        for r in [x for x in R if x["k"] == h["k"]]:
            if r["status"] != "ok":
                print(f"  {r['kind']}: FAILED {r['errors'][-1:]}")
                continue
            ru = r["usage"]
            rth = (ru.get("output_tokens_details") or {}).get("thinking_tokens") or 0
            from sonnet_batch import verdict
            print(f"  {r['kind']} (max_tokens {r['max_tokens']:,}, effort {r.get('effort') or 'default'}): "
                  f"stop {r['stop_reason']}, output {ru['output_tokens']:,} = thinking {rth:,} + text "
                  f"~{ru['output_tokens'] - rth:,}, {r['latency_s']} s, ${r['cost_usd']}; verdict "
                  f"{verdict(r.get('smiles'), r['truth'])}; thinking-summary churn {churn(r.get('thinking_summary'))}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--env-file", required=True)
    r.add_argument("--model", default="claude-sonnet-5-5")
    r.add_argument("--n", type=int, default=50)
    r.add_argument("--conc", type=int, default=4)
    r.add_argument("--budget", type=float, default=15.0)
    r.add_argument("--max-tokens", type=int, default=0,
                   help=f"default {DEFAULT_MAX_TOKENS}, or the model's maximum output if lower (Models API)")
    r.add_argument("--prompt-file")
    r.add_argument("--prompt-version", default="v1")
    r.add_argument("--max-consec-fail", type=int, default=5)
    r.add_argument("--publish-every", type=int, default=0)
    r.add_argument("--publish-cmd")
    for name in ("status", "maxtok"):
        s = sp.add_parser(name)
        s.add_argument("--out", required=True)
    a = ap.parse_args()
    sys.exit({"run": cmd_run, "status": cmd_status, "maxtok": cmd_maxtok}[a.cmd](a))
