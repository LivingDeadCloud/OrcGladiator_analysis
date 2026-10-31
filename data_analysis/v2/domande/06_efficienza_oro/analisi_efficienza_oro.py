"""Domanda 06 - I soldi sono spesi in maniera efficiente?

Ricostruisce il bilancio dell'oro per classe simulando la meccanica della mappa (war3map.j)
sui comandi del replay, e lo valida con l'oro misurato negli screenshot della multiboard.

Eseguire dalla cartella del progetto:
    python data_analysis/v2/domande/06_efficienza_oro/analisi_efficienza_oro.py

Regole della mappa usate (verificate in data_map/raw/war3map.j):
- Run_Reward (fine challenge c): vittoria = (CurrentWave-1)*10 = 10*c a tutti;
  voto = vittoria * {A+:1, A:.75, B:.5, C:.4, D:.3, E:.2, F:.1, G:0} a tutti;
  Get_MVP_Current_Round: R2I(2.5*c) al migliore di danni, tank, boss, cure del round;
  "random gold" 2*c solo a chi ha scelto l'eroe a caso (qui nessuno: tutti hanno comprato l'eroe).
- End_of_Round_Effects: Scavenger = c * ScavengerGoldBonus (talento di squadra; rounds.csv: 2/round da ch.7);
  Contender's Token: +60 alla 2a fine round (perso se si muore); Goldstrike: +10*c (non comprato).
- Repay_Loans: subito dopo l'oro del voto e a ogni Wave_Start. Il debitore paga TUTTO l'oro che ha
  fino a estinguere il debito.
- -borrow N (N max 4 cifre, stringa esatta): una sola richiesta aperta alla volta, scade dopo 15 s;
  rifiutata se il debito gia' in essere e' >= 2500 (tranne wave 20).
- -loan [N]: presta min(N o tutto il proprio oro, residuo della richiesta).
- Tomi: se l'eroe e' sotto il livello 12 il prezzo (110) viene rimborsato.
- Stivali: comprando un nuovo paio si riceve il 75% del prezzo del vecchio.
- Un ordine di acquisto senza oro sufficiente viene rifiutato dal gioco (nessun costo).
Niente interessi sull'oro (nessun trigger di interesse nel codice) e nessuna taglia sulle uccisioni
(PLAYER_STATE_GIVES_BOUNTY non e' mai impostato).
"""
import csv, os, re, sys, statistics
from collections import defaultdict, OrderedDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import objdata  # noqa: E402


def P(*a):
    return os.path.join(ROOT, *a)


def rcsv(path):
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def wcsv(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, '') for c in cols})


# ---------------------------------------------------------------- anagrafica
roles = {r['classe']: r['ruolo'] for r in rcsv(P('data_map', 'class_roles.csv'))}
pl2cl = {r['player']: r['weapon_class'].split(' (')[0] for r in rcsv(P('data_map', 'classes.csv'))}
CLASSES = sorted(roles)

# ---------------------------------------------------------------- prezzi (mappa)
wts = objdata.parse_wts(open(P('data_map', 'raw', 'war3map.wts'), 'rb').read())
w3t = objdata.parse_obj(open(P('data_map', 'raw', 'war3map.w3t'), 'rb').read(), 'w3t', wts)
# costo di default degli oggetti base quando la mappa non lo modifica
# (letto da Units\ItemData.slk in War3Patch.mpq del gioco installato)
BASE_GOLD = {'belv': 400, 'rhe3': 300, 'texp': 500, 'tdex': 150, 'rdis': 75, 'lnrn': 50, 'rag1': 100, 'fgfh': 550}

TOMES = {'I03H', 'I03I', 'I03J', 'I03K', 'I03L', 'I03M'}
BOOTS = {'I00F', 'I06Z', 'I00N', 'I06U', 'I00H', 'I00D', 'I00L', 'I06T', 'I072', 'I070', 'I071', 'I00K'}
POTIONS = {'I00T', 'I00Q', 'I00R', 'I00V', 'I07Q', 'I00U', 'I07P', 'I00W', 'I07R'}
TOKENS = {'I056': (2, 60), 'I057': (3, 180), 'I058': (4, 480)}


def item_info(code):
    o = w3t.get(code)
    if not o:
        return '?', 0, 0, ''
    m = o['mods']
    name = objdata.clean(m.get(('unam', 0)) or m.get(('utip', 0)) or code)
    gold = m.get(('igol', 0))
    if gold is None:
        gold = BASE_GOLD.get(o['base'], 0)
    lum = m.get(('ilum', 0)) or 0
    return name, gold, lum, m.get(('icla', 0), '')


def categoria(code, gold, lum, icla):
    if lum and not gold:
        return 'talento (punti talento, non oro)'
    if gold == 0:
        return 'gratuito (teletrasporto / Ancestral Strength)'
    if code in TOMES:
        return 'tomo (statistiche permanenti)'
    if code in BOOTS:
        return 'stivali (permanente)'
    if code in POTIONS:
        return 'pozione (riutilizzabile, cooldown 40 s)'
    if code in TOKENS:
        return 'scommessa (token)'
    if code == 'I05S':
        return 'consumabile (evocazione)'
    if code.startswith('I04Z') or 'Hex' in item_info(code)[0]:
        return 'hex (potenzia un oggetto)'
    return 'reliquia/artefatto (permanente)'


# ---------------------------------------------------------------- tempi dei round
fin = {int(r['challenge']): (float(r['inizio_s']), float(r['fine_s']))
       for r in rcsv(P('data_analysis', 'v2', 'abilita_mana', 'finestre_combattimento.csv'))}
rounds = {}
for r in rcsv(P('data_screenshots', 'rounds.csv')):
    c = int(r['challenge'])
    rounds[c] = r
GRADE_F = {'A+': 1, 'A': .75, 'B': .5, 'C': .4, 'D': .3, 'E': .2, 'F': .1, 'G': 0}

# snapshot (oro misurato)
snaps = OrderedDict()
for r in rcsv(P('data_screenshots', 'multiboard_snapshots.csv')):
    k = (r['screenshot'], float(r['game_time_s']), int(r['challenges_completed']), r['phase'])
    snaps.setdefault(k, {})[pl2cl[r['player']]] = (int(r['gold']) if r['gold'] not in ('', None) else None,
                                                    int(r['level']) if r['level'] else None)
snap_list = list(snaps.items())


def level_at(cls, t):
    """Livello all'ultimo screenshot prima di t (limite inferiore) e al successivo (limite superiore)."""
    lo, hi = 1, None
    for (sid, ts, cc, ph), d in snap_list:
        lv = d.get(cls, (None, None))[1]
        if lv is None:
            continue
        if ts <= t:
            lo = lv
        elif hi is None:
            hi = lv
    return lo, hi


# ---------------------------------------------------------------- eventi
EV = []  # (t, priorita, tipo, dati)
# acquisti
for r in rcsv(P('data_replay', 'actions_named.csv')):
    if r['order'].startswith('I0') and r['kind'] == 'order_notarget':
        EV.append((int(r['game_time_ms']) / 1000, 5, 'buy', (pl2cl[r['player']], r['order'])))
# chat prestiti
for r in rcsv(P('data_replay', 'chat.csv')):
    m = r['message']
    if m.startswith('-borrow') or m.startswith('-loan') or m.startswith('-borr') or m.startswith('-lo') or m.startswith('-oan') or m.startswith('-boo'):
        EV.append((int(r['game_time_ms']) / 1000, 4, 'chat', (pl2cl[r['player']], m)))
# fine round / inizio round
name2cl = pl2cl
for c in range(1, 21):
    a, b = fin[c]
    EV.append((a, 1, 'wave_start', c))
    if c <= 19:
        EV.append((b - 0.5, 2, 'round_end', c))
# scelte dopo ch 12 e 19 (finestra di scelta ~12-22 s dopo la ricompensa)
for r in rcsv(P('data_screenshots', 'stat_choices.csv')):
    m = re.search(r'\+(\d+) Gold', r['choice'])
    if m:
        c = int(r['after_challenge'])
        EV.append((fin[c][1] + 15, 3, 'stat_gold', (pl2cl[r['player']], int(m.group(1)), c)))
# screenshot
for (sid, ts, cc, ph), d in snap_list:
    EV.append((ts, 9, 'snap', (sid, cc, ph, d)))
EV.sort(key=lambda e: (e[0], e[1]))

SCAV_FROM = 7  # rounds.csv: scavenger_bonus presente dalla challenge 7


def run(anchor=True, ch8_grade=None, ch12_grade=None):
    gold = {c: 0 for c in CLASSES}
    debt = defaultdict(int)  # (debitore, creditore) -> importo
    boots = {}  # classe -> prezzo degli stivali posseduti
    tokens = []  # [classe, code, fine_round_contati]
    ledger = []  # movimenti
    validation = []
    failed = []
    loans = []
    borrow = None  # dict richiesta aperta
    income_t = []  # (t, classe, importo) per tempo di permanenza

    def mov(t, cls, amount, kind, detail=''):
        gold[cls] += amount
        ledger.append({'t': t, 'classe': cls, 'importo': amount, 'tipo': kind, 'dettaglio': detail,
                       'saldo': gold[cls]})

    def repay(t, when):
        for deb in CLASSES:
            for cred in CLASSES:
                d = debt[(deb, cred)]
                if d <= 0:
                    continue
                w = gold[deb]
                pay = d if d <= w else max(w, 0)
                if pay > 0:
                    mov(t, deb, -pay, 'rimborso_prestito_pagato', cred + ' (' + when + ')')
                    mov(t, cred, pay, 'rimborso_prestito_ricevuto', deb + ' (' + when + ')')
                    debt[(deb, cred)] = d - pay
                    for L in loans:
                        if L['debitore'] == deb and L['creditore'] == cred and L['residuo'] > 0:
                            q = min(L['residuo'], pay)
                            L['residuo'] -= q
                            pay -= q
                            if L['residuo'] == 0:
                                L['rimborsato_s'] = round(t)
                            if pay == 0:
                                break

    def close_borrow(t):
        nonlocal borrow
        if borrow and t >= borrow['scade']:
            borrow = None

    for t, pr, typ, data in EV:
        close_borrow(t)
        if typ == 'buy':
            cls, code = data
            name, price, lum, icla = item_info(code)
            cat = categoria(code, price, lum, icla)
            if price <= 0:
                ledger.append({'t': t, 'classe': cls, 'importo': 0, 'tipo': 'acquisto', 'dettaglio': f'{code} {name} | {cat}', 'saldo': gold[cls]})
                continue
            if gold[cls] < price:
                failed.append({'t': round(t, 1), 'classe': cls, 'ruolo': roles[cls], 'codice': code, 'oggetto': name,
                               'prezzo': price, 'oro_simulato': gold[cls]})
                continue
            mov(t, cls, -price, 'acquisto', f'{code} {name} | {cat}')
            if code in TOMES:
                lo, hi = level_at(cls, t)
                if hi is not None and hi < 12:
                    mov(t, cls, price, 'rimborso_tomo', 'livello < 12')
            if code in BOOTS:
                if cls in boots:
                    ref = int(boots[cls] * .75)
                    mov(t, cls, ref, 'rimborso_stivali', '75% stivali precedenti')
                boots[cls] = price
            if code in TOKENS:
                tokens.append([cls, code, 0])
        elif typ == 'chat':
            cls, msg = data
            m = re.fullmatch(r'-borrow (.{1,4})', msg)
            if msg.startswith('-borrow '):
                sub = msg[8:12]
                ok_str = msg == '-borrow ' + sub
                try:
                    n = int(sub.strip()) if sub.strip().isdigit() else 0
                except ValueError:
                    n = 0
                if ok_str and n > 0 and borrow is None:
                    tot = sum(debt[(cls, c)] for c in CLASSES)
                    wave = next((c for c in range(1, 21) if fin[c][0] <= t <= fin[c][1] + 130), 0)
                    if tot >= 2500 and wave != 20:
                        continue
                    borrow = {'chi': cls, 'resto': n, 'richiesto': n, 'scade': t + 15, 't': t}
                continue
            if msg == '-loan' or msg.startswith('-loan '):
                sub = msg[6:10] if len(msg) > 6 else ''
                if not (msg == '-loan ' + sub or msg == '-loan'):
                    continue
                if borrow is None or cls == borrow['chi'] or gold[cls] <= 0:
                    continue
                n = int(sub) if sub.strip().isdigit() else 0
                amt = n
                if amt <= 0:
                    amt = gold[cls]
                if gold[cls] < amt:
                    amt = gold[cls]
                if amt >= borrow['resto']:
                    amt = borrow['resto']
                deb = borrow['chi']
                mov(t, deb, amt, 'prestito_ricevuto', cls)
                mov(t, cls, -amt, 'prestito_dato', deb)
                debt[(deb, cls)] += amt
                loans.append({'t_s': round(t), 'debitore': deb, 'ruolo_debitore': roles[deb], 'creditore': cls,
                              'ruolo_creditore': roles[cls], 'importo': amt, 'richiesta': borrow['richiesto'],
                              'residuo': amt, 'rimborsato_s': ''})
                borrow['resto'] -= amt
                if borrow['resto'] <= 0:
                    borrow['scade'] = t + 1
        elif typ == 'wave_start':
            repay(t, 'inizio challenge %d' % data)
        elif typ == 'round_end':
            c = data
            r = rounds.get(c, {})
            vic = 10 * c
            for cls in CLASSES:
                mov(t, cls, vic, 'oro_vittoria', 'ch%d' % c)
                income_t.append((t, cls, vic))
            # MVP
            mvp = R2I = int(2.5 * c)
            for col in ('best_damage', 'best_tank', 'best_boss_slayer', 'best_healer'):
                p = r.get(col, '')
                if p:
                    mov(t, name2cl[p], mvp, 'oro_migliore_round', col + ' ch%d' % c)
                    income_t.append((t, name2cl[p], mvp))
            # voto
            gg = r.get('grade_gold', '')
            if gg == '' and c == 8 and ch8_grade is not None:
                gg = int(vic * GRADE_F[ch8_grade])
            if gg == '' and c == 12 and ch12_grade is not None:
                gg = int(vic * GRADE_F[ch12_grade])
            if gg != '':
                for cls in CLASSES:
                    mov(t, cls, int(gg), 'oro_voto', 'ch%d' % c)
                    income_t.append((t, cls, int(gg)))
            # scavenger
            if c >= SCAV_FROM:
                for cls in CLASSES:
                    mov(t, cls, 2 * c, 'oro_scavenger', 'ch%d' % c)
                    income_t.append((t, cls, 2 * c))
            # token
            for tk in tokens:
                tk[2] += 1
                need, pay = TOKENS[tk[1]]
                if tk[2] == need:
                    mov(t, tk[0], pay, 'oro_token', tk[1] + ' (ipotesi: sopravvissuto)')
                    income_t.append((t, tk[0], pay))
            tokens[:] = [tk for tk in tokens if tk[2] < TOKENS[tk[1]][0]]
            repay(t, 'fine challenge %d' % c)
        elif typ == 'stat_gold':
            cls, g, c = data
            mov(t, cls, g, 'oro_ricompensa_statistica', 'dopo ch%d' % c)
            income_t.append((t, cls, g))
        elif typ == 'snap':
            sid, cc, ph, d = data
            for cls in CLASSES:
                meas = d.get(cls, (None, None))[0]
                if meas is None:
                    continue
                validation.append({'screenshot': sid, 't_s': round(t), 'challenge_completate': cc, 'fase': ph,
                                   'classe': cls, 'ruolo': roles[cls], 'oro_misurato': meas,
                                   'oro_simulato': gold[cls], 'scarto': meas - gold[cls]})
                if anchor and meas != gold[cls]:
                    mov(t, cls, meas - gold[cls], 'correzione_screenshot', sid)
    return dict(gold=gold, ledger=ledger, validation=validation, failed=failed, loans=loans, debt=debt,
                income_t=income_t)


# ---------------------------------------------------------------- stima voto ch.8 e ch.12
# Il voto delle challenge 8 e 12 non e' visibile. Si sceglie il voto che minimizza lo scarto mediano
# assoluto sugli screenshot dopo ch.8 e ch.12 (stessa somma per tutte le classi).
def score(ch8, ch12):
    res = run(anchor=True, ch8_grade=ch8, ch12_grade=ch12)
    e8 = [abs(v['scarto']) for v in res['validation'] if v['challenge_completate'] == 8 and v['fase'] == 'post']
    e12 = [abs(v['scarto']) for v in res['validation'] if v['challenge_completate'] == 12 and v['fase'] == 'post']
    return statistics.median(e8), statistics.median(e12)


best8 = min(GRADE_F, key=lambda g: score(g, None)[0])
best12 = min(GRADE_F, key=lambda g: score(None, g)[1])
grade_scan = [{'challenge': 8, 'voto_ipotizzato': g, 'scarto_mediano_assoluto': score(g, None)[0]} for g in GRADE_F] + \
             [{'challenge': 12, 'voto_ipotizzato': g, 'scarto_mediano_assoluto': score(None, g)[1]} for g in GRADE_F]
wcsv('stima_voto_ch8_ch12.csv', grade_scan, ['challenge', 'voto_ipotizzato', 'scarto_mediano_assoluto'])

A = run(anchor=True, ch8_grade=best8, ch12_grade=best12)     # ancorata agli screenshot
F = run(anchor=False, ch8_grade=best8, ch12_grade=best12)    # libera (deriva cumulativa)

# ---------------------------------------------------------------- output: validazione
val = A['validation']
free_by = {(v['screenshot'], v['classe']): v for v in F['validation']}
for v in val:
    fv = free_by.get((v['screenshot'], v['classe']))
    v['oro_simulato_senza_ancoraggio'] = fv['oro_simulato'] if fv else ''
    v['scarto_senza_ancoraggio'] = fv['scarto'] if fv else ''
wcsv('validazione_oro_screenshot.csv', val,
     ['screenshot', 't_s', 'challenge_completate', 'fase', 'classe', 'ruolo', 'oro_misurato', 'oro_simulato', 'scarto',
      'oro_simulato_senza_ancoraggio', 'scarto_senza_ancoraggio'])
wcsv('movimenti_oro.csv', [dict(l, t=round(l['t'], 1)) for l in A['ledger'] if l['importo'] != 0 or l['tipo'] == 'acquisto'],
     ['t', 'classe', 'tipo', 'importo', 'saldo', 'dettaglio'])
wcsv('acquisti_rifiutati_simulati.csv', A['failed'], ['t', 'classe', 'ruolo', 'codice', 'oggetto', 'prezzo', 'oro_simulato'])
for L in A['loans']:
    L['stato'] = 'rimborsato' if L['residuo'] == 0 else 'NON rimborsato (residuo %d)' % L['residuo']
wcsv('prestiti.csv', A['loans'], ['t_s', 'debitore', 'ruolo_debitore', 'creditore', 'ruolo_creditore', 'importo',
                                  'richiesta', 'stato', 'rimborsato_s'])

# ---------------------------------------------------------------- bilancio per classe
END_T = max(ts for (sid, ts, cc, ph), d in snap_list)
bil = []
cat_rows = defaultdict(lambda: defaultdict(int))
for cls in CLASSES:
    L = [l for l in A['ledger'] if l['classe'] == cls]
    s = defaultdict(int)
    for l in L:
        s[l['tipo']] += l['importo']
        if l['tipo'] == 'acquisto' and l['importo']:
            cat = l['dettaglio'].split(' | ')[1]
            cat_rows[cls][cat] += -l['importo']
    for l in L:
        if l['tipo'].startswith('rimborso_tomo') or l['tipo'] == 'rimborso_stivali':
            pass
    entrate = sum(s[k] for k in ('oro_vittoria', 'oro_voto', 'oro_migliore_round', 'oro_scavenger', 'oro_token',
                                 'oro_ricompensa_statistica'))
    spesa = -s['acquisto'] - s['rimborso_tomo'] - s['rimborso_stivali']
    meas = {}
    for (sid, ts, cc, ph), d in snap_list:
        if d.get(cls, (None,))[0] is not None:
            meas[(cc, ph, sid)] = d[cls][0]
    last_post19 = snaps[[k for k in snaps if k[2] == 19 and k[3] == 'post'][0]][cls][0]
    boss = snaps[[k for k in snaps if k[3] == 'boss'][0]][cls][0]
    fine = [d[cls][0] for (sid, ts, cc, ph), d in snap_list if ph == 'sconfitta' and d.get(cls, (None,))[0] is not None]
    post = [d[cls][0] for (sid, ts, cc, ph), d in snap_list if ph == 'post']
    # tempo medio di permanenza (legge di Little): saldo medio pesato sul tempo / entrate per secondo
    pts = [(l['t'], l['saldo']) for l in L]
    area = 0.0
    t0 = 0.0
    bal = 0
    for t, sal in pts:
        area += bal * (t - t0)
        t0, bal = t, sal
    area += bal * (END_T - t0)
    rate = entrate / END_T
    perm = area / END_T / rate if rate else 0
    # FIFO: ritardo tra arrivo dell'oro (entrate proprie) e spesa in acquisti
    lots = []
    delays = []
    for l in L:
        if l['importo'] > 0 and l['tipo'].startswith('oro_'):
            lots.append([l['t'], l['importo']])
        elif l['importo'] < 0 and l['tipo'] in ('acquisto',):
            need = -l['importo']
            while need > 0 and lots:
                q = min(need, lots[0][1])
                delays.append((l['t'] - lots[0][0], q))
                lots[0][1] -= q
                need -= q
                if lots[0][1] == 0:
                    lots.pop(0)
    fifo = sum(d * q for d, q in delays) / sum(q for d, q in delays) if delays else 0
    dato = -s['prestito_dato']
    ricevuto = s['prestito_ricevuto']
    bil.append({
        'classe': cls, 'ruolo': roles[cls],
        'entrate_vittoria': s['oro_vittoria'], 'entrate_voto': s['oro_voto'], 'entrate_migliore_round': s['oro_migliore_round'],
        'entrate_scavenger': s['oro_scavenger'], 'entrate_token': s['oro_token'], 'entrate_ricompensa_statistica': s['oro_ricompensa_statistica'],
        'entrate_totali_stimate': entrate,
        'spesa_netta_acquisti': spesa,
        'spesa_tomi': cat_rows[cls]['tomo (statistiche permanenti)'] - s['rimborso_tomo'],
        'spesa_reliquie': cat_rows[cls]['reliquia/artefatto (permanente)'],
        'spesa_stivali_netta': cat_rows[cls]['stivali (permanente)'] - s['rimborso_stivali'],
        'spesa_pozioni': cat_rows[cls]['pozione (riutilizzabile, cooldown 40 s)'],
        'spesa_altro': cat_rows[cls]['scommessa (token)'] + cat_rows[cls]['consumabile (evocazione)'] + cat_rows[cls]['hex (potenzia un oggetto)'],
        'prestiti_dati': dato, 'prestiti_ricevuti': ricevuto,
        'rimborsi_ricevuti': s['rimborso_prestito_ricevuto'], 'rimborsi_pagati': -s['rimborso_prestito_pagato'],
        'correzioni_screenshot_totali': s['correzione_screenshot'],
        'oro_medio_fine_round_misurato': round(statistics.mean(post)),
        'oro_max_fine_round_misurato': max(post),
        'oro_dopo_ch19_misurato': last_post19, 'oro_durante_boss_misurato': boss,
        'oro_alla_sconfitta_misurato': fine[0] if fine else '',
        'oro_residuo_su_entrate_pct': round(100 * boss / entrate, 1) if entrate else '',
        'permanenza_media_oro_s_little': round(perm), 'ritardo_medio_fifo_s': round(fifo),
        'acquisti_rifiutati_simulati': sum(1 for f in A['failed'] if f['classe'] == cls),
    })
cols_bil = list(bil[0].keys())
wcsv('bilancio_oro_classi.csv', bil, cols_bil)

# per ruolo
ruoli = OrderedDict()
for r in ('Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza'):
    rr = [b for b in bil if b['ruolo'] == r]
    row = {'ruolo': r, 'n_classi': len(rr)}
    for k in cols_bil[2:]:
        vals = [b[k] for b in rr if b[k] != '']
        row[k] = round(statistics.mean(vals), 1) if vals else ''
    ruoli[r] = row
wcsv('bilancio_oro_ruoli.csv', list(ruoli.values()), ['ruolo', 'n_classi'] + cols_bil[2:])

# per round: oro misurato a fine round, entrate del round, quota non spesa
pr = []
for (sid, ts, cc, ph), d in snap_list:
    if ph != 'post':
        continue
    for cls in CLASSES:
        pr.append({'challenge': cc, 'classe': cls, 'ruolo': roles[cls], 'oro_misurato': d[cls][0], 'livello': d[cls][1]})
wcsv('oro_fine_round_misurato.csv', pr, ['challenge', 'classe', 'ruolo', 'oro_misurato', 'livello'])

# acquisti doppi / ridondanti
acq = [l for l in A['ledger'] if l['tipo'] == 'acquisto' and l['importo'] < 0]
red = []
seen = defaultdict(list)
for l in acq:
    code = l['dettaglio'].split(' ')[0]
    seen[(l['classe'], code)].append(l)
for (cls, code), ls in seen.items():
    name, price, lum, icla = item_info(code)
    if len(ls) > 1 and code not in TOMES:
        red.append({'classe': cls, 'ruolo': roles[cls], 'codice': code, 'oggetto': name, 'acquisti': len(ls),
                    'tempi_s': ' '.join(str(round(x['t'])) for x in ls), 'oro_speso': price * len(ls),
                    'nota': 'pozioni con lo stesso gruppo di cooldown (A02E): la seconda copia non aggiunge usi' if code in POTIONS
                    else ('evocazione consumabile: due copie = due evocazioni (non necessariamente ridondante)' if code == 'I05S'
                          else 'oggetto Unique: la seconda copia non somma l\'effetto unico')})
# cambi di stivali (perdita 25%)
for cls in CLASSES:
    bs = [l for l in acq if l['classe'] == cls and l['dettaglio'].split(' ')[0] in BOOTS]
    if len(bs) > 1:
        persi = 0
        for a, b in zip(bs, bs[1:]):
            persi += -a['importo'] - int(-a['importo'] * .75)
        red.append({'classe': cls, 'ruolo': roles[cls], 'codice': 'stivali', 'oggetto': ' -> '.join(item_info(x['dettaglio'].split(' ')[0])[0] for x in bs),
                    'acquisti': len(bs), 'tempi_s': ' '.join(str(round(x['t'])) for x in bs), 'oro_speso': persi,
                    'nota': 'cambio stivali: oro perso = 25% del prezzo dei vecchi'})
wcsv('acquisti_ridondanti.csv', red, ['classe', 'ruolo', 'codice', 'oggetto', 'acquisti', 'tempi_s', 'oro_speso', 'nota'])

# riepilogo stampato
print('voto stimato ch8 =', best8, ' ch12 =', best12)
vp = [v for v in val if v['fase'] == 'post']
ab = [abs(v['scarto']) for v in vp]
print('validazione ancorata: n=%d, esatti=%d, |scarto| mediano=%s, medio=%.1f, max=%d' % (
    len(ab), sum(1 for x in ab if x == 0), statistics.median(ab), statistics.mean(ab), max(ab)))
for b in bil:
    print(b['classe'], b['entrate_totali_stimate'], b['spesa_netta_acquisti'], b['oro_durante_boss_misurato'],
          b['permanenza_media_oro_s_little'], b['ritardo_medio_fifo_s'], b['prestiti_dati'], b['prestiti_ricevuti'],
          b['correzioni_screenshot_totali'], b['acquisti_rifiutati_simulati'])

# ---------------------------------------------------------------- sensibilita' sui prezzi
# Indizio: alcune classi chiedono in prestito esattamente quanto manca a 25 (Survival Treads) o a 75
# (Wizard's Potion) e poi usano la pozione: i prezzi effettivi potrebbero essere piu' bassi di quelli
# del w3t. Variante "prezzi_osservati" (IPOTESI, causa non trovata nel codice).
_orig_item_info = item_info
VARIANTE = {'I06Z': 25, 'I00R': 75, 'I00Q': 75, 'I00W': 187}


def _ii_var(code):
    n, p, l, c = _orig_item_info(code)
    return n, VARIANTE.get(code, p), l, c


def _stats(res):
    ab = [abs(v['scarto']) for v in res['validation'] if v['fase'] == 'post']
    tot = defaultdict(int)
    for v in res['validation']:
        if v['fase'] == 'post':
            tot[v['challenge_completate']] += v['scarto']
    return {'n_confronti': len(ab), 'esatti': sum(1 for x in ab if x == 0),
            'entro_25': sum(1 for x in ab if x <= 25), 'scarto_ass_mediano': statistics.median(ab),
            'scarto_ass_medio': round(statistics.mean(ab), 1), 'scarto_ass_max': max(ab),
            'somma_scarti_squadra': sum(tot.values()), 'acquisti_rifiutati': len(res['failed'])}


sens = [dict(variante='prezzi del w3t (base)', **_stats(A))]
item_info = _ii_var
sens.append(dict(variante='prezzi_osservati (ipotesi: treads 25, pozioni 75, rage 187)',
                 **_stats(run(anchor=True, ch8_grade=best8, ch12_grade=best12))))
item_info = _orig_item_info
wcsv('validazione_sintesi.csv', sens, ['variante', 'n_confronti', 'esatti', 'entro_25', 'scarto_ass_mediano',
                                       'scarto_ass_medio', 'scarto_ass_max', 'somma_scarti_squadra', 'acquisti_rifiutati'])
print(sens)

# acquisti "rifiutati" dalla simulazione ma con uso successivo osservato (=> in realta' riusciti)
uso = {(r['classe'], r['pozione_attribuita'][-5:-1]): r for r in rcsv(P('data_analysis', 'v2', 'cure', 'uso_pozioni_slot.csv'))
       if r['pozione_attribuita']}
for f in A['failed']:
    u = uso.get((f['classe'], f['codice']))
    f['uso_successivo_osservato'] = ('si (primo uso %s s)' % u['primo_uso_s']) if u else ''
wcsv('acquisti_rifiutati_simulati.csv', A['failed'], ['t', 'classe', 'ruolo', 'codice', 'oggetto', 'prezzo', 'oro_simulato',
                                                      'uso_successivo_osservato'])

# prestiti per coppia di ruoli
pr2 = defaultdict(lambda: [0, 0])
for L in A['loans']:
    k = (L['ruolo_creditore'], L['ruolo_debitore'])
    pr2[k][0] += 1
    pr2[k][1] += L['importo']
wcsv('prestiti_per_ruolo.csv', [{'ruolo_creditore': k[0], 'ruolo_debitore': k[1], 'n_prestiti': v[0], 'oro_stimato': v[1]}
                                for k, v in sorted(pr2.items())], ['ruolo_creditore', 'ruolo_debitore', 'n_prestiti', 'oro_stimato'])

# tomi: primo acquisto vs primo screenshot con livello >= 12
tomi = []
for cls in CLASSES:
    first12 = next((ts for (sid, ts, cc, ph), d in snap_list if (d.get(cls, (None, None))[1] or 0) >= 12), None)
    tb = [l['t'] for l in A['ledger'] if l['classe'] == cls and l['tipo'] == 'acquisto' and l['dettaglio'].split(' ')[0] in TOMES]
    oro12 = [d[cls][0] for (sid, ts, cc, ph), d in snap_list if ph == 'post' and first12 is not None and first12 <= ts < (tb[0] if tb else 1e9)]
    tomi.append({'classe': cls, 'ruolo': roles[cls], 'livello12_dal_s': first12, 'primo_tomo_s': round(tb[0]) if tb else '',
                 'attesa_s': round(tb[0] - first12) if tb and first12 else '', 'tomi_comprati': len(tb),
                 'oro_medio_fine_round_nell_attesa': round(statistics.mean(oro12)) if oro12 else ''})
wcsv('tomi_attesa.csv', tomi, ['classe', 'ruolo', 'livello12_dal_s', 'primo_tomo_s', 'attesa_s', 'tomi_comprati',
                               'oro_medio_fine_round_nell_attesa'])
for t_ in tomi:
    print(t_)
