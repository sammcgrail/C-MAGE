# Progress\n\nStarted 2026-09-09T16:48:43+00:00

## Unit 0: recon
- Read /root/seb/skills/cmage/SKILL.md (full runbook)
- Read deploy-app SKILL.md
- Webapp frontend is a SINGLE file: /root/C-MAGE/webapp/static/index.html (2061 lines), no build step
- Server: /root/C-MAGE/webapp/server/{app,benchmark,results,jobs,chem,canon,uploads,config}.py
- Deploy: cd /root/cmage && docker compose up --build -d

## Unit 1: data recon
- /api/benchmark serves 4 runs: pdfs_corpus_expanded (242 struct, 34 expected, ladder 9->18->18),
  images_realworld_every7 (97, frag_match 64 = 66.0%, phantom 63, rescued 53, crosstab high n=26),
  pdfs_known_answer (70), images_upscaled_4x (24)
- 675-image full corpus NOT in the API -> need to check /tmp/cmage-675/scored/
- remap experiment in /tmp/cropwhite/scored{0,15,remap}/

## Unit 2: numbers VERIFIED by direct recomputation (RDKit, largest fragment, cxsmiles expand)
| arm | exact | phantom>1frag |
|---|---|---|
| 97 sample STOCK | 64/97 = 66.0% | 63/97 |
| 97 remap 245->255 | 75/97 = 77.3% | 18/97 |
| 97 CropWhite tol15 | 31/97 = 32.0% | 24/97 |
- 675 corpus: 462 exact. DENOMINATOR DISCREPANCY FOUND:
  - 462/743 emitted = 62.2% (68 rows have NO ground truth, charged as wrong)
  - 462/675 rows WITH a reference = 68.4%
  - high tier: 168/200 = 84.0% incl stereo (200 incl 15 unscorable); 165/185 scorable = 89.2% exact
  - low tier: 336/543 = 61.9% incl stereo; 297/490 scorable = 60.6% exact
  => the label "675 images with an answer" pairs with 68.4%, not 62.2%. Report BOTH.
- 97 sample tiers: high 25/26 = 96.2% (n=26!), low 39/71=54.9%

## Unit 3: plan fixed
- Benchmark tab is 26797 px tall on 390px mobile, prose-dominant. Gallery list shows bare crop thumbs, no SMILES.
- Data layer: commit scored structures.csv for (a) 675 full corpus (b) 97 stock (c) 97 remap into
  /root/C-MAGE/benchmarks/scored/<name>/structures.csv ; generator benchmarks/build_headline.py ->
  benchmarks/headline.json ; benchmark.py includes it under key "headline" in /api/benchmark.
- Charts: inline SVG helpers in static/index.html (no library).
- Gallery: /api/runs summary() gains per-thumb smiles/cxsmiles/expanded/confidence + conf array for sparkline.

## Unit 4: server done
- benchmarks/build_headline.py + benchmarks/headline.json (3 arms) + benchmarks/scored/*/structures.csv
- webapp/server/benchmark.py: headline_path(), _load_headline(), signature includes it, payload key "headline"
- webapp/server/jobs.py: summary() now emits previews[] (image, cxsmiles, expanded, confidence, tier,
  valid, abbreviations, verdict, fragments), confidences[], tiers[], verdicts[]
- NEXT: frontend charts in webapp/static/index.html

## Unit 5: frontend rewritten (not yet deployed)
- CSS: .chart/.cbar/.ccols/.stats/.tweak/.crange/.spark/.previews/.pv primitives
- JS primitives: svgEl, bar(), chart(), barChart(), stepChart(), histChart(), rangeChart(), sparkline()
- paintBenchmark -> headlineBlock(d): 3 stat tiles + accuracy-by-corpus bars + tier bars(n) +
  fragment histogram + input-normalisation tweak panel (with the rejected CropWhite arm as one sentence)
- headline()/recallHead()/ladderBlock()/crosstab()/abbrevBlock()/perDocBlock()/gapBlock()/corpusBlock()/
  expanderBlock()/benchRun() prose all cut to charts + caveats
- Gallery: runCard() + previewCard() -> crop + CXSMILES + expanded + confidence; per-run sparkline

## Unit 6: deployed twice, verified
- deploy 1 image 2719e7ec, deploy 2 image 090fa647 (docker inspect == docker images, both times)
- assert-js on rendered DOM PASSED all 16 required numbers + 3 negative controls
- privacy re-verified: review-known-answers.pdf / really-a-png.pdf / =2*21 / review-nochem.pdf absent
  from /api/runs; positive control US4231938A_lovastatin.pdf present so the grep proves something
- fixes in deploy 2: .run white-space (button nowrap clipped every SMILES line), bar name truncation,
  corpus chart now uses rung_found.expanded_largest (was tally.found -> 15/44 captioned as
  largest-fragment when largest-fragment is 18/44), PAGE 24->8, metaBlock/expander/table folded

## Unit 7: verification (deploy 3, image 0ca23854)
- CONTRACT BUG FOUND AND FIXED IN MY OWN TESTS: assert-js returning a bare string is
  coerced truthy, so "FAIL ..." reported PASS. Both scripts now return {pass,msg} and are
  self-tested to FAIL on the wrong tab (bench asserts fail on gallery; gallery asserts fail on extract).
- benchmark mobile: 2/2 asserts, no hscroll, 16 required numbers + 5 negative controls
- gallery mobile: 16 cards, 78 previews, 20 crops loaded (positive control), 26 with expansion,
  78 with confidence, 16 sparklines, privacy holds in the RENDERED DOM
- contrast: origin (localhost:20079) needed - CF adds latency past the checker's 2200ms wait,
  and a 7-node run is vacuous. At origin: benchmark 108/108 nodes pass, gallery 21/21, ringleader 22/22
- check-mobile.py: PASS (13/13)
- page height 26797 -> 16272 px on 390x844

## Unit 8: DONE — final state
- Live image f0e342571f39 == cmage-webapp in docker images. CF purged.
- Committed c4432e0 "Charts where the paragraphs were, and the SMILES under every crop";
  origin/main == c4432e0 (git ls-remote confirmed).
- NOTE: a concurrent agent in this session committed 9fd50d1 + 1f8260c and swept my
  in-progress server/benchmarks files into 9fd50d1. Nothing lost; all present in HEAD.
  That agent's 9fd50d1 message reports the C-MAGE preprint's own headline metric is
  high-confidence precision (paper 77.6% / 82.9%), and this fork's 84.0% (168/200) matches it.
- BEFORE/AFTER measured like-for-like (throwaway container on :20099 running the pre-change
  index.html against the SAME API and data; removed afterwards):
  first result on the tab   1200px (1.42 screens) -> 201px (0.24 screens)
  running prose chars       15916 -> 11002
  total text                31132 -> 18530
  page height 390x844       26797px -> 16272px
- Gallery intact (16 runs), data dir intact (17 job dirs), no stray containers.
