"""Genera presentazione/presentazione.html: la presentazione in un unico file, apribile con doppio click.

Legge presentazione/sorgente/deck.json (ordine delle slide e font) e le slide in presentazione/sorgente/slides/.
La pagina e' una presentazione a schermo intero, una slide alla volta (canvas 1920x1080 adattato alla finestra).
All'arrivo di ogni slide gli elementi compaiono in sequenza, le barre crescono da zero e i numeri contano
fino al loro valore. Le slide sorgente non cambiano: le animazioni si applicano da sole.

Comandi: frecce, spazio, PagSu/PagGiu, click o swipe per cambiare slide; Home/Fine per la prima/ultima;
F per lo schermo intero; N per le note di chi presenta (il tag <aside>); R per ripetere le animazioni.
Ctrl+P stampa una slide per pagina, senza animazioni. Serve internet solo per i font Google.

Uso: python build_presentazione.py
La versione online (modificabile, esportabile in PDF/PowerPoint) e' su claude.ai: li' le animazioni non ci sono.
"""
import html, json, os, re

SRC = os.path.join('presentazione', 'sorgente')
OUT = os.path.join('presentazione', 'presentazione.html')

CSS = '''
html, body { margin:0; height:100%; background:#141210; overflow:hidden; font-family:'Rubik', Arial, sans-serif; }
#deck { position:fixed; inset:0; }
.slide { position:absolute; inset:0; opacity:0; visibility:hidden; transition:opacity .5s ease, visibility .5s; }
.slide.on { opacity:1; visibility:visible; }
.canvas { position:absolute; left:50%; top:50%; width:1920px; height:1080px; transform:translate(-50%,-50%) scale(var(--s,1)); }
.canvas section { width:1920px; height:1080px; box-sizing:border-box; position:relative; overflow:hidden; }
.canvas h1, .canvas h2, .canvas h3, .canvas p, .canvas ul, .canvas ol { margin:0; }
.canvas ul, .canvas ol { padding-left:1.3em; }
.canvas div { box-sizing:border-box; }
.canvas table { border-collapse:collapse; width:100%; }
.canvas th, .canvas td { padding:.35em .6em; border-bottom:1px solid #d3c8b8; vertical-align:top; }
.canvas th { font-weight:600; }
.count { font-variant-numeric:tabular-nums; }
#hud { position:fixed; right:16px; bottom:16px; display:flex; gap:6px; align-items:center; padding:6px; border-radius:10px;
  background:rgba(20,18,16,.75); color:#e6dfd3; font-size:14px; transition:opacity .4s; z-index:3; }
#hud.idle { opacity:0; }
#hud button { background:none; border:1px solid #5a514a; color:#e6dfd3; border-radius:6px; min-width:34px; height:30px;
  font:inherit; cursor:pointer; padding:0 8px; }
#hud button:hover { background:#3a332e; }
#hud span { min-width:56px; text-align:center; font-variant-numeric:tabular-nums; }
#notes { position:fixed; left:16px; right:16px; bottom:60px; max-height:35vh; overflow:auto; padding:16px 20px;
  border-radius:10px; background:rgba(20,18,16,.92); color:#e6dfd3; font-size:17px; line-height:1.5; z-index:2; }
#notes[hidden] { display:none; }
#progress { position:fixed; left:0; top:0; height:3px; background:#d9622b; transition:width .4s ease; z-index:3; }
@media print {
  @page { size:1920px 1080px; margin:0; }
  html, body { height:auto; overflow:visible; background:none; }
  #deck { position:static; }
  .slide { position:relative; width:1920px; height:1080px; opacity:1; visibility:visible; transition:none; break-after:page; }
  .slide:last-child { break-after:auto; }
  .canvas { position:static; transform:none; }
  #hud, #notes, #progress { display:none; }
}
'''

JS = r'''
(function () {
  const slides = [...document.querySelectorAll('.slide')];
  const notes = document.getElementById('notes');
  const counter = document.getElementById('counter');
  const progress = document.getElementById('progress');
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let cur = -1, running = [], timers = [];

  // --- adattamento alla finestra ---
  function fit() {
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    document.documentElement.style.setProperty('--s', s);
  }
  addEventListener('resize', fit); fit();

  // --- numeri: formato italiano (1.540; 2,3) ---
  const NUM = /\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?/g;
  function fmt(v, dec, thousands) {
    let s = v.toFixed(dec).replace('.', ',');
    if (thousands) s = s.replace(/^(\d+)/, d => d.replace(/\B(?=(\d{3})+(?!\d))/g, '.'));
    return s;
  }
  function prepareCount(el) {
    // ogni nodo di testo con numeri diventa una sequenza di pezzi fissi e numeri da animare
    const parts = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const nodes = []; while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach(n => {
      const text = n.nodeValue; if (!NUM.test(text)) return; NUM.lastIndex = 0;
      const tokens = []; let last = 0, m;
      while ((m = NUM.exec(text))) {
        const raw = m[0], dec = (raw.split(',')[1] || '').length;
        tokens.push({ pre: text.slice(last, m.index), val: parseFloat(raw.replace(/\./g, '').replace(',', '.')), dec, th: raw.includes('.') });
        last = m.index + raw.length;
      }
      parts.push({ node: n, tokens, tail: text.slice(last), orig: text });
    });
    el.classList.add('count');
    return parts;
  }
  function render(parts, k) {
    parts.forEach(p => {
      p.node.nodeValue = k >= 1 ? p.orig : p.tokens.map(t => t.pre + fmt(t.val * k, t.dec, t.th)).join('') + p.tail;
    });
  }
  function countUp(el, delay, dur) {
    if (!el._parts) el._parts = prepareCount(el);
    const parts = el._parts; if (!parts.length) return;
    render(parts, 0);
    const t = setTimeout(() => {
      const t0 = performance.now();
      (function step(now) {
        const x = Math.min(1, (now - t0) / dur), k = 1 - Math.pow(1 - x, 3);
        render(parts, k);
        if (x < 1 && el._run === run) requestAnimationFrame(step); else render(parts, 1);
      })(t0);
    }, delay);
    const run = el._run = {}; timers.push(t); counted.push(el);
  }
  let counted = [];

  // --- cosa animare in una slide ---
  const px = (el, prop) => parseFloat(el.style[prop]) || 0;
  const isBar = el => el.tagName === 'DIV' && !el.children.length && el.style.width.endsWith('px') &&
    px(el, 'height') >= 16 && px(el, 'height') <= 48 && el.style.background;
  const isStack = el => el.tagName === 'DIV' && el.style.display === 'flex' && px(el, 'height') >= 40 &&
    el.children.length >= 2 && [...el.children].every(c => c.style.flex);
  const isBig = el => el.tagName === 'P' && /Oswald/.test(el.style.fontFamily) && px(el, 'fontSize') >= 56 && /\d/.test(el.textContent);

  function units(section) {
    // blocchi che compaiono uno dopo l'altro, in ordine di lettura; il pie' di pagina fisso per ultimo
    const out = [], pinned = [];
    function add(el) {
      const st = el.style, kids = [...el.children];
      if (el.tagName === 'TABLE') { el.querySelectorAll('tr').forEach(r => out.push(r)); return; }
      if (el.tagName === 'UL' || el.tagName === 'OL') { kids.forEach(k => out.push(k)); return; }
      if (el.tagName === 'DIV' && kids.length >= 2 && !isStack(el) && !isBar(el) &&
          (st.display === 'grid' || (st.display === 'flex' && st.flexDirection !== 'column') ||
           (st.display === 'flex' && st.flexDirection === 'column' && !st.background && !st.border && !st.borderTop))) {
        kids.forEach(add); return;
      }
      out.push(el);
    }
    [...section.children].forEach(el => {
      if (el.tagName === 'ASIDE') return;
      if (el.style.position === 'absolute') pinned.push(el); else add(el);
    });
    return out.concat(pinned);
  }

  function play(slide) {
    stop();
    const section = slide.querySelector('section');
    if (calm) return;
    const list = units(section);
    const step = Math.max(45, Math.min(110, 1100 / list.length));
    list.forEach((el, i) => {
      const d = 120 + i * step;
      running.push(el.animate([{ opacity: 0, transform: 'translateY(26px)' }, { opacity: 1, transform: 'none' }],
        { duration: 650, delay: d, easing: 'cubic-bezier(.2,.7,.2,1)', fill: 'backwards' }));
      // barre, barre impilate e numeri dentro questo blocco partono con lui
      const inner = [el, ...el.querySelectorAll('*')];
      let b = 0;
      inner.forEach(x => {
        if (isBar(x)) {
          // si anima la larghezza (non una scala) cosi' il numero accanto segue la barra
          const bd = d + 200 + b++ * 40;
          running.push(x.animate([{ width: '0px', minWidth: '0px' }, { width: x.style.width }],
            { duration: 1000, delay: bd, easing: 'cubic-bezier(.25,.8,.25,1)', fill: 'backwards' }));
          const label = x.nextElementSibling;
          if (label && label.tagName === 'P' && /\d/.test(label.textContent)) countUp(label, bd, 1000);
        } else if (isStack(x)) {
          running.push(x.animate([{ clipPath: 'inset(0 100% 0 0)' }, { clipPath: 'inset(0 0 0 0)' }],
            { duration: 1300, delay: d + 200, easing: 'cubic-bezier(.45,.05,.25,1)', fill: 'backwards' }));
        } else if (isBig(x)) {
          countUp(x, d + 150, 1300);
        }
      });
    });
  }
  function stop() {
    running.forEach(a => a.cancel()); running = [];
    timers.forEach(clearTimeout); timers = [];
    counted.forEach(el => { el._run = null; render(el._parts, 1); }); counted = [];
  }

  // --- navigazione ---
  function go(n, replay) {
    n = Math.max(0, Math.min(slides.length - 1, n));
    if (n === cur && !replay) return;
    if (cur >= 0) slides[cur].classList.remove('on');
    cur = n; slides[cur].classList.add('on');
    counter.textContent = (cur + 1) + ' / ' + slides.length;
    progress.style.width = ((cur + 1) / slides.length * 100) + '%';
    const aside = slides[cur].querySelector('template');
    notes.textContent = aside ? aside.content.textContent.trim() : 'Nessuna nota per questa slide.';
    history.replaceState(null, '', '#' + (cur + 1));
    play(slides[cur]);
  }
  const next = () => go(cur + 1), prev = () => go(cur - 1);
  function full() {
    if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen().catch(() => {});
  }
  const toggleNotes = () => { notes.hidden = !notes.hidden; };

  addEventListener('keydown', e => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    const k = e.key;
    if (['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'].includes(k)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'].includes(k)) { e.preventDefault(); prev(); }
    else if (k === 'Home') go(0);
    else if (k === 'End') go(slides.length - 1);
    else if (k === 'f' || k === 'F') full();
    else if (k === 'n' || k === 'N') toggleNotes();
    else if (k === 'r' || k === 'R') go(cur, true);
  });
  document.getElementById('deck').addEventListener('click', e => {
    if (e.target.closest('a')) return;
    (e.clientX < innerWidth / 3 ? prev : next)();
  });
  let tx = null;
  addEventListener('touchstart', e => { tx = e.touches[0].clientX; }, { passive: true });
  addEventListener('touchend', e => {
    if (tx === null) return; const dx = e.changedTouches[0].clientX - tx; tx = null;
    if (Math.abs(dx) > 50) (dx < 0 ? next : prev)();
  });
  document.getElementById('b-prev').onclick = prev;
  document.getElementById('b-next').onclick = next;
  document.getElementById('b-notes').onclick = toggleNotes;
  document.getElementById('b-full').onclick = full;

  // la barra dei comandi sparisce quando il mouse sta fermo
  const hud = document.getElementById('hud'); let idle;
  function wake() { hud.classList.remove('idle'); clearTimeout(idle); idle = setTimeout(() => hud.classList.add('idle'), 2500); }
  addEventListener('mousemove', wake); wake();

  // in stampa tutto al valore finale
  addEventListener('beforeprint', stop);

  const start = parseInt(location.hash.slice(1), 10);
  const begin = () => go(Number.isFinite(start) ? start - 1 : 0);
  // le animazioni partono quando i font sono pronti, cosi' le misure non cambiano a meta'
  (document.fonts ? Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 1500))]) : Promise.resolve()).then(begin);
})();
'''

deck = json.load(open(os.path.join(SRC, 'deck.json'), encoding='utf-8'))
fonts = '\n'.join(f'<link rel="stylesheet" href="{html.escape(f["href"])}">'
                  for f in deck['faces'].values() if 'href' in f)

blocks = []
for i, sid in enumerate(deck['order'], 1):
    s = open(os.path.join(SRC, 'slides', sid + '.html'), encoding='utf-8').read().strip()
    m = re.search(r'<aside>(.*?)</aside>', s, re.S)
    note = m.group(1).strip() if m else ''
    s = re.sub(r'<aside>.*?</aside>', '', s, flags=re.S)
    blocks.append(f'<div class="slide" id="s{i}"><div class="canvas">{s}</div>'
                  f'<template>{html.escape(note)}</template></div>')

page = f'''<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(deck["title"])}</title>
{fonts}
<style>{CSS}</style>
</head>
<body>
<div id="progress"></div>
<div id="deck">
{chr(10).join(blocks)}
</div>
<div id="notes" hidden></div>
<div id="hud">
<button id="b-prev" title="Slide precedente (freccia sinistra)">&#8249;</button>
<span id="counter"></span>
<button id="b-next" title="Slide successiva (freccia destra o spazio)">&#8250;</button>
<button id="b-notes" title="Note per chi presenta (N)">Note</button>
<button id="b-full" title="Schermo intero (F)">&#x26F6;</button>
</div>
<script>{JS}</script>
</body>
</html>
'''
open(OUT, 'w', encoding='utf-8').write(page)
print('Scritto', OUT, '-', len(deck['order']), 'slide')
