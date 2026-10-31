# Analisi Orc Gladiators Revenge 1.29f – replay del 15/03/2026

Partita: WC3 1.24 (build 6059), 10 giocatori in co-op, 20 challenge più il boss finale, durata 1h44m.
Obiettivo: capire chi fa pochi danni o poche cure, chi tanka, chi si muove molto, per migliorare la strategia del gruppo.

## Struttura delle cartelle

| Cartella | Contenuto |
|---|---|
| `replay_originali/` | File originali della partita: replay `orcgladiatorsbutei.w3g`, archivio `files orc gladiators.rar` e, in `screenshots/`, i 23 screenshot `.tga` della multiboard. |
| `data_replay/` | Dati estratti dal replay (solo i **comandi** dei giocatori). |
| `data_screenshots/` | Multiboard "Gladiator Statistics" trascritta a mano dagli screenshot (danni, cure, tank). |
| `data_map/` | Dati letti dal file della mappa: abilità e classi degli eroi. |
| `data_analysis/` | Dataset finali, già pronti per grafici e analisi (li usa la dashboard). |
| `dashboard/` | Report: `index.html` si apre con doppio click; `artifact/` contiene i file della dashboard online. |
| `presentazione/` | Presentazione dei risultati (12 slide): `presentazione.html` si apre con doppio click (rigenerabile con `python build_presentazione.py`); `sorgente/` contiene i file delle slide. Versione online, esportabile in PDF/PowerPoint: https://claude.ai/artifact/TZPQS75DakUAXvXtn5jU9d |
| (cartella principale) | Script Python e `order_ids.csv`. |

Dashboard online: https://claude.ai/artifact/Dhe1AzMmSoEBYaWzMrudtL

## Rigenerare tutto

Da eseguire nella cartella principale, in quest'ordine:

```
python w3g_parser.py replay_originali/orcgladiatorsbutei.w3g data_replay
python build_multiboard.py data_screenshots
python summarize_replay.py
python build_ability_map.py <cartella_file_mappa> <cartella_file_gioco>
python analysis.py
python build_standalone.py
```

Analisi v2 (per classe e ruolo, senza nomi dei giocatori), dopo i passi sopra:

```
python extract_map.py "C:/Program Files (x86)/Warcraft III/Maps/Download/Orc Gladiators Revenge 1.29fc.w3x"
python analisi_classi_ruoli.py
python analisi_cure.py
python analisi_wave.py
python analisi_abilita_mana.py
python aggrega.py
```

| Script | Cosa fa | Output |
|---|---|---|
| `w3g_parser.py` | Legge il replay `.w3g`. | `data_replay/`: `actions.csv`, `players.csv`, `chat.csv`, `leaves.csv` |
| `build_multiboard.py` | Contiene i valori della multiboard trascritti a mano e li salva. | `data_screenshots/`: `multiboard_snapshots.csv`, `rounds.csv`, `stat_choices.csv` |
| `summarize_replay.py` | Aggrega le azioni per giocatore e per challenge. I confini tra le challenge vengono dagli orari degli screenshot. | `data_replay/player_summary.csv`, `player_round.csv` |
| `build_ability_map.py` | Traduce i codici degli ordini (`0x0D....`) in nomi di abilità e oggetti della mappa. | `data_map/ability_catalog.csv`, `classes.csv`; `data_replay/actions_named.csv`, `player_abilities.csv` |
| `analysis.py` | Unisce replay, screenshot e mappa nei dataset finali. | `data_analysis/*.csv` |
| `build_standalone.py` | Genera il report offline con i CSV incorporati. | `dashboard/index.html` |

Script di supporto (non si lanciano direttamente):
- `mpq.py`: lettore degli archivi MPQ (il formato di `.w3x` e `.mpq`).
- `objdata.py`: parser dei dati della mappa (`war3map.w3a/.w3u/.w3t`) e dei testi `.wts`.
- `order_ids_from_game.py`: ricava da `game.dll` la tabella nome ordine → order id (`order_ids.csv`). Si esegue una volta sola:
  `python order_ids_from_game.py "C:/Program Files (x86)/Warcraft III/game.dll" order_ids.csv`

Per `build_ability_map.py` servono:
- `<cartella_file_mappa>`: i file `war3map.wts`, `war3map.w3a`, `war3map.w3u` e `war3map.w3t` estratti (con `mpq.py`) da
  `C:\Program Files (x86)\Warcraft III\Maps\Download\Orc Gladiators Revenge 1.29fc.w3x`;
- `<cartella_file_gioco>`: i file `*AbilityFunc.txt` del gioco, nominati `war3.mpq_*.txt`, `War3x.mpq_*.txt` e `War3Patch.mpq_*.txt`.

Questi file estratti non sono salvati nel progetto. Per rilanciare lo script vanno estratti di nuovo. Gli altri passi non ne hanno bisogno.

## Dettaglio dei dati

### data_replay/ (dal replay)
- `actions.csv`: 60.156 azioni. `game_time_ms` è il tempo di gioco al netto delle pause e coincide con l'orologio del replay.
  `order`: `smart` = click destro; `0x0D....` = abilità (order id); `I0..` = oggetti; `useslotN` = uso dell'oggetto nello slot N.
- `actions_named.csv`: come `actions.csv`, con in più la colonna `ability_name`.
- `player_summary.csv`: per giocatore: APM, click destri a terra (movimento) e su unità, hold, abilità, oggetti, comandi -loan/-borrow, "distanza" dei comandi di movimento, abilità più usate, codice eroe.
- `player_round.csv`: le stesse metriche, divise per challenge.
- `player_abilities.csv`: quante volte ogni giocatore ha usato ogni abilità (con il nome).
- `chat.csv`, `leaves.csv`, `players.csv`.

### data_screenshots/ (multiboard trascritta a mano)
- `multiboard_snapshots.csv`: una riga per giocatore per screenshot: livello, %HP, mana, **% danni, % danni al boss, % cure, % danni subiti (tank)**, oro.
  Le percentuali sono **cumulative** dall'inizio della partita e sono quote del totale del team: ogni colonna somma a circa 100 (verificato).
  `challenges_completed` = challenge appena completate. Le righe `boss`/`sconfitta` si riferiscono al boss finale, durante e alla fine.
- `rounds.csv`: per challenge: ondata, secondi impiegati, voto, migliori del round (danni, tank, boss, cure), oro.
- `stat_choices.csv`: ricompense scelte dopo le challenge 12 e 19.

### data_map/ (dalla mappa)
- `ability_catalog.csv`: 324 abilità e oggetti con nome, tooltip, hotkey e order id.
- `classes.csv`: per giocatore: eroe scelto, classe d'arma e abilità.

### data_analysis/ (dataset finali)
- `profilo_giocatori.csv`: una riga per giocatore: classe, arma, quote finali di danni, boss, cure e tank, APM, abilità e click al minuto, oggetti, oro, round sotto il 20% di HP, premi, abilità principale.
- `andamento_round.csv`: giocatore × challenge: danni, boss, cure, tank, oro, HP a fine round, livello.
- `attivita_round.csv`: giocatore × challenge: APM e abilità usate.
- `round.csv`: una riga per challenge: ondata, secondi, voto, eroi sotto il 20% di HP, attività del team, migliori del round.
- `abilita.csv`: giocatore × abilità: numero di usi.

## Analisi v2: data_analysis/v2/

Tutti gli output sono per **classe** (nome dell'arma) e **ruolo**, mai per nome del giocatore (gli script lo verificano).
La corrispondenza giocatore → classe → ruolo è in `data_map/class_roles.csv`, unica fonte di verità: per cambiare un ruolo si modifica lì e si rilancia tutto.
`data_map/raw/` contiene i file estratti dalla mappa con `extract_map.py` (war3map.j, .w3a, .w3u, .w3t, .wts…).

Ruoli: Tank (War Hammer, Runeblade), Healer (Druid Staff), Support (War Drums), DPS mischia (Claws, Double Blade, Pickaxe), DPS distanza (Bow, Wizard Staff, Naga Trident).

| Cartella | Script | Contenuto |
|---|---|---|
| `classi_ruoli/` | `analisi_classi_ruoli.py` | Profilo, andamento e attività per classe e per ruolo; coerenza tra ruolo assegnato e comportamento. |
| `cure/` | `analisi_cure.py` | Cosa conta la mappa come "cura" (dal codice) e stima della quota da sole abilità (scenari a/b/c). |
| `wave/` | `analisi_wave.py` | Composizione delle wave dalla mappa, tipo (solo mischia / solo distanza / ibrida), sottoanalisi per tipo. |
| `abilita_mana/` | `analisi_abilita_mana.py` | Simulazione del mana (zone <20%, 20–80%, >80%) validata sugli screenshot; cast effettivi e tempo in cooldown. |
| `aggregato/` | `aggrega.py` | Tabelle uniche per le domande: `scheda_classi.csv`, `scheda_ruoli.csv`, `classe_challenge.csv`, `ruolo_challenge.csv`, `classe_tipo_wave.csv`, `ruolo_tipo_wave.csv`, `confronto_metodi_round.csv`, `dizionario_metriche.csv`. |

Ogni cartella ha un `NOTE.md` con metodo, colonne, risultati e limiti. `aggregato/dizionario_metriche.csv` dice per ogni metrica se è misurata o stimata e quanto è affidabile.

Avvertenze principali:
- La "% cure" della multiboard include pozioni, rigenerazione e lifesteal (Vampiric Aura): la quota "solo abilità" è una stima.
- La quota del singolo round è stimata per differenza tra quote cumulative (concorda con i premi del round in 59 casi su 64).
- La simulazione del mana è affidabile solo per Wizard Staff; non affidabile per War Drums, Double Blade, Bow e Naga Trident.
- Ogni classe è giocata da una sola persona: "classe" coincide con "quel giocatore" in questa partita.
- In `data_replay/actions_named.csv` alcuni nomi di abilità sono sbagliati: "Healing Wave" del Claws è Rock Shield (A0G6), "Volatile Concoction" del Pickaxe è Unstable Concoction (A0FS). Le analisi v2 usano i nomi corretti.

## Limiti
- Il replay non contiene danni né cure, solo i comandi. Danni e cure si conoscono solo dagli screenshot: 19 momenti più il boss finale.
- Manca il riepilogo della challenge 12, e mancano i secondi delle challenge 8 e 19.
- Per analizzare nuove partite servono il replay e uno screenshot della multiboard alla fine di ogni round.
