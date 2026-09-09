# C-MAGE corpus expansion — incremental progress log

Started 2026-09-08 ~23:45 UTC. Written after EVERY validated PDF; assume termination at any moment.
Prior run (same dir, 18:39-18:45 today) surveyed 14 Google Patents; its notes are in `findings.md`
(lowercase) and are already folded into `MERMaid/pdfdir/SOURCES.md`. Nothing there is re-surveyed.

Disk at start: `/` 150G, 126G used, 18G free (88%). `/tmp/cmage-pdfs` was 104 MB before this run.
Budget: whole dir < 200 MB.

Validation protocol per PDF: HTTP code + Content-Type + byte size + `%PDF` magic via `head -c 5`
(`file` is not installed on this box) + `pdfinfo` page count + render at least one structure page
with `pdftoppm` and LOOK at it. Ground truth: PubChem PUG REST name -> CID, SMILES,
ConnectivitySMILES, recorded in manifest.json.

## Entries (append-only)

### Checkpoint 1 (downloads done, visual checks partly done) — 2026-09-08 ~23:58 UTC
Route notes: MDPI direct PDF = 403; use https://europepmc.org/articles/PMCxxxx?pdf=render (works).
BJOC direct works: https://www.beilstein-journals.org/bjoc/content/pdf/1860-5397-<vol>-<art>.pdf
NTP RoC profiles work: https://ntp.niehs.nih.gov/sites/default/files/ntp/roc/content/profiles/<name>.pdf
Google Patents citation_pdf_url route works for 1960s-80s patents too (same 300-dpi CCITT raster).
EPO B1 docs via Google Patents are a DIFFERENT format: EP0564409B1 (imatinib, 32p, 214KB) is vector text
(Arial Type1C) with 20 small CCITT structure clippings inline; EP0463756B1 (sildenafil, 37p) is JBIG2 page rasters.

Old public-domain US patents downloaded (all %PDF, ImageMagick 300-dpi CCITT, pages):
- US3385886A ibuprofen 1968, 7p, 957924B — Markush p1-2, big typeset condensed-formula scheme p3-4. PRELIM ACCEPT (style: 1960s typeset condensed formulae).
- US4231938A lovastatin 1980, 10p, 872095B — stereo drawings p1,p4,p6,p9; p2-3 are NMR/IR spectra (negative control); p10 PTE cert. PRELIM ACCEPT.
- US4255431A omeprazole 1981, 13p, 1183727B — ~15-20 line-art formulas p1-5,p8-9; p11-13 certificates (text). PRELIM ACCEPT.
- US4046889A captopril 1977, 11p — ~8 generic typewriter-style formulas, examples all text. PRELIM REJECT (density).
- US4314081A fluoxetine 1982, 11p — ~6 generic Markush drawings, tables text. PRELIM REJECT (density).
- US4199574A acyclovir 1980, 18p — ~8 generic purine Markush drawings over 18p. PRELIM REJECT (density/length).
- US3136815A diazepam 1964, 27p; US3950333A cimetidine 1976, 39p — REJECT on length (not inspected in detail).

NTP Report on Carcinogens substance profiles (US Government work, public domain; Adobe PDF Library 9.0):
aflatoxins 3p, nitroarenes 9p, benzidineanddyesmetabolized 4p, basicred9 2p, adriamycin 2p, aristolochicacids 5p,
azacitidine 2p, dimethylbenzidineanddyes 3p, dimethoxybenzidineanddyes 4p, chloramphenicol 3p, diethylstilbestrol 3p
— all in /tmp/cmage-pdfs/ntp/, visual check pending.

BJOC (CC BY 4.0, Beilstein Publishing System/iText): bjoc_19-15 pheromones review 9p; bjoc_21-197 aglacin B 5p;
bjoc_18-169 macarpine 7p; bjoc_21-47 simonsol C 6p — visual check pending.
OCSR papers (J Cheminform CC BY 4.0): PMC9185882 hand-drawn dataset 4p; PMC7541205 OCSR review 13p;
PMC11227129 enhanced DECIMER 11p; PMC13390035 Chem Res Toxicol patent-OCSR benchmark 8p (page-1 says CC-BY 4) — pending.
Approved-drug reviews via EPMC: PMC12114780 42p, PMC13023470 39p, PMC10180415 21p, PMC9416721 25p, PMC11771699 24p (CC BY per p1) — all over 20p; inspect density later.

### Checkpoint 2 — BJOC / OCSR verdicts (visual, contact sheets at 50 dpi) — 2026-09-09 ~00:05 UTC
- bjoc_21-197.pdf ACCEPT. Yao et al., "Ni-promoted reductive cyclization cascade enables a total synthesis of (+)-aglacin B",
  Beilstein J. Org. Chem. 2025, 21, 2548-2552, doi:10.3762/bjoc.21.197, CC BY 4.0 (License and Terms box p5). 5 pages, 835165 B.
  URL https://www.beilstein-journals.org/bjoc/content/pdf/1860-5397-21-197.pdf. Style: ChemDraw, vector, journal typesetting.
  Fig 1 (p2): aglacins A, B, C, E (4 named natural products, wedge/hash stereo, many OMe labels); Schemes 1-3 (p2-3): ~25 numbered
  intermediates + an X-ray ORTEP (negative control). ~30 structures / 5 pages = densest doc found. GT: aglacins via PubChem (pending).
- bjoc_18-169.pdf ACCEPT. Fu et al., "Formal total synthesis of macarpine via a Au(I)-catalyzed 6-endo-dig cycloisomerization strategy",
  BJOC 2022, 18, 1589-1595, doi:10.3762/bjoc.18.169, CC BY 4.0. 7 pages, 603298 B.
  URL https://www.beilstein-journals.org/bjoc/content/pdf/1860-5397-18-169.pdf. Scheme 1 (p2): classification of benzo[c]phenanthridine
  alkaloids — chelerythrine, sanguinarine, macarpine, chelilutine, dihydro-forms etc.: CHARGED quaternary iminium (N+) species with
  PubChem CIDs. Schemes 2-6 + Tables 1-2 with drawn substrates: ~35 structures / 7 pages.
- bjoc_19-15.pdf ACCEPT (lower priority). Gayon et al., "Total synthesis of insect sex pheromones: recent improvements based on
  iron-mediated cross-coupling chemistry", BJOC 2023, 19, 158-166, doi:10.3762/bjoc.19.15, CC BY 4.0. 9 pages, 382253 B.
  Style: ChemDraw; long-chain E/Z dienes (E/Z stereo rather than wedges), Grignard/enol-phosphate reagents, ~25 structures.
- bjoc_21-47.pdf HOLD: simonsol C total synthesis, 6 p, ~30 ChemDraw structures, but same style as 21-197; keep only if the
  natural products (simonsol C/F/G, fargenone A, fargenin) resolve in PubChem.
- PMC9185882.pdf ACCEPT-IF-GT. Brinkhaus et al., "DECIMER—hand-drawn molecule images dataset", J Cheminform 2022, 14:36,
  CC BY 4.0, 4 pages, 1139404 B, URL https://europepmc.org/articles/PMC9185882?pdf=render. Fig 1: ~12 HAND-DRAWN structures
  (unlabelled); Fig 2/3: hand-drawn depictions labelled ID CDK_Depict_46_36 and CDK_Depict_45_18 (GT in Zenodo 6456306).
- PMC11227129.pdf ACCEPT. Rajan et al., "Advancements in hand-drawn chemical structure recognition through an enhanced DECIMER
  architecture", J Cheminform 2024, 16:78, CC BY 4.0, 11 pages, 1546844 B. Graphical abstract (p2) and Fig 1 (p4) print the SMILES
  CN1C=NC2=C1C(=O)N(C(=O)N2C)C beside the drawing; Fig 2 (p6) is a MULTI-PANEL grid of hand-drawn-style caffeine depictions.
  GT = caffeine CID 2519 for every panel. Only 3 of 11 pages carry figures.
- PMC13390035.pdf ACCEPT (medium). Tariq et al., "A Benchmark Evaluation of Chemical Structure Extraction from Patents",
  Chem. Res. Toxicol. 2026, 39, 1349-1356, doi:10.1021/acs.chemrestox.6c00057, CC-BY 4.0 (p1 badge), 8 pages, 2996547 B.
  Graphical abstract with SMILES; Fig 3/4 patent-style Markush images; Table 2 (p5) multi-panel input/DECIMER/MolScribe/Mathpix.
- PMC7541205.pdf REJECT: 2020 OCSR review, 13 p, essentially text + tables + one bar chart; no structure density.

### Checkpoint 3 — old patents / EP / reviews / PubChem — 2026-09-09 ~00:15 UTC
OLD PATENTS (90-dpi close-ups viewed):
- US4231938A lovastatin ACCEPT (confirmed): p1 abstract structure; p4 two structures (lactone + hydroxy acid, hand-inked line art,
  bold wedge/hash stereo); p6 one; p9 claim structure. p2-3 NMR/IR spectra = non-structure figure negative control. GT: lovastatin
  CID 53232, lovastatin acid CID 64727 (free acid; sodium salt CID 23689330 named in Ex. 7).
- US4255431A omeprazole ACCEPT (confirmed): p2 formulas I, II, III as clean line art; more on p3-5, p8-9. GT: omeprazole CID 4594
  (Ex. 1 / Table compounds are Markush-substituted; only omeprazole itself is drawn explicitly? — record as principal).
- US3385886A ibuprofen: p3 is TEXT (typewritten compound lists), not a scheme. Only 2-3 typeset formulas on p1-2. REJECT (density)
  — but it is the only 1960s-typeset example seen; keep the URL in SOURCES as a rejected candidate.
EP (Google Patents serves EPO B1 PDFs; two distinct formats):
- 1990s B1 (EP0463756B1 sildenafil 37p, EP0454436B1 olanzapine 25p, EP0717738B1 linezolid 21p): whole-page JBIG2/A4 rasters.
- 1998-2004 B1 (EP0564409B1 imatinib 32p, EP0641330B1 pregabalin 22p, EP0759917B1 oseltamivir 269p): VECTOR text + inline
  300-dpi CCITT structure clippings (1376x608 px typical). Imatinib: 20 clippings/32 p, mostly Markush I/IV/V -> REJECT (value).
  Pregabalin: 15 clippings/22 p, checking. Oseltamivir: 269 p REJECT.
REVIEWS (sheets viewed): PMC10180415 Molecules 2023 21p CC BY — ~14 pages of named 2022 FDA drugs + syntheses, ChemDraw; best
  journal GT source but 21 p (~4.2 h). PMC11771699 Arch Pharm 2025 24p CC BY — macrocyclic drugs, very dense, colour ring
  highlights, metal chelates (DOTA-TATE); ~4.8 h. PMC12114780 42p / PMC13023470 39p / PMC9416721 25p REJECT on length (not inspected).
PUBCHEM (all via PUG REST, cached in tools/.pc_cache):
  aglacin A 11755236, B 10071343, C 11741714, E — none; chelerythrine 2703, sanguinarine 5154, macarpine 440929,
  dihydrosanguinarine 124069, dihydrochelerythrine 485077, chelilutine 443720, chelirubine 161243, 10-hydroxysanguinarine 14655851;
  (8E,10Z)-tetradeca-8,10-dienal 5352448, (E)-dodeca-9,11-dienyl acetate 5367504, (7E,9Z)-dodeca-7,9-dienyl acetate 1794807,
  codlemone 1787910, sorbic acid 643460; caffeine 2519; simonsol C/F/G, fargenone A, fargenin — NONE -> bjoc_21-47 REJECT (no GT).
  NTP: aflatoxin B1 186907, B2 2724360, G1 2724361, G2 2724362, M1 15558498; 1-nitropyrene 21694, 4-nitropyrene 62134,
  1,6-dinitropyrene 39184, 1,8-dinitropyrene 39185, 6-nitrochrysene 24121; benzidine 7111, Direct Black 38 5284349, Direct Blue 6 17449,
  Direct Brown 95 135585372; pararosaniline HCl 11292; doxorubicin 31703; aristolochic acid I 2236, II 108168; azacitidine 9444;
  o-tolidine 8413; trypan blue 6296; dianisidine 8411; Direct Blue 15 17059; chloramphenicol 5959; diethylstilbestrol 448537.
DISK: render_* dirs deleted; dir at 197 MB before deleting rejected downloads.

### Checkpoint 4 — NTP verdicts, hand-drawn GT verified, manifest built — 2026-09-09 ~00:30 UTC
- PMC9185882 Figs 2-3 GT VERIFIED without Zenodo (API 504 twice): transcribed SMILES -> PubChem fastidentity:
  Fig 2 CDK_Depict_46_36 = CID 142705143 5,6,6-trinitro-1,2-oxathiane C4H5N3O7S (unique hit);
  Fig 3 CDK_Depict_45_18 = CID 129067542 tert-butyl (3S)-3-amino-5-methylsulfonylpent-4-ynoate (only 3S exists; R and racemate: no hits).
- NTP (all pages viewed at 40 dpi): exactly ONE vector structure per substance. ACCEPT the 2-page trio as corpus/ntp_roc_{basicred9,
  adriamycin,azacitidine}.pdf (charged NH2+ Cl-, stereo-dense anthracycline, nucleoside). REJECT aflatoxins (no drawing at all),
  nitroarenes (5 structures / 9 p), benzidine + dimethyl/dimethoxybenzidine dye profiles (only the parent amine drawn), aristolochic
  acids (1 / 5 p); chloramphenicol + DES = optional 3-page extras.
- EP0641330B1 pregabalin ACCEPTED (corpus/EP0641330B1_pregabalin.pdf): 22 p, 15 CCITT clippings on p1,4,6,14-21 = Charts I/Ia/II
  reaction schemes with explicit numbered intermediates (Evans auxiliary, azide, pregabalin (9)/(109)).
- manifest.json built by tools/build_manifest.py from tools/spec.json (12 accepted, 2 deferred, 22 rejected).
- corpus/ now holds the 12 accepted files with canonical names; sha256 in manifest.

### Checkpoint 5 — omeprazole demoted, Fig 3 GT, SOURCES addition written — 2026-09-09 ~00:40 UTC
- US4255431A omeprazole REJECTED after 100-dpi check of p1/p8/p9: abstract and claim structures are the generic formula (R1-R5);
  no explicit compound is drawn anywhere. File moved to /tmp/cmage-pdfs/US4255431A_omeprazole_REJECTED.pdf; spec updated.
- NTP trio close-ups (120 dpi) confirm: Basic Red 9 drawn as NH2+ with separate Cl-; doxorubicin with wedges; azacitidine with wedges.
- PMC13390035 Fig 3 (p4) six explicit structures: (c) tert-butyl N-(3,5-dimethoxyphenyl)carbamate CID 10634629; (d) 1,1-dimethyl-
  guanidine (name lookup gives sulfate salt CID 69024; free-base identity search pending); (e) cyclohexyltrimethoxysilane CID 10998130;
  (f) perfluoro acid, chain length pending (PFOA 9554 / PFNA 67821); (b) transcribed SMILES OC(=O)c1cc(OCc2ccccc2)c(F)cc1NC(=O)OCc1ccccc1
  has no PubChem identity hit -> SMILES-only GT; (a) bis-binaphthol dialdehyde, not transcribed. GA SMILES n1ccn2CCCn2c1 is valid
  (RDKit C1=CN2CCCN2C=N1); the two crossed-out ones are invalid by design.
- Pipeline ingestion verified in code: DECIMER-Image-Segmentation uses pdf2image.convert_from_path(pdf, 300) (= pdftoppm 300 dpi),
  the same renderer used to validate every accepted file. No pipeline run started: another agent's DECIMER job is at ~470% CPU.
- Deliverable 3 written: /tmp/cmage-pdfs/SOURCES_addition.md (SOURCES.md voice; accepted ranked, deferred, rejected with reasons).
- Corpus now 11 files in /tmp/cmage-pdfs/corpus/ (about 11 MB). Whole dir 169 MB.

### FINAL checkpoint — 2026-09-09 ~00:50 UTC
State of deliverables:
1. /tmp/cmage-pdfs/PROGRESS.md — this log (checkpoints 1-5 + final).
2. /tmp/cmage-pdfs/manifest.json — built by tools/build_manifest.py from tools/spec.json: 11 accepted (82 pages, ~16.4 h at
   12 min/page), 2 deferred, 23 rejected, 38 expected molecules of which 34 carry a PubChem CID + SMILES + ConnectivitySMILES +
   InChIKey + RDKit-canonical SMILES (RDKit 2025.03.3 from /root/C-MAGE/.venv-ms); 4 are SMILES-only or unresolvable
   (aglacin E not in PubChem; Fig 3a/3b of PMC13390035 no identity hit; the graphical-abstract SMILES has no CID by design).
3. /tmp/cmage-pdfs/SOURCES_addition.md — proposed addition to MERMaid/pdfdir/SOURCES.md (accepted ranked, deferred, rejected).
4. Verdict/ranking is in the final message and in SOURCES_addition.md.
Files: /tmp/cmage-pdfs/corpus/ holds the 11 accepted PDFs (11 MB) with canonical names; sha256 in manifest.
Disk: /tmp/cmage-pdfs = 169 MB (< 200 MB budget); of that ~50 MB is the PRIOR run's rejected long patents (US6573293B2 8.4 MB,
US8946235B2 9.7 MB, US7514444B2 7.7 MB, ...), left in place because they are another agent's artefacts; deleting them is safe
(all are documented as rejected in SOURCES.md). `/` went from 88% (18 GB free) at start to 81% (29 GB free) at end — other agents
freed space; this run's net footprint is +65 MB in /tmp/cmage-pdfs after cleanup.
PII / <host>: `git grep --no-index` over SOURCES_addition.md, manifest.json, tools/spec.json: no <host>, no e-mail, no /root/seb;
the one regex hit was the digit pattern matching a sha256 prefix (false positive).
Pipeline NOT run (another agent's DECIMER job at ~470% CPU); ingestibility shown by code inspection: stage 2 uses
pdf2image.convert_from_path(pdf, 300) = the pdftoppm render used to validate every file, including the vector-only NTP PDFs and
the hybrid EP PDF.
