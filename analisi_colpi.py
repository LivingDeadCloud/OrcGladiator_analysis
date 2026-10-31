"""Colpi presi: cosa misura davvero la colonna "tank" della multiboard e scorporo eroe / unita' evocate.

Da eseguire nella cartella principale del progetto:
    python analisi_colpi.py
Output in data_analysis/v2/colpi/ (vedi NOTE.md nella stessa cartella). Usa solo la libreria standard.
Nei file compaiono solo classe e ruolo, mai i nomi dei giocatori.

Punti chiave (verificati nel war3map.j, citazioni in evidenze_codice_colpi.csv):
- la colonna "tank" e' la quota di COLPI presi, non di danni: ogni evento di danno vale +1, qualunque sia il danno;
- i colpi vanno al PROPRIETARIO dell'unita' colpita, quindi comprendono quelli presi dalle unita' evocate;
- il danno ricevuto in HP non viene registrato da nessuna parte.

Lo scorporo eroe / evocazioni e' una STIMA: la multiboard da' solo il totale per giocatore.
Modello: in ogni challenge un'unita' evocata viene colpita k volte quanto un eroe medio, per secondo in campo.
  quota_evocazioni_i = 100 * k * E_i / (somma secondi-eroe + k * somma E)
dove E_i sono i secondi-unita' delle evocazioni della classe i dentro le finestre di combattimento.
Scenari: basso k = 0.5, centrale k = 1, alto k = 2. La quota dell'eroe e' il totale misurato meno quella delle evocazioni.
Limite: le evocazioni hanno 100-250 HP e muoiono dopo pochi colpi, mentre il modello le conta in campo per tutta la durata.
Per questo l'eroe non scende mai sotto la quota del meno colpito tra le classi SENZA evocazioni, nello stesso
screenshot o nella stessa challenge (pavimento). Quando il limite scatta la stima e' segnata come 'limitata'.
"""
import csv, os, re, statistics as st
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'data_analysis', 'v2', 'colpi')
JASS = os.path.join(BASE, 'data_map', 'raw', 'war3map.j')
os.makedirs(OUT, exist_ok=True)

SCENARI = {'basso': 0.5, 'centrale': 1.0, 'alto': 2.0}
ORDINE_RUOLI = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']


def p(*a):
    return os.path.join(BASE, *a)


def load(path):
    with open(path, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def write(name, rows, cols=None):
    cols = cols or list(rows[0])
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)


def r1(x, n=1):
    return '' if x is None or x == '' else round(x, n)


roles = load(p('data_map', 'class_roles.csv'))
CL = {r['player']: r['classe'] for r in roles}
RUOLO = {r['classe']: r['ruolo'] for r in roles}
CLASSI = sorted(CL.values(), key=lambda c: (ORDINE_RUOLI.index(RUOLO[c]), c))

# ---------------------------------------------------------------- 1. evidenze nel codice della mappa
EVIDENZE = [
    ('contatore colpi', "set udg_DamageTakenCount[udg_DamageMeter_Player]=(udg_DamageTakenCount[udg_DamageMeter_Player]+1.)",
     "Ogni evento di danno aggiunge 1, non l'importo del danno: la colonna 'tank' conta i colpi."),
    ('a chi va il colpo', "set udg_DamageMeter_Player=(1+GetPlayerId(GetOwningPlayer(udg_DamageEventTarget)))",
     "Il colpo va al proprietario dell'unita' colpita: eroe, unita' evocate, torri, compagni e illusioni."),
    ('nessun filtro sul bersaglio', "if(Trig_DamageMeterCount_Func002C())then",
     "Il controllo 'non illusione' (Func002C) racchiude solo il conteggio dei danni FATTI; i colpi presi si contano sempre."),
    ('quota in multiboard', "set udg_StatisticsPercentageHits[udg_StatisticsInteger]=(udg_DamageTakenCount[udg_StatisticsInteger]/ udg_StatisticsTotals[2])",
     "La percentuale mostrata e' la quota di colpi sul totale del team (la variabile si chiama proprio 'Hits')."),
    ('comando in partita', "\"'s hits tanked: \"",
     "La mappa stessa chiama questo valore 'hits tanked' (colpi incassati)."),
    ('danno fatto, per confronto', "set udg_DamageCountTotal[udg_DamageMeter_Player]=(udg_DamageCountTotal[udg_DamageMeter_Player]+udg_DamageEventAmount)",
     "Per i danni fatti invece si somma l'importo: le due colonne non sono omogenee."),
    ('evocazione Claws', "call UnitApplyTimedLifeBJ(18.,'BTLF',bj_lastCreatedUnit)",
     "Feral Spirit: 2 lupi 'o00A' al livello 1, 1 Spirit Guardian 'o00D' al livello 2, durata 18 s."),
    ('evocazione Druid Staff', "set udg_TEMP_REAL_ay[2]=70.",
     "Force of Nature: 3 Treant 'e002' ai livelli 1 e 3 (1 Treant Protector 'e003' ai livelli 2 e 4), durata 70 s."),
    ('evocazione Wizard Staff', "call UnitApplyTimedLifeBJ(60.,'BTLF',bj_lastCreatedUnit)",
     "Water Elemental: 1 elementale 'h011', durata 60 s (cooldown 40 s: ne possono esistere due)."),
    ('compagno Runeblade', "call CreateNUnitsAtLoc(1,'U00C',GetOwningPlayer(GetTriggerUnit()),udg_TEMP_POINT,GetUnitFacing(GetTriggerUnit()))",
     "Undead Companion (Banshee, 'U00C'): unita' eroe permanente, rianimabile."),
    ('torre Pickaxe', "call KillUnit(udg_Abil_ConstructTower[(1+GetPlayerId(GetOwningPlayer(GetTriggerUnit())))])",
     "Construct Tower: una torre per volta, la nuova distrugge la vecchia; resta finche' non viene distrutta."),
]


def evidenze():
    j = re.sub(r'\s+', ' ', open(JASS, encoding='latin-1').read())
    rows = []
    for nome, codice, sig in EVIDENZE:
        c = re.sub(r'\s+', ' ', codice)
        rows.append({'elemento': nome, 'trovato_nel_codice': 'si' if c in j else 'NO', 'codice': codice, 'significato': sig})
    assert all(r['trovato_nel_codice'] == 'si' for r in rows), [r['elemento'] for r in rows if r['trovato_nel_codice'] != 'si']
    write('evidenze_codice_colpi.csv', rows)


# ---------------------------------------------------------------- 2. evocazioni: parametri e lanci dal replay
# (classe, nome nel replay) -> parametri. 'unita' puo' dipendere dal tempo (livello dell'abilita').
LIV2_FERAL = 2060.194   # Claws prende il talento Guardian: Feral Spirit al livello 2 (eventi_livelli_e_bonus.csv)
EVOCAZIONI = [
    dict(classe='Claws', abilita='Feral Spirit', voce='Lupi (Claws)', cooldown=20, durata=18,
         unita=lambda t: 2 if t < LIV2_FERAL else 1, hp_base=100,
         nota='2 lupi da 100 HP base, poi 1 Spirit Guardian dal secondo 2060; HP in piu\' con l\'Agilita\''),
    dict(classe='Druid Staff', abilita='Force of Nature', voce='Treant (Druid Staff)', cooldown=70, durata=70,
         unita=lambda t: 3, hp_base=100, nota='3 Treant (livello 1 per tutta la partita); HP in piu\' con l\'Agilita\''),
    dict(classe='Wizard Staff', abilita='Water Elemental', voce='Elementale (Wizard Staff)', cooldown=40, durata=60,
         unita=lambda t: 1, hp_base=100, nota='1 elementale per lancio, durata 60 s'),
    dict(classe='Double Blade', abilita='Dimensional Gate', voce='Portali (Double Blade)', cooldown=180, durata=60,
         unita=lambda t: 2, hp_base=250, nota='2 portali di tipo "ward": di solito i nemici li attaccano poco'),
    dict(classe='Pickaxe', abilita='Construct Tower (probabile)', voce='Torre (Pickaxe)', cooldown=90, durata=None,
         unita=lambda t: 1, hp_base=250, nota='resta finche\' non ne viene costruita un\'altra (o viene distrutta)'),
    dict(classe='Runeblade', abilita='[whirlwind]', voce='Compagno (Runeblade)', cooldown=None, durata=None,
         unita=lambda t: 1, hp_base=None, nota='Banshee scelta al secondo 4925 (challenge 18); permanente, rianimabile'),
]


def lanci():
    """Lanci per evocazione: primo comando, poi solo comandi distanti almeno il 90% del cooldown."""
    acts = load(p('data_replay', 'actions_named.csv'))
    out = {}
    for ev in EVOCAZIONI:
        ts = sorted(int(a['game_time_ms']) / 1000 for a in acts
                    if CL.get(a['player']) == ev['classe'] and a['ability_name'] == ev['abilita'])
        keep = []
        for t in ts:
            if not keep or ev['cooldown'] is None or t - keep[-1] >= 0.9 * ev['cooldown']:
                keep.append(t)
        if ev['cooldown'] is None:
            keep = keep[:1]
        out[ev['voce']] = (ts, keep)
    return out


def intervalli(ev, keep, fine_partita, finestre, scenario):
    """Intervalli (inizio, fine, n unita') in cui le evocazioni sono in campo."""
    iv = []
    for i, t in enumerate(keep):
        if ev['durata'] is not None:
            fine = t + ev['durata']
        elif ev['voce'].startswith('Torre'):
            succ = keep[i + 1] if i + 1 < len(keep) else fine_partita
            if scenario == 'basso':
                # solo fino alla fine della challenge in cui e' costruita (o della successiva, se costruita in pausa)
                fin = [f for (a, f) in finestre if f >= t]
                fine = min(succ, fin[0]) if fin else succ
            else:
                fine = succ
        else:
            fine = fine_partita
        iv.append((t, fine, ev['unita'](t)))
    return iv


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


# ---------------------------------------------------------------- 3. modello
def main():
    evidenze()
    fin = load(p('data_analysis', 'v2', 'abilita_mana', 'finestre_combattimento.csv'))
    W = {int(r['challenge']): (float(r['inizio_s']), float(r['fine_s'])) for r in fin}
    finestre = [W[c] for c in sorted(W)]
    FINE = max(f for _, f in finestre)

    # Gli eroi si contano in campo per tutta la challenge: il tempo da morto non si toglie, perche' le morti
    # (domande/07_morti) si stimano dopo l'aggregato, che usa questo file. L'effetto sulle quote e' piccolo.

    L = lanci()
    par = []
    for ev in EVOCAZIONI:
        ts, keep = L[ev['voce']]
        par.append({'voce': ev['voce'], 'classe': ev['classe'], 'ruolo': RUOLO[ev['classe']], 'abilita': ev['abilita'].replace(' (probabile)', '').replace('[whirlwind]', 'Undead Companion (Banshee)'),
                    'comandi_nel_replay': len(ts), 'lanci_stimati': len(keep),
                    'unita_per_lancio': ev['unita'](0) if ev['voce'] != 'Lupi (Claws)' else '2, poi 1',
                    'durata_s': ev['durata'] if ev['durata'] else ('fino alla torre successiva' if ev['voce'].startswith('Torre') else 'permanente'),
                    'hp_base': ev['hp_base'] or '', 'nota': ev['nota']})
    write('evocazioni_parametri.csv', par)

    # esposizione per challenge: secondi-unita' delle evocazioni e secondi-eroe
    espo = {}    # scenario -> (voce, challenge) -> secondi-unita'
    for sc in SCENARI:
        e = defaultdict(float)
        for ev in EVOCAZIONI:
            for (a, b, n) in intervalli(ev, L[ev['voce']][1], FINE, finestre, sc):
                for c, (w0, w1) in W.items():
                    e[(ev['voce'], c)] += n * overlap(a, b, w0, w1)
        espo[sc] = e
    eroe_s = {(cl, c): w1 - w0 for cl in CLASSI for c, (w0, w1) in W.items()}

    VOCI = [ev['voce'] for ev in EVOCAZIONI]
    SENZA_EVOC = [c for c in CLASSI if c not in {ev['classe'] for ev in EVOCAZIONI}]
    PADRE = {ev['voce']: ev['classe'] for ev in EVOCAZIONI}

    def quote_evocazioni(sc, challenges):
        """Quota (sul totale colpi del team) presa da ogni voce di evocazione, sulle challenge indicate."""
        k = SCENARI[sc]
        H = sum(eroe_s[(cl, c)] for cl in CLASSI for c in challenges)
        E = {v: sum(espo[sc][(v, c)] for c in challenges) for v in VOCI}
        den = H + k * sum(E.values())
        return {v: 100 * k * E[v] / den if den else 0.0 for v in VOCI}

    rows_esp = []
    for c in sorted(W):
        for v in VOCI:
            rows_esp.append({'challenge': c, 'voce': v, 'classe': PADRE[v],
                             'secondi_unita_centrale': r1(espo['centrale'][(v, c)]), 'secondi_unita_basso': r1(espo['basso'][(v, c)]),
                             'durata_challenge_s': r1(W[c][1] - W[c][0]),
                             'unita_medie_in_campo': r1(espo['centrale'][(v, c)] / (W[c][1] - W[c][0]), 2)})
    write('evocazioni_esposizione_challenge.csv', rows_esp)

    # quota del modello per classe e challenge (senza pavimento: lo applica chi la usa, sul totale stimato del round)
    rows_mod = []
    for c in sorted(W):
        q = {sc: quote_evocazioni(sc, [c]) for sc in SCENARI}
        for cl in CLASSI:
            rows_mod.append({'challenge': c, 'classe': cl, 'ruolo': RUOLO[cl],
                             **{f'quota_evocazioni_modello_{sc}': r1(sum(v for vv, v in q[sc].items() if PADRE[vv] == cl), 3) for sc in SCENARI}})
    write('evocazioni_quota_modello_challenge.csv', rows_mod)

    # ------------------------------------------------ scorporo sugli screenshot (quote cumulative)
    snaps = load(p('data_screenshots', 'multiboard_snapshots.csv'))
    per_shot = defaultdict(dict)
    for s in snaps:
        per_shot[(s['screenshot'], int(s['game_time_s']), s['phase'], s['challenges_completed'])][CL[s['player']]] = float(s['tank_pct'])
    rows_snap = []
    for (shot, t, phase, done), tank in sorted(per_shot.items(), key=lambda x: x[0][1]):
        chs = [c for c in W if W[c][0] < t]
        # per la challenge in corso conta solo la parte gia' giocata: si usa la finestra tagliata a t
        out = {}
        for sc, k in SCENARI.items():
            H = 0.0; E = defaultdict(float)
            for c in chs:
                w0, w1 = W[c]; frac = (min(w1, t) - w0) / (w1 - w0) if w1 > w0 else 0
                H += sum(eroe_s[(cl, c)] for cl in CLASSI) * frac
                for v in VOCI:
                    E[v] += espo[sc][(v, c)] * frac
            den = H + k * sum(E.values())
            out[sc] = {v: 100 * k * E[v] / den if den else 0.0 for v in VOCI}
        pav = min(tank[c] for c in SENZA_EVOC if c in tank)
        for cl in CLASSI:
            if cl not in tank:
                continue
            r = {'screenshot': shot, 'game_time_s': t, 'fase': phase, 'challenge_completate': done, 'classe': cl, 'ruolo': RUOLO[cl],
                 'colpi_quota_totale_misurata': tank[cl], 'pavimento_eroe': pav,
                 **{f'limitata_{sc}': 'no' for sc in SCENARI}}
            for sc in SCENARI:
                ev_q = sum(q for v, q in out[sc].items() if PADRE[v] == cl)
                lim = max(0.0, tank[cl] - pav)
                if ev_q > lim:
                    r[f'limitata_{sc}'] = 'si'
                ev_q = min(ev_q, lim)
                r[f'colpi_quota_evocazioni_{sc}'] = r1(ev_q, 2)
                r[f'colpi_quota_eroe_{sc}'] = r1(tank[cl] - ev_q, 2)
            rows_snap.append(r)
    write('colpi_snapshot.csv', rows_snap)

    # ------------------------------------------------ quadro finale: dopo la challenge 19 e al boss
    def finale(shot_id):
        rs = [r for r in rows_snap if r['screenshot'] == shot_id]
        t = rs[0]['game_time_s']
        chs = [c for c in W if W[c][0] < t]
        q = {sc: quote_evocazioni(sc, chs) for sc in SCENARI}
        righe = []
        for r in rs:
            righe.append({'voce': r['classe'], 'tipo': 'eroe', 'classe': r['classe'], 'ruolo': r['ruolo'],
                          'colpi_quota_centrale': r['colpi_quota_eroe_centrale'],
                          'colpi_quota_min': min(r[f'colpi_quota_eroe_{s}'] for s in SCENARI),
                          'colpi_quota_max': max(r[f'colpi_quota_eroe_{s}'] for s in SCENARI),
                          'colpi_quota_totale_classe_misurata': r['colpi_quota_totale_misurata']})
        for v in VOCI:
            cl = PADRE[v]
            rc = next(r for r in rs if r['classe'] == cl)
            tot = rc['colpi_quota_totale_misurata']
            # con una sola voce di evocazione per classe la quota della voce e' quella delle evocazioni della classe
            vals = [rc[f'colpi_quota_evocazioni_{s}'] for s in SCENARI]
            if max(vals) < 0.05:
                continue
            lim = any(rc.get(f'limitata_{s}') == 'si' for s in SCENARI)
            righe.append({'voce': v, 'tipo': 'evocazione', 'classe': cl, 'ruolo': RUOLO[cl],
                          'colpi_quota_centrale': rc['colpi_quota_evocazioni_centrale'], 'colpi_quota_min': min(vals),
                          'colpi_quota_max': max(vals), 'colpi_quota_totale_classe_misurata': tot,
                          'limitata_dal_pavimento': 'si' if lim else 'no'})
        for r in righe:
            r.setdefault('limitata_dal_pavimento', '')
        return righe

    shots = {r['screenshot']: (r['fase'], r['challenge_completate'], r['game_time_s']) for r in rows_snap}
    dopo19 = next(s for s, (f, d, t) in shots.items() if f == 'post' and d == '19')
    boss = max((s for s, (f, d, t) in shots.items() if f == 'boss'), key=lambda s: shots[s][2])
    # al boss: ultimo screenshot 'boss' con tutte e 10 le classi
    boss = max((s for s, (f, d, t) in shots.items() if f == 'boss' and sum(1 for r in rows_snap if r['screenshot'] == s) == 10),
               key=lambda s: shots[s][2])
    write('colpi_finali_dopo_challenge_19.csv', finale(dopo19))
    write('colpi_finali_boss.csv', finale(boss))

    # ------------------------------------------------ per challenge: quote della singola challenge (stima per differenza)
    # Quota della challenge k = (S_k*T_k - S_(k-1)*T_(k-1)) / (T_k - T_(k-1)), con T = secondi di combattimento cumulati
    # (stesso metodo "proxy tempo" delle altre analisi). Valori negativi -> 0 e rinormalizzazione a 100.
    snap_ch = {}
    for s, (f, d, t) in shots.items():
        if f == 'post' and d.isdigit():
            snap_ch[int(d)] = s
    snap_ch[20] = boss
    Tcum = {}
    acc = 0.0
    for c in sorted(W):
        acc += W[c][1] - W[c][0]; Tcum[c] = acc
    serie = {'totale': 'colpi_quota_totale_misurata', **{f'eroe_{sc}': f'colpi_quota_eroe_{sc}' for sc in SCENARI}}
    val = {(r['screenshot'], r['classe']): r for r in rows_snap}
    rows_ch = []
    prev = None
    for c in sorted(snap_ch):
        s = snap_ch[c]
        cur = {cl: val[(s, cl)] for cl in CLASSI if (s, cl) in val}
        out = {}
        for nome, col in serie.items():
            if prev is None:
                q = {cl: float(cur[cl][col]) for cl in cur}
            else:
                cp, sp = prev
                T1, T0 = Tcum[c], Tcum[cp]
                q = {cl: max(0.0, (float(cur[cl][col]) * T1 - float(val[(sp, cl)][col]) * T0) / (T1 - T0))
                     for cl in cur if (sp, cl) in val}
            tot_raw = sum(float(cur[cl]['colpi_quota_totale_misurata']) for cl in cur) if nome == 'totale' else None
            out[nome] = q
        # rinormalizza: totale a 100; eroi alla stessa scala del totale
        scala = 100 / sum(out['totale'].values())
        for cl in out['totale']:
            tot = out['totale'][cl] * scala
            row = {'classe': cl, 'ruolo': RUOLO[cl], 'challenge': c, 'challenge_precedente_usata': prev[0] if prev else '',
                   'colpi_quota_round_totale': r1(tot, 2)}
            for sc in SCENARI:
                er = min(tot, out[f'eroe_{sc}'].get(cl, 0.0) * scala)
                row[f'colpi_quota_round_eroe_{sc}'] = r1(er, 2)
                row[f'colpi_quota_round_evocazioni_{sc}'] = r1(tot - er, 2)
            rows_ch.append(row)
        prev = (c, s)
    write('colpi_per_challenge.csv', rows_ch)

    # ------------------------------------------------ verifiche sui dati
    ver = []
    # (a) Runeblade prima/dopo il compagno (challenge 18)
    rb = {x['challenge']: x['colpi_quota_round_totale'] for x in rows_ch if x['classe'] == 'Runeblade'}
    prima = [rb[c] for c in (14, 15, 16, 17) if c in rb]; dopo = [rb[c] for c in (18, 19, 20) if c in rb]
    pred = [next(x['colpi_quota_round_evocazioni_centrale'] for x in rows_ch if x['classe'] == 'Runeblade' and x['challenge'] == c) for c in (18, 19, 20)]
    ver.append({'verifica': 'Runeblade: quota colpi per round, challenge 14-17 (senza compagno) vs 18-20 (con compagno)',
                'valore_osservato': f'{st.mean(prima):.1f} -> {st.mean(dopo):.1f} (differenza {st.mean(dopo) - st.mean(prima):+.1f} punti)',
                'previsto_dal_modello_centrale': f'{st.mean(pred):.1f} punti presi dal compagno',
                'lettura': 'se la quota sale di circa quanto previsto, il modello e\' plausibile; poche challenge, indicazione debole'})
    # (b) Claws: quota colpi per round contro unita' evocate in campo
    xs, ys = [], []
    for c in sorted(W):
        x = next((x for x in rows_ch if x['classe'] == 'Claws' and x['challenge'] == c), None)
        if x:
            xs.append(espo['centrale'][('Lupi (Claws)', c)] / (W[c][1] - W[c][0])); ys.append(x['colpi_quota_round_totale'])
    if len(xs) > 3:
        mx, my = st.mean(xs), st.mean(ys)
        b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
        rho = st.correlation(xs, ys) if hasattr(st, 'correlation') else float('nan')
        ver.append({'verifica': 'Claws: quota colpi per round contro lupi medi in campo (per challenge)',
                    'valore_osservato': f'pendenza {b:+.1f} punti per lupo in campo, correlazione {rho:+.2f}, n = {len(xs)}',
                    'previsto_dal_modello_centrale': 'circa +8/+10 punti per lupo sempre in campo (un\'unita\' in piu\' su ~11)',
                    'lettura': 'pendenza positiva = i lupi prendono colpi; la forza del legame dice quanto fidarsi'})
    write('verifiche_modello.csv', ver)

    for r in finale(dopo19):
        print(f"{r['voce']:28s} {r['colpi_quota_centrale']:>6} ({r['colpi_quota_min']}-{r['colpi_quota_max']})  totale classe {r['colpi_quota_totale_classe_misurata']}")
    for v in ver:
        print(v['verifica'], '|', v['valore_osservato'], '|', v['previsto_dal_modello_centrale'])
    for x in par:
        print(x['voce'], x['comandi_nel_replay'], '->', x['lanci_stimati'])


if __name__ == '__main__':
    main()
