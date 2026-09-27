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

## Endpoint noti, non ancora utili

- **Classifica: nessun endpoint** (non c'è nemmeno nel client di riferimento). Si ricava
  dal calendario, con i criteri di parità di `config/league.json` → `competizioni`.
- `/gaming/v1/teamLineup/<competizione>/<giornata>/<giornata Serie A>/<casa>/<trasferta>`
  (anche con `?extra=1`): formazioni schierate di una partita. Il 27/09, prima della
  giornata, risponde `{"cal": false, "mday", "cmday", "idcomp", "sign", "res", "resr",
  "home": null, "away": null}`. **Probabilmente** dopo il calcolo contiene formazioni e
  voti per giocatore calcolati dalla lega: da verificare alla prima giornata calcolata.
- `/onboarding/v1/league/players`: listone della lega con le sue quotazioni (verificato
  su una lega di test, non usato: il listone arriva da fantacalcio.it).
- `/onboarding/v1/league/update`: nel client di riferimento, è una scrittura. Mai usarlo.
