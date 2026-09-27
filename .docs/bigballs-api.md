# BigBalls Sports Data API — riferimento per Fanta Carbonara

Note operative sull'API usata da `scripts/import_calendario_seriea.py` e
`scripts/import_matchday_stats.py`.

Fonte primaria: lo **spec OpenAPI ufficiale** (`https://api.bigballsdata.com/openapi.json`,
544 KB, 133 path, v1.0.0), non le pagine marketing — quelle si sono già rivelate
imprecise (dicevano che il piano free include le statistiche per giocatore in modo
diverso da com'è). Tutto ciò che qui è marcato **verificato** è stato provato con
chiamate reali in sessione il 19/09/2026.

## Accesso

- Base URL: `https://api.bigballsdata.com` (fallback Railway documentato nello spec).
- Auth: header `x-api-key: <chiave>` **oppure** `Authorization: Bearer <chiave>`.
  Formato chiave: `bbs_<env>_<32hex>`.
- La chiave sta in `BIGBALLS_API_KEY` da ambiente. Mai in chat, mai committata.
- Account/quota: `GET /v1/usage` e `GET /v1/user/me` (quest'ultimo restituisce
  anche l'email dell'account: non copiarne l'output nel repo).

### Piano attuale e limiti (verificato via `/v1/usage`)

| Voce | Valore |
|---|---|
| Piano | `free` |
| Rate limit | 100 richieste/minuto, **500/giorno** |
| Reset finestra giornaliera | mezzanotte UTC |

Header di rate limit esposti: `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
`X-RateLimit-Reset`, `X-RateLimit-Limit-Minute`, `X-RateLimit-Limit-Day`,
`Retry-After`, più `X-Request-Id` per il supporto.

**Vincolo pratico da tenere a mente**: il box score è una chiamata *per partita*.
Un import completo delle 380 partite di una stagione costerebbe 380 chiamate,
oltre i 2/3 del tetto giornaliero. Gli import fatti finora (calendario completo +
box score delle 44 partite giocate) hanno consumato ~190 chiamate in un giorno.

## Struttura delle risposte

Wrapper standard: `{ "data": ..., "meta": {...}, "error": null }`.

- Solo `data` è garantito. `error` può essere **assente** (non null) su una 200.
- `meta` non garantisce nessun campo: `cached`, `request_id`, `source`,
  `cache_age_ms`, `confidence` compaiono a intermittenza (lo spec stesso documenta
  su quante risposte campionate ciascuno è apparso). Va trattato tutto come opzionale.
- Errore: `{ "code": "NOT_FOUND", "message": "...", "details": ... }`.
- Paginazione liste: `?limit=` + `?offset=` (`?page=N` è alias di offset; sugli
  endpoint a pagina singola `?page=` dà 400 invece di essere ignorato).

### Convenzioni che ci riguardano

- **`season` è l'anno di INIZIO stagione**: `season=2026` = stagione 2026-27.
- `sport=football` significa calcio (il football americano è `american_football`).
- `league`: codice, non id. Per noi `serie_a` (alias `seriea` accettato).
  La lista autorevole è in `GET /v1/leagues` (campo `id`).
- Gli id (`StoredId`) sono UUID BigBalls, **non** condivisi con altre fonti:
  per incrociare con `data/players.json` serve matching per nome+squadra.
- `MatchStatus`: `scheduled | in_progress | finished | postponed | cancelled | suspended`
  (la lista `/v1/matches` accetta anche `live`).

## Endpoint che usiamo

### `GET /v1/matches` — calendario e risultati (usato da `import_calendario_seriea.py`)

Parametri: `sport`, `league`, `date` (ISO o `today`), `tz`, `status`, `limit`, `offset`,
`season`.

Campi utili per partita: `id`, `league` (nome display), `home`/`away` (`{id, name,
short_name, logo_url}`), `kickoff_utc`, `status`, `score {home, away}`, `linescore`,
`round`, `attendance`, `broadcast`, `has_odds`.

- **`round`** è la giornata, come testo libero (`"Regular Season - 5"`), popolato
  **solo per il calcio**. Da qui ricaviamo `giornata`.
- **Verificato**: `round` arriva con ~1 giorno di ritardo rispetto al fischio finale.
  Le partite giocate oggi hanno `round: null` anche interrogando l'API in diretta,
  mentre quelle di ieri ce l'hanno. Non è un bug nostro: basta rilanciare l'import
  il giorno dopo (il merge è idempotente per `match_id`). Verificato il 24/09: le
  partite del 19/09 ora hanno `"Regular Season - 5"`.
- **Verificato**: sulle partite **future** `round` è sempre `null` (335 su 335 il
  24/09). Viene assegnato solo dopo che la partita si gioca, quindi questo campo non
  dice qual è la prossima giornata: per quello va ricavata dalle date (`kickoff_utc`).
- `season` e `venue` **non** vengono emessi dagli endpoint lista (documentato).
- Su `/v1/matches/{id}` il parametro `fields` è accettato ma **non cambia la
  risposta** (lo spec lo dichiara esplicitamente: non costruirci sopra nulla).

### `GET /v1/stored/matches/{id}/stats` — box score per giocatore (usato da `import_matchday_stats.py`)

Ritorna `data.team_stats` (spesso vuoto) e `data.players[]`, ogni giocatore con
`id`, `name`, `position`, `jersey_number`, `team_id`, `team_name` e `stats` come
dizionario `{chiave: {value, label}}` — i valori sono **stringhe**, vanno convertiti.

Chiavi osservate: `goals`, `assists`, `yellow_cards`, `red_cards`, `fouls_committed`,
`fouls_drawn`, `minutes`, `goals_conceded`, `saves`, `penalty_scored`,
`penalty_missed`, `penalty_saved`, `shots_total`, `shots_on`, `passes_total`,
`passes_key`, `pass_accuracy`, `dribbles_attempts`, `dribbles_success`,
`duels_total`, `duels_won`, `tackles_total`, `tackles_blocks`, `interceptions`,
`offsides`, `captain`, `substitute`, `rating`.

**Avvertenze importanti, verificate:**

1. **`rating` NON è il voto fantacalcio.** È un rating generico stile Opta/Sofascore.
   Il voto che conta per lo scoring è solo quello di fantacalcio.it /
   leghe.fantacalcio.it. In `matchday_stats.json` i campi `voto`/`fantavoto` restano
   `null` e non vanno mai riempiti da qui.
2. **Il `team_name` del box score non è affidabile**: nella lista giocatori di una
   partita di Serie A compaiono giocatori con `team_name` di club o nazionali estranee
   (Liverpool, Chelsea, Marsiglia, RB Lipsia, Argentina, Croazia, Svizzera,
   Giappone…), alcuni con `team_name: null` o caratteri corrotti nel nome.
   **Verificato il 27/09: in gran parte non sono estranei**, sono giocatori veri della
   partita, con i minuti giusti, etichettati con la squadra della stagione scorsa o la
   nazionale (Kean "Fiorentina" nel Como, Curtis Jones "Liverpool" nell'Inter, N.
   González "Argentina" nella Juventus). Il matching per squadra li perdeva: 179 voti
   senza statistiche. Difesa adottata: una riga nuova si scrive **solo** se
   nome+squadra combaciano con un giocatore della partita in `data/players.json`; le
   righe che fantacalcio.it ha già per quella partita vengono arricchite con un
   abbinamento per nome sui soli giocatori non abbinati (riconciliazione in
   `import_matchday_stats.py`). Controllo: gol, assist e cartellini tornano con
   fantavoto − voto in 130 righe riconciliate su 131.
3. **Nomi sporchi**: entità HTML (`N&apos;Diaye`), UTF-8 letto come Latin-1
   (`OulaÃ¯`, `ObriÄ\x87`), cognomi staccati (`Del Prato` per `Delprato`), doppi cognomi
   spagnoli (`Jacobo Ramón Naveros`). La riconciliazione li ripara prima di confrontare.
4. **Chiavi omesse a zero**: `shots_total`, `shots_on`, `passes_key` ecc. mancano quando
   valgono 0 (anche per chi ha giocato 90'); si scrivono 0. `substitute` c'è sempre:
   `true` = partiva dalla panchina (con `minutes` > 0 è entrato). Contando i titolari
   (`substitute: false` con minuti) tra le righe abbinate, 68 squadre-partita su 100 ne
   hanno 11, 20 ne hanno di più (fino a 16: subentrati segnati come titolari) e 12 di
   meno (giocatori non abbinati). Rumore della fonte, non corretto.
5. ~~**Rigori quasi assenti**~~ — **smentito il 27/09 sera, non era una magagna.**
   `penalty_scored`/`penalty_missed` danno 5 rigori calciati in 50 partite, e sembravano
   troppo pochi. Verificato contro fantacalcio.it (pagina "Statistiche Serie A" della
   stagione in corso, la fonte dei voti della lega): **anche lì sono 5**, e sono gli stessi
   cinque giocatori (Maldini, Colombo, Zaccagni, Varela G., Yeboah J.). Nelle prime 5
   giornate del 2026-27 ci sono stati davvero solo 5 rigori. Quindi su questo campo
   BigBalls è completo, e i rigori realizzati **si possono** togliere dal fantavoto se
   serve. Resta vero che il **rigorista designato** non si ricava da qui: chi non ha ancora
   avuto un rigore da tirare non lascia traccia (vedi `scripts/rigoristi.py`).

### `GET /v1/matches/{id}/events` — timeline eventi

Parametri: `id`, `sport` (obbligatorio), `type` (`?type=all` per **cartellini e
sostituzioni**, altrimenti solo i gol).

Campi: `elapsed`, `elapsed_extra`, `team`, `player_name`, `player_id`, `assist_name`,
`assist_player_id`, `event_type` (`Goal` | `Card` | `subst`), `event_detail`
(`Normal Goal`, `Yellow Card`, …), `coordinate_x/y`, `xg`, `xgot`.

- Coordinate e xG sono popolati **solo per il Mondiale 2026**, `null` altrove
  (documentato nello spec, non implicito).
- **Verificato: questo feed duplica gli eventi.** Su Roma-Inter del 19/09 mostrava
  3 gol di Koné (6', 37', 39') su una partita finita 2-2, e il giallo di Barella due
  volte (11' e 12'). L'utente ha spiegato il caso del gol: annullato per fuorigioco
  e poi convalidato dopo revisione VAR, quindi ri-registrato. Il box score
  (`/stored/matches/{id}/stats`) invece conta correttamente 2 gol e 1 giallo.
  **Per i conteggi usare sempre il box score, mai `/events`.**

## Endpoint potenzialmente utili, non ancora usati

| Endpoint | Cosa dà | Note |
|---|---|---|
| `GET /v1/coverage` | Cosa copre davvero il servizio, per sport e lega, con conteggi reali | Serie A: 13 stagioni dal 2014-15. `?v=2` per i "grain" (per-giocatore vs per-squadra) |
| `GET /v1/matches/{id}/statistics` | Statistiche **di squadra** post-partita (possesso, tiri, falli, corner, cartellini, parate) | Solo calcio. `meta.available=false` finché l'upstream non pubblica (~30 min dal 90') |
| `GET /v1/stored/matches/{id}/lineups` | Formazioni titolari/panchina con `starter` | Lo spec dice "non ancora ingerite, ritorna vuoto", ma **in sessione ha restituito formazioni reali**: spec più vecchia del servizio, verificare caso per caso |
| `GET /v1/stored/matches/{id}/h2h` | Ultime N sfide tra le stesse due squadre | Utile per lo storico-per-avversario |
| `GET /v1/standings` | Classifica di Serie A | **Verificato, 200 su free**: `data[0].rows[]` con `team_id`, `team_name`, `rank`, ecc., `season: "2026-27"` |
| `GET /v1/leagues/{id}/top-scorers` | Capocannonieri con gol, assist, minuti, presenze | **Verificato, 200 su free** con `id=serie-a` (o id numerico `135`). Ha l'id giocatore BigBalls, joinabile. **Attenzione**: non concorda con i box score della stessa API — per Malen dava 5 gol in 3 presenze, i box score per partita ne danno 6 in 5 presenze (i nostri dati sono coerenti, 5 righe senza duplicati). Aggregato e per-partita sono due pipeline diverse: non mescolarli |
| `GET /v1/teams/{id}/form` | Ultime partite con risultato W/D/L dal punto di vista della squadra | **Verificato, 200 su free** (vedi sotto: lo spec lo dava come Solo+) |
| `GET /v1/injuries` | Infortuni attivi per sport | Il significato dei campi varia per lega, documentato nello spec |
| `GET /v1/teams/{id}/elo` | Elo squadra + rank in campionato | Possibile proxy di "difficoltà avversario" per il consiglio formazione |
| `GET /v1/players/{id}/game-log` | Log partita per partita di un giocatore, filtrabile per avversario/casa-trasferta | Alternativa al nostro import per-partita, da valutare |

### Limiti di piano: lo spec non è affidabile, testare

Lo spec dichiara Solo+ per `/v1/teams/{id}/form`, `/v1/teams/{id}/h2h-intelligence`,
`/v1/players/{id}/rolling-stats`, gli headshot giocatore e `expected_goals` dentro
`/v1/matches/{id}/statistics`; Pro+ per il play-by-play di NBA/NHL/NFL; Edge+ per i
webhook.

**Ma `/v1/teams/{id}/form` risponde 200 con dati veri sul nostro piano free**
(verificato). Quindi le note di gating nello spec vanno trattate come indicative:
prima di escludere un endpoint perché "a pagamento", provarlo.

`/v1/predictions` invece è un limite reale di copertura, non di piano: contiene
solo Mondiale 2026, NBA e NHL — nessuna previsione per la Serie A.

## Connettore MCP vs API REST

Il connettore MCP `BigBallsFootbal` espone **solo 6 tool**: `find_players`,
`get_coverage`, `get_matches`, `get_player_stats`, `get_standings`, `get_team_elo`.
Non copre gli endpoint per-partita (`/events`, `/stored/matches/{id}/stats`,
`/lineups`) e `get_matches` non ha `offset`, quindi si ferma a 200 risultati.
Per tutto il resto serve chiamare l'API REST direttamente con la chiave.
`get_player_stats` sul calcio ha restituito `stats: null` anche per un titolare di
Serie A: per i dati per-giocatore usare il box score REST, non quel tool.
