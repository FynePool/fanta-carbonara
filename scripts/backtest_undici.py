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
irrilevante; sul modulo e' stata provata e non ha mostrato guadagni).

Per ogni giornata N >= 3 e per ognuna delle 12 rose della lega schiera con i soli dati
fino a N-1 e somma i punti veri. La simulazione sta in `lib/simulazione.py`, la stessa che
usa il report per misurare l'incertezza del punteggio atteso: li' c'e' scritto cosa si
usa per schierare (foto degli status alla scadenza, avversario dal calendario, probabilita'
di voto stimata dallo storico) e come si contano i voti d'ufficio.

COME LEGGERE GLI INTERVALLI. Bootstrap appaiato sulle coppie (squadra, giornata), che pero'
non sono indipendenti: nella stessa giornata le 12 rose condividono le partite. Gli
intervalli sono quindi ottimisti, e con 3 giornate un bootstrap per giornata non si puo'
fare. "Indistinguibile" vuol dire che con questi dati la differenza non si distingue da
zero, NON che la variante non guadagni niente. Il 29/09 bastava prendere l'avversario dal
calendario invece che dal tabellino per spostare due etichette da una parte all'altra.

LA REGOLA DEL PROGETTO e' a favore dello stato attuale, dichiaratamente: nessun cambiamento a
`roster.py`, ne' per aggiungere un pezzo ne' per toglierlo, senza un intervallo che escluda
lo zero. Per questo il termine avversario resta (entrato con prove poi ridimensionate: e'
provvisorio, si rimisura alla giornata 8) e modulo col valore atteso e scelta congiunta di
titolari e panchina restano fuori (non dimostrati, non smentiti).

Non scrive niente.

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
from lib.simulazione import Simulazione

STORICO_MIN_VOTI = 10


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dal", type=int, default=3, help="prima giornata da schierare (default 3)")
    parser.add_argument("--bootstrap", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    sim = Simulazione()
    cfg, teams, panchina_cfg = sim.cfg, sim.teams, sim.panchina_cfg
    giornate = sim.giornate(args.dal)
    if not giornate:
        print("Non ci sono ancora abbastanza giornate con i voti.")
        return 1
    path = store.DATA_DIR / "storico_stagioni.json"
    stagioni = store.load_json(path)["stagioni"] if path.exists() else {}
    scorsa = stagioni[max(stagioni)]["giocatori"] if stagioni else {}

    # --- regole di valore: con cosa si ordina un giocatore ---
    modello = sim.valore_modello

    def media_nuda(p, g, mo):
        rr = mo["per_giocatore"].get(p["id"], [])
        return st.mean(r["fantavoto"] for r in rr) if rr else None

    def stagione_scorsa(p, g, mo):
        d = scorsa.get(p["id"])
        return d["fantamedia"] if d and d["partite_con_voto"] >= STORICO_MIN_VOTI else None

    def quotazione(p, g, mo):
        return p.get("quotazione_iniziale") or 0

    def nessun_ordine(p, g, mo):
        return 0.0

    def oracolo(p, g, mo):
        return sim.vero.get((p["id"], g))  # bara: sa i voti veri. E' il tetto massimo.

    chiavi = [(t, g) for t in teams for g in giornate]
    rnd = random.Random(args.seed)
    campioni = [[rnd.choice(chiavi) for _ in chiavi] for _ in range(args.bootstrap)]

    def esegui(chiave, par=None, pan=True, mod=False, campo="punti"):
        return {(t, g): sim.schiera(t, g, chiave, sim.modello(g, **(par or {})), pan, mod)[campo]
                for t, g in chiavi}

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
          f"Bootstrap appaiato {args.bootstrap}, seed {args.seed}: intervalli ottimisti (le rose")
    print("della stessa giornata condividono le partite).")
    con_foto = [g for g in giornate if sim.status_alla_scadenza(g) is not None]
    senza_foto = [g for g in giornate if sim.status_alla_scadenza(g) is None]
    print("Infortunati e squalificati com'erano alla scadenza: "
          + (f"foto per le giornate {con_foto}" if con_foto else "nessuna foto")
          + (f"; giornate {senza_foto} senza foto, nessuno escluso." if senza_foto else "."))
    u = sim.voti_ufficio
    print(f"Voti d'ufficio (solo a chi ha giocato): {u['cartellini_gialli']} ammoniti senza voto, "
          f"{u['cartellini_rossi']} espulsi senza voto; {u['minuti_ignoti']} con cartellino e minuti "
          "sconosciuti, non contati.\n")

    # Il riferimento e' il motore come gira davvero: panchina scelta con la probabilita' di
    # prendere voto, modulo scelto sulla somma dei valori dei titolari (vedi suggest_lineup).
    base = esegui(modello)
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
    print("stata provata e non ha mostrato guadagni: vedi il commento in suggest_lineup.")
    print("Negativo = quella variante fa peggio del motore di oggi.")
    for nome, pan, mod in (("panchina per solo valore (come prima del 27/09)", False, False),
                           ("modulo col valore atteso invece della somma", True, True),
                           ("modulo col valore atteso + panchina vecchia", False, True)):
        v = esegui(modello, pan=pan, mod=mod)
        print(f"  {nome:<38} {st.mean(v.values()):6.2f}  " +
              "{:+.2f} [{:+.2f},{:+.2f}] {}".format(*confronta(v, base)))

    print("\nAblazione del modello in punti. Ogni variante cambia UNA cosa rispetto al motore")
    print("(produzione spenta, contesto acceso, freno 5). 'indistinguibile' = con 36 formazioni")
    print("non si distingue da zero, non che quel pezzo valga zero.")
    VARIANTI = [("senza contesto (avversario)", dict(contesto=False)),
                ("CON la produzione (spenta dal 27/09)", dict(produzione=True)),
                ("produzione a meta peso", dict(produzione=True, peso_produzione=0.5)),
                ("produzione, senza contesto", dict(produzione=True, contesto=False)),
                (f"freno 3 invece di {R.FRENO_VOTI}", dict(freno=3)),
                (f"freno 10 invece di {R.FRENO_VOTI}", dict(freno=10))]
    for nome, par in VARIANTI:
        v = esegui(modello, par=par)
        print(f"  {nome:<36} {st.mean(v.values()):6.2f}  " +
              "{:+.2f} [{:+.2f},{:+.2f}] {}".format(*confronta(v, base)))

    atteso = esegui(modello, campo="atteso")
    scarti = [base[k] - atteso[k] for k in chiavi]
    print("\nQuanto sbaglia il punteggio atteso della formazione intera (punti veri meno atteso):")
    print(f"  scarto medio {st.mean(scarti):+.2f}, deviazione standard {st.pstdev(scarti):.2f} "
          f"su {len(scarti)} formazioni.")
    print("  Misurati con la probabilita' di voto stimata dallo storico, non con quella del sito che")
    print("  usa il report: il report ne prende la larghezza per lo scenario dei gol, ma ne' la")
    print("  larghezza ne' lo scarto medio sono verificati per lui (lib/simulazione.py,")
    print("  scarti_formazione). Si rimisurano dalla giornata 6 con le probabili salvate alla scadenza.")

    print("\nQuanto costa la panchina corta: slot rimasti scoperti (0 punti) per giornata,")
    print("col modello e la panchina scelta per valore.")
    scoperti = 0
    for t in teams:
        for g in giornate:
            mo = sim.modello(g)
            per_ruolo = {r: [] for r in R.ROLES}
            for p in sim.rose[t]:
                if sim.disponibile(p, g):
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
                presi = sum(1 for p in cand if sim.vero.get((p["id"], g)) is not None)
                scoperti += max(0, n - presi)
    print(f"  {scoperti} slot scoperti su {len(chiavi) * 11} ({scoperti / len(chiavi):.2f} per formazione, "
          f"circa {scoperti / len(chiavi) * 6:.1f} punti a giornata buttati)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
