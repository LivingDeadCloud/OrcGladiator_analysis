"""Domanda 01 - La scelta delle classi e' ottimale?

Da lanciare nella cartella principale del progetto:
    python data_analysis/v2/domande/01_scelta_classi/analisi_scelta_classi.py

Solo libreria standard. Nessun nome di giocatore nei file prodotti (solo classe e ruolo).

Output (nella cartella di questo script):
- classi_selezionabili.csv : le 16 armi/classi selezionabili nella mappa (war3map.j + war3map.w3u), giocata si/no,
                             tipo dichiarato dalla mappa, abilita' e bonus dal tooltip (sulla carta, NON misurati).
- contributo_classi.csv    : per classe: quote cumulative (dopo ch. 19), ruolo osservato, round con HP<=20%,
                             quote medie del round nelle challenge difficili vs facili (stime per round).
- ruoli_round_difficili.csv: per ruolo e gruppo di challenge (difficili / facili / boss finale parziale):
                             somma delle quote del round (stima) ed eroi a HP<=20% (misurato).
- indicatori_composizione.csv: indicatori di copertura, ridondanza e concentrazione del team.
"""
import csv
import os
import re
import sys

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
import objdata  # noqa: E402

OUT = os.path.join(ROOT, 'data_analysis', 'v2', 'domande', '01_scelta_classi')
AGG = os.path.join(ROOT, 'data_analysis', 'v2', 'aggregato')
RAW = os.path.join(ROOT, 'data_map', 'raw')

RUOLI = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']
# 'tank' = colpi presi dalla classe, evocazioni comprese (multiboard); 'colpi_eroe' = solo l'eroe (stima)
METRICHE = ['danni', 'tank', 'colpi_eroe', 'cure', 'boss']
LETTERE_DIFFICILI = {'D', 'E', 'F', 'G'}


def leggi(path):
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def scrivi(nome, righe, campi):
    with open(os.path.join(OUT, nome), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campi)
        w.writeheader()
        w.writerows(righe)


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def media(v):
    v = [x for x in v if x is not None]
    return round(sum(v) / len(v), 2) if v else ''


# ---------------------------------------------------------------- 1. classi selezionabili (mappa)
def classi_selezionabili():
    j = open(os.path.join(RAW, 'war3map.j'), encoding='latin-1').read()
    wts = objdata.parse_wts(open(os.path.join(RAW, 'war3map.wts'), 'rb').read())
    w3u = objdata.parse_obj(open(os.path.join(RAW, 'war3map.w3u'), 'rb').read(), 'w3u', wts)
    # bottoni di scelta: set udg_WeaponPickButton[i]='Oxxx'
    bottoni = re.findall(r"set udg_WeaponPickButton\[(\$?[0-9A-F]+)\]='(\w{4})'", j)
    bans = sorted(set(re.findall(r'"-ban ([a-z ]+)"', j)))
    giocate = {r['pick_code']: r for r in leggi(os.path.join(ROOT, 'data_map', 'class_roles.csv'))}
    righe = []
    for idx, code in bottoni:
        i = int(idx[1:], 16) if idx.startswith('$') else int(idx)
        m = w3u[code]['mods']
        tip = objdata.clean(m[('utip', 0)])
        tub = objdata.clean(m[('utub', 0)])
        mt = re.match(r'(.+?)\s*\(\s*(\w+)\s*,\s*(.+?)\)', tip)
        nome, attr, tipo = (mt.group(1).strip(), mt.group(2), mt.group(3).strip()) if mt else (tip, '', '')
        ab = re.search(r'will learn\s*:\s*(.*?)(?:\.\s{2,}|\s{2,})', tub)
        bo = re.search(r'(?:bonuses|Bonuses)\s*:\s*(.*)$', tub)
        g = giocate.get(code)
        righe.append({
            'indice_scelta': i, 'codice_scelta': code, 'classe': nome, 'attributo': attr,
            'tipo_dichiarato_mappa': tipo, 'distanza_dichiarata': tipo.split()[0] if tipo else '',
            'giocata': 'si' if g else 'no', 'ruolo_progetto': g['ruolo'] if g else '',
            'bannabile_con_comando': 'si' if nome.lower() in bans else 'no',
            'abilita_tooltip': ab.group(1).strip().rstrip('.') if ab else '',
            'bonus_tooltip': bo.group(1).strip() if bo else '',
            'fonte': 'war3map.j (udg_WeaponPickButton) + war3map.w3u (utip/utub)',
        })
    righe.sort(key=lambda r: r['indice_scelta'])
    scrivi('classi_selezionabili.csv', righe, list(righe[0].keys()))
    return righe


# ---------------------------------------------------------------- 2. contributo per classe e round difficili
def gruppi_challenge():
    rc = leggi(os.path.join(ROOT, 'data_analysis', 'v2', 'classi_ruoli', 'round_classi.csv'))
    diff, facili, escluse = [], [], []
    for r in rc:
        c = int(r['challenge'])
        voto = r['voto'].strip()
        eroi = num(r['eroi_sotto_20hp'])
        if c == 20:
            continue
        if voto in LETTERE_DIFFICILI or (eroi is not None and eroi >= 3):
            diff.append(c)
        elif voto in {'A', 'B', 'C'}:
            facili.append(c)
        else:
            escluse.append(c)
    return diff, facili, escluse, {int(r['challenge']): r for r in rc}


def main():
    sel = classi_selezionabili()
    scheda = leggi(os.path.join(AGG, 'scheda_classi.csv'))
    cc = leggi(os.path.join(AGG, 'classe_challenge.csv'))
    diff, facili, escluse, rc = gruppi_challenge()
    print('challenge difficili:', diff, '| facili:', facili, '| escluse (senza voto):', escluse)

    tipo_mappa = {r['classe']: r['tipo_dichiarato_mappa'] for r in sel}

    # contributo per classe
    righe = []
    for s in scheda:
        cl = s['classe']
        rr = {int(x['challenge']): x for x in cc if x['classe'] == cl}
        d = {'classe': cl, 'ruolo': s['ruolo'], 'tipo_dichiarato_mappa': tipo_mappa.get(cl, ''),
             'ruolo_osservato': s['ruolo_osservato'], 'ruolo_coerente': s['ruolo_coerente']}
        for m in METRICHE:
            d[f'quota_{m}_cum_ch19'] = s[f'quota_{m}' if m != 'cure' else 'quota_cure_multiboard']
        d['quota_cure_solo_abilita_b'] = s['quota_cure_solo_abilita_b']
        for m in METRICHE:
            d[f'{m}_round_difficili_media'] = media([num(rr[c][f'{m}_quota_round']) for c in diff if c in rr])
            d[f'{m}_round_facili_media'] = media([num(rr[c][f'{m}_quota_round']) for c in facili if c in rr])
        hp = lambda cs: [num(rr[c]['hp_fine_round']) for c in cs if c in rr]  # noqa: E731
        d['hp_fine_round_difficili_media'] = media(hp(diff))
        d['round_hp_le20_difficili'] = sum(1 for v in hp(diff) if v is not None and v <= 20)
        d['round_hp_le20_totale_ch1_19'] = s['round_sotto_20hp']
        d['premi_totali'] = s['premi_totali']
        d['quota_danni_boss_finale_parziale'] = s['quota_danni_boss_finale']
        d['quota_tank_boss_finale_parziale'] = s['quota_tank_boss_finale']
        d['quota_colpi_eroe_boss_finale_parziale'] = s['quota_colpi_eroe_boss_finale']
        d['quota_colpi_evocazioni_cum_ch19'] = s['quota_colpi_evocazioni']
        d['quota_colpi_eroe_min_ch19'] = s['quota_colpi_eroe_min']
        d['quota_colpi_eroe_max_ch19'] = s['quota_colpi_eroe_max']
        d['quota_cure_boss_finale_parziale'] = s['quota_cure_boss_finale']
        for m in METRICHE:
            d[f'{m}_round_ch20_stima'] = rr[20][f'{m}_quota_round'] if 20 in rr else ''
        righe.append(d)
    scrivi('contributo_classi.csv', righe, list(righe[0].keys()))

    # per ruolo e gruppo
    gr = []
    gruppi = [('difficili', diff), ('facili', facili), ('boss_finale_parziale', [20])]
    for ruolo in RUOLI:
        classi = [s['classe'] for s in scheda if s['ruolo'] == ruolo]
        for gname, cs in gruppi:
            g = {'ruolo': ruolo, 'n_classi': len(classi), 'gruppo': gname,
                 'challenge': ' '.join(map(str, cs))}
            for m in METRICHE:
                per_ch = []
                for c in cs:
                    v = [num(x[f'{m}_quota_round']) for x in cc if int(x['challenge']) == c and x['classe'] in classi]
                    v = [a for a in v if a is not None]
                    if v:
                        per_ch.append(sum(v))
                g[f'{m}_quota_round_somma_media'] = media(per_ch)
            eroi = [num(x['hp_fine_round']) for x in cc if int(x['challenge']) in cs and x['classe'] in classi]
            g['eroi_hp_le20'] = sum(1 for v in eroi if v is not None and v <= 20) if gname != 'boss_finale_parziale' else ''
            g['eroi_round_osservati'] = len([v for v in eroi if v is not None]) if gname != 'boss_finale_parziale' else ''
            g['quota_eroi_hp_le20_pct'] = (round(100 * g['eroi_hp_le20'] / g['eroi_round_osservati'], 1)
                                          if g['eroi_round_osservati'] else '')
            gr.append(g)
    scrivi('ruoli_round_difficili.csv', gr, list(gr[0].keys()))

    # indicatori di composizione
    q = {s['classe']: s for s in scheda}
    f = lambda c, k: float(q[c][k])  # noqa: E731
    ind = []

    def add(nome, valore, tipo, fonte, nota=''):
        ind.append({'indicatore': nome, 'valore': valore, 'tipo': tipo, 'fonte': fonte, 'nota': nota})

    n_sel = len(sel)
    n_gioc = sum(1 for r in sel if r['giocata'] == 'si')
    add('classi_selezionabili', n_sel, 'misurato', 'war3map.j', 'bottoni udg_WeaponPickButton[1..16]')
    add('classi_giocate', n_gioc, 'misurato', 'class_roles.csv')
    add('classi_non_giocate', '; '.join(f"{r['classe']} ({r['tipo_dichiarato_mappa']})" for r in sel if r['giocata'] == 'no'),
        'misurato', 'war3map.w3u')
    add('melee_tank_disponibili_e_giocati', f"{sum(1 for r in sel if r['tipo_dichiarato_mappa']=='Melee Tank')} / "
        f"{sum(1 for r in sel if r['tipo_dichiarato_mappa']=='Melee Tank' and r['giocata']=='si')}", 'misurato', 'war3map.w3u')
    dps = [c for c in q if q[c]['ruolo'].startswith('DPS')]
    add('quota_danni_classe_top', f"{max(f(c,'quota_danni') for c in q)} (Claws)", 'misurato', 'multiboard ch.19')
    add('quota_danni_DPS_mischia_da_Claws_pct',
        round(100 * f('Claws', 'quota_danni') / sum(f(c, 'quota_danni') for c in q if q[c]['ruolo'] == 'DPS mischia'), 1),
        'misurato (rapporto)', 'multiboard ch.19')
    add('quota_boss_da_Claws', f('Claws', 'quota_boss'), 'misurato', 'multiboard ch.19')
    add('quota_colpi_classi_non_Tank', round(sum(f(c, 'quota_tank') for c in q if q[c]['ruolo'] != 'Tank'), 1),
        'misurato', 'multiboard ch.19', 'colpi presi, evocazioni comprese')
    add('quota_colpi_eroi_non_Tank', round(sum(f(c, 'quota_colpi_eroe') for c in q if q[c]['ruolo'] != 'Tank'), 1),
        'stimato', 'colpi/NOTE.md', 'solo eroi, senza evocazioni (scenario centrale)')
    add('quota_colpi_eroi_Tank', round(sum(f(c, 'quota_colpi_eroe') for c in q if q[c]['ruolo'] == 'Tank'), 1),
        'stimato', 'colpi/NOTE.md')
    add('quota_colpi_evocazioni_totale', round(sum(f(c, 'quota_colpi_evocazioni') for c in q), 1),
        'stimato', 'colpi/NOTE.md', 'lupi, Treant, elementali, torre, portali, compagno')
    add('quota_colpi_eroi_Double_Blade_piu_Claws', round(f('Double Blade', 'quota_colpi_eroe') + f('Claws', 'quota_colpi_eroe'), 1),
        'stimato', 'colpi/NOTE.md',
        f"forbice {round(float(q['Double Blade']['quota_colpi_eroe_min']) + float(q['Claws']['quota_colpi_eroe_min']), 1)}"
        f"-{round(float(q['Double Blade']['quota_colpi_eroe_max']) + float(q['Claws']['quota_colpi_eroe_max']), 1)}")
    add('classi_con_cure_multiboard_sopra_10pct', '; '.join(c for c in q if f(c, 'quota_cure_multiboard') > 10),
        'misurato', 'multiboard ch.19', 'include pozioni/rigenerazione/lifesteal')
    add('cure_solo_abilita_scenario_b', '; '.join(f"{c} {q[c]['quota_cure_solo_abilita_b']}" for c in q
                                               if f(c, 'quota_cure_solo_abilita_b') > 0), 'stimato', 'cure/NOTE.md')
    add('classi_sotto_quota_equa_su_tutte_le_metriche',
        '; '.join(c for c in q if max(f(c, 'quota_danni'), f(c, 'quota_colpi_eroe'), f(c, 'quota_cure_multiboard')) < 10),
        'misurato', 'multiboard ch.19', 'quota equa = 10%')
    add('DPS_sotto_quota_equa_danni', '; '.join(c for c in dps if f(c, 'quota_danni') < 10), 'misurato', 'multiboard ch.19')
    add('challenge_difficili', ' '.join(map(str, diff)), 'misurato', 'round_classi.csv', 'voto D-G oppure >=3 eroi a HP<=20%')
    add('challenge_facili', ' '.join(map(str, facili)), 'misurato', 'round_classi.csv', 'voto A-C e <3 eroi a HP<=20%')
    add('challenge_escluse', ' '.join(map(str, escluse)) + ' 20', 'misurato', 'round_classi.csv',
        'senza voto (8 e 12); la 20 e il boss finale, trattato a parte')
    scrivi('indicatori_composizione.csv', ind, ['indicatore', 'valore', 'tipo', 'fonte', 'nota'])

    # controllo anonimato
    nomi = [r['player'] for r in leggi(os.path.join(ROOT, 'data_map', 'class_roles.csv'))]
    for fn in os.listdir(OUT):
        if fn.endswith(('.csv', '.md')):
            t = open(os.path.join(OUT, fn), encoding='utf-8').read().lower()
            for n in nomi:
                if n.lower() in t:
                    raise SystemExit(f'ATTENZIONE: nome di giocatore trovato in {fn}')
    print('ok, file scritti in', OUT)


if __name__ == '__main__':
    main()
