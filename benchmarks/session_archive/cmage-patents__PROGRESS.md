# Round 4 patent survey — progress log

Task: find more real pharmaceutical patent PDFs for the C-MAGE chemical-structure
extraction benchmark. Gaps targeted: synthesis-route patents with specific named
intermediates, salt/polymorph patents, 1970s-80s typewritten scans, a DE or JP
patent (Latin-script non-English), deuterated/isotopically-labelled drugs.

Checkpoint files: /tmp/cmage-patents/PROGRESS.md, /tmp/cmage-patents/manifest.json,
PDFs in /tmp/cmage-patents/corpus/.

Rules in force (each learned by getting it wrong):
1. Reject Markush-only. Check at 100 dpi, count SPECIFIC drawings.
2. Resolve by printed CAS, never name.
3. The drawn structure must BE the named compound.
4. Prefer 300 dpi+; tiny/sparse depictions yield sub-300px crops that score 0.

## Log

[16:32] setup: dirs created, PROGRESS.md started
### Route finding (2026-09-09, round 4)
- `patents.google.com/patent/<ID>/en` now returns **503 "automated queries"** to this box —
  the round-1..3 `citation_pdf_url` route is DEAD from here.
- **NEW deterministic route that works: `https://patentimages.storage.googleapis.com/pdfs/US<number>.pdf`**
  (no kind code). 200, `application/octet-stream`, real `%PDF-`. SOURCES.md round 1 recorded this
  form as 403 — it is not, at least for US documents. Verified against two committed files:
  US4231938 -> 10 pages, US6699871 -> 23 pages. Byte sizes differ slightly from the hashed-path
  copies (871216 vs 872095 for US4231938), so it is a separately generated file, not a mirror.
- The same bare route 403s for **CN, EP, DE, JP** — US only.
- **EPO publication server works unauthenticated** for EP documents:
  `https://data.epo.org/publication-server/rest/v1.2/publication-dates/<YYYYMMDD>/patents/<EPnnnnnnn>NWB1/document.pdf`
  -> 200 application/pdf, byte-identical size to the committed EP0641330B1.pdf (291555).
- DEPATISnet `action=pdf&docid=` returns HTML, not PDF (session-gated).

### REJECT US4879303 (amlodipine besylate salt, Pfizer 1989, 4 p, 440359 B)
Fetched and validated (200, %PDF-, 4 pages, 300-dpi CCITT). Rejected on CONTENT: the front page
prints "**11 Claims, No Drawings**" and the body names amlodipine and every counterion in TEXT
only (Table 1 lists besylate/tosylate/mesylate/succinate/salicylate/maleate/acetate/HCl as words).
Zero structures. The ideal salt-vs-salt comparison on paper; nothing to score.
LESSON: for any US patent, `pdftotext -f 1 -l 1 | grep -i 'Drawing'` reads the front-page
"N Claims, M Drawing Sheets" line and screens this out before rendering.

### ACCEPT US7326708B2 — sitagliptin phosphate (Merck, 2008, 15 p, 1277699 B)
"Phosphoric acid salt of a dipeptidyl peptidase-IV inhibitor". 300-dpi CCITT full-page rasters
(Producer ImageMagick), 2560x3300. Fills THREE gaps at once:
- **salt/polymorph**: draws sitagliptin dihydrogenphosphate (formula I, spec pp1-2), its (R) and
  (S) forms (II, III, spec pp3-4 and again in the claims), the free base (IV), and the
  monohydrate on the Example page drawn as `.H3PO4 .H2O` — the counterion is DRAWN, not named.
- **synthesis route with specific isolable intermediates**: Scheme 1 (PDF p10) 1-1 bishydrazide,
  1-2 oxadiazole, 1-3 amidine, 1-4 triazolopiperazine.HCl; Scheme 2 (PDF p11) 2-1 trifluorophenyl-
  acetic acid, Meldrum's acid, 2-2 adduct, 2-3 ketoamide, 2-4 enamine, 2-5 (R)-amine.
- **built-in hard negatives**: PDF pp2-6 are five instrument plots (XRPD, 13C CPMAS NMR,
  19F MAS NMR, TGA, DSC). Nothing on those pages is a structure.
ZERO Markush anywhere. Figure-bearing pages: 7,8,9,10,11,14,15 = 7 structure pages + 5 plot pages.

### ACCEPT US5273995A — atorvastatin calcium (Warner-Lambert/Roth, 1993, 10 p, 765709 B)
"[R-(R*,R*)]-2-(4-fluorophenyl)-b,d-dihydroxy-5-(1-methylethyl)-3-phenyl-4-[(phenylamino)carbonyl]-
1H-pyrrole-1-heptanoic acid, its lactone form and salts thereof" — the Lipitor hemicalcium patent.
300-dpi CCITT. Front page says "12 Claims, No Drawings" and the spec is nonetheless full of
structures: p2 draws mevinolin (1a) and compactin (1b); Scheme 1 (pp3-6) is the (R)-(+)-alpha-
methylbenzylamine RESOLUTION - trans racemate, both diastereomeric amides, the [R-(R*,R*)] and
[S-(R*,R*)] lactones, then both sodium salts; Scheme 2 (pp5-8) numbered intermediates (3)(4)(5)(6);
p10 an Example structure. Every drawing SPECIFIC (Ph / CONHPh / PhNHOC abbreviations only, which
cxsmiles.py expands). Zero Markush.

### ACCEPT US4943590A — escitalopram (H. Lundbeck, 1990, 9 p, 702550 B)
"Pharmaceutically useful (+)-1-(3-dimethylaminopropyl)-1-(4'-fluorophenyl)-1,3-dihydroisobenzofuran-
5-carbonitrile and non-toxic acid addition salts thereof". 300-dpi CCITT. A RESOLUTION patent:
front page draws citalopram (formula I); spec p2 formula I and the diol formula II; Reaction
Scheme I (pp3-4) draws the diol, both Mosher (alpha-methoxy-alpha-trifluoromethylphenylacetyl)
diastereomeric esters, and then the (+) and (-) enantiomers of citalopram SEPARATELY, each with
its own stereo drawing; Reaction Scheme II (pp4-5) the mesylate ring-closure. The same 2D skeleton
drawn twice with mirrored configuration is the sharpest stereo test in the corpus.

### LESSON (correcting my own screen two entries above)
"N Claims, **No Drawings**" on a US front page means no formal DRAWING SHEETS. It says nothing
about structures printed inline in the specification. US5273995 and US4943590 both say
"No Drawings" and are full of them; US4879303 says the same and has none. The line is not a screen
- render the pages.

### ACCEPT US8524733B2 — deutetrabenazine (Auspex, 2013, 27 p, 2223459 B)  [THE DEUTERATED GAP]
"Benzoquinoline inhibitors of vesicular monoamine transporter 2". 300-dpi CCITT.
Front page and spec pp3-4 carry a genuine R1-R23 Markush (formula I) - so this is NOT a
Markush-free document - but the Markush is 2 drawings against a very large specific set:
- spec p2 draws TETRABENAZINE itself, labelled, specific.
- Example 1 (pp21-22) is the non-deuterated synthesis: 6,7-dimethoxy-3,4-dihydroisoquinoline,
  3-((dimethylamino)methyl)-5-methyl-hexan-2-one, the (2-acetyl-4-methyl-pentyl)trimethyl-
  ammonium iodide quaternary salt, then tetrabenazine.
- Example 2 (pp23-25) is the SAME route run with d6-iodomethane: d6-(E)-1,2-dimethoxy-4-(2-
  nitrovinyl)benzene, 2-(3,4-d6-dimethoxyphenyl)ethanamine, 6,7-d6-dimethoxy-3,4-dihydro-
  isoquinoline, ending in deutetrabenazine. The two examples are the SAME skeleton with and
  without D - a controlled isotope pair.
- pp26-32: a gallery of ~50 explicitly deuterated analogues, each with the D atoms DRAWN as
  labels on specific ring and methyl positions. Not Markush - every position is committed.
Expect most gallery compounds to be unscoreable (hypothetical analogues, not in PubChem); that is
the accepted outcome for synthesis/analogue content and it is what the macrocycle paper already
does. The scoreable core is tetrabenazine + deutetrabenazine + the four named intermediates.
NEW recognition test nothing in the corpus has: reading `D` as deuterium rather than as a
generic atom label.

### REJECT US4346227A — pravastatin/ML-236B (Sankyo, 1982, 23 p, 1512348 B)
Fetched and validated (23 p, 300-dpi CCITT, "25 Claims, 5 Drawing Figures"). Rejected on the
Markush rule plus duplication: formulae (I)-(X) across spec pp1-8 and the claims pp21-24 all carry
R1 ("wherein R1 represents a hydrogen atom or a C1-C5 alkyl group") and formula (I) additionally
says "wherein R represents a group of formula". The only specific drawings are ML-236B
(mevastatin) as lactone and as the ring-opened acid, three drawings in 23 pages - and that is the
same 1980s Japanese/US hand-inked statin art the corpus already has in US4231938A lovastatin.
pp2-4 are five NMR/IR spectra (Figs 1-5), which would be useful negatives, but not at this price.
Worth recording: p23 is a CERTIFICATE OF CORRECTION that redraws a structural formula inside the
certificate box - a genuinely odd page type, if anyone ever wants one.

### REJECT US3904682A — naproxen (Syntex, 1975, 18 p, 2352506 B)
Fetched and validated (18 p, 300-dpi CCITT, "2 Claims, No Drawings"). Rejected on selection rule 1,
unambiguously: every drawing in the document carries R1/R2/R3/R4/R11/"Alkyl" - formula (I) and
formulae (A) and (C)-(M) and (P)(Q)(R) in the reaction sequences on spec pp5-10. Naproxen itself
is never drawn as a specific structure; it appears only as the title text
"2-(6'-methoxy-2'-naphthyl)acetic acid". A textbook Markush trap: the schemes LOOK like specific
synthesis art at a glance and are generic at every position.

### ACCEPT DE60100786T2 — citalopram crystalline base (Lundbeck, DPMA 2004, 10 p, 179024 B)  [NON-ENGLISH GAP]
"Kristalline Base von Citalopram, und Hydrochlorid- oder Hydrobromidsalz davon" - the German
translation (DE ... T2) of EP 1 227 088 B1, published by the Deutsches Patent- und Markenamt.
- **The Latin-script non-English document the corpus lacked.** Whole specification is German,
  including the substituent prose ("worin Z Halogen, -O-SO2-(CF2)n-CF3 ... ist") and the tables
  ("Tablettengehalt", "Zerbroeckelbarkeit"). Separates "non-English" from "CJK layout", which is
  all CN108503621B could test.
- **A FOURTH patent PDF class**: Acrobat Distiller 5.0.5 vector text with the structures inserted
  as 300-302 ppi CCITT **stencil** clippings (pdfimages type `stencil`, not `image`) - against the
  US files' full-page 300-dpi CCITT rasters, EP0641330B1's 300-dpi CCITT clippings, and
  CN108503621B's 150-ppi indexed rasters.
- 9 clippings on pp2,3,4,7,8,9. Specific drawings: citalopram (formula I) on p2 and p3, and a
  1-butyl-3-methylimidazolium hexafluorophosphate IONIC LIQUID on p4 drawn with N+ and a separate
  PF6- - the corpus's first inorganic counter-anion. Generic: formula (II) with a Z substituent,
  on p3 and again in the claims p9. pp7-8 are four tablet-formulation TABLES (non-structure).
- Pairs with US4943590A: same molecule, same applicant, two languages, two document classes,
  two drawing styles. p10 prints "Es folgt kein Blatt Zeichnungen".
- Honest limitation: only 3 specific drawings in 10 pages. Cheap style/language probe, not a
  structure-rich document.

### REJECT DE602005004834T2 — methylphenidate synthesis (Ipca, DPMA 2009, 6 p, 182174 B)
German, same DPMA T2 class, "Ein verbessertes Verfahren fuer die Synthese von Methylphenidaten und
Zwischenprodukten". Real PDF, verified. Rejected on density: `pdfimages -list` finds exactly TWO
300-ppi stencils in 6 pages. Strictly dominated by DE60100786T2 (9 clippings in 10 pages).

### REJECT DE69929462T2 — sertraline hydrochloride Form V (Teva, DPMA 2006, 14 p, 226926 B)
German T2, same class. Rejected unseen-in-detail on the same density argument: the Google Patents
record exposes ONE chemical-structure image plus a table image for 14 pages.

### REJECT US4517359A — azithromycin (Pliva, 1985, 6 p, 520127 B)
6 pages, 300-dpi CCITT, and a tempting title (the full IUPAC name of one specific macrolide).
Rejected on selection rule 1: both drawings are generic - formula (1) is the erythromycin skeleton
with R1-R5 ("wherein R1 stands for methyl, whereas R2, R3, R4 and R5 ... stand for hydrogen atoms,
C1-C3 alkanoyl groups") and formula (2) is R6-O-CO-O-R7. Examples 1-11 are text only.

### REJECT US4199569A — ivermectin / C-076 (Merck, 1980, 10 p, 1333737 B)
Rejected on selection rule 1: the avermectin macrolide is drawn twice (spec pp1-2 and pp3-4) but
both drawings carry R1/R2/R3 keyed to an A1a/A1b/A2a/A2b/B1a/B1b/B2a/B2b variant TABLE, and the
oleandrose disaccharide is drawn under "wherein R is the 4'-(alpha-L-oleandrosyl)-alpha-L-
oleandrose group". The catalyst is written as the generic [(R4)3P]3RhX. Nothing specific.

### FINDING: the 1970s-80s "specific structure" gap is structurally hard
Four 1970s-80s candidates were fetched and rendered this round (US4346227 pravastatin 1982,
US3904682 naproxen 1975, US4517359 azithromycin 1985, US4199569 ivermectin 1980) and every one is
Markush-dominated. That era's chemical patents claim genera. US4231938A lovastatin is in the corpus
precisely because a FERMENTATION product has no genus to claim - so the way to find more old
specific-structure art is to look for isolated natural products, not for drug classes.

### ACCEPT US4117118A — cyclosporin (Sandoz, 1978, 17 p, 1195115 B)  [PRE-1980 + LARGEST DEPICTION]
"Organic compounds" - the original cyclosporin isolation patent. pp2-7 are FIG 1-6 (UV, IR, 90 MHz
1H NMR of S 7481/F-1 and F-2), six built-in negatives. p8 draws S 7481/F-1 and p9 draws S 7481/F-2
as complete cyclic undecapeptides, every atom spelled out, stereo carried ONLY by a printed D, L or
R beside each alpha carbon - not one wedge in either drawing. Cyclosporin A is 85 heavy atoms in a
single connected object filling half a page: the largest depiction in the corpus.
**IDENTITY CONFLICT, recorded not resolved.** The text names F-1 = cyclosporin A and F-2 =
cyclosporin B ([Ala2]CsA). At 300 dpi BOTH drawings carry a CH2-CH3 (Abu) side chain at the residue
between MeBmt and sarcosine, which is cyclosporin A's residue 2. And the empirical formula the
document prints for F-1, C61H109N11O12, is PubChem's formula for cyclosporin B (CID 12797522), not
for A (C62H111N11O12, CID 5284373). Name, formula and drawing disagree pairwise. F-1 is scored
against cyclosporin A because the DRAWING is unambiguous; F-2 is drawn-but-not-scored.
Attempts made before giving up: 300-dpi crops of the matching residue in both drawings (identical),
and an IoU alignment sweep of the two structure regions (best IoU 0.028 - the scans are offset
enough that pixel differencing carries no signal). Recorded as a genuine open question.

### INGESTIBILITY PROOF (the only pipeline run of this round)
1. `pdf2image.convert_from_path(pdf, 300)` - the exact call stage 1 makes - on page 1 of all six
   accepted files: all load, RGB, 2320x3408 / 2560x3300 (US), 2480x3509 (DE). 0.1-0.4 s each.
2. One real end-to-end run, `--local --device cpu`, on a 3-page ghostscript slice of
   DE60100786T2 (original pp2-4, all three figure-bearing), with
   `DECIMER_WEIGHTS=/root/cmage-models/decimer/mask_rcnn_molecule.h5`:
   **stage 1 = 30.96 s (10.3 s/page), stage 2 = 16.48 s, stage 3 = 19.19 s, wall ~67 s.**
   4 figures -> 4 segments -> 4 CXSMILES, all four classified High Confidence, low-confidence
   sheet empty. Results:
   - orig p2 citalopram -> `CC1=CC=C2C(COC2(CCCN)c2ccc(C)cc2)C1` at **0.899** - WRONG: nitrile and
     fluorine both read as methyl, NMe2 read as NH2, and a ring invented. The single highest
     confidence in the run is the single worst answer, exactly as FINDINGS.md describes.
   - orig p3 citalopram -> `*c1ccc2c(c1)COC2(CCCN(C)C)c1ccc(F)cc1 |$NC;...$|` at 0.869 - correct
     modulo the nitrile being carried as a CXSMILES abbreviation label, which cxsmiles.py expands.
     Same molecule, same document, near-identical depiction, one right and one wrong.
   - orig p3 formula (II), the GENERIC one -> the same skeleton with `|$Z;...$|`: the Markush
     placeholder is carried through verbatim as a CXSMILES label. Useful and slightly surprising.
   - orig p4 imidazolium -> `CCCC[N+]1=CN(C)CC1` at 0.872: right connectivity, ring read as partly
     saturated, and **the PF6- counterion dropped entirely** - the counterion test firing on its
     first contact with the pipeline.
   Stage 1 at 10.3 s/page is ~6x cheaper than the 64 s/page model, which agrees with round three's
   note that the model badly overestimates VECTOR documents. The five raster files in this round
   are the class the 64 s figure came from, so their estimates should be nearer the mark.

## RANKED VERDICT (run order), cost from the measured model

Cost columns: `measured` = pages x 64 s, the figure-bearing rate applied to every page;
`mixed` = figure_bearing x 64 s + text_only x 703 s. Round three recorded a 50x overshoot of this
model on a VECTOR document, and my own 3-page probe this round measured 10.3 s/page on a vector
document, so treat both columns as UPPER BOUNDS - with the caveat that five of these six files are
full-page RASTER scans, which is the document class the 703 s datum actually came from.

| # | file | p | fig p | scored | measured | mixed | why this position |
|---|---|---|---|---|---|---|---|
| 1 | US4943590A_escitalopram | 9 | 6 | 8 | 0.16 h | 0.69 h | cheapest structure-rich file; fires two distinct tests at once (enantiomer pair, condensed side chains) |
| 2 | US5273995A_atorvastatin_calcium | 10 | 8 | 8 | 0.18 h | 0.53 h | drawn Ca(2+) and a drawn enantiomer pair; lowest text-page overhead in the round |
| 3 | US7326708B2_sitagliptin_phosphate | 15 | 12 | 12 | 0.27 h | 0.80 h | biggest single contribution to the denominator, plus five built-in negatives |
| 4 | DE60100786T2_citalopram_german | 10 | 6 | 2 | 0.18 h | 0.89 h | only 2 scored, but the only non-English Latin-script document and the only new PDF class; 3 of its pages are already run |
| 5 | US8524733B2_deutetrabenazine | 27 | 20 | 9 | 0.48 h | 1.72 h | the deuterium test is unique, but 3x the run of the files above and ~140 of its ~160 drawings are unscoreable |
| 6 | US4117118A_cyclosporin | 17 | 8 | 1 | 0.30 h | 1.90 h | 1 scored molecule for 17 pages. Run last. Its value is stylistic - D/L-letter stereo, an 85-heavy-atom single object, six spectra negatives - not recall |
| | **total** | **88** | **60** | **40** | **1.57 h** | **6.53 h** | |

The mixed figure is dominated by 28 text-only pages at 703 s each = 5.47 h of the 6.53 h. The
skill's own advice applies: strip the text-only pages before stage 1 and the whole round costs
**60 x 64 s = 1.07 h**. Doing that also removes the only pages that can produce a false positive
without a corresponding negative control, so it is not free - keep the text pages for the
false-positive measurement and drop them for the recall measurement.

Budget: 6,343,556 bytes = **6.05 MB** against a 30 MB ceiling. Disk unchanged at 82%.
