#!/usr/bin/env python3
"""The big-molecule superatom set ("Real, big (>= 50 atoms)"): a resumable, mechanical pipeline. No LLM agent and
no subscription use; the only model calls are the Sonnet 5.5 API reads (API credits).

    big_expand.py status
    big_expand.py odp-check             exit 0 only when the USPTO ODP key answers 200 (big_odp.py check)
    big_expand.py step [--n 250] [--source auto|test|odp|train] [--no-publish] [--no-signal]
    big_expand.py tick                  the timer's entry point: one step per new 5 h block, if the gates allow
    big_expand.py publish               rebuild + purge + commit + push only

Sources (truth always from the source's own MOL data, never a model's reading):
  test   MolScribe real.zip USPTO test images with >= 50 heavy atoms not yet in any superatom set (held out from
         MolScribe training, so fair to both arms). The first 100 (rb_0001..rb_0100) come from here.
  odp    USPTO Open Data Portal grant red book, 2017 on (big_odp.py): CWU TIF + the applicant's MOL. Postdates
         MolScribe's training data, so clean for both arms (src "USPTO-ODP"). PROTACs first (Sam: ~3000), then
         peptides, then macrocycles. Used whenever odp-check passes; big_odp.py fetch streams more weeks as needed.
  train  MolScribe uspto_mol.zip: USPTO grant TIFs with the patent's own MOL file (indexed by big_index.py into
         pool.jsonl). Weighted to PROTACs, then peptides, then other big molecules. src "USPTO-train": this is
         MolScribe's TRAINING data, so CXMolScribe has very likely seen these images; its numbers there are flagged
         and must never be pooled into its headline.
Dedupe: InChIKey against the corpus, every superatom set and the big set; at most PER_PATENT drawings per patent.

A step: pick N -> pixels-only PNGs (assert no text chunks, RDKit cannot read a molecule back) -> append
big/set.json + run_set.json -> CXMolScribe stage 3 (nice 15) on rows without a prediction, merged into the
cxmolscribe/ pair -> Sonnet 5.5 API (api_reader_set.py, prompt v2, 64k, streamed) on rows without a reading,
under the spend guard -> publish (build_superatoms.py, build_llmocr.py, CF purge, commit --only, push) ->
2-line Signal to Sam.
Caps: the big set's API spend <= BIG_CAP ($140, Sam; at the cap -> big/STOP, timer disabled); this month's API
spend (every published_runs ledger, backfill.month_api_spend's rule) + this step's estimate <= MONTH_CAP (read from
backfill.py's API_MONTH_CAP, $195): when that trips the API part is skipped, rows wait, and the timer carries on
(the guard reopens at the monthly reset). The timer is disabled automatically once TARGET_PROTAC PROTAC rows have an
API reading.
tick gates: a NEW 5 h block (resets_at differs from the last one recorded), 5 h < 98%, week < 98% (Sam)."""
import argparse, collections, csv, datetime as dt, fcntl, glob, json, os, random, re, subprocess, sys, time
from pathlib import Path

REPO = Path("/root/C-MAGE")
TOOLS = REPO / "tools"
PY = str(REPO / ".venv-ms/bin/python")
SA = REPO / "benchmarks/published_runs/sonnet55_api_superatoms"
RUN = SA / "big"
CXP = SA / "cxmolscribe"
WORK = Path("/root/cmage-work/bigsa")
IMG = WORK / "images"
POOL = WORK / "pool.jsonl"
STATE = WORK / "state.json"
LOG = WORK / "big.log"
LOCK = WORK / "big.lock"
ZIP = WORK / "dl/uspto_mol.zip"
TEST_CSV = Path("/root/cmage-work/superatoms/dl/molscribe_real/real/USPTO.csv")
TEST_DIR = Path("/root/cmage-work/superatoms/dl/molscribe_real")
ENV = Path("/root/seb/.env")
USAGE = ["/root/seb/skills/ccusage/scripts/usage", "server", "--json"]
SEND = "/root/seb/scripts/send-signal"
TIMER = "cmage-bigsa.timer"
SITE = "https://cmage.sebland.com"
MIN_HEAVY = 50
N_TEST = 100
PER_PATENT = 30               # the first 100 (test): 115 eligible, 44 from one patent; 30 leaves 101
PER_PATENT_TRAIN = 20         # the training-set well: one patent can hold thousands of drawings
PER_PATENT_ODP = 40           # a PROTAC patent holds hundreds of PROTACs
ODP_POOL = WORK / "odp_pool.jsonl"
MAX_WEEKS_PER_STEP = 16       # ODP weeks streamed per step at most (~4 GB, ~2.5 min each); ~25 capped PROTACs a week
TARGET_PROTAC = 3000          # Sam: ~3000 PROTACs (ODP)
BIG_CAP = 140.0               # Sam 2026-10-09 (was 70, then 100)


def _month_cap():
    """backfill.py's API_MONTH_CAP (one constant for every C-MAGE API runner); 195 if it cannot be read."""
    try:
        t = Path("/root/seb/skills/cmage/scripts/backfill.py").read_text()
        return float(re.search(r"^API_MONTH_CAP\s*=\s*([\d.]+)", t, re.M).group(1))
    except Exception:
        return 195.0


MONTH_CAP = _month_cap()
EST_PER_IMAGE = 0.06          # deliberately high for these sizes (measured ~$0.02-0.03 at 50-100 heavy atoms)
CAP_5H, CAP_7D = 98.0, 98.0
SEED = 20261009
ORDER = [("odp", "protac"), ("odp", "peptide"), ("odp", "macrocycle"),
         ("train", "protac"), ("train", "peptide"), ("train", "macrocycle"), ("train", "other")]
COMMIT = ["benchmarks/published_runs/sonnet55_api_superatoms/big",
          "benchmarks/published_runs/sonnet55_api_superatoms/cxmolscribe",
          "benchmarks/wall/llmocr.json", "benchmarks/wall/llmocr_detail.json", "benchmarks/wall/llmocr_pred",
          "benchmarks/wall/superatoms.json", "benchmarks/wall/superatoms", "benchmarks/wall/superatoms_pred",
          "benchmarks/wall/superatoms_txt", "benchmarks/wall/superatoms_ocr"]
PURGE = ["wall/llmocr.json", "wall/llmocr_detail.json", "wall/superatoms.json", "wall/gallery.json"]
TRACKED_ONLY = ["benchmarks/wall/gallery.json"]   # committed only once its owner (agent "gallery") tracks it


def now():
    return dt.datetime.now(dt.timezone.utc)


def log(msg):
    WORK.mkdir(parents=True, exist_ok=True)
    line = f"{now().strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in open(p) if l.strip()] if p.exists() else []


def load_state():
    return json.load(open(STATE)) if STATE.exists() else {"last_block": None, "steps": [], "halted": None}


def save_state(s):
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s, indent=1))
    os.replace(tmp, STATE)


def admin_number():
    for line in ENV.read_text().splitlines():
        if line.startswith("ADMIN_SIGNAL_NUMBER="):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if v:
                return v
    raise SystemExit("ADMIN_SIGNAL_NUMBER not in /root/seb/.env")


def signal(text, on=True):
    log("signal: " + text.replace("\n", " | "))
    if not on:
        return
    p = WORK / "signal_msg.txt"
    p.write_text(text)
    r = subprocess.run([SEND, admin_number(), "--from-file", str(p)], capture_output=True, text=True, timeout=120)
    log(f"signal rc={r.returncode}")


def disable_timer(why):
    subprocess.run(["systemctl", "--user", "disable", "--now", TIMER], capture_output=True,
                   env={**os.environ, "XDG_RUNTIME_DIR": "/run/user/0"})
    log(f"timer disabled: {why}")


# ------------------------------------------------------------------------------------------------ money
def run_spend(d):
    return sum((r.get("cost_usd") or 0) for p in ("ledger.jsonl", "retries.jsonl") for r in jl(Path(d) / p))


def month_api_spend():
    """backfill.month_api_spend's rule: every ledger/retries row under benchmarks/published_runs this month."""
    month = now().strftime("%Y-%m")
    t = 0.0
    for p in glob.glob(str(REPO / "benchmarks/published_runs/**/*.jsonl"), recursive=True):
        if not re.search(r"/(ledger|retries)\.jsonl$", p):
            continue
        for r in jl(p):
            ts = str(r.get("started") or r.get("ended") or r.get("at") or "")
            if not ts or ts.startswith(month):
                t += r.get("cost_usd") or 0
    return t


# ------------------------------------------------------------------------------------------------ the set
def set_rows():
    return json.load(open(RUN / "set.json")) if (RUN / "set.json").exists() else []


def api_have():
    return {r["k"] for r in jl(RUN / "ledger.jsonl") if r.get("status") == "ok"}


def cx_have():
    sys.path.insert(0, str(TOOLS))
    import pandas as pd
    out = set()
    for f in ("High", "Low"):
        p = CXP / f"Completed_{f}Confidence_CMAGE.xlsx"
        if p.exists():
            out |= {Path(x).stem for x in pd.read_excel(p, usecols=["File Path"])["File Path"]}
    return out


def known_keys():
    """InChIKeys of every truth already used anywhere: corpus, superatom synth/real, the big set."""
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    cache = WORK / "known_ik.json"
    c = json.load(open(cache)) if cache.exists() else {}
    smis = [r["truth_smiles"] for r in csv.DictReader(open(REPO / "corpus_images/manifest.csv"))]
    for d in ("synth", "real", "big"):
        if (SA / d / "set.json").exists():
            smis += [x["truth"] for x in json.load(open(SA / d / "set.json"))]
    out = set()
    for s in smis:
        if s not in c:
            m = Chem.MolFromSmiles(s)
            c[s] = Chem.MolToInchiKey(m) if m is not None else None
        if c[s]:
            out.add(c[s])
    cache.write_text(json.dumps(c))
    return out


def clean_png(src_img, dst):
    """Pixels only: re-encode, then assert no text chunks, no PIL info but dpi/gamma, no RDKit molecule."""
    from PIL import Image
    from rdkit import Chem
    im = Image.open(src_img)
    im.load()
    im.convert("RGB").save(dst)
    b = Path(dst).read_bytes()
    assert not any(t in b for t in (b"zTXt", b"tEXt", b"iTXt")), dst
    im2 = Image.open(dst); im2.load()
    assert not (set(im2.info) - {"dpi", "gamma"}), (dst, im2.info)
    assert Chem.MolFromPNGFile(str(dst)) is None, dst


def candidates_test(known, used_files):
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    sys.path.insert(0, str(Path(__file__).parent))
    big_index = __import__("big_index")
    real_used = {x["orig_file"] for x in json.load(open(SA / "real/set.json"))}
    out = []
    for r in csv.DictReader(open(TEST_CSV)):
        s = r["SMILES"]
        if "*" in s or r["file_path"] in real_used or r["file_path"] in used_files:
            continue
        m = Chem.MolFromSmiles(s)
        if m is None or m.GetNumHeavyAtoms() < MIN_HEAVY or m.HasSubstructMatch(big_index.OOO):
            continue
        fr = sorted((f.GetNumHeavyAtoms() for f in Chem.GetMolFrags(m, asMols=True)), reverse=True)
        if fr[0] < MIN_HEAVY or (len(fr) > 1 and fr[1] > 12):      # big_index.py's rule: one compound per drawing
            continue
        ik = Chem.MolToInchiKey(m)
        if ik in known:
            continue
        cls, n = big_index.classify(m)
        out.append({"src": "USPTO", "orig_id": r["image_id"], "orig_file": r["file_path"],
                    "patent": r["image_id"].rsplit("-", 1)[0], "truth": s, "heavy": m.GetNumHeavyAtoms(),
                    "inchikey": ik, "cls": cls, "n_res": n})
    return out


def candidates_train(known, used_files):
    if not POOL.exists():
        raise SystemExit(f"{POOL} missing: run big_index.py first")
    out = []
    for r in jl(POOL):
        if r["inchikey"] in known or r["mol"] in used_files:
            continue
        out.append({"src": "USPTO-train", "pool": "train", "orig_id": r["id"], "orig_file": r["tif"], "orig_mol": r["mol"],
                    "patent": r["patent"], "truth": r["smiles"], "heavy": r["heavy"], "inchikey": r["inchikey"],
                    "cls": r["cls"], "n_res": r["n_res"]})
    return out


def candidates_odp(known, used_files):
    out = []
    for r in jl(ODP_POOL):
        if r["inchikey"] in known or r["tif"] in used_files:
            continue
        out.append({"src": "USPTO-ODP", "pool": "odp", "orig_id": r["id"], "orig_file": r["tif"],
                    "orig_mol": r["mol"], "patent": r["patent"], "truth": r["smiles"], "heavy": r["heavy"],
                    "inchikey": r["inchikey"], "cls": r["cls"], "n_res": r["n_res"], "week": r.get("week")})
    return out


def odp_ok():
    r = subprocess.run([PY, str(Path(__file__).parent / "big_odp.py"), "check"], capture_output=True, text=True)
    return r.returncode == 0


def pick(cands, n, per_patent_now):
    """(pool, class) in ORDER; within one a seeded shuffle; at most PER_PATENT_ODP / PER_PATENT_TRAIN per patent
    overall; one per InChIKey."""
    rng = random.Random(SEED)
    by = collections.defaultdict(list)
    for c in sorted(cands, key=lambda c: c["orig_file"]):
        by[(c["pool"], c["cls"])].append(c)
    out, seen, pp = [], set(), collections.Counter(per_patent_now)
    for key in ORDER:
        lst = by.get(key, [])
        rng.shuffle(lst)
        cap = PER_PATENT_ODP if key[0] == "odp" else PER_PATENT_TRAIN
        for c in lst:
            if len(out) >= n:
                return out
            if c["inchikey"] in seen or pp[c["patent"]] >= cap:
                continue
            seen.add(c["inchikey"]); pp[c["patent"]] += 1
            out.append(c)
    return out


def add_rows(n, source):
    rows = set_rows()
    used = {x["orig_file"] for x in rows} | {x.get("orig_mol") for x in rows if x.get("orig_mol")}
    n_test = sum(1 for x in rows if x["src"] == "USPTO")
    if source == "auto":
        source = "test" if n_test < N_TEST else ("odp" if odp_ok() else "train")
    if source == "test":
        n = min(n, N_TEST - n_test) if n_test < N_TEST else n
    known = known_keys()
    if source == "odp":     # stream more ODP weeks until enough unused PROTACs (or the week budget) are on disk
        for _ in range(MAX_WEEKS_PER_STEP):
            have = [c for c in candidates_odp(known, used) if c["cls"] == "protac"]
            if len(have) >= n:
                break
            r = subprocess.run([PY, str(Path(__file__).parent / "big_odp.py"), "fetch", "--weeks", "1"],
                               capture_output=True, text=True)
            log("odp fetch: " + (r.stdout.strip().splitlines() or ["(no output)"])[0][:200])
            if r.returncode != 0:
                log(f"odp fetch failed: {r.stderr[-300:]}")
                break
        cands = candidates_odp(known, used) + candidates_train(known, used)
    elif source == "test":
        cands = candidates_test(known, used)
    else:
        cands = candidates_train(known, used)
    pp = collections.Counter(x["patent"] for x in rows)
    if source == "test":     # the first 100: a spread of sizes, every drawing >= 60 kept, the rest sampled
        rng = random.Random(SEED)
        big = [c for c in cands if c["heavy"] >= 60]
        small = [c for c in cands if c["heavy"] < 60]
        rng.shuffle(small)
        cands_sorted = big + small
        chosen, seen = [], set()
        for c in cands_sorted:
            if len(chosen) >= n:
                break
            if c["inchikey"] in seen or pp[c["patent"]] >= PER_PATENT:
                continue
            seen.add(c["inchikey"]); pp[c["patent"]] += 1
            chosen.append(c)
    else:
        chosen = pick(cands, n, pp)
    random.Random(f"{SEED}-{len(rows)}").shuffle(chosen)
    IMG.mkdir(parents=True, exist_ok=True)
    RUN.mkdir(parents=True, exist_ok=True)
    k0 = max([int(x["id"][3:]) for x in rows] + [0])
    zf = None
    new = []
    for i, c in enumerate(chosen, k0 + 1):
        rid = f"rb_{i:04d}"
        dst = IMG / f"{rid}.png"
        if c["src"] == "USPTO":
            clean_png(TEST_DIR / c["orig_file"], dst)
        elif c["src"] == "USPTO-ODP":
            clean_png(c["orig_file"], dst)
        else:
            import io, zipfile
            zf = zf or zipfile.ZipFile(ZIP)
            clean_png(io.BytesIO(zf.read(c["orig_file"])), dst)
        new.append({"id": rid, "src": c["src"], "orig_id": c["orig_id"], "orig_file": c["orig_file"],
                    **({"orig_mol": c["orig_mol"]} if c.get("orig_mol") else {}), "patent": c["patent"],
                    "png": str(dst), "truth": c["truth"], "labels": [], "heavy": c["heavy"], "cls": c["cls"],
                    "n_res": c["n_res"], "inchikey": c["inchikey"], "show": True,
                    **({"week": c["week"]} if c.get("week") else {}),
                    "added": now().strftime("%Y-%m-%d")})
    if new:
        json.dump(rows + new, open(RUN / "set.json", "w"), indent=1)
        json.dump([{"id": x["id"], "png": x["png"], "truth": x["truth"]} for x in rows + new],
                  open(RUN / "run_set.json", "w"), indent=0)
    log(f"added {len(new)} rows from {source} ({dict(collections.Counter(x['cls'] for x in new))}); "
        f"{len(cands)} candidates were eligible")
    return new


# ------------------------------------------------------------------------------------------------ readers
def run_cx():
    rows = set_rows()
    have = cx_have()
    todo = [x for x in rows if x["id"] not in have]
    if not todo:
        return 0
    d = WORK / f"cx_in_{now().strftime('%Y%m%dT%H%M%S')}"
    d.mkdir(parents=True)
    for x in todo:
        os.symlink(x["png"], d / f"{x['id']}.png")
    out = WORK / "cx_out"
    out.mkdir(exist_ok=True)
    before = set(glob.glob(str(out / "run_*")))
    log(f"CXMolScribe stage 3 on {len(todo)} images (nice 15)")
    r = subprocess.run(["nice", "-n", "15", str(REPO / "benchmarks/run_stage3_only.sh"), "--images", str(d),
                        "--out", str(out), "--device", "cpu"], capture_output=True, text=True)
    runs = sorted(set(glob.glob(str(out / "run_*"))) - before)
    if r.returncode != 0 or not runs:
        raise RuntimeError(f"stage 3 failed rc={r.returncode}: {r.stderr[-400:]}")
    merge_cx(runs[-1])
    return len(todo)


def merge_cx(run_dir):
    """Append a stage-3 run's rows to the published pair (text only, one row per id; the same rule as
    merge_cx.py)."""
    import pandas as pd
    ids = {x["id"] for d in ("synth", "real", "big") if (SA / d / "set.json").exists()
           for x in json.load(open(SA / d / "set.json"))}
    seen = set()
    for f in ("High", "Low"):
        p = CXP / f"Completed_{f}Confidence_CMAGE.xlsx"
        old = pd.read_excel(p)
        newp = Path(run_dir) / "03_CXMS_Results" / f"Completed_{f}Confidence_CMAGE.xlsx"
        new = pd.read_excel(newp) if newp.exists() else old.iloc[0:0]
        for dfr in (old, new):
            for fp in dfr["File Path"]:
                k = Path(fp).stem
                assert k in ids, k
                assert k not in seen, f"{k} twice"
                seen.add(k)
        m = pd.concat([old, new.reindex(columns=old.columns)], ignore_index=True)
        m = m.drop(columns=[c for c in m.columns if c == "Unnamed: 0"])
        m.to_excel(p)
    with open(CXP / "RUN.txt", "a") as fh:
        fh.write(Path(run_dir).name + "  (big set, merged text-only)\n")
    log(f"merged {run_dir}; {len(seen)} ids have a CX row")


def run_api():
    rows = set_rows()
    have = api_have()
    todo = [x for x in rows if x["id"] not in have]
    if not todo:
        return 0, 0.0
    big = run_spend(RUN)
    month = month_api_spend()
    if big >= BIG_CAP:
        (RUN / "STOP").write_text(f"big set API cap ${BIG_CAP} reached (${big:.2f})\n")
        raise CapHit(f"the big set's API spend ${big:.2f} reached the ${BIG_CAP:.0f} cap")
    room = min(BIG_CAP - big, MONTH_CAP - month)
    n_ok = max(0, int(room / EST_PER_IMAGE))
    if n_ok == 0:
        if BIG_CAP - big < EST_PER_IMAGE:
            (RUN / "STOP").write_text(f"big set API cap ${BIG_CAP} reached (${big:.2f})\n")
            raise CapHit(f"the big set's API spend ${big:.2f} is at the ${BIG_CAP:.0f} cap")
        log(f"month guard: ${month:.2f} of ${MONTH_CAP:.0f} used; API skipped until the monthly reset "
            f"({len(todo)} rows wait)")
        return 0, 0.0
    if n_ok < len(todo):
        log(f"room for {n_ok} of {len(todo)} at ${EST_PER_IMAGE}/image")
    sub = WORK / "api_run_set.json"
    json.dump([{"id": x["id"], "png": x["png"], "truth": x["truth"]} for x in todo[:n_ok]], open(sub, "w"))
    cap = round(big + room, 2)
    log(f"API on {min(n_ok, len(todo))} images; big set ${big:.2f}, month ${month:.2f}, guard cap ${cap}")
    r = subprocess.run([PY, "-u", str(TOOLS / "api_reader_set.py"), "--set", str(sub),
                        "--spend-glob", str(RUN / "ledger.jsonl"), "--spend-glob", str(RUN / "retries.jsonl"),
                        "--cap", str(cap), "--org-cap", "1000000", "--",
                        "--out", str(RUN), "--env-file", str(ENV), "--model", "claude-sonnet-5-5", "--conc", "4",
                        "--budget", str(cap), "--max-tokens", "64000", "--prompt-file", str(SA / "prompt_v2.txt"),
                        "--prompt-version", "v2", "--max-consec-fail", "5"],
                       capture_output=True, text=True, cwd=str(REPO))
    with open(WORK / "api.log", "a") as fh:
        fh.write(r.stdout[-20000:] + r.stderr[-5000:])
    stop = RUN / "STOP"
    if stop.exists() and run_spend(RUN) >= BIG_CAP - 0.01:
        raise CapHit(f"the big set's API spend reached the ${BIG_CAP:.0f} cap")
    if stop.exists():          # the guard's STOP for a step-level cap: clear it so the next step can run
        stop.unlink()
    return len(api_have() & {x["id"] for x in todo}), run_spend(RUN) - big


class CapHit(Exception):
    pass


# ------------------------------------------------------------------------------------------------ scoring
def score():
    """verdict() per arm on rows both arms have read; CX via build_superatoms.cx_score (label expansion)."""
    sys.path.insert(0, str(TOOLS))
    import build_superatoms as B
    rows = {x["id"]: x for x in set_rows()}
    fr = B.final_rows(RUN)
    cxp = B.cx_preds()
    out = collections.defaultdict(collections.Counter)
    for k, (r, r0, rets) in fr.items():
        if r is None or k not in cxp or k not in rows:
            continue
        m = rows[k]
        v = B.verdict(B.parse_smiles(r.get("text")) or "", m["truth"])
        c = B.cx_score(cxp[k][0], m["truth"])[1]
        for g in (m["src"], "all"):
            out[g]["n"] += 1
            out[g]["api"] += v == "exact"
            out[g]["cx"] += c == "exact"
    return {g: dict(c) for g, c in out.items()}


# ------------------------------------------------------------------------------------------------ publish
def wait_repo_quiet(limit_s=900):
    pat = re.compile(r"build_sonnet55c?\.py|build_wall\.py|build_sonnet\.py|build_superatoms\.py|build_llmocr\.py|build_gallery\.py|git (commit|push|add)")
    t0 = time.time()
    while time.time() - t0 < limit_s:
        if (REPO / ".git/index.lock").exists():
            time.sleep(10); continue
        r = subprocess.run(["ps", "-eo", "pid,ppid,args"], capture_output=True, text=True)
        me = {os.getpid()}
        busy = [l for l in r.stdout.splitlines()[1:] if pat.search(l) and int(l.split()[0]) not in me
                and int(l.split()[1]) not in me]
        if not busy:
            return
        time.sleep(10)


def publish(msg):
    hold = Path("/root/cmage-work/backfill/hold_publish")
    t0 = time.time()
    while hold.exists() and time.time() - t0 < 3600:
        time.sleep(30)
    wait_repo_quiet()
    for tool in ("build_superatoms.py", "build_llmocr.py", "build_gallery.py"):
        if not (TOOLS / tool).exists():
            continue
        r = subprocess.run([PY, str(TOOLS / tool)], capture_output=True, text=True, cwd=str(REPO))
        if r.returncode != 0:
            raise RuntimeError(f"{tool} failed: {r.stderr[-400:]}")
    for u in PURGE:
        subprocess.run(["/root/seb/scripts/cf-purge", f"{SITE}/{u}"], capture_output=True)
    paths = [p for p in COMMIT if (REPO / p).exists()]
    paths += [p for p in TRACKED_ONLY if subprocess.run(["git", "ls-files", "--error-unmatch", p], cwd=str(REPO),
                                                         capture_output=True).returncode == 0]
    mf = WORK / "commit_msg.txt"
    mf.write_text(msg + "\n\nCo-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>\n")
    wait_repo_quiet()
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, cwd=str(REPO))
    g("add", "--", *paths)
    r = g("commit", "-q", "-F", str(mf), "--only", "--", *paths)
    if r.returncode != 0 and "nothing" not in (r.stdout + r.stderr):
        raise RuntimeError(f"commit failed: {r.stderr[-300:]}")
    r = g("push", "-q", "origin", "HEAD:main")
    head = g("log", "-1", "--format=%h").stdout.strip()
    if r.returncode != 0:
        log(f"push failed (next step retries): {r.stderr[-300:]}")
        return head + " (not pushed)"
    return head


# ------------------------------------------------------------------------------------------------ commands
def n_protac_read():
    have = api_have()
    return sum(1 for x in set_rows() if x["cls"] == "protac" and x["id"] in have)


def status():
    rows = set_rows()
    api, cx = api_have(), cx_have()
    ids = {x["id"] for x in rows}
    s = load_state()
    print(json.dumps({
        "rows": len(rows), "by_src": dict(collections.Counter(x["src"] for x in rows)),
        "by_class": dict(collections.Counter(x["cls"] for x in rows)),
        "api_read": len(api & ids), "cx_read": len(cx & ids),
        "big_api_spend": round(run_spend(RUN), 2), "month_api_spend": round(month_api_spend(), 2),
        "pool": sum(1 for _ in open(POOL)) if POOL.exists() else None,
        "heavy_hist": dict(sorted(collections.Counter(min(x["heavy"] // 25 * 25, 150) for x in rows).items())),
        "last_block": s.get("last_block"), "halted": s.get("halted"), "steps": len(s.get("steps", [])),
        "protac_read": n_protac_read(), "target_protac": TARGET_PROTAC, "big_cap": BIG_CAP, "month_cap": MONTH_CAP,
        "odp_pool": dict(collections.Counter(r["cls"] for r in jl(ODP_POOL))),
        "odp_weeks": len(json.load(open(WORK / "odp_weeks.json"))) if (WORK / "odp_weeks.json").exists() else 0},
        indent=1))


def step(n, source="auto", do_publish=True, do_signal=True):
    s = load_state()
    if s.get("halted"):
        log(f"halted ({s['halted']}); nothing runs. Clear 'halted' in {STATE} to resume.")
        return 1
    t0 = time.time()
    rows = set_rows()
    if n_protac_read() >= TARGET_PROTAC:
        disable_timer(f"{n_protac_read()} PROTAC rows read (target {TARGET_PROTAC})")
        return 0
    backlog = len([x for x in rows if x["id"] not in api_have()])
    n = max(0, n - backlog)              # rows still waiting for the API (month guard) count against this step
    new = add_rows(n, source) if n > 0 else []
    try:
        ncx = run_cx()
        napi, cost = run_api()
    except CapHit as e:
        s["halted"] = str(e); save_state(s)
        disable_timer(str(e))
        signal(f"C-MAGE big superatom set STOPPED: {e}.\nTimer disabled. Log {LOG}", do_signal)
        return 1
    sc = score()
    a = sc.get("all", {"n": 0, "api": 0, "cx": 0})
    pct = lambda x, n: f"{x / n * 100:.1f}%" if n else "-"
    total = len(api_have() & {x["id"] for x in set_rows()})
    line1 = (f"C-MAGE big superatoms: +{len(new)} drawings ({dict(collections.Counter(x['cls'] for x in new))}), "
             f"{napi} read by Sonnet 5.5 API (${cost:.2f}), {ncx} by CXMolScribe; {total} read in all, PROTACs "
             f"{n_protac_read()}/{TARGET_PROTAC}; big-set API ${run_spend(RUN):.2f}/{BIG_CAP:.0f}.")
    parts = []
    for g in ("USPTO", "USPTO-ODP", "USPTO-train"):
        if g in sc:
            x = sc[g]
            parts.append(f"{g}{' (CX trained on these)' if g == 'USPTO-train' else ''}: API {x['api']}/{x['n']} "
                         f"{pct(x['api'], x['n'])}, CX {x['cx']}/{x['n']} {pct(x['cx'], x['n'])}")
    line2 = "Exact: " + "; ".join(parts) if parts else "Exact: nothing scored yet."
    head = None
    if do_publish:
        head = publish(f"Superatoms big set: +{len(new)} drawings, {napi} API reads, {ncx} CXMolScribe reads\n\n"
                       f"{line1}\n{line2}")
        line2 += f" Commit {head}."
    s["steps"].append({"at": now().isoformat(), "added": len(new), "api": napi, "cx": ncx, "cost": round(cost, 4),
                       "commit": head, "minutes": round((time.time() - t0) / 60, 1)})
    save_state(s)
    signal(line1 + "\n" + line2, do_signal)
    if n_protac_read() >= TARGET_PROTAC:
        disable_timer(f"{n_protac_read()} PROTAC rows read (target {TARGET_PROTAC})")
    return 0


def tick():
    s = load_state()
    if s.get("halted"):
        log("tick: halted"); return 0
    r = subprocess.run(USAGE, capture_output=True, text=True, timeout=180)
    try:
        u = json.loads(r.stdout)
        p5, p7, rs = u["5h"]["pct"], u["7d"]["pct"], u["5h"]["resets_at"]
    except Exception:
        log(f"tick: usage unreadable ({r.stderr[-200:]})"); return 0
    block = (rs or "")[:16]
    # the server's resets_at jitters by up to a minute (11:19 vs 11:20 seen), so a block is NEW only when it is
    # more than 30 min from the last one recorded
    def _t(x):
        return dt.datetime.fromisoformat(x) if x else None
    last = _t(s.get("last_block"))
    if last is not None and abs((_t(block) - last).total_seconds()) < 1800:
        log(f"tick: same 5 h block ({block}); skip"); return 0
    if p5 >= CAP_5H or p7 >= CAP_7D:
        log(f"tick: 5 h {p5}% / week {p7}% at or over {CAP_5H:.0f}/{CAP_7D:.0f}; skip"); return 0
    s["last_block"] = block
    save_state(s)
    log(f"tick: new block {block}, 5 h {p5}%, week {p7}%: step")
    return step(250)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("status")
    st = sp.add_parser("step")
    st.add_argument("--n", type=int, default=250)
    st.add_argument("--source", default="auto", choices=["auto", "test", "odp", "train"])
    st.add_argument("--no-publish", action="store_true")
    st.add_argument("--no-signal", action="store_true")
    sp.add_parser("tick")
    sp.add_parser("publish")
    sp.add_parser("odp-check")
    a = ap.parse_args()
    if a.cmd == "status":
        return status()
    if a.cmd == "odp-check":
        return 0 if odp_ok() else 1
    WORK.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log(f"{a.cmd}: another big_expand run holds the lock; skip")
        return 0
    try:
        if a.cmd == "step":
            return step(a.n, a.source, not a.no_publish, not a.no_signal)
        if a.cmd == "tick":
            return tick()
        if a.cmd == "publish":
            print(publish("Superatoms big set: rebuild and publish"))
            return 0
    except Exception as e:
        s = load_state()
        s["halted"] = f"{type(e).__name__}: {e}"[:500]
        save_state(s)
        disable_timer("error")
        signal(f"C-MAGE big superatom set HALTED on an error: {str(e)[:300]}\nTimer disabled. Log {LOG}",
               a.cmd != "step" or not getattr(a, "no_signal", False))
        raise


if __name__ == "__main__":
    sys.exit(main() or 0)
