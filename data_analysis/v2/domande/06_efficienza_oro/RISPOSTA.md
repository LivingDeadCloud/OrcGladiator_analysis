# Domanda 06: i soldi sono spesi in maniera efficiente?

Script: `analisi_efficienza_oro.py`, da lanciare dalla cartella del progetto. Tutti i file citati sono in questa cartella.

## 1) Risposta breve

**In parte.** Alla fine quasi tutto l'oro è stato speso: alla sconfitta restano 712 ori su circa 31.600 guadagnati dalla squadra (2,3%), e i prestiti hanno spostato oro verso chi stava comprando. Tutti i prestiti risultano restituiti.
La spesa però arriva **tardi**. Dopo ogni round restavano in media circa 270 ori per classe inutilizzati, cioè più dell'oro di un round intero. I tomi di statistiche (110 oro) si possono comprare dal livello 12 (circa minuto 57), ma quasi tutte le classi hanno comprato il primo solo al minuto 90, dopo la challenge 18: in media 29 minuti di attesa con 200-700 ori fermi.
Il bilancio ricostruito spiega bene l'inizio della partita. Dopo spiega l'oro misurato solo in modo approssimativo (scarto mediano 42 ori per classe e per round), quindi i valori per singola classe sono indicativi.

## Criteri di "efficienza" usati (definiti per questa analisi)

1. **Oro mai usato**: oro rimasto alla sconfitta, rispetto alle entrate.
2. **Oro fermo**: oro a fine round e tempo medio di permanenza dell'oro prima della spesa.
3. **Spesa sprecata**: acquisti ridondanti e perdite sui cambi di stivali.
4. **Uso del pool di squadra**: prestiti -loan/-borrow, chi presta a chi, se sono restituiti.
5. **Meccaniche che premiano tenere o spendere l'oro**: interessi, token, voto, Goldstrike.

Non c'è un riferimento assoluto: un oggetto da 1.000-1.250 oro richiede di risparmiare per diversi round, e questo non è uno spreco. Per questo l'"oro fermo" va letto insieme a cosa è stato comprato dopo.

## 2) Evidenze

### Meccanica dell'oro: MISURATA dal codice (`data_map/raw/war3map.j`)

**Entrate a fine challenge c:**

| Voce | Quanto | Chi la riceve | Fonte nel codice |
|---|---|---|---|
| Vittoria | 10·c | tutti | `Run_Reward` |
| Voto | vittoria × {A+ 1; A 0,75; B 0,5; C 0,4; D 0,3; E 0,2; F 0,1; G 0} | tutti | `Run_Reward` |
| Migliore del round | int(2,5·c) | il migliore di danni, tank, boss e cure | `Get_MVP_Current_Round` |
| Scavenger | 2·c | tutti, dalla challenge 7 (talento di squadra) | `End_of_Round_Effects`, `rounds.csv` |
| Token | +60 / +180 / +480 dopo 2 / 3 / 4 round se non si muore | chi ha il token | `End_of_Round_Effects` |
| Goldstrike | +10·c | chi ha l'oggetto | `End_of_Round_Effects` |
| Ricompensa a scelta | +25 o +50 | chi la sceglie, dopo le challenge 12 e 19 | `stat_choices.csv` |

**Assenti:**
- Nessun interesse sull'oro: non esiste un trigger che lo calcoli.
- Nessuna taglia sulle uccisioni: `PLAYER_STATE_GIVES_BOUNTY` non compare mai.
- Tenere oro non rende nulla.

**Prestiti:**
- `-borrow N`: N al massimo di 4 cifre. Una sola richiesta aperta alla volta, che scade in 15 s. È rifiutata se si hanno già 2.500 ori di debito.
- `-loan`: dà tutto il proprio oro, fino al residuo della richiesta.
- **Rimborso** (`Repay_Loans`): parte da solo a ogni fine round (subito dopo l'oro del voto) e a ogni inizio round. Il debitore paga tutto l'oro che ha finché il debito non è estinto. Un prestito è quindi un anticipo sulle entrate successive.
- Chi ha Goldstrike non può prestare né chiedere prestiti.

**Prezzi:**
- I prezzi vengono da `war3map.w3t`, campo `igol`. Per 2 oggetti senza prezzo nella mappa ho usato quello di default del gioco: 400 per gli oggetti di base `belv` (da `ItemData.slk` di War3Patch.mpq).
- I **talenti** costano punti talento (lumber, `ilum`=1), **non oro**: la spesa in oro per i talenti è 0.
- Le **pozioni** sono oggetti riutilizzabili con cooldown di 40 s, non consumabili.
- I tomi sotto il livello 12 vengono rimborsati.
- Cambiando stivali si recupera il 75% del prezzo dei vecchi.

### Validazione della ricostruzione: STIMATA (`validazione_oro_screenshot.csv`, `validazione_sintesi.csv`)

**Metodo.** Ho simulato in ordine di tempo tutti gli ordini di acquisto, i comandi -borrow/-loan e le entrate di ogni round. A ogni screenshot l'oro simulato viene riallineato a quello misurato. Lo scarto è quindi l'errore del singolo intervallo tra due screenshot.

**Risultati:**
- Challenge 1: scarto **0 per tutte le 10 classi**. Le regole sulle entrate sono confermate e l'oro iniziale è 0.
- Su tutti i 190 confronti di fine round:

| | Valore |
|---|---|
| Confronti esatti | 33 |
| Entro ±25 ori | 76 |
| Scarto assoluto mediano | 42,5 ori |
| Scarto assoluto medio | 79 ori |
| Scarto massimo | 611 ori |

- La somma degli scarti della squadra è −4.773 ori. C'è cioè **circa il 15% di uscite che la simulazione non vede**: forse acquisti non registrati come ordine `I0..`, vendite, morti con token, o prezzi diversi da quelli del file.
- Indizio sui prezzi (IPOTESI):
  - Diverse classi chiedono in prestito esattamente quanto basta per arrivare a 25 oro (Survival Treads, listino 50) o a 75 oro (Wizard's Potion, listino 100).
  - 7 acquisti di pozioni che la simulazione rifiuta per oro insufficiente sono invece seguiti dall'uso della pozione (`acquisti_rifiutati_simulati.csv`), quindi sono riusciti.
  - Con i prezzi "osservati" lo scarto mediano scende a 38 ori.
  - Non ho trovato nel codice la causa di questo sconto.
- Il voto delle challenge 8 e 12 non è visibile negli screenshot. Ho scelto il voto che riduce lo scarto: A per la 8, A+ per la 12 (`stima_voto_ch8_ch12.csv`). È una STIMA.

### Entrate e uscite per classe: STIMATE (`bilancio_oro_classi.csv`, `bilancio_oro_ruoli.csv`)

**Entrate:** da 2.996 (War Hammer) a 3.554 (Claws) ori a testa.
- 1.900 dalla vittoria, 734 dal voto e 338 dallo scavenger sono uguali per tutti.
- La differenza viene dal premio "migliore del round": Claws 582, Druid Staff 371, War Drums 0.

**Uscite stimate, 26.032 ori in totale per la squadra:**

| Categoria | Oro | Quota |
|---|---|---|
| Reliquie e artefatti permanenti | 12.225 | 47% |
| Tomi | 8.580 | 33% |
| Stivali, al netto dei rimborsi | 3.997 | 15% |
| Pozioni | 400 | 1,5% |
| Token, evocazioni, Hex | 830 | 3% |
| Talenti | 0 (si pagano in punti talento) | — |

- Per ruolo (media per classe): i DPS mischia spendono di più (3.127), i Tank di meno (2.285).

### Oro mai usato: MISURATO (screenshot)

- **Dopo la challenge 19**, prima del boss: 3.692 ori nella squadra. War Hammer ne ha 912.
- **Durante il boss e alla sconfitta**: 712 ori, il 2,3% delle entrate.

| Classe | Oro rimasto | % delle sue entrate |
|---|---|---|
| Bow | 365 | 11,5% |
| Wizard Staff | 93 | 3% |
| Runeblade | 90 | 3% |
| Claws | 89 | 2,5% |
| War Drums | 75 | 2,5% |
| Altre 5 classi | 0 | 0% |

Bow è l'unica classe che non ha mai comprato tomi.

### Oro fermo

- **Oro a fine round** (MISURATO): media per classe da 136 (Bow) a 362 (Pickaxe), circa 270 in media. Picchi di 1.228 (War Drums) e 1.261 (Pickaxe).
  - Per confronto, l'entrata media di un round è circa 165 ori a testa.
- **Tempo medio di permanenza dell'oro** (STIMATO): calcolato come saldo medio diviso per entrate al secondo (legge di Little). Va da 192 s (Double Blade) a 360 s (Wizard Staff). Un ciclo round + pausa dura circa 300 s, quindi l'oro resta fermo in media circa un round.
  - Il ritardo FIFO (500-1.750 s) è solo indicativo: è falsato dai prestiti.
- **Tomi** (`tomi_attesa.csv`): sono disponibili dal livello 12, cioè dallo screenshot a 3.418 s o a 3.660 s secondo la classe. Il primo tomo arriva:
  - a 4.861 s per Claws;
  - tra 5.396 e 5.735 s per tutte le altre classi;
  - mai per Bow.
  - L'attesa va da 1.200 a 2.300 s, cioè 20-38 minuti. Nel frattempo l'oro a fine round era in media da 249 (Double Blade) a 736 (Pickaxe), e 627 per War Drums.
  - In parte era risparmio per reliquie, comprate davvero in quella finestra (per esempio Pickaxe: Warrior's Spirit da 1.250 a 4.300 s). Per le altre classi una parte di quell'oro poteva diventare +2 alle statistiche già 6-8 round prima.

### Prestiti: STIMATI (`prestiti.csv`, `prestiti_per_ruolo.csv`)

- **Volume**: 101 prestiti per circa 7.990 ori. Gli importi sono simulati, perché la chat registra i comandi ma non le cifre trasferite.
- **Chi presta di più**: Druid Staff (Healer) 2.297, War Drums (Support) 1.726, Pickaxe 1.456.
- **Chi chiede di più**: Double Blade 2.194, Bow 1.765, War Hammer 1.105.
- **Per ruolo**: Healer e Support prestano molto e ricevono poco. War Drums ha ricevuto 21 ori in tutta la partita.
- **Restituzione**: nella simulazione **tutti restituiti**, con durata mediana di 108 s, cioè entro l'inizio o la fine del round successivo. È coerente con il rimborso automatico, che non lascia scelta.
- **Comandi senza effetto**: diversi comandi erano scritti male ("-borroe", "-oan", "-loam", "-borrow 5000000" oltre le 4 cifre, "-borrow loan").

### Spesa ridondante: STIMATA (`acquisti_ridondanti.csv`)

- **Cambi di stivali**: 6 classi passano da Survival Treads a stivali migliori, e il Druid Staff li cambia due volte. La perdita è il 25% del prezzo vecchio: 13-57 ori per classe, circa 120 in totale. È trascurabile.
- **Ordini doppi**:
  - Double Blade ha 2 ordini di Tank's Potion nello stesso secondo. Le pozioni condividono il cooldown (gruppo A02E), quindi una seconda copia non serve. Probabilmente il secondo ordine è stato rifiutato.
  - Double Blade ha anche 2 Spiked Collar (evocazione, 25 ciascuno): non necessariamente uno spreco.
- **Oggetti Unique**: nessuna classe ne ha comprato due copie.

### Meccaniche che premiano tenere o spendere

- **Voto** (MISURATO): il voto paga fino al 75-100% dell'oro di vittoria per i round veloci. La squadra ha preso 734 ori di voto a testa. Con tutti A ne avrebbe presi 1.425 (STIMA). Non si può dire quanto la spesa abbia inciso sulla velocità dei round.
- **Token** (scommesse): solo Bow ne ha comprato uno, il Contender's Token da 30, che rende +60 se si sopravvive 2 round. Il pagamento è un'IPOTESI, perché le morti non sono nel replay.
- **Goldstrike** (800 oro, +60 danni): raddoppia l'oro di vittoria. Comprato a fine challenge k rende 10·(k+1) + … + 10·19 (STIMA).
  - Si ripaga entro la challenge 19 solo se comprato entro la fine della 14.
  - Comprato presto (per esempio dopo la 8) renderebbe circa 1.540 ori a fronte di 800.
  - Nessuno l'ha comprato.

## 3) Cosa non si può dire e perché

- **Il saldo esatto per classe**: il replay non registra l'oro. Con lo scarto mediano di 42 ori, e un 15% di uscite non spiegate, il bilancio per singola classe è indicativo. Solo l'oro degli screenshot è una misura certa.
- **Se un ordine di acquisto è riuscito**: un ordine senza oro sufficiente viene rifiutato dal gioco ma resta nel replay. La simulazione segnala 27 ordini "rifiutati", ma almeno 7 sono riusciti, perché la pozione viene poi usata.
- **Il prezzo effettivo pagato**: c'è un indizio di sconti non trovati nel codice. Non verificato.
- **Il valore di ciò che si è comprato**: se una reliquia ha reso più di N tomi, o se comprare prima avrebbe evitato la sconfitta. Mancano danni e cure per oggetto: non determinabile.
- **Vendite di oggetti e morti** (che fanno perdere i token): non sono nel replay.
- **I round 8, 12 e 19**: voto e/o migliori del round non sono visibili, quindi le loro entrate sono stimate.

**Cosa registrare nella prossima partita:**
- uno screenshot della multiboard (con l'oro) **all'inizio e alla fine di ogni round**, non solo alla fine;
- lo screenshot del riepilogo dei round 8, 12 e 19;
- se possibile, il log dei messaggi "loaned X gold" e "You paid X gold" (screenshot della chat dopo i prestiti);
- l'inventario di ogni eroe a fine partita.

## 4) Raccomandazioni per il gruppo

1. **Comprare i tomi appena si arriva al livello 12**, con l'oro che altrimenti resta fermo tra un round e l'altro. Supportato: 20-38 minuti di attesa, con 250-700 ori a fine round in media.
2. **Non arrivare al boss con oro in tasca**: Bow aveva 365 ori, l'11,5% delle sue entrate, mai spesi. Prima del round 20 conviene spendere o prestare tutto.
3. **Valutare Goldstrike presto** (entro la challenge 8-10) su un DPS che non ha bisogno di prestiti. È un calcolo dalla mappa, non provato in partita: blocca -loan e -borrow.
4. **Continuare a usare i prestiti per raggiungere le reliquie costose**: funzionano e si restituiscono da soli. Ma scrivete i comandi esatti: `-borrow N` con al massimo 4 cifre, e `-loan`.
5. **Healer e Support** hanno fatto da "banca": hanno prestato circa 4.000 ori e ricevuto poco. Il gruppo può decidere se è voluto. Il Support ha speso solo 375 ori in reliquie.

## 5) Grado di fiducia

- **Medio-alto** su:
  - meccanica delle entrate e dei prestiti (codice della mappa, verificata esatta sulla challenge 1);
  - oro rimasto a fine round e alla sconfitta (misurato);
  - tempi degli acquisti (replay).
- **Medio-basso** su:
  - bilancio per singola classe;
  - importi dei prestiti;
  - ripartizione della spesa per categoria.

  Sono ricostruzioni con scarto mediano di 42 ori e circa 15% di uscite non spiegate.
- **Basso** su cosa sarebbe successo spendendo diversamente (efficacia degli oggetti): non determinabile con questi dati.
