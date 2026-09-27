#!/usr/bin/env python3
"""Listone ufficiale di fantacalcio.it in data/players.json: è la fonte di chi esiste.

Fonte: la pagina "Quotazioni Fantacalcio" (https://www.fantacalcio.it/quotazioni-fantacalcio),
HTML statico, una riga `tr.player-row` per giocatore con il link alla scheda
(".../squadre/udinese/alaba/2404": l'ultimo numero è l'id fantacalcio, "fd2404" qui),
il ruolo classic (`span.role`), la quotazione attuale (`td.player-classic-current-price`)
e l'FVM (`td.player-classic-fvm`). Verificata il 27/09/2026: 598 giocatori.

Perché questa e non FantaDraft: FantaDraft ne aveva 532 (mancavano Leão, Lukaku,
Di Gregorio, due giocatori presi all'asta...), mentre l'asta (Fantalab) e i voti
(import_voti.py) usano gli id di questa pagina. FantaDraft resta solo per gli infortuni
(import_fantadraft.py).

Il file viene riscritto con i giocatori della pagina; di quelli già noti si tengono
status, nota, data e probabilità di titolarità. Chi non è più nel listone (venduto
all'estero, in Serie B) sparisce da players.json, ma **il suo storico in
matchday_stats.json resta**: quel file non si accorcia mai (store.save_matchday_stats).

Protezioni, perché una pagina cambiata o tagliata non passi per un listone vero:
- meno di 400 giocatori letti: niente scritto;
- una squadra che non è nel calendario: niente scritto;
- più di MAX_USCITI giocatori che escono in un colpo solo: niente scritto (un mercato
  vero ne toglie pochi al giorno), a meno di --accetta-uscite.

Il nome della squadra si ricava dallo slug del link ("udinese" -> "Udinese")
confrontandolo con le squadre del calendario, senza tabelle scritte a mano.

Uso:
    python3 scripts/import_listone_fc.py
    python3 scripts/import_listone_fc.py --html /percorso/pagina.html   # test offline
"""
import argparse
import re
import sys
import unicodedata
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
MIN_GIOCATORI = 400
MAX_USCITI = 40
CAMPI_STATUS = ("status", "status_note", "status_updated_at", "prob_titolare")


def slugify(nome: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


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
    parser.add_argument(
        "--accetta-uscite", action="store_true",
        help=f"scrive anche se escono dal listone più di {MAX_USCITI} giocatori in un colpo",
    )
    args = parser.parse_args()

    righe, anomalie = parse(fetch_html(args.html))
    if len(righe) < MIN_GIOCATORI:
        print(f"ERRORE: solo {len(righe)} giocatori letti dalla pagina, mi aspettavo circa 600. Niente scritto.")
        for a in anomalie:
            print(f"  {a}")
        return 1

    calendario = store.load_json(store.DATA_DIR / "calendario_serie_a.json")
    squadra_di = {slugify(t): t for m in calendario for t in (m["squadra_casa"], m["squadra_trasferta"])}
    ignoti = sorted({r["slug"] for r in righe} - set(squadra_di))
    if ignoti:
        print(f"ERRORE: squadre della pagina che non sono nel calendario: {ignoti}. Niente scritto.")
        return 1

    vecchi = {p["id"]: p for p in store.load_players()}
    nuovi_ids = {r["id"] for r in righe}
    usciti = [p for pid, p in vecchi.items() if pid not in nuovi_ids]
    if len(usciti) > MAX_USCITI and not args.accetta_uscite:
        print(f"ERRORE: {len(usciti)} giocatori uscirebbero dal listone in un colpo solo (massimo {MAX_USCITI}): "
              "pagina cambiata? Niente scritto. Se è un mercato vero, rilancia con --accetta-uscite.")
        return 1

    players, entrati, cambiati = [], [], []
    for r in righe:
        prev = vecchi.get(r["id"])
        p = {
            "id": r["id"],
            "name": r["name"],
            "role": r["role"],
            "serie_a_team": squadra_di[r["slug"]],
            "quotazione": r["quotazione"],
            "fvm": r["fvm"],
            "status": "n/d",
            "status_note": "",
            "status_updated_at": "",
            "prob_titolare": None,
        }
        if prev is None:
            entrati.append(f"{p['name']} ({p['serie_a_team']}, {p['role']})")
        else:
            p.update({k: prev.get(k, p[k]) for k in CAMPI_STATUS})
            if (prev["serie_a_team"], prev["role"]) != (p["serie_a_team"], p["role"]):
                cambiati.append(f"{p['name']}: {prev['serie_a_team']}/{prev['role']} -> "
                                f"{p['serie_a_team']}/{p['role']}")
        players.append(p)

    # Ordine stabile: quello della pagina segue le quotazioni e rimescolerebbe il file a
    # ogni variazione, rendendo illeggibili i diff nel git.
    players.sort(key=lambda p: ("PDCA".index(p["role"]), p["serie_a_team"], p["name"], p["id"]))
    store.save_json(store.DATA_DIR / "players.json", players)

    print(f"OK: {len(players)} giocatori nel listone di fantacalcio.it scritti in players.json "
          f"(prima {len(vecchi)}).")
    if entrati:
        print(f"Entrati ({len(entrati)}): " + ", ".join(entrati))
    if usciti:
        print(f"Usciti dal listone ({len(usciti)}; il loro storico in matchday_stats resta): "
              + ", ".join(f"{p['name']} ({p['serie_a_team']})" for p in usciti))
    if cambiati:
        print(f"Squadra o ruolo cambiati ({len(cambiati)}):")
        for c in cambiati:
            print(f"  {c}")
    if anomalie:
        print(f"ATTENZIONE: {len(anomalie)} righe della pagina non lette:")
        for a in anomalie:
            print(f"  {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
