"""Gestione del mana e uso dei cooldown, per classe e per ruolo.

Uso (dalla cartella del progetto):  python analisi_abilita_mana.py
Output: data_analysis/v2/abilita_mana/*.csv + NOTE.md (scritto a parte, vedi NOTE.md)

Fonti:
- data_replay/actions_named.csv  : ordini dei giocatori (comandi, non effetti)
- replay_originali/*.w3g         : riletto solo per gli ID oggetto delle unita' selezionate (eroe di ogni giocatore)
- data_screenshots/*.csv         : livello e mana attuale (misura reale), confini delle challenge, scelte statistiche
- data_map/raw/                  : war3map.w3a/.w3u/.w3t/.wts/.j, war3mapMisc.txt
- Warcraft III *.mpq (sola lettura): Units\\AbilityData.slk, UnitBalance.slk, MiscGame.txt (valori base)

Nessun nome di giocatore negli output: si usano classe e ruolo.
"""
import csv, math, os, re, statistics, sys
from collections import Counter, defaultdict

from objdata import parse_obj, parse_wts, clean
import w3g_parser
from mpq import MPQ

OUT = 'data_analysis/v2/abilita_mana'
RAW = 'data_map/raw'
# file del gioco: prima nella cartella del progetto (replay_originali/gioco), poi nell'installazione Windows
WC3 = os.path.join('replay_originali', 'gioco')   # relativo alla cartella del progetto (da cui si lanciano gli script)
if not os.path.isdir(WC3):
    WC3 = r'C:/Program Files (x86)/Warcraft III'
REPLAY = 'replay_originali/orcgladiatorsbutei.w3g'
DT = 0.5                      # passo della simulazione (s)
ALPHAS = [x / 4 for x in range(-24, 49)]   # regen extra calibrata: -6 .. +12 mana/s
BS = chr(92)


def load(path):
    return list(csv.DictReader(open(path, encoding='utf-8')))


def write(name, rows, cols):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
    print('scritto', name, len(rows))


# ----------------------------------------------------------------------------------------- dati di gioco base
def slk(data):
    rows, y, x = {}, 0, 0
    for line in data.decode('latin-1').splitlines():
        parts = line.split(';')
        if parts[0] != 'C':
            continue
        val = None
        for p in parts[1:]:
            if p.startswith('X'):
                x = int(p[1:])
            elif p.startswith('Y'):
                y = int(p[1:])
            elif p.startswith('K'):
                val = p[1:].strip('"')
        if val is not None:
            rows.setdefault(y, {})[x] = val
    hdr = rows[1]
    return {r[1]: {hdr.get(k, k): v for k, v in r.items()} for yy, r in rows.items() if yy != 1 and r.get(1)}


def game_files():
    """Legge da War3Patch.mpq (poi War3x, war3) le tabelle base. Sola lettura."""
    out = {}
    for arc in ('War3Patch.mpq', 'War3x.mpq', 'war3.mpq'):
        try:
            m = MPQ(os.path.join(WC3, arc))
        except Exception:
            continue
        for n in ('AbilityData.slk', 'UnitBalance.slk', 'MiscGame.txt', 'MiscData.txt'):
            if n in out:
                continue
            try:
                d = m.read('Units' + BS + n)
            except Exception:
                d = None
            if d:
                out[n] = d
    return out


def num(v, default=None):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return default


# ----------------------------------------------------------------------------------------- parsing JASS
def jass_funcs(j):
    return {m.group(1): m.group(2) for m in
            re.finditer(r'function (\w+) takes nothing returns \w+\n(.*?)\nendfunction', j, re.S)}


def cond_text(funcs, name, depth=0):
    """Espande ricorsivamente una funzione-condizione nel suo testo."""
    body = funcs.get(name, '')
    if depth > 5:
        return body
    return re.sub(r'(Trig_\w+C)\(\)', lambda m: '(' + cond_text(funcs, m.group(1), depth + 1) + ')', body)


def walk_if(body, funcs, on_line):
    """Scorre le righe di una funzione con lo stack delle condizioni if/else."""
    stack = []
    for line in body.split('\n'):
        m = re.match(r'if\((Trig_\w+C)\(\)\)then', line)
        if m:
            stack.append([cond_text(funcs, m.group(1)), True])
            continue
        if line == 'else':
            if stack:
                stack[-1][1] = False
            continue
        if line == 'endif':
            if stack:
                stack.pop()
            continue
        on_line(line, [c for c, pos in stack if pos])


def parse_level_up(j, funcs):
    """Abilita' aggiunte dal trigger Level_Up: {tipo eroe: [(livello, abilita')]}."""
    i = j.find('function Trig_Level_Up_Actions')
    body = j[i:j.find('\nendfunction', i)]
    res = defaultdict(list)

    def on(line, conds):
        m = re.match(r"call UnitAddAbility\(GetTriggerUnit\(\),'(\w{4})'\)", line)
        if not m:
            return
        lvl = utype = None
        for c in conds:
            ml = re.search(r'udg_HeroLevel==(\d+)', c)
            mu = re.search(r"GetUnitTypeId\(GetTriggerUnit\(\)\)=='(\w{4})'", c)
            lvl = int(ml.group(1)) if ml else lvl
            utype = mu.group(1) if mu else utype
        if utype:
            res[utype].append((lvl, m.group(1)))
    walk_if(body, funcs, on)
    return res


def parse_talents(j, funcs):
    """Talenti (oggetti comprati con i punti talento): {item: [(abilita', livello_richiesto|None, nuovo_livello)]}
    + effetti speciali noti (int = livello eroe)."""
    rules = defaultdict(list)
    special = {}
    for m in re.finditer(r'function (Trig_\w+_Talent_Buy_Actions) takes', j):
        name = m.group(1)
        body = j[m.start():j.find('\nendfunction', m.start())]
        state = {'abil': None}

        def on(line, conds):
            item = None
            for c in conds:
                mi = re.search(r"GetItemTypeId\(GetSoldItem\(\)\)=='(\w{4})'", c)
                item = mi.group(1) if mi else item
            ms = re.match(r"set udg_TalentUpgradeAbility='(\w{4})'", line)
            if ms:
                state['abil'] = ms.group(1)
                return
            ml = re.match(r"call SetUnitAbilityLevelSwapped\((udg_TalentUpgradeAbility|'\w{4}'),udg_TalentHero,(\d+)\)", line)
            if ml and item:
                ab = state['abil'] if ml.group(1).startswith('udg') else ml.group(1).strip("'")
                req = None
                for c in conds:
                    mr = re.findall(r"GetUnitAbilityLevelSwapped\((?:udg_TalentUpgradeAbility|'\w{4}'),udg_TalentHero\)==(\d+)", c)
                    if mr:
                        req = [int(x) for x in mr]
                rules[item].append((ab, req, int(ml.group(2))))
            if 'ModifyHeroStat(2,udg_TalentHero,0,GetHeroLevel(udg_TalentHero))' in line and item:
                special[item] = 'int_piu_livello'
        walk_if(body, funcs, on)
    return rules, special


# ----------------------------------------------------------------------------------------- replay: ID dell'eroe
def scan_selections(a, pid, t, out):
    q = 0
    skip = {0x03: 1, 0x07: 4, 0x10: 14, 0x11: 22, 0x12: 30, 0x13: 38, 0x14: 43, 0x18: 2, 0x19: 12, 0x1B: 9, 0x1C: 9,
            0x1D: 8, 0x1E: 5, 0x21: 8, 0x27: 5, 0x28: 5, 0x2D: 5, 0x2E: 4, 0x50: 5, 0x51: 9, 0x62: 12, 0x68: 12,
            0x69: 16, 0x6A: 16, 0x75: 1}
    none = {0x01, 0x02, 0x04, 0x05, 0x1A, 0x20, 0x22, 0x23, 0x24, 0x25, 0x26, 0x29, 0x2A, 0x2B, 0x2C, 0x2F, 0x30,
            0x31, 0x32, 0x61, 0x65, 0x66, 0x67}
    while q < len(a):
        aid = a[q]; q += 1
        if aid in none:
            continue
        if aid in skip:
            q += skip[aid]
        elif aid == 0x06:
            _, q = w3g_parser.read_cstr(a, q)
        elif aid in (0x16, 0x17):
            mode, n = a[q], int.from_bytes(a[q + 1:q + 3], 'little')
            ids = [f'{int.from_bytes(a[q + 3 + 8 * i:q + 7 + 8 * i], "little"):08X}-'
                   f'{int.from_bytes(a[q + 7 + 8 * i:q + 11 + 8 * i], "little"):08X}' for i in range(n)]
            if aid == 0x16 and mode == 1 and n == 1:
                out.append({'time_ms': t, 'pid': pid, 'kind': 'sel1', 'id': ids[0]})
            q += 3 + 8 * n
        elif aid == 0x60:
            q += 8; _, q = w3g_parser.read_cstr(a, q)
        elif aid == 0x6B:
            for _ in range(3):
                _, q = w3g_parser.read_cstr(a, q)
            q += 4
        else:
            return


def hero_ids(players_by_pid):
    orig = w3g_parser.parse_actions
    w3g_parser.parse_actions = scan_selections
    try:
        _, players, _, acts, _, _ = w3g_parser.parse(REPLAY)
    finally:
        w3g_parser.parse_actions = orig
    cnt = defaultdict(Counter)
    for a in acts:
        cnt[a['pid']][a['id']] += 1
    res = {}
    for pid, c in cnt.items():
        name = players.get(pid, '').replace('\ufffd', '')
        if c:
            res[name] = c.most_common(1)[0][0]
    return res


# ----------------------------------------------------------------------------------------- main
def main():
    gf = game_files()
    ABD = slk(gf['AbilityData.slk'])
    UBAL = slk(gf['UnitBalance.slk'])
    misc_default = {}
    for n in ('MiscGame.txt', 'MiscData.txt'):
        for line in gf.get(n, b'').decode('latin-1').splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                misc_default.setdefault(k.strip(), v.strip())
    misc_map = {}
    for line in open(os.path.join(RAW, 'war3mapMisc.txt'), encoding='latin-1'):
        if '=' in line:
            k, v = line.split('=', 1)
            misc_map[k.strip()] = v.strip()
    CONSTS = {
        'mappa (war3mapMisc.txt)': (num(misc_map.get('IntManaBonus'), 15), num(misc_map.get('IntRegenBonus'), 0.05)),
        'default WC3 (MiscGame.txt)': (num(misc_default.get('IntManaBonus'), 15), num(misc_default.get('IntRegenBonus'), 0.05)),
    }

    wts = parse_wts(open(os.path.join(RAW, 'war3map.wts'), 'rb').read())
    W3A = parse_obj(open(os.path.join(RAW, 'war3map.w3a'), 'rb').read(), 'w3a', wts)
    W3U = parse_obj(open(os.path.join(RAW, 'war3map.w3u'), 'rb').read(), 'w3u', wts)
    W3T = parse_obj(open(os.path.join(RAW, 'war3map.w3t'), 'rb').read(), 'w3t', wts)
    J = open(os.path.join(RAW, 'war3map.j'), encoding='latin-1').read()
    FUNCS = jass_funcs(J)
    catalog = load('data_map/ability_catalog.csv')
    order_str = {r['order_hex']: r['order_string'] for r in csv.DictReader(open('order_ids.csv'))}

    # ---- parametri abilita'
    def afield(aid, fid, lvl, slkcol):
        o = W3A.get(aid)
        if o:
            if (fid, lvl) in o['mods']:
                return o['mods'][(fid, lvl)], 'mappa'
            if lvl == 0 and (fid, 0) in o['mods']:
                return o['mods'][(fid, 0)], 'mappa'
        base = o['base'] if o else aid
        v = ABD.get(base, {}).get(slkcol)
        return (v, 'slk base') if num(v) is not None else (None, None)

    def ability_params(aid):
        lv = afield(aid, 'alev', 0, 'levels')[0]
        nlev = int(num(lv, 1) or 1)
        cost, cd, src = [], [], set()
        for l in range(1, max(nlev, 1) + 1):
            c, s1 = afield(aid, 'amcs', l, f'Cost{l}')
            d, s2 = afield(aid, 'acdn', l, f'Cool{l}')
            c, d = num(c), num(d)
            cost.append(c if c is not None else (cost[-1] if cost else 0.0))
            cd.append(d if d is not None else (cd[-1] if cd else 0.0))
            src |= {s1 or 'default', s2 or 'default'}
        dur = num(afield(aid, 'ahdu', 1, 'HeroDur1')[0]) or num(afield(aid, 'adur', 1, 'Dur1')[0]) or 0
        o = W3A.get(aid, {'base': aid})
        return {'levels': nlev, 'cost': cost, 'cd': cd, 'src': '+'.join(sorted(src)), 'base': o['base'], 'dur': dur}

    def lvl_val(arr, lvl):
        return arr[min(max(lvl, 1), len(arr)) - 1]

    # ---- classi, eroi
    roles = {r['player']: r for r in load('data_map/class_roles.csv')}
    pick_hero = dict(zip(re.findall(r"set udg_WeaponPickButton\[[^\]]*\]='(\w{4})'", J),
                         re.findall(r"set udg_RandomWeaponHero\[[^\]]*\]='(\w{4})'", J)))
    level_up = parse_level_up(J, FUNCS)
    talent_rules, talent_special = parse_talents(J, FUNCS)

    def ufield(code, fid, slkcol):
        o = W3U[code]
        if (fid, 0) in o['mods']:
            return num(o['mods'][(fid, 0)])
        return num(UBAL.get(o['base'], {}).get(slkcol), 0)

    HERO = {}
    for p, r in roles.items():
        h = pick_hero[r['pick_code']]
        abis = [x for x in (W3U[h]['mods'].get(('uabi', 0)) or '').split(',') if x]
        HERO[p] = {'hero': h, 'int0': ufield(h, 'uint', 'INT'), 'inp': ufield(h, 'uinp', 'INTplus'),
                   'mana_base': ufield(h, 'umpm', 'manaN'), 'mana_init': ufield(h, 'umpi', 'mana0'),
                   'regen_base': ufield(h, 'umpr', 'regenMana'),
                   'abil_set': set(abis) | {a for _, a in level_up.get(h, [])}}
    for item, rl in talent_rules.items():
        pass

    # ---- dati replay
    acts = load('data_replay/actions_named.csv')
    snaps = load('data_screenshots/multiboard_snapshots.csv')
    rounds = {int(r['challenge']): r for r in load('data_screenshots/rounds.csv')}
    leaves = {r['player']: int(r['game_time_ms']) / 1000 for r in load('data_replay/leaves.csv')}
    choices = load('data_screenshots/stat_choices.csv')
    END = max(int(s['game_time_s']) for s in snaps)          # sconfitta (fine partita giocata)

    # ---- finestre di combattimento
    ends = {0: 0.0}
    for s in snaps:
        if s['phase'] == 'post':
            ends[int(s['challenges_completed'])] = float(s['game_time_s'])
    ends[20] = float(END)
    breaks = []
    for c in range(1, 20):
        cs = num(rounds.get(c, {}).get('clear_seconds'))
        if cs and c in ends and c - 1 in ends and c > 1:
            breaks.append(ends[c] - cs - ends[c - 1])
    med_break = statistics.median(breaks)
    WIN = {}
    for c in range(1, 21):
        cs = num(rounds.get(c, {}).get('clear_seconds'))
        if cs:
            WIN[c] = (ends[c] - cs, ends[c], 'secondi del riepilogo round')
        else:
            WIN[c] = (ends[c - 1] + med_break, ends[c], f'stimato: fine challenge prec. + pausa mediana {med_break:.0f}s')
    COMBAT = sum(b - a for a, b, _ in WIN.values())

    def challenge_of(t):
        for c, (a, b, _) in WIN.items():
            if a <= t < b:
                return c
        return None

    def segment_of(t):   # segmento come in summarize_replay (fine challenge prec. -> fine challenge)
        for c in range(1, 21):
            if ends[c - 1] <= t < ends[c] or (c == 20 and t >= ends[19]):
                return c
        return 20

    # ---- ID eroe dal replay (per Innervate)
    hid = hero_ids(None)
    id_to_player = {v: k for k, v in hid.items()}

    # ---- risoluzione ordine -> abilita'
    cat_by_order = defaultdict(list)
    for c in catalog:
        if c['order_hex']:
            cat_by_order[c['order_hex']].append(c)

    def cname(c):
        return re.sub(r'^\(\s*\w\s*\)\s*', '', c['name'] or c['tooltip']).strip()

    def resolve(p, order, aname):
        if not order.startswith('0x0D'):
            return None, 'non abilita'
        if aname.startswith(('Oggetto', 'Learn')) or 'autocast' in aname or aname.startswith('['):
            return None, 'toggle/oggetto/apprendimento'
        os_ = order_str.get(order, '')
        if (os_.endswith('on') and os_[:-2] in order_str.values()) or (os_.endswith('off') and os_[:-3] in order_str.values()):
            return None, 'toggle autocast'
        cands = ([c for c in cat_by_order[order] if c['ability_id'] in HERO[p]['abil_set']] or
                 [c for c in cat_by_order[order] if c['ability_id'] in CLASS_TALENT_ABILS[p]])
        names = [n.strip() for n in aname.split('/')]
        named = [c for c in cands if cname(c) in names] or [c for c in cat_by_order[order] if cname(c) in names]
        pick = named or cands
        if not pick:
            # ordine non presente nel catalogo: cerca per nome tra le abilita' della mappa
            nm0 = [n.replace(' (probabile)', '') for n in names]
            if nm0 == ['Fire', 'Frost', 'Magic Bolt'] or aname == 'Fire/Frost/Magic Bolt':
                nm0 = [WIZ_BOLT.get(p) or 'Fire Bolt']
            hits = sorted(k for k, o in W3A.items() if clean(o['mods'].get(('anam', 0)) or '') in nm0
                          and o['base'] not in ('AHtb', 'AId1') and not str(o['mods'].get(('anam', 0))).startswith(('Dummy', 'Boss', 'Creep', 'Item')))
            if not hits:
                return None, 'non risolto'
            return hits[0], 'per nome' + (' (ambiguo: ' + ','.join(hits) + ')' if len(hits) > 1 else '')
        ids = sorted({c['ability_id'] for c in pick if c['ability_id'] in W3A})
        return (ids[0] if ids else pick[0]['ability_id']), ('ambiguo: ' + ','.join(ids) if len(ids) > 1 else 'ok')

    # abilita' toccate dai talenti della propria classe (prefisso "(Classe)" degli oggetti talento comprati)
    item_name0 = {k: clean(o['mods'].get(('unam', 0)) or '') for k, o in W3T.items()}
    CLASS_TALENT_ABILS = defaultdict(set)
    for a in acts:
        if a['player'] in roles and a['order'] in talent_rules:
            pref = re.match(r'\(([^)]*)\)', item_name0.get(a['order'], ''))
            if pref:
                for it, rl in talent_rules.items():
                    if item_name0.get(it, '').startswith('(' + pref.group(1) + ')'):
                        CLASS_TALENT_ABILS[a['player']] |= {r[0] for r in rl}

    # Wizard Staff: quale "bolt" e' stato appreso (ordine dell'abilita' "Learn X Bolt", es. windwalk = Learn Frost Bolt)
    learn_bolt = {}
    for k in ('A0CI', 'A0CJ', 'A0CK'):
        o = W3A.get(k)
        if o:
            os_ = o['mods'].get(('Ncl6', 1)) or o['mods'].get(('Ncl6', 0))
            hx = next((h for h, s in order_str.items() if s == os_), None)
            if hx:
                learn_bolt[hx] = clean(o['mods'].get(('anam', 0)))[6:]
    WIZ_BOLT = {}
    for a in acts:
        if a['player'] in roles and roles[a['player']]['classe'] == 'Wizard Staff' and a['order'] in learn_bolt:
            WIZ_BOLT.setdefault(a['player'], learn_bolt[a['order']])
            a['ability_name'] = 'Learn ' + learn_bolt[a['order']]

    # ---- eventi per giocatore
    PL = list(roles)
    orders = defaultdict(list)       # p -> [(t, aid, aname)]
    unresolved = Counter()
    buys = defaultdict(list)         # p -> [(t, item)]
    learn = defaultdict(list)
    t_create = {}
    for a in acts:
        p = a['player']
        if p not in roles or not a['kind'].startswith('order'):
            continue
        t = int(a['game_time_ms']) / 1000
        o = a['order']
        if o == roles[p]['pick_code']:
            t_create.setdefault(p, t)
        elif re.fullmatch(r'I0\w\w', o):
            buys[p].append((t, o))
        elif a['ability_name'].startswith('Learn'):
            learn[p].append((t, a['ability_name']))
        elif o.startswith('0x0D'):
            aid, why = resolve(p, o, a['ability_name'])
            if aid:
                orders[p].append((t, aid, a['ability_name'], a['target']))
            else:
                unresolved[(p, a['ability_name'], why)] += 1

    # ---- livelli abilita' (talenti) nel tempo
    item_name = {k: clean(o['mods'].get(('unam', 0)) or '') for k, o in W3T.items()}
    lvl_events = defaultdict(list)     # p -> [(t, aid, da, a, item)]
    ab_level = {}
    special_events = defaultdict(list)
    for p in PL:
        cur = defaultdict(lambda: 1)
        seen = set()
        for t, it in sorted(buys[p]):
            if it not in talent_rules and it not in talent_special:
                continue
            if it in seen:            # l'oggetto talento viene tolto dallo stock dopo l'acquisto
                continue
            seen.add(it)
            for ab, req, new in talent_rules.get(it, []):
                if req is None or cur[ab] in req:
                    lvl_events[p].append((t, ab, cur[ab], new, item_name.get(it, it)))
                    cur[ab] = new
                    break
            if it in talent_special:
                special_events[p].append((t, talent_special[it], item_name.get(it, it)))

    def level_at(p, aid, t):
        L = 1
        for te, ab, _, new, _ in lvl_events[p]:
            if ab == aid and te <= t:
                L = new
        return L

    # ---- livello eroe nel tempo (interpolato dagli screenshot)
    lv_pts = defaultdict(list)
    for s in snaps:
        if s['level']:
            lv_pts[s['player']].append((float(s['game_time_s']), float(s['level'])))

    def hero_level(p, t):
        pts = [(t_create.get(p, 0), 1.0)] + sorted(lv_pts[p])
        if t <= pts[0][0]:
            return 1.0
        for (t0, l0), (t1, l1) in zip(pts, pts[1:]):
            if t0 <= t <= t1:
                return l0 + (l1 - l0) * (t - t0) / (t1 - t0) if t1 > t0 else l1
        return pts[-1][1]

    # ---- bonus permanenti a INT / regen da oggetti e scelte
    def item_effects(code):
        """(int, mana_max, regen_pct) dagli effetti standard dell'oggetto; 'Purchase X' -> oggetto 'X'."""
        nm = item_name.get(code, '')
        if nm.startswith('Purchase '):
            tgt = [k for k, v in item_name.items() if v == nm[9:]]
            if tgt:
                code = tgt[0]
        o = W3T.get(code)
        if not o:
            return 0, 0, 0
        iint = iman = imrp = 0.0
        for ab in (o['mods'].get(('iabi', 0)) or '').split(','):
            ab = ab.strip()
            ao = W3A.get(ab)
            base = ao['base'] if ao else ab
            mods = ao['mods'] if ao else {}
            sl = ABD.get(base, {})
            if base.startswith(('AIi', 'AIx')):
                iint += num(mods.get(('Iint', 1)), num(sl.get('DataB1'), 0))
            elif base == 'AIrm':
                imrp += num(mods.get(('Imrp', 1)), num(sl.get('DataA1'), 0))
            elif base in ('AImm', 'AIbm', 'AImb'):
                iman += num(mods.get(('Iman', 1)), num(sl.get('DataA1'), 0))
        return iint, iman, imrp

    perm = defaultdict(list)   # p -> [(t, int, mana, regen_pct, descr)]
    for p in PL:
        last = {}
        for t, it in sorted(buys[p]):
            nm = item_name.get(it, it)
            if nm.startswith('Tome: +2 Intelligence'):
                perm[p].append((t, 2, 0, 0, nm)); continue
            if nm.startswith('Tome: +1 Stats'):
                perm[p].append((t, 1, 0, 0, nm)); continue
            if it in talent_rules or it in talent_special:
                continue
            if it in last and t - last[it] < 5:      # click ripetuti sullo stesso oggetto
                continue
            last[it] = t
            ii, im, ir = item_effects(it)
            if ii or im or ir:
                perm[p].append((t, ii, im, ir, nm))
        for c in choices:
            if c['player'] == p and re.search(r'\+1 Int', c['choice']):
                perm[p].append((ends[int(c['after_challenge'])], 1, 0, 0, 'scelta statistiche: ' + c['choice']))
        for t, kind, nm in special_events[p]:
            if kind == 'int_piu_livello':
                perm[p].append((t, int(hero_level(p, t)), 0, 0, nm + ' (+INT = livello eroe)'))
        perm[p].sort()

    # aura di Brilliance (Wizard Staff): regen piatta a tutti gli alleati (ipotesi: in raggio)
    brill_ab = None
    for m in re.finditer(r"call UnitAddAbility\(GetTriggerUnit\(\),'(\w{4})'\)", J[J.find('function Trig_G_Innate_Abilities_Actions'):]):
        brill_ab = m.group(1); break
    brill_val = [num(W3A[brill_ab]['mods'].get(('Hab1', l)), num(ABD.get('ACba', {}).get(f'DataA{l}'), 0))
                 for l in (1, 2)] if brill_ab in W3A else [0, 0]
    brill_pct = num(ABD.get(W3A.get(brill_ab, {'base': 'ACba'})['base'], {}).get('DataB1'), 0)
    brill_t = None
    brill_lv2_t = None
    for p in PL:
        for t, nm in learn[p]:
            if 'Brilliance' in nm:
                brill_t = t if brill_t is None else min(brill_t, t)
        for t, ab, da, a_, nm in lvl_events[p]:
            if ab == brill_ab and a_ >= 2:
                brill_lv2_t = t

    def brilliance(t):
        if brill_t is None or t < brill_t:
            return 0.0
        return brill_val[1] if (brill_lv2_t is not None and t >= brill_lv2_t) else brill_val[0]

    # mana tide: tick ogni 2 s, durata = PV del totem / 25 per tick
    tide_hp = num(UBAL.get(W3U.get('o009', {'base': 'oeye'})['base'], {}).get('HP'), 50) or 50
    tide_ticks = max(1, int(math.ceil(tide_hp / 25)))
    TIDE_AMOUNT = 15.63

    # ---- parametri di ogni abilita' usata
    PAR = {}
    for p in PL:
        for _, aid, _, _ in orders[p]:
            if aid not in PAR:
                PAR[aid] = ability_params(aid)
    ANAME = {}
    for p in PL:
        for _, aid, nm, _ in orders[p]:
            ANAME[(p, aid)] = nm

    # ---- simulazione
    snaps_by_p = defaultdict(list)
    for s in snaps:
        if s['mana']:
            hp = float(s['hp_pct'])
            mana = float(s['mana'])
            excl = ''
            if s['phase'] == 'sconfitta' or hp == 0:
                excl = 'eroe morto / fine partita'
            elif hp <= 25 and mana <= 125:
                excl = 'probabile rianimazione (eroe rianimato con 75 mana e 10% PV)'
            snaps_by_p[s['player']].append({'t': float(s['game_time_s']), 'mana': mana, 'hp': hp, 'level': s['level'],
                                            'shot': s['screenshot'], 'excl': excl, 'challenge': s['challenges_completed'],
                                            'phase': s['phase']})
    for p in snaps_by_p:
        snaps_by_p[p].sort(key=lambda x: x['t'])

    def build_gains():
        """Guadagni di mana da abilita' note (ricostruiti dai cast stimati: filtro cooldown)."""
        g = defaultdict(list)
        for p in PL:
            nxt = {}
            for t, aid, nm, tgt in sorted(orders[p]):
                par = PAR[aid]
                L = level_at(p, aid, t)
                if t < nxt.get(aid, -1):
                    continue
                nxt[aid] = t + lvl_val(par['cd'], L)
                if 'Innervate' in nm:
                    tp = id_to_player.get(tgt)
                    if tp is None:
                        continue
                    self_ = tp == p
                    tot = (75 if L in (1, 3) else 112.5) if self_ else (150 if L in (1, 3) else 225)
                    for k in range(1, 11):
                        g[tp].append((t + k, tot / 10, 'Innervate'))
                elif 'Mana Tide' in nm:
                    for q in PL:
                        for k in range(1, tide_ticks + 1):
                            g[q].append((t + 2 * k, TIDE_AMOUNT, 'Mana Tide'))
        return g

    GAINS = build_gains()

    def int_at(p, t):
        h = HERO[p]
        v = h['int0'] + h['inp'] * (hero_level(p, t) - 1)
        for te, ii, _, _, _ in perm[p]:
            if te <= t:
                v += ii
        return math.floor(v)

    def perm_mana(p, t):
        return sum(im for te, _, im, _, _ in perm[p] if te <= t)

    def regen_pct(p, t):
        return sum(ir for te, _, _, ir, _ in perm[p] if te <= t)

    def simulate(p, kM, kR, alpha, assim, record=False, cast_filter_mana=True):
        h = HERO[p]
        t0 = t_create.get(p, 0)
        tend = min(leaves.get(p, END), END)
        evs = sorted(orders[p])
        gains = sorted(GAINS[p])
        sn = snaps_by_p[p]
        ei = gi = si = 0
        offset = 0.0
        mana = None
        nxt = {}
        preds = []
        stats = {'cast': Counter(), 'cd_waste': Counter(), 'mana_rej': Counter(), 'spent': 0.0}
        zone = defaultdict(lambda: [0.0, 0.0, 0.0])
        bych = defaultdict(lambda: {'cast': 0, 'waste': 0, 'rej': 0, 'spent': 0.0})
        avatar_until = -1
        t = t0
        while t < tend:
            lvl_int = int_at(p, t)
            mx = h['mana_base'] + kM * lvl_int + perm_mana(p, t) + offset
            if mana is None:
                mana = min(h['mana_init'] or mx, mx)
            rg = h['regen_base'] * (1 + regen_pct(p, t)) + kR * lvl_int + brilliance(t) + alpha
            if t < avatar_until:
                rg += 8
            t1 = t + DT
            # eventi nel passo
            while gi < len(gains) and gains[gi][0] < t1:
                mana = min(mx, mana + gains[gi][1]); gi += 1
            while ei < len(evs) and evs[ei][0] < t1:
                te, aid, nm, tgt = evs[ei]; ei += 1
                if te < t0:
                    continue
                par = PAR[aid]
                L = level_at(p, aid, te)
                cost, cd = lvl_val(par['cost'], L), lvl_val(par['cd'], L)
                ch = challenge_of(te)
                if te < nxt.get(aid, -1):
                    stats['cd_waste'][aid] += 1
                    bych[ch]['waste'] += 1
                    continue
                if cast_filter_mana and mana < cost:
                    stats['mana_rej'][aid] += 1
                    bych[ch]['rej'] += 1
                    continue
                nxt[aid] = te + cd
                mana -= cost
                stats['cast'][aid] += 1
                stats['spent'] += cost
                bych[ch]['cast'] += 1
                bych[ch]['spent'] += cost
                if 'Terror' in nm:
                    mana = min(mx, mana + (25 if L == 1 else 50))
                elif 'Death Pact' in nm and L in (2, 4):
                    mana = min(mx, mana + 150)
                elif 'Avatar' in nm and L in (3, 4):
                    avatar_until = te + (par['dur'] or 30)
            while si < len(sn) and sn[si]['t'] < t1:
                s = sn[si]; si += 1
                base_mx = h['mana_base'] + kM * lvl_int + perm_mana(p, s['t'])
                preds.append({'snap': s, 'pred': mana, 'max_mod': mx, 'max_base': base_mx})
                if assim:
                    offset = max(offset, s['mana'] - base_mx)
                    mx = base_mx + offset
                    mana = min(s['mana'], mx)
            mana = max(0.0, min(mx, mana + rg * DT))
            if record:
                frac = mana / mx if mx > 0 else 0
                b = 0 if frac < 0.2 else (2 if frac > 0.8 else 1)
                zone['partita'][b] += DT
                ch = challenge_of(t)
                if ch:
                    zone['combattimento'][b] += DT
                    zone[ch][b] += DT
            t = t1
        return preds, stats, zone, bych

    # ---- validazione e calibrazione
    def errors(preds):
        return [(x['pred'] - x['snap']['mana'], x) for x in preds if not x['snap']['excl']]

    valid_rows, rel_rows = [], []
    best = {}
    const_score = {}
    for cname_, (kM, kR) in CONSTS.items():
        tot = []
        viol = 0
        for p in PL:
            pr, _, _, _ = simulate(p, kM, kR, 0.0, True)
            tot += [abs(e) for e, _ in errors(pr)]
            viol += sum(1 for x in pr if x['snap']['mana'] > x['max_base'] + 1 and not x['snap']['excl'])
        const_score[cname_] = (statistics.mean(tot), viol)
    CHOSEN = min(const_score, key=lambda k: (const_score[k][1], const_score[k][0]))
    kM, kR = CONSTS[CHOSEN]
    print('costanti:', const_score, '->', CHOSEN)

    ALPHA = {}
    for p in PL:
        sims = {al: simulate(p, kM, kR, al, True)[0] for al in ALPHAS}
        errs = {al: errors(sims[al]) for al in ALPHAS}
        n = len(errs[0.0])
        loo = []
        for i in range(n):
            al_i = min(ALPHAS, key=lambda al: (sum(abs(e) for k, (e, _) in enumerate(errs[al]) if k != i), abs(al)))
            loo.append(errs[al_i][i][0])
        al_all = min(ALPHAS, key=lambda al: (sum(abs(e) for e, _ in errs[al]), abs(al)))
        ALPHA[p] = al_all
        free = errors(simulate(p, kM, kR, 0.0, False)[0])
        free_cal = errors(simulate(p, kM, kR, al_all, False)[0])
        e0 = errs[0.0]
        mx_mean = statistics.mean(x['max_mod'] for _, x in e0) if e0 else float('nan')
        mae = lambda xs: statistics.mean(abs(v) for v in xs) if xs else float('nan')
        loo_pct = mae(loo) / mx_mean * 100 if e0 else float('nan')
        # baseline ingenua: "il mana resta quello dello screenshot precedente" (stessi snapshot validi)
        pers = []
        prev = None
        for x in sims[0.0]:
            s_ = x['snap']
            if prev is not None and not s_['excl']:
                pers.append(prev - s_['mana'])
            prev = s_['mana']
        base_mae = mae(pers)
        if loo_pct <= 15 and mae(loo) < base_mae:
            judge = 'affidabile'
        elif loo_pct <= 25 and mae(loo) <= 1.1 * base_mae:
            judge = 'indicativa'
        else:
            judge = 'non affidabile'
        r = roles[p]
        rel_rows.append({
            'classe': r['classe'], 'ruolo': r['ruolo'], 'costanti_usate': CHOSEN,
            'snapshot_totali': len(snaps_by_p[p]), 'snapshot_validi': n,
            'mana_max_medio_modello': mx_mean,
            'mae_libera': mae([e for e, _ in free]), 'mae_libera_calibrata': mae([e for e, _ in free_cal]),
            'mae_assimilata_alpha0': mae([e for e, _ in e0]),
            'bias_assimilata_alpha0': statistics.mean(e for e, _ in e0) if e0 else float('nan'),
            'mae_assimilata_loo': mae(loo), 'mae_loo_pct_mana_max': loo_pct,
            'mae_baseline_persistenza': base_mae,
            'alpha_regen_extra_mana_s': al_all, 'giudizio': judge})
        pr_free = simulate(p, kM, kR, 0.0, False)[0]
        pr_a0 = sims[0.0]
        pr_al = sims[al_all]
        loo_map = {id(x['snap']): v for v, (_, x) in zip(loo, e0)}
        for xf, xa, xc in zip(pr_free, pr_a0, pr_al):
            s = xa['snap']
            valid_rows.append({
                'classe': r['classe'], 'ruolo': r['ruolo'], 'screenshot': s['shot'], 'tempo_s': s['t'],
                'challenge_completate': s['challenge'], 'fase': s['phase'], 'livello_eroe': s['level'], 'hp_pct': s['hp'],
                'mana_osservato': s['mana'], 'mana_max_modello_base': xa['max_base'], 'mana_max_modello_assimilato': xa['max_mod'],
                'oltre_max_modello': 'si' if s['mana'] > xa['max_base'] + 1 else 'no',
                'prev_libera': xf['pred'], 'prev_assimilata_alpha0': xa['pred'], 'prev_assimilata_calibrata': xc['pred'],
                'errore_assimilata_loo': loo_map.get(id(s), ''),
                'escluso_validazione': s['excl'] or ''})
    write('validazione_mana_snapshot.csv', valid_rows, list(valid_rows[0]))
    # zone sugli screenshot: mana MISURATO / mana massimo del MODELLO (max assimilato: mai sotto il valore osservato)
    obs_rows = []
    for p in PL:
        r = roles[p]
        vv = [v for v in valid_rows if v['classe'] == r['classe'] and not v['escluso_validazione']]
        fr = [v['mana_osservato'] / v['mana_max_modello_assimilato'] for v in vv if v['mana_max_modello_assimilato'] > 0]
        n = len(fr)
        obs_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'snapshot_validi': n,
                         'pct_snapshot_sotto_20': 100 * sum(f < 0.2 for f in fr) / n if n else '',
                         'pct_snapshot_20_80': 100 * sum(0.2 <= f <= 0.8 for f in fr) / n if n else '',
                         'pct_snapshot_sopra_80': 100 * sum(f > 0.8 for f in fr) / n if n else '',
                         'mana_osservato_medio': statistics.mean(v['mana_osservato'] for v in vv) if vv else '',
                         'frazione_mana_media': statistics.mean(fr) if fr else '',
                         'tipo_dato': 'mana misurato (screenshot) / mana max stimato'})
    write('zone_mana_snapshot_osservate.csv', obs_rows, list(obs_rows[0]))
    write('affidabilita_simulazione_mana.csv', rel_rows, list(rel_rows[0]))
    REL = {r['classe']: r for r in rel_rows}

    # ---- simulazione finale
    FINAL, FINAL0 = {}, {}
    for p in PL:
        FINAL[p] = simulate(p, kM, kR, ALPHA[p], True, record=True)
        FINAL0[p] = simulate(p, kM, kR, 0.0, True, record=True)   # sensibilita': senza calibrazione
    # filtro solo cooldown (indipendente dal mana simulato) per la parte B
    CDONLY = {p: simulate(p, kM, kR, ALPHA[p], True, cast_filter_mana=False) for p in PL}

    # ---- parametri abilita'
    par_rows = []
    for p in PL:
        r = roles[p]
        for aid in sorted({a for _, a, _, _ in orders[p]}):
            par = PAR[aid]
            for L in range(1, par['levels'] + 1):
                par_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'abilita': ANAME[(p, aid)],
                                 'nome_in_mappa': clean(W3A.get(aid, {'mods': {}})['mods'].get(('anam', 0)) or ''), 'ability_id': aid,
                                 'abilita_base': par['base'], 'livello': L, 'costo_mana': lvl_val(par['cost'], L),
                                 'cooldown_s': lvl_val(par['cd'], L), 'fonte_valori': par['src']})
    write('parametri_abilita.csv', par_rows, list(par_rows[0]))
    ev_rows = []
    for p in PL:
        for t, ab, da, a_, nm in lvl_events[p]:
            ev_rows.append({'classe': roles[p]['classe'], 'tempo_s': t, 'challenge_in_corso': segment_of(t),
                            'talento': nm, 'ability_id': ab, 'abilita': ANAME.get((p, ab), ''), 'livello_da': da, 'livello_a': a_})
        for t, ii, im, ir, nm in perm[p]:
            ev_rows.append({'classe': roles[p]['classe'], 'tempo_s': t, 'challenge_in_corso': segment_of(t),
                            'talento': nm, 'ability_id': '', 'abilita': f'bonus INT {ii:+g}, mana max {im:+g}, regen {ir*100:+g}%',
                            'livello_da': '', 'livello_a': ''})
    ev_rows.sort(key=lambda x: (x['classe'], x['tempo_s']))
    write('eventi_livelli_e_bonus.csv', ev_rows, ['classe', 'tempo_s', 'challenge_in_corso', 'talento', 'ability_id', 'abilita', 'livello_da', 'livello_a'])

    # ---- B: cooldown
    def cd_intervals(p, aid, use_mana):
        """Intervalli [cast, cast+cd] dei cast effettivi (ricalcolati con lo stesso filtro della simulazione)."""
        out = []
        nxt = -1
        for t, a, nm, _ in sorted(orders[p]):
            if a != aid or t < nxt:
                continue
            cd = lvl_val(PAR[aid]['cd'], level_at(p, aid, t))
            out.append((t, t + cd))
            nxt = t + cd
        return out

    def overlap(iv, a, b):
        return sum(max(0, min(y, b) - max(x, a)) for x, y in iv)

    cd_rows, cdch_rows = [], []
    for p in PL:
        r = roles[p]
        tend = min(leaves.get(p, END), END)
        t0 = t_create.get(p, 0)
        stats_cd = CDONLY[p][1]
        stats_m = FINAL[p][1]
        n_ord = Counter(a for _, a, _, _ in orders[p])
        for aid in sorted(n_ord, key=lambda a: -n_ord[a]):
            par = PAR[aid]
            iv = cd_intervals(p, aid, False)
            occ_c = sum(overlap(iv, a, b) for a, b, _ in WIN.values())
            occ_g = overlap(iv, t0, tend)
            cds = sorted({lvl_val(par['cd'], level_at(p, aid, t)) for t, a, _, _ in orders[p] if a == aid})
            costs = sorted({lvl_val(par['cost'], level_at(p, aid, t)) for t, a, _, _ in orders[p] if a == aid})
            gaps = []
            last = None
            for t, a, _, _ in sorted(orders[p]):
                if a != aid:
                    continue
                if last is not None:
                    gaps.append(t - last)
                last = t
            cdmin = min(cds) if cds else 0
            near = sum(1 for g in gaps if cdmin and 0.5 * cdmin <= g < cdmin)
            note = []
            if cdmin == 0:
                note.append('cooldown 0: nessun filtro possibile')
            if gaps and cdmin and near / len(gaps) > 0.15:
                note.append('molti ordini a 50-99% del cooldown: possibile riduzione cooldown non modellata')
            if 'Parasite' in ANAME[(p, aid)] or 'Searing' in ANAME[(p, aid)]:
                note.append('abilita con autocast: i cast automatici non sono nel replay')
            cd_rows.append({
                'classe': r['classe'], 'ruolo': r['ruolo'], 'abilita': ANAME[(p, aid)],
                'nome_in_mappa': clean(W3A.get(aid, {'mods': {}})['mods'].get(('anam', 0)) or ''), 'ability_id': aid,
                'cooldown_s': '/'.join(f'{c:g}' for c in cds), 'costo_mana': '/'.join(f'{c:g}' for c in costs),
                'ordini_totali': n_ord[aid], 'cast_effettivi_stimati': stats_cd['cast'][aid],
                'ordini_sprecati_in_cooldown': stats_cd['cd_waste'][aid],
                'quota_ordini_sprecati_pct': 100 * stats_cd['cd_waste'][aid] / n_ord[aid],
                'cast_effettivi_con_mana_sim': stats_m['cast'][aid], 'ordini_respinti_mana_sim': stats_m['mana_rej'][aid],
                'cooldown_occupato_pct_combattimento': 100 * occ_c / COMBAT if cdmin else '',
                'cooldown_occupato_pct_partita': 100 * occ_g / (tend - t0) if cdmin else '',
                'cast_max_teorici_combattimento': COMBAT / cdmin if cdmin else '',
                'cast_in_combattimento': sum(1 for x, _ in iv if challenge_of(x)),
                'mana_speso_stimato': stats_m['cast'][aid] * statistics.mean(costs) if costs else 0,
                'note': '; '.join(note)})
            for c, (a, b, _) in WIN.items():
                o_c = sum(1 for t, x, _, _ in orders[p] if x == aid and a <= t < b)
                cast_c = sum(1 for x, _ in iv if a <= x < b)
                cdch_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'challenge': c, 'abilita': ANAME[(p, aid)],
                                  'ordini': o_c, 'cast_effettivi_stimati': cast_c, 'ordini_sprecati': o_c - cast_c,
                                  'cooldown_occupato_pct': 100 * overlap(iv, a, b) / (b - a) if cdmin else ''})
    write('cooldown_abilita_classe.csv', cd_rows, list(cd_rows[0]))
    write('cooldown_abilita_challenge.csv', cdch_rows, list(cdch_rows[0]))

    # ---- A: zone di mana
    def pct(z):
        s = sum(z)
        return [100 * v / s if s else float('nan') for v in z]

    zone_rows, zch_rows = [], []
    for p in PL:
        r = roles[p]
        rel = REL[r['classe']]
        zone, bych = FINAL[p][2], FINAL[p][3]
        for amb in ('combattimento', 'partita'):
            lo, mid, hi = pct(zone[amb])
            lo0, mid0, hi0 = pct(FINAL0[p][2][amb])
            zone_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'ambito': amb, 'secondi': sum(zone[amb]),
                              'pct_sotto_20': lo, 'pct_20_80': mid, 'pct_sopra_80': hi,
                              'pct_sotto_20_senza_calibrazione': lo0, 'pct_20_80_senza_calibrazione': mid0,
                              'pct_sopra_80_senza_calibrazione': hi0,
                              'affidabilita_simulazione': rel['giudizio'], 'errore_loo_pct_mana_max': rel['mae_loo_pct_mana_max'],
                              'tipo_dato': 'stima da simulazione'})
        for c in range(1, 21):
            lo, mid, hi = pct(zone[c])
            zch_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'challenge': c,
                             'secondi_combattimento': sum(zone[c]), 'pct_sotto_20': lo, 'pct_20_80': mid, 'pct_sopra_80': hi,
                             'cast_effettivi_sim': bych[c]['cast'], 'ordini_sprecati_cooldown': bych[c]['waste'],
                             'ordini_respinti_mana_sim': bych[c]['rej'], 'mana_speso_sim': bych[c]['spent'],
                             'affidabilita_simulazione': rel['giudizio']})
    write('zone_mana_classe.csv', zone_rows, list(zone_rows[0]))
    write('zone_mana_challenge.csv', zch_rows, list(zch_rows[0]))

    # ---- C: riepiloghi
    summ = []
    for p in PL:
        r = roles[p]
        rel = REL[r['classe']]
        zc = {z['ambito']: z for z in zone_rows if z['classe'] == r['classe']}
        rows_c = [x for x in cd_rows if x['classe'] == r['classe']]
        occ = [x['cooldown_occupato_pct_combattimento'] for x in rows_c if x['cooldown_occupato_pct_combattimento'] != '']
        w = [x['cast_effettivi_stimati'] for x in rows_c if x['cooldown_occupato_pct_combattimento'] != '']
        mins_c = COMBAT / 60
        summ.append({
            'classe': r['classe'], 'ruolo': r['ruolo'], 'attributo': r['attributo'],
            'pct_mana_20_80_combattimento': zc['combattimento']['pct_20_80'],
            'pct_mana_sotto_20_combattimento': zc['combattimento']['pct_sotto_20'],
            'pct_mana_sopra_80_combattimento': zc['combattimento']['pct_sopra_80'],
            'pct_mana_20_80_partita': zc['partita']['pct_20_80'],
            'affidabilita_simulazione': rel['giudizio'], 'errore_loo_pct_mana_max': rel['mae_loo_pct_mana_max'],
            'abilita_attive_usate': len(rows_c),
            'ordini_abilita': sum(x['ordini_totali'] for x in rows_c),
            'cast_effettivi_stimati': sum(x['cast_effettivi_stimati'] for x in rows_c),
            'ordini_sprecati_in_cooldown': sum(x['ordini_sprecati_in_cooldown'] for x in rows_c),
            'quota_ordini_sprecati_pct': 100 * sum(x['ordini_sprecati_in_cooldown'] for x in rows_c) / max(1, sum(x['ordini_totali'] for x in rows_c)),
            'cast_in_combattimento_al_minuto': sum(x['cast_in_combattimento'] for x in rows_c) / mins_c,
            'cooldown_occupato_medio_pct_combattimento': statistics.mean(occ) if occ else '',
            'cooldown_occupato_max_pct_combattimento': max(occ) if occ else '',
            'abilita_piu_sfruttata': max(rows_c, key=lambda x: x['cooldown_occupato_pct_combattimento'] or 0)['abilita'] if rows_c else '',
            'mana_speso_stimato': sum(x['mana_speso_stimato'] for x in rows_c),
            'ordini_respinti_mana_sim': sum(x['ordini_respinti_mana_sim'] for x in rows_c)})
    write('riepilogo_classe.csv', summ, list(summ[0]))
    by_role = defaultdict(list)
    for s in summ:
        by_role[s['ruolo']].append(s)
    rr = []
    for role, ss in by_role.items():
        def m(k):
            v = [s[k] for s in ss if s[k] != '' and not (isinstance(s[k], float) and math.isnan(s[k]))]
            return statistics.mean(v) if v else ''
        ok = [s for s in ss if s['affidabilita_simulazione'] != 'non affidabile']
        def mo(k):
            v = [s[k] for s in ok]
            return statistics.mean(v) if v else ''
        rr.append({'ruolo': role, 'classi': ' + '.join(s['classe'] for s in ss), 'n_classi': len(ss),
                   'classi_usate_per_mana': ' + '.join(s['classe'] for s in ok) or 'nessuna (simulazione non affidabile)',
                   'pct_mana_20_80_combattimento': mo('pct_mana_20_80_combattimento'),
                   'pct_mana_sotto_20_combattimento': mo('pct_mana_sotto_20_combattimento'),
                   'pct_mana_sopra_80_combattimento': mo('pct_mana_sopra_80_combattimento'),
                   'classi_simulazione_affidabile': sum(1 for s in ss if s['affidabilita_simulazione'] == 'affidabile'),
                   'cast_in_combattimento_al_minuto': m('cast_in_combattimento_al_minuto'),
                   'quota_ordini_sprecati_pct': m('quota_ordini_sprecati_pct'),
                   'cooldown_occupato_medio_pct_combattimento': m('cooldown_occupato_medio_pct_combattimento')})
    write('riepilogo_ruolo.csv', rr, list(rr[0]))
    # per ruolo x challenge
    rc = []
    for role, ss in by_role.items():
        cls = {s['classe'] for s in ss}
        cls_ok = {s['classe'] for s in ss if s['affidabilita_simulazione'] != 'non affidabile'}
        for c in range(1, 21):
            zz = [z for z in zch_rows if z['classe'] in cls_ok and z['challenge'] == c]
            zall = [z for z in zch_rows if z['classe'] in cls and z['challenge'] == c]
            cc = [x for x in cdch_rows if x['classe'] in cls and x['challenge'] == c and x['cooldown_occupato_pct'] != '']
            def mm(rows, k):
                v = [x[k] for x in rows if not (isinstance(x[k], float) and math.isnan(x[k]))]
                return statistics.mean(v) if v else ''
            rc.append({'ruolo': role, 'challenge': c, 'pct_mana_20_80': mm(zz, 'pct_20_80'), 'pct_mana_sotto_20': mm(zz, 'pct_sotto_20'),
                       'pct_mana_sopra_80': mm(zz, 'pct_sopra_80'),
                       'classi_usate_per_mana': ' + '.join(sorted(cls_ok)) or 'nessuna',
                       'cast_effettivi': sum(z['cast_effettivi_sim'] for z in zall),
                       'ordini_sprecati_cooldown': sum(z['ordini_sprecati_cooldown'] for z in zall),
                       'cooldown_occupato_medio_pct': mm(cc, 'cooldown_occupato_pct')})
    write('riepilogo_ruolo_challenge.csv', rc, list(rc[0]))
    fin = [{'challenge': c, 'inizio_s': a, 'fine_s': b, 'durata_s': b - a, 'fonte': src} for c, (a, b, src) in WIN.items()]
    write('finestre_combattimento.csv', fin, list(fin[0]))

    # ---- diagnostica a video (per NOTE.md)
    print('\ncombattimento totale (s):', COMBAT, 'pausa mediana', med_break)
    print('eroi (id) trovati:', len(hid), ' innervate mappati:',
          sum(1 for _, _, nm, tg in orders['BoomKhamenei'] if 'Innervate' in nm and tg in id_to_player), '/',
          sum(1 for _, _, nm, tg in orders['BoomKhamenei'] if 'Innervate' in nm))
    print('innervate per bersaglio:', Counter(roles[id_to_player[tg]]['classe'] for _, _, nm, tg in orders['BoomKhamenei']
                                               if 'Innervate' in nm and tg in id_to_player))
    print('brilliance:', brill_ab, brill_val, 'pct flag', brill_pct, 'appresa a', brill_t, 'liv2 a', brill_lv2_t)
    print('mana tide ticks', tide_ticks)
    print('ordini non risolti:', {(roles[p]['classe'], n, w): c for (p, n, w), c in unresolved.items()})
    for p in PL:
        h = HERO[p]
        print(roles[p]['classe'], h['hero'], 'int0', h['int0'], 'inp', h['inp'], 'base', h['mana_base'], 'regen', h['regen_base'],
              'alpha', ALPHA[p], 'perm', [(round(t), ii, im, ir) for t, ii, im, ir, _ in perm[p]][:12])


if __name__ == '__main__':
    main()
