#!/usr/bin/env python3
"""Backtest del valore dei giocatori (scripts/lib/roster.py): per ogni giornata N >= 3
prevede il fantavoto di chi ha preso voto usando solo i dati fino alla giornata N-1, e
confronta con quello vero.

Metriche:
- errore medio assoluto (MAE) sul fantavoto, sulle righe dei giocatori che avevano già
  almeno un voto (senza voti il modello non stima niente, per scelta);
- ordine giusto: tra due giocatori dello stesso ruolo e della stessa squadra della lega
  che hanno preso voto nella stessa giornata, quante volte il modello mette davanti chi
  poi ha fatto di più (le coppie a pari fantavoto non contano).
Gli intervalli al 95% sono bootstrap appaiati: per il MAE si ricampionano i giocatori,
per l'ordine le coppie (squadra della lega, giornata).

Cosa il backtest NON può fare, e perché:
- la probabilità di titolarità di fantacalcio.it esiste solo dal 21/09 (primo snapshot di
  data/formazioni_history.json), dopo la giornata 5: non c'è per nessuna giornata da
  prevedere. La variante "titolare/spezzone" usa quindi la quota di presenze da
  subentrato del giocatore nelle giornate precedenti;
- la quotazione iniziale (QI) è fissata prima della stagione: usarla non bara. La
  quotazione attuale e l'FVM invece contengono le giornate giocate e non si usano.

Uso:
    python3 scripts/backtest_formazione.py
    python3 scripts/backtest_formazione.py --dal 3 --bootstrap 2000
    python3 scripts/backtest_formazione.py --descrittive   # i fatti citati nel doc
"""
import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib.roster import CONTESTO_FRENO_PARTITE, FRENO_VOTI, SOGLIA_PARI, _retta, costruisci_modello, rate_player

ROLES = "PDCA"


# --- Varianti scartate: non stanno in roster.py, si calcolano qui sopra il modello ---

def _somma_corretti(r: dict, k: float) -> float:
    return r["base"] * (r["n"] + k) - k * r["riferimento"]


def variante_freno_stimato(modello: dict, players: dict, **_) -> dict:
    """Freno per ruolo stimato sui dati (metodo dei momenti): varianza dei voti dentro
    il giocatore diviso varianza vera tra giocatori. Se la seconda esce <= 0 il freno
    diventa enorme (vale solo la media del ruolo)."""
    k = {}
    for ruolo in ROLES:
        gruppi = [
            [modello["corretto"](x) for x in rr]
            for pid, rr in modello["per_giocatore"].items() if players[pid]["role"] == ruolo
        ]
        doppi = [g for g in gruppi if len(g) >= 2]
        if not doppi:
            k[ruolo] = FRENO_VOTI
            continue
        s2 = sum((y - mean(g)) ** 2 for g in doppi for y in g) / sum(len(g) - 1 for g in doppi)
        tutti = mean(y for g in gruppi for y in g)
        tau2 = mean((mean(g) - tutti) ** 2 for g in gruppi) - mean(s2 / len(g) for g in gruppi)
        k[ruolo] = s2 / tau2 if tau2 > 0 else 1e6
    return k


def variante_apriori_qi(modello: dict, players: dict, **_) -> dict:
    """Riferimento del freno dalla quotazione iniziale: retta fantavoto ~ QI per ruolo."""
    retta = {}
    for ruolo in ROLES:
        righe = [x for pid, rr in modello["per_giocatore"].items() if players[pid]["role"] == ruolo for x in rr]
        xs = [players[x["player_id"]]["quotazione_iniziale"] or 0 for x in righe]
        ys = [modello["corretto"](x) for x in righe]
        b = _retta(xs, ys)
        retta[ruolo] = (mean(ys) - b * mean(xs), b)
    return retta


def variante_spezzone(modello: dict, players: dict, **_) -> dict:
    """Effetto del subentrare sul fantavoto dello stesso giocatore (scarto dalla sua media,
    subentrato meno titolare), per ruolo, e quota di presenze da subentrato del ruolo."""
    effetto, quota = {}, {}
    for ruolo in ROLES:
        sub, tit, flag = [], [], []
        for pid, rr in modello["per_giocatore"].items():
            if players[pid]["role"] != ruolo:
                continue
            rr = [x for x in rr if x.get("subentrato") is not None]
            flag += [x["subentrato"] for x in rr]
            if len(rr) < 2:
                continue
            m = mean(modello["corretto"](x) for x in rr)
            for x in rr:
                (sub if x["subentrato"] else tit).append(modello["corretto"](x) - m)
        effetto[ruolo] = mean(sub) - mean(tit) if sub and tit else 0.0
        quota[ruolo] = sum(flag) / len(flag) if flag else 0.0
    return {"effetto": effetto, "quota": quota}


def variante_casa(modello: dict, players: dict, **_) -> float:
    """Di quanto sale il fantavoto in casa rispetto alla media del giocatore (un
    coefficiente per tutti: +1 casa, -1 trasferta)."""
    xs, ys = [], []
    for rr in modello["per_giocatore"].values():
        if len(rr) < 2:
            continue
        m = mean(modello["corretto"](x) for x in rr)
        for x in rr:
            xs.append(1.0 if x["home_away"] == "casa" else -1.0)
            ys.append(modello["corretto"](x) - m)
    return _retta(xs, ys)


def variante_portieri_fatti(modello: dict, players: dict, calendario: list, giornata: int, **_) -> dict:
    """Per i portieri il contesto con i gol *fatti* dall'avversario invece di quelli
    subiti: è l'attacco avversario che fa prendere gol al portiere. Stesso metodo del
    contesto di roster.py (freno verso la media del campionato, beta sugli scarti del
    portiere dalla sua media, gol fatti calcolati senza quella partita). Il 27/09, su 55
    previsioni di portieri, non si distingueva dai gol subiti: da riguardare con più voti."""
    fatti = defaultdict(dict)  # squadra -> match_id -> gol fatti
    for m in calendario:
        if m["stato"] == "finished" and m.get("gol_casa") is not None and m.get("giornata") is not None \
                and m["giornata"] < giornata:
            fatti[m["squadra_casa"]][m["match_id"]] = m["gol_casa"]
            fatti[m["squadra_trasferta"]][m["match_id"]] = m["gol_trasferta"]
    tutti = [g for d in fatti.values() for g in d.values()]
    media = mean(tutti) if tutti else 0.0

    def scarto(squadra: str, senza: str | None = None) -> float:
        g = [x for mid, x in fatti.get(squadra, {}).items() if mid != senza]
        return (sum(g) + CONTESTO_FRENO_PARTITE * media) / (len(g) + CONTESTO_FRENO_PARTITE) - media

    xs, ys = [], []
    for pid, rr in modello["per_giocatore"].items():
        if players[pid]["role"] != "P" or len(rr) < 2:
            continue
        m = mean(x["fantavoto"] for x in rr)
        for x in rr:
            xs.append(scarto(x["opponent_serie_a_team"], senza=x["match_id"]))
            ys.append(x["fantavoto"] - m)
    return {"beta": _retta(xs, ys) if len(xs) >= 2 else 0.0, "scarto": scarto}


def prevedi(conf: dict, modello: dict, extra: dict, player: dict, riga: dict) -> float | None:
    r = rate_player(player, modello, riga["opponent_serie_a_team"])
    if r is None:
        return None
    ruolo, n, k = player["role"], r["n"], modello["freno"]
    somma = _somma_corretti(r, k)
    riferimento = r["riferimento"]
    if "apriori_qi" in extra:
        a, b = extra["apriori_qi"][ruolo]
        riferimento = a + b * (player["quotazione_iniziale"] or 0)
    if "freno_stimato" in extra:
        k = extra["freno_stimato"][ruolo]
    if "spezzone" in extra:
        eff = extra["spezzone"]["effetto"][ruolo]
        rr = modello["per_giocatore"][player["id"]][-n:]
        somma -= eff * sum(1 for x in rr if x.get("subentrato"))
        flag = [x["subentrato"] for x in modello["per_giocatore"][player["id"]] if x.get("subentrato") is not None]
        quota = (sum(flag) + 2 * extra["spezzone"]["quota"][ruolo]) / (len(flag) + 2)
        if "oracolo" in extra and riga.get("subentrato") is not None:
            quota = 1.0 if riga["subentrato"] else 0.0  # bara apposta: sa se partirà titolare
        valore = (somma + k * riferimento) / (n + k) + eff * quota
    else:
        valore = (somma + k * riferimento) / (n + k)
    if "portieri_fatti" in extra and ruolo == "P":
        v = extra["portieri_fatti"]
        valore += v["beta"] * v["scarto"](riga["opponent_serie_a_team"])
    elif r["contesto"]:
        valore += r["contesto"]["effetto"]
    if "casa" in extra:
        valore += extra["casa"] * (1.0 if riga["home_away"] == "casa" else -1.0)
    return valore


NUOVO = f"NUOVO: produzione + contesto, freno {FRENO_VOTI}"
CONFIGURAZIONI = [
    # nome, parametri di costruisci_modello, varianti scartate
    ("attuale (27/09): media ruolo, freno 3", dict(produzione=False, contesto=False, freno=3), ()),
    ("attuale con freno 5", dict(produzione=False, contesto=False, freno=5), ()),
    (f"freno {FRENO_VOTI} + contesto", dict(produzione=False, contesto=True), ()),
    (f"freno {FRENO_VOTI} + produzione", dict(produzione=True, contesto=False), ()),
    (NUOVO, dict(produzione=True, contesto=True), ()),
    ("nuovo, freno 1", dict(produzione=True, contesto=True, freno=1), ()),
    ("nuovo, freno 3", dict(produzione=True, contesto=True, freno=3), ()),
    ("nuovo, freno 10", dict(produzione=True, contesto=True, freno=10), ()),
    ("nuovo, produzione a metà peso", dict(produzione=True, contesto=True, peso_produzione=0.5), ()),
    ("nuovo + freno stimato per ruolo", dict(produzione=True, contesto=True), ("freno_stimato",)),
    ("nuovo + a priori da QI", dict(produzione=True, contesto=True), ("apriori_qi",)),
    ("nuovo + titolare/spezzone", dict(produzione=True, contesto=True), ("spezzone",)),
    ("nuovo + titolare/spezzone ORACOLO (bara)", dict(produzione=True, contesto=True), ("spezzone", "oracolo")),
    ("nuovo + casa/trasferta", dict(produzione=True, contesto=True), ("casa",)),
    ("nuovo, portieri con gol fatti avversario", dict(produzione=True, contesto=True), ("portieri_fatti",)),
    ("attuale + a priori da QI + freno stimato", dict(produzione=False, contesto=False, freno=3), ("apriori_qi", "freno_stimato")),
]
VARIANTI = {
    "freno_stimato": variante_freno_stimato,
    "apriori_qi": variante_apriori_qi,
    "spezzone": variante_spezzone,
    "casa": variante_casa,
    "portieri_fatti": variante_portieri_fatti,
    "oracolo": lambda modello, players, **_: True,
}


def esegui(conf, righe, players, calendario, giornate, own):
    """Ritorna errori [(player_id, giornata, errore)], coppie per cluster
    {(squadra lega, giornata): [giuste, totali]}, e le previsioni [(riga, previsione)]."""
    nome, parametri, varianti = conf
    errori, coppie, previsioni = [], defaultdict(lambda: [0, 0]), []
    for g in giornate:
        modello = costruisci_modello(righe, players, calendario, prima_di_giornata=g, **parametri)
        extra = {v: VARIANTI[v](modello, players, calendario=calendario, giornata=g) for v in varianti}
        prev = []
        for riga in righe:
            if riga["matchday"] != g or riga.get("fantavoto") is None or riga["player_id"] not in players:
                continue
            p = prevedi(conf, modello, extra, players[riga["player_id"]], riga)
            if p is None:
                continue
            prev.append((riga, p))
            errori.append((riga["player_id"], g, abs(p - riga["fantavoto"])))
        previsioni += prev
        for i in range(len(prev)):
            for j in range(i + 1, len(prev)):
                (ri, pi), (rj, pj) = prev[i], prev[j]
                squadra = own.get(ri["player_id"])
                if (
                    not squadra or squadra != own.get(rj["player_id"])
                    or players[ri["player_id"]]["role"] != players[rj["player_id"]]["role"]
                    or ri["fantavoto"] == rj["fantavoto"] or pi == pj
                ):
                    continue
                c = coppie[(squadra, g)]
                c[0] += (pi > pj) == (ri["fantavoto"] > rj["fantavoto"])
                c[1] += 1
    return errori, coppie, previsioni


def bootstrap_mae(e0, e1, n, seed):
    """Differenza di MAE (e0 - e1, positivo = e1 migliore) con IC 95%, ricampionando giocatori."""
    base = {(p, g): x for p, g, x in e0}
    per_giocatore = defaultdict(list)
    for p, g, x in e1:
        if (p, g) in base:
            per_giocatore[p].append(base[(p, g)] - x)
    ids = sorted(per_giocatore)
    oss = sum(sum(v) for v in per_giocatore.values()) / sum(len(v) for v in per_giocatore.values())
    rnd = random.Random(seed)
    stime = []
    for _ in range(n):
        campione = [per_giocatore[rnd.choice(ids)] for _ in ids]
        stime.append(sum(sum(v) for v in campione) / sum(len(v) for v in campione))
    stime.sort()
    return oss, stime[int(0.025 * n)], stime[int(0.975 * n) - 1]


def bootstrap_ordine(c0, c1, n, seed):
    chiavi = sorted(set(c0) | set(c1))

    def quota(c, ks):
        tot = sum(c[k][1] for k in ks)
        return sum(c[k][0] for k in ks) / tot if tot else 0.0

    oss = quota(c1, chiavi) - quota(c0, chiavi)
    rnd = random.Random(seed)
    stime = sorted(
        quota(c1, s) - quota(c0, s) for s in ([rnd.choice(chiavi) for _ in chiavi] for _ in range(n))
    )
    return oss, stime[int(0.025 * n)], stime[int(0.975 * n) - 1]


def _correlazione(xs, ys):
    mx, my = mean(xs), mean(ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5


def descrittive(righe, players):
    """I fatti sui dati di tutta la stagione che la revisione del 27/09 cita. Guardano
    indietro (non sono previsioni): servono a capire, non a scegliere il modello."""
    voti = [r for r in righe if r.get("fantavoto") is not None and r["player_id"] in players]
    ruolo = lambda r: players[r["player_id"]]["role"]
    per_g = defaultdict(list)
    for r in voti:
        per_g[r["player_id"]].append(r)
    print("\nDESCRITTIVE (tutte le giornate, guardando indietro)")

    def m(xs):
        return f"{mean(xs):.2f} ({len(xs)})" if xs else "-"

    print("Fantavoto medio per ruolo: per numero di voti del giocatore, per minuti, titolare/subentrato.")
    for r_ in "DCA":
        mie = [x for x in voti if ruolo(x) == r_]
        pochi = [x["fantavoto"] for x in mie if len(per_g[x["player_id"]]) <= 2]
        tanti = [x["fantavoto"] for x in mie if len(per_g[x["player_id"]]) >= 4]
        fascia = lambda a, b: [x["fantavoto"] for x in mie if x.get("minuti") is not None and a <= x["minuti"] < b]
        print(f"  {r_}: tutti {m([x['fantavoto'] for x in mie])}; giocatori con <=2 voti {m(pochi)}, con >=4 {m(tanti)}; "
              f"60'+ {m(fascia(60, 999))}, 30-59' {m(fascia(30, 60))}, <30' {m(fascia(0, 30))}; "
              f"titolare {m([x['fantavoto'] for x in mie if x.get('subentrato') is False])}, "
              f"subentrato {m([x['fantavoto'] for x in mie if x.get('subentrato') is True])}")
    print("Stesso giocatore, da titolare meno da subentrato (giocatori con entrambi, media semplice): "
          "se il divario sopra fosse dei minuti e non di chi gioca, sarebbe positivo.")
    for r_ in "DCA":
        d = []
        for pid, rr in per_g.items():
            if players[pid]["role"] != r_:
                continue
            t = [x["fantavoto"] for x in rr if x.get("subentrato") is False]
            s_ = [x["fantavoto"] for x in rr if x.get("subentrato") is True]
            if t and s_:
                d.append(mean(t) - mean(s_))
        print(f"  {r_}: {mean(d):+.2f} su {len(d)} giocatori")
    con_minuti = [x for x in righe if x.get("minuti") is not None]
    print(f"Spezzoni: voti presi con meno di 25' {sum(1 for x in con_minuti if x.get('fantavoto') is not None and x['minuti'] < 25)}, "
          f"minuto minimo con voto {min(x['minuti'] for x in con_minuti if x.get('fantavoto') is not None)}, "
          f"giocatori con 25' o più rimasti senza voto {sum(1 for x in con_minuti if x.get('fantavoto') is None and x['minuti'] >= 25)}.")
    print("Correlazione tra media del fantavoto (giocatori con >=3 voti) e quotazione iniziale (QI, pre-stagione), "
          "attuale (QA, si muove coi voti) e FVM:")
    for r_ in "PDCA":
        gg = [(players[pid], mean(x["fantavoto"] for x in rr)) for pid, rr in per_g.items()
              if players[pid]["role"] == r_ and len(rr) >= 3]
        ys = [v for _, v in gg]
        cor = {c: _correlazione([p[c] or 0 for p, _ in gg], ys) for c in ("quotazione_iniziale", "quotazione", "fvm")}
        print(f"  {r_} ({len(gg)} giocatori): QI {cor['quotazione_iniziale']:.2f}, QA {cor['quotazione']:.2f}, FVM {cor['fvm']:.2f}")
    calciati = [x for x in righe if (x.get("rigori_segnati") or 0) + (x.get("rigori_sbagliati") or 0)]
    partite = {x["match_id"] for x in righe if x.get("minuti") is not None}
    print(f"Rigori nel box score BigBalls: {sum(x['rigori_segnati'] + x['rigori_sbagliati'] for x in calciati)} "
          f"calciati in {len(partite)} partite ({', '.join(sorted(players[x['player_id']]['name'] for x in calciati if x['player_id'] in players))}).")
    senza = [x for x in voti if x.get("minuti") is None]
    print(f"Voti senza statistiche BigBalls: {len(senza)} righe, {len({x['player_id'] for x in senza})} giocatori.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dal", type=int, default=3, help="prima giornata da prevedere (default 3)")
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--descrittive", action="store_true", help="solo i fatti descrittivi, niente backtest")
    args = parser.parse_args()

    righe = store.load_matchday_stats()
    players = {p["id"]: p for p in store.load_players()}
    calendario = store.load_json(store.DATA_DIR / "calendario_serie_a.json")
    own = {o["player_id"]: o["team_id"] for o in store.load_ownership()}
    if args.descrittive:
        descrittive(righe, players)
        return 0
    ultima = max(r["matchday"] for r in righe if r["matchday"] is not None and r.get("fantavoto") is not None)
    giornate = list(range(args.dal, ultima + 1))

    risultati = {c[0]: esegui(c, righe, players, calendario, giornate, own) for c in CONFIGURAZIONI}
    rif = CONFIGURAZIONI[0][0]
    e_rif, c_rif, _ = risultati[rif]
    print(f"Backtest giornate {giornate[0]}-{giornate[-1]}, ciascuna prevista con i dati delle precedenti.")
    print(f"Righe previste: {len(e_rif)} (giocatori con almeno un voto prima). "
          f"Coppie per l'ordine: {sum(v[1] for v in c_rif.values())}. Bootstrap {args.bootstrap}, seed {args.seed}.")
    print("Differenze rispetto al modello attuale: positivo = meglio. IC 95% tra parentesi.\n")
    intest = f"{'modello':<42} {'MAE':>6}  {'per giornata':<20} {'Δ MAE':>7} {'IC 95%':<17} {'ordine':>6} {'Δ ordine':>8} {'IC 95%':<17}"
    print(intest)
    print("-" * len(intest))
    for nome, _, _ in CONFIGURAZIONI:
        e, c, _ = risultati[nome]
        per_g = "/".join(f"{mean(x for _, g, x in e if g == gg):.3f}" for gg in giornate)
        dm = bootstrap_mae(e_rif, e, args.bootstrap, args.seed)
        do = bootstrap_ordine(c_rif, c, args.bootstrap, args.seed)
        ordine = sum(v[0] for v in c.values()) / sum(v[1] for v in c.values())
        print(f"{nome:<42} {mean(x for *_, x in e):6.3f}  {per_g:<20} {dm[0]:+7.3f} [{dm[1]:+.3f},{dm[2]:+.3f}] "
              f"{ordine:6.3f} {do[0]:+8.3f} [{do[1]:+.3f},{do[2]:+.3f}]")

    nuovo = NUOVO
    print("\nOgni pezzo del nuovo modello, tolto uno alla volta (Δ = quanto perde il modello senza):")
    for senza, nome in (
        ("contesto", f"freno {FRENO_VOTI} + produzione"),
        ("produzione", f"freno {FRENO_VOTI} + contesto"),
        (f"produzione e contesto (freno {FRENO_VOTI} da solo)", "attuale con freno 5"),
    ):
        dm = bootstrap_mae(risultati[nome][0], risultati[nuovo][0], args.bootstrap, args.seed)
        do = bootstrap_ordine(risultati[nome][1], risultati[nuovo][1], args.bootstrap, args.seed)
        print(f"  senza {senza:<40} MAE {dm[0]:+.3f} [{dm[1]:+.3f},{dm[2]:+.3f}]  ordine {do[0]:+.3f} [{do[1]:+.3f},{do[2]:+.3f}]")

    print("\nVarianti rispetto al nuovo modello (Δ positivo = la variante è meglio del nuovo):")
    for nome, _, _ in CONFIGURAZIONI:
        if not nome.startswith(("nuovo", "attuale +")):
            continue
        dm = bootstrap_mae(risultati[nuovo][0], risultati[nome][0], args.bootstrap, args.seed)
        do = bootstrap_ordine(risultati[nuovo][1], risultati[nome][1], args.bootstrap, args.seed)
        print(f"  {nome:<42} MAE {dm[0]:+.3f} [{dm[1]:+.3f},{dm[2]:+.3f}]  ordine {do[0]:+.3f} [{do[1]:+.3f},{do[2]:+.3f}]")

    print("\nSolo portieri (il contesto dei portieri si decide qui: nelle rose le coppie di portieri sono poche). "
          "Ordine su tutte le coppie di portieri di Serie A della stessa giornata.")
    portieri = (f"freno {FRENO_VOTI} + produzione", nuovo, "nuovo, portieri con gol fatti avversario")
    err_p = {}
    for nome in portieri:
        prev = [(riga, p) for riga, p in risultati[nome][2] if players[riga["player_id"]]["role"] == "P"]
        err_p[nome] = {(riga["player_id"], riga["matchday"]): abs(p - riga["fantavoto"]) for riga, p in prev}
        ok = tot = 0
        for g in giornate:
            lista = [(riga["fantavoto"], p) for riga, p in prev if riga["matchday"] == g]
            for i in range(len(lista)):
                for j in range(i + 1, len(lista)):
                    (vi, pi), (vj, pj) = lista[i], lista[j]
                    if vi != vj and pi != pj:
                        ok += (pi > pj) == (vi > vj)
                        tot += 1
        print(f"  {nome:<42} {len(prev):4d} previsioni  MAE {mean(err_p[nome].values()):.3f}  ordine {ok / tot:.3f} ({tot} coppie)")
    a = err_p["nuovo, portieri con gol fatti avversario"]
    e_a = [(pid, g, a[(pid, g)]) for (pid, g) in a]
    e_b = [(pid, g, err_p[nuovo][(pid, g)]) for (pid, g) in a]
    dm = bootstrap_mae(e_b, e_a, args.bootstrap, args.seed)
    print(f"  gol fatti invece di subiti, Δ MAE (positivo = fatti meglio): {dm[0]:+.3f} [{dm[1]:+.3f},{dm[2]:+.3f}]")

    print(f"\nTaratura della soglia dei pari ({SOGLIA_PARI:.2f}): tutte le coppie dello stesso ruolo in Serie A "
          "che hanno preso voto nella stessa giornata, per distacco previsto.")
    for nome in (rif, nuovo):
        prev = risultati[nome][2]
        per_g = defaultdict(list)
        for riga, p in prev:
            per_g[(riga["matchday"], players[riga["player_id"]]["role"])].append((riga["fantavoto"], p))
        fasce = [(0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 99)]
        conta = {f: [0, 0] for f in fasce}
        for lista in per_g.values():
            for i in range(len(lista)):
                for j in range(i + 1, len(lista)):
                    (vi, pi), (vj, pj) = lista[i], lista[j]
                    if vi == vj:
                        continue
                    d = abs(pi - pj)
                    for f in fasce:
                        if f[0] <= d < f[1]:
                            conta[f][0] += (pi > pj) == (vi > vj)
                            conta[f][1] += 1
        print(f"  {nome}")
        for f, (ok, tot) in conta.items():
            if tot:
                print(f"    distacco {f[0]:.2f}-{'oltre' if f[1] == 99 else f'{f[1]:.2f}'}: {tot:5d} coppie, ordine giusto {ok / tot:.3f}")

    print("\nDistorsione per numero di voti precedenti (previsto meno vero, D/C/A): se il freno "
          "gonfiasse chi ha pochi voti, con n=1-2 sarebbe positiva.")
    for nome in (rif, nuovo):
        gruppi = defaultdict(list)
        for g in giornate:
            modello = costruisci_modello(righe, players, calendario, prima_di_giornata=g, produzione=False, contesto=False)
            for riga, p in risultati[nome][2]:
                if riga["matchday"] != g or players[riga["player_id"]]["role"] == "P":
                    continue
                n = len(modello["per_giocatore"].get(riga["player_id"], []))
                gruppi[(players[riga["player_id"]]["role"], min(n, 3))].append(p - riga["fantavoto"])
        testo = "  ".join(
            f"{r}{'n>=3' if n == 3 else f'n={n}'} {mean(v):+.2f} ({len(v)})" for (r, n), v in sorted(gruppi.items())
        )
        print(f"  {nome}: {testo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
