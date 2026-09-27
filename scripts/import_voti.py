#!/usr/bin/env python3
"""Voto e fantavoto per giocatore per partita da fantacalcio.it, in
data/matchday_stats.json.

Fonte: la pagina "Voti Fantacalcio Serie A"
(https://www.fantacalcio.it/voti-fantacalcio-serie-a/<stagione>/<giornata>),
HTML statico, una tabella per squadra per partita. Struttura verificata il 27/09/2026
sulle giornate 1-5 della 2026-27:

- intestazione della partita: `div.match-score` con squadra di casa, gol, gol, squadra
  in trasferta;
- una riga per giocatore con il link alla sua scheda, che finisce con l'id
  fantacalcio (".../zaccagni/632"): è lo stesso id del listone ("fd632"), quindi il
  matching è per id e non per nome;
- tre coppie voto/fantavoto (`span.player-grade` / `span.player-fanta-grade`), nell'ordine
  Redazione Fantacalcio, Voto Statistico, Voto Italia. La lega usa la **prima**
  (Redazione): è `config/league.json` -> `fonte_voti`;
- "55" nel voto e nel fantavoto vuol dire senza voto (giocato troppo poco): sulla
  pagina appare come un 6 grigio con fantavoto "-". Si scrive null, mai 6 né 5,5;
- l'ammonizione è la classe `yellow-card` sul voto, non un numero (il fantavoto la
  include già). Le righe degli allenatori (senza link) vengono ignorate.

Se la struttura è diversa da questa (colonne in altro ordine, classi sconosciute) lo
script lo segnala e non scrive quei valori invece di indovinare.

Si leggono solo le partite finite nel calendario (data/calendario_serie_a.json): durante
una giornata la pagina mostra voti provvisori. Il sito può correggere i voti nei giorni
successivi, quindi qui voto e fantavoto vengono **sempre riscritti** con l'ultimo valore
pubblicato. La partita si trova per coppia casa/trasferta, unica in una stagione.
Va lanciato **dopo** import_matchday_stats.py, che rifà le righe delle partite nuove.
Non toglie mai righe: un voto già in archivio resta anche se il giocatore esce dal
listone o la pagina non lo mostra più.

Righe: se c'è già la riga BigBalls (player_id, match_id) si riempiono voto e fantavoto;
se no (circa 30-60 giocatori a giornata che BigBalls non riconosce) si crea una riga
nuova con le statistiche BigBalls a null, non a 0: nessuno le ha misurate. I giocatori
che non sono nel listone vengono stampati e non scritti.

Uso:
    python3 scripts/import_voti.py                      # tutte le giornate finite
    python3 scripts/import_voti.py --giornata 5
    python3 scripts/import_voti.py --giornata 5 --html /percorso/pagina.html   # test offline
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from import_matchday_stats import STAT_FIELDS
from lib import store

URL = "https://www.fantacalcio.it/voti-fantacalcio-serie-a/{stagione}/{giornata}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
FONTI = ["Redazione Fantacalcio", "Voto Statistico", "Voto Italia"]
SENZA_VOTO = "55"
CLASSI_VOTO_NOTE = {"player-grade", "yellow-card", "red-card"}
ID_RE = re.compile(r"/(\d+)/?$")

# Nomi delle squadre sulla pagina voti -> nomi del calendario, dove diversi.
TEAM_MAP: dict[str, str] = {}


def stagione_label(anno: int) -> str:
    return f"{anno}-{str(anno + 1)[-2:]}"


def fetch_html(stagione: str, giornata: int, local_path: str | None) -> str:
    if local_path:
        return Path(local_path).read_text(encoding="utf-8")
    resp = requests.get(URL.format(stagione=stagione, giornata=giornata), headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_numero(raw: str):
    """'6,5' -> 6.5; '55' (senza voto) o vuoto -> None."""
    raw = (raw or "").strip()
    if raw in ("", SENZA_VOTO, "-"):
        return None
    return float(raw.replace(",", "."))


def parse(html: str, fonte: str):
    """Ritorna (righe, anomalie). Una riga: casa, trasferta, squadra, fc_id, nome, voto,
    fantavoto, senza_voto."""
    soup = BeautifulSoup(html, "html.parser")
    col = FONTI.index(fonte)
    righe, anomalie = [], []

    for tabella in soup.select("li.team-table"):
        punteggio = tabella.select_one("div.match-score")
        nome_squadra = tabella.select_one("a.team-name")
        if punteggio is None or nome_squadra is None:
            anomalie.append("scheda squadra senza intestazione partita o nome squadra")
            continue
        parti = [s.get_text(strip=True) for s in punteggio.find_all("span")]
        # "Bologna", "0", "-", "1", "Lazio"
        if len(parti) != 5 or parti[2] != "-":
            anomalie.append(f"intestazione partita inattesa: {parti}")
            continue
        casa, trasferta = TEAM_MAP.get(parti[0], parti[0]), TEAM_MAP.get(parti[4], parti[4])
        squadra = nome_squadra.get_text(strip=True)
        squadra = TEAM_MAP.get(squadra, squadra)

        # L'ordine delle fonti è nelle icone dell'intestazione: se cambia, non si indovina.
        icone = [img.get("title") for img in tabella.select("thead div.group img")]
        if icone[:3] != FONTI:
            anomalie.append(f"{squadra}: colonne dei voti in ordine inatteso {icone[:3]}")
            continue

        for tr in tabella.select("tr"):
            link = tr.select_one("a.player-name")
            if link is None:
                continue  # allenatore
            m = ID_RE.search(link.get("href", ""))
            if not m:
                anomalie.append(f"{squadra}: link giocatore senza id: {link.get('href')}")
                continue
            voti = tr.select("span.player-grade")
            fantavoti = tr.select("span.player-fanta-grade")
            nome = link.get_text(strip=True)
            if len(voti) != 3 or len(fantavoti) != 3:
                anomalie.append(f"{squadra} {nome}: {len(voti)} voti e {len(fantavoti)} fantavoti invece di 3")
                continue
            classi = set(voti[col].get("class", [])) - CLASSI_VOTO_NOTE
            if classi:
                anomalie.append(f"{squadra} {nome}: classe del voto sconosciuta {sorted(classi)}")
                continue
            raw_v, raw_fv = voti[col].get("data-value", ""), fantavoti[col].get("data-value", "")
            try:
                voto, fantavoto = parse_numero(raw_v), parse_numero(raw_fv)
            except ValueError:
                anomalie.append(f"{squadra} {nome}: voto non numerico {raw_v!r}/{raw_fv!r}")
                continue
            if (voto is None) != (fantavoto is None):
                anomalie.append(f"{squadra} {nome}: voto {raw_v!r} e fantavoto {raw_fv!r} incoerenti")
                continue
            righe.append({
                "casa": casa,
                "trasferta": trasferta,
                "squadra": squadra,
                "fc_id": m.group(1),
                "nome": nome,
                "voto": voto,
                "fantavoto": fantavoto,
                "senza_voto": raw_v.strip() == SENZA_VOTO,
            })
    return righe, anomalie


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--giornata", type=int, default=None, help="solo questa giornata (default: tutte le finite)")
    parser.add_argument("--html", default=None, help="pagina salvata, per test offline (richiede --giornata)")
    args = parser.parse_args()
    if args.html and args.giornata is None:
        print("ERRORE: --html richiede --giornata.")
        return 1

    config = store.load_league_config()
    fonte = config.get("fonte_voti", FONTI[0])
    if fonte not in FONTI:
        print(f"ERRORE: fonte_voti {fonte!r} in config/league.json non è tra {FONTI}.")
        return 1

    calendario = store.load_json(store.DATA_DIR / "calendario_serie_a.json")
    per_coppia = {(m["squadra_casa"], m["squadra_trasferta"]): m for m in calendario}
    stagione = calendario[0]["stagione"] if calendario else stagione_label(date.today().year)
    giornate_finite = sorted({m["giornata"] for m in calendario if m["stato"] == "finished" and m["giornata"]})
    giornate = [args.giornata] if args.giornata is not None else giornate_finite

    players = {p["id"]: p for p in store.load_players()}
    stats_path = store.DATA_DIR / "matchday_stats.json"
    stats = store.load_json(stats_path) if stats_path.exists() else []
    by_key = {(r["player_id"], r["match_id"]): r for r in stats}

    aggiornate = nuove = senza_voto = saltate_non_finite = 0
    non_nel_listone, squadra_diversa, anomalie_tot, fallite = [], [], [], []
    partite_senza_calendario = set()

    for giornata in giornate:
        try:
            html = fetch_html(stagione, giornata, args.html)
        except requests.RequestException as e:
            fallite.append((giornata, str(e)))
            continue
        righe, anomalie = parse(html, fonte)
        anomalie_tot += [f"giornata {giornata}: {a}" for a in anomalie]
        if not righe and not anomalie:
            continue  # giornata non ancora pubblicata

        for r in righe:
            match = per_coppia.get((r["casa"], r["trasferta"]))
            if match is None:
                partite_senza_calendario.add((giornata, r["casa"], r["trasferta"]))
                continue
            if match["stato"] != "finished":
                saltate_non_finite += 1
                continue
            pid = f"fd{r['fc_id']}"
            if pid not in players:
                non_nel_listone.append((giornata, r["squadra"], r["nome"], pid))
                continue
            if players[pid]["serie_a_team"] != r["squadra"]:
                # Per id il giocatore è giusto; la squadra del listone è quella di oggi.
                squadra_diversa.append((giornata, r["nome"], r["squadra"], players[pid]["serie_a_team"]))

            key = (pid, match["match_id"])
            row = by_key.get(key)
            if row is None:
                in_casa = r["squadra"] == match["squadra_casa"]
                row = {
                    "player_id": pid,
                    "match_id": match["match_id"],
                    "matchday": match["giornata"],
                    "opponent_serie_a_team": match["squadra_trasferta"] if in_casa else match["squadra_casa"],
                    "home_away": "casa" if in_casa else "trasferta",
                    "voto": None,
                    "fantavoto": None,
                    **{field: None for field in STAT_FIELDS},
                }
                by_key[key] = row
                nuove += 1
            else:
                aggiornate += 1
            row["voto"], row["fantavoto"] = r["voto"], r["fantavoto"]
            senza_voto += r["senza_voto"]

    merged = sorted(by_key.values(), key=lambda r: (r["matchday"] or 0, r["match_id"], r["player_id"]))
    try:
        store.save_matchday_stats(merged)
    except store.StoricoPerso as e:
        print(f"ERRORE: {e}")
        return 1

    print(f"OK: fonte {fonte!r}, giornate {giornate}. Righe con voto aggiornate {aggiornate}, "
          f"righe nuove (giocatori che BigBalls non ha) {nuove}; senza voto (s.v.) in totale {senza_voto}.")
    if saltate_non_finite:
        print(f"Saltate {saltate_non_finite} righe di partite non ancora finite nel calendario (voti provvisori).")
    if fallite:
        print(f"ATTENZIONE: giornate non scaricate (riprovate al prossimo giro): {fallite}")
    if anomalie_tot:
        print(f"ATTENZIONE: {len(anomalie_tot)} anomalie di struttura della pagina, valori non scritti:")
        for a in anomalie_tot:
            print(f"  {a}")
    if partite_senza_calendario:
        print(f"ATTENZIONE: partite della pagina voti non trovate nel calendario (nome squadra diverso?): "
              f"{sorted(partite_senza_calendario)}")
    if squadra_diversa:
        print(f"Nota: {len(squadra_diversa)} voti di giocatori che nel listone hanno un'altra squadra "
              f"(scritti lo stesso, l'id è quello giusto):")
        for g, nome, sq, sq_listone in squadra_diversa:
            print(f"  giornata {g}: {nome} ({sq}, listone: {sq_listone})")
    if non_nel_listone:
        print(f"ATTENZIONE: {len(non_nel_listone)} voti di giocatori assenti dal listone (non scritti):")
        for g, sq, nome, pid in non_nel_listone:
            print(f"  giornata {g}: {nome} ({sq}) {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
