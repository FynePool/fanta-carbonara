---
name: aggiorna-formazioni
description: Scarica le probabili formazioni Serie A da fantacalcio.it e aggiorna lo status (titolare/ballottaggio/panchina) dei giocatori in data/players.json, mantenendo uno storico. Usare quando l'utente chiede "aggiorna le formazioni", "che status hanno i miei giocatori", o prima di generare il report formazione se i dati sono vecchi.
---

# Aggiorna probabili formazioni

1. Esegui:
   ```
   python3 scripts/scrape_formazioni.py
   ```
   Scrive `data/formazioni_correnti.json` (snapshot, non versionato) e aggiunge
   una voce a `data/formazioni_history.json` (storico versionato in git).
   Se fallisce (rete, struttura pagina cambiata), avvisa l'utente e fermati:
   non inventare uno status.
2. Esegui prima in modalità di controllo:
   ```
   python3 scripts/apply_formazioni_status.py --dry-run
   ```
   Mostra quanti status cambierebbero, la lista dei "non trovati" in entrambe
   le direzioni (matching per nome, non per id condiviso tra fonti — può
   sbagliare su omonimi o abbreviazioni). Presenta questo riepilogo all'utente.
3. Solo dopo che l'utente ha visto il riepilogo, se conferma, esegui senza
   `--dry-run` per scrivere effettivamente `data/players.json`.
4. Segnala sempre esplicitamente:
   - i giocatori della rosa dell'utente (se già nota) che risultano "non trovati"
     nello scrape — il loro status resta quello precedente, va verificato a mano;
   - lo status "ballottaggio" derivato da percentuali comprese tra 40-89%: è una
     probabilità, non una certezza, e va trattato come tale nel consiglio formazione.

## Limiti noti (da dire sempre all'utente, non da nascondere)

- Il matching giocatore avviene per nome normalizzato + squadra, non per un id
  condiviso tra fantacalcio.it e il listone FantaDraft: su nomi comuni o
  abbreviazioni ambigue può associare il giocatore sbagliato. In caso di dubbio,
  verificare a mano il giocatore specifico prima di escluderlo/includerlo in formazione.
- Una sola fonte (fantacalcio.it): a differenza di un aggregatore multi-fonte,
  non c'è validazione incrociata. Se in futuro si aggiungono altre fonti, il
  disaccordo tra fonti va segnalato, non risolto arbitrariamente scegliendone una.
