# C-MAGE near-miss analysis — PROGRESS

## Task
Test hypothesis: benchmark scoring calls predictions WRONG when they are right
(or chemically equivalent). Quantify, then fix scorer.

## Log
started 2026-09-09T16:31:51+00:00

### Step 0 — orientation (done)
- Read SKILL.md, FINDINGS.md, score_run.py, cxsmiles.py, rescore_fragments.py.
- 675 img corpus scored at /tmp/cmage-675/scored/structures.csv: 743 rows =
  wrong 504, invalid 86, exact 75, no-truth 68, stereo 10.
- 11 PDF docs scored per-doc at /tmp/cmage-pdfs/scored2/<name>/structures.csv
  with per-doc manifests /tmp/cmage-pdfs/manifests/<name>.json
- Disk 82%, 28G free. RDKit interpreter /root/C-MAGE/.venv-ms/bin/python

### Step 1 — NEGATIVE CONTROL on the Tanimoto threshold (done)
/tmp/cmage-nearmiss/control_tanimoto.json
675 ref molecules, 629 unique by canonical iso SMILES (46 dupes = alias names).
All 197,506 distinct pairs:
  >=0.85: 18 (0.0091%)   >=0.90: 10   >=0.95: 8   >=0.99: 7
  molecules with ANY distinct neighbour >=0.85: 33/629 = 5.2%
CRITICAL: Morgan r2 is STEREO-BLIND. 7 of the 18 are pure stereoisomer pairs at
Tanimoto EXACTLY 1.0 (levomilnacipran/milnacipran, galactose/glucose,
esomeprazole/omeprazole, esketamine/ketamine, citalopram/escitalopram,
cetirizine/levocetirizine, bupivacaine/levobupivacaine).
=> Tanimoto 1.0 does NOT mean same molecule. `near` must never be a pass grade.
Also osimertinib/tagrisso 0.946 = same drug, mesylate salt (charge/salt axis).
And: random-pair base rate UNDERSTATES the false-positive rate, because a real
misread is the reference minus one atom, not a random molecule. Noted as the
reverse-error risk.

### Step 2 — first full grading pass (done)
/tmp/cmage-nearmiss/graded_675.json  (743 rows), /tmp/cmage-nearmiss/graded_pdfs.json (242 rows)
675 corpus, 504 legacy-wrong regrade: exact 393 (78.0%), stereo 32, charge 12,
tautomer 4, skeleton 1, near 2, wrong 60.  393+32 all via largest-fragment strip.
PDF corpus, 212 legacy-wrong regrade: exact 19 (all via CXSMILES decode), charge 1,
wrong 192.  No near/skeleton at all; max Tanimoto among still-wrong 0.657.
CONTROLS PASS: legacy exact (75 img / 14 pdf) all stay exact with zero
normalisation; legacy stereo (10) all stay stereo; legacy invalid all stay invalid.
TODO: reconcile my 468 exact vs rescore_fragments 462/743 (different denominator
+ possible use_lf_ref leak); classify dropped fragments phantom/duplicate/real.

### Step 3 — hand-check of charge/tautomer/skeleton/near (done)
Raw dump: /tmp/cmage-nearmiss/handcheck_675_raw.txt
FOUND A REVERSE ERROR in my own v1 grader: comparing pred-largest-fragment against
REF-largest-fragment ("use_lf_ref") graded carboplatin EXACT while the prediction
had DROPPED THE PLATINUM. 6 rows used that path (carboplatin, farxiga,
lithium_carbonate, methylene_blue, rhodamine_b, toprol). Removing use_lf_ref.
Also: rescore_fragments.py's own largest-fragment rule LOSES methylene blue,
which score_run.py already scores exact (ref is legitimately 2 fragments).
Redesign for v2:
  - phantom strip = drop only NEUTRAL fragments whose atoms are all H and/or I
    (keeps [I-], a real counter-ion); + collapse duplicate identical fragments
  - `largest` fragment kept as a SEPARATE, looser, clearly-flagged rung
  - split charge (Uncharger only, no fragments removed) from salt (FragmentParent)
  - METAL GUARD: a metal present on one side only BLOCKS the salt rung
    (carboplatin/cisplatin/oxaliplatin: the metal IS the molecule)
  - cumulative ladder exact<stereo<tautomer<charge<salt<skeleton<near<wrong

### Step 4 — grader v2/v3 (metal guard, narrow phantom rule, cumulative ladder)
v2 results 675: exact 464 stereo 42 tautomer 4 charge 9 salt 5 skeleton 1 near 3
  wrong 61 invalid 86.  Of 504 legacy-wrong: 439 (87.1%) matched, 4 near-miss,
  61 genuinely different.
v2 results PDFs: of 212 legacy-wrong: 20 (9.4%) matched (all via CXSMILES decode),
  0 near-miss, 192 genuinely different (max Tanimoto 0.657 -- nowhere near).
METAL GUARD VERIFIED: carboplatin (pred lost the Pt) -> `near` T=0.889, NOT exact.
  oxaliplatin (both sides collapsed to the diaminocyclohexane LIGAND under
  FragmentParent) -> `wrong`, NOT charge.  Both were false passes in v1.
v3 adds tautomer-composed charge/salt forms so clozapine (tautomer + iodide)
  grades `salt` instead of needing the loose largest-fragment hammer.

### Step 5 — PDF corpus hand-checks (done), file /tmp/cmage-nearmiss/handcheck_pdfs.txt
DECODED-EXACT (19) e.g. pregabalin `*C[C@@H](CN)CC(C)C |$CO2H;;;;;;;;$|` == pregabalin;
  `*[C@@H]1OC(=O)N[C@@H]1C |$Ph;;;;;;;$|` == the oxazolidinone;
  `*Nc1cc(*)cc(*)c1 |$Boc;;;;;OMe;;;MeO;$|` == tert-butyl N-(3,5-dimethoxyphenyl)carbamate;
  `*[Si](*)(*)C1CCCCC1 |$H3CO;;OCH3;OCH3;...$|` == cyclohexyltrimethoxysilane;
  macarpine with OMe/Me labels == macarpine.
CHARGE (1): `*[C@@H]1OC(=O)[N-][C@@H]1* |$Ph;;;;;;;Me$|` -- ring NH read as [N-].
STILL-WRONG ceiling on this corpus: max Tanimoto 0.657, so the 0.85 near line is
  comfortably clear of every genuine miss here.

### Step 6 — FINAL grading scheme v5 (grade.py), results frozen
Two more self-traps found and fixed:
 (a) ranking grade above cost let the LOOSE largest-fragment hammer produce a
     "tighter" grade than an untouched one (clozapine: tautomer-via-hammer beat
     plain salt). Fixed by emitting TWO grades: `grade` (raw/decoded/dephantom
     only) and `grade_largest` (hammer allowed). Never merged.
 (b) rdMolStandardize.FragmentParent IS LargestFragmentChooser -- using it for the
     `salt` rung silently re-introduced the hammer: 33 image predictions reached
     `salt` only because FragmentParent binned their phantom I/[HH], and it strips
     [Pt+2] off carboplatin's reference. Replaced with SaltRemover's 15 curated
     patterns (strips mesylate/iodide/chloride, LEAVES [Pt+2], propylene glycol,
     succinic acid).
Verified no manifest reference (675 + 34 molecules) carries a neutral H/I-only
fragment, so dephantom cannot fabricate a match.
FINAL 675: grade exact 439 stereo 40 tautomer 3 charge 9 salt 20 skeleton 1
  near 15 wrong 62 invalid 86 | grade_largest exact 464 stereo 42 taut 4 charge 9
  salt 3 skel 1 near 4 wrong 62 invalid 86
FINAL PDFs: exact 33 charge 1 wrong 192 invalid 16 (identical with hammer)
Data files: graded_675_v5.json, graded_pdfs_v5.json

### Step 7 — production code written and gated
/root/C-MAGE/benchmarks/graded.py           the ladder + normalisations
/root/C-MAGE/benchmarks/graded_selftest.py  13 cases + teeth checks, GATE OPEN
Reproduced on both corpora via the production module:
  /tmp/cmage-nearmiss/final_675.json  /tmp/cmage-nearmiss/final_pdfs.json
Teeth check initially FAILED honestly: after switching to SaltRemover the metal
guard is a no-op on carboplatin/oxaliplatin, so the control had stopped testing
anything. Rewrote it to swap the stripper back to FragmentParent -- the exact
regression the guard exists to survive -- and it now discriminates
(near vs salt, wrong vs salt).
NEGATIVE RESULT worth reporting: rdMolStandardize.Normalizer rescues ZERO cases.
The residual charge misreads (isosorbide dinitrate nitro-OH, zidovudine and
pregabalin azide-NH2) are extra-HYDROGEN misreads, not charge notation, so no
`normalize` rung was added.
NEXT: patch score_run.py.

### Step 8 — score_run.py patched, and a REAL BUG caught by the diff check
`rec.update(graded.grade_prediction(...))` silently OVERWROTE the strict
`matched_name` column on 426 of 743 rows (graded.py used the same key name).
It was invisible in every summary NUMBER because the strict recall query also
gates on `verdict` -- pure luck. Found only by diffing structures.csv against the
pre-existing scored dir column by column.
Fix: graded.py renamed to graded_match / graded_match_largest / graded_closest,
and score_run.py now raises SystemExit if the two field-name sets ever intersect.
VERIFIED: `score_run.py --no-graded` reproduces all five output files of the
pre-existing /tmp/cmage-675/scored byte-for-byte (ignoring the timestamp).

### Step 9 — COMMITTED AND PUSHED
Code (benchmarks/graded.py, graded_selftest.py, score_run.py) landed in 1f8260c —
a CONCURRENT agent's commit swept my working-tree files in. Verified all three
match disk and the gate still passes after their commit.
FINDINGS.md section 4 committed as 4506a1c (part swept into 1f8260c too).
webapp/static/index.html has UNCOMMITTED changes from another agent — left alone.
Pushed to origin/main.
FINAL NUMBERS (both corpora, per-structure denominators):
  images 675: strict exact 75 stereo 10 wrong 504 invalid 86
              graded exact 439 stereo 40 tautomer 3 charge 9 salt 20 skeleton 1
                     near 15 wrong 62 invalid 86
              +hammer exact 464 stereo 42 taut 4 charge 9 salt 3 skel 1 near 4
                     wrong 62 invalid 86
              graded recall 511/675 vs strict 75/675
  docs 242:   strict exact 14 wrong 212 invalid 16
              graded exact 33 charge 1 wrong 192 invalid 16 (identical with hammer)
              graded recall 18/34 vs strict 9/34  <- matches rescore_fragments
                by a completely independent code path
