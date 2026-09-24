#!/usr/bin/env python3
"""Squalificati e diffidati di Serie A da fantacalcio.it, in data/squalifiche.json.

Fonte: la pagina "Indisponibili Serie A" (https://www.fantacalcio.it/indisponibili-serie-a),
HTML statico, una scheda per squadra con tre sezioni: Infortunati, Squalificati,
Diffidati. Qui si leggono solo le ultime due: gli infortuni arrivano già da
import_fantadraft.py e due fonti per lo stesso dato potrebbero non concordare.

Struttura verificata il 24/09/2026: dopo l'intestazione di ogni sezione c'è
`<ul class="unstyled">` con un `<li>` per giocatore (`strong.item-name` e
`div.item-description`), oppure `div.empty-list-message` ("Nessuno"). Per gli
infortunati la lista piena si è vista; per squalificati e diffidati quel giorno erano
tutti "Nessuno", quindi la loro lista piena è **dedotta** dallo stesso componente. Se
la pagina mostra qualcosa di diverso, lo script lo segnala e non indovina.

Il file viene riscritto a ogni giro con la sola situazione attuale: come per gli
infortuni, vale la presenza. Un diffidato non è indisponibile (con un'ammonizione
salta la giornata successiva): resta schierabile e il report lo segnala.

I nomi di fantacalcio.it seguono la stessa convenzione del listone ("Sulemana K."):
il matching è esatto su nome normalizzato + squadra. I non trovati vengono stampati
e non scritti.

Uso:
    python3 scripts/scrape_squalifiche.py
    python3 scripts/scrape_squalifiche.py --html /percorso/pagina.html   # test offline
"""
import argparse
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apply_formazioni_status import normalize
from lib import store

URL = "https://www.fantacalcio.it/indisponibili-serie-a"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
SEZIONI = {"Squalificati": "squalificato", "Diffidati": "diffidato"}


def fetch_html(local_path: str | None) -> str:
    if local_path:
        return Path(local_path).read_text(encoding="utf-8")
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse(html: str):
    """Ritorna (righe, anomalie, squadre_lette). Una riga: squadra, nome, tipo, nota."""
    soup = BeautifulSoup(html, "html.parser")
    righe, anomalie, squadre = [], [], []
    for card in soup.find_all("div", class_="team-card"):
        name_el = card.find("span", class_="team-name")
        if not name_el:
            continue
        squadra = name_el.get_text(strip=True)
        squadre.append(squadra)
        trovate = set()
        for header in card.find_all("header"):
            label = header.get_text(" ", strip=True)
            if label not in SEZIONI:
                continue
            trovate.add(label)
            contenuto = header.find_next_sibling()
            if contenuto is not None and "empty-list-message" in (contenuto.get("class") or []):
                continue
            if contenuto is None or contenuto.name != "ul":
                anomalie.append(f"{squadra}, {label}: dopo l'intestazione non c'è né una lista né 'Nessuno'")
                continue
            for li in contenuto.find_all("li", recursive=False):
                nome_el = li.find(class_="item-name")
                if nome_el is None:
                    anomalie.append(f"{squadra}, {label}: voce senza nome ({li.get_text(' ', strip=True)[:60]})")
                    continue
                descr = li.find(class_="item-description")
                righe.append({
                    "serie_a_team": squadra,
                    "name": nome_el.get_text(strip=True),
                    "tipo": SEZIONI[label],
                    "nota": descr.get_text(" ", strip=True) if descr else "",
                })
        for label in SEZIONI:
            if label not in trovate:
                anomalie.append(f"{squadra}: manca la sezione {label}")
    return righe, anomalie, squadre


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default=None, help="File HTML locale, per test offline invece di fetch live")
    args = parser.parse_args()

    righe, anomalie, squadre = parse(fetch_html(args.html))
    if len(squadre) != 20:
        print(f"ATTENZIONE: lette {len(squadre)} squadre invece di 20: la pagina è probabilmente cambiata.")
    if not squadre:
        print("ERRORE: nessuna squadra letta, data/squalifiche.json non modificato.")
        return 1

    indice = {(normalize(p["serie_a_team"]), normalize(p["name"])): p["id"] for p in store.load_players()}
    oggi = date.today().isoformat()
    scritte, non_trovati = [], []
    for r in righe:
        pid = indice.get((normalize(r["serie_a_team"]), normalize(r["name"])))
        if pid is None:
            non_trovati.append(r)
            continue
        scritte.append({"player_id": pid, **r, "imported_on": oggi})

    store.save_json(store.DATA_DIR / "squalifiche.json", scritte)
    n_sq = sum(1 for r in scritte if r["tipo"] == "squalificato")
    print(f"OK: {len(squadre)} squadre lette, {n_sq} squalificati e {len(scritte) - n_sq} diffidati.")
    for r in scritte:
        print(f"  {r['tipo']:<12} {r['name']:<22} ({r['serie_a_team']}) {r['nota'][:60]}")
    if non_trovati:
        print(f"ATTENZIONE: {len(non_trovati)} nomi non trovati nel listone (non scritti, verificare a mano):")
        for r in non_trovati:
            print(f"  {r['tipo']:<12} {r['name']} ({r['serie_a_team']})")
    if anomalie:
        print(f"ATTENZIONE: struttura della pagina diversa da quella attesa in {len(anomalie)} punti:")
        for a in anomalie:
            print(f"  {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
