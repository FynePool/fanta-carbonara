#!/usr/bin/env python3
"""Suggerisce la formazione per una giornata, a partire dai dati in data/.

Uso:
    python3 scripts/report_formazione.py --team-id t01 [--matchday 5]

I dati di stato giocatore (titolare/dubbio/infortunato/...) in data/players.json
vanno aggiornati a mano prima del lancio, leggendo le probabili formazioni.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib.roster import score_player, suggest_lineup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--matchday", type=int, default=None)
    args = parser.parse_args()

    config = store.load_league_config()
    module, starters, bench, flags = suggest_lineup(args.team_id)

    matchday_label = f"Giornata {args.matchday}" if args.matchday else "Prossima giornata"
    print(f"{matchday_label} — modalità {config['mode']}")
    if module is None:
        print("Impossibile proporre una formazione:")
        for f in flags:
            print(f"  - {f}")
        return

    print(f"Modulo consigliato: {module}\n")
    print("TITOLARI:")
    for p in sorted(starters, key=lambda p: "PDCA".index(p["role"])):
        score = score_player(p)
        print(f"  [{p['role']}] {p['name']:<25} media ultime 5: {score:.2f}")

    print("\nPANCHINA:")
    for p in bench:
        score = score_player(p)
        score_str = f"{score:.2f}" if score is not None else "n/d"
        print(f"  [{p['role']}] {p['name']:<25} media ultime 5: {score_str}  status: {p['status']}")

    if flags:
        print("\nDA VERIFICARE A MANO:")
        for f in flags:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
