# Domanda 04: i giocatori usano bene le abilità o ci sono tanti tempi morti?

Script: `analisi_tempi_morti.py`. Si lancia dalla cartella del progetto con
`python data_analysis/v2/domande/04_uso_abilita_tempi_morti/analisi_tempi_morti.py` e impiega circa 1 minuto.
Lo script riusa la logica di `analisi_abilita_mana.py`: cast effettivi = ordini fuori cooldown, livelli da talenti, mana simulato calibrato. Non modifica nessun file esistente: il sorgente viene caricato in memoria con due agganci e la scrittura dei CSV originali è disattivata (verificato con l'hash dei CSV di `abilita_mana/`, invariati). Negli output non ci sono nomi di giocatori; lo script lo controlla.

## 1) Risposta breve

**In parte.** Le abilità principali vengono usate con regolarità, ma ci sono molti tempi morti.
- **War Hammer** (Storm Bolt) e **Wizard Staff** (bolt) le riusano con un ritardo mediano di circa 2 s.
- Per quasi tutte le altre classi un'abilità di rotazione resta pronta per 4–18 s prima del cast successivo. Solo il 4–25% dei riusi avviene entro 2 s.
- Ci sono abilità del kit mai usate (Demonic Circle del Double Blade, Entangle del Druid) o usate pochissimo (Starfall, Piercing Shot, Firestorm, Thunderclap).

Le classi più in difficoltà sono le DPS a distanza Bow e Naga Trident, il War Drums e il Double Blade. Per Bow e Naga il dato è in parte confuso dall'attacco automatico e dalle probabili morti.

## 2) Evidenze

Legenda: **M** = misurato (ordini del replay); **S** = stimato (cast = ordini fuori dal cooldown della mappa, mana simulato); **NV** = valutazione con soglie dichiarate.

### Definizioni

- **Combattimento**: le 20 finestre di `abilita_mana/finestre_combattimento.csv`, 3.583 s in tutto. 4 finestre hanno l'inizio stimato.
- **Episodio di disponibilità**: comincia quando finisce il cooldown di un cast dentro una challenge. Il ritardo è il tempo fino al cast successivo della stessa abilità. Se l'abilità non viene più usata prima della fine della challenge, l'episodio è "non riusata".
- **Abilità di rotazione**: danno, cura o buff ripetibile. **Abilità situazionale**: controllo, emergenza, mobilità, utilità. La categoria è assegnata leggendo il tooltip nella mappa (`war3map.w3a`, campo `aub1`).
- **Pause oltre 60 s senza comandi** (probabile morte o attesa): sono escluse dalle metriche "corrette". La versione grezza resta nei CSV, nelle colonne `_grezzo`.

### (a) Ritardo tra fine del cooldown e cast successivo (S)

Fonte: `giudizio_classe.csv` e `ritardi_abilita_classe.csv`. Solo abilità di rotazione.

| Classe | Ruolo | Episodi | Ritardo mediano | % entro 2 s | % non riusata nella challenge |
|---|---|---|---|---|---|
| War Hammer | Tank | 436 | **2,4 s** | **39%** | 8% |
| Wizard Staff | DPS distanza | 535 | 2,8 s | 36% | 9% |
| Pickaxe | DPS mischia | 153 | 5,0 s | 25% | 20% |
| Claws | DPS mischia | 271 | 5,1 s | 17% | 11% |
| Druid Staff | Healer | 466 | 4,0 s | 18% | 9% |
| Runeblade | Tank | 360 | 7,4 s | 8% | 15% |
| Double Blade | DPS mischia | 72 | 8,1 s | 19% | 24% |
| Bow | DPS distanza | 98 | 7,5 s | 6% | 24% |
| Naga Trident | DPS distanza | 91 | 16,5 s | 5% | 25% |
| War Drums | Support | 68 | 18,5 s | 4% | 28% |

Come leggere i valori:
- **Riferimento interno.** Anche le abilità usate meglio (Storm Bolt: 44% entro 2 s, mediana 2,1 s; bolt del Wizard: 45%, mediana 2,2 s) non superano il 45% entro 2 s. Con cooldown brevi, il tempo di lancio e gli altri cast limitano il massimo pratico. Quindi un valore intorno al 40% è "buono" in questa partita.
- **Esempi di abilità lasciate pronte a lungo** (ritardo mediano):
  - Forked Lightning del Naga: 16 s, con cooldown di 8 s;
  - Crushing Wave del Naga: 17 s;
  - Embolden del War Drums: 18 s, 0% entro 2 s;
  - Rally del War Drums: 17 s;
  - Firestorm del Double Blade: 27 s, con cooldown di 10 s, e il 39% delle volte non riusata nella stessa challenge;
  - Desecrate del Runeblade: 14 s;
  - Thunderclap del War Hammer: 12 s, con cooldown di 7 s.
- **Primo uso dopo l'inizio della challenge**, quando l'abilità è già pronta (mediana, `ritardi_abilita_classe.csv`):
  - rapido per Storm Bolt (1,8 s), Rejuvenation (1,9 s), bolt del Wizard (1,5 s), Overdrive (1,3 s);
  - lento per Piercing Shot del Bow (88 s), Forked Lightning del Naga (38 s), Thunderclap (37 s), Force of Nature (35 s).

### (a+d) Tempo morto con il mana

Questa parte usa il mana simulato (S) ed è calcolata solo per le classi con simulazione affidabile o indicativa. Per ogni abilità, la quota del tempo di combattimento disponibile in cui l'abilità era pronta, divisa in due casi: c'era mana sufficiente, oppure no.

- **Wizard Staff (simulazione affidabile)**: è limitato dal **mana**, non dal cooldown.
  - Pyroblast: pronta con mana per il 17% del tempo, pronta ma senza mana per il 38%.
  - Water Elemental: 16% con mana, 20% senza.
  - Un ordine su tre di Pyroblast/Water Elemental cade con mana simulato insufficiente: 47 su 81 e 28 su 51 cast in combattimento.
  - Il bolt invece è senza mana solo il 7% del tempo.
- **Classi indicative**:
  - Il mana limita in modo apprezzabile Starfall del Druid (27% del tempo pronta senza mana) e Desecrate del Runeblade (19%).
  - Per tutte le altre abilità di rotazione delle classi indicative (War Hammer, Runeblade, Druid, Claws, Pickaxe), il tempo "pronta ma senza mana" è il 4–13% del totale. Per queste classi il tempo morto è dovuto in gran parte a **mancato uso con mana disponibile**: pronta con mana per il 40–59% del tempo della classe (`pct_tempo_pronta_con_mana_sim_rotazione`).

### (b) Inattività: intervalli senza comandi in combattimento

I comandi sono misurati (M); la soglia dei 60 s per escludere le probabili morti è una scelta di analisi. Fonte: `inattivita_classe.csv`.

| Classe | Comandi/min | % tempo in pause > 5 s | % tempo in pause > 10 s | % tempo in pause > 60 s (probabile morte) | % pause 10–60 s sul tempo "presente" |
|---|---|---|---|---|---|
| Bow | 22 | 72% | 56% | 33% | **35%** |
| Double Blade | 66 | 55% | 40% | 14% | 30% |
| War Drums | 33 | 56% | 41% | 17% | 28% |
| Naga Trident | 60 | 60% | 45% | 31% | 20% |
| Runeblade | 55 | 35% | 25% | 13% | 14% |
| Pickaxe | 88 | 31% | 21% | 11% | 11% |
| Druid Staff | 56 | 32% | 25% | 16% | 11% |
| Wizard Staff | 62 | 18% | 10% | 0% | 10% |
| Claws | 88 | 24% | 17% | 13% | 6% |
| War Hammer | 103 | 23% | 8% | 3% | 5% |

Le pause oltre 60 s si concentrano nelle challenge lunghe:
- **challenge 18** (432 s, voto G): pause massime di 337–382 s per 6 classi;
- **challenge 9** (428 s, voto G): Druid 333 s, Naga 354 s, Claws 301 s;
- **challenge 5** (voto D): Bow, Claws e Double Blade a 147–165 s.

Questo è coerente con le note della multiboard ("6 eroi sotto 30% HP" nella 18; nella 9 "healer migliore non" il Druid). È coerente anche con il riepilogo del round in `rounds.csv`: le abilità non sono state usate a lungo perché, con ogni probabilità, gli eroi erano a terra. **Le morti però non sono nel replay**, quindi resta un'ipotesi.

### (c) Abilità del kit mai o quasi mai usate

Il conteggio è misurato (M); la valutazione usa le soglie dichiarate (NV). Fonte: `kit_abilita_classe.csv`. Tutti gli eroi superano il livello 7 entro la challenge 7, quindi l'intero kit era disponibile per almeno 2/3 del combattimento. Le passive, le aure, gli autocast e i menu di apprendimento sono esclusi.

- **Mai usate (0 ordini in tutta la partita):**
  - **Demonic Circle** (Double Blade, livello 6): danno ad area 6× Forza, abilità di rotazione;
  - **Entangle** (Druid, livello 7): radici, il tooltip dice "Full duration versus Boss units", quindi è situazionale e utile sul boss.
- **Rotazione usata poco** (≤ 15% del tempo disponibile in cooldown):
  - Starfall del Druid: 6 cast su circa 98 possibili;
  - Firestorm del Double Blade: 32 su circa 306;
  - Piercing Shot del Bow: 18 su circa 143;
  - Thunderclap del War Hammer: 62 su circa 477;
  - Forked Lightning del Naga: 13% in cooldown.
- **Situazionali usate poco**: per queste il dato **non è per forza un errore**.
  - Surrender Soul (1 cast; ti uccide alla fine dell'effetto), Frost Shield (0 in combattimento), Conjure Soulstone (1), Twister (8), Intimidate (5), Binding Trap (6), Leap, Blink, Repair.
  - Hex del Claws (21 cast) e Time Stop del Wizard (11) sono invece usati con una certa regolarità.

### (d) Ordini sprecati

Ordini dati con l'abilità ancora in cooldown (S). Fonte: `ritardi_abilita_classe.csv`.

- Quasi nulli per tutti (0–4% degli ordini), con due eccezioni:
  - **Pickaxe**: 40% degli ordini in combattimento. Sono 96 ordini di Overdrive, **tutti doppi click entro 1 s**: non costano nulla nel gioco.
  - **Double Blade**: 11% (Terror). Anche questi sono **tutti doppi click entro 1 s**.
- Al netto dei doppi click, nessuna classe supera il 4%.
- Il Druid ha 10 ordini di Tranquility ripetuti a meno di 1 s.

### Facile e difficile a confronto

Gruppi per voto del round: A–B facili (challenge 1, 2, 3, 6, 17); C media; D–G difficili (5, 7, 9, 10, 15, 16, 18, 19). Fonte: `confronto_difficolta.csv`.

- **Nelle wave difficili i giocatori danno più comandi**: Tank 48 → 91 al minuto, DPS mischia 61 → 87, DPS distanza 36 → 51.
- **Le pause 10–60 s calano**: Tank dal 20% al 5%, DPS distanza dal 26% al 15%, DPS mischia dal 20% al 9%.
- **Le pause oltre 60 s compaiono quasi solo nelle wave difficili**: 14–32% del tempo, contro lo 0% nelle facili.
- **Il riuso delle abilità peggiora** (ritardo mediano facile → difficile):
  - Tank da 2,7 a 4,5 s;
  - DPS distanza da 2,3 a 4,0 s;
  - DPS mischia da 4,2 a 6,1 s;
  - Support da 6,8 a 32 s, con 0% entro 2 s.
  - Fa eccezione l'Healer, stabile intorno a 4 s.
- Nella lettura del gruppo: nelle wave difficili il gruppo si muove e riposiziona di più ma gestisce peggio le abilità.
- **Attenzione: il confronto non isola la difficoltà.** Le wave difficili sono anche le più lunghe e le più avanzate nella partita, con abilità a cooldown più lunghi e più morti.

### Giudizio per classe e per ruolo (NV)

Regole in `giudizio_classe.csv`. Una classe accumula un "problema" per ciascuna di queste condizioni:
- meno del 25% dei riusi di rotazione entro 2 s;
- più del 40% di episodi non riusati;
- più del 10% del tempo presente in pause di 10–60 s;
- abilità di rotazione mai o poco usate;
- più del 10% di ordini in anticipo, esclusi i doppi click.

Il giudizio è "buono" senza problemi, "migliorabile" con 1–2 problemi, "da migliorare" con 3 o più.

| Ruolo | Classi | Giudizio |
|---|---|---|
| Tank | War Hammer: migliorabile (solo Thunderclap poco usata); Runeblade: migliorabile (riuso lento, ritardo mediano 7,4 s) | il ruolo che usa meglio le abilità |
| Healer | Druid Staff: da migliorare | Rejuvenation usata in modo costante (359 episodi, mediana 3,6 s); Starfall quasi inutilizzata, Entangle mai usata, Force of Nature lenta (16 s) |
| Support | War Drums: migliorabile | riuso più lento di tutti (18,5 s) e molte pause. Ma il kit è per metà passivo o ad aura, e il mana non è simulabile |
| DPS mischia | Claws: migliorabile; Pickaxe: migliorabile; Double Blade: da migliorare | Double Blade: Demonic Circle mai usata, Firestorm lenta |
| DPS distanza | Wizard Staff: migliorabile (borderline sulle pause, limitato dal mana); Naga Trident: migliorabile; Bow: da migliorare | Bow e Naga hanno i ritardi più lunghi tra i DPS |

**Nessuna classe risulta "buona".** Le soglie però sono severe e arbitrarie: il War Hammer e il Wizard sono di fatto il riferimento della partita.

## 3) Cosa non si può dire e perché

- **Cast riusciti.** Il replay contiene solo comandi. Un ordine fuori cooldown può essere stato annullato, o il bersaglio poteva essere fuori portata. Il ritardo misura quindi il tempo fino al **prossimo ordine valido**, non fino al lancio reale.
- **Morti.** Non sono nel replay. Un eroe morto non dà comandi e non lancia abilità, quindi gonfia sia l'inattività sia i tempi morti. La soglia dei 60 s è un'approssimazione: le morti brevi restano conteggiate come tempo morto, e lunghe soste volontarie verrebbero escluse a torto. Per separarle servirebbero gli eventi di morte e resurrezione, cioè un log degli effetti o uno screenshot per ogni morte.
- **Pausa senza comandi ≠ giocatore fermo.** In WC3 l'eroe attacca da solo. Per un DPS a distanza come il Bow (22 comandi/min) stare fermo a colpire è normale. Le pause dicono "nessun nuovo ordine", non "nessun danno".
- **Autocast.** Parasite, Searing Arrows e Mark Target non sono visibili e sono esclusi. Per Bow e Naga parte dell'attività reale manca dal replay.
- **Mana.** La simulazione è utilizzabile solo per Wizard (affidabile) e, in modo indicativo, per War Hammer, Runeblade, Druid, Claws e Pickaxe. Per War Drums, Double Blade, Bow e Naga **non è determinabile** se i ritardi siano dovuti al mana.
- **Situazioni tattiche.** Non si sa se un'abilità non era usabile per motivi tattici: niente bersagli in portata, wave non ancora arrivata, attesa voluta per combinare un controllo sul boss. Per le abilità situazionali un uso basso può essere corretto.
- **Disponibilità delle abilità.** Lo sblocco per livello usa il primo screenshot con quel livello, quindi è una stima per eccesso dell'ora di sblocco. Per alcune abilità si usa il primo ordine, il che sottostima i tempi morti iniziali.
- **Inizio delle finestre.** L'inizio delle finestre delle challenge 8, 12, 19 e 20 è stimato.
- **Una sola partita, un giocatore per classe.** Non si può separare "la classe" da "chi l'ha giocata".

## 4) Raccomandazioni per il gruppo

Sono supportate dai dati sopra.

1. **Double Blade**: inserire Demonic Circle nella rotazione: mai usata, ha danno 6× Forza e un cooldown di circa 24 s. Usare Firestorm più spesso: cooldown di 10 s, oggi un cast ogni 27 s di mediana.
2. **Druid Staff**:
   - Starfall è quasi inutilizzata (6 cast). Va deciso se usarla sulle wave a mischia, dove il Druid è vicino ai nemici, o se lasciarla stare.
   - Entangle sul boss (efficace a durata piena sui boss secondo il tooltip) non è mai stata provata.
   - Force of Nature va lanciata appena pronta: 33% delle volte non riusata nella stessa challenge.
3. **Bow e Naga Trident**: riusare Volley, Piercing Shot, Forked Lightning e Crushing Wave appena pronte. Sono abilità con cooldown di 7–24 s lasciate pronte in mediana 7–17 s. Piercing Shot e Forked Lightning vanno usate subito a inizio challenge: oggi passano 88 s e 38 s.
4. **War Drums**: lanciare Embolden e Rally all'inizio di ogni challenge e appena tornano pronti. Oggi la mediana è 17–18 s, e nelle wave difficili sale a 32 s.
5. **Wizard Staff**: il limite è il mana, non i riflessi. Conviene puntare su Innervate dal Druid e Mana Tide del Claws nei momenti di Pyroblast e Water Elemental. Tuttavia questo è un suggerimento, non verificato sull'effetto in danni.
6. **Gruppo**: nelle wave difficili il riuso delle abilità rallenta per tutti e compaiono le lunghe pause (probabili morti). Sopravvivere più a lungo, con posizionamento e cure, vale probabilmente più che "cliccare di più". Questa è un'ipotesi: le morti non sono misurabili.
7. **Pickaxe e Double Blade**: i doppi click su Overdrive e Terror sono innocui e non serve correggerli.

## 5) Grado di fiducia

- **Alto** per il conteggio degli ordini e delle abilità mai usate (misurato), per gli ordini sprecati e per l'ordinamento delle classi per velocità di riuso.
- **Medio** per i valori dei ritardi e delle pause. Sono ordini, non cast reali. Le morti non sono note e sono escluse solo con la soglia dei 60 s. La categoria rotazione/situazionale è una scelta dell'analisi, basata sui tooltip.
- **Medio-basso** per la parte sul mana: affidabile solo per il Wizard, indicativa per altre 5 classi, non determinabile per 4.
- **Basso** per il confronto facile/difficile come effetto della difficoltà: ci sono fattori confondenti (durata, fase della partita, morti) e per ogni gruppo c'è un solo giocatore per classe.

## File prodotti

| File | Contenuto |
|---|---|
| `analisi_tempi_morti.py` | Script. |
| `ritardi_abilita_classe.csv` | Classe × abilità: categoria, cooldown, costo, tempo disponibile, cast, % in cooldown, % pronta con o senza mana, ritardi (mediana, p75, % entro 2 e 5 s, % non riusata), primo uso da inizio challenge, ordini sprecati (doppio click / in anticipo), cast con mana simulato insufficiente, versioni grezze. |
| `ritardi_episodi.csv` | Ogni episodio di disponibilità (3.348). |
| `inattivita_classe.csv` | Pause senza comandi per classe. |
| `inattivita_classe_challenge.csv` | Pause senza comandi per classe × challenge, con voto del round. |
| `kit_abilita_classe.csv` | Kit completo: attive, passive, autocast, menu; uso e giudizio. |
| `confronto_difficolta.csv` | Indicatori per classe/ruolo × gruppo di voto. |
| `giudizio_classe.csv`, `giudizio_ruolo.csv` | Indicatori riassuntivi e giudizio. |
