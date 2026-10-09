/* The "LLM vs OCR" tab: four readers on the same corpus drawings.
   Data: /wall/llmocr.json (charts + one compact row per image) and /wall/llmocr_detail.json
   (every answer, fetched the first time a sheet opens), both built by tools/build_llmocr.py.
   Every number on the tab comes from a built payload. The page only counts the filter chips (from
   the same rows the tiles are drawn from) and turns the renderer-control counts into percentages.
   Uses index.html's helpers ($, el, esc) and its #sheet dialog. */
(function(){
"use strict";
var CSS = [
".lo h2{font-size:16px;font-weight:750;margin:0}",
".lo .lead{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;padding:18px 0 4px}",
".lo .lead .n{color:var(--dim);font-size:13px}",
".lo .lgd{display:flex;flex-wrap:wrap;gap:6px 14px;margin:6px 0 2px;font-size:12.5px;color:var(--dim)}",
".lo .lgd i{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:-1px;border-radius:2px}",
".lo .grid{columns:3 360px;column-gap:12px;margin:12px 0}",
".lo .card{background:var(--panel);border:1px solid var(--line);padding:13px 14px 12px;min-width:0;break-inside:avoid;margin:0 0 12px;display:inline-block;width:100%}",
".lo .card h3{font-size:13.5px;font-weight:700;margin:0 0 10px;color:var(--ink)}",
".lo .card h3 span{color:var(--dim);font-weight:400}",
".lo .hb{display:grid;grid-template-columns:104px minmax(0,1fr) 56px 64px;align-items:center;column-gap:10px;row-gap:4px;margin:7px 0}",
".lo .hb .l{font-size:12.5px;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
".lo .hb .tr{height:14px;background:#0b0f14;position:relative;min-width:0}",
".lo .hb .tr i{position:absolute;left:0;top:0;bottom:0;border-radius:0 4px 4px 0}",
".lo .hb b{font-size:13px;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}",
".lo .hb .k{font-size:12px;color:var(--dim);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}",
".lo .hb .nt{grid-column:2/-1;font-size:12.5px;color:var(--dim)}",
".lo .grp{margin:10px 0 2px;font-size:12px;color:var(--dim)}",
".lo .grp b{color:var(--ink);font-weight:600}",
".lo .grp:first-of-type{margin-top:0}",
".lo .hb.sm{margin:3px 0} .lo .hb.sm .tr{height:10px} .lo .hb.sm b{font-size:12.5px}",
/* Head-to-head: discordant images only, centred, one side per arm. */
".lo .pr{margin:0 0 14px}",
".lo .pr .ph{display:flex;justify-content:space-between;gap:8px;font-size:12.5px;color:var(--ink);margin-bottom:4px}",
".lo .pr .ph span{white-space:nowrap}",
".lo .pr .dv{display:grid;grid-template-columns:46px minmax(0,1fr) 2px minmax(0,1fr) 46px;align-items:center;column-gap:0}",
".lo .pr .dv .ax{background:var(--dim);height:20px}",
".lo .pr .dv .sd{height:14px;display:flex;align-items:center;min-width:0}",
".lo .pr .dv .sd.lf{justify-content:flex-end}",
".lo .pr .dv .sd i{display:block;height:14px}",
".lo .pr .dv .sd.lf i{border-radius:4px 0 0 4px} .lo .pr .dv .sd.rt i{border-radius:0 4px 4px 0}",
".lo .pr .dv b{font-size:13px;font-variant-numeric:tabular-nums;white-space:nowrap}",
".lo .pr .dv b.ln{text-align:right;padding-right:8px} .lo .pr .dv b.rn{text-align:left;padding-left:8px}",
".lo .pr .pf{font-size:12px;color:var(--dim);margin-top:3px;text-align:center}",
".lo .cav{margin:4px 0 0;padding:0;list-style:none}",
".lo details.lomethod{margin-top:6px}",
".lo .cav li{font-size:12.5px;color:var(--dim);line-height:1.5;padding:3px 0 3px 12px;position:relative}",
".lo .cav li::before{content:'';position:absolute;left:0;top:11px;width:4px;height:4px;background:var(--dim)}",
/* The wall: image, then one cell per arm. */
".lo .wall{grid-template-columns:repeat(auto-fill,minmax(112px,1fr))}",
".lo .t.lt{aspect-ratio:auto;contain-intrinsic-size:auto 160px;background:var(--panel);text-align:left;color:var(--ink);font:inherit}",
".lo .t.lt::after{display:none}",
".lo .t.lt img{height:auto;aspect-ratio:1;background:#1c2128}",
".lo .t.lt img.ok{background:#fff}",
".lo .t.lt .cells{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:3px;padding:4px 3px 0}",
"#lofail,#lowallh{scroll-margin-top:68px}",
".lo .t.lt .cells i{font-style:normal;font-size:10.5px;letter-spacing:-.2px;font-weight:700;text-align:center;line-height:16px;height:19px;color:#06090d;border-radius:4px;padding:0;box-shadow:inset 0 -3px 0 var(--arm);overflow:hidden}",
".lo .t.lt .nm{display:block;font-size:12px;padding:3px 5px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink)}",
".lo .c-e{background:var(--exact)} .lo .c-s{background:var(--stereo)}",
".lo .c-w{background:var(--wrong);color:#fff!important} .lo .c-i{background:#4b535d;color:#fff!important}",
".lo .c-n{background:#0b0f14;color:var(--dim)!important}",
".lo .ckey i.c-n{box-shadow:inset 0 0 0 1px var(--line)}",
".lo .ckey{display:flex;flex-wrap:wrap;gap:6px 12px;font-size:12px;color:var(--dim);margin:2px 0 6px}",
".lo .ckey i{display:inline-block;width:10px;height:10px;margin-right:5px;vertical-align:-1px}",
".lo .ckey u{text-decoration:none;color:var(--ink);font-weight:600}",
".lo .bar{top:57px}",
"@media(max-width:560px){.lo .hb{grid-template-columns:82px minmax(0,1fr) 50px 58px;column-gap:8px}",
"  .lo .card{padding:12px 11px} .lo .wall{grid-template-columns:repeat(auto-fill,minmax(104px,1fr))}}",
"#sheet.lo-wide{max-width:1080px}",
"#sheet.lo-wide .sclose{border:1px solid var(--line);color:var(--ink);top:6px;right:6px;background:#0b0f14}",
".lo-top{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;margin-bottom:12px}",
"@media(min-width:700px){.lo-top{grid-template-columns:minmax(0,300px) minmax(0,1fr);align-items:start}}",
".lo-in{background:#fff;margin:0} .lo-in img{width:100%;max-height:30dvh;object-fit:contain;display:block}",
".lo-in figcaption{background:var(--panel);color:var(--dim);font-size:12px;padding:4px 0 0}",
".lo-arms{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}",
"@media(min-width:900px){.lo-arms{grid-template-columns:repeat(4,minmax(0,1fr))}}",
".lo-arm{background:#0b0f14;border:1px solid var(--line);padding:8px;min-width:0;display:flex;flex-direction:column;gap:6px}",
".lo-arm .ah,.lo-pr .ah{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:650;min-width:0}",
".lo-arm .ah i,.lo-pr .ah i{display:inline-block;width:10px;height:10px;border-radius:2px;flex:0 0 auto}",
".lo-arm .badge{align-self:flex-start}",
".lo-arm img{width:100%;aspect-ratio:1;max-height:170px;object-fit:contain;background:#fff;display:block}",
"#sheet.lo-wide .shead h3{font-size:15px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;cursor:pointer}",
"#sheet.lo-wide .shead h3.full{-webkit-line-clamp:unset;display:block}",
"@media(max-width:560px){.lo-in img{max-height:24dvh} .lo-arm img{max-height:130px} #sheet.lo-wide .shead h3{-webkit-line-clamp:2}}",
".lo-arm code{display:block;background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:6px 7px;",
"  font:11.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-all;user-select:text;-webkit-user-select:text}",
".lo-arm .nr{color:var(--dim);font-size:12.5px}",
".facts{margin:0;padding:0;list-style:none;font-size:12px;color:var(--dim);line-height:1.4}",
".lo-arm details.fold{margin-top:0} .lo-arm details.fold>summary{font-size:12.5px;min-height:44px}",
".lo-pr{border-top:1px solid var(--line);padding:12px 0}",
".lo-pr:first-child{border-top:0;padding-top:0}",
".lo-pr .ah{margin-bottom:8px}",
".facts b.mono{font:600 12.5px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink);user-select:text;-webkit-user-select:text}",
".lo-pr .facts{font-size:12.5px;margin-bottom:4px} .lo-pr .facts li{padding:2px 0}",
".lo .lead{justify-content:space-between}",
".lo .acts{display:flex;gap:6px;flex-wrap:wrap}",
".lo .acts .chip{color:var(--ink)}",
".lo .n{margin-top:2px}",
".lo .fchips{display:flex;flex-wrap:wrap;gap:7px;margin:4px 0 10px}",
".lo .srcsw{display:flex;flex-wrap:wrap;gap:7px;margin:4px 0 8px}",
".lo .srcsw .chip{color:var(--ink)}",
"@media(max-width:560px){.lo .fchips{display:grid;grid-template-columns:1fr 1fr;gap:6px}",
"  .lo .fchips .chip{white-space:normal;text-align:left;border-radius:10px;font-size:12.5px;padding:6px 10px;line-height:1.3}}",
".lo .lobar{align-items:center;gap:10px;padding:10px 0;overflow:visible;flex-wrap:wrap}",
".lo .lobar>.cur{flex:1 1 auto;min-width:0;font-size:13px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
".lo .lobar>.chip{flex:0 0 auto}",
".lo .lobar .cur b{color:var(--ink);font-weight:600}",
"@media(max-width:560px){.lo .lobar>input[type=search]{flex:1 0 100%!important;width:100%}}",
".lo .lobar>input[type=search]{flex:0 0 240px;min-width:0}"
].join("\n");
var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);

var V = {e:"exact", s:"stereo", w:"wrong", i:"invalid", "-":"not read", x:"invalid"};
var VL = {e:"exact", s:"stereo only", w:"wrong", i:"unparseable", "-":"not read", x:"excluded (lookup)"};
var S = {filter:"all", q:"", shown:150, step:150, detail:null, pending:null, view:"all"};
/* Where an image came from: the corpus, or the superatom set (built, real). Rows carry it as r[3]. */
var IMGDIR = {c: "img", b: "superatoms", r: "superatoms"};
var TXTDIR = {c: "sonnet55api_txt", b: "superatoms_txt", r: "superatoms_txt"};
function VW(){ return D.views[S.view] || D.views.all; }
var D = null, ARM = {}, IDX = {};
var fmt = function(n){ return n == null ? "–" : (+n).toLocaleString("en-US"); };
var pv = function(p){ return p < 0.001 ? "p<0.001" : "p=" + (+p).toPrecision(2).replace(/\.?0+$/, ""); };

/* Filters: who got it right. Index order is the payload's arm order. */
function filters(){
  var i = IDX, ok = function(c, a){ return c[i[a]] === "e"; }, rd = function(c, a){ return "eswi".indexOf(c[i[a]]) >= 0; };
  var miss = function(c, a){ return rd(c, a) && !ok(c, a); };
  var llm = function(c){ return ["s55","api","s5"].some(function(a){ return ok(c, a); }); };
  return [
    ["all", "All", function(){ return true; }],
    ["m55", "5.5 tools misses", function(c){ return miss(c, "s55"); }],
    ["mapi", "5.5 API misses", function(c){ return miss(c, "api"); }],
    ["m5", "Sonnet 5 misses", function(c){ return miss(c, "s5"); }],
    ["mcx", "CXMolScribe misses", function(c){ return miss(c, "cx"); }],
    ["both", "Missed by LLM and OCR", function(c){ return !llm(c) && !ok(c, "cx"); }],
    ["lo", "LLM right, OCR wrong", function(c){ return llm(c) && !ok(c, "cx"); }],
    ["ol", "OCR right, LLM wrong", function(c){ return ok(c, "cx") && !llm(c); }],
    ["ta", "Tools right, API wrong", function(c){ return ok(c, "s55") && miss(c, "api"); }],
    ["at", "API right, tools wrong", function(c){ return ok(c, "api") && miss(c, "s55"); }]
  ];
}

function hbar(label, pct, color, val, small, sm, title){
  return '<div class="hb' + (sm ? ' sm' : '') + '"' + (title ? ' title="' + esc(title) + '"' : '') + '><span class="l">' + esc(label)
    + '</span><span class="tr"><i style="width:' + Math.max(0.5, Math.min(100, pct)) + '%;background:' + color
    + '"></i></span><b>' + val + '</b><span class="k">' + (small || '') + '</span></div>';
}

function legend(){
  return '<div class="lgd">' + D.arms.map(function(a){
    return '<span><i style="background:' + a.color + '"></i>' + esc(a.label) + '</span>'; }).join("") + '</div>';
}

function cardShared(){
  var s = VW().shared;
  if (!s.n) return '<div class="card"><h3>Exact, images each arm has read <span>tool arms have not read these yet</span></h3>'
    + VW().each.map(function(x){ var a = ARM[x.id];
        return x.n ? hbar(a.short, x.pct, a.color, x.pct + "%", fmt(x.exact) + "/" + fmt(x.n), false)
                   : '<div class="hb"><span class="l">' + esc(a.short) + '</span><span class="nt">not read yet</span></div>';
      }).join("") + '</div>';
  return '<div class="card"><h3>Exact, same images <span>n = ' + fmt(s.n) + ', the images all four read</span></h3>'
    + s.arms.map(function(x){ var a = ARM[x.id];
        return hbar(a.short, x.pct, a.color, x.pct + "%", fmt(x.exact), false,
          a.label + ": exact " + x.exact + ", stereo only " + x.stereo + ", wrong " + x.wrong + ", unparseable " + x.invalid);
      }).join("") + '</div>';
}

function cardPairs(){
  var all = VW().pairs.map(function(p){ return {a:p.a, b:p.b, an:p.a_only, bn:p.b_only, n:p.n, both:p.both,
      ap:p.a_pct, bp:p.b_pct, p:p.p}; });
  var e = VW().either;
  if (!all.length) return '';
  var max = Math.max.apply(null, all.map(function(p){ return Math.max(p.an, p.bn); }).concat(e ? [e.llm_only, e.cx_only] : []));
  function side(n, color, left){
    return '<span class="sd ' + (left ? "lf" : "rt") + '"><i style="width:' + (n ? Math.max(1, n / max * 100) : 0)
      + '%;background:' + color + '"></i></span>';
  }
  function row(la, lb, ca, cb, an, bn, foot, ap, bp){
    return '<div class="pr"><div class="ph"><span>' + esc(la) + (ap != null ? ' ' + ap + '%' : '') + '</span><span>'
      + (bp != null ? bp + '% ' : '') + esc(lb) + '</span></div><div class="dv"><b class="ln">' + fmt(an) + '</b>' + side(an, ca, true)
      + '<span class="ax"></span>' + side(bn, cb, false) + '<b class="rn">' + fmt(bn) + '</b></div><div class="pf">' + foot + '</div></div>';
  }
  return '<div class="card"><h3>Who alone got it right <span>bars: images only one of the pair got exact; % on each pair\u2019s own n</span></h3>'
    + all.map(function(p){ var A = ARM[p.a], B = ARM[p.b];
        return row(A.short, B.short, A.color, B.color, p.an, p.bn,
          "n " + fmt(p.n) + " · both right " + fmt(p.both) + " · " + pv(p.p), p.ap, p.bp); }).join("")
    + (e && all.length > 1 ? row("Best of 3 Sonnet arms", "CXMolScribe", "#8b98a5", ARM.cx.color, e.llm_only, e.cx_only,
        "n " + fmt(e.n) + (e.api_alone ? " (" + fmt(e.api_alone) + " read only by the API arm)" : "")
        + " · either right " + fmt(e.any), null, null) : '')
    + '</div>';
}

function cardSize(){
  if (!VW().size.length) return '';
  return '<div class="card"><h3>Exact by molecule size <span>heavy atoms, same ' + fmt(VW().shared.n) + ' images</span></h3>'
    + VW().size.map(function(g){
        return '<div class="grp"><b>' + esc(g.label) + ' atoms</b> · n ' + fmt(g.n) + '</div>'
          + g.arms.map(function(x){ var a = ARM[x.id];
              return hbar(a.short, x.pct, a.color, x.pct + "%", fmt(x.exact), true, a.label + ": " + x.exact + " of " + g.n); }).join("");
      }).join("") + '</div>';
}

function cardCost(){
  var known = VW().cost.filter(function(c){ return c.usd != null; });
  if (!known.length) return '';
  var max = Math.max.apply(null, known.map(function(c){ return c.usd; }));
  return '<div class="card"><h3>Cost per image <span>API list price, ' + (VW().shared.n ? 'same images' : 'images each arm read') + '</span></h3>'
    + VW().cost.map(function(c){ var a = ARM[c.id];
        if (c.usd == null) return '<div class="hb"><span class="l">' + esc(a.short) + '</span><span class="nt">'
          + esc(c.id === "cx" ? c.note : "not read yet") + '</span></div>';
        return hbar(a.short, c.usd / max * 100, a.color, "$" + (c.usd < 0.1 ? c.usd.toFixed(3) : c.usd.toFixed(2)), null, false,
          a.label + ": mean over " + c.n + " images");
      }).join("") + '</div>';
}

/* The renderer-control card reads /wall/control.json itself (its own builder rewrites it as control
   readers land), so new control readings show up without a rebuild of this tab's payload. The payload's
   copy is the fallback if that fetch fails. */
var CTL_ID = {"Sonnet 5.5 API only": "api", "Sonnet 5.5 with tools": "s55"};
function controlFrom(C){
  if (!C || !C.arms) return null;
  var ren = String(C.renderer || "other renderer").split(",")[0];
  var arms = C.arms.filter(function(a){ return a.n; }).map(function(a){
    var p = function(x){ return Math.round(x / a.n * 1000) / 10; };
    return {id: CTL_ID[a.arm] || a.arm, n: a.n, corpus: a.corpus_exact, control: a.control_exact,
            corpus_pct: p(a.corpus_exact), control_pct: p(a.control_exact), p: a.mcnemar_p};
  });
  return arms.length ? {renderer: ren, short: ren.replace(/^EPAM\s+|\s+[\d.]+$/g, ""), arms: arms} : null;
}
function liveControl(){
  fetch("/wall/control.json", {cache: "no-cache"}).then(function(r){ return r.ok ? r.json() : null; })
    .then(function(C){ var c = controlFrom(C), box = $("#loctl"); if (c && box){ D.control = c; box.outerHTML = cardControl(); } },
          function(){});
}
function cardControl(){
  var c = D.control;
  if (!c) return '<div id="loctl"></div>';
  return '<div class="card" id="loctl"><h3>Corpus renderer vs another renderer <span>RDKit vs ' + esc(c.renderer) + ', same molecules</span></h3>'
    + c.arms.map(function(x){ var a = ARM[x.id] || {label: x.id, short: x.id, color: "#8b98a5"};
        return '<div class="grp"><b>' + esc(a.label) + '</b> · n ' + fmt(x.n) + (x.p != null ? ' · ' + pv(x.p) : '') + '</div>'
          + hbar("RDKit", x.corpus_pct, a.color, x.corpus_pct + "%", fmt(x.corpus), true)
          + hbar(c.short || c.renderer, x.control_pct, a.color, x.control_pct + "%", fmt(x.control), true);
      }).join("") + '</div>';
}

function cardHand(){
  var h = D.hand;
  if (!h) return '';
  return '<div class="card"><h3>Hand-picked set <span>n = ' + h.n + '</span></h3>'
    + h.bars.map(function(x){ var a = ARM[x.id];
        return hbar(x.short || a.short, x.pct, a.color, x.exact + "/" + x.n, null, false, x.label); }).join("")
    + '<p class="sub" style="font-size:12.5px;margin-top:6px">' + esc(h.note) + '</p></div>';
}

function tile(r){
  var b = el("button", "t lt"), c = r[2];
  b.innerHTML = '<img decoding="async" data-src="/wall/' + IMGDIR[r[3]] + '/' + encodeURIComponent(r[0]) + '.png" alt="">'
    + '<span class="cells">' + D.arms.map(function(a, i){
        var v = c[i];
        return '<i class="c-' + (v === "-" || v === "x" ? "n" : v) + '" style="--arm:' + a.color + '" title="' + esc(a.label + ": " + VL[v]) + '">' + esc(a.tag) + '</i>';
      }).join("") + '</span><span class="nm">' + esc(r[1]) + '</span>';
  if (window.lazyImg) window.lazyImg(b.firstChild); else b.firstChild.src = b.firstChild.dataset.src;
  b.onclick = function(){ openSheet(r); };
  return b;
}

var io = new IntersectionObserver(function(es){
  if (es.some(function(e){ return e.isIntersecting; })){ S.shown += S.step; paint(); }
}, {rootMargin: "1200px"});

function rowsNow(){
  var f = filters().filter(function(x){ return x[0] === S.filter; })[0] || filters()[0];
  return D.rows.filter(function(r){ return inView(r) && f[2](r[2]) && (!S.q || r[1].toLowerCase().indexOf(S.q) >= 0); });
}

function paint(){
  var w = $("#lowall"); if (!w) return;
  io.disconnect();
  var rows = rowsNow(), frag = document.createDocumentFragment();
  w.innerHTML = "";
  rows.slice(0, S.shown).forEach(function(r){ frag.appendChild(tile(r)); });
  w.appendChild(frag);
  if (rows.length > S.shown){ var m = el("div", "more", fmt(rows.length - S.shown) + " more below"); w.appendChild(m); io.observe(m); }
  else if (!rows.length) w.appendChild(el("div", "more", "Nothing matches."));
  $("#locount").textContent = fmt(rows.length) + (rows.length === 1 ? " image" : " images");
}

function chips(){
  var box = el("div", "fchips");
  filters().forEach(function(f){
    var n = D.rows.filter(function(r){ return inView(r) && f[2](r[2]); }).length;
    var b = el("button", "chip");
    var arm = {m55: "s55", mapi: "api", m5: "s5", mcx: "cx"}[f[0]];
    b.innerHTML = (f[0] === "all" ? "" : '<span class="dot" style="background:' + (arm ? ARM[arm].color : "#8b98a5") + '"></span>')
      + esc(f[1]) + '<i>' + fmt(n) + '</i>';
    b.dataset.f = f[0];
    b.setAttribute("aria-pressed", S.filter === f[0]);
    b.onclick = function(){ setFilter(f[0], true); };
    box.appendChild(b);
  });
  return box;
}

function setFilter(f, jump){
  S.filter = f; S.shown = S.step;
  [].forEach.call(document.querySelectorAll(".lo .fchips .chip"), function(x){ x.setAttribute("aria-pressed", x.dataset.f === f); });
  var lab = filters().filter(function(x){ return x[0] === f; })[0];
  $("#locur").textContent = lab ? lab[1] : "All";
  paint();
  if (jump) $("#lowallh").scrollIntoView({behavior: "smooth", block: "start"});
}

function stickyBar(){
  var bar = el("div", "bar lobar");
  bar.innerHTML = '<span class="cur">Showing <b id="locur">All</b> · <span id="locount"></span></span>'
    + '<button class="chip" id="lofilt">Filters ↑</button>';
  var s = el("input"); s.type = "search"; s.placeholder = "Search name"; s.value = S.q;
  s.oninput = function(){ S.q = s.value.trim().toLowerCase(); S.shown = S.step; paint(); };
  bar.appendChild(s);
  bar.querySelector("#lofilt").onclick = function(){ $("#lofail").scrollIntoView({behavior: "smooth", block: "start"}); };
  return bar;
}

function getDetail(){
  if (S.detail) return Promise.resolve(S.detail);
  if (!S.pending) S.pending = fetch("/wall/llmocr_detail.json").then(function(r){
    if (!r.ok) throw new Error("HTTP " + r.status); return r.json();
  }).then(function(d){ S.detail = d; return d; }, function(e){ S.pending = null; throw e; });
  return S.pending;
}

function wide(){
  var d = $("#sheet");
  d.classList.add("lo-wide");
  d.addEventListener("close", function(){ d.classList.remove("lo-wide"); }, {once: true});
}

function openSheet(r){
  var k = r[0], c = r[2];
  $("#sheetHead").innerHTML = '<button class="sclose" aria-label="Close" onclick="document.getElementById(\'sheet\').close()">&times;</button>'
    + '<h3 title="' + esc(r[1]) + '" onclick="this.classList.toggle(\'full\')">' + esc(r[1]) + '</h3>';
  var body = $("#sheetBody");
  body.innerHTML = '<div class="lo-top"><figure class="lo-in"><img decoding="sync" src="/wall/' + IMGDIR[r[3]] + '/' + encodeURIComponent(k)
    + '.png" alt="Input drawing"><figcaption>Input</figcaption></figure><div class="lo-ref" id="loref"></div></div>'
    + '<div class="lo-arms" id="lodet"><div class="sub">Loading answers…</div></div>';
  wide();
  $("#sheet").showModal();
  body.scrollTop = 0;
  getDetail().then(function(d){
    var x = d[k] || {};
    var ref = $("#loref"), det = $("#lodet"); if (!ref || !det) return;
    ref.innerHTML = x.t ? '<div class="kv"><label>Reference (PubChem)</label><code>' + esc(x.t) + '</code></div>'
             : '<div class="kv"><label>Reference</label><code>' + esc((D.withheld && D.withheld.note) || "Withheld") + '</code></div>';
    det.innerHTML = D.arms.map(function(a, i){
      var v = c[i], y = x[a.id];
      var h = '<div class="lo-arm"><div class="ah"><i style="background:' + a.color + '"></i>' + esc(a.short) + '</div>';
      if (!y) return h + '<div class="nr">' + esc(VL[v]) + '</div></div>';
      h += '<span class="badge ' + V[v] + '">' + esc(VL[v]) + '</span>'
        + (y[3] ? '<img loading="lazy" src="/wall/llmocr_pred/' + y[3] + '.png" alt="">' : '')
        + '<code>' + esc(y[0] || "(nothing emitted)") + '</code>'
        + '<ul class="facts">' + (y[1] != null && y[1] !== "" ? '<li>confidence ' + esc(y[1]) + '</li>' : '')
        + (y[2] || []).map(function(t){ return '<li>' + esc(t) + '</li>'; }).join("") + '</ul>'
        + (a.id === "api" ? '<details class="fold" data-k="' + esc(k) + '"><summary>Full reply</summary><div class="pre">Loading…</div></details>' : '');
      return h + '</div>';
    }).join("");
    var f = det.querySelector("details[data-k]");
    if (f) f.addEventListener("toggle", function(){
      if (!f.open || f.dataset.got) return; f.dataset.got = "1";
      fetch("/wall/" + TXTDIR[r[3]] + "/" + encodeURIComponent(k) + ".txt").then(function(q){
        if (!q.ok) throw new Error("HTTP " + q.status); return q.text(); })
      .then(function(s){ f.querySelector(".pre").textContent = s; },
            function(e){ f.querySelector(".pre").textContent = "Could not load the reply (" + e.message + ")"; });
    });
  }, function(e){ var t = $("#lodet"); if (t) t.textContent = "Could not load the answers (" + e.message + ")"; });
}

function openPrompts(){
  $("#sheetHead").innerHTML = '<button class="sclose" aria-label="Close" onclick="document.getElementById(\'sheet\').close()">&times;</button>'
    + '<h3>Prompts and settings</h3>';
  var body = $("#sheetBody");
  body.innerHTML = (D.prompts || []).map(function(p){
    var a = ARM[p.id];
    return '<section class="lo-pr"><div class="ah"><i style="background:' + a.color + '"></i>' + esc(a.label) + '</div>'
      + '<ul class="facts"><li>Model <b class="mono">' + esc(p.model) + '</b></li>' + p.settings.map(function(t){ return '<li>' + esc(t) + '</li>'; }).join("") + '</ul>'
      + (p.prompts || []).map(function(q){ return '<details class="fold"><summary>' + esc(q[0] === "Prompt" ? "Show the prompt" : "Prompt: " + q[0].toLowerCase())
          + '</summary><div class="pre">' + esc(q[1]) + '</div></details>'; }).join("")
      + '</section>';
  }).join("");
  wide();
  $("#sheet").showModal();
  body.scrollTop = 0;
}

function inView(r){ return S.view === "all" || r[3] === S.view; }

function chartsHTML(){
  var V = VW(), corpusish = S.view === "all" || S.view === "c";
  return '<div class="sub n">' + fmt(V.n) + ' images · read by ' + D.arms.map(function(a){ return esc(a.short) + ' ' + fmt(V.read[a.id]); }).join(" · ") + '</div>'
    + '<div class="grid">' + cardShared() + cardPairs() + cardSize() + cardCost()
    + (corpusish ? cardControl() + cardHand() : '') + '</div>';
}

function viewSwitch(){
  var order = ["all", "c", "b", "r"].filter(function(v){ return D.views[v]; });
  if (order.length < 2) return '';
  return '<div class="srcsw" role="group" aria-label="Image source">' + order.map(function(v){
    return '<button class="chip" data-v="' + v + '" aria-pressed="' + (S.view === v) + '">' + esc(D.views[v].label)
      + '<i>' + fmt(D.views[v].n) + '</i></button>'; }).join("") + '</div>';
}

function setView(v){
  S.view = v;
  [].forEach.call(document.querySelectorAll(".lo .srcsw .chip"), function(x){ x.setAttribute("aria-pressed", x.dataset.v === v); });
  $("#locharts").innerHTML = chartsHTML();
  liveControl();
  var box = $("#lofail .fchips"); if (box) box.replaceWith(chips());
  S.shown = S.step; setFilter(S.filter, false);
}

function render(view, data){
  D = data; ARM = {}; IDX = {};
  D.arms.forEach(function(a, i){ ARM[a.id] = a; IDX[a.id] = i; });
  if (!D.views[S.view]) S.view = "all";
  var root = el("div", "lo");
  root.innerHTML = '<div class="lead"><h2>LLM vs OCR</h2>'
    + '<span class="acts"><button class="chip" id="lojump">Failures ↓</button><button class="chip" id="loprompt">Prompts &amp; settings</button></span></div>'
    + viewSwitch() + legend()
    + '<div id="locharts">' + chartsHTML() + '</div>'
    + '<ul class="cav">' + D.caveats.map(function(t){ return '<li>' + esc(t) + '</li>'; }).join("") + '</ul>'
    + (D.method && D.method.length ? '<details class="fold lomethod"><summary>Caveats &amp; method</summary><ul class="cav">'
        + D.method.map(function(t){ return '<li>' + esc(t) + '</li>'; }).join("") + '</ul></details>' : '')
    + '<div class="block" id="lofail"><h2 class="blockh">Failures and disagreements</h2></div>';
  view.appendChild(root);
  root.querySelector("#lofail").appendChild(chips());
  var wh = el("div", "ckey"); wh.id = "lowallh";
  wh.innerHTML = 'Cells: ' + D.arms.map(function(a){ return '<span><u>' + esc(a.tag) + '</u> ' + esc(a.short) + '</span>'; }).join(" ")
    + ' &nbsp; <span><i class="c-e"></i>exact</span><span><i class="c-s"></i>stereo only</span>'
    + '<span><i class="c-w"></i>wrong</span><span><i class="c-i"></i>unparseable</span><span><i class="c-n"></i>not read</span>';
  root.appendChild(wh);
  root.appendChild(stickyBar());
  var w = el("div", "wall"); w.id = "lowall"; root.appendChild(w);
  var f = el("footer"); f.textContent = "Built " + D.built.replace("T", " ").replace("Z", " UTC") + "."
    + (D.withheld && D.withheld.n ? " Reference withheld on " + fmt(D.withheld.n) + " images until the tool-using readers have read them." : "");
  root.appendChild(f);
  root.querySelector("#lojump").onclick = function(){ $("#lofail").scrollIntoView({behavior: "smooth", block: "start"}); };
  root.querySelector("#loprompt").onclick = openPrompts;
  var sw = root.querySelector(".srcsw");
  if (sw) sw.addEventListener("click", function(e){ var b = e.target.closest("button[data-v]"); if (b) setView(b.dataset.v); });
  S.shown = S.step;
  setFilter(S.filter, false);
  liveControl();
}

window.LLMOCR = {render: render};
})();
