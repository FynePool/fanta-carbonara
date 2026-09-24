#!/usr/bin/env python3
"""Applica lo snapshot di data/formazioni_correnti.json (prodotto da
scrape_formazioni.py) allo status dei giocatori in data/players.json.

Euristica di derivazione dello status dalla percentuale (probabilità di
titolarità secondo fantacalcio.it), NON una certezza:
    titolare, percentuale >= 90   -> "titolare"
    titolare, percentuale 50-89   -> "ballottaggio"
    panchina, percentuale >= 40   -> "ballottaggio"
    panchina, percentuale < 40    -> "panchina"
Il matching giocatore avviene per (squadra Serie A + nome normalizzato):
è un match euristico su stringhe, non un id condiviso tra fonti diverse,
quindi va sempre controllato l'elenco dei "non trovati" in output.

Chi non compare nelle probabili passa a "n/d" con la data delle probabili nella nota,
invece di tenere lo status della volta prima (può essere squalificato, escluso, o
scritto con un nome diverso). status_updated_at è la data delle probabili, non quella
di oggi: se lo scrape di oggi fallisce e si riapplica uno snapshot vecchio, il dato
deve risultare vecchio.

Dopo le probabili applica data/injuries.json: chi ha un infortunio aperto diventa
"infortunato" a prescindere da come lo dà lo scrape (un infortunato compare spesso
in panchina, ma non è schierabile). Vale la presenza nel file, non una data: la
fonte elenca solo gli infortuni in corso, quindi chi è rientrato sparisce da sola
al prossimo import. Per questo injuries.json va rinfrescato PRIMA, con
import_fantadraft.py: se è vecchio lo script lo segnala invece di fidarsene.

Per ultimi gli squalificati di data/squalifiche.json (scrape_squalifiche.py): diventano
"squalificato", con la stessa logica degli infortuni. I diffidati no, possono giocare.

Uso:
    python3 scripts/import_fantadraft.py          # rinfresca listone + infortuni
    python3 scripts/scrape_formazioni.py          # scarica le probabili
    python3 scripts/scrape_squalifiche.py         # squalificati e diffidati
    python3 scripts/apply_formazioni_status.py [--dry-run]
"""
import argparse
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store


def normalize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower().replace(".", "").strip()
    return " ".join(name.split())


def derive_status(entry: dict) -> str:
    pct = entry["percentuale"] or 0
    if entry["status"] == "titolare":
        return "titolare" if pct >= 90 else "ballottaggio"
    return "ballottaggio" if pct >= 40 else "panchina"


def build_scrape_index(snapshot: dict):
    index = {}
    for team in snapshot["teams"]:
        team_key = normalize(team["serie_a_team"])
        for entry in team["titolari"] + team["panchina"]:
            if not entry["name"]:
                continue
            key = (team_key, normalize(entry["name"]))
            index[key] = entry
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Mostra le modifiche senza scrivere players.json")
    args = parser.parse_args()

    snapshot_path = store.DATA_DIR / "formazioni_correnti.json"
    if not snapshot_path.exists():
        print("ERRORE: data/formazioni_correnti.json non esiste. Lancia prima scrape_formazioni.py.")
        return 1

    snapshot = store.load_json(snapshot_path)
    scrape_index = build_scrape_index(snapshot)
    players = store.load_players()
    # Lo status prende la data delle probabili, non quella di oggi: se lo scrape di
    # oggi è fallito e si riapplica uno snapshot vecchio, il dato deve sembrare vecchio.
    data_probabili = snapshot["scraped_at"][:10]
    if data_probabili != date.today().isoformat():
        print(
            f"ATTENZIONE: le probabili in data/formazioni_correnti.json sono del {data_probabili}, "
            "non di oggi: lo scrape di oggi non è andato a buon fine?"
        )

    updated, unmatched_players = [], []
    matched_keys = set()

    for p in players:
        key = (normalize(p["serie_a_team"]), normalize(p["name"]))
        entry = scrape_index.get(key)
        if entry is None:
            # fallback: match sull'ultimo token del nome (cognome), stessa squadra
            last_token = normalize(p["name"]).split()[-1] if p["name"] else ""
            candidates = [
                (k, v) for k, v in scrape_index.items()
                if k[0] == normalize(p["serie_a_team"]) and last_token and last_token in k[1]
            ]
            if len(candidates) == 1:
                (key, entry) = candidates[0]
        if entry is None:
            unmatched_players.append(p)
            continue

        matched_keys.add(key)
        new_status = derive_status(entry)
        if p["status"] != new_status:
            updated.append((p, p["status"], new_status, entry["percentuale"]))
        p["status"] = new_status
        # la percentuale pubblicata, come numero: la leggono il report e gli avvisi
        p["prob_titolare"] = entry["percentuale"]
        p["status_note"] = (
            f"fantacalcio.it probabili formazioni: {entry['status']} {entry['percentuale']}%"
        )
        p["status_updated_at"] = data_probabili

    # Chi non compare nelle probabili non tiene lo status della volta prima: può essere
    # squalificato, escluso, o scritto con un nome diverso. Si dice che non si sa.
    for p in unmatched_players:
        p["status"] = "n/d"
        p["prob_titolare"] = None
        p["status_note"] = (
            f"non trovato nelle probabili del {data_probabili} (assente, o nome scritto diversamente)"
        )
        p["status_updated_at"] = data_probabili

    unmatched_scrape = [v for k, v in scrape_index.items() if k not in matched_keys]

    # L'infortunio ha l'ultima parola sulle probabili: un infortunato può comparire
    # in panchina nello scrape, ma non è schierabile. Applicato qui e non in uno
    # script a parte per non dipendere dall'ordine in cui vengono lanciati.
    injuries = {i["player_id"]: i for i in store.load_injuries()}
    injured = []
    for p in players:
        inj = injuries.get(p["id"])
        if inj is None:
            continue
        injured.append((p, p["status"]))
        p["status"] = "infortunato"
        p["status_note"] = f"infortunio: {inj.get('expected_return') or 'rientro non indicato'}"
        p["status_updated_at"] = inj.get("imported_on") or data_probabili

    # Lo squalificato è certo quanto l'infortunato: esce dai disponibili. Il diffidato
    # invece può giocare, e resta com'è (lo segnala il report).
    squalifiche_path = store.DATA_DIR / "squalifiche.json"
    squalifiche = store.load_json(squalifiche_path) if squalifiche_path.exists() else None
    squalificati = []
    if squalifiche is None:
        print("ATTENZIONE: data/squalifiche.json non esiste: lancia prima scrape_squalifiche.py.")
    else:
        by_id = {p["id"]: p for p in players}
        for s in squalifiche:
            p = by_id.get(s["player_id"])
            if s["tipo"] != "squalificato" or p is None:
                continue
            squalificati.append((p, p["status"]))
            p["status"] = "squalificato"
            p["status_note"] = f"squalificato: {s.get('nota') or 'giornate non indicate'}"
            p["status_updated_at"] = s.get("imported_on") or data_probabili
        vecchie = {s.get("imported_on") for s in squalifiche} - {date.today().isoformat()}
        if vecchie:
            print(
                f"ATTENZIONE: data/squalifiche.json è del {sorted(vecchie)[-1]}, non di oggi: "
                "rilancia scrape_squalifiche.py."
            )

    stale = {i.get("imported_on") for i in injuries.values()} - {date.today().isoformat()}
    if stale:
        print(
            f"ATTENZIONE: data/injuries.json è stato importato il {sorted(stale)[-1]}, non oggi. "
            "Chi è rientrato risulterebbe ancora infortunato: rilancia import_fantadraft.py."
        )

    print(f"Aggiornati {len(updated)} status su {len(players)} giocatori del listone.")
    for p, old, new, pct in updated[:40]:
        print(f"  {p['name']:<25} ({p['serie_a_team']:<12}) {old} -> {new} ({pct}%)")
    if len(updated) > 40:
        print(f"  ... e altri {len(updated) - 40}")

    if unmatched_players:
        print(f"\n{len(unmatched_players)} giocatori del listone non trovati nello scrape (passano a n/d; gli infortunati poi diventano 'infortunato'):")
        for p in unmatched_players[:15]:
            print(f"  {p['name']} ({p['serie_a_team']})")
        if len(unmatched_players) > 15:
            print(f"  ... e altri {len(unmatched_players) - 15}")

    if injured:
        print(f"\n{len(injured)} giocatori marcati infortunati da data/injuries.json:")
        for p, old in injured[:15]:
            print(f"  {p['name']:<25} ({p['serie_a_team']:<12}) {old} -> infortunato")
        if len(injured) > 15:
            print(f"  ... e altri {len(injured) - 15}")

    if squalificati:
        print(f"\n{len(squalificati)} giocatori marcati squalificati da data/squalifiche.json:")
        for p, old in squalificati:
            print(f"  {p['name']:<25} ({p['serie_a_team']:<12}) {old} -> squalificato")

    if unmatched_scrape:
        print(f"\n{len(unmatched_scrape)} giocatori nello scrape non trovati nel listone (probabile differenza di nome):")
        for e in unmatched_scrape[:15]:
            print(f"  {e['name']}")
        if len(unmatched_scrape) > 15:
            print(f"  ... e altri {len(unmatched_scrape) - 15}")

    if args.dry_run:
        print("\n--dry-run: nessuna modifica scritta su disco.")
        return 0

    store.save_json(store.DATA_DIR / "players.json", players)
    print("\nScritto data/players.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
