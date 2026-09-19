#!/usr/bin/env python3
"""Importa lo storico gol/assist/cartellini/falli/minuti per giocatore per
partita da BigBalls Sports Data API, in data/matchday_stats.json.

Fonte verificata in questa sessione con una chiamata reale:
GET /v1/stored/matches/{id}/stats restituisce un box score completo per
ogni giocatore delle due squadre (gol, assist, cartellini gialli/rossi,
falli commessi/subiti, minuti, più extra come tiri/passaggi/duelli — non
tutti importati qui). NON è il voto fantacalcio: il campo "rating" che la
fonte restituisce è un rating generico (tipo Opta/Sofascore), calcolato con
criteri diversi da quello di fantacalcio.it/leghe.fantacalcio.it, che è
l'unico che conta per lo scoring. `voto` e `fantavoto` restano quindi
sempre null qui: vanno riempiti da un'altra fonte quando l'API di
leghe.fantacalcio.it sarà verificabile con una lega reale.

Gira su tutte le partite "finished" di data/calendario_serie_a.json (va
quindi rilanciato import_calendario_seriea.py prima, se serve aggiornarlo).

Matching giocatore: i nomi di BigBalls non sono coerenti tra loro (a volte
"M. Koné", a volte "Lautaro Martínez" per la stessa fonte) e non
condividono id con data/players.json (che usa "Cognome Iniziale.", es.
"Martinez L."). Il matching è euristico per squadra + cognome (+ iniziale
per disambiguare cognomi ripetuti nella stessa squadra): mai indovinato,
i "non trovati/ambigui" vengono stampati e NON scritti in matchday_stats.json.

Richiede BIGBALLS_API_KEY da ambiente. Merge idempotente per
(player_id, match_id): rilanciarlo aggiorna, non duplica.

Uso:
    python3 scripts/import_matchday_stats.py
"""
import os
import sys
import unicodedata
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from import_calendario_seriea import normalize_team

API_BASE_URL = "https://api.bigballsdata.com/v1"

STAT_FIELDS = {
    "gol": "goals",
    "assist": "assists",
    "cartellini_gialli": "yellow_cards",
    "cartellini_rossi": "red_cards",
    "falli_commessi": "fouls_committed",
    "falli_subiti": "fouls_drawn",
    "minuti": "minutes",
}


EXTRA_ACCENTS = str.maketrans({
    "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ł": "l", "Ł": "L",
    "đ": "d", "Đ": "D", "ß": "ss",
})
NAME_PARTICLES = {"de", "van", "von", "da", "di", "la", "le", "mc", "du", "dos", "del"}


def strip_accents(s: str) -> str:
    s = s.translate(EXTRA_ACCENTS)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def split_name(raw: str):
    """Ritorna (cognome_normalizzato, iniziale_o_None) da un nome grezzo,
    gestendo 'Martinez L.'/'Konè M.' (Cognome Iniziale, formato di
    data/players.json), 'M. Koné' (Iniziale Cognome, formato BigBalls),
    'Lautaro Martínez' (Nome Cognome, con eventuali particelle come
    'De Bruyne') e 'Svilar'/'Vítinha' (solo cognome)."""
    tokens = strip_accents(raw).lower().replace(".", "").split()
    if not tokens:
        return "", None
    if len(tokens) == 1:
        return tokens[0], None
    if len(tokens[-1]) == 1:  # "martinez l" -> cognome iniziale
        return " ".join(tokens[:-1]), tokens[-1]
    if len(tokens[0]) == 1:  # "m kone" -> iniziale cognome
        return " ".join(tokens[1:]), tokens[0]
    # "lautaro martinez" / "kevin de bruyne" -> nome [particelle] cognome
    i = len(tokens) - 1
    while i > 0 and tokens[i - 1] in NAME_PARTICLES:
        i -= 1
    return " ".join(tokens[i:]), tokens[0][0]


def build_player_index(players: list[dict]):
    """(squadra, cognome) -> lista di (player_id, iniziale_o_None)."""
    index: dict[tuple[str, str], list] = {}
    for p in players:
        cognome, iniziale = split_name(p["name"])
        index.setdefault((p["serie_a_team"], cognome), []).append((p["id"], iniziale))
    return index


def match_player(index: dict, team: str, raw_name: str):
    cognome, iniziale = split_name(raw_name)
    candidates = index.get((team, cognome), [])
    if len(candidates) == 1:
        return candidates[0][0]
    if len(candidates) > 1 and iniziale:
        matches = [pid for pid, i in candidates if i == iniziale]
        if len(matches) == 1:
            return matches[0]
    return None


def fetch_match_stats(api_key: str, match_id: str):
    resp = requests.get(
        f"{API_BASE_URL}/stored/matches/{match_id}/stats",
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code} — {resp.text[:200]}")
    return resp.json().get("data", {}).get("players", [])


def main():
    api_key = os.environ.get("BIGBALLS_API_KEY")
    if not api_key:
        print("ERRORE: imposta BIGBALLS_API_KEY come variabile d'ambiente.")
        return 1

    calendario = [m for m in store.load_json(store.DATA_DIR / "calendario_serie_a.json") if m["stato"] == "finished"]
    players = store.load_players()
    index = build_player_index(players)

    stats_path = store.DATA_DIR / "matchday_stats.json"
    existing = store.load_json(stats_path) if stats_path.exists() else []
    by_key = {(r["player_id"], r["match_id"]): r for r in existing}

    unmatched = []
    failed_matches = []

    for match in calendario:
        try:
            player_rows = fetch_match_stats(api_key, match["match_id"])
        except RuntimeError as e:
            failed_matches.append((match["match_id"], str(e)))
            continue

        for pr in player_rows:
            team = normalize_team(pr["team_name"])
            player_id = match_player(index, team, pr["name"])
            if player_id is None:
                unmatched.append((match["match_id"], team, pr["name"]))
                continue

            if team == match["squadra_casa"]:
                opponent, home_away = match["squadra_trasferta"], "casa"
            else:
                opponent, home_away = match["squadra_casa"], "trasferta"

            row = {
                "player_id": player_id,
                "match_id": match["match_id"],
                "matchday": match["giornata"],
                "opponent_serie_a_team": opponent,
                "home_away": home_away,
                "voto": None,
                "fantavoto": None,
            }
            for field, source_key in STAT_FIELDS.items():
                raw_value = pr["stats"].get(source_key, {}).get("value")
                row[field] = int(raw_value) if raw_value is not None else 0

            by_key[(player_id, match["match_id"])] = row

    merged = sorted(by_key.values(), key=lambda r: (r["matchday"] or 0, r["match_id"], r["player_id"]))
    store.save_json(stats_path, merged)

    print(f"OK: {len(merged)} righe totali in matchday_stats.json.")
    if failed_matches:
        print(f"ATTENZIONE: {len(failed_matches)} partite non scaricate: {failed_matches}")
    if unmatched:
        print(f"ATTENZIONE: {len(unmatched)} giocatori non riconosciuti (non scritti, verificare a mano):")
        for match_id, team, name in unmatched:
            print(f"  match={match_id} squadra={team!r} nome={name!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
