"""Domanda 04 - I giocatori usano bene le abilita' o ci sono tanti tempi morti?

Uso (dalla cartella del progetto):
    python data_analysis/v2/domande/04_uso_abilita_tempi_morti/analisi_tempi_morti.py

Riusa SENZA MODIFICARLO lo script analisi_abilita_mana.py: il sorgente viene letto, gli vengono aggiunti in memoria
due agganci (registrazione del mana simulato passo per passo e copia delle variabili interne prima della parte
"B: cooldown") e la funzione `write` viene disattivata, quindi i CSV di data_analysis/v2/abilita_mana NON vengono
riscritti. Serve, come per lo script originale, Warcraft III installato (sola lettura degli MPQ). ~1 minuto.

Output (in questa cartella, nessun nome di giocatore):
  ritardi_abilita_classe.csv      (a)+(d) per classe x abilita' attiva
  ritardi_episodi.csv             ogni "episodio di disponibilita'" in combattimento (per controlli)
  inattivita_classe.csv           (b) pause senza comandi per classe
  inattivita_classe_challenge.csv (b) per classe x challenge, con voto del round
  kit_abilita_classe.csv          (c) kit attivo disponibile e uso
  confronto_difficolta.csv        indicatori per classe/ruolo e gruppo di difficolta' (voto del round)
  giudizio_classe.csv / giudizio_ruolo.csv
"""
import bisect, contextlib, csv, io, math, os, re, statistics, sys
from collections import Counter, defaultdict

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
OUT = os.path.join('data_analysis', 'v2', 'domande', '04_uso_abilita_tempi_morti')
DT = 0.5
SOGLIE_PAUSA = (5, 10)
SOGLIA_ASSENZA = 60   # pause senza comandi oltre 60 s: probabile morte/attesa, escluse nella versione 'corretta'
COMANDI = {'order_target', 'order_notarget', 'order_point', 'give_item'}
AZIONI_ALTRE = {'select', 'select_subgroup', 'select_group', 'assign_group', 'esc'}

# voto del round (multiboard): A/B facile, C media, D/E/G difficile; 8 e 12 senza voto, 20 = boss finale
GRUPPO_VOTO = {'A': 'facile (A-B)', 'B': 'facile (A-B)', 'C': 'media (C)', 'D': 'difficile (D-G)',
               'E': 'difficile (D-G)', 'F': 'difficile (D-G)', 'G': 'difficile (D-G)'}

# Categoria d'uso, dedotta dal tooltip della mappa (war3map.w3a, campo aub1):
#  rotazione   = danno / cura / buff ripetibile: ha senso usarla appena pronta
#  situazionale = controllo folla, emergenza, mobilita', utilita': un uso basso non e' per forza un errore
SITUAZIONALI = {
    'A00P': 'mobilita (salto)', 'A0HN': 'emergenza (invulnerabile poi muori)', 'A05Y': 'cura di gruppo di emergenza',
    'A05T': 'controllo (radici, utile sul boss)', 'A01L': 'controllo (Hex, utile sul boss)',
    'A09X': 'controllo (paura)', 'A09W': 'mana + reset cooldown a un alleato', 'A01J': 'mana di gruppo',
    'A0G6': 'cura + armatura mirata', 'A00A': 'portale (spostamento)', 'A038': 'crea pietra di resurrezione',
    'A036': 'difensiva (pelle demoniaca)', 'A08S': 'ripara la torre', 'A03L': 'controllo (trappola)',
    'A0D9': 'mobilita (blink)', 'A0DA': 'difensiva (scudo)', 'A0DI': 'controllo (Time Stop)',
    'A03O': 'controllo (stordimento)', 'A0FW': 'controllo + danno (Vortex)', 'A08N': 'evoca torre (1 alla volta)',
    'A01H': 'danno ad area, cooldown 180 s',
}
AUTOCAST = {'A08Q': 'Parasite', 'A08V': 'Mark Target', 'A0FM': 'Searing Arrows'}
BASI_PASSIVE = {'ACac', 'ACav', 'ACat', 'SCae', 'ACev', 'ACnr', 'AId1', 'Alit', 'AInv'}


def patched_hook():
    src = open('analisi_abilita_mana.py', encoding='utf-8').read()
    a1 = "            if record:\n"
    a2 = "    # ---- B: cooldown\n"
    a3 = "if __name__ == '__main__':\n    main()"
    for a in (a1, a2, a3):
        assert src.count(a) == 1, 'analisi_abilita_mana.py e\' cambiato: aggancio non trovato: ' + a
    src = src.replace(a1, a1 + "                _TL[(p, alpha)].append((t, mana, mx))\n")
    src = src.replace(a2, "    _HOOK.update(locals())\n    return\n" + a2)
    src = src.replace(a3, '')
    ns = {'__name__': 'analisi_abilita_mana_agganciato', '_TL': defaultdict(list), '_HOOK': {}}
    exec(compile(src, 'analisi_abilita_mana.py', 'exec'), ns)
    ns['write'] = lambda *a, **k: None          # nessun file di abilita_mana viene riscritto
    with contextlib.redirect_stdout(io.StringIO()):
        ns['main']()
    return ns['_HOOK'], ns['_TL']


def write(name, rows, cols=None):
    cols = cols or list(rows[0])
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()})
    print('scritto', name, len(rows))


def med(xs):
    return statistics.median(xs) if xs else ''


def pctile(xs, q):
    if not xs:
        return ''
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def main():
    H, TL = patched_hook()
    from objdata import clean
    roles, HERO, orders, PAR = H['roles'], H['HERO'], H['orders'], H['PAR']
    level_at, lvl_val, WIN, ALPHA = H['level_at'], H['lvl_val'], H['WIN'], H['ALPHA']
    W3A, ANAME, learn, lv_pts, t_create = H['W3A'], H['ANAME'], H['learn'], H['lv_pts'], H['t_create']
    level_up = H['level_up']
    REL = {r['classe']: r['giudizio'] for r in H['rel_rows']}
    acts = H['acts']
    rounds = {int(r['challenge']): r for r in csv.DictReader(open('data_screenshots/rounds.csv', encoding='utf-8'))}
    PL = list(roles)
    ability_params = H['ability_params']

    def voto(c):
        g = (rounds.get(c, {}).get('grade') or '').strip()
        return g if g in GRUPPO_VOTO else ''

    def gruppo(c):
        if c == 20:
            return 'boss finale (20)'
        return GRUPPO_VOTO.get(voto(c), 'senza voto (8, 12)')

    def anam(aid):
        return clean(W3A.get(aid, {'mods': {}})['mods'].get(('anam', 0)) or '')

    # nomi corretti (come in abilita_mana/: etichette replay corrette)
    def nome(p, aid):
        n = ANAME.get((p, aid)) or anam(aid) or aid
        m = anam(aid)
        return f'{n} (= {m})' if m and m not in n and n not in ('Fire/Frost/Magic Bolt',) else n

    # ---- mana simulato (calibrato) per passo
    def mana_series(p):
        pts = {}
        for t, mana, mx in TL[(p, ALPHA[p])]:
            pts.setdefault(round(t * 2), (mana, mx))
        ks = sorted(pts)
        return ks, pts
    MS = {p: mana_series(p) for p in PL}

    def mana_at(p, t):
        ks, pts = MS[p]
        i = bisect.bisect_right(ks, round(t * 2)) - 1
        return pts[ks[i]][0] if i >= 0 else None

    def first_snapshot_level(p, L):
        for t, l in sorted(lv_pts[p]):
            if l >= L:
                return t
        return None

    # ---- disponibilita' (sblocco) di ogni abilita'
    def unlock_time(p, aid, first_order):
        h = HERO[p]
        lu = {a: l for l, a in level_up.get(h['hero'], [])}
        cand = []
        if aid in lu and lu[aid]:
            t = first_snapshot_level(p, lu[aid])     # primo screenshot con livello >= L: limite superiore
            if t is not None:
                cand.append((t, f'livello eroe {lu[aid]} (primo screenshot)'))
        elif aid in h['abil_set']:
            cand.append((t_create.get(p, 0), 'abilita base dell eroe'))
        else:                                        # Wizard Staff: abilita' apprese dai libri
            nm = anam(aid)
            for t, ln in learn[p]:
                if nm and (nm in ln or ln.replace('Learn ', '') in nm):
                    cand.append((t, 'ordine Learn nel replay'))
                    break
        if first_order is not None and (not cand or first_order < cand[0][0]):
            return first_order, 'primo ordine (nessun dato di sblocco precedente)'
        return cand[0] if cand else (None, 'non determinabile')

    # ---- comandi per inattivita'
    cmd_times = defaultdict(list)
    any_times = defaultdict(list)
    for a in acts:
        p = a['player']
        if p not in roles:
            continue
        t = int(a['game_time_ms']) / 1000
        if a['kind'] in COMANDI:
            cmd_times[p].append(t)
            any_times[p].append(t)
        elif a['kind'] in AZIONI_ALTRE:
            any_times[p].append(t)
    for d in (cmd_times, any_times):
        for p in d:
            d[p].sort()

    COMBAT = sum(b - a for a, b, _ in WIN.values())

    # pause senza comandi > SOGLIA_ASSENZA dentro le finestre: eroe probabilmente morto o giocatore assente
    EXCL = defaultdict(list)
    for p in PL:
        for c, (a, b, _) in WIN.items():
            i = bisect.bisect_left(cmd_times[p], a)
            j = bisect.bisect_left(cmd_times[p], b)
            pts = [a] + cmd_times[p][i:j] + [b]
            for x, y in zip(pts, pts[1:]):
                if y - x > SOGLIA_ASSENZA:
                    EXCL[p].append((x, y))

    def in_excl(p, t):
        return any(x <= t < y for x, y in EXCL[p])

    def overlaps_excl(p, s0, s1):
        return any(x < s1 and y > s0 for x, y in EXCL[p])

    # =========================================================== (a) + (d) per abilita'
    ab_rows, ep_rows = [], []
    ab_by_class = defaultdict(list)
    for p in PL:
        r = roles[p]
        rel = REL[r['classe']]
        mana_ok_class = rel in ('affidabile', 'indicativa')
        per_aid = defaultdict(list)
        for t, aid, nm, tgt in sorted(orders[p]):
            per_aid[aid].append(t)
        for aid, ts in per_aid.items():
            if aid in AUTOCAST:
                continue
            par = PAR[aid]
            # cast effettivi (filtro cooldown, come in abilita_mana) + ordini sprecati
            casts, waste, spam, early = [], [], 0, 0
            nxt, prev = -1, None
            for t in ts:
                if t < nxt:
                    waste.append(t)
                    if prev is not None and t - prev < 1.0:
                        spam += 1
                    else:
                        early += 1
                else:
                    cd = lvl_val(par['cd'], level_at(p, aid, t))
                    casts.append((t, t + cd))
                    nxt = t + cd
                prev = t
            t_un, src_un = unlock_time(p, aid, ts[0])
            cds = sorted({lvl_val(par['cd'], level_at(p, aid, t)) for t in ts})
            costs = sorted({lvl_val(par['cost'], level_at(p, aid, t)) for t in ts})
            cast_t = [c for c, _ in casts]
            # griglia sul tempo di combattimento
            disp = cdocc = pronta = pronta_mana = pronta_nomana = 0.0
            disp_g = pronta_g = 0.0
            for c, (a, b, _) in WIN.items():
                t = a
                while t < b:
                    if t >= t_un:
                        k = bisect.bisect_right(cast_t, t) - 1
                        disp_g += DT
                        if not (k >= 0 and casts[k][1] > t):
                            pronta_g += DT
                    if t >= t_un and not in_excl(p, t):
                        disp += DT
                        k = bisect.bisect_right(cast_t, t) - 1
                        in_cd = k >= 0 and casts[k][1] > t
                        if in_cd:
                            cdocc += DT
                        else:
                            pronta += DT
                            if mana_ok_class:
                                m = mana_at(p, t)
                                cost = lvl_val(par['cost'], level_at(p, aid, t))
                                if m is not None and m >= cost:
                                    pronta_mana += DT
                                else:
                                    pronta_nomana += DT
                    t += DT
            # episodi di disponibilita' (a)
            eps = []
            for c, (a, b, _) in WIN.items():
                starts = []
                k = bisect.bisect_right(cast_t, a) - 1
                if a >= t_un and not (k >= 0 and casts[k][1] > a):
                    starts.append((a, 'pronta a inizio challenge'))
                for (x, y) in casts:
                    if a < y < b and y >= t_un:
                        starts.append((y, 'fine cooldown'))
                for s, tipo in starts:
                    nxtc = next((x for x in cast_t if x >= s - 1e-9), None)
                    used = nxtc is not None and nxtc < b
                    delay = (nxtc - s) if used else None
                    # versione con mana: inizio = primo istante con mana simulato >= costo
                    delay_m, mana_note = '', ''
                    if mana_ok_class:
                        cost = lvl_val(par['cost'], level_at(p, aid, s))
                        tt = s
                        lim = nxtc if used else b
                        while tt < lim and (mana_at(p, tt) or 0) < cost:
                            tt += DT
                        if used and tt < lim:
                            delay_m = nxtc - tt
                        elif used:
                            delay_m = 0.0 if lim <= s + DT else ''
                            mana_note = '' if lim <= s + DT else 'cast con mana simulato insufficiente'
                        elif tt >= b:
                            mana_note = 'mana simulato insufficiente fino a fine challenge'
                    ass = overlaps_excl(p, s, nxtc if used else b)
                    eps.append({'tipo': tipo, 'delay': delay, 'used': used, 'delay_m': delay_m, 'assente': ass,
                                'censura': (b - s) if not used else '', 'challenge': c, 'mana_note': mana_note})
                    ep_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'abilita': nome(p, aid), 'challenge': c,
                                    'voto_round': voto(c), 'gruppo_difficolta': gruppo(c), 'tipo_episodio': tipo,
                                    'disponibile_dal_s': round(s - a, 1),
                                    'ritardo_s': round(delay, 2) if used else '',
                                    'usata_prima_della_fine': 'si' if used else 'no',
                                    'secondi_rimasti_senza_uso': round(b - s, 1) if not used else '',
                                    'ritardo_da_mana_sufficiente_s': round(delay_m, 2) if delay_m != '' else '',
                                    'nota_mana': mana_note,
                                    'in_pausa_comandi_oltre_60s': 'si' if ass else 'no'})
            post_g = [e for e in eps if e['tipo'] == 'fine cooldown']
            post = [e for e in post_g if not e['assente']]
            post_used = [e['delay'] for e in post if e['used']]
            start = [e for e in eps if e['tipo'] == 'pronta a inizio challenge' and not e['assente']]
            start_used = [e['delay'] for e in start if e['used']]
            dm = [e['delay_m'] for e in post if e['used'] and e['delay_m'] != '']
            ord_comb = [t for t in ts if any(a <= t < b for a, b, _ in WIN.values())]
            waste_comb = [t for t in waste if any(a <= t < b for a, b, _ in WIN.values())]
            cast_comb = [t for t in cast_t if any(a <= t < b for a, b, _ in WIN.values())]
            nomana_cast = 0
            if mana_ok_class:
                for t in cast_comb:
                    m = mana_at(p, t - DT)
                    if m is not None and m < lvl_val(par['cost'], level_at(p, aid, t)):
                        nomana_cast += 1
            cat = 'situazionale' if aid in SITUAZIONALI else 'rotazione'
            row = {
                'classe': r['classe'], 'ruolo': r['ruolo'], 'abilita': nome(p, aid), 'ability_id': aid,
                'categoria': cat, 'uso_atteso': SITUAZIONALI.get(aid, 'usare appena pronta (danno/cura/buff)'),
                'cooldown_s': '/'.join(f'{x:g}' for x in cds), 'costo_mana': '/'.join(f'{x:g}' for x in costs),
                'disponibile_da_s': round(t_un, 1), 'fonte_disponibilita': src_un,
                'tempo_combattimento_disponibile_s': disp,
                'cast_in_combattimento': len(cast_comb),
                'cast_al_minuto_disponibile': 60 * len(cast_comb) / disp if disp else '',
                'pct_tempo_in_cooldown': 100 * cdocc / disp if disp else '',
                'pct_tempo_pronta_non_usata': 100 * pronta / disp if disp else '',
                'pct_tempo_pronta_con_mana_sim': 100 * pronta_mana / disp if disp and mana_ok_class else '',
                'pct_tempo_pronta_ma_senza_mana_sim': 100 * pronta_nomana / disp if disp and mana_ok_class else '',
                'episodi_dopo_cooldown': len(post),
                'ritardo_mediano_s': med(post_used), 'ritardo_p75_s': pctile(post_used, 0.75),
                'pct_entro_2s': 100 * sum(1 for d in post_used if d <= 2) / len(post) if post else '',
                'pct_entro_5s': 100 * sum(1 for d in post_used if d <= 5) / len(post) if post else '',
                'pct_non_riusata_entro_fine_challenge': 100 * sum(1 for e in post if not e['used']) / len(post) if post else '',
                'ritardo_mediano_da_mana_sufficiente_s': med(dm) if mana_ok_class else '',
                'pct_entro_2s_da_mana_sufficiente': (100 * sum(1 for d in dm if d <= 2) / len(dm)) if mana_ok_class and dm else '',
                'challenge_con_abilita_pronta_a_inizio': len(start),
                'ritardo_mediano_primo_uso_da_inizio_challenge_s': med(start_used),
                'pct_challenge_senza_uso_pur_pronta_a_inizio': 100 * sum(1 for e in start if not e['used']) / len(start) if start else '',
                'pct_tempo_pronta_non_usata_grezzo': 100 * pronta_g / disp_g if disp_g else '',
                'pct_entro_2s_grezzo': 100 * sum(1 for e in post_g if e['used'] and e['delay'] <= 2) / len(post_g) if post_g else '',
                'pct_non_riusata_grezzo': 100 * sum(1 for e in post_g if not e['used']) / len(post_g) if post_g else '',
                'episodi_esclusi_pausa_oltre_60s': len(post_g) - len(post),
                'ordini_in_combattimento': len(ord_comb),
                'ordini_sprecati_in_cooldown_combattimento': len(waste_comb),
                'pct_ordini_sprecati': 100 * len(waste_comb) / len(ord_comb) if ord_comb else '',
                'sprecati_doppio_click_lt1s': sum(1 for i, t in enumerate(ts)
                                                  if t in set(waste_comb) and i > 0 and t - ts[i - 1] < 1.0),
                'cast_con_mana_sim_insufficiente': nomana_cast if mana_ok_class else '',
                'affidabilita_mana_sim': rel,
            }
            row['sprecati_in_anticipo_ge1s'] = len(waste_comb) - row['sprecati_doppio_click_lt1s']
            ab_rows.append(row)
            ab_by_class[r['classe']].append((row, post, post_used))
    ab_rows.sort(key=lambda x: (x['ruolo'], x['classe'], x['categoria'], -x['cast_in_combattimento']))
    write('ritardi_abilita_classe.csv', ab_rows)
    write('ritardi_episodi.csv', ep_rows)

    # =========================================================== (b) inattivita'
    def gaps_in(times, a, b):
        i = bisect.bisect_left(times, a)
        j = bisect.bisect_left(times, b)
        pts = [a] + times[i:j] + [b]
        return [y - x for x, y in zip(pts, pts[1:])], j - i

    in_rows, inch_rows = [], []
    INACT = {}
    for p in PL:
        r = roles[p]
        res = {}
        for lab, times in (('comandi', cmd_times[p]), ('tutte_azioni', any_times[p])):
            allg, ncmd = [], 0
            for c, (a, b, _) in WIN.items():
                g, n = gaps_in(times, a, b)
                allg += g
                ncmd += n
                if lab == 'comandi':
                    tot = b - a
                    inch_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'challenge': c, 'voto_round': voto(c),
                                      'gruppo_difficolta': gruppo(c), 'durata_s': tot, 'comandi': n,
                                      'comandi_al_minuto': 60 * n / tot,
                                      'pause_oltre_5s': sum(1 for x in g if x > 5), 'pause_oltre_10s': sum(1 for x in g if x > 10),
                                      'pct_tempo_in_pause_oltre_5s': 100 * sum(x for x in g if x > 5) / tot,
                                      'pct_tempo_in_pause_oltre_10s': 100 * sum(x for x in g if x > 10) / tot,
                                      'pausa_max_s': max(g),
                                      'secondi_in_pause_oltre_60s': sum(x for x in g if x > SOGLIA_ASSENZA),
                                      'pct_tempo_in_pause_5_60s_su_tempo_presente': 100 * sum(x for x in g if 5 < x <= SOGLIA_ASSENZA) / max(1e-9, tot - sum(x for x in g if x > SOGLIA_ASSENZA)) if tot - sum(x for x in g if x > SOGLIA_ASSENZA) > 0 else '',
                                      'pct_tempo_in_pause_10_60s_su_tempo_presente': 100 * sum(x for x in g if 10 < x <= SOGLIA_ASSENZA) / max(1e-9, tot - sum(x for x in g if x > SOGLIA_ASSENZA)) if tot - sum(x for x in g if x > SOGLIA_ASSENZA) > 0 else ''})
            res[lab] = {'n': ncmd, 'g': allg}
        g = res['comandi']['g']
        g2 = res['tutte_azioni']['g']
        row = {'classe': r['classe'], 'ruolo': r['ruolo'], 'tempo_combattimento_s': COMBAT,
               'comandi_in_combattimento': res['comandi']['n'], 'comandi_al_minuto': 60 * res['comandi']['n'] / COMBAT,
               'intervallo_mediano_tra_comandi_s': med(g), 'intervallo_p90_s': pctile(g, 0.9),
               'pause_oltre_5s': sum(1 for x in g if x > 5), 'pause_oltre_10s': sum(1 for x in g if x > 10),
               'pause_oltre_5s_ogni_10_min': 600 * sum(1 for x in g if x > 5) / COMBAT,
               'pct_tempo_in_pause_oltre_5s': 100 * sum(x for x in g if x > 5) / COMBAT,
               'pct_tempo_in_pause_oltre_10s': 100 * sum(x for x in g if x > 10) / COMBAT,
               'pausa_max_s': max(g),
               'pause_oltre_60s': sum(1 for x in g if x > SOGLIA_ASSENZA),
               'secondi_in_pause_oltre_60s': sum(x for x in g if x > SOGLIA_ASSENZA),
               'pct_tempo_in_pause_oltre_60s': 100 * sum(x for x in g if x > SOGLIA_ASSENZA) / COMBAT,
               'pct_tempo_in_pause_5_60s_su_tempo_presente': 100 * sum(x for x in g if 5 < x <= SOGLIA_ASSENZA) / (COMBAT - sum(x for x in g if x > SOGLIA_ASSENZA)),
               'pct_tempo_in_pause_10_60s_su_tempo_presente': 100 * sum(x for x in g if 10 < x <= SOGLIA_ASSENZA) / (COMBAT - sum(x for x in g if x > SOGLIA_ASSENZA)),
               'pct_tempo_in_pause_oltre_5s_contando_selezioni': 100 * sum(x for x in g2 if x > 5) / COMBAT,
               'pct_tempo_in_pause_oltre_10s_contando_selezioni': 100 * sum(x for x in g2 if x > 10) / COMBAT}
        INACT[r['classe']] = row
        in_rows.append(row)
    in_rows.sort(key=lambda x: -x['pct_tempo_in_pause_oltre_5s'])
    write('inattivita_classe.csv', in_rows)
    write('inattivita_classe_challenge.csv', inch_rows)

    # =========================================================== (c) kit
    kit_rows = []
    used_aids = {(row['classe'], row['ability_id']): row for row in ab_rows}
    for p in PL:
        r = roles[p]
        h = HERO[p]
        lu = {a: l for l, a in level_up.get(h['hero'], [])}
        aids = set(h['abil_set']) | {aid for _, aid, _, _ in orders[p]}
        for aid in sorted(aids):
            o = W3A.get(aid, {'base': aid, 'mods': {}})
            base = o['base']
            nm = anam(aid) or (ANAME.get((p, aid)) or aid)
            if nm.startswith(('Locked Ability', 'Special - Hero Glow')) or base in ('AInv', 'AId1', 'ACnr'):
                continue
            if aid in AUTOCAST or base == 'ACbk':
                tipo = 'autocast (uso non visibile nel replay)'
            elif base in BASI_PASSIVE:
                tipo = 'passiva / aura (non conta)'
            elif base == 'Aspb':
                tipo = 'menu / libro di apprendimento (non valutabile)'
            else:
                tipo = 'attiva'
            if tipo != 'attiva':
                kit_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'abilita': nm, 'ability_id': aid, 'tipo': tipo,
                                 'livello_eroe_sblocco': lu.get(aid, ''), 'ordini_totali': sum(1 for x in orders[p] if x[1] == aid),
                                 'categoria': '', 'cast_in_combattimento': '', 'pct_tempo_in_cooldown': '', 'giudizio_uso': ''})
                continue
            row = used_aids.get((r['classe'], aid))
            t_un, src = unlock_time(p, aid, None)
            if row is None:
                par = ability_params(aid)
                disp = sum(max(0, b - max(a, t_un)) for a, b, _ in WIN.values()) if t_un is not None else ''
                cat = 'situazionale' if aid in SITUAZIONALI else 'rotazione'
                kit_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'abilita': nm, 'ability_id': aid, 'tipo': tipo,
                                 'livello_eroe_sblocco': lu.get(aid, ''), 'ordini_totali': 0, 'categoria': cat,
                                 'uso_atteso': SITUAZIONALI.get(aid, 'usare appena pronta (danno/cura/buff)'),
                                 'cooldown_s': '/'.join(f'{x:g}' for x in par['cd']), 'costo_mana': '/'.join(f'{x:g}' for x in par['cost']),
                                 'tempo_combattimento_disponibile_s': disp, 'cast_in_combattimento': 0,
                                 'cast_max_teorici': (disp / min(par['cd'])) if disp and min(par['cd']) else '',
                                 'pct_tempo_in_cooldown': 0, 'giudizio_uso': 'MAI USATA'})
                continue
            cmax = row['tempo_combattimento_disponibile_s'] / min(float(x) for x in row['cooldown_s'].split('/')) if row['cooldown_s'] and min(float(x) for x in row['cooldown_s'].split('/')) else ''
            occ = row['pct_tempo_in_cooldown'] or 0
            n = row['cast_in_combattimento']
            if n <= 3 and occ < 35:
                g = 'quasi mai usata (<=3 cast in combattimento)'
            elif occ < 15:
                g = 'poco usata (<15% del tempo in cooldown)'
            elif occ < 35:
                g = 'uso medio (15-35%)'
            else:
                g = 'molto usata (>=35%)'
            kit_rows.append({'classe': r['classe'], 'ruolo': r['ruolo'], 'abilita': row['abilita'], 'ability_id': aid, 'tipo': tipo,
                             'livello_eroe_sblocco': lu.get(aid, '') or ('appresa (Learn)' if src.startswith('ordine Learn') else ''),
                             'ordini_totali': len([x for x in orders[p] if x[1] == aid]), 'categoria': row['categoria'],
                             'uso_atteso': row['uso_atteso'], 'cooldown_s': row['cooldown_s'], 'costo_mana': row['costo_mana'],
                             'tempo_combattimento_disponibile_s': row['tempo_combattimento_disponibile_s'],
                             'cast_in_combattimento': n, 'cast_max_teorici': cmax, 'pct_tempo_in_cooldown': occ,
                             'giudizio_uso': g})
    kit_rows.sort(key=lambda x: (x['ruolo'], x['classe'], x['tipo'], x['abilita']))
    write('kit_abilita_classe.csv', kit_rows, ['classe', 'ruolo', 'abilita', 'ability_id', 'tipo', 'categoria', 'uso_atteso',
                                               'livello_eroe_sblocco', 'cooldown_s', 'costo_mana', 'tempo_combattimento_disponibile_s',
                                               'ordini_totali', 'cast_in_combattimento', 'cast_max_teorici', 'pct_tempo_in_cooldown',
                                               'giudizio_uso'])

    # =========================================================== confronto per difficolta'
    cmp_rows = []
    groups = ['facile (A-B)', 'media (C)', 'difficile (D-G)', 'senza voto (8, 12)', 'boss finale (20)']
    ep_by = defaultdict(list)
    for e in ep_rows:
        ep_by[(e['classe'], e['gruppo_difficolta'])].append(e)
    rot_names = {(x['classe'], x['abilita']) for x in ab_rows if x['categoria'] == 'rotazione'}
    for lvl, keyf in (('classe', lambda r: r['classe']), ('ruolo', lambda r: r['ruolo'])):
        keys = sorted({keyf(r) for r in roles.values()})
        for k in keys:
            classes = [r['classe'] for r in roles.values() if keyf(r) == k]
            for gname in groups:
                chs = [c for c in WIN if gruppo(c) == gname]
                ich = [x for x in inch_rows if x['classe'] in classes and x['challenge'] in chs]
                dur = sum(x['durata_s'] for x in ich)
                eps = [e for cl in classes for e in ep_by[(cl, gname)]
                       if e['tipo_episodio'] == 'fine cooldown' and (cl, e['abilita']) in rot_names
                       and e['in_pausa_comandi_oltre_60s'] == 'no']
                d = [e['ritardo_s'] for e in eps if e['usata_prima_della_fine'] == 'si']
                cmp_rows.append({'livello': lvl, 'classe_o_ruolo': k, 'gruppo_difficolta': gname,
                                 'challenge': ' '.join(str(c) for c in chs), 'secondi_combattimento_x_classi': dur,
                                 'comandi_al_minuto': 60 * sum(x['comandi'] for x in ich) / dur if dur else '',
                                 'pct_tempo_in_pause_oltre_5s': 100 * sum(x['pct_tempo_in_pause_oltre_5s'] * x['durata_s'] / 100 for x in ich) / dur if dur else '',
                                 'pct_tempo_in_pause_oltre_10s': 100 * sum(x['pct_tempo_in_pause_oltre_10s'] * x['durata_s'] / 100 for x in ich) / dur if dur else '',
                                 'pct_tempo_in_pause_oltre_60s': 100 * sum(x['secondi_in_pause_oltre_60s'] for x in ich) / dur if dur else '',
                                 'pct_tempo_in_pause_10_60s_su_tempo_presente': 100 * sum(x['pct_tempo_in_pause_10_60s_su_tempo_presente'] * (x['durata_s'] - x['secondi_in_pause_oltre_60s']) / 100 for x in ich if x['pct_tempo_in_pause_10_60s_su_tempo_presente'] != '') / max(1e-9, sum(x['durata_s'] - x['secondi_in_pause_oltre_60s'] for x in ich)) if dur else '',
                                 'episodi_rotazione_dopo_cooldown': len(eps),
                                 'ritardo_mediano_rotazione_s': med(d),
                                 'pct_entro_2s_rotazione': 100 * sum(1 for x in d if x <= 2) / len(eps) if eps else '',
                                 'pct_non_riusata_entro_fine_challenge': 100 * sum(1 for e in eps if e['usata_prima_della_fine'] == 'no') / len(eps) if eps else ''})
    write('confronto_difficolta.csv', cmp_rows)

    # =========================================================== giudizio per classe / ruolo
    # Regole (dichiarate in RISPOSTA.md): indicatori sulle sole abilita' di rotazione, episodi "fine cooldown".
    g_rows = []
    for p in PL:
        r = roles[p]
        cl = r['classe']
        rows = ab_by_class[cl]
        rot = [(row, post, pu) for row, post, pu in rows if row['categoria'] == 'rotazione']
        eps = sum(len(post) for _, post, _ in rot)
        allu = [d for _, _, pu in rot for d in pu]
        w2 = 100 * sum(1 for d in allu if d <= 2) / eps if eps else ''
        nonr = 100 * sum(1 for _, post, _ in rot for e in post if not e['used']) / eps if eps else ''
        kit = [k for k in kit_rows if k['classe'] == cl and k['tipo'] == 'attiva']
        mai = [k['abilita'] for k in kit if k['giudizio_uso'] == 'MAI USATA']
        poco_rot = [k['abilita'] for k in kit if k['categoria'] == 'rotazione' and k['giudizio_uso'].startswith(('quasi mai', 'poco', 'MAI'))]
        poco_sit = [k['abilita'] for k in kit if k['categoria'] == 'situazionale' and k['giudizio_uso'].startswith(('quasi mai', 'poco', 'MAI'))]
        ia = INACT[cl]
        ordc = sum(row['ordini_in_combattimento'] for row, _, _ in rows)
        wst = sum(row['ordini_sprecati_in_cooldown_combattimento'] for row, _, _ in rows)
        wst_ant = sum(row['sprecati_in_anticipo_ge1s'] for row, _, _ in rows)
        rel = REL[cl]
        pr = [row for row, _, _ in rot if row['pct_tempo_pronta_con_mana_sim'] != '']
        dispt = sum(row['tempo_combattimento_disponibile_s'] for row in pr)
        prm = 100 * sum(row['pct_tempo_pronta_con_mana_sim'] * row['tempo_combattimento_disponibile_s'] / 100 for row in pr) / dispt if dispt else ''
        prn = 100 * sum(row['pct_tempo_pronta_ma_senza_mana_sim'] * row['tempo_combattimento_disponibile_s'] / 100 for row in pr) / dispt if dispt else ''
        # punteggio semplice: 1 punto di "problema" per ciascuna soglia superata
        prob = []
        if w2 != '' and w2 < 25:
            prob.append('riuso lento delle abilita di rotazione (<25% entro 2 s)')
        if nonr != '' and nonr > 40:
            prob.append('spesso non riusate fino a fine challenge (>40% degli episodi)')
        if ia['pct_tempo_in_pause_10_60s_su_tempo_presente'] > 10:
            prob.append('molte pause senza comandi (>10% del tempo presente in pause 10-60 s)')
        if poco_rot:
            prob.append('abilita di rotazione poco o mai usate: ' + ', '.join(poco_rot))
        if ordc and 100 * wst_ant / ordc > 10:
            prob.append(f'molti ordini dati con abilita ancora in cooldown ({100 * wst_ant / ordc:.0f}%, esclusi doppi click)')
        verdict = 'buono' if not prob else ('migliorabile' if len(prob) <= 2 else 'da migliorare')
        g_rows.append({'classe': cl, 'ruolo': r['ruolo'],
                       'episodi_rotazione_dopo_cooldown': eps,
                       'ritardo_mediano_rotazione_s': med(allu), 'pct_riuso_entro_2s_rotazione': w2,
                       'pct_non_riusata_entro_fine_challenge': nonr,
                       'pct_tempo_pronta_con_mana_sim_rotazione': prm, 'pct_tempo_pronta_ma_senza_mana_sim_rotazione': prn,
                       'affidabilita_mana_sim': rel,
                       'pct_tempo_in_pause_oltre_5s': ia['pct_tempo_in_pause_oltre_5s'],
                       'pct_tempo_in_pause_oltre_10s': ia['pct_tempo_in_pause_oltre_10s'],
                       'pct_tempo_in_pause_oltre_60s_probabile_morte': ia['pct_tempo_in_pause_oltre_60s'],
                       'pct_tempo_in_pause_10_60s_su_tempo_presente': ia['pct_tempo_in_pause_10_60s_su_tempo_presente'],
                       'comandi_al_minuto': ia['comandi_al_minuto'],
                       'pct_ordini_sprecati_in_cooldown': 100 * wst / ordc if ordc else '',
                       'pct_ordini_in_cooldown_esclusi_doppi_click': 100 * wst_ant / ordc if ordc else '',
                       'abilita_attive_mai_usate': '; '.join(mai),
                       'rotazione_poco_usate': '; '.join(poco_rot), 'situazionali_poco_usate': '; '.join(poco_sit),
                       'problemi': ' | '.join(prob), 'giudizio': verdict})
    g_rows.sort(key=lambda x: (x['ruolo'], x['classe']))
    write('giudizio_classe.csv', g_rows)

    gr = []
    for role in sorted({r['ruolo'] for r in roles.values()}):
        ss = [g for g in g_rows if g['ruolo'] == role]
        def m(k):
            v = [g[k] for g in ss if g[k] != '']
            return statistics.mean(v) if v else ''
        gr.append({'ruolo': role, 'classi': ' + '.join(g['classe'] for g in ss),
                   'pct_riuso_entro_2s_rotazione_media': m('pct_riuso_entro_2s_rotazione'),
                   'ritardo_mediano_rotazione_s_media': m('ritardo_mediano_rotazione_s'),
                   'pct_non_riusata_entro_fine_challenge_media': m('pct_non_riusata_entro_fine_challenge'),
                   'pct_tempo_in_pause_oltre_5s_media': m('pct_tempo_in_pause_oltre_5s'),
                   'pct_tempo_in_pause_oltre_10s_media': m('pct_tempo_in_pause_oltre_10s'),
                   'pct_tempo_in_pause_oltre_60s_media': m('pct_tempo_in_pause_oltre_60s_probabile_morte'),
                   'pct_tempo_in_pause_10_60s_su_tempo_presente_media': m('pct_tempo_in_pause_10_60s_su_tempo_presente'),
                   'pct_ordini_sprecati_media': m('pct_ordini_sprecati_in_cooldown'),
                   'giudizi_classi': ' + '.join(f"{g['classe']}: {g['giudizio']}" for g in ss)})
    write('giudizio_ruolo.csv', gr)

    # controllo privacy: nessun nome di giocatore negli output
    names = set(roles)
    for fn in os.listdir(OUT):
        if fn.endswith('.csv'):
            txt = open(os.path.join(OUT, fn), encoding='utf-8').read()
            bad = [n for n in names if n and n in txt]
            assert not bad, f'nome giocatore in {fn}'
    print('controllo nomi: ok')


if __name__ == '__main__':
    main()
