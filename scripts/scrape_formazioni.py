#!/usr/bin/env python3
"""Scrape delle probabili formazioni Serie A da fantacalcio.it/probabili-formazioni-serie-a/.

Fonte pubblica, HTML statico (verificato: nessun rendering JS necessario per i
dati di formazione). Estrae, per ogni squadra Serie A in campo nel prossimo turno:
modulo, titolari con percentuale, panchina, ballottaggi, indisponibili.

Salva:
    data/formazioni_correnti.json      — snapshot dell'ultimo scrape (sovrascritto)
    data/formazioni_history.json       — append-only, uno snapshot per timestamp,
                                          usato per costruire uno storico nel tempo

Uso:
    python3 scripts/scrape_formazioni.py
    python3 scripts/scrape_formazioni.py --html /path/to/pagina_salvata.html   # per test offline
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store

URL = "https://www.fantacalcio.it/probabili-formazioni-serie-a/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def fetch_html(local_path: str | None) -> str:
    if local_path:
        return Path(local_path).read_text(encoding="utf-8")
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def _parse_player_list(ul, status_label: str):
    players = []
    if ul is None:
        return players
    for li in ul.find_all("li", class_="player-item"):
        role_span = li.find("span", class_="role")
        role = (role_span.get("data-value") or "").upper() if role_span else None
        name_a = li.find("a", class_="player-name")
        name = name_a.get_text(strip=True) if name_a else None
        href = name_a.get("href") if name_a else None
        fanta_id = href.rstrip("/").rsplit("/", 1)[-1] if href else None
        pct_div = li.find("div", class_="progress-value")
        pct = None
        if pct_div:
            txt = pct_div.get_text(strip=True).replace("%", "")
            if txt.isdigit():
                pct = int(txt)
        players.append(
            {
                "name": name,
                "role": role,
                "fantacalcio_it_id": fanta_id,
                "percentuale": pct,
                "status": status_label,
            }
        )
    return players


def parse_teams(html: str):
    soup = BeautifulSoup(html, "html.parser")
    teams = []
    for card in soup.find_all("div", class_="team-card"):
        name_el = card.find("h3", class_="team-name")
        if not name_el:
            continue
        formation_el = card.find("div", class_="team-formation")
        starters_ul = card.find("ul", class_="player-list starters")
        reserves_ul = card.find("ul", class_="player-list reserves")
        teams.append(
            {
                "serie_a_team": name_el.get_text(strip=True),
                "modulo": formation_el.get_text(strip=True) if formation_el else None,
                "titolari": _parse_player_list(starters_ul, "titolare"),
                "panchina": _parse_player_list(reserves_ul, "panchina"),
            }
        )
    return teams


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default=None, help="File HTML locale, per test offline invece di fetch live")
    args = parser.parse_args()

    html = fetch_html(args.html)
    teams = parse_teams(html)

    if not teams:
        print("ATTENZIONE: nessuna squadra estratta. La struttura della pagina è probabilmente cambiata.")
        return 1

    snapshot = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": URL,
        "teams": teams,
    }

    store.save_json(store.DATA_DIR / "formazioni_correnti.json", snapshot)

    history_path = store.DATA_DIR / "formazioni_history.json"
    history = store.load_json(history_path) if history_path.exists() else []
    # Con un giro al giorno lo storico crescerebbe di ~90 KB anche quando le probabili
    # non cambiano (soste, giorni senza notizie): si aggiunge solo se sono diverse.
    invariato = bool(history) and history[-1]["teams"] == teams
    if not invariato:
        history.append(snapshot)
        store.save_json(history_path, history)

    total_players = sum(len(t["titolari"]) + len(t["panchina"]) for t in teams)
    print(f"OK: {len(teams)} squadre, {total_players} giocatori estratti.")
    print(f"Snapshot corrente: data/formazioni_correnti.json")
    if invariato:
        print("Probabili identiche all'ultimo snapshot: storico non modificato.")
    else:
        print(f"Storico ({len(history)} snapshot totali): data/formazioni_history.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
