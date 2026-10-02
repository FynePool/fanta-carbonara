# Progetti simili: verifica dell'analisi esterna e cosa usare davvero

Analisi del 02/10/2026 del PDF "Fantacalcio + Claude: progetti simili a fanta-carbonara"
(ricerca dello stesso giorno). Il PDF si basava sul README, che non è aggiornato. Qui ogni
sua affermazione è confrontata col codice di `main` (commit `eeb1c07`, 02/10) e con il
codice delle fonti che cita. **Non è stato implementato niente**: l'unico calcolo nuovo è
una misura descrittiva fatta fuori dal repo (appendice A).

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

1. **Il "probabile difetto" principale del PDF è in parte già superato, e la correzione che
   propone non è sostenuta dai nostri dati.** [Certain] I portieri hanno già un coefficiente
   `avv` separato, e la variante "portieri sui gol fatti dall'avversario" è già stata provata
   il 27/09 (indistinguibile, da rifare alla giornata 10). Il README non lo dice, per questo
   il PDF non lo sapeva. Resta vero che i difensori condividono il coefficiente con
   centrocampisti e attaccanti. [Likely] Ma sui nostri 5 turni, per i difensori i gol fatti e
   i gol subiti dall'avversario portano **la stessa quantità** di informazione, e insieme ne
   portano di più: sostituire uno con l'altro, come propone il PDF (copiato da JARVIS), non
   mostra guadagni. Sezione 3.
2. **Due affermazioni marcate [Certain] nel PDF sono sbagliate.** [Certain] "Nessuno invia la
   formazione in automatico" e "fantabot: invio della formazione non costruito": fantabot ha
   documentato e implementato l'invio (`POST /gaming/v1/teamLineup/{division}`, catturato il
   02/09, bloccato da due interruttori). [Certain] "BigBalls è indietro di almeno una
   giornata": non lo è. Fra il 20/09 e il 10/10 non c'è nessuna partita, ed è così in tutti e
   cinque i campionati maggiori (BigBalls: Serie A, Liga, Premier, Ligue 1 e Bundesliga hanno
   tutti l'ultima partita il 20/09 e la prossima il 9-10/10). Anche leghe.fantacalcio.it mette
   la prima giornata della lega sul turno 6 di Serie A, con scadenza il 10/10.
3. **Dei 7 "prossimi passi" del PDF, nessuno è il più utile.** Il resolver di `teamLineup` c'è
   già dal 29/09. La calibrazione della titolarità era già in programma. Asta di riparazione e
   scambi sono a gennaio-febbraio. Le tre cose che servono davvero, nelle fonti ci sono, ma il
   PDF non le mette in evidenza:
   - **l'endpoint delle regole della lega** (`/onboarding/v1/league/settings/calculate`, da
     fantabot): chiuderebbe i due `null` di `scoring` in `config/league.json` (bonus
     rigore parato e porta inviolata) leggendoli dalla lega invece che dal regolamento;
   - **i campi della giornata calcolata di `teamLineup`** (`scr`, `cscr`, `b`, `m`), che
     fantabot e fantaclaude hanno già decodificato su leghe vere il 22/09. Il nostro
     `.docs/leghe-fc-api.md` li dà ancora "da capire alla prima giornata calcolata";
   - **l'archivio di JARVIS: 9 stagioni di voti per partita**, presi dalla stessa pagina di
     fantacalcio.it che legge `import_voti.py`. È il solo modo per stimare con abbastanza dati
     i pezzi piccoli del modello (avversario per ruolo, casa/trasferta), che con 5 giornate
     il backtest non può misurare.
4. **Un problema vero che il PDF non vede, e che arriva la settimana prossima.** [Certain]
   `FORMA_ULTIMI_VOTI = 5` (`scripts/lib/roster.py:44`) non è mai stato provato nel
   backtest: con 5 giornate giocate "gli ultimi 5" erano tutti i voti. Dalla giornata 6 il
   modello comincia a **buttare** i voti più vecchi. [Likely] JARVIS, su 9 stagioni, ha
   misurato che la forma recente non predice e usa una memoria di circa 33 presenze. Va messa
   alla prova prima che la finestra cominci a contare (sezione 4, punto C).
5. **"Su un paio di punti sono avanti a noi" va capito bene.** [Certain] Sul *metodo di
   verifica* non lo sono. Il "+2,2 punti a giornata" di fanta-asta è misurato su dati
   generati dall'autore, e il README lo dice. JARVIS si verifica con la correlazione
   sulle stagioni passate (0,16-0,22), non in punti con le regole della lega. Il nostro
   `backtest_undici.py` è più severo di entrambi. Sono avanti su **dati e conoscenza
   dell'API**, non sul modello.

---

## 1. Le affermazioni del PDF sul nostro progetto, una per una

Verdetti: **Corretta**, **Parziale** (vera ma incompleta o imprecisa), **Superata** (il
progetto lo fa già), **Sbagliata**.

| # | Il PDF dice | Come stanno le cose | Verdetto |
|---|---|---|---|
| 1 | `avv` è lo stesso termine per tutti i ruoli, anche per P e D | `costruisci_modello` stima **due** coefficienti: uno per i portieri, uno per D+C+A insieme (`roster.py:252`, `:257`, `:301`). Il regressore (gol subiti dall'avversario) è lo stesso per tutti. La variante portieri sui gol fatti esiste (`backtest_formazione.py:149`) ed è stata giudicata indistinguibile su 55 previsioni (`.docs/difetti-consiglio-formazione.md`, sezione "Portieri, gol fatti o subiti"). Per i difensori nessuna variante è mai stata provata. Nota a margine: i β citati nel doc (0,40 per D/C/A, 0,45 per P) sono del 27/09, oggi sono 0,58 e 0,45 | **Parziale** |
| 2 | Rischio: alla rimisura `avv` viene scartato "per il motivo sbagliato" | [Likely] Il rischio che `avv` esca "non dimostrato" c'è, ma la causa principale è la potenza (5 giornate, 36 formazioni), non il regressore: la sezione 3 mostra che per i difensori i due regressori si equivalgono | **Parziale** |
| 3 | Classifica: nessun endpoint | Vero. Il report però somma già i punti in classifica dal calendario della lega (`roster.py:417`, `report_formazione.py:384`), e i criteri di parità sono in `config/league.json` → `competizioni` | **Corretta, incompleta** |
| 4 | `teamLineup`: serve un resolver `matchDay` ↔ `championshipMatchDay`, "prima della giornata 6" | Esiste dal 29/09: `giornata_da_controllare` (`controlla_formazione.py:60`) legge i due numeri dal calendario della lega (`lega_competizioni.json`, che li prende così come li dà l'API), e la risposta viene scartata se il `tid` non è il mio (`:122`). Resta un caso limite, sezione 4.B | **Superata** |
| 5 | "La lega ha 33 giornate contro 38" come rischio di disallineamento | La corrispondenza è una per una (Serie A 6-38 = giornate 1-33) e non viene calcolata: si legge dall'API | **Sbagliata** come rischio |
| 6 | `asta.py` non applica le regole di mercato | Vero (`config/league.json` → `regole_mercato`). Ma la riparazione è "a mercato invernale chiuso": non è urgente | **Corretta, non urgente** |
| 7 | Scambi | Solo a gennaio, e per `CLAUDE.md` l'assistente scambi non si fa senza una richiesta esplicita | **Corretta, fuori scopo oggi** |
| 8 | Scontri diretti: manca la probabilità di vittoria | Vero: il report mostra l'avversario di lega e lo scenario dei gol, non la probabilità di vincere. Sul valore vedi sezione 4.F | **Corretta** come mancanza, valore dubbio |
| 9 | Calibrazione della titolarità con `status_scadenze.json` | Già in programma (`CLAUDE.md`: "servirà a misurare quanto `prob_titolare` indovina chi prende voto"). La prima foto è della giornata 6. Il metodo di fantaclaude è utile (4.D) | **Già pianificata** |
| 10 | Modello addestrato "con cancello", come JARVIS | Il nostro cancello è più severo (punti veri, intervallo che esclude lo zero). Quello che ci manca non è il cancello, sono i dati (4.E) | **Parziale** |
| 11 | Due agenti, ricognitore e allenatore, per rendere `verificata` un vincolo | La separazione esiste già dove decide: i numeri li calcola `report_formazione.py`, che non va su internet, e le notizie decidono solo i pari. Il punto debole vero è un altro: in `notizie_rosa.json` una fonte aperta e uno snippet di ricerca hanno lo stesso aspetto (4.G) | **Parziale** |
| 12 | Schede con scadenza, idea per `notizie_rosa.json` | Già fatto: scadenza a 30 giorni, 90 per allenatore e mercato (`notizie_rosa.py:49-50`) | **Superata** |
| 13 | Correzione limitata a ±0,6 di fantavoto per le notizie | La nostra regola è più severa: le notizie non toccano i numeri, decidono i pari e cambiano lo status solo se cambiano i fatti | **Superata** |
| 14 | Dati vecchi meglio di file vuoti, avviso oltre i 4 giorni | Già fatto: soglie che bloccano la scrittura (meno di 400 giocatori, rose vuote, colonne cambiate) e `STATUS_VECCHIO_GIORNI = 4` (`roster.py:12`) | **Superata** |
| 15 | Controlli sullo scraping (squadra giusta, paginazione) | Lo spirito c'è già (le soglie sopra). Paginazione, `networkidle` e banner riguardano Playwright e l'HTML di Leghe, che noi non usiamo: leggiamo l'API | **Superata / non applicabile** |
| 16 | Il fuzzy matching risolverebbe i "non trovati" | Non sono d'accordo: oggi 1 solo giocatore posseduto su 300 è `n/d` (Haps). E il matching è severo apposta, perché "Lautaro Martinez" finiva sul portiere `Martinez Jo.` (vedi `rigoristi.py`). Un abbinamento sbagliato fa più danni di un "non trovato", che almeno si vede | **Sbagliata** come proposta |
| 17 | BigBalls indietro di almeno una giornata | Pausa delle nazionali in tutti i campionati (punto 0.2) | **Sbagliata** |
| 18 | Nessuno invia la formazione; fantabot non l'ha costruito | fantabot sì (punto 0.2) | **Sbagliata** |
| 19 | Il `docs/leghe-api.md` di fantabot risponde 404 | Nel repo al commit `799210e` c'è: 665 righe. [Guessing] Il PDF ha usato un URL sbagliato o una versione vecchia | **Sbagliata** |
| 20 | Cifrare il token a riposo, come fantabot | Non si applica: non salviamo token, il jwt vive solo durante l'esecuzione, e le credenziali arrivano dall'ambiente | **Non applicabile** |
| 21 | Nel registry dei connettori non c'è niente di fantacalcio; BigBalls copre la Serie A dal 2014-15 (4.941 partite) | Verificato il 02/10 | **Corretta** |
| 22 | Rischio termini d'uso di fantacalcio.it | Ragionevole. Oggi facciamo pochi login al giorno, tutti nel giro del mattino (import della lega e controllo della formazione). Non vanno aumentati senza leggere i termini | **Corretta** |

---

## 2. Le fonti, verificate

Solo ciò che conta per noi. "Confermato" vuol dire letto nel codice o nei documenti del repo
al commit indicato sopra.

**fantaclaude** (Mantra). Confermati il server MCP in sola lettura (`get_account`,
`get_league`, `get_league_settings`, `get_my_team`, `list_teams`, `list_competitions`,
`get_server_time`, `get_lineup`) e la rimozione delle email. Il resolver controlla **tutti**
i turni di una competizione che cadono sulla stessa giornata di Serie A
(`mcp/.../calendar.py`): il caso è dichiarato possibile, non osservato. La calibrazione c'è
ed è più completa di come la descrive il PDF (`core/.../analysis/calibration/pstart.py`): fasce
di 10 punti con intervalli di Wilson, Brier score della percentuale pubblicata contro la sola
frequenza di base, ed esito "ha preso voto", non "è partito titolare". È proprio la domanda
che ci serve. Il PDF **non dice** la cosa più utile: il 22/09, su 138 righe delle giornate
3-5, hanno verificato che `scr` è il voto di fantacalcio.it e che `cscr` è il fantavoto della
lega, con due codici per "senza voto" (`scr` 55 e 56, insieme a `cscr` 100)
(`core/.../ingest/match_scores.py`).

**fantabot** (Mantra, licenza MIT). Il suo `docs/leghe-api.md` è il riferimento più completo
che esista sull'API di Leghe, ed è la fonte più utile di tutta la ricerca. Cosa contiene:
- `GET /onboarding/v1/league/settings/calculate`: regole di punteggio (`bnMls`, bonus e malus
  per evento), soglie dei gol (`step`) e sostituzioni (`subst`). Non decodificate, e lo dice;
- `GET /onboarding/v1/league/status`: `mstr` è l'inizio della prima partita, cioè la
  scadenza (verificato contro la giornata 5), e `sto` diventa vero quando la giornata è
  chiusa;
- la giornata calcolata di `teamLineup`: `cscr = scr + Σ b[i]·peso(i) − m` su 454 righe; `b`
  ha 16 contatori, di cui 13 identificati (gol, gol subiti, rigore parato, porta inviolata,
  assist...); `m` è un malus da −1; `lply` resta `null`;
- l'invio della formazione (`POST`), che noi **non** vogliamo usare (sezione 5).

Lo schema del "sentiment" con confidenza zero uguale a "nessuna copertura" è confermato
(`domain/asta/sentiment.py`).

**JARVIS** (Classic con modificatore di difesa). Confermati: `avv` per ruolo (P e D sui gol
fatti dall'avversario, C e A sui gol subiti), stagione precedente mescolata fino alla decima
partita, neopromosse con la media delle retrocesse (`scripts/modello.py`, `contesto()`).
Confermati anche "La sfida, sulla carta", "Com'è andata", il file `.ics`, ntfy e l'avviso
oltre i 4 giorni. Il PDF **non dice** quattro cose che contano più dell'`avv` per ruolo:
- lo storico: `scripts/storico.py` scarica `fantacalcio.it/voti-fantacalcio-serie-a/{stagione}/{giornata}`
  dal 2015-16, la stessa pagina e lo stesso schema di URL di `import_voti.py`. Il modello è
  addestrato su 92.770 righe (2017-18 → 2025-26);
- i coefficienti misurati, per gol a partita dell'avversario: P 0,50, A 0,31, D 0,16, C 0,16.
  Il fattore campo vale tra +0,14 e +0,18 in tutti i ruoli. Annotano che i pesi messi a mano
  prima sopravvalutavano l'avversario (D 0,8 → 0,16);
- "la forma recente è stata misurata e lasciata fuori: non predice" (`STORIA.md`, B2): usano
  una media con decadimento 0,97, circa 33 presenze;
- la probabilità di vittoria è implementata (2.000 simulazioni) con un suggerimento di cambio
  per varianza, e il 15/09 i suggerimenti sono stati **zero**. È l'unico dato reale che
  abbiamo sull'utilità di questa idea.

La loro verifica è una correlazione sulle due stagioni tenute da parte, non punti di lega:
modello contro calcolo di prima P 0,217/0,203, D 0,189/0,131, C 0,197/0,183, A 0,165/0,154.

**fanta-asta** (Classic con modificatore). Confermati `schiera.py` (Monte Carlo a numeri
comuni contro l'avversario), `proposte()` con capitano e vice intoccabili, il bug "501 su 500"
del **loro** ottimizzatore d'asta (`tests/qa_asta.py:208`) e il prezzo massimo come prezzo di
indifferenza. Il PDF non dice due limiti. Il "+2,2 fantapunti a giornata" è misurato su
dati finti, e il README lo dichiara. E il test RED/GREEN della skill di scouting ha dato
"3 su 3 conformi" perché con la skill gli agenti si sono **astenuti** (0 KPI su 8, ricerca
web bloccata): il documento stesso dice che il test copre solo il ramo "web chiuso". Il RED
però è istruttivo: 3 agenti su 3 citavano link mai aperti, e 3 su 3 contavano due volte numeri
già nelle stime.

**fantamagazine**. Confermati gli URL `classifica?id=…&app=true&legacy=true` dentro un
iframe, il controllo sulla paginazione, `domcontentloaded` al posto di `networkidle`, e "3,5
crediti per punto di quotazione". La parte sulle pagine si applica solo a chi legge l'HTML,
non a noi.

**fanta** (armandoferrara86). Confermati tre subagent (`ricognitore`, `statistico`,
`allenatore`), l'ultimo senza strumenti web. Attenzione alla regola dell'allenatore: "un
titolare sicuro da 6 vale più di un fuoriclasse in ballottaggio". È l'opposto di quello che
abbiamo dimostrato (dentro un ruolo si ordina per il valore se prende voto, la panchina
copre). Si può prendere la struttura, non la logica.

**fantanostalgia PR #114**. La loro "ipotesi" riguarda il *voto senza bonus* (`cscr` meno i
bonus positivi), che serve al loro punteggio e a noi no. Il PDF la presenta come un dubbio
su `teamLineup` che ci riguarda: non lo è.

**fantacalcio-nuovo** (`CLAUDE.md` → `MEMORIA.md`), **Fantacalcio-Assistant** (bot Telegram)
e **fantacalcio-py** (indice "Affare") sono confermati. "Il doppio per credito" di
fantacalcio-py è punti divisi per crediti: premia per costruzione chi costa poco, e con
gli slot fissi non dice quale rosa fa più punti.

---

## 3. L'`avv` per ruolo, misurato sui nostri dati

**Cosa si è misurato** (appendice A, fuori dal repo, sola lettura di `data/`). Come fa
`costruisci_modello`: per ogni giocatore con almeno 2 voti, lo scarto di ogni fantavoto dalla
sua media; per ogni partita i gol subiti e i gol fatti dall'avversario **senza quella
partita**, frenati verso la media come se avesse 5 partite in più. Pendenza per ruolo, con
intervallo bootstrap ricampionando le partite. Giornate 1-5, 50 partite.

| Ruolo | n | Solo gol subiti: β [IC 95%] | Solo gol fatti (segno invertito): β [IC 95%] | Insieme: subiti | Insieme: fatti |
|---|---|---|---|---|---|
| P | 96 | +0,45 [−0,34, +1,21] | +0,62 [−0,03, +1,35] | +0,31 [−0,44, +1,06] | +0,53 [−0,08, +1,17] |
| D | 479 | +0,52 [+0,20, +0,81] | +0,49 [+0,18, +0,74] | +0,42 [+0,10, +0,71] | +0,38 [+0,06, +0,64] |
| C | 552 | +0,64 [+0,24, +1,08] | +0,51 [+0,13, +0,94] | +0,54 [+0,16, +0,99] | +0,35 [−0,08, +0,77] |
| A | 260 | +0,59 [−0,11, +1,37] | +0,67 [−0,00, +1,31] | +0,48 [−0,22, +1,25] | +0,58 [−0,10, +1,22] |
| D+C+A (oggi) | 1291 | +0,58 [+0,28, +0,89] | +0,54 [+0,25, +0,82] | +0,48 [+0,19, +0,78] | +0,41 [+0,09, +0,68] |

Fra le 20 squadre, gol fatti e gol subiti delle prime 5 giornate correlano a −0,30: i due
regressori sono diversi davvero, non due misure della stessa cosa.

**Cosa vuol dire** [Likely]:
- per i **difensori**, scambiare i gol subiti coi gol fatti (la proposta del PDF) non cambia
  niente: differenza fatti − subiti [−0,35, +0,27]. Usati insieme contano tutti e due. Se
  qualcosa va provato, è la **forza complessiva** dell'avversario (i due termini insieme, o la
  differenza reti), non lo scambio;
- per i **portieri** i gol fatti sono un po' davanti, come dice il meccanismo (−1 per gol
  subito), ma su 96 voti gli intervalli si sovrappongono quasi del tutto. È lo stesso verdetto
  del 27/09;
- i nostri β (0,45-0,65 per gol) sono 2-4 volte quelli che JARVIS stima su 92.770 righe per C
  e D (0,16). Le scale non sono identiche (loro mescolano la stagione prima, separano casa e
  fuori, e la storia del giocatore entra come regressore), quindi conta solo l'ordine di
  grandezza. [Guessing] Con 5 giornate il nostro coefficiente potrebbe essere gonfiato, e il
  `+0,28` a Frattesi contro il Monza sarebbe troppo;
- **limiti**: misura dentro il campione, non previsione; il bootstrap per partita ignora che
  le partite della stessa giornata si somigliano (intervalli ottimisti, come quelli del
  backtest); non è `backtest_undici.py`, che resta il collaudo.

**Conclusione.** La domanda giusta non è "quale regressore per i difensori" ma "come stimare
un effetto piccolo (±0,2 a partita) con 5 giornate". Con i dati della sola stagione non si
può, né alla giornata 8 né alla 10. Si può con le stagioni passate (4.E).

---

## 4. Cosa usare davvero, in ordine

Per ognuna: cosa, da dove, quando, costo, come si verifica. Niente di questo è stato fatto.

### Priorità 1: prima o subito dopo la giornata 6 (scadenza 10/10, calcolo dopo il 12/10)

**A. Leggere dalla lega le sue regole, invece di ricavarle dal regolamento** [Likely, alto
valore, costo basso]. Da fantabot: `GET /onboarding/v1/league/settings/calculate` e
`GET /onboarding/v1/league/status`, sola lettura, con il client che abbiamo
(`lib/leghe_fc_client.py`).
- chiude i due `null` di `scoring` (`bonus_rigore_parato`, `bonus_porta_inviolata`): in
  fantabot sono le voci `bmpsa` e `bmcsh` di `bnMls`;
- controlla soglie dei gol (66, poi +5), modalità delle sostituzioni e panchina, che oggi
  vengono da un documento e da una conferma a voce;
- `mstr` e `sto` controllano la scadenza che calcoliamo dalle date di BigBalls.

Rischio: fantabot non ha decodificato i nomi dei campi. Si verifica abbinando i valori già
noti (66 e 5 devono comparire in `step`), e si scrive in `.docs/leghe-fc-api.md` solo ciò
che combacia. Il primo passo è guardare la risposta, non scriverla in `config/`.

**B. La giornata calcolata di `teamLineup`: verificarla, poi usarla** [Certain che i campi
esistano su due leghe Mantra; Likely che valgano anche in Classic]. Dopo il 12/10:
1. confrontare `scr` col voto Redazione di `matchday_stats.json` e controllare che `cscr` =
   `scr` + Σ `b`·pesi − `m` coi pesi letti in A. Con due giornate di lega su due tornerebbe il
   fantavoto **della lega**, il blocco 1 della "Classifica" in `CLAUDE.md` (fasi future);
2. la **classifica**: non serve il fantavoto per giocatore, bastano `ptH`/`ptA`/`standingPt*`
   di `lega_competizioni.json` più i criteri di parità di `config/league.json`. Tutti e tre i
   blocchi di `CLAUDE.md` cadono alla prima giornata calcolata. La pagina "legacy" di
   fantamagazine conviene come **controllo a mano una tantum**, non come scraper (login
   Angular, banner, iframe);
3. la **retrospettiva di giornata** (da JARVIS "Com'è andata" e dalla "week" di
   fantaclaude): punti veri della formazione inserita, del consiglio, e della migliore
   possibile con la mia rosa. È il primo confronto col mondo vero sulla **mia** squadra e
   con i punti **della lega**: il backtest usa il fantavoto standard di fantacalcio.it e tutte
   le rose. La formazione inserita la legge già `controlla_formazione.py`.

Caso limite da coprire insieme (da fantaclaude): `giornata_da_controllare` controlla una sola
formazione anche se due competizioni (campionato e, quando arriverà, Coppa Italia) cadono
sulla stessa giornata di Serie A (`controlla_formazione.py:101`). Con `allComp` vero la
formazione è la stessa per tutte; con `allComp` falso la seconda non verrebbe controllata.
[Guessing] Oggi la lega ha una sola competizione: non succede.

### Priorità 2: dalla giornata 8 alla 10

**C. La finestra della forma, prima che cominci a contare** [Certain che non sia mai stata
provata; Likely che una finestra più lunga sia meglio]. `FORMA_ULTIMI_VOTI = 5` dalla
giornata 6 scarta i voti più vecchi. JARVIS, su 9 stagioni, trova che la forma recente non
predice. Da provare in `backtest_undici.py` (5, 10, tutti, decadimento): con 6-7 giornate la
differenza sarà minima e il test non la distinguerà. C'è una tensione con la regola del
progetto: "nessun cambiamento senza un intervallo che escluda lo zero" terrebbe il 5, ma il
5 è una scelta mai provata, che produce effetti solo da adesso. **[Guessing]** La scelta
prudente è non lasciare che una costante mai provata cominci a buttare dati. È una decisione
sul modello, quindi la prende l'utente, non questa analisi.

**D. Calibrare `prob_titolare` col metodo di fantaclaude** [Likely]. Esito "ha preso voto",
fasce di 10 punti con intervallo di Wilson, Brier score della percentuale del sito contro la
sola frequenza di base. Dati: `status_scadenze.json` (dalla giornata 6) più i voti. Verso la
giornata 10, circa 5 turni per 600 giocatori. Serve a due cose che oggi sono stime dichiarate:
la copertura della panchina (il 99% dei portieri) e lo scenario dei gol. Poi la scelta della
panchina va rimisurata con la probabilità tarata.

**E. Stimare i coefficienti piccoli sulle stagioni passate** [Likely, l'intervento con più
valore atteso sul modello]. Avversario per ruolo, casa/trasferta, forza della squadra a inizio
stagione: effetti da ±0,1-0,3 che con 5 giornate nessun backtest vede. Il dato:
- voti per partita 2024-25 e 2025-26 da fantacalcio.it, stessa pagina di `import_voti.py`
  (JARVIS la legge dal 2015-16). [Likely] Il parser andrà adattato: per lo storico delle
  stagioni il link della scheda cambiava fra stagione in corso e passate;
- calendari e risultati di quelle stagioni da BigBalls (`import_calendario_seriea.py --season`,
  coperte dal 2014-15), per sapere l'avversario e il campo;
- non servono i box score: niente consumo delle 500 chiamate al giorno.

Uso: coefficienti fissi (o un punto di partenza) stimati sullo storico; la base del giocatore
resta quella della stagione. Non contraddice il difetto 14 (la stagione scorsa come punto di
partenza **del giocatore** non serve): qui si stimano effetti **di contesto**. Collaudo: le
varianti in `backtest_undici.py`, con la regola di sempre. Varianti da mettere accanto
all'attuale: (a) JARVIS, P e D sui gol fatti; (b) i due termini insieme; (c) coefficienti
stimati sullo storico. Neopromosse con la media delle retrocesse, come JARVIS.

Il casa/trasferta merita una nota a parte: il progetto lo dà "provato e scartato" (−0,006 di
MAE su 3 giornate), mentre JARVIS su 92.770 righe trova +0,14/+0,18. [Likely] Il nostro test
non aveva la potenza per vedere un effetto così piccolo. Anche se è vero, sposterebbe solo
coppie già sotto `SOGLIA_PARI` (0,20): un effetto da pareggi, non da distacchi.

**F. Cosa dice una fonte, e se è stata aperta, nelle notizie** [Likely, costo basso]. Il RED
di fanta-asta (3 su 3 citavano link mai aperti) descrive il rischio della routine del mattino,
che scrive `notizie_rosa.json` senza nessuno che guardi. Oggi `fonti` è una lista di URL, e
non si distingue una pagina letta da uno snippet di ricerca. Proposta più economica dei due
agenti del PDF: per ogni fonte, letta sì/no e ora di lettura; `notizie_rosa.py valida`
rifiuta `verificata: true` se meno di due fonti sono state lette davvero. Poi un test RED
del passo 7 di `aggiorna-dati` con un subagent e la ricerca web bloccata o ridotta: si vede se
scrive comunque `verificata: true`. Esempio di quello che può scappare: la notizia sul Venezia
del 01/10 ha un refuso ("confirma"), indizio di testo riassunto più che letto. [Guessing]

### Priorità 3: dopo, o forse mai

**G. Probabilità di vittoria nello scontro diretto** [Likely: poco valore decisionale].
Servirebbe la varianza di ogni giocatore, che con 5-10 voti è rumore. La correlazione fra
compagni è 0,074 (`.docs/analisi-valutazione-formazione.md`), quindi le leve sulla varianza
sono poche. JARVIS l'ha implementata e il primo giorno ha prodotto zero suggerimenti; fanta-asta
la valida solo su dati finti. Se mai, solo come spareggio dentro "DECISIONI TUE": da sfavorito
il più imprevedibile, da favorito il più regolare. Nota: `teamLineup` dà già la formazione
inserita dall'avversario, prima della scadenza.

**H. Asta di riparazione e scambi** (rigioco con `regole_mercato`, `proposte()` di fanta-asta,
"Mercato, sulla carta" di JARVIS, tasso crediti/quotazione di fantamagazine). Da dicembre, e
solo su richiesta esplicita (`CLAUDE.md`). Il rigioco ha senso solo se c'è un piano d'asta
da collaudare: `asta.py` registra gli acquisti, non fa piani.

**I. Pulizia di documentazione** [Certain che serva]. Il PDF ha sbagliato perché il README è
fermo al 29/09: non dice di `controlla_formazione.py` né del coefficiente separato dei
portieri, e `.docs/difetti-consiglio-formazione.md` riporta β vecchi. Basta una riga nel
README che rimandi a `CLAUDE.md` e `.docs/` come fonte. Separare `CLAUDE.md` (43 KB, caricato
a ogni sessione) in regole e memoria, come Tiri6, è gusto: utile ma non urgente.

---

## 5. Cosa scartare, e perché

| Idea | Perché no |
|---|---|
| Fuzzy matching dei nomi (MCP di FPL) | 1 "non trovato" su 300 posseduti; un abbinamento sbagliato fa più danni di uno mancato. Se i "non trovati" crescono: una tabella di alias scritta a mano, come `kb/rules/aliases.yml` di fantaclaude |
| Invio automatico della formazione (fantabot) | Scrive sul sito con un'API non documentata: errore costoso (0-3 a tavolino o formazione sbagliata) e rischio sui termini d'uso. Il controllo in sola lettura che abbiamo copre il bisogno vero (accorgersi in tempo) |
| Due agenti, ricognitore e allenatore, come architettura | Da noi decide già il codice, che non va su internet. Il rischio rimasto lo copre meglio, e costa meno, il punto 4.F |
| Server MCP di Leghe (fantaclaude) | Abbiamo già client e importer; un MCP aggiunge un modo di accesso, non dati |
| Cifratura del token | Non salviamo token |
| Bot Telegram | La notifica della routine arriva già sul telefono |
| Indice "Affare" | Punti per credito premiano chi costa poco per costruzione; da riguardare solo per la riparazione |
| `.ics` delle scadenze (JARVIS) | Comodo, non migliora le decisioni: la notifica di `controlla_formazione.py` copre il rischio di dimenticarsi |

---

## 6. Limiti di questa analisi

- Ho letto codice e documenti delle fonti, non li ho eseguiti. fantaclaude e fantabot sono
  leghe **Mantra**: il significato dei campi di `teamLineup` e `settings/calculate` va
  riverificato sulla nostra lega Classic (4.A e 4.B lo prevedono).
- La misura della sezione 3 è descrittiva e dentro il campione. Non sostituisce
  `backtest_undici.py` e non autorizza a cambiare `roster.py`.
- I confronti numerici con JARVIS (coefficienti, casa/trasferta) mettono insieme modelli
  costruiti in modo diverso: valgono come ordine di grandezza.
- Non ho controllato i termini d'uso di fantacalcio.it.

## 7. Domande per chi rivede (altri LLM)

1. Sezione 3: la conclusione "lo scambio di regressore per i difensori non è sostenuto; il
   problema è la potenza" regge? C'è un modo più adatto di misurarlo con 5 giornate?
2. 4.C: è giusto trattare `FORMA_ULTIMI_VOTI = 5` come urgente, o con 6-7 giornate
   l'effetto è trascurabile e basta rimisurarlo alla 10?
3. 4.E: stimare i coefficienti di contesto sulle stagioni passate e applicarli a quella in
   corso introduce distorsioni (regole del voto cambiate, squadre diverse) che non ho visto?
4. 4.G: c'è un caso concreto, con 1-2 posti di panchina per ruolo e soglie a 66+5, in cui
   la probabilità di vittoria cambierebbe una scelta oltre `SOGLIA_PARI`?
5. Le affermazioni della sezione 1 marcate "Sbagliata": qualcuna è un mio errore di lettura?

---

## Appendice A: la misura della sezione 3

Eseguita il 02/10 sul commit `eeb1c07`, fuori dal repo, in sola lettura. Riproducibile con
questo script lanciato dalla radice del repo:

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

I β attuali del modello (stessi dati) si leggono con
`costruisci_modello(...)["beta"]`: `{'P': 0.452, 'altri': 0.584}`.
