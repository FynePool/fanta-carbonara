#!/usr/bin/env python3
"""Assistente per l'asta live a chiamata: registra gli acquisti di TUTTE le
12 squadre man mano che avvengono, aggiorna crediti/rose, e mostra chi resta
disponibile e quanto budget hai ancora per ruolo.

Comandi:
    assegna       Registra un acquisto (di qualunque squadra, non solo la tua)
    scambio       Registra uno scambio tra due squadre (giocatori e/o crediti)
    svincolo      Svincola un giocatore da una squadra (torna disponibile)
    stato         Mostra crediti e slot rimanenti per ogni squadra
    disponibili   Elenca i giocatori non ancora presi, per ruolo

Esempi:
    python3 scripts/asta.py assegna --player-id p001 --team-id t01 --prezzo 45
    python3 scripts/asta.py scambio --team-a t01 --team-b t02 \\
        --players-a p001,p002 --players-b p010 --credits-b-a 15
    python3 scripts/asta.py svincolo --player-id p001 --team-id t01
    python3 scripts/asta.py svincolo --player-id p001 --team-id t01 --rimborso 5
    python3 scripts/asta.py stato
    python3 scripts/asta.py stato --team-id t01
    python3 scripts/asta.py disponibili --ruolo A --top 15
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store


def cmd_assegna(args):
    players = {p["id"]: p for p in store.load_players()}
    if args.player_id not in players:
        print(f"ERRORE: player-id '{args.player_id}' non trovato in data/players.json")
        return 1

    teams = store.load_teams()
    team = next((t for t in teams if t["id"] == args.team_id), None)
    if team is None:
        print(f"ERRORE: team-id '{args.team_id}' non trovato in data/teams.json")
        return 1

    ownership = store.load_ownership()
    if any(o["player_id"] == args.player_id for o in ownership):
        print(f"ERRORE: {players[args.player_id]['name']} risulta già assegnato.")
        return 1

    if args.prezzo > team["credits_remaining"]:
        print(
            f"ATTENZIONE: {team['name']} ha solo {team['credits_remaining']} crediti "
            f"rimanenti, il prezzo indicato è {args.prezzo}. Registrazione comunque eseguita "
            "(verifica se è un errore di battitura)."
        )

    ownership.append(
        {
            "player_id": args.player_id,
            "team_id": args.team_id,
            "purchase_price": args.prezzo,
            "acquired_on": date.today().isoformat(),
            "acquired_via": "asta",
        }
    )
    store.save_json(store.DATA_DIR / "ownership.json", ownership)

    team["credits_remaining"] -= args.prezzo
    store.save_json(store.DATA_DIR / "teams.json", teams)

    market_log = store.load_market_log()
    market_log.append(
        {
            "date": date.today().isoformat(),
            "type": "asta",
            "team_from": None,
            "team_to": args.team_id,
            "players_out": [],
            "players_in": [args.player_id],
            "credits_from": 0,
            "credits_to": args.prezzo,
            "notes": "",
        }
    )
    store.save_json(store.DATA_DIR / "market_log.json", market_log)

    print(
        f"OK: {players[args.player_id]['name']} ({players[args.player_id]['role']}) -> "
        f"{team['name']} per {args.prezzo} crediti. Crediti rimanenti {team['name']}: "
        f"{team['credits_remaining']}"
    )
    return 0


def _split_ids(raw):
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def cmd_scambio(args):
    teams = {t["id"]: t for t in store.load_teams()}
    if args.team_a not in teams:
        print(f"ERRORE: team-id '{args.team_a}' non trovato in data/teams.json")
        return 1
    if args.team_b not in teams:
        print(f"ERRORE: team-id '{args.team_b}' non trovato in data/teams.json")
        return 1
    if args.team_a == args.team_b:
        print("ERRORE: team-a e team-b devono essere due squadre diverse.")
        return 1

    players_a = _split_ids(args.players_a)
    players_b = _split_ids(args.players_b)
    if not players_a and not players_b and args.credits_a_b == 0 and args.credits_b_a == 0:
        print("ERRORE: lo scambio non muove né giocatori né crediti.")
        return 1

    players = {p["id"]: p for p in store.load_players()}
    for pid in players_a + players_b:
        if pid not in players:
            print(f"ERRORE: player-id '{pid}' non trovato in data/players.json")
            return 1

    ownership = store.load_ownership()
    owner_by_pid = {o["player_id"]: o for o in ownership}
    for pid in players_a:
        o = owner_by_pid.get(pid)
        if o is None or o["team_id"] != args.team_a:
            print(f"ERRORE: {players[pid]['name']} non risulta di proprietà di {teams[args.team_a]['name']}.")
            return 1
    for pid in players_b:
        o = owner_by_pid.get(pid)
        if o is None or o["team_id"] != args.team_b:
            print(f"ERRORE: {players[pid]['name']} non risulta di proprietà di {teams[args.team_b]['name']}.")
            return 1

    team_a = teams[args.team_a]
    team_b = teams[args.team_b]
    if args.credits_a_b > team_a["credits_remaining"]:
        print(
            f"ATTENZIONE: {team_a['name']} ha solo {team_a['credits_remaining']} crediti "
            f"rimanenti, lo scambio ne richiede {args.credits_a_b}. Registrazione comunque eseguita."
        )
    if args.credits_b_a > team_b["credits_remaining"]:
        print(
            f"ATTENZIONE: {team_b['name']} ha solo {team_b['credits_remaining']} crediti "
            f"rimanenti, lo scambio ne richiede {args.credits_b_a}. Registrazione comunque eseguita."
        )

    today = date.today().isoformat()
    for pid in players_a:
        owner_by_pid[pid]["team_id"] = args.team_b
        owner_by_pid[pid]["acquired_via"] = "scambio"
        owner_by_pid[pid]["acquired_on"] = today
    for pid in players_b:
        owner_by_pid[pid]["team_id"] = args.team_a
        owner_by_pid[pid]["acquired_via"] = "scambio"
        owner_by_pid[pid]["acquired_on"] = today
    store.save_json(store.DATA_DIR / "ownership.json", ownership)

    team_a["credits_remaining"] += args.credits_b_a - args.credits_a_b
    team_b["credits_remaining"] += args.credits_a_b - args.credits_b_a
    store.save_json(store.DATA_DIR / "teams.json", list(teams.values()))

    market_log = store.load_market_log()
    market_log.append(
        {
            "date": today,
            "type": "scambio",
            "team_a": args.team_a,
            "team_b": args.team_b,
            "players_from_a": players_a,
            "players_from_b": players_b,
            "credits_from_a": args.credits_a_b,
            "credits_from_b": args.credits_b_a,
            "notes": "",
        }
    )
    store.save_json(store.DATA_DIR / "market_log.json", market_log)

    def _names(ids):
        return ", ".join(players[pid]["name"] for pid in ids) or "—"

    print(
        f"OK: scambio registrato.\n"
        f"  {team_a['name']} -> {team_b['name']}: {_names(players_a)}"
        + (f" + {args.credits_a_b} crediti" if args.credits_a_b else "")
        + "\n"
        f"  {team_b['name']} -> {team_a['name']}: {_names(players_b)}"
        + (f" + {args.credits_b_a} crediti" if args.credits_b_a else "")
        + "\n"
        f"  Crediti rimanenti: {team_a['name']} {team_a['credits_remaining']}, "
        f"{team_b['name']} {team_b['credits_remaining']}"
    )
    return 0


def cmd_svincolo(args):
    players = {p["id"]: p for p in store.load_players()}
    if args.player_id not in players:
        print(f"ERRORE: player-id '{args.player_id}' non trovato in data/players.json")
        return 1

    teams = store.load_teams()
    team = next((t for t in teams if t["id"] == args.team_id), None)
    if team is None:
        print(f"ERRORE: team-id '{args.team_id}' non trovato in data/teams.json")
        return 1

    ownership = store.load_ownership()
    entry = next(
        (o for o in ownership if o["player_id"] == args.player_id and o["team_id"] == args.team_id),
        None,
    )
    if entry is None:
        print(f"ERRORE: {players[args.player_id]['name']} non risulta di proprietà di {team['name']}.")
        return 1

    ownership.remove(entry)
    store.save_json(store.DATA_DIR / "ownership.json", ownership)

    team["credits_remaining"] += args.rimborso
    store.save_json(store.DATA_DIR / "teams.json", teams)

    market_log = store.load_market_log()
    market_log.append(
        {
            "date": date.today().isoformat(),
            "type": "svincolo",
            "team_from": args.team_id,
            "team_to": None,
            "players_out": [args.player_id],
            "players_in": [],
            "credits_from": 0,
            "credits_to": args.rimborso,
            "notes": "",
        }
    )
    store.save_json(store.DATA_DIR / "market_log.json", market_log)

    msg = f"OK: {players[args.player_id]['name']} svincolato da {team['name']}."
    if args.rimborso:
        msg += f" Rimborso {args.rimborso} crediti (rimanenti: {team['credits_remaining']})."
    print(msg)
    return 0


def _team_role_counts(team_id, players, ownership):
    owned_ids = {o["player_id"] for o in ownership if o["team_id"] == team_id}
    counts = {"P": 0, "D": 0, "C": 0, "A": 0}
    for pid in owned_ids:
        p = players.get(pid)
        if p:
            counts[p["role"]] += 1
    return counts


def cmd_stato(args):
    config = store.load_league_config()
    players = {p["id"]: p for p in store.load_players()}
    ownership = store.load_ownership()
    teams = store.load_teams()
    req = config["roster_requirements"]

    targets = [t for t in teams if t["id"] == args.team_id] if args.team_id else teams
    for team in targets:
        counts = _team_role_counts(team["id"], players, ownership)
        slots_left = {r: req[r] - counts[r] for r in req}
        print(f"\n{team['name']} — crediti rimanenti: {team['credits_remaining']}")
        for role in ["P", "D", "C", "A"]:
            print(f"  {role}: {counts[role]}/{req[role]} presi (mancano {slots_left[role]})")
        if all(v == 0 for v in slots_left.values()):
            print("  Rosa completa.")
    return 0


def cmd_disponibili(args):
    players = store.load_players()
    ownership = store.load_ownership()
    owned_ids = {o["player_id"] for o in ownership}
    available = [p for p in players if p["id"] not in owned_ids]
    if args.ruolo:
        available = [p for p in available if p["role"] == args.ruolo]
    available.sort(key=lambda p: p["quotazione"], reverse=True)
    for p in available[: args.top]:
        print(f"  [{p['role']}] {p['name']:<25} {p['serie_a_team']:<15} Qt.A: {p['quotazione']}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_assegna = sub.add_parser("assegna")
    p_assegna.add_argument("--player-id", required=True)
    p_assegna.add_argument("--team-id", required=True)
    p_assegna.add_argument("--prezzo", type=int, required=True)
    p_assegna.set_defaults(func=cmd_assegna)

    p_scambio = sub.add_parser("scambio")
    p_scambio.add_argument("--team-a", required=True)
    p_scambio.add_argument("--team-b", required=True)
    p_scambio.add_argument("--players-a", default="", help="player-id di team-a ceduti a team-b, separati da virgola")
    p_scambio.add_argument("--players-b", default="", help="player-id di team-b ceduti a team-a, separati da virgola")
    p_scambio.add_argument("--credits-a-b", type=int, default=0, help="crediti che team-a versa a team-b")
    p_scambio.add_argument("--credits-b-a", type=int, default=0, help="crediti che team-b versa a team-a")
    p_scambio.set_defaults(func=cmd_scambio)

    p_svincolo = sub.add_parser("svincolo")
    p_svincolo.add_argument("--player-id", required=True)
    p_svincolo.add_argument("--team-id", required=True)
    p_svincolo.add_argument("--rimborso", type=int, default=0, help="crediti restituiti alla squadra")
    p_svincolo.set_defaults(func=cmd_svincolo)

    p_stato = sub.add_parser("stato")
    p_stato.add_argument("--team-id", default=None)
    p_stato.set_defaults(func=cmd_stato)

    p_disp = sub.add_parser("disponibili")
    p_disp.add_argument("--ruolo", choices=["P", "D", "C", "A"], default=None)
    p_disp.add_argument("--top", type=int, default=20)
    p_disp.set_defaults(func=cmd_disponibili)

    args = parser.parse_args()
    sys.exit(args.func(args) or 0)


if __name__ == "__main__":
    main()
