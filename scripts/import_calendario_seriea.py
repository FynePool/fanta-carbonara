#!/usr/bin/env python3
"""Importa calendario e risultati di Serie A da BigBalls Sports Data API
(bigballsdata.com), in data/calendario_serie_a.json.

Fonte verificata in questa sessione via il connettore MCP BigBallsFootbal:
copre Serie A dal 2014-15 alla stagione corrente, con risultato, giornata
("round", es. "Regular Season - 5") e squadre casa/trasferta. NON copre
statistiche per giocatore (gol/cartellini/minuti) né il voto fantacalcio:
per quello serve un'altra fonte (vedi CLAUDE.md).

I nomi squadra di BigBalls non coincidono sempre con quelli di
data/players.json (es. "AS Roma" vs "Roma", "Inter Milan" vs "Inter"):
NAME_MAP li normalizza. Se BigBalls introduce un nome nuovo non mappato,
lo script lo segnala invece di indovinare.

Alcune partite finite da pochissimo possono avere "round" nullo per un
ritardo della fonte: restano nello storico con giornata=null, mai stimata
a mano, e vanno controllate a mano quando l'API si aggiorna.

Richiede BIGBALLS_API_KEY come variabile d'ambiente (mai in chat, mai
committata). Merge idempotente su data/calendario_serie_a.json: le
partite già presenti (stesso match_id) vengono aggiornate, non duplicate.

Uso:
    python3 scripts/import_calendario_seriea.py --season 2026
    python3 scripts/import_calendario_seriea.py --season 2026 --status finished
"""
import argparse
import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store

API_BASE_URL = "https://api.bigballsdata.com/v1"
LEAGUE = "serie_a"

NAME_MAP = {
    "AS Roma": "Roma",
    "Inter Milan": "Inter",
    "AC Milan": "Milan",
    "Como 1907": "Como",
    "Venezia FC": "Venezia",
}

ROUND_RE = re.compile(r"(\d+)\s*$")


def normalize_team(name: str) -> str:
    return NAME_MAP.get(name, name)


def parse_giornata(round_label):
    if not round_label:
        return None
    match = ROUND_RE.search(round_label)
    return int(match.group(1)) if match else None


def fetch_matches(api_key: str, season: int, status: str | None):
    matches = []
    offset = 0
    limit = 200
    while True:
        params = {
            "sport": "football",
            "league": LEAGUE,
            "season": season,
            "limit": limit,
            "offset": offset,
        }
        if status:
            params["status"] = status
        resp = requests.get(
            f"{API_BASE_URL}/matches",
            params=params,
            headers={"x-api-key": api_key, "Accept": "application/json"},
            timeout=30,
        )
        if not resp.ok:
            raise RuntimeError(f"Richiesta fallita: HTTP {resp.status_code} — {resp.text[:300]}")
        page = resp.json().get("data", [])
        if not page:
            break
        matches.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return matches


def to_row(match: dict, season_label: str) -> dict:
    score = match.get("score") or {}
    return {
        "match_id": match["id"],
        "stagione": season_label,
        "giornata": parse_giornata(match.get("round")),
        "giornata_raw": match.get("round"),
        "data_utc": match["kickoff_utc"],
        "squadra_casa": normalize_team(match["home"]["name"]),
        "squadra_trasferta": normalize_team(match["away"]["name"]),
        "gol_casa": score.get("home"),
        "gol_trasferta": score.get("away"),
        "stato": match["status"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True, help="Anno di inizio stagione, es. 2026 per 2026-27")
    parser.add_argument("--status", choices=["scheduled", "live", "finished", "postponed", "cancelled"], default=None)
    args = parser.parse_args()

    api_key = os.environ.get("BIGBALLS_API_KEY")
    if not api_key:
        print("ERRORE: imposta BIGBALLS_API_KEY come variabile d'ambiente.")
        return 1

    known_teams = {p["serie_a_team"] for p in store.load_players()}
    season_label = f"{args.season}-{str(args.season + 1)[-2:]}"

    raw_matches = fetch_matches(api_key, args.season, args.status)
    rows = [to_row(m, season_label) for m in raw_matches]

    unknown_teams = {
        t
        for r in rows
        for t in (r["squadra_casa"], r["squadra_trasferta"])
        if t not in known_teams
    }
    if unknown_teams:
        print(
            "ATTENZIONE: squadre non riconosciute rispetto a data/players.json "
            f"(aggiungi un mapping in NAME_MAP): {sorted(unknown_teams)}"
        )

    calendario_path = store.DATA_DIR / "calendario_serie_a.json"
    existing = store.load_json(calendario_path) if calendario_path.exists() else []
    by_id = {r["match_id"]: r for r in existing}
    for row in rows:
        by_id[row["match_id"]] = row

    merged = sorted(by_id.values(), key=lambda r: (r["data_utc"], r["match_id"]))
    store.save_json(calendario_path, merged)

    no_giornata = sum(1 for r in rows if r["giornata"] is None)
    print(f"OK: {len(rows)} partite importate/aggiornate (totale storico: {len(merged)}).")
    if no_giornata:
        print(f"ATTENZIONE: {no_giornata} partite senza giornata riconosciuta (round nullo dalla fonte) — verificare a mano.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
