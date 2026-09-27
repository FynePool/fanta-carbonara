---
name: aggiorna-dati
description: Aggiornamento completo e non interattivo dei dati del progetto (listone, infortuni, rose e calendario della lega, calendario e risultati Serie A, statistiche per giocatore, voti e fantavoto, probabili formazioni, squalificati e diffidati, status, notizie sulle squadre della rosa), con commit e push su main. Usare per la routine automatica del mattino, o quando l'utente chiede "aggiorna tutti i dati" / "aggiorna il database".
---

# Aggiornamento dati quotidiano

Pensata per girare da sola, senza nessuno che risponda: **non chiedere conferme**,
applica direttamente. Lo storico in `data/matchday_stats.json` non si accorcia mai: se uno
script si ferma con "righe dello storico sparirebbero", non aggirarlo, riportalo. Aggiorna solo i dati (notizie comprese): non dà consigli di formazione, non modifica codice.

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
   python3 scripts/import_listone_fc.py
   python3 scripts/import_fantadraft.py
   ```
   Il listone viene da fantacalcio.it (stessi id dell'asta e dei voti), gli infortuni da
   FantaDraft. Se il listone si rifiuta di scrivere ("mi aspettavo circa 600", "squadre
   che non sono nel calendario", "uscirebbero dal listone in un colpo solo"), **non**
   rilanciarlo con `--accetta-uscite`: riportalo in cima al riepilogo e vai avanti col
   listone di ieri. Riporta nel riepilogo chi è entrato, uscito o ha cambiato squadra.
1b. **Rose e crediti della lega** (dopo il listone, che serve per i ruoli):
   ```
   python3 scripts/import_rose_lega.py --league-id <league_id di config/league.json>
   ```
   Da leghe.fantacalcio.it: riscrive `teams.json` e `ownership.json` con le squadre
   in gioco, cioè quelle con almeno un giocatore (le vuote restano fuori). Serve `LEGHE_FC_USERNAME` e
   `LEGHE_FC_PASSWORD` nell'ambiente: se mancano, salta il passo e scrivilo in cima al
   riepilogo. Se si rifiuta di scrivere ("ora risultano vuote o sparite"), restano le
   rose di ieri: riportalo, e **non** rilanciarlo con `--accetta-squadre-uscite`
   (lo decide l'utente, dopo aver guardato la lega). Riporta in cima anche le "squadre entrate in gioco". Riporta chi è entrato o uscito da una rosa.
1c. **Competizioni della lega, calendario e risultati** (dopo le rose):
   ```
   python3 scripts/import_calendario_lega.py --league-id <league_id di config/league.json>
   ```
   Stesse credenziali del passo 1b: se mancano, salta. Non perde mai una giornata già
   calcolata. Riporta nel riepilogo le giornate calcolate per competizione, le
   competizioni nuove (Coppa Italia, Europa League) e ogni "ATTENZIONE".
2. **Calendario e risultati Serie A** (prima delle statistiche, che leggono le
   partite finite da qui):
   ```
   python3 scripts/import_calendario_seriea.py --season <stagione> --status finished
   python3 scripts/import_calendario_seriea.py --season <stagione> --status scheduled
   python3 scripts/import_calendario_seriea.py --season <stagione> --status postponed
   ```
3. **Statistiche per giocatore** (gol, assist, cartellini, falli, minuti, tiri,
   passaggi chiave, rigori, subentrato):
   ```
   python3 scripts/import_matchday_stats.py
   ```
   È incrementale: scarica le partite finite non ancora in archivio, più quelle con
   voti di ieri non ancora cercati nel box score (circa 10 chiamate in più il giorno
   dopo un turno). Non usare `--ricostruisci` in un giro automatico: costa una chiamata
   per ogni partita della stagione, su 500 al giorno del piano free. Nel riepilogo
   riporta anche le righe "riconciliate con i voti" e i giocatori "marcati non trovati".
4. **Probabili formazioni, squalificati e diffidati:**
   ```
   python3 scripts/scrape_formazioni.py
   python3 scripts/scrape_squalifiche.py
   ```
   Se `scrape_squalifiche.py` segnala una "struttura della pagina diversa da quella
   attesa", riportalo in cima al riepilogo: la lista piena degli squalificati non era
   mai stata vista quando lo script è stato scritto, quindi è il primo punto da
   controllare la prima volta che ci sono squalificati veri.
5. **Status dei giocatori** (probabili + infortuni + squalifiche):
   ```
   python3 scripts/apply_formazioni_status.py
   ```
6. **Voti e fantavoto** (dopo il passo 3, mai prima: l'importer BigBalls rifà le righe
   delle partite nuove, e questo ci scrive sopra i voti):
   ```
   python3 scripts/import_voti.py
   ```
   Da fantacalcio.it, voto "Redazione Fantacalcio" (`fonte_voti` in
   `config/league.json`), abbinato per id. Non usa la chiave BigBalls: va fatto anche se
   i passi 2 e 3 sono saltati. Riscrive i voti di tutte le giornate finite (il sito
   li può correggere nei giorni dopo). Se stampa "anomalie di struttura della pagina",
   riportalo in cima al riepilogo: quei voti non sono stati scritti.
7. **Notizie sulle squadre della mia rosa** (i numeri non vedono un allenatore
   cambiato, un infortunio in nazionale, un rigorista nuovo). Cosa cercare:
   ```
   python3 scripts/notizie_rosa.py squadre
   ```
   Per ogni squadra elencata, una ricerca web sulle notizie degli ultimi giorni:
   allenatore, infortuni e rientri (anche in nazionale), chi gioca titolare e i
   ballottaggi, rigoristi, squalifiche, mercato. Aggiungi a `data/notizie_rosa.json`
   solo i **fatti** nuovi che toccano i giocatori della rosa o la loro squadra, uno per
   voce, nel formato descritto in `scripts/notizie_rosa.py`:
   - ogni notizia con almeno un link; `verificata: true` solo con due fonti
     indipendenti o la fonte ufficiale del club;
   - niente pareri, voci di mercato senza conferma o previsioni: se un fatto non è
     sicuro, `verificata: false` e scrivilo nel testo;
   - non duplicare una notizia già nel file; se è cambiata, aggiorna quella;
   - mai inventare: se la ricerca non trova niente per una squadra, non si scrive niente.
   Poi aggiorna `aggiornato_il` e controlla il file:
   ```
   python3 scripts/notizie_rosa.py valida
   ```
   Se `valida` segnala errori, correggili; se non ci riesci, ripristina il file di ieri
   (`git checkout -- data/notizie_rosa.json`) e riportalo. Se la ricerca web non è
   disponibile in questo giro, salta il passo e scrivilo in cima al riepilogo.
8. **Quota API rimasta**, per il riepilogo:
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
- listone: giocatori entrati, usciti, con squadra o ruolo cambiati;
- rose della lega: chi è entrato o uscito da una rosa, crediti cambiati;
- competizioni della lega: giornate calcolate, competizioni nuove;
- voti: righe aggiornate, righe nuove, e quanti voti di giocatori assenti dal listone;
- infortunati ora e differenza rispetto a prima (chi è entrato, chi è rientrato);
- squalificati e diffidati, per nome e squadra;
- notizie nuove sulla rosa, una riga ciascuna con il link (e quelle non verificate);
- quanti status sono cambiati, e i numeri dei "non trovati" nel matching nomi;
- partite giocate ancora senza giornata;
- chiamate API rimaste oggi;
- dove sono finiti i dati: hash del commit e branch (deve essere `main`).

Dati che questa routine **non** copre ancora, da non inventare:

- il fantavoto calcolato con le regole della lega (c'è quello standard di fantacalcio.it);
- la classifica della lega (non c'è un endpoint: si ricaverà dal calendario).
