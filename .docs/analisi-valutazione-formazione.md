# Come il progetto valuta la formazione — analisi e interventi (27/09/2026)

Revisione esterna della catena che produce l'undici (`data/` → `scripts/lib/roster.py` →
`scripts/report_formazione.py`), e gli interventi che ne sono seguiti. Ogni affermazione è
stata rieseguita sul codice e sui dati del repo.

Marcatori come negli altri doc: **[Certo]** eseguito e visto · **[Probabile]** inferenza
forte · **[Ipotesi]** sto colmando un vuoto.

---

## Il fatto che ha ribaltato l'analisi

La prima stesura di questa revisione dava per buono quello che diceva
`config/league.json`: **sostituzioni illimitate**. Con quell'ipotesi la panchina è lunga,
la probabilità di giocare non conta mai, e tutto il motore è coerente.

**Non è così.** La regola vera, confermata dall'utente il 27/09: **la panchina è di 7
giocatori a composizione fissa — 1 P, 2 D, 2 C, 2 A — entra sempre il primo dello stesso
ruolo, e se finiscono le riserve di quel ruolo lo slot non prende voto e vale 0.**

Cambia tre cose:

1. Il report **stampava 14 panchinari** come se andassero tutti in distinta. Ne entrano 7,
   e non a scelta libera: 1 per ruolo più 2 per D, C, A.
2. La probabilità di prendere voto **torna a contare**, non nell'ordine dentro un ruolo
   (lì resta dimostrato che non conta) ma nella scelta di **chi** occupa i pochi posti in
   panchina. Il doc dei difetti lo aveva scritto in una riga il 24/09 — «con una panchina
   corta, per gli ultimi posti conta anche la probabilità di giocare» — e nessuno l'aveva
   raccolta perché si credeva la panchina illimitata.
3. Esiste un modo nuovo di perdere punti che non era misurato: **lo slot vuoto**. Nel
   backtest succede 6 volte su 396 slot, cioè **circa 1 punto a giornata buttato**. **[Certo]**

Tutti i numeri di questo doc sono misurati con la regola vera.

---

## La metrica che mancava

`backtest_formazione.py` misura l'errore sul fantavoto di un singolo giocatore (MAE) e
quante volte mette in ordine giusto due giocatori della stessa rosa. Nessuna delle due
risponde alla domanda che conta: **quanti punti a giornata guadagna la formazione
consigliata?** Un modello può prevedere meglio ogni voto e schierare lo stesso undici: in
quel caso non vale niente.

`scripts/backtest_undici.py` la misura. Per ogni giornata dalla 3 alla 5 e per **ognuna
delle 12 rose della lega** schiera coi soli dati precedenti, applica le regole vere
(panchina 1P/2D/2C/2A, cambi solo tra pari ruolo, slot scoperto = 0) e somma i punti veri.
36 formazioni, bootstrap appaiato su (squadra, giornata). Chiama le funzioni vere di
`roster.py`, non una loro copia. **[Certo]**

```
regola di valore                    punti    min    max   contro il modello, IC 95%
modello attuale                     72.32   56.5   86.0   (riferimento)
media nuda dei voti                 70.89   56.5   85.5   -1.43 [-2.42,-0.49] peggio
fantamedia stagione scorsa          69.17   52.5   84.0   -3.15 [-4.97,-1.47] peggio
quotazione iniziale                 70.10   53.5   80.0   -2.22 [-3.99,-0.44] peggio
nessun ordine (ordine d'acquisto)   69.07   49.5   87.5   -3.25 [-5.21,-1.31] peggio
ORACOLO (sa i voti veri)            78.18   67.0   92.5   +5.86 [+4.69,+7.15] MEGLIO
```

**Il motore vale +3,25 punti a giornata** rispetto a schierare la rosa senza pensarci, e
batte ogni regola semplice provata, tutte con intervalli che escludono lo zero. Con le
soglie gol standard (primo gol a 66, poi ogni 6) sono **circa mezzo gol a giornata**: su 33
giornate, 15-18 gol. Un oracolo che conoscesse i voti farebbe +5,86, quindi il motore
prende **il 36% di ciò che c'è da prendere**; il resto è caso e non si recupera.

> Trappola in cui sono cascato per primo: sulla sola rosa mia (3 formazioni) la fantamedia
> della stagione scorsa sembrava *battere* il modello di 0,17 punti. Su 36 formazioni perde
> di 3,15. **Sotto i 3-4 punti, con 3 osservazioni, è tutto rumore.** **[Certo]**

---

## Cosa è stato cambiato, e perché

Regola di accettazione applicata a me stesso: **entra solo ciò che guadagna punti**. Due
cose che avevo scritto sono state buttate perché non lo facevano.

### Entrato: la panchina vera, tagliata e scelta con la probabilità

`config/league.json → regole_lega` ora contiene `panchina` (1P/2D/2C/2A),
`modalita_sostituzioni: pari_ruolo`, `slot_scoperto: 0`, `sostituzioni_max: 7`.

`roster.py` taglia la panchina ai posti veri e sceglie **chi** ci va massimizzando il
valore atteso degli slot (`_scegli_panchina`, `_slot_attesi`): una riserva che non gioca
mai è un posto buttato. I titolari restano i primi per valore, dove la probabilità non
c'entra.

**Misurato: +0,60 [+0,03, +1,32] punti a giornata** rispetto a riempire la panchina coi
successivi per valore. Intervallo che esclude lo zero. **[Certo]**

### Entrato: due portieri della stessa squadra non sono indipendenti

I tuoi tre portieri sono **tutti dell'Inter**. Trattandoli come indipendenti il motore
stimava il 90,5% di copertura e consigliava di cambiare Provedel perché «gioca solo al 5%».
Sbagliato due volte: di portieri dell'Inter ne gioca esattamente uno, quindi la copertura è
90% + 5% = **95%**, e Provedel è proprio la riserva giusta — se non gioca Martinez, gioca
lui. `_slot_attesi` ora tratta i portieri della stessa squadra come gruppo a scelta unica.
Per i giocatori di movimento non vale: tre centrocampisti della stessa squadra possono
partire tutti e tre. **[Certo]**

### Entrato: gli avvisi che prima non c'erano

- **Rischio slot vuoto per ruolo**, con la probabilità di copertura. Oggi: P 95,0%, A 95,4%,
  C 97,2%, D 97,2%.
- **Fuori distinta**: i 7 giocatori della rosa che non entrano né in campo né in panchina.
- **Punteggio atteso** e sua conversione in gol con le soglie: oggi 70,7 punti = 1 gol, e
  per il secondo ne servono 72, cioè +1,3. Serve a sapere **se una decisione cambia il
  risultato**: sotto +1,3 punti, oggi, non lo cambia.
- **Avversario di lega**, letto da `lega_competizioni.json` che prima nessuno leggeva:
  alla prossima giornata giochi in trasferta contro **BORUSSIA LABELLA** (giornata 1 di
  lega = Serie A 6).

### Uscita: la correzione per la produzione

Sostituiva i gol su azione con quelli attesi dai tiri in porta. Era la macchina più
elaborata del codice e produceva i numeri più grossi del report: **+0,62 su Zaccagni, −0,64
su Frattesi** che di gol ne aveva segnati 3.

**La decisione non si appoggia a un risultato significativo, e va detto.** Riaccenderla
vale −0,69 [−1,67, +0,39]: il test non distingue. Si appoggia a tre cose insieme:

1. tre misure indipendenti (panchina illimitata, panchina vera, e con una soglia sui tiri)
   danno tutte un punto stimato a favore dello spegnerla, nessuna del contrario; **[Certo]**
2. il meccanismo: in 5 giornate i tiri in porta accumulati sono in **mediana 0 per i
   difensori, 1 per i centrocampisti, 2 per gli attaccanti** — da 1-2 tiri i gol attesi sono
   rumore, e la correzione assume per giunta che nessuno sia più bravo a segnare degli altri
   del suo ruolo; **[Certo]**
3. falsa precisione: due decimali su un numero inaffidabile, mostrati a chi non può
   giudicarlo. Costa fiducia anche quando non costa punti.

Il parametro `produzione` resta e `backtest_undici.py` lo riprova a ogni giro: si riaccende
solo se con più giornate guadagna punti con l'intervallo che esclude lo zero.
(«Produzione a metà peso» è invece **peggio** del motore attuale: −0,54 [−1,21, −0,01].)

### Provata e SCARTATA: scegliere il modulo col valore atteso

Sarebbe l'obiettivo giusto — il valore atteso sconta chi non prende voto e gli slot che
restano vuoti, la somma dei valori dei titolari no. **Misurato: −0,47 [−1,26, +0,32], cioè
perde.** **[Certo]**

Il motivo è onesto e sta nel dato: il valore atteso dipende dalla probabilità di prendere
voto, e l'unica che abbiamo (`prob_titolare`) è la probabilità di **partire titolare**,
cioè un pavimento — chi entra a partita in corso prende voto lo stesso (129 voti con meno
di 25 minuti nelle giornate 1-5, minimo 2 minuti). Sottostimando la probabilità si
puniscono troppo i moduli con più titolari in un ruolo.

Quindi il modulo resta scelto sulla somma dei valori dei titolari, e il valore atteso serve
solo agli avvisi e al punteggio atteso, dove essere prudenti è un bene e non decide niente.
**Da riprovare quando la probabilità di prendere voto sarà misurata invece che
approssimata**: dalla giornata 6 esistono insieme le probabili (dal 21/09) e le giornate
giocate, quindi diventa misurabile.

---

## Punti forti, verificati

1. **Il criterio di fondo è quello giusto.** Dentro un ruolo, ordinare per «fantavoto
   atteso se prende voto» e ignorare la probabilità di giocare è dimostrabilmente ottimo:
   scambiando due giocatori vicini la differenza vale `P(A)·P(B)·(valore A − valore B)`.
   È controintuitivo, è corretto, e quasi nessun consiglio di fantacalcio in giro lo fa.
2. **Il freno sulle medie (shrinkage) è dove stanno i punti.** La cosa più semplice del
   modello è quella che rende: la media degli ultimi voti avvicinata alla media del ruolo
   quando i voti sono pochi. Il valore esatto del freno non conta (3 o 10 invece di 5:
   indistinguibili).
3. **Il termine sull'avversario adesso è significativo**: toglierlo costa −1,50 [−2,74,
   −0,35]. Ed è stimato con cura — sugli scarti di ogni giocatore dalla sua media, e con i
   gol subiti dall'avversario calcolati escludendo quella partita, le due precauzioni che
   quasi tutti dimenticano.
4. **L'onestà sui dati.** Il report dice su quanti voti si basa ogni numero, dichiara
   quando è una moneta (sotto 0,20 di distacco indovina il 52-55%), e non inventa mai un
   dato mancante. Per chi non sa di calcio vale più della precisione.
5. **Le regole della lega sono nel codice**, non nella testa di qualcuno, ognuna con la sua
   `_fonte`: rinvii, scadenza, squalificati, diffidati, nessun modificatore di difesa, e ora
   panchina e sostituzioni.

---

## Cosa resta aperto

1. **Le soglie gol non sono confermate.** `regole_lega.soglie_gol` ha i valori standard
   (66, poi ogni 6) con `da_confermare: true`, e il report lo dice ogni volta. Vanno lette
   nel pannello della lega. Non cambiano la formazione, cambiano solo il giudizio su
   quanto una decisione conti.
2. **La probabilità di prendere voto è approssimata** con quella di partire titolare. Dalla
   giornata 6 diventa misurabile (probabili dal 21/09 + giornate giocate). Quando lo sarà,
   va rifatto il confronto sul modulo (sopra).
3. **I rigoristi.** Un rigorista designato vale +0,5/+0,75 di fantavoto atteso
   **[Probabile]**: il singolo fattore più grande di tutti quelli discussi qui. Il box score
   BigBalls ha 5 rigori in 50 partite, troppo pochi per dedurlo **[Certo]**; la pagina
   «rigoristi» di fantacalcio.it non è mai stata letta. È l'unico dato mancante che vale la
   pena andare a prendere.
4. **Metà delle statistiche raccolte non entra nel modello**: `passaggi_chiave` (2044
   righe), `assist`, `cartellini_gialli` (154), `falli_commessi` (720), `minuti`. **La
   previsione è che modellarli non pagherà**, ed è la stessa idea della correzione per la
   produzione — sostituire l'evento realizzato con quello atteso — che misurata non vale
   niente con questo campione. Non è una cosa da fare: è una cosa da **non** fare finché
   `backtest_undici.py` non mostra che paga. **[Probabile]**
5. **Portieri, regressore sbagliato**: il contesto usa i gol *subiti* dall'avversario anche
   per i portieri, dove il meccanismo giusto sono i gol *fatti*. Provato: indistinguibile su
   55 previsioni. Da riguardare alla giornata 10. Impatto quasi nullo (di solito un solo
   portiere in rosa ha voti).
6. **Bonus porta inviolata e rigore parato sono `null` in config** perché il regolamento non
   li chiarisce (lo standard è +1 e +3). Il modello usa il fantavoto già calcolato da
   fantacalcio.it coi bonus standard: se la lega usa valori diversi i portieri sono
   sistematicamente sbagliati. Impatto: solo l'ordine fra i tuoi portieri.

---

## Critiche che ho provato e che NON reggono

Sono quelle che un esperto di fantacalcio direbbe per prime.

- **«Sei titolari da due sole squadre sono un rischio.»** Correlazione fra i fantavoti di
  due compagni nella stessa partita, sugli scarti dalle medie individuali: **ρ = 0,074 su
  7.260 coppie**. La σ del totale passa da 4,38 a 4,56: **+4%**. Trascurabile. **[Certo]**
  Il fantavoto dipende molto più dalla prestazione individuale che dal risultato di squadra.
- **«Il fattore campo va aggiunto.»** È l'effetto più solido del calcio, ma sul fantavoto
  individuale il backtest lo trova negativo. **[Probabile]** Si scarica sul risultato, non
  sui voti singoli, ed è in parte già dentro il termine avversario.
- **«La stagione scorsa deve entrare nel modello.»** Provata come punto di partenza del
  freno (niente) e come regola di ordinamento a sé: **−3,15 punti**. **[Certo]** Come
  contesto stampato va benissimo dov'è.
- **«Un giocatore che entra al 70' non prende voto.»** Falso: 129 voti con meno di 25
  minuti, minimo 2. **[Certo]**
- **«Il 3-4-3 è scelto per principio.»** No, è la somma dei valori. Che vincano spesso i
  moduli con più centrocampisti e attaccanti è **corretto**: senza modificatore di difesa un
  attaccante medio (6,83) rende più di un difensore medio (6,04). **[Certo]**

---

## Riprodurre

Non scrivono niente.

```bash
python3 scripts/backtest_undici.py                    # punti veri, varianti, ablazione
python3 scripts/report_formazione.py --team-id 20598917
python3 scripts/backtest_formazione.py --descrittive
```

Correlazione fra compagni di squadra e σ del totale:

```bash
python3 - <<'EOF'
import json, statistics as st
from collections import defaultdict
righe = json.load(open('data/matchday_stats.json'))
players = {p['id']: p for p in json.load(open('data/players.json'))}
voti = [r for r in righe if r.get('fantavoto') is not None and r['player_id'] in players]
m = defaultdict(list)
for r in voti:
    m[r['player_id']].append(r['fantavoto'])
m = {k: st.mean(v) for k, v in m.items() if len(v) >= 3}
sigma = st.pstdev([r['fantavoto'] - m[r['player_id']] for r in voti if r['player_id'] in m])
part = defaultdict(lambda: defaultdict(list))
for r in voti:
    if r['player_id'] in m:
        part[r['match_id']][players[r['player_id']]['serie_a_team']].append(r['fantavoto'] - m[r['player_id']])
xs, ys = [], []
for d in part.values():
    for s in d.values():
        for i in range(len(s)):
            for j in range(i + 1, len(s)):
                xs += [s[i], s[j]]; ys += [s[j], s[i]]
mx, my = st.mean(xs), st.mean(ys)
rho = (sum((a-mx)*(b-my) for a, b in zip(xs, ys))
       / (sum((a-mx)**2 for a in xs) * sum((b-my)**2 for b in ys)) ** 0.5)
print(f'sigma dentro il giocatore {sigma:.2f}, rho tra compagni {rho:.3f} su {len(xs)//2} coppie')
for gruppi, nome in (([[1]]*11, 'indipendenti'), ([[1,1,1],[1,1,1],[1],[1],[1],[1],[1]], 'club veri')):
    var = sum(len(g)*sigma**2 + len(g)*(len(g)-1)*rho*sigma**2 for g in gruppi)
    print(f'  sigma del totale, {nome}: {var**0.5:.2f}')
EOF
```

Tiri in porta accumulati in 5 giornate (perché la correzione produzione è spenta):

```bash
python3 - <<'EOF'
import json, statistics as st
from collections import defaultdict
righe = json.load(open('data/matchday_stats.json'))
players = {p['id']: p for p in json.load(open('data/players.json'))}
tp, n = defaultdict(int), defaultdict(int)
for x in righe:
    if x.get('tiri_porta') is not None and x['player_id'] in players:
        tp[x['player_id']] += x['tiri_porta']; n[x['player_id']] += 1
for ruolo in 'DCA':
    v = [tp[k] for k in tp if players[k]['role'] == ruolo and n[k] >= 3]
    print(f'{ruolo}: mediana {st.median(v):.0f} tiri in porta, max {max(v)}, {len(v)} giocatori')
EOF
```

## Fonti esterne

- [Impostazione delle Opzioni Sostituzioni — leghe.fantacalcio.it](https://leghe.fantacalcio.it/guide-leghe-fantacalcio/gestione-lega/impostazione-delle-opzioni-sostituzioni-88)
  — le tre modalità (Dynamic / Hybrid / **Traditional**, quella della nostra lega) e il
  numero di sostituzioni (1-10 o illimitate).
- [Regolamento Fantacalcio leghe private — fantacalcio.it](https://www.fantacalcio.it/regolamenti/leghe-private)
  — soglia gol (66 consigliata, fasce 4-6 punti), panchina e sostituzioni, bonus porta
  inviolata +1 e rigore parato +3.
- [Fasce gol al fantacalcio — fantacalcio-online.com](https://www.fantacalcio-online.com/it/regole/come-funziona-regola-del-59-bonus-pareggio)
  — la tabella tipica: 1 gol a 66, 2 a 72, 3 a 78.

## Limite di questa analisi

La stagione 2026-27 è oltre le mie conoscenze: **non ho verificato nessun giocatore, né la
sua squadra né il suo ruolo, contro la realtà.** Tutto è verificato sul codice e sui dati
del repo, non sul campo. Il controllo delle notizie vere resta alla skill `formazione` e a
`notizie_rosa.json`.
