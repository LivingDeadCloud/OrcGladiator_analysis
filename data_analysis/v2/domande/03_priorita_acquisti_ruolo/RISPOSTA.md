# Domanda 03: ha senso far acquistare prima gli oggetti a healer, tank o DPS?

Script: `analisi_priorita_acquisti.py`. Si lancia dalla cartella del progetto:
`python data_analysis/v2/domande/03_priorita_acquisti_ruolo/analisi_priorita_acquisti.py`.
Legenda: **[M]** = misurato, **[S]** = stimato (il metodo è indicato), **[C]** = letto nel codice della mappa (`war3map.j`, `war3map.w3t`), **[R]** = ragionamento (non è una prova).

## 1. Risposta breve

**Verdetto: in parte. Il controfattuale non è determinabile.** Con una sola partita non si può dimostrare che un altro ordine di acquisto avrebbe cambiato l'esito. Esiste un solo modo per fare un esperimento controllato: rigiocare.
La meccanica della mappa dà però un argomento solido. L'oro arriva quasi tutto in parti uguali a tutti, e **l'unica entrata che il team può aumentare dipende dalla velocità con cui chiude il round** (bonus del voto e punteggio per l'upgrade delle armi). Cure e tanking non danno oro extra. Quindi la priorità con più ritorno sono i danni, **dopo** due prerequisiti economici: un oggetto di mana economico per l'Healer (il suo mana a fine round è stato molto basso fino alla challenge 9) e gli oggetti difensivi a **chi prende davvero i colpi**, che in questa partita non erano i due Tank.
Ordinare gli acquisti per etichetta di ruolo ("prima l'healer", "prima i tank") non trova sostegno nei dati.

## 2. Evidenze

### 2.1 Da dove viene l'oro (meccanica, [C])
- **Fine round** (`Trig_Run_Reward`, con N = numero della challenge, perché `CurrentWave-1 = N`), uguale per tutti i 10 giocatori:
  - vittoria: **10·N**;
  - **bonus del voto**: una frazione di 10·N che dipende solo dai secondi del round. A+ ≤40 s = 100%, A ≤80 s = 75%, B ≤120 s = 50%, C ≤160 s = 40%, D ≤200 s = 30%, E ≤240 s = 20%, F ≤280 s = 10%, G = 0%.
  - Il voto aggiunge anche punteggio all'upgrade delle armi dell'intero team: +0,5 per A+, +0,3 per A, +0,1 per B.
- **Premi individuali** (`Trig_Get_MVP_Current_Round`): **R2I(2,5·N)** ciascuno al migliore per danni, tank, danni al boss e cure del round. Valgono poco: per esempio 47 oro alla challenge 19.
- **Scavenger** (`End_of_Round_Effects`): (N)·2 a **tutti**, attivato da un livello o talento del Pickaxe; secondo `rounds.csv` è attivo dalla challenge 7.
- **Non esistono taglie sulle uccisioni**: in `war3map.w3u` le bounty delle unità sono 0 e nessun trigger dà oro per le uccisioni.
- I tomi (110 oro) richiedono il livello 12, altrimenti il trigger `Tomes_Buy` li rimborsa. Gli stivali nuovi rimborsano il 75% di quelli vecchi (`Boots_Upgrade`, `BootCostReturnFactor = 0.75`).
- **Conseguenza [C+S]:** le entrate stimate fino alla challenge 19 vanno da **2.900 a 3.460 oro per giocatore** (`bilancio_oro_classe.csv`). La differenza tra giocatori viene solo dai premi individuali.
- **Nessun ruolo "guadagna" più oro degli altri.** Decidere chi compra prima vuol dire solo **spostare nel tempo** oro che arriva a tutti in modo uguale.

### 2.2 Prestiti -borrow / -loan (meccanica [C], eventi [M], esito [S])
- **Come si chiede.** `-borrow X` apre una richiesta, una alla volta, valida 15 s. Non si può chiedere se il proprio debito totale è ≥ 2.500, salvo alla wave 20.
- **Come si presta.** `-loan` senza importo dà **tutto l'oro necessario**, fino a tutto quello che ha chi presta. Il debito si registra in una tabella hash.
- **Come si restituisce.** **Automaticamente**: `Repay_Loans` gira all'inizio di ogni wave (`Wave_Start`) e dopo la ricompensa. Il debitore paga con tutto l'oro che ha finché il debito non è estinto.
- Il prestito quindi **anticipa un acquisto di circa un round**. È lo strumento con cui il gruppo può davvero decidere chi compra prima.
- **In partita** (`prestiti.csv`) ci sono state **24 richieste**:

| Chi ha chiesto | Richieste | Oro richiesto in totale |
|---|---|---|
| DPS distanza | 10 | 2.034 |
| Tank | 6 | 1.706 |
| DPS mischia | 5 | 1.535 |
| Healer | 3 | 553 |
| Support | 0 | 0 |

- Il primo `-loan` è arrivato più spesso da DPS mischia (8 volte), Healer e Support (5 ciascuno).
- **In 19 casi su 24 il richiedente compra un oggetto entro 20 s** [M]. Esempi:
  - Double Blade: 500 → Ethereal Armour (850) prima della challenge 7;
  - War Hammer: 600 → Petrified Bark (700) prima della 10;
  - Healer: 400 → Flag of Victory (1.250) prima della 16;
  - Naga Trident: 500 → Bonecarver Necklace (1.000) prima della 17;
  - Bow: 500 → Feral Visage (900) prima della 18.
- **Limite:** gli importi davvero trasferiti dipendono dall'oro di chi presta in quel momento, che non è registrato. L'esito è "coperto" solo se chi presta aveva oro sufficiente [S].

### 2.3 In che ordine i ruoli hanno speso ([M] ordini di acquisto, costi da `war3map.w3t`)
- **Spesa netta totale stimata: 31.900 oro.**

| Ruolo | Oro per giocatore | Già speso entro la ch. 9 | Entro la ch. 13 |
|---|---|---|---|
| Tank | 3.109 | 20% | 47% |
| Healer | 3.647 | 8% | 39% |
| Support | 2.468 | 6% | 21% |
| DPS mischia | 3.624 | 20% | 41% |
| DPS distanza | 2.906 | 12% | 32% |

- **Primo oggetto da ≥400 oro:**
  - Tank: War Hammer Heartstone alla ch. 6, Runeblade Heartstone alla ch. 8;
  - DPS mischia: Double Blade Ethereal Armour alla ch. 7, Claws Ring of Superiority alla ch. 8, Pickaxe Refresh Stone alla ch. 11;
  - Healer: Slippers of Focus alla ch. 10 (+300 mana max, +100% regen), Pipe of Insight alla ch. 12;
  - DPS distanza: ch. 11 (Wizard Staff, Naga Trident), Bow solo alla ch. 13;
  - Support: ch. 15.
- **Ordine reale:** Tank ≈ DPS mischia → DPS distanza ≈ Healer → Support.
- I primi grandi acquisti sono stati quasi tutti **difensivi o di statistiche**. Gli oggetti di puro danno sono arrivati tutti dalla challenge 16 in poi:
  - Warrior's Spirit;
  - Flag of Victory (+50% danni a tutti gli alleati, comprata dall'Healer);
  - Bonecarver Necklace;
  - Feral Visage.
- **Verifica del bilancio [S].** Ho confrontato entrate (codice + `rounds.csv`) − spesa (ordini) con l'oro letto negli screenshot.
  - Lo scarto mediano per classe va da 25 a 350 oro, con un massimo di circa 860.
  - Gli ordini di acquisto sono quindi un'approssimazione credibile, ma non esatta.
  - Lo scarto si spiega con le scelte di fine round con opzione oro (registrate solo dopo le challenge 12 e 19), con i prestiti non ancora chiusi, con eventuali acquisti falliti e con le vendite.

### 2.4 Colli di bottiglia nelle wave difficili (`colli_bottiglia_challenge.csv`)

**Round lenti = oro perso [C+M].** Rispetto al voto A+, il team ha perso circa **12.600 oro in totale** (circa 1.260 a testa, il 40% di quanto ha speso). I voti delle challenge 8 e 12 sono stimati.
- Le perdite maggiori:
  - challenge 18 (G, 432 s): 1.800;
  - challenge 19 (D): 1.330;
  - challenge 16 (E): 1.280;
  - challenge 15 (E): 1.200;
  - challenge 9 (G, 428 s): 900.
- **Un voto in più in ogni round vale circa 1.900–2.500 oro di team** in tutta la partita (circa 190–250 a testa) [S].

**I round lenti sono anche quelli in cui gli eroi cadono [M].**
- Eroi con HP ≤ 20% a fine round:
  - ch. 15: 8;
  - ch. 13: 6;
  - ch. 5 e ch. 18: 4 ciascuna;
  - ch. 9: 3.
- Per ruolo: **DPS distanza 13**, DPS mischia 8, Tank 3, Healer 3, Support 3.
- **Probabili rianimazioni** (HP ≤ 25% e mana ≤ 125, cioè i valori di ripristino del trigger) [S]: il **Bow in 8 round** e il Naga Trident in 5. Il Bow è anche la classe che ha speso meno (2.618) e ha comprato più tardi il primo oggetto grande.
- **Non si può dire** se il round è lento perché gli eroi muoiono o se gli eroi muoiono perché il round dura troppo.

**I tank non tankano [M, scorporo S].**
La colonna "tank" della multiboard conta i **colpi presi**, non i danni, e include i colpi presi dalle unità evocate (`colpi/NOTE.md`). Qui si usano i colpi del solo eroe.
- La quota di colpi degli eroi Tank scende così:
  - 57% nelle challenge 1–2;
  - 1,5–8,5% nelle challenge 13–14;
  - 26,5% sul totale della partita.
- Gli eroi DPS mischia ne prendono il 48,6% (fino al 70% in un round). Claws e Double Blade, al netto di lupi e portali, prendono più colpi dei due Tank: 20% e 27,6% al boss finale, contro il 13–14% di ciascun Tank.
- I Tank hanno speso come gli altri, soprattutto in oggetti difensivi. Più equipaggiamento difensivo ai Tank **non** ha spostato i colpi su di loro.

**Mana dell'Healer [M, rapporto S].**
- Mana a fine round nelle challenge 1–9: mediana **76** (circa l'11% del massimo stimato).
- Dalla challenge 10 (dopo Slippers of Focus) e dalla 12 (dopo Pipe of Insight), esclusi i round con probabile rianimazione: mediana **circa 800** (circa il 70%).
- Nello stesso passaggio la quota di cure del round sale in media da 33% (ch. 1–9) a 39% (ch. 10–19) [S, con altri fattori in gioco: livello, oggetti degli altri].

**Sconfitta al boss finale.**
- Allo snapshot a metà boss, gli eroi Tank hanno preso il 27% dei colpi e gli eroi DPS mischia il 48%.
- Gli HP del boss e la causa della sconfitta **non** sono nei dati.

### 2.5 Quote prima e dopo gli acquisti grandi (`effetto_acquisti_grandi.csv`, [S] molto incerta)
Per ciascuno dei 26 acquisti ≥400 ho confrontato la media dei 3 round prima con quella dei 3 round dopo: 14 salgono, 11 scendono, 1 resta uguale.

| Oggetto (classe) | Metrica | Prima → dopo |
|---|---|---|
| Shard of the Revenant (Claws) | danni | 23% → 40% |
| Warrior's Spirit (Pickaxe) | danni | 11% → 22% |
| Pipe of Insight (Healer) | cure | 33% → 42% |
| Ethereal Armour (Double Blade) | danni | 2% → 10% |
| Illuminators (Runeblade) | colpi presi (eroe) | 13% → 5% |
| Heartstone (Runeblade) | colpi presi (eroe) | 21% → 12,5% |

- Le variazioni maggiori riguardano oggetti da danni o da cura.
- Gli oggetti difensivi dei Tank non aumentano la loro quota di colpi presi.
- Sono quote a somma 100: ogni acquisto degli altri le modifica. **Non sono effetti causali.**

## 3. Cosa non si può dire, e perché
- **Il controfattuale.** Non si sa cosa sarebbe successo con un altro ordine di acquisto: c'è una sola partita, ogni classe è un solo giocatore e manca un gruppo di confronto.
- **Il valore di ogni oggetto in danni, cure o HP salvati.** Il replay contiene comandi, non effetti, e le quote della multiboard sono relative (a somma 100).
- **Chi è morto davvero e quando.** Le morti non sono nel replay: c'è solo una stima dagli HP e dal mana negli screenshot.
- **La causa dei round lenti.** Non si separano danni insufficienti da morti o disposizione in campo. Non sono noti gli HP dei boss né le ricerche `R0xx` date ai nemici.
- **Gli importi esatti dei prestiti e l'oro istante per istante.** L'oro si vede solo in circa 20 screenshot. Il bilancio non chiude: scarti fino a circa 860 oro.
- **Il costo di due oggetti.** Charm of Protection e Corrosive Oil non hanno il campo `igol` nella mappa.
- **Cosa registrare la prossima volta:**
  - screenshot della multiboard **prima e dopo la fase negozio** (oro);
  - il testo dei messaggi di sistema (voto, "loaned X gold", "You paid X", premi), per esempio con un replay salvato insieme al log della chat dei messaggi di gioco;
  - le scelte di ricompensa di **ogni** round;
  - le morti, segnate a mano o tramite i messaggi di rianimazione.
  - Per un vero confronto servono **due partite o più** con la stessa composizione e ordini di acquisto diversi (per esempio "danni prima" contro "difesa prima"), confrontando secondi per round e voti.

## 4. Raccomandazioni per il gruppo
Sono basate sulla meccanica verificata e sulle osservazioni. Non sono prove causali.

1. **Usare i prestiti in modo deliberato.** Il meccanismo li restituisce da solo al round dopo, quindi concentrare l'oro su un oggetto grande costa al team solo un round di attesa. Il gruppo lo ha già fatto (19 prestiti su 24 seguiti da un acquisto); conviene **decidere prima a chi**.
2. **All'Healer un oggetto di mana economico subito.** Per esempio Thinking Sandals (175) o Slippers of Focus (500), invece che alla challenge 10. Il suo mana a fine round era circa all'11% del massimo fino alla challenge 9 [M], e il costo è basso [R].
3. **Poi danni, preferendo gli oggetti che aiutano tutto il team.** Per esempio Flag of Victory (+50% danni a tutti) o Illuminators (−6 armatura ai nemici vicini), assegnati ai DPS principali. È l'unico investimento con un ritorno in oro (voto) e in upgrade delle armi [C]. Nei round in cui si è passati da E/G a C, il guadagno è circa 0,2–0,3 × 10·N oro per ciascun giocatore [C].
4. **L'equipaggiamento difensivo va a chi prende davvero i colpi.** In questa partita erano Claws e Double Blade, non l'etichetta "Tank". Il Bow, che probabilmente è caduto in 8 round, è il candidato più chiaro per un primo oggetto difensivo [M+R].
   - In alternativa i Tank devono attirare i nemici: il Defender's Buckler da 100 ha Taunt [C]. Il Runeblade lo ha comprato alla challenge 6, ma la quota dei Tank è scesa lo stesso [M].
5. **Non lasciare oro fermo prima del boss.** Allo snapshot del boss il Bow aveva 365 oro non spesi [M].

## 5. Grado di fiducia
- **Alto** sulla meccanica: oro, voti, prestiti, rimborsi. È letta direttamente nel `war3map.j`.
- **Medio** sulla cronologia degli acquisti e sulla spesa per ruolo. Gli ordini sono misurati, ma il bilancio dell'oro ha scarti di centinaia di oro: alcuni ordini potrebbero non essere andati a buon fine.
- **Basso** su ogni affermazione causale: quale ordine di acquisto avrebbe vinto, e l'effetto dei singoli oggetti. C'è una sola partita, un giocatore per classe e quote relative confuse da molti fattori.

## File prodotti
| File | Contenuto |
|---|---|
| `analisi_priorita_acquisti.py` | Script che genera tutti i CSV. |
| `acquisti_cronologia.csv` | Ogni ordine di acquisto: tempo, challenge, classe, ruolo, oggetto, categoria, costo e costo netto (rimborsi di tomi e stivali), effetto dalla descrizione. |
| `spesa_ruolo_per_challenge.csv` | Oro speso per ruolo prima di ogni challenge, cumulato e percentuale. |
| `spesa_classe_riepilogo.csv` | Spesa per classe, suddivisa per tipo, e acquisti grandi. |
| `prestiti.csv` | Richieste -borrow, primo prestatore, esito stimato. |
| `bilancio_oro_classe.csv` | Entrate stimate, spesa e oro osservato con residuo, per classe e challenge. |
| `colli_bottiglia_challenge.csv` | Per challenge: voto, oro perso rispetto ad A+, eroi ≤20% HP per ruolo, quote di tank, cure e danni, mana dell'Healer, spesa prima del round. |
| `effetto_acquisti_grandi.csv` | Quota del ruolo nei 3 round prima e dopo ogni acquisto ≥400 (stima). |
