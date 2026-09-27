import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_league_config():
    return load_json(CONFIG_DIR / "league.json")


def load_teams():
    return load_json(DATA_DIR / "teams.json")


def load_players():
    return load_json(DATA_DIR / "players.json")


def load_ownership():
    return load_json(DATA_DIR / "ownership.json")


def load_matchday_stats():
    return load_json(DATA_DIR / "matchday_stats.json")


class StoricoPerso(Exception):
    pass


def save_matchday_stats(rows: list[dict]) -> None:
    """Unico modo di scrivere data/matchday_stats.json: lo storico si aggiorna, non si
    accorcia mai. Se una riga (player_id, match_id) già su disco manca da `rows`, non
    scrive niente e alza StoricoPerso. I voti vecchi possono non essere più recuperabili
    dalle fonti, e un giocatore uscito dal listone (venduto all'estero) resta nello storico."""
    path = DATA_DIR / "matchday_stats.json"
    if path.exists():
        nuove = {(r["player_id"], r["match_id"]) for r in rows}
        perse = [k for k in ((r["player_id"], r["match_id"]) for r in load_json(path)) if k not in nuove]
        if perse:
            raise StoricoPerso(
                f"{len(perse)} righe dello storico sparirebbero (es. {perse[:3]}): niente scritto."
            )
    save_json(path, rows)


def load_injuries():
    return load_json(DATA_DIR / "injuries.json")


def load_market_log():
    return load_json(DATA_DIR / "market_log.json")
