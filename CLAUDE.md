# Fanta Carbonara

Progetto per gestire una squadra di fantacalcio (lega da 12 squadre, modalità **Classic**,
lega su leghe.fantacalcio.it) e ricevere consigli di formazione, mercato e scambi.

## Stato del progetto

Priorità attuale: **asta di inizio stagione imminente** (formato a chiamata classica,
12 squadre, 500 crediti, rose 3P-8D-8C-6A). Finché l'asta non è conclusa, il modulo
asta (`scripts/asta.py`) è più importante del modulo formazione: senza rose complete
non c'è nulla su cui basare un consiglio di formazione.

Nessuno scraping automatico in questa fase: il listone va importato da un export
ufficiale (vedi `scripts/import_listone.py`), gli acquisti live vanno registrati
a mano man mano che avvengono, e lo status giocatore va aggiornato a mano prima
di ogni deadline formazioni.

## Struttura dati (`data/`, JSON versionati in git)

- `teams.json` — le 12 squadre della lega: id, nome, proprietario, crediti totali/rimanenti.
- `players.json` — **pool completo di tutti i giocatori Serie A** (non solo quelli
  posseduti), importato dal listone ufficiale: id, nome, ruolo (P/D/C/A), squadra
  Serie A, `quotazione`. Il campo `status` (titolare | dubbio | ballottaggio |
  infortunato | squalificato | panchina | n/d) e `status_updated_at` diventano
  rilevanti solo a stagione iniziata e **vanno aggiornati prima di ogni deadline**
  leggendo le probabili formazioni pubblicate sui siti (fantacalcio.it, SOS Fanta,
  Gazzetta, ecc.).
- `ownership.json` — chi possiede quale giocatore: player_id, team_id, prezzo d'acquisto,
  data, modalità (asta/scambio/svincolato).
- `matchday_stats.json` — storico per giornata: player_id, matchday, squadra Serie A
  avversaria, casa/trasferta, voto, fantavoto, gol, assist, cartellini, minuti.
- `injuries.json` — storico infortuni: player_id, date, tipo, stato, rientro previsto.
- `market_log.json` — log di mercato/scambi: supporta scambi misti (giocatore + crediti).
- `calendario_serie_a.json` — calendario e risultati Serie A per giornata (squadra
  casa/trasferta, gol, stato), da BigBalls Sports Data API (vedi script sotto).
  Non contiene dati per giocatore (niente voto/gol/cartellini singoli): solo
  l'esito partita, usato per sapere chi ha giocato contro chi in una giornata.

`config/league.json` contiene le regole di scoring, i moduli ammessi e `my_team_id`
(la mia squadra — da impostare la prima volta che si popolano i dati).

## Script (`scripts/`)

- `import_listone.py --csv <file>` — importa il listone ufficiale (export Excel/CSV
  di fantacalcio.it) in `data/players.json`, preservando lo status dei giocatori già
  noti. Da lanciare prima dell'asta.
- `import_fantadraft.py` — importa listone + infortuni da FantaDraft (github.com/
  lucianomurr/FantaDraft, fonte pubblica aggregata, aggiornata quotidianamente).
- `scrape_formazioni.py` — scrape delle probabili formazioni Serie A da
  fantacalcio.it (HTML statico, verificato scrapeable senza rendering JS).
  Scrive uno snapshot (`data/formazioni_correnti.json`, non versionato) e ne
  accumula lo storico in `data/formazioni_history.json` (versionato).
- `apply_formazioni_status.py [--dry-run]` — applica lo snapshot più recente allo
  `status` dei giocatori in `players.json`, con matching per nome+squadra
  (euristico, non un id condiviso tra fonti: verificare i "non trovati" in output).
  Vedi `.claude/skills/aggiorna-formazioni/SKILL.md`.
- `lib/leghe_fc_client.py` — client per l'API privata non ufficiale di
  leghe.fantacalcio.it (`apileague.fantacalcio.it`), portato in Python dal
  codice sorgente reale di @legasanpetrux/leghe-fc-client (MIT, github.com/
  legasanpetrux/leghe-fc-client). Non è un'API pubblica/documentata da
  Fantacalcio.it, solo in lettura, uso a proprio rischio.
  **Verificato end-to-end in questa sessione** con un account e una lega
  di test reali: login con username/password, e lettura di rose+crediti
  (`/league/teams/all`) e listone della lega (`/league/players`). Punto
  critico: il payload di login contiene due jwt diversi (uno d'account,
  uno specifico per lega); solo quello di lega funziona per le chiamate
  autenticate — usare sempre `get_league_jwt()`, mai `data['jwt']` diretto.
  Credenziali sempre da variabili d'ambiente `LEGHE_FC_USERNAME`/
  `LEGHE_FC_PASSWORD`, mai in chat o committate.
- `leghe_fc_inspect.py {leghe|rose|listone} [--league-id ID]` — CLI di sola
  lettura per esplorare una lega reale via l'API sopra. Non scrive mai in
  `data/`: il mapping verso `teams.json`/`ownership.json` per la lega vera
  dell'asta va deciso e scritto solo dopo l'asta, non prima.
- `import_calendario_seriea.py --season <anno> [--status ...]` — importa calendario
  e risultati Serie A da BigBalls Sports Data API (bigballsdata.com) in
  `data/calendario_serie_a.json`. Fonte verificata in questa sessione: copre Serie A
  dal 2014-15 a oggi, con giornata ("round") e risultato, ma **non** statistiche per
  giocatore né il voto fantacalcio (quello resta da verificare via l'API di
  leghe.fantacalcio.it, endpoint `/gaming/v1/teamLineup`, non ancora testato — serve
  una lega reale con competizione collegata). Richiede `BIGBALLS_API_KEY` da
  ambiente. Le partite finite da pochissimo possono avere giornata nulla per
  ritardo della fonte: mai stimata, va verificata a mano al prossimo refresh.
  Merge idempotente sullo storico esistente (aggiorna per `match_id`, non duplica).
- `asta.py {assegna|scambio|svincolo|stato|disponibili}` — assistente live per l'asta
  e per il mercato post-asta: registra un acquisto di qualunque squadra, uno scambio
  misto (giocatori + crediti in entrambe le direzioni) tra due squadre, o lo svincolo
  di un giocatore (torna disponibile per tutti); mostra crediti/slot rimanenti per
  ruolo ed elenca i giocatori ancora liberi. Vedi `.claude/skills/asta/SKILL.md`.
- `report_formazione.py --team-id <id> [--matchday N]` — legge lo stato attuale della
  rosa e propone modulo, titolari e panchina, segnalando esplicitamente i giocatori
  senza storico sufficiente o con status incerto (mai inventare un dato mancante).
  Utile solo a rose fatte e stagione in corso.

## Regole per chi lavora su questo repo

- Non inventare mai un voto, uno status o un dato storico mancante: se manca,
  va segnalato come "da verificare a mano", mai stimato silenziosamente.
- Il campione per lo storico contro un singolo avversario è quasi sempre piccolo
  (1-2 incontri a stagione): trattarlo come indizio debole, non come dato solido.
- Le fasi successive del progetto (storico avversari, assistente asta/scambi
  completo, mapping automatico API lega -> ownership.json) sono descritte
  nella conversazione di progetto e non ancora implementate: non aggiungerle
  senza che siano state esplicitamente richieste.
- Mai committare credenziali, jwt, token o dati personali reali (email,
  username) in nessun file del repo. Le uniche variabili sensibili sono
  `LEGHE_FC_USERNAME`/`LEGHE_FC_PASSWORD`, sempre da ambiente.
