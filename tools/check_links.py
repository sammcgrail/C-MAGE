#!/usr/bin/env python3
"""Check every relative markdown link against `git ls-files`.

WHY GIT AND NOT THE FILESYSTEM. An earlier check here tested `os.path.exists`,
so `benchmarks/`, `docs/DOCKER.md` and `Dockerfile.allinone` all reported "ok"
while being UNTRACKED -- they existed on the machine that wrote the README and
would not exist in anyone's clone. A link checker that consults the working tree
answers a question nobody asked. Ask git.

Also resolves each link relative to the FILE IT APPEARS IN, not the repo root,
which is the other easy way to get a wrong answer in both directions.

    tools/check_links.py [--all]     # --all includes vendored subprojects

Exit status is the number of broken links, capped at 1, so it drops into CI.
"""
import argparse
import os
import re
import subprocess
import sys

VENDORED = ("cxmolscribe-wd/MolScribe/", "cxmolscribe-wd/DECIMER-Image-Segmentation/",
            "MERMaid/")


def strip_code(text):
    """Blank out fenced and inline code before looking for links.

    Not optional: SMILES are full of `](`. This checker reported
    `CNC[C@H](O)c1ccc(O)c(O)c1` inside a fenced block as a broken link to a file
    named "O". A checker that cries wolf gets ignored, which costs more than the
    bug it was written to catch.
    """
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"^(?: {4}|\t).*$", "", text, flags=re.M)   # indented code
    return re.sub(r"`[^`\n]*`", "", text)


def git_files():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return set(filter(None, out.stdout.split("\n")))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true",
                    help="also check vendored subprojects (their broken links are upstream's)")
    args = ap.parse_args()

    tracked = git_files()
    docs = [f for f in tracked if f.endswith(".md")]
    if not args.all:
        docs = [d for d in docs if not d.startswith(VENDORED)]

    broken = checked = skipped = 0
    for doc in docs:
        with open(doc) as fh:
            text = strip_code(fh.read())
        for link in re.findall(r"\]\(([^)]+)\)", text):
            link = link.split("#")[0].strip()
            if not link or link.startswith(("http://", "https://", "mailto:")):
                continue
            # A target that names no path is not a link. Unfenced SMILES produce
            # `](` by the dozen -- `[H](...)`, `[C@@H](O)`, `[*](Cl)` -- and every
            # one of them was reported BROKEN. Twelve permanent false positives is
            # a checker nobody reads, which is worse than no checker: the one real
            # break would arrive in a list that is always red. A path has a
            # separator or a file extension; require one.
            if "/" not in link and not os.path.splitext(link)[1]:
                skipped += 1
                continue
            checked += 1
            target = os.path.normpath(os.path.join(os.path.dirname(doc), link))
            # A directory link is satisfied by anything tracked beneath it.
            ok = target in tracked or any(t.startswith(target.rstrip("/") + "/") for t in tracked)
            if not ok:
                print(f"  BROKEN  {doc} -> {link}  (resolves to {target})")
                broken += 1

    print(f"checked {checked} relative links across {len(docs)} markdown files, "
          f"{broken} broken ({skipped} targets skipped as not-a-path, mostly SMILES)")
    # A checker that silently matched nothing would print "0 broken" and exit 0,
    # which is indistinguishable from success. It is not.
    if checked == 0:
        print("ERROR: found no relative links at all — the checker is not working", file=sys.stderr)
        return 1
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
