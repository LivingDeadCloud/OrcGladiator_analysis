"""Aggrega data_replay/actions.csv per giocatore e per challenge.

I confini delle challenge vengono dagli orari degli screenshot (data_screenshots/multiboard_snapshots.csv):
la challenge N termina all'orario dello screenshot con header N+1.
"""
import csv, math
from collections import defaultdict

BASIC = {'smart', 'stop', 'attack', 'move', 'patrol', 'holdposition', 'AImove', 'attackground',
         'attackonce', 'getitem', 'dropitem', 'setrally', 'cancel'}


def load(path):
    return list(csv.DictReader(open(path, encoding='utf-8')))


def classify(a):
    k, o = a['kind'], a['order']
    if k == 'order_target' and o == 'smart':
        return 'rclick_unit' if a['target_is_unit'] == 'True' else 'rclick_ground'
    if k == 'order_point' and o == 'smart':
        return 'rclick_ground'
    if o in ('move', 'patrol', 'AImove'):
        return 'move_cmd'
    if o in ('attack', 'attackonce', 'attackground'):
        return 'attack_cmd'
    if o == 'holdposition':
        return 'hold'
    if o == 'stop':
        return 'stop'
    if o.startswith('useslot'):
        return 'item_use'
    if o.startswith('moveslot') or k == 'give_item' or o in ('dropitem', 'getitem'):
        return 'item_manage'
    if k.startswith('order') and o.startswith('I0'):
        return 'shop_buy'
    if k.startswith('order') and o not in BASIC:
        return 'ability'
    if k in ('select', 'select_subgroup', 'select_group', 'assign_group'):
        return 'selection'
    if k == 'trigger_chat':
        t = a['text'].lower()
        return 'loan_cmd' if ('loan' in t or 'bor' in t or t.startswith('-oan') or t.startswith('-loam')) else 'chat_cmd'
    if k == 'esc':
        return 'esc'
    return k


METRICS = ['actions', 'rclick_ground', 'rclick_unit', 'move_cmd', 'attack_cmd', 'hold', 'stop', 'ability',
           'item_use', 'item_manage', 'shop_buy', 'selection', 'loan_cmd', 'esc', 'move_distance']


def main():
    acts = load('data_replay/actions.csv')
    leaves = {r['player']: int(r['game_time_ms']) for r in load('data_replay/leaves.csv')}
    snaps = load('data_screenshots/multiboard_snapshots.csv')
    bounds = sorted({(int(s['challenges_completed']), int(s['game_time_s']) * 1000)
                     for s in snaps if s['phase'] == 'post'})
    end_ms = max(int(a['game_time_ms']) for a in acts)
    # segmento N = da fine challenge N-1 a fine challenge N
    edges = [(0, 0)] + bounds + [(20, end_ms + 1)]

    def segment(t):
        for (c0, t0), (c1, t1) in zip(edges, edges[1:]):
            if t0 <= t < t1:
                return c1
        return 20

    players = []
    tot = defaultdict(lambda: defaultdict(float))
    per_round = defaultdict(lambda: defaultdict(float))
    ability_use = defaultdict(lambda: defaultdict(int))
    last_pt, hero = {}, {}
    for a in acts:
        p = a['player']
        if p not in players:
            players.append(p)
        if a['kind'] in ('pause', 'resume'):
            continue
        t = int(a['game_time_ms'])
        c = classify(a)
        seg = segment(t)
        for bucket in (tot[p], per_round[(p, seg)]):
            bucket['actions'] += 1
            bucket[c] += 1
        if c == 'ability' and a['order'][:1] in 'OUEHN' and a['order'][1:2] == '0':
            hero[p] = a['order']  # rawcode eroe custom scelto (es. O017)
        elif c == 'ability':
            ability_use[p][a['order']] += 1
        if c in ('rclick_ground', 'move_cmd') and a['x']:
            x, y = float(a['x']), float(a['y'])
            if p in last_pt:
                d = math.dist(last_pt[p], (x, y))
                tot[p]['move_distance'] += d
                per_round[(p, seg)]['move_distance'] += d
            last_pt[p] = (x, y)

    with open('data_replay/player_summary.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['player', 'hero_code', 'minutes_played', 'apm'] + METRICS + ['distinct_abilities', 'top_abilities'])
        for p in players:
            mins = leaves.get(p, end_ms) / 60000
            top = sorted(ability_use[p].items(), key=lambda x: -x[1])[:6]
            w.writerow([p, hero.get(p), round(mins, 1), round(tot[p]['actions'] / mins, 1)] +
                       [round(tot[p][m]) for m in METRICS] +
                       [len(ability_use[p]), ' '.join(f'{k}:{v}' for k, v in top)])
    seg_len = {c1: (t1 - t0) / 60000 for (c0, t0), (c1, t1) in zip(edges, edges[1:])}
    with open('data_replay/player_round.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['player', 'challenge', 'segment_minutes', 'apm'] + METRICS)
        for p in players:
            for c in sorted(seg_len):
                b = per_round[(p, c)]
                w.writerow([p, c, round(seg_len[c], 2), round(b['actions'] / seg_len[c], 1)] +
                           [round(b[m]) for m in METRICS])
    for p in players:
        r = tot[p]
        print(f"{p:16s} apm={r['actions'] / (leaves.get(p, end_ms) / 60000):6.1f} "
              f"rcG={r['rclick_ground']:5.0f} rcU={r['rclick_unit']:5.0f} hold={r['hold']:4.0f} "
              f"abil={r['ability']:4.0f} item={r['item_use']:4.0f} dist={r['move_distance']:9.0f}")


if __name__ == '__main__':
    main()

