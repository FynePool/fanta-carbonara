#!/usr/bin/env python3
"""Aggiunge a data/players.json i giocatori del listone ufficiale di fantacalcio.it che
FantaDraft non ha.

Perché: FantaDraft (import_fantadraft.py) ha un sottoinsieme del listone. Il 27/09/2026
aveva 532 giocatori contro i 598 di fantacalcio.it, e tra i 66 mancanti c'erano Leão,
Lukaku, Nkunku, Di Gregorio, Alaba: presi all'asta (che usa gli id fantacalcio) o con
voti in pagella, ma sconosciuti al progetto. Per i 532 in comune squadra, ruolo e nome
coincidevano.

Fonte: la pagina "Quotazioni Fantacalcio" (https://www.fantacalcio.it/quotazioni-fantacalcio),
HTML statico, una riga `tr.player-row` per giocatore con il link alla scheda
(".../squadre/udinese/alaba/2404": l'ultimo numero è l'id, lo stesso del listone, "fd2404"),
il ruolo classic (`span.role`), la quotazione attuale (`td.player-classic-current-price`)
e l'FVM (`td.player-classic-fvm`).

Solo aggiunte: i giocatori già presenti non vengono toccati (FantaDraft resta la fonte
per quotazioni, FVM e infortuni). Va lanciato **dopo** import_fantadraft.py, che riscrive
players.json da zero: quindi a ogni giro i mancanti vengono tolti e rimessi, e lo status
lo riassegna apply_formazioni_status.py, che viene dopo. I giocatori aggiunti hanno
`fonte_listone: "fantacalcio.it"`.

Il nome della squadra si ricava dallo slug del link ("udinese") guardando come il listone
chiama la squadra degli altri giocatori con lo stesso slug: nessuna tabella scritta a
mano. Uno slug mai visto viene segnalato e quei giocatori non vengono aggiunti.

Uso:
    python3 scripts/import_listone_fc.py
    python3 scripts/import_listone_fc.py --html /percorso/pagina.html   # test offline
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store

URL = "https://www.fantacalcio.it/quotazioni-fantacalcio"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
LINK_RE = re.compile(r"/squadre/([^/]+)/[^/]+/(\d+)/?$")
RUOLI = {"P", "D", "C", "A"}


def fetch_html(local_path: str | None) -> str:
    if local_path:
        return Path(local_path).read_text(encoding="utf-8")
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_int(td):
    testo = td.get_text(strip=True) if td else ""
    return int(testo) if testo.lstrip("-").isdigit() else None


def parse(html: str):
    """Ritorna (righe, anomalie). Una riga: id, nome, ruolo, slug squadra, quotazione, fvm."""
    soup = BeautifulSoup(html, "html.parser")
    righe, anomalie = [], []
    for tr in soup.select("tr.player-row"):
        link = tr.select_one("a.player-name")
        ruolo = tr.select_one("span.role")
        m = LINK_RE.search(link.get("href", "")) if link else None
        if m is None or ruolo is None:
            anomalie.append(f"riga senza link o ruolo: {tr.get('data-filter-keywords')!r}")
            continue
        r = ruolo.get("data-value", "").upper()
        if r not in RUOLI:
            anomalie.append(f"{link.get_text(strip=True)}: ruolo sconosciuto {r!r}")
            continue
        righe.append({
            "id": f"fd{m.group(2)}",
            "name": link.get_text(strip=True),
            "role": r,
            "slug": m.group(1),
            "quotazione": parse_int(tr.select_one("td.player-classic-current-price")),
            "fvm": parse_int(tr.select_one("td.player-classic-fvm")),
        })
    return righe, anomalie


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default=None, help="pagina salvata, per test offline")
    args = parser.parse_args()

    righe, anomalie = parse(fetch_html(args.html))
    if len(righe) < 400:
        # Una pagina cambiata o tagliata non deve passare per un listone vero.
        print(f"ERRORE: solo {len(righe)} giocatori letti dalla pagina, mi aspettavo circa 600. Niente scritto.")
        for a in anomalie:
            print(f"  {a}")
        return 1

    players = store.load_players()
    by_id = {p["id"]: p for p in players}

    squadre_per_slug = defaultdict(Counter)
    for r in righe:
        if r["id"] in by_id:
            squadre_per_slug[r["slug"]][by_id[r["id"]]["serie_a_team"]] += 1
    squadra_di = {slug: c.most_common(1)[0][0] for slug, c in squadre_per_slug.items()}

    aggiunti, slug_ignoti, diversi = [], Counter(), []
    for r in righe:
        prev = by_id.get(r["id"])
        squadra = squadra_di.get(r["slug"])
        if prev is not None:
            if squadra and (prev["serie_a_team"], prev["role"]) != (squadra, r["role"]):
                diversi.append(f"{prev['name']}: FantaDraft {prev['serie_a_team']}/{prev['role']}, "
                               f"fantacalcio.it {squadra}/{r['role']}")
            continue
        if squadra is None:
            slug_ignoti[r["slug"]] += 1
            continue
        players.append({
            "id": r["id"],
            "name": r["name"],
            "role": r["role"],
            "serie_a_team": squadra,
            "quotazione": r["quotazione"],
            "fvm": r["fvm"],
            "status": "n/d",
            "status_note": "",
            "status_updated_at": "",
            "prob_titolare": None,
            "fonte_listone": "fantacalcio.it",
        })
        aggiunti.append(f"{r['name']} ({squadra}, {r['role']})")

    store.save_json(store.DATA_DIR / "players.json", players)

    print(f"OK: {len(righe)} giocatori nel listone di fantacalcio.it, {len(aggiunti)} aggiunti a "
          f"players.json perché FantaDraft non li ha (totale ora {len(players)}).")
    if aggiunti:
        print("  " + ", ".join(aggiunti))
    if slug_ignoti:
        print(f"ATTENZIONE: squadre mai viste nel listone, giocatori non aggiunti: {dict(slug_ignoti)}")
    if diversi:
        print(f"ATTENZIONE: {len(diversi)} giocatori con squadra o ruolo diversi tra le due fonti (non toccati):")
        for d in diversi:
            print(f"  {d}")
    if anomalie:
        print(f"ATTENZIONE: {len(anomalie)} righe della pagina non lette:")
        for a in anomalie:
            print(f"  {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
