# Colpi presi: eroe e unità evocate

Generato da `analisi_colpi.py`, da lanciare nella cartella del progetto con `python analisi_colpi.py`. Usa solo la libreria standard.
Va lanciato dopo `analisi_abilita_mana.py` (usa le finestre di combattimento) e prima di `analisi_classi_ruoli.py`.
Nei file compaiono solo `classe` e `ruolo`, mai i nomi dei giocatori.

## 1. Cosa misura davvero la colonna "tank" della multiboard

**La colonna "tank" non è il danno subito: è il numero di colpi presi.** Le citazioni sono verificate dallo script e riportate in `evidenze_codice_colpi.csv`.

- **Il contatore.** `Trig_DamageMeterCount_Actions` esegue `DamageTakenCount[giocatore] += 1` a ogni evento di danno.
  Aggiunge 1 qualunque sia il danno: un colpo da 5 HP e uno da 500 valgono uguale.
  La percentuale in multiboard è `DamageTakenCount / totale del team`, e la variabile si chiama `StatisticsPercentageHits`.
  Anche il comando in partita lo chiama "hits tanked".
- **A chi va il colpo.** Va al **proprietario dell'unità colpita**, `GetOwningPlayer(udg_DamageEventTarget)`, quindi anche ai colpi presi da:
  - lupi, Treant ed elementali;
  - torri, portali e compagno.
  Il filtro "non illusione" (`Func002C`) vale solo per i danni fatti.
- **Il danno ricevuto in HP non è registrato da nessuna parte.** I danni *fatti* invece si sommano come importo (`DamageCountTotal += DamageEventAmount`).
  Quindi "danni" e "tank" nella multiboard non sono grandezze omogenee.

Conseguenze:

1. Le analisi precedenti chiamavano questa colonna "danni subiti". Da qui in avanti si chiama **colpi presi**.
2. Non si può verificare direttamente l'ipotesi "il Tank puro prende tanti colpi ma pochi danni (armatura alta), l'offtank pochi colpi ma tanti danni":
   la parte "danni" non esiste nei dati. Si può confrontare solo il numero di colpi.
3. I colpi delle unità evocate gonfiano il totale del padrone. Vanno scorporati (sezione 2).

## 2. Scorporo eroe / unità evocate (stima)

### Le evocazioni in questa partita (`evocazioni_parametri.csv`)

| Voce | Abilità | Lanci stimati | Unità per lancio | Durata | HP base |
|---|---|---|---|---|---|
| Lupi (Claws) | Feral Spirit | 136 | 2 lupi, poi 1 Spirit Guardian (dal secondo 2060) | 18 s | 100 |
| Treant (Druid Staff) | Force of Nature | 33 | 3 | 70 s | 100 |
| Elementale (Wizard Staff) | Water Elemental | 83 | 1 | 60 s | 100 |
| Portali (Double Blade) | Dimensional Gate | 5 | 2 (tipo "ward") | 60 s | 250 |
| Torre (Pickaxe) | Construct Tower | 25 | 1 | fino alla torre successiva | 250 |
| Compagno (Runeblade) | Undead Companion (Banshee) | 1 | 1 | permanente, dalla challenge 18 | – |

Come sono stati ricavati i valori:
- **Unità e durate:** dai trigger del `war3map.j`.
- **Lanci:** comandi nel replay, tenendo solo quelli distanti almeno il 90% del cooldown.
- **HP base:** dal `war3map.w3u`. Le evocazioni ricevono HP in più in base alle statistiche dell'eroe.

### Modello (`colpi_snapshot.csv`, `evocazioni_quota_modello_challenge.csv`)

- **Esposizione.** Per ogni challenge si contano i secondi-unità delle evocazioni dentro la finestra di combattimento (`E`) e i secondi-eroe (`H`).
- **Ipotesi.** Ogni unità evocata viene colpita **k volte** quanto un eroe medio, per secondo in campo:
  `quota evocazioni della classe = 100 · k · E_classe / (H + k · E_totale)`.
- **Tre scenari:** basso k = 0,5, **centrale k = 1**, alto k = 2.
- **Pavimento.** Le evocazioni hanno 100–250 HP e muoiono dopo pochi colpi, mentre il modello le conta in campo per tutta la durata.
  Per questo l'eroe non scende mai sotto il meno colpito tra le classi **senza** evocazioni (War Hammer, War Drums, Bow, Naga Trident), nello stesso screenshot o nella stessa challenge.
  Per Treant, Elementale e Torre il limite scatta in tutti gli scenari: i dati dicono solo che le evocazioni hanno preso quasi tutti i colpi della classe.
- **Colpi dell'eroe** = colpi della classe misurati − colpi delle evocazioni stimati.

### Verifiche sui dati (`verifiche_modello.csv`)

Due controlli indipendenti, entrambi coerenti con k ≈ 1:

- **Runeblade.** Ha preso il compagno alla challenge 18. La sua quota di colpi per round sale da 10,0 (challenge 14–17) a 17,6 (challenge 18–20), cioè +7,6 punti.
  Il modello ne attribuisce 5,4 al compagno. Sono solo tre challenge: indicazione debole.
- **Claws.** Nelle challenge con più lupi in campo la sua quota di colpi è più alta: +6,8 punti per lupo in campo (correlazione +0,31, 20 challenge).
  Con k = 1 il modello prevede circa +8/+10.

## 3. Risultati (`colpi_finali_dopo_challenge_19.csv`, `colpi_finali_boss.csv`)

Quote sul totale dei colpi del team dopo la challenge 19. Eroi ed evocazioni sommano a 100.

| Voce | Colpi, centrale | Forbice | Totale della classe (misurato) |
|---|---|---|---|
| Double Blade (eroe) | **27,3** | 26,7–27,7 | 28,3 |
| Claws (eroe) | **20,4** | 18,1–22,1 | 24,5 |
| Runeblade (eroe) | **13,3** | 12,6–13,9 | 14,7 |
| War Hammer (eroe) | **13,2** | – | 13,2 |
| Wizard Staff (eroe) | 1,8 | 1,0–4,4 | 8,1 |
| Druid Staff, War Drums, Pickaxe, Bow, Naga Trident (eroi) | 1,0 ciascuno | – | 4,5 / 1,0 / 3,7 / 1,0 / 1,0 |
| Elementale (Wizard Staff) | 6,3 | 3,7–7,1 | |
| Lupi (Claws) | 4,1 | 2,5–6,4 | |
| Treant (Druid Staff) | 3,5 | limitato | |
| Torre (Pickaxe) | 2,7 | limitato | |
| Compagno (Runeblade) | 1,4 | 0,8–2,1 | |
| Portali (Double Blade) | 1,0 | 0,6–1,6 | |

Lettura:
- **Evocazioni.** Prendono circa un quinto di tutti i colpi del team (19%).
- **Chi è davvero in prima linea.** Al netto delle evocazioni, l'ordine non cambia: Double Blade e Claws sono gli eroi più colpiti, poi i due Tank appaiati al 13%.
  Il dubbio "i Tank sembrano tankare poco perché hanno tanta armatura" non regge: **la colonna conta i colpi, non i danni**, e anche in colpi i Tank ne prendono meno di Double Blade e Claws.
- **Claws.** Circa un sesto dei suoi colpi va ai lupi, ma il suo eroe resta il secondo più colpito.
- **Wizard Staff, Druid Staff e Pickaxe.** Quasi tutti i loro colpi vanno all'elementale, ai Treant e alla torre; i loro eroi ne prendono pochissimi, come gli altri eroi a distanza.

## 4. File

| File | Contenuto |
|---|---|
| `evidenze_codice_colpi.csv` | Citazioni dal `war3map.j`: contatore, proprietario, evocazioni |
| `evocazioni_parametri.csv` | Una riga per evocazione: abilità, comandi e lanci stimati, unità, durata, HP |
| `evocazioni_esposizione_challenge.csv` | Evocazione × challenge: secondi-unità in combattimento (scenari centrale e basso), unità medie in campo |
| `evocazioni_quota_modello_challenge.csv` | Classe × challenge: quota di colpi delle evocazioni prevista dal modello (3 scenari, senza pavimento) |
| `colpi_snapshot.csv` | Classe × screenshot: colpi misurati (cumulativi) e scorporo eroe / evocazioni nei 3 scenari, con pavimento |
| `colpi_finali_dopo_challenge_19.csv`, `colpi_finali_boss.csv` | Quadro finale: eroi ed evocazioni come voci separate, valore centrale e forbice |
| `colpi_per_challenge.csv` | Quote della singola challenge per differenza (metodo "tempo"): molto rumorose, usate solo per le verifiche |
| `verifiche_modello.csv` | I due controlli della sezione 2 |

Le altre analisi usano `colpi_snapshot.csv` (cumulativi) e `evocazioni_quota_modello_challenge.csv` (per challenge).
La quota di colpi dell'eroe in una challenge si ottiene così: quota totale stimata con il metodo validato, meno la quota delle evocazioni del modello, con lo stesso pavimento.

## 5. Limiti

- **Lo scorporo è una stima.** La multiboard dà solo il totale per giocatore. La forbice tra gli scenari è più larga per Claws (±2 punti) e Wizard Staff.
- **Le evocazioni muoiono.** Una volta morte non prendono più colpi, ma il modello le conta in campo per tutta la durata.
  Per questo serve il pavimento, e per Treant, Elementale e Torre la stima è "quasi tutto il totale della classe".
- **Lanci.** I lanci sono comandi nel replay: un comando senza mana sufficiente non evoca nulla. Il filtro sul cooldown toglie i doppioni, non i comandi falliti.
- **Torre.** Non si sa quando viene distrutta: nello scenario basso dura solo fino alla fine della challenge in cui è costruita.
- **Tempo da morto.** Gli eroi morti si contano comunque in campo per tutta la challenge, perché le morti si stimano più avanti nella catena degli script.
- **Danno in HP.** La mappa non lo registra. Per confrontare "colpi" e "danni" servirebbe una mappa modificata, o un conteggio a mano dagli HP: non è possibile con replay e screenshot.
