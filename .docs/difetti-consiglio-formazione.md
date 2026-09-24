# Difetti del consiglio di formazione — revisione avversariale

Revisione del **24/09/2026** della catena che produce l'unico output che conta:
`data/` → `scripts/lib/roster.py` → `scripts/report_formazione.py` → l'undici da
schierare.

**Ricontrollata la sera del 24/09** sul codice e sui dati di `main`. La prima stesura
era stata eseguita su una copia locale non aggiornata, e le regole della lega non erano
ancora note. Dopo la verifica sono stati tolti 3 difetti e corrette 3 affermazioni,
elencati in [§ Rimossi dopo la verifica](#rimossi-dopo-la-verifica). Tutto ciò che
resta qui è stato riverificato sul codice di `main` del 24/09.

Marcatori: **[Certo]** eseguito e visto · **[Probabile]** inferenza forte dal
codice · **[Ipotesi]** sto colmando un vuoto.

---

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
| C2 | Prossimo turno ricavato dalle date; prossima partita per giocatore; rinviati fuori dai disponibili | `roster.py`, `report_formazione.py` | 6 | fatto 24/09 |

C2 è stata fatta diversamente da come la proponeva la prima stesura: **nessun numero di
giornata viene scritto nel calendario**. Un numero ricavato dalle date sarebbe un dato
stimato presentato come vero, e con un recupero giocato settimane dopo sbaglierebbe
tutti quelli successivi. Il report legge le date e basta. Le prime 10 partite non
giocate sono il prossimo turno solo se coprono le 20 squadre una volta ciascuna; se no
avvisa e non esclude nessuno.

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

**Da ritarare quando ci saranno i voti veri.** Il freno sulle medie (difetto 3) tira
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
- **Il freno sulle medie** (difetto 3) va ritarato sui voti veri appena arrivano.

---

## Riprodurre

Tutto in una copia di lavoro, il repo non viene toccato.

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
