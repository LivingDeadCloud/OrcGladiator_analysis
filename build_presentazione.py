"""Genera presentazione/presentazione.html: la presentazione in un unico file, apribile con doppio click.

Legge presentazione/sorgente/deck.json (ordine delle slide e font) e le slide in presentazione/sorgente/slides/.
Ogni slide e' un canvas 1920x1080 ridimensionato alla larghezza della finestra; le note per chi presenta
(il tag <aside>) compaiono sotto ogni slide. Serve internet solo per i font Google.
Uso: python build_presentazione.py
La versione online (modificabile, esportabile in PDF/PowerPoint) e' su claude.ai.
"""
import html, json, os, re

SRC = os.path.join('presentazione', 'sorgente')
OUT = os.path.join('presentazione', 'presentazione.html')

deck = json.load(open(os.path.join(SRC, 'deck.json'), encoding='utf-8'))
fonts = '\n'.join(f'<link rel="stylesheet" href="{html.escape(f["href"])}">'
                  for f in deck['faces'].values() if 'href' in f)

blocks = []
for i, sid in enumerate(deck['order'], 1):
    s = open(os.path.join(SRC, 'slides', sid + '.html'), encoding='utf-8').read().strip()
    m = re.search(r'<aside>(.*?)</aside>', s, re.S)
    note = m.group(1).strip() if m else ''
    s = re.sub(r'<aside>.*?</aside>', '', s, flags=re.S)
    blocks.append(f'''<div class="slide-wrap" id="s{i}">
<div class="frame"><div class="canvas">{s}</div></div>
<div class="meta"><span>{i} / {len(deck["order"])}</span>{"<details><summary>Note per chi presenta</summary><p>" + html.escape(note) + "</p></details>" if note else ""}</div>
</div>''')

page = f'''<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(deck["title"])}</title>
{fonts}
<style>
body {{ margin:0; background:#2b2622; font-family:'Rubik', Arial, sans-serif; color:#e6dfd3; }}
main {{ max-width:1600px; margin:0 auto; padding:24px 16px 64px; }}
.slide-wrap {{ margin-bottom:40px; }}
.frame {{ position:relative; width:100%; aspect-ratio:16/9; overflow:hidden; border-radius:8px; box-shadow:0 8px 32px rgba(0,0,0,.4); }}
.canvas {{ position:absolute; left:0; top:0; width:1920px; height:1080px; transform-origin:0 0; }}
.canvas section {{ width:1920px; height:1080px; box-sizing:border-box; position:relative; overflow:hidden; }}
.canvas h1, .canvas h2, .canvas h3, .canvas p, .canvas ul, .canvas ol {{ margin:0; }}
.canvas ul, .canvas ol {{ padding-left:1.3em; }}
.canvas div {{ box-sizing:border-box; }}
.canvas table {{ border-collapse:collapse; width:100%; }}
.canvas th, .canvas td {{ padding:.35em .6em; border-bottom:1px solid #d3c8b8; vertical-align:top; }}
.canvas th {{ font-weight:600; }}
.meta {{ display:flex; gap:24px; align-items:baseline; padding:10px 4px; font-size:15px; color:#b8ada0; }}
.meta details {{ flex:1; }} .meta summary {{ cursor:pointer; }} .meta p {{ margin:8px 0 0; line-height:1.5; color:#e6dfd3; }}
</style>
</head>
<body>
<main>
{chr(10).join(blocks)}
</main>
<script>
function fit() {{
  document.querySelectorAll('.frame').forEach(f => {{
    f.querySelector('.canvas').style.transform = 'scale(' + (f.clientWidth / 1920) + ')';
  }});
}}
window.addEventListener('resize', fit); fit();
</script>
</body>
</html>
'''
open(OUT, 'w', encoding='utf-8').write(page)
print('Scritto', OUT, '-', len(deck['order']), 'slide')
