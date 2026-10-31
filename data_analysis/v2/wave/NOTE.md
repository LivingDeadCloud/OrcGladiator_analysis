# Analisi per tipo di wave (mischia / distanza / ibrida)

Script: `analisi_wave.py` (cartella principale; `python analisi_wave.py`). Tutti i file qui sono rigenerati dallo script,
tranne questa nota. Nessun nome di giocatore: solo `classe` (arma) e `ruolo`.

## 1. Metodo

### Composizione delle wave (war3map.j + w3u + SLK del gioco)
- Ogni challenge N ha un trigger `Preload_Wave_N` con **3 varianti** (solo la 18, 19 e 20 ne hanno una).
  La variante si sceglie con `udg_Modes_WaveModifier`. In chat, al secondo 15, il giocatore 1 scrive `-waves3`.
  Il trigger `Player_Commands` fissa allora `Modes_OldWaves=true` e `Modes_WaveModifier=3`, cioè la **variante 3 per tutte le wave**.
  Lo confermano i nomi trascritti in `rounds.csv`: le challenge 2-19 coincidono tutte con la terza variante.
  Questo dà anche la wave 1, illeggibile nello screenshot ("?"): è **Prisoners**.
- Quantità: `Spawn_Wave_N` crea `SpawnSequence[1..SpawnAmount]` in 3 punti di spawn (Est, Nord, Ovest) per ognuno dei 10 giocatori.
  Ogni posizione della sequenza vale quindi 30 unità. Il boss è `SpawnBoss[1]`.
  Le unità create con id letterale si aggiungono quando la loro condizione `PLAYINGPLAYERS>=k` è vera con 10 giocatori:
  - wave 18: 3 boss eroi più 3 Kodo Beast (elite);
  - wave 19: boss Warden più 3 Furious Ancient (elite);
  - wave 20: il Lord of the Arena, creato dal trigger del boss finale dopo i "minion".
- Gittata e tipo d'arma: si leggono i campi modificati nel `war3map.w3u` (`ua1r/ua2r`, `ua1w/ua2w`, `ua1t`, `uaen`, `ua1g`, `uhpm`).
  I campi non modificati vengono da `Units\UnitWeapons.slk` e `UnitBalance.slk` dell'unità base (`War3Patch.mpq`, sola lettura).
  Conta solo l'arma attiva (`weapsOn`) che colpisce bersagli `ground`. Se le armi sono due, vale quella con gittata maggiore.
  Esempi: la Doom Guard ha l'arma 2 solo contro gli alberi; la Furious Ancient ha l'arma 2 a gittata 5000.
- **Mischia/distanza di un'unità**: tipo d'arma `normal` = mischia (gittata 90-200).
  `missile`, `instant`, `msplash` = distanza (gittata 240-810).
  Due casi corti ma a proiettile, contati come distanza: Blasphemer (missile, 240) e Contraption (instant, 270).

### Classificazione della wave (soglia esplicita)
- Si guarda la **quota degli HP totali delle truppe** (truppe più elite, boss escluso):
  - **solo mischia**: almeno l'85% degli HP è di unità da mischia;
  - **solo distanza**: almeno l'85% degli HP è di unità a distanza;
  - **ibrida**: tutti gli altri casi.
- Si riporta anche la quota per numero di unità. Non cambia nessuna classe.
- **Il boss si classifica a parte** (`tipo_boss`). Gli HP dei boss eroi non sono stimabili: dipendono da livello, forza e ricerche `R0xx` scalate sul numero di giocatori.

### Stima della quota per round
Le % della multiboard sono cumulative: S_p(c) = X_p(c) / X(c). Il contributo del round si stima per differenza, con un proxy W(c) proporzionale al totale cumulato del team X(c):

A_p(c) = S_p(c)·W(c) − S_p(c−1)·W(c−1). I valori negativi diventano 0, poi la somma si rinormalizza a 100 per round.

- **Proxy principale (`*_quota_round_stimata`)**: W = somma cumulata degli HP delle truppe delle wave.
  Il danno del team in un round è circa uguale agli HP dei nemici uccisi.
  Per cure e colpi presi si assume che crescano allo stesso modo con la forza della wave.
- **Colpi presi**: la colonna "tank" della multiboard conta i colpi (non i danni) ed è comprensiva delle unità evocate (`colpi/NOTE.md`).
  `tank_*` = colpi della classe, evocazioni comprese; `colpi_eroe_*` = colpi del solo eroe: quota `tank` stimata del round meno la
  quota delle evocazioni prevista dal modello per quella challenge (scenario centrale), con l'eroe mai sotto il meno colpito tra le
  classi senza evocazioni.
  Il proxy cresce di circa 50 volte dalla wave 1 alla 19.
- **Proxy alternativo (`*_quota_round_tempo`)**: W = tempo di gioco cumulato allo screenshot.
  Suppone un ritmo costante e quindi esagera gli scarti nei round avanzati. Serve solo come controllo di robustezza.
- **`*_delta_quota_cum`**: variazione in punti della quota cumulativa, senza proxy. Indica solo la direzione: positivo vuol dire che nel round il giocatore ha fatto più della sua media fino a quel momento.
- Le quote sono arrotondate a 0,1. Un errore di ±0,05 punti diventa ±0,05 × `amplificazione_errore` sulla quota stimata:
  - circa 1 per la wave 1;
  - 3-5 per le wave 4-14;
  - circa 6 per le wave 15-20.

  Nei round avanzati quindi ±0,3 punti per giocatore sono rumore.
- La quota di un **ruolo** è la somma delle quote dei suoi giocatori: 3 DPS mischia, 3 DPS distanza, 2 Tank, 1 Healer, 1 Support.
  Le attività (APM, abilità/min, click di movimento/min) sono invece la media per giocatore.

### Altre metriche
- **Eroi con HP ≤ 20%**: dallo snapshot di fine round (`hp_pct ≤ 20`, stessa regola di `data_analysis/round.csv`). Le note di `rounds.csv` restano nella colonna `note_rounds`.
- **Attività**: da `data_replay/player_round.csv`.
  - APM;
  - abilità/min = `ability` / `segment_minutes`;
  - click di movimento/min = (`rclick_ground` + `move_cmd`) / `segment_minutes`.
- **Perimetro degli aggregati**: challenge 1-19. La 20 (boss finale, sconfitta, un giocatore uscito) compare in `round_per_tipo.csv` e `classe_round.csv` ma resta fuori dalle medie. Per la 20 si usa l'ultimo snapshot disponibile di ogni giocatore.
- **Voto**: A=1 … G=7 (più basso = meglio).

## 2. Classificazione delle 20 wave

| Ch | Ondata (variante 3) | Truppe | % HP mischia | Tipo | Boss | Etichetta gioco |
|---|---|---|---|---|---|---|
| 1 | Prisoners | 90 Rebellious Slave (mischia), 30 Blasphemer (missile 240) | 83% | ibrida (al limite) | Thomas the Deserter, mischia | – |
| 2 | Machines | 30 Clockwerk (mischia), 60 Contraption (instant 270) | 40% | ibrida | Rattletrap, distanza 270 | – |
| 3 | Combatants (Melee) | 60 Combatant | 100% | mischia | Instructor Mathos, mischia | Melee ✓ |
| 4 | Voidwalkers (Ranged) | 30 Voidwalker (330) | 0% | distanza | Envoy Blackstar, **mischia** | Ranged ✓ |
| 5 | Sasquatches (Melee) | 60 Sasquatch Fighter | 100% | mischia | Rendclaw the Horrid, mischia | Melee ✓ |
| 6 | Boars | 60 Swine (mischia), 30 Quillbeast (390) | 58% | ibrida | Needler, distanza 390 | – |
| 7 | Goblins | 60 Goblin Shredder, 60 Goblin Sappers (420) | 60% | ibrida | Big Betty, distanza 630 | – |
| 8 | Mur'guls | 30 Reaver, 30 Snarecaster (450), 30 Bloodgill (450) | 41% | ibrida | Tidecaller Rinx, distanza 450 | – |
| 9 | Water Elementals (Ranged) | 60 Water Elemental (480) | 0% | distanza | Paragon Aquarius, distanza | Ranged ✓ (*) |
| 10 | Mammoths (Melee) | 30 Mammoth | 100% | mischia | Mammoth Patriarch, mischia | Melee ✓ |
| 11 | Nether Drakes (Ranged) | 30 Nether Drake, 30 Void Drake (540) | 0% | distanza | Anomaly Eraxis, distanza | Ranged ✓ |
| 12 | Giant Spiders | 60 Giant Stalker (mischia), 30 Giant Spitter (570) | 67% | ibrida | The Giant Stalker, distanza 570 | – |
| 13 | Revenants | 30 Death (mischia), 90 Fire/Ice/Lightning (600) | 31% | ibrida | Dethacus, mischia | – |
| 14 | Faceless Ones | 30 Faceless One (mischia), 60 Twisted One (630) | 34% | ibrida | The Apostle, mischia | – |
| 15 | War Golems (Melee) | 60 War Golem | 100% | mischia | Greasebeard's Magnum Opus, mischia | Melee ✓ |
| 16 | Salamanders (Ranged) | 30 Salamander (690) | 0% | distanza | Cinderspine, distanza | Ranged ✓ |
| 17 | Greater Demons (Melee) | 30 Doom Guard, 30 Infernal | 100% | mischia | Annihilus, **distanza 720** | Melee ✓ |
| 18 | Enslaved Orcs | 30 Grunt, 30 Raider (mischia), 30 Shaman (750), 3 Kodo (750) | 72% | ibrida | 3 boss: Blademaster e Tauren (mischia), Far Seer (distanza) | – |
| 19 | Night Elf Hunters | 60 Hunter (mischia), 60 Hunter (780), 3 Furious Ancient (5000) | 53% | ibrida | Anaya Orcslayer, mischia | – |
| 20 | Arena Organisers | 30 Jailer (mischia), 30 Containment Officer (405), 30 Arena Sniper (810) + Lord of the Arena | 40% | ibrida | Lord of the Arena, mischia | – |

(*) Nella mappa il nome è "Water Elementals (Ranged)". In `rounds.csv` manca il suffisso: è un limite della trascrizione, non una discrepanza.

**Confronto con le etichette del gioco**:
- Nessuna discrepanza. Tutte le 10 wave etichettate (Melee) o (Ranged) sono pure al 100% secondo i dati delle unità.
- Tutte le wave senza etichetta risultano ibride.
- La wave 1 è al limite (83% mischia, 75% per numero): con una soglia all'80% sarebbe "mischia".

**Boss diverso dalle truppe**:
- wave 4 (truppe a distanza, boss da mischia);
- wave 17 (truppe da mischia, boss a distanza).

**Conteggi (challenge 1-19)**:
- mischia n=5 (3, 5, 10, 15, 17);
- distanza n=4 (4, 9, 11, 16);
- ibrida n=10 (1, 2, 6, 7, 8, 12, 13, 14, 18, 19).

La 20 è ibrida.

## 3. File e colonne

| File | Contenuto |
|---|---|
| `wave_composizione.csv` | Una riga per unità di ogni wave: `challenge, ondata, variante, n_varianti, categoria` (truppa/elite/boss), `unita_id, id_base, nome_unita, nome_proprio` (nome del boss), `quantita, hp_base, hp_totale` (vuoti per i boss), `armi_attive` (weapsOn), `arma_usata, gittata, tipo_arma, tipo_attacco, mischia_distanza, fonte` (campi presi dal w3u o dallo SLK base). |
| `wave_tipo.csv` | Una riga per challenge: `ondata, ondata_rounds_csv, variante, etichetta_gioco, n_unita, hp_totale_truppe, quota_unita_mischia, quota_hp_mischia, quota_hp_distanza, tipo_wave, boss, tipo_boss, confronto_etichetta, note`. |
| `round_per_tipo.csv` | Una riga per challenge: `tipo_wave, tipo_boss, secondi, voto, voto_num, eroi_hp_le20_snapshot, hp_truppe_wave, peso_round_hp` (% del totale cumulato dovuta al round), `amplificazione_errore, apm_team, click_movimento_min_team, note_rounds`. |
| `riepilogo_tipo.csv` | Una riga per tipo (più "tutte"), challenge 1-19: `n_wave, n_con_secondi`, secondi (media, mediana, min, max), `n_con_voto, voto_medio_num, voti`, eroi ≤20% HP (media, totale, round con almeno uno), APM e click di movimento del team. |
| `classe_round.csv` | Classe × challenge: `tipo_wave, ruolo, distanza_classe, hp_fine_round, sotto_20hp`. Per danni/boss/cure/tank: `*_quota_round_stimata` (proxy HP), `*_quota_round_tempo` (proxy tempo) e `*_delta_quota_cum`. Poi `minuti_segmento, apm, abilita_min, oggetti_min, click_movimento_min`. |
| `classe_per_tipo.csv` | Classe × tipo (challenge 1-19): `n_wave, n_giocatori`, media di ogni metrica; per le metriche principali anche `_min`, `_max` (tra le wave del tipo) e `_rapporto_vs_tutte` (media del tipo / media su tutte le 19 wave). `sotto_20hp` = numero di round chiusi con HP ≤ 20%. |
| `ruolo_per_tipo.csv` | Come sopra, per ruolo. Le quote sono sommate sui giocatori del ruolo; le attività sono la media per giocatore. |

## 4. Risultati principali (challenge 1-19; n piccoli, leggere come indizi)

### Livello di squadra (`riepilogo_tipo.csv`)

| Tipo | n | secondi media / mediana (min-max) | voti (media num.) | eroi ≤20% HP (totale; round con ≥1) | APM team | click mov./min |
|---|---|---|---|---|---|---|
| mischia | 5 | 149 / 161 (77-236) | A D D E A (3,0) | 13; 3 su 5 | 51,4 | 30,7 |
| distanza | 4 | 237 / 185 (150-428) | C G C E (4,5) | 6; 3 su 4 | 62,9 | 41,8 |
| ibrida | 10 (7 con tempo, 8 con voto) | 157 / 121 (61-432) | A A B D C C G D (3,1) | 11; 3 su 10 | 54,3 | 33,5 |

- Le wave a distanza sono andate peggio: più lente e con voto medio 4,5 contro 3,0. La media però dipende molto dalla wave 9 (Water Elementals: 428 s, G). Senza la 9 i secondi vanno a 173 e la differenza con la mischia (149) scende.
- Le wave da mischia mettono più eroi in rosso a fine round: 13 eroi ≤20% HP in 5 wave, ma quasi tutti in due wave. La 5 ne ha 4 a 17%, la 15 ne ha 8 al 12-20%.
- Contro le wave a distanza tutti cliccano di più: +22% di APM e +36% di click di movimento per giocatore rispetto alle wave da mischia. È coerente con l'inseguire i tiratori.

### Chi tanka contro le wave a distanza (`ruolo_per_tipo.csv`, `classe_per_tipo.csv`; quota dei colpi presi dall'eroe, proxy HP)

| | mischia (n=5) | distanza (n=4) | ibrida (n=10) |
|---|---|---|---|
| Eroi Tank (2 giocatori) | 34,0% | **28,5%** | 33,9% |
| Eroi DPS mischia (3) | 44,2% | **47,9%** | 41,5% |
| Eroi DPS distanza (3) | 3,0% | **4,5%** | 3,2% |
| Double Blade (DPS mischia) | 22,8% | **31,2%** (5-51 per wave) | 20,4% |
| Claws (DPS mischia) | 20,2% | 14,7% | 19,6% |
| Runeblade (Tank) | 19,1% | 18,9% | 16,4% |
| War Hammer (Tank) | 14,9% | **9,6%** | 17,5% |

Con le evocazioni (colonne `tank_*`) i DPS mischia salgono a 52,8 / 56,4 / 51,3% e i DPS distanza a 7,8 / 10,2 / 8,1%: la differenza sono lupi, torre ed elementale.

- Contro le wave a distanza i due Tank prendono meno colpi, soprattutto il War Hammer. Il carico passa al Double Blade: 51% nella wave 9, 34% nella 11 e 35% nella 16.
- Nella wave 4 invece i colpi li hanno presi Runeblade (31%) e Claws (19%, 25% con i lupi), con il Double Blade al 5%. Il tank "di fatto" contro i tiratori non è sempre lo stesso.
- Anche gli eroi DPS a distanza vengono colpiti un po' di più: Naga Trident 1,5% contro 0,7% (rapporto 1,7), Wizard Staff 1,6% contro 1,2% (con l'elementale 7,4% contro 6,0%). Restano comunque quote basse.
- Il ruolo Tank, invece, contro i tiratori fa più danni (18,0% contro 15,6%) e più cure: il Runeblade sale al 22,9% delle cure contro il 16,7%.

### Danni (proxy HP) per classe

Rapporto = media del tipo / media su tutte le 19 wave.

- **Meglio contro le wave a distanza**:
  - Pickaxe: 19,1% contro 16,1% in mischia (rapporto 1,23);
  - Wizard Staff: 14,8% contro 12,2% (1,18);
  - Runeblade: 9,4% contro 6,7% (1,29).
- **Peggio contro le wave a distanza**:
  - Claws: 15,2% contro 18,3% in mischia e 23,7% nelle ibride (rapporto 0,74);
  - Bow: 10,8% contro 13,9% (0,87);
  - Naga Trident: 11,3% contro 13,8% (0,89).
- **Per ruolo** le differenze sono piccole:
  - DPS mischia: 40,4% in mischia, 40,9% a distanza, 43,8% nelle ibride;
  - DPS distanza: 39,9%, 36,9%, 36,8%.

  Contro le wave da mischia i DPS a distanza fanno circa 3 punti in più.
- **Danni al boss**: contro le wave a distanza i DPS mischia salgono al 43,8% (39,1% in mischia) e i DPS distanza scendono al 32,6% (37,6%).
  Attenzione: il boss della wave 4 è da mischia e quello della 17 a distanza.
- **Cure**: l'Healer (Druid Staff) ha una quota stabile, 32,5-36,9%. Contro le wave a distanza la quota scende un po' perché cura di più il Runeblade.

### Attività per classe (rapporto rispetto alla media su tutte le wave)

- Contro le wave a distanza si muovono e cliccano molto di più:
  - Wizard Staff: APM ×1,37, click di movimento ×1,55;
  - Double Blade: ×1,42 e ×1,53;
  - Pickaxe: ×1,19 e ×1,35;
  - Runeblade: ×1,28 e ×1,40.
- Bow, Naga Trident e Druid Staff non cambiano (0,9-1,06).
- L'uso delle abilità/min è quasi costante tra i tipi (rapporti 0,86-1,21). Fanno eccezione War Drums (×1,36 a distanza, ma su valori di 1-1,5/min) e Runeblade (×1,21).

### Robustezza
Con il proxy "tempo" le direzioni principali restano:
- meno tank per War Hammer e più per Double Blade contro le wave a distanza;
- Pickaxe e Wizard Staff in su, Claws e Bow in giù.

Le ampiezze cambiano. Per esempio Claws nelle ibride vale 23,7% con il proxy HP e 32,9% con il tempo. Le differenze di 1-2 punti tra tipi non sono da considerare affidabili.

## 5. Limiti
- **n molto piccoli**:
  - 5 wave da mischia, 4 a distanza, 10 ibride;
  - mancano i secondi delle wave 8, 12 e 19 e il voto delle 8 e 12;
  - ogni classe è un solo giocatore, quindi "classe" = "quel giocatore".

  Nessuna differenza qui ha un test statistico che la sostenga. Le colonne `_min`/`_max` mostrano quanto variano le wave dello stesso tipo, spesso più della differenza tra tipi.
- **Confondimento con la fase di gioco**: livelli, oggetti e ruoli cambiano nel corso della partita. Per esempio il Double Blade tanka sempre di più (13% nella wave 3, 32% nella 15). Le wave pure stanno tra la 3 e la 17 per entrambi i tipi, ma restano poche.
- **Quote per round stimate**, non misurate:
  - i proxy (HP delle truppe, tempo) sono approssimazioni;
  - gli HP dei boss non entrano nel proxy;
  - gli HP delle truppe non tengono conto delle ricerche `R0xx` date ai nemici, scalate sul numero di giocatori, né delle unità evocate dai nemici;
  - l'arrotondamento a 0,1 delle quote cumulative pesa fino a circa ±0,3 punti nei round avanzati.
- **Tipo dell'unità**: viene dal tipo d'arma della mappa. Non considera incantesimi, aure o abilità dei nemici: per esempio i Blasphemer con Inner Fire, i caster, o il Collapse dei boss.
- **Snapshot HP**: un solo istante (fine round). Non dice quanto sono scesi gli HP durante il round né chi è morto.
- **Attività**: misurata sull'intero segmento tra due screenshot, che comprende anche la pausa e lo shopping tra un round e l'altro, non solo il combattimento.
- **Wave 20**: esclusa dagli aggregati (boss finale perso, un giocatore uscito alla fine).
