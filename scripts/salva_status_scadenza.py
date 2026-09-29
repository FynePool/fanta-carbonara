#!/usr/bin/env python3
"""Fotografa, prima della scadenza della formazione, quello che il motore sapeva allora:
status e probabilità di partire titolare di ogni giocatore, in data/status_scadenze.json.

Serve al backtest. `backtest_undici.py` schierava le giornate passate escludendo chi è
infortunato **oggi**: guardava il futuro (29/09: 11 voti delle giornate 3-5 presi da
giocatori esclusi perché infortunati dopo, tra cui Busio e Holm). Da questa foto il
backtest sa chi era fuori alla scadenza di ogni giornata, e più avanti si potrà misurare
quanto `prob_titolare` indovina chi prende voto.

Ogni giro del mattino riscrive la foto del prossimo turno finché la scadenza non è
passata; dopo, quella foto non si tocca più. Il turno è quello di `prossimo_turno()`
(le prime 10 partite non giocate, se coprono le 20 squadre): se non si ricostruisce
(recupero, turno già iniziato) non scrive niente. La foto è indicizzata per scadenza e
porta gli id delle partite, non un numero di giornata: la fonte del calendario assegna
la giornata solo dopo che la partita è stata giocata, e qui non si inventa.

Va lanciato dopo apply_formazioni_status.py.

Uso:
    python3 scripts/salva_status_scadenza.py [--dry-run]
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib.roster import prossimo_turno

PATH = store.DATA_DIR / "status_scadenze.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    turno = prossimo_turno()
    giocate = [m for m in turno["partite"] if m["stato"] != "postponed"]
    if not turno["chiaro"] or not giocate:
        print("Il prossimo turno non si ricostruisce dalle date (recupero, rinvio, turno già "
              "iniziato): nessuna foto scritta.")
        return 0
    scadenza = giocate[0]["data_utc"]
    adesso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    players = store.load_players()
    foto = {
        "salvato_il": adesso,
        "partite": sorted(m["match_id"] for m in turno["partite"]),
        "status_aggiornati_al": max((p.get("status_updated_at") or "" for p in players), default="") or None,
        "status": {p["id"]: p["status"] for p in sorted(players, key=lambda p: p["id"])},
        "prob_titolare": {p["id"]: p.get("prob_titolare") for p in sorted(players, key=lambda p: p["id"])},
    }
    doc = store.load_json(PATH) if PATH.exists() else {
        "_note": ("Status e prob_titolare di ogni giocatore com'erano prima della scadenza di "
                  "ogni turno, per il backtest: vedi scripts/salva_status_scadenza.py. Una "
                  "foto per scadenza (ora UTC della prima partita non rinviata del turno); "
                  "si riscrive ogni mattina fino alla scadenza, poi non si tocca più."),
        "scadenze": {},
    }
    esclusi = sum(1 for s in foto["status"].values() if s in ("infortunato", "squalificato"))
    vecchia = doc["scadenze"].get(scadenza)
    print(f"Turno con scadenza {scadenza}: {len(foto['status'])} giocatori, {esclusi} "
          f"infortunati o squalificati, status aggiornati al {foto['status_aggiornati_al']}.")
    if vecchia:
        cambiati = sum(1 for pid in foto["status"]
                       if (vecchia["status"].get(pid), vecchia["prob_titolare"].get(pid))
                       != (foto["status"][pid], foto["prob_titolare"][pid]))
        print(f"Sostituisce la foto del {vecchia['salvato_il']}: {cambiati} giocatori cambiati.")
    if args.dry_run:
        print("--dry-run: niente scritto.")
        return 0
    doc["scadenze"][scadenza] = foto
    doc["scadenze"] = dict(sorted(doc["scadenze"].items()))
    store.save_json(PATH, doc)
    print(f"Scritto {PATH.relative_to(store.ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
