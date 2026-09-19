#!/usr/bin/env python3
"""Ispeziona una lega leghe.fantacalcio.it via l'API privata (sola lettura).

NON scrive nulla in data/: serve per esplorare/validare cosa risponde l'API
per la lega reale prima di decidere come mapparla su ownership.json/teams.json
(quel mapping va scritto solo dopo l'asta, quando la lega vera esiste).

Richiede LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD come variabili d'ambiente
(mai passarle come argomenti da riga di comando: finirebbero nella history
della shell).

Uso:
    python3 scripts/leghe_fc_inspect.py leghe                 # elenca le leghe dell'account
    python3 scripts/leghe_fc_inspect.py rose --league-id <id> # rose + crediti
    python3 scripts/leghe_fc_inspect.py listone --league-id <id>
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import leghe_fc_client as client


def get_credentials():
    username = os.environ.get("LEGHE_FC_USERNAME")
    password = os.environ.get("LEGHE_FC_PASSWORD")
    if not username or not password:
        print("ERRORE: imposta LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD come variabili d'ambiente.")
        sys.exit(1)
    return username, password


def cmd_leghe(args):
    username, password = get_credentials()
    payload = client.login(username, password)
    for lega in payload["data"]["leghe"]:
        print(f"id={lega['id']}  nome={lega['nome']!r}  admin={bool(lega['admin'])}  divisione={lega['divisione']}")


def cmd_rose(args):
    username, password = get_credentials()
    payload = client.login(username, password)
    jwt = client.get_league_jwt(payload, args.league_id)
    teams = client.authenticated_get("/onboarding/v1/league/teams/all", jwt)
    for t in teams["data"]:
        print(f"{t['n']:<25} crediti: {t['cr']}/{t['cri']} (spesi {t['crs']})  ruoli in rosa: {t['r']}")


def cmd_listone(args):
    username, password = get_credentials()
    payload = client.login(username, password)
    jwt = client.get_league_jwt(payload, args.league_id)
    players = client.authenticated_get("/onboarding/v1/league/players", jwt)
    print(f"{len(players['players'])} giocatori nel listone di questa lega.")
    print("Esempio primo giocatore (struttura grezza):", players["players"][0])


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_leghe = sub.add_parser("leghe")
    p_leghe.set_defaults(func=cmd_leghe)

    p_rose = sub.add_parser("rose")
    p_rose.add_argument("--league-id", default=None)
    p_rose.set_defaults(func=cmd_rose)

    p_listone = sub.add_parser("listone")
    p_listone.add_argument("--league-id", default=None)
    p_listone.set_defaults(func=cmd_listone)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
