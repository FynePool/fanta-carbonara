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


def load_injuries():
    return load_json(DATA_DIR / "injuries.json")


def load_market_log():
    return load_json(DATA_DIR / "market_log.json")
