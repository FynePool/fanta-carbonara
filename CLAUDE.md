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

`config/league.json` contiene le regole di scoring, i moduli ammessi e `my_team_id`
(la mia squadra — da impostare la prima volta che si popolano i dati).

## Script (`scripts/`)

- `import_listone.py --csv <file>` — importa il listone ufficiale (export Excel/CSV
  di fantacalcio.it) in `data/players.json`, preservando lo status dei giocatori già
  noti. Da lanciare prima dell'asta.
- `asta.py {assegna|stato|disponibili}` — assistente live per l'asta: registra un
  acquisto di qualunque squadra, mostra crediti/slot rimanenti per ruolo, elenca i
  giocatori ancora liberi. Vedi `.claude/skills/asta/SKILL.md`.
- `report_formazione.py --team-id <id> [--matchday N]` — legge lo stato attuale della
  rosa e propone modulo, titolari e panchina, segnalando esplicitamente i giocatori
  senza storico sufficiente o con status incerto (mai inventare un dato mancante).
  Utile solo a rose fatte e stagione in corso.

## Regole per chi lavora su questo repo

- Non inventare mai un voto, uno status o un dato storico mancante: se manca,
  va segnalato come "da verificare a mano", mai stimato silenziosamente.
- Il campione per lo storico contro un singolo avversario è quasi sempre piccolo
  (1-2 incontri a stagione): trattarlo come indizio debole, non come dato solido.
- Le fasi successive del progetto (scraping probabili formazioni pubbliche,
  integrazione API non ufficiale di leghe.fantacalcio.it, storico avversari,
  assistente asta/scambi) sono descritte nella conversazione di progetto e non
  ancora implementate: non aggiungerle senza che siano state esplicitamente richieste.
