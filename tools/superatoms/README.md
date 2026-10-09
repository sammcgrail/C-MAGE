# Superatom set generators (the "Superatoms (API)" tab)

Working copies run from `/root/cmage-work/superatoms/` (paths inside point there); these are the
committed sources. Order:

1. `fetch_pubchem.py` resolves `pubchem_names.txt` on PubChem.
2. `build_set.py` builds the synthetic set with `sa_abbrev.py` (RDKit `CondenseMolAbbreviations`,
   extended abbreviations, attachment rules, expand-back exactness gate, drawn-label gate, label
   overlap gate, metadata-free PNGs).
3. `classify_real.py USPTO CLEF acs UOB` screens the MolScribe real-image benchmarks with Haiku 5.5
   for text superatoms; `select_real.py` keeps images whose labels map to a group present in the
   truth; `build_real.py` samples, renames to `rs_NNNN` and writes the run set.
4. `tools/api_reader_set.py` reads each set (Sonnet 5.5, prompt v2, max_tokens 64,000, streamed,
   with a spend guard); `tools/build_superatoms.py` scores with `sonnet_batch.verdict()` and writes
   `wall/superatoms.json`.

## Expansion, 2026-10-09 (sa_0176..sa_0524, rs_0341..rs_1896)

- `sa_abbrev.py` gained a v2 list (`ALL_V2`): Trt, PMB on N, MOM/OMOM, THP/OTHP, SEM/OSEM, Piv/OPiv,
  Alloc, and RDKit's "NC" isocyanide dropped (ambiguous with a left-pointing nitrile; the reason sa_0034
  is excluded). `ALL_V1` is the first 175 unchanged (`build_set.py` still reproduces them);
  `ALL` is the union, used only for label lookup and CXMolScribe label expansion.
- `fetch_pubchem.py pubchem_names2.txt more/pubchem2.json` -> `build_more.py`: 300 drawings (PubChem
  picks with >= 2 labels + corpus molecules not yet used, greedy for label diversity), same gates.
- `fetch_pubchem_sub.py` -> `build_more_sub.py`: up to 5 PubChem substructure hits per group the name
  list left empty (OTIPS, OTBDPS, OTBS, OMOM, OTHP, SEM, Trt, PMB, Piv, Alloc).
- `rescreen_real.py` re-screens the Haiku replies that had not parsed; `build_real_more.py` adds EVERY
  remaining qualifying USPTO/CLEF image (showable sources only).
