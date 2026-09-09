# <app-host> hostile review — running checkpoint
Started 2026-09-08. Container: cmage (image cmage-webapp, 20079->8080). Source: /root/C-MAGE/webapp/. Compose: /root/cmage/docker-compose.yml. Caddy: /root/box/app/Caddyfile. Data: /root/cmage/data. Limits: 8g mem, 6 cpu, MAX_PDF_MB=20, MAX_PAGES=40, MAX_QUEUE=5.

## Findings (append as discovered)
- BBOX FIX (CONFIRMED): crop ORIGINAL figure pixels at get_expanded_masks bbox + 15% padding -> caffeine Cn1c(=O)c2c(ncn2C)n(C)c1=O conf 0.9011, paracetamol CC(=O)Nc1ccc(O)cc1 conf 0.9221. pad0 crops still wrong (fig1 bbox 274x234 at x=24..298,y=66..300 of 393x351; fig2 422x179 at x=17..439 of 488x290). apply_mask (decimer_segmentation.py:387-417) multiplies by mask and whites out the rest, then crops to mask bbox.
- Review scope: upstream/main 654a80a .. fork 6cbc3bb (17 files). HEAD moved to 5bff104 during review by another agent -> check below.

### Round 1 (source + API reads, no uploads yet) — 22:56
- Live index.html == /root/C-MAGE/webapp/static/index.html byte-for-byte except a Cloudflare-injected challenge script. check-mobile.py: PASS (13/13). check-contrast.py on landing: PASS (only fail is the DISABLED primary button, exempt).
- Confidence caveat EXISTS: `.caveat` block "Read the confidence honestly..." rendered on every results page (extract + gallery detail) and at the top of the gallery list; tier heading for low says "treat them as probably wrong"; footer explains 0.8431 split. So the headline caveat is present. Gaps to verify live: (a) per-card there is only a green HIGH CONFIDENCE badge + green bar + 3-decimal number; (b) "Copy all SMILES" copies low-tier valid SMILES too with no tier marker; (c) CSV has tier column but no caveat; (d) sample-origin runs (0j7qHPK-ADzp, jqoIEraPe7AT, U9jtRxrvu49w) carry NO note, only the seed import PkVo36Ti1PBs has the "2 of 5 are WRONG" note -> the "Try the one-page sample" demo shows 5/5 green with caffeine+paracetamol wrong and nothing card-level says which.
- Numbers on the app's own sample: WRONG caffeine 0.889, WRONG paracetamol 0.899; RIGHT ibuprofen 0.894/0.898, RIGHT ester 0.878. The 3-decimal score does not separate right from wrong at all here.
- Gallery is PUBLIC and lists every upload by filename with extracted figures, crops, SMILES, forever (MAX_GALLERY_RUNS=500). Upload card says nothing about public listing. No delete path: CMAGE_ADMIN_TOKEN unset in compose -> DELETE /api/runs always 403.
- Every click of "Try the one-page sample" creates a NEW permanent gallery entry (3 duplicates + seed already after ~1h).
- /api/jobs/{id}/log is public and contains container paths (/opt/cmage/.venvs/..., /data/jobs/<id>/...), python versions, lib deprecation warnings. No /root/, no host IPs seen. job.json stores client IP (incl. real user IPv6 2a02:...) forever; NOT served via API.
- CSV export writes job.filename raw via csv.writer -> Excel formula injection possible via filename (app.py:215). To verify live.
- Benchmark: available=false, runs_found=0, manifests found -> UI shows pending message. Description string is dev-speak ("embedded image == PubChem depiction of CID, pixel-exact").
- Refresh mid-run: URL carries ?job=<id>, boot code resumes polling -> should survive refresh. No localStorage fallback. poll() ignores non-404 errors silently (pulse keeps pulsing through a 502).

### Round 2 (live uploads) — 23:05
- Rejections all instant (<0.6s), clear, correct: empty->400 "The upload was empty."; text->400 "Only PDF, PNG..."; HTML->400 "That is an HTML page..."; %PDF-+garbage->400 "PDF header but could not be parsed"; 16x16 png->400; 41-page PDF->400 with page limit; 21MB->413 "over the 20 MB limit" (in 0.58s). POST w/o file -> 422 with pydantic array detail (UI would render "[object Object]" but UI never sends that). Malformed id -> 307 redirect (harmless). DELETE run w/o token -> 403 (deletion disabled on this deploy).
- Cancel works: DELETE while stage 1 running -> status cancelled in ~1s.
- No-chemistry 1-page PDF (PpLpzd45lUNo): done in 41s, 0 figures, 0 structures, no error -> lands in public gallery as a 0-structure run.
- **PubChem caffeine PNG 300x300 (xNzjsyufwE8b, named "=2*21"): done in 37s, ONE structure, HIGH confidence 0.868, SMILES C=C1c2c(ncn2C)N(C)C(=C)N1C — WRONG (both C=O read as C=CH2). Caffeine is Cn1cnc2c1c(=O)n(C)c(=O)n2C.** Input was a pristine depiction, not a page crop. Mechanism to confirm from the crop image.
- PNG renamed .pdf: accepted as kind=image, skips_stage1=true (server sniffs content); UI picked-line would have said "PDF, all three stages" (index.html choose(): /pdf$/i.test(f.name)). Mismatch only, not a failure.
- My earlier png-renamed.pdf was a REAL PDF (PIL picked format from extension) -> that first test was invalid; redone with a true PNG.
- Screenshots: mobile no-hscroll PASS on landing/gallery/seed-detail/benchmark; 0 console errors. Progress-card capture missed (job finished in 41s before chromium loaded) -> redo with cancel.
- My test jobs (for cleanup): 6C__6oMz3ifY (cancelled), PpLpzd45lUNo (done, gallery), xNzjsyufwE8b (done, gallery), 39dLFlvL5Ll1 (renamed png, see above).

### Round 3 — 23:07
- CONFIRMED mechanism for PubChem caffeine: /tmp/cmage-review/img/sheet_caffeine.png — the DECIMER crop (141x130) has the ring system whole and centred but BOTH carbonyl "O" labels removed; MolScribe read the dangling double bonds as =CH2, conf 0.868 (HIGH). Crop and render agree with each other. The UI caveat describes "a ring or substituent clipped by the segmenter" (edge clipping) — this is label erasure inside a whole-looking crop; the "compare crop and rendering" check passes. Input had PubChem's light-grey background (possible factor); still a textbook-clean depiction.
- example_figure_02 run: mol0 benzanilide and mol1 N-benzylaniline are CORRECT; the 3 <invalid> are Cp*Co organometallic catalysts (expected). Honest.
- Seed test_page crops (sheet_seed.png): caffeine crop lacks the fused imidazole; paracetamol crop cut before the OH -> iodine. As documented.
- Mobile progress card (shots/prog1): stages, hint, counts, elapsed, Cancel, View log all visible at 390x844; no hscroll; 0 console errors. Cancelled state (prog3): "That did not work / Cancelled." — reasonable.
- Deep link /?job=<id> resumes: done job -> results; cancelled -> error card. Refresh mid-run is survivable.
- CSV formula injection CONFIRMED live: document column contains raw `=2*21` (job xNzjsyufwE8b results.csv).
- Served HTML leak grep: nothing (no /root, /opt, emails, IPs, hostnames).
- Renamed-PNG job 39dLFlvL5Ll1 finished before I could cancel: done, 1 figure, 0 segments -> in gallery.
- Known-answer 4-page PDF submitted: Yf6NMK5_2HFL (8 PubChem depictions; truth in /tmp/cmage-review/up/ka/truth.txt).

### Round 4 — known-answer PDF (Yf6NMK5_2HFL), RDKit-confirmed via container canon.py — 23:12
- 4 pages, 8 PubChem depictions (500px, upscaled to 700px on a 1700x2200 page). Run: 92 s total (VH 21 s, DECIMER 28 s, MolScribe 15 s). VH took each whole page as one 1119x1883 figure; DECIMER crops 225-588 px (adequate resolution).
- Verdicts: aspirin match .895 | ibuprofen match .896 | paracetamol WRONG .867 (OH->OMe) | caffeine WRONG .881 (one C=O -> C=CH2) | nicotine match .880 | glucose WRONG .863 (two OH -> OMe) | benzoic acid match but LOW .840 | penicillin G WRONG .858 (no sulfur; thiazolidine lost).
- Tally: high+match 3, high+WRONG 4, low+match 1. The high tier is 43% correct; the low tier is 100% correct. Score range of the wrong ones (.858-.881) overlaps the right ones (.880-.896) completely.

### Round 5 — mechanism classification (sheets img/sheet_ka_1.png, img/sheet_ka_2.png) — 23:15
- paracetamol .867 HIGH: crop cut between "O" and its "H" at the crop's bottom edge -> read as O-CH3. EDGE CLIP (the caveat's case).
- glucose .863 HIGH: two peripheral O-H labels lost their H at the crop edge -> two OMe. EDGE CLIP.
- caffeine .881 HIGH: lower-left "O" glyph absent INSIDE a crop with whitespace around it -> C=CH2. LABEL ERASED; crop and render agree; caveat's "compare crop and rendering" passes it.
- penicillin G .858 HIGH: crop CONTAINS the "S" glyph; stage 3 dropped it and read tert-butyl. STAGE-3 MISREAD of a whole crop; caveat does not describe this class.
- Limitation of my test: 3 of 4 involve PubChem's light-grey explicit "H" rendering. But standalone caffeine (black "O" labels) and the repo's own ChemDraw-style test_page failed too.
- Hints vs reality (4-page PDF): stage 1 "10-30 s + a few s/page" -> 21 s; stage 2 "about 5 s per figure" -> 28 s for 4 figures; stage 3 "about 3 s per structure" -> 15 s for 8. Fair.
- 36 MP PNG -> 400 with clear message. Encrypted PDF path not exercised (no qpdf on host).
- Container healthy after 6 runs, mem 694 MiB idle.
- Cleanup: local /tmp/cmage-review/up/* removed except ka/review-known-answers.pdf + ka/truth-iso.txt. Server-side job dirs (1.5 MB total) left in place; ids in /tmp/cmage-review/my-jobs.txt.
