# API di leghe.fantacalcio.it — riferimento verificato

API privata e non documentata (`https://apileague.fantacalcio.it`), usata dal sito e
dall'app di leghe.fantacalcio.it. Il client è `scripts/lib/leghe_fc_client.py`, portato
da [@legasanpetrux/leghe-fc-client](https://github.com/legasanpetrux/leghe-fc-client)
(MIT). Solo lettura, solo la nostra lega, uso a proprio rischio. Tutto quello che segue è
stato **verificato il 27/09/2026 sulla lega vera** (FantaCarbonaraXI, id 923348), salvo
dove è scritto il contrario.

## Autenticazione

- L'`app_key` (header `app_key`, minuscolo con underscore) è pubblica: il client la
  legge dalla homepage di leghe.fantacalcio.it.
- Login con `LEGHE_FC_USERNAME`/`LEGHE_FC_PASSWORD` da ambiente. Il payload ha **due jwt**:
  `data.jwt` (d'account) e `data.leghe[i].jwt` (di lega). Solo il secondo funziona sulle
  chiamate `/onboarding/v1/league/*`: usare sempre `get_league_jwt()`.
- `data.leghe` elenca le leghe dell'account: sul nostro c'è solo FantaCarbonaraXI
  (divisione A, account admin).

## Endpoint usati

### `/onboarding/v1/league/teams/all` — rose e crediti (`import_rose_lega.py`)

Una riga per squadra della lega, **anche quelle vuote**: il 27/09 erano 18, di cui 6
senza giocatori (ragazzi che quest'anno non giocano). Campi:

| Campo | Cosa | Note |
|---|---|---|
| `id` | id della squadra | lo stesso di `tmids` nelle competizioni e di `tIdH`/`tIdA` nel calendario |
| `n` | nome | può cambiare quando lo cambia il proprietario |
| `cal` | id fantacalcio dei giocatori, separati da `;` | stessi id del listone (`fd<id>`) |
| `cs` | prezzi d'acquisto, stesso ordine di `cal` | |
| `cr` / `crs` / `cri` | crediti rimanenti / spesi / iniziali | `cri` = 554 |
| `bm` | correzione dei crediti | -54: i crediti veri sono `cri + bm` = 500. Ss Igari ha `bm` 0 (554), e va bene così |
| `r` | giocatori per ruolo | |
| `nu`, `all` | username del proprietario | **dato personale: mai salvato** |

Mentre l'admin sposta una rosa da una squadra a un'altra, per qualche secondo l'API può
restituire quasi tutte le rose vuote: successo il 27/09. Per questo l'import non scrive se
una squadra in gioco risulta vuota.

### `/onboarding/v1/league/competitions` — competizioni (`import_calendario_lega.py`)

Una riga per competizione: `id`, `name`, `type` (1 = campionato), `sDay`/`eDay` (prima e
ultima giornata di Serie A), `tmids` (squadre), `del` (eliminata), `lid`, `win`. Il 27/09
c'era solo il campionato:

- **FANTACARBONARA**, id 858469, giornate di Serie A 6-38 (33 giornate), le 12 squadre in
  gioco (Ss Igari sì, Fortitudo no).

Coppa Italia ed Europa League non ci sono ancora: l'import legge tutte le competizioni,
quindi entreranno da sole.

### `/onboarding/v1/league/competition/calendar/<id>` — calendario e risultati

Una riga per giornata: `matchDay` (giornata della competizione, da 1), `championshipMatchDay`
(giornata di Serie A), `calculated`, `matches`. Per partita: `tIdH`/`tIdA` (squadre),
`ptH`/`ptA` (punteggio), `standingPtH`/`standingPtA` (punti in classifica), `result`,
`resultSR`. Prima del calcolo: punteggi 0, risultato "-". Nel campionato ogni squadra
incontra ognuna delle altre 3 volte.

**Non visto ancora**: una giornata calcolata. Da controllare alla prima (Serie A 6,
10-12/10): che `ptH`/`ptA` siano i fantapunti totali e `result` il punteggio in gol, e
cosa contiene `resultSR`.

### `/gaming/v1/teamLineup/<competizione>/<giornata>/<giornata Serie A>/<casa>/<trasferta>` — formazioni inserite (`controlla_formazione.py`)

Le formazioni delle due squadre di una partita della lega (`?extra=1` dà la stessa risposta).
Il 27/09 mattina, prima che qualcuno schierasse, rispondeva `"home": null, "away": null`.
**Verificato il 29/09** (giornata 1, Serie A 6, 11 giorni prima della scadenza): appena una
squadra salva la formazione, la risposta la contiene. Campi in cima: `cal` (giornata
calcolata), `mday` (giornata della competizione), `cmday` (giornata di Serie A), `idcomp`,
`sign`/`res`/`resr` (esito: `"X"`, `"0-0"` prima del calcolo). Per squadra (`home`/`away`,
`null` se non ha inserito niente):

| Campo | Cosa | Note |
|---|---|---|
| `tid` | id della squadra | lo stesso di `teams.json` |
| `useId` | id dell'utente | **dato personale: mai salvato né stampato** |
| `starts` | gli 11 titolari | `pid` = id del listone (`fd<pid>`); `scr`, `cscr`, `b`, `ptype`, `m` a 56, 100, zeri e `-` prima del calcolo: da capire alla prima giornata calcolata |
| `bench` | i 7 panchinari **nell'ordine inserito** | è l'ordine delle sostituzioni (1 P, 2 D, 2 C, 2 A) |
| `mdl`, `nmdl` | modulo (`"343"`) | `controlla_formazione.py` lo ricava dai ruoli, non da qui |
| `lucnt` | quante volte è stata salvata | |
| `cdate`, `ldate` | primo e ultimo salvataggio, `AAAAMMGGhhmmssmmm` | fuso non dichiarato: **probabilmente UTC** (il 29/09 `ldate` diceva 16:09:55 e l'utente ha aperto la sessione per dirlo alle 16:11 UTC), non verificato; lo script ne usa solo il giorno |
| `visb` | visibile | `true` per tutte e due già 11 giorni prima della scadenza |
| `allComp` | valida per tutte le competizioni | |
| `points`, `tot`, `tbon`, `swtc`, `capt`, `rg`, `tkply`, `lply` | punteggi, bonus, cambi, capitano | a zero o `null` prima del calcolo |

**La risposta contiene anche la formazione dell'avversario**, già prima della scadenza.
`controlla_formazione.py` legge solo la mia: quella dell'avversario non cambia quale
formazione mi conviene. Resta da vedere alla prima giornata calcolata (Serie A 6) cosa
diventano `scr`, `b`, `points`, `tot`, `tbon` e `swtc`: probabilmente il voto per giocatore e
il punteggio calcolati dalla lega, che servono alla classifica (vedi CLAUDE.md, fasi future).

## Endpoint noti, non ancora utili

- **Classifica: nessun endpoint** (non c'è nemmeno nel client di riferimento). Si ricava
  dal calendario, con i criteri di parità di `config/league.json` → `competizioni`.
- `/onboarding/v1/league/players`: listone della lega con le sue quotazioni (verificato
  su una lega di test, non usato: il listone arriva da fantacalcio.it).
- `/onboarding/v1/league/update`: nel client di riferimento, è una scrittura. Mai usarlo.
