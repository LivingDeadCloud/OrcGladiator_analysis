# Domanda 5 – Il posizionamento dei giocatori sulla mappa è ottimale?

Script: `analisi_posizionamento.py`. Si lancia dalla cartella del progetto con `python data_analysis/v2/domande/05_posizionamento/analisi_posizionamento.py`.
Usa `w3g_parser.py` senza modificarlo: sostituisce solo in memoria la funzione che decodifica le azioni, per tenere gli ID delle unità selezionate.
CSV prodotti: `copertura_classe.csv`, `validazione_ultimo_click.csv`, `posizioni_classe.csv`, `metriche_gruppo_tipo_wave.csv`, `classe_challenge_posizione.csv`, `relazione_danni_hp.csv`.
Mappa: `posizioni.svg`. Le distanze sono in unità di gioco di WC3. Per confronto, l'arena misura circa 5200 × 5250.

## 1) Risposta breve

**Verdetto: in parte.** La disposizione di base è quella giusta. I Tank sono i più vicini ai nemici. L'Healer resta dietro i Tank per il 90% del tempo. Il gruppo è compatto e combatte nella parte sud-centrale dell'arena, la più lontana dai tre punti di spawn (Est, Nord, Ovest).
**Se però sia "ottimale" non si può stabilire.** Il replay non contiene le posizioni reali dei nemici, il terreno non è stato analizzato e con questi dati non c'è un legame chiaro tra posizione e danni subiti.
Due segnali parziali suggeriscono dei margini di miglioramento:
- i due Tank stanno entro la gittata delle cure dell'Healer (700) solo per circa il 57% del tempo;
- nelle wave ibride il gruppo è più disperso e l'Healer più lontano dai Tank.

## 2) Evidenze

### a) Quanto si può ricostruire

**Come si ottengono posizioni reali (MISURATO).** Il replay registra l'ID dell'unità bersaglio di ogni ordine. Si sono ricavati gli ID dei 10 eroi dal "sottogruppo attivo" (azione 0x19).
Quando un giocatore dà un ordine *su* un eroe (Rejuvenation, buff, click destro su un alleato), le coordinate x,y di quell'ordine sono il punto cliccato sopra l'eroe. Quel punto è la **posizione reale** dell'eroe in quell'istante, con l'errore di un click: ipotesi circa 50-100 unità.
Questi punti si chiamano qui *ancore*:
- 1964 in tutta la partita;
- 1196 in combattimento cliccate da *altri* giocatori, usate per la validazione.

**Gli ordini con coordinate vanno davvero agli eroi (MISURATO).** Tra il 93% (Wizard Staff) e il 99,8% (Runeblade) degli ordini con coordinate sono dati con l'eroe come unità attiva. Il resto va a evocazioni, torri o unità selezionate solo per guardarle.

**Copertura (MISURATO, `copertura_classe.csv`).** Quota del tempo di combattimento (3603 s, campionati ogni secondo) in cui l'ultimo ordine con coordinate dato all'eroe ha al massimo 10 s:

| Classe | % entro 10 s |
|---|---|
| War Hammer | 93% |
| Wizard Staff | 89% |
| Claws | 83% |
| Runeblade | 82% |
| Druid Staff | 79% |
| Pickaxe | 76% |
| War Drums | 69% |
| Naga Trident | 63% |
| Double Blade | 61% |
| Bow | 55% |

Le ancore misurate coprono solo il 6-15% del tempo, a seconda della classe.

**Affidabilità di "ultimo punto cliccato" (MISURATO contro le ancore, `validazione_ultimo_click.csv`).**
- **Usato così com'è (metodo A):** errore mediano **285**, 75° percentile 524; solo il 52% delle stime è entro 300.
  - Funziona peggio subito dopo il click (mediana 281 tra 0 e 2 s), perché l'eroe sta ancora camminando.
  - Funziona peggio per le classi a distanza: errore mediano 600 per Bow e 481-484 per Wizard Staff e Naga Trident. Il loro ultimo click è il nemico, non il punto in cui stanno.
- **Correzione con il movimento dell'eroe (STIMATO, metodo B):**
  - si usa la velocità base di 270 (unità base Otch, `UnitBalance.slk`; la mappa non la modifica) e la gittata d'attacco presa dal `war3map.w3u`;
  - per le abilità a terra si assume una gittata di lancio di 600 (**ipotesi**);
  - risultato: errore mediano **131**, 75° percentile 270; il **78%** delle stime è entro 300 e il 93% entro 600;
  - entro 10 s dall'ultimo ordine l'errore mediano è 122. Oltre 30 s sale a 621, per questo le stime più vecchie di 10 s sono state scartate;
  - errore per classe: da 72 (Druid Staff) a 301 (Bow).

**Posizioni utilizzabili (STIMATO).** Mettendo insieme le ancore e il metodo B, si ha una posizione per il 56% (Bow) fino al 93% (War Hammer) del tempo di combattimento. Il 94-99% di queste posizioni cade dentro `ArenaArea`.

### b) Geometria (MISURATO dal `war3map.j`)
- **Arena:** `ArenaArea` va da (-3104, -1088) a (2112, 4160).
- **Spawn** delle truppe, 30 unità per tipo e per giocatore in ciascuno dei tre punti:
  - Est (3840, 1536);
  - Nord (-512, 5888);
  - Ovest (-4864, 1536).
- **Inizio wave:** il trigger `Wave_Start` → `Teleport_Players` porta in `Region_014` (circa (-560, 656), sud-centro dell'arena) le unità che si trovano fuori dall'arena.
- **Aree vietate:** chi entra nelle zone vicine agli spawn (`GladiatorBlock*`, trigger `Prevent_Spawn_Camp`) o nella fontana durante la wave viene teletrasportato e stordito.

### c) Posizione del gruppo (STIMATO, `posizioni_classe.csv`, `posizioni.svg`)
- **Dove sta il gruppo:** le posizioni mediane delle classi cadono tutte tra x -1000 e -140 e tra y 280 e 700, cioè attorno al punto di teletrasporto. Lo spawn più vicino è a 3100-3500 (mediana).
- **Il gruppo resta compatto:** la dispersione mediana (distanza media dal baricentro, con almeno 6 eroi localizzati) è **419**.

**"Fronte" (STIMATO).** È la mediana dei punti cliccati su unità che non sono eroi nei ±5 s; il 99% di questi click cade nell'arena.
"Nemico più vicino" è il bersaglio non-eroe più vicino cliccato da *altri* giocatori nei ±3 s.

| Ruolo | Nemico più vicino (mediana) | Proiezione verso il fronte (mediana; > 0 = davanti al baricentro) |
|---|---|---|
| Tank | 266 | +167 |
| DPS mischia | 400 | +39 |
| DPS distanza | 421 | -26 |
| Support | 500 | -67 |
| Healer | 504 | -150 |

**Distanze tra ruoli:**
- Healer e Tank più vicino: mediana **494**. L'Healer è entro la gittata di Rejuvenation/Innervate (700, letta dal `war3map.w3a`) per il **74%** dei campioni.
- Visti dai Tank: War Hammer e Runeblade hanno l'Healer entro 700 solo per il **58%** e il **56%** del tempo (mediana circa 625).
- DPS distanza e Tank più vicino: mediana 388.
- Distanza tra i due Tank: mediana 622.

**"Dietro al Tank"** = distanza dal fronte meno quella del Tank più vicino. Vale +420 per l'Healer (dietro nel 90% dei campioni), +297 per i DPS distanza (81-86%) e +223 per i DPS mischia.

### d) Per tipo di wave (STIMATO, `metriche_gruppo_tipo_wave.csv`)

| Tipo | Dispersione | Tank-Healer | Healer entro 700 da un Tank | Proiezione Tank / Healer |
|---|---|---|---|---|
| mischia | 378 | 391 | 86% | +113 / -136 |
| distanza | 375 | 492 | 75% | +193 / -149 |
| ibrida | 455 | 523 | 70% | +169 / -161 |

### e) Relazione con danni subiti e HP < 20% (STIMATO, `relazione_danni_hp.csv`)
- **Distanza dal nemico più vicino e quota tank:** correlazione di Spearman **-0,29** tra le classi (n = 10) e **-0,24** per classe × challenge (n = 195). La relazione è debole e nella direzione attesa: chi sta più vicino ai nemici incassa un po' di più.
- **HP sotto il 20% a fine round:** questi 30 casi avevano in mediana il nemico più vicino a **438**, contro 389 negli altri 165. Non c'è segno che chi finisce sotto il 20% fosse più esposto. Il numero è piccolo e lo snapshot è un solo istante.

## 3) Cosa non si può dire e perché
- **La posizione dei nemici è nota solo nei punti cliccati.** Il "fronte" è un indicatore approssimativo:
  - i nemici non cliccati e quelli che attaccano da altri lati non si vedono;
  - le distanze dal nemico sono quindi sovrastimate. Per esempio i DPS mischia risultano a circa 400 dal nemico, ma la loro gittata è 100-140.
- **Le differenze sono vicine all'errore.** Molte differenze tra ruoli (100-200 unità) sono dello stesso ordine dell'errore del metodo B (mediana 131 per eroe, quindi circa 185 sulla distanza tra due eroi). Sono affidabili solo i segni delle differenze grandi: Tank avanti, Healer dietro.
- **Il modello del movimento è semplificato.** Non vede:
  - l'auto-acquisizione dei bersagli (l'eroe fermo insegue i nemici vicini);
  - spinte, stordimenti, rallentamenti e bonus di velocità degli oggetti;
  - le abilità di spostamento (Leap, teletrasporti);
  - la morte dell'eroe.
- **Il terreno non è stato analizzato** (`war3map.w3e`, `.doo`: alture, strettoie, ostacoli). Quindi non si può dire se esistesse un punto migliore.
- **"Ottimale" richiede un termine di paragone** (altre partite o altre disposizioni) e il danno subito momento per momento. Con una sola partita e la multiboard cumulativa questo non c'è.
- **Confini delle challenge 8, 12, 19 e 20 stimati.** Il loro inizio e la loro fine sono stimati (`finestre_combattimento.csv`), quindi i campioni ai bordi di queste finestre possono includere momenti fuori combattimento.

**Cosa servirebbe nella prossima partita:**
- uno strumento che esporti le posizioni reali di eroi e nemici dal replay osservato (per esempio un tracciamento delle unità durante la riproduzione), oppure registrazioni o screenshot della minimappa a intervalli fissi (per esempio ogni 5 s);
- la multiboard (danni subiti e HP) a ogni wave, o meglio più volte per wave;
- in alternativa, un trigger di debug nella mappa che scriva periodicamente le coordinate degli eroi nel log o nella chat.

## 4) Raccomandazioni (solo quelle supportate dai dati)
1. **Mantenere l'impostazione attuale:** combattere al centro-sud dell'arena, con i Tank verso i nemici e Healer e Support dietro. È coerente con i dati e con la geometria (spawn a E/N/W, nessuno a sud).
2. **Tenere i Tank più vicini all'Healer.** Oggi ciascun Tank è fuori dai 700 dell'Healer per circa il 42-44% del tempo, anche perché i due Tank stanno a circa 620 l'uno dall'altro. Due soluzioni possibili:
   - l'Healer si posiziona tra i due Tank;
   - i Tank tengono il fronte più stretto.
3. **Nelle wave ibride stringere il gruppo.** Dispersione 455 contro circa 375, Healer-Tank 523 contro 391 nelle wave mischia. Un punto di raduno concordato prima della wave (per esempio un ping sul punto di teletrasporto) può aiutare. L'efficacia è un'ipotesi da verificare.

## 5) Grado di fiducia
- **Medio** sulla ricostruibilità. La copertura e l'errore sono misurati contro posizioni reali (le ancore). Le ancore però sono ordini di cura e di supporto: sono più frequenti attorno agli eroi in difficoltà e potrebbero non rappresentare tutti i momenti.
- **Medio-basso** sui confronti di posizione tra ruoli. Le differenze sono stimate e vicine all'errore; sono solidi solo Tank avanti e Healer dietro.
- **Basso** sul giudizio "ottimale" e sul legame con i danni. Non c'è un termine di paragone, i nemici sono localizzati solo dove sono stati cliccati e la correlazione è debole.
