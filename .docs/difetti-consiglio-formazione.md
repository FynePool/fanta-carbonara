# Difetti del consiglio di formazione — revisione avversariale

Revisione del **24/09/2026** sulla catena che produce l'unico output che conta:
`data/` → `scripts/lib/roster.py` → `scripts/report_formazione.py` → l'undici da
schierare. Ogni difetto qui sotto è stato **eseguito e osservato**, non dedotto
leggendo il codice; dove c'è un'inferenza è marcata.

Marcatori: **[Certo]** eseguito e visto · **[Probabile]** inferenza forte dal
codice · **[Ipotesi]** sto colmando un vuoto.

Fuori scope: il modulo asta (`scripts/asta.py`, `.claude/skills/asta/`). L'asta si
fa in modo tradizionale e il modulo non viene usato. Resta però la dipendenza:
`report_formazione.py` legge `data/ownership.json` e `data/teams.json`, e con
`ownership.json` vuoto — cioè lo stato attuale del repo — non produce nulla:

```console
$ python3 scripts/report_formazione.py --team-id t01 --matchday 6
Giornata 6 — modalità classic
Impossibile proporre una formazione:
  - Nessun modulo schierabile con la rosa attuale e i dati disponibili.
```

Popolare `ownership.json` dopo l'asta è quindi un passo obbligato del percorso
critico, non un residuo del modulo asta (vedi § Percorso critico, passo 2).

---

## Premessa: il greedy non è il difetto

Per un modulo fissato, prendere i top-n per ruolo **è** l'ottimo esatto: i ruoli
sono insiemi disgiunti e la somma si decompone. Il codice enumera tutti e 7 i
moduli ammessi. La ricerca è corretta. [Certo, `roster.py:89-110`]

Il problema è la funzione obiettivo. `score_player` stima

> `E[fantavoto | il giocatore prende voto]`

mentre i punti veri sono

> `P(prende voto) × E[fantavoto] + (1 − P) × (punteggio del sostituto automatico)`

Tutto il meccanismo delle sostituzioni del Classic — panchina ordinata, s.v.,
numero di cambi ammessi — non esiste né in `roster.py` né in `config/league.json`.
Ottimizzare meglio la cosa sbagliata non serve.

---

## Difetti, ordinati per punti attesi persi a giornata

Le stime sono grossolane e il ragionamento è esplicitato caso per caso. Servono a
ordinare gli interventi, non a essere precise.

### 1. Gli indisponibili sono invisibili, e lo status non scade mai — 1-3 pt/giornata, code fino a 6

**Cosa si rompe.** `scrape_formazioni.py` non legge la lista degli indisponibili;
chi è fuori sparisce dallo snapshot, `apply_formazioni_status.py` lo classifica come
"non trovato" e **gli lascia lo status della settimana scorsa** — cioè "titolare".

**Dove.** `scripts/scrape_formazioni.py:83-84` legge solo `ul.player-list.starters`
e `.reserves` (il docstring alle righe 5-6 promette invece "ballottaggi,
indisponibili"). `scripts/apply_formazioni_status.py:83-85`:
`if entry is None: unmatched_players.append(p); continue` — nessuna scrittura,
nessun decadimento.

**Riproduzione** [Certo]:

```console
$ python3 scripts/scrape_formazioni.py --html /tmp/fake_probabili.html
  # la pagina contiene <ul class="player-list unavailable"> con Malen
OK: 1 squadre, 3 giocatori estratti.

$ python3 -c "import json;t=json.load(open('data/formazioni_correnti.json'))['teams'][0];\
print(list(t.keys()));print(any(x['name']=='Malen' for x in t['titolari']+t['panchina']))"
['serie_a_team', 'modulo', 'titolari', 'panchina']
False

$ python3 scripts/apply_formazioni_status.py | head -1
Aggiornati 3 status su 532 giocatori del listone.

$ # Malen era 'titolare' dal 2026-09-12 e tale resta:
Malen DOPO l'aggiornamento: {'status': 'titolare', 'status_note': 'settimana scorsa',
                             'status_updated_at': '2026-09-12'}
score_player(Malen) -> 9.04   (nessuna penalità, nessun flag)
```

**Corollario 1** [Certo]. `derive_status()` (`apply_formazioni_status.py:35-39`) può
restituire solo `titolare | ballottaggio | panchina`. Quindi
`EXCLUDED_STATUSES = {"infortunato", "squalificato"}` (`roster.py:6`) **è codice
irraggiungibile dalla pipeline automatica**: quei due status esistono solo se
scritti a mano in `players.json`.

**Corollario 2** [Certo]. `data/injuries.json` ha 60 voci con `expected_return`, e
`store.load_injuries()` non è chiamata da nessuno:

```console
$ grep -rn "injur" scripts/ --include=*.py
scripts/import_fantadraft.py:...   # solo l'importer
scripts/lib/store.py:40:def load_injuries():   # definita, mai usata
```

In una rosa simulata di 25 giocatori, **3 risultano in `injuries.json` con
`status: "in corso"`**: Solet, Bernabè, Santos A. (quest'ultimo *"proverà a tornare
arruolabile dalla seconda metà di ottobre"*).

**Perché costa punti.** L'output reale della pipeline completa (scrape probabili →
apply → report) schiera **Bernabè**, che in `injuries.json` risulta *"non fa parte
dei convocati per domenica contro il Genoa"*:

```
TITOLARI:
  [C] Bernardeschi              media ultime 5: 7.00
  [C] Paz N.                    media ultime 5: 6.97
  [C] McKennie                  media ultime 5: 6.80
  [C] Bernabè                   media ultime 5: 6.30     <-- infortunato in injuries.json
PANCHINA:
  [C] Pisilli                   media ultime 5: 5.70  status: ballottaggio
```

Pisilli finisce in panchina perché lo scrape gli ha dato "ballottaggio 60%" (−1,5);
Bernabè entra perché, essendo indisponibile, **non è nello scrape e conserva uno
status pulito**. Il sistema premia l'assenza di informazione. Bernabè prende s.v.,
il sito sostituisce col primo centrocampista in panchina con voto (Isaksen 5,75):
perdi ~1 punto e bruci uno dei cambi; se anche le riserve di ruolo sono s.v., perdi
l'intero slot.

**Correzione minima.**

1. In `scrape_formazioni.py`, parsare anche la lista indisponibili e marcarla
   `status: "indisponibile"`.
2. In `apply_formazioni_status.py`, per i "non trovati" **azzerare** lo status a
   `n/d` invece di lasciarlo: assente dalle probabili ≠ titolare.
3. In `score_player`, leggere `injuries.json` e restituire `None` + flag per chi ha
   un infortunio `in corso`.
4. In `score_player`, restituire `None` se `status_updated_at` è più vecchio di
   ~4 giorni.

---

### 2. Il punteggio è la media *condizionata al fatto che abbia giocato* — 1,5-3 pt/giornata

**Cosa si rompe.** `roster.py:44` scarta le righe senza `fantavoto`:

```python
votes = [r["fantavoto"] for r in rows if r.get("fantavoto") is not None]
```

Ma le righe senza fantavoto **sono** le giornate in cui il giocatore non ha giocato.
Il motore classifica quindi i giocatori sulla loro media *quando giocano*, e ignora
del tutto quanto spesso giocano.

**Riproduzione** [Certo] — undici scelto dal motore sui dati reali del repo:

```
TITOLARE           score g.squad in dist con voto min medi
Svilar              6.08       5       5       5      92
Doig                7.44       5       5       5      84
Dodò                6.50       4       4       1      22   <--
Dimarco             5.96       5       5       5      64
Bernardeschi        7.00       5       5       5      74
Paz N.              6.97       4       4       4      82
McKennie            6.80       4       1       1      90   <--
Bernabè             6.30       4       3       3      59
Malen               9.04       5       5       5      69
Romero D.           7.30       4       4       3      28   <--
Scamacca            6.85       4       4       4      60
```

- **Dodò**: 4 giornate in distinta, **1 sola con voto**, 22 minuti medi. Media 6,50 →
  titolare, secondo difensore.
- **McKennie**: la sua squadra ha giocato 4 giornate, lui compare in **1**. Media
  6,80 su n=1 → titolare.
- **Romero D.**: 28 minuti medi, tre spezzoni da 28'/55'/30' → 7,30, titolare.

**Perché costa punti.** Il contributo atteso di Dodò non è 6,50: è
`0,25 × 6,50 + 0,75 × (sostituto)`. Con Marcandalli in panchina (4 voti su 4, 5,85),
schierare Dodò rende ~5,75 contro 5,85 — e soprattutto **consuma un cambio**. Qui il
motore piazza 3 slot su 11 (27%) su giocatori ad alta probabilità di s.v.: i cambi
finiscono prima che servano davvero.

**Correzione minima.** In `average_fantavoto`, restituire anche il conteggio; in
`score_player`, moltiplicare per `p_voto = n_voti / n_giornate_giocate_dalla_squadra`
e aggiungere `(1 − p_voto) × 5.5` (stima grezza del sostituto). Il denominatore è già
calcolabile da `calendario_serie_a.json`.

---

### 3. "media ultime 5" è un'etichetta falsa: nessuna soglia di campione minimo — 0,5-1,5 pt/giornata

**Cosa si rompe.** `report_formazione.py:41` stampa
`f"media ultime 5: {score:.2f}"` qualunque sia `n`. McKennie viene presentato come
"media ultime 5: 6.80" con **un solo voto in archivio**.

**Dato preciso** [Certo], su `data/players.json` + `data/matchday_stats.json`:

| Ruolo | Nel listone | Con almeno un fantavoto | Con **un solo** voto |
|---|---|---|---|
| P | 64 | 20 (31%) | 1 |
| D | 190 | 128 (67%) | 16 |
| C | 192 | 134 (70%) | 12 |
| A | 86 | 57 (66%) | 2 |

**Perché costa punti.** È la maledizione del vincitore: ordinando per una media, il
massimo cade sistematicamente su chi ha il campione più piccolo e l'estrazione più
fortunata. Con σ per-partita ≈ 1,3 sul fantavoto [Ipotesi: valore di letteratura,
non misurabile su questi dati perché `fantavoto` è ovunque null], un giocatore con
n=1 ha errore standard 1,3 contro 0,58 di uno con n=5: verrà scelto molto più spesso
di quanto meriti. Ogni slot così scambiato costa ~0,4-0,8 punti.

**Correzione minima.** Due righe: stampare `media su {n} voti` invece di "media
ultime 5"; e in `score_player` restituire `None` (→ flag "valutazione manuale") sotto
3 voti, oppure applicare uno shrinkage verso 6.0: `(somma + 3*6.0) / (n + 3)`.

---

### 4. Il modificatore di difesa non è modellabile, e servirebbe `voto`, non `fantavoto` — 0-6 pt/giornata se la lega lo usa

**Cosa si rompe.** `config/league.json` non ha alcun campo per il modificatore di
difesa, né per il numero di sostituzioni, né per quanto vale un s.v. non sostituito.
`roster.py` non ha alcun ramo che dipenda dal numero di difensori schierati.

**Dato preciso** [Certo]. Il blocco `scoring` (`config/league.json:28-36`) **non è
letto da nessuno**:

```console
$ grep -rn "scoring\|bonus_gol\|malus_amm\|modificator" scripts/ --include=*.py
scripts/import_matchday_stats.py:12:l'unico che conta per lo scoring. `voto` e ...
scripts/lib/roster.py:70:    """Greedy suggestion: for each candidate module, ...
```

Solo commenti. Il blocco è anche incompleto: mancano **gol subito** e **porta
inviolata** del portiere, che nel Classic pesano ~1 punto a giornata sul solo
portiere. Finché il fantavoto arriva già calcolato da leghe.fantacalcio.it la cosa è
innocua; diventa un errore sistematico nel momento in cui qualcuno usa quella tabella
per calcolare un punteggio in proprio.

**Perché costa punti.** Il modificatore si calcola sulla media dei **voti** (non
fantavoto) di portiere + 3 migliori difensori, e solo schierando almeno 4 difensori
[Ipotesi sulla soglia e sulla tabella esatta: variano per lega, vanno lette nelle
impostazioni della lega vera]. Il motore ha scelto **3-4-3**: se il modificatore è
attivo, un 4-5-1 o 5-3-2 con la difesa giusta poteva valere +3/+6 punti che il 3-4-3
non prende mai. E il campo `voto` — separato da `fantavoto` — non compare in nessuna
roadmap: `roster.py` e `report_formazione.py` leggono solo `fantavoto`.

**Correzione minima.** Aggiungere a `config/league.json` tre campi
(`modificatore_difesa` con la tabella soglie, `sostituzioni_max`,
`voto_sv_non_sostituito`) e, se il modificatore è attivo, sommare il suo contributo
al totale nel confronto tra moduli (`roster.py:106`). Prima di tutto: **leggere le
impostazioni reali della lega** — oggi non sono scritte da nessuna parte.

---

### 5. Il matching nome→status assegna lo status di un altro giocatore — 0,3-1 pt/giornata

**Cosa si rompe.** `apply_formazioni_status.py:75-82`: se la chiave esatta fallisce,
il fallback cerca gli ingressi della stessa squadra il cui nome **contiene come
sottostringa** l'ultimo token del nome del listone. Per i **92 giocatori su 532** con
suffisso iniziale (`"Martinez Jo."`, convenzione FantaDraft) l'ultimo token è una o
due lettere — e la chiave esatta non combacia mai con fantacalcio.it, che pubblica il
cognome per esteso. Per quei 92 il fallback è l'unica strada.

**Riproduzione** [Certo] — simulazione sui 532 giocatori veri, snapshot costruito dai
cognomi reali:

```
  match corretto : 439
  MATCH SBAGLIATO: 7  (status di un altro giocatore scritto su questo)
  non trovato    : 86  (status precedente lasciato invariato)

  Martinez Jo.           (Inter       P) <- ha preso lo status di Jones          [fallback]
  Terracciano            (Milan       P) <- ha preso lo status di Terracciano    [esatto]
  Terracciano F.         (Milan       D) <- ha preso lo status di Loftus-Cheek   [fallback]
  Monteiro J.            (Lecce       C) <- ha preso lo status di Jean           [fallback]
  Esposito Se.           (Sassuolo    A) <- ha preso lo status di Leysen         [fallback]
  Rrahmani Al.           (Venezia     A) <- ha preso lo status di Halhal         [fallback]
  Robinson J.            (Monza       A) <- ha preso lo status di Strajnar       [fallback]
```

Non è un caso di bordo: il primo della lista è **il portiere titolare dell'Inter**
(quotazione 17). I due Terracciano del Milan mostrano l'altro lato: l'omonimo
corretto assorbe la chiave esatta, l'altro finisce a caso.

La simulazione è **generosa**: usa i cognomi del listone stesso. I nomi reali di
fantacalcio.it divergono di più, quindi i "non trovati" nella realtà saranno di più —
e ogni "non trovato" ricade nel difetto 1 (status stantio conservato).

**Perché costa punti.** Se Martinez Jo. è il tuo portiere e Jones è in panchina al
20%, il tuo portiere prende `status: "panchina"` e −1,5. Se lo status sbagliato è
invece "titolare 95%" su un giocatore realmente fuori, schieri un s.v.

**Correzione minima.** Nel fallback, rifiutare i candidati quando `last_token` è
lungo ≤2 caratteri (`if len(last_token) > 2 and ...`) e richiedere match esatto sul
cognome invece di `in`. I 92 diventano "non trovati" espliciti, che è l'esito onesto.

---

### 6. La penalità per titolarità incerta è piatta: la percentuale viene buttata — 0,5-1,5 pt/giornata

**Cosa si rompe.** `apply_formazioni_status.py:35-39` comprime la percentuale in tre
etichette, poi `roster.py:64-66` applica lo stesso `-1.5` a tutte e tre quelle
incerte.

**Riproduzione** [Certo]:

```
  fantacalcio.it: titolare   95%  ->  status 'titolare'      ->  penalità  0.0
  fantacalcio.it: titolare   89%  ->  status 'ballottaggio'  ->  penalità -1.5
  fantacalcio.it: panchina   39%  ->  status 'panchina'      ->  penalità -1.5
  fantacalcio.it: panchina    0%  ->  status 'panchina'      ->  penalità -1.5
```

**Perché costa punti.** Due discontinuità assurde e una fusione assurda. Un giocatore
all'89% vale quasi quanto uno al 95%, ma perde 1,5 punti secchi: nell'output reale
del difetto 1, **Pisilli al 60% scende da 7,20 a 5,70 e lascia il posto a Bernabè
infortunato a 6,30**. All'opposto, un giocatore allo 0% di titolarità è penalizzato
esattamente come uno al 45%. La percentuale è nota, viene persino salvata in
`status_note` come testo, e poi scartata dal calcolo.

**Correzione minima.** Salvare `percentuale` come campo numerico in `players.json`
(non dentro una stringa) e in `score_player` usare
`avg * pct/100 + (1 − pct/100) * 5.5` al posto del `-1.5`.

---

### 7. Un portiere senza storico e il report si rifiuta di rispondere — 0 punti nelle settimane buone, tutta la giornata in quelle cattive

**Cosa si rompe.** `roster.py:96-102`: per ogni modulo i candidati sono i soli
giocatori con `score_player is not None`; se un ruolo non ne ha abbastanza il modulo
viene scartato. Con 0 portieri valutabili cadono tutti e 7.

**Dato preciso** [Certo]: **solo 20 dei 64 portieri del listone (31%) hanno almeno un
fantavoto** — in pratica uno per squadra di Serie A. Ogni rosa ne avrà quindi
esattamente uno valutabile. Se quell'uno è un nuovo acquisto, un portiere appena
promosso o uno che ha saltato le prime giornate:

```console
$ # rimuovo le righe di Svilar, unico portiere della rosa con storico
$ python3 scripts/report_formazione.py --team-id t01 --matchday 6
Giornata 6 — modalità classic
Impossibile proporre una formazione:
  - Svilar: nessuno storico fantavoto disponibile, valutazione manuale necessaria
  ...
```

**Perché costa punti.** Il modo di fallire è "nessun consiglio", e capita
esattamente nelle settimane in cui i dati mancano — cioè le prime giornate dopo
l'asta, quando servirebbe di più. Peggio: il meccanismo introduce un bias silenzioso
anche quando non fallisce. **Il modulo viene scelto dalla disponibilità dei dati, non
dal calcio**: con 2 soli attaccanti valutabili tutti i moduli a 3 punte scompaiono e
il motore "sceglie" un 4-5-1 senza dire che l'ha scelto per ignoranza.

**Correzione minima.** Fare fallback su `quotazione`/`fvm` (già presenti per tutti e
532) quando lo storico manca, marcando lo slot come stimato invece di scartarlo; e
stampare, per ogni modulo scartato, il motivo.

---

### 8. La panchina non è ordinata — 0,3-0,8 pt/giornata

**Cosa si rompe.** `roster.py:108-109`:
`bench = [p for p in roster if p["id"] not in bench_ids]` — ordine di
`ownership.json`. Nel Classic la panchina è **ordinata** e le sostituzioni
automatiche la scorrono in quell'ordine.

**Riproduzione** [Certo], dall'output reale:

```
PANCHINA:
  [P] Perri                     media ultime 5: n/d
  [P] Christensen O.            media ultime 5: n/d
  [D] Solet                     media ultime 5: 5.77
  [D] Diego Carlos              media ultime 5: n/d
  [D] Balerdi                   media ultime 5: n/d
  [D] Marcandalli               media ultime 5: 5.85
```

**Perché costa punti.** Se Dimarco prende s.v. entra Solet (5,77) e non Marcandalli
(5,85), che è quarto. Sono decimi per singolo cambio, ma è gratis da correggere: il
report è l'unico posto che conosce i punteggi, e non li usa per l'unica cosa che la
panchina fa.

**Correzione minima.** Una riga —
`bench.sort(key=lambda p: (score_player(p) is None, -(score_player(p) or 0)))` — e
stampare la panchina numerata.

---

### 9. La garanzia "le squadre estranee non hanno match possibile" è falsa — <0,1 pt/giornata, ma smentisce un invariante documentato

**Cosa si rompe.** `import_matchday_stats.py:154-157`:

```python
if team == match["squadra_casa"]:
    opponent, home_away = match["squadra_trasferta"], "casa"
else:
    opponent, home_away = match["squadra_casa"], "trasferta"
```

Nessun controllo che `team` sia una delle due squadre della partita. Quando il box
score contaminato porta un giocatore di una **terza squadra di Serie A**,
`match_player` lo trova regolarmente nell'indice (la coppia squadra+cognome esiste
davvero) e il ramo `else` gli fabbrica un avversario e un casa/trasferta inventati.

**Riproduzione** [Certo], su `data/matchday_stats.json` già committato — confronto di
ogni riga col calendario, verificando che la squadra del giocatore sia una delle due:

```
ok 1593   bad 3   match non in calendario 0
  ('TEAM NON IN PARTITA', 'Sulemana K.', 'Atalanta', 'Bologna', 'Sassuolo', 'Bologna', 'trasferta')
  ('TEAM NON IN PARTITA', 'Sulemana K.', 'Atalanta', 'Sassuolo', 'Juventus', 'Sassuolo', 'trasferta')
  ('TEAM NON IN PARTITA', 'Sulemana K.', 'Atalanta', 'Monza',    'Sassuolo', 'Monza',   'trasferta')
```

Sulemana K. (Atalanta, A) ha in archivio tre partite del Sassuolo, con avversario e
casa/trasferta inventati. `CLAUDE.md` afferma che le squadre estranee «non hanno
match possibile e restano escluse per costruzione»: accade il contrario ogni volta
che la contaminazione è un giocatore di *un'altra squadra di Serie A*.

**Secondo problema nello stesso file** [Certo per lettura,
`import_matchday_stats.py:103-104`]: `if len(candidates) == 1: return candidates[0][0]`
— l'iniziale è usata **solo** per disambiguare, **mai** per rifiutare. Un
"K. Sulemana" del Sassuolo verrebbe assegnato a `Sulemana I.` del Sassuolo senza un
fiato, perché è l'unico candidato con quel cognome in quella squadra. Ogni giocatore
di Serie A assente dal listone che condivide il cognome con un compagno *presente*
eredita le sue statistiche.

**Correzione minima.** Due `if`: saltare la riga se
`team not in (match["squadra_casa"], match["squadra_trasferta"])`; e in
`match_player`, rifiutare quando l'iniziale cercata e quella del candidato unico sono
entrambe note e diverse.

---

### 10. Il calendario futuro non ha giornata: il sistema non sa né quando né contro chi si gioca — oggi 0, blocca la roadmap

**Cosa si rompe.** `--matchday` in `report_formazione.py:29` è **solo un'etichetta**.

**Riproduzione** [Certo]:

```console
$ diff <(python3 scripts/report_formazione.py --team-id t01 --matchday 1) \
       <(python3 scripts/report_formazione.py --team-id t01 --matchday 38)
1c1
< Giornata 1 — modalità classic
---
> Giornata 38 — modalità classic
```

**Dato preciso** [Certo], più grave:

```console
$ # su data/calendario_serie_a.json
scheduled: 335   con giornata non nulla: 0
giornata_raw campione scheduled: [(None, 335)]
```

**Tutte e 335 le partite non ancora giocate hanno `giornata: null`.** `CLAUDE.md`
documenta il ritardo di un giorno sulle partite appena finite (3 casi); nessuno ha
notato che per il resto della stagione la giornata **non c'è affatto**. Il README
dichiara «Calendario e risultati per giornata | 379 partite»: è vero per 41 righe su
379.

**Perché costa punti.** Tre cose diventano impossibili, non difficili: sapere qual è
la prossima giornata; sapere chi affronta un tuo giocatore; sapere se la sua squadra
gioca. L'ultima è il caso silenzioso pericoloso: una **partita rinviata** manda in
s.v. tutti i tuoi giocatori di quelle due squadre, e il report li schiera con lo
stesso tono sicuro di sempre. Raro (1-2 volte a stagione) ma può valere 3-4 slot.

**Correzione minima.** `data_utc` c'è per tutte le 335: derivare la giornata
raggruppando le partite per finestra temporale (10 per gruppo) e scriverla in
`giornata` in `import_calendario_seriea.py`; oppure usare direttamente `data_utc` per
rispondere «quali partite nei prossimi 4 giorni». Poi far leggere quel dato a
`report_formazione.py` e flaggare i giocatori la cui squadra non compare.

---

### 11. Il buco temporale in `matchday: null` si allargherà — 0 oggi, crescente

**Cosa si rompe.** `roster.py:31-36` mette le righe senza giornata **in fondo**
all'ordinamento, con la motivazione (nel docstring) che «una riga senza giornata è
quasi sempre la più recente». Vero oggi. Falso tra due settimane: nessuno script
riempie quelle giornate a posteriori, quindi le 110 righe della 5ª giornata
resteranno `null` per sempre e continueranno a ordinarsi dopo la 10ª, la 20ª, la 38ª.
[Probabile: certo per lettura del codice e `git log`, che non mostra alcun passo di
backfill; l'effetto si manifesterà al prossimo import]

**Perché costa punti.** La finestra `last_n=5` di `average_fantavoto` verrà
permanentemente inquinata da 3 partite di settembre. Non è un crash: è un punteggio
leggermente sbagliato per sempre.

**Correzione minima.** In `import_matchday_stats.py:162`, se `match["giornata"]` è
`None`, ricavarla dal `match_id` in `calendario_serie_a.json` al refresh successivo —
e riscrivere le righe già esistenti, non solo le nuove.

---

## Il percorso critico

Sequenza minima perché la prima giornata utile dopo l'asta produca un consiglio
fidato. In quest'ordine, perché ogni passo dipende dal precedente.

1. **Scrivere le regole vere della lega** in `config/league.json`: modificatore di
   difesa sì/no e con quale tabella, numero di sostituzioni, cosa vale un s.v. non
   sostituito. Senza questo il confronto tra moduli (`roster.py:106`) non può essere
   corretto nemmeno in linea di principio. Mezz'ora sul sito della lega, e sblocca
   tutto il resto.
2. **Popolare `ownership.json` e `teams.json`** con le 12 rose reali. L'asta è
   tradizionale, quindi questo passo è manuale o via `leghe_fc_inspect.py rose`.
   Attenzione: mappare i nomi della lega vera sugli id `fd*` del listone è lo stesso
   problema di matching del difetto 5, e qui un errore non sposta uno status ma
   **cancella un giocatore dalla rosa in silenzio** — `roster.py:27` scarta senza
   dire niente le righe di `ownership.json` il cui `player_id` non è in
   `players.json`. Va verificato che le righe scritte siano esattamente 25 per
   squadra, e che ogni `player_id` esista.
3. **Collegare `leghe.fantacalcio.it` per `voto` e `fantavoto`**
   (`/gaming/v1/teamLineup`, identificato ma mai testato). È la dipendenza più lunga:
   va cominciata appena la lega esiste. Servono **entrambi** i campi, non solo il
   fantavoto, se il modificatore di difesa è attivo.
4. **Far decadere lo status invece di conservarlo**: indisponibili nello scrape,
   "non trovati" → `n/d`, `injuries.json` letto da `score_player`,
   `status_updated_at` più vecchio di 4 giorni → `None`. (Difetto 1.)
5. **Mettere `P(prende voto)` nel punteggio** e stampare il numero di voti invece di
   "media ultime 5". (Difetti 2 e 3, ~20 righe, nessuna dipendenza esterna.)
6. **Ricostruire la giornata sulle 335 partite `scheduled`** da `data_utc`, e far
   leggere il calendario a `report_formazione.py` almeno per rispondere «la sua
   squadra gioca?». (Difetto 10.)
7. **Ordinare la panchina** e numerarla nel report. (Difetto 8.)
8. Solo dopo: pesare avversario e casa/trasferta — l'unica voce che il README già
   elenca come mancante, e l'ultima che conta.

I passi 1, 4, 5 e 7 si possono fare **subito**, senza nessun dato nuovo e senza
aspettare l'asta.

---

## Cosa dovrebbe essere vero e non lo è

Le assunzioni implicite del progetto che i dati non sostengono.

- **«Se non abbiamo il dato, lo diciamo.»** [Certo] È la regola fondante del
  progetto, e la pipeline la viola nel punto peggiore: un giocatore assente dalle
  probabili non produce un «non lo so», produce lo status della settimana scorsa.
  L'assenza di informazione viene silenziosamente convertita in informazione
  positiva.
- **«La media del fantavoto misura quanto vale un giocatore.»** [Certo] Misura quanto
  vale *quando gioca*. Su 1596 righe, **422 hanno `minuti: 0`** e 540 hanno meno di
  20 minuti: un terzo dei dati riguarda giocatori che non sono scesi in campo, e il
  motore lo tratta come campione mancante invece che come il segnale che è.
- **«Il matching per nome è un rischio noto e controllato.»** [Certo] È noto, non è
  controllato: 7 assegnazioni sbagliate su 532 nella pipeline status (incluso il
  portiere dell'Inter), 3 righe di statistiche attribuite al giocatore sbagliato
  nell'archivio già committato, e in nessuno dei due casi il codice se ne accorge —
  solo un confronto esterno col calendario le trova.
- **«Abbiamo il calendario della Serie A.»** [Certo] Ci sono i risultati di 44 partite
  e 335 date senza giornata. Per la domanda che serve — *chi gioca contro chi nella
  prossima giornata* — il file non risponde.
- **«I 1596 record di statistiche alimentano il consiglio.»** [Certo] `grep` su
  `roster.py` e `report_formazione.py`: nessuna occorrenza di `minuti`, `cartellini`,
  `falli`, `gol`, `opponent_serie_a_team`, `calendario`, `injuries`, `scoring`. Il
  motore legge **una sola colonna** delle quattordici, `fantavoto`, che è null in
  tutte e 1596 le righe. Le altre tredici non sono sprecate — sono la materia prima
  dei fix 2 e 10 — ma oggi non sono collegate a niente. `player_history_vs_opponent`
  e `store.load_injuries()` sono definite e mai chiamate.
- **«Il rischio squalifica è coperto.»** [Certo] Il README lo cita come motivazione
  dell'import dei cartellini (*«un difensore a 3 gialli è a un passo dalla
  squalifica»*); nessuna riga di codice somma i gialli di un giocatore. Oggi nessuno
  è oltre 1 giallo, quindi non costa ancora nulla — ma alla 15ª giornata sì, e il
  conteggio è a una `sum()` di distanza.

---

## Riprodurre tutto

Copia di lavoro, non tocca il repo. `ownership.json` viene scritto direttamente,
come si farebbe trascrivendo una rosa dopo un'asta tradizionale.

```bash
W=/tmp/fc-work && rm -rf $W && cp -r ~/Documents/fanta-carbonara $W && cd $W && rm -rf .git
pip install beautifulsoup4

python3 - <<'PY'
import json, random

# 12 squadre + my_team_id
json.dump([{"id": f"t{i:02d}", "name": f"Squadra {i}", "owner": f"O{i}",
            "credits_total": 500, "credits_remaining": 500} for i in range(1, 13)],
          open("data/teams.json", "w"), ensure_ascii=False, indent=2)
cfg = json.load(open("config/league.json")); cfg["my_team_id"] = "t01"
json.dump(cfg, open("config/league.json", "w"), ensure_ascii=False, indent=2)

# rosa 3P-8D-8C-6A: come se 12 squadre pescassero a turno per quotazione
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

# fantavoto come lo darebbe leghe.fantacalcio.it: s.v. dove minuti == 0
random.seed(7); rows = json.load(open("data/matchday_stats.json"))
for x in rows:
    if x["minuti"] == 0: continue
    v = round(random.gauss(6.0, 0.7), 1)
    x["voto"] = v
    x["fantavoto"] = round(v + 3*x["gol"] + x["assist"]
                           - 0.5*x["cartellini_gialli"] - x["cartellini_rossi"], 1)
json.dump(rows, open("data/matchday_stats.json", "w"), ensure_ascii=False, indent=2)
PY

python3 scripts/report_formazione.py --team-id t01 --matchday 6
```

Il `fantavoto` è **simulato**: serve solo a far girare il motore oltre il blocco
noto (nessuna delle 1596 righe ha un fantavoto reale). I difetti 1, 5, 7, 9, 10 e 11
non dipendono da quella simulazione e si osservano anche sui dati grezzi del repo.

Per il difetto 1 serve una pagina di prova con la sezione indisponibili:

```bash
cat > /tmp/fake_probabili.html <<'HTML'
<html><body>
<div class="team-card">
  <h3 class="team-name">Roma</h3>
  <div class="team-formation">3-4-2-1</div>
  <ul class="player-list starters">
    <li class="player-item"><span class="role" data-value="p"></span>
      <a class="player-name" href="/x/svilar/1">Svilar</a><div class="progress-value">95%</div></li>
    <li class="player-item"><span class="role" data-value="c"></span>
      <a class="player-name" href="/x/pisilli/2">Pisilli</a><div class="progress-value">60%</div></li>
  </ul>
  <ul class="player-list reserves">
    <li class="player-item"><span class="role" data-value="d"></span>
      <a class="player-name" href="/x/balerdi/3">Balerdi</a><div class="progress-value">30%</div></li>
  </ul>
  <ul class="player-list unavailable">
    <li class="player-item"><span class="role" data-value="a"></span>
      <a class="player-name" href="/x/malen/4">Malen</a><div class="progress-value">0%</div></li>
  </ul>
</div>
</body></html>
HTML

python3 scripts/scrape_formazioni.py --html /tmp/fake_probabili.html
python3 scripts/apply_formazioni_status.py
python3 scripts/report_formazione.py --team-id t01 --matchday 6
```
