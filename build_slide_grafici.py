"""Rigenera le slide con i grafici per classe, leggendo i numeri dai CSV delle analisi.

Uso (dalla cartella principale, dopo le analisi e prima di build_presentazione.py):
    python build_slide_grafici.py
Scrive in presentazione/sorgente/slides/: metodo, q1, colpi (nuova), q2, q4, q5, q7; colora i ruoli nella tabella di q3;
aggiunge 'colpi' all'ordine in deck.json e rinumera i pie' di pagina di tutte le slide.

Regole grafiche:
- colore per ruolo (barre e nomi): Healer verde, Tank viola, DPS distanza arancione, DPS mischia blu, Support grigio;
- nei grafici che confrontano le classi con la media del team il valore e' chiuso in un rettangolo
  VERDE se e' meglio della media e ROSSO se e' peggio (il colore della barra resta quello del ruolo);
- icona della classe al posto del nome quando ci sono tutte le icone (presentazione/sorgente/icone/, da estrai_icone.py);
  altrimenti il nome della classe, colorato per ruolo.
"""
import csv, json, os, re

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'presentazione', 'sorgente')
SLIDES = os.path.join(SRC, 'slides')
ICONE = os.path.join(SRC, 'icone')
V2 = os.path.join(ROOT, 'data_analysis', 'v2')

COLORE_RUOLO = {'Tank': '#7a4fb0', 'Healer': '#2f8a4c', 'Support': '#8a837b',
                'DPS mischia': '#2f6da3', 'DPS distanza': '#d9622b'}
CHIARO_RUOLO = {'Tank': '#cdb9e6', 'Healer': '#b5dcc0', 'Support': '#d6d1cb',
                'DPS mischia': '#b4cde6', 'DPS distanza': '#f3c3a6'}
ORDINE_RUOLI = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']
MEGLIO = ('#1f7a3a', '#dcefdf')     # bordo, sfondo
PEGGIO = ('#b3261e', '#f7dedb')

FONT = "font-family:'Rubik', Arial, sans-serif"
OSW = "font-family:'Oswald', Arial, sans-serif"
SEZ = (f"background:#f3eee4;color:#2a2522;{FONT};padding:128px 128px 160px;display:flex;flex-direction:column")
TESTO = 'font-size:26px;line-height:1.4;color:#4a4440'


def load(*p):
    with open(os.path.join(V2, *p), encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


ROLES = list(csv.DictReader(open(os.path.join(ROOT, 'data_map', 'class_roles.csv'), encoding='utf-8')))
RUOLO = {r['classe']: r['ruolo'] for r in ROLES}
CLASSI = sorted(RUOLO, key=lambda c: (ORDINE_RUOLI.index(RUOLO[c]), c))


def slug(c):
    return c.lower().replace(' ', '_')


ICON_MODE = all(os.path.exists(os.path.join(ICONE, slug(c) + '.png')) for c in CLASSI)


def it(x, dec=1):
    s = f'{x:.{dec}f}'.replace('.', ',')
    return s


def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def etichetta(classe, larghezza, testo=None, piccola=False):
    """Icona della classe (se ci sono tutte) oppure nome colorato per ruolo."""
    col = COLORE_RUOLO[RUOLO[classe]]
    testo = testo or classe
    if ICON_MODE:
        size = 32 if piccola else 40
        img = (f'<img src="icone/{slug(classe)}.png" alt="{esc(classe)}" '
               f'style="width:{size}px;height:{size}px;object-fit:contain;border-radius:4px">')
        if testo != classe:   # evocazione: icona del padrone + nome dell'evocazione
            return (f'<div style="width:{larghezza}px;display:flex;flex-direction:row;align-items:center;justify-content:flex-end;gap:10px">'
                    f'<p style="font-size:24px;color:{col}">{esc(testo)}</p>{img}</div>')
        return f'<div style="width:{larghezza}px;display:flex;flex-direction:row;justify-content:flex-end">{img}</div>'
    return f'<p style="width:{larghezza}px;font-size:24px;text-align:right;color:{col};font-weight:500;white-space:nowrap">{esc(testo)}</p>'


def valore(testo, giudizio=None, grassetto=False):
    t = f'<b>{testo}</b>' if grassetto else testo
    if giudizio is None:
        return f'<p style="font-size:24px">{t}</p>'
    bordo, fondo = MEGLIO if giudizio == 'meglio' else PEGGIO
    return (f'<p style="font-size:24px;padding:0px 10px;border:3px solid {bordo};background:{fondo};border-radius:6px">{t}</p>')


def barra(px, ruolo, altezza=28, evocazione=False):
    px = max(4, round(px))
    col = COLORE_RUOLO[ruolo]
    if evocazione:
        fondo = f'repeating-linear-gradient(135deg, {col} 0px, {col} 6px, {CHIARO_RUOLO[ruolo]} 6px, {CHIARO_RUOLO[ruolo]} 12px)'
        return f'<div style="width:{px}px;height:{altezza}px;background:{fondo};border-radius:4px"></div>'
    return f'<div style="width:{px}px;height:{altezza}px;background:{col};border-radius:4px"></div>'


def riga(classe, val, scala, testo_val, larghezza_et, giudizio=None, altezza=28, grassetto=False, testo_et=None, evocazione=False):
    return ('<div style="display:flex;flex-direction:row;align-items:center;gap:16px;white-space:nowrap">'
            + etichetta(classe, larghezza_et, testo_et, piccola=evocazione)
            + barra(val * scala, RUOLO[classe], altezza, evocazione)
            + valore(testo_val, giudizio, grassetto) + '</div>')


def giudizio(v, media, meglio_se_basso):
    if abs(v - media) < 1e-9:
        return None
    sotto = v < media
    return 'meglio' if sotto == meglio_se_basso else 'peggio'


def legenda_media():
    chip = lambda c: f'<span style="color:{c[0]};font-weight:600">▢</span>'  # noqa: E731
    return (f'<p style="font-size:24px;color:#4a4440">Valore nel rettangolo <span style="color:{MEGLIO[0]};font-weight:600">verde</span>: '
            f'meglio della media del team · <span style="color:{PEGGIO[0]};font-weight:600">rosso</span>: peggio</p>')


def legenda_ruoli():
    pezzi = ''.join(f'<span style="color:{COLORE_RUOLO[r]};font-weight:600">■ {r}</span>  ' for r in ORDINE_RUOLI)
    return f'<p style="font-size:24px;color:#4a4440">{pezzi}</p>'


def kicker(t):
    return f'<p style="font-size:24px;color:#a4471a;letter-spacing:3px;text-transform:uppercase">{t}</p>'


def titolo(t):
    return f'<h2 style="{OSW};font-size:64px;font-weight:500;line-height:1.1;color:#1c1917">{t}</h2>'


def h3(t):
    return f'<h3 style="font-size:28px;font-weight:600;color:#1c1917">{t}</h3>'


def piede(t):
    return f'<p style="position:absolute;left:128px;bottom:64px;width:1664px;font-size:24px;color:#6b625b">{t} · 0</p>'


def nota(sid):
    """Note per chi presenta gia' presenti nella slide (se c'e')."""
    p = os.path.join(SLIDES, sid + '.html')
    if not os.path.exists(p):
        return ''
    m = re.search(r'<aside>.*?</aside>', open(p, encoding='utf-8').read(), re.S)
    return m.group(0) if m else ''


def scrivi(sid, gap, corpo, aside):
    html = f'<section id="{sid}" data-transition="fade" style="{SEZ};gap:{gap}px">\n{corpo}\n{aside}\n</section>\n'
    open(os.path.join(SLIDES, sid + '.html'), 'w', encoding='utf-8').write(html)


LW = 64 if ICON_MODE else 250        # larghezza etichetta nei grafici per classe

# ---------------------------------------------------------------- dati
scheda = {r['classe']: r for r in load('aggregato', 'scheda_classi.csv')}
ruoli = {r['ruolo']: r for r in load('classi_ruoli', 'profilo_ruoli.csv')}
colpi = load('colpi', 'colpi_finali_dopo_challenge_19.csv')
verif = load('colpi', 'verifiche_modello.csv')
giud4 = {r['classe']: r for r in load('domande', '04_uso_abilita_tempi_morti', 'giudizio_classe.csv')}
pozioni = {r['classe']: r for r in load('domande', '02_acquisto_oggetti', 'uso_oggetti_attivabili.csv')
           if 'Potion' in r['oggetto']}
morti = {r['classe']: r for r in load('domande', '07_morti', 'morti_per_classe.csv')}
morti_ruolo = load('domande', '07_morti', 'morti_per_ruolo.csv')
f = float


# ---------------------------------------------------------------- metodo
def slide_metodo():
    righe = []
    for r in ORDINE_RUOLI:
        cl = [c for c in CLASSI if RUOLO[c] == r]
        if ICON_MODE:
            cls = '  '.join(f'<img src="icone/{slug(c)}.png" alt="{esc(c)}" style="width:32px;height:32px;border-radius:4px"> {esc(c)}' for c in cl)
        else:
            cls = ', '.join(cl)
        righe.append(f'<tr><td><span style="color:{COLORE_RUOLO[r]};font-weight:600">■ {r}</span></td><td>{cls}</td></tr>')
    card = lambda t, d: (f'<div style="background:#fbf8f2;border:1px solid #ddd3c4;border-radius:12px;padding:28px;display:flex;flex-direction:column;gap:8px">'  # noqa: E731
                         f'<h3 style="font-size:32px;font-weight:600;color:#1c1917">{t}</h3><p style="{TESTO}">{d}</p></div>')
    corpo = '\n'.join([
        kicker('Come leggere i dati'), titolo('Tre fonti, una sola partita'),
        '<div style="display:flex;flex-direction:row;gap:64px;flex:1">',
        '<div style="flex:1;display:flex;flex-direction:column;gap:20px">',
        card('Replay', '60.156 comandi dei giocatori. Non contiene danni, morti, oro né posizioni reali.'),
        card('Screenshot della multiboard', '20 momenti: quote cumulative di danni, cure e <b>colpi presi</b> (non danni subiti), HP, mana e oro.'),
        card('Codice della mappa', 'Regole di oro, cure, colpi, morti, evocazioni e composizione delle wave.'),
        '</div>',
        '<div style="flex:1;display:flex;flex-direction:column;gap:20px">',
        h3('Ruoli e colori usati nei grafici'),
        '<table style="font-size:26px;color:#2a2522">',
        '<tr><th style="width:34%;text-align:left">Ruolo</th><th style="width:66%;text-align:left">Classi</th></tr>',
        *righe, '</table>',
        f'<p style="{TESTO}">Un giocatore per classe: l’effetto della classe e quello di chi la gioca non si separano. '
        'Ogni numero è <b>misurato</b> o <b>stimato</b>, e lo diciamo.</p>',
        '</div>', '</div>',
        piede('Fonti: replay del 15/03/2026, 23 screenshot, Orc Gladiators Revenge 1.29fc.w3x')])
    aside = ('<aside>Il replay registra solo i comandi. Danni, cure e colpi presi vengono dagli screenshot della multiboard, '
             'come quote del totale del team. Attenzione: la colonna "tank" della multiboard conta i colpi, non i danni, e include '
             'i colpi presi dalle unità evocate. Le regole del gioco sono lette direttamente dal codice della mappa. '
             'Colori: Tank viola, Healer verde, Support grigio, DPS mischia blu, DPS distanza arancione.</aside>')
    scrivi('metodo', 36, corpo, aside)


# ---------------------------------------------------------------- q1
def slide_q1():
    sc = 14
    sx, dx = [], []
    top_d = max(CLASSI, key=lambda c: f(scheda[c]['quota_danni']))
    top_c = max(CLASSI, key=lambda c: f(scheda[c]['quota_colpi_eroe']))
    for c in CLASSI:
        d = f(scheda[c]['quota_danni']); e = f(scheda[c]['quota_colpi_eroe'])
        sx.append(riga(c, d, sc, it(d), LW, grassetto=c == top_d))
        dx.append(riga(c, e, sc, it(e), LW, grassetto=c == top_c))
    t, dm = f(ruoli['Tank']['quota_colpi_eroe']), f(ruoli['DPS mischia']['quota_colpi_eroe'])
    ev = sum(f(scheda[c]['quota_colpi_evocazioni']) for c in CLASSI)
    corpo = '\n'.join([
        kicker('1 · La scelta delle classi è ottimale?'),
        titolo('Il tank lo fanno i DPS mischia, i danni li fa Claws'),
        '<div style="display:flex;flex-direction:row;gap:64px">',
        '<div style="flex:1;display:flex;flex-direction:column;gap:12px">', h3('Quota dei danni del team (%)'), *sx, '</div>',
        '<div style="flex:1;display:flex;flex-direction:column;gap:12px">', h3('Quota dei colpi presi dall’eroe (%)'), *dx, '</div>',
        '</div>',
        f'<p style="{TESTO}">Gli eroi Tank prendono il {it(t)}% dei colpi, gli eroi DPS mischia il {it(dm)}%. '
        f'Il {it(ev, 0)}% va alle unità evocate (slide seguente). Delle 16 classi della mappa ne sono state giocate 10.</p>',
        legenda_ruoli(),
        piede('Danni misurati; colpi dell’eroe stimati togliendo le evocazioni. Multiboard dopo la challenge 19')])
    aside = ('<aside>Verdetto: non determinabile se ottimale, adeguata in parte. Tutti i ruoli sono coperti, ma i ruoli non sono '
             'stati svolti come previsto. Double Blade è il vero tank: anche togliendo i colpi presi dalle evocazioni, gli eroi '
             'Double Blade e Claws prendono più colpi dei due Tank. Claws regge da sola un quarto dei danni. Ipotesi da provare: '
             'un DPS mischia puro (Katana o Great Axe) al posto di un DPS mischia che fa pochi danni.</aside>')
    scrivi('q1', 28, corpo, aside)


# ---------------------------------------------------------------- colpi (nuova)
def slide_colpi():
    voci = sorted(colpi, key=lambda r: -f(r['colpi_quota_centrale']))
    sc = 16
    righe = []
    for r in voci:
        c = r['classe']; v = f(r['colpi_quota_centrale'])
        lo, hi = f(r['colpi_quota_min']), f(r['colpi_quota_max'])
        ev = r['tipo'] == 'evocazione'
        txt = it(v)
        if hi - lo >= 0.5:
            txt += f' <span style="color:#6b625b">({it(lo, 0)}–{it(hi, 0)})</span>'
        nome = r['voce'].split(' (')[0] if ev else None
        righe.append(riga(c, v, sc, txt, (LW + 150) if ICON_MODE else 330, altezza=22,
                          testo_et=nome + (' · ' + c if not ICON_MODE else '') if ev else None, evocazione=ev))
    ev_tot = sum(f(r['colpi_quota_centrale']) for r in colpi if r['tipo'] == 'evocazione')
    dett = ' · '.join(f"{r['voce'].split(' (')[0].lower()} {it(f(r['colpi_quota_centrale']))}"
                      for r in sorted(colpi, key=lambda r: -f(r['colpi_quota_centrale'])) if r['tipo'] == 'evocazione')
    rb = verif[0]['valore_osservato']; m = re.search(r'differenza ([+-][\d.]+)', rb)
    rb_oss = it(float(m.group(1))) if m else rb
    rb_prev = it(float(re.search(r'([\d.]+)', verif[0]['previsto_dal_modello_centrale']).group(1)))
    cw = re.search(r'pendenza ([+-][\d.]+)', verif[1]['valore_osservato']).group(1)
    card = lambda t, d, scuro=False: (  # noqa: E731
        f'<div style="background:{"#1c1917" if scuro else "#fbf8f2"};{"" if scuro else "border:1px solid #ddd3c4;"}border-radius:12px;padding:22px 26px;display:flex;flex-direction:column;gap:6px">'
        + (f'<p style="{OSW};font-size:64px;font-weight:600;color:#e8894f;line-height:1.05">{t}</p>' if scuro else
           f'<h3 style="font-size:28px;font-weight:600;color:#1c1917">{t}</h3>')
        + f'<p style="font-size:24px;line-height:1.35;color:{"#e6dfd3" if scuro else "#4a4440"}">{d}</p></div>')
    corpo = '\n'.join([
        kicker('1 · Approfondimento: chi prende i colpi'),
        titolo('La multiboard conta i colpi, non i danni'),
        '<div style="display:flex;flex-direction:row;gap:56px">',
        '<div style="flex:1;display:flex;flex-direction:column;gap:5px">',
        h3('Quota dei colpi presi dal team (%): eroi ed evocazioni'), *righe,
        '<p style="font-size:24px;color:#4a4440">Barre a righe: unità evocate. Tra parentesi la forbice della stima.</p>',
        '</div>',
        '<div style="width:600px;display:flex;flex-direction:column;gap:18px">',
        card(f'{it(ev_tot, 0)}%', f'dei colpi va alle unità evocate: {dett}', scuro=True),
        card('Un colpo vale 1', 'da 5 o da 500 HP. Il danno ricevuto in HP la mappa non lo registra: «tanti colpi, pochi danni» non si può verificare.'),
        card('Due verifiche', f'Runeblade col compagno: +{rb_oss.lstrip("+")} punti di colpi (previsti {rb_prev}). Claws: {it(float(cw))} punti per lupo in campo.'),
        '</div>', '</div>',
        piede('Colpi misurati per giocatore; scorporo eroe/evocazioni stimato da replay e codice della mappa')])
    aside = ('<aside>La colonna "tank" della multiboard non misura il danno subito: ogni colpo ricevuto vale 1, qualunque sia il danno, '
             'e i colpi presi dalle unità evocate vanno al loro padrone. Abbiamo stimato quanti colpi hanno preso lupi, Treant, '
             'elementali, torre, portali e compagno, contando quante evocazioni erano in campo e per quanto tempo. Anche togliendole, '
             'Double Blade e Claws restano gli eroi più colpiti; i due Tank sono appaiati intorno al 13%. Il dubbio "i Tank prendono '
             'pochi danni perché hanno tanta armatura" non si applica: qui si contano colpi, non danni.</aside>')
    scrivi('colpi', 28, corpo, aside)


# ---------------------------------------------------------------- q2
def slide_q2():
    vals = {c: f(pozioni[c]['uso_pct_del_max']) for c in pozioni}
    media = sum(vals.values()) / len(vals)
    righe = [riga(c, v, 6, it(v, 0), LW, giudizio(v, media, False), altezza=28)
             for c, v in sorted(vals.items(), key=lambda x: -x[1])]
    card = lambda n, d: (f'<div style="background:#fbf8f2;border:1px solid #ddd3c4;border-radius:12px;padding:24px 28px;display:flex;flex-direction:column;gap:4px">'  # noqa: E731
                         f'<p style="{OSW};font-size:64px;font-weight:600;color:#a4471a;line-height:1.1">{n}</p><p style="{TESTO.replace("1.4", "1.35")}">{d}</p></div>')
    corpo = '\n'.join([
        kicker('2 · L’acquisto degli oggetti è ottimale?'),
        titolo('Build coerenti col ruolo, ma risorse lasciate ferme'),
        '<div style="display:flex;flex-direction:row;gap:64px">',
        '<div style="width:600px;display:flex;flex-direction:column;gap:20px">',
        card('2 su 6', 'punti talento spesi dal Druid Staff; quattro classi lasciano fermi i punti per 3–4 challenge'),
        card('0 attivazioni', 'di Warrior’s Spirit (1.250 oro) e del taunt del Defender’s Buckler'),
        card('8 su 10', 'classi con la Wizard’s Potion, che dà solo mana: anche i Tank'),
        '</div>',
        '<div style="flex:1;display:flex;flex-direction:column;gap:10px">',
        h3(f'Uso della pozione rispetto al massimo possibile in combattimento (%) · media {it(media, 0)}'), *righe,
        legenda_media(),
        '</div>', '</div>',
        piede('Misurato: ordini di acquisto e d’uso dal replay; oggetto nello slot stimato')])
    scrivi('q2', 36, corpo, nota('q2'))


# ---------------------------------------------------------------- q4
def slide_q4():
    rit = {c: f(giud4[c]['ritardo_mediano_rotazione_s']) for c in CLASSI}
    pau = {c: f(giud4[c]['pct_tempo_in_pause_oltre_10s']) for c in CLASSI}
    mr, mp = sum(rit.values()) / len(rit), sum(pau.values()) / len(pau)
    ordine = sorted(CLASSI, key=lambda c: rit[c])
    sx = [riga(c, rit[c], 22, it(rit[c]), LW, giudizio(rit[c], mr, True)) for c in ordine]
    dx = [riga(c, pau[c], 7, it(pau[c], 0), LW, giudizio(pau[c], mp, True), grassetto=pau[c] == max(pau.values())) for c in ordine]
    corpo = '\n'.join([
        kicker('4 · Le abilità sono usate bene?'),
        titolo('Le abilità restano pronte troppo a lungo'),
        '<div style="display:flex;flex-direction:row;gap:64px">',
        '<div style="flex:1;display:flex;flex-direction:column;gap:12px">',
        h3(f'Attesa mediana tra «pronta» e riuso (s) · media {it(mr)}'), *sx, '</div>',
        '<div style="flex:1;display:flex;flex-direction:column;gap:12px">',
        h3(f'Tempo in pause oltre 10 s senza comandi (%) · media {it(mp, 0)}'), *dx, '</div>',
        '</div>',
        legenda_media(),
        f'<p style="{TESTO}">Mai usate: Demonic Circle (Double Blade) ed Entangle (Druid Staff). Le pause includono anche il tempo da morti.</p>',
        piede('Stimato: ordini del replay e cooldown della mappa, abilità di rotazione')])
    scrivi('q4', 24, corpo, nota('q4'))


# ---------------------------------------------------------------- q5
def slide_q5():
    old = open(os.path.join(SLIDES, 'q5.html'), encoding='utf-8').read()
    # ricolora le barre per ruolo (le etichette sono i nomi dei ruoli)
    def ricolora(m):
        ruolo = m.group(2)
        return (f'{m.group(1)}<p style="width:200px;font-size:24px;text-align:right;color:{COLORE_RUOLO[ruolo]};font-weight:500">{ruolo}</p>'
                f'<div style="width:{m.group(3)}px;height:36px;background:{COLORE_RUOLO[ruolo]};border-radius:4px"></div>')
    new = re.sub(r'(<div style="display:flex;flex-direction:row;align-items:center;gap:16px">)<p style="width:200px;font-size:24px;text-align:right[^"]*">'
                 r'(Tank|Healer|Support|DPS mischia|DPS distanza)</p><div style="width:(\d+)px;height:36px;background:#[0-9a-f]{6};border-radius:4px"></div>',
                 ricolora, old)
    assert new.count('height:36px') == 5
    open(os.path.join(SLIDES, 'q5.html'), 'w', encoding='utf-8').write(new)


# ---------------------------------------------------------------- q7
def slide_q7():
    v = {c: int(morti[c]['morti_alta_piu_media']) for c in CLASSI}
    media = f(next(iter(morti.values()))['media_team_morti'])
    ordine = sorted(CLASSI, key=lambda c: (-v[c], c))
    righe = []
    for c in ordine:
        t = str(v[c])
        if c == ordine[0]:
            t += f" · ×{it(f(morti[c]['rapporto_su_media_team']))}"
        righe.append(riga(c, v[c], 70, t, LW, giudizio(v[c], media, True), grassetto=c == ordine[0]))
    tab = ''.join(f'<tr><td><span style="color:{COLORE_RUOLO[r["ruolo"]]};font-weight:600">■ {r["ruolo"]}</span></td>'
                  f'<td style="text-align:right">{it(f(r["morti_per_classe"]))}</td></tr>'
                  for r in sorted(morti_ruolo, key=lambda r: -f(r['morti_per_classe'])))
    corpo = '\n'.join([
        kicker('7 · Ci sono giocatori che muoiono troppo?'),
        titolo('Il Bow muore più del doppio della media'),
        '<div style="display:flex;flex-direction:row;gap:64px">',
        '<div style="flex:1;display:flex;flex-direction:column;gap:12px">',
        h3(f'Morti stimate nelle challenge 1–19 (media del team: {it(media)})'), *righe, legenda_media(), '</div>',
        '<div style="width:560px;display:flex;flex-direction:column;gap:20px">',
        h3('Morti medie per classe, per ruolo'),
        '<table style="font-size:26px;color:#2a2522">',
        '<tr><th style="width:62%;text-align:left">Ruolo</th><th style="width:38%;text-align:right">Morti</th></tr>', tab, '</table>',
        '<div style="background:#1c1917;border-radius:12px;padding:24px 28px;display:flex;flex-direction:column;gap:6px">',
        f'<p style="{OSW};font-size:56px;font-weight:600;color:#e8894f;line-height:1.1">13 su 23</p>',
        '<p style="font-size:26px;line-height:1.35;color:#e6dfd3">attivazioni della Pietra Ancestrale andate a vuoto: troppo presto o troppo ravvicinate</p>',
        '</div>', '</div>', '</div>',
        piede('Stimato: il replay non registra le morti; conteggi minimi da screenshot, silenzi e regole della mappa')])
    scrivi('q7', 32, corpo, nota('q7'))


# ---------------------------------------------------------------- q3: ruoli colorati nella tabella
def slide_q3():
    p = os.path.join(SLIDES, 'q3.html')
    s = open(p, encoding='utf-8').read()
    s = re.sub(r'<span style="color:#[0-9a-f]{6};font-weight:600">([^<]*)</span>', r'\1', s)   # idempotente
    def col(m):
        parti = [x.strip() for x in m.group(1).split(',')]
        return '<tr><td>' + ', '.join(f'<span style="color:{COLORE_RUOLO[x]};font-weight:600">{x}</span>' for x in parti) + '</td>'
    s = re.sub(r'<tr><td>((?:Tank|Healer|Support|DPS mischia|DPS distanza)(?:, (?:Tank|Healer|Support|DPS mischia|DPS distanza))*)</td>', col, s)
    open(p, 'w', encoding='utf-8').write(s)


# ---------------------------------------------------------------- ordine e numeri di pagina
def deck_e_numeri():
    pd = os.path.join(SRC, 'deck.json')
    deck = json.load(open(pd, encoding='utf-8'))
    if 'colpi' not in deck['order']:
        deck['order'].insert(deck['order'].index('q1') + 1, 'colpi')
        json.dump(deck, open(pd, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    for i, sid in enumerate(deck['order'], 1):
        p = os.path.join(SLIDES, sid + '.html')
        s = open(p, encoding='utf-8').read()
        s2 = re.sub(r'(<p style="position:absolute;left:128px;bottom:64px;[^"]*">[^<]*(?:<[^/][^>]*>[^<]*</[a-z]+>[^<]*)*?) · \d+</p>',
                    lambda m: f'{m.group(1)} · {i}</p>', s)
        open(p, 'w', encoding='utf-8').write(s2)


if __name__ == '__main__':
    slide_metodo(); slide_q1(); slide_colpi(); slide_q2(); slide_q4(); slide_q5(); slide_q7(); slide_q3()
    deck_e_numeri()
    print('Slide rigenerate. Icone:', 'si' if ICON_MODE else 'no (mancano file: nomi colorati per ruolo)')
