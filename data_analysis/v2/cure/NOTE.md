# Cure al netto di pozioni e aure

Generato da `analisi_cure.py`, da lanciare nella cartella del progetto con `python analisi_cure.py`. Usa solo la libreria standard.
Nei file compaiono solo `classe` e `ruolo`, mai i nomi dei giocatori.

## 1. Cosa conta la mappa come "cura" (risposta netta)

**La colonna "% cure" della multiboard (`heal_pct`) comprende pozioni, rigenerazione, lifesteal (anche quello della Vampiric Aura) e oggetti.**
Quindi **non** misura le sole cure da abilità e non si può usare così com'è per la domanda posta.

Come funziona nel `war3map.j` (le citazioni sono verificate dallo script e riportate in `evidenze_codice_cure.csv`):

- **Il contatore.** `Trig_HealMeterCount_Actions` esegue
  `udg_HealCountTotal[1+GetPlayerId(GetOwningPlayer(udg_heal_source))] += udg_heal_amount`.
  Scatta su `udg_HealEvent == 1` (`InitTrig_HealMeterCount`) con la condizione
  `IsUnitType(udg_heal_source, UNIT_TYPE_HERO) and udg_heal_amount <= 10000` (`Trig_HealMeterCount_Conditions`).
  La quota in multiboard è `HealCountTotal / StatisticsTotals[4]`, cioè la quota sul totale del team (riga ~1180).
- **Chi alimenta il contatore.** `udg_heal_source` viene assegnata **solo** dentro `Trig_Heal_Unit_Actions`
  (`set udg_heal_source=udg_NextHealSource`, poi viene ripristinata). Il valore iniziale è `null`.
  - Il rilevamento per differenza di vita (`Trig_Heal_Check_Loop_Actions`, ogni 0,05 s, soglia `HEAL_THRESHOLD` = 25,
    rigenerazione stimata con `heal_regen`/`REGEN_THRESHOLD`) **non imposta mai la sorgente**. Le cure che rileva hanno
    sorgente `null` e la condizione "sorgente eroe" le scarta. Per questo **le cure native di WC3** (fontana, abilità
    o oggetti senza trigger) **non vengono contate**.
  - Viene contato **tutto ciò che passa da `Heal_Unit`** con `NextHealSource` eroe: 36 chiamate in 30 funzioni, elencate in
    `evidenze_codice_cure.csv`. Tra queste:
    - **abilità**: Rejuvenation, Tranquility e Innervate (Druid); Motivate e War Drums (War Drums); Death Coil, Death Pact e Cannibalize (Runeblade);
      Rock Shield e Mana Tide Totem (Claws); Demon Skin (Double Blade); Avatar (War Hammer, solo con Runed Bracers); più le abilità
      di classi non presenti in questa partita;
    - **pozioni**: `Trig_PotionPeriodic_Func001A`, sorgente `udg_PlayerHero[owner]`, quindi chi beve;
    - **rigenerazione**: `Trig_GlobalRegeneration_*`, ogni 0,5 s, `HPmax × Regeneration_Value / 200`, sorgente l'eroe stesso.
      `Regeneration_Value` parte da 0,5 per tutti (0,25% HP/s) e cresce con gli oggetti (Survival Treads +1, Prayer Beads +1,5, ...).
      Gli eroi non hanno altra rigenerazione (`uhpr` = 0, `StrRegenBonus` = 0). **Tutta la rigenerazione degli eroi è contata come cura.**
      `Regeneration_FTDisable` spegne solo il testo fluttuante (`HealTag`), non il contatore;
    - **lifesteal**: `Trig_GlobalLifeSteal_Actions`, sorgente **chi attacca**. Comprende il buff Vampiric Aura `B002`
      (40% o 80% per il Double Blade, unità `O005`; 8% per gli alleati), Hunger `B027`, Mask of Death `I05X`/`I04X` ed Enchant: Blood `A0AW`;
    - **oggetti**: `Trig_GlobalItemEffects_Actions`, cioè Scepter of Healing `A0BJ` (30% HP) e Heartstone `I096`/`I0AQ`
      (+4% HP max a ogni incantesimo lanciato).
  - C'è una sola scrittura diretta su `HealCountTotal` fuori dal contatore: lo scudo del Pelt in `Trig_PeltDamageModifierEvent_Actions`.
    Il danno assorbito viene accreditato al proprietario del bersaglio. Il Pelt non è in questa partita.
- **Overheal.** Non viene contato. `Heal_Unit` applica la cura con `SetWidgetLife`, che si ferma al massimo, e conta
  `heal_amount = vita dopo − vita prima`. Una cura vale solo se ≥ 1 HP (`Trig_Heal_Unit_Func009C`, `heal_diff = 1`).
  Pozioni e rigenerazione contano quindi solo quando l'eroe non ha la vita piena: si misura la cura **effettiva**.
- **Quando conta.** Il contatore si accende in `Trig_Wave_Start_Actions` (`EnableTrigger(gg_trg_HealMeterCount)`) e si spegne in
  `Trig_Wave_Finish_Actions`. Le cure tra una challenge e l'altra (negozio, fontana) non sono contate.
- **A chi va la cura.** Va al proprietario della sorgente:
  - per le abilità, a chi lancia;
  - per pozioni, rigenerazione, Heartstone, Demon Skin, Death Pact e Avatar, a sé stessi;
  - per il lifesteal, a chi colpisce. Le cure della Vampiric Aura vanno a chi ne beneficia, non al portatore dell'aura.

## 2. Metodo

### 2a. Quote misurate e per challenge (`quota_cure_per_challenge.csv`)
- `cure_quota_cumulativa_misurata` e `colpi_quota_cumulativa_misurata` sono i valori della multiboard (cumulativi, somma ≈ 100).
  La colonna "tank" della multiboard conta i **colpi presi** (non i danni), evocazioni comprese: vedi `colpi/NOTE.md`.
- `colpi_eroe_quota_tra_eroi_*` = colpi del solo eroe (stima centrale di `analisi_colpi.py`), riportati a 100 tra i soli eroi.
  È questa la grandezza usata nel modello: rigenerazione, pozioni e lifesteal curano l'eroe, non le sue evocazioni.
  La challenge k è lo screenshot `post` con `challenges_completed = k`. La challenge 20 (boss) è lo screenshot `031526_03`,
  l'ultimo con tutti i 10 eroi: in `040526_23` (sconfitta) manca il Double Blade.
- `cure_variazione_quota_pp_misurata` = S(k) − S(k−1), in punti percentuali. È misurata, ma **non** è la quota della challenge.
- `cure_quota_challenge_stimata` (**stima**). Se W(k) è il totale di cure del team fino alla challenge k, la quota della sola
  challenge k è `(S(k)·W(k) − S(k−1)·W(k−1)) / (W(k) − W(k−1))`. Il totale assoluto non è noto, quindi si assume
  **W proporzionale al tempo di combattimento cumulato**:
  - si usano i `clear_seconds` di `rounds.csv`;
  - dove mancano (challenge 8, 12, 19 e boss) si usa il tempo tra screenshot × 0,55, il rapporto mediano clear/tempo tra screenshot.

  I valori negativi, dovuti all'arrotondamento a 0,1 della trascrizione e all'ipotesi sul peso, vengono azzerati e la riga viene
  rinormalizzata a 100: è successo 31 volte su 200 per le cure e 23 per i colpi dell'eroe. Il valore prima di questa correzione è in
  `cure_quota_challenge_grezza_stimata`. Nelle ultime challenge una variazione di 0,1 punti nella quota cumulativa sposta la quota
  della challenge di circa 1–2 punti: questi valori vanno letti come indicativi.

### 2b. Stima "solo abilità" (`stima_cure_solo_abilita.csv`)
1. **Fatto certo dal codice.** Bow, Naga Trident, Pickaxe e Wizard Staff **non hanno alcuna abilità che chiami `Heal_Unit`**: tutta la loro
   `heal_pct` viene da rigenerazione, pozioni, lifesteal e oggetti. Il War Hammer ha come unica cura da abilità Avatar, che cura solo con i
   Runed Bracers, comprati a 5431 s (challenge 19): fino a lì la sua cura è da Heartstone, rigenerazione e lifesteal.
   Queste 5 classi fanno da **riferimento** e la loro quota "solo abilità" è 0.
2. **Modello.** Le cure su sé stessi (rigenerazione, pozioni, lifesteal) possono solo recuperare danno preso dall'eroe, quindi la parte
   non-abilità di ogni classe si stima come `r × colpi_eroe`, con `r` = Σ cure / Σ colpi dell'eroe delle classi di riferimento
   (cumulativo, ricalcolato a ogni snapshot; al boss r = 0,90). Per le classi con abilità:
   `cure_abilità = max(0, heal_pct − r·colpi_eroe)`. La quota "solo abilità" è la loro rinormalizzazione a 100.
   Fino alla versione precedente si usava la colonna "tank" intera, che comprende i colpi delle evocazioni: il Runeblade risultava
   più "colpito" per via del compagno, e il Wizard Staff per via dell'elementale.
3. **Scenari** (il rapporto r varia molto da classe a classe: da 0,64 a 2,78):
   - `_a`: r = 0, cioè tutta la cura delle classi con abilità viene trattata come da abilità. È il massimo per le classi molto colpite;
   - `_b`: r = rapporto aggregato delle classi di riferimento (**scenario centrale**);
   - `_c`: r = rapporto individuale massimo, cioè una forte componente non-abilità.
   Per la stima per challenge si applica lo stesso modello alle quote per challenge stimate, con l'r cumulativo.
4. `frazione_proprie_cure_da_abilita_*` indica quanta parte della `heal_pct` di quella classe sarebbe da abilità.

### 2c. Replay (`eventi_cura_replay.csv`, `comandi_abilita_curative.csv`, `uso_pozioni_slot.csv`)
- **Comandi di abilità curative.** Ordini con l'order id dell'abilità, filtrati per classe (tabella `ABIL_CURA` nello script).
  Sono **comandi** e non lanci riusciti: contano anche i clic ripetuti. Death Coil cura solo se il bersaglio è un alleato,
  ma il replay non dice se il bersaglio è alleato o nemico. Motivate è passiva e non genera comandi. Le challenge sono divise con gli
  orari degli screenshot, come in `summarize_replay.py`.
- **Pozioni.** Il replay registra `useslotN`, non quale oggetto c'è nello slot. Lo slot della pozione è stato ricostruito incrociando
  i dati del replay:
  - l'unico acquisto di pozione nel replay;
  - il primo uso dello slot, che arriva dopo l'acquisto;
  - gli intervalli tra usi, quasi sempre ≥ 40 s (la ricarica della pozione: le pozioni sono permanenti e riutilizzabili).

  Il risultato:
  - **8 classi** hanno comprato la Wizard's Potion (`I00R`), **che dà solo mana (160) e nessuna cura**;
  - il Bow ha la Rage Potion (`I00W`, 25% HP) in slot 3 (confidenza alta);
  - il Double Blade ha la Tank's Potion (`I00Q`, 40% HP), attribuita allo slot 5 (confidenza media: il primo uso è a 2131 s, lontano dall'acquisto a 972 s).

  I comandi ripetuti a meno di 40 s dall'ultimo uso contato non contano come nuovi usi (`comandi_slot_pozione` riporta il totale grezzo).
  `cura_pozioni_nominale_hp_max` = usi × frazione di HP max, cioè il **massimo teorico**. La cura reale dipende dagli HP mancanti
  e la mappa la conta solo durante le challenge.

## 3. Risultati principali (snapshot del boss, cumulativo)

| classe | ruolo | % cure misurata | % colpi misurata | % colpi eroe (tra eroi, stima) | cure da abilità? | quota solo abilità a / **b** / c | comandi cura | usi pozione cura | usi pozione mana |
|---|---|---|---|---|---|---|---|---|---|
| Druid Staff | Healer | 34,7 | 4,5 | 1,1 | sì | 43,4 / **67,6** / 72,0 | 684 | 0 | 74 |
| Runeblade | Tank | 16,4 | 14,8 | 16,4 | sì | 20,5 / **3,5** / 0 | 249 | 0 | 34 |
| War Drums | Support | 15,4 | 0,9 | 1,1 | sì | 19,3 / **28,9** / 28,0 | 46 (+ Motivate passiva) | 0 | 26 |
| War Hammer | Tank | 12,5 | 13,6 | 16,8 | solo da 5431 s | 0 / **0** / 0 | 21 (Avatar) | 0 | 25 |
| Claws | DPS mischia | 6,7 | 24,1 | 24,8 | sì | 8,4 / **0** / 0 | 32 | 0 | 45 |
| Double Blade | DPS mischia | 6,7 | 28,6 | 34,2 | sì | 8,4 / **0** / 0 | 44 | 40 | 0 |
| Pickaxe | DPS mischia | 3,1 | 3,5 | 1,1 | no | 0 | 0 | 0 | 61 |
| Bow | DPS distanza | 2,1 | 0,9 | 1,1 | no | 0 | 0 | 67 | 0 |
| Wizard Staff | DPS distanza | 1,3 | 8,0 | 2,0 | no | 0 | 0 | 0 | 63 |
| Naga Trident | DPS distanza | 1,1 | 1,1 | 1,4 | no | 0 | 0 | 0 | 11 |

- **Misurato.** Almeno il **7,6%** delle cure del team è sicuramente non da abilità: è la quota delle 4 classi senza alcuna cura
  da abilità. Con il War Hammer, che fino alla challenge 18 non ha cure da abilità, si arriva al **20,1%**.
- **Stimato (scenario b).** Circa il **50%** della `heal_pct` del team viene da rigenerazione, pozioni, lifesteal e oggetti.
  Al netto di questa parte:
  - il **Druid Staff** sale da 34,7% a circa **68%** delle cure da abilità (circa il 97% della sua cura è da abilità);
  - il **War Drums** sale da 15,4% a circa **29%** (circa il 94%);
  - il **Runeblade** scende da 16,4% a circa **3,5%** (circa un decimo della sua cura è da abilità; il resto è rigenerazione,
    Heartstone e lifesteal da tank);
  - **War Hammer, Claws e Double Blade** scendono a circa 0: le loro cure sono spiegate da colpi presi, rigenerazione,
    Heartstone (War Hammer), lifesteal della Vampiric Aura e Tank's Potion (Double Blade).
- **Per challenge** (quota cure stimata): il Druid oscilla tra 23% e 53% nelle challenge 1–19. Nel boss crolla a circa 5%,
  perché la sua quota cumulativa scende da 36,0 a 34,7 nonostante 62 comandi di cura. Il War Drums sale nelle fasi finali:
  41% nella 17, 32% nella 19 e circa 46% nel boss.
- **Pozioni.** Solo 2 classi su 10 hanno una pozione che cura: Bow (67 usi, al massimo circa 16,8 × HP max) e Double Blade
  (40 usi, al massimo circa 16 × HP max). Tutte le altre usano una pozione **di solo mana**: le loro cure da "pozione" sono quindi 0.

## 4. File e colonne

| file | contenuto |
|---|---|
| `evidenze_codice_cure.csv` | funzione JASS, ruolo nel sistema, `sorgente_cura` (NextHealSource), `quantita_cura` (NextHealAmount), fonte, classe/oggetto, tipo, categoria (abilità / esclusa), estratto del codice; riga `VERIFICA` = dove viene assegnata `udg_heal_source` |
| `catalogo_fonti_cura.csv` | classe, fonte, id_mappa, order_hex, tipo (cura diretta, ad area, nel tempo, aura, lifesteal, pozione/oggetto, rigenerazione), categoria, contata_dalla_mappa, attribuita_a, formula_dal_codice, note |
| `quota_cure_per_challenge.csv` | classe × challenge: screenshot, tempo, peso, quote cumulative misurate (cure, tank), variazione, quota per challenge stimata (grezza e corretta) |
| `stima_cure_solo_abilita.csv` | classe × challenge: rapporti r, cure abilità / non-abilità in punti, frazione delle proprie cure da abilità, quota solo abilità cumulativa e per challenge negli scenari a/b/c |
| `eventi_cura_replay.csv` | classe × challenge: comandi abilità curative, comandi sullo slot della pozione, usi pozione cura / solo mana, usi di slot non attribuiti, cura nominale delle pozioni in multipli di HP max |
| `comandi_abilita_curative.csv` | classe × challenge × abilità: n_comandi |
| `uso_pozioni_slot.csv` | classe × slot: usi, primo uso, pozione attribuita, acquisto, intervallo minimo, % intervalli ≥ 40 s, confidenza |
| `riepilogo_classi.csv` | una riga per classe con i valori della tabella sopra |

## 5. Limiti
- Il replay contiene solo comandi. Le quantità di cura reali, gli HP max e gli attributi degli eroi non sono noti, quindi non si può fare una stima
  "dal basso" in HP. La stima "solo abilità" è un modello dall'alto (`r × colpi_eroe`) con un'ipotesi forte: la parte non-abilità è
  proporzionale ai colpi presi dall'eroe. Ma i colpi non sono danni: un eroe con molta armatura recupera meno HP per colpo. Il lifesteal dipende invece dal danno fatto, e la rigenerazione dagli HP max e dal tempo passato ferito.
  Il ventaglio a–c ne mostra la sensibilità.
- Le quote per challenge dipendono dall'ipotesi "totale cure del team ∝ tempo di combattimento" e dall'arrotondamento della trascrizione.
- La mappa slot → pozione è un'inferenza. Il Double Blade ha confidenza media; gli slot non attribuiti sono contati a parte.
- I comandi di abilità non sono lanci riusciti. Il bersaglio di Death Coil (alleato o nemico) non è noto.
- Le classi di riferimento non sono omogenee: il rapporto cure/colpi dell'eroe va da 0,64 a 2,78 (Bow, che ha la Rage Potion e viene colpito pochissimo).
- I colpi dell'eroe sono una stima (`colpi/NOTE.md`): l'incertezza dello scorporo si somma a quella di questo modello.
- Il War Hammer è trattato come classe senza cure da abilità per tutta la partita. Avatar cura solo con i Runed Bracers, presenti solo dalla challenge 19.
