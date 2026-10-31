"""Domanda 05 - Il posizionamento dei giocatori sulla mappa e' ottimale?

Uso (dalla cartella principale del progetto):
    python data_analysis/v2/domande/05_posizionamento/analisi_posizionamento.py

Cosa fa:
1. Rilegge il replay con il parser del progetto (w3g_parser.py, NON modificato) sostituendo in memoria
   la sola funzione che decodifica le azioni, per conservare due informazioni che actions.csv scarta:
   - l'ID oggetto e il tipo di unita' del "sottogruppo attivo" (azione 0x19), per sapere se il comando
     e' dato all'eroe o ad altre unita' (evocazioni, negozi, nemici selezionati per guardarli);
   - gli ID delle unita' selezionate (azione 0x16).
2. Ricava l'ID oggetto di ogni eroe e quindi riconosce gli ordini dati SU un eroe (cure, buff, click destro
   su alleato): le coordinate x,y di quegli ordini sono il punto cliccato sopra l'eroe = posizione MISURATA
   dell'eroe in quell'istante (ancora).
3. Stima la posizione di ogni eroe con "ultimo punto ordinato" (movimento a terra, bersaglio, abilita' a terra)
   e la valida contro le ancore (errore in unita' di gioco per fascia di "eta'" dell'ultimo ordine).
4. Calcola copertura, posizione per classe, distanze dal fronte (bersagli nemici cliccati), dispersione,
   distanze Tank-Healer/DPS distanza, per tipo di wave, e il confronto prudente con quota tank e HP<20%.
Output: CSV e posizioni.svg nella stessa cartella dello script. Nessun nome di giocatore.
"""
import bisect, csv, os, struct, sys, math, statistics as st
from collections import defaultdict, Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import w3g_parser as W  # noqa: E402

REPLAY = os.path.join(ROOT, 'replay_originali', 'orcgladiatorsbutei.w3g')
NULL_ID = 'FFFFFFFF-FFFFFFFF'
SPEED = 270.0      # velocita' base dell'eroe (unita' base Otch, UnitBalance.slk 'spd'; la mappa non la modifica)
OTCH_RANGE = 128.0  # gittata base Otch (UnitWeapons.slk 'rangeN1'), usata se war3map.w3u non modifica ua1r
AB_RANGE = 600.0   # IPOTESI: distanza di lancio tipica delle abilita' a terra (non letta dai dati)
HEAL_RANGE = 700.0  # gittata di Rejuvenation/Innervate (war3map.w3a, aran)
MAXAGE = 10.0      # eta' massima dell'ultimo ordine per usare la stima (scelta dalla validazione)

# --- geometria della mappa (war3map.j, Rect(minx,miny,maxx,maxy)) -------------------------------------------
RECTS = {
    'ArenaArea': (-3104, -1088, 2112, 4160),
    'SpawnEast': (3584, 1248, 4096, 1824),
    'SpawnNorth': (-800, 5632, -224, 6144),
    'SpawnWest': (-5120, 1248, -4608, 1824),
    'Region_014 (teletrasporto a inizio wave)': (-1376, 416, 256, 896),
    'GladiatorBlockHome (fontana, vietata in wave)': (-896, -3328, -160, -1312),
    'Boss_Spawn': (-608, 2912, -192, 3328),
}


def center(r):
    return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)


SPAWNS = {k: center(RECTS[k]) for k in ('SpawnEast', 'SpawnNorth', 'SpawnWest')}


def inside(r, x, y):
    return r[0] <= x <= r[2] and r[1] <= y <= r[3]


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


# --- parser esteso (copia di W.parse_actions con in piu' ID selezione e sottogruppo) --------------------------
def parse_actions_ext(a, pid, t, out):
    q = 0

    def add(kind, **kw):
        out.append({'time_ms': t, 'pid': pid, 'kind': kind, **kw})
    while q < len(a):
        aid = a[q]; q += 1
        if aid == 0x01: add('pause')
        elif aid == 0x02: add('resume')
        elif aid == 0x03: q += 1
        elif aid in (0x04, 0x05): pass
        elif aid == 0x06: _, q = W.read_cstr(a, q)
        elif aid == 0x07: q += 4
        elif aid == 0x10:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); q += 14
            add('order_notarget', order=W.order_name(oid), flags=flags)
        elif aid == 0x11:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); x, y = struct.unpack('<ff', a[q + 14:q + 22]); q += 22
            add('order_point', order=W.order_name(oid), flags=flags, x=x, y=y)
        elif aid == 0x12:
            flags, oid = struct.unpack('<HI', a[q:q + 6]); x, y = struct.unpack('<ff', a[q + 14:q + 22])
            o1, o2 = struct.unpack('<II', a[q + 22:q + 30]); q += 30
            add('order_target', order=W.order_name(oid), flags=flags, x=x, y=y, tid=f'{o1:08X}-{o2:08X}')
        elif aid == 0x13: q += 38
        elif aid == 0x14: q += 43
        elif aid == 0x16:
            mode, n = struct.unpack('<BH', a[q:q + 3])
            ids = []
            for i in range(n):
                o1, o2 = struct.unpack('<II', a[q + 3 + 8 * i:q + 11 + 8 * i]); ids.append(f'{o1:08X}-{o2:08X}')
            q += 3 + 8 * n; add('select', mode=mode, ids=ids)
        elif aid == 0x17:
            g, n = struct.unpack('<BH', a[q:q + 3]); q += 3 + 8 * n
        elif aid == 0x18: add('select_group'); q += 2
        elif aid == 0x19:
            it, o1, o2 = struct.unpack('<4sII', a[q:q + 12]); q += 12
            add('subgroup', utype=it[::-1].decode('latin-1'), oid=f'{o1:08X}-{o2:08X}')
        elif aid == 0x1A: pass
        elif aid in (0x1B, 0x1C): q += 9
        elif aid == 0x1D: q += 8
        elif aid == 0x1E: q += 5
        elif aid == 0x21: q += 8
        elif aid in (0x20, 0x22, 0x23, 0x24, 0x25, 0x26, 0x29, 0x2A, 0x2B, 0x2C, 0x2F, 0x30, 0x31, 0x32): pass
        elif aid in (0x27, 0x28, 0x2D, 0x50): q += 5
        elif aid == 0x2E: q += 4
        elif aid == 0x51: q += 9
        elif aid == 0x60:
            q += 8; _, q = W.read_cstr(a, q)
        elif aid in (0x61, 0x65, 0x66, 0x67): pass
        elif aid == 0x62: q += 12
        elif aid == 0x68: q += 12
        elif aid in (0x69, 0x6A): q += 16
        elif aid == 0x6B:
            _, q = W.read_cstr(a, q); _, q = W.read_cstr(a, q); _, q = W.read_cstr(a, q); q += 4
        elif aid == 0x75: q += 1
        else:
            add('unknown'); return


def load_replay():
    W.parse_actions = parse_actions_ext  # solo in memoria: il file w3g_parser.py non viene toccato
    meta, players, slots, actions, chat, leaves = W.parse(REPLAY)
    pauses, start = [], None
    for a in actions:
        if a['kind'] == 'pause' and start is None:
            start = a['time_ms']
        elif a['kind'] == 'resume' and start is not None:
            pauses.append((start, a['time_ms'])); start = None
    for a in actions:
        t = a['time_ms']
        a['t'] = (t - sum(min(t, e) - s for s, e in pauses if t > s)) / 1000.0
    return players, actions


def read_csv(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write_csv(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols); w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k in cols})


def med(v):
    return st.median(v) if v else None


def pct(v, q):
    if not v:
        return None
    s = sorted(v); k = (len(s) - 1) * q; i = int(k)
    return s[i] if i + 1 >= len(s) else s[i] + (s[i + 1] - s[i]) * (k - i)


def spearman(a, b):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v); i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = rank(a), rank(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def main():
    players, acts = load_replay()

    # --- classe di ogni pid (nomi usati solo in memoria per l'aggancio, mai scritti) -------------------------
    roles = {r['pick_code']: r for r in read_csv('data_map/class_roles.csv')}
    pick_by_name = {r['player']: r['pick_code'] for r in read_csv('data_map/classes.csv')}
    pid_pick = {pid: pick_by_name.get(n) for pid, n in players.items()}
    missing = [c for c in roles if c not in pid_pick.values()]
    unk = [p for p, c in pid_pick.items() if c is None]
    if len(missing) == 1 and len(unk) == 1:  # un nome con caratteri diversi tra i due file
        pid_pick[unk[0]] = missing[0]
    CL = {pid: roles[c]['classe'] for pid, c in pid_pick.items()}
    RU = {roles[c]['classe']: roles[c]['ruolo'] for c in roles}
    DI = {roles[c]['classe']: roles[c]['distanza'] for c in roles}
    ORDER = ['War Hammer', 'Runeblade', 'Druid Staff', 'War Drums', 'Claws', 'Double Blade', 'Pickaxe',
             'Bow', 'Wizard Staff', 'Naga Trident']

    # --- ID oggetto dell'eroe: l'ID piu' frequente nei sottogruppi attivi di tipo eroe ('O...') ------------
    sub = defaultdict(Counter)
    for a in acts:
        if a['kind'] == 'subgroup' and a['utype'].startswith('O') and a['utype'] != 'O000':
            sub[a['pid']][(a['utype'], a['oid'])] += 1
    HERO = {}  # pid -> (tipo, oid)
    for pid, c in sub.items():
        HERO[pid] = c.most_common(1)[0][0]
    OID2PID = {v[1]: pid for pid, v in HERO.items()}

    # --- finestre di combattimento e tipo di wave -------------------------------------------------------------
    win = [(int(r['challenge']), float(r['inizio_s']), float(r['fine_s']), r['fonte'])
           for r in read_csv('data_analysis/v2/abilita_mana/finestre_combattimento.csv')]
    tipo = {int(r['challenge']): r['tipo_wave'] for r in read_csv('data_analysis/v2/wave/wave_tipo.csv')}

    def challenge_at(t):
        for c, s, e, _ in win:
            if s <= t <= e:
                return c
        return None

    # --- gittata d'attacco degli eroi (war3map.w3u; se non modificata: Otch = 128 da UnitWeapons.slk) ---------
    import objdata
    w3u = objdata.parse_obj(open(os.path.join(ROOT, 'data_map', 'raw', 'war3map.w3u'), 'rb').read(), 'u')
    RANGE = {}
    for pid, (ut, _) in HERO.items():
        mods = {f: v for (f, _l), v in w3u.get(ut, {'mods': {}})['mods'].items()}
        RANGE[ut] = float(mods.get('ua1r', OTCH_RANGE))

    dr = defaultdict(list)  # pid -> [(t, stato)]; stato = (t0, x0, y0, xdest, ydest, distanza_di_arresto)

    def dr_state_where(s, t):
        t0, x0, y0, tx, ty, sd = s
        d = math.hypot(tx - x0, ty - y0)
        if d == 0:
            return (x0, y0)
        m = min(max(0.0, d - sd), SPEED * max(0.0, t - t0))
        return (x0 + (tx - x0) * m / d, y0 + (ty - y0) * m / d)

    def dr_where(pid, t):
        v = dr.get(pid)
        if not v:
            return None
        i = len(v) - 1 if t >= v[-1][0] else bisect.bisect_right(dr_t_cache(pid), t) - 1
        return dr_state_where(v[i][1], t) if i >= 0 else None

    _cache = {}

    def dr_t_cache(pid):
        v = dr[pid]
        c = _cache.get(pid)
        if c is None or len(c) != len(v):
            c = [e[0] for e in v]; _cache[pid] = c
        return c

    # --- flusso ordini: controllo dell'eroe, ordini propri con coordinate, ancore -----------------------------
    active = {}  # pid -> oid del sottogruppo attivo
    own = defaultdict(list)  # pid -> [(t, x, y, tipo_ordine)]
    anchors = []  # (t, pid_eroe, x, y, pid_cliccante, ordine)
    enemy_clicks = []  # (t, x, y) bersagli non-eroi cliccati in combattimento
    n_coord_orders = Counter(); n_coord_hero = Counter()
    for a in acts:
        pid = a['pid']
        if a['kind'] == 'subgroup':
            active[pid] = a['oid']; continue
        if a['kind'] not in ('order_target', 'order_point', 'order_notarget'):
            continue
        hero_ctrl = pid in HERO and active.get(pid, HERO[pid][1]) == HERO[pid][1]
        if a['kind'] == 'order_target' and a.get('tid') in OID2PID:
            anchors.append((a['t'], OID2PID[a['tid']], a['x'], a['y'], pid, a['order']))
        if a['kind'] == 'order_notarget':
            if hero_ctrl and a['order'] in ('holdposition', 'stop'):
                cur = dr_where(pid, a['t'])
                if cur:
                    dr[pid].append((a['t'], (a['t'], cur[0], cur[1], cur[0], cur[1], 0.0)))
            continue
        if a['kind'] == 'order_target' and a['tid'] != NULL_ID and a['tid'] not in OID2PID \
                and a['order'] in ('smart', 'attack') and challenge_at(a['t']):
            enemy_clicks.append((a['t'], a['x'], a['y'], pid))
        n_coord_orders[pid] += 1
        if not hero_ctrl:
            continue
        n_coord_hero[pid] += 1
        if a['kind'] == 'order_point':
            k = 'abilita_a_terra'
        elif a['tid'] == NULL_ID:
            k = 'movimento_a_terra' if a['order'] in ('smart', 'move', 'attack', 'patrol') else 'abilita_a_terra'
        elif a['tid'] in OID2PID:
            k = 'su_eroe_alleato'
        else:
            k = 'su_unita_bersaglio'
        own[pid].append((a['t'], a['x'], a['y'], k))
        # modello "dead reckoning": l'eroe parte dalla posizione stimata e va verso il punto a velocita' SPEED,
        # fermandosi a distanza 'sd' (gittata d'attacco per i bersagli, IPOTESI 600 per le abilita' a terra)
        cur = dr_where(pid, a['t']) or (a['x'], a['y'])
        sd = 0.0 if k == 'movimento_a_terra' else (AB_RANGE if k == 'abilita_a_terra' else RANGE.get(HERO[pid][0], 128))
        dr[pid].append((a['t'], (a['t'], cur[0], cur[1], a['x'], a['y'], sd)))

    own_t = {pid: [e[0] for e in v] for pid, v in own.items()}

    def last_own(pid, t, strict=True):
        ts = own_t.get(pid, [])
        i = (bisect.bisect_left(ts, t) if strict else bisect.bisect_right(ts, t)) - 1
        return own[pid][i] if i >= 0 else None

    # --- 1) VALIDAZIONE contro le ancore misurate (solo ancore cliccate da ALTRI giocatori, in combattimento) --
    # metodo A = "ultimo punto cliccato" grezzo; metodo B = dead reckoning (movimento a velocita' SPEED)
    val = []
    for t, hp, x, y, cp, order in anchors:
        if cp == hp or not challenge_at(t):
            continue
        e = last_own(hp, t)
        if not e:
            continue
        b_ = dr_where(hp, t - 1e-6)
        val.append({'t': t, 'pid': hp, 'eta': t - e[0], 'tipo': e[3], 'err_A': dist((x, y), (e[1], e[2])),
                    'err_B': dist((x, y), b_) if b_ else None})
    bands = [(0, 2), (2, 5), (5, 10), (10, 30), (30, 1e9)]
    vrows = []
    for metodo, key in (('A_ultimo_punto_cliccato', 'err_A'), ('B_dead_reckoning_270', 'err_B')):
        for tipo_o in ['tutti', 'movimento_a_terra', 'su_unita_bersaglio', 'abilita_a_terra', 'su_eroe_alleato']:
            for lo, hi in bands + [(0, 10), (0, 1e9)]:
                v = [r[key] for r in val if lo <= r['eta'] < hi and r[key] is not None
                     and (tipo_o == 'tutti' or r['tipo'] == tipo_o)]
                if len(v) < 5:
                    continue
                vrows.append({'metodo': metodo, 'tipo_ultimo_ordine': tipo_o,
                              'eta_ultimo_ordine_s': f'{lo}-{hi if hi < 1e8 else "oltre"}',
                              'n_ancore': len(v), 'errore_mediano': med(v), 'errore_p75': pct(v, .75),
                              'errore_p90': pct(v, .9), 'pct_entro_300': 100 * sum(x <= 300 for x in v) / len(v),
                              'pct_entro_600': 100 * sum(x <= 600 for x in v) / len(v)})
    write_csv('validazione_ultimo_click.csv', vrows, list(vrows[0].keys()))
    # stessa validazione per classe (eta' <= MAXAGE)
    vcl = []
    for pid in sorted(HERO, key=lambda p: ORDER.index(CL[p])):
        va = [r['err_A'] for r in val if r['pid'] == pid and r['eta'] <= MAXAGE]
        vb = [r['err_B'] for r in val if r['pid'] == pid and r['eta'] <= MAXAGE and r['err_B'] is not None]
        vcl.append({'classe': CL[pid], 'ruolo': RU[CL[pid]],
                    'ancore_altri_in_combattimento': sum(1 for r in val if r['pid'] == pid),
                    'ancore_usate_validazione': len(vb),
                    'errore_mediano_ultimo_click': med(va), 'errore_mediano_dead_reckoning': med(vb),
                    'errore_p75_dead_reckoning': pct(vb, .75),
                    'pct_entro_300_dead_reckoning': (100 * sum(x <= 300 for x in vb) / len(vb)) if vb else None})

    # --- 2) COPERTURA ------------------------------------------------------------------------------------------
    STEP = 1.0
    samples = []  # campioni ogni secondo di combattimento
    for c, s, e, _ in win:
        t = s
        while t <= e:
            samples.append((c, t)); t += STEP
    cov = []
    anc_by_hero = defaultdict(list)
    for t, hp, x, y, cp, order in anchors:
        anc_by_hero[hp].append((t, x, y, cp))
    for v in anc_by_hero.values():
        v.sort()
    anc_t = {p: [a[0] for a in v] for p, v in anc_by_hero.items()}

    def anchor_near(pid, t, tol=1.5):
        ts = anc_t.get(pid, [])
        i = bisect.bisect_left(ts, t - tol)
        best = None
        while i < len(ts) and ts[i] <= t + tol:
            if best is None or abs(ts[i] - t) < abs(best[0] - t):
                best = anc_by_hero[pid][i]
            i += 1
        return best

    pos = {}  # (pid, t) -> (x, y, fonte)
    for pid in HERO:
        ages = []
        n_anc = 0
        in_arena = []
        for c, t in samples:
            e = last_own(pid, t, strict=False)
            age = t - e[0] if e else 1e9
            ages.append(age)
            a = anchor_near(pid, t)
            if a:
                n_anc += 1; pos[(pid, t)] = (a[1], a[2], 'ancora')
            elif age <= MAXAGE:
                pos[(pid, t)] = (*dr_where(pid, t), 'dead_reckoning')
            if (pid, t) in pos:
                in_arena.append(inside(RECTS['ArenaArea'], *pos[(pid, t)][:2]))
        n = len(samples)
        cls = CL[pid]
        cov.append({'classe': cls, 'ruolo': RU[cls], 'secondi_combattimento': n * STEP,
                    'ordini_con_coordinate_in_combattimento': sum(1 for e in own[pid] if challenge_at(e[0])),
                    'pct_ordini_coord_dati_all_eroe': 100 * n_coord_hero[pid] / n_coord_orders[pid] if n_coord_orders[pid] else None,
                    'pct_tempo_ultimo_ordine_entro_2s': 100 * sum(x <= 2 for x in ages) / n,
                    'pct_tempo_ultimo_ordine_entro_5s': 100 * sum(x <= 5 for x in ages) / n,
                    'pct_tempo_ultimo_ordine_entro_10s': 100 * sum(x <= 10 for x in ages) / n,
                    'pct_tempo_ultimo_ordine_entro_30s': 100 * sum(x <= 30 for x in ages) / n,
                    'eta_mediana_ultimo_ordine_s': med(ages),
                    'pct_tempo_con_ancora_misurata_1_5s': 100 * n_anc / n,
                    'pct_tempo_con_posizione_usabile': 100 * sum(1 for c, t in samples if (pid, t) in pos) / n,
                    'pct_posizioni_dentro_arena': 100 * sum(in_arena) / len(in_arena) if in_arena else None})
    cov.sort(key=lambda r: ORDER.index(r['classe']))
    # unisco la validazione per classe
    vmap = {r['classe']: r for r in vcl}
    for r in cov:
        r.update({k: v for k, v in vmap[r['classe']].items() if k not in ('classe', 'ruolo')})
    write_csv('copertura_classe.csv', cov, list(cov[0].keys()))

    # --- 3) FRONTE: punti dei bersagli non-eroe cliccati (+-5 s) ---------------------------------------------
    # F(t) = mediana dei punti cliccati su unita' non-eroe da TUTTI i giocatori (posizione approssimata dei nemici)
    # nemico vicino = bersaglio non-eroe piu' vicino cliccato da ALTRI giocatori in +-3 s (evita la circolarita')
    enemy_clicks.sort(); ect = [e[0] for e in enemy_clicks]

    def front(t, tol=5.0, nmin=3):
        i, j = bisect.bisect_left(ect, t - tol), bisect.bisect_right(ect, t + tol)
        if j - i < nmin:
            return None
        return (st.median(e[1] for e in enemy_clicks[i:j]), st.median(e[2] for e in enemy_clicks[i:j]))

    def nearest_enemy(pid, xy, t, tol=3.0):
        i, j = bisect.bisect_left(ect, t - tol), bisect.bisect_right(ect, t + tol)
        v = [dist(xy, (e[1], e[2])) for e in enemy_clicks[i:j] if e[3] != pid]
        return min(v) if v else None

    tanks = [p for p in HERO if RU[CL[p]] == 'Tank']
    healers = [p for p in HERO if RU[CL[p]] == 'Healer']
    per_cls = defaultdict(lambda: defaultdict(list))  # pid -> metrica -> valori
    per_cc = defaultdict(lambda: defaultdict(list))   # (pid, challenge)
    group = defaultdict(lambda: defaultdict(list))    # tipo_wave -> metrica

    def acc(tw, key, v):
        group[tw][key].append(v); group['tutte'][key].append(v)

    for c, t in samples:
        F = front(t)
        P = {pid: pos[(pid, t)][:2] for pid in HERO if (pid, t) in pos}
        tw = tipo.get(c, '?')
        cen = None
        if len(P) >= 6:  # metriche di gruppo solo se almeno 6 eroi su 10 hanno una posizione
            cen = (st.mean(p[0] for p in P.values()), st.mean(p[1] for p in P.values()))
            acc(tw, 'dispersione', st.mean(dist(p, cen) for p in P.values()))
        for pid, xy in P.items():
            r = RU[CL[pid]]
            d = per_cls[pid]; dc = per_cc[(pid, c)]
            d['x'].append(xy[0]); d['y'].append(xy[1])
            d['spawn'].append(min(dist(xy, s_) for s_ in SPAWNS.values()))
            ne = nearest_enemy(pid, xy, t)
            if ne is not None:
                d['nemico'].append(ne); dc['nemico'].append(ne); acc(tw, 'nemico_' + r, ne)
            if F:
                df = dist(xy, F); d['fronte'].append(df); dc['fronte'].append(df); acc(tw, 'fronte_' + r, df)
                if cen and dist(cen, F) > 1:
                    ux, uy = (F[0] - cen[0]) / dist(cen, F), (F[1] - cen[1]) / dist(cen, F)
                    pr = (xy[0] - cen[0]) * ux + (xy[1] - cen[1]) * uy  # >0 = verso il fronte, <0 = dietro
                    d['proiezione'].append(pr); acc(tw, 'proiezione_' + r, pr)
            others = [P[p] for p in tanks if p in P and p != pid]
            if others:
                dt = min(dist(xy, o) for o in others); d['tank'].append(dt)
                if r == 'Healer':
                    acc(tw, 'tank_healer', dt); acc(tw, 'tank_healer_entro_700', dt <= HEAL_RANGE)
                if r == 'DPS distanza':
                    acc(tw, 'tank_dps_distanza', dt)
                if F and r != 'Tank':
                    tf = min(dist(o, F) for o in others)
                    d['dietro'].append(df - tf); dc['dietro'].append(df - tf); acc(tw, 'dietro_' + r, df - tf)
            hs = [P[p] for p in healers if p in P and p != pid]
            if hs:
                dh = min(dist(xy, h) for h in hs); d['healer'].append(dh)
                d['entro_700_healer'].append(dh <= HEAL_RANGE)

    ROLES = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']
    prow = []
    for pid in sorted(HERO, key=lambda p: ORDER.index(CL[p])):
        d = per_cls[pid]
        prow.append({'classe': CL[pid], 'ruolo': RU[CL[pid]], 'distanza_classe': DI[CL[pid]],
                     'campioni_con_posizione': len(d['x']), 'x_mediana': med(d['x']), 'y_mediana': med(d['y']),
                     'dist_mediana_nemico_piu_vicino': med(d['nemico']), 'campioni_nemico': len(d['nemico']),
                     'dist_mediana_dal_fronte': med(d['fronte']), 'campioni_con_fronte': len(d['fronte']),
                     'proiezione_verso_fronte_mediana': med(d['proiezione']),
                     'pct_campioni_verso_fronte': (100 * sum(v > 0 for v in d['proiezione']) / len(d['proiezione'])) if d['proiezione'] else None,
                     'dist_mediana_tank_piu_vicino': med(d['tank']),
                     'dietro_al_tank_mediana': med(d['dietro']),
                     'pct_campioni_dietro_al_tank': (100 * sum(v > 0 for v in d['dietro']) / len(d['dietro'])) if d['dietro'] else None,
                     'dist_mediana_healer': med(d['healer']),
                     'pct_entro_700_dal_healer': (100 * sum(d['entro_700_healer']) / len(d['entro_700_healer'])) if d['entro_700_healer'] else None,
                     'dist_mediana_spawn_piu_vicino': med(d['spawn'])})
    write_csv('posizioni_classe.csv', prow, list(prow[0].keys()))

    grow = []
    for tw in ['tutte', 'mischia', 'distanza', 'ibrida']:
        g = group[tw]
        grow.append({'tipo_wave': tw, 'campioni_dispersione': len(g['dispersione']),
                     'dispersione_mediana': med(g['dispersione']),
                     'tank_healer_mediana': med(g['tank_healer']), 'campioni_tank_healer': len(g['tank_healer']),
                     'pct_healer_entro_700_da_un_tank': (100 * sum(g['tank_healer_entro_700']) / len(g['tank_healer_entro_700'])) if g['tank_healer_entro_700'] else None,
                     'tank_dps_distanza_mediana': med(g['tank_dps_distanza']),
                     **{f'nemico_vicino_{r.replace(" ", "_")}_mediana': med(g['nemico_' + r]) for r in ROLES},
                     **{f'proiezione_fronte_{r.replace(" ", "_")}_mediana': med(g['proiezione_' + r]) for r in ROLES},
                     **{f'fronte_{r.replace(" ", "_")}_mediana': med(g['fronte_' + r]) for r in ROLES},
                     **{f'dietro_tank_{r.replace(" ", "_")}_mediana': med(g['dietro_' + r]) for r in ROLES[1:]}})
    write_csv('metriche_gruppo_tipo_wave.csv', grow, list(grow[0].keys()))

    # --- 4) relazione prudente con quota tank e HP<20% ---------------------------------------------------------
    cc = {(r['classe'], int(r['challenge'])): r for r in read_csv('data_analysis/v2/aggregato/classe_challenge.csv')}
    ccrows = []
    for (pid, c), d in per_cc.items():
        r = cc.get((CL[pid], c))
        if not r:
            continue
        ccrows.append({'classe': CL[pid], 'ruolo': RU[CL[pid]], 'challenge': c, 'tipo_wave': tipo.get(c),
                       'campioni_con_fronte': len(d['fronte']), 'dist_mediana_fronte': med(d['fronte']),
                       'campioni_nemico': len(d['nemico']), 'dist_mediana_nemico_vicino': med(d['nemico']),
                       'dietro_al_tank_mediana': med(d['dietro']),
                       'tank_quota_round': float(r['tank_quota_round']) if r['tank_quota_round'] else None,
                       'hp_fine_round': float(r['hp_fine_round']) if r['hp_fine_round'] else None})
    ccrows.sort(key=lambda r: (r['challenge'], ORDER.index(r['classe'])))
    write_csv('classe_challenge_posizione.csv', ccrows, list(ccrows[0].keys()))

    sc = {r['classe']: r for r in read_csv('data_analysis/v2/aggregato/scheda_classi.csv')}
    rel = []
    ok = [r for r in prow if r['dist_mediana_dal_fronte'] is not None]
    a = [r['dist_mediana_dal_fronte'] for r in ok]
    rel.append({'confronto': 'classe: dist. mediana dal fronte vs quota_tank finale', 'n': len(ok),
                'spearman': spearman(a, [float(sc[r['classe']]['quota_tank']) for r in ok])})
    rel.append({'confronto': 'classe: dist. mediana dal fronte vs round_sotto_20hp', 'n': len(ok),
                'spearman': spearman(a, [float(sc[r['classe']]['round_sotto_20hp']) for r in ok])})
    good = [r for r in ccrows if r['campioni_con_fronte'] >= 20 and r['tank_quota_round'] is not None]
    rel.append({'confronto': 'classe x challenge (>=20 campioni): dist. dal fronte vs tank_quota_round', 'n': len(good),
                'spearman': spearman([r['dist_mediana_fronte'] for r in good], [r['tank_quota_round'] for r in good])})
    low = [r['dist_mediana_fronte'] for r in good if r['hp_fine_round'] is not None and r['hp_fine_round'] <= 20]
    hi = [r['dist_mediana_fronte'] for r in good if r['hp_fine_round'] is not None and r['hp_fine_round'] > 20]
    rel.append({'confronto': f'dist. mediana dal fronte: casi HP<=20% a fine round (n={len(low)}) vs altri (n={len(hi)})',
                'n': len(low) + len(hi), 'mediana_gruppo_a': med(low), 'mediana_gruppo_b': med(hi)})
    okn = [r for r in prow if r['dist_mediana_nemico_piu_vicino'] is not None]
    rel.append({'confronto': 'classe: dist. mediana dal nemico piu vicino vs quota_tank finale', 'n': len(okn),
                'spearman': spearman([r['dist_mediana_nemico_piu_vicino'] for r in okn], [float(sc[r['classe']]['quota_tank']) for r in okn])})
    goodn = [r for r in ccrows if r['campioni_nemico'] >= 20 and r['tank_quota_round'] is not None]
    rel.append({'confronto': 'classe x challenge (>=20 campioni): dist. nemico piu vicino vs tank_quota_round', 'n': len(goodn),
                'spearman': spearman([r['dist_mediana_nemico_vicino'] for r in goodn], [r['tank_quota_round'] for r in goodn])})
    lown = [r['dist_mediana_nemico_vicino'] for r in goodn if r['hp_fine_round'] is not None and r['hp_fine_round'] <= 20]
    hin = [r['dist_mediana_nemico_vicino'] for r in goodn if r['hp_fine_round'] is not None and r['hp_fine_round'] > 20]
    rel.append({'confronto': f'dist. mediana nemico piu vicino: casi HP<=20% a fine round (n={len(lown)}) vs altri (n={len(hin)})',
                'n': len(lown) + len(hin), 'mediana_gruppo_a': med(lown), 'mediana_gruppo_b': med(hin)})
    write_csv('relazione_danni_hp.csv', rel, ['confronto', 'n', 'spearman', 'mediana_gruppo_a', 'mediana_gruppo_b'])

    # --- 5) SVG ------------------------------------------------------------------------------------------------
    svg(prow, enemy_clicks, win, tipo)

    # riepilogo a schermo
    print('eroi riconosciuti:', len(HERO), '| ancore totali:', len(anchors),
          '| ancore da altri in combattimento:', len(val), '| click su bersagli non-eroe in combattimento:', len(enemy_clicks))
    print('campioni di combattimento (1/s):', len(samples))
    for r in vrows:
        if r['tipo_ultimo_ordine'] == 'tutti':
            print('validazione', r)
    for r in cov:
        print('copertura', {k: (round(v, 1) if isinstance(v, float) else v) for k, v in r.items()})
    for r in prow:
        print('posizione', {k: (round(v) if isinstance(v, float) else v) for k, v in r.items()})
    for r in grow:
        print('gruppo', {k: (round(v) if isinstance(v, float) else v) for k, v in r.items()})
    for r in rel:
        print('relazione', r)
    # quota di click nemici dentro l'arena
    print('click su bersagli non-eroe dentro ArenaArea: %.1f%%' %
          (100 * sum(inside(RECTS['ArenaArea'], x, y) for _, x, y, _p in enemy_clicks) / len(enemy_clicks)))


def svg(prow, enemy_clicks, win, tipo):
    minx, miny, maxx, maxy = -5400, -3500, 4600, 6400
    W_, H_ = 700, int(700 * (maxy - miny) / (maxx - minx))

    def tx(x): return (x - minx) / (maxx - minx) * W_
    def ty(y): return H_ - (y - miny) / (maxy - miny) * H_
    col = {'Tank': '#c0392b', 'Healer': '#27ae60', 'Support': '#8e44ad', 'DPS mischia': '#e67e22', 'DPS distanza': '#2471a3'}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W_} {H_ + 60}" font-family="sans-serif" font-size="11">',
         f'<rect width="{W_}" height="{H_ + 60}" fill="#fafafa"/>']
    for name, r in RECTS.items():
        fill = '#f5d5d5' if name.startswith('Spawn') else ('#eef3fa' if name == 'ArenaArea' else '#e8e8e8')
        o.append(f'<rect x="{tx(r[0]):.1f}" y="{ty(r[3]):.1f}" width="{tx(r[2]) - tx(r[0]):.1f}" height="{ty(r[1]) - ty(r[3]):.1f}" '
                 f'fill="{fill}" stroke="#888" stroke-width="0.8"/>')
        o.append(f'<text x="{tx(r[0]) + 3:.1f}" y="{ty(r[3]) + 12:.1f}" fill="#555">{name.split(" (")[0]}</text>')
    for _, x, y, _p in enemy_clicks[::3]:
        o.append(f'<circle cx="{tx(x):.1f}" cy="{ty(y):.1f}" r="1.2" fill="#999" fill-opacity="0.35"/>')
    for r in prow:
        if r['x_mediana'] is None:
            continue
        cx, cy = tx(r['x_mediana']), ty(r['y_mediana'])
        o.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{col[r["ruolo"]]}" stroke="#fff"/>')
        o.append(f'<text x="{cx + 8:.1f}" y="{cy + 4:.1f}" fill="{col[r["ruolo"]]}">{r["classe"]}</text>')
    y0 = H_ + 18
    o.append(f'<text x="8" y="{y0}" fill="#333">Posizione mediana stimata per classe durante le wave (ultimo ordine &lt;=5 s o ancora misurata). '
             'Punti grigi: bersagli non-eroe cliccati (fronte).</text>')
    x0 = 8
    for k, c in col.items():
        o.append(f'<circle cx="{x0 + 5}" cy="{y0 + 18}" r="5" fill="{c}"/><text x="{x0 + 13}" y="{y0 + 22}">{k}</text>')
        x0 += 110
    o.append('</svg>')
    with open(os.path.join(OUT, 'posizioni.svg'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(o))


if __name__ == '__main__':
    main()
