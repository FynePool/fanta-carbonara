# Fanta Carbonara

Progetto per gestire una squadra di fantacalcio (lega da 12 squadre, modalità **Classic**,
lega su leghe.fantacalcio.it) e ricevere consigli di formazione, mercato e scambi.

## Stato del progetto

Fase 1 (MVP manuale): nessuno scraping automatico. I dati vengono aggiornati a mano
in `data/` dopo ogni giornata e prima di ogni deadline formazioni.

## Struttura dati (`data/`, JSON versionati in git)

- `teams.json` — le 12 squadre della lega: id, nome, proprietario, crediti totali/rimanenti.
- `players.json` — anagrafica giocatori: id, nome, ruolo (P/D/C/A), squadra Serie A,
  `status` (titolare | dubbio | ballottaggio | infortunato | squalificato | panchina),
  `status_updated_at`. **Va aggiornato prima di ogni deadline** leggendo le probabili
  formazioni pubblicate sui siti (fantacalcio.it, SOS Fanta, Gazzetta, ecc.).
- `ownership.json` — chi possiede quale giocatore: player_id, team_id, prezzo d'acquisto,
  data, modalità (asta/scambio/svincolato).
- `matchday_stats.json` — storico per giornata: player_id, matchday, squadra Serie A
  avversaria, casa/trasferta, voto, fantavoto, gol, assist, cartellini, minuti.
- `injuries.json` — storico infortuni: player_id, date, tipo, stato, rientro previsto.
- `market_log.json` — log di mercato/scambi: supporta scambi misti (giocatore + crediti).

`config/league.json` contiene le regole di scoring, i moduli ammessi e `my_team_id`
(la mia squadra — da impostare la prima volta che si popolano i dati).

## Script (`scripts/`)

- `report_formazione.py --team-id <id> [--matchday N]` — legge lo stato attuale della
  rosa e propone modulo, titolari e panchina, segnalando esplicitamente i giocatori
  senza storico sufficiente o con status incerto (mai inventare un dato mancante).

## Regole per chi lavora su questo repo

- Non inventare mai un voto, uno status o un dato storico mancante: se manca,
  va segnalato come "da verificare a mano", mai stimato silenziosamente.
- Il campione per lo storico contro un singolo avversario è quasi sempre piccolo
  (1-2 incontri a stagione): trattarlo come indizio debole, non come dato solido.
- Le fasi successive del progetto (scraping probabili formazioni pubbliche,
  integrazione API non ufficiale di leghe.fantacalcio.it, storico avversari,
  assistente asta/scambi) sono descritte nella conversazione di progetto e non
  ancora implementate: non aggiungerle senza che siano state esplicitamente richieste.
