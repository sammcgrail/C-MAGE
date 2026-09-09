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
