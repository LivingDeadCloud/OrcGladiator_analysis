"""Domanda 03 - Ha senso far acquistare prima gli oggetti a healer, tank o DPS?

Eseguire dalla cartella del progetto:
    python data_analysis/v2/domande/03_priorita_acquisti_ruolo/analisi_priorita_acquisti.py

Ricostruisce (senza nomi di giocatori negli output):
  1. cronologia degli acquisti (ordini I0.. nel replay) con costo letto da war3map.w3t;
  2. spesa d'oro per ruolo e per fase (prima di ogni challenge);
  3. prestiti -borrow/-loan dalla chat, con la meccanica del war3map.j;
  4. bilancio dell'oro per classe (entrate dal codice + rounds.csv) confrontato con l'oro
     visto negli screenshot: serve a verificare che gli ordini di acquisto siano acquisti reali;
  5. colli di bottiglia per challenge (voto, oro perso rispetto ad A+, eroi <=20% HP);
  6. quote del ruolo prima/dopo gli acquisti grandi (stima, molto confusa).
"""
import csv, os, re, sys, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
sys.path.insert(0, ROOT)
import objdata  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
P = lambda *a: os.path.join(ROOT, *a)


def rcsv(path):
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def wcsv(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print('scritto', name, len(rows), 'righe')


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- dati di base
roles = rcsv(P('data_map', 'class_roles.csv'))
P2C = {r['player']: r['classe'] for r in roles}          # solo uso interno
C2R = {r['classe']: r['ruolo'] for r in roles}
CLASSI = [r['classe'] for r in roles]
RUOLI = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']

win = {int(r['challenge']): (float(r['inizio_s']), float(r['fine_s']), r['fonte'])
       for r in rcsv(P('data_analysis', 'v2', 'abilita_mana', 'finestre_combattimento.csv'))}

rounds = {int(r['challenge']): r for r in rcsv(P('data_screenshots', 'rounds.csv'))}
snaps = rcsv(P('data_screenshots', 'multiboard_snapshots.csv'))

wts = objdata.parse_wts(open(P('data_map', 'raw', 'war3map.wts'), 'rb').read())
items = objdata.parse_obj(open(P('data_map', 'raw', 'war3map.w3t'), 'rb').read(), 'w3t', wts)


def item_info(code):
    m = items.get(code, {}).get('mods', {})
    return (objdata.clean(m.get(('unam', 0), code)), m.get(('igol', 0)), m.get(('ilum', 0)),
            objdata.clean(m.get(('utub', 0), '')))


def fase(t):
    """Restituisce (challenge di riferimento, 'durante'/'prima')."""
    for n in sorted(win):
        a, b, _ = win[n]
        if a <= t <= b:
            return n, 'durante'
        if t < a:
            return n, 'prima'
    return 21, 'dopo la fine'


# livello per classe agli screenshot (per i tomi: richiedono livello 12, altrimenti rimborso 110)
lev = collections.defaultdict(list)
for s in snaps:
    if s['level']:
        lev[P2C[s['player']]].append((float(s['game_time_s']), float(s['level'])))


def livello(classe, t):
    pts = sorted(lev[classe])
    prev = None
    for tt, lv in pts:
        if tt >= t:
            if prev is None:
                return lv
            t0, l0 = prev
            return l0 + (lv - l0) * (t - t0) / (tt - t0) if tt > t0 else lv
        prev = (tt, lv)
    return pts[-1][1]


# ---------------------------------------------------------------- 1. acquisti
BOOT_PREFIX = 'Purchase '
acq = []
last_boot = {}
for r in rcsv(P('data_replay', 'actions_named.csv')):
    o = r['order']
    if r['kind'] != 'order_notarget' or not re.fullmatch(r'I0[0-9A-Z]{2}', o or ''):
        continue
    classe = P2C.get(r['player'])
    if not classe:
        continue
    t = int(r['game_time_ms']) / 1000
    nome, gold, lum, desc = item_info(o)
    nota = ''
    if nome.startswith('Arena Teleport'):
        cat = 'teletrasporto (gratis)'
    elif nome == 'Ancestral Strength':
        cat = 'pietra ancestrale (gratis, rianima)'
    elif lum:
        cat = 'talento (punti talento, non oro)'
    elif nome.startswith('Tome'):
        cat = 'tomo statistiche'
    elif 'Potion' in nome:
        cat = 'pozione'
    elif nome.startswith(BOOT_PREFIX):
        cat = 'stivali'
    else:
        cat = 'oggetto permanente'
    costo = gold if isinstance(gold, int) else None
    if cat.startswith('teletrasporto') or cat.startswith('pietra') or cat.startswith('talento'):
        costo = 0
    netto = costo
    lv = livello(classe, t)
    if cat == 'tomo statistiche' and lv < 12:
        nota = f'livello stimato {lv:.1f} < 12: il trigger Tomes_Buy rimborsa 110 (costo netto 0)'
        netto = 0
    if cat == 'stivali' and costo is not None:
        if classe in last_boot:
            rimborso = int(last_boot[classe] * 0.75)
            netto = costo - rimborso
            nota = f'rimborso 75% stivali precedenti ({rimborso}) dal trigger Boots_Upgrade'
        last_boot[classe] = costo
    if costo is None:
        nota = 'costo non presente nella mappa (campo igol assente): non determinabile'
    n, quando = fase(t)
    acq.append(dict(tempo_s=round(t, 1), challenge_rif=n, momento=quando, classe=classe, ruolo=C2R[classe],
                    codice=o, oggetto=nome, categoria=cat, costo_oro=costo if costo is not None else '',
                    costo_netto_stimato=netto if netto is not None else '', punti_talento=lum or 0,
                    livello_stimato=round(lv, 1), nota=nota,
                    effetto_sintetico=desc[:160]))
acq.sort(key=lambda x: x['tempo_s'])
wcsv('acquisti_cronologia.csv', acq,
     ['tempo_s', 'challenge_rif', 'momento', 'classe', 'ruolo', 'codice', 'oggetto', 'categoria', 'costo_oro',
      'costo_netto_stimato', 'punti_talento', 'livello_stimato', 'nota', 'effetto_sintetico'])

oro_acq = [a for a in acq if isinstance(a['costo_netto_stimato'], int) and a['costo_netto_stimato'] > 0]

# ---------------------------------------------------------------- 2. spesa per ruolo e fase
spesa = collections.defaultdict(float)   # (ruolo, n) -> oro netto
for a in oro_acq:
    spesa[(a['ruolo'], a['challenge_rif'])] += a['costo_netto_stimato']
ncl = collections.Counter(C2R[c] for c in CLASSI)
tot_ruolo = {ru: sum(v for (r2, _), v in spesa.items() if r2 == ru) for ru in RUOLI}
rows = []
cum = collections.defaultdict(float)
for n in range(1, 22):
    tot_n = sum(spesa[(ru, n)] for ru in RUOLI)
    for ru in RUOLI:
        cum[ru] += spesa[(ru, n)]
        rows.append(dict(spesa_entro_challenge=n if n <= 20 else 'dopo 20', ruolo=ru, n_classi=ncl[ru],
                         oro_speso=round(spesa[(ru, n)]), oro_speso_per_classe=round(spesa[(ru, n)] / ncl[ru]),
                         quota_spesa_fase_pct=round(100 * spesa[(ru, n)] / tot_n, 1) if tot_n else '',
                         oro_cumulato=round(cum[ru]), oro_cumulato_per_classe=round(cum[ru] / ncl[ru]),
                         pct_della_spesa_totale_del_ruolo=round(100 * cum[ru] / tot_ruolo[ru], 1) if tot_ruolo[ru] else ''))
wcsv('spesa_ruolo_per_challenge.csv', rows,
     ['spesa_entro_challenge', 'ruolo', 'n_classi', 'oro_speso', 'oro_speso_per_classe', 'quota_spesa_fase_pct',
      'oro_cumulato', 'oro_cumulato_per_classe', 'pct_della_spesa_totale_del_ruolo'])

# riepilogo per classe: tempi della spesa
rows = []
for c in CLASSI:
    mine = [a for a in oro_acq if a['classe'] == c]
    tot = sum(a['costo_netto_stimato'] for a in mine)
    half = None
    run = 0
    for a in mine:
        run += a['costo_netto_stimato']
        if half is None and run >= tot / 2:
            half = a['challenge_rif']
    grandi = [a for a in mine if a['costo_netto_stimato'] >= 400]
    perm = sum(a['costo_netto_stimato'] for a in mine if a['categoria'] in ('oggetto permanente', 'stivali'))
    tomi = sum(a['costo_netto_stimato'] for a in mine if a['categoria'] == 'tomo statistiche')
    poz = sum(a['costo_netto_stimato'] for a in mine if a['categoria'] == 'pozione')
    rows.append(dict(classe=c, ruolo=C2R[c], oro_speso_netto=tot, oro_oggetti_e_stivali=perm, oro_tomi=tomi,
                     oro_pozioni=poz, n_acquisti_con_oro=len(mine),
                     challenge_meta_spesa=half or '',
                     primo_acquisto_grande=(f"{grandi[0]['oggetto']} ({grandi[0]['costo_netto_stimato']}) prima della ch. {grandi[0]['challenge_rif']}" if grandi else ''),
                     acquisti_grandi=' ; '.join(f"ch{a['challenge_rif']}:{a['oggetto']}({a['costo_netto_stimato']})" for a in grandi),
                     acquisti_costo_ignoto=sum(1 for a in acq if a['classe'] == c and a['costo_oro'] == '')))
rows.sort(key=lambda r: RUOLI.index(r['ruolo']))
wcsv('spesa_classe_riepilogo.csv', rows,
     ['classe', 'ruolo', 'oro_speso_netto', 'oro_oggetti_e_stivali', 'oro_tomi', 'oro_pozioni', 'n_acquisti_con_oro',
      'challenge_meta_spesa', 'primo_acquisto_grande', 'acquisti_grandi', 'acquisti_costo_ignoto'])
spesa_classe = {r['classe']: r for r in rows}

# ---------------------------------------------------------------- 3. prestiti
chat = sorted(rcsv(P('data_replay', 'chat.csv')), key=lambda r: int(r['game_time_ms']))
prest = []
cur = None
for r in chat:
    msg = r['message']
    t = int(r['game_time_ms']) / 1000
    c = P2C.get(r['player'])
    if not c:
        continue
    if cur and t > cur['t0'] + 15.5:
        cur['esito_stimato'] = cur['esito_stimato'] or 'scaduta senza prestiti validi'
        prest.append(cur)
        cur = None
    m = re.fullmatch(r'-borrow (.{1,4})', msg)
    if m and msg == '-borrow ' + msg[8:12]:
        amt = num(m.group(1).strip())
        if cur is None and amt and amt > 0:
            n, quando = fase(t)
            cur = dict(tempo_s=round(t, 1), challenge_rif=n, momento=quando, richiedente=c,
                       ruolo_richiedente=C2R[c], importo_richiesto=int(amt), t0=t,
                       prestatori=[], esito_stimato='', nota='')
            if m.group(1) != m.group(1).strip():
                cur['nota'] = 'importo con spazio iniziale: S2I(" 41") assunto = 41 (ipotesi)'
        continue
    m = re.fullmatch(r'-loan( (.{1,4}))?', msg)
    if m and cur and c != cur['richiedente']:
        val = num(m.group(2)) if m.group(2) else 0
        cur['prestatori'].append((c, val))
        # con "-loan" senza importo il prestatore copre tutto il residuo se ha oro (Func014C/018C)
        if not cur['esito_stimato']:
            cur['esito_stimato'] = 'coperto (se il primo prestatore aveva oro sufficiente)' if not val or val >= cur['importo_richiesto'] else 'parziale'
if cur:
    prest.append(cur)
rows = []
for p in prest:
    rows.append(dict(tempo_s=p['tempo_s'], challenge_rif=p['challenge_rif'], momento=p['momento'],
                     richiedente=p['richiedente'], ruolo_richiedente=p['ruolo_richiedente'],
                     importo_richiesto=p['importo_richiesto'],
                     primo_prestatore=p['prestatori'][0][0] if p['prestatori'] else '',
                     ruolo_primo_prestatore=C2R[p['prestatori'][0][0]] if p['prestatori'] else '',
                     n_comandi_loan=len(p['prestatori']),
                     esito_stimato=p['esito_stimato'] or 'scaduta senza prestiti validi', nota=p['nota']))
wcsv('prestiti.csv', rows,
     ['tempo_s', 'challenge_rif', 'momento', 'richiedente', 'ruolo_richiedente', 'importo_richiesto',
      'primo_prestatore', 'ruolo_primo_prestatore', 'n_comandi_loan', 'esito_stimato', 'nota'])
prestiti_rows = rows

# ---------------------------------------------------------------- 4. bilancio oro per classe
# entrate per challenge N (dal codice Run_Reward / Get_MVP_Current_Round, con CurrentWave-1 = N):
#   vittoria 10*N a tutti; bonus voto (rounds.csv grade_gold) a tutti; premio R2I(2.5*N) a migliore danni/tank/boss/cure
#   (+ eventuale bonus "random gold" 2*N per chi ha scelto l'eroe a caso: non verificabile -> residuo)
VOTO_FRAZ = {'A+': 1, 'A': .75, 'B': .5, 'C': .4, 'D': .3, 'E': .2, 'F': .1, 'G': 0}


def voto_da_secondi(s):
    for lim, v in ((40, 'A+'), (80, 'A'), (120, 'B'), (160, 'C'), (200, 'D'), (240, 'E'), (280, 'F')):
        if s <= lim:
            return v
    return 'G'


rows_ch = []
entr = collections.defaultdict(lambda: collections.defaultdict(float))  # classe -> n -> oro
for n in range(1, 20):
    r = rounds[n]
    vitt = 10 * n
    voto = r['grade']
    stim = ''
    if r['grade_gold']:
        gg = int(r['grade_gold'])
    else:
        sec = win[n][1] - win[n][0]
        voto = voto or voto_da_secondi(sec)
        gg = int(vitt * VOTO_FRAZ[voto])
        stim = f'voto/bonus stimati da durata stimata {sec:.0f}s'
    if not r['grade'] and not r['grade_gold']:
        voto = voto_da_secondi(win[n][1] - win[n][0])
    premio = int(2.5 * n)
    scav = int(r['scavenger_bonus']) if r.get('scavenger_bonus') else (2 * n if n >= 7 else 0)
    # ScavengerGoldBonus (End_of_Round_Effects): (CurrentWave-1)*2 a TUTTI i giocatori, attivo dal talento/livello del Pickaxe;
    # dalla challenge 7 secondo rounds.csv (per 12 e 19, non visibili, si assume 2*N)
    for c in CLASSI:
        entr[c][n] += vitt + gg + scav
    for col in ('best_damage', 'best_tank', 'best_boss_slayer', 'best_healer'):
        if r.get(col):
            entr[P2C[r[col]]][n] += premio
    rows_ch.append(dict(challenge=n, voto=voto, oro_vittoria=vitt, oro_bonus_voto=gg, oro_scavenger=scav, oro_bonus_max_Aplus=vitt,
                        oro_perso_vs_Aplus_per_giocatore=vitt - gg, oro_perso_vs_Aplus_team=10 * (vitt - gg),
                        nota=stim))
for r in rcsv(P('data_screenshots', 'stat_choices.csv')):
    g = sum(int(x) for x in re.findall(r'\+(\d+) Gold', r['choice']))
    if g:
        entr[P2C[r['player']]][int(r['after_challenge'])] += g

# residuo: oro_osservato - (entrate_cum - spesa_cum)  -> prestiti, rimborsi, scavenger, bonus random, acquisti falliti
bil = []
for s in snaps:
    if s['phase'] != 'post' or s['gold'] == '':
        continue
    c = P2C[s['player']]
    t = float(s['game_time_s'])
    n = int(s['challenges_completed'])
    e = sum(v for k, v in entr[c].items() if k <= n)
    sp = sum(a['costo_netto_stimato'] for a in oro_acq if a['classe'] == c and a['tempo_s'] <= t)
    bil.append(dict(classe=c, ruolo=C2R[c], dopo_challenge=n, entrate_stimate_cum=round(e), spesa_ordini_cum=round(sp),
                    oro_atteso=round(e - sp), oro_osservato=int(float(s['gold'])),
                    residuo=round(float(s['gold']) - (e - sp))))
wcsv('bilancio_oro_classe.csv', bil,
     ['classe', 'ruolo', 'dopo_challenge', 'entrate_stimate_cum', 'spesa_ordini_cum', 'oro_atteso', 'oro_osservato', 'residuo'])

# ---------------------------------------------------------------- 5. colli di bottiglia per challenge
rc = rcsv(P('data_analysis', 'v2', 'aggregato', 'ruolo_challenge.csv'))
by = collections.defaultdict(dict)
for r in rc:
    by[int(r['challenge'])][r['ruolo']] = r
cc = rcsv(P('data_analysis', 'v2', 'aggregato', 'classe_challenge.csv'))
sotto = collections.defaultdict(list)
for r in cc:
    h = num(r['hp_fine_round'])
    if h is not None and h <= 20:
        sotto[int(r['challenge'])].append(r['ruolo'])
out = []
chmap = {r['challenge']: r for r in rows_ch}
for n in range(1, 21):
    t = by[n]['Tank']
    row = dict(challenge=n, tipo_wave=t['tipo_wave'], secondi=t['secondi_round'], voto=t['voto_round'],
               oro_perso_vs_Aplus_team=chmap[n]['oro_perso_vs_Aplus_team'] if n in chmap else '',
               eroi_hp_le20=len(sotto[n]),
               ruoli_hp_le20=' + '.join(f'{k} x{v}' for k, v in collections.Counter(sotto[n]).items()),
               healer_hp_fine=by[n]['Healer']['hp_fine_round_medio'],
               colpi_eroe_quota_ruolo_Tank=t['colpi_eroe_quota_round'],
               colpi_eroe_quota_DPS_mischia=by[n]['DPS mischia']['colpi_eroe_quota_round'],
               cure_quota_Healer=by[n]['Healer']['cure_quota_round'],
               danni_quota_DPS_totale=round((num(by[n]['DPS mischia']['danni_quota_round']) or 0) +
                                            (num(by[n]['DPS distanza']['danni_quota_round']) or 0), 1),
               mana_Healer_pct_20_80=by[n]['Healer']['mana_pct_20_80_medio'],
               spesa_team_prima=round(sum(spesa[(ru, n)] for ru in RUOLI)))
    out.append(row)
wcsv('colli_bottiglia_challenge.csv', out, list(out[0].keys()))

# ---------------------------------------------------------------- 6. quote prima/dopo acquisti grandi (stima)
METR = {'Tank': 'colpi_eroe_quota_round', 'Healer': 'cure_quota_round', 'Support': 'cure_quota_round',
        'DPS mischia': 'danni_quota_round', 'DPS distanza': 'danni_quota_round'}
qc = collections.defaultdict(dict)
for r in cc:
    qc[r['classe']][int(r['challenge'])] = r
eff = []
for a in oro_acq:
    if a['costo_netto_stimato'] < 400 or a['categoria'] not in ('oggetto permanente', 'stivali'):
        continue
    c, n = a['classe'], a['challenge_rif']
    m = METR[a['ruolo']]
    first = n if a['momento'] == 'prima' else n + 1
    pre = [num(qc[c][k][m]) for k in range(first - 3, first) if k in qc[c] and k <= 19 and num(qc[c][k][m]) is not None]
    post = [num(qc[c][k][m]) for k in range(first, first + 3) if k in qc[c] and k <= 19 and num(qc[c][k][m]) is not None]
    mp = sum(pre) / len(pre) if pre else None
    mq = sum(post) / len(post) if post else None
    eff.append(dict(classe=c, ruolo=a['ruolo'], oggetto=a['oggetto'], costo_netto=a['costo_netto_stimato'],
                    primo_round_con_oggetto=first, metrica=m, media_3_round_prima=round(mp, 1) if mp is not None else '',
                    media_3_round_dopo=round(mq, 1) if mq is not None else '',
                    differenza=round(mq - mp, 1) if mp is not None and mq is not None else '',
                    n_prima=len(pre), n_dopo=len(post)))
wcsv('effetto_acquisti_grandi.csv', eff, list(eff[0].keys()) if eff else ['classe'])

# ---------------------------------------------------------------- stampa sintesi
print('\nSpesa netta per ruolo (oro):')
for ru in RUOLI:
    print(f'  {ru:13s} tot {tot_ruolo[ru]:6.0f}  per classe {tot_ruolo[ru] / ncl[ru]:6.0f}')
print('\nResiduo bilancio (|residuo| mediano per classe):')
for c in CLASSI:
    rs = sorted(abs(b['residuo']) for b in bil if b['classe'] == c)
    print(f'  {c:13s} mediana {rs[len(rs) // 2]:5d}  max {max(rs):5d}')
print('\nPrestiti:', len(prestiti_rows))
for p in prestiti_rows:
    print('  ', p['tempo_s'], 'ch', p['challenge_rif'], p['momento'], p['ruolo_richiedente'], p['richiedente'],
          p['importo_richiesto'], '<-', p['ruolo_primo_prestatore'], p['primo_prestatore'], p['esito_stimato'])
