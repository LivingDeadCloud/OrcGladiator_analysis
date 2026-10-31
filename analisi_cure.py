"""Cure al netto di pozioni e aure.

Uso (dalla cartella del progetto):   python analisi_cure.py

Legge:
  data_map/raw/war3map.j                       script JASS della mappa (per le evidenze sul conteggio cure)
  data_map/class_roles.csv                     giocatore -> classe, ruolo (i nomi NON vengono mai scritti)
  data_screenshots/multiboard_snapshots.csv    heal_pct / tank_pct cumulativi (trascritti a mano)
  data_screenshots/rounds.csv                  secondi impiegati per challenge (peso per le quote per challenge)
  data_replay/actions_named.csv                comandi del replay

Scrive in data_analysis/v2/cure/:
  evidenze_codice_cure.csv      ogni punto del war3map.j che alimenta udg_HealCountTotal, con sorgente e quantita
  catalogo_fonti_cura.csv       fonti di cura per classe, tipo, categoria (abilita / esclusa) e formula
  quota_cure_per_challenge.csv  heal_pct e tank_pct: cumulativi (misurati), variazione e quota per challenge (stimata)
  stima_cure_solo_abilita.csv   stima della quota "solo abilita" (3 scenari) cumulativa e per challenge
  uso_pozioni_slot.csv          mappa slot -> pozione ricostruita dal replay, con le evidenze
  eventi_cura_replay.csv        per classe x challenge: comandi di abilita curative e usi di pozioni
  comandi_abilita_curative.csv  dettaglio per classe x challenge x abilita
  riepilogo_classi.csv          una riga per classe
Solo libreria standard.
"""
import csv
import os
import re
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, 'data_analysis', 'v2', 'cure')
JASS = os.path.join(BASE, 'data_map', 'raw', 'war3map.j')


def p(*a):
    return os.path.join(BASE, *a)


def load(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(name, header, rows):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([r.get(h, '') for h in header] if isinstance(r, dict) else r)
    print(f'  {name}: {len(rows)} righe')


def r1(x, n=1):
    return '' if x is None else round(x, n)


# --------------------------------------------------------------------------------------------
# 0. Classi (nessun nome giocatore in output)
# --------------------------------------------------------------------------------------------
ROLES = {r['player']: (r['classe'], r['ruolo']) for r in load(p('data_map', 'class_roles.csv'))}
CLASSI = sorted({c for c, _ in ROLES.values()})
RUOLO = {c: r for c, r in ROLES.values()}

# Classi che NON hanno alcuna abilita che chiami Heal_Unit (verificato sul war3map.j, vedi NOTE.md).
# War Hammer: l'unica cura da abilita (Avatar, 2% HP/s) richiede l'oggetto Runed Bracers (I095)
# o I077; nel replay i Runed Bracers sono comprati a 5431 s (durante la challenge 19).
CLASSI_SENZA_CURE_ABILITA = ['Bow', 'Naga Trident', 'Pickaxe', 'Wizard Staff']
CLASSI_RIFERIMENTO = CLASSI_SENZA_CURE_ABILITA + ['War Hammer']

# --------------------------------------------------------------------------------------------
# 1. Evidenze dal codice: chi alimenta udg_HealCountTotal
# --------------------------------------------------------------------------------------------
# prefisso funzione JASS -> (fonte, classe/oggetto, tipo, categoria rispetto alla richiesta)
CLASSIFICA = [
    ('Trig_PotionPeriodic', 'Pozioni (sistema UsePotion/PotionPeriodic)', 'tutte', 'pozione', 'esclusa: pozione'),
    ('Trig_GlobalRegeneration', 'Rigenerazione % HP (Regeneration_Value: base 0,5 + oggetti)', 'tutte', 'rigenerazione', 'esclusa: rigenerazione'),
    ('Trig_GlobalLifeSteal', 'Lifesteal (buff Vampiric Aura B002, Hunger B027, Mask of Death I05X/I04X, Enchant: Blood A0AW)', 'tutte', 'lifesteal/aura', 'esclusa: aura/lifesteal'),
    ('Trig_GlobalItemEffects', 'Oggetti: Scepter of Healing (A0BJ, 30% HP) e Heartstone (I096/I0AQ, 4% HP a ogni incantesimo)', 'tutte', 'oggetto', 'esclusa: oggetto'),
    ('Trig_DruidRejuvenation', 'Rejuvenation (A05R)', 'Druid Staff', 'cura nel tempo', 'abilita'),
    ('Trig_DruidTranquility', 'Tranquility (A05Y)', 'Druid Staff', 'cura ad area nel tempo', 'abilita'),
    ('Trig_DruidInnervate', 'Innervate (A060, liv. 3-4 applica Rejuvenation)', 'Druid Staff', 'cura nel tempo (condizionale)', 'abilita'),
    ('Trig_WarDrumsPeriodic', 'Motivate (A0AJ, passiva sugli attacchi; Rally la raddoppia)', 'War Drums', 'cura nel tempo', 'abilita'),
    ('Trig_WarDrumsWarDrums', 'War Drums / Bestow Aura (A0A0-A0AA)', 'War Drums', 'cura ad area', 'abilita'),
    ('Trig_RunebladeDeathCoil', 'Death Coil (A0HJ) su alleato', 'Runeblade', 'cura diretta', 'abilita'),
    ('Trig_RunebladeDeathPact', 'Death Pact (A0HK)', 'Runeblade', 'auto-cura diretta', 'abilita'),
    ('Trig_RunebladeCannibalize', 'Cannibalize (A0HY)', 'Runeblade', 'auto-cura nel tempo', 'abilita'),
    ('Trig_ClawsRockShield', 'Rock Shield (A0G6)', 'Claws', 'cura diretta', 'abilita'),
    ('Trig_ClawsManaTideTotem', 'Mana Tide Totem (A01J)', 'Claws', 'cura ad area nel tempo (condizionale)', 'abilita'),
    ('Trig_DoubleEdgeDemonSkin', 'Demon Skin (A036)', 'Double Blade', 'auto-cura nel tempo', 'abilita'),
    ('Trig_WarHammerAvatar', 'Avatar (A00Q) con Runed Bracers I095/I077', 'War Hammer', 'auto-cura nel tempo (condizionale)', 'abilita'),
    ('Trig_Create_Corpse', 'Avenging Rage (A03V) alla morte di un alleato', 'Katana (non in partita)', 'auto-cura diretta', 'abilita'),
    ('Trig_NecromancerSoulHarvest', 'Soul Harvest (A00B)', 'Necromancer (non in partita)', 'auto-cura', 'abilita'),
    ('Trig_FleshGolemStrikes', 'Flesh Golem (evocazione)', 'Necromancer (non in partita)', 'cura ad area', 'abilita'),
    ('Trig_GreatAxeRelentless', 'Relentless', 'Great Axe (non in partita)', 'auto-cura nel tempo', 'abilita'),
    ('Trig_CrystalBall', 'Alter Fate / Saviour', 'Crystal Ball (non in partita)', 'cura diretta', 'abilita'),
    ('Trig_AlchemyFlaskHealingPlume', 'Healing Plume (A0KL)', 'Alchemy Flask (non in partita)', 'cura ad area nel tempo', 'abilita'),
    ('Trig_AlchemyFlaskChemicalRage', 'Chemical Rage', 'Alchemy Flask (non in partita)', 'cura nel tempo', 'abilita'),
    ('Trig_PeltPrimalRage', 'Primal Rage', 'Pelt (non in partita)', 'cura nel tempo', 'abilita'),
    ('Trig_Heal_Adjust', 'Interno al sistema (NextHealSource nullo)', '-', 'interno', 'non contata'),
]


def classifica(fn):
    for pref, fonte, cl, tipo, cat in CLASSIFICA:
        if fn.startswith(pref):
            return fonte, cl, tipo, cat
    return '?', '?', '?', '?'


def evidenze_codice():
    t = open(JASS, encoding='latin-1').read()
    funcs = {m.group(1): m.group(0) for m in re.finditer(r'function\s+(\w+)\s+takes.*?endfunction', t, re.S)}
    rows = []
    # a) contatore e sue condizioni
    for fn in ('Trig_HealMeterCount_Conditions', 'Trig_HealMeterCount_Actions', 'InitTrig_HealMeterCount',
               'Trig_Heal_Check_Loop_Actions', 'Trig_Heal_Unit_Actions', 'Trig_Heal_Unit_Func009C',
               'Trig_Heal_Configuration_Actions'):
        body = funcs.get(fn, 'NON TROVATA')
        rows.append({'funzione_jass': fn, 'ruolo_nel_sistema': {
            'Trig_HealMeterCount_Conditions': 'condizione del contatore: sorgente eroe e quantita <= 10000',
            'Trig_HealMeterCount_Actions': 'somma udg_heal_amount a HealCountTotal del proprietario di udg_heal_source',
            'InitTrig_HealMeterCount': 'il contatore scatta su udg_HealEvent == 1',
            'Trig_Heal_Check_Loop_Actions': 'rilevamento per differenza di vita ogni 0,05 s: NON imposta udg_heal_source (resta null)',
            'Trig_Heal_Unit_Actions': 'cura via trigger: applica NextHealAmount, misura la vita realmente guadagnata, imposta heal_source=NextHealSource',
            'Trig_Heal_Unit_Func009C': 'conta solo se la vita guadagnata >= heal_diff (1 HP per le cure via trigger)',
            'Trig_Heal_Configuration_Actions': 'soglie: HEAL_THRESHOLD 25, intervallo 0,05 s, REGEN_THRESHOLD 5',
        }[fn], 'sorgente_cura': '', 'quantita_cura': '', 'fonte': '', 'classe_o_oggetto': '', 'tipo': '',
            'categoria': '', 'estratto_codice': re.sub(r'\s+', ' ', body)[:600]})
    # b) ogni chiamata a Heal_Unit
    for fn, body in funcs.items():
        if fn in ('main', 'InitCustomTriggers'):
            continue
        for m in re.finditer(r'TriggerExecute\(gg_trg_Heal_Unit\)', body):
            pre = body[:m.start()]
            src = re.findall(r'set udg_NextHealSource=([^\n]*)', pre)
            amt = re.findall(r'set udg_NextHealAmount=([^\n]*)', pre)
            fonte, cl, tipo, cat = classifica(fn)
            rows.append({'funzione_jass': fn, 'ruolo_nel_sistema': 'chiama Heal_Unit',
                         'sorgente_cura': src[-1] if src else '(non impostata -> null)',
                         'quantita_cura': amt[-1] if amt else '(cura gia avvenuta; misura differenza)',
                         'fonte': fonte, 'classe_o_oggetto': cl, 'tipo': tipo, 'categoria': cat,
                         'estratto_codice': ''})
    # c) scritture dirette su HealCountTotal fuori dal contatore
    for fn, body in funcs.items():
        if fn in ('main', 'InitGlobals', 'Trig_HealMeterCount_Actions'):
            continue
        if re.search(r'set udg_HealCountTotal\[[^\]]*\]=\(udg_HealCountTotal', body):
            i = body.find('set udg_HealCountTotal')
            rows.append({'funzione_jass': fn, 'ruolo_nel_sistema': 'scrive direttamente HealCountTotal',
                         'sorgente_cura': 'proprietario di udg_DamageEventTarget (il bersaglio protetto)',
                         'quantita_cura': 'udg_DamageEventAmount (danno assorbito dallo scudo)',
                         'fonte': 'Scudo assorbente (Abil_AbsorbAmount)', 'classe_o_oggetto': 'Pelt (non in partita)',
                         'tipo': 'scudo', 'categoria': 'abilita (non in partita)',
                         'estratto_codice': re.sub(r'\s+', ' ', body[max(0, i - 250):i + 250])})
    # verifica: udg_heal_source viene assegnata solo dentro Heal_Unit
    assegn = [fn for fn, b in funcs.items() if 'set udg_heal_source=' in b and fn not in ('main',)]
    rows.append({'funzione_jass': 'VERIFICA', 'ruolo_nel_sistema':
                 'funzioni che assegnano udg_heal_source: ' + ', '.join(sorted(assegn)) +
                 ' (valore iniziale in InitGlobals: null)', 'estratto_codice':
                 re.search(r'unit udg_heal_source=\w+', t).group(0)})
    cols = ['funzione_jass', 'ruolo_nel_sistema', 'sorgente_cura', 'quantita_cura', 'fonte', 'classe_o_oggetto',
            'tipo', 'categoria', 'estratto_codice']
    write('evidenze_codice_cure.csv', cols, rows)
    return rows


# --------------------------------------------------------------------------------------------
# 2. Catalogo delle fonti di cura per classe
# --------------------------------------------------------------------------------------------
# (classe, fonte, id, order_hex, tipo, categoria, conta_nella_mappa, attribuita_a, formula, note)
CATALOGO = [
    ('Druid Staff', 'Rejuvenation', 'A05R', '0x0D00C0', 'cura nel tempo', 'abilita', 'si', 'lanciatore',
     '15 x Int in 24 s su alleato (+3 x Int istantanei con I093/I079)', 'su nemico diventa Wither (danno)'),
    ('Druid Staff', 'Innervate', 'A060', '0x0D00C1', 'cura nel tempo (condizionale)', 'abilita', 'si', 'lanciatore',
     'mana; ai livelli 3-4 applica anche Rejuvenation 30 x Int in 24 s', ''),
    ('Druid Staff', 'Tranquility', 'A05Y', '0x0D00D8', 'cura ad area nel tempo', 'abilita', 'si', 'lanciatore',
     '2,25 x Int per impulso a ogni alleato (tooltip: 45 x Int in 10 s)', ''),
    ('Druid Staff', 'Thorns Aura', '', '', 'aura', 'esclusa: aura', 'no', '-', 'nessuna cura', ''),
    ('War Drums', 'Motivate', 'A0AJ', '(passiva)', 'cura nel tempo', 'abilita', 'si', 'lanciatore',
     '0,2-0,8 x Agi al secondo per 10 s a 1 alleato entro 700, innescata dagli attacchi', 'nessun comando nel replay'),
    ('War Drums', 'Rally', 'A09Z', '0x0D0084', 'potenziamento di cura', 'abilita', 'indiretta', 'lanciatore',
     '+100% alla cura di Motivate mentre e attiva', ''),
    ('War Drums', 'War Drums (Bestow Aura)', 'A0A0-A0AA', '0x0D0216/007C/026C/00D1/0065/008E/024C', 'cura ad area',
     'abilita', 'si', 'lanciatore', '9 x Agi ad alleati entro 600', 'conferisce anche un\'aura (es. Vampiric)'),
    ('Runeblade', 'Death Coil', 'A0HJ', '0x0D00FE', 'cura diretta', 'abilita', 'si', 'lanciatore',
     '6 / 9 / 12 x Str su alleato', 'su nemico fa danno: il replay non distingue il bersaglio'),
    ('Runeblade', 'Death Pact', 'A0HK', '0x0D00FF', 'auto-cura diretta', 'abilita', 'si', 'lanciatore',
     '36 x Str su se stesso', ''),
    ('Runeblade', 'Cannibalize', 'A0HY', '0x0D00DC', 'auto-cura nel tempo', 'abilita', 'si', 'lanciatore',
     '4% HP max ogni 0,5 s', 'mai usata nel replay'),
    ('Runeblade', 'Unholy Presence', 'A0HM', '', 'aura', 'esclusa: aura', 'no', '-', 'nessuna cura', ''),
    ('Claws', 'Rock Shield (slot Healing Wave)', 'A0G6', '0x0D00C0', 'cura diretta', 'abilita', 'si', 'lanciatore',
     '12 o 24 x Agi + 100 armatura', 'nel catalogo del replay compare come "Healing Wave"'),
    ('Claws', 'Mana Tide Totem', 'A01J', '0x0D008D', 'cura ad area nel tempo (condizionale)', 'abilita', 'si',
     'lanciatore', 'mana; con condizione del trigger anche 2 x Agi ogni 2 s', ''),
    ('Double Blade', 'Demon Skin', 'A036', '0x0D0084', 'auto-cura nel tempo', 'abilita', 'si', 'lanciatore',
     '2% HP max al secondo durante il buff; +12% HP max istantaneo dal livello 3', ''),
    ('Double Blade', 'Vampiric Aura', 'S000', '(passiva)', 'aura / lifesteal', 'esclusa: aura', 'si',
     'chi attacca (non il portatore dell\'aura)', 'lifesteal 40% o 80% del danno fisico per il Double Blade, 8% per gli alleati',
     'aura: conta come cura di chi colpisce'),
    ('War Hammer', 'Avatar', 'A00Q', '0x0D0076', 'auto-cura nel tempo (condizionale)', 'abilita', 'si', 'lanciatore',
     '2% HP max al secondo, solo con Runed Bracers (I095) o I077', 'Runed Bracers comprati a 5431 s'),
    ('War Hammer', 'Might Aura', '', '', 'aura', 'esclusa: aura', 'no', '-', 'nessuna cura', ''),
    ('Pickaxe', 'Repair', '', '0x0D005F', 'riparazione strutture', 'esclusa', 'no', '-',
     'riparazione nativa di unita meccaniche: non passa da Heal_Unit', ''),
    ('Bow', '(nessuna abilita curativa)', '', '', '', '', '', '', '', 'Trueshot Aura non cura'),
    ('Wizard Staff', '(nessuna abilita curativa)', '', '', '', '', '', '', '', 'Brilliance Aura non cura'),
    ('Naga Trident', '(nessuna abilita curativa)', '', '', '', '', '', '', '', 'Windward Aura non cura'),
    ('tutte', 'Rigenerazione % HP', 'Regeneration_Value', '(passiva)', 'rigenerazione', 'esclusa: rigenerazione',
     'si', 'se stesso', 'HP max x Regeneration_Value / 200 ogni 0,5 s; base 0,5 (0,25% HP/s), +1 Survival Treads, +1,5 Prayer Beads, ...',
     'gli eroi non hanno altra rigenerazione (uhpr=0, StrRegenBonus=0)'),
    ('tutte', 'Pozioni HP', 'I00P,I00Q,I00T,I00V,I00U,I00W,I07P', 'useslotN', 'pozione', 'esclusa: pozione', 'si',
     'se stesso', '15-40% HP max in 6-15 s (Wizard\'s Potion I00R: solo mana)', 'riutilizzabili, ricarica 40 s'),
    ('tutte', 'Lifesteal da oggetti/buff', 'I05X,I04X,B002,B027,A0AW', '(passiva)', 'lifesteal', 'esclusa: aura/lifesteal',
     'si', 'chi attacca', 'Mask of Death +20% sotto il 60% HP; Vampiric Aura 8%; Hunger 50%', ''),
    ('tutte', 'Heartstone', 'I096,I0AQ', '(passiva)', 'oggetto', 'esclusa: oggetto', 'si', 'se stesso',
     '4% HP max a ogni incantesimo lanciato', 'comprato da War Hammer (1274 s) e Runeblade (1811 s)'),
    ('tutte', 'Scepter of Healing', 'A0BJ', '0x0D005F', 'oggetto', 'esclusa: oggetto', 'si', 'chi lo usa',
     '30% HP max del bersaglio', 'non comprato in questa partita'),
    ('tutte', 'Cure native WC3 (fontana, abilita/oggetti senza trigger)', '', '', 'varie', 'non contata', 'no', '-',
     'rilevate solo da Heal_Check_Loop con sorgente null: scartate dal contatore', ''),
]


def catalogo():
    cols = ['classe', 'fonte', 'id_mappa', 'order_hex', 'tipo', 'categoria', 'contata_dalla_mappa', 'attribuita_a',
            'formula_dal_codice', 'note']
    write('catalogo_fonti_cura.csv', cols, [dict(zip(cols, c)) for c in CATALOGO])


# --------------------------------------------------------------------------------------------
# 3. Quote misurate (cumulative) e per challenge (stimate)
# --------------------------------------------------------------------------------------------
COLPI = {(r['screenshot'], r['classe']): r for r in load(p('data_analysis', 'v2', 'colpi', 'colpi_snapshot.csv'))}


def snapshot_series():
    rows = load(p('data_screenshots', 'multiboard_snapshots.csv'))
    rounds = {int(r['challenge']): r for r in load(p('data_screenshots', 'rounds.csv'))}
    # challenge k = snapshot 'post' con challenges_completed = k; 20 = boss (ultimo snapshot boss completo)
    by = defaultdict(dict)
    meta = {}
    for r in rows:
        if r['phase'] == 'post':
            k = int(r['challenges_completed'])
        elif r['screenshot'] == '031526_03':
            k = 20
        else:
            continue
        cl, _ = ROLES[r['player']]
        # 'tank' del modello = colpi presi dal solo EROE (al netto delle evocazioni, stima centrale di
        # analisi_colpi.py): rigenerazione, pozioni e lifesteal curano solo l'eroe, non le unita' evocate.
        # 'tank_tot' = colonna tank_pct della multiboard (colpi presi, evocazioni comprese).
        by[k][cl] = {'heal': float(r['heal_pct']), 'tank_tot': float(r['tank_pct']),
                     'tank': float(COLPI[(r['screenshot'], cl)]['colpi_quota_eroe_centrale'])}
        meta[k] = (r['screenshot'], int(r['game_time_s']))
    ks = sorted(by)
    # i colpi degli eroi si riportano a 100 tra i soli eroi, come le altre quote del modello
    for k in ks:
        tot = sum(v['tank'] for v in by[k].values()) or 1.0
        for v in by[k].values():
            v['tank'] = 100.0 * v['tank'] / tot
    # pesi: secondi impiegati (rounds.csv); se mancanti, tempo tra screenshot x rapporto mediano
    dt = {k: meta[k][1] - (meta[k - 1][1] if k - 1 in meta else 0) for k in ks}
    ratio = sorted(float(rounds[k]['clear_seconds']) / dt[k] for k in ks
                   if k in rounds and rounds[k]['clear_seconds'] not in ('', None) and k < 20)
    med = ratio[len(ratio) // 2]
    peso, fonte_peso = {}, {}
    for k in ks:
        cs = rounds.get(k, {}).get('clear_seconds', '')
        if cs and k < 20:
            peso[k], fonte_peso[k] = float(cs), 'clear_seconds'
        else:
            peso[k], fonte_peso[k] = dt[k] * med, f'tempo tra screenshot x {med:.2f}'
    return ks, by, meta, peso, fonte_peso, med


def per_challenge(ks, by, peso, col):
    """quota per challenge (stima): (S_k*W_k - S_{k-1}*W_{k-1}) / (W_k - W_{k-1}), negativi a 0, rinormalizzata."""
    W, cum = {}, 0.0
    for k in ks:
        cum += peso[k]
        W[k] = cum
    out, grezzi, negativi = {}, {}, 0
    for k in ks:
        raw = {}
        for c in CLASSI:
            s1 = by[k][c][col]
            s0 = by[k - 1][c][col] if k - 1 in by else 0.0
            w0 = W[k - 1] if k - 1 in W else 0.0
            raw[c] = (s1 * W[k] - s0 * w0) / (W[k] - w0)
        grezzi[k] = raw
        neg = {c: max(0.0, v) for c, v in raw.items()}
        negativi += sum(1 for v in raw.values() if v < 0)
        tot = sum(neg.values()) or 1.0
        out[k] = {c: 100.0 * v / tot for c, v in neg.items()}
    return out, grezzi, negativi


def stima_abilita(heal, tank, r):
    """heal, tank: dict classe->quota. Restituisce quota (su 100) delle cure da abilita stimate."""
    ab = {}
    for c in CLASSI:
        if c in CLASSI_RIFERIMENTO:
            ab[c] = 0.0
        else:
            ab[c] = max(0.0, heal[c] - r * tank[c])
    tot = sum(ab.values())
    return {c: (100.0 * v / tot if tot else 0.0) for c, v in ab.items()}, ab


def rapporti(heal, tank):
    sh = sum(heal[c] for c in CLASSI_RIFERIMENTO)
    st = sum(tank[c] for c in CLASSI_RIFERIMENTO)
    ind = [heal[c] / tank[c] for c in CLASSI_RIFERIMENTO if tank[c] >= 0.5]
    return (sh / st if st else 0.0), (min(ind) if ind else 0.0), (max(ind) if ind else 0.0)


# --------------------------------------------------------------------------------------------
# 4. Replay: comandi di abilita curative e uso pozioni
# --------------------------------------------------------------------------------------------
ABIL_CURA = {  # (classe, order_hex) -> (abilita, tipo)
    ('Druid Staff', '0x0D00C0'): ('Rejuvenation', 'cura nel tempo'),
    ('Druid Staff', '0x0D00C1'): ('Innervate', 'cura nel tempo (condizionale)'),
    ('Druid Staff', '0x0D00D8'): ('Tranquility', 'cura ad area nel tempo'),
    ('Claws', '0x0D00C0'): ('Rock Shield', 'cura diretta'),
    ('Claws', '0x0D008D'): ('Mana Tide Totem', 'cura ad area nel tempo (condizionale)'),
    ('Runeblade', '0x0D00FE'): ('Death Coil (alleato o nemico)', 'cura diretta'),
    ('Runeblade', '0x0D00FF'): ('Death Pact', 'auto-cura diretta'),
    ('Runeblade', '0x0D00DC'): ('Cannibalize', 'auto-cura nel tempo'),
    ('War Drums', '0x0D0084'): ('Rally', 'potenziamento di Motivate'),
    ('Double Blade', '0x0D0084'): ('Demon Skin', 'auto-cura nel tempo'),
    ('War Hammer', '0x0D0076'): ('Avatar', 'auto-cura nel tempo (condizionale)'),
}
for _o in ('0x0D0216', '0x0D007C', '0x0D026C', '0x0D00D1', '0x0D0065', '0x0D008E', '0x0D024C'):
    ABIL_CURA[('War Drums', _o)] = ('War Drums (Bestow Aura)', 'cura ad area')

POZIONI = {  # id -> (nome, frazione HP max, mana)
    'I00P': ("Gladiator's Potion", 0.25, 100), 'I00Q': ("Tank's Potion", 0.40, 0),
    'I00T': ('Jail Potion', 0.15, 50), 'I00R': ("Wizard's Potion", 0.0, 160),
    'I00V': ('Rejuvenation Potion', 0.25, 100), 'I00U': ('Stoneskin Potion', 0.40, 0),
    'I00W': ('Rage Potion', 0.25, 100), 'I07P': ("King's Potion", 0.25, 100),
}
# slot -> pozione, ricostruito: la pozione e l'unico acquisto compatibile, l'uso dello slot inizia
# dopo l'acquisto e gli intervalli tra usi sono quasi sempre >= 40 s (ricarica). Vedi uso_pozioni_slot.csv
SLOT_POZIONE = {
    'Bow': ('useslot3', 'I00W', 'alta'),
    'Double Blade': ('useslot5', 'I00Q', 'media'),
}
for _c in ('Druid Staff', 'Claws', 'Pickaxe', 'Wizard Staff', 'War Drums', 'War Hammer', 'Runeblade', 'Naga Trident'):
    SLOT_POZIONE[_c] = ('useslot3', 'I00R', 'alta')


def replay(ks, meta):
    acts = load(p('data_replay', 'actions_named.csv'))
    bounds = sorted((k, meta[k][1] * 1000) for k in ks if k < 20)
    edges = [(0, 0)] + bounds

    def seg(t):
        for (c0, t0), (c1, t1) in zip(edges, edges[1:]):
            if t0 <= t < t1:
                return c1
        return 20

    acquisto = {}  # (classe, item) -> primo acquisto ms
    for a in acts:
        if a['order'] in POZIONI and a['player'] in ROLES:
            key = (ROLES[a['player']][0], a['order'])
            acquisto.setdefault(key, int(a['game_time_ms']))
    cmd = defaultdict(int)          # (classe, ch, abilita, tipo) -> n
    pot = defaultdict(lambda: defaultdict(float))
    usi_slot = defaultdict(list)    # (classe, slot) -> tempi
    ultimo_uso = {}                 # (classe, slot) -> ultimo uso contato (ricarica 40 s)
    for a in acts:
        if a['player'] not in ROLES:
            continue
        cl = ROLES[a['player']][0]
        t = int(a['game_time_ms'])
        k = seg(t)
        o = a['order']
        if (cl, o) in ABIL_CURA and a['kind'].startswith('order'):
            ab, tipo = ABIL_CURA[(cl, o)]
            cmd[(cl, k, ab, tipo)] += 1
        if o.startswith('useslot'):
            usi_slot[(cl, o)].append(t)
            slot, item, _conf = SLOT_POZIONE.get(cl, (None, None, None))
            d = pot[(cl, k)]
            if o == slot and t >= acquisto.get((cl, item), 10 ** 12):
                nome, frac, mana = POZIONI[item]
                d['comandi_slot_pozione'] += 1
                if t - ultimo_uso.get((cl, o), -10 ** 9) < 40000:
                    continue  # comando ripetuto durante la ricarica: non e un nuovo uso
                ultimo_uso[(cl, o)] = t
                if frac > 0:
                    d['usi_pozione_cura'] += 1
                    d['cura_pozioni_nominale_hp_max'] += frac
                else:
                    d['usi_pozione_solo_mana'] += 1
            else:
                d['usi_slot_non_attribuiti'] += 1
    # evidenze slot
    ev = []
    for (cl, slot), ts in sorted(usi_slot.items()):
        ts.sort()
        gaps = [(b - a) / 1000 for a, b in zip(ts, ts[1:])]
        s, item, conf = SLOT_POZIONE.get(cl, (None, None, None))
        attrib = (slot == s)
        acq = acquisto.get((cl, item)) if attrib else None
        ev.append({'classe': cl, 'ruolo': RUOLO[cl], 'slot': slot, 'n_usi': len(ts),
                   'primo_uso_s': round(ts[0] / 1000), 'pozione_attribuita': (POZIONI[item][0] + f' ({item})') if attrib else '',
                   'acquisto_pozione_s': round(acq / 1000) if acq else '',
                   'usi_prima_acquisto': sum(1 for x in ts if acq and x < acq) if attrib else '',
                   'intervallo_min_s': round(min(gaps), 1) if gaps else '',
                   'quota_intervalli_almeno_40s': round(100 * sum(g >= 40 for g in gaps) / len(gaps), 1) if gaps else '',
                   'cura_hp_max_per_uso': POZIONI[item][1] if attrib else '',
                   'confidenza': conf if attrib else 'slot non attribuito (oggetto ignoto)'})
    write('uso_pozioni_slot.csv', list(ev[0].keys()), ev)
    return cmd, pot


# --------------------------------------------------------------------------------------------
def main():
    print('Evidenze dal codice...')
    evidenze_codice()
    catalogo()

    print('Quote dalla multiboard...')
    ks, by, meta, peso, fonte_peso, med = snapshot_series()
    heal_ch, heal_raw, neg_h = per_challenge(ks, by, peso, 'heal')
    tank_ch, tank_raw, neg_t = per_challenge(ks, by, peso, 'tank')
    rows = []
    for k in ks:
        for c in CLASSI:
            prev = by[k - 1][c] if k - 1 in by else {'heal': 0.0, 'tank': 0.0, 'tank_tot': 0.0}
            rows.append({'classe': c, 'ruolo': RUOLO[c], 'challenge': k if k < 20 else '20 (boss)',
                         'screenshot': meta[k][0], 'tempo_gioco_s': meta[k][1],
                         'peso_challenge_s': r1(peso[k], 0), 'fonte_peso': fonte_peso[k],
                         'cure_quota_cumulativa_misurata': by[k][c]['heal'],
                         'cure_variazione_quota_pp_misurata': r1(by[k][c]['heal'] - prev['heal']),
                         'cure_quota_challenge_grezza_stimata': r1(heal_raw[k][c]),
                         'cure_quota_challenge_stimata': r1(heal_ch[k][c]),
                         'colpi_quota_cumulativa_misurata': by[k][c]['tank_tot'],
                         'colpi_eroe_quota_tra_eroi_cumulativa_stimata': r1(by[k][c]['tank']),
                         'colpi_eroe_quota_tra_eroi_challenge_stimata': r1(tank_ch[k][c])})
    write('quota_cure_per_challenge.csv', list(rows[0].keys()), rows)

    print('Stima solo abilita...')
    stima = []
    for k in ks:
        hc = {c: by[k][c]['heal'] for c in CLASSI}
        tc = {c: by[k][c]['tank'] for c in CLASSI}
        r_c, r_lo, r_hi = rapporti(hc, tc)
        s_max, ab_max = stima_abilita(hc, tc, 0.0)
        s_cen, ab_cen = stima_abilita(hc, tc, r_c)
        s_min, ab_min = stima_abilita(hc, tc, r_hi)
        # per challenge: stesso modello sulle quote per challenge stimate, con r cumulativo
        hk = heal_ch[k]
        tk = tank_ch[k]
        k_max, _ = stima_abilita(hk, tk, 0.0)
        k_cen, _ = stima_abilita(hk, tk, r_c)
        k_min, _ = stima_abilita(hk, tk, r_hi)
        quota_non_ab_cen = sum(hc[c] - ab_cen[c] for c in CLASSI)
        for c in CLASSI:
            stima.append({
                'classe': c, 'ruolo': RUOLO[c], 'challenge': k if k < 20 else '20 (boss)',
                'ha_cure_da_abilita': 'no' if c in CLASSI_SENZA_CURE_ABILITA else
                ('solo con Runed Bracers (da 5431 s)' if c == 'War Hammer' else 'si'),
                'cure_quota_cumulativa_misurata': hc[c],
                'colpi_quota_cumulativa_misurata': by[k][c]['tank_tot'],
                'colpi_eroe_quota_tra_eroi_stimata': r1(tc[c]),
                'r_cure_su_colpi_eroe_riferimento': round(r_c, 3), 'r_min_individuale': round(r_lo, 3),
                'r_max_individuale': round(r_hi, 3),
                'cure_abilita_stimate_pp_centrale': r1(ab_cen[c]),
                'cure_non_abilita_stimate_pp_centrale': r1(hc[c] - ab_cen[c]),
                'frazione_proprie_cure_da_abilita_a': r1(100 * ab_max[c] / hc[c]) if hc[c] else '',
                'frazione_proprie_cure_da_abilita_b': r1(100 * ab_cen[c] / hc[c]) if hc[c] else '',
                'frazione_proprie_cure_da_abilita_c': r1(100 * ab_min[c] / hc[c]) if hc[c] else '',
                'quota_cure_non_abilita_team_stimata_b': r1(quota_non_ab_cen),
                'quota_solo_abilita_cumulativa_a': r1(s_max[c]),
                'quota_solo_abilita_cumulativa_b': r1(s_cen[c]),
                'quota_solo_abilita_cumulativa_c': r1(s_min[c]),
                'quota_solo_abilita_challenge_a': r1(k_max[c]),
                'quota_solo_abilita_challenge_b': r1(k_cen[c]),
                'quota_solo_abilita_challenge_c': r1(k_min[c]),
            })
    write('stima_cure_solo_abilita.csv', list(stima[0].keys()), stima)

    print('Replay...')
    cmd, pot = replay(ks, meta)
    det = [{'classe': c, 'ruolo': RUOLO[c], 'challenge': k if k < 20 else '20 (boss)', 'abilita': ab,
            'tipo': tipo, 'n_comandi': n} for (c, k, ab, tipo), n in sorted(cmd.items())]
    write('comandi_abilita_curative.csv', ['classe', 'ruolo', 'challenge', 'abilita', 'tipo', 'n_comandi'], det)
    ev = []
    for k in ks:
        for c in CLASSI:
            n = sum(v for (cc, kk, _a, _t), v in cmd.items() if cc == c and kk == k)
            d = pot[(c, k)]
            ev.append({'classe': c, 'ruolo': RUOLO[c], 'challenge': k if k < 20 else '20 (boss)',
                       'comandi_abilita_curative': n,
                       'comandi_slot_pozione': int(d['comandi_slot_pozione']),
                       'usi_pozione_cura': int(d['usi_pozione_cura']),
                       'usi_pozione_solo_mana': int(d['usi_pozione_solo_mana']),
                       'usi_slot_non_attribuiti': int(d['usi_slot_non_attribuiti']),
                       'cura_pozioni_nominale_hp_max': r1(d['cura_pozioni_nominale_hp_max'], 2)})
    write('eventi_cura_replay.csv', list(ev[0].keys()), ev)

    # riepilogo per classe (snapshot boss = cumulativo finale completo)
    fin = {s['classe']: s for s in stima if s['challenge'] == '20 (boss)'}
    rie = []
    for c in sorted(CLASSI, key=lambda c: -fin[c]['cure_quota_cumulativa_misurata']):
        tot_cmd = sum(e['comandi_abilita_curative'] for e in ev if e['classe'] == c)
        dett = defaultdict(int)
        for (cc, _k, ab, _t), n in cmd.items():
            if cc == c:
                dett[ab] += n
        rie.append({'classe': c, 'ruolo': RUOLO[c],
                    'cure_quota_finale_misurata': fin[c]['cure_quota_cumulativa_misurata'],
                    'colpi_quota_finale_misurata': fin[c]['colpi_quota_cumulativa_misurata'],
                    'colpi_eroe_quota_tra_eroi_finale_stimata': fin[c]['colpi_eroe_quota_tra_eroi_stimata'],
                    'ha_cure_da_abilita': fin[c]['ha_cure_da_abilita'],
                    'frazione_proprie_cure_da_abilita_b': fin[c]['frazione_proprie_cure_da_abilita_b'],
                    'quota_solo_abilita_stimata_a': fin[c]['quota_solo_abilita_cumulativa_a'],
                    'quota_solo_abilita_stimata_b': fin[c]['quota_solo_abilita_cumulativa_b'],
                    'quota_solo_abilita_stimata_c': fin[c]['quota_solo_abilita_cumulativa_c'],
                    'comandi_abilita_curative': tot_cmd,
                    'dettaglio_comandi': '; '.join(f'{a}={n}' for a, n in sorted(dett.items(), key=lambda x: -x[1])),
                    'usi_pozione_cura': sum(e['usi_pozione_cura'] for e in ev if e['classe'] == c),
                    'usi_pozione_solo_mana': sum(e['usi_pozione_solo_mana'] for e in ev if e['classe'] == c),
                    'cura_pozioni_nominale_hp_max': r1(sum(float(e['cura_pozioni_nominale_hp_max'] or 0)
                                                           for e in ev if e['classe'] == c), 2)})
    write('riepilogo_classi.csv', list(rie[0].keys()), rie)
    print(f'Valori negativi azzerati nelle quote per challenge: cure {neg_h}, colpi eroe {neg_t}; rapporto mediano pesi {med:.2f}')
    for x in rie:
        print(x['classe'], x['cure_quota_finale_misurata'], 'solo abilita a/b/c', x['quota_solo_abilita_stimata_a'], x['quota_solo_abilita_stimata_b'], x['quota_solo_abilita_stimata_c'])


if __name__ == '__main__':
    main()
