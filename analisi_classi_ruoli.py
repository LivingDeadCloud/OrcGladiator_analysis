"""Profilo per classe e per ruolo (output anonimi: chiave = classe, mai il nome del giocatore).

Da eseguire nella cartella principale del progetto:
    python analisi_classi_ruoli.py
Output in data_analysis/v2/classi_ruoli/ (vedi NOTE.md nella stessa cartella).
Fonte di verita' per classe/ruolo: data_map/class_roles.csv.
Richiede prima: python analisi_colpi.py (colpi dell'eroe al netto delle unita' evocate, stima).

Nota sui nomi: la metrica 'tank' (colonna tank_pct della multiboard) e' la quota di COLPI presi dalla classe,
evocazioni comprese, non di danni (vedi data_analysis/v2/colpi/NOTE.md). 'colpi_eroe' e' la stessa quota per il solo
eroe, al netto delle unita' evocate (stima, scenario centrale).
"""
import csv, os, statistics as st
from collections import Counter, defaultdict

OUT = os.path.join('data_analysis', 'v2', 'classi_ruoli')
os.makedirs(OUT, exist_ok=True)

METRICHE = [('danni', 'dmg_pct'), ('boss', 'boss_dmg_pct'), ('cure', 'heal_pct'), ('tank', 'tank_pct')]
ORDINE_RUOLI = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']


def load(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write(name, rows, cols=None):
    cols = cols or list(rows[0])
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    return name


def r1(x, n=1):
    return '' if x is None or x == '' else round(x, n)


# ---------------------------------------------------------------- caricamento
roles = load('data_map/class_roles.csv')
CL = {r['player']: r['classe'] for r in roles}          # giocatore -> classe (usato solo internamente)
RUOLO = {r['classe']: r['ruolo'] for r in roles}
DIST = {r['classe']: r['distanza'] for r in roles}
TIPO = {r['classe']: r['tipo_mappa'] for r in roles}
ATTR = {r['classe']: r['attributo'] for r in roles}
assert len(set(CL.values())) == len(CL), 'ogni giocatore deve avere una classe diversa'
CLASSI = sorted(CL.values(), key=lambda c: (ORDINE_RUOLI.index(RUOLO[c]), c))
N_RUOLO = Counter(RUOLO.values())

snaps = load('data_screenshots/multiboard_snapshots.csv')
rounds = load('data_screenshots/rounds.csv')
summ = {CL[r['player']]: r for r in load('data_replay/player_summary.csv')}
pround = load('data_replay/player_round.csv')
abil = load('data_replay/player_abilities.csv')

# ---------------------------------------------------------------- snapshot -> stato cumulativo per challenge
# challenge 1..19: snapshot 'post' (challenges_completed = c).
# challenge 20 (boss finale): ultimo snapshot 'boss' con tutti e 10 presenti (031526_03, 5987 s);
# lo snapshot 'sconfitta' (040526_23) manca di una riga (giocatore uscito) e non viene usato per le quote.
cum = {}      # (classe, challenge) -> riga snapshot
tempo = {}    # challenge -> game_time_s dello snapshot
for s in snaps:
    if s['phase'] == 'post':
        c = int(s['challenges_completed'])
    elif s['screenshot'] == '031526_03':
        c = 20
    else:
        continue
    cum[(CL[s['player']], c)] = s
    tempo[c] = int(s['game_time_s'])
CHALL = sorted(tempo)

# colpi dell'eroe al netto delle evocazioni (analisi_colpi.py): si aggiungono come colonna degli snapshot
COLPI = {(r['screenshot'], r['classe']): r for r in load('data_analysis/v2/colpi/colpi_snapshot.csv')}
for key in list(cum):
    s = dict(cum[key]); cp = COLPI[(s['screenshot'], key[0])]
    s['colpi_eroe_pct'] = cp['colpi_quota_eroe_centrale']
    s['colpi_eroe_min'] = min(float(cp[f'colpi_quota_eroe_{x}']) for x in ('basso', 'centrale', 'alto'))
    s['colpi_eroe_max'] = max(float(cp[f'colpi_quota_eroe_{x}']) for x in ('basso', 'centrale', 'alto'))
    cum[key] = s
EVOC_MOD = {(r['classe'], int(r['challenge'])): float(r['quota_evocazioni_modello_centrale'])
            for r in load('data_analysis/v2/colpi/evocazioni_quota_modello_challenge.csv')}
SENZA_EVOC = [k for k in CLASSI if all(EVOC_MOD.get((k, c), 0) == 0 for c in range(1, 21))]
FINALE = 19   # profilo complessivo: quote cumulative dopo la challenge 19 (ultimo snapshot 'post', 10/10 presenti)

# ---------------------------------------------------------------- stima quota del singolo round
# Q_c = quota cumulativa dopo c, T_c = totale cumulativo del team (sconosciuto), r = T_{c-1}/T_c.
# quota_round_k = (Q_c,k - r*Q_{c-1},k) / (1 - r).
# 1) ipotesi base: T_c proporzionale al tempo di gioco  ->  r_tempo = t_{c-1}/t_c.
# 2) vincolo: nessuna classe puo' avere contributo negativo -> r <= min_k Q_c,k/Q_{c-1},k
#    (calcolato solo sulle classi con Q_{c-1} >= SOGLIA_VINCOLO, per non farsi guidare dall'arrotondamento a 0,1).
#    Si usa r = min(r_tempo, r_vincolo): se l'output del team cresce piu' del tempo (eroi piu' forti), il round pesa di piu'.
# 3) eventuali negativi residui (rumore) -> 0, poi rinormalizzazione a 100.
SOGLIA_VINCOLO = 2.0
stima = {}          # (classe, challenge, metrica) -> quota stimata del round
diagn = []
for i, c in enumerate(CHALL):
    tprev = tempo[CHALL[i - 1]] if i else 0
    r_t = tprev / tempo[c]
    for m, col in METRICHE:
        prev = {k: float(cum[(k, CHALL[i - 1])][col]) if i else 0.0 for k in CLASSI}
        cur = {k: float(cum[(k, c)][col]) for k in CLASSI}
        rat = [cur[k] / prev[k] for k in CLASSI if prev[k] >= SOGLIA_VINCOLO]
        r_v = min(rat) if (i and rat) else None
        r = min(r_t, r_v) if r_v is not None else r_t
        raw = {k: (cur[k] - r * prev[k]) / (1 - r) for k in CLASSI}
        neg = {k: v for k, v in raw.items() if v < 0}
        pos = {k: max(v, 0.0) for k, v in raw.items()}
        tot = sum(pos.values())
        for k in CLASSI:
            stima[(k, c, m)] = 100 * pos[k] / tot if tot > 0 else None
        diagn.append({'challenge': c, 'metrica': m, 'secondi_snapshot': tempo[c], 'secondi_snapshot_prec': tprev,
                      'r_ipotesi_tempo': round(r_t, 4), 'r_vincolo_non_negativita': r1(r_v, 4),
                      'r_usato': round(r, 4), 'peso_round_stimato_pct': round(100 * (1 - r), 1),
                      'vincolo_attivo': 'si' if r < r_t else 'no',
                      'classi_con_stima_negativa': len(neg), 'somma_negativi_azzerati': round(sum(neg.values()), 1)})

# colpi dell'eroe nel round: quota totale stimata del round meno la quota delle evocazioni prevista dal modello
# per quella challenge; l'eroe non scende sotto il meno colpito tra le classi senza evocazioni (pavimento).
for c in CHALL:
    pav = min(stima[(k, c, 'tank')] or 0 for k in SENZA_EVOC)
    for k in CLASSI:
        tot = stima[(k, c, 'tank')]
        if tot is None:
            stima[(k, c, 'colpi_eroe')] = None
            continue
        ev = min(EVOC_MOD.get((k, c), 0.0), max(0.0, tot - pav))
        stima[(k, c, 'colpi_eroe')] = tot - ev
METRICHE_OUT = METRICHE + [('colpi_eroe', 'colpi_eroe_pct')]

# ---------------------------------------------------------------- attivita' per challenge
att = {}
for p in pround:
    att[(CL[p['player']], int(p['challenge']))] = p

# ---------------------------------------------------------------- premi del round (rounds.csv -> classe)
PREMI = [('danni', 'best_damage'), ('tank', 'best_tank'), ('boss', 'best_boss_slayer'), ('cure', 'best_healer')]
premi = defaultdict(Counter)   # classe -> categoria -> n
for r in rounds:
    for cat, col in PREMI:
        if r[col]:
            premi[CL[r[col]]][cat] += 1


def anonimizza(testo):
    for p, k in sorted(CL.items(), key=lambda x: -len(x[0])):
        testo = testo.replace(p, k)
    return testo.replace('non Boom', 'non ' + CL['BoomKhamenei'])   # abbreviazione del nick nelle note


# ================================================================ 1. CLASSI
# --- profilo complessivo per classe
profilo = []
abil_cl = defaultdict(list)
for a in abil:
    if not a['name'].startswith('Oggetto'):
        abil_cl[CL[a['player']]].append((a['name'], int(a['count'])))
for k in CLASSI:
    s = summ[k]
    f = cum[(k, FINALE)]
    mins = float(s['minutes_played'])
    post_rows = [cum[(k, c)] for c in CHALL if c <= 19]
    golds = [int(x['gold']) for x in post_rows]
    top = max(abil_cl[k], key=lambda x: x[1])
    profilo.append({
        'classe': k, 'ruolo': RUOLO[k], 'distanza': DIST[k], 'tipo_mappa': TIPO[k], 'attributo': ATTR[k],
        'quota_danni': float(f['dmg_pct']), 'quota_boss': float(f['boss_dmg_pct']),
        'quota_cure': float(f['heal_pct']), 'quota_tank': float(f['tank_pct']),
        'quota_colpi_eroe': float(f['colpi_eroe_pct']), 'quota_colpi_eroe_min': f['colpi_eroe_min'],
        'quota_colpi_eroe_max': f['colpi_eroe_max'],
        'quota_colpi_evocazioni': round(float(f['tank_pct']) - float(f['colpi_eroe_pct']), 2),
        'quota_danni_boss_finale': float(cum[(k, 20)]['dmg_pct']), 'quota_tank_boss_finale': float(cum[(k, 20)]['tank_pct']),
        'quota_colpi_eroe_boss_finale': float(cum[(k, 20)]['colpi_eroe_pct']),
        'quota_cure_boss_finale': float(cum[(k, 20)]['heal_pct']),
        'minuti_giocati': mins, 'apm': float(s['apm']),
        'abilita_min': round(int(s['ability']) / mins, 2),
        'click_movimento_min': round(int(s['rclick_ground']) / mins, 1),
        'click_bersaglio_min': round(int(s['rclick_unit']) / mins, 1),
        'distanza_movimento_min': round(float(s['move_distance']) / mins),
        'hold_position': int(s['hold']), 'oggetti_usati': int(s['item_use']), 'acquisti': int(s['shop_buy']),
        'comandi_prestito': int(s['loan_cmd']),
        'oro_medio_fine_round': round(st.mean(golds)), 'oro_max': max(golds),
        'round_sotto_20hp': sum(1 for x in post_rows if int(x['hp_pct']) <= 20),
        'premi_danni': premi[k]['danni'], 'premi_tank': premi[k]['tank'], 'premi_boss': premi[k]['boss'],
        'premi_cure': premi[k]['cure'], 'premi_totali': sum(premi[k].values()),
        'abilita_principale': top[0], 'abilita_principale_usi': top[1],
    })
files = [write('profilo_classi.csv', profilo)]

# --- andamento per challenge (quote cumulative + stima del round)
andamento = []
for k in CLASSI:
    for c in CHALL:
        s = cum[(k, c)]
        row = {'classe': k, 'ruolo': RUOLO[k], 'challenge': c,
               'fase': 'boss_finale_parziale' if c == 20 else 'fine_round'}
        for m, col in METRICHE_OUT:
            row[f'{m}_cum'] = float(s[col])
        for m, _ in METRICHE_OUT:
            row[f'{m}_round_stima'] = r1(stima[(k, c, m)])
        row.update({'oro': int(s['gold']), 'hp_fine_round': int(s['hp_pct']), 'livello': int(s['level'])})
        andamento.append(row)
files.append(write('andamento_classi.csv', andamento))

# --- attivita' per challenge
attivita = []
for k in CLASSI:
    for c in range(1, 21):
        a = att.get((k, c))
        if not a:
            continue
        mins = float(a['segment_minutes'])
        attivita.append({'classe': k, 'ruolo': RUOLO[k], 'challenge': c, 'minuti': mins, 'apm': float(a['apm']),
                         'abilita': int(a['ability']), 'abilita_min': round(int(a['ability']) / mins, 2),
                         'click_movimento_min': round(int(a['rclick_ground']) / mins, 1),
                         'oggetti_usati': int(a['item_use']), 'acquisti': int(a['shop_buy'])})
files.append(write('attivita_classi.csv', attivita))

# --- uso abilita'
uso = []
for k in CLASSI:
    tot = sum(n for _, n in abil_cl[k])
    mins = float(summ[k]['minutes_played'])
    for nome, n in sorted(abil_cl[k], key=lambda x: -x[1]):
        uso.append({'classe': k, 'ruolo': RUOLO[k], 'abilita': nome, 'usi': n, 'usi_min': round(n / mins, 2),
                    'quota_usi_classe': round(100 * n / tot, 1)})
files.append(write('abilita_classi.csv', uso))

# --- round con migliori per classe/ruolo
eroi20 = Counter(c for (k, c), s in cum.items() if c <= 19 and int(s['hp_pct']) <= 20)
rr = []
for r in rounds:
    c = int(r['challenge'])
    row = {'challenge': c, 'ondata': r['wave'], 'secondi': r['clear_seconds'], 'voto': r['grade'],
           'eroi_sotto_20hp': eroi20.get(c, 0) if c <= 19 else ''}
    for cat, col in PREMI:
        k = CL[r[col]] if r[col] else ''
        row[f'migliore_{cat}'] = k
        row[f'migliore_{cat}_ruolo'] = RUOLO[k] if k else ''
    row['note'] = anonimizza(r['notes'])
    rr.append(row)
files.append(write('round_classi.csv', rr))

# ================================================================ 2. RUOLI
def per_ruolo(righe, somme, medie):
    g = defaultdict(list)
    for x in righe:
        g[x['ruolo']].append(x)
    out = {}
    for ru in ORDINE_RUOLI:
        xs = g[ru]
        d = {'ruolo': ru, 'n_classi': len(xs), 'classi': '; '.join(x['classe'] for x in xs)}
        for c in somme:
            vals = [x[c] for x in xs if x[c] != '' and x[c] is not None]
            d[c] = round(sum(vals), 1) if len(vals) == len(xs) else ''
        for c in medie:
            vals = [float(x[c]) for x in xs if x[c] != '' and x[c] is not None]
            d[c] = round(st.mean(vals), 2) if vals else ''
        out[ru] = d
    return out


Q = ['quota_danni', 'quota_boss', 'quota_cure', 'quota_tank', 'quota_colpi_eroe', 'quota_colpi_evocazioni',
     'quota_danni_boss_finale', 'quota_tank_boss_finale', 'quota_colpi_eroe_boss_finale', 'quota_cure_boss_finale']
PR = ['premi_danni', 'premi_tank', 'premi_boss', 'premi_cure', 'premi_totali', 'round_sotto_20hp']
ATT = ['apm', 'abilita_min', 'click_movimento_min', 'click_bersaglio_min', 'distanza_movimento_min',
       'oggetti_usati', 'acquisti', 'oro_medio_fine_round']
pr = per_ruolo(profilo, Q + PR, ATT)
profilo_ruoli = []
for ru in ORDINE_RUOLI:
    d = pr[ru]
    n = d['n_classi']
    row = {'ruolo': ru, 'n_classi': n, 'classi': d['classi']}
    for c in Q:
        row[c] = d[c]
    for c in ('quota_danni', 'quota_cure', 'quota_tank', 'quota_colpi_eroe'):
        row[c + '_per_classe'] = round(d[c] / n, 1)          # confrontabile con la quota "equa" 10
    for c in PR:
        row[c] = d[c]
    for c in ATT:
        row[c + '_media'] = d[c]
    profilo_ruoli.append(row)
files.append(write('profilo_ruoli.csv', profilo_ruoli))

# per challenge
and_ruoli = []
for c in CHALL:
    righe = [x for x in andamento if x['challenge'] == c]
    att_c = {x['classe']: x for x in attivita if x['challenge'] == c}
    for x in righe:
        a = att_c.get(x['classe'], {})
        x['_apm'] = a.get('apm', '')
        x['_abmin'] = a.get('abilita_min', '')
        x['_mov'] = a.get('click_movimento_min', '')
    somme = [f'{m}_cum' for m, _ in METRICHE_OUT] + [f'{m}_round_stima' for m, _ in METRICHE_OUT]
    g = per_ruolo(righe, somme, ['hp_fine_round', 'livello', '_apm', '_abmin', '_mov'])
    for ru in ORDINE_RUOLI:
        d = g[ru]
        row = {'ruolo': ru, 'challenge': c, 'n_classi': d['n_classi']}
        for s_ in somme:
            row[s_] = d[s_]
        row.update({'hp_fine_round_medio': d['hp_fine_round'], 'livello_medio': d['livello'],
                    'apm_medio': d['_apm'], 'abilita_min_media': d['_abmin'], 'click_movimento_min_medio': d['_mov']})
        and_ruoli.append(row)
files.append(write('andamento_ruoli.csv', and_ruoli))

# uso abilita' per ruolo
uso_r = defaultdict(lambda: [0, 0.0])
for u in uso:
    uso_r[(u['ruolo'], u['abilita'])][0] += u['usi']
min_ruolo = defaultdict(float)
for k in CLASSI:
    min_ruolo[RUOLO[k]] += float(summ[k]['minutes_played'])
rows = []
for ru in ORDINE_RUOLI:
    xs = sorted(((ab, v[0]) for (r_, ab), v in uso_r.items() if r_ == ru), key=lambda x: -x[1])
    tot = sum(n for _, n in xs)
    for ab, n in xs:
        rows.append({'ruolo': ru, 'abilita': ab, 'usi': n, 'usi_min_per_classe': round(n / min_ruolo[ru], 2),
                     'quota_usi_ruolo': round(100 * n / tot, 1)})
files.append(write('abilita_ruoli.csv', rows))

files.append(write('stima_round_diagnostica.csv', diagn))

# ================================================================ 3. COERENZA RUOLI
def rango(col):
    ordine = sorted(profilo, key=lambda x: -x[col])
    return {x['classe']: i + 1 for i, x in enumerate(ordine)}


rk = {m: rango('quota_' + m) for m in ('danni', 'tank', 'colpi_eroe', 'cure', 'boss')}
top_round = defaultdict(Counter)   # classe -> metrica -> n challenge (1..19) in cui e' 1a nella stima del round
for c in CHALL:
    if c > 19:
        continue
    for m, _ in METRICHE_OUT:
        vals = {k: stima[(k, c, m)] for k in CLASSI if stima[(k, c, m)] is not None}
        if vals:
            top_round[max(vals, key=vals.get)][m] += 1
tank_tank = [x['quota_colpi_eroe'] for x in profilo if x['ruolo'] == 'Tank']
heal_heal = [x['quota_cure'] for x in profilo if x['ruolo'] == 'Healer']
dps_min = min(x['quota_danni'] for x in profilo if x['ruolo'].startswith('DPS'))
coer = []
for x in profilo:
    k, ru = x['classe'], x['ruolo']
    idx = {'danni': x['quota_danni'] / 10, 'tank': x['quota_colpi_eroe'] / 10, 'cure': x['quota_cure'] / 10}
    dom = max(idx, key=idx.get)
    osservato = {'danni': 'DPS', 'tank': 'Tank', 'cure': 'Healer'}[dom] if idx[dom] >= 1 else 'contributo sotto la media'
    note = []
    if ru == 'Tank':
        if x['quota_colpi_eroe'] < max(p['quota_colpi_eroe'] for p in profilo if p['ruolo'] != 'Tank'):
            altri = [p['classe'] for p in profilo if p['ruolo'] != 'Tank' and p['quota_colpi_eroe'] > x['quota_colpi_eroe']]
            note.append(f"Tank il cui eroe prende meno colpi di {', '.join(altri)}")
        if x['quota_cure'] > 10:
            note.append(f"cura molto ({x['quota_cure']}%, sopra la quota equa 10%)")
    else:
        if x['quota_colpi_eroe'] > min(tank_tank):
            note.append(f"non-Tank il cui eroe prende piu' colpi di almeno un Tank ({x['quota_colpi_eroe']}% vs min Tank {min(tank_tank)}%)")
    if ru != 'Healer' and x['quota_cure'] > 10:
        note.append(f"non-Healer con quota cure {x['quota_cure']}% (> 10%)")
    if ru == 'Healer' and x['quota_cure'] < max(p['quota_cure'] for p in profilo if p['ruolo'] != 'Healer'):
        note.append('Healer non primo per cure')
    if ru.startswith('DPS') and x['quota_danni'] < 10:
        note.append(f"DPS sotto la quota equa di danni ({x['quota_danni']}% < 10%)")
    if not ru.startswith('DPS') and x['quota_danni'] > dps_min:
        note.append(f"non-DPS con piu' danni del DPS piu' basso ({x['quota_danni']}% vs {dps_min}%)")
    atteso = {'Tank': 'Tank', 'Healer': 'Healer', 'DPS mischia': 'DPS', 'DPS distanza': 'DPS', 'Support': None}[ru]
    if atteso is None:
        coerente = 'n.d. (Support: nessuna metrica diretta)'
    elif osservato == atteso and not note:
        coerente = 'si'
    elif osservato == atteso:
        coerente = 'parziale'
    else:
        coerente = 'no'
    coer.append({'classe': k, 'ruolo': ru, 'distanza': x['distanza'],
                 'quota_danni': x['quota_danni'], 'rango_danni': rk['danni'][k],
                 'quota_tank': x['quota_tank'], 'rango_tank': rk['tank'][k],
                 'quota_colpi_eroe': x['quota_colpi_eroe'], 'rango_colpi_eroe': rk['colpi_eroe'][k],
                 'quota_colpi_evocazioni': x['quota_colpi_evocazioni'],
                 'quota_cure': x['quota_cure'], 'rango_cure': rk['cure'][k],
                 'quota_boss': x['quota_boss'], 'rango_boss': rk['boss'][k],
                 'indice_danni': round(idx['danni'], 2), 'indice_tank': round(idx['tank'], 2),
                 'indice_cure': round(idx['cure'], 2),
                 'premi_danni': x['premi_danni'], 'premi_tank': x['premi_tank'], 'premi_cure': x['premi_cure'],
                 'round_primo_danni_stima': top_round[k]['danni'], 'round_primo_tank_stima': top_round[k]['tank'],
                 'round_primo_colpi_eroe_stima': top_round[k]['colpi_eroe'],
                 'round_primo_cure_stima': top_round[k]['cure'],
                 'ruolo_osservato': osservato, 'coerente': coerente, 'nota': '; '.join(note)})
files.append(write('coerenza_ruoli.csv', coer))

# ================================================================ validazione: stima del round vs premi del round
# I premi "migliore del round" (rounds.csv) sono un riscontro indipendente: la classe prima nella stima
# del round dovrebbe coincidere con il premiato.
val = []
for r in rounds:
    c = int(r['challenge'])
    if c not in CHALL:
        continue
    for cat, col in PREMI:
        if not r[col]:
            continue
        premiato = CL[r[col]]
        st_ = {k: stima[(k, c, cat)] or 0 for k in CLASSI}
        cu = {k: float(cum[(k, c)][dict(METRICHE)[cat]]) for k in CLASSI}
        p_st, p_cu = max(st_, key=st_.get), max(cu, key=cu.get)
        val.append({'challenge': c, 'metrica': cat, 'premiato': premiato, 'primo_stima_round': p_st,
                    'primo_cumulativo': p_cu, 'concorda_stima': 'si' if p_st == premiato else 'no',
                    'concorda_cumulativo': 'si' if p_cu == premiato else 'no'})
files.append(write('validazione_stima_round.csv', val))
print('validazione: stima round concorda', sum(v['concorda_stima'] == 'si' for v in val), '/', len(val),
      '| cumulativo concorda', sum(v['concorda_cumulativo'] == 'si' for v in val), '/', len(val))

# ================================================================ controllo anonimato
nomi = list(CL) + ['Boom']
for fn in files:
    testo = open(os.path.join(OUT, fn), encoding='utf-8').read()
    trovati = [n for n in nomi if n in testo]
    assert not trovati, f'{fn} contiene nomi giocatore: {trovati}'

print('File scritti in', OUT)
for fn in files:
    print(' -', fn)
for x in profilo_ruoli:
    print({k: x[k] for k in ('ruolo', 'n_classi', 'quota_danni', 'quota_tank', 'quota_colpi_eroe', 'quota_cure', 'quota_boss', 'apm_media')})
for x in coer:
    print(x['classe'], '|', x['ruolo'], '->', x['ruolo_osservato'], '|', x['coerente'], '|', x['nota'])
