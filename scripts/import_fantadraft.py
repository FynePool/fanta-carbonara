#!/usr/bin/env python3
"""Infortuni da FantaDraft (github.com/lucianomurr/FantaDraft, MIT, dati aggregati da
fonti pubbliche: quotazioni ufficiali, FBref, Gazzetta), in data/injuries.json.

Fino al 27/09/2026 questo script scriveva anche il listone (data/players.json), ma
FantaDraft ha solo una parte dei giocatori (532 su 598): ora il listone arriva da
import_listone_fc.py (fantacalcio.it) e qui si leggono solo gli infortuni. Gli id sono
gli stessi ("fd" + id fantacalcio).

injuries.json viene riscritto da zero con i soli infortuni in corso: chi è rientrato
sparisce da solo (vale la presenza, vedi apply_formazioni_status.py).

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
    listone = {p["id"] for p in store.load_players()}

    injuries, fuori_listone = [], []
    for row in source:
        inj = row.get("inj")
        if not inj:
            continue
        pid = f"fd{row['id']}"
        if pid not in listone:
            fuori_listone.append(f"{row['n']} ({row['s']})")
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

    store.save_json(store.DATA_DIR / "injuries.json", injuries)
    print(f"Importati {len(injuries)} infortuni in corso da {len(source)} giocatori di FantaDraft.")
    if fuori_listone:
        print(f"Nota: {len(fuori_listone)} infortunati non sono nel listone (scritti lo stesso): "
              + ", ".join(fuori_listone))
    print("Fonte: github.com/lucianomurr/FantaDraft (dati aggregati da fonti pubbliche, MIT).")


if __name__ == "__main__":
    main()
