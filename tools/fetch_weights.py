#!/usr/bin/env python3
"""Fetch the DECIMER segmentation weights, so a run never depends on Zenodo
being up at the moment you happen to need it.

WHY THIS EXISTS
---------------
`decimer_segmentation.load_model()` downloads ~260 MB from a single Zenodo URL,
at import time, with no retry and (before patches/0002) no validation. On
2026-09-08 Zenodo returned 503 for hours and the whole pipeline was unusable:
there is no official mirror, upstream still points at the same URL, and the
weights are not on HuggingFace or PyPI.

A single hard-coded URL to a third party is the reproducibility hole. This tool
closes it four ways, in the order you actually want them tried:

  1. A local file you already have          DECIMER_WEIGHTS=/path/to.h5
  2. Any mirrors you control                DECIMER_WEIGHTS_MIRRORS=url1,url2
  3. Zenodo, with backoff                   (503 is transient by definition)
  4. A clear failure that tells you how to place the file by hand

and it validates before it commits anything to the cache, so an outage can
never poison the cache the way it did on the 8th.

USAGE
    tools/fetch_weights.py                 # fetch to the default cache
    tools/fetch_weights.py --wait 3600     # keep retrying for an hour
    tools/fetch_weights.py --check         # is a valid file already cached?
    DECIMER_WEIGHTS=/mnt/w.h5 tools/fetch_weights.py   # adopt a local copy

The Docker image calls this at BUILD time, so the container never reaches for
Zenodo at run time at all.
"""
import argparse
import hashlib
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

ZENODO_URL = "https://zenodo.org/record/10663579/files/mask_rcnn_molecule.h5?download=1"
CACHE_PATH = os.path.join(os.path.expanduser("~"), ".cache", "decimer", "mask_rcnn_molecule.h5")
HDF5_MAGIC = b"\x89HDF\r\n\x1a\n"
MIN_BYTES = 8 * 1024 * 1024          # real file ~260 MB; an error page is bytes
# Recorded from a known-good fetch on 2026-09-08 once Zenodo recovered. Pinning
# it turns "we got 260 MB of something" into "we got THE file", which is the
# difference that matters when the source is a third party that has already
# served us an error page once. Set DECIMER_ALLOW_UNPINNED=1 to accept a
# different checksum (e.g. if upstream legitimately republishes).
EXPECTED_SHA256 = "329120facb69e88add819a3216db0fbfef57e9a37d6b6db0f6149819a11d46a5"
EXPECTED_BYTES = 272650600
UA = "C-MAGE/fetch_weights (+https://github.com/AlexTaylor54/C-MAGE)"


def log(msg):
    print(f"[fetch_weights] {msg}", flush=True)


def validate(path):
    """Is this actually the model? Returns (ok, why_not).

    Checked in this order because it is also the order of increasing cost, and
    because each one catches a failure the next would misreport: an HTML error
    page has the wrong magic, a truncated download has the right magic and the
    wrong size.
    """
    if not os.path.exists(path):
        return False, "missing"
    size = os.path.getsize(path)
    if size < MIN_BYTES:
        return False, f"only {size} bytes (expected ~260 MB) — probably an error page"
    with open(path, "rb") as fh:
        if fh.read(8) != HDF5_MAGIC:
            return False, "not an HDF5 file (bad magic)"
    # Checksum last: it is the only check that costs a full read of 260 MB, and
    # it is the only one that can tell the right file from a plausible wrong one.
    if EXPECTED_SHA256 and not os.environ.get("DECIMER_ALLOW_UNPINNED"):
        got = sha256(path)
        if got != EXPECTED_SHA256:
            return False, (f"sha256 {got[:16]}... does not match the pinned "
                           f"{EXPECTED_SHA256[:16]}... (set DECIMER_ALLOW_UNPINNED=1 to accept)")
    return True, f"{size} bytes"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def try_url(url, dest):
    """Download to dest.part, validate, then rename. Never leaves a partial or
    invalid file where a later run would trust it."""
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            ctype = resp.headers.get("Content-Type", "")
            if "html" in ctype.lower():
                return False, f"server sent HTML (Content-Type: {ctype}) — service is down or rate-limiting"
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            with open(tmp, "wb") as fh:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
                    if total:
                        pct = 100 * got // total
                        if pct % 10 == 0:
                            print(f"\r[fetch_weights] {pct:3d}%  {got >> 20} MB", end="", flush=True)
            print()
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:                                   # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"

    ok, why = validate(tmp)
    if not ok:
        os.remove(tmp)
        return False, f"rejected: {why}"
    os.replace(tmp, dest)
    return True, why


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default=os.environ.get("DECIMER_CACHE", CACHE_PATH))
    ap.add_argument("--wait", type=int, default=0,
                    help="seconds to keep retrying while the server is down (0 = one attempt)")
    ap.add_argument("--check", action="store_true", help="report cache status and exit")
    args = ap.parse_args()

    dest = args.dest
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    ok, why = validate(dest)
    if args.check:
        log(f"{'OK  ' if ok else 'MISSING/INVALID'}  {dest}  ({why})")
        if ok:
            log(f"sha256 {sha256(dest)}")
        return 0 if ok else 1
    if ok:
        log(f"already cached and valid: {dest} ({why})")
        return 0

    # 1. A local copy the operator already has. This is the escape hatch that
    #    makes the pipeline reproducible on an air-gapped or offline box.
    local = os.environ.get("DECIMER_WEIGHTS")
    if local:
        lok, lwhy = validate(local)
        if not lok:
            log(f"DECIMER_WEIGHTS={local} is not usable ({lwhy})")
            return 2
        log(f"adopting local weights from {local} ({lwhy})")
        shutil.copyfile(local, dest + ".part")
        os.replace(dest + ".part", dest)
        log(f"sha256 {sha256(dest)}")
        return 0

    # 2. Operator-controlled mirrors, 3. Zenodo last — it is the one that fails.
    mirrors = [u for u in os.environ.get("DECIMER_WEIGHTS_MIRRORS", "").split(",") if u.strip()]
    urls = mirrors + [ZENODO_URL]

    deadline = time.time() + args.wait
    delay = 15
    attempt = 0
    while True:
        attempt += 1
        for url in urls:
            log(f"attempt {attempt}: {url.split('?')[0]}")
            good, why = try_url(url, dest)
            if good:
                log(f"OK — cached {dest} ({why})")
                log(f"sha256 {sha256(dest)}")
                return 0
            log(f"  failed: {why}")
        if time.time() >= deadline:
            break
        # 503 is transient by definition, so back off rather than hammer.
        nap = min(delay, max(1, int(deadline - time.time())))
        log(f"retrying in {nap}s (until {time.strftime('%H:%M:%S', time.localtime(deadline))})")
        time.sleep(nap)
        delay = min(delay * 2, 300)

    log("")
    log("Could not obtain the weights. This is not fatal to the rest of C-MAGE —")
    log("stages 1 and 3 do not need them. To finish stage 2 without this server:")
    log(f"  1. get mask_rcnn_molecule.h5 (~260 MB) from {ZENODO_URL.split('?')[0]}")
    log(f"  2. DECIMER_WEIGHTS=/path/to/mask_rcnn_molecule.h5 {sys.argv[0]}")
    log("  or place it directly at:")
    log(f"     {dest}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
