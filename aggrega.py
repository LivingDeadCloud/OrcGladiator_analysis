"""Aggrega i risultati delle quattro analisi (classi/ruoli, cure, wave, abilita'/mana) in data_analysis/v2/aggregato/.

Va lanciato dopo analisi_classi_ruoli.py, analisi_cure.py, analisi_wave.py e analisi_abilita_mana.py.
Uso: python aggrega.py

Output:
- confronto_metodi_round.csv: i tre metodi di stima della quota del singolo round, confrontati con i premi
  "migliore del round"; quello con piu' concordanze diventa il metodo usato sotto.
- scheda_classi.csv / scheda_ruoli.csv: una riga per classe / ruolo con tutte le metriche principali.
- classe_challenge.csv / ruolo_challenge.csv: classe (ruolo) x challenge, con tipo di wave.
- classe_tipo_wave.csv / ruolo_tipo_wave.csv: medie per tipo di wave (challenge 1-19) col metodo scelto.
- dizionario_metriche.csv: per ogni metrica fonte, misurata/stimata e affidabilita'.
"""
import csv, os
from collections import defaultdict

V2 = os.path.join('data_analysis', 'v2')
OUT = os.path.join(V2, 'aggregato')
os.makedirs(OUT, exist_ok=True)
PLAYERS = [r['player'] for r in csv.DictReader(open('data_map/class_roles.csv', encoding='utf-8'))]


def load(*p):
    return list(csv.DictReader(open(os.path.join(V2, *p), encoding='utf-8')))


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def chn(x):
    """Numero di challenge anche da valori come '20 (boss)'."""
    return int(str(x).split()[0])


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def write(name, rows, cols=None):
    cols = cols or list(rows[0])
    with open(os.path.join(OUT, name), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


# ---------- fonti ----------
prof = {r['classe']: r for r in load('classi_ruoli', 'profilo_classi.csv')}
coer = {r['classe']: r for r in load('classi_ruoli', 'coerenza_ruoli.csv')}
andam = {(r['classe'], chn(r['challenge'])): r for r in load('classi_ruoli', 'andamento_classi.csv')}
attiv = {(r['classe'], chn(r['challenge'])): r for r in load('classi_ruoli', 'attivita_classi.csv')}
premi = {chn(r['challenge']): r for r in load('classi_ruoli', 'round_classi.csv')}
cure = {r['classe']: r for r in load('cure', 'riepilogo_classi.csv')}
cure_ch = {(r['classe'], chn(r['challenge'])): r for r in load('cure', 'stima_cure_solo_abilita.csv')}
wtipo = {chn(r['challenge']): r for r in load('wave', 'wave_tipo.csv')}
wround = {chn(r['challenge']): r for r in load('wave', 'round_per_tipo.csv')}
wcl = {(r['classe'], chn(r['challenge'])): r for r in load('wave', 'classe_round.csv')}
mana = {r['classe']: r for r in load('abilita_mana', 'riepilogo_classe.csv')}
mana_ch = {(r['classe'], chn(r['challenge'])): r for r in load('abilita_mana', 'zone_mana_challenge.csv')}
cd_ch = defaultdict(list)
for r in load('abilita_mana', 'cooldown_abilita_challenge.csv'):
    cd_ch[(r['classe'], chn(r['challenge']))].append(r)

CLASSI = list(prof)
RUOLO = {c: prof[c]['ruolo'] for c in CLASSI}
RUOLI = ['Tank', 'Healer', 'Support', 'DPS mischia', 'DPS distanza']
CHALL = range(1, 21)
# 'tank' = quota di COLPI presi (evocazioni comprese); 'colpi_eroe' = colpi del solo eroe (stima, analisi_colpi.py)
METRICHE = ['danni', 'boss', 'cure', 'tank', 'colpi_eroe']

# ---------- 1. scelta del metodo per la quota del singolo round ----------
metodi = {
    'tempo_vincolato (classi_ruoli)': lambda c, ch, m: f(andam[(c, ch)][f'{m}_round_stima']),
    'peso_hp_nemici (wave)': lambda c, ch, m: f(wcl[(c, ch)][f'{m}_quota_round_stimata']),
    'tempo_semplice (wave)': lambda c, ch, m: f(wcl[(c, ch)][f'{m}_quota_round_tempo']),
}
PREMIO_COL = {'danni': 'migliore_danni', 'boss': 'migliore_boss', 'tank': 'migliore_tank', 'cure': 'migliore_cure'}
confronto = []
for nome, get in metodi.items():
    ok = tot = 0
    for ch in range(2, 20):  # la challenge 1 e' identica in tutti i metodi
        for m in PREMIO_COL:
            vinc = premi.get(ch, {}).get(PREMIO_COL[m])
            if not vinc:
                continue
            vals = {c: get(c, ch, m) for c in CLASSI}
            if any(v is None for v in vals.values()):
                continue
            tot += 1
            ok += max(vals, key=vals.get) == vinc
    confronto.append({'metodo': nome, 'premi_confrontati': tot, 'concordanze': ok,
                      'pct_concordanza': round(100 * ok / tot, 1) if tot else None})
best = max(confronto, key=lambda r: r['concordanze'])
for r in confronto:
    r['scelto'] = 'si' if r is best else 'no'
write('confronto_metodi_round.csv', confronto)
quota_round = metodi[best['metodo']]
print('Metodo quota per round:', best['metodo'], f"({best['concordanze']}/{best['premi_confrontati']})")

# ---------- 2. classe x challenge ----------
rows_cc = []
for c in CLASSI:
    for ch in CHALL:
        a, at, w, mc = andam.get((c, ch), {}), attiv.get((c, ch), {}), wtipo[ch], mana_ch.get((c, ch), {})
        cds = cd_ch.get((c, ch), [])
        row = {'classe': c, 'ruolo': RUOLO[c], 'distanza': prof[c]['distanza'], 'challenge': ch,
               'ondata': w['ondata'], 'tipo_wave': w['tipo_wave'], 'tipo_boss': w['tipo_boss'],
               'secondi_round': wround[ch]['secondi'], 'voto_round': wround[ch]['voto']}
        for m in METRICHE:
            row[f'{m}_quota_cum'] = a.get(f'{m}_cum')
            row[f'{m}_quota_round'] = quota_round(c, ch, m) if (c, ch) in andam and (c, ch) in wcl else None
        cc = cure_ch.get((c, ch), {})
        for s in 'abc':
            row[f'cure_solo_abilita_round_{s}'] = cc.get(f'quota_solo_abilita_challenge_{s}')
        row.update({
            'hp_fine_round': a.get('hp_fine_round'), 'livello': a.get('livello'), 'oro': a.get('oro'),
            'apm': at.get('apm'), 'abilita_min': at.get('abilita_min'),
            'click_movimento_min': at.get('click_movimento_min'), 'oggetti_usati': at.get('oggetti_usati'),
            'mana_pct_sotto_20': mc.get('pct_sotto_20'), 'mana_pct_20_80': mc.get('pct_20_80'),
            'mana_pct_sopra_80': mc.get('pct_sopra_80'), 'mana_affidabilita': mc.get('affidabilita_simulazione'),
            'cast_effettivi': sum(int(x['cast_effettivi_stimati']) for x in cds) if cds else None,
            'ordini_sprecati_cooldown': sum(int(x['ordini_sprecati']) for x in cds) if cds else None,
            'cooldown_occupato_medio_pct': mean([f(x['cooldown_occupato_pct']) for x in cds]),
            'premi_round': ', '.join(m for m in PREMIO_COL if premi.get(ch, {}).get(PREMIO_COL[m]) == c),
        })
        rows_cc.append(row)
write('classe_challenge.csv', rows_cc)

# ---------- 3. ruolo x challenge ----------
SOMMA = [f'{m}_quota_round' for m in METRICHE] + [f'{m}_quota_cum' for m in METRICHE] + \
        [f'cure_solo_abilita_round_{s}' for s in 'abc']
MEDIA = ['hp_fine_round', 'livello', 'apm', 'abilita_min', 'click_movimento_min', 'cooldown_occupato_medio_pct']
rows_rc = []
for ruolo in RUOLI:
    for ch in CHALL:
        g = [r for r in rows_cc if r['ruolo'] == ruolo and r['challenge'] == ch]
        row = {'ruolo': ruolo, 'challenge': ch, 'n_classi': len(g), 'ondata': g[0]['ondata'],
               'tipo_wave': g[0]['tipo_wave'], 'secondi_round': g[0]['secondi_round'], 'voto_round': g[0]['voto_round']}
        for k in SOMMA:
            vals = [f(r[k]) for r in g]
            row[k] = round(sum(vals), 2) if all(v is not None for v in vals) else None
        for k in MEDIA:
            row[k + ('' if k.endswith('_pct') else '_medio')] = mean([f(r[k]) for r in g])
        ok = [r for r in g if r['mana_affidabilita'] in ('affidabile', 'indicativa')]
        row['mana_pct_20_80_medio'] = mean([f(r['mana_pct_20_80']) for r in ok])
        row['mana_classi_usate'] = ' + '.join(r['classe'] for r in ok)
        row['sotto_20hp'] = sum(1 for r in g if f(r['hp_fine_round']) is not None and f(r['hp_fine_round']) <= 20)
        rows_rc.append(row)
write('ruolo_challenge.csv', rows_rc)

# ---------- 4. per tipo di wave (challenge 1-19, col metodo scelto) ----------
def per_tipo(rows, key):
    out = []
    for k in sorted({r[key] for r in rows}, key=lambda x: (RUOLI + CLASSI).index(x) if x in RUOLI + CLASSI else 99):
        for t in ['mischia', 'distanza', 'ibrida']:
            g = [r for r in rows if r[key] == k and r['tipo_wave'] == t and r['challenge'] <= 19]
            row = {key: k, 'tipo_wave': t, 'n_wave': len({r['challenge'] for r in g})}
            if key == 'classe':
                row['ruolo'] = RUOLO[k]
            for m in METRICHE:
                row[f'{m}_quota_round_media'] = mean([f(r[f'{m}_quota_round']) for r in g])
            row['cure_solo_abilita_round_b_media'] = mean([f(r['cure_solo_abilita_round_b']) for r in g])
            for k2 in ['apm', 'abilita_min', 'click_movimento_min', 'hp_fine_round']:
                row[k2 + '_medio'] = mean([f(r[k2 + ('_medio' if key == 'ruolo' else '')]) for r in g])
            row['volte_sotto_20hp'] = sum(int(r['sotto_20hp']) for r in g) if key == 'ruolo' else \
                sum(1 for r in g if f(r['hp_fine_round']) is not None and f(r['hp_fine_round']) <= 20)
            row['secondi_round_medi'] = mean([f(r['secondi_round']) for r in {r['challenge']: r for r in g}.values()])
            out.append(row)
    return out


write('classe_tipo_wave.csv', per_tipo(rows_cc, 'classe'))
write('ruolo_tipo_wave.csv', per_tipo(rows_rc, 'ruolo'))

# ---------- 5. schede ----------
def tipo_media(c, tipo, m):
    return mean([f(r[f'{m}_quota_round']) for r in rows_cc
                 if r['classe'] == c and r['tipo_wave'] == tipo and r['challenge'] <= 19])


schede = []
for c in CLASSI:
    p, cu, ma, co = prof[c], cure[c], mana[c], coer[c]
    row = {'classe': c, 'ruolo': p['ruolo'], 'distanza': p['distanza'], 'attributo': p['attributo'],
           'tipo_mappa': p['tipo_mappa'], 'ruolo_osservato': co['ruolo_osservato'], 'ruolo_coerente': co['coerente'],
           'quota_danni': p['quota_danni'], 'quota_boss': p['quota_boss'], 'quota_tank': p['quota_tank'],
           'quota_colpi_eroe': p['quota_colpi_eroe'], 'quota_colpi_eroe_min': p['quota_colpi_eroe_min'],
           'quota_colpi_eroe_max': p['quota_colpi_eroe_max'], 'quota_colpi_evocazioni': p['quota_colpi_evocazioni'],
           'quota_cure_multiboard': p['quota_cure'],
           'quota_cure_solo_abilita_a': cu['quota_solo_abilita_stimata_a'],
           'quota_cure_solo_abilita_b': cu['quota_solo_abilita_stimata_b'],
           'quota_cure_solo_abilita_c': cu['quota_solo_abilita_stimata_c'],
           'quota_danni_boss_finale': p['quota_danni_boss_finale'], 'quota_tank_boss_finale': p['quota_tank_boss_finale'],
           'quota_colpi_eroe_boss_finale': p['quota_colpi_eroe_boss_finale'],
           'quota_cure_boss_finale': p['quota_cure_boss_finale']}
    for t in ['mischia', 'distanza', 'ibrida']:
        row[f'danni_round_wave_{t}'] = tipo_media(c, t, 'danni')
        row[f'tank_round_wave_{t}'] = tipo_media(c, t, 'tank')
        row[f'colpi_eroe_round_wave_{t}'] = tipo_media(c, t, 'colpi_eroe')
    row.update({
        'apm': p['apm'], 'abilita_min': p['abilita_min'], 'click_movimento_min': p['click_movimento_min'],
        'distanza_movimento_min': p['distanza_movimento_min'], 'oggetti_usati': p['oggetti_usati'],
        'acquisti': p['acquisti'], 'oro_medio_fine_round': p['oro_medio_fine_round'],
        'round_sotto_20hp': p['round_sotto_20hp'], 'premi_totali': p['premi_totali'],
        'premi_danni': p['premi_danni'], 'premi_tank': p['premi_tank'], 'premi_boss': p['premi_boss'],
        'premi_cure': p['premi_cure'],
        'comandi_abilita_curative': cu['comandi_abilita_curative'], 'usi_pozione_cura': cu['usi_pozione_cura'],
        'usi_pozione_solo_mana': cu['usi_pozione_solo_mana'],
        'mana_pct_20_80': ma['pct_mana_20_80_combattimento'], 'mana_pct_sotto_20': ma['pct_mana_sotto_20_combattimento'],
        'mana_pct_sopra_80': ma['pct_mana_sopra_80_combattimento'], 'mana_affidabilita': ma['affidabilita_simulazione'],
        'mana_errore_pct_max': ma['errore_loo_pct_mana_max'],
        'cast_al_minuto_combattimento': ma['cast_in_combattimento_al_minuto'],
        'cooldown_occupato_medio_pct': ma['cooldown_occupato_medio_pct_combattimento'],
        'cooldown_occupato_max_pct': ma['cooldown_occupato_max_pct_combattimento'],
        'abilita_piu_sfruttata': ma['abilita_piu_sfruttata'], 'ordini_sprecati_cooldown_pct': ma['quota_ordini_sprecati_pct'],
        'ordini_respinti_mana_sim': ma['ordini_respinti_mana_sim'],
    })
    schede.append(row)
write('scheda_classi.csv', schede)

QUOTE = [k for k in schede[0] if (k.startswith('quota_') and not k.endswith(('_min', '_max')))
         or k.startswith(('danni_round_', 'tank_round_', 'colpi_eroe_round_'))]
MEDIE = ['apm', 'abilita_min', 'click_movimento_min', 'distanza_movimento_min', 'oggetti_usati', 'oro_medio_fine_round',
         'cast_al_minuto_combattimento', 'cooldown_occupato_medio_pct', 'ordini_sprecati_cooldown_pct']
CONTEGGI = ['round_sotto_20hp', 'premi_totali', 'premi_danni', 'premi_tank', 'premi_boss', 'premi_cure',
            'comandi_abilita_curative', 'usi_pozione_cura']
sr = []
for ruolo in RUOLI:
    g = [s for s in schede if s['ruolo'] == ruolo]
    row = {'ruolo': ruolo, 'n_classi': len(g), 'classi': ' + '.join(s['classe'] for s in g),
           'ruolo_coerente': ', '.join(f"{s['classe']}: {s['ruolo_coerente']}" for s in g)}
    for k in QUOTE:
        vals = [f(s[k]) for s in g]
        row[k] = round(sum(vals), 2) if all(v is not None for v in vals) else None
        if k in ('quota_danni', 'quota_tank', 'quota_colpi_eroe', 'quota_cure_multiboard'):
            row[k + '_per_classe'] = round(row[k] / len(g), 2) if row[k] is not None else None
    for k in MEDIE:
        row[k + '_medio'] = mean([f(s[k]) for s in g])
    for k in CONTEGGI:
        row[k] = sum(int(f(s[k]) or 0) for s in g)
    ok = [s for s in g if s['mana_affidabilita'] in ('affidabile', 'indicativa')]
    for k in ('mana_pct_20_80', 'mana_pct_sotto_20', 'mana_pct_sopra_80'):
        row[k + '_medio'] = mean([f(s[k]) for s in ok])
    row['mana_classi_usate'] = ' + '.join(s['classe'] for s in ok) or 'nessuna (simulazione non affidabile)'
    sr.append(row)
write('scheda_ruoli.csv', sr)

# ---------- 6. dizionario delle metriche ----------
diz = [
    ('quota_danni / quota_boss', 'multiboard (screenshot)', 'misurata', 'alta',
     'Quota cumulativa del team dopo la challenge 19 (somma 100). Danni = importo dei danni fatti.'),
    ('quota_tank', 'multiboard (screenshot)', 'misurata', 'alta',
     'Quota di COLPI presi (numero di eventi di danno, non HP persi), evocazioni comprese: la mappa assegna al '
     'proprietario anche i colpi presi da lupi, Treant, elementali, torri, portali e compagno. Somma 100.'),
    ('quota_colpi_eroe / quota_colpi_evocazioni', 'multiboard + replay + codice mappa', 'stimata', 'media',
     'Colpi del solo eroe e delle sue evocazioni (scenario centrale k = 1; _min/_max = scenari k = 0,5 e 2). '
     'Verificata su Runeblade (compagno) e Claws (lupi). Il danno ricevuto in HP non e\' registrato dalla mappa.'),
    ('quota_cure_multiboard', 'multiboard', 'misurata', 'alta',
     'Include pozioni, rigenerazione, lifesteal (Vampiric Aura) e alcuni oggetti oltre alle abilita.'),
    ('quota_cure_solo_abilita_a/b/c', 'multiboard + codice mappa', 'stimata', 'bassa-media',
     'Tre scenari; b = centrale. Usare come forbice, non come valore esatto.'),
    ('*_quota_round', 'multiboard, per differenza', 'stimata', 'media',
     f"Metodo {best['metodo']}: concorda con i premi del round in {best['concordanze']}/{best['premi_confrontati']} casi. "
     'Ordine tra classi affidabile, valori puntuali +-1-2 punti.'),
    ('tipo_wave', 'codice mappa (war3map.j + dati unita)', 'misurata', 'alta',
     'Soglia 85% degli HP delle truppe; boss escluso. Variante 3 di tutte le wave (-waves3).'),
    ('apm / abilita_min / click_movimento_min', 'replay', 'misurata', 'alta', 'Comandi, non effetti.'),
    ('mana_pct_*', 'simulazione da replay + mappa, calibrata sugli screenshot', 'stimata', 'variabile',
     'Affidabile solo Wizard Staff; non affidabile per War Drums, Double Blade, Bow, Naga Trident (escluse dalle medie).'),
    ('cast_effettivi / cooldown_occupato_* / ordini_sprecati', 'replay + cooldown da mappa', 'stimata', 'media-alta',
     'Cast = ordini fuori cooldown (limite superiore). Autocast non visibili.'),
    ('round_sotto_20hp / hp_fine_round', 'multiboard', 'misurata', 'alta', 'Solo istante dello screenshot.'),
]
write('dizionario_metriche.csv', [dict(zip(['metrica', 'fonte', 'tipo', 'affidabilita', 'nota'], d)) for d in diz])

# ---------- controllo anonimato ----------
for fn in os.listdir(OUT):
    txt = open(os.path.join(OUT, fn), encoding='utf-8').read().lower()
    bad = [p for p in PLAYERS if p.lower() in txt]
    assert not bad, f'{fn} contiene nomi di giocatori: {bad}'
print('Scritti:', ', '.join(sorted(os.listdir(OUT))))
