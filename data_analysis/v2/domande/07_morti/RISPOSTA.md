# Domanda 07 – Ci sono giocatori che muoiono troppo?

Script: `analisi_morti.py`. Si lancia dalla cartella del progetto con `python data_analysis/v2/domande/07_morti/analisi_morti.py`. Usa solo la libreria standard e verifica che nei file prodotti non ci siano nomi di giocatori.

## 1) Risposta breve

**Verdetto: sì, in parte.** Il **Bow (DPS distanza)** muore molto più degli altri. Ha 9 morti ricostruite con certezza alta in **8 round su 19**, contro una media del team di 3,9. È rimasto a terra almeno **1.130 s**, circa il 35% del tempo di combattimento. Subito dopo vengono il **Naga Trident (DPS distanza, 7)** e il **Druid Staff (Healer, 6)**. Il ruolo DPS distanza nel complesso muore il doppio della media.

Il conteggio è un **limite inferiore**: il replay non registra le morti. Le morti seguite da una rianimazione rapida, o una seconda morte nello stesso round, possono sfuggire. I numeri esatti quindi **non sono determinabili**, ma la classifica tra le classi è solida.

## 2) Evidenze

### A. Cosa fa la mappa quando un eroe muore (MISURATO dal codice, `meccanica_morte_mappa.csv`)

- **Alla morte.** Il trigger `Create_Corpse` nasconde l'eroe (`ShowUnitHide`) e al suo posto crea un cadavere in pausa e non selezionabile. Da morto il giocatore **non può dare ordini**: nel replay restano solo le selezioni. Per esempio, nella challenge 18 i 6 eroi morti hanno 0 ordini e 3–153 selezioni in 325 s.
- **Fine round.** `Wave_Finish` chiama `Revive_Players` circa 4 s dopo la fine del round: ogni cadavere torna in vita al **10% HP e 75 mana**. Da qui la "firma" negli screenshot: coppie identiche come 17%/86, 12%/91, 16%/114.
- **Durante il round.** L'unica rianimazione usata in questa partita è la **Pietra Ancestrale** (oggetto I06J "Ancestral Strength", gratuito):
  - costa 100 mana alla pietra, che ne guadagna 1/s solo durante il round (massimo 300) e torna a 0 a fine round;
  - rianima **un eroe caduto a caso** con HP e mana pieni.
- **Rianimazioni non usate.** Nel replay non ci sono acquisti o usi di Grand Scroll of Life (I03A), Soulstone, Revival Draught o Ancient's Sap, né ordini `animatedead` (abilità A04B, A0E0, A00I).
- **Sconfitta.** Quando nessun gladiatore è vivo parte un conto alla rovescia di 25 s.
- **Penalità.** L'unica penalità per la morte è la perdita dei token-scommessa (I056–I058).
- **Contatore di morti: non esiste.** La multiboard non ha una colonna morti, `udg_IsPlayerHeroDead` non viene mai messo a `true` e `udg_DeathEvent` serve solo al sistema di cure.

### B. Come è costruito l'indicatore di morte

| Indizio | Fonte | Certezza assegnata |
|---|---|---|
| Firma di rianimazione nello screenshot (HP ≤ 25%, mana ≤ 150), valori identici a quelli di altri eroi | screenshot (misurato) | alta |
| Firma singola + nessun ordine per ≥ 20 s prima della rianimazione di fine round (stimata) | screenshot + replay | alta (sotto i 20 s: media) |
| Silenzio di ordini ≥ 30 s che finisce esattamente alla rianimazione di fine round, HP ≤ 35% | replay + screenshot | alta se ≥ 60 s, altrimenti media |
| Silenzio che finisce 0,5–10 s dopo un'attivazione **riuscita** della pietra (mana della pietra simulato) | replay + codice (stimato) | alta se ≥ 30 s e unico candidato, altrimenti media |
| Silenzio ≥ 30 s senza altri indizi | replay | bassa (non conteggiato) |

**Istante reale di fine round** (`ritardo_screenshot_round.csv`, STIMATO): lo screenshot arriva in mediana **9,4 s** dopo la fine del round. Il valore è misurato in 9 round, dal primo ordine dato dagli eroi rianimati.

**Pietra Ancestrale** (`pietra_ancestrale.csv`):
- 23 tentativi, di cui 10 riusciti secondo la simulazione.
- Nella challenge 9 tutte e 3 le attivazioni riuscite sono seguite, entro 3,5–4,3 s, dal ritorno ai comandi di un eroe silenzioso da 94–301 s. È la conferma che il metodo funziona.
- I 7 tentativi fatti a meno di circa 100 s dall'inizio del round falliscono per mana insufficiente della pietra.

**Calibrazione della soglia di silenzio** (`calibrazione_soglia_silenzio.csv`). I casi certi sono le 18 morti con firma identica a quella di altri eroi.

| Soglia di silenzio | Morti certe catturate | Silenzi non spiegati | Probabilità di coincidenza con la pietra (finestra 10 s) |
|---|---|---|---|
| 30 s | 100% | 1,8 per ora-eroe | 4,6% |
| 15 s | 100% | 10,4 per ora-eroe | 24% |
| 60 s | 94% | 0,1 per ora-eroe | 0,3% |

Per questo i silenzi di 15–30 s abbinati alla pietra hanno certezza solo media.

### C. Morti per classe, challenge 1–19 (`morti_per_classe.csv`; morti certezza alta + media)

| Classe | Ruolo | Morti (alta + media) | Round con morte / 19 | Tempo da morto min. (s) | Rispetto alla media del team (3,9) | p (Poisson, ≥ k) |
|---|---|---|---|---|---|---|
| **Bow** | DPS distanza | **9** (9 + 0) | **8** (42%) | 1.133 | ×2,3 | **0,019** |
| **Naga Trident** | DPS distanza | **7** (5 + 2) | 6 | 1.114 | ×1,8 | 0,10 |
| **Druid Staff** | Healer | **6** (6 + 0) | 4 | 661 | ×1,5 | 0,20 |
| Pickaxe | DPS mischia | 5 | 5 | 497 | ×1,3 | 0,35 |
| War Drums | Support | 3 | 3 | 619 | ×0,8 | 0,75 |
| Claws, Double Blade, Runeblade | – | 2 ciascuno | 2 | 440–490 | ×0,5 | 0,90 |
| Wizard Staff | DPS distanza | 2 (1 + 1) | 2 | 54 | ×0,5 | 0,90 |
| War Hammer | Tank | 1 | 1 | 112 | ×0,3 | 0,98 |

Il tempo di combattimento delle challenge 1–19 è di circa 3.270 s: Bow e Naga hanno passato **più di un terzo del combattimento da morti** (STIMATO, limite inferiore).

### D. Per ruolo (`morti_per_ruolo.csv`, morti per classe)

| Ruolo | Morti per classe | Indicazione |
|---|---|---|
| DPS distanza | **6,0** | trainato da Bow e Naga; il Wizard Staff muore poco |
| Healer | **6,0** | grave: 3 delle 6 morti avvengono a metà round (nelle challenge 15 e 18 muore, viene rianimato dalla pietra e muore di nuovo) |
| Support | 3,0 | |
| DPS mischia | 3,0 | |
| Tank | 1,5 | |

Media del team: 3,9 morti per classe.

**Vicino alla morte.** Gli eroi **vivi** a fine round con HP ≤ 20% sono quasi assenti: War Drums 1, Claws 1 (MISURATO). Quasi tutti i "round sotto 20% HP" di `scheda_classi.csv` sono in realtà **eroi morti e rianimati**: per il Bow lo sono 7 su 7. L'indicatore "round sotto 20% HP" va quindi letto come un indicatore di morte, non di sopravvivenza al limite. Il War Hammer finisce due volte tra il 21% e il 50% da vivo, come è normale per un tank.

### E. Per tipo di wave (`morti_per_tipo_wave.csv`, morti ogni 100 eroi-round)

| Tipo di wave | Team | DPS distanza | Tank |
|---|---|---|---|
| Distanza | 27,5 | **58** | 0 |
| Mischia | 28 | 33 | 20 |
| Ibrida | 14 | 20 | 5 |

- Nelle wave a distanza muoiono soprattutto i DPS distanza, mentre i tank non muoiono mai.
- Le challenge più letali sono la **15** (9 morti, 8 eroi a terra a fine round), la **18** (9), la **9** (6), la **5** e la **13** (4 ciascuna). Coincidono con i voti E/G/D.

### F. Boss finale (challenge 20)

Sconfitta di squadra: 8 eroi a 0 HP nello screenshot finale. Il Double Blade è uscito dalla partita; il War Hammer risulta al 60% (dato non spiegabile). Non è conteggiata per classe. Prima della sconfitta ci sono 3 probabili rianimazioni dalla pietra (certezza media: Bow, War Drums, Wizard Staff).

## 3) Cosa non si può dire e perché

- **Numero esatto di morti: non determinabile.**
  - Una morte con rianimazione dalla pietra entro pochi secondi lascia un silenzio troppo corto per distinguerla da una pausa.
  - Due morti nello stesso round si vedono solo se separate da una rianimazione.
  - Le 17 "possibili morti" (certezza bassa, non conteggiate) sono silenzi di 30–60 s, soprattutto di War Drums (5) e Double Blade (4). Sono classi con kit passivo e pochi ordini, quindi questi silenzi possono essere solo attesa.
- **Chi rianima chi con la pietra.** La mappa sceglie il morto **a caso**: l'abbinamento si deduce dai tempi (STIMATO).
  - Alcune attivazioni "riuscite" non hanno un eroe abbinato: per esempio nella challenge 16 nessun silenzio è compatibile con l'attivazione a 123 s.
  - Il caso più evidente è la challenge 18, dove il Naga finisce al 21%/140 invece che con la firma comune 16%/114: può essere stato rianimato dalla pietra senza tornare ai comandi (AFK). È un'ipotesi non verificabile.
- **Perché si muore** (posizionamento, aggro, mancanza di cure): non è nei dati. Il replay contiene solo comandi, non danni né posizioni degli eroi.
- **Significatività.** Con 10 classi confrontate, il p = 0,019 del Bow non supera una correzione per confronti multipli (Bonferroni: 0,19). È un **segnale forte ma su una sola partita**.
- **Ogni classe è una sola persona:** non si può separare "classe fragile" da "stile del giocatore".
- La durata delle challenge 8, 12, 19 e 20 è stimata, quindi l'istante della pietra in quei round è meno preciso.

## 4) Raccomandazioni per il gruppo

1. **Bow e Naga Trident (DPS distanza):** muoiono spesso già nei primi 20–80 s del round, con silenzi di 60–380 s.
   - Devono stare dietro ai tank, soprattutto nelle wave a distanza (58 morti ogni 100 eroi-round contro 0 dei tank).
   - Valutare oggetti di sopravvivenza o di rianimazione: Revival Draught (50 oro, rianimazione automatica dopo 6 s al 60%), mai comprato in questa partita.
2. **Healer:** muore 6 volte, 3 delle quali due volte nello stesso round (challenge 15 e 18). Proteggerlo è prioritario, perché quando muore lui il round si allunga e crollano tutti (challenge 15: 8 eroi su 10 a terra).
3. **Pietra Ancestrale:**
   - Secondo la simulazione, 13 tentativi su 23 sono falliti: 7 sono stati fatti prima di circa **100 s** dall'inizio del round, quando la pietra non aveva ancora 100 mana; 6 sono arrivati troppo presto dopo un'attivazione riuscita.
   - Regola pratica: attivarla dopo 100 s di round e poi ogni 100 s. Il massimo è 3 rianimazioni per round, e il mana in eccesso oltre 300 va perso.
   - Nelle challenge 9 e 18 (oltre 400 s) si potevano fare fino a 4 attivazioni: ne sono riuscite 3.
4. **Cosa registrare nelle prossime partite:**
   - uno screenshot della multiboard anche **a metà round**, o quando compare il messaggio "Gladiators Alive: N";
   - meglio ancora, una **colonna "morti" nella multiboard**: la mappa non la ha, ma è una modifica semplice al trigger `Create_Corpse`;
   - in alternativa, annotare chi muore e quando, oppure usare un replay di una versione che registri le morti.
   - Utile anche registrare chi viene rianimato dalla pietra (messaggio in chat).

## 5) Grado di fiducia

- **Alto** per la meccanica della mappa (codice letto) e per la **classifica**: Bow > Naga > Druid > resto, con i tank in fondo.
  - 36 delle 39 morti conteggiate hanno certezza alta.
  - La firma identica, i silenzi di ordini e la pietra concordano: nella challenge 9 tre attivazioni su tre sono seguite dalla ripresa dei comandi entro 4 s.
- **Medio** per i conteggi esatti: sono un limite inferiore, possono mancare morti brevi o doppie.
- **Basso** per i confronti fini tra le classi in fondo alla classifica (1–3 morti), che non sono distinguibili tra loro.

## File prodotti

| File | Contenuto |
|---|---|
| `analisi_morti.py` | script |
| `meccanica_morte_mappa.csv` | evidenze dal war3map.j |
| `ritardo_screenshot_round.csv` | fine reale dei round (stimata) |
| `pietra_ancestrale.csv` | 23 tentativi e loro esito stimato |
| `silenzi_combattimento.csv` | silenzi di ordini di almeno 15 s |
| `calibrazione_soglia_silenzio.csv` | scelta della soglia di silenzio |
| `eventi_morte.csv` | ogni morte, con indizi e certezza |
| `morti_per_classe.csv`, `morti_per_ruolo.csv`, `morti_per_tipo_wave.csv`, `morti_per_challenge.csv` | riepiloghi |
