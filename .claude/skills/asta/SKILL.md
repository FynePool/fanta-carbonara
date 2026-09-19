---
name: asta
description: Assistente live per l'asta a chiamata del fantacalcio. Registra gli acquisti di tutte le 12 squadre, tiene traccia di crediti e slot rimanenti, e suggerisce chi resta disponibile o quanto conviene rilanciare. Usare durante l'asta quando l'utente dice "preso X da squadra Y per Z crediti", "quanto budget mi resta", "chi resta libero per ruolo X".
---

# Assistente asta

Prerequisito: `data/players.json` deve contenere il listone completo (importato con
`scripts/import_listone.py`), non solo placeholder. Se contiene ancora dati TODO,
avvisa l'utente e chiedi il file del listone prima di procedere.

## Durante l'asta

- Quando l'utente riporta un acquisto (di qualunque squadra, non solo la sua),
  registralo con:
  ```
  python3 scripts/asta.py assegna --player-id <id> --team-id <id> --prezzo <n>
  ```
  Se non conosci l'id esatto, cerca il nome in `data/players.json` prima di chiedere
  conferma all'utente — non indovinare l'id.
- "Quanto budget mi resta" / "a che punto è la mia rosa":
  ```
  python3 scripts/asta.py stato --team-id <my_team_id>
  ```
  Confronta i crediti rimanenti con `config/league.json -> auction_budget_split_suggestion`
  e con gli slot ancora da riempire per ruolo: se un ruolo ha pochi slot rimanenti e
  tanto budget assegnato, segnalalo (rischio di sprecare crediti o restare senza slot).
- "Chi resta disponibile per ruolo X":
  ```
  python3 scripts/asta.py disponibili --ruolo <P|D|C|A> --top 15
  ```
- Prima di consigliare un rilancio massimo su un giocatore, controlla sempre
  gli slot e i crediti rimanenti reali (via `stato`) — non stimare a memoria.

## Regole

- Non registrare mai un acquisto senza che l'utente lo abbia confermato esplicitamente
  (nome giocatore, squadra acquirente, prezzo).
- Il consiglio di allocazione budget per ruolo in `league.json` è un'euristica di
  partenza, non un vincolo: se l'utente vuole sforare per un giocatore specifico,
  segui la sua scelta e aggiorna solo il tracking.
