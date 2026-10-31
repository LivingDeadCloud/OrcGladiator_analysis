# Domanda 02: l'acquisto degli oggetti è ottimale?

Script: `analisi_acquisti.py`. Si lancia dalla cartella del progetto con
`python data_analysis/v2/domande/02_acquisto_oggetti/analisi_acquisti.py`. Usa solo la libreria standard e legge i file in sola lettura.
Negli output ci sono solo classe e ruolo, e lo script verifica che non compaiano nomi di giocatori.

## 1) Risposta breve

**Verdetto: in parte, e un giudizio di "ottimale" non è determinabile.**
Gli acquisti sono in gran parte **coerenti** con la classe e con il ruolo che ogni eroe ha davvero svolto. L'oro viene speso quasi tutto: risparmiare fino a 900–1.260 oro serviva ogni volta a comprare subito dopo una reliquia da 1.000–1.250.
Ci sono però inefficienze misurabili:
- il Druid Staff ha **4 punti talento non spesi su 6**;
- 4 classi hanno tenuto fermi i punti talento dei livelli 12 e 14 per circa 3–4 challenge;
- due oggetti con effetto attivabile, Defender's Buckler e Warrior's Spirit, **non sono mai stati attivati**, e il blink delle Warp Treads quasi mai;
- alcune pozioni sono state usate poco: Naga Trident al 14%, tank e War Drums intorno al 30%.

Non esiste una build di riferimento e c'è una sola partita, quindi "ottimale rispetto a cosa" non si può stabilire. Nemmeno l'effetto degli acquisti sulle quote si distingue dal rumore.

## 2) Evidenze

### 2.1 Come compaiono gli acquisti nel replay e se possono fallire
- **MISURATO.** Ogni acquisto è un ordine `order_notarget` con il codice dell'oggetto (`I0..`) come ordine: 417 ordini in tutto.
  - Comprende anche "oggetti" gratuiti: 190 teletrasporti nell'arena e 23 tentativi di resurrezione con l'Ancestral Stone.
  - I **talenti** sono oggetti che costano 1 legno (= 1 punto talento).
  - Gli stivali sono oggetti "Purchase X" che un trigger trasforma negli stivali veri, rimborsando il 75% di quelli vecchi (JASS `Boots_Upgrade`, `BootCostReturnFactor = 0,75`).
- **Il replay registra il comando, non l'esito.**
  - In WC3 l'ordine viene registrato anche se poi il motore lo rifiuta, per esempio per oro insufficiente. Questa è un'**ipotesi sul motore**, non verificabile nei file della mappa.
  - La mappa invece rimborsa via trigger due casi:
    - i tomi comprati sotto il livello 12 dell'eroe o oltre il limite di 50 usi (JASS `Tomes_Buy`: +110 oro);
    - i talenti comprati quando l'eroe è nascosto.
  - Con il livello stimato dagli screenshot, **nessun tomo** risulta comprato sotto il livello 12.
- **Verifica con l'oro della multiboard** (`riconciliazione_oro.csv`, **STIMATO**).
  - Per ogni intervallo tra due screenshot si calcola, per ogni classe: entrata comune implicita = oro finale − oro iniziale + costi degli ordini − rimborsi − premi individuali di fine round. I premi individuali sono quelli del JASS: 2,5 × (ondata − 1) oro al migliore del round per danni, tank e cure.
  - Questa entrata dovrebbe essere uguale per tutti.
  - Nei 20 intervalli di fine round senza prestiti (`-borrow`/`-loan`) lo scarto mediano dalla mediana di squadra è di **13 oro**, e 17 intervalli su 20 restano entro 50 oro. Quindi gli ordini corrispondono ad acquisti realmente pagati.
  - Negli altri intervalli gli scarti si spiegano con i prestiti: il JASS `Repay_Loans` li restituisce automaticamente a inizio wave, e gli importi non si possono ricostruire.
- **Unico caso anomalo.** Il Double Blade, a 972 s, ha dato due ordini identici nello stesso millisecondo per una Tank's Potion (100 oro). Ha 110 oro a 925 s e la sua entrata risulta di circa 110 oro sopra la squadra. Quindi **probabilmente il secondo acquisto è fallito per oro insufficiente** (STIMATO).

### 2.2 Spesa e tempi (`riepilogo_classi_acquisti.csv`, `cronologia_acquisti.csv`)
Costi da `war3map.w3t` (campo `igol`). Per Charm of Protection e Corrosive Oil la mappa non modifica il costo, quindi si usa il default dell'oggetto base `belv` (400, da `ItemData.slk`).

| classe | ruolo | spesa oggetti (netta rimborsi) | tomi validi (spesa) | primo oggetto ≥500 oro | oro max a fine round | oro durante il boss finale |
|---|---|---|---|---|---|---|
| Claws | DPS mischia | 2.362 | 15 (1.650) | 1.801 s (dopo C7) | 756 | 89 |
| Double Blade | DPS mischia | 2.412 | 9 (990) | 1.518 s (dopo C6) | 701 | 0 |
| Pickaxe | DPS mischia | 2.025 | 13 (1.430) | 4.301 s (dopo C15) | 1.261 | 0 |
| Bow | DPS distanza | 3.017 | 0 | 3.700 s (dopo C13) | 428 | 365 |
| Wizard Staff | DPS distanza | 2.462 | 5 (550) | 2.939 s (dopo C10) | 993 | 93 |
| Naga Trident | DPS distanza | 2.537 | 5 (550) | 2.947 s (dopo C10) | 689 | 0 |
| Druid Staff | Healer | 2.656 | 9 (990) | 2.637 s (dopo C9) | 937 | 0 |
| War Drums | Support | 1.437 | 13 (1.430) | 3.919 s (dopo C14) | 1.228 | 75 |
| Runeblade | Tank | 2.225 | 10 (1.100) | 3.425 s (dopo C12) | 832 | 90 |
| War Hammer | Tank | 2.012 | 8 (880) | 2.656 s (dopo C9) | 912 | 0 |

- **Accumulo di oro finalizzato** (MISURATO). Ogni picco di oro è seguito subito da un acquisto grosso:
  - Pickaxe: 1.261 → Warrior's Spirit (1.250) 30 s dopo;
  - Wizard Staff: 993 → Shard of the Revenant (1.000);
  - Druid Staff: 937 → Flag of Victory (1.250);
  - War Drums: 1.228 → 11 tomi;
  - War Hammer: 912 → 8 tomi prima del boss.
- **Oro rimasto inutilizzato durante il boss finale**: 712 in tutto, di cui 365 del Bow.
- **Tomi** (+2 a una statistica per 110 oro, solo dal livello 12): comprati quasi tutti nelle pause dopo le challenge 17–19. Il Bow non ne ha comprato nessuno.
- Quasi tutti gli acquisti a pagamento avvengono nelle pause tra le challenge. Cadono dentro una finestra di combattimento solo i 23 tentativi di resurrezione, 4 tomi e 3 talenti a fine C19 e la Runed Bracers del Pickaxe a fine C12. Le finestre di C12 e C19 sono però stimate (mancano i secondi del round), quindi questi 8 acquisti possono essere avvenuti a round già finito.

### 2.3 Coerenza oggetto–classe (`catalogo_oggetti.csv`, tooltip della mappa, MISURATO)
- **Attributo principale.** Tra i bonus agli attributi comprati (oggetti più tomi), quelli sull'attributo principale pesano:
  - 100% per Double Blade e Druid Staff;
  - 93% Pickaxe, 73% Runeblade;
  - 50–59% per Claws, Wizard Staff, Naga Trident e War Drums: gli oggetti danno 2 attributi, quindi il 50% è il massimo possibile;
  - 47% War Hammer, che ha comprato 8 tomi "+1 Stats" invece di "+2 Strength".
- **Ruolo.**
  - Tank (War Hammer, Runeblade): Heartstone, Petrified Bark, Imbued Greaves, Illuminators, Defender's Buckler. Tutti oggetti dei negozi tank.
  - Healer (Druid Staff): solo mana (Thinking Sandals → Slippers of Focus, Pipe of Insight) più Flag of Victory, che dà +50% danni a tutta la squadra.
  - Support (War Drums): Charm of Protection, Mysterious Figurine e I093. Sono oggetti di squadra, e I093 potenzia anche Embolden.
  - Bow: solo danno (Hood of Cunning, Corrosive Oil, Hex of Augmentation III, che trasforma proprio la Corrosive Oil, Windwalkers, Feral Visage).
  - Wizard Staff: Mysterious Codex (le ultimate rimborsano 200 mana), Ring, Shard (bonus alle evocazioni: Water Elementals).
- **Double Blade.** È classificato DPS mischia, ma ha una build **da tank**: Tank's Potion, Ethereal Armour, Petrified Bark, Imbued Greaves, 5 tomi +160 HP. Questo è coerente con il ruolo che ha svolto davvero: è primo per colpi presi, 28,3% (27,3% il solo eroe, senza i portali), in `scheda_classi.csv`. La colonna "tank" della multiboard conta i colpi, non i danni (`colpi/NOTE.md`).

### 2.4 Oggetti attivabili e pozioni (`uso_oggetti_attivabili.csv`)
Il replay dà solo `useslotN`, quindi lo slot → oggetto è un'attribuzione. Le pozioni sono oggetti permanenti con 40 s di cooldown: si comprano una volta sola.

| classe | oggetto | usi | % del massimo teorico in combattimento |
|---|---|---|---|
| Druid Staff | Wizard's Potion | 74 | 85% |
| Bow | Rage Potion | 67 | 83% |
| Wizard Staff | Wizard's Potion | 63 | 74% |
| Pickaxe | Wizard's Potion | 61 | 72% |
| Claws | Wizard's Potion | 45 | 53% |
| Double Blade | Tank's Potion | 40 | 49% |
| Runeblade | Wizard's Potion | 34 | 42% |
| War Drums | Wizard's Potion | 26 | 31% |
| War Hammer | Wizard's Potion | 25 | 29% |
| Naga Trident | Wizard's Potion | 11 | **14%** |
| War Drums | Charm of Protection (cooldown 180 s) | 6 | 40% (attribuzione media) |
| Naga Trident | Warp Treads, blink | 3 | 2% |
| War Drums, Claws | Warp Treads, blink | 0 | 0% |
| Runeblade | Defender's Buckler, taunt (cooldown 20 s) | **0** | 0% |
| Pickaxe | Warrior's Spirit, +10.000 HP (1.250 oro, cooldown 100 s) | **0** | 0% |

- **Pozioni.** 8 classi su 10 hanno comprato la Wizard's Potion, che dà **solo mana** (160 in 6 s), tanker inclusi. Solo Bow e Double Blade hanno una pozione che cura.
  - Per il Wizard Staff, l'unica classe con simulazione del mana affidabile, la scelta è coerente: è sotto il 20% di mana per il 70% del tempo di combattimento (stima di `abilita_mana`).
  - Per le altre classi il bisogno di mana è solo indicativo o non affidabile.
- Per Defender's Buckler e Warrior's Spirit restano comunque i bonus passivi (armatura e blocco; +25 Strength). La parte attivabile, che motiva buona parte del prezzo, non è stata usata.

### 2.5 Talenti (MISURATO gli ordini, STIMATO i punti)
- Il JASS `Level_Up` dà 1 punto talento ai livelli 8, 10, 12, 14, 16, 18, 21… Al livello finale (18–19) i punti sono 6 per tutti.
- **Druid Staff: 2 talenti comprati su 6 punti.** Ha comprato Brambles a C8 e Nourish a C10, poi più nulla.
- Runeblade e Bow: 5 su 6.
- War Drums ha 7 ordini: Persevere due volte a 0,1 s di distanza, probabile doppio click. Naga Trident ha comprato Thunder 3 volte: è ripetibile per tooltip.
- **Punti tenuti fermi.** Wizard Staff, Pickaxe, Runeblade e War Hammer non comprano nessun talento tra il livello 10 (dopo C10) e il livello 15 (dopo C16). Poi ne comprano due insieme: i punti dei livelli 12 e 14 sono rimasti inutilizzati per circa 1.000–1.200 s, cioè 3–4 challenge.
  - Gli altri 5 eroi hanno comprato un talento già al livello 12–13, quindi il punto era utilizzabile.
  - Resta però un'ipotesi che quei talenti fossero disponibili: il trigger `R_Master_Spells` aggiunge talenti allo stock durante la partita.

### 2.6 Quote prima/dopo gli acquisti importanti (`quote_prima_dopo_acquisti.csv`, `quote_confronto_riferimento.csv`, STIMATO)
- Considerati 23 acquisti da almeno 500 oro. Per ciascuno si confronta la quota per round della metrica del ruolo (danni per i DPS, colpi presi dall'eroe per i tank, cure per Healer e Support): media delle 3 challenge successive contro media delle 3 precedenti.
- Risultato: mediana **+2,1 punti**, 61% di casi positivi. Su tutte le pause della partita lo stesso calcolo dà mediana −1,0 e 46% positivi.
- Esempi:
  - in salita: Claws +17 dopo Shard of the Revenant, Pickaxe +11 dopo Warrior's Spirit, Druid Staff +12 e +9 dopo Slippers of Focus e Pipe of Insight;
  - in discesa: Bow −8,6 dopo Feral Visage, Runeblade −8,5 (colpi presi) dopo Illuminators, Naga Trident −5,5 dopo le Warp Treads.
- Le quote sono a somma 100: crescono anche quando sono gli altri a calare. Inoltre il tipo di wave, le morti e gli acquisti degli altri cambiano insieme. **La differenza non si può attribuire agli oggetti.**

## 3) Cosa non si può dire e perché
- **Se la build è "ottimale".** Manca un riferimento: un'altra partita, una build consigliata dalla mappa o un modello del danno. Con una sola partita e un giocatore per classe non si confrontano scelte alternative.
- **Il valore reale degli oggetti.** Il replay non contiene danni, cure né statistiche dell'eroe. Le quote esistono solo a fine round e sono relative.
  - Esempio: se per il War Hammer conveniva "+2 Strength" rispetto a "+1 Stats" dipende dalle costanti per attributo. Le analisi precedenti hanno mostrato che le costanti personalizzate in `war3mapMisc.txt` non sono in uso, quindi la domanda resta aperta.
- **L'esito di ogni singolo ordine.** È verificato solo in modo aggregato (riconciliazione dell'oro) e solo negli intervalli senza prestiti.
- **Gli 8 `dropitem`** (5 del Double Blade). Il bersaglio non è salvato nei CSV, quindi non si sa se sono vendite o passaggi di oggetti.
- **Quale oggetto c'è nei singoli slot.** È un'inferenza, con confidenza indicata nel CSV.
- **Se i 23 ordini di resurrezione con l'Ancestral Stone sono andati a buon fine.** La pietra deve avere 100 mana.
- **Se i talenti mancanti erano davvero disponibili nel negozio talenti in quel momento.**

**Cosa registrare nella prossima partita:**
- uno screenshot dell'inventario (6 slot) e dell'oro di ogni eroe a fine round;
- i messaggi a schermo ("Not enough gold", rimborsi, prestiti);
- i punti talento disponibili;
- se possibile, una seconda partita con build diverse sulla stessa classe, per avere un confronto.

## 4) Raccomandazioni (solo quelle supportate dai dati)
1. **Spendere sempre i punti talento appena arrivano**: livelli 8, 10, 12, 14, 16, 18. Sono gratuiti. Riguarda soprattutto il Druid Staff (4 punti non spesi) e chi ha aspettato fino al livello 15: Wizard Staff, Pickaxe, Runeblade, War Hammer.
2. **Usare gli attivi che si pagano**: il taunt del Defender's Buckler (Runeblade), Warrior's Spirit (Pickaxe), il blink delle Warp Treads (War Drums, Claws). In alternativa, preferire oggetti con soli effetti passivi.
3. **Pozioni**:
   - chi la compra la usi a cooldown: Naga Trident 14%, War Hammer 29%, War Drums 31%;
   - i tank, che hanno la Wizard's Potion (solo mana), valutino se serve più mana o più vita. Il Double Blade, il tank effettivo, usa la Tank's Potion;
   - non serve comprare due volte la stessa pozione: è permanente.
4. **Non tenere oro durante il boss finale** (365 oro del Bow, circa 3 tomi). Comprare i tomi dal livello 12 in poi con l'oro avanzato.
5. **Attenzione ai doppi click sugli acquisti**: 73 ordini sono ripetuti entro 2 s. Per gli oggetti Unique o costosi il secondo ordine, se va a buon fine, spreca oro.

## 5) Grado di fiducia
- **Alto** su:
  - la cronologia degli acquisti e i costi (replay + `war3map.w3t`);
  - la coerenza oggetto–classe e oggetto–ruolo (tooltip della mappa);
  - l'oro non speso alla fine (multiboard);
  - il fatto che gli ordini corrispondano ad acquisti pagati (riconciliazione dell'oro: scarto mediano 13 oro).
- **Medio** su:
  - i punti talento non spesi o ritardati (dipende dal livello interpolato e dalla disponibilità dei talenti);
  - l'uso degli attivi (dipende dall'attribuzione slot → oggetto);
  - il secondo acquisto fallito del Double Blade.
- **Basso o nullo** su un effetto degli acquisti sulle quote e su qualunque giudizio di "ottimalità" in senso stretto.

## File prodotti
- `analisi_acquisti.py`: lo script.
- `cronologia_acquisti.csv`: tutti i 417 ordini di acquisto con classe, momento, challenge, livello stimato, costo, rimborsi e note.
- `catalogo_oggetti.csv`: 171 oggetti dei negozi più quelli ordinati, con negozio, costo, fonte del costo, bonus agli attributi, funzione e tooltip.
- `riepilogo_classi_acquisti.csv`: una riga per classe (spesa, tomi, talenti, oro, uso degli slot).
- `riconciliazione_oro.csv`: verifica dell'oro tra screenshot consecutivi.
- `uso_oggetti_attivabili.csv`: uso di pozioni e oggetti attivabili rispetto al massimo teorico.
- `quote_prima_dopo_acquisti.csv` e `quote_confronto_riferimento.csv`: quote prima e dopo gli acquisti da almeno 500 oro.
