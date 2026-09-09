# corpus_synth2 — synthetic CXSMILES benchmark, v2

1031 drawings of 503 distinct compounds across 87 PDFs (207 US-Letter pages,
5.5 MB). Built by `benchmarks/make_synthetic_corpus_v2.py` from the plan in
`benchmarks/synth_v2_build/synthetic_plan_v2.json`; ground truth is
`benchmarks/ground_truth/synthetic_manifest_v2.json`.

## What makes the ground truth trustworthy

Every structure was drawn from the same molecule object whose `MolToCXSmiles`
is recorded as `drawn_cxsmiles`:

    cond = rdAbbreviations.CondenseMolAbbreviations(mol, abbrevs, maxCoverage=0.8)
    cx   = Chem.MolToCXSmiles(cond)
    draw(cond)

The picture and the reference come from one object, so they cannot disagree.
`benchmarks/synthetic_selftest_v2.py` is the standing gate: 20163 checks, and it
also proves the grader still says NO (a wrong label must cost the grade).

## Upper bound — say this wherever a number from here is quoted

RDKit line art on exactly white, one drawing convention throughout, no scanner
noise, no overlapping labels, no hand-drawn bonds. Every figure this corpus
produces is an UPPER BOUND on the pipeline against real literature, and the
`basic` stratum is a control that should sit near ceiling rather than a result.

## Layout

    s2_<stratum>_NN.pdf   core corpus, 12 structures per PDF, 6 per page
    s2_mixed_NN.pdf       all six strata on one page, reported separately
    s2_dens_*.pdf         the SAME 48 compounds at 1, 4, 6, 12 and 20 per page
    s2_ink_*.pdf          the SAME 48 compounds at bond line width 1.0 / 3.5
    s2_space_tight_*.pdf  the SAME 48 compounds with the gutters removed
    s2_vocab_in_NN.pdf    condensed labels inside CXMolScribe's 75-entry vocabulary
    s2_vocab_out_NN.pdf   the same molecules with the same labels MIRRORED
                          (CO2Et -> EtO2C), which the vocabulary does not contain

The crossed arms draw no per-structure caption: `space_tight` would collide with
one, and a caption is ink near a structure — a confound in an experiment about
ink. They carry their own `dens_std` control drawn under the arm's conventions,
so density is only ever compared inside the arm.

## Rebuilding

    .venv-ms/bin/python benchmarks/select_synthetic_v2.py          # plan (deterministic)
    .venv-ms/bin/python benchmarks/make_synthetic_corpus_v2.py \
        --plan benchmarks/synth_v2_build/synthetic_plan_v2.json \
        --out-pdfs benchmarks/corpus_synth2 \
        --out-manifest benchmarks/ground_truth/synthetic_manifest_v2.json
    .venv-ms/bin/python benchmarks/synthetic_selftest_v2.py
