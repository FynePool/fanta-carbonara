# Come il progetto valuta la formazione — analisi esterna (27/09/2026)

Revisione della catena che produce l'undici: `data/` → `scripts/lib/roster.py` →
`scripts/report_formazione.py`. Fatta da fuori, senza fidarsi di
`.docs/difetti-consiglio-formazione.md`: ogni affermazione è stata rieseguita sul codice
e sui dati di questo branch.

Marcatori come negli altri doc: **[Certo]** eseguito e visto · **[Probabile]** inferenza
forte · **[Ipotesi]** sto colmando un vuoto.

Strumento nuovo introdotto qui: `scripts/backtest_undici.py`. Non cambia niente in
`roster.py`.

---

## La verità scomoda, prima di tutto

**Il pezzo più complicato del modello non guadagna un punto, e la regola su cui si
regge tutto l'ordinamento non è mai stata verificata con la lega.**

1. La **correzione per la produzione** (sostituire i gol veri con quelli attesi dai tiri
   in porta) è la macchina più elaborata del codice e produce i numeri più grossi che si
   leggono nel report — oggi **+0,62 su Zaccagni e −0,64 su Frattesi**, tre volte il
   massimo del termine sull'avversario (±0,21). In punti veri vale **+0,14 punti a
   giornata, con intervallo [−0,79, +0,89]**: zero misurabile, e il segno è persino
   dalla parte sbagliata. **[Certo]**
2. Il criterio "dentro un ruolo ordino per media quando gioca, la probabilità di giocare
   non conta" è corretto **solo se** le sostituzioni avvengono tra pari ruolo. Il doc dei
   difetti lo marca `[Ipotesi da confermare]` e da allora non è stato confermato.
   leghe.fantacalcio.it offre **tre** modalità (Traditional / Hybrid / Dynamic): in due
   su tre il modulo può cambiare durante il calcolo, e l'ordinamento per ruolo non è più
   la regola giusta. **[Certo]** sull'esistenza delle tre modalità, **[Ipotesi]** su
   quale usi FantaCarbonara.

Il resto del motore, invece, funziona e ora si sa di quanto.

---

## La metrica che mancava

`backtest_formazione.py` misura due cose: l'errore sul fantavoto di un singolo giocatore
(MAE) e quante volte mette in ordine giusto due giocatori della stessa rosa. Nessuna
delle due risponde alla domanda che conta: **quanti punti a giornata guadagna la
formazione consigliata?** Un modello può prevedere meglio ogni singolo voto e schierare
lo stesso undici: in quel caso non vale niente.

`scripts/backtest_undici.py` chiude il buco. Per ogni giornata dalla 3 alla 5 e per
**ognuna delle 12 rose della lega** schiera la formazione coi soli dati precedenti,
applica le regole (sostituzioni illimitate tra pari ruolo, slot scoperto = 0 punti) e
somma i punti veri. 36 formazioni, bootstrap appaiato su (squadra, giornata). **[Certo]**

```
regola                              punti    min    max   contro il modello, IC 95%
modello attuale                     72.31   61.0   87.0   (riferimento)
media nuda dei voti                 71.07   61.0   83.0   -1.24 [-2.51,-0.04] peggio
fantamedia stagione scorsa          70.51   60.0   87.0   -1.79 [-3.22,-0.35] peggio
meta modello + meta scorsa          71.24   60.0   86.0   -1.07 [-1.86,-0.33] peggio
quotazione iniziale                 71.14   60.0   83.5   -1.17 [-2.67,+0.39] indistinguibile
nessun ordine (ordine d'acquisto)   70.56   58.5   87.5   -1.75 [-3.54,-0.10] peggio
ORACOLO (sa i voti veri)            78.18   67.0   92.5   +5.88 [+4.78,+7.03] MEGLIO
```

Come si legge: **il modello vale circa +1,75 punti a giornata** rispetto a schierare la
rosa senza pensarci, e batte ogni regola semplice provata. Con la soglia gol standard (il
primo gol a 66 punti, poi fasce di 4-6 punti) **+1,75 punti valgono circa un terzo di gol
a giornata**: su 33 giornate sono 10-14 gol, la differenza tra metà classifica e i primi
posti. Non è poco, ed è la prima volta che il numero esiste.

Il tetto: un oracolo che conoscesse i voti in anticipo farebbe +5,88. Il modello prende
quindi **circa il 23% di ciò che c'è da prendere**. Il resto è irriducibile: nel
fantacalcio la maggior parte del risultato è caso.

> Nota di metodo, perché è la trappola in cui sono cascato io per primo. Sulla sola rosa
> mia (3 formazioni) la fantamedia della stagione scorsa sembrava battere il modello di
> 0,17 punti. Su 36 formazioni perde di 1,79 con intervallo che esclude lo zero. **Con
> 3 osservazioni qualunque differenza sotto i 3-4 punti è rumore.** Vale per questa
> analisi e vale per ogni conclusione tratta da `--descrittive`. **[Certo]**

---

## Punti forti

### 1. Il criterio di fondo è quello giusto per questa lega (dato il presupposto)

Con sostituzioni illimitate tra pari ruolo, ordinare per "fantavoto atteso **se** prende
voto" e ignorare la probabilità di giocare è dimostrabilmente ottimo: scambiando due
giocatori vicini in lista la differenza vale `P(A)·P(B)·(media A − media B)`, quindi
vince sempre chi ha la media più alta. Il doc lo dimostra e lo verifica in Monte Carlo.
**[Certo]** Questo è il pezzo di pensiero più prezioso del progetto: è controintuitivo,
è corretto, e quasi nessun consiglio di fantacalcio in circolazione lo fa.

### 2. Il freno sulle medie (shrinkage) è dove stanno i punti

L'ablazione in punti dice che togliendo **entrambi** i pezzi sofisticati si perde solo
1,32 [−2,78, −0,06]. Quindi quasi tutto il vantaggio di +1,75 viene dalla cosa più
semplice: **la media degli ultimi voti avvicinata alla media del ruolo quando i voti sono
pochi.** **[Certo]** È statistica di base fatta bene, ed è la parte che nessuno nota.

Bonus: il valore esatto del freno non conta. 3 invece di 5 vale −0,12 [−0,43, +0,15];
10 invece di 5 vale −0,36 [−1,06, +0,22]. **[Certo]** La ritaratura da 3 a 5 del 27/09 è
stata lavoro sprecato, ma innocuo: qualunque freno tra 3 e 10 va bene.

### 3. L'onestà sui dati, che è quasi unica

- Il report dice **su quanti voti** si basa ogni numero, e quanto è "media del ruolo"
  ("il valore è per 71% la media del ruolo" su Esposito Se.). **[Certo]**
- La sezione "DECISIONI TUE" dichiara quando il modello **non sa**: sotto 0,20 di
  distacco indovina il 52-55% delle volte, cioè una moneta, e lo dice. **[Certo]**
- Niente viene inventato: status mancante → `n/d` con la nota, giocatore fuori dal
  listone → segnalato, ruolo senza dati → slot lasciato all'utente col motivo.
- Lo storico dei voti non si accorcia mai (`store.save_matchday_stats` si rifiuta).

Un sistema che dichiara la propria incertezza vale più di uno più preciso che non la
dichiara, soprattutto per chi non sa di calcio e non può accorgersi da solo dell'errore.

### 4. L'econometria del termine "avversario" è fatta con cura

`β` si stima sugli **scarti di ogni giocatore dalla sua media** (così chi è forte non
inquina il coefficiente) e i gol subiti dall'avversario si calcolano **escludendo quella
partita** (altrimenti il gol del giocatore gonfia da sé i gol subiti, e il coefficiente).
**[Certo]** Sono le due precauzioni che quasi tutti dimenticano. In punti il termine vale
+0,57 [−1,56, +0,26]: probabilmente positivo, non ancora dimostrato.

### 5. Le regole vere della lega sono dentro il codice, non nella testa di qualcuno

Rinvii (6 politico fino a 3 partite, voto del recupero oltre), scadenza formazione
calcolata dalla prima partita non rinviata, squalificati esclusi, diffidati segnalati,
nessun modificatore di difesa. Ogni regola ha il suo `_fonte` in `config/league.json`.
**[Certo]** La gestione dei rinvii in particolare è più curata di quella di molti siti.

---

## Punti debili, dal più grave

### 1. Tre impostazioni della lega non sono mai state lette, e due possono invalidare il motore

Sono tre caselle nel pannello della lega su leghe.fantacalcio.it. Nessuna è nel repo.

| Impostazione | Cosa assume il progetto | Cosa succede se è diversa |
|---|---|---|
| **Modalità sostituzioni** | Traditional (solo pari ruolo) | Con Hybrid o Dynamic il modulo cambia durante il calcolo: ordinare per ruolo non è più ottimo, e la panchina va ordinata per "primo che configura un modulo valido" |
| **Dimensione panchina** | illimitata: il report stampa **14 panchinari** | Se la lega ne ammette 7 (tipico), 7 dei 14 non entrano mai. **Quali** 7 escludere dipende dalla probabilità di giocare — l'unico posto dove quella probabilità serve davvero |
| **Soglie gol** (66, poi fasce 4-6) | non esiste da nessuna parte | Senza di essa non si può dire se +0,30 punti cambia il risultato o no |

**[Certo]** che le tre impostazioni esistano e siano configurabili (documentazione
ufficiale, link in fondo). **[Ipotesi]** su come sia impostata FantaCarbonara.

La prima è la più grave perché è **portante**: tutto l'ordinamento, la scelta del modulo e
la frase "la probabilità di giocare non entra nel numero" dipendono da lei. Costo per
verificarla: un minuto. Costo se è sbagliata: tutto il motore.

La seconda è quella che morde subito. Il report di oggi elenca 14 panchinari numerati
(P1-P2, D1-D5, C1-C4, A1-A3) come se andassero tutti in distinta. Se la panchina è
limitata, l'utente — che per sua stessa ammissione non sa di calcio — taglia a caso.

### 2. Il motore non sa contro chi giochi, pur avendo il dato in casa

`data/lega_competizioni.json` contiene il calendario testa-a-testa completo: 33 giornate,
tutte le partite, i punteggi. Alla prossima giornata (Serie A 6 = giornata 1 di lega)
**VAR-tificiale gioca in trasferta contro BORUSSIA LABELLA**. **[Certo]**

`grep -rn lega_competizioni scripts/` → il file non viene letto da nessuno tranne il suo
importer. **[Certo]**

Perché conta. Nel fantacalcio non si massimizza il punteggio, si vince o si perde una
partita. I punti diventano gol a scatti (66 → 1 gol, poi ogni 4-6 punti un altro), quindi:

- contro una squadra più forte conviene **alzare la varianza** (giocatori più rischiosi:
  se fai la partita media perdi comunque);
- contro una più debole conviene **abbassarla** (basta non sbagliare).

Il motore fa sempre la stessa cosa. **[Probabile]** l'effetto è più piccolo di 1,75 punti
a giornata, ma è gratis: i dati ci sono già.

### 3. La correzione per la produzione è rumore travestito da precisione

Questo è il difetto che costa più **fiducia** che punti.

**Cosa fa.** Sostituisce i gol veri del giocatore con quelli attesi dai suoi tiri in
porta, usando il tasso di conversione **del ruolo** (D 0,265, C 0,294, A 0,324). Cioè
assume che nessun giocatore sia più bravo degli altri a segnare: un tiro in porta di
Zaccagni vale come quello di un difensore qualunque del campionato.

**Perché non può funzionare adesso [Certo].** Tiri in porta accumulati in 5 giornate, per
chi ha giocato almeno 3 partite: **mediana 0 per i difensori, 1 per i centrocampisti, 2
per gli attaccanti.** Da 1-2 tiri non si stima niente.

**Cosa produce [Certo].** I due numeri più grandi del report di oggi:

```
Zaccagni  +0.62   0 gol su azione contro 2.1 attesi da 7 tiri in porta su 12
Frattesi  -0.64   3 gol su azione contro 0.9 attesi da 3 tiri in porta su 7
```

Frattesi ha segnato 3 gol e il modello gli toglie 0,64 punti perché "statisticamente non
doveva". Può anche essere giusto in media su mille partite; su cinque è una scommessa
grossa presentata con la stessa autorevolezza di tutto il resto.

**Quanto vale [Certo].** +0,14 [−0,79, +0,89] punti a giornata: niente. E `peso_produzione`
a metà invece che pieno vale −0,01 [−0,81, +0,62]: il parametro che decide la dimensione
della correzione più grande del modello **non è distinguibile da zero né da uno**.

**Perché è un problema di fiducia e non solo di punti.** L'utente non sa di calcio. La
colonna `prod` gli dice, con due decimali, che Frattesi vale meno di quanto ha fatto
vedere. Non ha modo di sapere che quel numero è indistinguibile dal caso, mentre il report
lo segnala solo quando i tiri **mancano** ("senza tiri da BigBalls"), non quando ce ne
sono troppo pochi per contare.

### 4. Nessun avviso sulla profondità di un ruolo

Il criterio "ignora la probabilità di giocare" ha un limite che il doc riconosce e che il
codice non copre: vale finché la panchina del ruolo **copre**. Se nessuno di un ruolo
prende voto, lo slot vale 0 (circa 6 punti buttati, un decimo del totale).

Il caso vivo: **i tre portieri sono tutti dell'Inter** (Martinez Jo. 90%, Provedel 5%,
Di Gennaro 1%). **[Certo]** Per fortuna questo protegge invece di esporre — in ogni
partita dell'Inter esattamente un portiere dell'Inter gioca — ma il motore non lo sa e per
caso ha ragione. Se l'Inter fosse rinviata o non giocasse, **tutti e tre** i portieri
sarebbero fuori insieme, e il report non dice una parola. Lo stesso vale per un ruolo
falcidiato da infortuni a metà stagione.

Ho misurato il difetto teorico collegato: il criterio del modulo (somma dei valori dei
primi n) **sovrastima** il totale atteso di 0,7-1,4 punti, perché non sconta chi non
prende voto. Ma la sovrastima è quasi identica per tutti i moduli, quindi **oggi non
cambia la scelta: costo 0,00** **[Certo]**. Il difetto è reale e dormiente: si sveglia
quando un ruolo si assottiglia. La correzione utile non è modellistica, è un avviso:
"nel ruolo X, se i primi due non prendono voto lo slot resta vuoto".

### 5. Metà delle statistiche raccolte non entra da nessuna parte

Righe in `matchday_stats.json` con il dato presente, e uso nel modello:

| campo | righe | usato? |
|---|---|---|
| `passaggi_chiave` | 2044 | **no, mai letto** |
| `assist` | 2044 (103 con assist) | solo stampato, non modellato |
| `cartellini_gialli` | 2044 (154 con giallo) | **no** |
| `falli_commessi` | 2044 (720) | **no** |
| `minuti`, `rigori_sbagliati` | 2044 | **no** |

**[Certo]** Il malus giallo è −0,5 e il giocatore più ammonito della Serie A ne prende
0,60 a partita: **−0,30 punti attesi, più del massimo del termine avversario (±0,21).**
Oggi quel malus entra solo attraverso il fantavoto realizzato, cioè in modo molto rumoroso
su 5 partite.

**Ma la mia previsione è che modellarli non pagherà, e il motivo lo dà il difetto 3.**
Assist-dai-passaggi-chiave e gialli-dai-falli sono esattamente la stessa idea della
correzione per la produzione: sostituire l'evento realizzato con quello atteso. Quella
idea, misurata, vale zero con questo campione. **[Probabile]** Le altre valgono meno,
perché gli effetti sono più piccoli. Quindi questa non è una cosa da fare: è una cosa da
**non** fare finché `backtest_undici.py` non mostra che paga.

### 6. Rigoristi: il buco vero nei dati

Un rigorista designato vale 0,15-0,25 rigori a partita, cioè **+0,5/+0,75 di fantavoto
atteso**: il singolo fattore più grande di tutti quelli discussi qui, più grande del
termine avversario e della correzione produzione messi insieme. **[Probabile]**, è
aritmetica sui bonus.

Oggi: i gol su rigore restano nel fantavoto come sono (giusto), ma **chi è il rigorista
non si sa**. Il box score BigBalls ha 5 rigori in 50 partite, troppo pochi per dedurlo
**[Certo]**, e la pagina "rigoristi" di fantacalcio.it non è mai stata letta. Il doc lo
segna come aperto e ha ragione a non inventare. Conseguenza concreta: un rigorista che non
ha ancora calciato è sottovalutato, e chi ha segnato due rigori per caso è sopravvalutato.
Questo è l'unico dato mancante che vale la pena andare a prendere.

### 7. Cose minori, verificate

- **Portieri, regressore sbagliato [Certo].** Il contesto usa i gol **subiti**
  dall'avversario anche per i portieri, dove il meccanismo giusto sono i gol **fatti**.
  Il backtest ha provato la variante: indistinguibile su 55 previsioni. Giusto lasciarla
  lì. Impatto oggi quasi nullo: in una rosa un solo portiere ha voti.
- **Bonus porta inviolata e rigore parato sono `null` in config** perché il regolamento
  non li chiarisce. Lo standard è +1 e +3. Il modello usa il fantavoto **già calcolato**
  da fantacalcio.it con i bonus standard: se la lega usa valori diversi, i portieri sono
  sistematicamente sbagliati. Impatto: solo l'ordine tra i tuoi portieri, cioè quasi
  niente. Da chiarire con la lega quando capita, non urgente.
- **`CLAUDE.md` dice che il campionato ha "33 giornate" importate; il file ce le ha
  [Certo]** — verificato, 33 giornate con le 6 partite ciascuna. Nessun disallineamento.
- **Avversario ignoto trattato come medio [Probabile].** In `costruisci_modello`, se il
  nome della squadra avversaria non si trova, `subiti_a_partita` restituisce la media del
  campionato e il contributo diventa 0 senza avviso. Silenzioso, non sbagliato.
- **Un giocatore senza voti va in fondo al suo ruolo**, dietro chiunque abbia un solo
  voto, anche se la stagione scorsa aveva una fantamedia alta ed è un titolare fisso. Il
  report lo segnala ("Titolari senza nessun voto, da decidere a mano") e mostra
  "STAGIONI PASSATE", quindi l'informazione c'è; l'ordine no. Oggi in rosa non fa danno.

---

## Critiche che ho provato e che NON reggono

Le scrivo perché sono quelle che un esperto di fantacalcio direbbe per prime, e sono
sbagliate. Il progetto le aveva già respinte: confermo con i numeri.

- **"Sei titolari da due sole squadre (3 Lazio, 3 Bologna) sono un rischio."** Misurata la
  correlazione tra i fantavoti di due compagni nella stessa partita, sugli scarti dalle
  medie individuali: **ρ = 0,074 su 7.260 coppie**. La σ del totale dell'undici passa da
  4,38 (indipendenti) a **4,56**: **+4%**. **[Certo]** Trascurabile. Il fantavoto dipende
  molto più dalla prestazione individuale che dal risultato di squadra. Il progetto ha
  ragione a ignorarlo.
- **"Il fattore campo va aggiunto."** È l'effetto più solido del calcio, ma sul fantavoto
  individuale il backtest lo trova negativo (−0,006 sul MAE). **[Probabile]** Il vantaggio
  casalingo si scarica sul risultato, non sui voti singoli, e in parte è già dentro il
  termine avversario. Non insisterei.
- **"La stagione scorsa deve entrare nel modello."** Provata come punto di partenza del
  freno (niente) e ora anche come regola di ordinamento a sé: **70,51 punti contro 72,31,
  −1,79 [−3,22, −0,35]**. **[Certo]** Peggio. Come contesto stampato va benissimo dov'è.
- **"Un giocatore che entra al 70' non prende voto."** Falso: 129 voti presi con meno di
  25 minuti, minimo 2 minuti. **[Certo]**
- **"Il 3-4-3 è scelto per principio."** No: è la somma dei valori. Che i moduli con più
  centrocampisti e attaccanti vincano spesso è **corretto**, perché senza modificatore di
  difesa un attaccante medio (6,83) rende più di un difensore medio (6,04). **[Certo]**

---

## Cosa farei, in ordine

1. **Guardare tre caselle nel pannello della lega** e scriverle in `config/league.json`:
   modalità sostituzioni, dimensione massima della panchina, soglie gol. Un minuto di
   lavoro, e la prima può invalidare il motore. Finché non è fatto, tutto il resto è
   costruire sopra un'ipotesi.
2. **Tagliare o parcheggiare la correzione produzione.** Vale zero punti e produce i
   numeri più vistosi e meno affidabili del report. Se resta, va marcata nel report come
   "indicativa, pochi tiri" quando i tiri in porta sono meno di ~10, non solo quando
   mancano del tutto.
3. **Leggere `lega_competizioni.json` nel report**: chi è l'avversario di lega, come è
   andato nelle giornate calcolate, e — con le soglie gol — se la decisione in ballo
   cambia il risultato o no. È il passo che trasforma "+0,30 punti" in "cambia/non cambia
   niente".
4. **Un avviso di profondità per ruolo**: "se i primi due del ruolo X non prendono voto,
   lo slot resta vuoto". Sostituisce il difetto dormiente della scelta del modulo senza
   toccare il modello.
5. **Cercare la lista dei rigoristi.** È l'unico dato mancante che vale più di tutti i
   raffinamenti statistici discussi qui.
6. **Usare `backtest_undici.py` come collaudo**: nessuna modifica a `roster.py` entra se
   non guadagna punti con l'intervallo che esclude lo zero. È la regola che avrebbe
   fermato la correzione produzione e la ritaratura del freno.

Quello che **non** farei: aggiungere assist attesi, gialli attesi, minuti, o altri
segnali. Sono la stessa idea che ha già fallito la misura, e con 5 giornate non c'è
campione per sostenerli.

---

## Riprodurre

Non scrivono niente.

```bash
python3 scripts/backtest_undici.py                    # il backtest dell'undici e l'ablazione in punti
python3 scripts/report_formazione.py --team-id 20598917
python3 scripts/backtest_formazione.py --descrittive
grep -rn "lega_competizioni" scripts/                 # solo il suo importer
```

Correlazione tra compagni di squadra e σ del totale:

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

Tiri in porta accumulati in 5 giornate (perché la correzione produzione non può funzionare):

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
  — le tre modalità (Dynamic / Hybrid / Traditional) e il numero di sostituzioni (1-10 o illimitate).
- [Regolamento Fantacalcio leghe private — fantacalcio.it](https://www.fantacalcio.it/regolamenti/leghe-private)
  — soglia gol (66 consigliata, fasce 4-6 punti), panchina e sostituzioni, bonus porta
  inviolata +1 e rigore parato +3.
- [Fasce gol al fantacalcio — fantacalcio-online.com](https://www.fantacalcio-online.com/it/regole/come-funziona-regola-del-59-bonus-pareggio)
  — la tabella tipica: 1 gol a 66, 2 a 72, 3 a 78.
- [Impostazione delle Opzioni Rose e Formazioni — leghe.fantacalcio.it](https://leghe.fantacalcio.it/guide-leghe-fantacalcio/gestione-lega/impostazione-delle-opzioni-rose-e-formazioni-76)

## Limite di questa analisi

La stagione 2026-27 è oltre le mie conoscenze: **non ho verificato nessun giocatore, né
la sua squadra né il suo ruolo, contro la realtà.** Tutto quello che c'è qui è verificato
sul codice e sui dati del repo, non sul campo. Il controllo delle notizie vere resta in
mano alla skill `formazione` e a `notizie_rosa.json`.
