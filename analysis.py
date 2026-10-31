"""Costruisce i dataset di analisi (cartella data_analysis/) da replay + screenshot + mappa."""
import csv, os, statistics as st
from collections import Counter, defaultdict

os.makedirs('data_analysis', exist_ok=True)


def load(p):
    return list(csv.DictReader(open(p, encoding='utf-8')))


def write(name, rows):
    with open(os.path.join('data_analysis', name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, list(rows[0])); w.writeheader(); w.writerows(rows)


snaps = load('data_screenshots/multiboard_snapshots.csv')
rounds = load('data_screenshots/rounds.csv')
summ = {r['player']: r for r in load('data_replay/player_summary.csv')}
pround = load('data_replay/player_round.csv')
abil = load('data_replay/player_abilities.csv')
classes = {r['player']: r for r in load('data_map/classes.csv')}
post = [s for s in snaps if s['phase'] == 'post']
PLAYERS = list(summ)
SHORT_ROLE = {'Orange Jews': 'Shaman (Claws)', 'MountainKing': 'Warlock (Double Blade)', 'JesusOnlyFans': 'Death Knight (Runeblade)',
              'KimberlyRimming': 'Ingegnere (Pickaxe)', 'Tamburello': 'Tamburi (War Drums)', 'TheCadger': 'Mago (Wizard Staff)',
              'Focascina': 'Guerriero (War Hammer)', 'bombtelaviv': 'Arciere (Bow)', 'IFreniiiiiiiiii': 'Naga (Trident)',
              'BoomKhamenei': 'Druido (Druid Staff)'}

# --- andamento per round (quote cumulative) ---
trend = []
for s in post:
    trend.append({'player': s['player'], 'challenge': int(s['challenges_completed']),
                  'danni': float(s['dmg_pct']), 'boss': float(s['boss_dmg_pct']), 'cure': float(s['heal_pct']),
                  'tank': float(s['tank_pct']), 'oro': int(s['gold']), 'hp_fine_round': int(s['hp_pct']),
                  'livello': int(s['level'])})
write('andamento_round.csv', trend)

# --- round ---
team = defaultdict(lambda: defaultdict(float))
for r in pround:
    c = int(r['challenge'])
    team[c]['actions'] += float(r['actions']); team[c]['ability'] += float(r['ability'])
    team[c]['min'] = float(r['segment_minutes'])
lowhp = Counter(int(t['challenge']) for t in trend if t['hp_fine_round'] <= 20)
round_rows = []
for r in rounds:
    c = int(r['challenge'])
    round_rows.append({'challenge': c, 'ondata': r['wave'].split(' (boss')[0], 'secondi': r['clear_seconds'] or '',
                       'voto': r['grade'], 'eroi_sotto_20hp': lowhp.get(c, 0) if c <= 19 else '',
                       'apm_team': round(team[c]['actions'] / team[c]['min'] / 10, 1) if team[c]['min'] else '',
                       'abilita_min_team': round(team[c]['ability'] / team[c]['min'], 1) if team[c]['min'] else '',
                       'migliore_danni': r['best_damage'], 'migliore_tank': r['best_tank'],
                       'migliore_cure': r['best_healer']})
write('round.csv', round_rows)

# --- profilo giocatori ---
final = {s['player']: s for s in snaps if s['screenshot'] == '040526_20'}  # dopo challenge 19, tutti presenti
awards = Counter()
for r in rounds:
    for k in ('best_damage', 'best_tank', 'best_boss_slayer', 'best_healer'):
        if r[k]:
            awards[r[k]] += 1
top_ab = {}
for a in abil:
    if a['name'].startswith('Oggetto'):
        continue
    if a['player'] not in top_ab or int(a['count']) > int(top_ab[a['player']]['count']):
        top_ab[a['player']] = a
prof = []
for p in PLAYERS:
    s, f = summ[p], final[p]
    mins = float(s['minutes_played'])
    golds = [t['oro'] for t in trend if t['player'] == p]
    prof.append({
        'giocatore': p, 'classe': SHORT_ROLE[p], 'arma': classes[p]['weapon_class'].split('(')[1].rstrip(') ').strip(),
        'danni': float(f['dmg_pct']), 'boss': float(f['boss_dmg_pct']), 'cure': float(f['heal_pct']), 'tank': float(f['tank_pct']),
        'apm': float(s['apm']),
        'abilita_min': round(int(s['ability']) / mins, 2),
        'click_movimento_min': round(int(s['rclick_ground']) / mins, 1),
        'click_bersaglio_min': round(int(s['rclick_unit']) / mins, 1),
        'hold_position': int(s['hold']), 'oggetti_usati': int(s['item_use']), 'acquisti': int(s['shop_buy']),
        'oro_medio_fine_round': round(st.mean(golds)), 'oro_max': max(golds),
        'round_sotto_20hp': sum(1 for t in trend if t['player'] == p and t['hp_fine_round'] <= 20),
        'premi_round': awards.get(p, 0), 'comandi_prestito': int(s['loan_cmd']),
        'abilita_principale': top_ab[p]['name'], 'abilita_principale_usi': int(top_ab[p]['count']),
    })
write('profilo_giocatori.csv', prof)

# --- attivita' per round (APM) ---
write('attivita_round.csv', [{'player': r['player'], 'challenge': int(r['challenge']), 'apm': float(r['apm']),
                              'abilita': int(r['ability'])} for r in pround])

# --- abilita' (senza oggetti) ---
write('abilita.csv', [{'player': a['player'], 'abilita': a['name'], 'usi': int(a['count'])}
                      for a in abil if not a['name'].startswith('Oggetto') and int(a['count']) >= 3])

# --- stampe di controllo ---
for p in prof:
    print({k: p[k] for k in ('giocatore', 'danni', 'tank', 'cure', 'apm', 'abilita_min', 'oro_medio_fine_round', 'oro_max', 'round_sotto_20hp', 'premi_round')})
rr = [r for r in round_rows if r['secondi'] and r['apm_team'] != '']
xs = [float(r['apm_team']) for r in rr]; ys = [float(r['secondi']) for r in rr]
zs = [float(r['eroi_sotto_20hp'] or 0) for r in rr]
print('corr apm_team vs secondi', round(st.correlation(xs, ys), 2), ' corr eroi<20hp vs secondi', round(st.correlation(zs, ys), 2))
dm = [p['danni'] for p in prof]; ap = [p['apm'] for p in prof]
print('corr apm vs danni', round(st.correlation(ap, dm), 2))
for r in round_rows: print(r)

