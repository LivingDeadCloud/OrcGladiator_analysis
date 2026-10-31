# Gestione del mana e uso dei cooldown

Script: `analisi_abilita_mana.py`. Si lancia dalla cartella del progetto con `python analisi_abilita_mana.py` e impiega circa 1 minuto.
Legge i file di `data_replay/`, `data_screenshots/` e `data_map/raw/`, il replay originale (solo per gli ID delle unità selezionate) e, in sola lettura, `Units\AbilityData.slk`, `UnitBalance.slk` e `MiscGame.txt` dagli MPQ di Warcraft III.
Negli output non ci sono nomi di giocatori: ogni riga riporta `classe` e `ruolo`.

**Cosa è misurato e cosa è stimato.**
- **Misurato:** gli ordini di abilità e gli acquisti (dal replay); il livello dell'eroe, gli HP e il mana attuale nei ~23 screenshot.
- **Stimato:** cast effettivi, tempo in cooldown, mana massimo, andamento del mana tra uno screenshot e l'altro, percentuali di tempo nelle zone di mana.

---

## 1. Dati della mappa ricostruiti

- **Eroi reali.** Le unità scelte all'inizio (O015, O01A, …) sono solo pulsanti di scelta. L'eroe vero viene da `udg_WeaponPickButton` → `udg_RandomWeaponHero` nel JASS: per esempio Wizard Staff = O00P, Druid Staff = O00I. Per l'INT base, la crescita di INT, il mana base e la regen base si usano i campi di `war3map.w3u`; i campi non modificati vengono dal Tauren Chieftain (Otch) in `UnitBalance.slk`.
- **Abilità per classe.** Si prendono le abilità dell'eroe (`uabi`) più quelle sbloccate dal trigger `Level_Up` (livelli 2–7 dell'eroe).
- **Livelli delle abilità.** Nel replay **non ci sono azioni "learn skill"**: le abilità non si imparano dal menu dell'eroe.
  - Il livello sale solo con i **talenti**: oggetti comprati con i punti talento, che il replay registra come ordini `I0xx` dal giocatore. Le regole vengono dai trigger `*_Talent_Buy` (oggetto → abilità → passaggio di livello, per esempio 1→2 oppure 2→4).
  - Il risultato è in `eventi_livelli_e_bonus.csv`. Senza talento, ogni abilità resta al livello 1.
- **Costo e cooldown per livello.** Vengono da `war3map.w3a` (campi `amcs` e `acdn`). Se un campo manca nella mappa si usa `AbilityData.slk` dell'abilità base; se manca anche lì, il valore del livello precedente.
- **Riconoscere l'abilità dall'ordine.** Alcuni ordini non sono nel catalogo (Storm Bolt, Piercing Shot, Fire/Frost/Magic Bolt, Mark Target, Construct Tower) e sono stati riconosciuti per nome.
  - Per il Wizard Staff, il bolt appreso è Frost Bolt (A04I): lo prova l'ordine "windwalk", che corrisponde a Learn Frost Bolt.
  - Alcune etichette di `actions_named.csv` non coincidono con il nome nella mappa (colonna `nome_in_mappa`):
    - Claws: "Healing Wave" = **Rock Shield** (A0G6), "Lightning Strike" = Lightning Bolt (A01C).
    - Pickaxe: "Volatile Concoction" = **Unstable Concoction** (A0FS).
- **Escluse dall'analisi dei cooldown:**
  - attivazioni e disattivazioni dell'autocast (Parasite, Mark Target, Searing/Black Arrows);
  - abilità di apprendimento ("Learn …");
  - abilità degli oggetti;
  - ordini non risolti: 39 in tutto, elencati a video.

## 2. B – Cooldown: regola per i cast effettivi

**Regola.** Per ogni abilità, il primo ordine conta come cast. Un ordine successivo conta come cast solo se arriva **dopo la fine del cooldown** dell'ultimo cast valido; il cooldown è quello del livello che l'abilità ha in quel momento. Gli ordini dentro il cooldown sono **sprecati**: click ripetuti o abilità non ancora pronta.

Questo filtro **non dipende dalla simulazione del mana** (colonna `cast_effettivi_stimati`). La colonna `cast_effettivi_con_mana_sim` scarta in più gli ordini per cui il mana simulato era insufficiente: è un'indicazione, non una misura.

**Cosa la regola non vede:**
- ordini annullati prima del lancio (per esempio da un click destro subito dopo);
- bersaglio fuori portata;
- cast automatici con autocast;
- riduzioni del cooldown da oggetti o talenti non modellate.

Quindi i cast effettivi sono un **limite superiore**. C'è un controllo: se più del 15% degli intervalli tra ordini cade tra il 50% e il 99% del cooldown, la colonna `note` segnala una possibile riduzione non modellata. Non è scattato per nessuna abilità.

**Tempo in cooldown** = unione degli intervalli [cast, cast + cooldown], divisa per:
- (a) il **tempo di combattimento**: somma delle 20 finestre di challenge, 3.583 s (59,7 min);
- (b) la **partita** dell'eroe: dalla creazione alla fine, circa 6.120 s.

È la quota del massimo teorico: 100% significa usare l'abilità appena torna disponibile.

**Finestre di combattimento** (`finestre_combattimento.csv`):
- La challenge N finisce all'orario dello screenshot "post" con `challenges_completed = N`, come in `summarize_replay.py`.
- La finestra inizia `clear_seconds` prima (da `rounds.csv`).
- Per le challenge 8, 12, 19 e 20 (tempo non visibile) l'inizio = fine della challenge precedente + pausa mediana tra round (126 s; le pause note sono molto regolari, 123–129 s).

## 3. A – Simulazione del mana

### Modello (passo di 0,5 s, per ogni eroe dalla sua creazione)

- **Mana massimo** = `umpm` dell'eroe + **15 × INT**.
- **Regen** = `umpr` (1,5/s) × (1 + bonus % degli oggetti AIrm) + **0,05 × INT** + Brilliance Aura + **α**.
- **INT** = INT base + crescita × (livello − 1), arrotondato per difetto, più:
  - tomi (+2 INT, +1 a tutte le statistiche);
  - scelte statistiche dopo le challenge 12 e 19;
  - oggetti con INT comprati: Ring of Superiority +10, Shard of the Revenant +15, Mysterious Codex e oggetto I093 +4, "Purchase X" → oggetto X;
  - talento Glass Cannon (+INT pari al livello dell'eroe).
- **Livello dell'eroe:** interpolato in modo lineare tra gli screenshot.
- **Spese:** a ogni cast che supera il filtro cooldown si toglie il costo del livello corrente. Se il mana non basta, il cast è scartato (`ordini_respinti_mana_sim`).
- **Recuperi ricostruiti dal JASS:**

| Fonte | Effetto |
|---|---|
| Innervate (A060) | 150/225 mana in 10 s all'alleato, 75/112,5 su sé stesso secondo il livello. Il bersaglio viene identificato: 111/111 ordini attribuiti grazie agli ID delle unità selezionate nel replay. |
| Mana Tide Totem | 15,63 mana ogni 2 s per 8 tick a tutti gli eroi (ipotesi: tutti nel raggio di 900). |
| Brilliance Aura del Wizard Staff | +1,0 mana/s a tutti dal momento di "Learn Brilliance Aura"; +1,5 e raggio globale dopo il talento Genius. |
| Terror (Double Blade) | +25 al livello 1, +50 ai livelli successivi. |
| Death Pact livello 2/4 | +150. |
| Avatar livello 3/4 | +8/s. |

- **Costanti di gioco.** `war3mapMisc.txt` della mappa dice IntManaBonus = 4 e IntRegenBonus = 0. Con questi valori, **72 screenshot su ~200 superano il mana massimo possibile**, già a livello 2 e prima di qualsiasi oggetto: per esempio Wizard Staff con 354 mana osservati contro un massimo di 330. Quindi le costanti personalizzate **non sono in uso**. Si usano i valori di default del gioco (15 e 0,05), con 0 violazioni.

### Validazione sugli screenshot

**Screenshot esclusi dall'errore:**
- eroe morto o fine partita (HP = 0);
- **probabile rianimazione**: HP ≤ 25% e mana ≤ 125. Il trigger di rianimazione riporta l'eroe a 10% di HP e **75 di mana**; si vedono infatti molte coppie identiche come 17%/86 o 12%/91 in più eroi nello stesso istante. Le morti non sono nel replay e il modello non può prevederle.

Restano 14–21 screenshot validi per classe.

**Tre modalità** (`validazione_mana_snapshot.csv`):
1. **libera**: simulazione da inizio partita, senza usare gli screenshot;
2. **assimilata**: a ogni screenshot il mana simulato viene riportato al valore osservato, e si misura l'errore della previsione fatta dallo screenshot precedente. Il mana massimo viene alzato solo se il valore osservato lo supera (oggetti non visti);
3. **calibrata**: si aggiunge per ogni classe una regen extra **α** (da −6 a +12 mana/s), scelta minimizzando l'errore. L'errore riportato è **leave-one-out**: ogni intervallo è previsto con l'α stimato sugli altri.

**Confronto di riferimento:** "il mana resta quello dello screenshot precedente" (persistenza).

**Giudizio:**
- **affidabile**: errore LOO ≤ 15% del mana massimo e migliore della persistenza;
- **indicativa**: ≤ 25% e non peggiore della persistenza di oltre il 10%;
- **non affidabile**: tutti gli altri casi.

| classe | ruolo | MAE libera | MAE assim. α=0 (bias) | MAE LOO | % del max | persistenza | α (mana/s) | giudizio |
|---|---|---|---|---|---|---|---|---|
| War Hammer | Tank | 256 | 210 (+199) | 106 | 16% | 114 | −1,5 | indicativa |
| Runeblade | Tank | 370 | 247 (+238) | 168 | 23% | 184 | −1,75 | indicativa |
| Druid Staff | Healer | 265 | 207 (+173) | 182 | 20% | 256 | −1,5 | indicativa |
| War Drums | Support | 295 | 252 (+241) | 152 | 22% | 112 | −3,0 | **non affidabile** |
| Claws | DPS mischia | 150 | 146 (+9) | 184 | 19% | 182 | −0,25 | indicativa |
| Double Blade | DPS mischia | 413 | 364 (+364) | 138 | 18% | 120 | −4,0 | **non affidabile** |
| Pickaxe | DPS mischia | 297 | 171 (+87) | 181 | 21% | 179 | −1,0 | indicativa |
| Bow | DPS distanza | 474 | 377 (+363) | 142 | 21% | 83 | −3,25 | **non affidabile** |
| Wizard Staff | DPS distanza | 389 | 231 (+204) | 135 | 11% | 188 | −2,5 | **affidabile** |
| Naga Trident | DPS distanza | 443 | 341 (+341) | 171 | 23% | 97 | −2,5 | **non affidabile** |

**Come leggere la tabella:**
- Senza calibrazione il modello **sovrastima sempre il mana**: bias da +9 a +364. Per 9 classe su 10 serve una regen extra **negativa**, tra −1 e −4 mana/s. Esiste quindi una spesa di mana che il replay non vede:
  - mana consumato dall'autocast: Searing Arrows del Bow costa 6 mana a freccia, Parasite del Naga Trident 15 mana ogni 5 s;
  - morti e rianimazioni (mana riportato a 75);
  - prelievi via trigger (per esempio Magical Matrix toglie il 25% del mana);
  - abilità passive o aure a mana non visibili.
- Solo il **Wizard Staff** è affidabile (errore 11% del massimo).
- Sei classi sono **indicative** (errore 16–23%).
- Per War Drums, Double Blade, Bow e Naga Trident la simulazione **non batte la semplice persistenza**: le loro percentuali di tempo in zona **non vanno usate come misura**. Restano nei CSV, marcate `non affidabile`, ma sono escluse dalle medie di ruolo.
- **Sensibilità.** `zone_mana_classe.csv` riporta anche le percentuali senza calibrazione (α = 0), e per alcune classi cambiano molto: War Drums passa da 60% a 25% nella zona 20–80. È un altro segnale della fragilità delle stime per le classi incerte.

## 4. Risultati principali

### A – Zone di mana durante il combattimento (simulazione calibrata)

**Classi con simulazione affidabile o indicativa:**

| classe | < 20% | 20–80% | > 80% | affidabilità |
|---|---|---|---|---|
| Wizard Staff | **70%** | 30% | 0% | affidabile |
| Claws | **50%** | 40% | 10% | indicativa |
| Pickaxe | 44% | 46% | 10% | indicativa |
| Runeblade | 37% | 54% | 9% | indicativa |
| Druid Staff | 26% | 46% | 28% | indicativa |
| War Hammer | 16% | **61%** | 23% | indicativa |

Non affidabili, solo come orientamento: War Drums 60% nella zona 20–80, Double Blade 66%, Naga Trident 49%, Bow 35% (60% sotto il 20%).

**Controllo diretto sugli screenshot** (`zone_mana_snapshot_osservate.csv`): mana **misurato** a fine challenge diviso per il mana massimo **stimato**.
- La quota di screenshot **sotto il 20%** è 48% per Wizard Staff, Claws e Naga Trident, 43% per il Bow, 35% per il Druid, 28% per il Pickaxe.
- Per Tank, War Drums e Double Blade è del 5–10%.
- **Quasi mai sopra l'80%**: 2 screenshot su 190.

Queste quote confermano l'ordine delle classi indicato dalla simulazione: Wizard Staff e Claws arrivano spesso a fine combattimento quasi senza mana. Gli screenshot sono però presi a fine round, quindi sono sbilanciati verso lo stato di fine combattimento.

**Per ruolo** (media delle sole classi non "non affidabili", `riepilogo_ruolo.csv`):

| ruolo | 20–80% | < 20% | > 80% |
|---|---|---|---|
| Tank | 58% | 27% | 16% |
| Healer | 46% | 26% | 28% |
| DPS mischia (Claws + Pickaxe) | 43% | 47% | 10% |
| DPS distanza (solo Wizard Staff) | 30% | 70% | 0% |
| Support | non stimabile | | |

**Per challenge** (`zone_mana_challenge.csv`, `riepilogo_ruolo_challenge.csv`):
- Il rischio OOM è massimo nelle challenge 6, 4, 10, 5 e 2 (in media 61–85% del tempo sotto il 20% tra le classi valutabili).
- È minimo nella 1, nella 13 e nel boss finale (20), dove la quota sotto il 20% scende al 2–16%.
- Il mana "sprecato" (sopra l'80%) compare soprattutto nelle challenge 13, 9, 18, 15 e 20, con il 20–36% del tempo.

### B – Cooldown (`cooldown_abilita_classe.csv`)

**Ordini sprecati** (dentro il cooldown):
- Quasi nulli per la maggior parte delle classi (0–3%).
- Eccezioni:
  - **Pickaxe 39%**: 163 dei 281 ordini di Overdrive sono doppi o tripli click a 0,1–0,2 s;
  - **Double Blade 11%**: Terror, 18 su 79;
  - Druid Tranquility (11 su 30) e Wizard Time Stop (9 su 23): ordini ripetuti mentre l'abilità era ancora in cooldown.

**Abilità più sfruttate** (tempo in cooldown durante il combattimento):

| Classe | Abilità | Tempo in cooldown |
|---|---|---|
| Druid | Tranquility | 64% |
| Pickaxe | Hydra Arrows | 62% |
| Wizard | Water Elemental | 61% |
| Bow | Take Aim | 58% |
| War Hammer | Avatar | 56% |
| Claws | Feral Spirit | 53% |
| Druid | Force of Nature | 51% |
| Runeblade | Death Pact | 51% |
| War Hammer | Storm Bolt | 50% (526 cast, 352 in combattimento) |

**Abilità poco sfruttate rispetto al massimo:**
- Naga Trident: Forked Lightning 13% (cooldown 8 s), Vortex 14%, Twister 3%.
- Bow: Volley 11% (cooldown 7 s), Piercing Shot 8%.
- Double Blade: Demon Skin 6%, Firestorm 9%.
- Druid: Starfall 4,5%.
- War Hammer: Thunderclap 12%.

**Cast al minuto di combattimento:**
- Wizard 9,1, Druid 8,1, War Hammer 7,7, Runeblade 5,7, Claws 5,2.
- Molto meno: Pickaxe 2,5, Naga 2,4, Bow 1,8, Double Blade 1,8, War Drums 1,4.
- Per War Drums e Double Blade molto del kit è passivo o ad aura (War Drums, Motivate, Vampiric Aura), quindi pochi cast non significano per forza gioco scarso.

**Tempo in cooldown medio per ruolo:** Healer 37%, Tank 29%, Support 26%, DPS mischia 26%, DPS distanza 21%.

**Mana e cooldown insieme.** Il Wizard Staff ha le abilità chiave in cooldown il 40–60% del tempo, ma la simulazione respinge per mana insufficiente 194 ordini (Pyroblast 48, Water Elemental 34, bolt 99). Il suo limite è il **mana, non il cooldown**. Lo stesso vale, in misura minore, per Claws (Feral Spirit e Lightning Strike) e per il Druid (Rejuvenation 40 ordini respinti).

### Classi senza mana "a energia/rage"

Tutte e 10 le classi hanno abilità attive a mana: nessuna usa energia o rage. Il bonus +4 mana per colpo (abilità A07A) non è presente sugli eroi. Casi particolari:
- Double Blade: Terror non costa mana e anzi lo restituisce (+25/+50).
- War Drums: kit soprattutto passivo o ad aura, 1,4 cast al minuto.
- Bow e Naga Trident: autocast a mana (Searing Arrows, Parasite) che il replay non registra. È il motivo principale per cui la loro simulazione non è affidabile.

## 5. File e colonne

| File | Contenuto |
|---|---|
| `parametri_abilita.csv` | Classe × abilità × livello: `costo_mana`, `cooldown_s`, `fonte_valori` (mappa / slk base), `nome_in_mappa`. |
| `eventi_livelli_e_bonus.csv` | Talenti comprati con passaggio di livello (`livello_da` → `livello_a`) e bonus permanenti a INT, mana e regen considerati, con il tempo (s) e la challenge in corso. |
| `cooldown_abilita_classe.csv` | Per classe e abilità: `ordini_totali`, `cast_effettivi_stimati` (filtro cooldown), `ordini_sprecati_in_cooldown`, `quota_ordini_sprecati_pct`, `cast_effettivi_con_mana_sim`, `ordini_respinti_mana_sim`, `cooldown_occupato_pct_combattimento`, `cooldown_occupato_pct_partita`, `cast_max_teorici_combattimento` (tempo di combattimento / cooldown minimo), `cast_in_combattimento`, `mana_speso_stimato`, `note`. |
| `cooldown_abilita_challenge.csv` | Stesse metriche per challenge: `ordini`, `cast_effettivi_stimati`, `ordini_sprecati`, `cooldown_occupato_pct`. |
| `validazione_mana_snapshot.csv` | Uno per screenshot: `mana_osservato`, `mana_max_modello_base` / `_assimilato`, `oltre_max_modello`, previsioni `prev_libera` / `prev_assimilata_alpha0` / `prev_assimilata_calibrata`, `errore_assimilata_loo`, `escluso_validazione` (motivo). |
| `affidabilita_simulazione_mana.csv` | Errori per classe (MAE in mana) e `giudizio`. |
| `zone_mana_classe.csv` | `pct_sotto_20`, `pct_20_80`, `pct_sopra_80` per ambito (`combattimento` / `partita`), versione calibrata e `_senza_calibrazione`, `affidabilita_simulazione`. |
| `zone_mana_challenge.csv` | Le stesse zone per challenge, con `cast_effettivi_sim`, `ordini_sprecati_cooldown`, `ordini_respinti_mana_sim`, `mana_speso_sim`. |
| `zone_mana_snapshot_osservate.csv` | Quota di screenshot (mana misurato / massimo stimato) in ogni zona. |
| `riepilogo_classe.csv` / `riepilogo_ruolo.csv` / `riepilogo_ruolo_challenge.csv` | Riepiloghi. Nelle medie di ruolo sul mana entrano solo le classi non "non affidabili" (`classi_usate_per_mana`). |
| `finestre_combattimento.csv` | Inizio e fine di ogni challenge e fonte (riepilogo round o stima). |

## 6. Limiti

- **Ordini, non effetti.** I cast effettivi sono un limite superiore: un ordine dopo la fine del cooldown può comunque essere stato annullato o non lanciato. I cast dell'autocast mancano del tutto.
- **Il mana è misurato solo ~20 volte per eroe**, sempre a fine challenge (più 3 durante il boss). Tra uno screenshot e l'altro tutto è modellato. L'errore tipico della previsione (100–185 mana) è paragonabile all'ampiezza della zona 20–80% per eroi con 600–1.300 di mana.
- **Morti e rianimazioni** (mana a 75) non sono nel replay: è la principale fonte di errore insieme all'autocast. La calibrazione con α le assorbe solo in media.
- **Oggetti.** Si assume che ogni oggetto comprato resti nell'inventario fino alla fine e che ogni ordine di acquisto sia riuscito (l'oro non è verificabile).
  - Non sono modellati: pozioni (Wizard's Potion), oggetti attivabili (`useslot`), effetti a trigger degli oggetti, il +1 casuale alle statistiche a ogni livello, le aure donate dal War Drums (Bestow/Eminence), Motivate, Surrender Soul.
  - Il mana massimo viene alzato a posteriori quando uno screenshot lo supera.
- **Ipotesi di vicinanza.** Mana Tide e Brilliance Aura sono applicati a tutti gli eroi come se fossero sempre nel raggio.
- **Livello dell'eroe** interpolato in modo lineare tra gli screenshot; la quantità di INT tra uno screenshot e l'altro è approssimata.
- **Inizio delle challenge 8, 12, 19 e 20** stimato con la pausa mediana.
- **Il mana massimo è sempre una stima**, anche nella tabella sugli screenshot: se l'INT reale è più bassa, le percentuali "sotto il 20%" sono sottostimate.
