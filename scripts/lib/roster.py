from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from statistics import mean

from . import store

EXCLUDED_STATUSES = {"infortunato", "squalificato"}
ROLES = ["P", "D", "C", "A"]
# Oltre questa età lo status di un titolare va ricontrollato: con la routine del
# mattino dovrebbe avere al massimo un giorno.
STATUS_VECCHIO_GIORNI = 4

# Il valore di un giocatore è quello che ci si aspetta dal suo fantavoto nella prossima
# partita, *se prende voto* (con i cambi illimitati è il criterio giusto per ordinare:
# vedi .docs/difetti-consiglio-formazione.md). È fatto di tre pezzi, ognuno verificato
# con scripts/backtest_formazione.py (prevedere la giornata N con i dati fino a N-1):
#   base      media degli ultimi voti, frenata verso la media del ruolo;
#   produzione nei voti della base, i gol su azione sostituiti da quelli attesi dai tiri
#              in porta (chi tira tanto e non segna sale, chi segna con un tiro scende);
#   contesto  quanto subisce l'avversario della prossima partita.
# Provati e scartati perché non migliorano le previsioni (numeri nel doc): l'a priori
# dalla quotazione iniziale al posto della media del ruolo, il valore separato da
# titolare e da subentrato, il fattore campo, il freno stimato ruolo per ruolo.

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
    produzione: bool = True,
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


def _role_order(entries: list[dict]) -> list[dict]:
    """Con sostituzioni illimitate nello stesso ruolo conviene mettere avanti chi ha
    la media più alta quando gioca, qualunque sia la probabilità che giochi: se non
    scende in campo entra il successivo. La probabilità non entra nell'ordine.
    Chi non ha voti va in fondo, ordinato per probabilità di giocare."""
    con_voti = sorted((e for e in entries if e["rating"]), key=lambda e: -e["rating"]["punteggio"])
    senza_voti = sorted(
        (e for e in entries if not e["rating"]),
        key=lambda e: -(e["player"].get("prob_titolare") or 0),
    )
    return con_voti + senza_voti


def _valore(e: dict) -> float | None:
    return e["rating"]["punteggio"] if e["rating"] else None


def _decisioni(modulo: str, per_modulo: dict, per_ruolo: dict) -> list[str]:
    """Le scelte che il modello non sa fare meglio di te: coppie entro SOGLIA_PARI al
    confine tra titolari e panchina, o tra i primi due cambi di un ruolo; moduli che
    valgono quasi quanto quello scelto; titolari con pochi dati."""
    decisioni = []
    counts = {"P": 1, **MODULE_ROLE_COUNTS[modulo]}
    for role, n in counts.items():
        ordine = [e for e in per_ruolo[role] if e["rating"] and not e["rating"].get("politico")]
        titolari = [e for e in per_ruolo[role][:n] if e in ordine]
        panchina = [e for e in per_ruolo[role][n:] if e in ordine]
        if titolari and panchina:
            ultimo, primo = titolari[-1], panchina[0]
            diff = round(_valore(ultimo) - _valore(primo), 2)
            if diff < SOGLIA_PARI:
                decisioni.append(
                    f"[{role}] {ultimo['player']['name']} ({_valore(ultimo):.2f}) titolare o "
                    f"{primo['player']['name']} ({_valore(primo):.2f}) in panchina: differenza {diff:.2f}, "
                    f"sotto la soglia di {SOGLIA_PARI:.2f}. Equivalenti per il modello."
                )
        if len(panchina) >= 2:
            diff = round(_valore(panchina[0]) - _valore(panchina[1]), 2)
            if diff < SOGLIA_PARI:
                decisioni.append(
                    f"[{role}] Primo cambio: {panchina[0]['player']['name']} ({_valore(panchina[0]):.2f}) o "
                    f"{panchina[1]['player']['name']} ({_valore(panchina[1]):.2f}), differenza {diff:.2f}."
                )

    scelto_chiave, scelti = per_modulo[modulo]
    ids_scelti = {e["player"]["id"] for e in scelti}
    for altro, (chiave, titolari) in per_modulo.items():
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
        if e["player"]["role"] != "P" and (prod is None or prod["voti_con_tiri"] < r["n"]):
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
    usa il modificatore di difesa) e ordina la panchina ruolo per ruolo con lo stesso
    criterio dei titolari, perché è lei a coprire chi non prende voto."""
    config = store.load_league_config()
    modules = allowed_modules or config["formation_modules"]
    players_by_id = {p["id"]: p for p in store.load_players()}
    roster, mancanti = team_roster(team_id, players_by_id)
    calendario_path = store.DATA_DIR / "calendario_serie_a.json"
    modello = costruisci_modello(
        store.load_matchday_stats(),
        players_by_id,
        store.load_json(calendario_path) if calendario_path.exists() else [],
    )

    avvisi = []
    if mancanti:
        avvisi.append(
            f"{_n(len(mancanti), 'giocatore', 'giocatori')} di ownership.json non più nel listone, fuori dal consiglio: "
            f"{', '.join(mancanti)}"
        )
    attesi = sum(config["roster_requirements"].values())
    if roster and len(roster) + len(mancanti) != attesi:
        avvisi.append(f"La rosa ha {len(roster) + len(mancanti)} giocatori invece di {attesi}.")

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
        if p["status"] in EXCLUDED_STATUSES:
            non_disponibili.append({"player": p, "motivo": p.get("status_note") or p["status"]})
            continue
        avversario = None
        if partita:
            casa = partita["squadra_casa"] == p["serie_a_team"]
            avversario = partita["squadra_trasferta"] if casa else partita["squadra_casa"]
        rating = rate_player(p, modello, avversario)
        if partita in rinviate and sei_politico:
            # Il 6 è sicuro e non lascia il posto alla panchina: vale 6, non la media.
            rating = {"media": 6.0, "n": 0, "punteggio": 6.0, "politico": True}
        per_ruolo[p["role"]].append({"player": p, "rating": rating, "partita": partita})
    per_ruolo = {role: _role_order(entries) for role, entries in per_ruolo.items()}

    risultato = {
        "modulo": None,
        "titolari": [],
        "panchina": [e for role in ROLES for e in per_ruolo[role]],
        "non_disponibili": non_disponibili,
        "turno": turno,
        "scoperti": {},
        "avvisi": avvisi,
        "decisioni": [],
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
        titolari, scoperti = [], {}
        for role, n in counts.items():
            titolari.extend(per_ruolo[role][:n])
            if len(per_ruolo[role]) < n:
                scoperti[role] = n - len(per_ruolo[role])
        # Prima i moduli che si riempiono tutti, poi quelli con meno titolari senza
        # voti da decidere a mano, poi la somma dei punteggi più alta.
        chiave = (
            sum(scoperti.values()),
            sum(1 for e in titolari if not e["rating"]),
            -sum(e["rating"]["punteggio"] for e in titolari if e["rating"]),
        )
        per_modulo[module] = (chiave, titolari)
        if best is None or chiave < best[0]:
            best = (chiave, module, titolari, scoperti)

    _, module, titolari, scoperti = best
    in_campo = {e["player"]["id"] for e in titolari}
    risultato.update(
        modulo=module,
        titolari=titolari,
        panchina=[e for role in ROLES for e in per_ruolo[role] if e["player"]["id"] not in in_campo],
        scoperti=scoperti,
    )
    risultato["decisioni"] = _decisioni(module, per_modulo, per_ruolo)
    for role, n in scoperti.items():
        avvisi.append(f"Ruolo {role}: manca{'' if n == 1 else 'no'} {_n(n, 'giocatore disponibile', 'giocatori disponibili')}, nessun modulo lo copre.")
    senza_voti = [e["player"]["name"] for e in titolari if not e["rating"]]
    if senza_voti:
        avvisi.append(f"Titolari senza nessun voto, da decidere a mano: {', '.join(senza_voti)}.")
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
