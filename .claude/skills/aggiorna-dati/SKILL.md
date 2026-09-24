---
name: aggiorna-dati
description: Aggiornamento completo e non interattivo dei dati del progetto (listone, infortuni, calendario e risultati Serie A, statistiche per giocatore, probabili formazioni e status), con commit e push su main. Usare per la routine automatica del mattino, o quando l'utente chiede "aggiorna tutti i dati" / "aggiorna il database".
---

# Aggiornamento dati quotidiano

Pensata per girare da sola, senza nessuno che risponda: **non chiedere conferme**,
applica direttamente. Aggiorna solo i dati: non tocca la rosa (`ownership.json`,
`teams.json`), non dà consigli di formazione, non modifica codice.

## Prima di cominciare

- `pip install -r requirements.txt` (in un container nuovo `beautifulsoup4` può
  mancare).
- `BIGBALLS_API_KEY` deve essere nell'ambiente. Se manca, salta i passi 2 e 3,
  fai tutto il resto, e scrivilo in cima al riepilogo: calendario e statistiche non
  si aggiornano finché la chiave non viene configurata nell'ambiente.
- Stagione in corso = anno di inizio: l'anno corrente se siamo tra luglio e
  dicembre, altrimenti l'anno precedente (2026 per la 2026-27). Sotto è `<stagione>`.

## Passi, in quest'ordine

L'ordine conta. Se un passo fallisce, annotalo e **passa al successivo**: un passo
rotto non deve fermare gli altri. Non inventare mai un dato per coprire un passo
fallito.

1. **Listone e infortuni** (prima dello status, che li usa):
   ```
   python3 scripts/import_fantadraft.py
   ```
2. **Calendario e risultati Serie A** (prima delle statistiche, che leggono le
   partite finite da qui):
   ```
   python3 scripts/import_calendario_seriea.py --season <stagione> --status finished
   python3 scripts/import_calendario_seriea.py --season <stagione> --status scheduled
   python3 scripts/import_calendario_seriea.py --season <stagione> --status postponed
   ```
3. **Statistiche per giocatore** (gol, assist, cartellini, falli, minuti):
   ```
   python3 scripts/import_matchday_stats.py
   ```
   È incrementale: scarica solo le partite finite non ancora in archivio. Non usare
   `--ricostruisci` in un giro automatico: costa una chiamata per ogni partita della
   stagione, su 500 al giorno del piano free.
4. **Probabili formazioni:**
   ```
   python3 scripts/scrape_formazioni.py
   ```
5. **Status dei giocatori** (probabili + infortuni):
   ```
   python3 scripts/apply_formazioni_status.py
   ```
6. **Voti e fantavoto: NON ANCORA DISPONIBILI.** Manca l'importer da
   leghe.fantacalcio.it. Quando esisterà, va aggiunto qui dopo il passo 3. Oggi
   scrivi nel riepilogo che `voto` e `fantavoto` restano vuoti.
7. **Quota API rimasta**, per il riepilogo:
   ```
   curl -sS https://api.bigballsdata.com/v1/usage -H "x-api-key: $BIGBALLS_API_KEY"
   ```

## Commit

Committa **solo** i file in `data/` che sono cambiati, con messaggio
`Aggiornamento dati del <AAAA-MM-GG>`, e pusha su `main`: è la policy
dell'utente, niente branch. Se non è cambiato niente, niente commit. Non aprire
pull request.

## Riepilogo finale

Breve, in italiano, fatti e numeri:

- per ogni passo: ok o fallito, e perché;
- partite finite in archivio e quante sono nuove rispetto a prima;
- righe di statistiche aggiunte;
- infortunati ora e differenza rispetto a prima (chi è entrato, chi è rientrato);
- quanti status sono cambiati, e i numeri dei "non trovati" nel matching nomi;
- partite giocate ancora senza giornata;
- chiamate API rimaste oggi;
- dove sono finiti i dati: hash del commit e branch (deve essere `main`).

Dati che questa routine **non** copre ancora, da non inventare:

- voti e fantavoto (vedi passo 6);
- squalificati e diffidati: nessuno script li legge. Sul sito stanno nella pagina
  "Squalificati e diffidati";
- rose e scambi tra le squadre della lega: dopo l'asta andranno letti da
  leghe.fantacalcio.it, e anche quel passo andrà aggiunto qui.
