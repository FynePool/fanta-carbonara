#!/usr/bin/env python3
"""Importa il listone ufficiale (export Excel/CSV di fantacalcio.it o simili)
in data/players.json, come pool completo di giocatori Serie A pre-asta.

Il file ufficiale fantacalcio.it ha tipicamente colonne:
    Id, R, RM, Nome, Squadra, Qt.A, Qt.I, Diff., Qt.A M, Qt.I M, Diff.M, FVM, FVM M

Per la modalità Classic ci servono solo: Id, R, Nome, Squadra, Qt.A (quotazione attuale).
Se il tuo export ha nomi di colonna diversi, passali con --col-*.

Uso:
    python3 scripts/import_listone.py --csv listone.csv
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store

ROLE_MAP = {"P": "P", "D": "D", "C": "C", "A": "A"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Percorso del file CSV del listone")
    parser.add_argument("--col-id", default="Id")
    parser.add_argument("--col-role", default="R")
    parser.add_argument("--col-name", default="Nome")
    parser.add_argument("--col-team", default="Squadra")
    parser.add_argument("--col-quotazione", default="Qt.A")
    parser.add_argument("--delimiter", default=";")
    parser.add_argument(
        "--out",
        default=None,
        help="Se assente, sovrascrive data/players.json preservando status esistenti per id già noti",
    )
    args = parser.parse_args()

    existing = {p["id"]: p for p in store.load_players()}

    rows = []
    with open(args.csv, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=args.delimiter)
        for row in reader:
            pid = row[args.col_id].strip()
            role = ROLE_MAP.get(row[args.col_role].strip().upper(), row[args.col_role].strip().upper())
            prev = existing.get(pid, {})
            rows.append(
                {
                    "id": pid,
                    "name": row[args.col_name].strip(),
                    "role": role,
                    "serie_a_team": row[args.col_team].strip(),
                    "quotazione": int(float(row[args.col_quotazione].strip() or 0)),
                    "status": prev.get("status", "n/d"),
                    "status_note": prev.get("status_note", ""),
                    "status_updated_at": prev.get("status_updated_at", ""),
                    "prob_titolare": prev.get("prob_titolare"),
                }
            )

    out_path = Path(args.out) if args.out else (store.DATA_DIR / "players.json")
    store.save_json(out_path, rows)
    print(f"Importati {len(rows)} giocatori in {out_path}")


if __name__ == "__main__":
    main()
