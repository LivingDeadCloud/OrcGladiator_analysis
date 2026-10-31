# Domanda 01 – La scelta delle classi è ottimale?

Script: `analisi_scelta_classi.py` (da lanciare nella cartella principale del progetto:
`python data_analysis/v2/domande/01_scelta_classi/analisi_scelta_classi.py`). Nessun file contiene nomi di giocatori.

## 1) Risposta breve

**Verdetto: non determinabile come "ottimale"; in parte adeguata.** La composizione copre tutti i ruoli e il team ha
preso le uniche due classi "Melee Tank" che la mappa offre. In gioco però i ruoli non sono stati svolti come previsto:
i danni subiti li hanno presi soprattutto due DPS mischia (Double Blade e Claws). I danni dipendono molto da una sola
classe (Claws). Nelle wave difficili i DPS a distanza sono finiti spesso sotto il 20% di HP. Dire se un'altra
composizione avrebbe fatto meglio, e in particolare se avrebbe battuto il boss finale, **non è possibile**: le 6 classi
non giocate non hanno dati, c'è una sola partita e ogni classe è stata giocata da una sola persona. L'effetto della
classe e quello del giocatore non si possono separare.

## 2) Evidenze

### 2a. Cosa offriva la mappa (MISURATO, dal file della mappa)
`classi_selezionabili.csv`, fonte: `war3map.j` (`udg_WeaponPickButton[1..16]`) e tooltip `utip`/`utub` in `war3map.w3u`.

- **16 classi selezionabili, 10 giocate.** Non giocate: Katana (Melee DPS), Great Axe (Melee DPS),
  Pelt (Melee Adaptable), Scythe (Ranged Summoner), Crystal Ball (Ranged Caster), Alchemy Flask (Ranged Support).
- **Tipi dichiarati dalla mappa:**
  - Melee Tank: 2, entrambi giocati (War Hammer, Runeblade);
  - Ranged Support: 3, 2 giocati (Druid Staff, War Drums), escluso Alchemy Flask;
  - Melee DPS "puri": 2, nessuno giocato (Katana, Great Axe).
- **Classificazione della mappa ≠ ruoli del progetto.** La mappa classifica Double Blade e Claws come "Melee Caster",
  non come DPS. Nel tooltip il Double Blade ha +200 HP e +3 armatura (il War Hammer +200 HP e +4), più Demon Skin e
  Vampiric Aura. Dal codice (`cure/NOTE.md`), la Vampiric Aura dà al Double Blade il 40/80% di lifesteal.
  Sulla carta quindi il Double Blade è un ibrido resistente, e il suo comportamento "da tank" è coerente con il kit.
- **Sulla carta le classi non giocate offrono:**
  - cure da abilità che passano dal contatore della mappa (`cure/evidenze_codice_cure.csv`): Alchemy Flask (Healing
    Plume, Chemical Rage), Crystal Ball (Saviour, Alter Fate), Pelt (Primal Rage e uno scudo accreditato come cura),
    Scythe (Soul Harvest, Flesh Golem) e Great Axe (Relentless);
  - per la Katana nessuna cura: è danno puro (Critical Strike, Bladestorm…).

  Sono descrizioni del tooltip, **non rendimento misurato**.
- La mappa ha i comandi `-ban <classe>` (15 classi; non il Pelt). In chat non risulta nessun `-ban`
  (`data_replay/chat.csv`). Non ho verificato se due giocatori possano scegliere la stessa arma.

### 2b. Chi ha svolto davvero i ruoli
MISURATO: multiboard dopo la challenge 19 (`scheda_classi.csv`, `coerenza_ruoli.csv`).

| Classe (ruolo) | Danni | Tank | Cure (multiboard) | Boss | Ruolo osservato |
|---|---|---|---|---|---|
| Runeblade (Tank) | 5,6 | 14,7 | 16,3 | 3,9 | Healer (no) |
| War Hammer (Tank) | 7,1 | 13,2 | 12,9 | 8,9 | Tank (parziale) |
| Druid Staff (Healer) | 1,0 | 4,5 | 36,0 | 0,8 | Healer (sì) |
| War Drums (Support) | 1,7 | 1,0 | 13,8 | 2,2 | n.d. |
| Claws (DPS mischia) | **26,9** | 24,5 | 7,3 | **33,2** | DPS (parziale) |
| Double Blade (DPS mischia) | 5,5 | **28,3** | 5,7 | 8,1 | Tank (no) |
| Pickaxe (DPS mischia) | 15,3 | 3,7 | 3,1 | 8,9 | DPS (sì) |
| Bow (DPS distanza) | 12,7 | 1,0 | 2,3 | 14,3 | DPS (sì) |
| Naga Trident (DPS distanza) | 11,3 | 1,0 | 1,2 | 6,7 | DPS (sì) |
| Wizard Staff (DPS distanza) | 12,9 | 8,1 | 1,5 | 12,9 | DPS (sì) |

- **Tank: copertura nominale sì, effettiva no.**
  - Le classi non-Tank hanno subito il **72,1%** dei danni; Double Blade e Claws insieme il **52,8%**.
  - I due Tank, insieme, hanno subito il 27,9%.
  - I premi "migliore tank" dei Tank sono 5, tutti entro la challenge 7. Il Double Blade ne prende 7 (challenge 9–16).
- **Cure: ridondanza.** Quattro classi superano il 10% delle cure della multiboard (Druid Staff, Runeblade, War Drums,
  War Hammer). La % della multiboard però include rigenerazione, pozioni e lifesteal.

  Cure da sole abilità, STIMATE (scenario centrale b):

  | Classe | Quota |
  |---|---|
  | Druid Staff | 60,9% |
  | War Drums | 28,6% |
  | Runeblade | 10,5% |
  | War Hammer | 0% |

  Le cure da abilità sono quindi concentrate su Healer e Support. Le cure dei Tank sono in buona parte autocura.
- **Danni: concentrazione su una classe.**
  - Claws fa da sola il 26,9% dei danni del team, il 56% di quelli dei DPS mischia, e il 33,2% dei danni al boss.
    Prende 19 premi su 64.
  - Il Double Blade, nel ruolo di DPS, è sotto la quota equa del 10% (5,5%): fa meno danni di entrambi i Tank.
  - I tre DPS a distanza sono equilibrati (11,3–12,9%).

### 2c. Rendimento sui tipi di wave
Quote del round STIMATE, già in `aggregato/classe_tipo_wave.csv` e `ruolo_tipo_wave.csv`. n = 5 wave da mischia,
4 a distanza, 10 ibride.

- **Contro le wave a distanza:**
  - la quota tank dei Tank scende (somma 24,8 contro 31,2 in mischia; War Hammer 7,6);
  - il Double Blade sale a 36,0;
  - il voto medio è il peggiore (4,5 contro 3,0 in mischia), ma la media pesa molto sulla wave 9 (G).
- **Danni per ruolo:** le differenze tra tipi sono piccole (DPS mischia 41,8 / 44,0 / 47,3; DPS distanza 40,8 / 35,0 /
  36,2 su mischia / distanza / ibrida), entro il rumore di ±1–2 punti dichiarato.

### 2d. Wave difficili e boss finale
`ruoli_round_difficili.csv`, `contributo_classi.csv`.

Definizione delle challenge "difficili": voto D–G oppure almeno 3 eroi con HP ≤20% a fine round. Sono le challenge
5, 7, 9, 10, 13, 15, 16, 18 e 19. "Facili" = voto A–C e meno di 3 eroi a HP ≤20%: challenge 1, 2, 3, 4, 6, 11, 14 e 17.
Escluse la 8 e la 12 (senza voto).

- **Eroi a HP ≤20% a fine round nelle challenge difficili** (MISURATO, un solo istante per round):

  | Ruolo / classe | Eroi a HP ≤20% | Quota dei casi |
  |---|---|---|
  | DPS distanza | **13 su 27** | 48% |
  | Healer | 3 su 9 | 33% |
  | Support | 3 su 9 | 33% |
  | DPS mischia | 7 su 27 | 26% |
  | Tank | 3 su 18 | 17% |
  | Bow | **7 su 9** (HP medio 33%) | 78% |
  | Naga Trident | 5 su 9 | 56% |

  Nelle challenge facili i casi sono 1 in tutto. In pratica **le retrovie (tiratori, Healer, Support) finiscono in rosso
  più dei Tank**. È coerente con Tank che non trattengono i nemici, ma il replay non contiene posizioni né bersagli dei
  nemici: è un'**ipotesi**.
- **Quota tank del round, difficili contro facili** (STIMATA): Tank 24,4 contro 37,3; DPS mischia 58,0 contro 52,8;
  Double Blade 30,8 contro 21,0. Nelle challenge difficili il carico si sposta ancora di più dai Tank ai DPS mischia.
- **Quota boss del round** (STIMATA, poco significativa fuori dai round con boss): DPS mischia 48,8 nelle difficili
  contro 29,4 nelle facili; Claws 31,7 contro 12,2. Nelle challenge difficili il boss lo abbatte soprattutto Claws.
- **Boss finale** (challenge 20, persa). Le quote sono dallo snapshot parziale a 5987 s: STIMA del round, ±1–2 punti.

  | Metrica | Classi principali |
  |---|---|
  | Danni | Claws 31,4; Wizard Staff 26,4; Pickaxe 15,3 |
  | Danni subiti | Double Blade 33,3; War Hammer 20,3; Runeblade 16,3 |
  | Cure | War Drums 32,3; Druid Staff 21,1 |

  Alla sconfitta (snapshot a 6158 s) tutti i 9 eroi presenti sono a 0 HP tranne il War Hammer (60%); il Double Blade
  è già uscito. Non si sa che cosa abbia causato la sconfitta.

### 2e. Classe o giocatore?
Alcuni segnali riguardano il modo di giocare più che la classe (MISURATO dal replay, ma non separabile dalla classe):

| Classe | Abilità/min | APM | Ordini sprecati in cooldown | Nota |
|---|---|---|---|---|
| Double Blade | 1,75 | – | 11% | |
| War Drums | 1,10 | 32,4 (la più bassa) | – | |
| Pickaxe | – | – | 39% | |
| Wizard Staff | 9,07 | – | – | 1 solo round a HP ≤20% |

Con una persona per classe questi numeri non permettono di dire se una classe "rende poco" o se l'ha giocata male
chi l'aveva.

## 3) Cosa non si può dire e perché

- **Se la composizione fosse ottimale.** Servirebbe confrontarla con altre composizioni. Qui ce n'è una sola, in una
  sola partita.
- **Il rendimento delle 6 classi non giocate** (Katana, Great Axe, Pelt, Scythe, Crystal Ball, Alchemy Flask). Non ci
  sono dati: le loro descrizioni sono solo sulla carta. Non si può dire, per esempio, che una Alchemy Flask al posto
  del War Drums o una Great Axe al posto del Double Blade avrebbero aiutato.
- **Classe contro giocatore.** Una persona per classe: le due cose sono confuse al 100%. Il "Double Blade che tanka"
  può dipendere dal kit (HP, armatura, lifesteal) o da come l'ha giocato quella persona.
- **Il valore del Support.** Aure e buff (Embolden, Rally, War Drums…) non compaiono nella multiboard. Si vedono solo le
  sue cure, stimate al 28,6% delle cure da abilità.
- **Perché si è perso il boss finale.** Non ci sono danni, morti, posizioni né ordine delle morti. Ci sono solo due
  snapshot parziali e uno di sconfitta, con un giocatore uscito.
- **Danni assoluti.** Le quote sono relative al team: non dicono se il team nel complesso facesse abbastanza danni.
- **Uso dei ban.** Il comando esiste ma nessuno l'ha usato. Non ho verificato se due giocatori potessero prendere la
  stessa classe.

**Dati da registrare nella prossima partita:**
- ripetere la partita con composizioni diverse (almeno 2–3) e, se possibile, ruotare le classi tra i giocatori, per
  separare classe e giocatore;
- uno screenshot della multiboard a fine di ogni round e durante il boss finale, a intervalli regolari;
- registrare le morti, con l'ordine e la challenge;
- annotare quali classi si potevano scegliere, se c'erano ban, e le scelte della Wizard Staff.

## 4) Raccomandazioni per il gruppo

Sono supportate solo in parte: sono indizi da una partita, non prove.

1. **Ridefinire chi tanka, invece di cambiare classi alla cieca.** In pratica il tank principale è stato il Double
   Blade, e il suo kit lo consente: o lo si dichiara tank, o i Tank devono mettersi davanti, soprattutto nelle wave a
   distanza, dove il War Hammer scende al 7,6% dei danni subiti.
2. **Proteggere le retrovie nelle wave difficili.** I DPS a distanza sono a HP ≤20% nel 48% dei casi (il Bow nel 78%).
   Conviene un posizionamento più arretrato dei tiratori, oppure cure e pozioni dirette a loro. Il Bow è l'unico ad
   avere una pozione di cura (Rage Potion); gli altri DPS a distanza hanno solo pozioni di mana.
3. **Ridurre la dipendenza da Claws.** Fa un terzo dei danni al boss. Un secondo DPS mischia che faccia danni conta più
   di un terzo personaggio che subisce danni. Se il gruppo vuole provare un cambio, il candidato naturale (sulla carta) è
   un Melee DPS puro, Katana o Great Axe, al posto di uno dei DPS mischia poco offensivi. È **da testare**, non dimostrato.
4. **La ridondanza nelle cure è più apparente che reale.** Le cure da abilità sono di Druid Staff e War Drums; quelle
   dei Tank sono soprattutto autocura. Non risulta un eccesso di guaritori da tagliare.

## 5) Grado di fiducia

- **Alto** sui fatti descrittivi: le classi disponibili lette dalla mappa, le quote cumulative della multiboard, chi ha
  subito i danni, la concentrazione dei danni su Claws, gli eroi a HP ≤20%.
- **Medio** sulle quote per round e per tipo di wave: sono stime con ±1–2 punti e n di 4–10 wave.
- **Basso / nullo** sul giudizio "ottimale o no" e sulle alternative: una sola partita, una persona per classe, nessun
  dato sulle classi non giocate e nessun dato sulla causa della sconfitta.

## File prodotti

| File | Contenuto |
|---|---|
| `analisi_scelta_classi.py` | script; rigenera i CSV e controlla che non ci siano nomi di giocatori |
| `classi_selezionabili.csv` | le 16 classi della mappa: codice, attributo, tipo dichiarato, giocata sì/no, abilità e bonus dal tooltip |
| `contributo_classi.csv` | per classe: quote cumulative, ruolo osservato, medie del round nelle challenge difficili e facili, HP ≤20%, boss finale |
| `ruoli_round_difficili.csv` | per ruolo e gruppo di challenge (difficili / facili / boss finale): quote del round sommate ed eroi a HP ≤20% |
| `indicatori_composizione.csv` | indicatori di copertura, ridondanza e concentrazione, ognuno con tipo (misurato/stimato) e fonte |
