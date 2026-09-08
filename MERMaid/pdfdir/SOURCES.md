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
- Too long for a 2-core box: US7157456B2 rivaroxaban 78 p, US7514444B2 ibrutinib 74 p,
  US8946235B2 osimertinib 86 p, US6573293B2 sunitinib 134 p, US6362178B1 vardenafil 146 p,
  US6251910B1 ticagrelor 51 p (not inspected).

### Optional extra (NOT copied into this directory)
A verified open-access journal article is parked at /tmp/cmage-pdfs/PMC11643494.pdf if a
journal-layout baseline is wanted: Mishra et al., "Structure-Activity Relationship Studies in a
Series of 2-Aryloxy-N-(pyrimidin-5-yl)acetamide Inhibitors of SLACK Potassium Channels",
Molecules 2024, 29(23), 5494, doi:10.3390/molecules29235494, licence CC BY 4.0 (Europe PMC
record: isOpenAccess=Y, license "cc by"), 19 pages, downloaded from
https://europepmc.org/articles/PMC11643494?pdf=render. Vector text (pdfTeX) with structures
embedded as 600-dpi CCITT stencil images: Figure 1 on p. 3, schemes pp. 5-7, SAR tables with
drawn scaffolds pp. 8-13.
