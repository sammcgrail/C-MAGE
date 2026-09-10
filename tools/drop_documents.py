"""Remove documents from the corpus, every manifest, the scored rows and the tiles.

Five places have to agree or the site reports a corpus it no longer has:
corpus/*.pdf, corpus/SHA256SUMS, every ground_truth/pdf_manifest*.json that names
the group, benchmarks/scored/pdfs_all/structures.csv, and benchmarks/wall/pdf*/.
Doing it by hand once is fine; doing it twice is how one of them gets missed.

    drop_documents.py <stem> [<stem> ...]
"""
import csv
import glob
import json
import os
import subprocess
import sys

ROOT = "/root/C-MAGE/benchmarks"


def main(stems: list[str]) -> int:
    drop = set(stems)
    gone = 0
    for g in drop:
        p = f"{ROOT}/corpus/{g}.pdf"
        if os.path.exists(p):
            os.remove(p)
            gone += 1
    print(f"corpus: -{gone} PDFs, {len(glob.glob(ROOT + '/corpus/*.pdf'))} remain")

    for f in sorted(glob.glob(ROOT + "/ground_truth/pdf_manifest*.json")):
        d = json.load(open(f))
        if not isinstance(d, dict) or "groups" not in d:
            continue
        hit = [g for g in d["groups"] if g in drop]
        if not hit:
            continue
        for g in hit:
            del d["groups"][g]
        json.dump(d, open(f, "w"), indent=1)
        print(f"  {os.path.basename(f)}: -{len(hit)}, {len(d['groups'])} left")

    sc = f"{ROOT}/scored/pdfs_all/structures.csv"
    if os.path.exists(sc):
        rows = [r for r in csv.DictReader(open(sc)) if r["group"] not in drop]
        with open(sc, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"scored rows: {len(rows)} remain")

    n = 0
    for g in drop:
        for p in glob.glob(f"{ROOT}/wall/pdf*/Image_DIS_VH_File_{g}_*.png"):
            os.remove(p)
            n += 1
    print(f"tiles: -{n}")

    subprocess.run("cd %s/corpus && sha256sum *.pdf > SHA256SUMS" % ROOT, shell=True, check=True)
    # A stem that matched nothing anywhere is a typo, not a no-op.
    left = {os.path.basename(p)[:-4] for p in glob.glob(ROOT + "/corpus/*.pdf")}
    still = drop & left
    assert not still, f"still present after removal: {sorted(still)}"
    print(f"SHA256SUMS rewritten: {len(left)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
