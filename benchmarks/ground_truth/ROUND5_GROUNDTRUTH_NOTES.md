# Round 5 PDF ground truth — what is in `pdf_manifest_round5.json`

Eleven pharmaceutical PATENTS chosen to widen the range of DRAWING STYLES and
LANGUAGES, not chemistry. The corpus was already strong on ChemDraw vector and
1980s USPTO scans, so this round deliberately adds: **Cyrillic, Korean, Japanese
and a second Chinese** document; native **French and German** EPO B1 grants;
**1970s hand-inked** draftsman art that draws *specific* compounds rather than a
Markush genus; stereochemistry printed as **S/R letters**; and **two-component
salts drawn as such**, including one drawn with no dot glyph at all.

Method as in round 3/4. Every structure was located by reading the PDF
(`pdftotext`, `pdfimages`, `pdftoppm` page crops). Every resolved molecule needed
TWO independent views to agree — a PubChem lookup (by a name/CAS printed in the
document, or, where only a Roman-numeral label is printed, a same-connectivity
structure search on the drawn reading) AND a reading of the drawing. Every SMILES
round-trips through RDKit and its InChIKey was verified equal to the recorded
value (**0 mismatches over all 50 rows**). `pixel_verified` is false everywhere.

## Counts

| group | drawn | resolved | generic | unresolved |
|---|---|---|---|---|
| JP6924794B2_afuresertib | 1 | 1 | 0 | 0 |
| KR101146095B1_canagliflozin | 1 | 1 | 0 | 0 |
| CN103025753A_ezatiostat | 1 | 1 | 0 | 0 |
| RU2405786C2_asenapine | 3 | 2 | 0 | 0 |
| KR102514961B1_edoxaban | 3 | 2 | 0 | 1 |
| US4110165_clavulanic_acid | 5 | 3 | 0 | 0 |
| JP6724082B2_vortioxetine | 7 | 4 | 3 | 0 |
| US3781268_kanamycin | 8 | 2 | 6 | 0 |
| EP0308341NWB1_perindopril | 14 | 8 | 6 | 0 |
| US4194047_thienamycin | 16 | 5 | 9 | 1 |
| EP3337801B1_finerenone | 21 | 21 | 0 | 0 |
| **total** | **80** | **50** | **24** | **2** |

**Read the units.** `drawn`, `generic` and `unresolved` count **depictions**;
`resolved` counts **rows in `molecules`**, i.e. distinct compounds, because repeat
drawings of one compound collapse to one row. That is why the columns do not sum:
US4110165 draws clavulanic acid three times, and US4194047's 16 depictions cover
only 6 distinct full structures. The 24 generic depictions are described by 10
`unscoreable` rows (near-duplicate generics grouped); the 2 unresolved by 2 rows.

## Two schema decisions (unchanged from round 3/4)

1. Rows with no SMILES are **not** in `molecules` — `score_run.py` calls
   `Chem.MolFromSmiles` on every entry there and a `None` raises `TypeError`.
   Generic (Markush) and unresolved structures live in a sibling `unscoreable`
   array carrying `generic` / `confidence`, `page` and a `note`.
2. Repeat drawings of one compound collapse to ONE row, matched by `name`, with
   every page listed. No group has a duplicate name or InChIKey.

`confidence` values: `name_match` (a name/CAS printed in the document resolves to
the CID and the drawing agrees), `drawing_read` (no printed name; read off the
drawing and confirmed by a PubChem structure search whose InChIKey equalled the
read), `unresolved`, `generic`.

## Per document — and the ONE caveat to know before quoting a score

### JP6924794B2 — afuresertib (Japanese, vector) — 1 drawn / 1 resolved
One structure (p2, 構造 I): afuresertib drawn as free base joined to HCl by a salt
dot, scored as the hydrochloride (CID 46843056). Figures 1–3 are PXRD (negatives).
**Caveat.** Do not resolve by trade name — `capivasertib` returns CID 25227436, a
different pyrrolopyrimidine (C21H25ClN6O2). Only the printed IUPAC name and the
drawing agree, on afuresertib. A pipeline that segments the salt emits the base
(CID 46843057) + HCl, not this row.

### KR101146095B1 — canagliflozin (Korean; new script) — 1 drawn / 1 resolved
One structure (p3, 화학식 I) = canagliflozin free base (CID 24812758); 도면1/도면2 are
XRPD and IR spectra (negatives).
**Caveat.** The patent claims the HEMIHYDRATE, but the 0.5 H2O is not drawn — the
depiction is the anhydrous free base, so the reference is canagliflozin.

### CN103025753A — ezatiostat (Chinese, scanned) — 1 drawn / 1 resolved
One structure (p3) = ezatiostat free base (CID 5310939), named 依泽替米贝 / TLK199 /
TER199. 图6/图7/图8 are XRPD and 13C NMR (negatives). Every page is a 300-dpi
full-page RASTER re-wrapped by iText — a different PDF class from CN108503621B's
vector-text-plus-clippings.
**Caveat.** The drug substance is the HYDROCHLORIDE (a Form D ansolvate), but only
the free base is drawn; the HCl is named, never depicted. The three stereocentres
were confirmed at the connectivity level from the scan, so the printed name is the
anchor.

### RU2405786C2 — asenapine maleate (RUSSIAN / Cyrillic) — 3 drawn / 2 resolved
Схема 1 (p3) has two compound boxes: (1) азенапин and (2) малеат азенапина, the
latter containing the base plus a fully drawn **cis** maleic acid, with the
composition printed as `C17H16ClNO . C4H4O4` and Мм = 401,84 — which is what pins
CID 6917875 (285.77 + 116.07 = 401.84). XRPD on pp13–14 are negatives.
**Caveat.** The document names the compound only as `транс-` (no R/S). Asenapine is
the trans RACEMATE while PubChem CID 163091 carries a defined single-enantiomer
stereo layer, so an opposite-enantiomer or stereo-free prediction is a
stereo-level match, not a miss.

### KR102514961B1 — edoxaban besylate (Korean) — 3 drawn / 2 resolved / 1 unresolved
p4 carries [화학식 1] the edoxaban free base and [화학식 2] the base, a fully drawn
benzenesulfonic acid and a bare `H2O` label **juxtaposed with no dot glyph**.
Scored as two component rows (edoxaban CID 10280735, benzenesulfonic acid CID
7371). 도1–도4 (XRPD, 1H NMR, DSC, and a *comparative* oxalate XRPD) are negatives.
**Caveat.** The document's actual subject — edoxaban benzenesulfonate monohydrate —
has **no PubChem record** and is therefore `unresolved`. The nearest hit, CID
25022378 *Edoxaban tosylate monohydrate*, is the p-TOLUENEsulfonate: one extra ring
methyl, a different salt. Using it would silently turn a correct prediction into a
scored failure.

### US4110165 — clavulanic acid (1978, hand-inked) — 5 drawn / 3 resolved
4-page extract (original pp1–4). Clavulanic acid (CID 5280980) drawn FLAT in the
front-page abstract and again as formula (II) with its printed systematic name,
then WITH (2R,5R) wedges as formula (I); plus sodium (CID 23670298) and potassium
(CID 23665591) clavulanate as condensed CO2Na / CO2K labels. p2 is the patent's
sole "Drawing Figure", a full-page IR spectrum (negative).
**Caveat.** The same molecule is drawn both flat and stereo-wedged while the
reference CID carries defined stereo, so the two flat depictions can only ever be
recovered at the stereo-free level.

### JP6724082B2 — vortioxetine (Japanese) — 7 drawn / 4 resolved / 3 generic
2-page extract (original pp16, 32). Scoreable: vortioxetine (CID 9966051) and the
three drawn reagents of scheme 化10 — 2,4-dimethylbenzenethiol (83617),
1,2-dibromobenzene (11414), N-Boc-piperazine (143452). Generic: 化3 Ar-SR', 化4
ortho-C6H4(X1)(X2), 化5 N-R piperazine.
**Caveat.** Vortioxetine is drawn as the free base; the marketed hydrobromide (CID
56843850) and a fumarate are named in the examples but never drawn as salts.

### US3781268 — kanamycin A/B (1973, wobbliest hand-drawn) — 8 drawn / 2 resolved / 6 generic
2-page extract (original pp1–2). Freehand chair-conformation sugar rings with
typewriter-style condensed labels and no wedges anywhere. Kanamycin A (CID 6032)
and kanamycin B (CID 439318) are drawn specifically under their printed names and
differ by a single OH/NH2 label.
**Caveat.** AMIKACIN (BB-K8) — the patent's actual subject, named in the abstract —
is drawn ONLY through the two-member variable R3 (= OH or NH2), so it is generic
and deliberately not scored. Note also that the front page says "No Drawing" and
the specification is nonetheless full of inline structures.

### EP0308341NWB1 — perindopril (FRENCH EPO B1) — 14 drawn / 8 resolved / 6 generic
300-dpi JBIG2 full-page scans. Ring SKELETONS carrying stereochemistry as printed
S/R LETTERS alongside fully CONDENSED formulae. Scoreable: perindopril (107807),
(2S,3aS,7aS)-octahydroindole-2-carboxylic acid (7408452), indoline-2-carboxylic
acid (86074), the side-chain acid VI (13258848), L-norvaline (65098), its ethyl
ester (10080526), the benzyl ester cation IX (10149261) and perindopril benzyl
ester X (11396975). Generic: esters III/IV and the four diastereomers IIa–IId.
**Caveat.** The TARGET of every claim is the tert-butylamine salt (perindopril
erbumine), but formula (I) is DRAWN as the free acid, so the reference is
perindopril acid. Formula (IX) is a drawn tosylate (`PTS` written beside it) scored
on its benzyl-ester CATION, since the full salt is not a distinct PubChem record.

### US4194047 — thienamycin / imipenem (1980) — 16 drawn / 5 resolved / 9 generic / 1 unresolved
3-page extract (original pp2, 19, 20). Scoreable: thienamycin (441128), imipenem
(104838), O-(2,4,5-trichlorophenyl)isourea hydrochloride (20535606, itself a drawn
`.HCl` salt), 2,4,5-trichlorophenol (7271) and N-acetimidoyl thienamycin
(90669620).
**Caveat.** Six depictions are a `Th` BRACKET standing for the whole bicyclic
nucleus, with only the OH, the N-substituent and the CO2H drawn outside it. These
are **not full structures**: a tool that silently expands `Th` yields a chemically
correct molecule that was never drawn, and must not be credited. Separately,
N-trifluoroacetimidoyl thienamycin (Example 11) IS drawn in full and named but has
no PubChem record — recorded `unresolved` with its read formula C13H16F3N3O4S in
the note and no SMILES asserted.

### EP3337801B1 — finerenone (GERMAN EPO B1) — 21 drawn / 21 resolved
6-page extract (original doc pp3–8) of the 74-page grant; every drawn compound is
a specific, PubChem-resolvable intermediate and there is NO Markush in the extract.
Contents: the (4S) drug (60150535) and its (4R) distomer ent-(I) (59349636) named
and drawn side by side on p1; Schema 1 (II–XIII); Schema 2 additions VIa/VIb; and
the halobenzoic-acid route (XIV, XIVa, XV, XVI). Nineteen of the 21 carry only a
Roman-numeral label and are therefore `drawing_read`.
**Caveat.** This single document contributes 21 of the round's 50 scoreable
molecules — weight it accordingly in any per-document average. The fully aromatic
pyridine Formel (XVII) (CID 126623403) of the enantiomer-recycle loop is drawn only
in a later Beispiel OUTSIDE this extract, so it is named here but not scored.

## Provenance note

Google Patents now IP-blocks the collecting host (HTTP 503 on both IPv4 and IPv6),
so `record_url` values pointing there are bibliographic references, not fetchable
from that machine. Working routes are recorded in the selection manifest's
`retrieval_note`. Two files were re-fetched and confirmed **byte-identical** to the
committed copies (US patents via `patentimages/pdfs/US<number>.pdf`; RU2405786C2 via
the Rospatent/FIPS archive). The single exception is KR102514961B1, whose direct
PDF URL could not be re-verified afterwards; its committed SHA256 is the integrity
anchor and its content was confirmed by rendering (the KIPO number 10-2514961 is
printed on every page).
