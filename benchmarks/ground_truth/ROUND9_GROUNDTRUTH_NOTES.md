# Round 9 PDF ground truth — anti-infective patents

Twenty-five granted European patent specifications in the four anti-infective
areas — antibacterial (ten, of which two are antimycobacterial), antiviral
(seven), antifungal (five) and antiparasitic (three) — priority dates 2010–2022.
Selection provenance is in `pdf_corpus_round9_manifest.json`; this file and
`pdf_manifest_round9.json` are the scoreable half, in the
`pdf_manifest_expanded.json` schema that `score_run.py` reads.

Nothing here was derived from a pipeline prediction. Every structure was located
by reading the PDF — `pdftotext -layout` for text, `pdfimages -png` to pull each
embedded structure clipping at its native resolution, and `pdftoppm` at 200–450
dpi wherever a single wedge had to be settled. Every resolved molecule needed two
independent views to agree: a PubChem record reached by a name **printed in the
document** or by a `/compound/smiles/` structure search on the drawn reading,
**and** a reading of the drawing. A structure search was accepted only when the
returned record's InChIKey equalled the RDKit InChIKey of the hand reading
exactly; a returned CID with a *different* key was treated as a miss. Every
SMILES round-trips through RDKit and the builder that wrote the manifest asserts
`inchikey == inchikey_rdkit` on every row.

## Counts

`drawn` counts **depictions on the kept pages**. `resolved`, `generic` and
`unresolved` count **rows** — distinct compounds, or named classes of depiction.
The columns do not sum: a compound drawn eleven times is one row.

| group | area | pages kept | size | drawn | resolved | generic | unresolved |
|---|---|---|---|---|---|---|---|
| `EP3067355B1_nacubactam` | antibacterial | 1,3-6,12,14-16 | 227 KB | 42\* | 2 | 6 | 0 |
| `EP3189841B1_cefiderocol` | antibacterial | 1-6,9,11,27-31 | 365 KB | 25 | 2 | 0 | 2 |
| `EP3299356B1_pleuromutilin` | antibacterial | 1-4,9,10,15-17 | 227 KB | 14\* | 2 | 1 | 1 |
| `EP3529236B1_eravacycline` | antibacterial | 1-3,19,25-28,30-35 | 324 KB | 32 | 5 | 0 | 5 |
| `EP3592362B1_taniborbactam` | antibacterial | 1,3,5,9,12,21,36-38 | 253 KB | 10 | 2 | 0 | 3 |
| `EP3643719B1_spiropyrimidinetriones` | antibacterial | 1,3-9,77,78 | 315 KB | 24\* | 0 | 1 | 1 |
| `EP3719020B1_BLI_gallery` | antibacterial | 1-3,7,17-21 | 262 KB | 24\* | 7 | 0 | 1 |
| `EP3868768B1_contezolid_acefosamil` | antibacterial | 1-14 (complete) | 380 KB | 6 | 2 | 0 | 1 |
| `EP4003521B1_telacebec` | antibacterial (antimycobacterial) | 1-3,22,51,68,69 | 307 KB | 3 | 2 | 0 | 2 |
| `EP4121058B1_oxazolidinone_TB` | antibacterial (antimycobacterial) | 1-17 (complete) | 424 KB | 22 | 9 | 0 | 1 |
| `EP3221308B1_olorofim` | antifungal | 1,4-9,32,34,35,38 | 198 KB | 12 | 8 | 1 | 1 |
| `EP3247711B1_ibrexafungerp` | antifungal | 1,2,6,25,52,54,56,58 | 487 KB | 5 | 1 | 0 | 1 |
| `EP3720438B1_gwt1_antifungals` | antifungal | 1-3,74-79 | 251 KB | 22 | 6 | 1 | 1 |
| `EP3810115B1_manogepix_prodrugs` | antifungal | 1,3,13,14,20-23,31,32 | 248 KB | 14 | 3 | 1 | 1 |
| `EP4069690B1_opelconazole` | antifungal | 1,3,24,27-31,33 | 240 KB | 11 | 1 | 0 | 0 |
| `EP3578557B1_cipargamin` | antiparasitic | 1,3-6,11-13 | 254 KB | 24\* | 6 | 0 | 2 |
| `EP3743419B1_antiparasitic_tetrazoles` | antiparasitic | 1-3,53-55,57 | 232 KB | 12 | 8 | 1 | 1 |
| `EP4061375B1_antimalarial_markush` | antiparasitic | 1-6,41,52,53 | 343 KB | 26\* | 0 | 2 | 1 |
| `EP3321253B1_tecovirimat` | antiviral | 1-19 (complete) | 353 KB | 32 | 9 | 0 | 0 |
| `EP3473629B1_baloxavir_route` | antiviral | 1-4,22,41 | 226 KB | 13\* | 7 | 1 | 1 |
| `EP3512863B1_ethynyl_nucleosides` | antiviral | 1,5,6,33,199,200 | 204 KB | 12 | 3 | 1 | 1 |
| `EP3544977B1_pritelivir` | antiviral | 1,5,6,12,14-17,42 | 463 KB | 12 | 2 | 0 | 1 |
| `EP3668859B1_lenacapavir` | antiviral | 1-3,5,9,48-50,61 | 260 KB | 8 | 2 | 0 | 0 |
| `EP3953330B1_nirmatrelvir` | antiviral | 1,4,53,62,63,181,182 | 234 KB | 27 | 16 | 2 | 1 |
| `EP4079746B1_molnupiravir` | antiviral | 1-13 (complete) | 411 KB | 22 | 5 | 0 | 2 |
| **total** | | **251 pages** | **7.7 MB** | **454** | **110** | **18** | **31** |

\* starred `drawn` counts are estimates, made from image objects or a
low-dpi contact sheet rather than a box-by-box census at full resolution. They
are flagged per group by `structures_drawn_is_estimate`. No estimated number can
move a score: recall runs over `molecules` and precision over what a pipeline
emits, and both are exact.

**The denominator to quote with any recall figure from this round is 110**, and
only if you score all twenty-five groups. Two of them contain no scoreable
molecule at all (see "The two zero groups"), so the honest denominator over the
twenty-three scoring groups is still 110. If you drop the seven recall-only
groups — `EP3720438B1`, `EP3578557B1`, `EP3473629B1`, `EP3299356B1`,
`EP3512863B1`, `EP3810115B1` and `EP3743419B1` — the denominator is **69**.

`molecules` holds 110 rows under 108 distinct names. Two compounds appear in two
groups each, on purpose: **ibrexafungerp** is the sole subject of
`EP3247711B1` and is also drawn as a competitor comparator inside
`EP3221308B1`, and **nacubactam** is the subject of `EP3067355B1` and is drawn
as a prior-art reference inside `EP3719020B1`. Neither group contains a
duplicate name internally, which is the constraint `score_run.py` cares about.

## Three schema decisions a reader must know

1. **Rows with no SMILES are not in `molecules`.** `score_run.py` calls
   `Chem.MolFromSmiles(m["smiles"])` on every entry and a `None` raises
   `TypeError` before the script's own error message. Generics, unresolved
   structures and compounds that are named in the text but never drawn live in a
   sibling per-group `unscoreable` array, which the scorer ignores.
2. **Repeat drawings of one compound are collapsed to one row.** Cefiderocol is
   drawn eight times in its document and eravacycline dihydrochloride eleven
   times in its; each is one row.
3. **A `molecules` row requires a PubChem CID.** Every scoreable row in every
   previous round carries one and this round keeps the invariant. Five compounds
   whose structure is *certain* but which PubChem does not hold are therefore
   `unresolved`, not scoreable: cefiderocol sodium (the drawn salt, whose printed
   molecular weight 774.20 matches a hand-built SMILES to 0.01), pritelivir
   maleate (the claimed compound, printed as C22H22N4O7S2 [518.56]), two
   molnupiravir acetonide esters, and nirmatrelvir's intermediate C31 — the only
   member of its own seven-step route with no record.

`confidence` values used: `name_match` (a name printed in the document resolves
to the CID and the drawing agrees), `drawing_read` (no name printed; the
structure was read off the drawing and confirmed against a PubChem record by
structure search), `generic`, `unresolved`. `pixel_verified` is `false`
everywhere.


## What this round adds that the corpus did not have

- **Beta-lactams and beta-lactamase inhibitors, six documents deep.** A
  siderophore cephalosporin (cefiderocol), a cyclic boronate (taniborbactam), two
  diazabicyclooctanes (nacubactam, and the Qilu guanidinooxy compound), and a
  single figure — `EP3719020B1` p2–p3 — that draws **clavulanic acid, sulbactam,
  tazobactam, avibactam, relebactam and nacubactam side by side** in three
  different charge conventions.
- **A sugar group.** `EP4079746B1` is thirteen pages of ribofuranosides with an
  anomeric centre, and it is where the anomer trap fired (below).
- **A rigid polycyclic cage.** Tecovirimat's cyclopropane-fused
  bicyclo[2.2.2]octene imide, drawn with six explicit stereo hydrogens and no CIP
  letters, in a document where every compound differs from its neighbours by one
  atom.
- **Two azoles and a tetrazole antifungal**: opelconazole's 1,2,4-triazole on a
  trisubstituted tetrahydrofuran, oteseconazole's tetrazole (drawn inside a
  *competitor's* patent), and ibrexafungerp's eleven-stereocentre triterpene.
- **Isotopologues.** Olorofim, its piperazine-d8 and its phenylene-d4 are three
  real PubChem records sharing one skeleton InChIKey block and one RDKit
  molecular formula string.
- **A phosphorus heterocycle with no ring carbon** (T3P, drawn as a reagent), an
  **isocyanate**, a **boronic acid drawn in both its closed and open forms**, and
  six **reagents and solvents drawn as full structures with no label at all**.

## Six failure modes this round demonstrates, with the evidence

**1. The wrong anomer resolves cleanly.** Building
2',3'-O-isopropylidenecytidine free-hand from the `EP4079746B1` drawing inverted
the anomeric carbon. PUG-REST returned **CID 92271334**, a real record, InChIKey
`UBGDNZQSYVIVHU-ZQNVIIHSSA-N` — same formula, same skeleton block, no warning of
any kind. The correct compound, built instead by fusing an acetonide across
cytidine CID 6175's own oxygens, is **CID 124388903**,
`UBGDNZQSYVIVHU-JZKKDOLYSA-N`. A **third** record, CID 351235, answers to the
*name* and is stereo-undefined. Three PubChem records, one skeleton, and the name
route, the free-hand structure route and the derived structure route each return
a different one.

**2. The wrong diastereomer returns CID 0 — which is how it was caught.** The
first hand-built SMILES for nacubactam's Boc/benzyl intermediate wrote the
bicyclo[3.2.1] bridge in the other sense. Same formula C21H30N4O6, same skeleton
block `MEQZWILNPLMCMK`, different stereo layer, and PubChem returned **CID 0**.
Had it happened to hold a record for that diastereomer — as it did for round 6's
vepdegestrant cereblon fragment — nothing would have flagged it. **A CID-0 answer
is a real result and should be read as one.**

**3. PubChem silently accepts stereochemistry its record does not have.**
Taniborbactam is drawn *trans*-1,4 on the cyclohexane and named `trans-` in
words. PubChem CID 76902493 does not encode that ring at all
(`PFZUWUXKQPRWAL-PXCJXSSVSA-N`). Submitting the trans-specified SMILES
(`-BJJXKVORSA-N`) returns CID 76902493 anyway. So a **faithful** reading of that
drawing scores `stereo`, not `exact`, and a tool that drops the wedges scores
`exact`. That is a property of the reference.

**4. One wedge, two real records, drawn 400 pixels apart.** `EP3529236B1` p25
prints an impurity gallery in which `Epimer (TP-498)` and `TP-034` are identical
except that the C-4 dimethylamino is a **bold** wedge in one and a **hashed**
wedge in the other. They are eravacycline (`AKLMFDDQCHURPW-ISIOAQNYSA-N`) and its
C-4 epimer (`AKLMFDDQCHURPW-BNWPUYEGSA-N`). The same shape appears three more
times in `EP3743419B1`, where Examples 5/6, 7/8 and 11/12 are three
(2R)/(2S) pairs drawn on the same pages as each other.

**5. CIP letters move when the molecule does not.** PubChem calls contezolid
(5S) and contezolid acefosamil (5R) at the same carbon with the same spatial
arrangement — phosphorylating a remote nitrogen puts a P in the second sphere.
The cipargamin route does it again: the Boc mesylate is (2R) and the amine one
LiAlH4 reduction later is (2S), stereocentre untouched. Matching printed
descriptors to drawn wedges across a scheme will conclude, wrongly, that
something inverted.

**6. Protomers and tautomers give one InChIKey and several canonical SMILES.**
Cefiderocol is drawn on p2 with the cephem carboxylate anionic and on p6 with the
proton moved to the *other* carboxyl. Both are
`DBPPRLRVDVJOCL-FQRUVTKNSA-N` and two different RDKit canonical SMILES, and the
document says explicitly that both are the invention. The Qilu guanidine does the
same thing (`-O-N=C(N)N` versus `-O-NH-C(=N)N`). Under string equality one
faithful reading of each pair is wrong; under InChIKey both are right.

## The two zero groups, and why they are opposites

`EP3643719B1_spiropyrimidinetriones` and `EP4061375B1_antimalarial_markush`
both have `molecules: []`. **Score both for false positives only** — precision and
recall over them are undefined, as they were for round 6's auristatin group.

They fail for opposite reasons, which is the point of keeping both. The
spiropyrimidinetrione patent draws eighteen compounds, gives every one a complete
and correct IUPAC name, and **not one of them exists in PubChem** — a 2017 Chinese
filing of new chemical entities. Its parent drug, zoliflodacin, is named as
AZD0914 twenty-six times in the text and never drawn. The MSD antimalarial
patent, by contrast, draws almost nothing that *is* a molecule: its claim genera
carry a **floating substituent with a count subscript**, `R10(m)`, whose bond
crosses the ring interior instead of landing on an atom, and its ten-step Scheme 1
leaves even the protecting group as a variable `P`. One document is all molecule
and no reference; the other is all reference-shaped drawing and no molecule.

## Per document

### Antibacterial

#### `EP3067355B1_nacubactam` — 42 drawn, 2 resolved, 6 generic, 0 unresolved

EP 3 067 355 B1, Meiji Seika Pharma Co., Ltd., application 14850074.2 filed 2014-10-08 (priority 2013-10-08 JP), granted 2020-12-16, "Crystals of diazabicyclooctane derivative and production method for crystals of diazabicyclooctane derivative" - crystalline nacubactam (OP0595 / RG6080)

**Why it is here.** A process patent that draws almost everything GENERICALLY - R1, R3, P1, P2 - and specifies its two real compounds only on p6. It is the round's clean measurement of whether a tool can tell an R-group drawing from a molecule, and the INN is never printed: the compound is identified only by a full IUPAC name.

**Drawing style.** EPO B1: vector text with bitonal structure clippings. Two distinct drawing registers - large single formulae and reaction schemes on pp3-6 and 14-16, and a dense 12-member R-group gallery on p12 in which every entry carries P1/P2 protecting-group placeholders.

**Counts and page tally.** About 42 depictions, of which only TWO are fully specified molecules and both are on p6. Page tally: p3 x5 (formula VII, then Scheme 1's IV -> V -> VII with substituents given in words), p4 x2, p5 x3, p6 x12 (VII-1, IV-1 and a ~8-box Scheme 2), p12 x12 (the P1/P2 gallery), p14 x4, p15 x2, p16 x2. The p6 Scheme 2 count is an ESTIMATE from a 100-dpi contact sheet, which is why structures_drawn_is_estimate is true; it cannot move a score, since recall runs over molecules[] and precision over what a pipeline emits. Non-structure content on the kept pages: the p12 claim listing of ~30 full IUPAC names with no drawings, and the crystallisation tables. The four full-page XRPD sheets (pp61-64) were dropped.

**Caveats.**

- *nacubactam* — The INN nacubactam is NEVER printed - the document calls it 'a diazabicyclooctane derivative of formula (VII-1)' and gives the IUPAC name. Everywhere except p6 it is drawn as the GENERIC formula (VII) with the substituent supplied in words ('VII-1: R3 = CH2CH2NH2'), which is a drawing a structure recogniser must NOT resolve to nacubactam.
- *tert-butyl N-[2-[[(2S,5R)-7-oxo-6-phenylmethoxy-1,6-diazabicyclo[3.2.1* — A LIVE INSTANCE OF THE NEAR-MISS, caught. The first hand-built SMILES for this compound wrote the bicyclo[3.2.1] bridge with the stereocentres in the other sense; it gave the SAME formula C21H30N4O6 and the SAME skeleton InChIKey block MEQZWILNPLMCMK with a different stereo layer (-DLBZAZTESA-N), and PUG-REST returned CID 0. The CID-0 answer is what caught it. Had PubChem happened to hold a record for the wrong diastereomer - as it did for the vepdegestrant cereblon fragment in round 6 - nothing would have flagged it.
- *formula (VII) - the R3 genus* (generic) — The parent claim's formula: the DBO sulfate with 'R3 is C1-6 alkyl or heterocyclyl, R3 may be modified with 0-5 groups R4 selected from C1-6 alkyl, heterocyclyl, R5(R6)N- and a protecting group'. Drawn three times.
- *formula (VI) - the R3 genus as its tetrabutylammonium sulfate* (generic) — Same genus, drawn with an explicit OSO3- nBu4N+ ion pair - a quaternary-ammonium counterion drawn as a condensed 'nBu4N' label rather than as atoms.
- *formula (IV) - the R3 genus, O-benzyl protected* (generic) — Same genus with OBn in place of the sulfate; OBn is a condensed protecting-group label, not an expanded benzyloxy.
- *formula (III) - the R1 ester genus* (generic) — R1O2C- on the DBO with OBn; R1 is undefined in the drawing.
- *formulae (V), (VII-CR) and (VIII) - process-stage genera* (generic) — (VII-CR) is the CRUDE of (VII) and (VIII) its purified form: the SAME generic drawing given three different labels for three different physical states of one substance. No structure recogniser can tell them apart, and it should not try.
- *p12 twelve-member P1/P2 gallery (IV-1..IV-12 / VI-1..VI-12 / VII-1..VI* (generic) — Twelve drawings, each carrying P1 and P2 protecting-group placeholders and each captioned with THREE compound codes at once, so 12 depictions stand for 36 nominal compounds and zero specified molecules. This is the document's largest depiction class and the one most likely to be emitted as real structures.

#### `EP3189841B1_cefiderocol` — 25 drawn, 2 resolved, 0 generic, 2 unresolved

EP 3 189 841 B1, Kawasaki, Kojima, Takahashi, Matsubara, Matsuoka, Fujihira, Shionogi & Co., Ltd., application 15838647.4 filed 2015-09-03 (priority 2014-09-04 JP 2014180174), granted 2023-11-22, "Pharmaceutical preparation comprising cephalosporin having catechol groups" - the stabilised lyophilisate of cefiderocol (S-649266, FETROJA)

**Why it is here.** A marketed beta-lactam whose INN is printed in the specification, drawn 25 times across three claim languages; the free acid is drawn as TWO different protomers with the same InChIKey; a named degradant and a dimeric degradant give a non-drug structure class inside a drug document; and the document prints molecular weights (752.21, 774.20) as a second view.

**Drawing style.** EPO B1: vector Arial/Times text with 300-dpi CCITT structure clippings inline. Claims are printed three times - English (p27-28), German (p29-30) and French (p30-31) - and every formula is REDRAWN in each language block, so 15 of the 25 depictions are the same four compounds repeated.

**Counts and page tally.** 25 depictions of only FOUR distinct compounds. Page tally: p2 x1, p3 x1, p4 x3, p5 x2, p6 x3, p9 x1, p11 x2, p27 x2, p28 x2, p29 x3, p30 x3, p31 x2. The English claims (p27-28), German claims (p29-30) and French claims (p30-31) each redraw the same formulae (I), (II), (III), (IV), so a per-page structure count triples the true compound count. Non-structure content on the kept pages: none - the full-page instrument plot on p13 and the formulation tables on pp15-25 were dropped. Example 1 at [0055] p11 prepares a '1.3 tosilate salt / 0.4 sulfuric acid salt' of compound (IA): a NON-INTEGER, two-counterion stoichiometry that no single SMILES can express, and neither counterion is ever drawn.

**Caveats.**

- *cefiderocol* — THE PROTOMER TRAP. p6 [Chemical formula 10] draws formula (I') with the cephem C-4 as neutral COOH and the oxime isobutyrate as COO-, i.e. the proton moved to the other carboxyl; p6 [Chemical formula 12] draws (I''). All of these give the SAME standard InChIKey DBPPRLRVDVJOCL-FQRUVTKNSA-N and DIFFERENT RDKit canonical SMILES, so under string-equality grading a faithful reading of p6 scores wrong while a faithful reading of p2 scores exact. The text at p6 says 'so the compounds of the both chemical structures are included in the present invention'. Collapsed to one row.
- *2-chloro-3,4-dihydroxy-N-(2-pyrrolidin-1-ylethyl)benzamide* — This is the catechol 'tail' of cefiderocol released by hydrolysis. It is drawn five times and never named.
- *cefiderocol sodium (mono-sodium salt, formula (II))* (unresolved) — Drawn five times as the inner salt (cephem COO- / pyrrolidinium N+) with the oxime isobutyrate as COO- Na+. The document prints its molecular weight at [0016] p6 as 774.20 and a hand-built SMILES from CID 77843966 with the isobutyric proton replaced by Na gives C30H33ClN7NaO10S2, RDKit MW 774.21 - agreement to 0.01. But PubChem has NO record for that structure (a /compound/smiles/ search returns nothing) and the salt is never named in words, so there is no second CATALOGUED view and no CID. Left unresolved rather than putting a CID-less SMILES in molecules[].
- *dimeric degradation product of cefiderocol* (unresolved) — Drawn five times, always unnamed, and by far the largest depiction in the document: two complete aminothiazolyl-oximino-cephem units joined by a C-C bond from the C-3' methylene of one cephem into the thiazole ring of the other. The text only calls it 'the compound represented by formula (IV)' and caps it at 0.06%. No printed name, no molecular weight, no PubChem record - one hand reading with no second view.

#### `EP3299356B1_pleuromutilin` — 14 drawn, 2 resolved, 1 generic, 1 unresolved

EP 3 299 356 B1, Nabriva Therapeutics, granted 2021-11-24 (priority 2010-05-26), "Process for the preparation of pleuromutilins"

**Why it is here.** The tricyclic DITERPENE ring system - a fused 5-6-8 carbocycle with eight stereocentres drawn as a non-standard polygon layout, unlike any other skeleton in the corpus. It also gives a clean UNDER-SPECIFICATION case: the drawn side-chain cyclohexane carries one hashed bond among three ring stereocentres, so the drawing cannot be read as lefamulin even though lefamulin is what the process makes.

**Drawing style.** EPO B1: vector text with bitonal clippings around 1000-1230 px wide. Every methyl is spelled out as CH3 or H3C and the terminal vinyl as CH2; the eight-membered ring is drawn as an irregular octagon with three bold-wedge and three hashed-wedge bonds inside it.

**Counts and page tally.** About 14 depictions on the kept pages, two catalogued; the count is an estimate from image objects rather than a box-by-box census. This group is a two-molecule recall test on a hard ring system plus a precision test against a generic epimer pair that looks almost exactly like the real compound.

**Caveats.**

- *pleuromutilin* — The only NATURAL PRODUCT in round 9 and the only 8-membered carbocycle. Its eight stereocentres are drawn purely as wedges with no CIP letters anywhere in the document.
- *14-O-[(4-amino-2-hydroxycyclohexyl)sulfanylacetyl]mutilin* — AN HONEST UNDER-SPECIFICATION, and the reason this row is not lefamulin. The drawn cyclohexane has THREE stereocentres (C-1 sulfanyl, C-2 hydroxy, C-4 amino) and only ONE drawn stereo bond, the hashed S. One wedge among three centres fixes nothing. Fully specifying them gives lefamulin, CID 58076382, InChIKey KPVIXBKIJXZQJX-CSOZIWFHSA-N - the SAME skeleton block as this row with a different stereo layer. Choosing lefamulin as the reference would score a correct, faithful reading of this drawing as wrong.
- *formulae (IIa) and (IIb) - the R-genus epimer pair* (generic) — Two drawings identical to formula (I) except that the cyclohexane amine carries a variable R and the bond to it is HASHED in (IIa) and BOLD in (IIb). They are a generic drawn twice to define two epimers, which means the pair encodes a stereochemical distinction on top of an unresolved substituent - neither half is a molecule.
- *the further protected intermediates on pp3-4, 9-10 and 15-17* (unresolved) — About eight more boxes, all coded or R-substituted. Score this group recall-only against the two rows.

#### `EP3529236B1_eravacycline` — 32 drawn, 5 resolved, 0 generic, 5 unresolved

EP 3 529 236 B1, Tetraphase Pharmaceuticals, Inc., application 17794505.2 filed 2017-10-19 (priority 2016-10-19 US), granted 2024-02-07, "Crystalline forms of eravacycline" - the XERAVA bis-hydrochloride Forms A/B/I/J

**Why it is here.** THE ROUND'S SINGLE-WEDGE TEST. p25 prints a gallery of eight process impurities of eravacycline, two of which - 'Epimer (TP-498)' and 'TP-034' - are drawn identically except that ONE bond to the C-4 dimethylamino group is a bold wedge in the first and a hashed wedge in the second, and both are real, distinct PubChem records. It also brings a tetracycline scaffold, which the corpus lacked.

**Drawing style.** EPO B1: vector text with 300-dpi structure clippings. Two clipping classes - a small one (992x327) carrying the single Structural Formula 1, repeated on nine pages, and large gallery/scheme clippings on pp25-28. pp36-52 of the original are seventeen full-page XRPD/TGA/DSC/DVS sheets and were dropped.

**Counts and page tally.** 32 depictions on the kept pages, only TEN distinct compounds. Page tally: p2 x1, p3 x1, p19 x2, p25 x6, p26 x5, p27 x4, p28 x4, p30 x1, p31 x2, p32 x2, p33 x1, p34 x2, p35 x1. pp30-35 are the English (p30-32), German (p32-34) and French (p34-35) claims, which redraw the bis-HCl formula nine times between them. The five schemes on pp19 and 26-28 each draw the SAME salt twice, once as 'Form B' and once as 'Form I' - the two crystal forms are chemically identical and a structure recogniser cannot tell them apart, so each scheme contributes two depictions and zero new compounds. Non-structure content on the kept pages: the Table 8 impurity-purging table on p25 and the batch tables on pp27-28. The seventeen full-page XRPD/DSC/TGA/DVS sheets (pp36-52) and the peak tables were dropped.

**Caveats.**

- *eravacycline* — The p25 gallery labels this drawing 'TP-034', a digit transposition of TP-434 - Table 8 immediately above it lists the row as TP-434. It is drawn as an impurity of its own hydrochloride salt.
- *eravacycline dihydrochloride* — A pipeline that segments the components separately emits eravacycline plus hydrogen chloride and matches the eravacycline row, not this one. The salt is drawn with the HCl written as a free-floating label rather than joined by a dot glyph on pp26-28, and with '2HCl' inline on p3 - two different salt notations for one compound inside one document.
- *4-epi-eravacycline* — THIS IS THE ROUND-6 STEREO NEAR-MISS MADE EXPLICIT AND DELIBERATE. Eravacycline is AKLMFDDQCHURPW-ISIOAQNYSA-N and its C-4 epimer is AKLMFDDQCHURPW-BNWPUYEGSA-N: identical formula, identical skeleton InChIKey block, one differing stereo layer, both real PubChem records, and the document draws them 400 pixels apart. A tool that ignores wedge direction returns the same SMILES for both and scores one exact and one wrong, with no signal that it guessed.
- *1-methylpyrrolidin-2-one* — A residual SOLVENT drawn in a gallery of drug-related impurities - a small-molecule class a tool tuned to drug-like structures may skip.
- *2-(pyrrolidin-1-yl)acetic acid* — The acid half of eravacycline's C-9 side chain, released by amide hydrolysis. Its carboxyl is drawn as the CONDENSED label CO2H, not as an expanded C(=O)OH.
- *M-16 (TP-6773)* (unresolved) — Drawn in the p25/p26 impurity gallery with NO chemical name - only a mass-shift code and a Tetraphase compound number, both of which Table 8 also uses. A mass shift is not a structure, so there is no second independent view against which to check a hand reading of a fully substituted tetracycline; putting a guessed SMILES here would convert a correct prediction into a scored failure.
- *M-18 (TP-5799)* (unresolved) — Drawn in the p25/p26 impurity gallery with NO chemical name - only a mass-shift code and a Tetraphase compound number, both of which Table 8 also uses. A mass shift is not a structure, so there is no second independent view against which to check a hand reading of a fully substituted tetracycline; putting a guessed SMILES here would convert a correct prediction into a scored failure.
- *M-2 (TP-4705)* (unresolved) — Drawn in the p25/p26 impurity gallery with NO chemical name - only a mass-shift code and a Tetraphase compound number, both of which Table 8 also uses. A mass shift is not a structure, so there is no second independent view against which to check a hand reading of a fully substituted tetracycline; putting a guessed SMILES here would convert a correct prediction into a scored failure.
- *M+14 (TP-363)* (unresolved) — Drawn in the p25/p26 impurity gallery with NO chemical name - only a mass-shift code and a Tetraphase compound number, both of which Table 8 also uses. A mass shift is not a structure, so there is no second independent view against which to check a hand reading of a fully substituted tetracycline; putting a guessed SMILES here would convert a correct prediction into a scored failure.
- *M+94 (TP-3978)* (unresolved) — Drawn in the p25/p26 impurity gallery with NO chemical name - only a mass-shift code and a Tetraphase compound number, both of which Table 8 also uses. A mass shift is not a structure, so there is no second independent view against which to check a hand reading of a fully substituted tetracycline; putting a guessed SMILES here would convert a correct prediction into a scored failure.

#### `EP3592362B1_taniborbactam` — 10 drawn, 2 resolved, 0 generic, 3 unresolved

EP 3 592 362 B1, Venatorx Pharmaceuticals, Inc., application 18763383.9 filed 2018-03-06 (priority 2017-03-06 US), granted 2025-02-19, "Solid forms and combination compositions comprising a beta-lactamase inhibitor and uses thereof" - crystalline taniborbactam (VNRX-5133) dihydrochloride with cefepime

**Why it is here.** A BORON drug - the corpus had no boronic acid - and p5 draws the SAME compound twice, once as the closed cyclic benzoxaborinine and once as the open acyclic boronic acid, two different molecular formulae for one substance. It also exposes a silent PubChem normalisation on the cyclohexane stereochemistry.

**Drawing style.** EPO B1: vector text with bitonal structure clippings, small (818x284) for the single-compound drawings and larger for the p21 scheme. Trilingual claims - EN p36, DE p37, FR p38 - each redrawing compound 1. The fifteen full-page XRPD/DSC/TGA/DVS sheets on pp40-54 were dropped.

**Counts and page tally.** 10 depictions of four distinct species. Page tally: p3 x1, p5 x2 (closed and open forms), p9 x1, p12 x1, p21 x2 (Structure 2 -> Compound 1 dihydrochloride), p36 x1, p37 x1, p38 x1. Non-structure content on the kept pages: XRPD 2-theta peak tables on pp3, 5 and 9, the DSC/TGA/DVS method text on p21, and the dosing-regimen Table 22 on p36. The fifteen full-page instrument sheets (pp40-54) were dropped.

**Caveats.**

- *taniborbactam* — SILENT STEREO NORMALISATION - the most dangerous thing in this group. The document says trans-4-cyclohexyl in words AND draws it trans (hashed + bold). PubChem CID 76902493 does NOT encode the cyclohexane at all: its own InChIKey is PFZUWUXKQPRWAL-PXCJXSSVSA-N (undefined). Submitting the trans-specified SMILES (PFZUWUXKQPRWAL-BJJXKVORSA-N) to PUG-REST /compound/smiles/ returns CID 76902493 anyway, with nothing in the response saying the query carried stereochemistry the record does not. So a FAITHFUL reading of this drawing scores stereo, not exact, against this reference, and a tool that drops the cyclohexane wedges scores exact. That is a property of the reference, not of the prediction.
- *taniborbactam dihydrochloride* — SALT NOTATION TRAP. The claimed compound is the DIHYDROCHLORIDE, but seven of the ten depictions - every one outside Example 1 - draw only the free base with no counterion, and the salt exists solely in the surrounding words. Only p21 draws it, and it writes the counterions as the condensed text '(HCl)2', not as two dot-separated components.
- *taniborbactam, open acyclic boronic acid form* (unresolved) — p5 draws compound 1 a second time as the RING-OPENED species: a free B(OH)2, a free phenol OH, and the benzoate CO2H, with the text 'Compound 1 may exist in an equilibrium between the "closed" cyclic form (as shown above) and the "open" acyclic form'. It is a different molecular formula from the closed form - C19H30BN3O6 against C19H28BN3O5, one water apart - so it is a different molecule, not a redraw. A PUG-REST /compound/smiles/ search on the hand reading returns CID 0: PubChem has no record of the open form. One view only. The same paragraph adds that 'Compound 1 may associate into intramolecular dimers, trimers, and any combinations thereof', which no single SMILES expresses either.
- *Structure 2 (bis-Boc pinanediol boronate precursor)* (unresolved) — The document prints its FULL IUPAC name at [0149] - 'tert-butyl 3-((R)-2-(2-((1r,4R)-4-((tert-butoxycarbonyl)(2-((tert-butoxycarbonyl)amino)ethyl)amino)cyclohexyl)acetamido)-2-((3aS,4S,6S,7aR)-3a,5,5-trimethylhexahydro-4,6-methanobenzo[d][1,3,2]dioxaborol-2-yl)ethyl)-2-methoxybenzoate' - and PubChem returns NOT FOUND for it. Six stereocentres, four of them in the pinanediol bicycle, and no second view to check a hand-built SMILES against. Given that this group has already shown PubChem silently accepting over-specified stereochemistry, a hand-built reference here would be exactly the wrong-enantiomer failure this corpus exists to catch. Left unresolved.
- *cefepime (named in the text and claims, never drawn)* (unresolved) — Cefepime is the co-formulated partner and appears in claim 4 onwards and throughout the dosage tables, but it is NEVER drawn anywhere in the document. A text-mining stage emits it and scores a false positive; a structure recogniser correctly emits nothing.

#### `EP3643719B1_spiropyrimidinetriones` — 24 drawn, 0 resolved, 1 generic, 1 unresolved

EP 3 643 719 B1, granted 2022-08-10 (priority 2017-06-22 CN), "Thiazolidone spiro pyrimidine trione compound, preparation method therefor and uses thereof" - thiazolidinone analogues of zoliflodacin (AZD0914)

**Why it is here.** THE ROUND'S ZERO-BY-DESIGN GROUP, and it scores zero for a different reason from round 6's auristatin patent. Every specific compound here IS fully drawn and IS fully named with a correct IUPAC name - and not one of the eighteen exists in PubChem, because they are new chemical entities from a 2017 Chinese filing. It is the cleanest available measurement of what a benchmark can and cannot grade: the drawings are excellent, the names are excellent, and there is no reference.

**Drawing style.** EPO B1: vector text with bitonal clippings. The claim genus on p3 uses TWO unusual Markush devices - asterisks (* and **) marking stereocentres whose configuration is defined in prose, and a DASHED CURVED LINE joining R2 and R3 to mean 'optionally taken together to form a ring'.

**Counts and page tally.** About 24 depictions on the kept pages and ZERO scoreable molecules. Page tally: p3 x1 (genus), pp4-9 roughly x20 (Compounds 1-18 plus intermediates, counted from image objects rather than box by box), p77-78 x3 (the genus redrawn in the claims). SCORE THIS GROUP FOR FALSE POSITIVES ONLY: precision and recall over molecules[] are both undefined, exactly as they are for round 6's US9463252B2 auristatin group. The contrast between the two is the useful part - the auristatin patent scores zero because nothing in it is a molecule, and this one scores zero because everything in it is a molecule that no public database has ever catalogued.

**Caveats.**

- *formula (I) and (Ia) - the R1/R2/R3 genus with asterisk stereocentres * (generic) — The claim genus. The dashed loop between R2 and R3 is the device to watch: it is drawn as a curved dashed arc floating above the thiazolidinone, not as a bond, and it means the two substituents may close a ring. A recogniser that reads it as a bond emits a bicycle that does not exist; one that ignores it loses the only information the arc carries. The asterisks * and ** sit ON ring atoms and are stereocentre markers, not atom labels.
- *Compounds 1-18, each drawn and each named with a full IUPAC name, none* (unresolved) — Example headings such as 'Example 1: (2R,4S,4aS)-11-fluoro-2,4-dimethyl-8-(2-oxothiazolin-3-yl)-1,2,4,4a-tetrahydro-2'H,6H-spiro[isoxazole[4,5-g][1,4]oxazine[4,3-a]quinoline-5,5'-pyrimidine]-2',4',6'(1'H,3'H)-trione (Compound 1)' give the complete constitution and all three stereocentres. PubChem's name endpoint returns NOT FOUND for these names, and the parent drug they are analogues of - zoliflodacin, CID 76685216 - is NAMED in the text as AZD0914 twenty-six times and NEVER DRAWN. So the document contains eighteen fully specified, fully named, correctly drawn molecules and zero scoreable references. Assigning zoliflodacin's CID to any of them would be wrong: they differ from it by an oxazolidinone-to-thiazolidinone swap plus ring substituents.

#### `EP3719020B1_BLI_gallery` — 24 drawn, 7 resolved, 0 generic, 1 unresolved

EP 3 719 020 B1, Qilu Pharmaceutical Co., Ltd., filed 2018-11-30 (priority 2017-12-01 CN 201711251386.3), granted 2022-09-21, "Crystal form of beta-lactamase inhibitor and preparation method therefor"

**Why it is here.** A GALLERY OF SIX NAMED BETA-LACTAMASE INHIBITORS on two pages - clavulanic acid, sulbactam, tazobactam, avibactam, relebactam and nacubactam - drawn side by side in three different charge conventions, plus the claimed compound. It is the densest beta-lactam/beta-lactamase content in the round and its charge-state mix is a single controlled experiment in how a reference represents ionisation.

**Drawing style.** EPO B1: vector text with bitonal clippings; the p2/p3 prior-art gallery is two multi-structure clippings with captions baked into the image. Trilingual claims - EN p17, DE p18, FR p19-20 - each redrawing formula (I). p7 carries a full synthesis scheme with coded intermediates.

**Counts and page tally.** About 24 depictions, seven distinct compounds, all seven resolved. Page tally: p2 x3 (clavulanic acid, sulbactam, tazobactam in ONE clipping), p3 x4 (avibactam, relebactam, nacubactam in one clipping plus formula (I)), p7 ~x10 (the Embodiment-1 scheme, ESTIMATED from an 80-dpi render), p17 x2, p18 x2, p19 x2, p20 x1. THE CHARGE-CONVENTION EXPERIMENT: within the six-member gallery, clavulanic acid / sulbactam / tazobactam are drawn NEUTRAL and their PubChem records are neutral (exact match possible); avibactam is drawn with an EXTERNAL Na+ and PubChem's avibactam sodium is the same two-component salt (exact match possible); relebactam, nacubactam and formula (I) are drawn as INNER SALTS with a protonated amine or guanidine against a sulfate anion, while every PubChem record for them is NEUTRAL - so a faithful reading of those three scores wrong under string equality and right under a charge-normalising comparison. Three conventions in one figure, and the same six-membered ring system throughout. p21 was kept as a non-structure negative (a full-page XRPD pattern).

**Caveats.**

- *clavulanic acid* — This compound is ALSO in the corpus as the subject of round 5's US4110165_clavulanic_acid.pdf, where it is 1978 hand-inked draftsman art. Here it is 2022 vector ChemDraw. Same molecule, two drawing eras, two documents - useful, not a duplicate document.
- *avibactam sodium* — The only member of the p2/p3 gallery drawn with an EXTERNAL counterion. Its three DBO neighbours are drawn as inner salts instead, so one gallery of six mixes three charge conventions.
- *relebactam* — Drawn as an INNER SALT (zwitterion) while the PubChem record is neutral - see the group note.
- *nacubactam* — The SAME compound is the subject of this round's EP3067355B1_nacubactam group, where it is drawn neutral and identified by a full IUPAC name. Here it is drawn as a zwitterion and identified by a bare development code. Two groups, two conventions, one molecule.
- *compound of formula (I) - [(2S,5R)-2-[2-(diaminomethylideneamino)oxyet* — TAUTOMER NOTE: writing the guanidine as -O-N=C(N)N (PubChem's form) or as -O-NH-C(=N)N (the drawn form) gives the SAME InChIKey HOJIPBUGHMYVQD-RQJHMYQMSA-N and TWO DIFFERENT RDKit canonical SMILES. Under string equality one of them is wrong; under InChIKey both are right. Drawn as an INNER SALT (zwitterion) while the PubChem record is neutral - see the group note.
- *p7 Embodiment-1 scheme intermediates 1-A to 1-F* (unresolved) — About ten structures in one scheme, labelled only with document-internal codes (1-A, 1-B, ...). The surrounding text names the REAGENTS (N-hydroxyphthalimide, triethylamine, N,N-dimethylformamide) but never the intermediates, and several carry phthalimide and Boc protecting groups drawn in full. No printed name, no mass, no second view.

#### `EP3868768B1_contezolid_acefosamil` — 6 drawn, 2 resolved, 0 generic, 1 unresolved

EP 3 868 768 B1, MicuRx Pharmaceutical (Zhejiang)/Shanghai MicuRx, application 19872651.5 filed 2019-10-14 (priority 2018-10-15 CN), granted 2024-06-12, "Pharmaceutical crystal of contezolid acefosamil, preparation method therefor, and uses thereof"

**Why it is here.** A recent oxazolidinone whose INN is printed in the title; a two-member scheme with a resolvable intermediate; and, at 380 KB for the whole grant, it costs nothing to keep the three full-page XRPD/DSC sheets as a figure-class false-positive test.

**Drawing style.** EPO B1: vector text with 5 inline structure clippings, one of which (p6) holds a two-member reaction scheme. Trilingual claims - EN p8, DE p9, FR p10 - each redrawing formula (I). pp11-13 are three full-page instrument plots.

**Counts and page tally.** 6 depictions in 5 clippings, only TWO distinct compounds. Page tally: p2 x1 (formula I), p6 x2 (a single clipping holding Intermediate-1 -> Example 1 over a TMSI/Ac2O/NaOAc arrow), p8 x1, p9 x1, p10 x1 (the same formula I redrawn in the English, German and French claims). Non-structure figures kept on purpose: p11 FIG 1-3 XRPD, p12 FIG 4-5 DSC, p13 FIG 6-7 - three full-page instrument sheets with no chemistry, plus DSC/XRPD parameter tables on pp5-6 and a 2-theta peak table on p7.

**Caveats.**

- *contezolid acefosamil* — STEREO CHECK, and it is a CIP-letter trap rather than a geometry trap. PubChem names contezolid itself (CID 25184541) (5S) and contezolid acefosamil (CID 131750213) (5R) at the SAME oxazolidinone carbon with the SAME spatial arrangement: phosphorylating the exocyclic nitrogen puts a P in the second sphere and flips the CIP letter. Confirmed independently by taking CID 25184541's SMILES, replacing only the N-H, and canonicalising - InChIKey JANNTEAGZXJITO-BTQNPOSSSA-M, identical to CID 131750213. Writing the wedge the other way gives JANNTEAGZXJITO-ZOWNYOTGSA-M, a distinct key with the same skeleton block. The 2D layout was read out independently (O-1 up, C-4 left, bold-wedge CH2 down-right, H back = clockwise a>b>c = R) and agrees.
- *Intermediate-1 (diisopropyl phosphoramidate of contezolid)* — The label is misspelled in the drawing itself, which is a small OCR trap on the caption rather than the structure.
- *linezolid, contezolid (named in the text, never drawn)* (unresolved) — [0002] names linezolid as 'the first drug of this class' and [0003] names contezolid as the parent drug; NEITHER is ever drawn. A text-mining stage that emits every INN it finds scores two false positives here, and a structure recogniser correctly emits neither. Deliberately left out of molecules[] - named but not drawn is not a scoreable molecule for an OCSR benchmark.

### Antibacterial — antimycobacterial

#### `EP4003521B1_telacebec` — 3 drawn, 2 resolved, 0 generic, 2 unresolved

EP 4 003 521 B1, Qurient Co. Ltd., granted 2024-05-29, "Different forms of 6-chloro-2-ethyl-N-(4-(4-(4-(trifluoromethoxy)phenyl)piperidine-1-yl)benzyl)imidazo[1,2-a]pyridine-3-carboxamide" - solid forms of telacebec (Q203), an anti-tuberculosis clinical candidate

**Why it is here.** The counterion-notation and figure-class test for the antibacterial half of the round. Its two structure drawings are the free base and a DITOSYLATE whose two counterions sit inside a square bracket with a subscript 2; three further salts and eight more salt formers are named only in words; and the original document is 156 pages of which about 78 are full-page XRPD/DSC/NMR plots.

**Drawing style.** EPO B1: vector text with bitonal clippings. Only three of the 156 original pages carry a chemical structure; the rest of the image population is instrument plots. OCF3 is drawn as the condensed label F3CO.

**Counts and page tally.** Only 3 depictions in the whole 156-page grant, and two of them are the same free base with and without counterions. Page tally on the kept pages: p2 x1 (ditosylate), p22 x1 (free base), p68 x1 (ditosylate, claim 1). Kept deliberately as negatives: p3 and p69, two full-page XRPD patterns - representatives of the ~78 instrument sheets on pp3-8, 61-63 and 78-155 of the original - and p51, a salt-former table. A pipeline that treats a numbered figure or a bordered plot as a structure scores dozens of false positives on the full document and two on this extract.

**Caveats.**

- *telacebec ditosylate* — COUNTERION NOTATION. The stoichiometry lives entirely in a bracket subscript outside the drawn tosylic acid - there is no dot glyph and no second drawn copy of the acid. A tool that reads the bracket contents once and ignores the subscript emits the MONO-tosylate, which the document also claims separately as a different compound (claim 6), so the error resolves to a real but wrong species.
- *telacebec* — The INN telacebec is never printed; the document uses the code Q203 and the IUPAC name. No stereocentres anywhere in this document.
- *mono-hydrochloride, mono-phosphate and mono-tosylate salts (claimed an* (unresolved) — Claims 6-9 claim three further mono-acid addition salts by NAME and identify each only by an XRPD peak list. Not one of them is drawn. This is the US4879303A amlodipine-besylate failure mode recorded in the corpus README - a salt-versus-salt comparison that looks ideal until you find the counterions exist only as words.
- *eight salt formers in Table 21 (lactobionic, ascorbic, 2-furoic, galac* (unresolved) — p51 is a salt-screening table listing acid partners by common name with molar ratios and XRPD form codes, immediately below a drawn structure. The adjacency is the trap: a pipeline that associates the table rows with the structure above them will emit co-crystals that were never drawn.

#### `EP4121058B1_oxazolidinone_TB` — 22 drawn, 9 resolved, 0 generic, 1 unresolved

EP 4 121 058 B1, granted 2026-02-18 (priority 2020-03-20), "Oxazolidinone compound and its use thereof as an antibacterial agent" - a thiomorpholine-dioxide oxazolidinone for Mycobacterium tuberculosis

**Why it is here.** The highest scoreable density in the round: a complete seven-step route on ONE page, every step captioned with its full IUPAC name, and nine distinct compounds that all resolve. It also carries three condensed-label classes (NHCbz, OAc, NHAc) and a stereocentre whose two enantiomers are both real PubChem records.

**Drawing style.** EPO B1: vector text with bitonal clippings. The p10 scheme is ONE tall image split across four PDF image objects, so pdfimages reports four bands and a naive per-image segmenter cuts three structures in half. Trilingual claims - EN pp14-15, DE p16, FR p17 - each redrawing formula (I).

**Counts and page tally.** 22 depictions, nine distinct compounds, ALL NINE RESOLVED. Page tally: p3 x2, p4 x1, p10 x9 (the whole Step A-G route plus its starting material and co-reagent), p14 x5 (formula I in claim 1 plus four comparator structures inside two PK tables), p15 x1, p16 x2, p17 x2. Non-structure images that are NOT structures and must not be counted as such: the p1 EPO barcode, and three 1535x55 text-strip rasters on p13 which are the inline 'lambda-6' superscript typography, not chemistry. There are no instrument plots in this document at all.

**Caveats.**

- *compounds 48 and 59 of WO2017/070024* (unresolved) — Two comparator structures drawn inside the cells of the p14 PK tables, captioned only 'Example # from WO2017/070024: 48' and '59'. A document-external example number is not a name and there is no second view; both are drawn small inside a bordered table cell, which is also a segmentation trap - the cell borders read as a structure box.

### Antiviral

#### `EP3321253B1_tecovirimat` — 32 drawn, 9 resolved, 0 generic, 0 unresolved

EP 3 321 253 B1, Siga Technologies, Inc., granted 2020-02-12 (priority 2012-08-16 US), "Method of preparing tecovirimat" - the TPOXX / ST-246 smallpox antiviral

**Why it is here.** A RIGID POLYCYCLIC CAGE - a cyclopropane-fused bicyclo[2.2.2]octene imide - drawn with six explicit stereo hydrogens on wedges and no CIP letters anywhere. Nothing else in the corpus has this shape. Nineteen pages at 362 KB, so the whole grant fits.

**Drawing style.** EPO B1: vector text with 32 bitonal structure clippings across pp4-18, mostly small single-compound boxes. Scheme 5 on p4 and p14 is drawn at about a third the size of the rest, so its four structures are near-illegible at 100 dpi and only resolve above 300.

**Counts and page tally.** 32 depictions, nine distinct compounds, ALL NINE RESOLVED. Page tally from pdfimages: p4 x2 clippings (Scheme 5 holds four structures), p5 x4, p6 x3, p7 x4, p8 x3, p9 x1, p10 x2, p11 x2, p12 x1, p13 x2, p14 x2 (Scheme 5 again), p15 x2, p16 x3, p17 x2, p18 x2 - pp9-13 are the English claims, pp14-18 the German and French claims, and each redraws the same cage compounds. THE POINT OF THIS DOCUMENT is that every cage structure differs from its neighbours by one atom or one substituent - imide N vs anhydride O, NH2 vs NHBoc vs NHC(=O)Ar, CF3 vs I - while six stereocentres stay constant, so a reader that gets the cage right and the substituent wrong lands on a DIFFERENT REAL PubChem record every time. Non-structure content: none.

**Caveats.**

- *tecovirimat* — Six drawn stereo hydrogens on a rigid cage: no chain to twist, and the drawing gives no CIP letters. Everything downstream in this group was derived from THIS record's geometry rather than re-read from each drawing.
- *(1R,2R,6S,7S,8S,10R)-4-amino-4-azatetracyclo[5.3.2.0(2,6).0(8,10)]dode* — TWO DRAWINGS, TWO PROTONATION STATES, ONE CODE. Scheme 5 draws compound 7 as its hydrochloride using a condensed label; p8 draws the free base. A PUG-REST search on the hydrochloride returns nothing, so the scoreable row is the free base and a faithful reading of the Scheme-5 drawing scores wrong.
- *tert-butyl N-(3,5-dioxo-4-azatetracyclo[5.3.2.0(2,6).0(8,10)]dodec-11-* — PubChem writes this one's cage as (1S,2S,6R,7R,8R,10S) and its N-amino neighbour as (1R,2R,6S,7S,8S,10R). Both are the same cage: with a symmetric N-substituent the cage is meso and the descriptors can be assigned from either end. The InChIKeys, not the letters, settle it.
- *N-(2,5-dioxopyrrol-1-yl)-4-(trifluoromethyl)benzamide* — This and tecovirimat differ ONLY by the cage: the maleimide is the dienophile and tecovirimat the adduct. A tool that misses the four-ring cage returns exactly this molecule, which is a real record - so the error scores as a confident wrong answer rather than a failure to read.

#### `EP3473629B1_baloxavir_route` — 13 drawn, 7 resolved, 1 generic, 1 unresolved

EP 3 473 629 B1, Shionogi & Co., Ltd., granted 2022-11-16 (priority 2016-06-20 JP), "Method for producing substituted polycyclic pyridone derivative and crystal of same" - the baloxavir marboxil (XOFLUZA) tricyclic core route

**Why it is here.** A SEVEN-MEMBER LINEAR ROUTE building a fused 1,4,7-triazatricyclo[7.4.0.0(3,7)] system, in which NOT ONE compound carries a chemical name - every box is labelled 165A, 165B ... 165 - and all seven still resolve, because the ring system is unambiguous once read. The complement to the name-rich groups in this round.

**Drawing style.** EPO B1: vector text with large bitonal scheme clippings. Section headings are Japanese-style '[Chem. 1]', '[Chem. 2]' rather than 'Scheme'. OBn, CO2Me, CO2H and CHO are all condensed labels.

**Counts and page tally.** About 13 depictions on the kept pages, seven catalogued and all seven resolved; the count is an estimate because pp4 and 22 were counted from image objects. THE STEREOCHEMICAL POINT is a negative one and it is stated by the document itself: [0011] says 'a reduction in the optical purity of an optically active substituted cyclic pyridone derivative occurs in a coupling step', i.e. the whole invention is about preserving a stereocentre - yet every one of the seven structures in the p3 route is drawn FLAT, with no wedge anywhere, because the stereocentre is set later. A reader that infers stereochemistry from the surrounding prose rather than from the drawing will over-specify all four of the tricyclic members.

**Caveats.**

- *formulae (I)-(VI) of the [Chem. 1] genus* (generic) — The p2 clipping holds the claim genera with R-groups; [0009] refers them to WO 2016/175224 rather than defining a specific compound.
- *the p4 and p22 scheme boxes* (unresolved) — Further coded intermediates and the thiepine coupling partner, not catalogued. Score this group recall-only against the seven p3 rows.

#### `EP3512863B1_ethynyl_nucleosides` — 12 drawn, 3 resolved, 1 generic, 1 unresolved

EP 3 512 863 B1, ATEA Pharmaceuticals, Inc., granted 2021-12-08 (priority 2016-09-07 US), "2'-substituted-N6-substituted purine nucleotides for RNA virus treatment" - the bemnifosbuvir (AT-527) series

**Why it is here.** A PHOSPHORUS STEREOCENTRE DRAWN AS A WAVY BOND, on a molecule whose four sugar stereocentres are drawn with ordinary wedges - a single depiction that mixes 'this centre is defined' and 'this centre is deliberately not' - plus a 2'-substituent whose triple bond is easily read as a bold wedge at low resolution.

**Drawing style.** EPO B1: vector text with bitonal clippings, mostly 620-900 px, four to six per page in the claim galleries. The furanose is drawn in the standard Haworth-like projection with a bold wedge to the base and hashed wedges to the 3'-OH.

**Counts and page tally.** 12 depictions on the kept pages, three catalogued. TWO READING TRAPS, both settled by zooming. (1) The 2'-substituent is an ETHYNYL drawn as a bold wedge into a triple bond; at 100 dpi the wedge and the two triple-bond lines merge into what looks like a single '=' or a plain methyl wedge, and reading it as methyl gives bemnifosbuvir (CID 122527275) - a real, marketed, wrong answer. These are the 2'-ethynyl analogues, not AT-527. (2) In both ProTide drawings the bond from phosphorus to the alaninyl nitrogen is a WAVY line: the P stereocentre is deliberately undefined while the four sugar centres beside it are drawn with hard wedges. PubChem's bemnifosbuvir record specifies P as [P@]; the records matching these drawings do not. Kept as a non-structure negative: p33, a page of tables.

**Caveats.**

- *formula I and the R3A/R3B phosphoramidate fragment* (generic) — The p5 genus carries Y, R3, R4, R12 and R13; the p6 drawing is a PHOSPHORUS FRAGMENT with a SQUIGGLY OPEN VALENCE - an isolated P(=O)(R3A)(R3B) with a wavy line where the rest of the molecule attaches. That is the auristatin fragment class from round 6 appearing in a nucleotide patent.
- *the other claim-gallery nucleosides (N6-methyl-N6-cyclopropyl, N6,N6-d* (unresolved) — About six further fully specified structures in the same two galleries, differing only in the N-6 amine. Not catalogued for time; score this group recall-only against the three rows.

#### `EP3544977B1_pritelivir` — 12 drawn, 2 resolved, 0 generic, 1 unresolved

EP 3 544 977 B1, AiCuris Anti-infective Cures GmbH, granted 2021-05-19 (priority 2016-11-28 EP), "A maleate salt of the free base of N-[5-(aminosulfonyl)-4-methyl-1,3-thiazol-2-yl]-N-methyl-2-[4-(2-pyridinyl)-phenyl]-acetamide, ..." - pritelivir (BAY 57-1293, AIC316)

**Why it is here.** A RASTER-SCANNED drawing register inside an otherwise vector EPO B1 - the structures are grey, soft-edged bitmaps, unlike every other EPO document in this round - and each is captioned with its MOLECULAR FORMULA AND MASS in square brackets, which is the second independent view round 6 valued in the niraparib group. It also captions one drawing with THREE different names for one compound.

**Drawing style.** EPO B1 whose structure clippings are SCANNED greyscale rasters, visibly soft and speckled, in contrast to the crisp bitonal vector-derived clippings elsewhere in this round. Formulas and masses are printed under the drawings as C18H18N4O3S2 [402.49] and C22H22N4O7S2 [518.56]. pp42-88 of the original are 47 full-page instrument sheets.

**Counts and page tally.** 12 depictions of three species. Page tally: p5 x1 (free base with the three-name caption), p6 x1 (formula (I), base + maleic acid), p12 x2 (a BOXED before/after conversion diagram, free base -> maleate, with formulas and masses under each), p14 x2, p15 x2, p16 x2, p17 x2 - the English, German and French claims each redrawing formula (I) as base plus counterion. Kept as a non-structure negative: p42, one of the 47 full-page XRPD/DSC/NMR sheets on pp42-88 of the original. The p12 box is itself a segmentation trap: a rectangular border encloses two structures, an arrow and four lines of caption, so a box-detector returns one region where there are two molecules.

**Caveats.**

- *pritelivir* — THREE NAMES, ONE CAPTION, and only one of the three (pritelivir) resolves at PubChem's name endpoint - 'BAY 57-1293' and 'AIC316' are development codes. A name-first pipeline that takes the first line of the caption gets nothing.
- *maleic acid* — The Z geometry is the whole identity here: the E isomer is fumaric acid, CID 444972, a different real record with the same formula. Round 5's asenapine group hit the same fork. The drawing settles it - both COOH point to the same side.
- *pritelivir maleate (formula (I), the CLAIMED compound)* (unresolved) — The claimed substance and the most-drawn thing in the document, and PubChem has NO record of it: the name 'pritelivir maleate' returns NOT FOUND and a /compound/smiles/ search on the two-component salt built from CID 491941 plus CID 444266 returns nothing. The document prints its formula and mass, C22H22N4O7S2 [518.56], and a hand-built SMILES gives C22H22N4O7S2 at 518.57 - agreement to 0.01 - but a printed mass is not a second CATALOGUED view, so there is no CID and the row stays out of molecules[]. A pipeline that splits the two components matches the pritelivir and maleic acid rows instead, and is scored correct for both.

#### `EP3668859B1_lenacapavir` — 8 drawn, 2 resolved, 0 generic, 0 unresolved

EP 3 668 859 B1, Gilead Sciences, Inc., granted 2022-03-30 (priority 2017-08-17 US), "Solid forms of an HIV capsid inhibitor" - crystalline sodium salt forms of lenacapavir (GS-6207, SUNLENCA)

**Why it is here.** ATROPISOMERS DRAWN SIDE BY SIDE AND CLAIMED SEPARATELY. Round 6 flagged sotorasib's atropisomer claims as the most interesting thing in that round; this document goes further - it draws Isomer A and Isomer B as two 2D structures, states their equilibrium ratio and rotational barrier, and claims a process for enriching one over the other. No SMILES in existence distinguishes them. Ten fluorines and three sulfonyl groups also make it the most heteroatom-dense molecule in the round.

**Drawing style.** EPO B1: vector text with bitonal clippings; the p2 Compound 1 drawing is a large 889x884 box, the p5 atropisomer pair a 1696x577 side-by-side. Me, CF3 and F3C appear as condensed labels. pp61-75 of the original are fifteen full-page XRPD/DSC sheets.

**Counts and page tally.** 8 depictions of TWO species, one of which is never drawn. Page tally: p2 x1 (Compound 1), p3 x2, p5 x2 (Isomer A and Isomer B side by side), p9 x2, p48 x0, p50 x2 - actually p50 redraws the atropisomer pair inside the claims. Kept as non-structure negatives: p49 (claims text with XRPD peak lists) and p61 (a full-page XRPD pattern, one of fifteen in the original). The document's chemistry is a single molecule; what it tests is whether a reader invents a difference between two nearly identical drawings, or invents a salt that is only ever written in words.

**Caveats.**

- *lenacapavir* — THE ATROPISOMER PAIR. [0010] p5: 'Compound 1 ... consists of two atropisomers, Isomer A and Isomer B, that can rotate along one of the C-C bonds ... In solution, the two atropisomers coexist in the ratio of about 1:5 to 1:8 ... the rotational energy barrier is about 24 kcal/mol.' The p5 drawing shows both, and the ONLY visible differences are which of the three point stereocentres carry drawn wedges - the axial relationship itself is not drawn at all. The claims include a process for enriching one atropisomer over the other. Both depictions collapse to this single row: no SMILES here can tell them apart, and neither can any reading of the drawings.
- *lenacapavir sodium* — THE SODIUM SALT IS NEVER DRAWN. It is the claimed substance, defined only in words and by XRPD peak lists, while every drawing in the document is of the neutral free acid. [0010] even prints the pKa that justifies it - 6.7 at the sulfonamide - so the site of deprotonation is stated in text and nowhere in a picture.

#### `EP3953330B1_nirmatrelvir` — 27 drawn, 16 resolved, 2 generic, 1 unresolved

EP 3 953 330 B1, Pfizer Inc., granted 2022-10-12 (priority 2020-09-03 US), "Nitrile-containing compounds useful as antiviral agents for the treatment of a coronavirus infection" - the nirmatrelvir (PF-07321332, PAXLOVID) compound patent

**Why it is here.** The richest single group in the round: two schemes that draw SIXTEEN resolvable species including the drug, its MTBE solvate, two salts, and six reagents/solvents drawn as full structures. It also carries a protein SEQUENCE LISTING on p181 and an eight-member R4 Markush grid inside claim 1 on p182 - two non-molecule classes that sit immediately beside real chemistry.

**Drawing style.** EPO B1: vector text with large bitonal scheme clippings (up to 1830x2189). Every methyl is spelled out as CH3 and every tert-butyl as three CH3 - the drawings are maximally explicit, except CF3 and HCl which are condensed.

**Counts and page tally.** 27 depictions on the kept pages, 20 distinct species, 16 resolved. Page tally: p4 x1 (formula I genus), p53 x11 (starting ester HCl, Boc-tert-leucine, DIPEA, C31, C32, C7 mesylate, 4-methylmorpholine, C33, methanesulfonic acid, trifluoroacetic anhydride, 13), p63 x7 (C42, C16 HCl, 1-methylimidazole, T3P, the MTBE solvate, isopropyl acetate, 13), p182 x8 (the R4 grid). SIX of the sixteen resolved rows are REAGENTS OR SOLVENTS drawn as full structures with no label of any kind - DIPEA, 4-methylmorpholine, methanesulfonic acid, trifluoroacetic anhydride, 1-methylimidazole and isopropyl acetate. Any pipeline that filters to 'drug-like' loses six of sixteen here. TWO NON-STRUCTURE PAGES KEPT AS NEGATIVES: p62, an XRPD 2-theta peak table, and p181, a PROTEIN SEQUENCE LISTING in three-letter amino-acid codes laid out in numbered columns - a text block whose visual texture is unlike anything else in the corpus and which a layout model may segment as a figure.

**Caveats.**

- *nirmatrelvir* — The INN nirmatrelvir is never printed - the document uses '13' and 'PF-07321332'.
- *nirmatrelvir methyl tert-butyl ether solvate* — A SOLVATE drawn with a dot glyph, in the same document as the unsolvated drug on the same page. A tool that discards the second component matches the nirmatrelvir row instead of this one, and both rows are in this group, so that error is silently converted into a duplicate hit on the wrong row.
- *(2S)-2-amino-3-[(3S)-2-oxopyrrolidin-3-yl]propanamide hydrochloride* — A DOCUMENT-INTERNAL SALT INCONSISTENCY worth knowing: the synthesis of C16 at line 2370 makes the METHANESULFONATE, and p63 uses and draws the HYDROCHLORIDE. The code C16 alone does not fix the counterion; only the drawing does.
- *propylphosphonic anhydride (T3P)* — A phosphorus HETEROCYCLE with no carbon in the ring - an atom-type mix this corpus had no other example of.
- *C31 - methyl (1R,2S,5S)-3-[N-(tert-butoxycarbonyl)-3-methyl-L-valyl]-6* (unresolved) — Drawn and fully NAMED in the p53 Step 1 heading, and PubChem has NO record: a /compound/smiles/ search on C20H34N2O5 built from the neighbouring C32 acid returns CID 0, and the name endpoint 404s. Its own methyl ester C32 (CID 11660672) and its own amide C33 (CID 163283364) both exist. Left unresolved rather than inventing a reference - exactly the round-6 talazoparib compound-17 situation.
- *claim 1 formulae Ih-1a, Ih-1b, Ih-1c, Ii-1a, Ii-1b, Ii-1c, Ik-a, Ik-c* (generic) — EIGHT drawings in a 2x4 grid inside claim 1, each of which looks like a fully specified molecule at a glance - the bicyclic core, the nitrile warhead and the glutamine lactam are all drawn out with wedges - but every one carries a single R4 label on the tert-leucine alpha carbon. They are the most convincing Markush drawings in the round, and a tool that resolves any of them to nirmatrelvir is wrong.
- *formula I (claim genus, R1/R2/R3)* (generic) — The summary-of-invention genus with three R-groups defined in prose over half a page.

#### `EP4079746B1_molnupiravir` — 22 drawn, 5 resolved, 0 generic, 2 unresolved

EP 4 079 746 B1, Divi's Laboratories Limited, granted 2025-06-11 (priority 2021-04-23 IN), "Process for the preparation of molnupiravir"

**Why it is here.** THE SUGAR GROUP. Thirteen pages, 421 KB, and every structure is a ribofuranoside with four stereocentres including an anomeric one. It is the round's sharpest test of the failure the brief names: three PubChem records share this skeleton - the beta anomer, the alpha anomer and a stereo-undefined one - and a structure search on the wrong anomer returns a valid CID silently.

**Drawing style.** EPO B1: vector text with bitonal clippings, the two schemes as tall multi-structure images. Sugar stereochemistry is drawn with bold and hashed wedges on the ring substituents; NHOH, HOH2C and NH2.H2SO4 appear as condensed labels.

**Counts and page tally.** 22 depictions, seven distinct compounds, five resolved. The two schemes on pp3-4 carry the chemistry; pp5 and 7-11 are the English, German and French claims, each redrawing formulae (I), (III), (IV) and (V). A SALT-NOTATION POINT: the Scheme 2 acetonide is drawn with the condensed text 'NH2.H2SO4' hanging off the cytosine 4-amino group, i.e. the sulfate counterion is inside an atom LABEL rather than drawn as a component; a faithful reading emits C12H19N3O9S, for which PubChem returns CID 0, so the scoreable row is the free base and a tool that honours the label scores wrong on it. Non-structure content: none - this document has no instrument plots and no tables.

**Caveats.**

- *molnupiravir* — N4-hydroxy is drawn as NHOH throughout - never as an expanded N-O-H - so the hydroxylamine that defines the whole drug is four characters of condensed text.
- *5'-O-isobutyryl cytidine* — The printed name and the drawing DISAGREE on the acyl group: 'cytidine butyrate' in words, isobutyryl in the picture. The drawing wins - molnupiravir's ester is isobutyrate.
- *2',3'-O-isopropylidenecytidine* — THE ANOMER TRAP, and it fired during this work. A free-hand SMILES for the same compound - written from the drawing rather than derived from cytidine - inverted the ANOMERIC carbon, and PUG-REST returned CID 92271334, a real record for the alpha anomer, InChIKey UBGDNZQSYVIVHU-ZQNVIIHSSA-N: same formula, same skeleton block, no warning. A THIRD record, CID 351235, answers to the NAME '2',3'-O-isopropylidenecytidine' and is stereo-UNDEFINED (UBGDNZQSYVIVHU-UHFFFAOYSA-N). Three PubChem records, one skeleton, and only one of them is what the patent draws.
- *5'-O-isobutyryl-2',3'-O-isopropylidenecytidine (formula IV)* (unresolved) — Drawn in Scheme 2 and claimed as formula (IV). Built from the verified beta-anomer acetonide by adding the 5'-isobutyryl ester, C16H23N3O6; a PUG-REST /compound/smiles/ search returns CID 0. No PubChem record, no printed name, no mass - one view only.
- *N4-hydroxy-5'-O-isobutyryl-2',3'-O-isopropylidenecytidine* (unresolved) — The Scheme 2 hydroxylamination product before acetonide removal, C16H23N3O7. Also returns CID 0.

### Antifungal

#### `EP3221308B1_olorofim` — 12 drawn, 8 resolved, 1 generic, 1 unresolved

EP 3 221 308 B1, F2G Limited, granted 2018-09-19 (priority 2014-11-21 GB), "Antifungal agents" - olorofim (F901318) and its deuterated analogues

**Why it is here.** THREE ISOTOPOLOGUES OF ONE MOLECULE, drawn with explicit D labels, resolving to three distinct real PubChem records that share a skeleton InChIKey block and a molecular formula. It also draws TWO competitor drugs as comparators - oteseconazole and ibrexafungerp - the second of which is the sole subject of another group in this same round.

**Drawing style.** EPO B1: vector text with bitonal clippings at two very different qualities - the F2G compounds are clean 800-950 px line art, while the two comparator drugs on p9 are small, grey, halftone-speckled scans of published figures.

**Counts and page tally.** 12 depictions, ten distinct entities, eight resolved. Page tally: p4 x1 (olorofim), p5 x1 (the R genus), p6 x1 (d8), p7 x2 (d4 and the d2), p8 x2, p9 x5 (formulae (II), (III), (IV) plus VT-1161 and SCY-078), p32 x1, p34 x1, p35 x1 (the English, German and French claims). Kept as a non-structure negative: p38, one of eight full-page instrument sheets on pp38-45 of the original. THE ISOTOPE POINT, restated because it decides three of the eight rows: olorofim, its d8 and its d4 all give the RDKit formula C28H27FN6O2 and the InChIKey block SUFPWYYDCOKDLL, and are separated only by the isotope layer of the InChI. A pipeline that drops explicit D labels collapses all three onto one prediction.

**Caveats.**

- *olorofim-d8 (piperazine-2,2,3,3,5,5,6,6-d8)* — THE ISOTOPE TRAP. Olorofim, its d8 and its d4 all carry the SAME skeleton InChIKey block SUFPWYYDCOKDLL and the same RDKit molecular formula string C28H27FN6O2 - RDKit does not put D in the formula - and differ only in the InChI isotope layer: -UHFFFAOYSA-N, -DHNBGMNGSA-N, -OCFVFILASA-N. Neither the name endpoint nor a formula comparison separates them; only the drawn D labels do.
- *1,2-dimethyl-4-phenylpyrrole* — A REGIOCHEMISTRY TEST against its own neighbours: (IV) is the 4-phenyl pyrrole, while every olorofim drawing on the surrounding pages is a 3-phenyl pyrrole. Two isomers, one document, and the only difference is which ring carbon carries the phenyl.
- *oteseconazole* — The round's TETRAZOLE azole antifungal, and it is drawn INSIDE a competitor's patent. Note it is a 1,2,3,4-tetrazole, not the 1,2,4-triazole of conventional azoles, which is the point of the compound.
- *ibrexafungerp* — CROSS-DOCUMENT DRAWING-QUALITY PAIR. This is the SAME molecule as the sole compound of EP3247711B1_ibrexafungerp, but here it is a small, grey, speckled scan of a scan - eleven stereocentres compressed into a 560x313 raster - while EP3247711B1 draws it crisp and large. Two documents in one round, one molecule, two ends of the resolution range.
- *pyrimidine-4,6-d2 analogue of olorofim* (unresolved) — Drawn on p8 with two D labels on the fluoropyrimidine ring. A PUG-REST /compound/smiles/ search returns CID 0 - PubChem holds the d8 and the d4 isotopologues but not this one - and the compound list does not name it. One view only.
- *formula with a variable R on the central phenylene* (generic) — The Example-2 genus, drawn identically to olorofim except that the meta position of the central benzene carries a bare 'R'. It sits between two fully specified drawings on adjacent pages, which is exactly where a generic gets mistaken for a molecule.

#### `EP3247711B1_ibrexafungerp` — 5 drawn, 1 resolved, 0 generic, 1 unresolved

EP 3 247 711 B1, Scynexis, Inc., granted 2022-03-09 (priority 2015-01-19 US), "Novel salts and polymorphs of SCY-078" - ibrexafungerp (BREXAFEMME)

**Why it is here.** ELEVEN STEREOCENTRES ON A FUSED PENTACYCLIC TRITERPENE, drawn with ATOM POSITION NUMBERS printed on the skeleton (5, 7, 13, 14, 15) - stray digits inside the structure box, the exact trap round 6 recorded for icovamenib's Compound P, here on a much harder molecule. The original is 186 pages of which about 160 are full-page XRPD/DSC sheets.

**Drawing style.** EPO B1: vector text with bitonal clippings. Every drawn structure is the same molecule; hashed and bold wedges appear on eleven ring and side-chain positions, two ring-fusion hydrogens are drawn as explicit H, and five ring-position NUMBERS are printed inside the skeleton.

**Counts and page tally.** 5 depictions of ONE compound. Page tally: p2 x1, p6 x1, p25 x1 (above Table 8), p52 x1, p54 x1, p56 x1 - the last three are the English, German and French claims. Kept as a non-structure negative: p58, one of roughly 160 full-page XRPD, DSC and TGA sheets that make up pp58-185 of the original. This group is a recall test of exactly one very hard molecule, and a precision test against a salt table and an instrument sheet.

**Caveats.**

- *ibrexafungerp* — ATOM NUMBERS INSIDE THE STRUCTURE. The drawing prints '5', '7', '13', '14' and '15' next to skeleton atoms, because the specification refers to those positions in prose. They are not substituents, not charges and not atom labels; a recogniser that treats a digit adjacent to a bond as a label emits a molecule with phantom heteroatoms. Two ring-fusion hydrogens are ALSO drawn explicitly as 'H' on hashed wedges, so the same box contains both real atom labels and typographic ones.
- *seventeen salt formers of Table 8 (HCl, H3PO4, maleic, citric, hippuri* (unresolved) — p25 is a 17-row x 6-column salt/solvent screening matrix printed DIRECTLY BELOW a drawing of SCY-078, listing every acid partner by common name and every outcome by form code. Not one counterion is drawn. Same failure mode as the amlodipine-besylate patent recorded in the corpus README and as this round's telacebec Table 21 - the salts exist only as words, and the adjacency to a real structure invites a pipeline to pair them.

#### `EP3720438B1_gwt1_antifungals` — 22 drawn, 6 resolved, 1 generic, 1 unresolved

EP 3 720 438 B1, Amplyx Pharmaceuticals, Inc., granted 2023-08-30 (priority 2017-12-07 US), "Heterocycle substituted pyridine derivative antifungal agents" - analogues of manogepix (APX001A)

**Why it is here.** A CONGENERIC SERIES ON ONE SCAFFOLD: six of the 178 examples, all on the same 2-aminopyridin-3-yl-isoxazol-5-yl core and differing only in the heteroaryl at the far end of a benzyl-benzyl linker. Every one is flat and achiral, so this group isolates CONNECTIVITY reading with the stereo problem removed - the complement to the sugar and cage groups in this round.

**Drawing style.** EPO B1: vector text with SMALL bitonal clippings, typically 500-620 px wide by 155-180 px tall, two to four per page, each sitting under its own Example heading. In the original pp7-11 the same clippings are tiled TWELVE OR THIRTEEN to a page as a compound gallery, which is where a per-page image count explodes.

**Counts and page tally.** About 22 depictions on the kept pages, six catalogued. Page tally: p2 x2 (claim genera), p74 x2, p75 x3, p76 x3, p77 x4, p78 x4, p79 x4. SCORE THIS GROUP RECALL-ONLY - most of what it draws is a named example that is not in molecules[]. The reason to keep it anyway is the congeneric series: six molecules that share 17 of their heavy atoms and differ only in a terminal five- or six-membered heteroaryl, which is precisely the discrimination an OCSR tool is most likely to blur.

**Caveats.**

- *formula (III) and the other claim genera* (generic) — The p2 claim drawings carry ring-variable and substituent-variable positions; p3 states 'All other Examples are merely reference examples', so the CLAIMED subject matter is a genus and every specific compound in the document is formally a reference example.
- *the ~16 further named examples drawn on the kept pages* (unresolved) — pp75-79 carry about sixteen more Example structures beyond the six catalogued, each with a full IUPAC heading of the same quality. They were not resolved for time, not for any defect: this group should be scored RECALL-ONLY against the six rows, because a correct prediction of an uncatalogued example would otherwise be counted wrong. Precision over this group is a lower bound.

#### `EP3810115B1_manogepix_prodrugs` — 14 drawn, 3 resolved, 1 generic, 1 unresolved

EP 3 810 115 B1, Basilea Pharmaceutica International Ltd, granted 2024-07-17 (priority 2018-06-25), "Pyridine derivatives substituted by heterocyclic ring and amino group" - carbamate, thiocarbamate and urea prodrugs of manogepix

**Why it is here.** A SPECIFIC/GENERIC BOUNDARY drawn on one page. p21 puts three fully specified molecules and three R-group genera in the same two schemes, and the genera differ from the specifics ONLY in the substituent hanging off one nitrogen. It also draws an isocyanate, a functional group with no other example in the corpus, and it is a second, independent view of the manogepix scaffold that this round's EP3720438B1 group covers from the analogue side.

**Drawing style.** EPO B1: vector text with bitonal clippings up to 1955x936. Variable labels are set as multi-character superscripted tokens - R13B, R13C, X2, R3D - so a single substituent position carries three or four glyphs, and one genus uses a LETTERED RING PLACEHOLDER, a bare circle labelled 'A' standing for an unspecified ring.

**Counts and page tally.** 14 depictions on the kept pages, six distinct entities, three resolved and three generic. Page tally: p3 x1, p13 x1, p14 x1, p20 x1, p21 x2 clippings holding 6 structures, p22 x2, p23 x1, p31 x1, p32 x2. THE MEASUREMENT here is the specific/generic boundary at its narrowest: Intermediate A and formula (Ia) are the same 27 heavy atoms plus one acyl group, and the only difference on the page is whether that acyl carries an 'R3D' label. A tool that emits a molecule for (Ia) scores a false positive; one that refuses Intermediate A because it looks like its neighbours scores a false negative.

**Caveats.**

- *manogepix* — The document's entire purpose is to acylate THIS molecule's aniline nitrogen, and every downstream drawing therefore differs from it by one N-substituent - which in the claims is always a variable. Intermediate A is the only fully specified member of its own series.
- *5-(2-isocyanatopyridin-3-yl)-3-[[4-(pyridin-2-yloxymethyl)phenyl]methy* — A drawn ISOCYANATE - two consecutive double bonds on a linear N=C=O - is a bond-order pattern nothing else in the corpus contains, and it sits directly above the aminopyridine it came from, which has the same three atoms in the same place with entirely different bond orders.
- *formulae (Ia), (Ib) and (Ibb) - the prodrug genera* (generic) — Three related genera. (Ia) is manogepix with the aniline acylated by C(=O)R3D; (Ibb) is the same with C(=O)X2-R13C where X2 is O, S or NR13B, stated in a text line BELOW the drawing rather than in it; (Ib) is the fully abstract version carrying R1, R2, R3, W, X1, Y, Z and a circled 'A' for an unspecified ring. The last is the most dangerous drawing class in the group: everything except the substituents looks like a real molecule, and the circled A is a ring that is not drawn at all.
- *the Example 2-5 prodrug products (glycosyl, peptidyl, phosphotoxy and * (unresolved) — The Examples are headed by CLASS names - 'Synthesis of glycosyl carbamate', 'Synthesis of peptidyl carbamates', 'Synthesis of phosphotoxy carbamate' - not by compound names, and several are drawn with sugar or amino-acid residues left as blocks. Not catalogued; score this group recall-only against the three rows.

#### `EP4069690B1_opelconazole` — 11 drawn, 1 resolved, 0 generic, 0 unresolved

EP 4 069 690 B1, Pulmocide Limited, granted 2024-11-13 (priority 2019-12-06 GB), "Polymorphs of triazole antifungal compound PC945" - opelconazole

**Why it is here.** The round's conventional 1,2,4-TRIAZOLE azole, and the counterpoint to oteseconazole's tetrazole in the olorofim group. Its two stereocentres sit on a 2,2,4-trisubstituted tetrahydrofuran and are drawn with a bold and a hashed wedge on adjacent ring carbons - the classic azole antifungal stereo motif, and one the corpus had no example of.

**Drawing style.** EPO B1: vector text with bitonal clippings, all of one molecule at 1150-1220 px. Me is a condensed label; the amide is drawn as HN-C(=O) with the H on the left of the N, which puts the hydrogen between two ring systems.

**Counts and page tally.** 11 depictions of ONE compound; p3 alone draws it three times in a row, identically, because the specification restates it once per aspect of the invention. Page tally: p3 x3, p24 x1, p27 x2, p28 x1, p29 x1, p30 x1, p31 x1 - pp27-31 are the English, German and French claims. Kept as a non-structure negative: p33, one of ten full-page XRPD/DSC sheets on pp33-42 of the original. Two further raster objects in the original are NOT structures and should not be counted: a 719x123 strip on p22 and a 1794x53 strip on p25, both of which are inline typographic fragments.

**Caveats.**

- *opelconazole* — The INN opelconazole is NEVER printed - the document says 'PC945' and 'Compound I' only, and the (3R,5R) assignment therefore rests entirely on the [0008] IUPAC name plus the two drawn wedges. The two stereocentres are on ADJACENT positions of a five-membered ring with one bold and one hashed wedge, which is the configuration most often mis-transcribed as the cis/trans opposite.

### Antiparasitic

#### `EP3578557B1_cipargamin` — 24 drawn, 6 resolved, 0 generic, 2 unresolved

EP 3 578 557 B1, Novartis AG, granted 2023-09-20 (priority 2012-03-23), "Chemical process for preparing spiroindolones and intermediates thereof" - the cipargamin (KAE609 / NITD609) route

**Why it is here.** A COMPLETE SIX-STEP ROUTE ON ONE PAGE ending in a spiro quaternary stereocentre, drawn almost entirely with CONDENSED LABELS - CO2H, NHAc, CO2Me, NHBoc, OMs, NH2 - so most of the heavy atoms in the scheme are hidden behind two to four characters of text. It also contains a clean CIP-letter flip across a reduction.

**Drawing style.** EPO B1: vector text with bitonal clippings. The p3 route is ONE 1600x758 image holding seven structures in three rows; pp4-6 and 11-13 hold smaller single-structure and two-structure boxes.

**Counts and page tally.** About 24 depictions on the kept pages, six catalogued, all six resolved; the total is an ESTIMATE because pp4-6 and 11-13 were counted from image objects rather than box by box. All six catalogued compounds are in the single p3 scheme. WHAT THIS GROUP MEASURES is condensed-label expansion: of the seven structures in that scheme, five hide their functional groups behind CO2H, NHAc, CO2Me, NHBoc, OMs or NH2, and the difference between the third and fourth boxes is entirely inside the labels - CO2Me becomes CH2OMs while the drawn skeleton does not change at all.

**Caveats.**

- *2-acetamido-3-(6-chloro-5-fluoro-1H-indol-3-yl)propanoic acid* — The stereo-free drawing and its resolved partner are drawn SIDE BY SIDE and differ by one hashed wedge. Only the racemate has a PubChem record.
- *(2S)-1-(6-chloro-5-fluoro-1H-indol-3-yl)propan-2-amine* — A CIP-LETTER FLIP with no change of configuration: PubChem calls the mesylate (2R) and this amine (2S), and the two are one LiAlH4 reduction apart with the stereocentre untouched. Removing the ester oxygen demotes that branch below the indolylmethyl and the descriptor inverts. Anyone matching printed descriptors to drawn wedges across this scheme will conclude, wrongly, that the configuration changed.
- *cipargamin* — The INN cipargamin is never printed; the document says only 'spiroindolone'. The SPIRO quaternary centre carries no wedge of its own in this drawing - its configuration is implied by the ring fusion and by the (1R,3S) of the marketed compound, not read off the page. Treat this row as name-independent and geometry-inferred, the weakest assignment in the group.
- *the resolved (single-enantiomer) N-acetyl amino acid* (unresolved) — Drawn immediately after the 'L-aminoacylase resolution >99% e.e.' arrow, identical to the racemate except for one hashed wedge at the alpha carbon. A /compound/smiles/ search on the stereo-specified reading returns CID 0 in both senses - PubChem holds only the stereo-free record RDETZPQUOZMZOR-UHFFFAOYSA-N. Giving it that CID would put a duplicate SMILES in this group, so it stays unresolved: the same situation as round 6's talazoparib compound 17.
- *the remaining pp4-6 and 11-13 boxes* (unresolved) — About seventeen further structures - protected intermediates and process variants labelled only with document-internal letters. Not catalogued; score this group RECALL-ONLY against the six rows.

#### `EP3743419B1_antiparasitic_tetrazoles` — 12 drawn, 8 resolved, 1 generic, 1 unresolved

EP 3 743 419 B1, GlaxoSmithKline Intellectual Property Development Ltd, granted 2022-09-14 (priority 2018-01-24), "Novel compounds for the treatment of parasitic infections"

**Why it is here.** FOUR MATCHED PAIRS ON SEVEN PAGES. Examples 5/6, 7/8 and 11/12 are three (2R)/(2S) DIASTEREOMER pairs drawn adjacently, and Examples 5/7 and 6/8 are TETRAZOLE REGIOISOMER pairs - N-1 versus N-2 attachment on the same ring, which changes nothing about the atom count and everything about the identity. All eight resolve to distinct real PubChem records.

**Drawing style.** EPO B1: vector text with small bitonal clippings, 842x260-350, two or three per page, each under its Example heading.

**Counts and page tally.** 12 depictions on the kept pages, eight catalogued, all eight resolved. Page tally: p2 x1 (genus), p3 x2 (genus), p53 x2, p54 x2, p55 x2, p57 x3. THE POINT OF THIS GROUP is the pair structure. Examples 5 and 6 share the InChIKey block QEKFYNVTISONGC and differ only in the hydroxyl stereocentre; 7 and 8 share RMWYAYFMEWWLSK; 11 and 12 share BGZJNJSMIAKQIL. Independently, 5 and 7 have the SAME molecular formula C21H22FN5O3 and the same atoms and differ only in whether the propyl chain is bonded to tetrazole N-1 or N-2 - a bond that moves one position around a four-nitrogen ring. A tool that gets the tetrazole regiochemistry wrong lands on the other real record, and a tool that ignores the wedge lands on the diastereomer, so each of the four errors is a confident wrong answer rather than a miss. Every member of every pair is drawn on the same page as its partner.

**Caveats.**

- *the claim genus on pp2-3* (generic) — Three R-group formulae on the first two text pages define the claimed class; the specific compounds are all in the Examples.
- *Examples 13, 14 and others drawn on pp58, 65, 66 and 79 of the origina* (unresolved) — Not in the extract and not catalogued.

#### `EP4061375B1_antimalarial_markush` — 26 drawn, 0 resolved, 2 generic, 1 unresolved

EP 4 061 375 B1, Merck Sharp & Dohme LLC / MSD, granted 2025-06-04 (priority 2019-11-19), "Antimalarial agents"

**Why it is here.** THE ROUND'S ONE GENUS-ONLY DOCUMENT, and it is kept for the DEVICES rather than the molecules: a floating substituent with a count subscript, R10(m), attached to a ring by a bond that crosses the ring rather than landing on an atom; a full synthesis scheme in which even the PROTECTING GROUP is a variable (P); and asterisks marking stereocentres that are explicitly NOT defined, drawn on the same molecule as ordinary wedges that are.

**Drawing style.** EPO B1: vector text with bitonal clippings. Variables are superscripted multi-character tokens (R1, R2, R3, R4, R5, R6, R9, R10, R11, and 'P' for a protecting group); the count subscript '(m)' rides on R10 and R11; asterisks sit ON ring atoms as stereocentre-undefined markers.

**Counts and page tally.** About 26 depictions on the kept pages and ZERO scoreable molecules; the count is an estimate. SCORE THIS GROUP FOR FALSE POSITIVES ONLY. It is the deliberate genus-only pick allowed by the round's brief, and it complements EP3643719B1_spiropyrimidinetriones, which also scores zero but for the opposite reason - there, everything drawn is a real named molecule that no database holds; here, almost nothing drawn is a molecule at all. Between them they bracket the two ways a well-drawn patent page can be worth nothing to a recall metric.

**Caveats.**

- *formulae (I), (IA) and (IC) - the claim genera* (generic) — A 2-imino-tetrahydropyrimidin-4-one N-linked through a CH(R9) to a cyclopropane whose other carbon is a carboxamide. Formula (I) carries R1, R2, R3, R4, R5, R6 and R9. Formulae (IA) and (IC) replace the amide substituents with a chromane and an indane respectively, EACH CARRYING A FLOATING SUBSTITUENT 'R10(m)' or 'R11(m)' whose bond crosses the ring interior instead of terminating on an atom - the notation means m copies of R at unspecified ring positions. That device has no representation in SMILES at all, and a recogniser that attaches the bond to whichever atom it happens to cross emits a specific, wrong molecule.
- *SCHEME 1 intermediates S-1 to S-10* (generic) — A complete ten-member route in which EVERY box is generic: S-1 carries 'PO' for a protected alkoxide, S-2/S-3/S-5/S-7 carry 'CO2R', S-4 is written 'R9MX or R9M' - a reagent expressed as two variables and a metal - and S-6/S-7/S-8 carry both 'NP' (a protected imine) and R5/R6. Ten drawn boxes, zero molecules. The wavy bond on R9 in S-5 and S-7 marks that centre as a mixture.
- *the Example gallery on pp52-56 of the original* (unresolved) — Eight to ten FULLY SPECIFIED structures per page, differing in the gem-dialkyl pair on the pyrimidinone and in the chromane or indane substitution, each labelled with an example number and characterised only by 1H NMR and LCMS - no chemical name anywhere. Several carry ASTERISKS on stereocentres, which in this document means the configuration at that centre was not assigned, while other centres in the same drawing carry ordinary bold and hashed wedges. Left unresolved: a compound with four stereocentres of which one or two are explicitly undefined, and no printed name, gives no second view, and this round has twice caught a plausible hand-built SMILES resolving to a real record for the wrong isomer.


## One note on page extracts

**Twenty-two of the twenty-five files are page extracts, not whole grants.** The
kept range is in `pages_kept` in both manifests and in the `pages_kept` field of
every group. Three files are complete documents because they were already small:
`EP3868768B1_contezolid_acefosamil.pdf` (14 pp), `EP4121058B1_oxazolidinone_TB.pdf`
(17 pp) and `EP3321253B1_tecovirimat.pdf` (19 pp). Every extract was cut with

```
qpdf <original>.pdf --pages <original>.pdf "<range>" -- <stem>.pdf
```

and the ranges were chosen to keep (a) the front page, so the document identifies
itself, (b) every page carrying a structure that is catalogued here, and (c) in
most groups one or two deliberate NEGATIVES — a full-page XRPD or DSC sheet, a
salt-former table, an NMR peak list, or in `EP3953330B1` a **protein sequence
listing** in three-letter amino-acid codes. The dropped pages are running
specification text, further instrument sheets and example write-ups. The whole
round is 7.4 MB across 25 files, largest 487 KB.

## Two notes on retrieval, for whoever adds round 10

**The round-6 proxy route has degraded further.** `patents.google.com` still 503s
plain `curl`, and the read-through proxy that round 6 used now returns Google's
*"your computer or network may be sending automated queries"* interstitial — it is
rate-limited rather than gone, and four agents sharing one egress IP will not get
through it. Not one document in this round came from Google.

**Two routes carried the whole round, and neither touches Google.**

1. **The EPO publication server** for any granted EP, unauthenticated:
   `https://data.epo.org/publication-server/rest/v1.2/patents/EP<number>NWB1/document.pdf`
   for the PDF and `/document.xml` for the same document as XML. B1 only; an A1
   request returns HTTP 500. The XML endpoint **honours HTTP Range requests**, so
   a 26 KB range fetch returns the bibliographic head — `<B542>` invention title
   in three languages, `<B730>` applicant, publication and priority dates, IPC —
   for about one fortieth of the bytes of the PDF. About 150 candidates were
   screened that way before a single PDF was downloaded, at three concurrent
   connections.
2. **PubChem PUG-REST as a patent search engine.**
   `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/<drug>/xrefs/PatentID/JSON`
   returns every patent PubChem has cross-referenced to a compound — between 30
   and 3000 per drug. Filter that list to `EP…B1` whose number starts 3 or 4 (a
   filing from about 2016 onwards) and screen the survivors through route 1. That
   pair found every document in this round. The list is *noisy* — a patent that
   merely mentions a compound in a list of prior art is cross-referenced too —
   which is exactly why route 1's title screen matters.

**A search result is still not a patent number.** Round 6 recorded `EP2989196B1`
being returned as the zanubrutinib patent when it is in fact an article about
radiation-resistant algae. Every number in this round was verified by fetching
the document and reading its own title page and applicant, and two candidates
were rejected at that step (see `rejected` in
`pdf_corpus_round9_manifest.json`).
