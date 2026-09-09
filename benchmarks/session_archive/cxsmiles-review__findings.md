# CXSMILES review findings
Started 2026-09-09T01:45:07+00:00

## F1 (CONFIRMED, high importance): the commenting-out is UPSTREAM C-MAGE's, not the fork's
- `git diff upstream/main HEAD -- cxmolscribe-wd/MolScribe/molscribe/chemistry.py` is EMPTY.
- merge-base(upstream/main, HEAD) = 654a80a = tip of upstream/main. Fork adds 19 commits, none touch chemistry.py.
- Only fork changes under MolScribe/: dataset.py (indigo_compat import, 3 lines) + new indigo_compat.py.
- The commented-out ABBREVIATIONS lookups in `_expand_abbreviation` AND `get_smiles_from_symbol` are present in
  upstream's FIRST C-MAGE commit 42569f7 "Added CXMolScribe and Cleaned Edits" and in upstream/main today.
- 654a80a (upstream, jeehyunhwang, "Requested by Alex") only removed debug prints + a commented rdAbbreviations
  attempt (`# abbrevs = rdAbbreviations.GetDefaultAbbreviations()` / `# v2mol = CondenseMolAbbreviations(...)`).
=> Claim "if my fork introduced it I broke the pipeline" is moot: the fork did NOT introduce it. No revert needed.

## F2 (WRONG in the claim): build/lib/molscribe/chemistry.py is NOT upstream thomas0809/MolScribe's copy
- Fetched raw upstream chemistry.py (646 lines). build/lib copy differs from it in exactly 2 lines:
  `def _expand_functional_group` and `def _convert_graph_to_smiles` are commented out (`#def ...`).
  That file is a stale, syntactically BROKEN intermediate snapshot of the C-MAGE author's edits (tracked in
  upstream git too), not upstream's. It does still carry upstream's intact ABBREVIATIONS lookup, which is why
  it looked like "upstream's" — but it is not a reference copy of anything.
- constants.py and interface.py in the fork are byte-identical to upstream thomas0809/MolScribe (diff exit 0).
## F3 (claim 2 is OVERSTATED): the fork preserves TABLE abbreviations, but still expands element-only condensed formulas
Live trace of fork `_convert_graph_to_smiles` on 2-atom graphs ['C', '[label]'] (edges single):
  OMe/Ph/OBn/Bu/CO2H/CF3/OEt/OTBS/OTHP/CO2Me/OR2/SO2NH2/NMe2/SiMe3 -> '*C |$label;$|'  (preserved)
  [R1] -> '[1*]C |$R1;$|'
  CH2OH -> 'CCO'   NH2 -> 'CN'   CH2CH2OH -> 'CCCO'      (STILL EXPANDED, via _parse_formula/_condensed_formula_list_to_smiles
                                                           because _expand_abbreviation('C')='[C]' etc. are valid bracket atoms)
Mechanism: only the ABBREVIATIONS lookups are commented out; the condensed-formula parser is untouched. A label is kept iff
its formula-parse contains a token RDKit cannot parse as an atom (any table key, R-group, junk). Pure-element formulas expand.
`#N3 CHANGES ... # formula_list = symbol` shows the author tried and reverted a full bypass. So "keep as drawn" is the effect
for named abbreviations only; there is no comment or doc stating the intent.
Upstream thomas0809/MolScribe on the same inputs: OMe->COC, Ph->Cc1ccccc1, OTBS->CO[Si](C)(C)C(C)(C)C, CO2Me->COC(C)=O,
  OR2->[2*]OC, SO2NH2->'C[SH2][N+](=O)[O-]' (GARBAGE: regex tokenises O2N as the nitro key), OTHP->'*C', NMe2->'*C'.
=> upstream really does guess, sometimes wrongly; fork keeps the label. Claim 3 (purpose) is consistent with behaviour but is
   inferred, not documented anywhere in code/README.

## F4 (WRONG premise): the "paper" DOI does not exist
- https://doi.org/10.26434/chemrxiv.15008460 -> HTTP 404 at doi.org. Figshare-era DOI shape (2021 numeric), but upstream
  repo was created 2026-08-03 (first commit 3ea9717). Engage API is Cloudflare-blocked from here; WebSearch for
  "C-MAGE"/"CXMolScribe" returns nothing. Upstream README has NO citation, DOI, or paper link. The only chemrxiv DOI in the
  repo is MERMaid/VisualHeist's (10.26434/chemrxiv-2025-8z6h2), which is stage 1's upstream, not C-MAGE.
=> There is no C-MAGE manuscript to read; any claim about what "the paper says" about CXSMILES is unsupported either way.
## F5 (WRONG, high severity): the tool's RWMol surgery corrupts stereochemistry
Tetrahedral: RemoveAtom(dummy) + AddBond(anchor, new atom) appends the new bond at the END of the anchor's bond list;
the @/@@ tag is relative to bond order, so parity flips whenever the dummy was not already last. Hand tests (truth =
textual in-place substitution, canonicalised):
  C[C@H](*)F |$;;OMe;$|       -> CO[C@H](C)F   truth CO[C@@H](C)F   FLIPPED
  F[C@](Cl)(*)Br |$;;;Ph;$|   -> FLIPPED ; *[C@@](F)(Cl)Br |$Ph$| -> FLIPPED ; O[C@H]1CC[C@@H](*)CC1 -> FLIPPED
  *[C@H](C)F, C[C@@H](F)*     -> preserved (dummy already first/last).   5 of 7 tetrahedral cases wrong.
E/Z: */C=C/C |$Ph;;;$| -> CC=Cc1ccccc1 (stereo LOST); C/C=C/* -> lost; */C=C\C -> lost; C/C=C(/*)C -> lost.
  Only preserved when the dummy is not a stereo-defining substituent (*C(=O)/C=C/C ok). 4 of 5 alkene cases lost.
Bond order to the dummy is silently replaced by SINGLE: *=C |$CHO;$| -> CC=O, C#* |$;CN$| -> CC#N.
  Corpus scan: 6 non-single bonds to labelled dummies in 242 rows, all junk labels -> no practical impact here.

## F6 (WRONG, headline numbers): 9/34 and 16/34 reproduce; 18/34 does NOT (with stereo required)
Independent recount over /tmp/cmage-pdfs/scored2/*/structures.csv vs /tmp/cmage-pdfs/manifests (34 molecules, 242 rows):
  stereo required : raw 9 | expanded 16 | expanded+largest-fragment 16   (LF adds ZERO)
  stereo relaxed  : raw 9 | expanded 18 | expanded+largest-fragment 18
  => "18/34" is the stereo-RELAXED expanded number, not a largest-fragment effect.
  aglacin B doc: 0/3 -> 2/3 stereo-required, 0/3 -> 3/3 only stereo-relaxed. Patent OCSR 2/4 -> 4/4 holds either way.
  pheromones: 2 -> 2 (stereo) / 3 (relaxed). macarpine 0 -> 2.

## F7 (context): upstream C-MAGE DOCUMENTS label retention in its own diagram
details/pipeline.png (upstream) shows CXMolScribe output
  *c1ccc2c(c1)N(S(*)(=O)=O)C[C@@](*)(C=C)O2 |$Ph;;;;;;;;;Ar;;;;;Me;;;$|  captioned "High Confidence CXSMILES Retained"
and README says stage 3 = "Individual Structure Images -> CXSMILES". That is the only design statement that exists.

## F8 (tool, table integrity): attachment assumption holds for the table; SEM entry is broken
All 74 parseable ABBREVIATIONS SMILES have exactly one radical atom and it is atom 0 -> "attachment = atom 0" is valid.
SEM smiles '[CH2]CSi(C)(C)C' does not parse (Si unbracketed) AND is chemically wrong (that is TMS-ethyl, SEM = Me3SiCH2CH2OCH2-).
Tool reports SEM as unknown rather than crashing. Table also bakes in guesses: NBoc -> [NH1]Boc (NH!), Py -> 2-pyridyl, Bz -> benzoyl.

## F9 (coverage): 242 rows: 82 fully expanded, 73 no labels, 71 with >=1 unknown label (29%), 16 unparseable.
423 label occurrences: 248 in table (58.6%), 46 R-group, 129 other. 77 distinct labels, 18 in table.
Unknown-but-deterministic labels the tool refuses that upstream's condensed-formula parser expands: OTBS(6), CO2Bn(2), BnO,
NHCbz, OPO(OEt)2/OP(O)(OEt)2(6), OCH3 is in table. 'Fes' x45 is junk. Zero-attachment '* |$Ph$|' refused (upstream -> benzene).
Cross-check tool vs upstream MolScribe's own _expand_functional_group applied to the same CXSMILES: 215/242 agree, 27 differ
(all = labels the tool refuses: OTBS, CO2Bn, OR2/ORf -> [2*] dummies, NHCbz/BnO, lone Ph/COOH). Row-level exact hits equal (31).

## F10 (tool, minor): label on a NON-dummy atom is "expanded" by deleting that atom: '*C |$;OMe$|' -> '*OC'.
   No check that the labelled atom is '*'. Trailing junk after '|..|' silently treated as plain SMILES.
## F11 (KEY, the correct API): Chem.molzip preserves stereo; both the tool AND upstream MolScribe's expander flip it
On the 9 stereo hand cases: tool 0/9 correct, upstream _expand_functional_group 0/9, Chem.molzip (map-numbered dummies) 9/9.
Corpus consequences (per-molecule, 34):
  sorbic acid  '*/C=C/C=C/C |$COOH;;;;;$|' -> tool 'C/C=C/C=CC(=O)O' (E/Z lost) => misses exact; molzip -> exact hit.
  aglacin A    OAc on a stereocentre mid-neighbour-list -> tool flips it => misses exact (stereo-relaxed only).
  So of the 18 "stereo-relaxed" hits, at least 1 (sorbic acid) is a tool-caused miss, and aglacin A is a tool-caused flip.
'Fes' x45 comes from ONE junk row (pheromones); excluding it, 248/378 label occurrences (65.6%) are in the table.
## F12 (KEY): with a stereo-correct expander the numbers are raw 9 / expanded 18 / +largest-fragment 18 (stereo REQUIRED)
Reference prototype /tmp/cxsmiles-review/zip_expand.py (removeHs=False parse + Chem.molzip): 9/9 stereo hand cases right,
corpus: raw 9, expanded 18 exact, 18 stereo-relaxed; largest-fragment adds 0 either way. aglacin B doc 0/3 -> 3/3 exact.
=> The FINDINGS.md table row "+ largest fragment as well | 18/34" is mislabelled: 18 is what expansion gives once the
   tool stops flipping/dropping stereo; the largest-fragment step contributes nothing on this corpus.
Prototype pitfall found on the way: a default (sanitized) MolFromSmiles removes explicit [H] atoms (aglacin row 28->26 atoms)
and misaligns the $...$ label list. The tool's sanitize=False parse avoids that correctly; use removeHs=False if sanitising.

## F13 (coverage extenders): RDKit rdAbbreviations only CONDENSES (no expand API); its default table has 37 entries
(26 overlap MolScribe's 75; adds nHex/nOct/iPent/NO/CO2-...; has no TBS/SEM/Boc-variants). Upstream MolScribe's
get_smiles_from_symbol (condensed-formula parser + table lookup) expands OTBS(6 rows), OPO(OEt)2/OP(O)(OEt)2/OPO(OPh)2(8),
CO2Bn(2), BnO(1), NHCbz(1) = 18 deterministic rows the tool refuses, plus 14 R-bearing ones (OR2->[O][2*]) -- but it also
GUESSES garbage for unknowns (OTHP -> '[P]([H])([T])=[O]', Z1 -> '*'), so it must be gated (reject any token not an
element/table key). None of these rows are manifest molecules, so no effect on the 34.

## F14 (overclaims in FINDINGS.md / commit afd88b8 / cxsmiles.py docstring)
- "162 of 242 predictions scored wrong for this reason alone": 162 rows carry labels, but only 82 are fully expandable and
  most are intermediates with no ground truth; the supportable statement is recall 9 -> 16 (tool) / 18 (correct expander).
- "this fork's MolScribe deliberately does NOT expand": it is upstream C-MAGE's (AlexTaylor54, 42569f7) vendored MolScribe;
  Sam's fork changed nothing there. "deliberately" is inferred from the diagram/README, no paper exists.
- "OTBS ... table entry has smiles=None": there is no OTBS entry at all; no table entry has smiles=None.

Review complete 2026-09-09T02:02:21+00:00
