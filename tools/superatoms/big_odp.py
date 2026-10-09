#!/usr/bin/env python3
"""USPTO Open Data Portal source for the big superatom set: post-2016 patent grant "red book" weekly files
(product PTGRDT, Patent Grant Full Text with Embedded TIFF Images). Each weekly I*.tar holds one ZIP per patent;
chemistry patents carry CWU drawings as TIF + the applicant-filed MOL (+ CDX). Truth = that MOL, via
big_index.one() (same gates as the uspto_mol well). Grants from 2017 on postdate MolScribe's training data, so
the set is clean for both arms (src "USPTO-ODP").

    big_odp.py check                exit 0 only when the key answers 200 (the key is read from .env, never printed)
    big_odp.py fetch [--weeks 2]    stream the next unprocessed weeks (newest first, back to 2017), keep every drawing
                                    of class protac / peptide / macrocycle with >= 50 heavy atoms; TIF + MOL saved under
                                    /root/cmage-work/bigsa/odp/, rows appended to odp_pool.jsonl, weeks to odp_weeks.json
The tar is streamed (tarfile 'r|'), never stored; one download at a time (ODP rate limits)."""
import argparse, io, json, sys, tarfile, time, zipfile
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).parent))
import big_index

WORK = Path("/root/cmage-work/bigsa")
ODP = WORK / "odp"
POOL = WORK / "odp_pool.jsonl"
WEEKS = WORK / "odp_weeks.json"
API = "https://api.uspto.gov/api/v1/datasets/products"
KEEP = {"protac", "peptide", "macrocycle"}
FIRST_YEAR = 2017


def key():
    for line in Path("/root/seb/.env").read_text().splitlines():
        if line.startswith("USPTO_API_KEY="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if v:
                return v
    return None


def check():
    k = key()
    if not k:
        print("no USPTO_API_KEY in .env"); return 2
    r = requests.get(f"{API}/search", params={"q": "PTGRDT"}, headers={"X-API-KEY": k}, timeout=60)
    print(f"ODP key check: HTTP {r.status_code}")
    return 0 if r.status_code == 200 else 1


def week_files():
    """All PTGRDT weekly tars from FIRST_YEAR on, newest first; an _r1 re-release replaces its original."""
    k = key()
    out = {}
    for y in range(time.gmtime().tm_year, FIRST_YEAR - 1, -1):
        r = requests.get(f"{API}/PTGRDT", params={"fileDataFromDate": f"{y}-01-01", "fileDataToDate": f"{y}-12-31",
                                                  "includeFiles": "true"}, headers={"X-API-KEY": k}, timeout=120)
        r.raise_for_status()
        for f in r.json()["bulkDataProductBag"][0]["productFileBag"]["fileDataBag"]:
            n = f["fileName"]
            if not n.startswith("I") or not n.endswith(".tar"):
                continue
            wk = n[1:9]
            if wk not in out or "_r" in n:
                out[wk] = f
        time.sleep(1)
    return [out[w] for w in sorted(out, reverse=True)]


def process_week(f):
    k = key()
    kept, n_mol = 0, 0
    with requests.get(f["fileDownloadURI"], headers={"X-API-KEY": k}, stream=True, timeout=600) as r:
        r.raise_for_status()
        r.raw.decode_content = True
        with tarfile.open(fileobj=r.raw, mode="r|") as tf, open(POOL, "a") as fh:
            for m in tf:
                if not m.isfile() or not m.name.upper().endswith(".ZIP"):
                    continue
                data = tf.extractfile(m).read()
                try:
                    z = zipfile.ZipFile(io.BytesIO(data))
                except zipfile.BadZipFile:
                    continue
                names = z.namelist()
                mols = [n for n in names if n.upper().endswith(".MOL")]
                if not mols:
                    continue
                tifs = {n.upper(): n for n in names if n.upper().endswith((".TIF", ".TIFF"))}
                for n in mols:
                    n_mol += 1
                    t = tifs.get(n.upper()[:-4] + ".TIF")
                    if not t:
                        continue
                    row = big_index.one((n, z.read(n).decode("latin-1")))
                    if not row or row["cls"] not in KEEP:
                        continue
                    d = ODP / row["patent"]
                    d.mkdir(parents=True, exist_ok=True)
                    (d / Path(n).name).write_bytes(z.read(n))
                    (d / Path(t).name).write_bytes(z.read(t))
                    row.update({"mol": str(d / Path(n).name), "tif": str(d / Path(t).name), "week": f["fileName"]})
                    fh.write(json.dumps(row) + "\n")
                    kept += 1
    return kept, n_mol


def fetch(weeks):
    done = json.load(open(WEEKS)) if WEEKS.exists() else {}
    todo = [f for f in week_files() if f["fileName"] not in done][:weeks]
    tot = 0
    for f in todo:
        t0 = time.time()
        kept, n_mol = process_week(f)
        done[f["fileName"]] = {"kept": kept, "mol": n_mol, "bytes": f.get("fileSize"),
                               "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "s": round(time.time() - t0)}
        WEEKS.write_text(json.dumps(done, indent=1))
        print(f"{f['fileName']}: {n_mol} MOL drawings, kept {kept} ({time.time() - t0:.0f} s)", flush=True)
        tot += kept
    return tot


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("check")
    f = sp.add_parser("fetch")
    f.add_argument("--weeks", type=int, default=2)
    a = ap.parse_args()
    if a.cmd == "check":
        return check()
    WORK.mkdir(parents=True, exist_ok=True)
    print("kept", fetch(a.weeks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
