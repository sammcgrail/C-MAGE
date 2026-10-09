#!/usr/bin/env python3
"""Scan USPTO ODP grant weeks (big_odp's stream) for SMALL CWU drawings whose MOL marks an open valence:
a ChemDraw wavy attachment line (wavy_glyph: stereo-4 bonds to degree-1 end points; the older pseudo-atom
scan, interesting_old, found R-group Markush drawings instead). Saves TIF + MOL + a summary row
to /root/cmage-work/wavy/scan.jsonl for manual / screened selection of wavy-bond attachment-point fragments.
    wavy_scan.py WEEK_TAR_NAME [...]"""
import io, json, re, sys, tarfile, zipfile
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).parent))
import big_odp
OUT = Path("/root/cmage-work/wavy")
SCAN = "scan2.jsonl"
MAX_ATOMS = 40


def atoms_of(txt):
    lines = txt.splitlines()
    if len(lines) < 4 or "V3000" in lines[3]:
        return None
    try:
        na = int(lines[3][0:3])
    except ValueError:
        return None
    return [l[31:34].strip() for l in lines[4:4 + na]]


def wavy_glyph(txt):
    """ChemDraw exports a wavy attachment line as bonds with stereo flag 4 ('either') from the crossing atom to
    the line's end points, which are degree-1 carbons. -> list of (crossing atom, [glyph end atoms]) or []."""
    lines = txt.splitlines()
    na, nb = int(lines[3][0:3]), int(lines[3][3:6])
    bonds = []
    for l in lines[4 + na:4 + na + nb]:
        bonds.append((int(l[0:3]), int(l[3:6]), int(l[6:9]), int(l[9:12] or 0)))
    deg = {}
    for a, b, _, _ in bonds:
        deg[a] = deg.get(a, 0) + 1; deg[b] = deg.get(b, 0) + 1
    by = {}
    for a, b, o, st in bonds:
        if st == 4 and o == 1:
            for x, y in ((a, b), (b, a)):
                if deg[y] == 1 and deg[x] >= 2:
                    by.setdefault(x, []).append(y)
    return [(x, ys) for x, ys in by.items() if len(ys) >= 2]


def interesting(txt):
    at = atoms_of(txt)
    if not at or len(at) > MAX_ATOMS:
        return None
    try:
        g = wavy_glyph(txt)
    except ValueError:
        g = []
    if g:
        return {"n_atoms": len(at), "wavy": g, "pseudo": [a for a in at if not a.isalpha() or a in ("R", "A", "Q", "X") or re.fullmatch(r"R\d+", a)],
                "alias": re.findall(r"^A  +\d+\r?\n(.*?)\r?$", txt, re.M), "apo": "M  APO" in txt, "rgp": "M  RGP" in txt,
                "sgroup": re.findall(r"^M  STY.*$", txt, re.M)}
    return None


def interesting_old(txt):
    at = atoms_of(txt)
    if not at or len(at) > MAX_ATOMS:
        return None
    pseudo = [a for a in at if a in ("*", "R", "R#", "A", "Q", "X", "Xx", "L", "Lp") or re.fullmatch(r"R\d*", a)]
    alias = re.findall(r"^A  +(\d+)\n(.*)$", txt, re.M)
    apo = "M  APO" in txt
    rgp = "M  RGP" in txt
    if not (pseudo or alias or apo or rgp):
        return None
    return {"n_atoms": len(at), "pseudo": pseudo, "alias": [a[1] for a in alias], "apo": apo, "rgp": rgp}


def scan(week):
    k = big_odp.key()
    f = next(f for f in big_odp.week_files() if f["fileName"] == week)
    n = 0
    with requests.get(f["fileDownloadURI"], headers={"X-API-KEY": k}, stream=True, timeout=600) as r:
        r.raise_for_status()
        with tarfile.open(fileobj=r.raw, mode="r|") as tf, open(OUT / SCAN, "a") as fh:
            for m in tf:
                if not m.isfile() or not m.name.upper().endswith(".ZIP"):
                    continue
                try:
                    z = zipfile.ZipFile(io.BytesIO(tf.extractfile(m).read()))
                except zipfile.BadZipFile:
                    continue
                names = z.namelist()
                tifs = {x.upper(): x for x in names if x.upper().endswith(".TIF")}
                for x in names:
                    if not x.upper().endswith(".MOL"):
                        continue
                    t = tifs.get(x.upper()[:-4] + ".TIF")
                    if not t:
                        continue
                    txt = z.read(x).decode("latin-1")
                    info = interesting(txt)
                    if not info:
                        continue
                    d = OUT / "files" / Path(x).parent.name
                    d.mkdir(parents=True, exist_ok=True)
                    (d / Path(x).name).write_text(txt, encoding="latin-1")
                    (d / Path(t).name).write_bytes(z.read(t))
                    fh.write(json.dumps({"week": week, "id": Path(x).stem, "mol": str(d / Path(x).name),
                                         "tif": str(d / Path(t).name), **info}) + "\n")
                    n += 1
    print(week, n, "candidates", flush=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for w in sys.argv[1:]:
        scan(w)
