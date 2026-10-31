(function () {
  const root = document.querySelector('#dash-root .og');
  const F = {
    pct: v => (+v).toFixed(1) + '%',
    int: v => d3.format(',')(Math.round(+v)),
    dec1: v => (+v).toFixed(1),
    dec2: v => (+v).toFixed(2),
  };
  const METRICS = {
    danni: { label: 'Danni', fmt: F.pct, color: 0 },
    boss: { label: 'Danni al boss', fmt: F.pct, color: 1 },
    cure: { label: 'Cure', fmt: F.pct, color: 2 },
    tank: { label: 'Colpi presi', fmt: F.pct, color: 3 },
    oro: { label: 'Oro in tasca', fmt: F.int, color: 4 },
  };
  const state = window.ogState || (window.ogState = { metric: 'danni', player: 'Orange Jews' });

  // ---------- valori calcolati ----------
  dash.calc('round_lenti', {
    inputs: ['round'], title: 'Round con voto E o G',
    description: 'Conta le challenge chiuse con voto E o G, i due voti peggiori.',
    fn: (round) => [{ n: round.filter(r => r.voto === 'E' || r.voto === 'G').length }],
  });
  dash.calc('oro_team', {
    inputs: ['profilo'], title: 'Oro medio non speso',
    description: "Media sui 10 giocatori dell'oro in tasca a fine round.",
    fn: (profilo) => [{ oro: Math.round(profilo.reduce((s, r) => s + Number(r.oro_medio_fine_round), 0) / profilo.length) }],
  });
  dash.calc('corr_hp_tempo', {
    inputs: ['round'], title: 'Eroi a terra vs durata',
    description: 'Correlazione di Pearson tra eroi con HP ≤ 20% a fine round e secondi per chiudere l\'ondata (round con entrambi i dati).',
    fn: (round) => {
      const r = round.filter(x => x.secondi !== '' && x.eroi_sotto_20hp !== '');
      const xs = r.map(x => Number(x.eroi_sotto_20hp)), ys = r.map(x => Number(x.secondi));
      const mx = xs.reduce((a, b) => a + b, 0) / xs.length, my = ys.reduce((a, b) => a + b, 0) / ys.length;
      let sxy = 0, sxx = 0, syy = 0;
      xs.forEach((x, i) => { sxy += (x - mx) * (ys[i] - my); sxx += (x - mx) ** 2; syy += (ys[i] - my) ** 2; });
      return [{ r: Math.round(sxy / Math.sqrt(sxx * syy) * 100) / 100 }];
    },
  });
  dash.calc('corr_apm_danni', {
    inputs: ['profilo'], title: 'APM vs danni',
    description: 'Correlazione di Pearson tra APM e quota di danni dei 10 giocatori.',
    fn: (profilo) => {
      const xs = profilo.map(x => Number(x.apm)), ys = profilo.map(x => Number(x.danni));
      const mx = xs.reduce((a, b) => a + b, 0) / xs.length, my = ys.reduce((a, b) => a + b, 0) / ys.length;
      let sxy = 0, sxx = 0, syy = 0;
      xs.forEach((x, i) => { sxy += (x - mx) * (ys[i] - my); sxx += (x - mx) ** 2; syy += (ys[i] - my) ** 2; });
      return [{ r: Math.round(sxy / Math.sqrt(sxx * syy) * 100) / 100 }];
    },
  });

  // ---------- helper ----------
  const tip = document.createElement('div');
  tip.className = 'og-tip'; tip.hidden = true; root.append(tip);
  function showTip(evt, title, lines) {
    tip.textContent = '';
    const t = document.createElement('div'); t.className = 't'; t.textContent = title; tip.append(t);
    lines.forEach(l => { const d = document.createElement('div'); d.textContent = l; tip.append(d); });
    tip.hidden = false;
    const rb = root.getBoundingClientRect();
    let x = evt.clientX - rb.left + 12, y = evt.clientY - rb.top + 12;
    const w = tip.offsetWidth, h = tip.offsetHeight;
    if (x + w > rb.width) x = evt.clientX - rb.left - w - 12;
    if (x < 0) x = 0;
    tip.style.left = x + 'px'; tip.style.top = Math.max(0, y - (y + h > rb.height ? h + 24 : 0)) + 'px';
  }
  const hideTip = () => { tip.hidden = true; };

  function ready(el, ids) {
    const st = ids.map(i => dash.data(i).status);
    el.classList.remove('og-failed');
    if (st.every(s => s === 'ok')) { el.classList.remove('dash-skeleton'); return true; }
    el.textContent = '';
    if (st.some(s => s === 'error' || s === 'connect' || s === 'missing' || s === 'declined')) {
      el.classList.remove('dash-skeleton'); el.classList.add('og-failed');
      const s = document.createElement('span'); s.className = 'og-fail'; s.textContent = 'Caricamento non riuscito'; el.append(s);
    } else el.classList.add('dash-skeleton');
    return false;
  }
  const div = (cls, text) => { const d = document.createElement('div'); d.className = cls; if (text != null) d.textContent = text; return d; };
  const cssColor = (c) => { const p = document.createElement('span'); p.style.color = c; root.append(p); const v = getComputedStyle(p).color; p.remove(); return v; };

  function fillMarks() {
    root.querySelectorAll('[data-fill]').forEach(el => {
      const d = dash.data(el.dataset.source);
      if (d.status !== 'ok') { el.textContent = '—'; return; }
      let row;
      if (el.dataset.where) {
        const i = el.dataset.where.indexOf('=');
        const k = el.dataset.where.slice(0, i), v = decodeURIComponent(el.dataset.where.slice(i + 1));
        row = d.data.find(r => String(r[k]) === v);
      } else row = d.data[+(el.dataset.row || 0)];
      const v = row ? row[el.dataset.field] : '';
      el.textContent = (v === '' || v == null) ? '—' : F[el.dataset.fill](v);
    });
  }

  // barre orizzontali in HTML
  function hbars(el, items, { max, fmt, color, extra }) {
    el.textContent = '';
    items.forEach(it => {
      const row = div('og-bar-row');
      const track = div('og-bar-track');
      const bar = div('og-bar'); bar.style.width = (it.value / max * 100) + '%'; bar.style.background = color;
      track.append(bar);
      if (it.max != null) { const m = div('og-bar-max'); m.style.left = `calc(${it.max / max * 100}% - 1px)`; track.append(m); }
      row.append(div('og-bar-label', it.label), track, div('og-bar-val', fmt(it.value)));
      row.addEventListener('pointermove', e => showTip(e, it.label + ' · ' + it.sub, extra(it)));
      row.addEventListener('pointerleave', hideTip);
      el.append(row);
    });
  }

  function drawRoleBars(prof) {
    ['danni', 'boss', 'cure', 'tank'].forEach(m => {
      const el = document.getElementById('b-' + m);
      if (!ready(el, ['profilo'])) return;
      const items = prof.map(r => ({ label: r.giocatore, sub: r.classe, value: +r[m] })).sort((a, b) => b.value - a.value);
      hbars(el, items, { max: 40, fmt: F.pct, color: dash.colors[METRICS[m].color], extra: it => [METRICS[m].label + ': ' + F.pct(it.value)] });
    });
    const el = document.getElementById('b-oro');
    if (!ready(el, ['profilo'])) return;
    const items = prof.map(r => ({ label: r.giocatore, sub: r.classe, value: +r.oro_medio_fine_round, max: +r.oro_max })).sort((a, b) => b.value - a.value);
    hbars(el, items, { max: d3.max(items, d => d.max), fmt: F.int, color: dash.colors[4], extra: it => ['Media a fine round: ' + F.int(it.value), 'Massimo: ' + F.int(it.max)] });
  }

  // ---------- andamento ----------
  function drawTrend(rows) {
    const el = document.getElementById('c-trend');
    if (!ready(el, ['andamento'])) return;
    el.textContent = '';
    const m = state.metric, sel = state.player, meta = METRICS[m];
    const W = Math.max(280, el.clientWidth), H = 300;
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img')
      .attr('aria-label', `${meta.label} cumulati per challenge, ${sel} evidenziato`);
    const byP = d3.group(rows.map(r => ({ p: r.player, c: +r.challenge, v: +r[m] })), d => d.p);
    const ymax = d3.max(rows, r => +r[m]) * 1.08;
    // misura etichetta finale
    const probe = svg.append('text').attr('class', 'og-strong').text(sel + ' 00.0%');
    const endW = Math.min(probe.node().getComputedTextLength() + 10, W * 0.4); probe.remove();
    const yTicks = d3.scaleLinear([0, ymax], [0, 1]).nice().ticks(5);
    const probe2 = svg.append('text').text(meta.fmt(yTicks[yTicks.length - 1]));
    const left = probe2.node().getComputedTextLength() + 10; probe2.remove();
    const mg = { t: 10, r: endW, b: 28, l: left };
    const x = d3.scaleLinear([1, 19], [mg.l, W - mg.r]);
    const y = d3.scaleLinear([0, ymax], [H - mg.b, mg.t]).nice();
    const g = svg.append('g');
    y.ticks(5).forEach(t => {
      g.append('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y(t)).attr('y2', y(t)).attr('stroke', 'var(--cds-chart-grid)').attr('stroke-width', 1);
      g.append('text').attr('x', mg.l - 6).attr('y', y(t) + 4).attr('text-anchor', 'end').text(meta.fmt(t));
    });
    const step = W < 480 ? 3 : 2;
    for (let c = 1; c <= 19; c += step) g.append('text').attr('x', x(c)).attr('y', H - 8).attr('text-anchor', 'middle').text(c);
    g.append('text').attr('x', W - mg.r).attr('y', H - 8).attr('text-anchor', 'end').text('challenge');
    const line = d3.line().x(d => x(d.c)).y(d => y(d.v));
    for (const [p, pts] of byP) if (p !== sel)
      g.append('path').attr('d', line(pts)).attr('fill', 'none').attr('stroke', 'var(--cds-chart-muted)').attr('stroke-width', 1.5).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
    const sp = byP.get(sel) || [];
    const col = dash.colors[meta.color];
    g.append('path').attr('d', line(sp)).attr('fill', 'none').attr('stroke', col).attr('stroke-width', 2.5).attr('stroke-linejoin', 'round').attr('stroke-linecap', 'round');
    const last = sp[sp.length - 1];
    if (last) {
      g.append('circle').attr('cx', x(last.c)).attr('cy', y(last.v)).attr('r', 4).attr('fill', col);
      g.append('text').attr('class', 'og-strong').attr('x', x(last.c) + 8).attr('y', y(last.v) + 4).text(meta.fmt(last.v));
      g.append('text').attr('x', x(last.c) + 8).attr('y', y(last.v) + 18).text(sel.length > 14 ? sel.slice(0, 13) + '…' : sel);
    }
    const rule = g.append('line').attr('y1', mg.t).attr('y2', H - mg.b).attr('stroke', 'var(--cds-chart-reference)').attr('opacity', 0);
    const dot = g.append('circle').attr('r', 5).attr('fill', col).attr('opacity', 0);
    svg.append('rect').attr('x', mg.l).attr('y', 0).attr('width', W - mg.l - mg.r).attr('height', H).attr('fill', 'transparent')
      .on('pointermove', (e) => {
        const [mx] = d3.pointer(e); const c = Math.max(1, Math.min(19, Math.round(x.invert(mx))));
        const pt = sp.find(d => d.c === c); if (!pt) return;
        rule.attr('x1', x(c)).attr('x2', x(c)).attr('opacity', 1);
        dot.attr('cx', x(c)).attr('cy', y(pt.v)).attr('opacity', 1);
        const all = [...byP].map(([p, ps]) => [p, (ps.find(d => d.c === c) || {}).v]).filter(d => d[1] != null).sort((a, b) => b[1] - a[1]);
        const rank = all.findIndex(d => d[0] === sel) + 1;
        showTip(e, `Dopo la challenge ${c}`, [`${sel}: ${meta.fmt(pt.v)} (${rank}° su ${all.length})`, `Primo: ${all[0][0]} ${meta.fmt(all[0][1])}`]);
      })
      .on('pointerleave', () => { rule.attr('opacity', 0); dot.attr('opacity', 0); hideTip(); });
  }

  // ---------- round ----------
  function roundBars(el, rows, field, { color, label, maxFixed, fmtTop }) {
    el.textContent = '';
    const W = Math.max(280, el.clientWidth), H = 240, mg = { t: 18, r: 6, b: 26, l: 34 };
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', label);
    const x = d3.scaleBand(rows.map(r => +r.challenge), [mg.l, W - mg.r]).padding(0.25);
    const vals = rows.map(r => r[field] === '' ? null : +r[field]);
    const y = d3.scaleLinear([0, maxFixed || d3.max(vals) * 1.1], [H - mg.b, mg.t]).nice();
    y.ticks(4).forEach(t => {
      svg.append('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y(t)).attr('y2', y(t)).attr('stroke', 'var(--cds-chart-grid)');
      svg.append('text').attr('x', mg.l - 6).attr('y', y(t) + 4).attr('text-anchor', 'end').text(d3.format(',')(t));
    });
    svg.append('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y(0)).attr('y2', y(0)).attr('stroke', 'var(--cds-chart-axis)');
    const every = W < 420 ? 3 : (W < 640 ? 2 : 1);
    rows.forEach((r, i) => {
      const c = +r.challenge, v = vals[i], bx = x(c), bw = x.bandwidth();
      if (((c - 1) % every === 0 && 20 - c >= every) || c === 20) svg.append('text').attr('x', bx + bw / 2).attr('y', H - 8).attr('text-anchor', 'middle').text(c);
      if (v == null) {
        svg.append('text').attr('x', bx + bw / 2).attr('y', y(0) - 4).attr('text-anchor', 'middle').text(c === 20 ? '✕' : '·');
      } else {
        const h = Math.max(0, y(0) - y(v));
        svg.append('rect').attr('x', bx).attr('y', y(v)).attr('width', bw).attr('height', h + 0.01).attr('rx', Math.min(4, bw / 2)).attr('fill', color(r));
        const top = fmtTop(r); if (top && bw >= 6) svg.append('text').attr('class', 'og-strong').style('font-size', bw < 12 ? '9px' : '11px').attr('x', bx + bw / 2).attr('y', y(v) - 4).attr('text-anchor', 'middle').text(top);
      }
      svg.append('rect').attr('x', bx - x.step() * x.paddingInner() / 2).attr('y', mg.t).attr('width', x.step()).attr('height', H - mg.t - mg.b).attr('fill', 'transparent')
        .on('pointermove', e => showTip(e, `Challenge ${c} · ${r.ondata}`, [
          r.secondi !== '' ? `Durata: ${r.secondi} s` : 'Durata: non disponibile',
          `Voto: ${r.voto || 'non disponibile'}`,
          r.eroi_sotto_20hp !== '' ? `Eroi con HP ≤ 20%: ${r.eroi_sotto_20hp}` : 'Boss finale: sconfitta',
          `APM medio del team: ${r.apm_team}`]))
        .on('pointerleave', hideTip);
    });
  }
  function drawRounds(rows) {
    const e1 = document.getElementById('c-secondi');
    if (ready(e1, ['round'])) roundBars(e1, rows, 'secondi', {
      label: 'Secondi per chiudere ogni challenge',
      color: r => (r.voto === 'E' || r.voto === 'G') ? 'var(--cds-chart-status-critical)' : dash.colors[0],
      fmtTop: r => r.voto && r.voto.length === 1 ? r.voto : '',
    });
    const e2 = document.getElementById('c-hp');
    if (ready(e2, ['round'])) roundBars(e2, rows, 'eroi_sotto_20hp', {
      label: 'Eroi con HP al 20% o meno a fine round', maxFixed: 10,
      color: r => +r.eroi_sotto_20hp >= 4 ? 'var(--cds-chart-status-critical)' : dash.colors[1],
      fmtTop: r => r.eroi_sotto_20hp !== '' && +r.eroi_sotto_20hp > 0 ? r.eroi_sotto_20hp : '',
    });
  }

  // ---------- scatter ----------
  function drawScatter(prof) {
    const el = document.getElementById('c-scatter');
    if (!ready(el, ['profilo'])) return;
    el.textContent = '';
    const W = Math.max(280, el.clientWidth), H = 280, mg = { t: 12, r: 12, b: 34, l: 40 };
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'img').attr('aria-label', 'APM contro quota di danni');
    const x = d3.scaleLinear([0, 100], [mg.l, W - mg.r]);
    const y = d3.scaleLinear([0, 30], [H - mg.b, mg.t]);
    y.ticks(3).forEach(t => {
      svg.append('line').attr('x1', mg.l).attr('x2', W - mg.r).attr('y1', y(t)).attr('y2', y(t)).attr('stroke', 'var(--cds-chart-grid)');
      svg.append('text').attr('x', mg.l - 6).attr('y', y(t) + 4).attr('text-anchor', 'end').text(t + '%');
    });
    x.ticks(5).forEach(t => svg.append('text').attr('x', x(t)).attr('y', H - 16).attr('text-anchor', 'middle').text(t));
    svg.append('text').attr('x', W - mg.r).attr('y', H - 2).attr('text-anchor', 'end').text('APM →');
    svg.append('text').attr('x', mg.l).attr('y', mg.t - 2).text('danni ↑');
    const placed = [];
    const overlaps = (b) => placed.some(p => b.x < p.x + p.w && b.x + b.w > p.x && b.y < p.y + p.h && b.y + b.h > p.y)
      || b.x < mg.l || b.x + b.w > W;
    prof.forEach(r => {
      const cx = x(+r.apm), cy = y(+r.danni);
      svg.append('circle').attr('cx', cx).attr('cy', cy).attr('r', 6).attr('fill', dash.colors[0]).attr('stroke', 'var(--color-panel)').attr('stroke-width', 2);
      placed.push({ x: cx - 7, y: cy - 7, w: 14, h: 14 });
    });
    prof.forEach(r => {
      const cx = x(+r.apm), cy = y(+r.danni);
      const name = r.giocatore.length > 12 ? r.giocatore.slice(0, 11) + '…' : r.giocatore;
      const label = svg.append('text').text(name);
      const w = label.node().getComputedTextLength(), h = 12;
      // prova destra, sinistra, sopra, sotto; tiene la prima posizione libera
      const tries = [[cx + 10, cy + 4, 'start'], [cx - 10, cy + 4, 'end'], [cx, cy - 11, 'middle'], [cx, cy + 19, 'middle'],
        [cx + 10, cy - 8, 'start'], [cx + 10, cy + 16, 'start'], [cx - 10, cy - 8, 'end'], [cx - 10, cy + 16, 'end']];
      const box = ([lx, ly, a]) => ({ x: a === 'start' ? lx : a === 'end' ? lx - w : lx - w / 2, y: ly - h + 2, w, h });
      for (const dy of [-20, 28, -32, 40]) tries.push([cx, cy + dy, 'middle']);
      const area = (b) => placed.reduce((s, p) => s + Math.max(0, Math.min(b.x + b.w, p.x + p.w) - Math.max(b.x, p.x)) * Math.max(0, Math.min(b.y + b.h, p.y + p.h) - Math.max(b.y, p.y)), 0)
        + (b.x < mg.l || b.x + b.w > W || b.y < 0 || b.y + b.h > H - mg.b ? 1e6 : 0);
      const pick = tries.find(t => !overlaps(box(t))) || tries.reduce((best, t) => area(box(t)) < area(box(best)) ? t : best, tries[0]);
      label.attr('x', pick[0]).attr('y', pick[1]).attr('text-anchor', pick[2]);
      placed.push(box(pick));
    });
    prof.forEach(r => {
      const cx = x(+r.apm), cy = y(+r.danni);
      svg.append('circle').attr('cx', cx).attr('cy', cy).attr('r', 14).attr('fill', 'transparent')
        .on('pointermove', e => showTip(e, r.giocatore + ' · ' + r.classe, ['APM: ' + F.dec1(r.apm), 'Danni: ' + F.pct(r.danni), 'Abilità al minuto: ' + F.dec2(r.abilita_min)]))
        .on('pointerleave', hideTip);
    });
  }

  // ---------- heatmap ----------
  function drawHeat(rows) {
    const el = document.getElementById('c-heat');
    if (!ready(el, ['attivita'])) return;
    el.textContent = '';
    const ch = [...new Set(rows.map(r => +r.challenge))].sort((a, b) => a - b);
    el.style.gridTemplateColumns = `minmax(7rem, 9rem) repeat(${ch.length}, minmax(1.2rem, 1fr))`;
    const lo = cssColor('var(--color-panel)'), hi = cssColor(dash.colors[0]);
    const max = d3.max(rows, r => +r.apm);
    const ramp = d3.interpolateRgb(lo, hi);
    document.getElementById('heat-ramp').style.background = `linear-gradient(90deg, ${ramp(0.08)}, ${ramp(1)})`;
    el.append(div('n h', ''));
    ch.forEach(c => el.append(div('h', c)));
    const players = [...new Set(rows.map(r => r.player))];
    players.forEach(p => {
      el.append(div('n', p));
      ch.forEach(c => {
        const r = rows.find(x => x.player === p && +x.challenge === c);
        const cell = div('c'); const v = r ? +r.apm : 0;
        cell.style.background = ramp(0.08 + 0.92 * v / max);
        cell.addEventListener('pointermove', e => showTip(e, `${p} · challenge ${c}`, ['APM: ' + F.dec1(v), 'Abilità lanciate: ' + (r ? r.abilita : 0)]));
        cell.addEventListener('pointerleave', hideTip);
        el.append(cell);
      });
    });
  }

  // ---------- tabelle ----------
  const sortState = { k: 'danni', dir: -1 };
  function drawProfileTable(prof) {
    const t = document.getElementById('t-profilo'); const tb = t.querySelector('tbody');
    tb.textContent = '';
    if (dash.data('profilo').status !== 'ok') return;
    const cols = [...t.querySelectorAll('th')].map(th => th.dataset.field);
    const isNum = k => !['giocatore', 'classe', 'abilita_principale'].includes(k);
    const rows = [...prof].sort((a, b) => {
      const k = sortState.k; const va = isNum(k) ? +a[k] : a[k], vb = isNum(k) ? +b[k] : b[k];
      return (va > vb ? 1 : va < vb ? -1 : 0) * sortState.dir;
    });
    t.querySelectorAll('th').forEach(th => th.setAttribute('aria-sort', th.dataset.field === sortState.k ? (sortState.dir > 0 ? 'ascending' : 'descending') : 'none'));
    rows.forEach(r => {
      const tr = document.createElement('tr');
      cols.forEach(k => {
        const td = document.createElement('td'); if (!isNum(k)) td.className = 'txt';
        td.textContent = ['danni', 'boss', 'cure', 'tank'].includes(k) ? (+r[k]).toFixed(1)
          : k === 'apm' ? F.dec1(r[k]) : k === 'abilita_min' ? F.dec2(r[k]) : isNum(k) ? F.int(r[k]) : r[k];
        tr.append(td);
      });
      tb.append(tr);
    });
  }
  function drawAbilityTable(rows) {
    const t = document.getElementById('t-abilita'); const tb = t.querySelector('tbody');
    tb.textContent = '';
    if (dash.data('abilita').status !== 'ok') return;
    const q = (document.getElementById('ab-search').value || '').toLowerCase();
    [...rows].sort((a, b) => a.player.localeCompare(b.player) || b.usi - a.usi)
      .filter(r => !q || (r.player + ' ' + r.abilita).toLowerCase().includes(q))
      .forEach(r => {
        const tr = document.createElement('tr');
        [r.player, r.abilita, F.int(r.usi)].forEach((v, i) => { const td = document.createElement('td'); if (i < 2) td.className = 'txt'; td.textContent = v; tr.append(td); });
        tb.append(tr);
      });
  }

  // ---------- controlli ----------
  document.querySelectorAll('#metric-seg button').forEach(b => b.addEventListener('click', () => {
    state.metric = b.dataset.m;
    document.querySelectorAll('#metric-seg button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    const d = dash.data('andamento'); if (d.status === 'ok') drawTrend(d.data);
  }));
  const selEl = document.getElementById('player-sel');
  selEl.addEventListener('change', () => { state.player = selEl.value; const d = dash.data('andamento'); if (d.status === 'ok') drawTrend(d.data); });
  document.querySelectorAll('#t-profilo th button').forEach(b => b.addEventListener('click', () => {
    if (sortState.k === b.dataset.k) sortState.dir *= -1; else { sortState.k = b.dataset.k; sortState.dir = ['giocatore', 'classe', 'abilita_principale'].includes(b.dataset.k) ? 1 : -1; }
    const d = dash.data('profilo'); if (d.status === 'ok') drawProfileTable(d.data);
  }));
  document.getElementById('ab-search').addEventListener('input', () => { const d = dash.data('abilita'); if (d.status === 'ok') drawAbilityTable(d.data); });

  let animated = false;
  dash.onData(() => {
    fillMarks();
    const prof = dash.data('profilo'), and = dash.data('andamento'), rnd = dash.data('round'), att = dash.data('attivita'), ab = dash.data('abilita');
    if (and.status === 'ok' && !selEl.options.length) {
      [...new Set(and.data.map(r => r.player))].forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = p; selEl.append(o); });
      selEl.value = state.player;
    }
    drawRoleBars(prof.status === 'ok' ? prof.data : []);
    drawTrend(and.status === 'ok' ? and.data : []);
    drawRounds(rnd.status === 'ok' ? rnd.data : []);
    drawScatter(prof.status === 'ok' ? prof.data : []);
    drawHeat(att.status === 'ok' ? att.data : []);
    drawProfileTable(prof.status === 'ok' ? prof.data : []);
    drawAbilityTable(ab.status === 'ok' ? ab.data : []);
    if (!animated && prof.status === 'ok') {
      animated = true;
      const named = document.getElementById(location.hash.slice(1));
      if (named) { named.scrollIntoView(); dash.setLink(named.id); }
    }
  });
})();


