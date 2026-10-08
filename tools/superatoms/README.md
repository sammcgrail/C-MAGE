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
