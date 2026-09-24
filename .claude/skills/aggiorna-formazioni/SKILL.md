---
name: aggiorna-formazioni
description: Scarica le probabili formazioni Serie A da fantacalcio.it, gli infortuni aggiornati, squalificati e diffidati, e li applica allo status (titolare/ballottaggio/panchina/infortunato/squalificato) dei giocatori in data/players.json, mantenendo uno storico. Usare quando l'utente chiede "aggiorna le formazioni", "che status hanno i miei giocatori", "chi è infortunato", "chi è squalificato", o prima di generare il report formazione se i dati sono vecchi.
---

# Aggiorna probabili formazioni

L'ordine conta: gli infortuni vanno rinfrescati **prima**, perché
`apply_formazioni_status.py` li applica sopra le probabili come ultima parola.

1. Rinfresca listone e infortuni:
   ```
   python3 scripts/import_fantadraft.py
   ```
   Riscrive `data/injuries.json` da zero con i soli infortuni ancora in corso
   secondo la fonte: chi è rientrato sparisce da solo. Lo status dei giocatori
   già noto in `players.json` viene preservato. Se salti questo passo,
   `apply_formazioni_status.py` avvisa che gli infortuni sono vecchi — non
   ignorare quell'avviso, significa che qualcuno rientrato risulta ancora fuori.
2. Esegui:
   ```
   python3 scripts/scrape_formazioni.py
   python3 scripts/scrape_squalifiche.py
   ```
   Il primo scrive `data/formazioni_correnti.json` (snapshot, non versionato) e
   aggiunge una voce a `data/formazioni_history.json` (storico versionato in git).
   Il secondo scrive `data/squalifiche.json`: lo squalificato diventa non
   disponibile come l'infortunato, il diffidato resta schierabile ma segnalato.
   Se uno dei due fallisce (rete, struttura pagina cambiata), avvisa l'utente e
   fermati: non inventare uno status.
3. Esegui prima in modalità di controllo:
   ```
   python3 scripts/apply_formazioni_status.py --dry-run
   ```
   Mostra quanti status cambierebbero, la lista dei "non trovati" in entrambe
   le direzioni (matching per nome, non per id condiviso tra fonti — può
   sbagliare su omonimi o abbreviazioni). Presenta questo riepilogo all'utente.
4. Solo dopo che l'utente ha visto il riepilogo, se conferma, esegui senza
   `--dry-run` per scrivere effettivamente `data/players.json`.
5. Segnala sempre esplicitamente:
   - i giocatori della rosa dell'utente (se già nota) che risultano "non trovati"
     nello scrape — il loro status resta quello precedente, va verificato a mano;
   - lo status "ballottaggio" derivato da percentuali comprese tra 40-89%: è una
     probabilità, non una certezza, e va trattato come tale nel consiglio formazione;
   - i giocatori marcati "infortunato": il motore formazione li esclude
     automaticamente, quindi se uno di loro è in realtà rientrato l'utente perde
     un titolare senza accorgersene. Vale la presenza nel feed infortuni, non una
     data di rientro (quelle sono testo libero e non vengono interpretate).

## Limiti noti (da dire sempre all'utente, non da nascondere)

- Il matching giocatore avviene per nome normalizzato + squadra, non per un id
  condiviso tra fantacalcio.it e il listone FantaDraft: su nomi comuni o
  abbreviazioni ambigue può associare il giocatore sbagliato. In caso di dubbio,
  verificare a mano il giocatore specifico prima di escluderlo/includerlo in formazione.
- Una sola fonte (fantacalcio.it): a differenza di un aggregatore multi-fonte,
  non c'è validazione incrociata. Se in futuro si aggiungono altre fonti, il
  disaccordo tra fonti va segnalato, non risolto arbitrariamente scegliendone una.
