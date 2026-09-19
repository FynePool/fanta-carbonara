---
name: formazione
description: Propone la formazione da schierare per la prossima giornata di fantacalcio, leggendo lo stato della rosa in data/ ed eseguendo scripts/report_formazione.py. Usare quando l'utente chiede "che formazione schiero", "consigliami la formazione", o invoca /formazione.
---

# Consiglio formazione

1. Rifetcha prima i dati: esegui `python3 scripts/import_fantadraft.py` per
   aggiornare listone e infortuni da FantaDraft (fonte pubblica, aggiornata
   quotidianamente). Se fallisce (es. rete non disponibile), avvisa l'utente
   che il report userà dati eventualmente non aggiornati, invece di bloccarti.
   Nota: questo script aggiorna solo quotazione/FVM/infortuni, non lo `status`
   di titolarità (vedi punto 3).
2. Leggi `config/league.json` per recuperare `my_team_id`. Se è `null`, chiedi
   all'utente quale sia la sua squadra (`data/teams.json`) prima di continuare.
3. Controlla `data/players.json`: se `status_updated_at` di uno o più giocatori
   della rosa dell'utente è più vecchio della data delle probabili formazioni
   correnti, avvisa che i dati potrebbero essere obsoleti e chiedi se aggiornarli
   prima di procedere (non aggiornarli da solo senza fonte fornita dall'utente).
4. Esegui:
   ```
   python3 scripts/report_formazione.py --team-id <my_team_id> [--matchday N]
   ```
5. Presenta il risultato in modo leggibile: modulo, titolari per ruolo, panchina,
   e in evidenza la sezione "DA VERIFICARE A MANO" — questi punti vanno sempre
   riportati all'utente, mai omessi o risolti a scelta autonoma.
6. Se lo script segnala "Nessun modulo schierabile", spiega perché (dati mancanti,
   troppi giocatori esclusi) invece di proporre una formazione approssimativa.
