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
from lib.roster import suggest_lineup


def _voti(rating: dict | None) -> str:
    if rating is None:
        return "  -    senza voti"
    if rating.get("politico"):
        return " 6.00  6 politico (rinvio)"
    n = rating["n"]
    return f"{rating['punteggio']:5.2f}  media {rating['media']:.2f} su {n} vot{'o' if n == 1 else 'i'}"


ROMA = ZoneInfo("Europe/Rome")


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
    if "sostituzioni_max" not in regole:
        cambi = "regole sulle sostituzioni non indicate in config/league.json"
    elif regole["sostituzioni_max"] is None:
        cambi = "cambi illimitati nello stesso ruolo"
    else:
        cambi = f"massimo {regole['sostituzioni_max']} cambi"
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
        print("Il numero è il valore usato per scegliere: la media quando gioca, avvicinata")
        print("alla media del ruolo se i voti sono pochi.\n")
        panchina_per_ruolo = {}
        for e in r["panchina"]:
            panchina_per_ruolo.setdefault(e["player"]["role"], []).append(e["player"]["name"])
        print("TITOLARI:")
        for e in r["titolari"]:
            p = e["player"]
            riga = f"  [{p['role']}] {p['name']:<22} {_voti(e['rating']):<34} {_titolarita(p):<17} {_partita(e)}"
            prob = p.get("prob_titolare")
            politico = e["rating"] and e["rating"].get("politico")
            if prob is not None and prob < 75 and not politico and panchina_per_ruolo.get(p["role"]):
                riga += f"   <- se non gioca entra {panchina_per_ruolo[p['role']][0]}"
            print(riga)
    else:
        print("Nessuna formazione consigliata.")

    if r["modulo"]:
        print("\nPANCHINA (in ordine: per ogni titolare senza voto entra il primo del suo ruolo):")
    elif r["panchina"]:
        print("\nROSA PER RUOLO:")
    contatori = {}
    for e in r["panchina"]:
        p = e["player"]
        contatori[p["role"]] = contatori.get(p["role"], 0) + 1
        etichetta = f"{p['role']}{contatori[p['role']]}"
        print(f"  {etichetta:<3} {p['name']:<22} {_voti(e['rating']):<34} {_titolarita(p):<17} {_partita(e)}")

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
