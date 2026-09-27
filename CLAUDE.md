# Fanta Carbonara

Progetto per gestire una squadra di fantacalcio (lega da 12 squadre, modalità **Classic**,
lega su leghe.fantacalcio.it) e ricevere consigli di formazione, mercato e scambi.

## Stato del progetto

Asta di inizio stagione **conclusa** (settembre 2026; a chiamata classica, 12 squadre,
500 crediti, rose 3P-8D-8C-6A). Priorità attuale: il consiglio di formazione. Rose e
crediti arrivano dalla lega vera su leghe.fantacalcio.it (`import_rose_lega.py`, dal
27/09), che è la fonte: nomi e id delle squadre sono i suoi. L'app usata per l'asta era
un'altra (Fantalab), con altri nomi di squadra: il suo export CSV è servito solo a
verificare le rose importate (identiche, giocatori e prezzi) e non sta nel repo. La mia
squadra è VAR-tificiale (`my_team_id` in `config/league.json`).

I dati (listone, infortuni, calendario, statistiche, voti, probabili formazioni,
squalifiche e status) si aggiornano ogni mattina con una routine automatica che esegue
la skill `aggiorna-dati` e pusha su `main`. Dal 27/09 il giro legge anche rose, crediti,
competizioni e calendario della lega da leghe.fantacalcio.it.

## Struttura dati (`data/`, JSON versionati in git)

- `teams.json` — le squadre in gioco della lega (12, quelle con una rosa): id e nome di
  leghe.fantacalcio.it, crediti totali/rimanenti. Il proprietario non si salva (dato personale).
- `players.json` — **pool completo di tutti i giocatori Serie A** (non solo quelli
  posseduti), dal listone ufficiale di fantacalcio.it (`import_listone_fc.py`): id, nome, ruolo (P/D/C/A), squadra
  Serie A, `quotazione`. Il campo `status` (titolare | dubbio | ballottaggio |
  infortunato | squalificato | panchina | n/d) e `status_updated_at` diventano
  rilevanti solo a stagione iniziata e **vanno aggiornati prima di ogni deadline**
  leggendo le probabili formazioni pubblicate sui siti (fantacalcio.it, SOS Fanta,
  Gazzetta, ecc.). `prob_titolare` è la percentuale di titolarità pubblicata da
  fantacalcio.it (0-100), come numero: serve agli avvisi del report, **non**
  all'ordine dei giocatori.
- `ownership.json` — chi possiede quale giocatore: player_id, team_id (id della squadra
  su leghe.fantacalcio.it), prezzo d'acquisto, data, modalità (asta | da_verificare).
  Riscritto ogni mattina dalla lega: vedi `import_rose_lega.py`.
- `matchday_stats.json` — storico per giornata: player_id, matchday, squadra Serie A
  avversaria, casa/trasferta, voto, fantavoto, gol, assist, cartellini, falli, minuti.
  Gol/assist/cartellini/falli/minuti da BigBalls; `voto` e `fantavoto` da fantacalcio.it
  (`import_voti.py`, voto "Redazione Fantacalcio"), `null` se il giocatore è senza voto.
  Le righe dei giocatori con voto che BigBalls non riconosce (30-60 a giornata) hanno
  le statistiche BigBalls a `null`. L'endpoint BigBalls
  usato mescola nel box score di una partita anche giocatori di squadre estranee
  (altri campionati, nazionali): una riga viene scritta solo se nome+squadra
  combaciano con un giocatore che sappiamo essere davvero in quella squadra di
  Serie A in `players.json`. Questo esclude le squadre di altri campionati, ma
  **non** un giocatore di un'altra squadra di Serie A finito nel box score sbagliato:
  oggi ci sono 3 righe di questo tipo (vedi difetto 7 in
  `.docs/difetti-consiglio-formazione.md`). I "non trovati" (script stampa l'elenco) sono
  in parte questo rumore, in parte veri giocatori mancanti dal listone: da
  ricontrollare quando si rinfresca `players.json`.
- `injuries.json` — storico infortuni: player_id, date, tipo, stato, rientro previsto.
- `squalifiche.json` — squalificati e diffidati attuali da fantacalcio.it (pagina
  "Indisponibili Serie A"): player_id, nome, squadra, `tipo` (squalificato |
  diffidato), nota, data. Riscritto a ogni giro: vale la presenza, come per gli
  infortuni.
- `market_log.json` — log di mercato/scambi: supporta scambi misti (giocatore + crediti).
- `lega_competizioni.json` — le competizioni della lega su leghe.fantacalcio.it e il loro
  calendario testa-a-testa con i risultati (`import_calendario_lega.py`). Per ogni
  competizione: id, nome, tipo, giornate di Serie A di inizio e fine, squadre (id di
  `teams.json`), e per ogni giornata (`giornata` della competizione, `giornata_serie_a`,
  `calcolata`) le partite con squadre, punteggi, punti in classifica e risultato. Il
  27/09 c'era solo il campionato FANTACARBONARA (Serie A 6-38, 33 giornate, ogni
  avversario 3 volte); Coppa Italia ed Europa League entreranno da sole. Una giornata
  calcolata non si perde mai, come lo storico dei voti.
- `calendario_serie_a.json` — calendario e risultati Serie A per giornata (squadra
  casa/trasferta, gol, stato), da BigBalls Sports Data API (vedi script sotto).
  Non contiene dati per giocatore (niente voto/gol/cartellini singoli): solo
  l'esito partita, usato per sapere chi ha giocato contro chi in una giornata.

`config/league.json` contiene le regole di scoring, i moduli ammessi e `my_team_id`
(la mia squadra — da impostare la prima volta che si popolano i dati). Le regole
vengono dal regolamento FantaCarbonara (24/09) e dai chiarimenti della lega, ognuna con
la sua `_fonte`. In `regole_lega`: **nessun modificatore di difesa, sostituzioni
illimitate**, rinvii, scadenza formazione, penalità. In `regole_mercato`: sforamento
(ogni offerta deve lasciare almeno 1 credito per slot ancora vuoto), rimborsi (1 credito
per uno svincolo, il prezzo d'acquisto per una cessione all'estero o in Serie B), asta di
riparazione con +50 crediti, scambi solo a gennaio; `asta.py` non le applica ancora. In
`competizioni` i criteri di parità per la futura fase classifica. I punteggi in
`scoring` non li legge nessuno script (il fantavoto arriva già calcolato dal sito) e
due valori sono `null` perché il regolamento non li chiarisce. Con i cambi illimitati, dentro un ruolo va
schierato prima chi ha la media più alta quando gioca, anche se gioca poco, perché
se non scende in campo entra il primo della panchina: vedi
`.docs/difetti-consiglio-formazione.md`.

## Script (`scripts/`)

- `import_listone.py --csv <file>` — importa il listone ufficiale (export Excel/CSV
  di fantacalcio.it) in `data/players.json`, preservando lo status dei giocatori già
  noti. Da lanciare prima dell'asta.
- `import_listone_fc.py` — il listone ufficiale di fantacalcio.it (pagina "Quotazioni
  Fantacalcio", HTML statico, 598 giocatori il 27/09) in `players.json`: id (lo stesso
  dell'asta e dei voti), nome, ruolo, squadra, quotazione e FVM ufficiali. Di chi è già
  noto tiene status e probabilità. Chi esce dal listone (venduto all'estero) sparisce da
  `players.json` ma non dallo storico. Non scrive niente se legge meno di 400
  giocatori, se trova una squadra fuori dal calendario, o se ne uscirebbero più di 40
  in un colpo (`--accetta-uscite` per un mercato vero). Ordine del file stabile (ruolo,
  squadra, nome) per diff leggibili.
- `import_fantadraft.py` — solo gli infortuni, da FantaDraft (github.com/lucianomurr/
  FantaDraft, fonte pubblica aggregata, aggiornata quotidianamente). Fino al 27/09
  scriveva anche il listone, ma aveva 532 giocatori su 598 (mancavano Leão, Lukaku,
  Di Gregorio...).
- `scrape_formazioni.py` — scrape delle probabili formazioni Serie A da
  fantacalcio.it (HTML statico, verificato scrapeable senza rendering JS).
  Scrive uno snapshot (`data/formazioni_correnti.json`, non versionato) e ne
  accumula lo storico in `data/formazioni_history.json` (versionato), ma solo se è
  diverso dall'ultimo: con un giro al giorno lo storico crescerebbe di ~90 KB anche
  nei giorni in cui le probabili non cambiano.
- `apply_formazioni_status.py [--dry-run]` — applica lo snapshot più recente allo
  `status` dei giocatori in `players.json`, con matching per nome+squadra
  (euristico, non un id condiviso tra fonti: verificare i "non trovati" in output).
  Poi sovrascrive con `infortunato` chiunque compaia in `data/injuries.json`:
  l'infortunio ha l'ultima parola sulle probabili (un infortunato compare spesso
  in panchina nello scrape, ma `roster.py` non lo schiera). Vale la presenza nel
  file, non una data di rientro — quelle sono testo libero e non si interpretano.
  Per questo `injuries.json` va rinfrescato PRIMA con `import_fantadraft.py`, che
  lo riscrive da zero con i soli infortuni ancora in corso: chi è rientrato sparisce
  da solo (verificato: 60 infortuni il 19/9, 50 il 21/9). Se il file non è di oggi
  lo script lo segnala invece di fidarsene.
  Chi non compare nelle probabili passa a `n/d` con una nota ("non trovato nelle
  probabili del <data>"), invece di tenere lo status della volta prima.
  `status_updated_at` è la data delle probabili, non di oggi: se lo scrape fallisce e
  si riapplica uno snapshot vecchio, il dato risulta vecchio (e lo script avvisa).
  Per ultimi applica gli squalificati di `data/squalifiche.json` (status
  `squalificato`); i diffidati restano schierabili e li segnala il report.
  Vedi `.claude/skills/aggiorna-formazioni/SKILL.md`.
- `scrape_squalifiche.py` — squalificati e diffidati dalla pagina "Indisponibili Serie
  A" di fantacalcio.it (HTML statico, una scheda per squadra) in
  `data/squalifiche.json`. La stessa pagina ha anche gli infortunati, ma non vengono
  letti: arrivano già da FantaDraft, e due fonti per lo stesso dato potrebbero non
  concordare. Matching esatto su nome + squadra (stessa convenzione del listone).
  **La lista piena degli squalificati è dedotta**, non vista: il 24/09 erano tutti
  "Nessuno". Lo script controlla la struttura e segnala ogni sezione diversa da quella
  attesa invece di indovinare: alla prima giornata con squalificati veri va guardato
  il suo output.
- `lib/leghe_fc_client.py` — client per l'API privata non ufficiale di
  leghe.fantacalcio.it (`apileague.fantacalcio.it`), portato in Python dal
  codice sorgente reale di @legasanpetrux/leghe-fc-client (MIT, github.com/
  legasanpetrux/leghe-fc-client). Non è un'API pubblica/documentata da
  Fantacalcio.it, solo in lettura, uso a proprio rischio.
  **Verificato end-to-end in questa sessione** con un account e una lega
  di test reali: login con username/password, e lettura di rose+crediti
  (`/league/teams/all`) e listone della lega (`/league/players`). Punto
  critico: il payload di login contiene due jwt diversi (uno d'account,
  uno specifico per lega); solo quello di lega funziona per le chiamate
  autenticate — usare sempre `get_league_jwt()`, mai `data['jwt']` diretto.
  Credenziali sempre da variabili d'ambiente `LEGHE_FC_USERNAME`/
  `LEGHE_FC_PASSWORD`, mai in chat o committate.
- `leghe_fc_inspect.py {leghe|rose|listone} [--league-id ID]` — CLI di sola
  lettura per esplorare una lega reale via l'API sopra. Non scrive mai in `data/`.
- `import_rose_lega.py --league-id <id> [--verifica-csv file] [--dry-run]` — rose e
  crediti della lega (`/league/teams/all`) in `teams.json` e `ownership.json`. La lega
  FantaCarbonaraXI (`league_id` in config) ha 18 squadre di cui 6 vuote (ragazzi che
  quest'anno non giocano): entra ogni squadra con almeno un giocatore, quindi una
  squadra vuota che prende dei giocatori entra da sola (e viene segnalata). Se una
  squadra già in `teams.json` risulta vuota o sparita non scrive niente (il 27/09, mentre
  l'admin spostava la rosa di Fortitudo sulla squadra Ss Igari, l'API ha restituito per
  qualche secondo quasi tutte le rose vuote): un'uscita vera si accetta a mano con
  `--accetta-squadre-uscite`, e i giocatori spostati tengono data e modalità d'acquisto.
  I crediti si scrivono come li dà la lega, senza controlli: Ss Igari ne ha 554 totali
  invece di 500, e per decisione dell'utente (27/09) non importa, contano rose e voti. Crediti totali =
  `cri` + `bm` (554 - 54 = 500). Non salva il proprietario (è lo username, dato
  personale). Chi entra in una rosa dopo il primo import è `da_verificare`: l'API non
  dice se è uno svincolato o uno scambio. `--verifica-csv` confronta con un export
  dell'asta.
- `import_calendario_lega.py --league-id <id> [--dry-run]` — competizioni
  (`/league/competitions`) e calendari (`/league/competition/calendar/<id>`) della lega in
  `lega_competizioni.json`. Una giornata già calcolata non viene mai sostituita da una non
  calcolata; una ricalcolata dalla lega viene aggiornata e segnalata; competizioni e
  giornate sparite dall'API restano in archivio. Non esiste un endpoint della classifica.
- `import_calendario_seriea.py --season <anno> [--status ...]` — importa calendario
  e risultati Serie A da BigBalls Sports Data API (bigballsdata.com) in
  `data/calendario_serie_a.json`. Fonte verificata in questa sessione: copre Serie A
  dal 2014-15 a oggi, con giornata ("round") e risultato, ma **non** statistiche per
  giocatore né il voto fantacalcio (quello resta da verificare via l'API di
  leghe.fantacalcio.it, endpoint `/gaming/v1/teamLineup`, non ancora testato — serve
  una lega reale con competizione collegata). Richiede `BIGBALLS_API_KEY` da
  ambiente. Le partite finite da pochissimo possono avere giornata nulla per
  ritardo della fonte: mai stimata, va verificata a mano al prossimo refresh.
  Merge idempotente sullo storico esistente (aggiorna per `match_id`, non duplica).
- `import_voti.py [--giornata N]` — voto e fantavoto per giocatore da fantacalcio.it
  (pagina "Voti Fantacalcio Serie A", HTML statico, verificata il 27/09 sulle giornate
  1-5) in `data/matchday_stats.json`. Il sito pubblica tre voti (Redazione, Statistico,
  Italia): la lega usa **Redazione**, `fonte_voti` in `config/league.json`. Abbinamento
  **per id**: il link di ogni giocatore finisce con l'id fantacalcio, lo stesso del
  listone (`fd<id>`). "55" sulla pagina è senza voto (un 6 grigio a video): si scrive
  `null`. Solo partite finite nel calendario (durante la giornata i voti sono
  provvisori), e i voti vengono sempre riscritti perché il sito li può correggere.
  Va lanciato dopo `import_matchday_stats.py`. I voti di giocatori assenti dal listone
  vengono stampati e non scritti: 11 sulle prime 5 giornate, giocatori che non sono
  nemmeno nel listone ufficiale di oggi (usciti dalla Serie A o mai listati). Il fantavoto del
  sito usa i bonus standard, non per forza quelli della lega (vedi `scoring`): per
  ordinare i giocatori va bene, per un'eventuale classifica fa fede leghe.fantacalcio.it.
- `import_matchday_stats.py [--ricostruisci]` — box score per giocatore da BigBalls
  (`/v1/stored/matches/{id}/stats`) in `data/matchday_stats.json`. **Incrementale**:
  scarica solo le partite finite non ancora in archivio (il piano free ha 500
  chiamate al giorno; `--ricostruisci` le riscarica tutte). Aggiorna la giornata
  delle righe esistenti dal calendario, e non sovrascrive mai `voto`/`fantavoto` già
  presenti. Non scrive righe di giocatori la cui squadra non gioca la partita (box
  score contaminato), ma non toglie mai righe già in archivio.
  Il matching nomi gestisce le abbreviazioni del listone a più lettere ("Martinez
  Jo."), i cognomi doppi ("Kolo Muani") e rifiuta un abbinamento se le iniziali sono
  note e diverse: se listone e BigBalls non concordano sulla squadra di un giocatore
  (es. Sulemana, Törnqvist), la riga non viene attribuita e finisce tra i "non
  riconosciuti".
- `asta.py {assegna|scambio|svincolo|stato|disponibili}` — assistente live per l'asta
  e per il mercato post-asta. **Dopo l'asta le rose le scrive la lega**: quello che
  `asta.py` registra in `teams.json`/`ownership.json` viene sovrascritto dal giro del
  mattino, quindi oggi serve solo a simulare (`stato` e `disponibili` restano utili): registra un acquisto di qualunque squadra, uno scambio
  misto (giocatori + crediti in entrambe le direzioni) tra due squadre, o lo svincolo
  di un giocatore (torna disponibile per tutti); mostra crediti/slot rimanenti per
  ruolo ed elenca i giocatori ancora liberi. Vedi `.claude/skills/asta/SKILL.md`.
- `report_formazione.py --team-id <id> [--matchday N]` — legge lo stato attuale della
  rosa e propone modulo, titolari e panchina **ordinata** (la logica sta in
  `lib/roster.py`). Dentro ogni ruolo ordina per media quando il giocatore gioca
  (ultimi 5 voti), avvicinata alla media del ruolo se i voti sono pochi; la
  probabilità di giocare non entra nell'ordine ma negli avvisi ("se non gioca entra
  X"). Stampa per ognuno "media X su N voti". Non si blocca se un ruolo è senza
  dati: lascia lo slot a te col motivo. Segnala i giocatori di `ownership.json`
  spariti dal listone. Per ogni giocatore mostra la prossima partita della sua
  squadra (avversario, casa/trasferta, data), ricavata dalle date del calendario
  senza inventare numeri di giornata: le prime 10 partite non giocate sono il
  prossimo turno se coprono le 20 squadre una volta ciascuna. In quel caso applica la
  regola della lega sui rinvii, che vale per giornata: fino a 3 partite rinviate i loro
  giocatori valgono 6 politico nell'ordine; oltre 3 restano con la loro media (voto del
  recupero). Nessun rinviato viene escluso; se i rinvii sono 3 avvisa che uno in più
  cambia la regola. Stampa anche la scadenza della formazione (inizio della prima
  partita non rinviata del turno). Se il turno non è ricostruibile (recupero, turno già
  iniziato) avvisa e non applica niente di tutto questo. Avvisa anche per i titolari
  assenti dalle probabili, per gli status più vecchi di 4 giorni e per i titolari
  diffidati. `--matchday` è solo l'etichetta del titolo.
- Skill `aggiorna-dati` (`.claude/skills/aggiorna-dati/SKILL.md`) — il giro completo
  di aggiornamento dati, nell'ordine giusto, non interattivo, con commit su `main`.
  È quella che esegue la routine del mattino: per aggiungere un dato al giro
  quotidiano si modifica la skill, non la routine.

## Documentazione di riferimento (`.docs/`)

- `.docs/bigballs-api.md` — riferimento dell'API BigBalls (auth, limiti del piano,
  endpoint usati e non ancora usati, convenzioni su `season`/`league`/`round`) con
  le magagne verificate sul campo: box score contaminato da squadre estranee,
  eventi duplicati, `rating` che non è il voto fantacalcio, `round` assegnato solo
  dopo la partita (in ritardo di circa un giorno, e vuoto su tutte le partite
  future), note di piano nello spec non affidabili. Da leggere prima di toccare
  gli importer o di aggiungere endpoint.
- `.docs/leghe-fc-api.md` — riferimento dell'API di leghe.fantacalcio.it verificato sulla
  lega vera: autenticazione (i due jwt), campi di rose, competizioni e calendario, le
  squadre vuote, i crediti `cri + bm`, lo svuotamento temporaneo delle rose durante le
  modifiche dell'admin, cosa non esiste (classifica) e cosa resta da vedere alla prima
  giornata calcolata (`teamLineup`, significato di `result`). Da leggere prima di toccare
  gli importer della lega.
- `.docs/difetti-consiglio-formazione.md` — revisione avversariale della catena
  `data/` → `roster.py` → `report_formazione.py`, ricontrollata il 24/09 sul codice
  di `main` e con le regole vere della lega: 8 difetti riprodotti con comando e
  output, tutti risolti il 24/09 (fasi A, B, C e squalifiche), l'elenco di ciò che è stato
  tolto dopo la verifica, le correzioni trovate strada facendo e cosa resta da
  ritarare quando arriveranno i voti. Da leggere prima di toccare
  `roster.py`, `report_formazione.py` o la pipeline delle probabili formazioni.

## Fasi future (non ancora implementate, richieste esplicitamente)

- **Classifica e storico vittorie/sconfitte della lega fantacalcio**: per ogni
  giornata, punteggio totale di ciascuna delle 12 squadre (somma fantavoto
  titolari + eventuale modificatore, da chiarire se la lega ne usa uno oltre
  ai bonus/malus già inclusi nel fantavoto), confronto testa-a-testa e
  classifica. Bloccata su tre cose che non esistono ancora, non solo sul voto:
  1. il fantavoto calcolato con le regole della lega (oggi c'è quello standard di
     fantacalcio.it, vedi `import_voti.py`; quello della lega sta su leghe.fantacalcio.it);
  2. ~~il calendario testa-a-testa della lega~~: importato dal 27/09
     (`lega_competizioni.json`), con i punteggi calcolati dalla lega a ogni giornata:
     la classifica si ricava da lì (non c'è un endpoint);
  3. ~~`ownership.json` popolato~~: fatto il 27/09 dalla lega.
  Da riprendere quando tutti e tre esistono, non prima.

## Regole per chi lavora su questo repo

- **Lo storico non si accorcia mai.** `data/matchday_stats.json` si scrive solo con
  `store.save_matchday_stats`, che si rifiuta se una riga (giocatore, partita) già
  presente sparirebbe: i voti vecchi possono non essere più recuperabili dalle fonti, e
  un giocatore uscito dal listone o passato a un'altra squadra resta nello storico.
  Pulire righe sbagliate è un'operazione a mano, voluta e committata a parte.

- Non inventare mai un voto, uno status o un dato storico mancante: se manca,
  va segnalato come "da verificare a mano", mai stimato silenziosamente.
- Il campione per lo storico contro un singolo avversario è quasi sempre piccolo
  (1-2 incontri a stagione): trattarlo come indizio debole, non come dato solido.
- Le fasi successive del progetto (storico avversari, assistente asta/scambi
  completo) sono descritte
  nella conversazione di progetto e non ancora implementate: non aggiungerle
  senza che siano state esplicitamente richieste.
- Mai committare credenziali, jwt, token o dati personali reali (email,
  username) in nessun file del repo. Le variabili sensibili sono
  `LEGHE_FC_USERNAME`/`LEGHE_FC_PASSWORD` e `BIGBALLS_API_KEY`, sempre da
  ambiente, mai incollate in chat (se càpita, vanno considerate compromesse
  e rigenerate sul sito del provider, non solo tenute com'erano).
