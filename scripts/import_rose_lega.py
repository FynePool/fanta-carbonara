#!/usr/bin/env python3
"""Rose e crediti delle squadre della lega da leghe.fantacalcio.it, in data/teams.json e
data/ownership.json. La lega è la fonte: nomi, id e crediti sono i suoi.

Fonte: l'API privata di leghe.fantacalcio.it (lib/leghe_fc_client.py), endpoint
`/onboarding/v1/league/teams/all`, verificata il 27/09/2026 sulla lega vera. Per ogni
squadra: `id`, `n` (nome), `cal` (id fantacalcio dei giocatori, separati da ";"), `cs`
(prezzi d'acquisto, nello stesso ordine), `cr` (crediti rimanenti), `cri` (crediti
iniziali, 554) e `bm` (correzione, -54): i crediti totali sono cri + bm = 500.

La lega ha anche squadre vuote (18 squadre il 27/09, 6 senza nessun giocatore): non
sono in gioco e vengono lasciate fuori. Se le squadre con la rosa non sono esattamente
`teams_count` di config/league.json (12), non si scrive niente: meglio le rose di ieri
che una lega sbagliata.

ownership.json viene riscritto con le rose di oggi. Una coppia (giocatore, squadra) già
nota tiene data e modalità d'acquisto; al primo import sono "asta" senza data (l'API non
la dà), dopo sono "da_verificare" con la data dell'import, perché l'API non dice se è
uno svincolato, uno scambio o altro. Chi entra o esce da una rosa viene stampato.
Il proprietario non viene salvato: è lo username dell'account, un dato personale.

--verifica-csv confronta le rose con un export dell'asta (colonne Squadra,
Fantacalcio_Id, Prezzo; l'app dell'asta usa altri nomi di squadra): per ogni squadra
della lega cerca la squadra del CSV con più giocatori in comune e segnala ogni
differenza di giocatori o prezzi. Il CSV non viene mai scritto nel repo.

Richiede LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD da ambiente.

Uso:
    python3 scripts/import_rose_lega.py --league-id 923348
    python3 scripts/import_rose_lega.py --league-id 923348 --verifica-csv /percorso/rose.csv --dry-run
"""
import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import leghe_fc_client as client
from lib import store


def leggi_rose(league_id):
    username = os.environ.get("LEGHE_FC_USERNAME")
    password = os.environ.get("LEGHE_FC_PASSWORD")
    if not username or not password:
        raise RuntimeError("imposta LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD come variabili d'ambiente.")
    payload = client.login(username, password)
    jwt = client.get_league_jwt(payload, league_id)
    squadre = []
    for t in client.authenticated_get("/onboarding/v1/league/teams/all", jwt)["data"]:
        ids = [x for x in (t.get("cal") or "").split(";") if x]
        prezzi = [int(x) for x in (t.get("cs") or "").split(";") if x]
        if len(ids) != len(prezzi):
            raise RuntimeError(f"{t['n']}: {len(ids)} giocatori ma {len(prezzi)} prezzi")
        squadre.append({
            "id": str(t["id"]),
            "name": t["n"],
            "credits_total": t["cri"] + t.get("bm", 0),
            "credits_remaining": t["cr"],
            "rosa": {f"fd{pid}": prezzo for pid, prezzo in zip(ids, prezzi)},
        })
    return squadre


def verifica_csv(squadre, path):
    """Ritorna le differenze tra le rose della lega e l'export dell'asta."""
    per_squadra = defaultdict(dict)
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            per_squadra[r["Squadra"]][f"fd{r['Fantacalcio_Id']}"] = int(r["Prezzo"])
    differenze, usate = [], set()
    for s in squadre:
        csv_nome = max(per_squadra, key=lambda k: len(per_squadra[k].keys() & s["rosa"].keys()))
        usate.add(csv_nome)
        attesa = per_squadra[csv_nome]
        for pid in s["rosa"].keys() - attesa.keys():
            differenze.append(f"{s['name']}: {pid} è nella lega ma non nel CSV ({csv_nome})")
        for pid in attesa.keys() - s["rosa"].keys():
            differenze.append(f"{s['name']}: {pid} è nel CSV ({csv_nome}) ma non nella lega")
        for pid in s["rosa"].keys() & attesa.keys():
            if s["rosa"][pid] != attesa[pid]:
                differenze.append(f"{s['name']}: {pid} pagato {s['rosa'][pid]} nella lega, {attesa[pid]} nel CSV")
        print(f"  {s['name']!r:<30} <-> CSV {csv_nome!r}")
    for nome in per_squadra.keys() - usate:
        differenze.append(f"squadra del CSV senza corrispondente nella lega: {nome}")
    return differenze


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league-id", required=True)
    parser.add_argument("--verifica-csv", default=None, help="export dell'asta, solo per controllo")
    parser.add_argument("--dry-run", action="store_true", help="non scrive niente")
    args = parser.parse_args()

    config = store.load_league_config()
    try:
        tutte = leggi_rose(args.league_id)
    except Exception as e:  # rete, login, formato: in ogni caso niente scritto
        print(f"ERRORE: {e}. Niente scritto.")
        return 1

    squadre = [s for s in tutte if s["rosa"]]
    vuote = [s["name"] for s in tutte if not s["rosa"]]
    if len(squadre) != config["teams_count"]:
        print(f"ERRORE: {len(squadre)} squadre con la rosa, ne aspettavo {config['teams_count']}. Niente scritto.")
        return 1

    players = {p["id"]: p for p in store.load_players()}
    richiesti = config["roster_requirements"]
    avvisi = []
    for s in squadre:
        per_ruolo = defaultdict(int)
        for pid in s["rosa"]:
            per_ruolo[players[pid]["role"] if pid in players else "?"] += 1
        if any(per_ruolo[r] != n for r, n in richiesti.items()):
            avvisi.append(f"{s['name']}: rosa {dict(per_ruolo)}, richiesta {richiesti}")
        fuori = [pid for pid in s["rosa"] if pid not in players]
        if fuori:
            avvisi.append(f"{s['name']}: giocatori non nel listone {fuori}")

    if args.verifica_csv:
        print("Verifica con l'export dell'asta:")
        differenze = verifica_csv(squadre, args.verifica_csv)
        print("  nessuna differenza di giocatori o prezzi." if not differenze else "")
        for d in differenze:
            print(f"  DIFFERENZA: {d}")

    vecchia = {(o["player_id"], o["team_id"]): o for o in store.load_ownership()}
    primo_import = not vecchia
    oggi = date.today().isoformat()
    ownership, entrati = [], []
    for s in squadre:
        for pid, prezzo in s["rosa"].items():
            prev = vecchia.get((pid, s["id"]))
            if prev is None and not primo_import:
                entrati.append(f"{players.get(pid, {}).get('name', pid)} -> {s['name']}")
            ownership.append({
                "player_id": pid,
                "team_id": s["id"],
                "purchase_price": prezzo,
                "acquired_on": prev["acquired_on"] if prev else (None if primo_import else oggi),
                "acquired_via": prev["acquired_via"] if prev else ("asta" if primo_import else "da_verificare"),
            })
    nuove = {(o["player_id"], o["team_id"]) for o in ownership}
    usciti = [f"{players.get(pid, {}).get('name', pid)} da {tid}" for pid, tid in vecchia if (pid, tid) not in nuove]
    teams = [{k: s[k] for k in ("id", "name", "credits_total", "credits_remaining")} for s in squadre]

    print(f"{'(dry-run) ' if args.dry_run else ''}{len(teams)} squadre, {len(ownership)} giocatori in rosa.")
    for t in teams:
        print(f"  {t['id']}  {t['name']:<30} crediti {t['credits_remaining']}/{t['credits_total']}")
    if vuote:
        print(f"Lasciate fuori {len(vuote)} squadre vuote della lega: {', '.join(vuote)}")
    if entrati:
        print(f"Entrati in una rosa ({len(entrati)}): " + ", ".join(entrati))
    if usciti:
        print(f"Usciti da una rosa ({len(usciti)}): " + ", ".join(usciti))
    for a in avvisi:
        print(f"ATTENZIONE: {a}")

    if args.dry_run:
        return 0
    store.save_json(store.DATA_DIR / "teams.json", teams)
    store.save_json(store.DATA_DIR / "ownership.json", ownership)
    return 0


if __name__ == "__main__":
    sys.exit(main())
