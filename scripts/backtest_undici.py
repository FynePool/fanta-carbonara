#!/usr/bin/env python3
"""Backtest dell'UNDICI, non del singolo voto, con la panchina VERA della lega.

`backtest_formazione.py` misura quanto il modello sbaglia il fantavoto di un giocatore
(MAE) e quanto spesso mette in ordine giusto due giocatori della stessa rosa. Nessuna
delle due dice la cosa che conta: **quanti punti a giornata guadagna la formazione
consigliata**. Un modello puo' prevedere meglio ogni singolo voto e schierare lo stesso
undici: in quel caso non vale niente.

Le regole vere, da `config/league.json -> regole_lega` (confermate dall'utente il 27/09):
panchina di **7 giocatori a composizione fissa** (1 P, 2 D, 2 C, 2 A), sostituzioni
**solo tra pari ruolo**, e se finiscono le riserve di un ruolo lo **slot vale 0**. E' la
differenza che conta: con la panchina corta la probabilita' di prendere voto torna a
pesare sulla scelta della panchina (non sull'ordine dentro il ruolo, dove resta
irrilevante; sul modulo e' stata provata e non guadagna).

Per ogni giornata N >= 3 e per ognuna delle 12 rose della lega schiera con i soli dati
fino a N-1 e somma i punti veri. Bootstrap appaiato sulle coppie (squadra, giornata).

La probabilita' di prendere voto qui NON viene da `prob_titolare` (fantacalcio.it la
pubblica solo dal 21/09, dopo la giornata 5: usarla sarebbe guardare il futuro). Si stima
dalle giornate precedenti: quota di giornate in cui il giocatore ha preso voto, frenata
verso la quota media del suo ruolo.

CHI E' FUORI (infortunato, squalificato) E' QUELLO CHE SI SAPEVA ALLA SCADENZA, non oggi.
Fino al 29/09 il backtest escludeva chi e' infortunato oggi anche dalle giornate passate:
guardava il futuro (11 voti delle giornate 3-5 di giocatori poi infortunati, tra cui Busio
e Holm), e gonfiava il modello. Ora legge la foto scritta prima di ogni scadenza da
`salva_status_scadenza.py` (data/status_scadenze.json). Per le giornate senza foto (fino
alla 5: la prima foto e' del 29/09, e players.json non esisteva prima del 19/09) non esclude
nessuno: tutte le regole giocano senza sapere chi e' fuori, quindi il confronto fra regole
resta alla pari, ma i punti assoluti sono un po' piu' bassi di quelli veri.

L'ammonito senza voto prende 5,5 d'ufficio nella lega (`scoring.senza_voto_ammonito` in
config/league.json) e non entra nessuno al suo posto: nei punti veri vale cosi'.

Non scrive niente. E' il collaudo da superare prima di toccare `lib/roster.py`.

Uso:
    python3 scripts/backtest_undici.py
    python3 scripts/backtest_undici.py --dal 3 --bootstrap 4000
"""
import argparse
import random
from collections import defaultdict
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib import roster as R

STORICO_MIN_VOTI = 10
# Freno sulla quota di voti presi: come se il giocatore avesse questo numero di giornate
# in piu' "da giocatore medio del suo ruolo". Con 2-4 giornate alle spalle serve.
FRENO_QUOTA = 2.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dal", type=int, default=3, help="prima giornata da schierare (default 3)")
    parser.add_argument("--bootstrap", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    cfg = store.load_league_config()
    players = {p["id"]: p for p in store.load_players()}
    righe = store.load_matchday_stats()
    calendario = store.load_json(store.DATA_DIR / "calendario_serie_a.json")
    teams = [t["id"] for t in store.load_json(store.DATA_DIR / "teams.json")]
    path = store.DATA_DIR / "storico_stagioni.json"
    stagioni = store.load_json(path)["stagioni"] if path.exists() else {}
    scorsa = stagioni[max(stagioni)]["giocatori"] if stagioni else {}
    panchina_cfg = {r: n for r, n in cfg["regole_lega"]["panchina"].items() if r in R.ROLES}

    ultima = max(r["matchday"] for r in righe if r["matchday"] is not None and r.get("fantavoto") is not None)
    giornate = list(range(args.dal, ultima + 1))
    if not giornate:
        print("Non ci sono ancora abbastanza giornate con i voti.")
        return 1

    vero = {(r["player_id"], r["matchday"]): r["fantavoto"] for r in righe if r.get("fantavoto") is not None}
    # regola della lega: l'ammonito senza voto prende un voto d'ufficio e non viene sostituito
    ammonito_sv = (cfg.get("scoring") or {}).get("senza_voto_ammonito")
    ammoniti = 0
    if ammonito_sv is not None:
        for r in righe:
            chiave_r = (r["player_id"], r["matchday"])
            if (r["matchday"] is not None and r.get("fantavoto") is None
                    and (r.get("cartellini_gialli") or 0) > 0 and chiave_r not in vero):
                vero[chiave_r] = float(ammonito_sv)
                ammoniti += 1

    foto = store.load_json(store.DATA_DIR / "status_scadenze.json")["scadenze"] \
        if (store.DATA_DIR / "status_scadenze.json").exists() else {}

    def status_alla_scadenza(g):
        """player_id -> status com'era alla scadenza della giornata g, dall'ultima foto salvata
        prima della sua prima partita e che ne copre la maggior parte delle partite. None se
        non c'e' foto: allora non si esclude nessuno."""
        partite = [m for m in calendario if m.get("giornata") == g]
        ids = {m["match_id"] for m in partite}
        inizio = min((m["data_utc"][:19] for m in partite if m["stato"] != "postponed"), default=None)
        buone = [f for f in foto.values()
                 if inizio and f["salvato_il"][:19] <= inizio and len(ids & set(f["partite"])) > len(ids) / 2]
        return max(buone, key=lambda f: f["salvato_il"])["status"] if buone else None

    status_g = {g: status_alla_scadenza(g) for g in giornate}

    def disponibile(p, g):
        st_ = status_g[g]
        return st_ is None or st_.get(p["id"]) not in R.EXCLUDED_STATUSES
    avversario = {
        (r["player_id"], r["matchday"]): r.get("opponent_serie_a_team")
        for r in righe if r["matchday"] is not None
    }
    rose = {t: R.team_roster(t, players)[0] for t in teams}

    # --- probabilita' di prendere voto, stimata solo sulle giornate precedenti ---
    def quote(g):
        """player_id -> quota di giornate (fra 1 e g-1) in cui ha preso voto, frenata verso
        la quota media del ruolo."""
        n_giornate = g - 1
        presi = {pid: 0 for pid in players}
        for (pid, md), _ in vero.items():
            if md is not None and md < g and pid in presi:
                presi[pid] += 1
        per_ruolo = {}
        for r_ in R.ROLES:
            v = [presi[pid] / n_giornate for pid in players if players[pid]["role"] == r_]
            per_ruolo[r_] = st.mean(v) if v else 0.5
        return {
            pid: (presi[pid] + FRENO_QUOTA * per_ruolo[players[pid]["role"]])
                 / (n_giornate + FRENO_QUOTA)
            for pid in players
        }

    def fantamedia_scorsa(pid):
        d = scorsa.get(pid)
        return d["fantamedia"] if d and d["partite_con_voto"] >= STORICO_MIN_VOTI else None

    # --- regole di valore: con cosa si ordina un giocatore ---
    def modello(p, g, mo):
        rt = R.rate_player(p, mo, avversario.get((p["id"], g)))
        return rt["punteggio"] if rt else None

    def media_nuda(p, g, mo):
        rr = mo["per_giocatore"].get(p["id"], [])
        return st.mean(r["fantavoto"] for r in rr) if rr else None

    def stagione_scorsa(p, g, mo):
        return fantamedia_scorsa(p["id"])

    def quotazione(p, g, mo):
        return p.get("quotazione_iniziale") or 0

    def nessun_ordine(p, g, mo):
        return 0.0

    def oracolo(p, g, mo):
        return vero.get((p["id"], g))  # bara: sa i voti veri. E' il tetto massimo.

    def schiera_e_conta(team, g, chiave, modelli, panchina_con_prob, modulo_con_prob):
        """Schiera e conta i punti veri. Usa `_scegli_panchina` e `_slot_attesi` di
        lib/roster.py — le funzioni vere del motore — passando lo stimatore storico della
        probabilita' di prendere voto al posto di `prob_titolare`, che per queste giornate
        non esiste. Cosi' il backtest collauda il codice che gira, non una sua copia."""
        mo = modelli[g]
        q = quote(g)
        prob = lambda e: q.get(e["player"]["id"], 0.5)
        per_ruolo = {r: [] for r in R.ROLES}
        for p in rose[team]:
            if disponibile(p, g):
                # le funzioni di roster.py vogliono le "entry" {player, rating}
                per_ruolo[p["role"]].append({"player": p, "rating": None})
        for r in R.ROLES:
            for e in per_ruolo[r]:
                v = chiave(e["player"], g, mo)
                e["rating"] = {"punteggio": v} if v is not None else None
                # come in suggest_lineup: chi non ha voti vale la media del ruolo negli
                # slot attesi, non 0 (sulle giornate 3-5 non cambia nessuna scelta)
                e["stima"] = mo["media_ruolo"].get(r)
            per_ruolo[r].sort(key=lambda e: -(e["rating"]["punteggio"] if e["rating"] else -99))

        def schierati(ruolo, n):
            posti = panchina_cfg.get(ruolo, 0)
            if panchina_con_prob:
                t_, r_ = R._scegli_panchina(per_ruolo[ruolo], n, posti, prob)
            else:   # come faceva il report prima: le riserve sono le successive per valore
                t_, r_ = per_ruolo[ruolo][:n], per_ruolo[ruolo][n:n + posti]
            return t_ + r_

        migliore, somma_migliore = None, None
        for module in cfg["formation_modules"]:
            counts = {"P": 1, **R.MODULE_ROLE_COUNTS[module]}
            if modulo_con_prob:
                s = sum(R._slot_attesi(schierati(r_, n), n, prob)[0] for r_, n in counts.items())
            else:   # somma dei valori dei titolari, senza scontare chi non prende voto
                s = sum((e["rating"]["punteggio"] if e["rating"] else 0)
                        for r_, n in counts.items() for e in per_ruolo[r_][:n])
            if somma_migliore is None or s > somma_migliore:
                somma_migliore, migliore = s, module

        punti = 0.0
        for ruolo, n in {"P": 1, **R.MODULE_ROLE_COUNTS[migliore]}.items():
            presi = 0
            for e in schierati(ruolo, n):   # titolari + le sole riserve ammesse dalla lega
                if presi >= n:
                    break
                fv = vero.get((e["player"]["id"], g))
                if fv is not None:          # senza voto: entra il prossimo DELLO STESSO RUOLO
                    punti += fv
                    presi += 1
            # se le riserve del ruolo finiscono, gli slot restano scoperti e valgono 0
        return punti

    modelli = {g: R.costruisci_modello(righe, players, calendario, prima_di_giornata=g) for g in giornate}
    chiavi = [(t, g) for t in teams for g in giornate]
    rnd = random.Random(args.seed)
    campioni = [[rnd.choice(chiavi) for _ in chiavi] for _ in range(args.bootstrap)]

    def esegui(chiave, modelli=modelli, pan=True, mod=False):
        return {k: schiera_e_conta(k[0], k[1], chiave, modelli, pan, mod) for k in chiavi}

    def confronta(v, rif):
        oss = st.mean(v[k] - rif[k] for k in chiavi)
        boot = sorted(st.mean(v[k] - rif[k] for k in s) for s in campioni)
        lo, hi = boot[int(0.025 * args.bootstrap)], boot[int(0.975 * args.bootstrap) - 1]
        return oss, lo, hi, ("MEGLIO" if lo > 0 else ("peggio" if hi < 0 else "indistinguibile"))

    panca = ", ".join(f"{n}{r}" for r, n in panchina_cfg.items())
    print(f"Backtest dell'undici: {len(teams)} rose x {len(giornate)} giornate "
          f"({giornate[0]}-{giornate[-1]}) = {len(chiavi)} formazioni.")
    print(f"Panchina vera: {sum(panchina_cfg.values())} giocatori ({panca}), sostituzioni solo tra")
    print(f"pari ruolo, slot scoperto = {cfg['regole_lega']['slot_scoperto']} punti. "
          f"Bootstrap appaiato {args.bootstrap}, seed {args.seed}.")
    con_foto = [g for g in giornate if status_g[g] is not None]
    senza_foto = [g for g in giornate if status_g[g] is None]
    print("Infortunati e squalificati com'erano alla scadenza: "
          + (f"foto per le giornate {con_foto}" if con_foto else "nessuna foto")
          + (f"; giornate {senza_foto} senza foto, nessuno escluso." if senza_foto else "."))
    if ammonito_sv is not None:
        print(f"Ammoniti senza voto: {ammoniti}, contati {ammonito_sv} d'ufficio come nella lega.")
    print()

    # Il riferimento e' il motore come gira davvero: panchina scelta con la probabilita' di
    # prendere voto, modulo scelto sulla somma dei valori dei titolari (vedi suggest_lineup).
    base = esegui(modello, pan=True, mod=False)
    # NESSUNA VARIANTE RIGORISTI, e vale la pena dire perche'.
    # Il primo tentativo assegnava il bonus al primo rigorista della STAGIONE SCORSA senza
    # controllare se fosse ancora in quella squadra: un rigorista che ha cambiato squadra
    # (o a cui sono cambiati i compagni) non e' piu' il rigorista, quindi il test era
    # sbagliato, non solo senza potere. E non c'e' un modo giusto di rifarlo: le gerarchie
    # di data/rigoristi.json sono state scritte guardando anche le giornate 1-5, quindi
    # usarle per prevedere quelle giornate sarebbe barare. Per questo il rigorista non
    # entra nel punteggio ma serve come spareggio, e la sua attendibilita' si misura
    # sull'unico dato onesto: i rigori davvero calciati quest'anno, guardando chi era in
    # campo quando sono stati calciati (5 in tutto il campionato al 29/09: il primo delle
    # fonti non e' mai stato scavalcato, il secondo del Venezia si'). Vedi
    # scripts/rigoristi.py.
    REGOLE = [("modello attuale", modello), ("media nuda dei voti", media_nuda),
              ("fantamedia stagione scorsa", stagione_scorsa), ("quotazione iniziale", quotazione),
              ("nessun ordine (ordine d'acquisto)", nessun_ordine), ("ORACOLO (sa i voti veri)", oracolo)]
    intest = f"{'regola di valore':<34} {'punti':>6} {'min':>6} {'max':>6}   contro il modello, IC 95%"
    print(intest)
    print("-" * (len(intest) + 8))
    for nome, f in REGOLE:
        v = base if nome == "modello attuale" else esegui(f)
        riga = f"{nome:<34} {st.mean(v.values()):6.2f} {min(v.values()):6.1f} {max(v.values()):6.1f}   "
        print(riga + ("(riferimento)" if nome == "modello attuale"
                      else "{:+.2f} [{:+.2f},{:+.2f}] {}".format(*confronta(v, base))))

    print("\nDove entra la probabilita' di prendere voto. NON nell'ordine dentro il ruolo (la'")
    print("e' dimostrato che non conta), ma nella scelta di chi va in panchina. Sul modulo e'")
    print("stata provata e non guadagna punti: vedi il commento in suggest_lineup.")
    print("Negativo = quella variante fa peggio del motore di oggi.")
    for nome, pan, mod in (("panchina per solo valore (come prima del 27/09)", False, False),
                           ("modulo col valore atteso invece della somma", True, True),
                           ("modulo col valore atteso + panchina vecchia", False, True)):
        v = esegui(modello, pan=pan, mod=mod)
        print(f"  {nome:<38} {st.mean(v.values()):6.2f}  " +
              "{:+.2f} [{:+.2f},{:+.2f}] {}".format(*confronta(v, base)))

    print("\nAblazione del modello in punti. 'indistinguibile' = quel pezzo non guadagna nulla,")
    print("e con 36 formazioni il test non distingue differenze sotto il punto e mezzo.")
    VARIANTI = [("senza contesto (avversario)", dict(produzione=False, contesto=False)),
                ("CON la produzione (spenta dal 27/09)", dict(produzione=True, contesto=True)),
                ("produzione a meta peso", dict(produzione=True, contesto=True, peso_produzione=0.5)),
                ("produzione senza contesto", dict(produzione=True, contesto=False)),
                (f"freno 3 invece di {R.FRENO_VOTI}", dict(produzione=True, contesto=True, freno=3)),
                (f"freno 10 invece di {R.FRENO_VOTI}", dict(produzione=True, contesto=True, freno=10))]
    for nome, par in VARIANTI:
        mods = {g: R.costruisci_modello(righe, players, calendario, prima_di_giornata=g, **par)
                for g in giornate}
        v = esegui(modello, modelli=mods)
        print(f"  {nome:<32} {st.mean(v.values()):6.2f}  " +
              "{:+.2f} [{:+.2f},{:+.2f}] {}".format(*confronta(v, base)))

    print("\nQuanto costa la panchina corta: slot rimasti scoperti (0 punti) per giornata,")
    print("col modello e la panchina scelta per valore.")
    scoperti = 0
    for t in teams:
        for g in giornate:
            mo = modelli[g]
            per_ruolo = {r: [] for r in R.ROLES}
            for p in rose[t]:
                if disponibile(p, g):
                    per_ruolo[p["role"]].append(p)
            val = {p["id"]: modello(p, g, mo) for r in R.ROLES for p in per_ruolo[r]}
            for r in R.ROLES:
                per_ruolo[r].sort(key=lambda p: -(val[p["id"]] if val[p["id"]] is not None else -99))
            # modulo come lo sceglie il motore oggi
            best, mig = None, None
            for m_ in cfg["formation_modules"]:
                c = {"P": 1, **R.MODULE_ROLE_COUNTS[m_]}
                s = sum(val[p["id"]] or 0 for r_, n in c.items() for p in per_ruolo[r_][:n])
                if best is None or s > best:
                    best, mig = s, m_
            for r_, n in {"P": 1, **R.MODULE_ROLE_COUNTS[mig]}.items():
                cand = per_ruolo[r_][:n + panchina_cfg.get(r_, 0)]
                presi = sum(1 for p in cand if vero.get((p["id"], g)) is not None)
                scoperti += max(0, n - presi)
    print(f"  {scoperti} slot scoperti su {len(chiavi) * 11} ({scoperti / len(chiavi):.2f} per formazione, "
          f"circa {scoperti / len(chiavi) * 6:.1f} punti a giornata buttati)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
