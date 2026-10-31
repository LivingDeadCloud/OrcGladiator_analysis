# Profilo per classe e per ruolo

Generato da `analisi_classi_ruoli.py` (cartella principale del progetto: `python analisi_classi_ruoli.py`).
Nessun file di questa cartella contiene nomi di giocatori: la chiave è sempre la `classe` (nome dell'arma), con il `ruolo`.
Lo script verifica l'anonimato alla fine (si ferma se trova un nome, anche l'abbreviazione usata in una nota di `rounds.csv`).

## Metodo

**Nota importante sul "tank".** La colonna `tank_pct` della multiboard conta i **colpi presi** (ogni evento di danno vale 1), non i
danni, e comprende i colpi presi dalle unità evocate del giocatore (lupi, Treant, elementali, torre, portali, compagno). Vedi
`colpi/NOTE.md`. In questa cartella:
- `tank` = colpi presi dalla classe, evocazioni comprese (misurato);
- `colpi_eroe` = colpi del solo eroe (stima, scenario centrale di `analisi_colpi.py`; forbice in `quota_colpi_eroe_min/_max`);
- `quota_colpi_evocazioni` = differenza tra i due.
La quota di colpi dell'eroe per round = quota `tank` stimata del round − quota delle evocazioni prevista dal modello per quella
challenge, con l'eroe mai sotto il meno colpito tra le classi senza evocazioni. La coerenza dei ruoli usa i colpi dell'eroe.

- **Classe e ruolo**: unica fonte `data_map/class_roles.csv` (giocatore → classe, ruolo, distanza). Ogni giocatore ha una classe diversa,
  quindi la conversione giocatore → classe è 1:1. Ruoli: Tank (2 classi), Healer (1), Support (1), DPS mischia (3), DPS distanza (3).
- **Quote cumulative** (danni, boss, cure, tank): da `multiboard_snapshots.csv`. Challenge 1–19 = snapshot `post` con
  `challenges_completed = c`. Challenge 20 (boss finale) = ultimo snapshot `boss` con tutti e 10 presenti (`031526_03`, 5987 s,
  boss ancora in corso: fase `boss_finale_parziale`). Il **profilo complessivo** usa lo snapshot dopo la challenge 19 (ultimo `post`);
  le quote a boss finale sono in colonne separate `*_boss_finale`.
- **Stima della quota del singolo round**. Con Q_c quota cumulativa dopo c e T_c totale cumulativo del team (sconosciuto),
  `quota_round = (Q_c − r·Q_{c−1}) / (1 − r)` con `r = T_{c−1}/T_c`. Serve un'ipotesi su r:
  1. ipotesi base: totale del team proporzionale al tempo di gioco (`r = t_{c−1}/t_c`, tempi degli snapshot);
  2. vincolo di non negatività: nessuna classe può "perdere" danni, quindi `r ≤ min Q_c/Q_{c−1}` (calcolato solo sulle classi con
     Q_{c−1} ≥ 2%, per non farsi guidare dall'arrotondamento a 0,1). Si usa `r = min(ipotesi tempo, vincolo)`: quando gli eroi diventano
     più forti il round "pesa" più del suo tempo. Il vincolo è attivo in 39 casi su 80 (challenge × metrica);
  3. negativi residui (rumore di arrotondamento) azzerati e quote rinormalizzate a 100.
  **Validazione**: la classe prima nella stima del round coincide con il premio "migliore del round" di `rounds.csv` in **63 casi su 68**
  (danni 15/17, tank 16/17, boss 17/17, cure 15/17), contro 47/68 se si usa la quota cumulativa. Dettaglio in `validazione_stima_round.csv`.
- **Aggregazione per ruolo**: le quote (cumulative e del round) sono **sommate** tra le classi del ruolo (quota del ruolo sul team);
  `*_per_classe` = somma / n classi, confrontabile con la quota "equa" del 10%. Le metriche di attività (APM, abilità/min, click, oro,
  HP, livello) sono **medie** tra le classi del ruolo. Premi e round sotto 20% HP sono **somme**.
- **Coerenza ruoli**: indice = quota / 10 (1 = quota equa). `ruolo_osservato` = metrica dominante tra danni, colpi dell'eroe e cure se il suo
  indice è ≥ 1, altrimenti "contributo sotto la media". Regole di segnalazione nella colonna `nota`: Tank il cui eroe prende meno colpi di una
  classe non-Tank; non-Tank il cui eroe prende più colpi di almeno un Tank; non-Healer con cure > 10%; Healer non primo per cure; DPS sotto il 10% di
  danni; non-DPS con più danni del DPS più basso. `coerente` = si / parziale (ruolo osservato giusto ma con segnalazioni) / no.
  Per il Support non esiste una metrica diretta (buff/aure non compaiono nella multiboard): `n.d.`.
- Attività da `data_replay/player_summary.csv` e `player_round.csv`; abilità da `data_replay/player_abilities.csv` (oggetti esclusi).

## File

| File | Righe | Colonne |
|---|---|---|
| `profilo_classi.csv` | 10 classi | classe, ruolo, distanza, tipo_mappa, attributo, quota_danni, quota_boss, quota_cure, quota_tank (colpi, dopo ch. 19), quota_colpi_eroe (+ _min, _max), quota_colpi_evocazioni, quota_danni_boss_finale, quota_tank_boss_finale, quota_colpi_eroe_boss_finale, quota_cure_boss_finale, minuti_giocati, apm, abilita_min, click_movimento_min, click_bersaglio_min, distanza_movimento_min, hold_position, oggetti_usati, acquisti, comandi_prestito, oro_medio_fine_round, oro_max, round_sotto_20hp, premi_danni, premi_tank, premi_boss, premi_cure, premi_totali, abilita_principale, abilita_principale_usi |
| `andamento_classi.csv` | classe × challenge 1–20 | classe, ruolo, challenge, fase, danni_cum, boss_cum, cure_cum, tank_cum, colpi_eroe_cum, danni_round_stima, boss_round_stima, cure_round_stima, tank_round_stima, colpi_eroe_round_stima, oro, hp_fine_round, livello |
| `attivita_classi.csv` | classe × challenge 1–20 | classe, ruolo, challenge, minuti, apm, abilita, abilita_min, click_movimento_min, oggetti_usati, acquisti |
| `abilita_classi.csv` | classe × abilità | classe, ruolo, abilita, usi, usi_min, quota_usi_classe |
| `round_classi.csv` | 20 challenge | challenge, ondata, secondi, voto, eroi_sotto_20hp, migliore_danni, migliore_danni_ruolo, migliore_tank, migliore_tank_ruolo, migliore_boss, migliore_boss_ruolo, migliore_cure, migliore_cure_ruolo, note (anonimizzate) |
| `profilo_ruoli.csv` | 5 ruoli | ruolo, n_classi, classi, quota_danni, quota_boss, quota_cure, quota_tank, quota_*_boss_finale, quota_danni_per_classe, quota_cure_per_classe, quota_tank_per_classe, premi_danni, premi_tank, premi_boss, premi_cure, premi_totali, round_sotto_20hp, apm_media, abilita_min_media, click_movimento_min_media, click_bersaglio_min_media, distanza_movimento_min_media, oggetti_usati_media, acquisti_media, oro_medio_fine_round_media |
| `andamento_ruoli.csv` | ruolo × challenge | ruolo, challenge, n_classi, danni_cum, boss_cum, cure_cum, tank_cum, danni_round_stima, boss_round_stima, cure_round_stima, tank_round_stima, hp_fine_round_medio, livello_medio, apm_medio, abilita_min_media, click_movimento_min_medio |
| `abilita_ruoli.csv` | ruolo × abilità | ruolo, abilita, usi, usi_min_per_classe, quota_usi_ruolo |
| `coerenza_ruoli.csv` | 10 classi | classe, ruolo, distanza, quota_/rango_ danni, tank, cure, boss, indice_danni, indice_tank, indice_cure, premi_danni, premi_tank, premi_cure, round_primo_danni_stima, round_primo_tank_stima, round_primo_cure_stima, ruolo_osservato, coerente, nota |
| `stima_round_diagnostica.csv` | challenge × metrica | challenge, metrica, secondi_snapshot, secondi_snapshot_prec, r_ipotesi_tempo, r_vincolo_non_negativita, r_usato, peso_round_stimato_pct, vincolo_attivo, classi_con_stima_negativa, somma_negativi_azzerati |
| `validazione_stima_round.csv` | challenge × premio | challenge, metrica, premiato, primo_stima_round, primo_cumulativo, concorda_stima, concorda_cumulativo |

Valori vuoti = dato non disponibile (es. secondi delle challenge 8, 12, 19; premi delle challenge 12, 19, 20; `eroi_sotto_20hp` per la 20).

## Risultati principali

1. **Gli eroi DPS mischia prendono più colpi dei Tank**, anche al netto delle evocazioni: colpi dell'eroe dopo la challenge 19
   DPS mischia 48,6% (3 classi, 16,2% a classe) contro Tank 26,5% (2 classi, 13,2% a classe). Con le evocazioni i DPS mischia arrivano
   al 56,5%. Double Blade è l'eroe più colpito (27,3%; 28,3% con i portali), Claws secondo (20,4%; 24,5% con i lupi); i due Tank sono
   3° e 4° (Runeblade 13,3% più 1,4% del compagno, War Hammer 13,2%). Le evocazioni di tutto il team prendono il 19% dei colpi.
2. **Il ruolo di tank si sposta nel tempo**: la quota di colpi del round degli eroi Tank scende dal 57% (challenge 1–2) a 1,5% (ch. 13)
   e 8,5% (ch. 14); nello stesso periodo gli eroi DPS mischia arrivano al 70% (ch. 14). L'eroe Double Blade prende il 35–50% dei colpi
   in ogni round dalla 9 alla 16 (tranne la 10: 26,9%) e prende 7 premi "migliore tank" (ch. 9–16), i Tank solo 5 in tutto (tutti entro
   la ch. 7). I premi della mappa contano i colpi evocazioni comprese.
3. **Danni: mischia sopra distanza, e in crescita**. Quota danni cumulativa DPS mischia da 32,1% (ch. 1) a 47,7% (ch. 19); DPS distanza
   stabile 36–40% (36,9% finale). Nella stima del round i DPS mischia superano il 55% nelle challenge 12, 13, 14, 16 e 17 (picco 67,4% nella 13). Ma è quasi tutto merito di
   Claws (26,9% dei danni, 1° anche per boss con 33,2%, 19 premi): Double Blade è al 5,5%, sotto entrambi i Tank.
4. **I DPS distanza sono equilibrati**: Wizard Staff 12,9%, Bow 12,7%, Naga Trident 11,3% di danni, tutti sopra la quota equa, eroi quasi
   mai colpiti (1–2%; il Wizard Staff arriva all'8% con l'elementale). Però hanno 13 round sotto il 20% di HP a fine round (Bow da solo 7), contro 8 dei DPS mischia.
5. **I Tank curano**: 29,2% delle cure del team (Runeblade 16,3%, War Hammer 12,9%), più dei DPS mischia (16,1%) e del Support (13,8%).
   Runeblade ha più cure che colpi presi: il comportamento osservato è da Healer secondario (anche premio "migliore cure" nella ch. 9).
6. **Healer coerente**: Druid Staff 36,0% delle cure, primo in 16 round su 17 con premio (e anche nella stima del round), quasi zero
   danni (1,0%).
7. **Support (War Drums)**: 13,8% delle cure, 1,7% danni, 1,0% colpi, APM più bassa del team (32,4) e 1,1 abilità/min. Nelle ultime
   challenge la sua quota di cure del round sale (21,7% ch. 19, 32,3% nel boss finale parziale).
8. **Attività**: APM media DPS mischia 72,8, Tank 65,4, Healer 56,4, DPS distanza 47,3, Support 32,4. Abilità/min più alte: Wizard
   Staff 9,07, Druid Staff 7,01, War Hammer 6,41; più basse War Drums 1,10 e Double Blade 1,75.
9. **Coerenza** (`coerenza_ruoli.csv`): coerenti Druid Staff, Pickaxe, Bow, Naga Trident, Wizard Staff; parziali War Hammer (tank ma
   superato da due DPS) e Claws (DPS il cui eroe prende il 20,4% dei colpi); **non coerenti Double Blade** (DPS mischia → comportamento da Tank, 5,5% danni)
   e **Runeblade** (Tank → comportamento da Healer).

## Limiti

- Le quote sono **relative al team**: non dicono quanti danni assoluti fa una classe, né se il team nel complesso fa abbastanza danni.
- La stima del round dipende dall'ipotesi sul totale del team (tempo + vincolo di non negatività). Quando il vincolo è attivo almeno una
  classe viene stimata a ~0 in quel round (stima "estrema" del peso del round). L'arrotondamento a 0,1 delle quote cumulative,
  moltiplicato per 1/(1−r), produce un errore fino a circa ±1–2 punti nelle challenge avanzate (peso del round 5–10%). La concordanza
  63/68 con i premi indica che l'ordine delle classi è affidabile, i valori puntuali meno.
- La metrica `boss` cresce solo nei round con boss/élite: la sua stima per round è poco significativa negli altri round.
- Challenge 1: lo snapshot (248 s) include il tempo prima dell'inizio dell'ondata.
- Challenge 20: lo snapshot usato (5987 s) è a metà del boss finale; lo snapshot di sconfitta (`040526_23`, 6158 s) ha solo 9 righe
  (manca la classe Double Blade, il cui giocatore esce) e le colonne sommano 94,9 / 93,0 / 92,9 / 71,2: non è usato per le quote.
- `ruolo_osservato` usa solo danni, tank e cure: buff, aure, controllo e utilità (tipici del Support) non sono misurabili.
- Ogni ruolo con più classi è dominato dalla classe più forte (es. DPS mischia = soprattutto Claws): leggere sempre anche `profilo_classi.csv`.
- Dati mancanti: riepilogo della challenge 12, premi della 19, secondi delle challenge 8 e 19 (lasciati vuoti).
