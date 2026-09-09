
## Session start 2026-09-08
Task: cut innerText per tab to <3000 chars on https://<app-host>
Source: /root/C-MAGE/webapp/static/index.html ; deploy from /root/cmage

### Baseline (390x844, live, 2026-09-09)
extract 1457 | gallery 12272 | benchmark 19102 | ringleader 3077
Dumps at /tmp/cmage-simplify/dump/*.txt

### Plan
Cut: footer essay, extract note+privacy sub, gallery CAVEAT (800->1 sentence),
sparkcap, "and N more", timestamps, smilesPair prose labels, all benchmark
narrative (retcons: reverted-crop-tweak, "published off the smaller sample",
"broken comparison survived"), chart-restating paragraphs, methodology essays.
Levers beyond prose: fold the per-structure browser; PAGE 8->3; gallery previews 6->N.
Backup of original: /tmp/cmage-simplify/index.html.orig

### After patches 1-6 (preview against live API, not yet deployed)
extract 1457->797 | gallery 12272->9235 | benchmark 19102->9013 | ringleader 3077->1640
No page/console errors. node --check on extracted JS: OK.

### After patch 7 (preview)
extract 797 | gallery 6353 | benchmark 7960 | ringleader 1640

### After patch 8 (preview)
extract 710 | gallery 6266 | benchmark 7349 | ringleader 1553

### DEPLOYED 2026-09-09 (live, measured after warming /api/benchmark)
extract 1457->710 | gallery 12272->6266 | benchmark 19102->7349 | ringleader 3077->1553
Container image d852aece4e02 == cmage-webapp. CF purged. Privacy check passed (16 runs,
positive control present, 4 forbidden names absent).

### FINAL (verified at time of assertion)
Commit e98fb62 pushed to origin (<owner>/C-MAGE), index.html only.
Container image d852aece4e02 == cmage-webapp: MATCH.
Privacy: 16 runs, positive control present, 0 forbidden names.
check-mobile PASS; check-contrast PASS on all 4 tabs vs origin (benchmark=100 nodes).
visual-verify: no hscroll @390 and @1200, 0 console errors, 9 charts / 34 bars.
