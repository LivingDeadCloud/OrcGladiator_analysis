"""Domanda 02 - L'acquisto degli oggetti e' ottimale?

Si lancia dalla cartella del progetto:
    python data_analysis/v2/domande/02_acquisto_oggetti/analisi_acquisti.py

Legge (sola lettura): data_replay/actions_named.csv, data_replay/chat.csv, data_map/class_roles.csv,
data_map/raw/war3map.{w3t,w3u,wts,j}, data_screenshots/multiboard_snapshots.csv,
data_analysis/v2/abilita_mana/finestre_combattimento.csv, data_analysis/v2/aggregato/classe_challenge.csv,
data_analysis/v2/cure/uso_pozioni_slot.csv e (se presente) Units\\ItemData.slk dagli MPQ di Warcraft III
per i costi non modificati dalla mappa.
Scrive i CSV nella stessa cartella dello script. Negli output non compaiono nomi di giocatori.
"""
import csv, os, re, sys, bisect, collections, statistics

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
import objdata  # noqa: E402

OUT = os.path.dirname(os.path.abspath(__file__))
WC3 = r'C:\Program Files (x86)\Warcraft III'
BS = '\\'


def rd(path):
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def wr(name, rows, cols=None):
    cols = cols or list(rows[0].keys())
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
    print('scritto', name, len(rows))


# ------------------------------------------------------------------------------------------- mappa
wts = objdata.parse_wts(open(os.path.join(ROOT, 'data_map/raw/war3map.wts'), 'rb').read())
W3T = objdata.parse_obj(open(os.path.join(ROOT, 'data_map/raw/war3map.w3t'), 'rb').read(), 'w3t', wts)
W3U = objdata.parse_obj(open(os.path.join(ROOT, 'data_map/raw/war3map.w3u'), 'rb').read(), 'w3u', wts)
JASS = open(os.path.join(ROOT, 'data_map/raw/war3map.j'), encoding='latin-1').read()


def base_item_costs():
    """Costo oro di default degli oggetti base (ItemData.slk), solo lettura. {} se non disponibile."""
    try:
        from mpq import MPQ
        from analisi_abilita_mana import slk
    except Exception:
        return {}
    for arc in ('War3Patch.mpq', 'War3x.mpq', 'war3.mpq'):
        try:
            d = MPQ(os.path.join(WC3, arc)).read('Units' + BS + 'ItemData.slk')
        except Exception:
            d = None
        if d:
            return {k: v.get('goldcost') for k, v in slk(d).items()}
    return {}


BASECOST = base_item_costs()


def imods(code):
    o = W3T.get(code)
    return ({f: v for (f, l), v in o['mods'].items()}, o['base']) if o else ({}, None)


# negozi
SHOP = {}
for k, o in W3U.items():
    m = {f: v for (f, l), v in o['mods'].items()}
    for it in (m.get('usei') or '').split(','):
        if it:
            SHOP[it] = objdata.clean(m.get('unam', k))

# nomi mancanti (unam assente): ricavati dal tooltip / dall'oggetto base
NOME_EXTRA = {'I093': 'I093 (reliquia senza nome: +4 Agi/+4 Int)',
              'I05S': 'I05S (base fgfh = Spiked Collar: evoca 2 Felhound)'}

# bonus agli attributi letti a mano dai tooltip della mappa (utub) degli oggetti comprati
ATTR = {  # codice: (STR, AGI, INT, nota)
    'I02W': (10, 10, 10, '+1/+2 a tutti a fine round'),
    'I09T': (0, 15, 15, ''),
    'I093': (0, 4, 4, ''),
    'I094': (4, 0, 4, ''),
    'I095': (4, 4, 0, ''),
    'I096': (6, 0, 0, ''),
    'I09F': (25, 0, 0, ''),
    'I00N': (6, 6, 6, 'premio fine round +1 stat -> +25 oro'),
    'I070': (10, 10, 10, ''),
}

# categoria funzionale (dal tooltip), usata per la coerenza col ruolo
FUNZ = {
    'I06Z': 'stivali (rigenerazione)', 'I00N': 'stivali (attributi/oro)', 'I06T': 'stivali (mana)',
    'I00K': 'stivali (mana, Spell Shield)', 'I070': 'stivali (attributi, armatura, blink)',
    'I071': 'stivali (difesa: armatura+HP)', 'I072': 'stivali (attacco: velocita/danno)',
    'I00R': 'pozione solo mana', 'I00Q': 'pozione cura 40% HP', 'I00W': 'pozione cura 25% HP + 100 mana + vel. attacco',
    'I056': 'scommessa (+60 oro dopo 2 round se non muori)', 'I05S': 'evocazione (Felhound)',
    'I00X': 'cooldown (reset a fine round)', 'I02S': 'mana (regen +250%)', 'I02W': 'attributi',
    'I02X': 'attacco (danno +90, vel. +20%)', 'I04Z': 'potenzia un oggetto (Corrosive Oil, Charm, Mask...)',
    'I05H': 'difesa (armatura, spine)', 'I05V': 'difesa + riduzione armatura nemici (aura)',
    'I05X': 'attacco + difesa (armatura, vel. attacco, lifesteal)', 'I088': 'difesa (armatura +25, resistenza)',
    'I08B': 'squadra (+50% danno a tutti gli alleati)', 'I08F': 'squadra (aura armatura, attiva +100 armatura)',
    'I093': 'attributi + potenzia Embolden/Rejuvenation/Rock Shield/Parasite',
    'I094': 'attributi + potenzia ultimate Wizard Staff ecc.', 'I095': 'attributi + potenzia Avatar/Towers ecc.',
    'I096': 'tank (Str, mana, cura al cast)', 'I09A': 'tank (taunt attivo, blocco)', 'I09F': 'tank (Str +25, attiva +10000 HP)',
    'I09I': 'squadra (bonus agli eroi alleati)', 'I09L': 'attacco (danno crescente nel round)',
    'I09N': 'attacco (danno, riduzione armatura)', 'I09O': 'attacco/boss (danno, -30% danni dai boss)',
    'I09T': 'attributi Int/Agi + bonus alle evocazioni',
}


def categoria(code, nome):
    if nome.startswith('('):
        return 'talento'
    if 'Arena Teleport' in nome:
        return 'teletrasporto (gratis)'
    if code == 'I06J':
        return 'resurrezione (Ancestral Stone, gratis)'
    if nome.startswith('Tome'):
        return 'tomo'
    if code in ('I00R', 'I00Q', 'I00W'):
        return 'pozione'
    if 'Purchase' in nome:
        return 'stivali'
    return 'oggetto'


def info(code):
    m, base = imods(code)
    nome = objdata.clean(m.get('unam') or '') or NOME_EXTRA.get(code, code)
    if code in NOME_EXTRA:
        nome = NOME_EXTRA[code]
    if m.get('igol') is not None:
        costo, fonte = m.get('igol'), 'mappa (igol)'
    else:
        c = BASECOST.get(base)
        costo, fonte = (int(c), 'default oggetto base %s (ItemData.slk)' % base) if c else (None, 'non trovato')
    return {'codice': code, 'nome': nome, 'categoria': categoria(code, nome), 'negozio': SHOP.get(code, ''),
            'costo_oro': costo, 'fonte_costo': fonte, 'costo_punti_talento': m.get('ilum') or 0,
            'classe_oggetto_wc3': m.get('icla') or '', 'effetto_tooltip': objdata.clean(m.get('utub') or '')[:300]}


# ------------------------------------------------------------------------------------------- giocatori, tempi
ROLES = {r['player']: r for r in rd('data_map/class_roles.csv')}
CL = {p: r['classe'] for p, r in ROLES.items()}
RUOLO = {r['classe']: r['ruolo'] for r in ROLES.values()}
ATTRP = {r['classe']: r['attributo'] for r in ROLES.values()}

WIN = [(int(r['challenge']), float(r['inizio_s']), float(r['fine_s']))
       for r in rd('data_analysis/v2/abilita_mana/finestre_combattimento.csv')]


def fase(t):
    for c, a, b in WIN:
        if a <= t <= b:
            return c, 'durante challenge %d' % c
    prev = [c for c, a, b in WIN if b < t]
    if not prev:
        return 0, 'prima della challenge 1'
    c = max(prev)
    return c, ('pausa dopo challenge %d' % c) if c < 20 else 'dopo challenge 20'


SNAP = collections.defaultdict(list)  # classe -> [(t, livello, oro, challenges_completed, phase)]
for r in rd('data_screenshots/multiboard_snapshots.csv'):
    SNAP[CL[r['player']]].append((int(r['game_time_s']), int(r['level']), int(r['gold']) if r['gold'] else None,
                                  r['challenges_completed'], r['phase']))
for c in SNAP:
    SNAP[c].sort()


def livello(c, t):
    s = SNAP[c]
    if t <= s[0][0]:
        return float(s[0][1])  # prima del primo screenshot: limite superiore
    for (t0, l0, *_), (t1, l1, *_) in zip(s, s[1:]):
        if t0 <= t <= t1:
            return l0 + (l1 - l0) * (t - t0) / (t1 - t0) if t1 > t0 else float(l1)
    return float(s[-1][1])


# ------------------------------------------------------------------------------------------- acquisti
acts = rd('data_replay/actions_named.csv')
ORD = [r for r in acts if r['order'].startswith('I0')]
CACHE = {}
acq = []
seen_unique = collections.defaultdict(set)
last_same = {}
boots_last = {}
for r in ORD:
    c = CL[r['player']]
    t = int(r['game_time_ms']) / 1000
    code = r['order']
    inf = CACHE.setdefault(code, info(code))
    nchal, fdesc = fase(t)
    lv = livello(c, t)
    note = []
    key = (c, code)
    if key in last_same and t - last_same[key] < 2:
        note.append('ripetuto entro 2 s (doppio click?)')
    last_same[key] = t
    if inf['categoria'] == 'tomo' and lv < 12:
        note.append('livello stimato <12: il trigger Tomes_Buy rimborsa 110 oro (acquisto annullato)')
    if 'Unique' in inf['effetto_tooltip'] and code in seen_unique[c]:
        note.append('oggetto Unique gia acquistato prima')
    seen_unique[c].add(code)
    rimborso = 0
    if inf['categoria'] == 'stivali':
        if c in boots_last:
            rimborso = round(0.75 * (boots_last[c] or 0))
            note.append('rimborso 75%% stivali precedenti: %d oro' % rimborso)
        boots_last[c] = inf['costo_oro']
    acq.append({'classe': c, 'ruolo': RUOLO[c], 'tempo_s': round(t, 1), 'challenge_rif': nchal, 'fase': fdesc,
                'livello_eroe_stimato': round(lv, 1), 'codice': code, 'oggetto': inf['nome'],
                'categoria': inf['categoria'], 'negozio': inf['negozio'], 'costo_oro': inf['costo_oro'],
                'costo_punti_talento': inf['costo_punti_talento'], 'rimborso_stimato': rimborso,
                'note': '; '.join(note)})

wr('cronologia_acquisti.csv', acq)

# catalogo: tutti gli oggetti dei negozi + quelli ordinati
codes = sorted(set(SHOP) | {r['codice'] for r in acq})
cat = []
nacq = collections.Counter(r['codice'] for r in acq)
for code in codes:
    if code not in W3T:
        continue
    inf = CACHE.setdefault(code, info(code))
    a = ATTR.get(code)
    cat.append({**inf, 'bonus_str': a[0] if a else '', 'bonus_agi': a[1] if a else '', 'bonus_int': a[2] if a else '',
                'funzione': FUNZ.get(code, ''), 'ordini_in_partita': nacq.get(code, 0)})
wr('catalogo_oggetti.csv', cat)

# ------------------------------------------------------------------------------------------- uso attivi (useslot)
useslot = collections.defaultdict(collections.Counter)
for r in acts:
    if r['order'].startswith('useslot'):
        useslot[CL[r['player']]][r['order']] += 1

# ------------------------------------------------------------------------------------------- prestiti (chat)
chat = rd('data_replay/chat.csv')
loans = collections.defaultdict(list)  # classe -> [(t, tipo, importo)]
for r in chat:
    msg = r['message'].strip()
    t = int(r['game_time_ms']) / 1000
    if msg.startswith('-borrow'):
        m = re.search(r'(\d+)', msg)
        loans[CL[r['player']]].append((t, 'borrow', int(m.group(1)) if m else None))
    elif msg.startswith('-loan'):
        loans[CL[r['player']]].append((t, 'loan', None))

# ------------------------------------------------------------------------------------------- riconciliazione oro
# Premi individuali di fine round (JASS: "Best damage/tank/healer that round", LeaderGoldReward = 2.5*(ondata-1),
# una variante usa 2*(ondata-1)): stimati da rounds.csv. Royal Greaves: +25 oro a fine round invece di +1 stat.
PREMI = collections.Counter()  # (classe, challenge) -> oro
for r in rd('data_screenshots/rounds.csv'):
    try:
        ch = int(r['challenge'])
    except ValueError:
        continue
    for col in ('best_damage', 'best_tank', 'best_boss_slayer', 'best_healer'):
        if r.get(col) in CL:
            PREMI[(CL[r[col]], ch)] += int(2.5 * (ch - 1))
royal = {r['classe']: r['tempo_s'] for r in acq if r['codice'] == 'I00N'}
rec = []
for c in SNAP:
    s = [x for x in SNAP[c] if x[2] is not None]
    for (t0, l0, g0, cc0, p0), (t1, l1, g1, cc1, p1) in zip(s, s[1:]):
        if t1 == t0:
            continue
        spese = sum((r['costo_oro'] or 0) for r in acq if r['classe'] == c and t0 < r['tempo_s'] <= t1)
        rimb = sum(r['rimborso_stimato'] for r in acq if r['classe'] == c and t0 < r['tempo_s'] <= t1)
        rimb += sum(110 for r in acq if r['classe'] == c and t0 < r['tempo_s'] <= t1 and 'rimborsa 110' in r['note'])
        premi = PREMI.get((c, int(cc1)), 0) if p1 == 'post' and cc1 != cc0 else 0
        if c in royal and royal[c] < t0 and p1 == 'post' and cc1 != cc0:
            premi += 25
        nb = sum(1 for x in loans[c] if t0 < x[0] <= t1 and x[1] == 'borrow')
        nl = sum(1 for x in loans[c] if t0 < x[0] <= t1 and x[1] == 'loan')
        rec.append({'classe': c, 'ruolo': RUOLO[c], 'da_s': t0, 'a_s': t1, 'challenge_completate_a': cc1, 'fase_a': p1,
                    'oro_inizio': g0, 'oro_fine': g1, 'spesa_ordini': spese, 'rimborsi_stimati': rimb,
                    'premi_individuali_stimati': premi,
                    'entrata_comune_implicita': g1 - g0 + spese - rimb - premi,
                    'richieste_borrow': nb, 'comandi_loan': nl})
by_int = collections.defaultdict(list)
for r in rec:
    by_int[(r['da_s'], r['a_s'])].append(r['entrata_comune_implicita'])
prev_loan = {}
for r in rec:
    med = statistics.median(by_int[(r['da_s'], r['a_s'])])
    r['mediana_squadra'] = med
    r['scarto_da_mediana'] = r['entrata_comune_implicita'] - med
    tocc = bool(r['richieste_borrow'] or r['comandi_loan'] or prev_loan.get(r['classe']))
    prev_loan[r['classe']] = bool(r['richieste_borrow'] or r['comandi_loan'])
    r['prestiti_in_gioco'] = 'si' if tocc else 'no'
    flag = ''
    if abs(r['scarto_da_mediana']) > 100:
        if tocc:
            flag = 'scarto spiegabile con prestiti (-borrow/-loan, rimborso automatico a inizio wave)'
        elif r['scarto_da_mediana'] > 0:
            flag = 'oro in piu non spiegato: possibile acquisto fallito, vendita o premio non modellato'
        else:
            flag = 'oro in meno non spiegato: possibile spesa non vista o premio altrui'
    r['segnalazione'] = flag
wr('riconciliazione_oro.csv', rec)

# ------------------------------------------------------------------------------------------- riepilogo per classe
CC = rd('data_analysis/v2/aggregato/classe_challenge.csv')
TALENT_LV = [8, 10, 12, 14, 16, 18, 21, 24, 27, 30]
riep = []
for c in sorted(SNAP, key=lambda x: (RUOLO[x], x)):
    a = [r for r in acq if r['classe'] == c]
    gold_items = [r for r in a if r['categoria'] in ('oggetto', 'stivali', 'pozione')]
    tomi = [r for r in a if r['categoria'] == 'tomo']
    tomi_ok = [r for r in tomi if 'rimborsa' not in r['note']]
    tal = [r for r in a if r['categoria'] == 'talento']
    lv_fin = max(x[1] for x in SNAP[c])
    punti = sum(1 for L in TALENT_LV if L <= lv_fin)
    spesa_ogg = sum((r['costo_oro'] or 0) - r['rimborso_stimato'] for r in gold_items)
    spesa_tomi = sum(r['costo_oro'] for r in tomi_ok)
    pre_boss = [x for x in SNAP[c] if x[4] == 'post' and x[3] == '19']
    oro_boss = [x[2] for x in SNAP[c] if x[4] in ('boss', 'sconfitta') and x[2] is not None]
    gold_post = [x[2] for x in SNAP[c] if x[4] == 'post' and x[2] is not None]
    bonus = collections.Counter()
    for r in a:
        if r['codice'] in ATTR:
            s_, ag, in_, _ = ATTR[r['codice']]
            bonus['Strength'] += s_; bonus['Agility'] += ag; bonus['Intelligence'] += in_
    for r in tomi_ok:
        n = r['oggetto']
        if 'Strength' in n: bonus['Strength'] += 2
        elif 'Agility' in n: bonus['Agility'] += 2
        elif 'Intelligence' in n: bonus['Intelligence'] += 2
        elif '+1 Stats' in n:
            for k in ('Strength', 'Agility', 'Intelligence'): bonus[k] += 1
    tot_b = sum(bonus.values())
    prim = ATTRP[c]
    tomi_txt = collections.Counter(r['oggetto'].replace('Tome: ', '') for r in tomi_ok)
    u = useslot[c]
    riep.append({
        'classe': c, 'ruolo': RUOLO[c], 'attributo_principale': prim,
        'n_ordini_oggetti_oro': len(gold_items),
        'oggetti_comprati': ' | '.join('%s@%ds' % (r['oggetto'].replace('Purchase ', ''), r['tempo_s']) for r in gold_items),
        'spesa_oggetti_netta_rimborsi': spesa_ogg,
        'primo_oggetto_da_500_s': next((r['tempo_s'] for r in gold_items if (r['costo_oro'] or 0) >= 500), ''),
        'n_tomi_validi': len(tomi_ok), 'n_tomi_rimborsati_stimati': len(tomi) - len(tomi_ok), 'spesa_tomi': spesa_tomi,
        'tomi_dettaglio': ' | '.join('%s x%d' % kv for kv in tomi_txt.items()),
        'bonus_attributi_acquistati_str_agi_int': '%d/%d/%d' % (bonus['Strength'], bonus['Agility'], bonus['Intelligence']),
        'quota_bonus_su_attributo_principale_pct': round(100 * bonus[prim] / tot_b, 1) if tot_b else '',
        'livello_finale': lv_fin, 'punti_talento_attesi': punti, 'talenti_comprati': len(tal),
        'punti_talento_non_spesi_stimati': punti - len(tal),
        'oro_medio_post_round': round(statistics.mean(gold_post)) if gold_post else '',
        'oro_max_post_round': max(gold_post) if gold_post else '',
        'oro_dopo_c19': pre_boss[0][2] if pre_boss else '', 'oro_durante_boss_finale': max(oro_boss) if oro_boss else '',
        'usi_slot': ' '.join('%s:%d' % kv for kv in sorted(u.items())),
        'ordini_resurrezione_ancestral': sum(1 for r in a if r['codice'] == 'I06J'),
        'ordini_teletrasporto': sum(1 for r in a if r['categoria'].startswith('teletrasporto')),
    })
wr('riepilogo_classi_acquisti.csv', riep)

# ------------------------------------------------------------------------------------------- quote prima/dopo acquisti importanti
cc_by = collections.defaultdict(dict)
for r in CC:
    try:
        cc_by[r['classe']][int(r['challenge'])] = r
    except ValueError:
        pass


def qround(c, ch, col):
    r = cc_by[c].get(ch)
    try:
        return float(r[col])
    except (TypeError, ValueError, KeyError):
        return None


pp = []
for r in acq:
    if r['categoria'] not in ('oggetto', 'stivali') or (r['costo_oro'] or 0) < 500:
        continue
    c = r['classe']
    nchal = r['challenge_rif']
    # acquisto nella pausa dopo la challenge N -> effetto dalla N+1; durante la N -> dalla N+1 (prudenza)
    after = [nchal + k for k in (1, 2, 3)]
    before = [nchal - k for k in (0, 1, 2)]
    for col, lab in (('danni_quota_round', 'danni'), ('colpi_eroe_quota_round', 'colpi_eroe'), ('cure_quota_round', 'cure')):
        b = [qround(c, x, col) for x in before]; b = [x for x in b if x is not None]
        a_ = [qround(c, x, col) for x in after if x <= 19]; a_ = [qround(c, x, col) for x in after if x <= 19]
        a_ = [x for x in a_ if x is not None]
        if len(b) < 2 or len(a_) < 2:
            continue
        pp.append({'classe': c, 'ruolo': RUOLO[c], 'oggetto': r['oggetto'], 'costo_oro': r['costo_oro'],
                   'tempo_s': r['tempo_s'], 'fase': r['fase'], 'metrica': lab,
                   'challenge_prima': ','.join(map(str, [x for x in before if qround(c, x, col) is not None])),
                   'challenge_dopo': ','.join(map(str, [x for x in after if x <= 19 and qround(c, x, col) is not None])),
                   'quota_media_prima': round(statistics.mean(b), 2), 'quota_media_dopo': round(statistics.mean(a_), 2),
                   'differenza_punti': round(statistics.mean(a_) - statistics.mean(b), 2),
                   'metrica_del_ruolo': 'si' if lab == {'Tank': 'colpi_eroe', 'Healer': 'cure', 'Support': 'cure'}.get(RUOLO[c], 'danni') else 'no'})
wr('quote_prima_dopo_acquisti.csv', pp)

# riferimento ("placebo"): stessa differenza dopo-prima calcolata in OGNI pausa, con o senza acquisti importanti
base = []
for c in SNAP:
    col = {'Tank': 'colpi_eroe_quota_round', 'Healer': 'cure_quota_round', 'Support': 'cure_quota_round'}.get(RUOLO[c], 'danni_quota_round')
    for n in range(2, 19):
        b = [qround(c, x, col) for x in (n, n - 1, n - 2)]; b = [x for x in b if x is not None]
        a_ = [qround(c, x, col) for x in (n + 1, n + 2, n + 3) if x <= 19]; a_ = [x for x in a_ if x is not None]
        if len(b) >= 2 and len(a_) >= 2:
            base.append(statistics.mean(a_) - statistics.mean(b))
dd = [r['differenza_punti'] for r in pp if r['metrica_del_ruolo'] == 'si']
conf = [{'gruppo': 'dopo acquisto >=500 oro (metrica del ruolo)', 'n': len(dd), 'mediana_differenza': statistics.median(dd),
         'quota_positive_pct': round(100 * sum(x > 0 for x in dd) / len(dd), 1)},
        {'gruppo': 'tutte le pause (riferimento)', 'n': len(base), 'mediana_differenza': round(statistics.median(base), 2),
         'quota_positive_pct': round(100 * sum(x > 0 for x in base) / len(base), 1)}]
wr('quote_confronto_riferimento.csv', conf)

# ------------------------------------------------------------------------------------------- oggetti attivabili
# Il replay registra useslotN (slot), non l'oggetto: l'attribuzione slot -> oggetto e' un'ipotesi (colonna confidenza).
SLOT_T = collections.defaultdict(list)
for r in acts:
    if r['order'].startswith('useslot'):
        SLOT_T[(CL[r['player']], r['order'])].append(int(r['game_time_ms']) / 1000)


def combat_after(t):
    return sum(max(0.0, b - max(a, t)) for _, a, b in WIN)


def usi_cd(times, cd):
    n, last = 0, -1e9
    for x in sorted(times):
        if x - last >= cd:
            n += 1; last = x
    return n


def tacq(c, code):
    return next((r['tempo_s'] for r in acq if r['classe'] == c and r['codice'] == code), None)


ATTIVI = [  # classe, codice, cooldown s (tooltip), slot ipotizzato, confidenza, nota
    ('Druid Staff', 'I00R', 40, 'useslot3', 'alta (cure/uso_pozioni_slot.csv)', 'pozione solo mana'),
    ('Pickaxe', 'I00R', 40, 'useslot3', 'alta', 'pozione solo mana'),
    ('Wizard Staff', 'I00R', 40, 'useslot3', 'alta', 'pozione solo mana'),
    ('Claws', 'I00R', 40, 'useslot3', 'alta', 'pozione solo mana'),
    ('Runeblade', 'I00R', 40, 'useslot3', 'alta', 'pozione solo mana'),
    ('War Drums', 'I00R', 40, 'useslot3', 'alta', 'pozione solo mana'),
    ('War Hammer', 'I00R', 40, 'useslot3', 'alta', 'pozione solo mana'),
    ('Naga Trident', 'I00R', 40, 'useslot3', 'alta', 'pozione solo mana'),
    ('Bow', 'I00W', 40, 'useslot3', 'alta', 'pozione cura+mana+vel. attacco'),
    ('Double Blade', 'I00Q', 40, 'useslot5', 'media', 'pozione cura 40% HP'),
    ('War Drums', 'I08F', 180, 'useslot4', 'media (unico oggetto attivabile comprato prima del 1o uso dello slot 4)', 'Charm of Protection: +100 armatura agli alleati vicini'),
    ('Double Blade', 'I05S', 0, 'useslot3', 'bassa (slot 3 usato anche a 486 s, prima dell acquisto)', 'Spiked Collar con talento Houndmaster (cariche illimitate)'),
    ('Naga Trident', 'I070', 15, 'useslot2', 'media (unici ordini useslot a bersaglio punto = blink)', 'Warp Treads: blink'),
    ('War Drums', 'I070', 15, '-', 'alta: nessun useslot a bersaglio punto', 'Warp Treads: blink'),
    ('Claws', 'I070', 15, '-', 'alta: nessun useslot a bersaglio punto dopo l acquisto', 'Warp Treads: blink'),
    ('Runeblade', 'I09A', 20, '-', 'alta: unico slot usato e il 3 (pozione)', "Defender's Buckler: taunt"),
    ('Pickaxe', 'I09F', 100, '-', 'alta: dopo l acquisto solo lo slot 3 (pozione)', "Warrior's Spirit: +10000 HP per 30 s"),
]
att = []
for c, code, cd, slot, conf, nota in ATTIVI:
    t0 = tacq(c, code)
    times = [x for x in SLOT_T.get((c, slot), []) if x >= t0] if slot != '-' else []
    if c == 'Claws' and code == 'I070':
        times = []
    comb = combat_after(t0)
    mx = int(comb // cd) + 1 if cd else ''
    u = usi_cd(times, cd) if cd else len(times)
    att.append({'classe': c, 'ruolo': RUOLO[c], 'codice': code, 'oggetto': CACHE[code]['nome'], 'acquisto_s': t0,
                'costo_oro': CACHE[code]['costo_oro'], 'cooldown_s': cd, 'slot_ipotizzato': slot,
                'confidenza_attribuzione': conf, 'comandi_slot_dopo_acquisto': len(times),
                'usi_contati_con_cooldown': u, 'secondi_combattimento_dopo_acquisto': round(comb),
                'max_teorico_in_combattimento': mx,
                'uso_pct_del_max': round(100 * u / mx, 1) if mx else '', 'nota': nota})
wr('uso_oggetti_attivabili.csv', att)

# controllo: nessun nome di giocatore negli output
names = set(ROLES)
for fn in os.listdir(OUT):
    if fn.endswith('.csv'):
        txt = open(os.path.join(OUT, fn), encoding='utf-8').read()
        bad = [n for n in names if n in txt]
        assert not bad, (fn, 'contiene nomi')
print('controllo nomi: ok')
