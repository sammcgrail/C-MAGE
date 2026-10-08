#!/usr/bin/env python3
"""Find REAL drawings with text superatoms: Haiku 5.5 lists multi-atom text labels per image
(one cheap API call each, credits key). Output real/classify.jsonl (resumable). Screening only:
the labels are later cross-checked against the ground-truth SMILES before an image is used."""
import base64, csv, json, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
sys.path.insert(0, "/root/C-MAGE/tools")
from api_reader import read_key, cost
ROOT = Path("/root/cmage-work/superatoms")
SRC = ROOT / "dl/molscribe_real"
OUT = ROOT / "real/classify.jsonl"
MODEL = "claude-haiku-5-5"
PROMPT = ("This image is a chemical structure drawing. List every TEXT LABEL in it that abbreviates a group of "
          "two or more non-hydrogen atoms (for example OMe, MeO, Et, Ph, Bn, Boc, Cbz, Fmoc, Ac, OAc, AcO, CF3, F3C, "
          "CN, NC, NO2, O2N, CO2H, HO2C, COOH, CO2Et, CO2Me, MeO2C, tBu, t-Bu, iPr, TMS, TBS, OTBS, TBDPS, Ts, OTs, Ms, "
          "Tf, SO2Me, NMe2, OCF3, NHBoc, BocHN). Do NOT list single-atom labels such as N, O, S, Cl, Br, F, OH, NH, NH2, "
          "SH, Me, CH3 or H. Copy each label as written, once per occurrence. Answer with ONLY a JSON object: "
          '{"labels": [...]} (an empty list if there are none).')
LOCK = threading.Lock()

def main(sets):
    key = read_key(Path("/root/seb/.env"))
    done = {json.loads(l)["id"] for l in open(OUT)} if OUT.exists() else set()
    rows = []
    for s in sets:
        for r in csv.DictReader(open(SRC / f"real/{s}.csv")):
            rid = f"{s}/{r['image_id']}"
            if rid not in done:
                rows.append((rid, s, r))
    print(f"{len(rows)} to classify", flush=True)
    tot = [0.0, 0]
    def one(item):
        rid, s, r = item
        png = (SRC / r["file_path"]).read_bytes()
        body = {"model": MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()}},
            {"type": "text", "text": PROMPT}]}]}
        for t in range(6):
            try:
                resp = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key,
                       "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=body, timeout=120)
            except requests.RequestException:
                time.sleep(5); continue
            if resp.status_code in (429, 529, 500, 503):
                time.sleep(float(resp.headers.get("retry-after") or 10)); continue
            break
        rec = {"id": rid, "set": s, "file": r["file_path"], "truth": r["SMILES"], "http": resp.status_code}
        if resp.ok:
            j = resp.json()
            txt = "".join(b.get("text", "") for b in j["content"] if b["type"] == "text")
            rec["cost"] = cost(j["usage"], MODEL)
            try:
                rec["labels"] = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])["labels"]
            except Exception:
                rec["raw"] = txt[:300]
        with LOCK:
            with open(OUT, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            tot[0] += rec.get("cost", 0); tot[1] += 1
            if tot[1] % 200 == 0:
                print(f"{tot[1]} done ${tot[0]:.3f}", flush=True)
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, rows))
    print(f"DONE {tot[1]} ${tot[0]:.4f}", flush=True)

if __name__ == "__main__":
    main(sys.argv[1:])
