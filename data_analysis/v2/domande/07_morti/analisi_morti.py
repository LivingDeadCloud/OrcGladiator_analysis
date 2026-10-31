"""Domanda 07 - Ci sono giocatori che muoiono troppo?

Da lanciare nella cartella principale del progetto:
    python data_analysis/v2/domande/07_morti/analisi_morti.py

Solo libreria standard. Nessun nome di giocatore nei file prodotti (solo classe e ruolo).

Il replay NON registra le morti. Lo script le ricostruisce in modo indiretto combinando:
  1. la meccanica della mappa (war3map.j): alla morte l'eroe viene nascosto e sostituito da un
     cadavere in pausa -> il giocatore non puo' piu' dare ordini all'eroe; a fine round tutti i
     cadaveri vengono rianimati al 10% HP e 75 mana; durante il round l'unico modo di rianimare
     usato in questa partita e' la "Ancestral Strength" della Pietra Ancestrale (oggetto I06J,
     gratuito, richiede 100 mana alla pietra, che ne guadagna 1/s durante il round e torna a 0 a
     fine round): rianima un eroe caduto a caso con HP e mana pieni;
  2. gli screenshot di fine round: firma di rianimazione = HP <= 25% e mana <= 150;
  3. i silenzi di ORDINI (non di selezioni) di ogni giocatore durante il combattimento;
  4. gli acquisti di I06J (tentativi di rianimazione) e la simulazione del mana della pietra.

Output (nella cartella di questo script):
- meccanica_morte_mappa.csv     : evidenze dal codice della mappa (trigger, valori).
- ritardo_screenshot_round.csv  : stima per round dell'istante reale di fine round e di rianimazione.
- pietra_ancestrale.csv         : ogni tentativo I06J con mana stimato della pietra ed esito stimato.
- silenzi_combattimento.csv     : tutti i silenzi di ordini >= 15 s in combattimento, con spiegazione.
- eventi_morte.csv              : un evento di morte (o possibile morte) per riga, con grado di certezza.
- morti_per_classe.csv          : conteggi per classe + indicatori "vicino alla morte" + confronto col team.
- morti_per_ruolo.csv           : idem per ruolo.
- morti_per_tipo_wave.csv       : per tipo di wave (mischia / distanza / ibrida) x ruolo.
- morti_per_challenge.csv       : per challenge: morti stimate, tentativi alla pietra, eroi a HP bassi.
"""
import csv
import math
import os
import re
from collections import defaultdict, Counter

ROOT = os.getcwd()
OUT = os.path.join(ROOT, 'data_analysis', 'v2', 'domande', '07_morti')
AGG = os.path.join(ROOT, 'data_analysis', 'v2', 'aggregato')
MANA = os.path.join(ROOT, 'data_analysis', 'v2', 'abilita_mana')
RAW = os.path.join(ROOT, 'data_map', 'raw')

RUOLI = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']
ORDINI = ('order_target', 'order_notarget', 'order_point')

# Parametri della mappa (verificati in war3map.j, vedi meccanica_morte_mappa.csv)
RIANIM_FINE_HP, RIANIM_FINE_MANA = 10, 75
RITARDO_RIANIM_FINE = 4.0      # Wave_Finish: Sleep(2) ... Sleep(2) -> Revive_Players
PIETRA_COSTO, PIETRA_MAX, PIETRA_REGEN = 100, 300, 1.0
REAZIONE = 1.0                 # s tra rianimazione e primo ordine (ipotesi, usata solo per stimare la fine round)

# Soglie dell'indicatore (calibrate sui casi certi, vedi RISPOSTA.md)
FIRMA_HP_MAX, FIRMA_MANA_MAX = 25, 150
GAP_MIN = 15.0                 # silenzi registrati
GAP_POSSIBILE = 30.0           # silenzio non spiegato -> possibile morte
GAP_PIETRA_FINESTRA = (0.5, 10.0)  # il silenzio finisce 0,5-10 s dopo un'attivazione riuscita
SILENZIO_FINALE_ALTA = 20.0    # firma singola + silenzio prima della rianimazione >= 20 s -> certezza alta
GAP_PIETRA_ALTA = 30.0         # silenzio abbinato alla pietra: >= 30 s alta, 15-30 s media (coincidenze ~25%)
HP_SENZA_FIRMA_MAX = 35        # silenzio che finisce alla rianimazione di fine round, HP un po' sopra la firma


def leggi(path):
    with open(path, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def scrivi(nome, righe, campi):
    with open(os.path.join(OUT, nome), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campi)
        w.writeheader()
        for r in righe:
            w.writerow({k: r.get(k, '') for k in campi})


def r1(x):
    return '' if x is None else round(x, 1)


# ---------------------------------------------------------------- 1. meccanica dal codice
def evidenze_mappa():
    with open(os.path.join(RAW, 'war3map.j'), encoding='latin-1') as f:
        j = f.read()
    righe = j.split('\n')

    def riga(pat):
        rx = re.compile(pat)
        for i, l in enumerate(righe):
            if rx.search(l):
                return i + 1, l.strip()[:160]
        return '', 'NON TROVATO'

    voci = [
        ('Morte eroe: trigger Create_Corpse', r'TriggerRegisterAnyUnitEventBJ\(gg_trg_Create_Corpse,EVENT_PLAYER_UNIT_DEATH',
         "Su morte di un eroe giocatore: l'eroe viene nascosto e al suo posto compare un cadavere 'O004' in pausa (non selezionabile, Aloc)."),
        ('Eroe nascosto alla morte', r'call ShowUnitHide\(GetTriggerUnit\(\)\)',
         "Da morto il giocatore non puo' dare ordini al proprio eroe: nel replay restano solo selezioni (verificato nei silenzi)."),
        ('Messaggio al morto', r'Your Gladiator is unconscious',
         'Testo mostrato: rianimabile da altri gladiatori o a fine round.'),
        ('Rianimazione a fine round: valori', r'call SetUnitLifePercentBJ\(udg_ReanimatingHero,10\.\)',
         'Revive_Players: tutti i cadaveri tornano in vita al 10% HP e 75 mana (riga successiva).'),
        ('Rianimazione a fine round: quando', r'call ConditionalTriggerExecute\(gg_trg_Revive_Players\)',
         "Chiamato da Wave_Finish ~4 s dopo la fine del round (Sleep 2 + Sleep 2), da Run_Reward e prima della fase finale del boss."),
        ('Sconfitta', r'No gladiators are alive',
         'Check_Defeat: se nessun gladiatore e\' vivo parte un conto alla rovescia di 25 s, poi sconfitta.'),
        ('Pietra Ancestrale: attivazione', r"GetItemTypeId\(GetManipulatedItem\(\)\)=='I06J'",
         "Oggetto I06J 'Ancestral Strength' (gratis): se la pietra ha >=100 mana li toglie e rianima UN eroe caduto a caso."),
        ('Pietra Ancestrale: valori rianimazione', r'set udg_RevivingHealth=10000\.',
         'HP e mana pieni (10000 / 2000, limitati al massimo).'),
        ('Pietra Ancestrale: regen', r'call SetUnitManaBJ\(gg_unit_n024_0014,\(GetUnitStateSwap\(UNIT_STATE_MANA,gg_unit_n024_0014\)\+1\)\)',
         '+1 mana/s, attiva solo durante il round (Wave_Start la abilita, Wave_Finish la disabilita e azzera il mana). Max 300 (w3u).'),
        ('Pergamena Grand Scroll of Life (I03A)', r"GetItemTypeId\(GetManipulatedItem\(\)\)=='I03A'",
         'Rianima tutti al 60% HP / 150 mana. Nessun acquisto nel replay.'),
        ('Abilita\' di rianimazione (A04B, A0E0, A00I)', r"GetSpellAbilityId\(\)=='A04B'",
         "Ordine 'animatedead' (0x0D00F9): rianima al 60% HP / 150 mana (A00I liv.1: 40%/150). Nessun ordine nel replay."),
        ('Soulstone / Revival Draught / Ancient\'s Sap', r'set udg_RevivingMana=100\.',
         'Auto-rianimazione dopo 4-6 s al 60% HP / 100 mana. Nessun acquisto di I01R/I05R/I09C nel replay.'),
        ('Contatore di morti', r'udg_DeathEvent',
         "NESSUN contatore di morti per giocatore: udg_DeathEvent e' solo un evento del sistema di cure; udg_IsPlayerHeroDead non viene mai aggiornato; la multiboard non ha una colonna morti."),
        ('Token (I056/I057/I058)', r"RemoveItem\(GetItemOfTypeFromUnitBJ\(GetDyingUnit\(\),'I056'\)\)",
         'I token-scommessa si perdono alla morte (1 solo acquisto di I056 nel replay).'),
    ]
    out = []
    for nome, pat, nota in voci:
        n, testo = riga(pat)
        out.append({'elemento': nome, 'riga_war3map_j': n, 'codice': testo, 'significato': nota})
    # verifica: IsPlayerHeroDead mai impostato a true
    n_true = len(re.findall(r'udg_IsPlayerHeroDead\[[^\]]*\]=true', j))
    out.append({'elemento': 'udg_IsPlayerHeroDead impostato a true', 'riga_war3map_j': '',
                'codice': f'occorrenze: {n_true}', 'significato': 'variabile inutilizzata come contatore'})
    scrivi('meccanica_morte_mappa.csv', out, ['elemento', 'riga_war3map_j', 'codice', 'significato'])
    return out


# ---------------------------------------------------------------- dati
def carica():
    cr = {r['player']: r for r in leggi(os.path.join(ROOT, 'data_map', 'class_roles.csv'))}
    classi = [r['classe'] for r in cr.values()]
    ruolo = {r['classe']: r['ruolo'] for r in cr.values()}
    fin = {int(r['challenge']): r for r in leggi(os.path.join(MANA, 'finestre_combattimento.csv'))}
    rounds = {int(r['challenge']): r for r in leggi(os.path.join(ROOT, 'data_screenshots', 'rounds.csv'))}
    tipo = {}
    for r in leggi(os.path.join(AGG, 'classe_challenge.csv')):
        tipo[int(r['challenge'])] = r['tipo_wave']
    snap = []
    for r in leggi(os.path.join(ROOT, 'data_screenshots', 'multiboard_snapshots.csv')):
        r = dict(r)
        r['classe'] = cr[r['player']]['classe']
        del r['player']
        snap.append(r)
    ordini = defaultdict(list)
    pietra = []
    for r in leggi(os.path.join(ROOT, 'data_replay', 'actions_named.csv')):
        t = int(r['game_time_ms']) / 1000
        c = cr[r['player']]['classe']
        if r['kind'] in ORDINI:
            ordini[c].append(t)
        if r['order'] == 'I06J':
            pietra.append((t, c))
    for c in ordini:
        ordini[c].sort()
    uscite = {cr[r['player']]['classe']: int(r['game_time_ms']) / 1000
              for r in leggi(os.path.join(ROOT, 'data_replay', 'leaves.csv'))}
    return classi, ruolo, fin, rounds, tipo, snap, ordini, sorted(pietra), uscite


def silenzi(ts, a, b, dopo=20.0):
    """Intervalli tra ordini consecutivi che iniziano in [a, b): (inizio, fine, durata)."""
    sel = [t for t in ts if a <= t <= b + dopo]
    out = []
    for x, y in zip(sel, sel[1:]):
        if x < b and y - x >= GAP_MIN:
            out.append((x, y, y - x))
    # silenzio aperto fino alla fine della finestra (nessun ordine dopo)
    if sel and sel[-1] < b and not [t for t in ts if t > sel[-1]][:1]:
        out.append((sel[-1], None, b - sel[-1]))
    return out


def poisson_coda(k, mu):
    """P(X >= k) con X ~ Poisson(mu)."""
    if k <= 0:
        return 1.0
    return 1.0 - sum(math.exp(-mu) * mu ** i / math.factorial(i) for i in range(k))


def main():
    evidenze_mappa()
    classi, ruolo, fin, rounds, tipo, snap, ordini, pietra, uscite = carica()
    CH = sorted(fin)

    # --- screenshot post per (challenge, classe) e firma di rianimazione
    post = {}
    for r in snap:
        if r['phase'] == 'post':
            post[(int(r['challenges_completed']), r['classe'])] = (float(r['hp_pct']), float(r['mana']))
    firma = {}
    for ch in CH:
        valori = Counter(v for (c2, _), v in post.items() if c2 == ch and v[0] <= FIRMA_HP_MAX)
        for c in classi:
            v = post.get((ch, c))
            if v and v[0] <= FIRMA_HP_MAX and v[1] <= FIRMA_MANA_MAX:
                firma[(ch, c)] = 'identica ad altri eroi' if valori[v] >= 2 else 'singola'

    # --- 2. stima del ritardo dello screenshot (fine reale del round)
    rit = {}
    for ch in CH:
        a, b = float(fin[ch]['inizio_s']), float(fin[ch]['fine_s'])
        fini = []
        for c in classi:
            if (ch, c) not in firma:
                continue
            for x, y, d in silenzi(ordini[c], a, b):
                if y is not None and d >= 20 and b - 40 <= y <= b + 10:
                    fini.append(y)
        if fini:
            rianim = min(fini) - REAZIONE
            rit[ch] = {'ritardo': b - (rianim - RITARDO_RIANIM_FINE), 'n': len(fini), 'primo_ordine': min(fini)}
    med = sorted(v['ritardo'] for v in rit.values())
    rit_med = med[len(med) // 2] if med else 5.0
    righe_rit = []
    T = {}
    for ch in CH:
        a, b = float(fin[ch]['inizio_s']), float(fin[ch]['fine_s'])
        d = rit[ch]['ritardo'] if ch in rit else rit_med
        T[ch] = {'start': a - d, 'finish': b - d, 'rianim': b - d + RITARDO_RIANIM_FINE, 'shot': b}
        righe_rit.append({'challenge': ch, 'fine_screenshot_s': b,
                          'ritardo_screenshot_s': r1(d),
                          'fonte': (f"misurato: primo ordine dopo il silenzio di {rit[ch]['n']} eroi con firma"
                                    if ch in rit else f'mediana degli altri round ({r1(rit_med)} s)'),
                          'fine_round_reale_s': r1(b - d), 'rianimazione_fine_round_s': r1(b - d + RITARDO_RIANIM_FINE),
                          'inizio_round_reale_s': r1(a - d), 'durata_round_s': r1(b - a),
                          'durata_fonte': fin[ch]['fonte']})
    scrivi('ritardo_screenshot_round.csv', righe_rit, list(righe_rit[0].keys()))

    # --- 3. Pietra Ancestrale: simulazione mana
    def ch_di(t):
        for ch in CH:
            if T[ch]['start'] - 5 <= t <= T[ch]['shot'] + 5:
                return ch
        return None

    att = []
    stato = {}
    for t, c in pietra:
        ch = ch_di(t)
        if ch is None:
            att.append({'t': t, 'classe': c, 'ch': None, 'mana': None, 'ok': False})
            continue
        m, tl = stato.get(ch, (0.0, T[ch]['start']))
        m = min(PIETRA_MAX, m + (min(t, T[ch]['finish']) - tl) * PIETRA_REGEN)
        ok = m >= PIETRA_COSTO and t <= T[ch]['finish']
        att.append({'t': t, 'classe': c, 'ch': ch, 'mana': m, 'ok': ok})
        stato[ch] = (m - PIETRA_COSTO if ok else m, t)

    # --- silenzi di tutti gli eroi in combattimento
    gaps = []
    for ch in CH:
        a, b = T[ch]['start'], T[ch]['shot']
        for c in classi:
            if c in uscite and uscite[c] < a:
                continue
            for x, y, d in silenzi(ordini[c], a, b):
                gaps.append({'ch': ch, 'classe': c, 'x': x, 'y': y, 'd': d})

    # abbina attivazioni riuscite -> silenzi che finiscono 0,5-10 s dopo
    for g in gaps:
        g['pietra'] = []
        if g['y'] is None:
            continue
        for k, s in enumerate(att):
            if s['ok'] and s['ch'] == g['ch'] and GAP_PIETRA_FINESTRA[0] <= g['y'] - s['t'] <= GAP_PIETRA_FINESTRA[1] \
                    and g['x'] < s['t']:
                g['pietra'].append(k)
    for k, s in enumerate(att):
        s['rianimati'] = [g['classe'] for g in gaps if k in g['pietra']]

    # --- 4. eventi di morte
    eventi = []
    spiegato = set()
    for ch in CH:
        if ch == 20:
            continue
        for c in classi:
            if (ch, c) not in firma:
                continue
            hp, mn = post[(ch, c)]
            rian = T[ch]['rianim']
            prima = [t for t in ordini[c] if t < rian - 0.5]
            ultimo = prima[-1] if prima else None
            sil = rian - ultimo if ultimo is not None else None
            g_fine = [g for g in gaps if g['ch'] == ch and g['classe'] == c and g['y'] is not None
                      and g['x'] < rian and g['y'] >= rian - 3]
            for g in g_fine:
                spiegato.add(id(g))
            identica = firma[(ch, c)] == 'identica ad altri eroi'
            lungo = sil is not None and sil >= SILENZIO_FINALE_ALTA
            cert = 'alta' if (identica or lungo) else 'media'
            ind = [f'screenshot {hp:.0f}% HP / {mn:.0f} mana (firma {firma[(ch, c)]})',
                   f'nessun ordine negli ultimi {sil:.0f} s prima della rianimazione stimata' if sil is not None else '']
            eventi.append({'classe': c, 'ruolo': ruolo[c], 'challenge': ch, 'tipo_wave': tipo.get(ch, ''),
                           'tipo_evento': 'morto a fine round (rianimato dal trigger di fine round)',
                           'morte_stimata_entro_s_dall_inizio': r1(ultimo - T[ch]['start']) if ultimo else '',
                           'secondi_da_morto_min': r1(sil), 'indizi': '; '.join(i for i in ind if i),
                           'certezza': cert,
                           'fonte': 'screenshot (misurato) + silenzio di ordini (misurato) + tempo di fine round (stimato)'})
    # silenzio lungo che termina proprio alla rianimazione di fine round, senza firma piena
    for g in gaps:
        ch, c = g['ch'], g['classe']
        if id(g) in spiegato or ch == 20 or g['y'] is None or g['d'] < GAP_POSSIBILE:
            continue
        rian = T[ch]['rianim']
        hp, mn = post.get((ch, c), (100.0, 0.0))
        if rian - 3 <= g['y'] <= rian + 10 and g['x'] < rian and hp <= HP_SENZA_FIRMA_MAX:
            spiegato.add(id(g))
            cert = 'alta' if g['d'] >= 60 else 'media'
            eventi.append({'classe': c, 'ruolo': ruolo[c], 'challenge': ch, 'tipo_wave': tipo.get(ch, ''),
                           'tipo_evento': 'morto a fine round (rianimato dal trigger di fine round)',
                           'morte_stimata_entro_s_dall_inizio': r1(g['x'] - T[ch]['start']),
                           'secondi_da_morto_min': r1(g['d']),
                           'indizi': (f"silenzio di ordini di {g['d']:.0f} s che termina {g['y'] - rian:+.1f} s dalla "
                                      f"rianimazione stimata di fine round; screenshot {hp:.0f}% HP / {mn:.0f} mana "
                                      "(sopra la soglia di firma)"),
                           'certezza': cert,
                           'fonte': 'replay (misurato) + screenshot (misurato) + tempo di fine round (stimato)'})
    for g in gaps:
        if id(g) in spiegato or not g['pietra'] or g['ch'] == 20 and g['y'] is None:
            continue
        concorrenti = [h for h in gaps if set(h['pietra']) & set(g['pietra'])]
        cert = 'alta' if len(concorrenti) == 1 and g['d'] >= GAP_PIETRA_ALTA else 'media'
        s = att[g['pietra'][0]]
        spiegato.add(id(g))
        eventi.append({'classe': g['classe'], 'ruolo': ruolo[g['classe']], 'challenge': g['ch'],
                       'tipo_wave': tipo.get(g['ch'], ''),
                       'tipo_evento': 'morto durante il round (rianimato dalla Pietra Ancestrale)',
                       'morte_stimata_entro_s_dall_inizio': r1(g['x'] - T[g['ch']]['start']),
                       'secondi_da_morto_min': r1(g['d']),
                       'indizi': (f"silenzio di ordini {g['d']:.0f} s che termina {g['y'] - s['t']:.1f} s dopo "
                                  f"un'attivazione riuscita della pietra (mana stimato {s['mana']:.0f})"
                                  + (f"; {len(concorrenti)} silenzi compatibili con la stessa attivazione" if len(concorrenti) > 1 else '')
                                  + ('; silenzio breve: coincidenza casuale possibile (~25%)' if g['d'] < GAP_PIETRA_ALTA else '')),
                       'certezza': cert,
                       'fonte': 'replay (misurato) + mana della pietra (stimato da codice)'})
    # boss finale: sconfitta = tutti morti
    sconf = {r['classe']: r for r in snap if r['phase'] == 'sconfitta'}
    for c in classi:
        r = sconf.get(c)
        ultimo = [t for t in ordini[c] if T[20]['start'] <= t <= T[20]['shot']]
        if r is None:
            stato_f = 'uscito dalla partita al momento della sconfitta (nessuna riga nello screenshot)'
        else:
            stato_f = f"screenshot finale {float(r['hp_pct']):.0f}% HP / {float(r['mana']):.0f} mana"
        eventi.append({'classe': c, 'ruolo': ruolo[c], 'challenge': 20, 'tipo_wave': tipo.get(20, ''),
                       'tipo_evento': 'sconfitta finale contro il boss (tutto il team)',
                       'morte_stimata_entro_s_dall_inizio': r1(ultimo[-1] - T[20]['start']) if ultimo else '',
                       'secondi_da_morto_min': r1(T[20]['shot'] - ultimo[-1]) if ultimo else '',
                       'indizi': stato_f + '; ultimo ordine prima della sconfitta',
                       'certezza': 'alta (morte di squadra)' if r is not None and float(r['hp_pct']) == 0 else 'non determinabile',
                       'fonte': 'screenshot sconfitta (misurato) + replay'})
    # silenzi non spiegati -> possibile morte
    for g in gaps:
        if id(g) in spiegato or g['d'] < GAP_POSSIBILE or g['ch'] == 20:
            continue
        g['possibile'] = True
        eventi.append({'classe': g['classe'], 'ruolo': ruolo[g['classe']], 'challenge': g['ch'],
                       'tipo_wave': tipo.get(g['ch'], ''),
                       'tipo_evento': 'possibile morte (solo silenzio di ordini)',
                       'morte_stimata_entro_s_dall_inizio': r1(g['x'] - T[g['ch']]['start']),
                       'secondi_da_morto_min': r1(g['d']),
                       'indizi': (f"silenzio di ordini di {g['d']:.0f} s senza firma nello screenshot e senza rianimazione "
                                  "della pietra compatibile; puo' essere anche attesa o AFK"),
                       'certezza': 'bassa', 'fonte': 'replay (misurato)'})
    eventi.sort(key=lambda e: (e['challenge'], e['classe']))
    campi_ev = ['challenge', 'tipo_wave', 'classe', 'ruolo', 'tipo_evento', 'certezza',
                'morte_stimata_entro_s_dall_inizio', 'secondi_da_morto_min', 'indizi', 'fonte']
    scrivi('eventi_morte.csv', eventi, campi_ev)

    # --- output pietra e silenzi
    righe_p = []
    for s in att:
        ch = s['ch']
        righe_p.append({'challenge': ch or '', 'classe_che_attiva': s['classe'], 'ruolo': ruolo[s['classe']],
                        'secondi_dall_inizio_round': r1(s['t'] - T[ch]['start']) if ch else '',
                        'mana_pietra_stimato': r1(s['mana']),
                        'esito_stimato': ('riuscita' if s['ok'] else 'fallita: pietra sotto 100 mana') if ch else 'fuori round',
                        'eroi_che_riprendono_a_dare_ordini_entro_10s': ' + '.join(s.get('rianimati', [])),
                        'nota': ('' if not s['ok'] or s.get('rianimati') else
                                 "riuscita ma nessun silenzio compatibile: nessun morto in quel momento, oppure eroe "
                                 "rianimato rimasto senza dare ordini")})
    scrivi('pietra_ancestrale.csv', righe_p, list(righe_p[0].keys()))
    righe_g = []
    for g in sorted(gaps, key=lambda g: (g['ch'], g['classe'], g['x'])):
        if id(g) in spiegato:
            sp = 'morte (vedi eventi_morte.csv)'
        elif g.get('possibile'):
            sp = 'possibile morte (bassa certezza)'
        elif g['ch'] == 20:
            sp = 'boss finale: non classificato'
        else:
            sp = f'sotto la soglia di {GAP_POSSIBILE:.0f} s: non classificato'
        righe_g.append({'challenge': g['ch'], 'classe': g['classe'], 'ruolo': ruolo[g['classe']],
                        'inizio_s_dall_inizio_round': r1(g['x'] - T[g['ch']]['start']),
                        'fine_s_dall_inizio_round': r1(g['y'] - T[g['ch']]['start']) if g['y'] else 'nessun ordine dopo',
                        'durata_s': r1(g['d']), 'spiegazione': sp})
    scrivi('silenzi_combattimento.csv', righe_g, list(righe_g[0].keys()))

    # --- calibrazione della soglia di silenzio
    t_comb = sum(T[ch]['shot'] - T[ch]['start'] for ch in CH if ch != 20) * len(classi)
    certi = [e for e in eventi if e['certezza'] == 'alta' and 'fine round' in e['tipo_evento']
             and 'identica' in e['indizi']]
    altri = [g for g in gaps if id(g) not in spiegato and g['ch'] != 20]
    cal = []
    for soglia in (10, 15, 20, 30, 45, 60, 90):
        sens = sum(1 for e in certi if float(e['secondi_da_morto_min']) >= soglia)
        fa = sum(1 for g in altri if g['d'] >= soglia)
        cal.append({'soglia_silenzio_s': soglia,
                    'morti_certe_con_firma_identica': len(certi),
                    'di_cui_con_silenzio_oltre_soglia': sens,
                    'sensibilita_pct': r1(100 * sens / len(certi)) if certi else '',
                    'silenzi_non_spiegati_oltre_soglia': fa,
                    'silenzi_non_spiegati_per_ora_eroe': r1(fa / (t_comb / 3600)),
                    'prob_coincidenza_finestra_10s_pct': r1(100 * (1 - math.exp(-fa / t_comb * len(classi) * 9.5)))})
    scrivi('calibrazione_soglia_silenzio.csv', cal, list(cal[0].keys()))

    # --- 5. riepiloghi
    def conta(filtro):
        k = Counter()
        for e in eventi:
            if filtro(e):
                k[(e['classe'], e['certezza'].split(' ')[0], e['tipo_evento'])] += 1
        return k

    n_round = len([ch for ch in CH if ch != 20])  # 19 round "normali"
    vicino = defaultdict(lambda: {'sotto20': 0, 'sotto20_vivo': 0, 'sotto50_vivo': 0, 'firma': 0})
    for (ch, c), (hp, mn) in post.items():
        if hp < 20:
            vicino[c]['sotto20'] += 1
        if (ch, c) in firma:
            vicino[c]['firma'] += 1
        elif hp <= 20:
            vicino[c]['sotto20_vivo'] += 1
        elif hp <= 50:
            vicino[c]['sotto50_vivo'] += 1
    sc = {r['classe']: r for r in leggi(os.path.join(AGG, 'scheda_classi.csv'))}

    per_classe = []
    for c in classi:
        ev = [e for e in eventi if e['classe'] == c and e['challenge'] != 20]
        alta = [e for e in ev if e['certezza'] == 'alta']
        media = [e for e in ev if e['certezza'] == 'media']
        bassa = [e for e in ev if e['certezza'] == 'bassa']
        per_classe.append({
            'classe': c, 'ruolo': ruolo[c],
            'morti_certezza_alta': len(alta), 'morti_certezza_media': len(media),
            'morti_alta_piu_media': len(alta) + len(media), 'possibili_morti_bassa': len(bassa),
            'di_cui_rianimato_fine_round': sum(1 for e in alta + media if 'fine round' in e['tipo_evento']),
            'di_cui_rianimato_pietra': sum(1 for e in alta + media if 'Pietra' in e['tipo_evento']),
            'round_con_morte_alta_media': len({e['challenge'] for e in alta + media}),
            'secondi_da_morto_min_totali': r1(sum(float(e['secondi_da_morto_min'] or 0) for e in alta + media)),
            'round_fine_sotto_20hp_screenshot': vicino[c]['sotto20'],
            'round_sotto_20hp_scheda_classi': sc[c]['round_sotto_20hp'],
            'round_fine_hp_basso_ma_vivo_le20': vicino[c]['sotto20_vivo'],
            'round_fine_hp_21_50_vivo': vicino[c]['sotto50_vivo'],
            'attivazioni_pietra_fatte': sum(1 for s in att if s['classe'] == c),
        })
    tot = sum(p['morti_alta_piu_media'] for p in per_classe)
    mu = tot / len(classi)
    for p in per_classe:
        k = p['morti_alta_piu_media']
        p['media_team_morti'] = r1(mu)
        p['rapporto_su_media_team'] = r1(k / mu) if mu else ''
        p['p_valore_poisson_almeno_k'] = round(poisson_coda(k, mu), 3)
        rm = [q['morti_alta_piu_media'] for q in per_classe if q['ruolo'] == p['ruolo']]
        p['media_ruolo_morti'] = r1(sum(rm) / len(rm))
        p['quota_round_morto_pct'] = r1(100 * p['round_con_morte_alta_media'] / n_round)
    per_classe.sort(key=lambda p: (-p['morti_alta_piu_media'], p['classe']))
    scrivi('morti_per_classe.csv', per_classe, list(per_classe[0].keys()))

    per_ruolo = []
    for ru in RUOLI:
        ps = [p for p in per_classe if p['ruolo'] == ru]
        n = len(ps)
        per_ruolo.append({
            'ruolo': ru, 'n_classi': n, 'classi': ' + '.join(p['classe'] for p in ps),
            'morti_alta_piu_media': sum(p['morti_alta_piu_media'] for p in ps),
            'morti_per_classe': r1(sum(p['morti_alta_piu_media'] for p in ps) / n),
            'possibili_bassa_per_classe': r1(sum(p['possibili_morti_bassa'] for p in ps) / n),
            'round_fine_sotto_20hp_per_classe': r1(sum(p['round_fine_sotto_20hp_screenshot'] for p in ps) / n),
            'round_hp_basso_ma_vivo_per_classe': r1(sum(p['round_fine_hp_basso_ma_vivo_le20'] for p in ps) / n),
            'media_team_morti_per_classe': r1(mu)})
    scrivi('morti_per_ruolo.csv', per_ruolo, list(per_ruolo[0].keys()))

    # per tipo di wave
    righe_w = []
    tipi = sorted({tipo[ch] for ch in CH if ch != 20})
    for tw in tipi:
        chs = [ch for ch in CH if ch != 20 and tipo[ch] == tw]
        for ru in RUOLI + ['TEAM']:
            cl = [c for c in classi if ru == 'TEAM' or ruolo[c] == ru]
            ev = [e for e in eventi if e['challenge'] in chs and e['classe'] in cl and e['certezza'] in ('alta', 'media')]
            sotto = sum(1 for ch in chs for c in cl if post.get((ch, c), (100,))[0] < 20)
            esposti = len(chs) * len(cl)
            righe_w.append({'tipo_wave': tw, 'challenge': ' '.join(map(str, chs)), 'ruolo': ru,
                            'n_classi': len(cl), 'eroi_round': esposti,
                            'morti_alta_media': len(ev),
                            'morti_per_100_eroi_round': r1(100 * len(ev) / esposti),
                            'fine_round_sotto_20hp': sotto,
                            'sotto_20hp_per_100_eroi_round': r1(100 * sotto / esposti)})
    scrivi('morti_per_tipo_wave.csv', righe_w, list(righe_w[0].keys()))

    # per challenge
    righe_c = []
    for ch in CH:
        ev = [e for e in eventi if e['challenge'] == ch]
        righe_c.append({
            'challenge': ch, 'ondata': rounds[ch]['wave'], 'tipo_wave': tipo.get(ch, ''),
            'voto': rounds[ch]['grade'], 'durata_s': fin[ch]['durata_s'],
            'morti_alta': sum(1 for e in ev if e['certezza'] == 'alta'),
            'morti_media': sum(1 for e in ev if e['certezza'] == 'media'),
            'possibili_bassa': sum(1 for e in ev if e['certezza'] == 'bassa'),
            'classi_morte_alta_media': ' + '.join(sorted({e['classe'] for e in ev if e['certezza'] in ('alta', 'media')})),
            'tentativi_pietra': sum(1 for s in att if s['ch'] == ch),
            'attivazioni_pietra_riuscite_stimate': sum(1 for s in att if s['ch'] == ch and s['ok']),
            'eroi_fine_sotto_20hp': sum(1 for c in classi if post.get((ch, c), (100,))[0] < 20),
            'eroi_con_firma_rianimazione': sum(1 for c in classi if (ch, c) in firma)})
    scrivi('morti_per_challenge.csv', righe_c, list(righe_c[0].keys()))

    # --- controllo: nessun nome di giocatore negli output
    nomi = [r['player'] for r in leggi(os.path.join(ROOT, 'data_map', 'class_roles.csv'))]
    for fn in os.listdir(OUT):
        if fn.endswith(('.csv', '.md')):
            with open(os.path.join(OUT, fn), encoding='utf-8') as f:
                testo = f.read()
            for n in nomi:
                if n in testo:
                    raise SystemExit(f'ERRORE: nome di giocatore in {fn}')

    # --- riepilogo a video
    print(f'Ritardo mediano screenshot: {rit_med:.1f} s; round con ritardo misurato: {sorted(rit)}')
    print('Eventi:', Counter((e['certezza'], e['tipo_evento']) for e in eventi))
    print('Attivazioni pietra:', len(att), 'riuscite stimate:', sum(s['ok'] for s in att))
    for p in per_classe:
        print(f"{p['classe']:13} {p['ruolo']:12} alta {p['morti_certezza_alta']} media {p['morti_certezza_media']} "
              f"bassa {p['possibili_morti_bassa']}  <20hp {p['round_fine_sotto_20hp_screenshot']} "
              f"vivo<=20 {p['round_fine_hp_basso_ma_vivo_le20']}  p={p['p_valore_poisson_almeno_k']}")


if __name__ == '__main__':
    main()
