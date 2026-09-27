#!/usr/bin/env python3
"""Competizioni della lega e loro calendari (partite testa-a-testa e risultati) da
leghe.fantacalcio.it, in data/lega_competizioni.json.

Fonte: l'API privata di leghe.fantacalcio.it (lib/leghe_fc_client.py), verificata il
27/09/2026 sulla lega vera:
- `/onboarding/v1/league/competitions`: una riga per competizione, con `id`, `name`,
  `type`, `sDay`/`eDay` (prima e ultima giornata di Serie A), `tmids` (id delle squadre,
  gli stessi di teams.json) e `del`. Il 27/09 c'era solo il campionato "FANTACARBONARA"
  (id 858469, giornate di Serie A 6-38, le 12 squadre in gioco); Coppa Italia ed Europa
  League arriveranno più avanti e vengono lette da sole.
- `/onboarding/v1/league/competition/calendar/<id>`: una riga per giornata, con
  `matchDay` (giornata della competizione), `championshipMatchDay` (giornata di Serie A),
  `calculated` e `matches`: per partita `tIdH`/`tIdA` (squadre), `ptH`/`ptA` (punteggio),
  `standingPtH`/`standingPtA` (punti in classifica), `result`, `resultSR`. Prima che la
  giornata sia calcolata i punteggi sono 0 e il risultato è "-".

Non esiste un endpoint della classifica (non c'è nemmeno nel client di riferimento): si
ricava da qui.

Lo storico dei risultati non si perde mai, come quello dei voti:
- una giornata già calcolata in archivio non viene mai sostituita da una non calcolata
  (se la lega la "scalcola", resta quella salvata e lo script lo segnala);
- una giornata calcolata che la lega ricalcola con numeri diversi viene aggiornata, e
  segnalata (la lega può correggere);
- una competizione o una giornata che sparisce dall'API resta nell'archivio, segnalata.

Richiede LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD da ambiente.

Uso:
    python3 scripts/import_calendario_lega.py --league-id 923348
    python3 scripts/import_calendario_lega.py --league-id 923348 --dry-run
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import leghe_fc_client as client
from lib import store

PATH = store.DATA_DIR / "lega_competizioni.json"


def converti_giornata(g: dict) -> dict:
    return {
        "giornata": g["matchDay"],
        "giornata_serie_a": g["championshipMatchDay"],
        "calcolata": bool(g["calculated"]),
        "partite": [
            {
                "casa": str(m["tIdH"]),
                "trasferta": str(m["tIdA"]),
                "punteggio_casa": m["ptH"],
                "punteggio_trasferta": m["ptA"],
                "punti_classifica_casa": m["standingPtH"],
                "punti_classifica_trasferta": m["standingPtA"],
                "risultato": m["result"],
                "risultato_sr": m["resultSR"],
            }
            for m in g["matches"]
        ],
    }


def leggi(league_id):
    username = os.environ.get("LEGHE_FC_USERNAME")
    password = os.environ.get("LEGHE_FC_PASSWORD")
    if not username or not password:
        raise RuntimeError("imposta LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD come variabili d'ambiente.")
    jwt = client.get_league_jwt(client.login(username, password), league_id)
    competizioni = []
    for c in client.authenticated_get("/onboarding/v1/league/competitions", jwt):
        calendario = client.authenticated_get(f"/onboarding/v1/league/competition/calendar/{c['id']}", jwt)
        competizioni.append({
            "id": str(c["id"]),
            "nome": c["name"],
            "tipo": c["type"],
            "eliminata": bool(c.get("del")),
            "giornata_serie_a_inizio": c["sDay"],
            "giornata_serie_a_fine": c["eDay"],
            "squadre": [str(t) for t in c["tmids"]],
            "calendario": [converti_giornata(g) for g in calendario],
        })
    return competizioni


def unisci(vecchie: list[dict], nuove: list[dict]):
    """Ritorna (competizioni, avvisi): le nuove sopra le vecchie, senza perdere risultati."""
    avvisi = []
    per_id = {c["id"]: c for c in vecchie}
    for nuova in nuove:
        vecchia = per_id.get(nuova["id"])
        if vecchia is None:
            avvisi.append(f"nuova competizione: {nuova['nome']} ({nuova['id']})")
            per_id[nuova["id"]] = nuova
            continue
        giornate = {g["giornata"]: g for g in vecchia["calendario"]}
        for g in nuova["calendario"]:
            prima = giornate.get(g["giornata"])
            if prima and prima["calcolata"] and not g["calcolata"]:
                avvisi.append(f"{nuova['nome']} giornata {g['giornata']}: era calcolata e ora no, "
                              "tengo i risultati salvati")
                continue
            if prima and prima["calcolata"] and g["calcolata"] and prima["partite"] != g["partite"]:
                avvisi.append(f"{nuova['nome']} giornata {g['giornata']}: ricalcolata dalla lega, "
                              "risultati aggiornati")
            giornate[g["giornata"]] = g
        sparite = sorted(set(giornate) - {g["giornata"] for g in nuova["calendario"]})
        if sparite:
            avvisi.append(f"{nuova['nome']}: giornate non più nell'API, tenute in archivio: {sparite}")
        per_id[nuova["id"]] = {**nuova, "calendario": [giornate[k] for k in sorted(giornate)]}
    for cid in set(per_id) - {c["id"] for c in nuove}:
        avvisi.append(f"competizione non più nell'API, tenuta in archivio: {per_id[cid]['nome']} ({cid})")
    return sorted(per_id.values(), key=lambda c: int(c["id"])), avvisi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league-id", required=True)
    parser.add_argument("--dry-run", action="store_true", help="non scrive niente")
    args = parser.parse_args()

    try:
        nuove = leggi(args.league_id)
    except Exception as e:  # rete, login, formato: in ogni caso niente scritto
        print(f"ERRORE: {e}. Niente scritto.")
        return 1

    vecchie = store.load_json(PATH) if PATH.exists() else []
    competizioni, avvisi = unisci(vecchie, nuove)

    squadre = {t["id"] for t in store.load_teams()}
    for c in competizioni:
        calcolate = sum(g["calcolata"] for g in c["calendario"])
        print(f"{c['nome']} ({c['id']}): {len(c['calendario'])} giornate (Serie A "
              f"{c['giornata_serie_a_inizio']}-{c['giornata_serie_a_fine']}), {calcolate} calcolate, "
              f"{len(c['squadre'])} squadre{', ELIMINATA sulla lega' if c['eliminata'] else ''}")
        fuori = sorted(set(c["squadre"]) - squadre)
        if fuori:
            print(f"  ATTENZIONE: squadre della competizione che non sono in teams.json: {fuori}")
    for a in avvisi:
        print(f"ATTENZIONE: {a}" if "nuova competizione" not in a else f"Nota: {a}")

    if not args.dry_run:
        store.save_json(PATH, competizioni)
    return 0


if __name__ == "__main__":
    sys.exit(main())
