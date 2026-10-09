#!/usr/bin/env python3
"""Re-screen the classify.jsonl records whose Haiku reply did not parse (truncated at max_tokens 400,
or empty), USPTO and CLEF only (the showable sources), same model and prompt, max_tokens 2000.
Output real/classify_retry.jsonl (resumable); select_real.py lets a parsed retry replace the
unparsed original."""
import base64, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
sys.path.insert(0, "/root/C-MAGE/tools")
sys.path.insert(0, str(Path(__file__).parent))
from api_reader import read_key, cost
from classify_real import PROMPT, MODEL, ROOT, SRC
OUT = ROOT / "real/classify_retry.jsonl"
LOCK = threading.Lock()


def main():
    key = read_key(Path("/root/seb/.env"))
    done = {json.loads(l)["id"] for l in open(OUT)} if OUT.exists() else set()
    todo = [r for r in map(json.loads, open(ROOT / "real/classify.jsonl"))
            if "labels" not in r and r["set"] in ("USPTO", "CLEF") and r["id"] not in done]
    print(f"{len(todo)} to re-screen", flush=True)
    tot = [0.0, 0]

    def one(r):
        png = (SRC / r["file"]).read_bytes()
        body = {"model": MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}},
            {"type": "text", "text": PROMPT}]}]}
        resp = None
        for t in range(6):
            try:
                resp = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key,
                       "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=body, timeout=120)
            except requests.RequestException:
                time.sleep(5); continue
            if resp.status_code in (429, 529, 500, 503):
                time.sleep(float(resp.headers.get("retry-after") or 10)); continue
            break
        rec = {k: r[k] for k in ("id", "set", "file", "truth")}
        rec["http"] = resp.status_code if resp is not None else None
        if resp is not None and resp.ok:
            j = resp.json()
            txt = "".join(b.get("text", "") for b in j["content"] if b["type"] == "text")
            rec["cost"] = cost(j["usage"], MODEL)
            rec["stop_reason"] = j.get("stop_reason")
            try:
                rec["labels"] = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])["labels"]
            except Exception:
                rec["raw"] = txt[:300]
        with LOCK:
            with open(OUT, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            tot[0] += rec.get("cost", 0); tot[1] += 1

    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, todo))
    print(f"DONE {tot[1]} ${tot[0]:.4f}", flush=True)


if __name__ == "__main__":
    main()
