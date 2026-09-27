#!/usr/bin/env python3
"""Supporto alle notizie sulle squadre della mia rosa (data/notizie_rosa.json).

Le notizie le cerca chi esegue la skill `aggiorna-dati` o `formazione` con la ricerca
web: questo script non va su internet. Serve a due cose:

- `squadre`: stampa le squadre di Serie A dei miei giocatori, con i giocatori di
  ciascuna e la prossima partita, cioè cosa cercare;
- `valida`: controlla il file (campi, tipi, date, almeno una fonte per notizia), toglie
  le notizie scadute (GIORNI_VALIDITA giorni, di più per allenatore e mercato) e
  ordina. Se trova errori non
  riscrive niente e li elenca.

Formato del file:
    {
      "aggiornato_il": "AAAA-MM-GG",
      "notizie": [
        {
          "data": "AAAA-MM-GG",          # quando è successo o è stato pubblicato
          "squadra": "Bologna",          # come in players.json (serie_a_team)
          "giocatori": ["fd1234"],       # id del listone coinvolti, anche vuoto
          "tipo": "allenatore",          # uno di TIPI
          "fatto": "Tedesco esonerato, al suo posto Palladino.",
          "fonti": ["https://..."],      # almeno una
          "verificata": true,            # 2 fonti indipendenti o fonte ufficiale
          "aggiunta_il": "AAAA-MM-GG"
        }
      ]
    }

Uso:
    python3 scripts/notizie_rosa.py squadre
    python3 scripts/notizie_rosa.py valida
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib.roster import prossimo_turno, team_roster

PATH = store.DATA_DIR / "notizie_rosa.json"
TIPI = {"allenatore", "infortunio", "rientro", "formazione", "rigori", "squalifica", "mercato", "clima", "altro"}
# Dopo quanti giorni una notizia esce dal file: un infortunio o una probabile
# formazione invecchiano in fretta, un cambio di allenatore o un trasferimento no.
GIORNI_VALIDITA = 30
GIORNI_VALIDITA_LUNGA = {"allenatore": 90, "mercato": 90}
CAMPI = {"data", "squadra", "giocatori", "tipo", "fatto", "fonti", "verificata", "aggiunta_il"}


def squadre() -> int:
    config = store.load_league_config()
    players_by_id = {p["id"]: p for p in store.load_players()}
    rosa, _ = team_roster(config["my_team_id"], players_by_id)
    turno = prossimo_turno()
    per_squadra = {}
    for p in rosa:
        per_squadra.setdefault(p["serie_a_team"], []).append(p)
    for squadra in sorted(per_squadra):
        nomi = ", ".join(f"{p['name']} ({p['role']}, {p['id']})" for p in per_squadra[squadra])
        partita = turno["per_squadra"].get(squadra)
        prossima = f"{partita['squadra_casa']}-{partita['squadra_trasferta']} {partita['data_utc'][:10]}" if partita else "prossima partita non ricostruibile"
        print(f"{squadra}: {nomi} | {prossima}")
    return 0


def _data(testo, campo, i, errori):
    try:
        return date.fromisoformat(testo)
    except (TypeError, ValueError):
        errori.append(f"notizia {i}: {campo} {testo!r} non è una data AAAA-MM-GG")
        return None


def valida() -> int:
    if not PATH.exists():
        print(f"{PATH.name} non esiste: niente da validare")
        return 0
    archivio = store.load_json(PATH)
    squadre_note = {p["serie_a_team"] for p in store.load_players()}
    ids = {p["id"] for p in store.load_players()}
    errori, tenute, tolte = [], [], 0
    for i, n in enumerate(archivio.get("notizie", [])):
        mancanti = CAMPI - set(n)
        if mancanti:
            errori.append(f"notizia {i}: mancano {sorted(mancanti)}")
            continue
        quando = _data(n["data"], "data", i, errori)
        _data(n["aggiunta_il"], "aggiunta_il", i, errori)
        if n["tipo"] not in TIPI:
            errori.append(f"notizia {i}: tipo {n['tipo']!r} non in {sorted(TIPI)}")
        if n["squadra"] not in squadre_note:
            errori.append(f"notizia {i}: squadra {n['squadra']!r} non è una squadra del listone")
        if not n["fonti"] or not all(str(f).startswith("http") for f in n["fonti"]):
            errori.append(f"notizia {i}: servono una o più fonti (link)")
        sconosciuti = [g for g in n["giocatori"] if g not in ids]
        if sconosciuti:
            errori.append(f"notizia {i}: giocatori non nel listone {sconosciuti}")
        if not isinstance(n["verificata"], bool):
            errori.append(f"notizia {i}: verificata deve essere true o false")
        giorni = GIORNI_VALIDITA_LUNGA.get(n["tipo"], GIORNI_VALIDITA)
        if quando and quando < date.today() - timedelta(days=giorni):
            tolte += 1
            continue
        tenute.append(n)
    if errori:
        print("Errori, niente di riscritto:")
        for e in errori:
            print(f"  - {e}")
        return 1
    tenute.sort(key=lambda n: (n["data"], n["squadra"]), reverse=True)
    archivio["notizie"] = tenute
    store.save_json(PATH, archivio)
    print(f"{len(tenute)} notizie valide, {tolte} scadute tolte")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("comando", choices=["squadre", "valida"])
    args = parser.parse_args()
    return squadre() if args.comando == "squadre" else valida()


if __name__ == "__main__":
    sys.exit(main())
