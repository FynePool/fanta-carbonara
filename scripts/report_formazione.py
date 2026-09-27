#!/usr/bin/env python3
"""Suggerisce la formazione per una giornata, a partire dai dati in data/.

Uso:
    python3 scripts/report_formazione.py --team-id t01 [--matchday 5]

I dati di stato giocatore (titolare/dubbio/infortunato/...) in data/players.json
vanno aggiornati prima del lancio (skill aggiorna-dati o aggiorna-formazioni).
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib.roster import PRODUZIONE_PREDEFINITA, SOGLIA_PARI, prossima_partita_lega, suggest_lineup


def _voti(rating: dict | None) -> str:
    """Il valore e i suoi tre pezzi, in colonna: voti (media frenata), produzione, contesto."""
    if rating is None:
        return "  -    senza voti"
    if rating.get("politico"):
        return " 6.00  6 politico (rinvio)"
    prod = rating["produzione"]
    ctx = rating["contesto"]
    pezzi = [f"voti {rating['base'] - (prod['effetto'] if prod else 0):.2f}"]
    # La colonna `prod` si stampa solo se la correzione per la produzione è accesa:
    # spenta, scrivere "prod n/d" farebbe credere che manchi un dato (vedi
    # PRODUZIONE_PREDEFINITA in lib/roster.py).
    if PRODUZIONE_PREDEFINITA:
        if prod:
            pezzi.append(f"prod {prod['effetto']:+.2f}")
        else:
            pezzi.append("prod     -" if rating.get("portiere") else "prod   n/d")
    pezzi.append(f"avv {ctx['effetto']:+.2f}" if ctx else "avv   n/d")
    return f"{rating['punteggio']:5.2f}  {'  '.join(pezzi)}"


def _dettaglio(e: dict) -> str:
    """Da cosa è fatto il valore, in parole: una riga per giocatore."""
    p, r = e["player"], e["rating"]
    if r is None:
        return f"[{p['role']}] {p['name']}: nessun voto, nessun valore. Decidi tu."
    if r.get("politico"):
        return f"[{p['role']}] {p['name']}: partita rinviata, 6 politico."
    n = r["n"]
    parti = [
        f"media {r['media']:.2f} su {n} vot{'o' if n == 1 else 'i'} "
        f"({r['titolare']} da titolare, {r['da_subentrato']} da subentrato"
        + (f", {n - r['titolare'] - r['da_subentrato']} senza dato" if n - r["titolare"] - r["da_subentrato"] else "")
        + f"), frenata verso {r['riferimento']:.2f} del ruolo"
    ]
    prod = r["produzione"]
    if prod and prod["voti_con_tiri"]:
        parti.append(
            f"{prod['gol_azione']} gol su azione contro {prod['gol_attesi']:.1f} attesi da "
            f"{prod['tiri_porta']} tiri in porta su {prod['tiri']} ({prod['effetto']:+.2f})"
        )
    elif p["role"] != "P" and PRODUZIONE_PREDEFINITA:
        parti.append("tiri non disponibili (BigBalls non ha il giocatore): produzione non conteggiata")
    ctx = r["contesto"]
    if ctx:
        parti.append(f"{ctx['avversario']} subisce {ctx['subiti']:.1f} gol a partita ({ctx['effetto']:+.2f})")
    return f"[{p['role']}] {p['name']} {r['punteggio']:.2f}: " + "; ".join(parti) + "."


ROMA = ZoneInfo("Europe/Rome")


def _stagione(d: dict | None) -> str:
    if not d or not d["partite_con_voto"]:
        return "non ha giocato in Serie A"
    testo = f"{d['squadra']} {d['partite_con_voto']} voti, fantamedia {d['fantamedia']:.2f}"
    if d["ruolo"] == "P":
        testo += f", {d['gol_subiti']} gol subiti"
    else:
        testo += f", {d['gol']} gol, {d['assist']} assist"
    if d["rigori_calciati"]:
        testo += f", rigori {d['rigori_segnati']} su {d['rigori_calciati']}"
    return testo


def _storico() -> dict:
    """Stagioni passate da data/storico_stagioni.json (import_storico_stagioni.py), dalla
    più recente. Solo contesto: non entra nel valore (il backtest non lo sostiene ancora)."""
    path = store.DATA_DIR / "storico_stagioni.json"
    return store.load_json(path)["stagioni"] if path.exists() else {}


def _quando(data_utc: str) -> str:
    return datetime.fromisoformat(data_utc.replace("Z", "+00:00")).astimezone(ROMA).strftime("%d/%m")


def _scadenza(turno: dict) -> str | None:
    """La formazione va inserita prima dell'inizio della partita che apre la giornata:
    la prima non rinviata del turno. Solo se il turno si ricostruisce dalle date."""
    giocate = [m for m in turno["partite"] if m["stato"] != "postponed"]
    if not turno["chiaro"] or not giocate:
        return None
    inizio = datetime.fromisoformat(giocate[0]["data_utc"].replace("Z", "+00:00")).astimezone(ROMA)
    return (
        f"Scadenza formazione: {inizio.strftime('%d/%m alle %H:%M')} (ora italiana), inizio di "
        f"{giocate[0]['squadra_casa']}-{giocate[0]['squadra_trasferta']}"
    )


def _partita(e: dict) -> str:
    """Prossima partita della squadra del giocatore, dal calendario: avversario, casa/trasferta, data."""
    m = e.get("partita")
    if not m:
        return "prossima partita: n/d"
    squadra = e["player"]["serie_a_team"]
    casa = m["squadra_casa"] == squadra
    avversario = m["squadra_trasferta"] if casa else m["squadra_casa"]
    rinviata = " RINVIATA" if m["stato"] == "postponed" else ""
    return f"vs {avversario} ({'C' if casa else 'T'}) {_quando(m['data_utc'])}{rinviata}"


def _rig(e: dict) -> str:
    """Marcatore compatto: solo il primo rigorista, che è l'unico che vale qualcosa
    (+0,26 di fantavoto atteso; il secondo calcia solo se manca il primo, +0,03)."""
    v = e.get("rigorista")
    return " RIG" if v and v.get("consenso_sul_primo") else "    "


def _titolarita(p: dict) -> str:
    prob = p.get("prob_titolare")
    if prob is not None:
        return f"{p['status']} {prob}%"
    return p["status"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--matchday", type=int, default=None)
    args = parser.parse_args()

    config = store.load_league_config()
    regole = config.get("regole_lega", {})
    panchina_cfg = {k: v for k, v in (regole.get("panchina") or {}).items() if k in "PDCA"}
    if panchina_cfg:
        composizione = ", ".join(f"{n} {role}" for role, n in panchina_cfg.items())
        cambi = f"panchina di {sum(panchina_cfg.values())} ({composizione}), cambi solo tra pari ruolo"
    elif regole.get("sostituzioni_max") is None:
        cambi = "cambi illimitati nello stesso ruolo"
    else:
        cambi = f"massimo {regole.get('sostituzioni_max')} cambi"
    r = suggest_lineup(args.team_id)

    matchday_label = f"Giornata {args.matchday}" if args.matchday else "Prossima giornata"
    print(f"{matchday_label} — modalità {config['mode']}, {cambi}")
    turno = r["turno"]
    if turno["partite"] and turno["chiaro"]:
        print(
            f"Prossimo turno dal calendario: {_quando(turno['partite'][0]['data_utc'])} - "
            f"{_quando(turno['partite'][-1]['data_utc'])} ({len(turno['partite'])} partite)"
        )
    scadenza = _scadenza(turno)
    if scadenza:
        print(scadenza)

    if r["modulo"]:
        print(f"Modulo consigliato: {r['modulo']}")
        print("Il numero è il fantavoto atteso se il giocatore prende voto, e ordina ogni ruolo:")
        print("  voti = media degli ultimi 5 voti, avvicinata alla media del ruolo se sono pochi;")
        if PRODUZIONE_PREDEFINITA:
            print("  prod = correzione dei gol su azione con quelli attesi dai tiri in porta;")
        print("  avv  = quanto subisce l'avversario rispetto alla media del campionato.")
        print("La probabilità di giocare NON entra nel numero: se un titolare non prende voto")
        print("entra il primo della panchina del suo ruolo, quindi conviene sempre mettere")
        print("avanti il più forte. Entra invece nella scelta di CHI va in panchina e del")
        print("modulo, perché i posti in panchina sono pochi e uno slot scoperto vale 0.\n")
        panchina_per_ruolo = {}
        for e in r["panchina"]:
            panchina_per_ruolo.setdefault(e["player"]["role"], []).append(e["player"]["name"])
        print("TITOLARI:")
        for e in r["titolari"]:
            p = e["player"]
            riga = f"  [{p['role']}] {p['name']:<18} {_voti(e['rating']):<39}{_rig(e)} {_titolarita(p):<17} {_partita(e)}"
            prob = p.get("prob_titolare")
            politico = e["rating"] and e["rating"].get("politico")
            if prob is not None and prob < 75 and not politico and panchina_per_ruolo.get(p["role"]):
                riga += f"   <- se non gioca entra {panchina_per_ruolo[p['role']][0]}"
            print(riga)
    else:
        print("Nessuna formazione consigliata.")

    if r["modulo"]:
        totale = sum(r["panchina_cfg"].values()) if r["panchina_cfg"] else len(r["panchina"])
        print(f"\nPANCHINA — {len(r['panchina'])} di {totale} posti "
              "(per ogni titolare senza voto entra il primo del suo ruolo;")
        print("se le riserve di quel ruolo finiscono, lo slot vale 0):")
    elif r["panchina"]:
        print("\nROSA PER RUOLO:")
    contatori = {}
    for e in r["panchina"]:
        p = e["player"]
        contatori[p["role"]] = contatori.get(p["role"], 0) + 1
        etichetta = f"{p['role']}{contatori[p['role']]}"
        print(f"  {etichetta:<3} {p['name']:<18} {_voti(e['rating']):<39}{_rig(e)} {_titolarita(p):<17} {_partita(e)}")

    if r["modulo"] and r["esclusi"]:
        print("\nFUORI DISTINTA (la panchina ha pochi posti per ruolo: questi non entrano):")
        for e in r["esclusi"]:
            p = e["player"]
            print(f"  [{p['role']}] {p['name']:<18} {_voti(e['rating']):<30} {_titolarita(p):<17} {_partita(e)}")

    if r["modulo"] and r["copertura"]:
        print("\nRISCHIO SLOT VUOTO per ruolo (probabilità che tutti gli slot siano coperti;")
        print("calcolata sulla probabilità di partire titolare, quindi prudente):")
        piu_esposto = min(r["copertura"].values())
        for role, coperto in sorted(r["copertura"].items(), key=lambda x: x[1]):
            print(f"  {role}: coperto al {coperto:6.1%}   rischio {1 - coperto:.1%}"
                  + ("  <- il più esposto" if coperto == piu_esposto else ""))

    if r["modulo"] and r["atteso"] is not None:
        print(f"\nPUNTEGGIO ATTESO: {r['atteso']:.1f} punti (somma degli 11 slot, già scontata per")
        print("chi rischia di non prendere voto e per gli slot che possono restare vuoti).")
        soglie = regole.get("soglie_gol") or {}
        if soglie.get("primo_gol"):
            primo, fascia = float(soglie["primo_gol"]), float(soglie["fascia"])
            gol = 0 if r["atteso"] < primo else int((r["atteso"] - primo) // fascia) + 1
            prossima_soglia = primo if gol == 0 else primo + gol * fascia
            manca = prossima_soglia - r["atteso"]
            print(f"  Con le soglie della lega (primo gol a {primo:.0f}, poi ogni {fascia:.0f}): "
                  f"{gol} gol.")
            print(f"  Per il gol successivo servono {prossima_soglia:.0f} punti, cioè {manca:+.1f}: "
                  + ("una decisione da meno di questo non cambia il risultato."
                     if manca > 0.5 else "sei sul filo, qui ogni decimale conta."))
            if soglie.get("da_confermare"):
                print("  ATTENZIONE: le soglie gol non sono confermate dalla lega, sono i valori")
                print("  standard di fantacalcio.it. Da verificare nel pannello della lega.")

    in_rosa = [e for e in r["titolari"] + r["panchina"] + r["esclusi"] if e.get("rigorista")]
    if in_rosa:
        valore = r["valore_rigorista"]
        print(f"\nRIGORISTI IN ROSA (RIG sulle righe sopra = primo rigorista, vale circa "
              f"+{valore:.2f} di")
        print("fantavoto atteso a partita). NON è dentro il numero, perché la media degli ultimi")
        print("voti contiene già i rigori davvero calciati e non si possono togliere: serve come")
        print("spareggio quando due giocatori sono equivalenti. Le gerarchie non sono un dato")
        print("ufficiale, sono pareri di giornali che spesso non concordano:")
        for e in sorted(in_rosa, key=lambda x: (x["rigorista"]["rango"], x["player"]["name"])):
            v, p = e["rigorista"], e["player"]
            tot = v["fonti_totali_sulla_squadra"]
            primo = v.get("fonti_che_lo_danno_primo", 0)
            if v["consenso_sul_primo"]:
                quanto = f"PRIMO rigorista ({primo} fonti su {tot} lo dicono)"
            elif primo:
                quanto = f"{v['rango']}º, ma {primo} fonte su {tot} lo dà primo"
            else:
                quanto = f"{v['rango']}º nella gerarchia: vale poco"
            nota = ""
            if v["consenso_sul_primo"] and e["rigori_calciati"]:
                nota = (f" — ne ha già calciato {e['rigori_calciati']}, la sua media lo "
                        "contiene già in parte")
            print(f"  [{p['role']}] {p['name']:<18} {v['squadra']:<12} {quanto}{nota}")

    lega = prossima_partita_lega(args.team_id)
    if lega:
        dove = "in casa" if lega["casa"] else "in trasferta"
        print(f"\nAVVERSARIO DI LEGA: {lega['avversario_nome']}, {dove} "
              f"({lega['competizione']}, giornata {lega['giornata']} = Serie A {lega['giornata_serie_a']}).")
        avv, mio = lega["avversario"], lega["mio"]
        if avv["giocate"]:
            print(f"  Lui: {avv['punti'] / avv['giocate']:.1f} punti di media in {avv['giocate']} "
                  f"giornate, {avv['classifica']} punti in classifica.")
            print(f"  Tu:  {mio['punti'] / mio['giocate']:.1f} punti di media in {mio['giocate']} "
                  f"giornate, {mio['classifica']} punti in classifica.")
        else:
            print("  Prima giornata della lega: non c'è ancora storico per confrontarvi.")

    if r["modulo"]:
        print("\nDA COSA È FATTO IL VALORE (titolari e primi due cambi di ogni ruolo):")
        primi = {}
        for e in r["panchina"]:
            primi.setdefault(e["player"]["role"], []).append(e)
        for e in r["titolari"] + [e for role in "PDCA" for e in primi.get(role, [])[:2]]:
            print(f"  {_dettaglio(e)}")

    storico = _storico()
    if storico and (r["titolari"] or r["panchina"]):
        stagioni = list(storico)[:2]
        print(f"\nSTAGIONI PASSATE in Serie A ({', '.join(stagioni)}; solo contesto, non entra nel valore):")
        for e in r["titolari"] + r["panchina"]:
            p = e["player"]
            dati = " | ".join(f"{s}: {_stagione(storico[s]['giocatori'].get(p['id']))}" for s in stagioni)
            print(f"  [{p['role']}] {p['name']:<16} {dati}")

    if r["decisioni"]:
        print(f"\nDECISIONI TUE (sotto {SOGLIA_PARI:.2f} di differenza il modello non sa scegliere meglio di una moneta):")
        for d in r["decisioni"]:
            print(f"  - {d}")

    if r["non_disponibili"]:
        print("\nNON DISPONIBILI:")
        for nd in r["non_disponibili"]:
            p = nd["player"]
            print(f"  [{p['role']}] {p['name']:<22} {nd['motivo']}")

    if r["avvisi"]:
        print("\nDA VERIFICARE A MANO:")
        for a in r["avvisi"]:
            print(f"  - {a}")


if __name__ == "__main__":
    main()
