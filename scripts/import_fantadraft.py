#!/usr/bin/env python3
"""Importa il listone + infortuni da FantaDraft (github.com/lucianomurr/FantaDraft,
MIT, dati aggregati da fonti pubbliche: quotazioni ufficiali, FBref, Gazzetta).

Scarica players_pen.json (o legge un file locale già scaricato) e popola
data/players.json (listone completo, quotazione + FVM) e data/injuries.json
(infortuni con descrizione e rientro previsto, dove presenti).

Uso:
    python3 scripts/import_fantadraft.py                      # scarica dal repo
    python3 scripts/import_fantadraft.py --json /path/to/players_pen.json
"""
import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store

DEFAULT_URL = "https://raw.githubusercontent.com/lucianomurr/FantaDraft/main/players_pen.json"


def load_source(json_path: str | None):
    if json_path:
        with open(json_path, encoding="utf-8") as f:
            return json.load(f)
    with urllib.request.urlopen(DEFAULT_URL) as resp:
        return json.load(resp)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=None, help="File locale già scaricato, invece di fetch da github")
    args = parser.parse_args()

    source = load_source(args.json)
    existing = {p["id"]: p for p in store.load_players()}

    players = []
    injuries = []
    for row in source:
        pid = f"fd{row['id']}"
        prev = existing.get(pid, {})
        players.append(
            {
                "id": pid,
                "name": row["n"],
                "role": row["r"],
                "serie_a_team": row["s"],
                "quotazione": row["q"],
                "fvm": row.get("f"),
                "status": prev.get("status", "n/d"),
                "status_note": prev.get("status_note", ""),
                "status_updated_at": prev.get("status_updated_at", ""),
                "prob_titolare": prev.get("prob_titolare"),
            }
        )
        inj = row.get("inj")
        if inj:
            injuries.append(
                {
                    "player_id": pid,
                    "start_date": None,
                    "expected_return": inj.get("r"),
                    "description": inj.get("d"),
                    "status": "in corso",
                    "source": "fantadraft_import",
                    "imported_on": date.today().isoformat(),
                }
            )

    store.save_json(store.DATA_DIR / "players.json", players)
    store.save_json(store.DATA_DIR / "injuries.json", injuries)
    print(f"Importati {len(players)} giocatori e {len(injuries)} infortuni segnalati.")
    print("Fonte: github.com/lucianomurr/FantaDraft (dati aggregati da fonti pubbliche, MIT).")
    print("NB: quotazioni generiche di mercato, non quelle personalizzate della tua lega se diverse.")


if __name__ == "__main__":
    main()
