/* The "Gallery" tab: every image the LLM vs OCR tab scores, filtered by molecule type.
   Data: /wall/gallery.json, built by tools/build_gallery.py from wall/llmocr.json (the same verdict codes,
   copied, never re-scored) plus RDKit types from each reference. Rows: [key, name, codes, src, heavy, [type idx]].
   The page only counts: on every filter change ONE pass over the rows gives the reader cards, the per-type
   chart and the chip counts. Uses index.html's helpers ($, el, esc, makeWall, gridBar, gridTop, lazyImg) and
   the LLM vs OCR sheet (LLMOCR.sheet) so a tap shows every reader's answer. */
(function(){
"use strict";
var CSS = [
".ga h2{font-size:16px;font-weight:750;margin:0}",
".ga .lead{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline;padding:18px 0 2px}",
".ga .lead .n{color:var(--dim);font-size:13px}",
".ga .cmph{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px;min-height:20px;margin:8px 0 7px}",
".ga .cmph .on{color:var(--ink);font-weight:600}",
/* Reader cards: fixed DOM, text and widths updated in place, so a filter change never moves layout. */
".ga .cmp.topc{margin:0 0 12px}",
".ga .side{position:relative}",
".ga .side .who{display:flex;align-items:center;gap:6px;min-height:16px}",
".ga .side .who i{display:inline-block;width:9px;height:9px;border-radius:2px;flex:0 0 auto}",
".ga .side .best{position:absolute;top:8px;right:8px;font-size:11px;font-weight:700;letter-spacing:.4px;",
"  text-transform:uppercase;color:#06090d;background:#e6edf3;padding:2px 6px;border-radius:3px;visibility:hidden}",
".ga .side.isbest{border-color:#e6edf3}",
".ga .side.isbest .best{visibility:visible}",
".ga .side.none .pc{color:var(--dim)}",
".ga .side .pc{font-variant-numeric:tabular-nums}",
".ga .side .of{font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
".ga .side .track i{transition:width .2s ease-out}",
"@media (prefers-reduced-motion:reduce){.ga .side .track i{transition:none}}",
/* Filter tools: one horizontally scrolling row per group, label first. */
".ga .frow{display:flex;gap:7px;align-items:center;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch;",
"  padding:3px 0;margin:0 -2px}",
".ga .frow::-webkit-scrollbar{display:none}",
".ga .frow>*{flex:0 0 auto}",
".ga .frow .gl{flex:0 0 74px;font-size:11.5px;line-height:1.25;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;padding-left:2px}",
"@media(min-width:900px){.ga .frow{flex-wrap:wrap;overflow:visible} .ga .frow .gl{flex-basis:90px}}",
".ga .frow .chip{min-height:40px;padding:7px 12px}",
".ga .frow .chip i{font-variant-numeric:tabular-nums}",
".ga .frow .chip.z{border-style:dashed}",
".ga .ftools{margin:2px 0 10px;border-top:1px solid var(--line);padding-top:8px}",
/* The chart: one row per type, the four readers as thin LEFT-ALIGNED bars stacked in one cell. */
".ga .card{background:var(--panel);border:1px solid var(--line);padding:12px 13px 10px;margin:10px 0 12px;max-width:980px}",
".ga .card h3{font-size:13.5px;font-weight:700;margin:0 0 4px;color:var(--ink)}",
".ga .card h3 span{color:var(--dim);font-weight:400}",
".ga .lgd{display:flex;flex-wrap:wrap;gap:4px 12px;margin:0 0 8px;font-size:12px;color:var(--dim)}",
".ga .lgd i{display:inline-block;width:9px;height:9px;margin-right:5px;vertical-align:-1px;border-radius:2px}",
".ga .tg{display:grid;grid-template-columns:max-content minmax(0,1fr) max-content;column-gap:10px;row-gap:2px;align-items:center}",
".ga .tr{display:contents;cursor:pointer}",
".ga .tr>*{padding:5px 0}",
".ga .tr .l{font-size:12.5px;color:var(--ink);text-align:right;white-space:nowrap;max-width:44vw;overflow:hidden;text-overflow:ellipsis;",
"  background:none;border:0;font-family:inherit;cursor:pointer;padding-left:0;padding-right:0}",
".ga .tr .l small{color:var(--dim);font-size:11.5px;margin-left:5px;font-variant-numeric:tabular-nums}",
".ga .tr.on .l{color:#79b8ff;font-weight:650}",
".ga .bs{display:flex;flex-direction:column;gap:2px;min-width:0}",
".ga .bs span{display:block;height:5px;background:#0b0f14;position:relative}",
".ga .bs span i{position:absolute;left:0;top:0;bottom:0;border-radius:0 2px 2px 0}",
".ga .bs span.nr{background:repeating-linear-gradient(90deg,#0b0f14 0 4px,transparent 4px 8px)}",
".ga .tr .g{font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right;color:var(--dim)}",
".ga .tr .g b{color:var(--ink);font-weight:650}",
".ga details.more{margin-top:4px} .ga details.more>summary{font-size:12.5px;color:#79b8ff;min-height:40px}",
".ga .card .sub{font-size:12px;margin-top:6px}",
/* The grid: drawings only. */
".ga .wall{grid-template-columns:repeat(auto-fill,minmax(82px,1fr));gap:5px}",
".ga .t::after{display:none}",
/* No content-visibility:auto here, measured: on 5,000 plain image tiles its per-tile visibility observer
   cost more than it saved (4x throttle, scrolling: intersection work 1.2 s vs 0.07 s per 20 frames,
   frame p50 236 ms vs 101 ms). The tiles are one <img> each, cheap to keep laid out. */
".ga .t{content-visibility:visible}",
"@media(min-width:900px){.ga .wall{grid-template-columns:repeat(auto-fill,minmax(120px,1fr))}}",
"@media(max-width:640px){.ga .cmp .pc{font-size:28px} .ga .cmp .side{padding:11px 11px}}",
"#gatop{scroll-margin-top:72px}"
].join("\n");
var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);

var IMGDIR = {c: "img", b: "superatoms", r: "superatoms", g: "superatoms"};
var MIN_N = 10;        // a reader needs this many images read in a set to be ranked "best" or to set a gap
var D = null, NA = 0, LLM = [], CX = -1;
var S = {type: -1, src: "all", q: "", same: false};
var GB = null, WALL = null, CARDS = [];
var fmt = function(n){ return (+n).toLocaleString("en-US"); };
var pc = function(e, n){ return n ? e / n * 100 : null; };

/* One pass over the rows for the current source / search / same-images choice: per type (and "all"),
   per arm, images read and exact. Index NT = "all". */
function tally(){
  var NT = D.types.length, read = [], ex = [], cnt = [], i, a;
  for (i = 0; i <= NT; i++){ read.push(new Array(NA).fill(0)); ex.push(new Array(NA).fill(0)); cnt.push(0); }
  var rows = D.rows, q = S.q, src = S.src, same = S.same;
  for (var j = 0; j < rows.length; j++){
    var r = rows[j];
    if (src !== "all" && r[3] !== src) continue;
    if (q && r[1].toLowerCase().indexOf(q) < 0) continue;
    var c = r[2];
    if (same && !allRead(c)) continue;
    var ts = r[5];
    cnt[NT]++;
    for (a = 0; a < NA; a++){
      var v = c.charCodeAt(a);   // e s w i read; - x not counted
      if (v === 101 || v === 115 || v === 119 || v === 105){
        read[NT][a]++; if (v === 101) ex[NT][a]++;
        for (i = 0; i < ts.length; i++){ read[ts[i]][a]++; if (v === 101) ex[ts[i]][a]++; }
      }
    }
    for (i = 0; i < ts.length; i++) cnt[ts[i]]++;
  }
  return {read: read, ex: ex, cnt: cnt, NT: NT};
}
function allRead(c){ for (var a = 0; a < NA; a++){ if ("eswi".indexOf(c[a]) < 0) return false; } return true; }

function rowsNow(){
  var t = S.type, src = S.src, q = S.q, same = S.same;
  return D.rows.filter(function(r){
    return (src === "all" || r[3] === src) && (t < 0 || r[5].indexOf(t) >= 0)
      && (!q || r[1].toLowerCase().indexOf(q) >= 0) && (!same || allRead(r[2]));
  });
}

/* Best = highest exact % among readers with >= MIN_N read; ties all marked. */
function bestOf(read, ex){
  var top = -1, who = [];
  for (var a = 0; a < NA; a++){
    if (read[a] < MIN_N) continue;
    var p = ex[a] / read[a];
    if (p > top + 1e-9){ top = p; who = [a]; } else if (Math.abs(p - top) <= 1e-9) who.push(a);
  }
  return who;
}

/* ---- Reader cards ---- */
function cardsInit(box){
  box.innerHTML = '<div class="cmp topc four">' + D.arms.map(function(a){
    return '<div class="side"><div class="who"><i style="background:' + a.color + '"></i>'
      + esc(a.short) + '</div><div class="pc">–</div><div class="of">&nbsp;</div>'
      + '<div class="track"><i style="width:0;background:' + a.color + '"></i></div></div>';
  }).join("") + '</div>';
  CARDS = [].map.call(box.querySelectorAll(".side"), function(s){
    return {s: s, pc: s.querySelector(".pc"), of: s.querySelector(".of"), bar: s.querySelector(".track i")};
  });
}
function cardsUpdate(T){
  var k = S.type < 0 ? T.NT : S.type, read = T.read[k], ex = T.ex[k], best = bestOf(read, ex);
  CARDS.forEach(function(C, a){
    var n = read[a], p = pc(ex[a], n);
    C.s.classList.toggle("none", !n);
    C.s.classList.toggle("isbest", best.length < NA && best.indexOf(a) >= 0);
    C.pc.textContent = n ? p.toFixed(1) + "%" : "–";
    C.of.textContent = n ? fmt(ex[a]) + " of " + fmt(n) + (n < MIN_N ? " · too few" : "") : "not read";
    C.bar.style.width = (n ? Math.min(100, p) : 0) + "%";
  });
  var lab = S.type < 0 ? "All types" : D.types[S.type].label;
  $("#gahead").innerHTML = '<span class="on">' + esc(lab) + '</span><span>' + fmt(T.cnt[k]) + ' images'
    + (S.src !== "all" ? ' · ' + esc(srcLabel(S.src)) : '') + (S.q ? ' · “' + esc(S.q) + '”' : '')
    + ' · exact, each reader on the images it read' + (S.same ? ' (only images all four read)' : '') + '</span>';
}
function srcLabel(s){ var x = D.sources.filter(function(y){ return y.k === s; })[0]; return x ? x.label : s; }

/* ---- Chart: where LLM readers and the OCR differ, per type ---- */
function chartHTML(T){
  var items = D.types.map(function(t, i){
    var read = T.read[i], ex = T.ex[i];
    var ll = LLM.filter(function(a){ return read[a] >= MIN_N; }).map(function(a){ return [ex[a] / read[a], a]; })
      .sort(function(x, y){ return y[0] - x[0]; })[0];
    var gap = ll && read[CX] >= MIN_N ? (ll[0] - ex[CX] / read[CX]) * 100 : null;
    return {i: i, t: t, n: T.cnt[i], read: read, ex: ex, gap: gap, best: bestOf(read, ex)};
  }).filter(function(x){ return x.n; });
  items.sort(function(x, y){
    var gx = x.gap == null ? -1 : Math.abs(x.gap), gy = y.gap == null ? -1 : Math.abs(y.gap);
    return gy - gx || y.n - x.n; });
  if (!items.length) return '<div class="sub">No images in this filter.</div>';
  var row = function(x){
    var title = D.arms.map(function(a, k){ return a.short + ": " + (x.read[k] ? (x.ex[k] / x.read[k] * 100).toFixed(1) + "% (" + x.ex[k] + " of " + x.read[k] + ")" : "not read"); }).join("; ");
    var g = x.gap == null ? '<span>–</span>'
      : Math.abs(x.gap) < 0.5 ? '<span>even</span>'
      : '<b>' + (x.gap > 0 ? 'LLM' : 'OCR') + ' +' + Math.abs(x.gap).toFixed(0) + '</b> pts';
    return '<div class="tr' + (x.i === S.type ? ' on' : '') + '" data-t="' + x.i + '" title="' + esc(title) + '">'
      + '<button class="l" type="button" aria-label="' + esc(x.t.label + ". " + title) + '">' + esc(x.t.label) + '<small>' + fmt(x.n) + '</small></button>'
      + '<span class="bs" aria-hidden="true">' + D.arms.map(function(a, k){
          return x.read[k] ? '<span><i style="width:' + Math.max(0.5, x.ex[k] / x.read[k] * 100) + '%;background:' + a.color + '"></i></span>'
                           : '<span class="nr"></span>'; }).join("") + '</span>'
      + '<span class="g">' + g + '</span></div>';
  };
  var top = items.slice(0, 6), rest = items.slice(6);
  return '<div class="tg">' + top.map(row).join("") + '</div>'
    + (rest.length ? '<details class="more"' + (S.more ? ' open' : '') + '><summary>More types (' + rest.length + ')</summary><div class="tg">'
        + rest.map(row).join("") + '</div></details>' : '');
}

/* ---- Filter tools ---- */
function chipRow(label, items){
  return '<div class="frow" role="group" aria-label="' + esc(label) + '"><span class="gl">' + esc(label) + '</span>' + items + '</div>';
}
function toolsHTML(){
  var tchip = function(i, lab){ return '<button class="chip" type="button" data-t="' + i + '" aria-pressed="' + (S.type === i) + '">'
    + esc(lab) + '<i></i></button>'; };
  var h = "", first = true;
  D.groups.forEach(function(g){
    var ts = D.types.map(function(t, i){ return [t, i]; }).filter(function(x){ return x[0].g === g.k; });
    if (!ts.length) return;
    h += chipRow(g.label, (first ? tchip(-1, "All types") : "") + ts.map(function(x){ return tchip(x[1], x[0].label); }).join(""));
    first = false;
  });
  h += chipRow("Source", '<button class="chip" type="button" data-s="all" aria-pressed="' + (S.src === "all") + '">All<i>' + fmt(D.rows.length) + '</i></button>'
    + D.sources.map(function(s){ return '<button class="chip" type="button" data-s="' + s.k + '" aria-pressed="' + (S.src === s.k) + '">'
      + esc(s.label) + '<i>' + fmt(s.n) + '</i></button>'; }).join("")
    + '<button class="chip" type="button" id="gasame" aria-pressed="' + S.same + '" title="Score and show only the images all four readers read">Same images only</button>');
  return h;
}
function chipCounts(T){
  [].forEach.call(document.querySelectorAll(".ga .frow .chip[data-t]"), function(b){
    var i = +b.dataset.t, n = T.cnt[i < 0 ? T.NT : i];
    b.lastChild.textContent = fmt(n);
    b.classList.toggle("z", !n);
    b.setAttribute("aria-pressed", i === S.type);
  });
}

function gbItems(T){
  return [{key: "-1", label: "All types", n: T.cnt[T.NT]}].concat(D.types.map(function(t, i){
    return {key: String(i), label: t.label, n: T.cnt[i]}; }));
}
function pinnedBar(root, T){
  var old = GB;
  GB = window.gridBar({items: gbItems(T), current: String(S.type), query: S.q,
    onPick: function(k){ var stuck = GB.bar.classList.contains("stuck"); setType(+k, stuck); },
    onSearch: function(q){ var stuck = GB.bar.classList.contains("stuck"); S.q = q; update(false);
      if (stuck) window.gridTop(GB.sent); }});
  if (old){ old.sent.replaceWith(GB.sent); old.bar.replaceWith(GB.bar); }
  else { root.appendChild(GB.sent); root.appendChild(GB.bar); }
}

function tile(r){
  var b = el("button", "t");
  b.type = "button";
  b.title = r[1];
  b.setAttribute("aria-label", r[1]);
  b.innerHTML = '<img decoding="async" data-src="/wall/' + IMGDIR[r[3]] + '/' + encodeURIComponent(r[0]) + '.png" alt="">';
  var im = b.firstChild;
  if (!GRP || GRP.length >= 12){ GRP = []; im._g = GRP; IO.observe(im); }
  GRP.push(im);
  b.onclick = function(){ window.LLMOCR.sheet([r[0], r[1], r[2], r[3]], D); };
  return b;
}

/* Take a wall out of the render tree cheaply (content-visibility:hidden skips its subtree), then drop its
   tiles 400 per idle slot (~15 ms each at 4x throttle) and finally the element itself. */
function retire(old){
  old.removeAttribute("id");
  old.setAttribute("aria-hidden", "true");
  /* makeWall's ResizeObserver stays on the old wall and re-measures its first tile when the size changes,
     forcing a layout of the whole hidden subtree (~350 ms at 4x). A non-tile first child makes it skip. */
  old.insertBefore(document.createElement("i"), old.firstChild);
  old.style.cssText = "position:absolute;left:-99999px;top:0;width:1px;height:1px;overflow:hidden;content-visibility:hidden";
  var idle = window.requestIdleCallback ? function(f){ requestIdleCallback(f, {timeout: 2000}); } : function(f){ setTimeout(f, 50); };
  (function step(){
    for (var i = 0; i < 400 && old.lastChild; i++) old.removeChild(old.lastChild);
    if (old.lastChild) idle(step); else old.remove();
  })();
}

/* Tile images load two screens ahead, like index.html's lazyImg, with two differences measured at 4x CPU
   throttle: the observer belongs to the current wall (a retired wall's unloaded images are dropped with it,
   not intersection-tested every frame), and it watches one tile in 12, which loads its group of 12, so
   5,000 tiles are 420 targets (intersection work per scrolled frame ~75 ms -> ~6 ms). */
var IO = null, GRP = null;
function newIO(){
  if (IO) IO.disconnect();
  GRP = null;
  IO = new IntersectionObserver(function(es){
    es.forEach(function(e){
      if (!e.isIntersecting) return;
      IO.unobserve(e.target);
      (e.target._g || [e.target]).forEach(function(i){
        i.addEventListener("load", function(){ i.classList.add("ok"); }, {once: true});
        i.src = i.dataset.src;
      });
    });
  }, {rootMargin: "300% 0px"});
}

function paint(){
  newIO();
  var old = $("#gawall"); if (!old) return;
  var rows = rowsNow();
  if (WALL) WALL.disconnect();
  /* A fresh wall in place of the old one, and the old one retired in pieces: tearing down 5,000 drawn tiles
     at once (makeWall's innerHTML = "", or a plain remove) is one ~80 ms task at 4x CPU throttle. */
  var w = el("div", "wall"); w.id = "gawall";
  old.parentNode.insertBefore(w, old);
  retire(old);
  WALL = window.makeWall(w, rows, tile, {step: 120, empty: "Nothing matches.",
    src: function(r){ return "/wall/" + IMGDIR[r[3]] + "/" + encodeURIComponent(r[0]) + ".png"; }});
  if (GB) GB.setCount(rows.length);
}

/* Everything a filter change touches: one tally, cards and chip counts in place, the chart's small
   HTML, the wall. barToo: rebuild the pinned bar's menu (its counts follow source / search). */
function update(barToo){
  var T = tally();
  cardsUpdate(T);
  chipCounts(T);
  $("#gachart").innerHTML = chartHTML(T);
  if (barToo) pinnedBar(null, T);
  else if (GB) GB.setCurrent(String(S.type));
  paint();
  var u = new URLSearchParams(location.search);
  u.set("tab", "gallery");
  if (S.type >= 0) u.set("type", D.types[S.type].k); else u.delete("type");
  if (S.src !== "all") u.set("src", S.src); else u.delete("src");
  history.replaceState(null, "", "?" + u.toString());
}
function setType(i, jump){
  S.type = i;
  update(false);
  if (jump && GB) window.gridTop(GB.sent);
}

function render(view, data){
  D = data; NA = D.arms.length;
  LLM = []; CX = -1;
  D.arms.forEach(function(a, i){ if (a.kind === "ocr") CX = i; else LLM.push(i); });
  var u = new URLSearchParams(location.search), tk = u.get("type"), sk = u.get("src");
  S.type = -1; D.types.forEach(function(t, i){ if (t.k === tk) S.type = i; });
  S.src = D.sources.some(function(s){ return s.k === sk; }) ? sk : "all";
  S.q = ""; S.same = false; GB = null; WALL = null;
  var root = el("div", "ga");
  root.innerHTML = '<div class="lead"><h2>Gallery</h2><span class="n">' + fmt(D.rows.length) + ' scored drawings, by molecule type</span></div>'
    + '<div class="cmph" id="gahead"></div><div id="gacards"></div>'
    + '<div class="ftools" id="gatools">' + toolsHTML() + '</div>'
    + '<div class="card"><h3>Where readers differ <span>exact % by type, best LLM vs OCR; tap a type to filter</span></h3>'
    + '<div class="lgd">' + D.arms.map(function(a){ return '<span><i style="background:' + a.color + '"></i>' + esc(a.short) + '</span>'; }).join("")
    + '</div><div id="gachart"></div><div class="sub">' + esc(D.note) + ' A reader needs ' + MIN_N + ' images read in a set to be ranked.</div></div>';
  view.appendChild(root);
  cardsInit($("#gacards"));
  var T = tally();
  pinnedBar(root, T);
  var w = el("div", "wall"); w.id = "gawall"; root.appendChild(w);
  var f = el("footer"); f.textContent = "Built " + D.built.replace("T", " ").replace("Z", " UTC") + " from the LLM vs OCR scores of "
    + D.from.replace("T", " ").replace("Z", " UTC") + "." + (D.dropped && D.dropped.length ? " Types with fewer than 10 images are not shown: "
    + D.dropped.map(function(x){ return x.label + " (" + x.n + ")"; }).join(", ") + "." : "");
  root.appendChild(f);
  window.GRID_END = function(cb, follow){ if (WALL) WALL.end(cb, follow); else if (cb) cb(); };
  $("#gatools").addEventListener("click", function(e){
    var b = e.target.closest("button"); if (!b) return;
    if (b.dataset.t != null) setType(+b.dataset.t, false);
    else if (b.dataset.s){ S.src = b.dataset.s;
      [].forEach.call(document.querySelectorAll(".ga .chip[data-s]"), function(x){ x.setAttribute("aria-pressed", x.dataset.s === S.src); });
      update(true); }
    else if (b.id === "gasame"){ S.same = !S.same; b.setAttribute("aria-pressed", S.same); update(true); }
  });
  $("#gachart").addEventListener("click", function(e){
    var r = e.target.closest(".tr"); if (!r) return;
    var i = +r.dataset.t; setType(S.type === i ? -1 : i, false);
  });
  $("#gachart").addEventListener("toggle", function(e){ if (e.target.matches("details.more")) S.more = e.target.open; }, true);
  update(true);
}

window.GALLERY = {render: render};
})();
