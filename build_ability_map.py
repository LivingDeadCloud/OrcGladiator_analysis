"""Traduce i codici ordine del replay in nomi di abilita'/oggetti della mappa.

Input: file estratti dalla mappa (war3map.w3a/.w3u/.w3t/.wts), *AbilityFunc.txt del gioco, order_ids.csv.
Uso: python build_ability_map.py <cartella_file_mappa> <cartella_file_gioco>
Output: data_map/ability_catalog.csv, data_map/classes.csv, data_replay/player_abilities.csv,
        data_replay/actions_named.csv (actions.csv + colonna ability_name)
"""
import csv, glob, os, re, sys
from collections import Counter, defaultdict
from objdata import parse_wts, parse_obj, clean

mapdir, gamedir = sys.argv[1], sys.argv[2]
os.makedirs('data_map', exist_ok=True)

wts = parse_wts(open(os.path.join(mapdir, 'war3map.wts'), 'rb').read())
abil = parse_obj(open(os.path.join(mapdir, 'war3map.w3a'), 'rb').read(), 'w3a', wts)
units = parse_obj(open(os.path.join(mapdir, 'war3map.w3u'), 'rb').read(), 'w3u', wts)
items = parse_obj(open(os.path.join(mapdir, 'war3map.w3t'), 'rb').read(), 'w3t', wts)
order_id = {r['order_string']: r['order_hex'] for r in csv.DictReader(open('order_ids.csv'))}

# order string di default delle abilita' base (dal gioco; i file piu' recenti sovrascrivono)
base_order = {}
for f in sorted(glob.glob(os.path.join(gamedir, 'war3.mpq_*.txt'))) + \
        sorted(glob.glob(os.path.join(gamedir, 'War3x.mpq_*.txt'))) + \
        sorted(glob.glob(os.path.join(gamedir, 'War3Patch.mpq_*.txt'))):
    cur = None
    for line in open(f, encoding='latin-1'):
        line = line.strip()
        m = re.match(r'\[(\w{4})\]', line)
        if m:
            cur = m.group(1)
        elif cur and '=' in line:
            k, v = line.split('=', 1)
            if k in ('Order', 'Orderon', 'Unorder') and v:
                base_order.setdefault(cur, {})[k] = v.strip()


def field(o, f, lvl=None):
    for (ff, l), v in o['mods'].items():
        if ff == f and (lvl is None or l == lvl):
            return v
    return None


catalog = []
for aid, o in abil.items():
    name = clean(field(o, 'anam') or '')
    tip = clean(field(o, 'atp1', 1) or field(o, 'atp1') or '')
    hot = field(o, 'ahky') or ''
    if o['base'] == 'ANcl':
        orders = {field(o, 'Ncl6', 1) or field(o, 'Ncl6') or 'channel'}
    else:
        bo = base_order.get(o['base'], {})
        orders = {field(o, 'aord') or bo.get('Order'), bo.get('Orderon')} - {None}
    for os_ in orders:
        catalog.append({'ability_id': aid, 'base': o['base'], 'name': name, 'tooltip': tip, 'hotkey': hot,
                        'order_string': os_, 'order_hex': order_id.get(os_, '')})
with open('data_map/ability_catalog.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, list(catalog[0])); w.writeheader(); w.writerows(catalog)

# classi (armi): pulsante di scelta -> abilita' elencate nella descrizione
PICKS = {'O015': 'Orange Jews', 'O017': 'MountainKing', 'O01L': 'JesusOnlyFans', 'O01D': 'KimberlyRimming',
         'O01E': 'Tamburello', 'O01F': 'TheCadger', 'O01A': 'Focascina', 'O016': 'bombtelaviv',
         'O01G': 'IFreniiiiiiiiii', 'O01B': 'BoomKhamenei'}
WIZARD = ('Fire Bolt, Frost Bolt, Magic Bolt, Pyroblast, Glacial Blast, Arcane Explosion, Fire Nova, '
          'Water Elemental, Summon Water Elemental, Replicate, Blink, Frost Shield, Meteor, Blizzard Wave, '
          'Time Stop, Fire Lord, Frozen Intuition, Brilliance Aura, Phoenix Blood')
classes = {}
for pick, player in PICKS.items():
    m = units[pick]['mods']
    tip = clean(m.get(('utip', 0)))
    tub = clean(m.get(('utub', 0)))
    learn = re.search(r'learn\s*:\s*(.*?)(?:\.|\s{2,}|$)', tub)
    skills = learn.group(1) if learn else ''
    if 'choose their abilities' in skills:
        skills = WIZARD
    skills = [s.strip() for s in re.split(r',| and ', skills) if s.strip()]
    classes[player] = {'pick': pick, 'weapon': tip, 'skills': skills}
with open('data_map/classes.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['player', 'pick_code', 'weapon_class', 'skills'])
    for p, c in classes.items():
        w.writerow([p, c['pick'], c['weapon'], '; '.join(c['skills'])])

by_order = defaultdict(list)
for c in catalog:
    if c['order_hex']:
        by_order[c['order_hex']].append(c)
item_name = {iid: clean(field(o, 'unam') or '') for iid, o in items.items()}


# Casi che il match automatico non risolve (verificati a mano su hotkey/tooltip della mappa)
OVERRIDES = {
    ('Orange Jews', '0x0D0097'): 'Lightning Strike', ('Orange Jews', '0x0D00C0'): 'Healing Wave',
    ('Orange Jews', '0x0D0216'): 'Hex', ('Orange Jews', '0x0D02BD'): 'Molten Boulder',
    ('Focascina', '0x0D02B6'): 'Storm Bolt', ('Focascina', '0x0D0080'): 'Thunderclap',
    ('Focascina', '0x0D0076'): 'Avatar', ('bombtelaviv', '0x0D02B6'): 'Piercing Shot',
    ('bombtelaviv', '0x0D0251'): 'Take Aim', ('TheCadger', '0x0D02B6'): 'Fire/Frost/Magic Bolt',
    ('KimberlyRimming', '0x0D00CE'): 'Volatile Concoction', ('KimberlyRimming', '0x0D028B'): 'Construct Tower (probabile)',
    ('KimberlyRimming', '0x0D00B6'): 'Mark Target (autocast on)', ('KimberlyRimming', '0x0D00B5'): 'Mark Target',
    ('MountainKing', '0x0D010E'): 'Firestorm', ('TheCadger', '0x0D00FE'): 'Pyroblast',
    ('TheCadger', '0x0D00F4'): 'Learn Pyroblast', ('TheCadger', '0x0D0229'): 'Learn Blink',
    ('TheCadger', '0x0D027D'): 'Learn Time Stop', ('TheCadger', '0x0D022A'): 'Learn Brilliance Aura', ('IFreniiiiiiiiii', '0x0D027B'): 'Parasite (autocast off)',
    ('IFreniiiiiiiiii', '0x0D027A'): 'Parasite (autocast on)',
}


def resolve(player, order):
    if (player, order) in OVERRIDES:
        return OVERRIDES[(player, order)]
    if re.fullmatch(r'I0\w\w', order):
        return 'Oggetto: ' + (item_name.get(order) or order)
    if not order.startswith('0x0D'):
        return order
    skills = [s.lower() for s in classes.get(player, {}).get('skills', [])]
    cands = by_order.get(order, [])
    hit = sorted({c['name'] or c['tooltip'] for c in cands
                  if any(s in (c['name'] + ' ' + c['tooltip']).lower() for s in skills)
                  and not c['name'].startswith(('Item', 'Boss', 'Dummy', 'Learn', 'Choose'))})
    if hit:
        return ' / '.join(re.sub(r'^\(\s*\w\s*\)\s*', '', h) for h in hit)
    items_ = sorted({c['name'] for c in cands if c['name'].startswith('Item')})
    if items_:
        return 'Oggetto-abilita: ' + ' / '.join(i[5:] for i in items_)
    os_ = next((k for k, v in order_id.items() if v == order), order)
    return f'[{os_}]'


acts = list(csv.DictReader(open('data_replay/actions.csv', encoding='utf-8')))
cnt = Counter()
for a in acts:
    a['ability_name'] = ''
    if a['kind'].startswith('order') and a['order'] and (a['order'].startswith('0x0D') or re.fullmatch(r'I0\w\w', a['order'])):
        a['ability_name'] = resolve(a['player'], a['order'])
        cnt[(a['player'], a['order'], a['ability_name'])] += 1
with open('data_replay/actions_named.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, list(acts[0])); w.writeheader(); w.writerows(acts)
with open('data_replay/player_abilities.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['player', 'weapon_class', 'order', 'name', 'count'])
    for (p, o, n), c in sorted(cnt.items(), key=lambda x: (x[0][0], -x[1])):
        w.writerow([p, classes.get(p, {}).get('weapon'), o, n, c])
for p, c in classes.items():
    print(p, '|', c['weapon'], '|', ', '.join(c['skills']))


