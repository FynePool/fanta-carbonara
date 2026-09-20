from collections import defaultdict
from statistics import mean

from . import store

EXCLUDED_STATUSES = {"infortunato", "squalificato"}
UNCERTAIN_STATUSES = {"dubbio", "ballottaggio", "panchina"}

# Role counts per module, excluding the goalkeeper (always 1).
MODULE_ROLE_COUNTS = {
    "3-4-3": {"D": 3, "C": 4, "A": 3},
    "3-5-2": {"D": 3, "C": 5, "A": 2},
    "4-3-3": {"D": 4, "C": 3, "A": 3},
    "4-4-2": {"D": 4, "C": 4, "A": 2},
    "4-5-1": {"D": 4, "C": 5, "A": 1},
    "5-3-2": {"D": 5, "C": 3, "A": 2},
    "5-4-1": {"D": 5, "C": 4, "A": 1},
}


def team_roster(team_id: str):
    players = {p["id"]: p for p in store.load_players()}
    ownership = store.load_ownership()
    return [
        {**players[o["player_id"]], "purchase_price": o["purchase_price"]}
        for o in ownership
        if o["team_id"] == team_id and o["player_id"] in players
    ]


def _matchday_sort_key(row: dict):
    """La giornata può essere nulla: la fonte la etichetta con circa un giorno di
    ritardo, quindi una riga senza giornata è quasi sempre la più recente. Va in
    fondo all'ordinamento invece di far fallire il confronto int/None."""
    matchday = row.get("matchday")
    return (1, 0) if matchday is None else (0, matchday)


def average_fantavoto(player_id: str, last_n: int | None = None):
    rows = [r for r in store.load_matchday_stats() if r["player_id"] == player_id]
    rows.sort(key=_matchday_sort_key)
    if last_n:
        rows = rows[-last_n:]
    votes = [r["fantavoto"] for r in rows if r.get("fantavoto") is not None]
    return mean(votes) if votes else None


def player_history_vs_opponent(player_id: str, opponent_serie_a_team: str):
    return [
        r
        for r in store.load_matchday_stats()
        if r["player_id"] == player_id
        and r["opponent_serie_a_team"] == opponent_serie_a_team
    ]


def score_player(player: dict) -> float | None:
    """Score used to rank a player for the starting XI. None = cannot be scored (missing data)."""
    if player["status"] in EXCLUDED_STATUSES:
        return None
    avg = average_fantavoto(player["id"], last_n=5)
    if avg is None:
        return None  # no history yet -> needs a manual call, flagged in the report
    if player["status"] in UNCERTAIN_STATUSES:
        avg -= 1.5  # simple penalty for uncertain starting status
    return avg


def suggest_lineup(team_id: str, allowed_modules: list[str] | None = None):
    """Greedy suggestion: for each candidate module, pick the best-scoring players per role
    and keep the module with the highest total. Returns (module, starters, bench, flags)."""
    config = store.load_league_config()
    modules = allowed_modules or config["formation_modules"]
    roster = team_roster(team_id)

    by_role = defaultdict(list)
    for p in roster:
        by_role[p["role"]].append(p)

    flags = []
    for p in roster:
        if score_player(p) is None and p["status"] not in EXCLUDED_STATUSES:
            flags.append(
                f"{p['name']}: nessuno storico fantavoto disponibile, valutazione manuale necessaria"
            )
        if p["status"] in EXCLUDED_STATUSES:
            flags.append(f"{p['name']}: escluso ({p['status']})")

    best = None
    for module in modules:
        counts = {"P": 1, **MODULE_ROLE_COUNTS[module]}
        starters = []
        ok = True
        for role, n in counts.items():
            candidates = sorted(
                (p for p in by_role.get(role, []) if score_player(p) is not None),
                key=lambda p: score_player(p),
                reverse=True,
            )
            if len(candidates) < n:
                ok = False
                break
            starters.extend(candidates[:n])
        if not ok:
            continue
        total = sum(score_player(p) for p in starters)
        if best is None or total > best["total"]:
            bench_ids = {p["id"] for p in starters}
            bench = [p for p in roster if p["id"] not in bench_ids]
            best = {"module": module, "starters": starters, "bench": bench, "total": total}

    if best is None:
        return None, [], [], flags + ["Nessun modulo schierabile con la rosa attuale e i dati disponibili."]
    return best["module"], best["starters"], best["bench"], flags
