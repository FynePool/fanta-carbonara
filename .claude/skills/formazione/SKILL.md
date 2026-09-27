---
name: formazione
description: Propone la formazione da schierare per la prossima giornata di fantacalcio, leggendo lo stato della rosa in data/ ed eseguendo scripts/report_formazione.py, controllando le notizie vere sulle squadre dei giocatori e spiegando ogni scelta in parole semplici. Usare quando l'utente chiede "che formazione schiero", "consigliami la formazione", o invoca /formazione.
---

# Consiglio formazione

**L'utente sa poco o niente di calcio.** Il progetto decide al posto suo, quindi ogni
scelta va motivata in parole semplici, e quando la scelta è sua deve avere tutte le
informazioni per capire cosa sceglie. Niente gergo senza spiegarlo ("regista",
"ballottaggio", "fantamedia": una frase su cosa vuol dire).

## Dati

1. Controlla che i dati siano di oggi. La routine del mattino li aggiorna con la
   skill `aggiorna-dati`: guarda `git log -1 -- data/` e `status_updated_at` in
   `data/players.json`. Se non sono di oggi, esegui la skill `aggiorna-dati`
   (listone, infortuni, calendario, statistiche, probabili e status, nell'ordine
   giusto). Se un passo fallisce, avvisa che il report userà dati vecchi per quella
   parte, invece di bloccarti.
2. Leggi `config/league.json` per recuperare `my_team_id`. Se è `null`, chiedi
   all'utente quale sia la sua squadra (`data/teams.json`) prima di continuare.
3. Vicino alla scadenza (le probabili cambiano fino a poche ore prima) usa la skill
   `aggiorna-formazioni` per rinfrescare probabili, infortuni e squalifiche.
4. Esegui:
   ```
   python3 scripts/report_formazione.py --team-id <my_team_id> [--matchday N]
   ```
   Il report mostra anche le stagioni passate di ogni giocatore
   (`data/storico_stagioni.json`): sono contesto, non entrano nel valore.

## Notizie: cosa succede davvero

I dati della routine sono numeri. Quello che i numeri non vedono (un allenatore
cambiato, un infortunio in nazionale, un giocatore finito fuori squadra, un rigorista
nuovo) va cercato ogni volta, prima di consigliare.

5. Leggi `data/notizie_rosa.json` (le notizie raccolte dal giro del mattino, con le
   fonti). Poi, per le squadre dei titolari e dei primi due cambi di ogni ruolo, cerca
   con la ricerca web le notizie degli ultimi giorni: allenatore, infortuni e rientri,
   chi parte titolare, rigoristi, squalifiche, clima della squadra (serie di risultati).
   Il calendario in `data/calendario_serie_a.json` dà la serie di risultati senza
   bisogno di cercarla.
6. Regole per le notizie e per i pareri (anche quelli di amici che l'utente incolla):
   - **Verifica i fatti.** Un fatto entra nel ragionamento solo con una fonte (link) o
     se si vede nei dati del repo. Un parere senza fatti ("secondo me X è forte") si
     riporta come parere, non come fatto.
   - **Le notizie decidono i pari, non ribaltano i distacchi.** Se il report mette due
     giocatori entro la soglia dei pari ("DECISIONI TUE"), le notizie verificate e le
     stagioni passate sono il modo giusto per scegliere. Se il distacco è sopra la
     soglia, una notizia lo ribalta solo se cambia i fatti di base (non gioca, ruolo
     cambiato, infortunio): altrimenti la si riporta come rischio e si lascia la
     scelta del modello, spiegando perché.
   - Un'informazione che il modello usa già (per esempio la forza della difesa
     avversaria, colonna `avv`) non si conta due volte: dillo.
   - Mai inventare una notizia, un infortunio o un titolare. Se la ricerca web non è
     disponibile, dillo in cima alla risposta: il consiglio vale solo sui dati.

## Come presentare

7. In cima, la cosa che l'utente deve sapere prima di tutto (un rischio, un dato
   vecchio, un titolare in dubbio).
8. Modulo, titolari per ruolo, panchina **nell'ordine in cui va inserita sul sito** (con
   i cambi illimitati è l'ordine delle sostituzioni), non disponibili. Per i titolari
   segnati "se non gioca entra X", dillo esplicitamente.
9. Per ogni scelta non ovvia (ogni riga di "DECISIONI TUE", ogni punto dove le notizie
   o l'utente spingono in un'altra direzione), questa struttura:
   - **cosa si decide**, in una frase ("chi gioca tra X e Y; l'altro entra se un
     centrocampista resta senza voto");
   - **cosa dicono i numeri** (valore del modello e distacco, stagioni passate), in
     parole semplici;
   - **cosa dicono le notizie**, con i link;
   - **il consiglio e il perché**;
   - **cosa rischi se è sbagliato** (quanti punti circa, quanto è probabile).
   Etichetta ogni affermazione [Certain] / [Likely] / [Guessing].
10. La sezione "DA VERIFICARE A MANO" va sempre riportata, mai omessa o risolta a
    scelta autonoma.
11. Se il report non propone una formazione, riporta il motivo che stampa (nessun
    voto, rosa vuota, ruolo scoperto) invece di proporne una approssimativa.
