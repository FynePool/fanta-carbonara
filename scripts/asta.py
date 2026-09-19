#!/usr/bin/env python3
"""Assistente per l'asta live a chiamata: registra gli acquisti di TUTTE le
12 squadre man mano che avvengono, aggiorna crediti/rose, e mostra chi resta
disponibile e quanto budget hai ancora per ruolo.

Comandi:
    assegna   Registra un acquisto (di qualunque squadra, non solo la tua)
    stato     Mostra crediti e slot rimanenti per ogni squadra
    disponibili   Elenca i giocatori non ancora presi, per ruolo

Esempi:
    python3 scripts/asta.py assegna --player-id p001 --team-id t01 --prezzo 45
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
