# Difetti del consiglio di formazione — revisione avversariale

Revisione del **24/09/2026** della catena che produce l'unico output che conta:
`data/` → `scripts/lib/roster.py` → `scripts/report_formazione.py` → l'undici da
schierare.

**Ricontrollata la sera del 24/09** sul codice e sui dati di `main`. La prima stesura
era stata eseguita su una copia locale non aggiornata, e le regole della lega non erano
ancora note. Dopo la verifica sono stati tolti 3 difetti e corrette 3 affermazioni,
elencati in [§ Rimossi dopo la verifica](#rimossi-dopo-la-verifica). Tutto ciò che
resta qui è stato riverificato sul codice di `main` del 24/09.

**Seconda revisione il 27/09**, sui voti veri delle giornate 1-5: il valore del
giocatore (freno, produzione offensiva, avversario), con backtest. Sta in
[§ Revisione del 27/09](#revisione-del-2709-il-valore-del-giocatore-sui-voti-veri);
le sezioni prima di quella descrivono lo stato del 24/09.

Marcatori: **[Certo]** eseguito e visto · **[Probabile]** inferenza forte dal
codice · **[Ipotesi]** sto colmando un vuoto.

---

> **AGGIORNAMENTO 27/09 sera — una premessa di questo doc era sbagliata.** Qui sotto si
> legge «sostituzioni illimitate», e da lì discende tutta la sezione seguente. La regola
> vera, confermata dall'utente: **panchina di 7 giocatori a composizione fissa (1 P, 2 D,
> 2 C, 2 A), entra il primo dello stesso ruolo, e se le riserve di quel ruolo finiscono lo
> slot non prende voto e vale 0.** La dimostrazione «dentro un ruolo ordina per valore,
> la probabilità non conta» **regge lo stesso** ed è ancora il criterio del motore. Cade
> invece il corollario implicito che la probabilità non serva mai: con 1-2 posti per ruolo
> serve a scegliere **chi** ci va, e vale +0,60 punti a giornata misurati. Vedi
> `.docs/analisi-valutazione-formazione.md`, che contiene anche la revisione in punti di
> tutti i pezzi del modello (la correzione per la produzione è stata spenta).

## Le regole della lega cambiano la diagnosi

Confermate dalla lega il 24/09 e scritte in `config/league.json → regole_lega`:

- **Nessun modificatore di difesa.** Scegliere il modulo con la somma più alta è
  corretto. Il fatto che il motore preferisca spesso i moduli a 3 difensori non è un
  difetto.
- **Sostituzioni illimitate.** Ogni titolare senza voto viene sostituito scorrendo la
  panchina. [Ipotesi da confermare: solo con un panchinaro dello stesso ruolo, che è il
  default del Classic.]

La conseguenza è controintuitiva e ribalta la priorità della prima stesura. **Con
sostituzioni illimitate, dentro un ruolo conviene ordinare i giocatori per media
quando giocano, ignorando la probabilità che giochino**: se il titolare non scende in
campo, entra il primo della panchina, e l'ordine giusto è sempre "prima il più forte".
La prova sta nello scambio di due giocatori A, B in posizioni vicine: la differenza di
valore atteso vale `P(A)·P(B)·(media A − media B)`, quindi va avanti sempre quello con
la media più alta, qualunque siano le probabilità.

**[Certo]**, simulazione Monte Carlo (script in [§ Riprodurre](#riprodurre)):

```
1 posto da difensore:
  titolare Dodò (gioca 1 su 4, media 6.50), Marcandalli in panchina:  6.013
  titolare Marcandalli (gioca sempre, media 5.85), Dodò in panchina:   5.850

3 posti, 6 giocatori con probabilità e medie diverse:
  ordino per media quando gioca:          20.030
  ordino per media x probabilità:         18.632
  ordino per probabilità di giocare:      18.632
  miglior ordine su tutte le 720 possibili: 20.027  (= ordine per media)
```

Quindi:

- il criterio di fondo del motore (media quando gioca) **è quello giusto** per questa
  lega;
- ciò che il motore sbaglia è **tutto ciò che sta intorno** a quel criterio: la
  panchina non è ordinata, una penalità rimescola l'ordine, e le medie calcolate su
  1 voto valgono quanto quelle su 5.

Due limiti della regola "ordina per media". Primo, vale se la panchina del ruolo è
abbastanza lunga da coprire: con una panchina corta, per gli ultimi posti conta anche
la probabilità di giocare. Secondo, la probabilità resta decisiva per **quanti** posti
di un ruolo si riesce a riempire, cioè per la scelta del modulo e per gli avvisi di
copertura.

---

## Difetti aperti, dal più grave

### 1. La panchina non è ordinata, e con i cambi illimitati è lei a fare i punti

> **Risolto il 24/09** (fase B1, vedi [§ Piano](#piano-cosa-si-può-fare-subito)).

**Cosa si rompe.** `roster.py:109` costruisce la panchina come
`[p for p in roster if p["id"] not in bench_ids]`, cioè nell'ordine di
`ownership.json`, senza ordinarla. Ci mette dentro anche gli infortunati. Con
sostituzioni illimitate la panchina lavora ogni giornata: per ogni titolare senza voto
entra il primo panchinaro del ruolo che ha preso voto.

**Prova [Certo]**, output del report sul codice del 24/09, rosa simulata di
[§ Riprodurre](#riprodurre):

```
PANCHINA:
  [P] Perri                     media ultime 5: n/d  status: titolare
  [P] Christensen O.            media ultime 5: n/d  status: panchina
  [D] Dimarco                   media ultime 5: 4.46  status: ballottaggio
  [D] Solet                     media ultime 5: 4.27  status: ballottaggio
  [D] Diego Carlos              media ultime 5: n/d  status: titolare
  [D] Balerdi                   media ultime 5: n/d  status: ballottaggio
  [D] Bellanova                 media ultime 5: 4.00  status: ballottaggio
  [C] Jones C.                  media ultime 5: n/d  status: ballottaggio
  [C] Isaksen                   media ultime 5: 4.25  status: ballottaggio
  [C] Hutchinson                media ultime 5: n/d  status: ballottaggio
  [C] Bernabè                   media ultime 5: n/d  status: infortunato
  [A] Santos A.                 media ultime 5: n/d  status: infortunato
  ...
```

Tre problemi nella stessa lista: l'ordine è quello di acquisto, non di valore; due
infortunati occupano posti in panchina; i giocatori senza dati sono mescolati a quelli
con dati. (I numeri stampati sono già penalizzati di 1,5: difetto 3.)

**Perché costa punti.** È il meccanismo che trasforma "schiero il più forte anche se è
incerto" da scommessa in scelta giusta. Con la panchina in ordine casuale, il sostituto
è casuale.

**Correzione.** Ordinare la panchina con lo stesso criterio dei titolari, cioè per
media dentro ogni ruolo. Spostare gli esclusi (infortunati, squalificati) in una lista
separata "non disponibili". Stampare la panchina numerata.

---

### 2. La penalità di −1,5 per titolarità incerta rimescola l'ordine giusto

> **Risolto il 24/09** (fase B2, vedi [§ Piano](#piano-cosa-si-può-fare-subito)).

**Cosa si rompe.** `apply_formazioni_status.py:44` riduce la percentuale di titolarità
pubblicata da fantacalcio.it (17 valori distinti, dall'1% al 90%) a tre etichette. Poi
`roster.py:65` toglie 1,5 punti a chi è `ballottaggio` o `panchina`, sempre la stessa
cifra.

**Prova [Certo]:**

```
fantacalcio.it: titolare   95%  ->  status 'titolare'      ->  penalità  0.0
fantacalcio.it: titolare   89%  ->  status 'ballottaggio'  ->  penalità -1.5
fantacalcio.it: panchina   39%  ->  status 'panchina'      ->  penalità -1.5
fantacalcio.it: panchina    0%  ->  status 'panchina'      ->  penalità -1.5
```

**Perché costa punti.** Per quanto visto sopra, con i cambi illimitati **qualunque**
penalità legata alla probabilità peggiora l'ordine: fa scendere un giocatore forte ma
incerto sotto uno più debole ma sicuro, quando conveniva il contrario. Nella
simulazione pesare per la probabilità costa ~1,4 punti su 3 posti (20,03 → 18,63).

**Correzione.** Togliere la penalità dall'ordinamento. Salvare la percentuale come campo
numerico in `players.json` (oggi finisce solo come testo in `status_note`) e usarla
per due cose soltanto: gli avvisi nel report ("titolare al 40%") e, più avanti, la
scelta del modulo in base alla copertura del ruolo.

**Attenzione all'ordine dei lavori.** Va fatta **insieme** alla correzione 1 o dopo,
mai prima. Senza panchina ordinata la penalità è l'unica cosa che protegge da un
sostituto casuale: toglierla da sola peggiorerebbe il consiglio.

---

### 3. "media ultime 5" è un'etichetta falsa: 1 voto vale quanto 5

> **Risolto il 24/09** (fase B3, vedi [§ Piano](#piano-cosa-si-può-fare-subito)).

**Cosa si rompe.** `report_formazione.py:41` e `:47` stampano
`media ultime 5: {score}` qualunque sia il numero di voti. Il valore stampato, poi,
non è nemmeno la media: è la media già penalizzata di 1,5 (difetto 2).

**Dato [Certo]**, sui dati veri (presenze con minuti > 0, giornate 1-5):

| Ruolo | Nel listone | Almeno una presenza | **Una sola** presenza |
|---|---|---|---|
| P | 64 | 20 (31%) | 1 |
| D | 190 | 128 (67%) | 16 |
| C | 192 | 134 (69%) | 12 |
| A | 86 | 57 (66%) | 2 |

**Perché costa punti.** Ora che l'ordine per media è il criterio giusto, questo difetto
**pesa di più** che nella prima stesura. Ordinando per media, in cima finisce di regola
chi ha giocato poco e ha avuto la partita fortunata: un 8 in una sola partita batte un
6,8 costante su cinque. [Ipotesi sulla dimensione: σ per partita ≈ 1,3 sul fantavoto,
valore di letteratura, non misurabile qui perché i fantavoto reali non ci sono ancora.]

**Correzione.** Frenare le medie costruite su pochi voti verso la media del ruolo
(`(somma + k·media_ruolo) / (n + k)`, con k ≈ 3), finché il giocatore non accumula
partite. Stampare sempre `media X su N voti`. Il freno va mostrato nel report, non
applicato di nascosto.

---

### 4. Lo status non scade: chi sparisce dalle probabili tiene quello vecchio

> **Risolto il 24/09** (fase C1, vedi [§ Piano](#piano-cosa-si-può-fare-subito). Lo status `squalificato`, rimasto fuori dalla C1, è stato aggiunto lo stesso giorno
> con `scrape_squalifiche.py` (vedi [§ Cosa resta aperto](#cosa-resta-aperto)).

**Cosa si rompe.** In `apply_formazioni_status.py:93`, chi non viene trovato nelle
probabili finisce in `unmatched_players` e **non viene toccato**: conserva status e
data della volta prima. `score_player` non guarda mai `status_updated_at`. Lo status
`squalificato` non viene assegnato da nessuno script (esiste solo nella riga che lo
definisce, `roster.py:6`).

**Prova [Certo]**, sullo snapshot vero del 21/09, in una copia temporanea: tolgo Malen
dalle probabili della Roma (come se fosse squalificato) e riapplico.

```
prima : ballottaggio 2026-09-21
dopo  : ballottaggio 2026-09-21 | note: fantacalcio.it probabili formazioni: titolare 80%
```

Nessun avviso: Malen resta schierabile con i dati della settimana prima.

**Perché costa punti.** Con i cambi illimitati il danno diretto è contenuto, perché se
non gioca entra il primo panchinaro. Il danno vero è che **il report sembra sicuro
quando non lo è**, e un utente che legge "ballottaggio 80%" su un giocatore squalificato
prende decisioni sbagliate fidandosi.

**Correzione.** Chi non compare nelle probabili passa a `n/d` con nota "assente dalle
probabili del <data>", invece di tenere lo status vecchio. Nel report, uno status più
vecchio di 4 giorni viene segnalato come da verificare.

**Nota sulla fonte.** La pagina delle probabili **non** contiene una lista degli
indisponibili (verificato: ha solo `player-list starters` e `player-list reserves`).
Su fantacalcio.it gli indisponibili stanno in pagine separate: "Infortunati",
"Squalificati e diffidati". Quest'ultima è la fonte naturale per lo status
`squalificato` e per il rischio diffida, se in futuro si vorrà coprirli.

---

### 5. Se un ruolo non ha dati, il report non propone niente

> **Risolto il 24/09** (fase B4, vedi [§ Piano](#piano-cosa-si-può-fare-subito)).

**Cosa si rompe.** `roster.py:100`: per ogni modulo servono abbastanza giocatori con
punteggio in ogni ruolo, altrimenti il modulo viene scartato. Se non ne resta nessuno,
il report risponde solo "Nessun modulo schierabile".

**Dato [Certo].** Solo 20 portieri su 64 hanno almeno una presenza, circa uno per
squadra. Se il tuo unico portiere con storico è infortunato, o è un nuovo acquisto
senza partite, non esce nessuna formazione: niente difesa, niente attacco, niente.

**Perché costa punti.** Il consiglio sparisce proprio nelle settimane con meno dati,
cioè le prime dopo l'asta. E anche quando non si blocca, il modulo finisce scelto da
quali dati ci sono, non dal calcio: con 2 soli attaccanti valutabili i moduli a 3
punte spariscono senza che il report lo dica.

**Correzione.** Non bloccare tutto: proporre comunque gli altri ruoli e lasciare lo
slot scoperto a te, con scritto il motivo ("nessun portiere con voti: scegli tu").
Niente stime inventate, come vuole la regola del progetto. Per ogni modulo scartato,
stampare perché.

---

### 6. Il calendario non sa qual è la prossima giornata

> **Risolto il 24/09** (fase C2, vedi [§ Piano](#piano-cosa-si-può-fare-subito)).

**Cosa si rompe.** `--matchday` è solo un'etichetta (`report_formazione.py:29`): la
formazione è identica per la giornata 1 e per la 38. E non potrebbe essere altrimenti:
**tutte le 335 partite future** in `calendario_serie_a.json` hanno `giornata: null`.

**Prova [Certo]:** `scheduled: 335, con giornata non nulla: 0`.

La fonte (BigBalls) assegna la giornata solo dopo che la partita è stata giocata. Per
le partite future il campo è vuoto finché non si giocano, non per "un giorno di
ritardo".

**Perché costa punti.** Il sistema non sa se la squadra di un tuo giocatore gioca. Una
partita rinviata manda in s.v. tutti i tuoi giocatori di quelle due squadre, e il
report li schiera come sempre. Raro (1-2 volte a stagione), ma può valere 3-4 slot.
(Scritto prima di conoscere il regolamento: nella lega il rinviato non prende s.v. ma
6 politico o il voto del recupero, vedi C2 nel piano.)

**Correzione.** `data_utc` c'è per tutte le partite: ricavare la prossima giornata
raggruppando le partite per date, e nel report segnalare chi appartiene a una squadra
che non compare in quella giornata.

---

### 7. Tre righe di statistiche attribuite al giocatore sbagliato

> **Risolto il 24/09** (fase A3, vedi [§ Piano](#piano-cosa-si-può-fare-subito)).

**Cosa si rompe.** `import_matchday_stats.py:154`: se la squadra del giocatore non è
quella di casa, lo script assume che sia quella in trasferta, senza controllare che
sia davvero una delle due. Quando il box score contaminato di BigBalls porta un
giocatore di **un'altra squadra di Serie A**, il matching lo trova (squadra + cognome
esistono davvero) e gli fabbrica avversario e casa/trasferta.

**Prova [Certo]**, su `data/matchday_stats.json` già committato:

```
righe con squadra non in partita: 3
  ('Sulemana K.', 'Atalanta', 'Bologna', 'Sassuolo')
  ('Sulemana K.', 'Atalanta', 'Sassuolo', 'Juventus')
  ('Sulemana K.', 'Atalanta', 'Monza', 'Sassuolo')
```

Stesso file, `:103`: con un solo candidato per cognome e squadra, l'iniziale viene
ignorata anche quando è diversa. Il matching la usa per scegliere tra omonimi, mai per
rifiutare.

**Perché costa punti.** Poco oggi (< 0,1 punti a giornata). Ma smentiva una garanzia
scritta in `CLAUDE.md` ("le squadre estranee restano escluse per costruzione"), ora
corretta.

**Correzione.** Due controlli nell'importer: scartare la riga se la squadra non è una
delle due della partita; rifiutare il match quando le due iniziali sono note e diverse.
Poi togliere le 3 righe dall'archivio.

> **Aggiornamento 27/09.** La pulizia dell'archivio girava a ogni import, non una volta
> sola: toglieva anche le righe di chi usciva dal listone o cambiava squadra. Tolta:
> resta il controllo alla scrittura, e lo storico non si accorcia più
> (`store.save_matchday_stats`).

---

### 8. Le giornate vuote si riempiono solo rilanciando gli import, e nessuno li rilancia

> **Risolto il 24/09** (fase A2, vedi [§ Piano](#piano-cosa-si-può-fare-subito)).

**Cosa si rompe.** Le 3 partite del 19/09 sono entrate in archivio senza giornata. La
fonte ora la fornisce (verificato il 24/09: Roma-Inter e Bologna-Torino hanno "Regular
Season - 5"), e i due import aggiornano le righe esistenti per `match_id`, quindi basta
rilanciarli. Il problema è che **non sono in nessuna routine**: la skill `formazione`
non li lancia, e neanche la routine programmata per il 27/09.

**Perché costa punti.** Finché non si rilanciano, 110 righe restano senza giornata, e
l'archivio smette di crescere: le partite giocate dopo il 19/09 non ci sono. La media
ristagna senza che nessuno se ne accorga.

**Correzione.** Aggiungere `import_calendario_seriea.py` e `import_matchday_stats.py`
alla routine della skill `formazione`. Costo: circa 50 chiamate BigBalls su 500 al
giorno disponibili.

---

## Rimossi dopo la verifica

Tolti dalla prima stesura perché, sul codice e sui dati di `main` o con le regole vere
della lega, non reggono.

| Era | Diceva | Perché è stato tolto |
|---|---|---|
| Difetto 2 | Il punteggio usa la media quando gioca e ignora quanto spesso gioca; correggere pesando per la probabilità | Con sostituzioni illimitate la media quando gioca **è** il criterio giusto. La correzione proposta peggiorava il consiglio (simulazione: 20,03 → 18,63). Resta vero solo per la copertura del ruolo |
| Difetto 4 | Il motore ignora il modificatore di difesa | La lega non lo usa |
| Difetto 5 | Il matching dei nomi assegna a un giocatore lo status di un altro (es. il portiere dell'Inter) | Falso sui dati veri: lo scrape del 21/09 dà 468 abbinamenti esatti e 0 passati dal fallback, perché fantacalcio.it usa la stessa convenzione dei nomi del listone ("Martinez Jo."). Il portiere dell'Inter ha lo status giusto. Il fallback a sottostringa resta un rischio latente, a bassa priorità |
| Difetto 1, parte infortuni | `injuries.json` non viene letto e `infortunato` non è mai assegnato | Già risolto il 21/09: `apply_formazioni_status.py` applica gli infortuni sopra le probabili. Oggi `infortunato` viene assegnato davvero (50 giocatori) |
| Difetto 1, prova | Lo scraper ignora la lista indisponibili della pagina | La pagina non ha una lista indisponibili. La prova usava un HTML inventato |
| Difetto 11 | Le giornate nulle resteranno nulle per sempre | La fonte le riempie; rilanciare gli import basta (ora è il difetto 8) |
| Varie | Uno schierato che non gioca "consuma un cambio" | I cambi sono illimitati |

---

## Piano: cosa si può fare subito

Tutto ciò che segue lavora sui dati già presenti in `data/`: non serve né l'asta né i
voti. Ogni fase si verifica con la rosa simulata di [§ Riprodurre](#riprodurre).

**Fase A — dati e regole** (basso rischio, sistema la materia prima)

| # | Cosa | Dove | Difetto | Stato |
|---|---|---|---|---|
| A1 | Scrivere le regole della lega | `config/league.json` | — | fatto 24/09 |
| A2 | Rilanciare gli import calendario e statistiche, e metterli nel giro quotidiano | skill `aggiorna-dati` | 8 | fatto 24/09 |
| A3 | Due controlli nell'importer statistiche + togliere le 3 righe di Sulemana | `import_matchday_stats.py`, `data/matchday_stats.json` | 7 | fatto 24/09 |

**Fase B — il motore** (il cuore; B1 e B2 vanno fatti insieme)

| # | Cosa | Dove | Difetto | Stato |
|---|---|---|---|---|
| B1 | Panchina ordinata per media dentro ogni ruolo, esclusi in lista a parte, numerata | `roster.py`, `report_formazione.py` | 1 | fatto 24/09 |
| B2 | Togliere la penalità −1,5 dall'ordine; salvare la percentuale come numero e usarla per gli avvisi | `apply_formazioni_status.py`, `roster.py` | 2 | fatto 24/09 |
| B3 | Frenare le medie su pochi voti e stampare "media X su N voti" | `roster.py`, `report_formazione.py` | 3 | fatto 24/09 |
| B4 | Non bloccare il report se un ruolo è senza dati: slot lasciato a te con il motivo | `roster.py`, `report_formazione.py` | 5 | fatto 24/09 |

**Fase C — affidabilità di quello che leggi**

| # | Cosa | Dove | Difetto | Stato |
|---|---|---|---|---|
| C1 | Chi sparisce dalle probabili passa a `n/d`; status più vecchio di 4 giorni segnalato | `apply_formazioni_status.py`, `roster.py` | 4 | fatto 24/09 |
| C2 | Prossimo turno ricavato dalle date; prossima partita per giocatore; rinviati trattati con la regola della lega (sotto) | `roster.py`, `report_formazione.py` | 6 | fatto 24/09, rivisto 24/09 |

C2 è stata fatta diversamente da come la proponeva la prima stesura: **nessun numero di
giornata viene scritto nel calendario**. Un numero ricavato dalle date sarebbe un dato
stimato presentato come vero, e con un recupero giocato settimane dopo sbaglierebbe
tutti quelli successivi. Il report legge le date e basta. Le prime 10 partite non
giocate sono il prossimo turno solo se coprono le 20 squadre una volta ciascuna; se no
avvisa e non esclude nessuno.

**Rivista il 24/09 con il regolamento della lega.** La prima versione toglieva dai
disponibili chi aveva la partita rinviata: sbagliato, perché la lega non dà s.v. a nessuno.
La regola, chiarita dall'utente, vale per giornata: fino a 3 partite rinviate i loro
giocatori prendono tutti 6 politico, senza recupero; con più di 3 si aspettano tutte e
vale il voto del recupero. Una partita spostata ma giocata dentro la giornata non è un
rinvio. Ora nessuno viene escluso: con 6 politico il giocatore entra nell'ordine con 6
(sicuro, non lascia il posto alla panchina), altrimenti con la sua media. Il report
conta i rinvii e avvisa quando sono esattamente 3, perché un rinvio in più, anche dopo la
scadenza, cambia la regola per tutti. Due limiti restano: il conto è quello del momento
in cui gira il report, e non sappiamo ancora come BigBalls segna un rinvio (nessuno visto
finora). Se sposta la data invece di scrivere `postponed`, il turno non si ricostruisce e
il report lo dice invece di applicare la regola.

Trovato durante la C1: lo status veniva timbrato con la data di **oggi** anche quando le
probabili erano di giorni prima (per esempio se lo scrape del mattino fallisce e si
riapplica lo snapshot vecchio). Ora prende la data delle probabili, e lo script avvisa
se non sono di oggi.

**Trovati e corretti durante le fasi A e B**, fuori dall'elenco iniziale:

- `import_matchday_stats.py` riscaricava tutte le partite a ogni giro (44 chiamate
  oggi, 380 a fine stagione, su 500 al giorno) e **riscriveva ogni riga con
  `voto: None`**: il giorno in cui arriveranno i voti, il giro successivo li avrebbe
  cancellati. Ora è incrementale e conserva voto e fantavoto.
- Il matching non riconosceva le abbreviazioni del listone a più lettere ("Martinez
  Jo.") né i cognomi doppi ("Kolo Muani"): mancavano, tra gli altri, il portiere
  titolare dell'Inter e un attaccante della Juventus. Recuperati 12 giocatori.
- `scrape_formazioni.py` aggiungeva allo storico una fotografia di ~90 KB a ogni giro,
  anche con probabili identiche: con la routine quotidiana, ~22 MB a stagione. Ora
  salva solo le fotografie diverse dalla precedente.

**Da ritarare quando ci saranno i voti veri** (fatto il 27/09: il freno passa da 3 a 5,
vedi difetto 11). Il freno sulle medie (difetto 3) tira
verso la media di tutto il ruolo, con peso pari a 3 partite. Per un giocatore che
entra a spezzoni questa media è probabilmente ottimistica: con 1 voto da 5,30 finisce
davanti a chi ne ha 5 da 5,34. È il comportamento statisticamente coerente con quel
riferimento, ma il riferimento stesso va verificato sui voti reali. [Ipotesi]

**Dopo l'asta (27/09).** Caricare le 12 rose, e controllare che ogni squadra abbia
esattamente 25 giocatori e che ogni `player_id` esista in `players.json`: oggi
`roster.py` scarta senza avvisare chi non trova.

**Dopo i voti.** Collegare leghe.fantacalcio.it per `voto` e `fantavoto`
(`/gaming/v1/teamLineup`, identificato ma mai testato). Senza voti il motore non ha
nulla da ordinare. Tutto ciò che è sopra rende il motore pronto per il giorno in cui
arrivano.

**Solo alla fine.** Pesare avversario e casa/trasferta. È l'ultima cosa che conta, e
con 1-2 incontri a stagione per avversario il campione è debole per definizione.
(27/09: la forza difensiva dell'avversario, misurata su tutte le sue partite e non sullo
storico del giocatore contro di lui, entra nel valore; casa/trasferta no. Vedi
[§ Revisione del 27/09](#revisione-del-2709-il-valore-del-giocatore-sui-voti-veri).)

---

## Cosa resta aperto

Verificato il 24/09 sera rieseguendo le prove di ogni difetto sul codice di `main`
(16 controlli, 13 superati, poi chiusa anche la parte squalifiche). Tutti gli 8
difetti hanno la correzione verificata; le assunzioni della prima stesura stanno così:

- **«Se non abbiamo il dato, lo diciamo.»** Risolto. Chi sparisce dalle probabili
  diventa `n/d` con la nota; ogni punteggio mostra su quanti voti si basa; un
  giocatore di `ownership.json` sparito dal listone viene segnalato; uno status
  vecchio viene segnalato come tale.
- **«Il calendario sa chi gioca quando.»** Risolto per quello che serve: il prossimo
  turno e la prossima partita di ogni squadra si ricavano dalle date. Il numero di
  giornata delle partite future resta vuoto, per scelta: non si inventa.
- **«Le statistiche alimentano il consiglio.»** In parte, e per ora va bene così.
  Il motore usa solo `fantavoto` (ancora vuoto ovunque): con i cambi illimitati il
  criterio giusto è la media quando il giocatore gioca, quindi i minuti non servono
  all'ordine. Avversario e casa/trasferta sono mostrati nel report ma non entrano nel
  punteggio: è l'ultima cosa da pesare, col campione debole di 1-2 incontri a stagione.
- **«Il rischio squalifica è coperto.»** Risolto il 24/09, dopo questa verifica.
  `scrape_squalifiche.py` legge squalificati e diffidati dalla pagina "Indisponibili
  Serie A" di fantacalcio.it: lo squalificato diventa `squalificato` ed esce dai
  disponibili, il diffidato resta schierabile e il report lo segnala. Non si conta
  nessun cartellino da noi: la fonte ufficiale dice già chi è squalificato. Unico
  limite: quel giorno non c'era nessuno squalificato, quindi la lista piena è dedotta
  dalla struttura degli infortunati nella stessa pagina. Lo script segnala ogni
  sezione con una struttura diversa da quella attesa, ed è la prima cosa da guardare
  alla prima squalifica vera. [Probabile]
- **Il freno sulle medie** (difetto 3) va ritarato sui voti veri appena arrivano. Fatto
  il 27/09 (da 3 a 5), da riguardare con più giornate.

---

## Revisione del 27/09: il valore del giocatore sui voti veri

Il 27/09 il report proponeva un 4-3-3 con Elphege titolare in attacco. Un amico esperto
l'ha criticato; alcune critiche erano giuste, altre no. Questa revisione le verifica sui
voti veri delle giornate 1-5 e ricostruisce il valore di ogni giocatore **pezzo per
pezzo, tenendo solo i pezzi che migliorano le previsioni**.

Il metodo è uno solo, per tutto: `scripts/backtest_formazione.py`. Per ogni giornata N da
3 a 5 prevede il fantavoto di chi ha preso voto usando solo i dati fino a N-1, e misura
(a) l'errore medio assoluto (MAE) e (b) quante volte, tra due giocatori dello stesso
ruolo e della stessa squadra della lega, il modello mette davanti chi poi ha fatto di
più. Gli intervalli al 95% sono bootstrap appaiati (giocatori per il MAE, coppie
squadra-giornata per l'ordine). Il campione è piccolo: 786 voti da prevedere, 1093
coppie. **[Certo]**, comandi in [§ Riprodurre](#riprodurre).

### La verità scomoda, prima di tutto

**[Certo]** Con 2-4 giornate alle spalle nessun modello ordina i giocatori molto meglio
di una moneta. Il modello del 27/09 indovinava chi fa di più nel **53,5%** delle coppie
della stessa rosa, il nuovo nel **59,2%**. Il guadagno è reale (IC 95% da +2,5 a +8,7
punti), ma quattro scelte su dieci restano sbagliate lo stesso. Per questo il report ora
dice quando una scelta è una moneta (difetto 12).

### Difetti nuovi, con prova e correzione

#### 9. BigBalls etichetta male chi ha cambiato squadra: 179 voti senza statistiche

**Cosa si rompe.** Il box score di BigBalls mette spesso, a chi ha cambiato squadra, la
squadra vecchia o la nazionale. L'importer abbinava per squadra + cognome e li perdeva.

**Prova [Certo]** (box score scaricati il 27/09): nella stessa partita, con i minuti
giusti, Kean è segnato "Fiorentina" (nel listone è del Como), Curtis Jones "Liverpool"
(Inter), N. González "Argentina" (Juventus), Esposito Se. "Cagliari" (Sassuolo). Altri
non combaciavano per il nome: "E. Del Prato" (Delprato), "A. N&apos;Diaye" (entità
HTML), "C. Inao OulaÃ¯" (UTF-8 letto male), "Jacobo Ramón Naveros" (Ramon). Risultato:
**179 righe con voto e senza minuti**, tra cui tutti i voti di Esposito Se. e Fatah.

Quindi quella che il doc BigBalls chiamava "contaminazione da squadre estranee" è in
buona parte un'etichetta vecchia su giocatori veri della partita.

**Correzione.** Riconciliazione con i voti in `import_matchday_stats.py`: se
fantacalcio.it ha già una riga per quella partita di un giocatore che BigBalls non ha
abbinato, un nome del box score non abbinato che combacia con lui (cognome senza spazi e
punteggiatura dentro il nome BigBalls, iniziale se nota, minuti > 0 se ha preso voto)
gli dà le statistiche. Arricchisce solo righe già confermate da fantacalcio.it, non ne
crea. Chi resta fuori viene marcato `bigballs: "non_trovato"` e non si riscarica.

**Verifica [Certo].** 145 righe riconciliate. Controllo indipendente: gol, assist e
cartellini di BigBalls devono spiegare fantavoto − voto di fantacalcio.it (movimento,
bonus standard). Tornano in **130 righe riconciliate su 131** controllabili (99,2%),
contro 1155 su 1170 (98,7%) delle righe abbinate per squadra; le differenze sono rigori
sbagliati e assist contati in modo diverso dalle due fonti. Righe con voto e senza
statistiche: **da 179 a 42** (17 giocatori che BigBalls non ha proprio: Fatah, Leysen,
Osmajic, N'Dri...). Questo controllo è stato fatto una volta in sessione, non è in uno
script del repo.

#### 10. Il distacco tra due valori non diceva niente

**Prova [Certo]** (backtest, tutte le coppie dello stesso ruolo in Serie A nella stessa
giornata): con il modello del 27/09 la quota di ordini giusti **non cresce col
distacco** previsto: 52% sotto 0,10, 58% tra 0,30 e 0,50, 56% oltre 1 punto. Un 7,30
contro un 6,44 valeva quanto un 6,50 contro un 6,44.

**Correzione.** Freno, produzione e contesto (sotto). Con il nuovo modello la quota
cresce col distacco: 52% sotto 0,10, 55% tra 0,10 e 0,20, 60% tra 0,20 e 0,30, 63% tra
0,30 e 0,50, 69-70% oltre 0,50. Il numero ora vuol dire qualcosa.

#### 11. Il freno a 3 voti era troppo leggero

**Prova [Certo]**, backtest del nuovo modello con freno diverso, confronto appaiato con
freno 5:

| Freno | MAE | Ordine rosa | Δ MAE vs 5 | Δ ordine vs 5 |
|---|---|---|---|---|
| 1 | 1,075 | 0,570 | −0,042 [−0,065, −0,020] | −0,022 [−0,036, −0,006] |
| 3 | 1,041 | 0,576 | −0,008 [−0,015, −0,001] | −0,016 [−0,027, −0,005] |
| **5** | **1,033** | **0,592** | — | — |
| 10 | 1,031 | 0,605 | +0,003 [−0,005, +0,010] | +0,013 [−0,004, +0,030] |

Anche il modello del 27/09 con freno 5 al posto di 3 migliora il MAE (+0,015 [+0,007,
+0,025]) senza cambiare l'ordine.

**Correzione.** `FRENO_VOTI = 5`, il passo più piccolo che batte 3 su entrambe le
metriche. **[Probabile]** Il guadagno è un po' ottimista: 5 è scelto tra 4 valori sugli
stessi dati che lo misurano. La stima ruolo per ruolo (metodo dei momenti) è stata
provata ed è peggio (sotto): con 5 giornate la varianza vera tra giocatori di C e A esce
quasi zero e il freno esploderebbe.

#### 12. Nessun avviso sui quasi pari

Calvani contro Ferguson era 6,20 contro 6,20, Elphege contro Adams 6,50 contro 6,44:
differenze sotto il rumore presentate come scelte nette.

**Correzione.** `SOGLIA_PARI = 0,20`, dalla taratura del difetto 10: sotto quel distacco
il nuovo modello indovina il 52-55% delle volte. Il report ha una sezione **DECISIONI
TUE** con: le coppie entro la soglia al confine tra titolari e panchina e tra i primi due
cambi di un ruolo, i moduli che valgono entro la soglia da quello scelto (con chi entra
e chi esce), e i titolari con dati deboli (≤ 2 voti, voti senza tiri BigBalls,
avversario ignoto).

#### 13. La quotazione attuale non è un'informazione a priori

La sessione precedente aveva misurato una correlazione ~0,5 tra quotazione e media dei
voti, e proponeva di usarla come a priori.

**Prova [Certo]** (`--descrittive`, giocatori con ≥ 3 voti): la quotazione **attuale**
(QA) correla 0,51-0,69 per ruolo, ma fantacalcio.it la aggiorna in base ai voti delle
giornate giocate: è in parte la stessa media che dovrebbe prevedere. La quotazione
**iniziale** (QI, fissata prima della stagione, colonna "QI" della pagina del listone)
correla solo 0,22-0,29. L'FVM (0,30-0,58) è un valore di mercato che si muove anch'esso
con la stagione.

**Correzione.** `import_listone_fc.py` legge anche la QI (`quotazione_iniziale` in
`players.json`). Nel backtest la QI come riferimento del freno non migliora niente
(sotto), quindi non entra nel valore.

### Il modello

Per ogni giocatore con almeno un voto, **valore = base + contesto**:

- **base** = `(Σ fv' + 5 · media_ruolo') / (n + 5)` sugli ultimi `n ≤ 5` voti.
- **produzione**, dentro la base: `fv' = fantavoto + 3 · (c_ruolo · tiri in porta − gol
  su azione)` per D, C, A con statistiche BigBalls; altrimenti `fv' = fantavoto`. I gol su
  rigore restano. `c_ruolo` = gol su azione / tiri in porta del ruolo, sui voti della
  stagione: oggi D 0,265 (22/83), C 0,294 (57/194), A 0,324 (59/182). `media_ruolo'` è la
  media di `fv'` del ruolo: P 4,70, D 6,04, C 6,37, A 6,83.
- **contesto** = `β · (gol subiti a partita dall'avversario − 1,45)`, con i gol subiti
  frenati verso la media del campionato come se la squadra avesse 5 partite in più. β
  si stima sugli scarti di ogni giocatore dalla sua media, con i gol subiti
  dall'avversario calcolati **senza quella partita** (se no il gol del giocatore gonfia
  da solo i gol subiti e β). Oggi β = 0,40 per D/C/A insieme, 0,45 per i portieri.
  Esempio: Monza 1,93 gol subiti a partita → +0,19; Cagliari 0,93 → −0,21.

Parametri scelti a mano, tutti in cima a `roster.py`: ultimi 5 voti, freno 5 (difetto
11), bonus gol 3 (quello del fantavoto di fantacalcio.it), freno delle squadre 5
partite (il backtest non ne dipende finché tutte hanno giocato lo stesso numero di
partite: β si riadatta), soglia dei pari 0,20 (difetto 12). Tutto il resto è stimato sui
dati a ogni giro.

Il valore stima il fantavoto **se il giocatore prende voto**: la media degli ultimi voti
contiene già titolarità e spezzoni nella proporzione in cui gli capitano. La probabilità
di giocare non entra, come deciso il 24/09.

### Evidenza

Backtest giornate 3-5 (`python3 scripts/backtest_formazione.py`), MAE e ordine giusto
tra coppie della stessa rosa, differenze rispetto al modello del 27/09:

| Modello | MAE | Δ MAE [IC 95%] | Ordine | Δ ordine [IC 95%] |
|---|---|---|---|---|
| del 27/09: media ruolo, freno 3 | 1,073 | — | 0,535 | — |
| freno 5 | 1,058 | +0,015 [+0,007, +0,025] | 0,535 | +0,000 [−0,007, +0,007] |
| freno 5 + contesto | 1,046 | +0,027 [+0,008, +0,046] | 0,597 | +0,062 [+0,027, +0,097] |
| freno 5 + produzione | 1,046 | +0,027 [+0,010, +0,046] | 0,545 | +0,010 [−0,014, +0,033] |
| **nuovo: freno 5 + produzione + contesto** | **1,033** | **+0,040 [+0,017, +0,063]** | **0,592** | **+0,057 [+0,025, +0,087]** |

Ogni pezzo tolto dal nuovo, uno alla volta: senza contesto l'ordine perde 0,047 [+0,022,
+0,073] e il MAE 0,012 [+0,000, +0,024]; senza produzione il MAE perde 0,012 [+0,001,
+0,024] e l'ordine non cambia (−0,005 [−0,032, +0,020]). Il contesto serve all'ordine,
la produzione all'errore.

**Il caso Elphege.** Il timore era che il freno verso la media del ruolo gonfiasse chi
gioca poco. Guardando indietro è vero che i giocatori con pochi voti hanno medie più
basse (A: 6,16 con ≤ 2 voti, 6,96 con ≥ 4) **[Certo]**. Ma **in avanti** il modello non
li sovrastima **[Certo]**: previsto meno vero, attaccanti con 1 voto precedente +0,00 (26
casi), con 2 −0,77 (54 casi, sottostimati); centrocampisti −0,10 e −0,05; difensori
+0,19 e −0,03. Nessuna distorsione sistematica da correggere, e il freno più forte
migliora. **[Probabile]** Il motivo: la media bassa di chi ha pochi voti viene soprattutto
da chi ne ha pochi *perché* è scarso, e quello il freno lo vede già dopo 2-3 voti.

### Provati e scartati

Confronti appaiati con il nuovo modello (Δ positivo = la variante è meglio):

| Variante | Δ MAE [IC 95%] | Δ ordine [IC 95%] | Perché fuori |
|---|---|---|---|
| a priori dalla QI al posto della media del ruolo | +0,001 [−0,011, +0,012] | −0,018 [−0,035, +0,000] | niente di meglio, ordine forse peggio |
| titolare/spezzone (quota di spezzoni dello storico) | −0,002 [−0,003, −0,000] | +0,001 [−0,004, +0,005] | niente |
| titolare/spezzone con l'**oracolo** (sa chi partirà titolare) | −0,003 [−0,007, +0,001] | +0,002 [−0,008, +0,011] | niente neanche barando |
| casa/trasferta | −0,006 [−0,011, −0,000] | −0,001 [−0,017, +0,014] | peggio |
| freno stimato per ruolo | −0,014 [−0,028, +0,001] | −0,007 [−0,034, +0,018] | instabile, peggio |
| produzione a metà peso | −0,005 [−0,011, +0,001] | +0,006 [−0,015, +0,028] | dentro il rumore: resta il peso pieno |
| a priori QI + freno stimato sul modello del 27/09 | −0,029 [−0,058, −0,001] | −0,061 [−0,114, −0,011] | peggio |
| a priori dalla fantamedia della stagione scorsa (tutti i ruoli / solo attaccanti) | −0,002 [−0,015, +0,011] / −0,000 [−0,010, +0,010] | −0,014 [−0,032, +0,007] / −0,004 [−0,014, +0,006] | niente: vedi difetto 14 |
| portieri: contesto dai gol **fatti** dall'avversario invece che subiti | −0,000 [−0,008, +0,006] | +0,003 [−0,002, +0,009] | indistinguibile: da riguardare alla giornata 10 (sotto) |

Perché titolare/spezzone non serve **[Certo]**, `--descrittive`: il divario tra titolari
e subentrati è quasi tutto di **chi** gioca, non di quanto. Attaccanti: 7,00 da
titolare, 6,42 da subentrato; ma **lo stesso** attaccante vale da subentrato quanto da
titolare (titolare − subentrato: A −0,09 su 34 giocatori, C −0,45 su 68, D +0,21 su 38).
Chi entra dalla panchina è di solito più scarso, e la sua media lo dice già. La
probabilità di titolarità pubblicata non si è potuta provare nel backtest: il primo
snapshot delle probabili è del 21/09, dopo la giornata 5 **[Certo]**.

**Portieri, gol fatti o subiti dall'avversario [Certo]** (sezione "Solo portieri" del
backtest). Per un portiere il meccanismo giusto è l'attacco avversario, ma il contesto
di `roster.py` usa per tutti i gol *subiti* dall'avversario (le due cose sono
correlate: chi subisce tanto di solito segna poco). Su 55 previsioni di portieri, giornate
3-5: senza contesto MAE 1,107 e ordine 0,691; gol subiti 1,085 e 0,655; gol fatti 1,090 e
0,649. Gol fatti contro subiti: Δ MAE −0,005 [−0,108, +0,098]. Il β dei portieri cambia
molto da una giornata all'altra (sui gol subiti da 0,22 a 1,38). Nessuna differenza
misurabile, quindi `roster.py` resta com'è e la variante resta nel backtest. **Da
riguardare dopo la giornata 10** (circa il doppio dei voti dei portieri): si passa ai gol
fatti solo se li batte con un intervallo che esclude lo zero. L'impatto pratico oggi è
minimo, perché nelle rose di solito un solo portiere ha voti.

L'attacco della propria squadra non si può stimare sugli scarti del giocatore (è
costante per lui) ed è già nella sua media **[Probabile]**. Non è nel backtest.

### Critiche risultate sbagliate

- "Se non entra prima del 75' non prende voto": falso. **[Certo]** 129 voti presi con
  meno di 25' giocati, minimo 2'; nessun giocatore con 25' o più è rimasto senza voto.
- "Il 3-4-3 è meglio per principio": il bonus dei centrocampisti è già dentro il
  fantavoto e il motore sceglie il modulo col totale più alto. Il 27/09 il nuovo modello
  sceglie 3-4-3, ma perché lo dicono i giocatori, non un principio.
- "Calvani a Napoli no" per reputazione: il Napoli subisce 1,32 gol a partita (frenato),
  poco sotto la media di 1,45: il contesto vale −0,05. Lo decide il dato.
- "Due della stessa squadra sono rischiosi": è varianza, non valore atteso. Non entra
  nel valore e non c'è un avviso.
- Scambi: solo a gennaio (`regole_mercato`). Fuori scopo.

### La simulazione del 24/09, rifatta con la nuova definizione

Il principio "dentro un ruolo, prima chi vale di più quando prende voto" regge anche
quando il valore mescola titolarità e spezzoni. Sei giocatori con probabilità di partire
titolare, di entrare dalla panchina, e medie diverse nei due casi; 3 posti; valore atteso
calcolato in modo esatto (script in [§ Riprodurre](#riprodurre)). **[Certo]**:

```
valore se prende voto (nuovo)    20.506
media da titolare                20.506
valore x probabilità di voto     19.103
probabilità di titolarità        19.065
migliore sulle 720 possibili     20.506  = ordine per valore se prende voto: True

ballottaggio: ordine nuovo 20.527, migliore sulle 720 20.527, per media da titolare 20.444
```

Nell'ultima riga due giocatori si giocano un posto (parte esattamente uno dei due): i
loro voti non sono più indipendenti, e l'ordine per "valore se prende voto" resta il
migliore dei 720, mentre ordinare per media da titolare perde. **[Probabile]** La prova
generale dello scambio assume voti indipendenti; con un ballottaggio vale in questo
esempio, non l'ho dimostrata in generale.

#### 14. La stagione scorsa come punto di partenza (27/09, sera)

**Idea.** Con 5 voti la forma di quest'anno dice poco (il freno migliore è forte), e la
fantamedia della stagione scorsa è un'informazione fissata prima della stagione: niente
dati del futuro. `import_storico_stagioni.py` la salva per tutti i giocatori
(`data/storico_stagioni.json`).

**Descrittivo [Certo].** Correlazione tra fantamedia 2025-26 (almeno 10 voti) e media di
quest'anno (almeno 3 voti): D 0,26 (67 giocatori), C 0,27 (84), **A 0,60 (36)**. La
quotazione iniziale sugli stessi ruoli: 0,22, 0,29, 0,27.

**Backtest [Certo]** (varianti "a priori stagione scorsa" e "stagione scorsa solo
attaccanti": il riferimento del freno diventa una retta sulla fantamedia scorsa, chi non
ce l'ha resta con la media del ruolo). Rispetto al nuovo modello: tutti i ruoli Δ MAE
−0,002 [−0,015, +0,011], ordine −0,014 [−0,032, +0,007]; solo attaccanti Δ MAE −0,000
[−0,010, +0,010], ordine −0,004 [−0,014, +0,006]. Nessun miglioramento, quindi il modello
non cambia. [Probabile] La correlazione degli attaccanti è alta ma su 36 giocatori, e
nelle giornate 3-5 il freno verso la media del ruolo cattura già quasi tutto.
Resta nel backtest: da riguardare dopo la giornata 10. Nel report le stagioni passate si
mostrano come contesto ("STAGIONI PASSATE").

### Dati mancanti, da non inventare

- **Rigoristi**: il box score BigBalls ha **5 rigori calciati in 50 partite** (Colombo,
  Maldini, Varela G., Yeboah J., Zaccagni) **[Certo]**. Sono pochi per essere tutti
  **[Ipotesi]**: il rigorista non si ricava da qui. I gol su rigore restano nel fantavoto
  come sono, senza correzione. Una pagina "rigoristi" di fantacalcio.it non è stata letta
  né verificata: resta aperto.
- **42 voti senza statistiche BigBalls** (17 giocatori): per quei voti la produzione non
  si applica, e il report lo dice.
- **Probabilità di titolarità storica**: non c'è prima del 21/09.

---

## Riprodurre

**Revisione del 27/09** (sui dati del repo, non scrive niente):

```bash
python3 scripts/backtest_formazione.py                 # backtest, ablazione, soglia, distorsione
python3 scripts/backtest_formazione.py --descrittive   # i fatti descrittivi citati sopra
python3 scripts/report_formazione.py --team-id <my_team_id>
```

Simulazione dell'ordine con titolarità e spezzoni (valore atteso esatto):

```bash
python3 - <<'EOF'
import itertools
# (P titolare, P di entrare se parte in panchina, media da titolare, media da subentrato)
ROSA = [(0.9, 0.5, 6.4, 6.0), (0.5, 0.6, 7.6, 6.2), (1.0, 0.0, 6.0, 6.0),
        (0.3, 0.7, 8.0, 6.3), (0.8, 0.5, 6.7, 6.4), (0.6, 0.5, 7.0, 5.8)]
K = 3
def p_voto(g): s, q, _, _ = g; return s + (1 - s) * q
def valore_se_vota(g): s, q, vs, vb = g; return (s * vs + (1 - s) * q * vb) / p_voto(g)
def atteso_dati(ordine, pm):
    """Valore esatto con K posti e cambi illimitati, voti indipendenti dato pm."""
    dist = [1.0] + [0.0] * K; tot = 0.0
    for g in ordine:
        p, m = pm[g]; tot += p * m * sum(dist[:K]); nuova = [0.0] * (K + 1)
        for j, pj in enumerate(dist):
            if j == K: nuova[K] += pj; continue
            nuova[j + 1] += pj * p; nuova[j] += pj * (1 - p)
        dist = nuova
    return tot
atteso = lambda o: atteso_dati(o, {g: (p_voto(g), valore_se_vota(g)) for g in ROSA})
criteri = {"valore se prende voto (nuovo)": lambda g: -valore_se_vota(g),
           "media da titolare": lambda g: -g[2],
           "valore x probabilità di voto": lambda g: -valore_se_vota(g) * p_voto(g),
           "probabilità di titolarità": lambda g: -g[0]}
for nome, f in criteri.items():
    print(f"{nome:<32} {atteso(sorted(ROSA, key=f)):.3f}")
best = max(itertools.permutations(ROSA), key=atteso)
print(f"{'migliore sulle 720 possibili':<32} {atteso(best):.3f}  = ordine per valore se prende voto: "
      f"{list(best) == sorted(ROSA, key=criteri['valore se prende voto (nuovo)'])}")
# Ballottaggio: parte titolare esattamente uno tra A e B (50%).
ROSA[1] = (0.5, 0.6, 7.6, 6.2); ROSA[5] = (0.5, 0.5, 7.0, 5.8); A, B = ROSA[1], ROSA[5]
def atteso_ballottaggio(ordine):
    tot = 0.0
    for parte_a in (True, False):
        pm = {g: (p_voto(g), valore_se_vota(g)) for g in ROSA}
        for g, parte in ((A, parte_a), (B, not parte_a)):
            pm[g] = (1.0, g[2]) if parte else (g[1], g[3])
        tot += 0.5 * atteso_dati(ordine, pm)
    return tot
nuovo = sorted(ROSA, key=lambda g: -valore_se_vota(g))
best = max(itertools.permutations(ROSA), key=atteso_ballottaggio)
print(f"\nballottaggio: ordine nuovo {atteso_ballottaggio(nuovo):.3f}, migliore sulle 720 "
      f"{atteso_ballottaggio(best):.3f}, per media da titolare "
      f"{atteso_ballottaggio(sorted(ROSA, key=lambda g: -g[2])):.3f}")
EOF
```

**Revisione del 24/09.** Tutto in una copia di lavoro, il repo non viene toccato.

**Rosa simulata con fantavoto simulati** (i fantavoto reali non esistono ancora; la
simulazione serve solo a far girare il motore oltre il blocco "nessun modulo
schierabile"):

```bash
W=/tmp/fc-work && rm -rf $W && cp -r <percorso-del-repo> $W && cd $W && rm -rf .git
pip install -r requirements.txt

python3 - <<'PY'
import json, random
json.dump([{"id": f"t{i:02d}", "name": f"Squadra {i}", "owner": f"O{i}",
            "credits_total": 500, "credits_remaining": 500} for i in range(1, 13)],
          open("data/teams.json", "w"), ensure_ascii=False, indent=2)
cfg = json.load(open("config/league.json")); cfg["my_team_id"] = "t01"
json.dump(cfg, open("config/league.json", "w"), ensure_ascii=False, indent=2)

players = json.load(open("data/players.json")); byrole = {}
for p in players: byrole.setdefault(p["role"], []).append(p)
for r in byrole: byrole[r].sort(key=lambda p: (-p["quotazione"], p["name"]))
own = []
for r, n in {"P": 3, "D": 8, "C": 8, "A": 6}.items():
    for k in range(n):
        p = byrole[r][k * 12]
        own.append({"player_id": p["id"], "team_id": "t01",
                    "purchase_price": max(1, round(p["quotazione"] * 1.6)),
                    "acquired_on": "2026-09-20", "acquired_via": "asta"})
json.dump(own, open("data/ownership.json", "w"), ensure_ascii=False, indent=2)

random.seed(7); rows = json.load(open("data/matchday_stats.json"))
for x in rows:
    if x["minuti"] == 0: continue          # s.v.: voto e fantavoto restano null
    v = round(random.gauss(6.0, 0.7), 1)
    x["voto"] = v
    x["fantavoto"] = round(v + 3*x["gol"] + x["assist"]
                           - 0.5*x["cartellini_gialli"] - x["cartellini_rossi"], 1)
json.dump(rows, open("data/matchday_stats.json", "w"), ensure_ascii=False, indent=2)
PY

python3 scripts/report_formazione.py --team-id t01 --matchday 6
```

**Ordine ottimale con sostituzioni illimitate** (la simulazione citata in cima):

```bash
python3 - <<'PY'
import random, itertools
random.seed(1)
def valore(ordine, k, n=200000):
    tot = 0.0
    for _ in range(n):
        presi = 0; s = 0.0
        for P, m in ordine:                 # scorro titolari e poi panchina
            if presi == k: break
            if random.random() < P: s += m; presi += 1
        tot += s
    return tot / n
rosa = [(0.9, 6.2), (0.5, 7.4), (1.0, 6.0), (0.3, 7.8), (0.8, 6.6), (0.6, 6.9)]
print("per media     ", valore(sorted(rosa, key=lambda x: -x[1]), 3))
print("per media x P ", valore(sorted(rosa, key=lambda x: -x[0]*x[1]), 3))
best = max(itertools.permutations(rosa), key=lambda o: valore(o, 3, 20000))
print("migliore      ", valore(best, 3), [m for _, m in best])
PY
```
