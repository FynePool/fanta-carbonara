# Progetti simili: verifica dell'analisi esterna e cosa usare davvero

Analisi del 02/10/2026 del PDF "Fantacalcio + Claude: progetti simili a fanta-carbonara"
(ricerca dello stesso giorno). Il PDF si basava sul README, che non è aggiornato. Qui ogni
sua affermazione è confrontata col codice di `main` (commit `eeb1c07`, 02/10) e con il
codice delle fonti che cita. **Non è stato implementato niente**: l'unico calcolo nuovo è
una misura descrittiva fatta fuori dal repo (appendice A).

**Rivista lo stesso giorno dopo una verifica avversariale di Codex** (sezione 8): ogni suo
rilievo è stato ricontrollato su codice e dati prima di correggere. La revisione ha trovato
il problema più grave di tutto il documento (punto 0.1), che nella prima versione era
liquidato come un refuso.

Etichette: **[Certain]** verificato su codice o dati letti; **[Likely]** inferenza forte;
**[Guessing]** ipotesi da verificare.

Fonti lette (clone in sola lettura, commit indicato):

| Repo | Commit | Data |
|---|---|---|
| gianmarcocalbi/fantaclaude | `2a5dba2` | 22/09 |
| valeriopisco72-ship-it/fanta-asta (PR #1 inclusa: è già fusa) | `b44d755` | 28/09 |
| ManzoChinaglia/JARVIS | `6cbd23d` | 02/10 |
| amargiovanni/fantamagazine | `3f4bf95` | 22/09 |
| armandoferrara86-crypto/fanta | `5d0c6b4` | 18/09 |
| SilvioBaratto/fantabot | `799210e` | 24/09 |
| simonediroma/fantanostalgia, PR #114 | `3a60fee` | 01/10 |
| Tiri6/fantacalcio-nuovo | `51f2e5b` | 25/09 |
| andreaorlandi29-sudo/Fantacalcio-Assistant | `de5e8ca` | 01/10 |
| piopy/fantacalcio-py | `4dda14a` | 13/09 |

I progetti minori (emanuelesordo, coneale90, agremi/fanta-mcp, gli MCP di FPL e Yahoo) e i
prodotti commerciali (FantaGPT, FantaGOAT) **non** sono stati verificati.

---

## 0. Le cose scomode, prima di tutto

1. **Due notizie marcate `verificata: true` sono false, e lo dicono i nostri stessi dati.**
   [Certain] In `data/notizie_rosa.json` (commit `eeb1c07`):
   - la notizia sul Venezia datata 15/09 (aggiunta il 01/10) dice che Adams "ha già calciato
     un rigore al posto [di Busio] alla giornata 5". Falso: alla giornata 5 il rigore l'ha
     calciato e sbagliato Yeboah J., con Adams in campo fino al 73'
     (`matchday_stats.json`: Yeboah `rigori_sbagliati: 1`, Adams `0`). `rigoristi.json` lo sa
     già: Adams "scavalcato da Yeboah J., giornata 5, in campo";
   - la notizia del 01/10 dice Busio "infortunato da almeno due mesi". Falso: si è fatto male
     l'11/09, tre settimane prima. Lo dice la notizia precedente e `injuries.json`.

   Adams è nella mia rosa, e il pari Elphege-Adams è proprio una scelta in cui il rigore fa
   da spareggio (`.docs/analisi-valutazione-formazione.md`): la skill `formazione` legge
   queste notizie. Il report non ne è toccato, perché usa `rigoristi.json`. È il punto debole
   più serio trovato, e il PDF non lo vede: lo strato delle notizie scrive fatti "verificati"
   senza controllarli contro i dati che abbiamo. Va corretto **prima della scadenza del
   10/10** (4.A).
2. **Il "probabile difetto" principale del PDF è in parte già superato, e la correzione che
   propone non è sostenuta. Ma nemmeno il contrario.** [Certain] I portieri hanno già un
   coefficiente `avv` separato, e la variante "portieri sui gol fatti dall'avversario" è già
   stata provata il 27/09 (indistinguibile, da rifare alla giornata 10). Il README non lo
   dice, per questo il PDF non lo sapeva. Resta vero che i difensori condividono il
   coefficiente con centrocampisti e attaccanti. Sui nostri 5 turni, sostituire i gol subiti
   coi gol fatti per i difensori **non mostra un guadagno**. Con un intervallo della differenza
   largo quanto [−0,35, +0,27], però, non si può nemmeno dire che i due regressori si
   equivalgano. Sezione 3.
3. **Due affermazioni marcate [Certain] nel PDF sono sbagliate.** [Certain] "Nessuno invia la
   formazione in automatico" e "fantabot: invio della formazione non costruito": fantabot l'ha
   documentato e implementato (`POST /gaming/v1/teamLineup/{division}`, catturato il 02/09,
   bloccato da due interruttori). [Certain] "BigBalls è indietro di almeno una giornata": in
   Serie A non si gioca fra il 20/09 e il 10/10. Tutti e cinque i campionati maggiori si
   fermano il 20/09 e ripartono il 9 o il 10/10 (connettore BigBalls, `get_coverage`, 02/10),
   e leghe.fantacalcio.it mette la prima giornata della lega sul turno 6 di Serie A, con
   scadenza il 10/10.
4. **Le cose più utili delle fonti il PDF non le mette in evidenza:**
   - **l'endpoint delle regole della lega** (`/onboarding/v1/league/settings/calculate`, da
     fantabot): i pesi di bonus e malus (`bnMls`) sono già identificati, compresi `bmpsa`
     (rigore parato) e `bmcsh` (porta inviolata), cioè i due `null` di `scoring` in
     `config/league.json`. Restano da interpretare `step`, `subst` e `stbdf`;
   - **i campi della giornata calcolata di `teamLineup`** (`scr`, `cscr`, `b`, `m`), già
     decodificati da fantabot e fantaclaude su leghe vere il 22/09. Il nostro
     `.docs/leghe-fc-api.md` li dà ancora "da capire alla prima giornata calcolata";
   - **l'archivio di JARVIS: 11 stagioni di voti per partita** (2015-16 → 2025-26, 9 usate
     per addestrare), prese dalla stessa pagina di fantacalcio.it che legge `import_voti.py`.
     È un modo per avere abbastanza dati sui pezzi piccoli del modello. Non è un beneficio
     garantito, e ha prerequisiti seri (4.G).
5. **Una costante mai provata comincia a contare dal consiglio per la giornata 7.** [Certain]
   `FORMA_ULTIMI_VOTI = 5` (`scripts/lib/roster.py:44`) non è mai stato messo alla prova nel
   backtest. Prima della giornata 6 nessuno ha più di 5 voti; dopo, il modello comincia a
   scartare i più vecchi. JARVIS dichiara che sulle sue stagioni la forma recente non predice,
   ma non si sa se valga per noi. **Il 5 resta finché una variante non passa il collaudo**: la
   regola del progetto non ha eccezioni. Quello che va fatto subito è preparare la misura
   (4.E).
6. **"Su un paio di punti sono avanti a noi" va capito bene.** [Certain] Nessuno domina. La
   nostra metrica è più vicina all'obiettivo: punti della formazione, regole della lega, tutte
   le rose. Ma è misurata su 36 formazioni di 3 giornate. JARVIS si verifica su due stagioni
   tenute fuori dall'addestramento (21.506 voti, correlazione ed errore). Il "+2,2 punti a
   giornata" di fanta-asta viene da stagioni generate dall'autore, e il README lo dice. Sono
   avanti su **dati e conoscenza dell'API**.

---

## 1. Le affermazioni del PDF sul nostro progetto, una per una

Verdetti: **Corretta**, **Parziale** (vera ma incompleta o imprecisa), **Superata** (il
progetto lo fa già), **Non sostenuta** (non regge per il caso attuale), **Sbagliata**.

| # | Il PDF dice | Come stanno le cose | Verdetto |
|---|---|---|---|
| 1 | `avv` è lo stesso termine per tutti i ruoli, anche per P e D | `costruisci_modello` stima **due** coefficienti: uno per i portieri, uno per D+C+A insieme (`roster.py:252`, `:257`, `:301`). Il regressore (gol subiti dall'avversario) è lo stesso per tutti. La variante portieri sui gol fatti esiste (`backtest_formazione.py:149`): 55 previsioni, ΔMAE −0,005 [−0,108, +0,098]. Per i difensori nessuna variante è mai stata provata. Nota: i β citati in `.docs/difetti-consiglio-formazione.md` (0,40 per D/C/A, 0,45 per P) sono del 27/09; oggi sono 0,58 e 0,45 | **Parziale** |
| 2 | Rischio: alla rimisura `avv` viene scartato "per il motivo sbagliato" | Il rischio che `avv` esca "non dimostrato" c'è (oggi +0,85 [−0,03, +1,71]). Che la causa sia il regressore dei difensori non è dimostrato, e nemmeno che sia la potenza | **Parziale** |
| 3 | Classifica: nessun endpoint | Nessun endpoint noto. Il report somma già i punti in classifica dal calendario della lega (`roster.py:417`, `report_formazione.py:384`), e i criteri di parità sono in `config/league.json` → `competizioni` | **Corretta, incompleta** |
| 4 | `teamLineup`: serve un resolver `matchDay` ↔ `championshipMatchDay`, "prima della giornata 6" | Esiste dal 29/09: `giornata_da_controllare` (`controlla_formazione.py:60`) legge i due numeri dal calendario della lega (`lega_competizioni.json`, presi così come li dà l'API), e la risposta viene scartata se il `tid` non è il mio (`:122`). Resta un caso limite, 4.D | **Superata** |
| 5 | "La lega ha 33 giornate contro 38" come rischio di disallineamento | Oggi la corrispondenza è una per una (Serie A 6-38 = giornate 1-33) e si legge dall'API, non si calcola. Non esclude disallineamenti futuri, ma il codice non li ricava da un conto | **Non sostenuta** per il mapping attuale |
| 6 | `asta.py` non applica le regole di mercato | Vero (`config/league.json` → `regole_mercato`). Ma la riparazione è "a mercato invernale chiuso": non è urgente | **Corretta, non urgente** |
| 7 | Scambi | Solo a gennaio, e per `CLAUDE.md` l'assistente scambi non si fa senza una richiesta esplicita | **Corretta, fuori scopo oggi** |
| 8 | Scontri diretti: manca la probabilità di vittoria | Vero: il report mostra l'avversario di lega e lo scenario dei gol, non la probabilità di vincere. Sul valore vedi 4.H | **Corretta** |
| 9 | Calibrazione della titolarità con `status_scadenze.json` | La raccolta è già in programma e già attiva (`salva_status_scadenza.py`, prima foto alla giornata 6). La calibrazione non è ancora fatta. Il metodo di fantaclaude è utile (4.F) | **Già pianificata** |
| 10 | Modello addestrato "con cancello", come JARVIS | Abbiamo un cancello in punti veri, ma su 36 formazioni; loro su due stagioni tenute fuori. Ci mancano i dati, più che il cancello (4.G) | **Parziale** |
| 11 | Due agenti, ricognitore e allenatore, per rendere `verificata` un vincolo | Dove si decide, la separazione esiste già: i numeri li calcola `report_formazione.py`, che non va su internet, e le notizie decidono solo i pari. Ma il punto 0.1 mostra che il vincolo su `verificata` oggi è solo procedurale: `notizie_rosa.py` controlla URL e tipi (`:97`), non la verità. Il PDF ha individuato il punto giusto con il rimedio sbagliato (4.A) | **Parziale** |
| 12 | Schede con scadenza, idea per `notizie_rosa.json` | Già fatto: scadenza a 30 giorni, 90 per allenatore e mercato (`notizie_rosa.py:49-50`) | **Superata** |
| 13 | Correzione limitata a ±0,6 di fantavoto per le notizie | La nostra regola è più severa: le notizie non toccano i numeri, decidono i pari e cambiano lo status solo se cambiano i fatti. Questo limita il danno di una notizia sbagliata, non lo annulla (punto 0.1) | **Superata** |
| 14 | Dati vecchi meglio di file vuoti, avviso oltre i 4 giorni | Già fatto: soglie che bloccano la scrittura (meno di 400 giocatori, rose vuote, colonne cambiate) e `STATUS_VECCHIO_GIORNI = 4` (`roster.py:12`). Le soglie bloccano i dati vuoti o rotti, non quelli sbagliati ma ben formati | **Superata** |
| 15 | Controlli sullo scraping (squadra giusta, paginazione) | Paginazione, `networkidle` e banner riguardano Playwright e l'HTML di Leghe, che noi non usiamo: leggiamo l'API | **Non applicabile** |
| 16 | Il fuzzy matching risolverebbe i "non trovati" | Oggi 1 solo giocatore posseduto su 300 è `n/d` (Haps). Il matching è severo apposta: "Lautaro Martinez" finiva sul portiere `Martinez Jo.` (vedi `rigoristi.py`). Un abbinamento sbagliato fa più danni di un "non trovato", che almeno si vede. Non esclude un uso controllato in futuro | **Non sostenuta** oggi |
| 17 | BigBalls indietro di almeno una giornata | Pausa delle nazionali (punto 0.3) | **Sbagliata** |
| 18 | Nessuno invia la formazione; fantabot non l'ha costruito | fantabot sì (punto 0.3) | **Sbagliata** |
| 19 | Il `docs/leghe-api.md` di fantabot risponde 404 | Nel repo al commit `799210e` c'è: 665 righe. Non so quale URL abbia letto il PDF, né se prima rispondesse 404 | **Sbagliata** al commit indicato |
| 20 | Cifrare il token a riposo, come fantabot | Non si applica: non salviamo token, il jwt vive in memoria durante l'esecuzione (`leghe_fc_client.py`), e le credenziali arrivano dall'ambiente | **Non applicabile** |
| 21 | Nel registry dei connettori non c'è niente di fantacalcio; BigBalls copre la Serie A dal 2014-15 (4.941 partite) | Verificato il 02/10 con la ricerca nel registry e con `get_coverage` del connettore BigBalls (istantanea delle 06:44 UTC) | **Corretta** |
| 22 | Rischio termini d'uso di fantacalcio.it | Ragionevole. Ogni giro del mattino fa 3 login: uno per ciascuno di `import_rose_lega.py`, `import_calendario_lega.py` e `controlla_formazione.py`. Non vanno aumentati senza leggere i termini | **Corretta** |

---

## 2. Le fonti, verificate

Solo ciò che conta per noi. "Confermato" vuol dire letto nel codice o nei documenti del repo
al commit indicato sopra.

**fantaclaude** (Mantra). Confermati il server MCP in sola lettura (`get_account`,
`get_league`, `get_league_settings`, `get_my_team`, `list_teams`, `list_competitions`,
`get_server_time`, `get_lineup`) e la rimozione delle email. Il resolver
(`mcp/.../calendar.py`) cerca la partita della squadra in tutti i turni della competizione
che cadono sulla stessa giornata di Serie A, e restituisce **la prima** che trova. Il caso di
più turni sulla stessa giornata è dichiarato possibile, non osservato. La calibrazione c'è
ed è più completa di come la descrive il PDF (`core/.../analysis/calibration/pstart.py`). Usa
fasce di 10 punti con intervalli di Wilson e confronta il Brier score della percentuale
pubblicata con quello della sola frequenza di base. L'esito misurato è "ha preso voto", non
"è partito titolare": è proprio la domanda che ci serve. Il PDF **non dice** la cosa più utile.
Il 22/09, su 138 righe delle giornate 3-5, hanno verificato che `scr` è il voto di
fantacalcio.it e che `cscr` è il fantavoto della lega, con due codici per "senza voto" (`scr`
55 e 56, insieme a `cscr` 100) (`core/.../ingest/match_scores.py`). Sono risultati
documentati da loro: non ho ripetuto le loro chiamate.

**fantabot** (Mantra, licenza MIT). Il suo `docs/leghe-api.md` (665 righe) è il riferimento
più ampio che ho trovato sull'API di Leghe, ed è la fonte più utile di questa ricerca:
- `GET /onboarding/v1/league/settings/calculate`: `bnMls` (bonus e malus per evento), `step`
  (soglie dei gol), `subst` (sostituzioni), `stbdf`. I pesi di `bnMls` usati nel calcolo sono
  identificati dalla decodifica di `teamLineup` (tabella a `:487`): `bmgs`, `bmgc`, `bmpsa`,
  `bmcsh`, `bmyc` e gli altri. `step`, `subst` e `stbdf` no;
- `GET /onboarding/v1/league/status`: `mstr` è l'inizio della prima partita in UTC, cioè la
  scadenza (verificato contro la giornata 5). `sto` diventa vero al primo calcio d'inizio,
  cioè quando la formazione non si può più cambiare, non quando la giornata è calcolata;
- la giornata calcolata di `teamLineup`: `cscr = scr + Σ b[i]·peso(i) − m` su 454 righe; `b`
  ha 16 contatori, di cui 13 identificati (gol, gol subiti, rigore parato, porta inviolata,
  assist...); `m` è un malus da −1; `lply` resta `null`;
- l'invio della formazione (`POST`, `adapters/http/apileague.py:492`, con doppia
  abilitazione in `application/arming.py`), che noi **non** vogliamo usare (sezione 5).

Lo schema del "sentiment" con confidenza zero uguale a "nessuna copertura" è confermato
(`domain/asta/sentiment.py`).

**JARVIS** (Classic con modificatore di difesa). Confermati: `avv` per ruolo (P e D sui gol
fatti dall'avversario, C e A sui gol subiti), stagione precedente mescolata fino alla decima
partita, neopromosse con la media delle retrocesse (`scripts/modello.py`, `contesto()`).
Confermati anche "La sfida, sulla carta", "Com'è andata", il file `.ics`, ntfy e l'avviso
oltre i 4 giorni. Il PDF **non dice** quattro cose che contano più dell'`avv` per ruolo:
- l'archivio: `scripts/storico.py` scarica `fantacalcio.it/voti-fantacalcio-serie-a/{stagione}/{giornata}`
  dal 2015-16 al 2025-26 (11 stagioni), la stessa pagina e lo stesso schema di URL di
  `import_voti.py`. Il modello è addestrato su 92.770 righe di 9 stagioni (2017-18 → 2025-26:
  per le prime due manca il calendario con gli avversari);
- i coefficienti che stima, per gol a partita dell'avversario: P 0,50, A 0,31, D 0,16, C 0,16.
  Il fattore campo vale tra +0,14 e +0,18 in tutti i ruoli. Annotano che i pesi messi a mano
  prima sopravvalutavano l'avversario (D 0,8 → 0,16);
- "la forma recente è stata misurata e lasciata fuori: non predice" (`STORIA.md`, B2): usano
  una media con decadimento 0,97, circa 33 presenze. È la loro conclusione, sui loro dati e
  con la loro metrica: non dice niente di certo sulla nostra finestra;
- la probabilità di vittoria è implementata (2.000 simulazioni), insieme a un suggerimento di
  cambio per varianza con soglie strette (vittoria +2 punti, giocatori entro 0,5). Il 15/09
  quel suggerimento non è scattato mai. Questo misura quel criterio in quel giorno, non il
  valore dell'idea.

La loro verifica, sulle due stagioni tenute da parte (21.506 voti), dà correlazione ed
errore: modello contro calcolo di prima P 0,217/0,203, D 0,189/0,131, C 0,197/0,183, A
0,165/0,154, con l'errore più basso in tutti i ruoli.

**fanta-asta** (Classic con modificatore). Confermati `schiera.py` (Monte Carlo a numeri
comuni contro l'avversario), `proposte()` con capitano e vice intoccabili, il bug "501 su 500"
del **loro** ottimizzatore d'asta (`tests/qa_asta.py:208`) e il prezzo massimo come prezzo di
indifferenza. Il "+2,2 fantapunti a giornata" è misurato su stagioni sintetiche, e il README
lo dichiara. Il test RED/GREEN della skill di scouting ha tre casi RED: 3 agenti su 3
citavano link mai aperti e contavano due volte numeri già nelle stime. Nei tre casi GREEN,
con la ricerca web bloccata, gli agenti si sono **astenuti** (0 KPI su 8). Poi c'è un quarto
caso con un testo leggibile e un giocatore inventato: 6 KPI su 8 corretti e nessuna nuova
razionalizzazione (`docs/superpowers/skill-tests/scouting-2026-09-28.md:33`).

**fantamagazine**. Confermati gli URL `classifica?id=…&app=true&legacy=true` dentro un
iframe, il controllo sulla paginazione, `domcontentloaded` al posto di `networkidle`, e "3,5
crediti per punto di quotazione" (8.615 su 2.452). Quest'ultimo vale per la loro lega, non è
un tasso da trasferire. La parte sulle pagine si applica solo a chi legge l'HTML, non a noi.

**fanta** (armandoferrara86). Confermati tre subagent (`ricognitore`, `statistico`,
`allenatore`), l'ultimo senza strumenti web. La regola dell'allenatore "un titolare sicuro da
6 vale più di un fuoriclasse in ballottaggio" va contro quello che abbiamo dimostrato per
l'**ordine dentro un ruolo** con la nostra panchina (si ordina per il valore se prende voto,
la panchina copre). Non dice niente sul resto delle loro scelte. Si può prendere la struttura,
non quella regola.

**fantanostalgia PR #114**. La formula "voto senza bonus = `cscr` meno i bonus positivi"
(`backend/api/fantacalcio.py:166`) serve al loro punteggio, non al nostro. Il resto delle
ipotesi sul formato della risposta (sentinelle 55/56, `b` a 16 contatori, nomi delle squadre
"assunto, non verificato") coincide con quanto documentato da fantabot e fantaclaude, e la
PR dichiara di non averlo verificato in diretta. Per noi non aggiunge prove, ma non è
irrilevante come riscontro.

**fantacalcio-nuovo** (`CLAUDE.md` → `MEMORIA.md`) e **Fantacalcio-Assistant** (bot Telegram)
sono confermati. Su **fantacalcio-py**: l'indice "Affare" combina fantamedia, presenze,
disciplina e continuità, e divide per `log1p(prezzo)`. Il confronto "il doppio per credito"
del README invece è punti divisi per crediti, una misura che favorisce chi costa poco e che,
con gli slot fissi, non dice quale rosa fa più punti.

---

## 3. L'`avv` per ruolo, misurato sui nostri dati

**Cosa si è misurato** (appendice A, fuori dal repo, sola lettura di `data/`). Come fa
`costruisci_modello`: per ogni giocatore con almeno 2 voti, lo scarto di ogni fantavoto dalla
sua media; per ogni partita i gol subiti e i gol fatti dall'avversario **senza quella
partita**, frenati verso la media come se avesse 5 partite in più. Pendenza per ruolo, con
intervallo bootstrap ricampionando le partite. Giornate 1-5, 50 partite. Codex ha rilanciato
lo script e ottenuto gli stessi numeri.

| Ruolo | n | Solo gol subiti: β [IC 95%] | Solo gol fatti (segno invertito): β [IC 95%] | Insieme: subiti | Insieme: fatti |
|---|---|---|---|---|---|
| P | 96 | +0,45 [−0,34, +1,21] | +0,62 [−0,03, +1,35] | +0,31 [−0,44, +1,06] | +0,53 [−0,08, +1,17] |
| D | 479 | +0,52 [+0,20, +0,81] | +0,49 [+0,18, +0,74] | +0,42 [+0,10, +0,71] | +0,38 [+0,06, +0,64] |
| C | 552 | +0,64 [+0,24, +1,08] | +0,51 [+0,13, +0,94] | +0,54 [+0,16, +0,99] | +0,35 [−0,08, +0,77] |
| A | 260 | +0,59 [−0,11, +1,37] | +0,67 [−0,00, +1,31] | +0,48 [−0,22, +1,25] | +0,58 [−0,10, +1,22] |
| D+C+A (oggi) | 1291 | +0,58 [+0,28, +0,89] | +0,54 [+0,25, +0,82] | +0,48 [+0,19, +0,78] | +0,41 [+0,09, +0,68] |

Fra le 20 squadre, gol fatti e gol subiti delle prime 5 giornate correlano a −0,29: i due
regressori non sono la stessa misura.

**Cosa si può dire, e cosa no:**
- per i **difensori** lo scambio proposto dal PDF non mostra un guadagno: la differenza fatti
  − subiti è [−0,35, +0,27]. Questo **non** dimostra che i due regressori si equivalgano:
  dichiarare un'equivalenza richiederebbe un margine pratico fissato prima e un intervallo
  stretto dentro quel margine, e qui l'intervallo è largo [Certain];
- nel campione, usati insieme, tutti e due hanno pendenze con intervalli sopra lo zero per i
  difensori e per D+C+A. È un indizio su cosa provare (la forza complessiva dell'avversario),
  non una prova che un modello con tutti e due preveda meglio: una pendenza nel campione non
  è un guadagno fuori campione, né punti della formazione [Certain];
- per i **portieri** i gol fatti sono un po' davanti, come vuole il meccanismo (−1 per gol
  subito), ma su 96 voti gli intervalli si sovrappongono quasi del tutto. È lo stesso verdetto
  del 27/09;
- **il confronto con JARVIS non mostra coefficienti gonfiati.** Nel fit il regressore è
  frenato: con 4 partite restanti e freno 5 vale 4/9 dello scarto vero dalla media. Riportati
  a un gol "nudo", i nostri β sono circa D 0,23, C 0,28, A 0,26, P 0,20, contro D 0,16, C
  0,16, A 0,31, P 0,50 di JARVIS (che per D e P usa l'altro regressore). Stesso ordine di
  grandezza. La prima versione di questo documento diceva "2-4 volte tanto": era un errore di
  scala [Certain];
- **limiti**: misura dentro il campione; il bootstrap per partita ignora che le partite della
  stessa giornata si somigliano (intervalli ottimisti, come quelli del backtest); non è
  `backtest_undici.py`, che resta il collaudo.

**Conclusione.** Che lo scambio per i difensori faccia guadagnare non è dimostrato, e non è
dimostrato nemmeno il contrario. Con 5 giornate c'è da aspettarsi molta incertezza anche alla
8 e alla 10, ma non ho un'analisi di potenza che dica quanta. La strada è il confronto in
punti, con previsioni fatte solo sul passato (4.G).

---

## 4. Cosa usare davvero, in ordine

Ordine rivisto dopo la verifica di Codex: prima ciò che serve prima della scadenza del 10/10
o che non si recupera dopo. Niente di questo è stato fatto.

### Priorità 1: prima della scadenza del 10/10

**A. Notizie coerenti con i dati del repo** [Certain che il problema esista]. Tre passi:
1. correggere le due notizie del punto 0.1. È una modifica a `data/`, quindi con il via
   dell'utente;
2. un controllo automatico in `notizie_rosa.py valida` per i fatti che il repo può smentire:
   rigori calciati e da chi (`matchday_stats.json`, `rigoristi.json`), date d'infortunio
   (`injuries.json`), squalifiche (`squalifiche.json`). Una notizia che contraddice i dati si
   rifiuta o si segnala, invece di entrare come verificata;
3. rendere controllabile la verifica. Un booleano "letta: sì" scritto da chi scrive la
   notizia non prova niente. Meglio una **citazione testuale** breve per fonte, che si può
   ricontrollare sulla pagina. Il criterio resta quello di `CLAUDE.md`: due fonti indipendenti
   **o** una fonte ufficiale (la prima versione proponeva "almeno due fonti lette", che
   cancellava l'eccezione della fonte ufficiale). Anche due URL non garantiscono indipendenza:
   due siti che riprendono la stessa agenzia sono una fonte sola.

Il test RED di fanta-asta (3 agenti su 3 citavano link mai aperti) suggerisce di provare il
passo 7 di `aggiorna-dati` con un subagent e la ricerca web bloccata o ridotta, per vedere se
scrive comunque `verificata: true`. Il punto 0.1 dice che il problema esiste anche con la
ricerca funzionante.

**B. Congelare il consiglio prima della scadenza** [Certain che oggi manchi].
`salva_status_scadenza.py` salva status e `prob_titolare`, non il consiglio, la rosa o i
parametri del modello. Senza il consiglio di prima della scadenza, la retrospettiva della
giornata (4.D) confronta la formazione inserita con un consiglio ricostruito dopo, e non è
più un confronto onesto. La storia di git aiuta solo in parte: `data/` è versionato ogni
mattina, ma il report dipende anche dalla data del giorno (`prossimo_turno`) e ricostruirlo è
fragile. Basta una foto come quella degli status: modulo, titolari, panchina in ordine,
valori, commit del codice. Va scritta ogni mattina fino alla scadenza. Per avere la giornata
6 deve esistere prima del 10/10.

**C. Leggere dalla lega le sue regole** [Likely, costo basso]. Da fantabot:
`GET /onboarding/v1/league/settings/calculate` e `GET /onboarding/v1/league/status`, sola
lettura, col client che abbiamo (`lib/leghe_fc_client.py`).
- `bnMls` dovrebbe chiudere i due `null` di `scoring` (`bonus_rigore_parato` →
  `bmpsa`, `bonus_porta_inviolata` → `bmcsh`);
- `step` e `subst` dovrebbero confermare soglie dei gol, sostituzioni e panchina, che oggi
  vengono da un documento e da una conferma a voce;
- `mstr` e `sto` controllano la scadenza che calcoliamo dalle date di BigBalls.

Ritrovare 66 e 5 in `step` dice che il campo è quello, non che tutta la sua semantica sia
chiara. La prova vera arriva dopo il 12/10: ricostruire `cscr` coi pesi letti qui (4.D). Il
primo passo è guardare la risposta e scriverla in `.docs/leghe-fc-api.md`, non in `config/`.

### Priorità 2: dopo la prima giornata calcolata (dopo il 12/10)

**D. La giornata calcolata di `teamLineup`: verificarla, poi usarla** [Certain che i campi
esistano su due leghe Mantra; Likely che valgano anche in Classic].
1. confrontare `scr` col voto Redazione di `matchday_stats.json` e controllare che `cscr` =
   `scr` + Σ `b`·pesi − `m` coi pesi letti in C. Se torna, abbiamo il fantavoto **della lega**,
   il blocco 1 della "Classifica" in `CLAUDE.md` (fasi future);
2. la **classifica**: non serve il fantavoto per giocatore. Bastano `punteggio_casa`,
   `punteggio_trasferta` e `punti_classifica_*` di `lega_competizioni.json` (l'importer
   rinomina così `ptH`, `ptA` e `standingPt*` dell'API, `import_calendario_lega.py:56`) più i
   criteri di parità di `config/league.json`. La pagina "legacy" di fantamagazine conviene
   come **controllo a mano una tantum**, non come scraper (login Angular, banner, iframe);
3. la **retrospettiva di giornata** (da JARVIS "Com'è andata" e dalla "week" di
   fantaclaude): punti veri della formazione inserita, del consiglio congelato (B) e della
   migliore possibile con la mia rosa, coi punti **della lega**. È il primo confronto col
   mondo vero sulla mia squadra. Il backtest usa il fantavoto standard di fantacalcio.it e
   tutte le rose.

Caso limite da coprire insieme (da fantaclaude): `giornata_da_controllare` restituisce una
sola giornata anche se due competizioni cadono sulla stessa giornata di Serie A
(`controlla_formazione.py:101`). Con formazioni distinte per competizione (`allComp` falso)
la seconda non verrebbe controllata. [Certain] Oggi la lega ha una sola competizione
(`lega_competizioni.json`: FANTACARBONARA): arriverà con la Coppa Italia, se arriverà.

**E. La finestra della forma: preparare la misura, non cambiarla** [Certain che non sia mai
stata provata]. Varianti in `backtest_undici.py`: ultimi 5 (oggi), 10, tutti, decadimento.
La prima giornata in cui la finestra conta è la 7: da lì il backtest le può confrontare. Il
5 resta finché una variante non passa il collaudo con l'intervallo che esclude lo zero. Non
è dimostrato che l'effetto alle giornate 7-8 sia trascurabile: pochi voti scartati possono
spostare una scelta vicina alla soglia. Per questo va misurato e mostrato presto, non deciso
a priori.

**F. Calibrare `prob_titolare` col metodo di fantaclaude** [Likely]. Esito "ha preso voto",
fasce di 10 punti con intervallo di Wilson, Brier score della percentuale del sito contro la
sola frequenza di base. Dati: `status_scadenze.json` più i voti; 5 turni si hanno **dopo** la
giornata 10. Da gestire: probabilità mancanti, ruoli, osservazioni dipendenti (giocatori della
stessa squadra e della stessa partita). Due prerequisiti:
- il backtest oggi **non** usa la percentuale del sito. `Simulazione.quote`
  (`lib/simulazione.py:108`) stima la probabilità dalle presenze precedenti anche quando le
  foto esistono. Per misurare la probabilità pubblicata, e poi quella tarata, va insegnato al
  backtest a leggere le foto;
- una calibrazione per singolo giocatore non verifica da sola il "99%" della coppia di
  portieri né lo scenario dei gol: sono probabilità congiunte.

### Priorità 3: dopo, con prerequisiti

**G. Le stagioni passate per i coefficienti piccoli** [Guessing sul beneficio]. È il modo che
vedo per avere abbastanza dati su avversario per ruolo, casa/trasferta e forza delle squadre a
inizio stagione. Non è un beneficio garantito, e non è detto che sia l'unico modo.
Prerequisiti, tutti [Certain] sul codice di oggi:
- **isolamento per stagione.** `import_calendario_seriea.py` fonde le stagioni nello stesso
  file (per `match_id`), le righe di `matchday_stats.json` non hanno la stagione, e
  `costruisci_modello` e `Simulazione` usano la giornata senza la stagione (`roster.py:199`,
  `simulazione.py:53`). Scrivere le stagioni passate negli stessi file contaminerebbe modello
  e backtest: servono file separati, con la stagione nella chiave;
- **coerenza storica**: bonus e regole del voto cambiati negli anni, ruoli e squadre di
  allora, giocatori non più nel listone, rose di oggi da non usare per il passato;
- **stagioni tenute fuori** sia dall'addestramento sia dalla scelta delle varianti;
- **chiamate API**: niente box score, ma `/matches` è paginato a 200, quindi almeno 2
  chiamate per stagione. Poche, non zero (`import_calendario_seriea.py:65`).

Varianti da mettere accanto all'attuale in `backtest_undici.py`: (a) JARVIS, P e D sui gol
fatti; (b) tutti e due i termini; (c) coefficienti stimati sullo storico. Neopromosse con la
media delle retrocesse, come JARVIS.

Sul casa/trasferta: il progetto lo dà "provato e scartato" (ΔMAE −0,006 [−0,011, −0,000] sulle
giornate 3-5), JARVIS lo stima tra +0,14 e +0,18 su 92.770 righe. Le due cose non si
contraddicono per forza: la nostra prova misura l'errore di una variante, non il coefficiente.
Anche se l'effetto fosse quello di JARVIS, da solo ribalterebbe solo confronti fra due
giocatori già vicini. Sommato agli altri pezzi e su tutta la formazione può contare di più.

**H. Probabilità di vittoria nello scontro diretto** [non misurata]. La prima versione la
dava "di poco valore": non era dimostrato. Codex ha dato un controesempio matematico. Gli
altri dieci fanno 67 e l'avversario 74. Un attaccante sicuro da 7 porta a 74 (pareggio
certo); uno da 4 o 9 al 50% porta a 71 o 76 (pareggio o vittoria). Si perde 0,5 di valore
atteso, più di `SOGLIA_PARI`, e si passa da 1 a 2 punti in classifica attesi. Con totali
incerti (circa ±7 punti) l'effetto si attenua, e quanto spesso capiti non è misurato. Resta
in priorità 3 per i dati: serve la varianza di ogni giocatore, che con 5-10 voti è rumore.
`teamLineup` dà già la formazione inserita dall'avversario, prima della scadenza.

**I. Asta di riparazione e scambi** (rigioco con `regole_mercato`, `proposte()` di fanta-asta,
"Mercato, sulla carta" di JARVIS, tasso crediti/quotazione di fantamagazine). Da dicembre, e
solo su richiesta esplicita (`CLAUDE.md`). Il rigioco ha senso solo se c'è un piano d'asta da
collaudare: `asta.py` registra gli acquisti, non fa piani.

**J. Documentazione** [Certain che serva]. Il README è fermo al 29/09: non dice di
`controlla_formazione.py` né del coefficiente separato dei portieri, e
`.docs/difetti-consiglio-formazione.md` riporta β vecchi. [Likely] È la causa più probabile
degli errori del PDF, che dichiara di essersi basato sul README. Basta una riga nel README
che rimandi a `CLAUDE.md` e `.docs/` come fonte. Separare `CLAUDE.md` (43 KB, caricato a ogni
sessione) in regole e memoria, come Tiri6, è utile ma non urgente.

---

## 5. Cosa scartare, e perché

| Idea | Perché no |
|---|---|
| Fuzzy matching dei nomi (MCP di FPL) | Oggi 1 "non trovato" su 300 posseduti; un abbinamento sbagliato fa più danni di uno mancato. Se i "non trovati" crescono: una tabella di alias scritta a mano, come `kb/rules/aliases.yml` di fantaclaude |
| Invio automatico della formazione (fantabot) | Scrive sul sito con un'API non documentata: un errore costa (0-3 a tavolino o formazione sbagliata), e c'è il rischio sui termini d'uso. Il controllo in sola lettura che abbiamo copre il bisogno vero (accorgersi in tempo) |
| Due agenti, ricognitore e allenatore, come architettura | Da noi decide già il codice, che non va su internet. Il rischio rimasto è la verità delle notizie, e lo copre il punto 4.A |
| Server MCP di Leghe (fantaclaude) | Abbiamo già client e importer; un MCP aggiunge un modo di accesso, non dati |
| Cifratura del token | Non salviamo token |
| Bot Telegram | La notifica della routine arriva già sul telefono |
| Indice "Affare" | Pensato per l'asta d'inizio stagione; da riguardare, se mai, per la riparazione |
| `.ics` delle scadenze (JARVIS) | Comodo, ma non migliora le decisioni: la notifica di `controlla_formazione.py` copre il rischio di dimenticarsi |

---

## 6. Limiti di questa analisi

- Ho letto codice e documenti delle fonti, non li ho eseguiti. fantaclaude e fantabot sono
  leghe **Mantra**: il significato dei campi di `teamLineup` e `settings/calculate` va
  riverificato sulla nostra lega Classic (4.C e 4.D lo prevedono).
- La misura della sezione 3 è descrittiva e dentro il campione. Non sostituisce
  `backtest_undici.py` e non autorizza a cambiare `roster.py`.
- I confronti numerici con JARVIS (coefficienti, casa/trasferta) mettono insieme modelli
  costruiti in modo diverso: valgono come ordine di grandezza.
- Non ho controllato i termini d'uso di fantacalcio.it.
- Il punto 0.1 è stato trovato da Codex. Non ho ricontrollato le altre 34 notizie una per
  una: il controllo automatico del punto 4.A serve proprio a questo.

---

## 7. Domande per chi rivede, e risposte di Codex

1. *La conclusione della sezione 3 regge?* No, nella prima versione: trasformava un
   risultato non significativo in un'equivalenza. Corretta.
2. *`FORMA_ULTIMI_VOTI` è urgente?* È urgente preparare la misura, non cambiare la costante.
   Corretto, e la prima giornata toccata è la 7, non la 6.
3. *Lo storico introduce distorsioni?* Sì: regole e voti cambiati negli anni, ruoli e squadre
   di allora, giocatori usciti dal listone, rose di oggi, e soprattutto stagioni mescolate
   negli stessi file. Aggiunte in 4.G.
4. *La probabilità di vittoria può cambiare una scelta oltre `SOGLIA_PARI`?* Sì, in
   principio (controesempio in 4.H). Quanto spesso, non si sa.
5. *Qualche "Sbagliata" della sezione 1 è troppo assoluta?* Sì: 5 e 16 sono diventate "Non
   sostenuta", 19 vale "al commit indicato".

---

## 8. Revisione di Codex (02/10), riscontrata

Codex ha letto il documento al commit `f69165a`, il codice a `eeb1c07` e i dieci repo ai
commit della tabella, e ha rilanciato l'appendice A e `backtest_undici.py`. Non aveva il PDF
né la chiave di BigBalls. Ogni rilievo qui sotto è stato ricontrollato su codice e dati prima
di correggere.

**Accolti e corretti** (tutti [Certain] dopo il controllo):

| Rilievo | Dove |
|---|---|
| Due notizie "verificate" false (Adams e il rigore della giornata 5, Busio "da due mesi") | 0.1, 4.A |
| Il validatore "due fonti lette" cancellava l'eccezione della fonte ufficiale; un booleano autodichiarato non prova la lettura | 4.A |
| Manca la foto del consiglio prima della scadenza: senza, la retrospettiva non è prospettica | 4.B |
| Lo storico delle stagioni passate non è isolato per stagione in nessun file né chiave | 4.G |
| Non significativo ≠ equivalente; una pendenza nel campione non è un guadagno | 0.2, 3 |
| Nessuna eccezione al collaudo per `FORMA_ULTIMI_VOTI`; la prima giornata toccata è la 7 | 0.5, 4.E |
| "Più severo di entrambi" non dimostrato: JARVIS ha 21.506 voti fuori campione | 0.6, 1.10 |
| Il confronto dei β con JARVIS ignorava il freno 4/9: nessuna prova di coefficienti gonfiati | 3 |
| Il backtest stima la probabilità dalle presenze, non dalle foto | 4.F |
| `/matches` di BigBalls consuma chiamate (pagine da 200) | 4.G |
| Nomi dei campi locali della classifica (`punteggio_*`, `punti_classifica_*`) | 4.D |
| Archivio JARVIS di 11 stagioni, 9 per l'addestramento | 0.4, 2 |
| La Liga riparte il 9/10, non il 10/10 | 0.3 |
| `sto` vuol dire formazione bloccata, non giornata chiusa | 2 |
| I pesi di `bnMls` sono già identificati da fantabot | 0.4, 2, 4.C |
| Il test RED/GREEN di fanta-asta ha anche un quarto caso con testo leggibile | 2 |
| fantanostalgia: le ipotesi sul formato non sono irrilevanti come riscontro | 2 |
| Indice Affare ≠ punti per credito | 2, 5 |
| Rimandi invertiti fra probabilità di vittoria e notizie; correlazione −0,29, non −0,30 | 1, 3 |
| Il "poco valore" della probabilità di vittoria non era dimostrato | 4.H |
| 5 e 16 troppo assolute; una competizione sola è un fatto verificabile, non un'ipotesi | 1, 4.D |
| Ordine delle priorità: notizie e foto del consiglio prima; lo storico sopravvalutato | 4 |

**Non accolti, o accolti in parte:**
- *BigBalls e registry "non verificabili"* (1.17, 1.21): Codex non aveva la chiave. Li ho
  verificati io il 02/10 col connettore BigBalls (`get_coverage`: tutti e cinque i campionati
  maggiori fermi dal 20/09, ripresa il 9-10/10, 4.941 partite di Serie A) e con la ricerca nel
  registry dei connettori. Restano come scritto, con la fonte indicata.
- *Numero dei login "non ricavabile dal codice"* (1.22): si ricava. Il giro del mattino lancia
  tre script che leggono la lega, e ognuno fa un login (`client.login(` una volta in ciascuno).
  Corretto in "3 login a giro".
- *Foto del consiglio* (4.B): accolto, ma con una precisazione. La storia di git di `data/` e
  del codice permette in principio di ricostruire il consiglio di una mattina; la foto resta
  necessaria perché quella ricostruzione dipende dalla data del giorno ed è fragile.

---

## Appendice A: la misura della sezione 3

Eseguita il 02/10 sul commit `eeb1c07`, fuori dal repo, in sola lettura; rilanciata da Codex
con gli stessi risultati. Riproducibile con questo script lanciato dalla radice del repo:

```python
import random, sys
from collections import defaultdict
from statistics import mean
sys.path.insert(0, "scripts")
from lib import store

FRENO = 5  # come CONTESTO_FRENO_PARTITE in roster.py
players = {p["id"]: p for p in store.load_players()}
cal = [m for m in store.load_json(store.DATA_DIR / "calendario_serie_a.json")
       if m["stato"] == "finished" and m.get("gol_casa") is not None]
sub, fat = defaultdict(dict), defaultdict(dict)
for m in cal:
    c, t, mid = m["squadra_casa"], m["squadra_trasferta"], m["match_id"]
    sub[c][mid], fat[c][mid] = m["gol_trasferta"], m["gol_casa"]
    sub[t][mid], fat[t][mid] = m["gol_casa"], m["gol_trasferta"]
media = mean(g for d in sub.values() for g in d.values())

def fren(d, squadra, senza):  # senza quella partita, frenato verso la media
    g = [x for k, x in d.get(squadra, {}).items() if k != senza]
    return (sum(g) + FRENO * media) / (len(g) + FRENO) - media

per = defaultdict(list)
for r in store.load_matchday_stats():
    if r.get("fantavoto") is not None and r["player_id"] in players:
        per[r["player_id"]].append(r)
rows = defaultdict(list)  # ruolo -> (match_id, scarto, x_subiti, x_fatti)
for pid, rr in per.items():
    if len(rr) < 2:
        continue
    mu = mean(r["fantavoto"] for r in rr)
    for r in rr:
        a = r["opponent_serie_a_team"]
        rows[players[pid]["role"]].append(
            (r["match_id"], r["fantavoto"] - mu, fren(sub, a, r["match_id"]), fren(fat, a, r["match_id"])))

def pendenza(data, i, segno=1):
    xs = [segno * d[i] for d in data]; ys = [d[1] for d in data]
    mx, my = mean(xs), mean(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)

def insieme(data):  # minimi quadrati con i due regressori (fatti col segno invertito)
    x1 = [d[2] for d in data]; x2 = [-d[3] for d in data]; y = [d[1] for d in data]
    m1, m2, my = mean(x1), mean(x2), mean(y)
    a = sum((u - m1) ** 2 for u in x1); c = sum((v - m2) ** 2 for v in x2)
    b = sum((u - m1) * (v - m2) for u, v in zip(x1, x2))
    p = sum((u - m1) * (w - my) for u, w in zip(x1, y)); q = sum((v - m2) * (w - my) for v, w in zip(x2, y))
    det = a * c - b * b
    return (c * p - b * q) / det, (a * q - b * p) / det

def bootstrap(data, f, B=2000, seed=1):  # ricampiona le partite
    rnd, per_partita = random.Random(seed), defaultdict(list)
    for d in data:
        per_partita[d[0]].append(d)
    chiavi = list(per_partita)
    out = sorted(f([d for k in (rnd.choice(chiavi) for _ in chiavi) for d in per_partita[k]]) for _ in range(B))
    return out[int(0.025 * B)], out[int(0.975 * B)]

for nome, ruoli in {"P": "P", "D": "D", "C": "C", "A": "A", "D+C+A": "DCA"}.items():
    data = [d for r_ in ruoli for d in rows[r_]]
    print(nome, len(data),
          "subiti", round(pendenza(data, 2), 2), bootstrap(data, lambda s: pendenza(s, 2)),
          "fatti", round(pendenza(data, 3, -1), 2), bootstrap(data, lambda s: pendenza(s, 3, -1)),
          "insieme", [round(x, 2) for x in insieme(data)],
          bootstrap(data, lambda s: insieme(s)[0]), bootstrap(data, lambda s: insieme(s)[1]))
```

La differenza fatti − subiti dei difensori citata nella sezione 3 ([−0,35, +0,27]) è lo
stesso bootstrap applicato a `pendenza(s, 3, -1) - pendenza(s, 2)`.

Il freno del regressore: nel fit ogni squadra ha 4 partite oltre a quella esclusa, quindi
`fren` vale (4 / (4 + 5)) = 4/9 dello scarto vero. Un β per gol "nudo" è il β del fit per 4/9.

I β attuali del modello (stessi dati) si leggono con
`costruisci_modello(...)["beta"]`: `{'P': 0.452, 'altri': 0.584}`.
