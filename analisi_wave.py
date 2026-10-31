"""Analisi per tipo di wave (mischia / distanza / ibrida).

Eseguire dalla cartella del progetto:
    python analisi_wave.py

Legge:
  data_map/raw/war3map.j, war3map.w3u, war3map.wts  (composizione wave e unità modificate)
  Units/UnitWeapons.slk, Units/UnitBalance.slk dagli archivi del gioco (sola lettura)
  data_screenshots/rounds.csv, multiboard_snapshots.csv
  data_replay/player_round.csv, data_replay/chat.csv
  data_map/class_roles.csv
Scrive in data_analysis/v2/wave/ (CSV UTF-8 + NOTE.md scritta a parte).
Nessun output contiene nomi di giocatori: solo classe e ruolo.
"""
import csv, os, re, statistics as st, sys
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from objdata import parse_obj, parse_wts  # noqa: E402
from mpq import MPQ  # noqa: E402

RAW = os.path.join(ROOT, 'data_map', 'raw')
OUT = os.path.join(ROOT, 'data_analysis', 'v2', 'wave')
GAME = r"C:\Program Files (x86)\Warcraft III"
N_PLAYERS = 10            # giocatori in partita (PLAYINGPLAYERS) durante le wave 1-20
SOGLIA = 0.85             # quota HP (truppe) dello stesso tipo per dire "solo mischia"/"solo distanza"

SPAWN_POINTS = 3          # SpawnEast, SpawnNorth, SpawnWest


def rcsv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def wcsv(name, rows, cols):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in cols})
    print('scritto', name, len(rows), 'righe')


def r2(x, n=2):
    return None if x is None else round(x, n)


def mean(xs):
    xs = [x for x in xs if x is not None]
    return st.mean(xs) if xs else None


# ---------------------------------------------------------------- 1. JASS
def jass_functions():
    s = open(os.path.join(RAW, 'war3map.j'), encoding='latin-1').read()
    funcs = {m.group(1): m.group(2) for m in
             re.finditer(r'function (\w+) takes .*? returns \w+(.*?)endfunction', s, re.S)}
    return s, funcs


def wave_modifier_from_chat():
    """Il comando '-waves3' (solo giocatore 1) fissa Modes_WaveModifier=3."""
    for r in rcsv(os.path.join(ROOT, 'data_replay', 'chat.csv')):
        m = re.fullmatch(r'-waves([23])', r['message'].strip())
        if m and r['pid'] == '1':
            return int(m.group(1))
    return None


def preload_variants(body):
    """Divide Preload_Wave_N_Actions nelle varianti (blocchi che iniziano con SpawnSequence[1])."""
    head = {}
    m = re.search(r'set udg_SpawnAmount=(\d+)', body); head['amount'] = int(m.group(1))
    m = re.search(r'set udg_SpawnDelay=([\d.]+)', body); head['delay'] = float(m.group(1))
    variants, cur = [], None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith('set udg_SpawnSequence[1]='):
            cur = {'seq': {}, 'boss': {}, 'name': None, 'title': None}
            variants.append(cur)
        if cur is None:
            continue
        m = re.match(r"set udg_SpawnSequence\[(\d+)\]='(\w{4})'", line)
        if m: cur['seq'][int(m.group(1))] = m.group(2)
        m = re.match(r"set udg_SpawnBoss\[(\d+)\]='(\w{4})'", line)
        if m: cur['boss'][int(m.group(1))] = m.group(2)
        m = re.match(r'set udg_SpawnMultiboardInfo="(.*)"', line)
        if m: cur['name'] = m.group(1)
        m = re.match(r'set udg_SpawnString\[1\]="(.*)"', line)
        if m: cur['title'] = re.sub(r'\|c[0-9a-fA-F]{8}|\|r', '', m.group(1))
    return head, variants


def spawn_extras(funcs, n):
    """Unità create con id letterale in Spawn_Wave_N (boss multipli, elite), con condizioni sul n. giocatori."""
    body = funcs.get('Trig_Spawn_Wave_%d_Actions' % n, '')
    out, active = [], [True]
    uses_boss1 = 'udg_SpawnBoss[1]' in body
    for line in body.splitlines():
        line = line.strip()
        m = re.match(r'if\((\w+)\(\)\)then', line)
        if m:
            cond = funcs.get(m.group(1), '')
            mm = re.search(r'udg_PLAYINGPLAYERS>=(\d+)', cond)
            active.append(N_PLAYERS >= int(mm.group(1)) if mm else True)
            continue
        if line == 'endif':
            active.pop(); continue
        m = re.match(r"call CreateNUnitsAtLoc\((\d+),'(\w{4})'", line)
        if m and all(active):
            out.append((m.group(2), int(m.group(1))))
    return out, uses_boss1


# ---------------------------------------------------------------- dati unità
def read_slk(data):
    rows, y, hdr = defaultdict(dict), 0, {}
    for line in data.decode('latin-1').splitlines():
        if not line.startswith('C;'):
            continue
        parts = line.split(';')
        x, k = None, None
        for p in parts[1:]:
            if p[:1] == 'X': x = int(p[1:])
            elif p[:1] == 'Y': y = int(p[1:])
            elif p[:1] == 'K': k = p[1:]
        if k is None:
            continue
        k = k.strip('"')
        rows[y][x] = k
    hdr = rows.pop(1)
    out = {}
    for y, cells in rows.items():
        rec = {hdr.get(x, x): v for x, v in cells.items()}
        if 1 in cells:
            out[cells[1]] = rec
    return out


def load_base_slk():
    res = {}
    for name in ('UnitWeapons', 'UnitBalance', 'UnitUI'):
        for arc in ('War3Patch.mpq', 'War3x.mpq', 'war3.mpq'):
            p = os.path.join(GAME, arc)
            if not os.path.exists(p):
                continue
            d = MPQ(p).read('Units\\%s.slk' % name)
            if d:
                res[name] = read_slk(d); break
    return res


def unit_info(uid, w3u, slk):
    obj = w3u.get(uid)
    base = obj['base'] if obj else uid
    mods = {f: v for (f, _l), v in obj['mods'].items()} if obj else {}
    wb = slk['UnitWeapons'].get(base, {})
    bb = slk['UnitBalance'].get(base, {})
    src = []

    def get(field, slk_rec, col, conv=str):
        if field in mods:
            src.append(field); return conv(mods[field])
        v = slk_rec.get(col)
        if v in (None, '', '-', '_'):
            return None
        try:
            return conv(v)
        except ValueError:
            return None

    weaps_on = get('uaen', wb, 'weapsOn', lambda v: int(float(v)))
    w = {}
    for i in (1, 2):
        w[i] = {'gittata': get('ua%dr' % i, wb, 'rangeN%d' % i, lambda v: int(float(v))),
                'tipo_arma': get('ua%dw' % i, wb, 'weapTp%d' % i),
                'tipo_attacco': get('ua%dt' % i, wb, 'atkType%d' % i),
                'bersagli': get('ua%dg' % i, wb, 'targs%d' % i) or ''}
    hp = get('uhpm', bb, 'HP', lambda v: int(float(v)))
    name = mods.get('unam') or slk.get('UnitUI', {}).get(base, {}).get('name') or base
    proper = mods.get('upro')
    if isinstance(proper, str):
        proper = proper.split(',')[0]
        if proper.strip('?') == '':
            proper = None
    is_hero = uid[0].isupper()
    # armi attive: weapsOn bit 1 = arma 1, bit 2 = arma 2. Si considerano solo le armi che colpiscono
    # bersagli "ground" (gli eroi); se ce ne sono due, conta quella con gittata maggiore
    # (es. Furious Ancient: arma 2 a 5000 di gittata; Doom Guard: arma 2 solo contro alberi).
    if weaps_on is None:
        weaps_on = 1 if w[1]['gittata'] else 0
    cand = [i for i in (1, 2) if weaps_on & i and 'ground' in w[i]['bersagli'] and w[i]['tipo_arma'] not in (None, '_')]
    arma = max(cand, key=lambda i: w[i]['gittata'] or 0) if cand else None
    if arma is None:
        md = 'nessun attacco'
        g = ta = tat = None
    else:
        g, ta, tat = w[arma]['gittata'], w[arma]['tipo_arma'], w[arma]['tipo_attacco']
        # tipo arma 'normal' = colpo corpo a corpo; missile/instant/msplash/artillery... = a distanza
        md = 'mischia' if ta == 'normal' else 'distanza'
    if is_hero:
        hp = None   # HP dei boss: dipendono da livello, forza e ricerche R0xx scalate sui giocatori -> non stimati
    return {'unita_id': uid, 'id_base': base, 'nome_unita': re.sub(r'^\(\d+\)\s*|^\d+\s+', '', str(name)).strip(),
            'nome_proprio': proper, 'eroe': is_hero, 'hp_base': hp,
            'armi_attive': weaps_on, 'arma_usata': arma, 'gittata': g, 'tipo_arma': ta,
            'tipo_attacco': tat, 'mischia_distanza': md,
            'fonte': 'w3u(%s)+slk' % ','.join(sorted(set(src))) if src else 'slk base'}


# ---------------------------------------------------------------- PARTE 1
def parte1():
    s, funcs = jass_functions()
    wts = parse_wts(open(os.path.join(RAW, 'war3map.wts'), 'rb').read())
    w3u = parse_obj(open(os.path.join(RAW, 'war3map.w3u'), 'rb').read(), 'w3u', wts)
    slk = load_base_slk()
    rounds = {int(r['challenge']): r for r in rcsv(os.path.join(ROOT, 'data_screenshots', 'rounds.csv'))}
    modifier = wave_modifier_from_chat()
    # boss finale: creato dal trigger dopo la sconfitta dei "minion" della wave 20
    final_boss = re.search(r"CreateNUnitsAtLoc\(1,'(\w{4})',Player\(\$B\),udg_TEMP_POINT,270\.\)", s)
    final_boss = final_boss.group(1) if final_boss else None

    comp, tipo = [], []
    for n in range(1, 21):
        head, variants = preload_variants(funcs['Trig_Preload_Wave_%d_Actions' % n])
        if len(variants) == 1:
            vi = 1
        else:
            vi = modifier
        v = variants[vi - 1]
        units = Counter()
        for i in range(1, head['amount'] + 1):
            units[v['seq'][i]] += SPAWN_POINTS * N_PLAYERS
        extras, uses_boss1 = spawn_extras(funcs, n)
        bosses = Counter()
        if uses_boss1 and v['boss'].get(1):
            bosses[v['boss'][1]] += 1
        elite = Counter()
        for uid, q in extras:
            if uid[0].isupper():
                bosses[uid] += q
            else:
                elite[uid] += q
        if n == 20 and final_boss:
            bosses[final_boss] += 1
        rows = []
        for cat, cnt in (('truppa', units), ('elite', elite), ('boss', bosses)):
            for uid, q in cnt.items():
                info = unit_info(uid, w3u, slk)
                hp_tot = info['hp_base'] * q if (info['hp_base'] and cat != 'boss') else None
                rows.append(dict(info, challenge=n, ondata=v['name'], variante=vi, n_varianti=len(variants),
                                 categoria=cat, quantita=q,
                                 hp_totale=hp_tot))
        comp += rows
        # classificazione: truppe + elite (non boss)
        mob = [r for r in rows if r['categoria'] != 'boss']
        n_tot = sum(r['quantita'] for r in mob)
        hp_tot = sum(r['hp_totale'] or 0 for r in mob)
        q_u_m = sum(r['quantita'] for r in mob if r['mischia_distanza'] == 'mischia') / n_tot
        q_hp_m = sum(r['hp_totale'] or 0 for r in mob if r['mischia_distanza'] == 'mischia') / hp_tot
        q_hp_d = sum(r['hp_totale'] or 0 for r in mob if r['mischia_distanza'] == 'distanza') / hp_tot
        if q_hp_m >= SOGLIA:
            t = 'mischia'
        elif q_hp_d >= SOGLIA:
            t = 'distanza'
        else:
            t = 'ibrida'
        bl = [r for r in rows if r['categoria'] == 'boss']
        boss_tipo = '/'.join(sorted({r['mischia_distanza'] for r in bl})) if bl else ''
        etich = re.search(r'\((Melee|Ranged)\)', v['name'] or '')
        etich = {'Melee': 'mischia', 'Ranged': 'distanza'}[etich.group(1)] if etich else ''
        nome_csv = rounds[n]['wave']
        etich_csv = re.search(r'\((Melee|Ranged)\)', nome_csv)
        etich_csv = {'Melee': 'mischia', 'Ranged': 'distanza'}[etich_csv.group(1)] if etich_csv else ''
        if etich:
            conc = 'concorda' if etich == t else 'DISCREPANZA'
        else:
            conc = 'nessuna etichetta'
        note = []
        base_name = re.sub(r'\s*\(.*\)$', '', v['name'] or '')
        if not nome_csv.startswith(base_name) and nome_csv != '?':
            note.append('nome diverso da rounds.csv (%s)' % nome_csv)
        if nome_csv == '?':
            note.append('nome non leggibile nello screenshot: variante dedotta da -waves%d' % modifier)
        if etich and not etich_csv:
            note.append("l'etichetta (%s) c'e' nella mappa ma manca nella trascrizione" % etich)
        if t == 'ibrida':
            note.append('ibrida: mischia %.0f%% / distanza %.0f%% degli HP truppe' % (100 * q_hp_m, 100 * q_hp_d))
        tipo.append({'challenge': n, 'ondata': v['name'], 'ondata_rounds_csv': nome_csv,
                     'variante': '%d di %d' % (vi, len(variants)),
                     'etichetta_gioco': etich, 'n_unita': n_tot, 'hp_totale_truppe': hp_tot,
                     'quota_unita_mischia': r2(q_u_m, 3), 'quota_hp_mischia': r2(q_hp_m, 3),
                     'quota_hp_distanza': r2(q_hp_d, 3), 'tipo_wave': t,
                     'boss': '; '.join('%s%s (%s, gittata %s)' % (
                         r['nome_proprio'] or r['nome_unita'], '' if r['quantita'] == 1 else ' x%d' % r['quantita'],
                         r['mischia_distanza'], r['gittata']) for r in bl),
                     'tipo_boss': boss_tipo, 'confronto_etichetta': conc, 'note': '; '.join(note)})
    wcsv('wave_composizione.csv', comp,
         ['challenge', 'ondata', 'variante', 'n_varianti', 'categoria', 'unita_id', 'id_base', 'nome_unita',
          'nome_proprio', 'quantita', 'hp_base', 'hp_totale', 'armi_attive', 'arma_usata', 'gittata', 'tipo_arma',
          'tipo_attacco', 'mischia_distanza', 'fonte'])
    wcsv('wave_tipo.csv', tipo,
         ['challenge', 'ondata', 'ondata_rounds_csv', 'variante', 'etichetta_gioco', 'n_unita', 'hp_totale_truppe',
          'quota_unita_mischia', 'quota_hp_mischia', 'quota_hp_distanza', 'tipo_wave', 'boss', 'tipo_boss',
          'confronto_etichetta', 'note'])
    return {r['challenge']: r for r in tipo}


# ---------------------------------------------------------------- PARTE 2
VOTI = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7}
METRICHE = ['danni', 'boss', 'cure', 'tank']
COL = {'danni': 'dmg_pct', 'boss': 'boss_dmg_pct', 'cure': 'heal_pct', 'tank': 'tank_pct'}


def anonimizza(testo, roles):
    """Sostituisce i nomi dei giocatori (anche abbreviati, es. 'Boom') con la classe."""
    for p in sorted(roles, key=len, reverse=True):
        testo = testo.replace(p, roles[p]['classe'])
    return testo.replace('Boom', roles['BoomKhamenei']['classe'])


def parte2(tipi):
    roles = {r['player']: r for r in rcsv(os.path.join(ROOT, 'data_map', 'class_roles.csv'))}
    snaps = rcsv(os.path.join(ROOT, 'data_screenshots', 'multiboard_snapshots.csv'))
    rounds = {int(r['challenge']): r for r in rcsv(os.path.join(ROOT, 'data_screenshots', 'rounds.csv'))}
    pr = rcsv(os.path.join(ROOT, 'data_replay', 'player_round.csv'))

    # snapshot di fine challenge c (c=1..19: riga "post" con challenges_completed=c; c=20: ultima riga per giocatore)
    snap = defaultdict(dict)   # snap[c][player] = row
    tsnap = {}
    for r in snaps:
        if r['phase'] == 'post':
            c = int(r['challenges_completed'])
            snap[c][r['player']] = r; tsnap[c] = int(r['game_time_s'])
    last = {}
    for r in snaps:
        if r['phase'] in ('boss', 'sconfitta'):
            last[r['player']] = r            # le righe sono in ordine di tempo
    snap[20] = last
    tsnap[20] = max(int(r['game_time_s']) for r in snaps)
    players = list(roles)

    # Stima della quota per round. Le quote S_p(c) sono cumulative: S_p(c) = X_p(c) / X(c), con X(c) totale
    # cumulato del team (ignoto). Se W(c) e' un proxy proporzionale a X(c):
    #   A_p(c) = S_p(c)*W(c) - S_p(c-1)*W(c-1)   (contributo del round), negativi a 0, rinormalizzato a 100.
    # Proxy principale ("hp"): HP totali cumulati delle truppe delle wave (dal war3map.j/w3u): il danno del
    # team in un round e' circa gli HP dei nemici uccisi; si assume che cure e danni subiti crescano allo stesso modo.
    # Proxy alternativo ("tempo"): tempo di gioco cumulato allo screenshot (assume un ritmo costante: sovrastima
    # gli scarti nei round avanzati, quando il team fa molto piu' danno al secondo).
    hp_w = {0: 0.0}
    for c in range(1, 21):
        hp_w[c] = hp_w[c - 1] + float(tipi[c]['hp_totale_truppe'])
    t_w = {0: 0.0}
    for c in range(1, 21):
        t_w[c] = float(tsnap[c])

    def stima_con(W):
        out = defaultdict(dict)
        for c in range(1, 21):
            for m in METRICHE:
                raw = {}
                for p in players:
                    if p not in snap[c]:
                        raw[p] = None; continue
                    s1 = float(snap[c][p][COL[m]])
                    s0 = float(snap[c - 1][p][COL[m]]) if c > 1 else 0.0
                    raw[p] = max(0.0, s1 * W[c] - s0 * W[c - 1])
                tot = sum(v for v in raw.values() if v is not None)
                for p in players:
                    out[c].setdefault(p, {})[m] = (100 * raw[p] / tot) if (raw[p] is not None and tot > 0) else None
        return out

    stima = stima_con(hp_w)
    stima_t = stima_con(t_w)
    # amplificazione dell'errore di arrotondamento (0,05 punti) delle quote cumulative: W(c)/(W(c)-W(c-1))
    amplif = {c: hp_w[c] / (hp_w[c] - hp_w[c - 1]) for c in range(1, 21)}
    delta = defaultdict(dict)  # variazione della quota cumulativa (punti %), solo dal round 2
    for c in range(2, 21):
        for p in players:
            if p in snap[c]:
                delta[c][p] = {m: float(snap[c][p][COL[m]]) - float(snap[c - 1][p][COL[m]]) for m in METRICHE}

    act = {(r['player'], int(r['challenge'])): r for r in pr}

    # ---- tabella giocatore(classe) x round
    cr = []
    for c in range(1, 21):
        for p in players:
            a = act.get((p, c))
            sm = float(a['segment_minutes']) if a else None
            hp = snap[c][p]['hp_pct'] if p in snap[c] else None
            row = {'challenge': c, 'tipo_wave': tipi[c]['tipo_wave'], 'classe': roles[p]['classe'],
                   'ruolo': roles[p]['ruolo'], 'distanza_classe': roles[p]['distanza'],
                   'hp_fine_round': hp,
                   'sotto_20hp': (1 if hp is not None and int(hp) <= 20 else 0) if hp is not None else None}
            for m in METRICHE:
                row['%s_quota_round_stimata' % m] = r2(stima[c][p][m])
                row['%s_quota_round_tempo' % m] = r2(stima_t[c][p][m])
                d = delta[c].get(p, {}).get(m)
                row['%s_delta_quota_cum' % m] = r2(d)
            if a:
                row['minuti_segmento'] = sm
                row['apm'] = float(a['apm'])
                row['abilita_min'] = r2(int(a['ability']) / sm)
                row['oggetti_min'] = r2(int(a['item_use']) / sm)
                row['click_movimento_min'] = r2((int(a['rclick_ground']) + int(a['move_cmd'])) / sm)
            cr.append(row)
    cols_cr = ['challenge', 'tipo_wave', 'classe', 'ruolo', 'distanza_classe', 'hp_fine_round', 'sotto_20hp'] + \
              ['%s_quota_round_stimata' % m for m in METRICHE] + ['%s_quota_round_tempo' % m for m in METRICHE] + \
              ['%s_delta_quota_cum' % m for m in METRICHE] + \
              ['minuti_segmento', 'apm', 'abilita_min', 'oggetti_min', 'click_movimento_min']
    wcsv('classe_round.csv', cr, cols_cr)

    # ---- tabella round
    rr = []
    for c in range(1, 21):
        r = rounds[c]
        n20 = sum(1 for p in players if p in snap[c] and int(snap[c][p]['hp_pct']) <= 20)
        rr.append({'challenge': c, 'ondata': tipi[c]['ondata'], 'tipo_wave': tipi[c]['tipo_wave'],
                   'tipo_boss': tipi[c]['tipo_boss'],
                   'secondi': int(r['clear_seconds']) if r['clear_seconds'] else None,
                   'voto': r['grade'], 'voto_num': VOTI.get(r['grade']),
                   'eroi_hp_le20_snapshot': n20 if c <= 19 else None,
                   'hp_truppe_wave': tipi[c]['hp_totale_truppe'],
                   'peso_round_hp': r2(100 * (hp_w[c] - hp_w[c - 1]) / hp_w[c], 1),
                   'amplificazione_errore': r2(amplif[c], 1),
                   'note_rounds': anonimizza(r['notes'], roles),
                   'apm_team': r2(mean([float(act[(p, c)]['apm']) for p in players if (p, c) in act]), 1),
                   'click_movimento_min_team': r2(mean([(int(act[(p, c)]['rclick_ground']) + int(act[(p, c)]['move_cmd']))
                                                        / float(act[(p, c)]['segment_minutes']) for p in players if (p, c) in act]), 1)})
    wcsv('round_per_tipo.csv', rr, ['challenge', 'ondata', 'tipo_wave', 'tipo_boss', 'secondi', 'voto', 'voto_num',
                                    'eroi_hp_le20_snapshot', 'hp_truppe_wave', 'peso_round_hp', 'amplificazione_errore',
                                    'apm_team', 'click_movimento_min_team', 'note_rounds'])

    # ---- riepilogo per tipo (challenge 1-19; la 20 e' il boss finale, perso)
    TIPI = ['mischia', 'distanza', 'ibrida']
    rs = []
    for t in TIPI + ['tutte']:
        sel = [x for x in rr if x['challenge'] <= 19 and (t == 'tutte' or x['tipo_wave'] == t)]
        sec = [x['secondi'] for x in sel if x['secondi'] is not None]
        vv = [x['voto_num'] for x in sel if x['voto_num'] is not None]
        lo = [x['eroi_hp_le20_snapshot'] for x in sel]
        rs.append({'tipo_wave': t, 'n_wave': len(sel), 'challenge': ' '.join(str(x['challenge']) for x in sel),
                   'n_con_secondi': len(sec), 'secondi_media': r2(mean(sec), 0),
                   'secondi_mediana': r2(st.median(sec), 0) if sec else None,
                   'secondi_min': min(sec) if sec else None, 'secondi_max': max(sec) if sec else None,
                   'n_con_voto': len(vv), 'voto_medio_num': r2(mean(vv), 2),
                   'voti': ' '.join(x['voto'] for x in sel if x['voto_num']),
                   'eroi_hp_le20_media': r2(mean(lo), 2), 'eroi_hp_le20_totale': sum(lo),
                   'round_con_almeno_1_eroe_le20': sum(1 for x in lo if x > 0),
                   'apm_team_media': r2(mean([x['apm_team'] for x in sel]), 1),
                   'click_movimento_min_team_media': r2(mean([x['click_movimento_min_team'] for x in sel]), 1)})
    wcsv('riepilogo_tipo.csv', rs, ['tipo_wave', 'n_wave', 'challenge', 'n_con_secondi', 'secondi_media',
                                    'secondi_mediana', 'secondi_min', 'secondi_max', 'n_con_voto', 'voto_medio_num',
                                    'voti', 'eroi_hp_le20_media', 'eroi_hp_le20_totale',
                                    'round_con_almeno_1_eroe_le20', 'apm_team_media', 'click_movimento_min_team_media'])

    # ---- classe x tipo e ruolo x tipo (challenge 1-19)
    VAL = ['%s_quota_round_stimata' % m for m in METRICHE] + ['%s_quota_round_tempo' % m for m in METRICHE] + \
          ['%s_delta_quota_cum' % m for m in METRICHE] + \
          ['apm', 'abilita_min', 'click_movimento_min', 'sotto_20hp']
    base = [x for x in cr if x['challenge'] <= 19]

    def aggregate(key):
        out = []
        groups = sorted({x[key] for x in base})
        for g in groups:
            # per il ruolo: prima somma (quote) o media (attivita') sui giocatori del ruolo per ogni round
            per_round = defaultdict(lambda: defaultdict(list))
            for x in base:
                if x[key] == g:
                    for v in VAL:
                        per_round[x['challenge']][v].append(x.get(v))
            n_gioc = len({x['classe'] for x in base if x[key] == g})
            series = {}
            for c, d in per_round.items():
                series[c] = {}
                for v in VAL:
                    xs = [y for y in d[v] if y is not None]
                    if not xs:
                        series[c][v] = None
                    elif 'quota' in v or v == 'sotto_20hp':
                        series[c][v] = sum(xs)       # quota del gruppo = somma delle quote
                    else:
                        series[c][v] = st.mean(xs)   # attivita' media per giocatore
            allm = {v: mean([series[c][v] for c in series]) for v in VAL}
            for t in TIPI:
                cs = [c for c in series if tipi[c]['tipo_wave'] == t]
                row = {key: g, 'n_giocatori': n_gioc, 'tipo_wave': t, 'n_wave': len(cs)}
                if key == 'classe':
                    row['ruolo'] = next(x['ruolo'] for x in base if x['classe'] == g)
                for v in VAL:
                    vals = [series[c][v] for c in cs if series[c][v] is not None]
                    mu = mean(vals)
                    row[v] = r2(mu)
                    if v in ('sotto_20hp',):
                        row[v] = sum(vals) if vals else None
                    if not v.endswith('delta_quota_cum') and v != 'sotto_20hp':
                        row[v + '_min'] = r2(min(vals)) if vals else None
                        row[v + '_max'] = r2(max(vals)) if vals else None
                        row[v + '_rapporto_vs_tutte'] = r2(mu / allm[v]) if (mu is not None and allm[v]) else None
                out.append(row)
        return out

    extra = []
    for v in VAL:
        if not v.endswith('delta_quota_cum') and v != 'sotto_20hp':
            extra += [v + '_min', v + '_max', v + '_rapporto_vs_tutte']
    cols = ['tipo_wave', 'n_wave', 'n_giocatori'] + VAL + extra
    wcsv('classe_per_tipo.csv', aggregate('classe'), ['classe', 'ruolo'] + cols)
    wcsv('ruolo_per_tipo.csv', aggregate('ruolo'), ['ruolo'] + cols)
    return rr, rs


if __name__ == '__main__':
    tipi = parte1()
    for c, t in tipi.items():
        print(c, t['ondata'], t['tipo_wave'], t['quota_hp_mischia'], t['quota_unita_mischia'], '| boss:', t['boss'],
              '|', t['confronto_etichetta'], t['note'])
    parte2(tipi)
