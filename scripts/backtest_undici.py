#!/usr/bin/env python3
"""Backtest dell'UNDICI, non del singolo voto.

`backtest_formazione.py` misura quanto il modello sbaglia il fantavoto di un giocatore
(MAE) e quanto spesso mette in ordine giusto due giocatori della stessa rosa. Nessuna
delle due cose dice la cosa che conta: **quanti punti a giornata guadagna la formazione
consigliata** rispetto a una regola banale. Un modello puo' prevedere meglio ogni singolo
voto e schierare lo stesso undici di prima: in quel caso non vale niente.

Questo script chiude quel buco. Per ogni giornata N >= 3 e per ognuna delle 12 rose della
lega, schiera la formazione usando **solo** i dati fino a N-1, poi applica le regole della
lega (sostituzioni illimitate tra pari ruolo: per ogni titolare senza voto entra il primo
del suo ruolo in panchina che ha preso voto; uno slot che non trova nessuno vale 0) e
somma i **punti veri** della giornata.

12 rose x 3 giornate = 36 formazioni, invece delle 3 della sola rosa mia: sulle 3 le
differenze sono tutte rumore (verificato: sulla sola rosa mia la fantamedia della
stagione scorsa sembrava battere il modello di 0,17 punti; su 36 formazioni perde di
1,79 con intervallo che esclude lo zero).

Confronta il modello con regole alternative e ne ablaziona i pezzi. Gli intervalli al
95% sono bootstrap appaiati sulle coppie (squadra della lega, giornata).

Non scrive niente. Da rilanciare quando ci sono piu' giornate, prima di toccare
`lib/roster.py`: e' la misura che dice se una modifica guadagna punti o solo decimali
di MAE.

Uso:
    python3 scripts/backtest_undici.py
    python3 scripts/backtest_undici.py --dal 3 --bootstrap 4000
"""
import argparse
import random
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib import roster as R

STORICO_MIN_VOTI = 10


def carica():
    cfg = store.load_league_config()
    players = {p["id"]: p for p in store.load_players()}
    righe = store.load_matchday_stats()
    calendario = store.load_json(store.DATA_DIR / "calendario_serie_a.json")
    teams = [t["id"] for t in store.load_json(store.DATA_DIR / "teams.json")]
    path = store.DATA_DIR / "storico_stagioni.json"
    stagioni = store.load_json(path)["stagioni"] if path.exists() else {}
    scorsa = stagioni[max(stagioni)]["giocatori"] if stagioni else {}
    return cfg, players, righe, calendario, teams, scorsa


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dal", type=int, default=3, help="prima giornata da schierare (default 3)")
    parser.add_argument("--bootstrap", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    cfg, players, righe, calendario, teams, scorsa = carica()
    ultima = max(r["matchday"] for r in righe if r["matchday"] is not None and r.get("fantavoto") is not None)
    giornate = list(range(args.dal, ultima + 1))
    if not giornate:
        print("Non ci sono ancora abbastanza giornate con i voti.")
        return 1

    # fantavoto vero e avversario per (giocatore, giornata): il voto vero serve solo a
    # contare i punti dopo aver schierato, e all'oracolo.
    vero = {(r["player_id"], r["matchday"]): r["fantavoto"] for r in righe if r.get("fantavoto") is not None}
    avversario = {
        (r["player_id"], r["matchday"]): r.get("opponent_serie_a_team")
        for r in righe if r["matchday"] is not None
    }
    rose = {t: R.team_roster(t, players)[0] for t in teams}

    def fantamedia_scorsa(pid):
        d = scorsa.get(pid)
        return d["fantamedia"] if d and d["partite_con_voto"] >= STORICO_MIN_VOTI else None

    # --- le regole da confrontare: ognuna da' il valore con cui ordinare un giocatore ---
    def modello(p, g, mo):
        rt = R.rate_player(p, mo, avversario.get((p["id"], g)))
        return rt["punteggio"] if rt else None

    def media_nuda(p, g, mo):
        rr = mo["per_giocatore"].get(p["id"], [])
        return st.mean(r["fantavoto"] for r in rr) if rr else None

    def stagione_scorsa(p, g, mo):
        return fantamedia_scorsa(p["id"])

    def meta_e_meta(p, g, mo):
        a, b = modello(p, g, mo), fantamedia_scorsa(p["id"])
        if a is None:
            return b
        return a if b is None else 0.5 * a + 0.5 * b

    def quotazione(p, g, mo):
        return p.get("quotazione_iniziale") or 0

    def nessun_ordine(p, g, mo):
        return 0.0

    def oracolo(p, g, mo):
        return vero.get((p["id"], g))  # bara: sa i voti veri. E' il tetto massimo.

    REGOLE = [
        ("modello attuale", modello),
        ("media nuda dei voti", media_nuda),
        ("fantamedia stagione scorsa", stagione_scorsa),
        ("meta modello + meta scorsa", meta_e_meta),
        ("quotazione iniziale", quotazione),
        ("nessun ordine (ordine d'acquisto)", nessun_ordine),
        ("ORACOLO (sa i voti veri)", oracolo),
    ]

    def schiera_e_conta(team, g, chiave, modelli):
        """Ordina ogni ruolo con `chiave`, scegli il modulo con la somma piu' alta (come fa
        roster.py), poi conta i punti veri applicando le sostituzioni."""
        mo = modelli[g]
        per_ruolo = {r: [] for r in R.ROLES}
        for p in rose[team]:
            if p["status"] not in R.EXCLUDED_STATUSES:
                per_ruolo[p["role"]].append(p)
        val = {p["id"]: chiave(p, g, mo) for r in R.ROLES for p in per_ruolo[r]}
        for r in R.ROLES:
            # chi non ha un valore va in fondo, come in roster.py
            per_ruolo[r].sort(key=lambda p: -(val[p["id"]] if val[p["id"]] is not None else -99))
        migliore, somma_migliore = None, None
        for module in cfg["formation_modules"]:
            counts = {"P": 1, **R.MODULE_ROLE_COUNTS[module]}
            s = sum(val[p["id"]] or 0 for r_, n in counts.items() for p in per_ruolo[r_][:n])
            if somma_migliore is None or s > somma_migliore:
                somma_migliore, migliore = s, module
        counts = {"P": 1, **R.MODULE_ROLE_COUNTS[migliore]}
        punti = 0.0
        for ruolo, n in counts.items():
            presi = 0
            for p in per_ruolo[ruolo]:
                if presi >= n:
                    break
                fv = vero.get((p["id"], g))
                if fv is not None:  # senza voto: si scorre, entra il prossimo del ruolo
                    punti += fv
                    presi += 1
            # gli slot che restano scoperti valgono 0
        return punti

    modelli = {g: R.costruisci_modello(righe, players, calendario, prima_di_giornata=g) for g in giornate}
    chiavi = [(t, g) for t in teams for g in giornate]
    rnd = random.Random(args.seed)
    campioni = [[rnd.choice(chiavi) for _ in chiavi] for _ in range(args.bootstrap)]

    def confronta(valori, riferimento):
        oss = st.mean(valori[k] - riferimento[k] for k in chiavi)
        boot = sorted(st.mean(valori[k] - riferimento[k] for k in s) for s in campioni)
        lo = boot[int(0.025 * args.bootstrap)]
        hi = boot[int(0.975 * args.bootstrap) - 1]
        verdetto = "MEGLIO" if lo > 0 else ("peggio" if hi < 0 else "indistinguibile")
        return oss, lo, hi, verdetto

    risultati = {nome: {k: schiera_e_conta(k[0], k[1], f, modelli) for k in chiavi} for nome, f in REGOLE}
    base = risultati["modello attuale"]

    print(f"Backtest dell'undici: {len(teams)} rose x {len(giornate)} giornate "
          f"({giornate[0]}-{giornate[-1]}) = {len(chiavi)} formazioni.")
    print("Ogni giornata schierata coi soli dati precedenti. Punti VERI, sostituzioni")
    print("illimitate tra pari ruolo, slot scoperto = 0. Bootstrap appaiato "
          f"{args.bootstrap}, seed {args.seed}.\n")
    intest = f"{'regola':<34} {'punti':>6} {'min':>6} {'max':>6}   contro il modello, IC 95%"
    print(intest)
    print("-" * (len(intest) + 8))
    for nome, _ in REGOLE:
        v = risultati[nome]
        riga = f"{nome:<34} {st.mean(v.values()):6.2f} {min(v.values()):6.1f} {max(v.values()):6.1f}   "
        if nome == "modello attuale":
            print(riga + "(riferimento)")
            continue
        oss, lo, hi, verdetto = confronta(v, base)
        print(riga + f"{oss:+.2f} [{lo:+.2f},{hi:+.2f}] {verdetto}")

    print("\nAblazione in punti: ogni pezzo del modello tolto o cambiato. Se una variante e'")
    print("'indistinguibile', quel pezzo non sta guadagnando punti misurabili.")
    VARIANTI = [
        ("senza produzione", dict(produzione=False, contesto=True)),
        ("senza contesto (avversario)", dict(produzione=True, contesto=False)),
        ("senza nessuno dei due", dict(produzione=False, contesto=False)),
        ("produzione a meta peso", dict(produzione=True, contesto=True, peso_produzione=0.5)),
        (f"freno 3 invece di {R.FRENO_VOTI}", dict(produzione=True, contesto=True, freno=3)),
        (f"freno 10 invece di {R.FRENO_VOTI}", dict(produzione=True, contesto=True, freno=10)),
    ]
    for nome, parametri in VARIANTI:
        mods = {g: R.costruisci_modello(righe, players, calendario, prima_di_giornata=g, **parametri)
                for g in giornate}
        v = {k: schiera_e_conta(k[0], k[1], modello, mods) for k in chiavi}
        oss, lo, hi, verdetto = confronta(v, base)
        print(f"  {nome:<32} {st.mean(v.values()):6.2f}  {oss:+.2f} [{lo:+.2f},{hi:+.2f}] {verdetto}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
