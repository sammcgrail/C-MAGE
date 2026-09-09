# Test-input PDFs for C-MAGE (VisualHeist -> DECIMER -> SMILES)

Four granted US small-molecule pharmaceutical patents, each a composition-of-matter /
medicinal-chemistry document with drawn skeletal formulae (Markush structures, intermediates,
reaction schemes, explicit compound drawings). All four were downloaded 2026-09-08, verified
as real PDFs (`file` -> application/pdf, `%PDF-1.3` magic), page-counted with `pdfinfo`, and
rendered with `pdftoppm` and inspected page by page to confirm the structure drawings.

Nature of the files (same for every Google Patents / USPTO document, any year): each page is one
300-dpi CCITT bitonal raster image (2320x3408 or 2560x3300 px) with an invisible OCR text layer
(Producer: ImageMagick). The drawings are therefore 300-dpi raster, not vector. No patent office
distributes vector patent PDFs, so this is the best available form for a patent test set.

Retrieval route that works: fetch `https://patents.google.com/patent/<ID>/en` with a browser
User-Agent and read the `<meta name="citation_pdf_url">` tag; it carries the hashed
`patentimages.storage.googleapis.com/xx/yy/zz/<hash>/<number>.pdf` path. The bare
`patentimages.../pdfs/<ID>.pdf` form and the USPTO `image-ppubs.uspto.gov/dirsearch-public/
print/downloadPdf/<number>` endpoint both return 403 to curl.

Licence / why free: published US patents are public records. The USPTO and Google Patents serve
the full documents to anyone without registration, and patent documents are not subject to
copyright as such (where an applicant includes a copyright notice under 37 CFR 1.71(e) it must
authorise facsimile reproduction of the patent document). Redistributing the PDFs as test data is
unrestricted.

---

## 1. US6699871B2_sitagliptin.pdf  (23 pages, 2,567,404 bytes, sha256 03a602f0a8228a94...)
- Patent: US 6,699,871 B2, granted 2004-03-02 (filed 2002-07-05). Assignee: Merck & Co., Inc.
- Title: "Beta-amino heterocyclic dipeptidyl peptidase inhibitors for the treatment or prevention
  of diabetes" (the sitagliptin / Januvia composition-of-matter patent).
- Source URL (PDF): https://patentimages.storage.googleapis.com/b2/13/04/e3584e05f9fb57/US6699871.pdf
- Record page: https://patents.google.com/patent/US6699871B2/en
- Structure drawings: Markush formulae I, Ia, Ib on pp. 2-4; dense explicit compound and
  intermediate drawings on pp. 9-22 (examples with Boc-protected beta-amino acids showing
  wedge stereochemistry, triazolopiperazine / imidazopyrazine cores, fluorinated phenyls);
  claims on pp. 19-22 carry Markush Ia/Ib/Ic plus explicit compound drawings. Page 23 is a
  Certificate of Correction (text only).

## 2. US6627754B2_tofacitinib.pdf  (14 pages, 1,560,172 bytes, sha256 42e8a774a82c37da...)
- Patent: US 6,627,754 B2, granted 2003-09-30 (filed 2000-12-08). Assignee: Pfizer Inc.
- Title: "Pyrrolo[2,3-d]pyrimidine compounds" (the tofacitinib / Xeljanz JAK-inhibitor patent).
- Source URL (PDF): https://patentimages.storage.googleapis.com/4d/4c/fa/c539613d1b0480/US6627754.pdf
- Record page: https://patents.google.com/patent/US6627754B2/en
- Structure drawings: abstract structure p. 1; Markush formula I p. 2-3; multi-step reaction
  schemes (Preparations A/B, Schemes 1-3) with arrows and numbered intermediates on pp. 6-7;
  Markush formulae I/II fragments in the claims on pp. 13-14. Pages 4-5 and 8-12 are text.

## 3. US7579449B2_empagliflozin.pdf  (38 pages, 3,539,338 bytes, sha256 9d2bc9b5cd30da41...)
- Patent: US 7,579,449 B2, granted 2009-08-25 (filed 2005-03-15). Assignee: Boehringer
  Ingelheim International GmbH.
- Title: "Glucopyranosyl-substituted phenyl derivatives, medicaments containing such compounds,
  their use and process for their manufacture" (the empagliflozin / Jardiance SGLT2 patent).
- Source URL (PDF): https://patentimages.storage.googleapis.com/bb/6e/db/4d1ca30f0ae63c/US7579449.pdf
- Record page: https://patents.google.com/patent/US7579449B2/en
- Structure drawings: Markush formula and sub-formulae pp. 4-7; synthetic schemes pp. 13-16;
  explicit intermediate drawings (TIPS-alkynyl aryl bromides etc.) pp. 19-24; a long two-column
  compound table ("Ex. / Structure") of C-aryl glucosides with wedge/hash stereochemistry on
  pp. 25-37 (about 10 structures per page). Page 38 is a Certificate of Correction.
  Best file in the set for testing stereo-bond recognition and table-embedded structures.

## 4. US6936612B2_palbociclib.pdf  (41 pages, 5,215,075 bytes, sha256 583cf2c2af171ae1...)
- Patent: US 6,936,612 B2, granted 2005-08-30 (filed 2003-01-16). Assignee: Warner-Lambert
  Company LLC (Pfizer).
- Title: "2-(Pyridin-2-ylamino)-pyrido[2,3-d]pyrimidin-7-ones" (the palbociclib / Ibrance
  CDK4/6 patent).
- Source URL (PDF): https://patentimages.storage.googleapis.com/21/cd/63/f2f69c1759732c/US6936612.pdf
- Record page: https://patents.google.com/patent/US6936612B2/en
- Structure drawings: abstract structure p. 1; Markush formula p. 2; explicit compounds pp. 6-7;
  reaction schemes 1-13 with generic R/X-substituted pyridopyrimidinones and arrows on
  pp. 13-17 (about 6-10 structures per page). Pages 18-41 are text-only examples and a data
  table; this file therefore also tests that the pipeline does not hallucinate structures on
  text pages.

---

### Candidates examined and rejected
- US6469012B1 (sildenafil use patent, 47 p): almost entirely citation lists plus a reexamination
  certificate; structures on only 4 pages.
- US5747498A (erlotinib, 26 p): structures on ~7 pages, remainder Markush prose; lower value.
- US6515117B2 (dapagliflozin, 16 p): good, but chemically duplicates the empagliflozin file.
- Too long to be worth a CPU-only run: US7157456B2 rivaroxaban 78 p, US7514444B2 ibrutinib 74 p,
  US8946235B2 osimertinib 86 p, US6573293B2 sunitinib 134 p, US6362178B1 vardenafil 146 p,
  US6251910B1 ticagrelor 51 p (not inspected).

### Optional extra (NOT copied into this directory)
If a journal-layout baseline is wanted, fetch this verified open-access article: Mishra et al., "Structure-Activity Relationship Studies in a
Series of 2-Aryloxy-N-(pyrimidin-5-yl)acetamide Inhibitors of SLACK Potassium Channels",
Molecules 2024, 29(23), 5494, doi:10.3390/molecules29235494, licence CC BY 4.0 (Europe PMC
record: isOpenAccess=Y, license "cc by"), 19 pages, downloaded from
https://europepmc.org/articles/PMC11643494?pdf=render. Vector text (pdfTeX) with structures
embedded as 600-dpi CCITT stencil images: Figure 1 on p. 3, schemes pp. 5-7, SAR tables with
drawn scaffolds pp. 8-13.

---

# Second survey (2026-09-09): style diversity and per-figure ground truth

The four patents above are all the same kind of object: a USPTO/Google Patents scan, 300-dpi
CCITT page raster, 2000s ChemDraw line art, and mostly Markush formulae whose R-groups make a
drawing unscorable. `benchmarks/FINDINGS.md` shows what the benchmark actually needs: figures
whose depicted molecule can be pinned to a PubChem CID, and drawing styles the corpus does not
yet have. This survey therefore looked for short (ideally under 10-page), redistributable
documents in styles the corpus lacks -- vector ChemDraw journal typesetting, hand-drawn input,
1980s hand-inked patent art, EPO's hybrid vector-text format, US-government vector line art --
and recorded a CID and PubChem SMILES for every expected structure in
`benchmarks/ground_truth/` (see `manifest.json` from the survey; machine-readable). Cost
estimate throughout: stage 1 at about 12 min/page on this CPU-only box.

Every file was checked the same way: HTTP status AND Content-Type AND size AND `%PDF-` magic
(`file` is not installed here, so `head -c 5`) AND `pdfinfo` page count AND at least one page
rendered with `pdftoppm` and looked at. The pipeline's own ingestion is
`pdf2image.convert_from_path(pdf, 300)`, i.e. the same `pdftoppm` render, so a file that
rendered here will be read the same way by stage 2.

Retrieval routes (all verified with plain curl + a browser User-Agent):
- Beilstein JOC: `https://www.beilstein-journals.org/bjoc/content/pdf/1860-5397-<vol>-<art>.pdf`
  (200, application/pdf, no cookie wall).
- Anything in PMC, including MDPI and Springer/BMC titles: `https://europepmc.org/articles/PMC<id>?pdf=render`
  (302 then 200 application/pdf). MDPI's own `/pdf` endpoint returns 403 to curl.
- NTP Report on Carcinogens profiles: `https://ntp.niehs.nih.gov/sites/default/files/ntp/roc/content/profiles/<name>.pdf`.
- Google Patents `citation_pdf_url` route (above) also works for 1960s-80s US patents and for EP B1 documents.

## Accepted (ranked by value per CPU-hour)

### 5. bjoc_21-197_aglacinB.pdf  (5 pages, 835,165 bytes, sha256 72e7ac6c8610...)
- Yao, Cao, Xiao, Wang, Peng, "Ni-promoted reductive cyclization cascade enables a total synthesis
  of (+)-aglacin B", Beilstein J. Org. Chem. 2025, 21, 2548-2552, doi:10.3762/bjoc.21.197.
- URL https://www.beilstein-journals.org/bjoc/content/pdf/1860-5397-21-197.pdf
- Licence: CC BY 4.0 (Beilstein-Institut Open Access License Agreement, stated in the "License and
  Terms" box on p. 5; identical to CC BY 4.0).
- Style: vector ChemDraw in Beilstein two-column typesetting; wedge/hash stereo; dense OMe labels.
- Structures: Figure 1 (p. 2) draws aglacins A, B, C and E; Schemes 1-3 (pp. 2-3) about 25 numbered
  intermediates; one X-ray ORTEP on p. 3 is a non-structure figure. About 30 drawings in 5 pages,
  the densest document found. Ground truth: aglacin A CID 11755236, B 10071343, C 11741714
  (E is not in PubChem). Cost about 1 h.

### 6. PMC9185882_decimer_handdrawn_dataset.pdf  (4 pages, 1,139,404 bytes, sha256 575475462672...)
- Brinkhaus, Zielesny, Steinbeck, Rajan, "DECIMER -- hand-drawn molecule images dataset",
  J. Cheminform. 2022, 14:36, doi:10.1186/s13321-022-00620-9. CC BY 4.0 (p. 1).
- URL https://europepmc.org/articles/PMC9185882?pdf=render
- Style: genuinely hand-drawn structures (pen on paper, scanned; and tablet) placed beside their CDK
  originals. Figure 1 (p. 2) is a 12-panel grid of unlabelled hand drawings; Figures 2 and 3 (p. 3) are
  labelled CDK_Depict_46_36 and CDK_Depict_45_18.
- Ground truth for Figs 2-3 was recovered without the Zenodo record (its API timed out): the drawings
  were transcribed to SMILES and submitted to PubChem's `fastidentity` search, which returned exactly
  one hit each -- CID 142705143 (5,6,6-trinitro-1,2-oxathiane) and CID 129067542 (tert-butyl
  (3S)-3-amino-5-methylsulfonylpent-4-ynoate; only the 3S enantiomer exists, matching the hashed
  bond). The dataset itself is CC BY 4.0 at doi:10.5281/zenodo.6456306 if the Fig 1 panels are wanted.
  Cost about 0.8 h.

### 7. bjoc_18-169_macarpine.pdf  (7 pages, 603,298 bytes, sha256 4288ce18ec71...)
- Fu, Li, Zhou, Cheng, Yang, Liu, "Formal total synthesis of macarpine via a Au(I)-catalyzed
  6-endo-dig cycloisomerization strategy", Beilstein J. Org. Chem. 2022, 18, 1589-1595,
  doi:10.3762/bjoc.18.169. CC BY 4.0 (p. 7).
- URL https://www.beilstein-journals.org/bjoc/content/pdf/1860-5397-18-169.pdf
- Why: CHARGED species with real ground truth. Scheme 1 (p. 2) classifies the benzo[c]phenanthridine
  alkaloids -- sanguinarine CID 5154, chelerythrine 2703, chelirubine 161243, chelilutine 443720,
  macarpine 440929, 10-hydroxysanguinarine 14655851, and the dihydro forms 124069 / 485077 -- all
  quaternary iminium cations drawn with N+. Schemes 2-6 and Tables 1-2 add about 25 more drawings
  (OTBS/OMe labels, Au-catalysed cyclisation substrates). About 35 drawings; cost about 1.4 h.

### 8. ntp_roc_basicred9.pdf, ntp_roc_adriamycin.pdf, ntp_roc_azacitidine.pdf  (2 pages each)
- NTP Report on Carcinogens, 15th edition (2021), substance profiles. US Government work
  (NIEHS/NTP, HHS): public domain.
- URLs https://ntp.niehs.nih.gov/sites/default/files/ntp/roc/content/profiles/{basicred9,adriamycin,azacitidine}.pdf
- Style: the only VECTOR line art in the corpus -- `pdfimages -list` reports no raster images at all;
  the structure is drawn with PDF paths in the header box next to the name and CAS number.
  Basic Red 9 is pararosaniline hydrochloride drawn as the NH2+ cation with a separate Cl- (CID 11292);
  Adriamycin is doxorubicin with six wedged stereocentres (CID 31703); azacitidine is a nucleoside
  with ribose stereo (CID 9444). One structure per file, so poor structures-per-hour, but 2 pages
  each (about 25 min) makes them the cheapest probe of the vector-page code path. Run basicred9 first.

### 9. US4231938A_lovastatin.pdf  (10 pages, 872,095 bytes, sha256 ef10096aa302...)
- US 4,231,938, Merck, granted 1980-11-04, "Hypocholesteremic fermentation products and process of
  preparation" (the lovastatin patent). Public record, same reasoning as the four patents above.
- URL https://patentimages.storage.googleapis.com/c9/33/a7/f3c16b72d538c3/US4231938.pdf
- Style: 1980 hand-inked line art with heavy wedge and hashed bonds, typeset labels, scanned at 300
  dpi. Explicit structures only: lovastatin (CID 53232) on pp. 1, 4, 6, 9 and its open hydroxy acid
  (CID 64727) on p. 4. Pages 2-3 are the NMR and IR spectra (the patent's two "drawing figures"):
  a figure that is not a structure, which stage 2 should reject. Cost about 2 h.

### 10. PMC13390035_patent_ocsr_benchmark.pdf  (8 pages, 2,996,547 bytes, sha256 0786d11aec05...)
- Tariq, Ylipaa, Jiang, Ryden, Andersson, "A Benchmark Evaluation of Chemical Structure Extraction
  from Patents", Chem. Res. Toxicol. 2026, 39, 1349-1356, doi:10.1021/acs.chemrestox.6c00057.
  CC-BY 4.0 (ACS open-access badge, p. 1).
- URL https://europepmc.org/articles/PMC13390035?pdf=render
- Why: the same task on the same kind of input. Figure 3 (p. 4) shows six EPO patent crops all three
  tools got right, four of them PubChem-resolvable (tert-butyl N-(3,5-dimethoxyphenyl)carbamate
  CID 10634629, 1,1-dimethylguanidine, cyclohexyltrimethoxysilane CID 10998130, a perfluoro acid);
  Figure 4 pairs Markush inputs with MolScribe re-depictions; Table 2 (p. 5) is a multi-panel
  input/DECIMER/MolScribe/Mathpix grid. The graphical abstract prints the answer SMILES
  (`n1ccn2CCCn2c1`) beside two deliberately wrong ones. Cost about 1.6 h.

### 11. bjoc_19-15_pheromones.pdf  (9 pages, 382,253 bytes, sha256 c44cd5b3135d...)
- Gayon, Lefevre, Guerret, Tintar, Chourreu, "Total synthesis of insect sex pheromones: recent
  improvements based on iron-mediated cross-coupling chemistry", Beilstein J. Org. Chem. 2023, 19,
  158-166, doi:10.3762/bjoc.19.15. CC BY 4.0 (p. 9).
- URL https://www.beilstein-journals.org/bjoc/content/pdf/1860-5397-19-15.pdf
- Why: E/Z double-bond geometry on skinny acyclic chains, a stereo class no wedge-bond document tests.
  Ground truth: (8E,10Z)-tetradeca-8,10-dienal CID 5352448, (E)-dodeca-9,11-dienyl acetate 5367504,
  (7E,9Z)-dodeca-7,9-dienyl acetate 1794807, codlemone 1787910, sorbic acid 643460. About 25
  drawings including Grignard and enol-phosphate reagents; cost about 1.8 h.

### 12. PMC11227129_decimer_handdrawn_caffeine.pdf  (11 pages, 1,546,844 bytes, sha256 6fe4cc823983...)
- Rajan, Brinkhaus, Zielesny, Steinbeck, "Advancements in hand-drawn chemical structure recognition
  through an enhanced DECIMER architecture", J. Cheminform. 2024, 16:78,
  doi:10.1186/s13321-024-00872-7. CC BY 4.0 (p. 1).
- URL https://europepmc.org/articles/PMC11227129?pdf=render
- Why: in-document SMILES (the graphical abstract on p. 2 and Fig. 1 on p. 4 print
  CN1C=NC2=C1C(=O)N(C(=O)N2C)C next to the drawing) and a multi-panel Figure 2 (p. 6) of synthetic
  hand-drawn-style caffeine depictions on paper and grid backgrounds. Every panel is caffeine
  (CID 2519), which isolates depiction variance from molecule variance. Only 3 of 11 pages carry
  figures; cost about 2.2 h.

### 13. EP0641330B1_pregabalin.pdf  (22 pages, 291,555 bytes, sha256 fce7abe43a63...)
- EP 0 641 330 B1, Northwestern University, granted 2001-10-17, "GABA and L-glutamic acid analogs
  for antiseizure treatment" (the pregabalin patent). EPO patent specification: an official
  publication, free of copyright under EPC-state law and served without restriction by Google Patents.
- URL https://patentimages.storage.googleapis.com/3f/a1/3b/5d27f2d370c6f1/EP0641330B1.pdf
- Why: a different PDF type from everything above. EPO B1 documents from about 1998-2004 are
  VECTOR text (embedded Arial) with the structures inserted as small 300-dpi CCITT clippings
  (`pdfimages -list`: 15 images on pp. 1, 4, 6, 14-21). The clippings are Charts I, Ia, II ... :
  reaction schemes with explicit numbered intermediates (4-methylpentanoic acid, its acid chloride,
  an Evans oxazolidinone with wedge stereo, azides, ending in pregabalin, CID 5486971). This is the
  page type modern journal PDFs also use, and 22 pages is the shortest hybrid-format EP document
  found for a named drug. About 60 structures across the clippings; cost about 4.4 h -- run last.

## Deferred (good, but over the page budget)
- PMC10180415 -- Molecules 2023, 28, 3651, "New approved drugs appearing in the pharmaceutical market
  in 2022 featuring fragments of tailor-made amino acids and fluorine", CC BY 4.0, 21 pages,
  https://europepmc.org/articles/PMC10180415?pdf=render. About 14 pages of named 2022 FDA approvals
  in ChemDraw with syntheses: the best named-drug ground truth seen, at about 4.2 h.
- PMC11771699 -- Arch. Pharm. 2025, e2400890, "FDA-approved drugs featuring macrocycles or
  medium-sized rings", CC BY 4.0, 24 pages, https://europepmc.org/articles/PMC11771699?pdf=render.
  Very dense macrocycle, peptide and metal-chelate structures with colour ring highlights; about 4.8 h.

## Candidates examined and rejected (second survey)
- US4255431A omeprazole (Haessle 1981, 13 p): about 18 clean line-art drawings, but every one is a
  generic formula with R1-R5 -- the abstract structure and the claims are the Markush too, and all
  explicit compounds are named in text only. Nothing to score.
- US3385886A ibuprofen (Boots 1968, 7 p): three typeset ring formulas; what looks like a scheme on
  pp. 3-4 is typewritten condensed formulae (R4.Ph.CH2.COOH), not drawings.
- US4046889A captopril (Squibb 1977, 11 p), US4314081A fluoxetine (Lilly 1982, 11 p), US4199574A
  acyclovir (Wellcome 1980, 18 p): six to eight generic drawings each, examples all text.
- US3136815A diazepam (1964, 27 p) and US3950333A cimetidine (1976, 39 p): too long; not inspected.
- EP0564409B1 imatinib (2000, 32 p): same hybrid format as the pregabalin file but 20 clippings in
  32 pages, nearly all Markush I/II/IV/V. EP0463756B1 sildenafil (37 p), EP0454436B1 olanzapine
  (25 p), EP0717738B1 linezolid (21 p): 1990s whole-page JBIG2 A4 rasters, nothing the US files do
  not already cover. EP0759917B1 oseltamivir: 269 pages.
- bjoc.21.47 (+/-)-simonsol C (6 p): as dense as the aglacin paper, but simonsol C/F/G, fargenone A
  and fargenin are not in PubChem, so there is no ground truth, and the style is already covered.
- PMC7541205, 2020 OCSR tools review (13 p): text, tables and one bar chart.
- PMC12114780 (42 p), PMC13023470 (39 p), PMC9416721 (25 p): approved-drug reviews rejected on length.
- NTP profiles not taken: aflatoxins (3 p, no drawing at all), nitroarenes (five nitro-PAHs but spread
  over 9 pages), benzidine / dimethylbenzidine / dimethoxybenzidine "and dyes" (only the parent amine
  is drawn; the sulfonated azo dyes are text), aristolochic acids (one drawing in 5 pages);
  chloramphenicol and diethylstilbestrol are fine drawings at 3 pages each if more vector probes are wanted.
- Not pursued: EPA pesticide fact sheets (probe URL 404; site restructured), FDA labels (label text
  is the sponsor's, licence unclear), WHO INN lists (CC BY-NC-SA, non-commercial clause).
---

# Third survey (2026-09-09): named-drug ground truth, metal centres, non-English, hard negatives

Round two produced 11 usable documents and two selection rules. Both rules were then partly
superseded by `benchmarks/FINDINGS.md` finding 3: CXSMILES abbreviation labels ARE scoreable now
(`benchmarks/cxsmiles.py` expands them at comparison time), so the objection to total-synthesis
papers is narrower than first written -- their intermediates are unscoreable because they have no
REFERENCE, not because they are abbreviated. The Markush rule stands unchanged and did real work
again this round.

This survey targeted the six gaps round two left: documents with many specific named
non-abbreviated structures, metal centres, peptides and macrocycles drawn in full, tables of
analogues on a shared scaffold, non-English documents, and hard negatives whose figures are not
chemical structures. Seven documents accepted, 59 molecules, all 59 PubChem-resolved, 12.36 MB.

Every file was checked the same way as before: HTTP status AND Content-Type AND size AND `%PDF-`
magic AND `pdfinfo` page count AND every page rendered with `pdftoppm` at 100 dpi and looked at,
plus `pdfimages -list` to establish whether the drawings are vector or raster and at what ppi.

## Accepted

### 14. PMC10180415_approved2022_aa_fluorine.pdf  (21 pages, 3,411,099 bytes, sha256 d1210b112b14...)
- Wang, Mei, Dhawan, Zhang, Han, Soloshonok, "New Approved Drugs Appearing in the Pharmaceutical
  Market in 2022 Featuring Fragments of Tailor-Made Amino Acids and Fluorine", Molecules 2023, 28,
  3651, doi:10.3390/molecules28093651. CC BY 4.0 (MDPI, stated p1).
- URL https://europepmc.org/articles/PMC10180415?pdf=render
- Deferred in round two on page count alone; reconsidered because stage 1 costs ~64 s per
  figure-bearing page, so 21 pages is minutes.
- ZERO Markush drawings in the whole document. 12 named 2022 FDA approvals, all PubChem-resolvable:
  adagrasib 138611145, lenacapavir 133082658, oteseconazole 77050711, vonoprazan 15981397,
  177Lu vipivotide tetraxetan 122706785, mavacamten 117761397, daridorexant 91801202,
  gadopiclenol 16223405, omidenepag isopropyl 44230999, omidenepag 44230575, taurursodiol 9848818,
  sodium phenylbutyrate 5258.
- Fills three gaps at once: named drugs (Fig 1 p2, Fig 2 p3), the corpus's FIRST METAL CENTRES
  (a 177Lu-DOTA chelate and a Gd-PCTA chelate, both drawn with the metal inside the ring), and a
  full solid-phase PEPTIDE synthesis with resin beads (Scheme 5, p10).
- ~85 drawings, 13 figure-bearing pages of 21.

### 15. PMC11771699_macrocycle_drugs.pdf  (24 pages, 6,067,188 bytes, sha256 3844e88c71fd...)
- Du, Semghouli, Wang, Mei, Kiss, Baecker, Soloshonok, Han, "FDA-approved drugs featuring
  macrocycles or medium-sized rings", Arch. Pharm. 2025, 358, e2400890, doi:10.1002/ardp.202400890.
  CC BY (stated in the p1 footer).
- URL https://europepmc.org/articles/PMC11771699?pdf=render
- Also deferred in round two on page count. The densest named-drug document found anywhere.
- 19 resolvable named drugs: Fig 1 p2 is five cyclic METAL complexes (177Lu dotatate 76966897,
  64Cu dotatate 124220636, 177Lu vipivotide tetraxetan 122706785, gadopiclenol 16223405,
  flotufolastat F 18 gallium 166177191); Fig 2 p3 is five cyclic PEPTIDES (lurbinectedin 57327016,
  setmelanotide 11993702, voclosporin 6918486, terlipressin 72081, rezafungin 78318119); Fig 3 p3 is
  seven more (lorlatinib 71731823, moxidectin 9832912, rifamycin SV 6324616, lefamulin 58076382,
  pacritinib 46216796, clarithromycin 84029, repotrectinib 135565923) plus vonoprazan 15981397 and
  amoxicillin 33613.
- Only COLOURED depictions in the corpus: every macrocyclic ring is overprinted in red, blue or
  orange, and coordination bonds to the metal are drawn DASHED.
- ~150 drawings, 17 figure-bearing pages of 24. Schemes 1-17 are dense in Boc/Fmoc/tBu/Trt/Acm/Pbf
  intermediates; expect most of them to be unscoreable, which is the expected and acceptable outcome
  for synthesis content.

### 16. ntp_roc_cisplatin.pdf  (2 pages, 134,313 bytes, sha256 a01b6e61e788...)
- NTP Report on Carcinogens, 15th edition (2021), substance profile: Cisplatin. US Government work
  (NIEHS/NTP, HHS), public domain.
- URL https://ntp.niehs.nih.gov/sites/default/files/ntp/roc/content/profiles/cisplatin.pdf
- Pure vector line art (`pdfimages -list` reports zero raster images), identical layout to the three
  NTP files already in the corpus -- a single-variable comparison. One drawing: square-planar Pt(II)
  with explicit Pt, 2 Cl, 2 NH3.
- Resolve by the printed CAS 15663-27-1 -> CID 5460033. Do NOT resolve by name: "cisplatin" returns
  CID 5702198 "azane;dichloroplatinum", and CID 441203 is the TRANS isomer.
- Already run end to end (see below): 0 of 1.

### 17. ntp_roc_pahs.pdf  (9 pages, 382,372 bytes, sha256 93ba10800d41...)
- NTP Report on Carcinogens, 15th edition (2021): Polycyclic Aromatic Hydrocarbons: 15 Listings.
  US Government work, public domain.
- URL .../roc/content/profiles/polycyclicaromatichydrocarbons.pdf
- The table-of-analogues layout the corpus lacked, and the purest skeleton-reading test available:
  pp1-2 draw 15 fused-ring aromatics in a two-column list, each with name and CAS, no abbreviations,
  no stereo, no charges. Four are C20H12 isomers and four are C24H14 isomers, so the test is entirely
  about ring-fusion position. CIDs: 5954, 9153, 9152, 9158, 2336, 9183, 9177, 5889, 9134, 9126, 9108,
  9106, 9119, 9131, 19427.
- Only 2 of 9 pages carry drawings, so the run cost is dominated by the text pages.

### 18. ntp_roc_heterocyclicamines.pdf  (5 pages, 188,698 bytes, sha256 5756d3816201...)
- NTP RoC 15th ed.: Heterocyclic Amines (Selected). US Government work, public domain.
- URL .../roc/content/profiles/heterocyclicamines.pdf
- Smaller companion to the PAH file: MeIQ 62274, MeIQx 62275, IQ 53462, PhIP 1530 -- four analogues
  on one 2-aminoimidazo-fused scaffold, drawn pp1-3. Optional; drop this one first if trimming.

### 19. CN108503621B_vonoprazan.pdf  (11 pages, 754,825 bytes, sha256 e05494da622c...)
- CN 108503621 B, "Preparation method of vonoprazan fumarate", CNIPA, granted 2018-09-07 /
  published 2021-09-14. Published patent document, public record; same basis as the US and EP files.
- Record https://patents.google.com/patent/CN108503621B/en
- PDF https://patentimages.storage.googleapis.com/3f/a1/a7/96daaa4952b1ff/CN108503621B.pdf
- The non-English gap. Whole document is Chinese, including the reagent labels ON the reaction
  arrows, so the layout and in-scheme text are language-dependent while the drawings are not.
- A THIRD patent PDF class: body text is vector (Producer iTextSharp) with the schemes inserted as
  150-ppi indexed raster clippings, against the US files' full-page 300-dpi CCITT rasters and
  EP0641330B1's 300-dpi CCITT clippings.
- Every drawing is a specific compound -- it is a process patent, not composition-of-matter, so
  there is no Markush anywhere. 8 resolvable: vonoprazan fumarate 45375887, vonoprazan 15981397,
  fumaric acid 444972, the pyrrole-3-carbaldehyde 86232932, the pyrrole-3-carbonitrile 141403376,
  pyridine-3-sulfonyl chloride 3164136, 5-(2-fluorophenyl)-1H-pyrrole-3-carbonitrile 46908592,
  2'-fluoroacetophenone 96744.
- Carries its own negative control: pp10-11 are four HPLC chromatograms with peak tables.
- Resolution caveat, recorded rather than assumed away: 150 ppi is below the corpus's 300-dpi
  preference, but one molecule occupies about 290x200 source px, i.e. ~580x400 px once the pipeline
  renders the page at 300 dpi -- above the ~300 px floor at which the phantom I/[HH] artifact appears.
  Verified by extracting the p4 clipping and reading it.

### 20. PMC12548288_negative_gromacs_metadump.pdf  (10 pages, 1,425,805 bytes, sha256 9b390a388e91...)
- Rosinec et al., "Gromacs MetaDump: a tool for extracting GROMACS simulation metadata",
  J. Cheminform. 2025, 17:160, doi:10.1186/s13321-025-01082-5. CC BY 4.0 (BMC, stated p1).
- URL https://europepmc.org/articles/PMC12548288?pdf=render
- HARD NEGATIVE, and a controlled one: same journal and the same Springer/BMC typesetting as
  PMC11227129 and PMC9185882 already in the corpus, so it varies figure CONTENT while holding
  document style fixed. Zero chemical structures in 10 pages. Fig 1 a schema box diagram, Figs 2-4
  code and JSON listings, Fig 5 a flowchart of boxes, diamonds and arrows (the maximally confusable
  case), Figs 6-7 pie charts, bar charts and histograms.
- n_expected = 0 by construction. Anything it emits is a false positive; it must NOT be added to any
  recall denominator.

## Candidates examined and rejected (third survey)
- PMC12771797 (All-atom protein sequence design, J. Cheminform, 15 p, 5.12 MB, CC BY): fetched as a
  hard-negative candidate, rejected on content -- Fig 1 p3 draws ring structures labelled
  "invalid molecule!" and "valid molecule, but different from original". Not a clean negative.
- PMC12898835 (N-Heterocyclic Carbene Platinum Complexes review, Molecules, 39 p, 7.41 MB, CC BY):
  sought as a true M-C organometallic; rejected on length and size -- 7.41 MB is 30% of a 25 MB
  budget for complexes that are novel and therefore not PubChem-resolvable.
- PMC13148217 (Weil et al., two Pd-NHC complexes, Acta Cryst. 2026, E82, 426-431, 19 p, 4.98 MB,
  CC BY 4.0): sought as a true M-C organometallic; rejected on CONTENT, which is the more useful
  reason -- the only 2D drawing in the paper is a generic X-Pd-X with "X = Cl, Br", a Markush by
  another name. Everything else is 3D ORTEP and packing diagrams. Worth remembering that an Acta
  Cryst E paper with a SPECIFIC 2D scheme would make an excellent ORTEP-based hard negative.
- CN109232537B "Preparation method of vonoprazan" (26 p) and CN110590746B "Preparation method of
  low-impurity vonoprazan fumarate" (14 p): both verified as real PDFs, both rejected against
  CN108503621B -- one on length, one for duplicating the same chemistry with no new variable.
- NTP RoC nitroarenes (9 p): same layout and licence as the PAH profile but 5 analogues instead of
  15 across the same 9 pages. Strictly dominated.
- Beilstein J. Nanotechnol. probed as a hard-negative source (the /bjnano/content/pdf/2190-4286-V-N
  route returns 200): NOT pursued because the four articles probed were 3.4 to 13.0 MB each, which a
  25 MB budget cannot absorb for a document that contributes no ground truth.

## Still open after round three
- A true M-C ORGANOMETALLIC. Metal CENTRES are now covered six times (Pt, Gd, Lu, Cu, Ga) but all of
  them are coordination compounds. The blocker is specific and now known: papers reporting NEW
  complexes are not PubChem-resolvable, so selection rule 3 fails. The resolvable organometallics are
  the classic named catalysts -- Grubbs II is CID 11147261 and ferrocene is CID 10219726, both
  verified this round, while "Karstedt's catalyst" and "PEPPSI-IPr" both 404. Look for a short CC-BY
  paper that DRAWS those, not one that reports new ones.
- A JP or DE patent, to sit beside the CN one and separate "CJK layout" from "non-English layout".
- A pharmacopoeia monograph excerpt (the licence question was not resolved this round).
# Proposed addition to MERMaid/pdfdir/SOURCES.md

---

# Fourth survey (2026-09-09): patents only — salts, synthesis routes, deuterium, non-English

Round three closed the metal-centre, non-English-CJK and hard-negative gaps and left four open:
a synthesis route whose intermediates are specific and isolable, a salt or polymorph document that
draws the counterion, an old typewritten scan whose structures are not generic, and a Latin-script
non-English patent. This survey looked only at PATENTS, because a patent is a public record and
redistribution needs no licence argument. Six documents accepted, 88 pages, 6.05 MB, 41 catalogued
molecules of which 40 are PubChem-resolved. Nine candidates fetched and rejected.

**The round-1 retrieval route is dead from this box.** `patents.google.com/patent/<ID>/en` now
answers **HTTP 503, "your computer or network may be sending automated queries"**, so the
`citation_pdf_url` trick cannot be used with curl. Three routes that do work, all verified:

- **US documents: `https://patentimages.storage.googleapis.com/pdfs/US<number>.pdf`** — no kind
  code, no hash. 200, `application/octet-stream`, real `%PDF-`. Round one recorded this form as
  403; it is not, at least for US. Checked against two committed files: US4231938 gives 10 pages
  and US6699871 gives 23, matching. The bytes differ slightly from the hashed-path copies
  (871216 vs 872095 for US4231938), so it is a separately generated file, not a mirror. The same
  URL shape 403s for CN, EP, DE and JP.
- **Any country:** resolve the hashed `patentimages` path with a server-side fetcher instead of
  curl — that path is not rate-limited — then curl the hashed URL, which is not blocked either.
  Control: asking a fetcher for every `patentimages` URL on the CN108503621B record page returned
  exactly the hashed path already recorded in round three, so the method is not inventing URLs.
  When a fetcher answers NONE the document genuinely has no PDF (DE19942809A1, a withdrawn German
  application, is one).
- **EP documents: `https://data.epo.org/publication-server/rest/v1.2/patents/EP<number>NW<kind>/document.pdf`**
  — unauthenticated, and **no publication date is needed in the path**, unlike the date form.
  Byte-identical size to the committed EP0641330B1.pdf. `/rest/v1.2/publication-dates` lists every
  publication date and `/publication-dates/<YYYYMMDD>/patents` lists every document published that
  day (2343 B1s on one date), which makes the EP corpus browsable. Two traps: the server honours a
  `Range:` header only sometimes, so pipe through `head -c` rather than trusting a 206; and the
  root element's `lang` attribute is the only reliable language flag — the B540 title block always
  lists de/en/fr in that order regardless of the language of proceedings, and every B1 carries
  German and French CLAIMS, so a naive grep for `lang="de"` over a whole document matches
  everything.

## Accepted

### 21. US7326708B2_sitagliptin_phosphate.pdf  (15 pages, 1,277,699 bytes, sha256 29fac05a2cdf...)
- US 7,326,708 B2, Cypes et al., Merck & Co., granted 2008-02-05, "Phosphoric acid salt of a
  dipeptidyl peptidase-IV inhibitor" — the sitagliptin phosphate salt-and-polymorph patent.
- PDF https://patentimages.storage.googleapis.com/pdfs/US7326708.pdf
- The best file of the round, and it fills three gaps at once.
  **Salt:** the counterion is DRAWN. Formula I is sitagliptin plus a separate `.H3PO4`; the Example
  page draws the monohydrate as `.H3PO4 .H2O`; compound 1-4 is drawn with its own separate `HCl`.
  Free base, anhydrous salt and hydrate are three depictions differing only by dotted-off fragments.
  **Synthesis route:** Scheme 1 (p10) and Scheme 2 (p11) give eleven specific, isolable,
  individually named intermediates, every one PubChem-resolvable.
  **Built-in negatives:** pp2-6 are five instrument plots — XRPD, 13C CPMAS NMR, 19F MAS NMR, TGA,
  DSC. Anything emitted there is a false positive, in a document that is otherwise all positives.
- ZERO Markush. It is a process and salt patent, not composition-of-matter, so there is no genus.
- Two resolution traps recorded rather than smoothed over. `sitagliptin phosphate` by name AND
  CAS 654671-78-0 both return the MONOHYDRATE (CID 11591741); the anhydrous salt (CID 6451150) came
  only from a fastidentity SMILES search. And CAS 764667-64-3 for compound 2-3 returns CID 54711477,
  which is compound **2-2** — a wrong answer that happens to be another compound in the same scheme.
- Deliberately pairs with the round-one US6699871B2_sitagliptin.pdf: same drug, same scanner, one
  drawn as an R-substituted genus and one as a specific salt.

### 22. US5273995A_atorvastatin_calcium.pdf  (10 pages, 765,709 bytes, sha256 6bbed1fe2bb4...)
- US 5,273,995, Bruce D. Roth, Warner-Lambert, granted 1993-12-28 — the atorvastatin hemicalcium
  patent. PDF https://patentimages.storage.googleapis.com/pdfs/US5273995.pdf
- The salt gap done properly: p9 draws the CALCIUM salt with an explicit `Ca2+` outside a
  subscripted bracket and m.w. 1155.4 printed beside it, and p4 draws the same anion twice as the
  mono-sodium salt (`CO2Na`), once per enantiomer.
- It is simultaneously a RESOLUTION patent. Scheme 1 (pp3-4) runs the trans racemate through
  (R)-1-phenylethylamine and draws both diastereomeric amides and then both enantiomeric lactones
  side by side — a pipeline that drops stereo scores the same molecule twice. Scheme 2 adds four
  numbered intermediates and one bracketed Mg2+ enolate with dashed coordination bonds.
- Zero Markush; the only non-atom labels are Ph and CONHPh, which cxsmiles.py expands.
- Resolution trap: the [S(R*R*)] lactone is the ENANTIOMER of atorvastatin lactone, and a
  fastidentity `same_connectivity` search returns CID 49849495, the (2S,4R) DIASTEREOMER. Inverting
  every centre of CID 6483036 in RDKit and searching `same_stereo` gives the right record, 13923665.

### 23. US8524733B2_deutetrabenazine.pdf  (27 pages, 2,223,459 bytes, sha256 917bb8bc886a...)
- US 8,524,733 B2, Gant and Shahbaz, Auspex Pharmaceuticals, granted 2013-09-03, "Benzoquinoline
  inhibitors of vesicular monoamine transporter 2" — deutetrabenazine / Austedo.
- PDF https://patentimages.storage.googleapis.com/pdfs/US8524733.pdf
- The ISOTOPE gap, and a recognition mode nothing else in the corpus has: deuterium drawn as an
  explicit `D` atom label, 6 to 17 of them crowded onto one depiction.
- Examples 1 and 2 (pp13-14) are the SAME four-step synthesis run with CH3I and with CD3I —
  a controlled isotope pair on an identical skeleton, with every intermediate named and resolvable.
  pp15-26 then give a gallery of about 140 explicitly deuterated analogues, roughly 12 per page,
  every D position committed. Expect nearly all of the gallery to be unscoreable: they are
  hypothetical analogues and are not in PubChem. That is the accepted outcome for analogue content.
- NOT Markush-free, and it is listed anyway: formula I (R1-R23) appears on p1 and p4 and Schemes
  I and II on pp11-12 are generic. Four generic drawings against roughly 150 committed ones.
- PubChem's deutetrabenazine record (CID 73442840) really does carry the six `[2H]`, so the
  reference is isotope-aware even though the displayed formula collapses to C19H27NO3.

### 24. US4943590A_escitalopram.pdf  (9 pages, 702,550 bytes, sha256 c4eea8f65384...)
- US 4,943,590, Boegesoe and Perregaard, H. Lundbeck A/S, granted 1990-07-24 — the escitalopram
  patent. PDF https://patentimages.storage.googleapis.com/pdfs/US4943590.pdf
- Reaction Scheme I (p3) draws the racemic diol, both Mosher acid chlorides, both diastereomeric
  esters, potassium tert-butoxide, and then (+)- and (-)-citalopram SEPARATELY: the same 2D
  skeleton twice, differing only in one wedge and a printed sign. The sharpest stereo test here.
- Also a deliberate HARD POSITIVE for depiction style. The art is SEMI-CONDENSED — rings drawn as
  skeletons, side chains written as inline text on the bond (`CH2CH2CH2N(CH3)2`, `CH2OH`), reagents
  spelled out atom by atom (`KO-C(CH3)3`, `CH3-SO2-Cl`). This is close to the style round two
  rejected US3385886A ibuprofen for, and the difference matters: ibuprofen's schemes had no drawn
  ring system at all, whereas here every ring is drawn and only the chains are text. Expect low
  recall; that is the measurement, and it separates "cannot see the drawing" from "cannot read a
  condensed side chain".
- Resolution trap: CAS 64372-56-1 for the diol returns CID 10193515, a ring-closed carboxamide with
  the SAME molecular formula C20H23FN2O2 and a different structure. The IUPAC name and an
  independent SMILES identity search agree on CID 10132164. Formula agreement is not identity.

### 25. DE60100786T2_citalopram_german.pdf  (10 pages, 179,024 bytes, sha256 865fa1932cc2...)
- DE 601 00 786 T2, H. Lundbeck A/S, published by the Deutsches Patent- und Markenamt 2004-07-15,
  "Kristalline Base von Citalopram, und Hydrochlorid- oder Hydrobromidsalz davon" — the German
  translation of EP 1 227 088 B1.
- PDF https://patentimages.storage.googleapis.com/d2/ab/84/7ab1a1a0af00a6/DE60100786T2.pdf
- The Latin-script NON-ENGLISH gap. Whole specification in German, including the substituent prose
  ("worin Z Halogen, -O-SO2-(CF2)n-CF3 ... ist") and the table headers ("Tablettengehalt",
  "Zerbroeckelbarkeit"), so layout and in-figure text are language-dependent while the drawings are
  not — exactly what CN108503621B does for CJK, now with the CJK variable removed.
- A FOURTH patent PDF class: Acrobat Distiller 5.0.5 vector text with the structures inserted as
  300-302 ppi CCITT **stencil** clippings (`pdfimages -list` reports type `stencil`, not `image`),
  against the US files' full-page 300-dpi rasters, EP0641330B1's 300-dpi CCITT image clippings and
  CN108503621B's 150-ppi indexed rasters.
- First inorganic counter-anion in the corpus: a 1-butyl-3-methylimidazolium hexafluorophosphate on
  p4, drawn with an N+ on the ring and a separate PF6-.
- Honest limitation: only 3 specific drawings in 10 pages (citalopram twice, the ionic liquid once;
  formula II with a Z substituent is generic and appears twice). A cheap style-and-language probe,
  not a structure-rich document. It pairs with US4943590A — same molecule, same applicant, two
  languages, two PDF classes, two drawing styles. 179 kB is the cheapest file in the corpus.

### 26. US4117118A_cyclosporin.pdf  (17 pages, 1,195,115 bytes, sha256 c83a01ae7308...)
- US 4,117,118, Haerri, Ruegger, Dreyfuss and Kobel, Sandoz Ltd., granted 1978-09-26, "Organic
  compounds" — the original cyclosporin isolation patent.
- PDF https://patentimages.storage.googleapis.com/pdfs/US4117118.pdf
- Two properties nothing else has. **Size:** cyclosporin A is 85 heavy atoms drawn as one connected
  object filling half a page, by far the largest single depiction in the corpus and a direct test
  of whether the segmenter emits one structure or several. **Stereo as text:** a printed D, L or R
  beside each alpha carbon is the only configuration information in the drawing — there is not one
  wedge in it — and the R letters are an excellent trap, because an OCSR tool has every reason to
  read `R` as an R-group.
- pp2-7 are FIG 1-6, the UV, IR and 90 MHz 1H NMR spectra: six more built-in negatives.
- **Only one of its two structures is scored, and the reason is the most useful thing in this
  round.** The document draws F-1 and F-2 and says they are cyclosporins A and B. At 300 dpi both
  drawings carry a CH2-CH3 side chain at the residue between MeBmt and sarcosine, i.e. Abu, which
  is cyclosporin A's residue 2 — cyclosporin B is [Ala2]. And the empirical formula printed for
  F-1, C61H109N11O12, is PubChem's formula for cyclosporin **B** (CID 12797522), not for A
  (C62H111N11O12, CID 5284373). Name, formula and drawing are three identity signals and no two of
  them agree. F-1 is scored against cyclosporin A because the DRAWING is unambiguous; F-2 is
  recorded as drawn-and-not-scored. Settle it against the 1976 Helv. Chim. Acta papers the patent
  cites before adding it to any denominator.

## Candidates examined and rejected (fourth survey)

- **US4879303A amlodipine besylate** (Pfizer 1989, 4 p, 440,359 B): the ideal salt-versus-salt
  comparison on paper — one parent, seven counterions, four pages — and it contains no structures
  at all. Front page says "11 Claims, No Drawings" and Table 1 lists besylate, tosylate, mesylate,
  succinate, salicylate, maleate, acetate and hydrochloride as WORDS. Fetched, rendered, rejected.
- **US4346227A pravastatin / ML-236B** (Sankyo 1982, 23 p): formulae (I)-(XIII) across the spec and
  the claims all carry R1 ("a hydrogen atom or a C1-C5 alkyl group") and formula (I) additionally
  says "wherein R represents a group of formula". The only specific drawings are ML-236B as lactone
  and as the ring-opened acid — three in 23 pages, in the same 1980s hand-inked statin art
  US4231938A already provides. Its p23 is a Certificate of Correction that REDRAWS a structural
  formula inside the certificate box, which is a genuinely odd page type if anyone wants one.
- **US3904682A naproxen** (Syntex 1975, 18 p): a textbook Markush trap. The schemes on pp5-10 look
  like specific synthesis art at a glance and every position is R1/R2/R3/R4/R11/"Alkyl". Naproxen
  itself is never drawn.
- **US4517359A azithromycin** (Pliva 1985, 6 p): six pages and a title that is one compound's full
  IUPAC name, and both of its drawings are generic — formula (1) is the macrolide with R1-R5 and
  formula (2) is R6-O-CO-O-R7. The eleven examples are text.
- **US4199569A ivermectin / C-076** (Merck 1980, 10 p): the avermectin macrolide is drawn twice and
  both drawings carry R1/R2/R3 keyed to an A1a/A1b/A2a/A2b/B1a/B1b/B2a/B2b variant table; the
  disaccharide is drawn under "wherein R is the 4'-(alpha-L-oleandrosyl)-alpha-L-oleandrose group";
  the catalyst is written [(R4)3P]3RhX.
- **US4110165A clavulanic acid** (Beecham 1978, 23 p): fetched and validated, not inspected —
  23 pages was already over budget once the cyclosporin file had covered the pre-1980 slot.
- **DE602005004834T2 methylphenidate** (Ipca, DPMA 2009, 6 p) and **DE69929462T2 sertraline HCl
  Form V** (Teva, DPMA 2006, 14 p): both real German T2 documents in the same new PDF class, both
  rejected on density. `pdfimages -list` finds exactly two 300-ppi stencils in the methylphenidate
  file; the sertraline record exposes one structure image and one table image for 14 pages. Both
  are strictly dominated by DE60100786T2's nine clippings in ten pages.
- **EP3655396B1** ("Polymorphs of 5-fluoro-4-imino-3-methyl-1-tosyl-3,4-dihydropyrimidin-2-one",
  39 p, 706,410 B), **EP3760607B1** (period-4 transition-metal-catalysed amide-to-ester process,
  50 p, 1,047,755 B), **EP3736272B1** (piperazine and piperidine VDAC inhibitors, 59 p,
  3,866,445 B): all three fetched from the EPO publication server as German-language candidates and
  all three are **English** — see the language-flag trap above. Kept here as a record of the modern
  EP B1 format, which is Callas pdfaPilot vector text with 300-ppi CCITT structure clippings, 80 to
  214 of them per document; EP3760607B1 is additionally an organometallic-catalysis process patent
  and would be worth a second look for the M-C gap if 50 pages ever becomes affordable.
- Not pursued: DPMA DEPATISnet's `action=pdf&docid=` endpoint returns a JavaScript shell, not a
  PDF, so DE documents have to come through Google Patents.

## What is still open after round four

- **A true M-C organometallic** — unchanged from round three. EP3760607B1 is the closest thing seen
  (a manganese/period-4 complex catalysing amide-to-ester conversion) and it is 50 pages of English.
- **A JP patent.** DE is now covered by DE60100786T2, so the remaining value of a JP document is a
  second CJK sample rather than a new axis; low priority.
- **An old typewritten patent whose structures are specific, beyond the two now committed.** Four
  1970s-80s candidates were fetched this round and every one was Markush-dominated. The reason is
  structural: that era's chemical patents claim genera. US4231938A lovastatin and US4117118A
  cyclosporin are in the corpus precisely because a FERMENTATION product has no genus to claim, so
  the way to find more old specific-structure art is to look for isolated natural products —
  clavulanic acid, mupirocin, the early cephalosporins — not for drug classes.
- **A pharmacopoeia monograph excerpt** — licence question still unresolved.
