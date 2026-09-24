---
name: formazione
description: Propone la formazione da schierare per la prossima giornata di fantacalcio, leggendo lo stato della rosa in data/ ed eseguendo scripts/report_formazione.py. Usare quando l'utente chiede "che formazione schiero", "consigliami la formazione", o invoca /formazione.
---

# Consiglio formazione

1. Controlla che i dati siano di oggi. La routine del mattino li aggiorna con la
   skill `aggiorna-dati`: guarda `git log -1 -- data/` e `status_updated_at` in
   `data/players.json`. Se non sono di oggi, esegui la skill `aggiorna-dati`
   (listone, infortuni, calendario, statistiche, probabili e status, nell'ordine
   giusto). Se un passo fallisce, avvisa che il report userà dati vecchi per quella
   parte, invece di bloccarti.
2. Leggi `config/league.json` per recuperare `my_team_id`. Se è `null`, chiedi
   all'utente quale sia la sua squadra (`data/teams.json`) prima di continuare.
3. Se l'utente vuole ricontrollare lo status prima di una deadline (le probabili
   cambiano fino a poche ore prima), usa la skill `aggiorna-formazioni`.
4. Esegui:
   ```
   python3 scripts/report_formazione.py --team-id <my_team_id> [--matchday N]
   ```
5. Presenta il risultato in modo leggibile: modulo, titolari per ruolo, panchina
   **nell'ordine in cui va inserita sul sito** (con i cambi illimitati è l'ordine
   delle sostituzioni), non disponibili, e in evidenza la sezione "DA VERIFICARE A
   MANO": quei punti vanno sempre riportati all'utente, mai omessi o risolti a
   scelta autonoma. Per i titolari segnati "se non gioca entra X", dillo esplicitamente.
6. Se il report non propone una formazione, riporta il motivo che stampa (nessun
   voto, rosa vuota, ruolo scoperto) invece di proporne una approssimativa.
