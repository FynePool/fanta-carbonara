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
  Serie A, `quotazione_iniziale` (QI, fissata prima della stagione), `quotazione` (QA,
  si muove coi voti) e `fvm`. Solo la QI è un'informazione a priori pulita: QA e FVM
  contengono le giornate già giocate (vedi difetto 13 del doc dei difetti). Il campo `status` (titolare | dubbio | ballottaggio |
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
  avversaria, casa/trasferta, voto, fantavoto, gol, assist, cartellini, falli, minuti,
  `tiri`, `tiri_porta`, `passaggi_chiave`, `rigori_segnati`, `rigori_sbagliati`,
  `subentrato` (vero se partiva dalla panchina). Le statistiche vengono da BigBalls;
  `voto` e `fantavoto` da fantacalcio.it (`import_voti.py`, voto "Redazione
  Fantacalcio"), `null` se il giocatore è senza voto. Le righe con voto di giocatori
  che BigBalls non ha (42 il 27/09, 17 giocatori) hanno le statistiche a `null` e
  `bigballs: "non_trovato"`. Il box score BigBalls etichetta spesso chi ha cambiato
  squadra con la squadra vecchia o la nazionale (Kean "Fiorentina", Curtis Jones
  "Liverpool"): l'importer li recupera riconciliandoli con i voti di fantacalcio.it
  (vedi `import_matchday_stats.py`). Una riga nuova si scrive solo se nome+squadra
  combaciano con un giocatore della partita in `players.json`; un giocatore di
  un'altra squadra di Serie A finito nel box score sbagliato non passa più (difetto 7
  in `.docs/difetti-consiglio-formazione.md`). I "non riconosciuti" che lo script
  stampa sono soprattutto giocatori assenti dal listone (Primavera, riserve).
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
- `storico_stagioni.json` — le stagioni passate in Serie A di tutti i giocatori (oggi
  2025-26 e 2024-25), da fantacalcio.it (`import_storico_stagioni.py`): per stagione e
  per id del listone, squadra, partite con voto, media voto, fantamedia, gol, gol
  subiti, rigori segnati/calciati/parati, assist, cartellini. Chi quella stagione non
  era in Serie A non c'è (5 dei miei 25 il 27/09). Contesto per il consiglio: **non**
  entra nel valore del modello, perché nel backtest non migliora le previsioni (difetto
  14 del doc dei difetti).
- `notizie_rosa.json` — i fatti delle ultime settimane sulle squadre dei miei giocatori
  (allenatore, infortuni e rientri, titolari, rigoristi, squalifiche, mercato), ognuno
  con i link alle fonti e `verificata` (due fonti indipendenti o fonte ufficiale). Li
  raccoglie con la ricerca web il giro del mattino e li ricontrolla la skill
  `formazione`; `notizie_rosa.py valida` controlla il formato e toglie le notizie
  scadute. Niente pareri, niente voci non confermate spacciate per fatti.
- `calendario_serie_a.json` — calendario e risultati Serie A per giornata (squadra
  casa/trasferta, gol, stato), da BigBalls Sports Data API (vedi script sotto).
  Non contiene dati per giocatore (niente voto/gol/cartellini singoli): solo
  l'esito partita, usato per sapere chi ha giocato contro chi in una giornata.

`config/league.json` contiene le regole di scoring, i moduli ammessi e `my_team_id`
(la mia squadra — da impostare la prima volta che si popolano i dati). Le regole
vengono dal regolamento FantaCarbonara (24/09) e dai chiarimenti della lega, ognuna con
la sua `_fonte`. In `regole_lega`: **nessun modificatore di difesa**, rinvii, scadenza
formazione, penalità, e le regole di panchina confermate dall'utente il 27/09 —
`panchina` (**7 posti a composizione fissa: 1 P, 2 D, 2 C, 2 A**),
`modalita_sostituzioni: pari_ruolo` (la modalità *Traditional* di leghe.fantacalcio.it:
entra sempre il primo panchinaro dello stesso ruolo, il modulo non cambia mai),
`slot_scoperto: 0` (se finiscono le riserve di un ruolo lo slot **non prende voto e vale
0**) e `sostituzioni_max: 7`. C'è anche `soglie_gol` (primo gol a 66, poi ogni 6) ma con
`da_confermare: true`: sono i valori standard di fantacalcio.it, **non** letti dal
pannello della lega, e il report lo dice ogni volta che li usa. In `regole_mercato`: sforamento
(ogni offerta deve lasciare almeno 1 credito per slot ancora vuoto), rimborsi (1 credito
per uno svincolo, il prezzo d'acquisto per una cessione all'estero o in Serie B), asta di
riparazione con +50 crediti, scambi solo a gennaio; `asta.py` non le applica ancora. In
`competizioni` i criteri di parità per la futura fase classifica. I punteggi in
`scoring` non li legge nessuno script (il fantavoto arriva già calcolato dal sito) e
due valori sono `null` perché il regolamento non li chiarisce.

**Dentro un ruolo** va schierato prima chi ha il fantavoto atteso più alto quando prende
voto, anche se gioca poco, perché se non scende in campo entra il primo della panchina di
quel ruolo: la probabilità di giocare non entra nell'ordine (dimostrazione in
`.docs/difetti-consiglio-formazione.md`). **Ma la panchina ha solo 1-2 posti per ruolo e
uno slot scoperto vale 0**, quindi la probabilità conta eccome per decidere *chi* ci va:
una riserva che non gioca mai è un posto buttato. Lo fa `_scegli_panchina` in `roster.py`.
Sceglierci anche il modulo è stato provato e **scartato** perché perde punti: vedi
`.docs/analisi-valutazione-formazione.md`.

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
  Va lanciato dopo `import_matchday_stats.py` (le righe che crea per giocatori non
  abbinati vengono riconciliate col box score al giro dopo). I voti di giocatori assenti dal listone
  vengono stampati e non scritti: 11 sulle prime 5 giornate, giocatori che non sono
  nemmeno nel listone ufficiale di oggi (usciti dalla Serie A o mai listati). Il fantavoto del
  sito usa i bonus standard, non per forza quelli della lega (vedi `scoring`): per
  ordinare i giocatori va bene, per un'eventuale classifica fa fede leghe.fantacalcio.it.
- `import_matchday_stats.py [--ricostruisci]` — box score per giocatore da BigBalls
  (`/v1/stored/matches/{id}/stats`) in `data/matchday_stats.json`: gol, assist,
  cartellini, falli, minuti, tiri, tiri in porta, passaggi chiave, rigori segnati e
  sbagliati, subentrato. **Incrementale**: scarica le partite finite non ancora in
  archivio, quelle con righe senza i campi nuovi (una volta sola) e quelle con righe di
  fantacalcio.it non ancora cercate nel box score (di solito il giorno dopo la partita).
  Il piano free ha 500 chiamate al giorno; `--ricostruisci` le riscarica tutte. Le
  righe già in archivio vengono **arricchite, non riscritte**: si riempiono solo i campi
  vuoti, la giornata si aggiorna dal calendario, `voto`/`fantavoto` non si toccano mai
  (`--ricostruisci` riscrive le statistiche, mai i voti). Non scrive righe nuove di
  giocatori la cui squadra non gioca la partita, e non toglie mai righe già in archivio.
  **Riconciliazione con i voti**: un nome del box score non abbinato (etichetta di
  squadra vecchia, "Del Prato" per "Delprato", entità HTML, UTF-8 rotto) che combacia
  con un giocatore che fantacalcio.it ha già in quella partita gli dà le statistiche;
  non crea righe. Verificata il 27/09: 145 righe recuperate, 130 su 131 coerenti con
  fantavoto − voto. Chi resta fuori è marcato `bigballs: "non_trovato"`.
  Il matching nomi gestisce le abbreviazioni del listone a più lettere ("Martinez
  Jo."), i cognomi doppi ("Kolo Muani") e rifiuta un abbinamento se le iniziali sono
  note e diverse: se listone e BigBalls non concordano sulla squadra di un giocatore
  (es. Sulemana, Törnqvist), la riga non viene attribuita e finisce tra i "non
  riconosciuti".
- `import_storico_stagioni.py [--stagioni 2025-26 2024-25]` — le statistiche di
  stagione di tutti i giocatori della Serie A da fantacalcio.it (pagina "Statistiche
  Serie A", HTML statico, verificata il 27/09: 663 giocatori nella 2025-26, 679 nella
  2024-25) in `storico_stagioni.json`. Abbinamento per id (il link della scheda finisce
  con l'id del listone). Le colonne sono controllate: se cambiano, o i giocatori sono
  meno di 400, non scrive niente. Stagioni finite, quindi si lancia una volta per
  stagione, non nel giro del mattino.
- `notizie_rosa.py {squadre|valida}` — supporto alle notizie: `squadre` stampa le
  squadre dei miei giocatori con la prossima partita (cosa cercare), `valida` controlla
  `notizie_rosa.json` (campi, tipi, fonti, id) e toglie le notizie scadute (30 giorni,
  90 per allenatore e mercato). Non va su internet: le notizie le cerca chi esegue la
  skill.
- `asta.py {assegna|scambio|svincolo|stato|disponibili}` — assistente live per l'asta
  e per il mercato post-asta. **Dopo l'asta le rose le scrive la lega**: quello che
  `asta.py` registra in `teams.json`/`ownership.json` viene sovrascritto dal giro del
  mattino, quindi oggi serve solo a simulare (`stato` e `disponibili` restano utili): registra un acquisto di qualunque squadra, uno scambio
  misto (giocatori + crediti in entrambe le direzioni) tra due squadre, o lo svincolo
  di un giocatore (torna disponibile per tutti); mostra crediti/slot rimanenti per
  ruolo ed elenca i giocatori ancora liberi. Vedi `.claude/skills/asta/SKILL.md`.
- `report_formazione.py --team-id <id> [--matchday N]` — legge lo stato attuale della
  rosa e propone modulo, titolari e **la panchina vera della lega** (7 posti, 1 P, 2 D,
  2 C, 2 A), più i giocatori che restano **fuori distinta** (la logica sta in
  `lib/roster.py`). Dentro ogni ruolo ordina per il **fantavoto atteso se il giocatore
  prende voto**, fatto di due pezzi mostrati in colonna: `voti` (media degli ultimi 5,
  frenata verso la media del ruolo come se avesse 5 partite in più) e `avv` (quanto
  subisce l'avversario della prossima partita rispetto alla media). La colonna `prod`
  non c'è più: la correzione per la produzione è spenta dal 27/09 (vedi
  `PRODUZIONE_PREDEFINITA` in `roster.py`). Ogni pezzo è verificato con
  `backtest_undici.py` in punti veri; a priori dalla quotazione e dalla stagione scorsa,
  titolare/spezzone e casa/trasferta sono stati provati e scartati. La probabilità di
  giocare non entra nell'ordine ma negli avvisi ("se non gioca entra X") e nella scelta
  di chi va in panchina. Stampa anche il **rischio slot vuoto per ruolo**, il
  **punteggio atteso** con la sua conversione in gol secondo `soglie_gol` (serve a
  sapere se una decisione cambia il risultato o no) e l'**avversario di lega** della
  prossima giornata, letto da `lega_competizioni.json`. La sezione "DA COSA È FATTO IL VALORE" spiega
  in una riga titolari e primi due cambi di ogni ruolo; "DECISIONI TUE" elenca le scelte
  entro 0,20 punti (dove nel backtest l'ordine indovina come una moneta), i moduli quasi
  pari e i titolari con dati deboli: lì decidi tu. "STAGIONI PASSATE" mostra per ogni
  giocatore le ultime due stagioni in Serie A (`storico_stagioni.json`), solo come
  contesto. Non si blocca se un ruolo è senza
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
- `backtest_formazione.py [--descrittive]` — prevede ogni giornata dalla 3 in poi con i
  soli dati precedenti e confronta modello del 27/09, nuovo e varianti (MAE, ordine
  giusto dentro la rosa, bootstrap), più la taratura della soglia dei pari e la
  distorsione per numero di voti. Non scrive niente. `--descrittive` stampa i fatti
  citati nel doc dei difetti. Da rilanciare quando ci sono più giornate, prima di
  toccare `roster.py`.
- `backtest_undici.py [--dal N] [--bootstrap N]` — il backtest **dell'undici**, non del
  singolo voto: per ogni giornata dalla 3 in poi e per tutte le 12 rose della lega
  schiera la formazione coi soli dati precedenti, applica le regole (sostituzioni
  illimitate tra pari ruolo, slot scoperto = 0) e somma i punti **veri**. Confronta il
  modello con regole banali (media nuda, fantamedia della stagione scorsa, quotazione
  iniziale, nessun ordine) e con un oracolo che conosce i voti, e ablaziona i pezzi del
  modello in punti. Bootstrap appaiato su (squadra, giornata). Risponde alla domanda che
  `backtest_formazione.py` non pone: quanti punti a giornata vale una modifica. Usa le
  funzioni vere di `roster.py` (`_scegli_panchina`, `_slot_attesi`), non una loro copia,
  passando una probabilità di prendere voto stimata dalle giornate precedenti (quella di
  fantacalcio.it esiste solo dal 21/09 e per queste giornate sarebbe guardare il futuro).
  Il 27/09 il motore valeva **+3,25 punti a giornata** sull'ordine d'acquisto e batteva
  ogni regola semplice; scegliere la panchina con la probabilità vale +0,60 e il termine
  avversario +1,50, entrambi con intervallo che esclude lo zero; la correzione per la
  produzione non guadagna niente ed è stata spenta. Vedi
  `.docs/analisi-valutazione-formazione.md`. **È il collaudo da superare prima di toccare
  `roster.py`**: una modifica entra solo se guadagna punti con l'intervallo che esclude
  lo zero. Non scrive niente.
- Skill `aggiorna-dati` (`.claude/skills/aggiorna-dati/SKILL.md`) — il giro completo
  di aggiornamento dati, nell'ordine giusto, non interattivo, con commit su `main`.
  È quella che esegue la routine del mattino: per aggiungere un dato al giro
  quotidiano si modifica la skill, non la routine.

## Documentazione di riferimento (`.docs/`)

- `.docs/bigballs-api.md` — riferimento dell'API BigBalls (auth, limiti del piano,
  endpoint usati e non ancora usati, convenzioni su `season`/`league`/`round`) con
  le magagne verificate sul campo: box score con etichette di squadra vecchie e
  giocatori estranei, rigori quasi assenti,
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
  tolto dopo la verifica, le correzioni trovate strada facendo. Il 27/09, sui voti
  veri: difetti 9-13, il modello del valore con formula e parametri, il backtest,
  i pezzi scartati e perché, la simulazione rifatta. Da leggere prima di toccare
  `roster.py`, `report_formazione.py` o la pipeline delle probabili formazioni.
- `.docs/analisi-valutazione-formazione.md` — analisi esterna del 27/09 di come il
  progetto valuta la formazione, e gli interventi che ne sono seguiti, con la metrica che
  mancava (`backtest_undici.py`, punti veri invece di MAE). Il fatto che ha ribaltato
  l'analisi: la panchina non è illimitata ma di 7 posti a quota fissa per ruolo, e uno
  slot scoperto vale 0 — quindi la probabilità di prendere voto torna a contare per
  *chi* va in panchina (+0,60 punti a giornata, misurato). Cosa è entrato (panchina vera
  e scelta con la probabilità, portieri della stessa squadra non indipendenti, avvisi di
  copertura, punteggio atteso in gol, avversario di lega), cosa è uscito (la correzione
  per la produzione, con la spiegazione onesta del perché la prova non è significativa) e
  cosa è stato **provato e scartato** (scegliere il modulo col valore atteso: −0,47 punti).
  Contiene anche le critiche da esperto che **non** reggono, misurate (compagni di
  squadra: ρ = 0,07, +4% di σ; stagione scorsa come ordinamento: −3,15 punti), e cosa
  resta aperto (soglie gol da confermare, probabilità di prendere voto approssimata,
  rigoristi). Da leggere insieme al doc dei difetti, prima di toccare `roster.py`.

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

- **Fusione in `main` senza chiedere** (decisione dell'utente, 27/09): una modifica
  finita si porta su `main` con una pull request e la si fonde subito, senza chiedere
  conferma, ma solo dopo averla verificata (script che girano, report e backtest
  rilanciati se toccati, diff riletto). Dopo, si dice all'utente cosa è stato fuso e il
  link della PR. Restano da chiedere prima le operazioni distruttive (riscrivere la
  storia di git, togliere righe dallo storico dei voti, cancellare dati).

- **L'utente sa poco o niente di calcio**: il progetto decide al posto suo. Ogni
  consiglio va motivato in parole semplici, spiegando il gergo; quando una scelta è sua
  (pari del modello, rischi), deve avere tutte le informazioni per capirla: cosa si
  decide, cosa dicono i numeri, cosa dicono le notizie, il consiglio, cosa rischia.
- **Numeri e realtà insieme.** Oltre ai dati della routine vanno considerate le
  notizie vere (allenatori, infortuni, chi gioca, clima della squadra), cercate e
  citate con le fonti. Le informazioni qualitative, anche i pareri che l'utente incolla,
  si verificano prima di usarle; decidono i pari del modello e segnalano rischi, ma non
  ribaltano un distacco netto se non cambiano i fatti di base (non gioca, ruolo
  cambiato). Vedi la skill `formazione`.

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
