from collections import Counter, defaultdict
from itertools import combinations
from datetime import date, datetime, timezone
from statistics import mean

from . import store

EXCLUDED_STATUSES = {"infortunato", "squalificato"}
ROLES = ["P", "D", "C", "A"]
# Oltre questa età lo status di un titolare va ricontrollato: con la routine del
# mattino dovrebbe avere al massimo un giorno.
STATUS_VECCHIO_GIORNI = 4

# Il valore di un giocatore è quello che ci si aspetta dal suo fantavoto nella prossima
# partita, *se prende voto*. Dentro un ruolo è il criterio giusto per ordinare, e la
# probabilità di giocare non c'entra: se il titolare non scende in campo entra il primo
# della panchina di quel ruolo, e scambiando due giocatori vicini la differenza vale
# P(A)·P(B)·(valore A − valore B). Vedi .docs/difetti-consiglio-formazione.md.
# ATTENZIONE: questo vale per l'ORDINE dentro un ruolo. NON vale per scegliere *chi* mettere
# in panchina né per scegliere il modulo: la panchina ha 7 posti a quota fissa per ruolo
# (1 P, 2 D, 2 C, 2 A) e se finiscono le riserve di un ruolo lo slot vale 0. Lì la
# probabilità di prendere voto conta, e ci pensano _scegli_panchina e _slot_attesi.
# Sul modulo è stata provata e non ha mostrato guadagni: vedi suggest_lineup.
# Il valore è fatto di due pezzi, verificati con scripts/backtest_undici.py (punti veri
# della formazione, non MAE sul singolo voto):
#   base      media degli ultimi voti, frenata verso la media del ruolo. È qui che stanno
#             i punti: il motore vale +2,61 [+0,64, +4,56] punti a giornata sull'ordine
#             d'acquisto, misurato su 36 formazioni con backtest_undici.py (29/09, senza
#             più guardare il futuro: il 27/09 diceva +3,25 perché escludeva dalle giornate
#             passate chi è infortunato oggi). Intervalli ottimisti: le rose della stessa
#             giornata condividono le partite.
#   contesto  quanto subisce l'avversario della prossima partita. Senza lo sguardo al
#             futuro vale +0,85 [−0,03, +1,71]: non dimostrato. Resta per la regola del
#             progetto, dichiaratamente a favore dello stato attuale (nessun cambiamento,
#             né in entrata né in uscita, senza un intervallo che escluda lo zero). È
#             PROVVISORIO: entrato con prove poi ridimensionate, si rimisura alla giornata 8.
# Provati e lasciati fuori perché non hanno mostrato guadagni (numeri in
# .docs/analisi-valutazione-formazione.md): l'a priori dalla quotazione iniziale e dalla
# fantamedia della stagione scorsa al posto della media del ruolo, il valore separato da
# titolare e da subentrato, il fattore campo, il freno stimato ruolo per ruolo, e la
# correzione per la produzione (vedi PRODUZIONE_PREDEFINITA).

# Forma recente: si guardano gli ultimi N voti presi, non le ultime N giornate.
FORMA_ULTIMI_VOTI = 5
# Chi ha pochi voti viene avvicinato alla media del suo ruolo, come se avesse
# FRENO_VOTI partite in più giocate "da giocatore medio". Senza freno, ordinando per
# media vince chi ha giocato una sola partita fortunata. Ritarato il 27/09 sui voti veri
# (backtest giornate 3-5): 1 peggiora, 5 batte 3 su errore e ordine con intervalli che
# escludono lo zero, 10 migliora ancora l'ordine ma non l'errore in modo netto. Scelto 5,
# il passo più piccolo sostenuto da entrambe le metriche: è scelto tra 4 valori sugli
# stessi dati che lo misurano, quindi il guadagno è un po' ottimista. Da riguardare con
# più giornate (scripts/backtest_formazione.py stampa 3, 5 e 10).
FRENO_VOTI = 5
# Bonus gol del fantavoto di fantacalcio.it (quello dei voti in matchday_stats.json).
BONUS_GOL = 3
# Gol subiti a partita di una squadra: frenati verso la media del campionato come se
# avesse CONTESTO_FRENO_PARTITE partite in più "da squadra media". Il backtest non
# dipende da questo valore finché tutte hanno giocato lo stesso numero di partite (il
# coefficiente si riadatta), serve solo a non esagerare con chi ne ha giocate meno.
CONTESTO_FRENO_PARTITE = 5
# Sotto questa differenza di valore due scelte sono equivalenti: nel backtest delle
# giornate 3-5, con distacchi sotto 0,20 l'ordine previsto indovina chi fa di più il
# 52-55% delle volte, quasi una moneta (0,20-0,30: 60%; sopra 0,50: 69-70%).
SOGLIA_PARI = 0.20
# La correzione per la produzione (sostituire i gol su azione con quelli attesi dai tiri
# in porta) è SPENTA dal 27/09. La decisione NON si appoggia a un risultato significativo:
# nel backtest in punti riaccenderla vale +0,07 [−0,79, +1,06], cioè il test non distingue.
# Si appoggia a tre cose insieme:
#  1. tre misure indipendenti (panchina illimitata, panchina vera, e con la soglia sui tiri)
#     danno tutte un punto stimato a favore dello spegnerla, nessuna a favore del contrario;
#  2. il meccanismo: in 5 giornate i tiri in porta accumulati sono in mediana 0 per i
#     difensori, 1 per i centrocampisti, 2 per gli attaccanti. Da 1-2 tiri i gol attesi sono
#     rumore, e la correzione assume anche che nessun giocatore sia più bravo a segnare degli
#     altri del suo ruolo;
#  3. produceva i numeri più grossi del report (+0,62 su Zaccagni, −0,64 su Frattesi che
#     aveva segnato 3 gol), con due decimali, a un utente che non può giudicarli: falsa
#     precisione, che costa fiducia anche quando non costa punti.
# Il parametro `produzione` resta: `backtest_undici.py` lo riprova a ogni giro, e si
# riaccende solo se con più giornate guadagna punti con l'intervallo che esclude lo zero.
PRODUZIONE_PREDEFINITA = False
# Probabilità di prendere voto usata quando `prob_titolare` manca: non si inventa un
# numero per giocatore, si usa una quota neutra solo per confrontare le panchine fra loro.
PROB_VOTO_IGNOTA = 50.0
# I portieri di una squadra, sommati, per fantacalcio.it fanno quasi sempre 96 (90 + 5 + 1:
# 16 squadre su 20 il 29/09). Il sito non scrive mai più di 90: è una scala, non una
# probabilità, e presa alla lettera lascia scoperta la porta il 4-5% delle volte anche con
# tutti i portieri della squadra in distinta. Dentro un gruppo di portieri della stessa
# squadra le quote si riportano a probabilità dividendo per la somma di tutti i portieri di
# quella squadra, ma solo se la somma è almeno questa: sotto, manca il dato del titolare
# (nome non abbinato, scrape fallito) e dividere gonfierebbe le riserve.
PORTIERI_QUOTA_MINIMA = 50.0
# Chi non ha voti ma per le probabili parte titolare almeno a questa percentuale, se resta in
# panchina o fuori distinta, viene segnalato (vedi suggest_lineup).
PROB_TITOLARE_SENZA_VOTI = 60.0
# Un panchinaro sotto questa probabilità di giocare è quasi uno slot di panchina buttato:
# la panchina ha 1-2 posti per ruolo, e il report lo segnala.
PROB_RISERVA_INUTILE = 25.0
# Sotto questa probabilità di riempire tutti gli slot di un ruolo, il report avvisa: se le
# riserve di quel ruolo non prendono voto lo slot vale 0, cioè circa 6 punti persi.
SOGLIA_AVVISO_COPERTURA = 0.97
# Il primo rigorista vale circa +0,26 di fantavoto atteso a partita (0,139 rigori per
# squadra a partita nella stagione scorsa x 1,90 per rigore: vedi scripts/rigoristi.py,
# che ricalcola il numero dai dati e lo scrive in data/rigoristi.json).
#
# NON entra nel punteggio, per due ragioni, nessuna delle quali è il backtest (lì il
# confronto non ha potere e la prima versione era anche sbagliata: assegnava il bonus al
# primo rigorista della stagione scorsa senza controllare se fosse ancora in quella
# squadra — vedi la nota nel doc).
#
#  1. LE GERARCHIE NON SONO UN DATO. Sono pareri di giornali che si contraddicono sul
#     primo rigorista di 9 squadre su 20, e i rigori veri per metterle alla prova sono
#     pochissimi (5 nelle prime 5 giornate). Il 27/09 qui c'era scritto che "3 su 5 le
#     hanno smentite": era FALSO. In tutti e tre i casi il primo designato non era in campo
#     (Pessina non ha ancora giocato, Mina in panchina, Busio infortunato). Dove un rigore
#     ha messo alla prova il primo delle fonti, ha calciato lui (Zaccagni, Colombo); una
#     volta è stato scavalcato il secondo (Adams A. al Venezia, con Busio fuori ha calciato
#     Yeboah mentre Adams era in campo). Lo conta scripts/rigoristi.py (valuta_rigori). Con
#     un campione così piccolo il flag non si somma a un punteggio.
#  2. DOPPIO CONTEGGIO su chi ha già calciato: la media degli ultimi voti contiene già il
#     rigore. Zaccagni ha segnato alla giornata 5, la sua media porta già +0,6, e
#     sommargli +0,26 lo conterebbe due volte. (I rigori si potrebbero togliere dai voti:
#     il box score BigBalls li ha tutti e 5, verificato contro fantacalcio.it. Ma resta la
#     ragione 1.)
#
# Quindi il rigorista serve dove l'informazione è decisiva, va pesata a mano e non si somma
# a niente: come spareggio fra due giocatori entro SOGLIA_PARI, distinguendo chi è
# CONFERMATO dai rigori veri di quest'anno da chi è solo una supposizione. Lo fa
# _decisioni, e il report lo mostra accanto al giocatore.
VALORE_PRIMO_RIGORISTA_DEFAULT = 0.26

# Role counts per module, excluding the goalkeeper (always 1).
MODULE_ROLE_COUNTS = {
    "3-4-3": {"D": 3, "C": 4, "A": 3},
    "3-5-2": {"D": 3, "C": 5, "A": 2},
    "4-3-3": {"D": 4, "C": 3, "A": 3},
    "4-4-2": {"D": 4, "C": 4, "A": 2},
    "4-5-1": {"D": 4, "C": 5, "A": 1},
    "5-3-2": {"D": 5, "C": 3, "A": 2},
    "5-4-1": {"D": 5, "C": 4, "A": 1},
}


def _n(n: int, singolare: str, plurale: str) -> str:
    return f"{n} {singolare if n == 1 else plurale}"


def team_roster(team_id: str, players_by_id: dict):
    """Ritorna (rosa, player_id di ownership.json che non esistono più nel listone)."""
    roster, mancanti = [], []
    for o in store.load_ownership():
        if o["team_id"] != team_id:
            continue
        if o["player_id"] in players_by_id:
            roster.append({**players_by_id[o["player_id"]], "purchase_price": o["purchase_price"]})
        else:
            mancanti.append(o["player_id"])
    return roster, mancanti


def _matchday_sort_key(row: dict):
    """La giornata può essere nulla: la fonte la etichetta con circa un giorno di
    ritardo, quindi una riga senza giornata è quasi sempre la più recente. Va in
    fondo all'ordinamento invece di far fallire il confronto int/None."""
    matchday = row.get("matchday")
    return (1, 0) if matchday is None else (0, matchday)


def _retta(xs: list[float], ys: list[float]) -> float:
    """Pendenza della retta dei minimi quadrati (0 se le x non variano)."""
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0


def costruisci_modello(
    righe: list[dict],
    players_by_id: dict,
    calendario: list[dict],
    prima_di_giornata: int | None = None,
    produzione: bool = PRODUZIONE_PREDEFINITA,
    contesto: bool = True,
    freno: float = FRENO_VOTI,
    peso_produzione: float = 1.0,
) -> dict:
    """Tutto quello che serve a valutare i giocatori, stimato sui dati (nessun numero a
    mano oltre alle costanti in cima). Con `prima_di_giornata` usa solo le giornate
    precedenti: è quello che fa il backtest. `produzione` e `contesto` accendono i due
    pezzi, `freno` e `peso_produzione` (1 = gol su azione sostituiti per intero da quelli
    attesi) servono solo alle prove di sensibilità del backtest.

    - conversione: gol su azione per tiro in porta, per ruolo (D, C, A);
    - media_ruolo: media dei voti del ruolo, già corretti per la produzione;
    - gol subiti a partita di ogni squadra, frenati verso la media del campionato;
    - beta: di quanto sale il fantavoto per ogni gol subito in più dall'avversario, uno
      per i portieri e uno per gli altri ruoli. Stimato sugli scarti di ogni giocatore
      dalla sua media, così chi è forte non pesa, e con i gol subiti dall'avversario
      calcolati senza quella partita: altrimenti il gol del giocatore gonfierebbe da
      solo i gol subiti dell'avversario, e il coefficiente."""
    def usa(giornata):
        return prima_di_giornata is None or (giornata is not None and giornata < prima_di_giornata)

    voti = [
        r for r in sorted(righe, key=_matchday_sort_key)
        if r.get("fantavoto") is not None and r["player_id"] in players_by_id and usa(r.get("matchday"))
    ]
    ruolo = {pid: p["role"] for pid, p in players_by_id.items()}

    conversione = {}
    for r_ in ("D", "C", "A"):
        con_tiri = [r for r in voti if ruolo[r["player_id"]] == r_ and r.get("tiri_porta") is not None]
        tiri = sum(r["tiri_porta"] for r in con_tiri)
        gol_azione = sum(r["gol"] - (r.get("rigori_segnati") or 0) for r in con_tiri)
        conversione[r_] = gol_azione / tiri if tiri else None

    def corretto(r: dict) -> float:
        """Il fantavoto con i gol su azione sostituiti da quelli attesi dai tiri in porta.
        Senza statistiche BigBalls (o per i portieri) resta il fantavoto."""
        conv = conversione.get(ruolo[r["player_id"]])
        if not produzione or conv is None or r.get("tiri_porta") is None:
            return r["fantavoto"]
        gol_azione = r["gol"] - (r.get("rigori_segnati") or 0)
        return r["fantavoto"] + peso_produzione * BONUS_GOL * (conv * r["tiri_porta"] - gol_azione)

    per_giocatore = defaultdict(list)
    for r in voti:
        per_giocatore[r["player_id"]].append(r)
    per_ruolo = defaultdict(list)
    for r in voti:
        per_ruolo[ruolo[r["player_id"]]].append(r)
    media_ruolo = {r_: mean(corretto(r) for r in rr) for r_, rr in per_ruolo.items()}

    subiti = defaultdict(dict)  # squadra -> match_id -> gol subiti
    for m in calendario:
        if m["stato"] == "finished" and m.get("gol_casa") is not None and usa(m.get("giornata")):
            subiti[m["squadra_casa"]][m["match_id"]] = m["gol_trasferta"]
            subiti[m["squadra_trasferta"]][m["match_id"]] = m["gol_casa"]
    tutti = [g for d in subiti.values() for g in d.values()]
    media_subiti = mean(tutti) if tutti else None

    def subiti_a_partita(squadra: str, senza: str | None = None) -> float | None:
        if media_subiti is None:
            return None
        g = [x for mid, x in subiti.get(squadra, {}).items() if mid != senza]
        return (sum(g) + CONTESTO_FRENO_PARTITE * media_subiti) / (len(g) + CONTESTO_FRENO_PARTITE)

    beta = {}
    if contesto and media_subiti is not None:
        xs, ys = {"P": [], "altri": []}, {"P": [], "altri": []}
        for pid, rr in per_giocatore.items():
            if len(rr) < 2:
                continue
            gruppo = "P" if ruolo[pid] == "P" else "altri"
            m = mean(corretto(r) for r in rr)
            for r in rr:
                xs[gruppo].append(subiti_a_partita(r["opponent_serie_a_team"], senza=r["match_id"]) - media_subiti)
                ys[gruppo].append(corretto(r) - m)
        beta = {g: _retta(xs[g], ys[g]) for g in xs if len(xs[g]) >= 2}

    return {
        "per_giocatore": per_giocatore,
        "media_ruolo": media_ruolo,
        "conversione": conversione,
        "corretto": corretto,
        "media_subiti": media_subiti,
        "subiti_a_partita": subiti_a_partita,
        "beta": beta,
        "freno": freno,
        "produzione": produzione,
    }


def rate_player(player: dict, modello: dict, avversario: str | None = None) -> dict | None:
    """Il valore atteso del giocatore nella prossima partita se prende voto, e i pezzi di
    cui è fatto, per mostrarli. None se il giocatore non ha nessun voto: non si stima
    niente. Un pezzo che non si può calcolare (nessun dato BigBalls, avversario ignoto)
    vale 0 e viene segnalato, non stimato."""
    rr = modello["per_giocatore"].get(player["id"], [])[-FORMA_ULTIMI_VOTI:]
    if not rr:
        return None
    ruolo, k = player["role"], modello["freno"]
    voti = [r["fantavoto"] for r in rr]
    corretti = [modello["corretto"](r) for r in rr]
    riferimento = modello["media_ruolo"].get(ruolo, mean(corretti))
    base = (sum(corretti) + k * riferimento) / (len(corretti) + k)

    con_tiri = [r for r in rr if r.get("tiri_porta") is not None]
    conv = modello["conversione"].get(ruolo)
    produzione = None
    if modello["produzione"] and ruolo != "P" and conv is not None:
        produzione = {
            "voti_con_tiri": len(con_tiri),
            "tiri": sum(r.get("tiri") or 0 for r in con_tiri),
            "tiri_porta": sum(r["tiri_porta"] for r in con_tiri),
            "gol_azione": sum(r["gol"] - (r.get("rigori_segnati") or 0) for r in con_tiri),
            "gol_attesi": conv * sum(r["tiri_porta"] for r in con_tiri),
            # quanto la correzione sposta il valore, già frenata come il resto della base
            "effetto": sum(c - v for c, v in zip(corretti, voti)) / (len(voti) + k),
        }

    contesto = None
    beta = modello["beta"].get("P" if ruolo == "P" else "altri")
    if avversario and beta is not None:
        subiti = modello["subiti_a_partita"](avversario)
        contesto = {
            "avversario": avversario,
            "subiti": subiti,
            "effetto": beta * (subiti - modello["media_subiti"]),
        }

    subentrato = [r.get("subentrato") for r in rr]
    return {
        "media": mean(voti),
        "n": len(voti),
        "riferimento": riferimento,
        "base": base,
        "produzione": produzione,
        "contesto": contesto,
        "portiere": ruolo == "P",
        "titolare": sum(1 for s in subentrato if s is False),
        "da_subentrato": sum(1 for s in subentrato if s is True),
        "punteggio": base + (contesto["effetto"] if contesto else 0.0),
    }


def player_history_vs_opponent(player_id: str, opponent_serie_a_team: str):
    return [
        r
        for r in store.load_matchday_stats()
        if r["player_id"] == player_id
        and r["opponent_serie_a_team"] == opponent_serie_a_team
    ]


def prossimo_turno(adesso: datetime | None = None) -> dict:
    """Il prossimo turno di Serie A ricavato dalle date delle partite, senza inventare il
    numero di giornata (la fonte lo assegna solo dopo che la partita è stata giocata).

    Il turno sono le prime 10 partite non ancora giocate: se coprono le 20 squadre una
    volta ciascuna è un turno pulito. Se no (un recupero, un rinvio, un turno già
    iniziato) `chiaro` è False e nessuno viene escluso: va controllato a mano."""
    path = store.DATA_DIR / "calendario_serie_a.json"
    calendario = store.load_json(path) if path.exists() else []
    adesso = (adesso or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S")
    futuri = sorted(
        (m for m in calendario if m["stato"] != "finished" and m["data_utc"][:19] >= adesso),
        key=lambda m: m["data_utc"],
    )
    turno = futuri[:10]
    squadre = Counter(t for m in turno for t in (m["squadra_casa"], m["squadra_trasferta"]))
    per_squadra = {}
    for m in futuri:
        for t in (m["squadra_casa"], m["squadra_trasferta"]):
            per_squadra.setdefault(t, m)
    return {
        "partite": turno,
        "chiaro": len(turno) == 10 and len(squadre) == 20,
        "per_squadra": per_squadra,
    }


def rigoristi() -> tuple[dict, float, dict]:
    """(player_id -> voce di data/rigoristi.json, valore del primo rigorista in fantavoto,
    come hanno retto le liste ai rigori veri).

    Le gerarchie non sono un dato ufficiale: sono valutazioni editoriali che si
    contraddicono spesso, quindi conta `consenso_sul_primo` (almeno due fonti indipendenti
    lo danno primo). `conferma` e `scavalcato_da` dicono cosa provano i rigori calciati
    quest'anno. Lo calcola scripts/rigoristi.py. Se il file non c'è, nessun rigorista.

    La prova: quante volte il primo delle fonti ha calciato lui, e quante volte è stato
    scavalcato mentre era in campo. Serve a dire allo spareggio quanto fidarsi."""
    path = store.DATA_DIR / "rigoristi.json"
    if not path.exists():
        return {}, VALORE_PRIMO_RIGORISTA_DEFAULT, {}
    doc = store.load_json(path)
    valore = doc.get("valore_primo_rigorista") or VALORE_PRIMO_RIGORISTA_DEFAULT
    voci = doc.get("rigoristi", [])
    prova = {
        "primo_ha_calciato": sum(1 for r in voci if r.get("conferma") == "confermato"),
        "primo_scavalcato": sum(1 for r in voci if r.get("rango") == 1 and any(
            x["dove"] == "in campo" for x in r.get("scavalcato_da", []))),
        "verifica": doc.get("verifica_gerarchie"),
    }
    return {r["player_id"]: r for r in voci}, valore, prova


def primi_di_fatto(rig: dict, players_by_id: dict) -> dict:
    """player_id -> nomi di chi le fonti gli mettono davanti ma oggi è fuori (infortunato,
    squalificato, uscito dal listone). È il primo rigorista disponibile della sua squadra
    quando il primo designato non gioca: al Venezia, con Busio infortunato, per le fonti
    tocca ad Adams A. Chi è pari di rango con lui lo è insieme a lui."""
    per_squadra = defaultdict(list)
    for v in rig.values():
        if v.get("rango"):
            per_squadra[v["squadra"]].append(v)

    def fuori(v):
        p = players_by_id.get(v["player_id"])
        return p is None or p["status"] in EXCLUDED_STATUSES

    eredi = {}
    for voci in per_squadra.values():
        voci.sort(key=lambda v: v["rango"])
        davanti = []
        for v in voci:
            if fuori(v):
                davanti.append(v["nome"])
                continue
            if davanti:
                for w in voci:
                    if w["rango"] == v["rango"] and not fuori(w):
                        eredi[w["player_id"]] = list(davanti)
            break
    return eredi


def prossima_partita_lega(team_id: str) -> dict | None:
    """La prossima partita della lega fantacalcio (`data/lega_competizioni.json`), cioè il
    primo turno non ancora calcolato in cui la squadra gioca, con l'avversario e come sta
    andando. Nel fantacalcio non si massimizza il punteggio: si vince o si perde una
    partita, e i punti diventano gol a scatti. Sapere chi si affronta serve a capire se una
    decisione cambia il risultato. Ritorna None se il calendario non c'è.

    Non esiste un endpoint della classifica: i punti fatti si sommano dalle giornate già
    calcolate (vedi .docs/leghe-fc-api.md)."""
    path = store.DATA_DIR / "lega_competizioni.json"
    if not path.exists():
        return None
    nomi = {t["id"]: t["name"] for t in store.load_json(store.DATA_DIR / "teams.json")}
    for comp in store.load_json(path):
        if comp.get("eliminata"):
            continue
        fatti = defaultdict(lambda: {"punti": 0.0, "giocate": 0, "vinte": 0, "classifica": 0})
        prossima = None
        for giornata in comp.get("calendario", []):
            for partita in giornata.get("partite", []):
                if not giornata.get("calcolata"):
                    if prossima is None and team_id in (partita["casa"], partita["trasferta"]):
                        casa = partita["casa"] == team_id
                        prossima = {
                            "competizione": comp["nome"],
                            "giornata": giornata["giornata"],
                            "giornata_serie_a": giornata["giornata_serie_a"],
                            "casa": casa,
                            "avversario_id": partita["trasferta"] if casa else partita["casa"],
                        }
                    continue
                for chi, punti, cl in (
                    (partita["casa"], partita["punteggio_casa"], partita["punti_classifica_casa"]),
                    (partita["trasferta"], partita["punteggio_trasferta"], partita["punti_classifica_trasferta"]),
                ):
                    d = fatti[chi]
                    d["punti"] += punti
                    d["giocate"] += 1
                    d["classifica"] += cl
        if prossima:
            avv, mio = fatti[prossima["avversario_id"]], fatti[team_id]
            prossima["avversario_nome"] = nomi.get(prossima["avversario_id"], prossima["avversario_id"])
            prossima["avversario"] = dict(avv)
            prossima["mio"] = dict(mio)
            return prossima
    return None


def _role_order(entries: list[dict]) -> list[dict]:
    """Dentro un ruolo conviene mettere avanti chi vale di più quando prende voto, qualunque
    sia la probabilità che giochi: se non scende in campo entra il successivo dello stesso
    ruolo. La probabilità non entra nell'ordine (entra in _scegli_panchina, che decide chi
    occupa i pochi posti in panchina). Chi non ha voti va in fondo, ordinato per
    probabilità di giocare."""
    con_voti = sorted((e for e in entries if e["rating"]), key=lambda e: -e["rating"]["punteggio"])
    senza_voti = sorted(
        (e for e in entries if not e["rating"]),
        key=lambda e: -(e["player"].get("prob_titolare") or 0),
    )
    return con_voti + senza_voti


def prob_voto(entry: dict) -> float:
    """Probabilità (0-1) che il giocatore prenda voto nella prossima giornata.

    È `prob_titolare` di fantacalcio.it, cioè la probabilità di **partire titolare**. Non
    conta chi entra a partita in corso, e non è ancora stata confrontata con chi prende voto
    davvero: se sia più alta o più bassa di quella vera lo dirà la taratura (dalla giornata
    6, con le foto di data/status_scadenze.json). Chi entra a partita in corso, nelle
    giornate 1-5, ha preso voto 256 volte su 358 (72%), quasi sempre da 20 minuti in su e
    quasi mai sotto i 10 (vedi `voto_da_subentrato`). NON è vero che chi entra prende voto
    comunque: la Redazione non ha una soglia di minuti. Usarla così non inventa nessun
    numero, ma gli avvisi di copertura sono stime non verificate.
    Chi non ha il dato prende PROB_VOTO_IGNOTA, che serve solo a confrontare fra loro i
    candidati alla panchina, non a stimare niente su di lui."""
    p = entry["player"].get("prob_titolare")
    if p is None:
        p = PROB_VOTO_IGNOTA
    return min(100.0, max(0.0, float(p))) / 100.0


def voto_da_subentrato(righe: list[dict]) -> tuple[int, int]:
    """(voti presi, ingressi) di chi è entrato a partita in corso con almeno un minuto: quante
    volte chi parte dalla panchina e gioca prende anche voto. Misurato, non assunto."""
    ingressi = [r for r in righe if r.get("subentrato") is True and (r.get("minuti") or 0) > 0]
    return sum(1 for r in ingressi if r.get("fantavoto") is not None), len(ingressi)


def _slot_attesi(candidati: list[dict], n: int, prob=None) -> tuple[float, float]:
    """(valore atteso degli n slot, probabilità che siano tutti coperti).

    `candidati` sono i titolari del ruolo seguiti dalle sue riserve, nell'ordine in cui la
    lega li scorre. Regola della lega: per ogni titolare senza voto entra il primo
    panchinaro **dello stesso ruolo** che ha preso voto; se le riserve del ruolo finiscono,
    lo slot resta scoperto e vale 0.

    Due portieri della stessa squadra di Serie A non possono partire titolari insieme: ne
    gioca uno solo, salvo un cambio del portiere a partita in corso (raro: lì prenderebbero
    voto tutti e due, e il modello lo ignora). Trattarli come indipendenti sottostima la copertura (con
    Martinez 90% e Provedel 5% dell'Inter darebbe 90,5% invece di 95%), e farebbe
    consigliare di cambiare una riserva che invece è quella giusta. Quindi i portieri della
    stessa squadra formano un gruppo a scelta unica: gioca il primo, o il secondo, o nessuno
    dei miei. Per i giocatori di movimento non vale — tre centrocampisti della stessa
    squadra possono partire tutti e tre — e restano indipendenti.

    Dentro un gruppo le quote di `prob_titolare` si dividono per la somma dei portieri
    **disponibili** della squadra (`quota_portieri_squadra`, vedi PORTIERI_QUOTA_MINIMA):
    col 90% di Martinez e il 5% di Provedel la porta è coperta al 99%, non al 95%, perché
    l'unico altro portiere dell'Inter è Di Gennaro all'1%. È una stima, non verificata. Se
    Martinez è fuori e il sito non ha ancora aggiornato le quote, Provedel (5) e Di Gennaro
    (1) si dividono per 6, non per 96: uno dei due deve giocare (prima della seconda
    revisione di Codex la copertura usciva 6%).

    Chi non ha voti vale la sua `stima` (la media del ruolo), non 0: se prende voto il
    fantavoto sarà qualcosa, non niente. È una stima dichiarata, serve al punteggio atteso
    e non all'ordine (chi non ha voti resta in fondo, vedi _role_order). Nel backtest delle
    giornate 3-5 non cambia nessuna scelta: punti identici al centesimo.

    Il 6 politico (partita rinviata) è sicuro: probabilità 1, qualunque sia `prob_titolare`.

    `prob` permette di passare un altro stimatore della probabilità di prendere voto: lo usa
    `backtest_undici.py`, che non può usare `prob_titolare` (fantacalcio.it la pubblica solo
    dal 21/09, dopo le giornate che il backtest deve prevedere) e la stima dalle giornate
    precedenti. Così il backtest collauda queste funzioni, non una loro copia. La divisione
    per i portieri della squadra vale solo per `prob_titolare` (lo stimatore predefinito).

    Enumerazione esatta: i candidati di un ruolo sono al massimo 7 (5 titolari + 2 riserve).
    """
    da_titolarita = prob is None
    prob = prob or prob_voto
    # gruppi a scelta unica (portieri della stessa squadra) e giocatori indipendenti. Chi ha
    # il 6 politico non entra in un gruppo: con la partita rinviata il 6 va a tutti, anche a
    # tutti e due i portieri, e non c'è nessuno "che gioca al posto dell'altro".
    def politico(e):
        return bool(e["rating"] and e["rating"].get("politico"))

    gruppi: list[list[int]] = []
    per_squadra: dict[str, int] = {}
    for i, e in enumerate(candidati):
        if e["player"]["role"] == "P" and not politico(e):
            squadra = e["player"]["serie_a_team"]
            if squadra in per_squadra:
                gruppi[per_squadra[squadra]].append(i)
                continue
            per_squadra[squadra] = len(gruppi)
        gruppi.append([i])

    def valore(e):
        v = _valore(e)
        return v if v is not None else (e.get("stima") or 0.0)

    def probabilita(e):
        return 1.0 if politico(e) else prob(e)

    dati = [(valore(e), probabilita(e)) for e in candidati]
    if da_titolarita:
        for gruppo in gruppi:
            quote = [candidati[i].get("quota_portieri_squadra") for i in gruppo]
            # sotto la quota minima si divide lo stesso se il portiere che manca alla somma è
            # fuori (infortunato, squalificato): allora le quote basse delle riserve sono
            # attese, e una di loro deve giocare
            fuori = any(candidati[i].get("titolare_porta_fuori") for i in gruppo)
            # col titolare fuori si divide anche un portiere da solo: una riserva posseduta
            # senza gli altri portieri della sua squadra (Christensen senza Lezzerini, se
            # De Gea si ferma) al 5% delle quote vecchie è sottostimata, fra i disponibili
            # è 5/6. Col titolare disponibile un portiere da solo resta com'è: lì il 90 del
            # sito è una scala da tarare (vedi prob_voto), non un errore da correggere.
            if ((len(gruppo) > 1 or fuori) and all(q and (q >= PORTIERI_QUOTA_MINIMA or fuori) for q in quote)
                    and all(candidati[i]["player"].get("prob_titolare") is not None for i in gruppo)):
                for i in gruppo:
                    dati[i] = (dati[i][0], min(1.0, candidati[i]["player"]["prob_titolare"] / quote[0]))
    # Ne gioca al massimo uno, quindi le probabilità del gruppo non possono sommare più di 1.
    # Succede se a un portiere manca il dato (PROB_VOTO_IGNOTA, 50%) accanto a un titolare
    # al 90%: senza questo la copertura usciva 140% e il valore gonfiato.
    for gruppo in gruppi:
        totale = sum(dati[i][1] for i in gruppo)
        if len(gruppo) > 1 and totale > 1.0:
            for i in gruppo:
                dati[i] = (dati[i][0], dati[i][1] / totale)

    def casi(k: int):
        """(probabilità, insieme degli indici che prendono voto) per ogni combinazione."""
        if k == len(gruppi):
            yield 1.0, ()
            return
        gruppo = gruppi[k]
        for prob_resto, indici in casi(k + 1):
            if len(gruppo) == 1:
                i = gruppo[0]
                yield prob_resto * dati[i][1], (i,) + indici
                yield prob_resto * (1.0 - dati[i][1]), indici
            else:
                totale = 0.0
                for i in gruppo:  # ne gioca al massimo uno
                    totale += dati[i][1]
                    yield prob_resto * dati[i][1], (i,) + indici
                yield prob_resto * max(0.0, 1.0 - totale), indici

    valore, coperti = 0.0, 0.0
    for probabilita, indici in casi(0):
        if probabilita == 0.0:
            continue
        presi, somma = 0, 0.0
        for i in range(len(dati)):   # si scorre nell'ordine di schieramento
            if presi >= n:
                break
            if i in indici:
                somma += dati[i][0]
                presi += 1
        valore += probabilita * somma
        if presi >= n:
            coperti += probabilita
    return valore, coperti


def _scegli_panchina(ordine: list[dict], n: int, posti: int, prob=None) -> tuple[list[dict], list[dict]]:
    """(titolari, riserve) di un ruolo, dato l'ordine per valore e i posti in panchina.

    I titolari sono i primi `n` per valore: dato l'insieme degli schierati, ordinare per
    valore è ottimo e la probabilità non c'entra. Le **riserve** sono un'altra cosa: la
    panchina ha 1-2 posti per ruolo, quindi un panchinaro che non gioca mai è un posto
    buttato e uno slot che rischia di valere 0. Si prende la combinazione di `posti`
    riserve che massimizza il valore atteso degli slot. Con 6-8 giocatori per ruolo sono
    al massimo 21 combinazioni: si enumerano tutte."""
    titolari, resto = ordine[:n], ordine[n:]
    posti = min(posti, len(resto))
    if posti <= 0:
        return titolari, []
    migliore_chiave, migliori_riserve = None, None
    for combo in combinations(range(len(resto)), posti):
        riserve = [resto[i] for i in combo]
        valore, _ = _slot_attesi(titolari + riserve, n, prob)
        # a pari valore atteso vince la combinazione col valore più alto in panchina:
        # serve solo a rendere la scelta stabile fra giri
        chiave = (valore, sum(_valore(e) or 0.0 for e in riserve))
        if migliore_chiave is None or chiave > migliore_chiave:
            migliore_chiave, migliori_riserve = chiave, riserve
    return titolari, migliori_riserve


def _valore(e: dict) -> float | None:
    return e["rating"]["punteggio"] if e["rating"] else None


def quote_portieri(players_by_id: dict) -> tuple[dict, set]:
    """(squadra -> somma di `prob_titolare` dei suoi portieri DISPONIBILI, squadre col
    TITOLARE fuori), per _slot_attesi. Un titolare fuori non deve restare al denominatore
    delle sue riserve: con Martinez infortunato e le quote non ancora aggiornate, Provedel
    (5) e Di Gennaro (1) davano 6/96 = 6% di copertura.

    "Titolare fuori" vuol dire che i portieri infortunati o squalificati della squadra
    avevano, prima di fermarsi, almeno PORTIERI_QUOTA_MINIMA di quota. Non basta un
    portiere qualsiasi fuori: il 29/09 era infortunato Grabara, una riserva della Juventus,
    e contarlo avrebbe gonfiato da solo il 90% di Vicario."""
    quota, quota_fuori = defaultdict(float), defaultdict(float)
    for q in players_by_id.values():
        if q["role"] != "P" or q.get("prob_titolare") is None:
            continue
        dove = quota_fuori if q["status"] in EXCLUDED_STATUSES else quota
        dove[q["serie_a_team"]] += float(q["prob_titolare"])
    return quota, {sq for sq, v in quota_fuori.items() if v >= PORTIERI_QUOTA_MINIMA}


def scavalcato_di_recente(v: dict) -> list[dict]:
    """Le volte in cui qualcuno che le fonti gli mettono sotto ha calciato mentre lui era in
    campo, dopo il suo ultimo rigore calciato: è il fatto più recente su di lui, e vale più
    di un rigore calciato prima. Vuota se non è mai stato scavalcato, o se ha calciato lui
    dopo."""
    ultimo = v.get("ultimo_rigore") or 0
    return [x for x in v.get("scavalcato_da", [])
            if x["dove"] == "in campo" and (x.get("giornata") or 0) >= ultimo]


def _spareggio_rigorista(a: dict, b: dict, valore: float, prova: dict | None = None) -> str:
    """Se fra due giocatori equivalenti per il modello uno è il primo rigorista della sua
    squadra e l'altro no, lo dice: vale circa `valore` di fantavoto atteso, più della soglia
    dei pari. Avvisa quando il rigore è già dentro la media, per non contarlo due volte.

    Aver calciato un rigore non basta a essere il primo: chi ha calciato perché il primo
    mancava è un sostituto, e chi è stato scavalcato mentre era in campo, dopo il suo ultimo
    rigore, non ha peso finché i rigori non dicono altro. Conta il fatto più recente: un
    rigore da primo alla giornata 5 non cancella uno scavalcamento alla giornata 8."""
    def peso(e):
        """0 = non è il primo rigorista; 1 = lo dicono le fonti (o è il primo disponibile
        perché chi gli sta davanti è fuori); 2 = ha calciato da primo delle fonti."""
        v = e.get("rigorista")
        if not v:
            return 0
        if scavalcato_di_recente(v):
            return 0
        if v.get("conferma") == "confermato":
            return 2
        return 1 if v.get("consenso_sul_primo") or e.get("erede_rigorista") else 0

    pa, pb = peso(a), peso(b)
    if pa == pb:
        return ""
    chi, altro = (a, b) if pa > pb else (b, a)
    voce = chi["rigorista"]
    if max(pa, pb) == 2:
        r = voce["rigori_stagione"]
        testo = (f" Spareggio: {chi['player']['name']} ha calciato {r['calciati']} "
                 f"rigor{'e' if r['calciati'] == 1 else 'i'} quest'anno ({r['segnati']} "
                 f"segnat{'o' if r['segnati'] == 1 else 'i'}), quindi è il rigorista per "
                 "davvero e non per sentito dire.")
        testo += (" Attento: il rigore è già dentro la sua media, quindi il vantaggio è "
                  "minore di quanto sembri.")
    else:
        if chi.get("erede_rigorista"):
            perche = (f"è il primo rigorista disponibile del {voce['squadra']} per le fonti, "
                      f"perché {', '.join(chi['erede_rigorista'])} è fuori")
        else:
            perche = (f"è dato primo rigorista del {voce['squadra']} da "
                      f"{voce.get('fonti_che_lo_danno_primo', 0)} fonti su "
                      f"{voce['fonti_totali_sulla_squadra']}")
        prova = prova or {}
        testo = (f" Spareggio: {chi['player']['name']} {perche}, e varrebbe circa "
                 f"+{valore:.2f} se calcia lui. Quest'anno non ha ancora calciato.")
        if prova.get("primo_ha_calciato") is not None:
            testo += (f" Finora il primo delle fonti ha calciato lui {prova['primo_ha_calciato']} "
                      f"volte ed è stato scavalcato mentre era in campo "
                      f"{prova.get('primo_scavalcato', 0)} volte: i rigori però sono ancora "
                      "pochi, quindi è un'indicazione, non una certezza.")
    return testo


def _decisioni(modulo: str, per_modulo: dict, per_ruolo: dict, riserve: dict,
               valore_rigorista: float = VALORE_PRIMO_RIGORISTA_DEFAULT,
               prova_rigoristi: dict | None = None) -> list[str]:
    """Le scelte che il modello non sa fare meglio di te: coppie entro SOGLIA_PARI al
    confine tra titolari e panchina, o tra i primi due cambi di un ruolo; moduli che
    valgono quasi quanto quello scelto; titolari con pochi dati. Dove i due sono pari,
    guarda se uno dei due è il primo rigorista: quello è uno spareggio vero."""
    decisioni = []
    counts = {"P": 1, **MODULE_ROLE_COUNTS[modulo]}
    for role, n in counts.items():
        ordine = [e for e in per_ruolo[role] if e["rating"] and not e["rating"].get("politico")]
        titolari = [e for e in per_ruolo[role][:n] if e in ordine]
        panchina = [e for e in riserve.get(role, []) if e in ordine]
        if titolari and panchina:
            ultimo, primo = titolari[-1], panchina[0]
            diff = round(_valore(ultimo) - _valore(primo), 2)
            if diff < SOGLIA_PARI:
                decisioni.append(
                    f"[{role}] {ultimo['player']['name']} ({_valore(ultimo):.2f}) titolare o "
                    f"{primo['player']['name']} ({_valore(primo):.2f}) in panchina: differenza {diff:.2f}, "
                    f"sotto la soglia di {SOGLIA_PARI:.2f}. Equivalenti per il modello."
                    + _spareggio_rigorista(ultimo, primo, valore_rigorista, prova_rigoristi)
                )
        if len(panchina) >= 2:
            diff = round(_valore(panchina[0]) - _valore(panchina[1]), 2)
            if diff < SOGLIA_PARI:
                decisioni.append(
                    f"[{role}] Primo cambio: {panchina[0]['player']['name']} ({_valore(panchina[0]):.2f}) o "
                    f"{panchina[1]['player']['name']} ({_valore(panchina[1]):.2f}), differenza {diff:.2f}."
                    + _spareggio_rigorista(panchina[0], panchina[1], valore_rigorista, prova_rigoristi)
                )

    scelto_chiave, scelti = per_modulo[modulo][:2]
    ids_scelti = {e["player"]["id"] for e in scelti}
    for altro, (chiave, titolari, _r) in per_modulo.items():
        if altro == modulo or chiave[:2] != scelto_chiave[:2]:
            continue
        diff = round(chiave[2] - scelto_chiave[2], 2)
        if diff >= SOGLIA_PARI:
            continue
        ids = {e["player"]["id"] for e in titolari}
        entrano = [f"{e['player']['name']} ({e['player']['role']})" for e in titolari if e["player"]["id"] not in ids_scelti]
        escono = [f"{e['player']['name']} ({e['player']['role']})" for e in scelti if e["player"]["id"] not in ids]
        decisioni.append(
            f"Modulo {altro} invece di {modulo}: {diff:.2f} in meno, sotto la soglia. "
            f"Entra{'no' if len(entrano) > 1 else ''} {', '.join(entrano)}; "
            f"esc{'ono' if len(escono) > 1 else 'e'} {', '.join(escono)}."
        )

    for e in scelti:
        r, nome = e["rating"], e["player"]["name"]
        if not r or r.get("politico"):
            continue
        deboli = []
        if r["n"] <= 2:
            deboli.append(f"solo {_n(r['n'], 'voto', 'voti')}: il valore è per {FRENO_VOTI / (r['n'] + FRENO_VOTI):.0%} "
                          f"la media del ruolo")
        prod = r["produzione"]
        # solo se la correzione per la produzione è accesa: spenta, i tiri mancanti non
        # tolgono niente al valore e segnalarli sarebbe un avviso su un difetto inesistente
        if PRODUZIONE_PREDEFINITA and e["player"]["role"] != "P" and (
            prod is None or prod["voti_con_tiri"] < r["n"]
        ):
            senza = r["n"] - (prod["voti_con_tiri"] if prod else 0)
            deboli.append(f"{senza} vot{'o' if senza == 1 else 'i'} su {r['n']} senza tiri da BigBalls, "
                          "correzione per la produzione solo sugli altri")
        if r["contesto"] is None:
            deboli.append("avversario non noto, niente contesto")
        if deboli:
            decisioni.append(f"Dati deboli su {nome}: {'; '.join(deboli)}.")
    return decisioni


def suggest_lineup(team_id: str, allowed_modules: list[str] | None = None) -> dict:
    """Sceglie il modulo con la somma di punteggi più alta tra i titolari (la lega non
    usa il modificatore di difesa). I titolari di ogni ruolo sono i primi per valore; la
    panchina la sceglie _scegli_panchina con la probabilità di prendere voto, perché i posti
    sono pochi e uno slot scoperto vale 0."""
    config = store.load_league_config()
    modules = allowed_modules or config["formation_modules"]
    players_by_id = {p["id"]: p for p in store.load_players()}
    roster, mancanti = team_roster(team_id, players_by_id)
    calendario_path = store.DATA_DIR / "calendario_serie_a.json"
    righe = store.load_matchday_stats()
    calendario = store.load_json(calendario_path) if calendario_path.exists() else []
    modello = costruisci_modello(righe, players_by_id, calendario)
    quota_portieri, titolare_porta_fuori = quote_portieri(players_by_id)

    panchina_cfg = {
        role: int(n)
        for role, n in (config.get("regole_lega", {}).get("panchina") or {}).items()
        if role in ROLES
    }

    avvisi = []
    if not panchina_cfg:
        avvisi.append(
            "regole_lega.panchina non è in config/league.json: la panchina viene stampata "
            "intera invece di essere tagliata ai posti veri. Va scritta, o il consiglio sulla "
            "panchina non è schierabile."
        )
    if mancanti:
        avvisi.append(
            f"{_n(len(mancanti), 'giocatore', 'giocatori')} di ownership.json non più nel listone, fuori dal consiglio: "
            f"{', '.join(mancanti)}"
        )
    attesi = sum(config["roster_requirements"].values())
    if roster and len(roster) + len(mancanti) != attesi:
        avvisi.append(f"La rosa ha {len(roster) + len(mancanti)} giocatori invece di {attesi}.")

    rig, valore_rigorista, prova_rigoristi = rigoristi()
    eredi = primi_di_fatto(rig, players_by_id)
    turno = prossimo_turno()
    if roster and turno["partite"] and not turno["chiaro"]:
        avvisi.append(
            "Il prossimo turno non si ricostruisce dalle date (un recupero, un rinvio, o il "
            "turno è già iniziato): controlla a mano che le squadre dei titolari giochino."
        )

    # Regola della lega sui rinvii, a giornata: fino a max_6 partite rinviate prendono
    # tutte 6 politico; oltre, si aspettano tutte e vale il voto del recupero. In
    # nessuno dei due casi il giocatore va escluso. Il conto è quello di oggi: un rinvio
    # deciso dopo la scadenza della formazione può ancora cambiare la regola.
    max_6 = config.get("regole_lega", {}).get("rinvii", {}).get("max_partite_6_politico", 3)
    rinviate = [m for m in turno["partite"] if m["stato"] == "postponed"] if turno["chiaro"] else []
    sei_politico = len(rinviate) <= max_6
    if roster and rinviate:
        elenco = ", ".join(f"{m['squadra_casa']}-{m['squadra_trasferta']}" for m in rinviate)
        if sei_politico:
            avvisi.append(
                f"{_n(len(rinviate), 'partita rinviata', 'partite rinviate')} nel turno ({elenco}): "
                f"fino a {max_6} prendono tutti 6 politico, contato come 6 nell'ordine."
            )
        else:
            avvisi.append(
                f"{len(rinviate)} partite rinviate nel turno ({elenco}): più di {max_6}, quindi tutte "
                "si recuperano e vale il voto del recupero. I giocatori restano ordinati per media."
            )
        if len(rinviate) == max_6:
            avvisi.append(
                "Un altro rinvio in questa giornata, anche dopo la scadenza, fa passare tutte le "
                "partite rinviate al voto del recupero: niente più 6 politico."
            )

    non_disponibili = []
    per_ruolo = {role: [] for role in ROLES}
    for p in roster:
        partita = turno["per_squadra"].get(p["serie_a_team"])
        # Con la partita rinviata e il 6 politico, il 6 va a tutta la rosa, infortunati e
        # squalificati compresi (regolamento ufficiale di fantacalcio.it): non si escludono.
        politico = partita in rinviate and sei_politico
        if p["status"] in EXCLUDED_STATUSES and not politico:
            non_disponibili.append({"player": p, "motivo": p.get("status_note") or p["status"]})
            continue
        avversario = None
        if partita:
            casa = partita["squadra_casa"] == p["serie_a_team"]
            avversario = partita["squadra_trasferta"] if casa else partita["squadra_casa"]
        rating = rate_player(p, modello, avversario)
        if politico:
            # Il 6 è sicuro e non lascia il posto alla panchina: vale 6, non la media.
            rating = {"media": 6.0, "n": 0, "punteggio": 6.0, "politico": True}
        # quanti rigori ha già calciato in queste giornate: serve a non contare due volte
        # il valore del rigorista (il box score ne ha pochi, quindi è un minimo)
        calciati = sum(
            (r.get("rigori_segnati") or 0) + (r.get("rigori_sbagliati") or 0)
            for r in modello["per_giocatore"].get(p["id"], [])
        )
        per_ruolo[p["role"]].append({
            "player": p,
            "rating": rating,
            # chi non ha voti entra nel punteggio atteso con la media del ruolo: una stima
            # dichiarata, non un dato (vedi _slot_attesi)
            "stima": None if rating else modello["media_ruolo"].get(p["role"]),
            "quota_portieri_squadra": quota_portieri.get(p["serie_a_team"]) if p["role"] == "P" else None,
            "titolare_porta_fuori": p["role"] == "P" and p["serie_a_team"] in titolare_porta_fuori,
            "partita": partita,
            "rigorista": rig.get(p["id"]),
            "erede_rigorista": eredi.get(p["id"]),
            "rigori_calciati": calciati,
        })
    per_ruolo = {role: _role_order(entries) for role, entries in per_ruolo.items()}

    risultato = {
        "modulo": None,
        "titolari": [],
        "panchina": [e for role in ROLES for e in per_ruolo[role]],
        "non_disponibili": non_disponibili,
        "esclusi": [],
        "copertura": {},
        "atteso": None,
        "panchina_cfg": panchina_cfg,
        "valore_rigorista": valore_rigorista,
        "prova_rigoristi": prova_rigoristi,
        "turno": turno,
        "scoperti": {},
        "avvisi": avvisi,
        "decisioni": [],
        "stimati": [],
    }
    if not roster:
        avvisi.append(f"Nessun giocatore in ownership.json per la squadra {team_id}.")
        return risultato
    if not any(e["rating"] and not e["rating"].get("politico") for entries in per_ruolo.values() for e in entries):
        avvisi.append(
            "Nessun giocatore della rosa ha ancora un voto: il motore non può consigliare "
            "una formazione finché non arrivano i voti. Sotto, la rosa per ruolo."
        )
        return risultato

    best = None
    per_modulo = {}
    for module in modules:
        counts = {"P": 1, **MODULE_ROLE_COUNTS[module]}
        titolari, riserve, scoperti, copertura, atteso = [], {}, {}, {}, 0.0
        for role, n in counts.items():
            posti = panchina_cfg[role] if panchina_cfg else max(0, len(per_ruolo[role]) - n)
            in_campo, in_panchina = _scegli_panchina(per_ruolo[role], n, posti)
            titolari.extend(in_campo)
            riserve[role] = in_panchina
            if len(per_ruolo[role]) < n:
                scoperti[role] = n - len(per_ruolo[role])
            valore, coperto = _slot_attesi(in_campo + in_panchina, n)
            atteso += valore
            copertura[role] = coperto
        # Prima i moduli che si riempiono tutti, poi quelli con meno titolari senza voti da
        # decidere a mano, poi la somma dei valori dei titolari.
        # PERCHÉ NON IL VALORE ATTESO, che sarebbe l'obiettivo giusto: provato, e nel
        # backtest in punti non ha mostrato guadagni contro la somma semplice (+0,12 [−0,64,
        # +0,94] il 29/09: indistinguibile, cioè né dimostrato né smentito). La regola del
        # progetto: nessun cambiamento senza un guadagno con intervallo che esclude lo zero.
        # E il punteggio atteso che userebbe è distorto: nel backtest sottostima i punti veri
        # di quasi 6 (lib/simulazione.py). Attenzione a non dare la colpa a `prob_titolare`:
        # il backtest non la usa (non esisteva per quelle giornate), usa la quota storica di
        # voti presi. Il valore atteso resta calcolato, ma serve agli avvisi di copertura e
        # al punteggio atteso del report. Da riprovare quando la probabilità di prendere voto
        # sarà misurata invece che approssimata (vedi prob_voto), con più giornate.
        chiave = (sum(scoperti.values()), sum(1 for e in titolari if not e["rating"]),
                  -sum(e["rating"]["punteggio"] for e in titolari if e["rating"]))
        per_modulo[module] = (chiave, titolari, riserve)
        if best is None or chiave < best[0]:
            best = (chiave, module, titolari, riserve, scoperti, copertura, atteso)

    _, module, titolari, riserve, scoperti, copertura, atteso = best
    risultato["atteso"] = atteso   # valore atteso degli 11 slot, per le soglie gol del report
    panchina = [e for role in ROLES for e in riserve.get(role, [])]
    risultato["stimati"] = [e for e in titolari + panchina if not e["rating"] and e.get("stima") is not None]
    # Il secondo portiere della stessa squadra del titolare: ne gioca uno solo (salvo un cambio
    # del portiere a partita in corso), quindi l'ordine fra i due non cambia quasi mai il
    # punteggio, e "nessun voto" vuol dire solo che finora in porta è
    # andato l'altro. Non è un giudizio sul giocatore, e non c'è niente da decidere.
    portiere = next((e for e in titolari if e["player"]["role"] == "P"), None)
    for e in riserve.get("P", []):
        if portiere and e["player"]["serie_a_team"] == portiere["player"]["serie_a_team"]:
            e["riserva_di"] = portiere["player"]["name"]
    in_distinta = {e["player"]["id"] for e in titolari + panchina}
    risultato.update(
        modulo=module,
        titolari=titolari,
        panchina=panchina,
        esclusi=[e for role in ROLES for e in per_ruolo[role] if e["player"]["id"] not in in_distinta],
        scoperti=scoperti,
        copertura=copertura,
    )
    risultato["decisioni"] = _decisioni(module, per_modulo, per_ruolo, riserve, valore_rigorista,
                                        prova_rigoristi)

    # Avvisi sulla panchina corta: è la novità del 27/09 e il posto dove si perdono punti
    # senza accorgersene (7 slot scoperti su 396 nel backtest, circa 1,2 punti a giornata).
    presi, ingressi = voto_da_subentrato(righe)
    testo_subentrati = (f"chi entra prende voto {presi} volte su {ingressi} finora ({presi / ingressi:.0%}), "
                        "quasi sempre se gioca almeno 20 minuti" if ingressi else
                        "quanti di loro prendano voto non è ancora misurato")
    for role, n in {"P": 1, **MODULE_ROLE_COUNTS[module]}.items():
        coperto = copertura.get(role)
        if coperto is None or coperto >= SOGLIA_AVVISO_COPERTURA:
            continue
        nomi = ", ".join(e["player"]["name"] for e in riserve.get(role, [])) or "nessuna"
        avvisi.append(
            f"Ruolo {role}: {1 - coperto:.0%} di rischio che uno slot resti vuoto, e uno slot "
            f"vuoto vale 0 (circa 6 punti persi). Riserve in panchina: {nomi}. "
            "È una stima: usa la probabilità di partire titolare, che non conta chi entra a "
            f"partita in corso ({testo_subentrati}) e non è ancora stata confrontata con chi ha "
            "preso voto davvero."
        )
    # Una riserva che non gioca quasi mai è un posto di panchina buttato — ma solo se in rosa
    # c'è un'alternativa dello stesso ruolo che gioca di più. Il secondo portiere della tua
    # stessa squadra di Serie A è al 5% e va benissimo lì: se il primo non gioca, gioca lui.
    fuori_per_ruolo = defaultdict(list)
    for e in risultato["esclusi"]:
        fuori_per_ruolo[e["player"]["role"]].append(e)
    inutili = []
    for e in panchina:
        prob = prob_voto(e) * 100
        if prob >= PROB_RISERVA_INUTILE:
            continue
        meglio = [a for a in fuori_per_ruolo[e["player"]["role"]] if prob_voto(a) * 100 > prob]
        if meglio:
            alternative = ", ".join(
                f"{a['player']['name']} ({prob_voto(a) * 100:.0f}%)" for a in meglio[:3]
            )
            inutili.append(f"{e['player']['name']} ({prob:.0f}%), al suo posto {alternative}")
    if inutili:
        avvisi.append(
            "Riserve che difficilmente giocheranno, con un'alternativa dello stesso ruolo che "
            f"gioca di più: {'; '.join(inutili)}. Il valore atteso le preferisce lo stesso, ma "
            "con pochi posti in panchina la scelta è tua."
        )
    for role, n in scoperti.items():
        avvisi.append(f"Ruolo {role}: manca{'' if n == 1 else 'no'} {_n(n, 'giocatore disponibile', 'giocatori disponibili')}, nessun modulo lo copre.")
    senza_voti = [e["player"]["name"] for e in titolari if not e["rating"]]
    if senza_voti:
        avvisi.append(f"Titolari senza nessun voto, da decidere a mano: {', '.join(senza_voti)}.")
    # Chi non ha voti va in fondo all'ordine: il modello non sa quanto vale, e metterlo
    # davanti con una stima porterebbe Provedel (media del ruolo 4,70) davanti a Martinez
    # (4,54), o una riserva che non gioca mai davanti a un titolare. Ma un acquisto nuovo o
    # un rientrante che le probabili danno titolare può restare fuori per questo: si avvisa.
    probabili_titolari = [
        e for e in panchina + risultato["esclusi"]
        if not e["rating"] and not e.get("riserva_di")
        and (e["player"].get("prob_titolare") or 0) >= PROB_TITOLARE_SENZA_VOTI
    ]
    if probabili_titolari:
        nomi = ", ".join(f"{e['player']['name']} ({e['player']['prob_titolare']}%)" for e in probabili_titolari)
        avvisi.append(
            f"Senza voti ma dati titolari dalle probabili, e per questo non in campo: {nomi}. Il "
            "modello non sa quanto valgono e li mette in fondo: decidi con le notizie se schierarli."
        )
    squalifiche_path = store.DATA_DIR / "squalifiche.json"
    diffidati = {
        s["player_id"]
        for s in (store.load_json(squalifiche_path) if squalifiche_path.exists() else [])
        if s["tipo"] == "diffidato"
    }
    nomi_diffidati = [e["player"]["name"] for e in titolari if e["player"]["id"] in diffidati]
    if nomi_diffidati:
        avvisi.append(
            f"Diffidati tra i titolari: {', '.join(nomi_diffidati)}. Con un'ammonizione "
            "saltano la giornata successiva."
        )
    fuori_probabili = [
        e["player"]["name"] for e in titolari
        if e["player"]["status"] == "n/d" and "non trovato nelle probabili" in (e["player"].get("status_note") or "")
    ]
    if fuori_probabili:
        avvisi.append(
            f"Titolari che non compaiono nelle probabili (assenti, o nome scritto diversamente): "
            f"{', '.join(fuori_probabili)}. Verifica prima della deadline."
        )
    oggi = date.today()
    vecchi = []
    for e in titolari:
        agg = e["player"].get("status_updated_at")
        if agg and (oggi - date.fromisoformat(agg)).days > STATUS_VECCHIO_GIORNI:
            vecchi.append(f"{e['player']['name']} ({agg})")
    if vecchi and len(vecchi) == len(titolari):
        avvisi.append(
            f"Lo status di tutti i titolari è più vecchio di {STATUS_VECCHIO_GIORNI} giorni. "
            "La routine del mattino sta girando?"
        )
    elif vecchi:
        avvisi.append(f"Status più vecchio di {STATUS_VECCHIO_GIORNI} giorni: {', '.join(vecchi)}.")
    return risultato
