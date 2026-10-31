"""Genera dashboard/index.html: il report apribile con doppio click, senza la dashboard online.

Usa gli stessi file della dashboard online (dashboard/artifact/index.html e app.js) e i CSV
di data_analysis/, incorporati nella pagina. Al posto del runtime della dashboard fornisce
un piccolo `dash` compatibile (data, calc, onData, colors) e i token di stile.
Serve internet solo per caricare d3 da cdnjs.
Uso: python build_standalone.py
"""
import csv, json

DATASETS = {'profilo': 'profilo_giocatori.csv', 'andamento': 'andamento_round.csv', 'round': 'round.csv',
            'attivita': 'attivita_round.csv', 'abilita': 'abilita.csv'}

data = {}
for k, f in DATASETS.items():
    with open(f'data_analysis/{f}', encoding='utf-8') as fh:
        r = csv.reader(fh)
        cols = next(r)
        data[k] = {'columns': cols, 'rows': [dict(zip(cols, row)) for row in r]}

fragment = open('dashboard/artifact/index.html', encoding='utf-8-sig').read()
fragment = fragment.replace('<script src="app.js"></script>', '')
app = open('dashboard/artifact/app.js', encoding='utf-8').read()

TOKENS = """
:root {
  color-scheme: light;
  --font-anthropic-sans: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
  --font-anthropic-serif: Georgia, "Times New Roman", serif;
  --color-bg: #f7f7f4; --color-panel: #ffffff; --color-fg: #1b1b18; --color-fg-muted: #6b6a64;
  --color-border-line: #e2e1da; --color-bad: #d03b3b; --color-ok: #0a7d0a; --color-warn: #b77700;
  --cds-chart-grid: #ecebe5; --cds-chart-axis: #c3c2b7; --cds-chart-reference: #898781;
  --cds-chart-muted: #d3d2ca; --cds-chart-status-critical: #d03b3b;
  --cds-surface-popover: #ffffff; --cds-border: #dcdbd3; --cds-text-secondary: #52514e;
  --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.12);
  --og-c1: #2a78d6; --og-c2: #eb6834; --og-c3: #1baf7a; --og-c4: #4a3aa7;
  --og-c5: #c98500; --og-c6: #e87ba4; --og-c7: #008300; --og-c8: #e34948;
  --cds-gap-xs: 4px; --cds-gap-sm: 8px; --cds-gap-md: 16px; --cds-gap-lg: 24px; --cds-gap-xl: 40px;
  --cds-pad-xs: 4px; --cds-pad-sm: 8px; --cds-pad-md: 12px; --cds-pad-lg: 18px; --cds-pad-xl: 28px;
  --cds-radius: 8px;
  --cds-font-size-caption: 12.5px; --cds-font-size-body: 15px; --cds-font-size-heading: 19px; --cds-font-size-title: 30px;
  --cds-font-weight-medium: 600; --cds-dur-slow: .3s;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --color-bg: #121211; --color-panel: #1c1c1a; --color-fg: #f2f1ec; --color-fg-muted: #a3a29b;
    --color-border-line: #33332f; --cds-chart-grid: #2a2a27; --cds-chart-axis: #45453f;
    --cds-chart-reference: #8a8983; --cds-chart-muted: #4a4a45;
    --cds-surface-popover: #262624; --cds-border: #3a3a36; --cds-text-secondary: #c3c2b7;
    --cds-shadow-popover: 0 4px 16px rgba(0,0,0,.5);
    --og-c1: #3987e5; --og-c2: #d95926; --og-c3: #199e70; --og-c4: #9085e9;
    --og-c5: #c98500; --og-c6: #d55181; --og-c7: #2fa52f; --og-c8: #e66767;
  }
}
html, body { margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 15px; }
#dash-root { padding: 24px clamp(16px, 4vw, 48px) 48px; }
#dash-root .dash-skeleton { min-height: 1em; background: var(--color-border-line); border-radius: 6px; }
"""

SHIM = """
(function () {
  const RAW = window.__OG_DATA;
  const calcs = {}, listeners = [];
  const resolve = (id) => {
    if (RAW[id]) return { status: 'ok', data: RAW[id].rows, rows: RAW[id].rows, columns: RAW[id].columns, refreshing: false, meta: [] };
    const c = calcs[id];
    if (!c) return { status: 'missing', data: [], rows: [], columns: [], meta: [] };
    if (!c.cache) {
      try { c.cache = { status: 'ok', data: c.fn(...c.inputs.map(i => resolve(i).data)) }; }
      catch (e) { console.error('calc', id, e); c.cache = { status: 'error', data: [], message: String(e) }; }
    }
    const d = c.cache.data;
    return { status: c.cache.status, data: d, rows: Array.isArray(d) ? d : [], columns: [], meta: [] };
  };
  let t;
  window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => listeners.forEach(f => f()), 150); });
  window.dash = {
    data: resolve,
    calc: (id, spec) => { calcs[id] = { ...spec }; },
    loader: () => {},
    onData: (fn) => { listeners.push(fn); fn(); },
    colors: ['--og-c1', '--og-c2', '--og-c3', '--og-c4', '--og-c5', '--og-c6', '--og-c7', '--og-c8'].map(v => `var(${v})`),
    refresh: () => {}, params: () => ({}), setParams: () => {}, resetParams: () => {}, setLink: () => {},
  };
})();
"""

page = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Orc Gladiators: analisi partita</title>
<style>{TOKENS}</style>
<script>window.__OG_DATA = {json.dumps(data, ensure_ascii=False)};</script>
<script>{SHIM}</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
</head>
<body>
<div id="dash-root">
{fragment}
</div>
<script>
if (!window.d3) {{
  document.querySelector('#dash-root .og-head').insertAdjacentHTML('beforeend',
    '<p style="color:var(--color-bad)">Grafici non disponibili: serve una connessione a internet per caricare la libreria d3.</p>');
}} else {{
{app}
}}
</script>
</body>
</html>
"""
open('dashboard/index.html', 'w', encoding='utf-8').write(page)
print('scritto dashboard/index.html', len(page.encode()), 'byte')
