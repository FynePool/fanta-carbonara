#!/usr/bin/env python3
"""Statistiche delle stagioni passate di tutti i giocatori della Serie A, da
fantacalcio.it, in data/storico_stagioni.json.

Fonte: la pagina "Statistiche Serie A" di fantacalcio.it
(https://www.fantacalcio.it/statistiche-serie-a/<stagione>/fantacalcio/medie), HTML
statico, una riga per giocatore che ha giocato almeno una volta in Serie A quella
stagione. Struttura verificata il 27/09/2026 sulle stagioni 2025-26 (663 giocatori) e
2024-25 (679):

- `tr.player-row`, con il link alla scheda del giocatore che finisce con
  ".../<id>/<stagione>": l'id è lo stesso del listone ("fd<id>"), quindi l'abbinamento
  è per id e non per nome;
- colonne `td[data-col-key]`, in quest'ordine: sq (squadra), pg (partite con voto, "PV"
  sul sito), mv (media voto), mfv (fantamedia), gol, gs (gol subiti, portieri), rig
  ("segnati / calciati"), rp (rigori parati), ass, amm, esp.
  L'ordine di "rig" è dedotto dall'attributo `data-penalties` della riga, che vale
  segnati + (segnati/calciati)/10 in tutte le 663 righe della 2025-26 ("2 / 3" ->
  2.0667): il primo numero non supera mai il secondo.

Se le colonne sono diverse da queste, o la pagina ha meno di 400 giocatori, lo script
non scrive niente e lo dice, invece di indovinare.

Solo Serie A: chi la stagione scorsa giocava in un altro campionato o in Serie B qui
non c'è, e non si inventa. Le stagioni finite non cambiano, quindi basta lanciarlo una
volta per stagione (non fa parte del giro del mattino). Rilanciarlo riscrive solo le
stagioni richieste e lascia le altre come sono.

Serve a dare contesto al consiglio (quanto ha giocato e reso un giocatore negli anni
scorsi, chi tira i rigori), non entra nel valore del modello finché il backtest non
dimostra che migliora le previsioni: vedi .docs/difetti-consiglio-formazione.md.

Uso:
    python3 scripts/import_storico_stagioni.py                         # 2025-26 e 2024-25
    python3 scripts/import_storico_stagioni.py --stagioni 2025-26
    python3 scripts/import_storico_stagioni.py --stagioni 2025-26 --html pagina.html   # test offline
"""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store

URL = "https://www.fantacalcio.it/statistiche-serie-a/{stagione}/fantacalcio/medie"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
PATH = store.DATA_DIR / "storico_stagioni.json"
COLONNE = ["sq", "pg", "mv", "mfv", "gol", "gs", "rig", "rp", "ass", "amm", "esp"]
MINIMO_GIOCATORI = 400
STAGIONE_RE = re.compile(r"^\d{4}-\d{2}$")
LINK_RE = re.compile(r"/(\d+)/(\d{4}-\d{2})/?$")
# Nella stagione IN CORSO il link della scheda non ha il suffisso della stagione: finisce
# con l'id (verificato il 27/09/2026: /serie-a/squadre/roma/malen/5585). Le colonne sono
# le stesse delle stagioni finite.
LINK_CORRENTE_RE = re.compile(r"/(\d+)/?$")
RIGORI_RE = re.compile(r"^(\d+)\s*/\s*(\d+)$")


def _numero(testo: str) -> float | None:
    testo = testo.strip().replace(",", ".")
    return float(testo) if testo else None


def _intero(testo: str) -> int:
    return int(testo.strip() or 0)


def leggi(html: str, stagione: str, corrente: bool = False) -> tuple[dict, list[str]]:
    """Ritorna (giocatori per id, anomalie). Con anomalie non si scrive niente.

    `corrente` per la stagione in corso, i cui link non portano la stagione."""
    soup = BeautifulSoup(html, "html.parser")
    giocatori, anomalie = {}, []
    for tr in soup.select("tr.player-row"):
        link = tr.select_one("a.player-name")
        href = link["href"].strip() if link and link.get("href") else ""
        if corrente:
            m = LINK_CORRENTE_RE.search(href)
            stagione_del_link = stagione if m else None
        else:
            m = LINK_RE.search(href)
            stagione_del_link = m.group(2) if m else None
        if not m or stagione_del_link != stagione:
            anomalie.append(f"riga senza link alla scheda della stagione {stagione}: {tr.get('data-filter-keywords')}")
            continue
        celle = tr.select("td[data-col-key]")
        chiavi = [td["data-col-key"] for td in celle]
        if chiavi != COLONNE:
            anomalie.append(f"colonne diverse da quelle attese per {tr.get('data-filter-keywords')}: {chiavi}")
            continue
        v = {k: td.get_text(strip=True) for k, td in zip(chiavi, celle)}
        rig = RIGORI_RE.match(v["rig"])
        if not rig or int(rig.group(1)) > int(rig.group(2)):
            anomalie.append(f"rigori non nel formato 'segnati / calciati' per {tr.get('data-filter-keywords')}: {v['rig']!r}")
            continue
        pg = _intero(v["pg"])
        giocatori[f"fd{m.group(1)}"] = {
            "nome": link.get_text(strip=True),
            "squadra": v["sq"],
            "ruolo": (tr.get("data-filter-role-classic") or "").upper() or None,
            "partite_con_voto": pg,
            # Senza partite il sito scrive 0 di media: non è un voto, è un'assenza.
            "media_voto": _numero(v["mv"]) if pg else None,
            "fantamedia": _numero(v["mfv"]) if pg else None,
            "gol": _intero(v["gol"]),
            "gol_subiti": _intero(v["gs"]),
            "rigori_segnati": int(rig.group(1)),
            "rigori_calciati": int(rig.group(2)),
            "rigori_parati": _intero(v["rp"]),
            "assist": _intero(v["ass"]),
            "ammonizioni": _intero(v["amm"]),
            "espulsioni": _intero(v["esp"]),
        }
    if len(giocatori) < MINIMO_GIOCATORI:
        anomalie.append(f"letti {len(giocatori)} giocatori, mi aspettavo almeno {MINIMO_GIOCATORI}")
    return giocatori, anomalie


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stagioni", nargs="+", default=["2025-26", "2024-25"])
    parser.add_argument("--html", help="pagina già scaricata (una sola stagione)")
    parser.add_argument(
        "--corrente", action="store_true",
        help=("la stagione è quella IN CORSO: si scrive in `stagione_in_corso`, non in "
              "`stagioni`. Serve ai rigori ufficiali di quest'anno (scripts/rigoristi.py). "
              "NON va in `stagioni` perché chi legge quel dizionario prende la stagione più "
              "recente come 'quella scorsa': ci finirebbe la stagione in corso e il backtest "
              "guarderebbe il futuro."),
    )
    args = parser.parse_args()
    if args.corrente and len(args.stagioni) != 1:
        parser.error("--corrente vale per una stagione sola")
    if args.html and len(args.stagioni) != 1:
        parser.error("--html vale per una stagione sola")

    archivio = store.load_json(PATH) if PATH.exists() else {"stagioni": {}}
    listone = {p["id"] for p in store.load_players()}
    scritte, errori = 0, 0
    for stagione in args.stagioni:
        if not STAGIONE_RE.match(stagione):
            print(f"{stagione}: formato stagione non valido (atteso AAAA-AA)")
            errori += 1
            continue
        url = URL.format(stagione=stagione)
        if args.html:
            html = Path(args.html).read_text(encoding="utf-8")
        else:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code != 200:
                print(f"{stagione}: HTTP {resp.status_code}, niente di scritto")
                errori += 1
                continue
            html = resp.text
        giocatori, anomalie = leggi(html, stagione, corrente=args.corrente)
        if anomalie:
            print(f"{stagione}: struttura della pagina diversa da quella attesa, niente di scritto:")
            for a in anomalie[:10]:
                print(f"  - {a}")
            if len(anomalie) > 10:
                print(f"  ... e altre {len(anomalie) - 10}")
            errori += 1
            continue
        voce = {
            "fonte": url,
            "letto_il": date.today().isoformat(),
            "giocatori": dict(sorted(giocatori.items())),
        }
        if args.corrente:
            voce["stagione"] = stagione
            voce["_note"] = (
                "Stagione IN CORSO: i numeri crescono a ogni giornata. Sta fuori da "
                "`stagioni` di proposito, perché chi legge quel dizionario prende la "
                "stagione più recente come 'quella scorsa'. La legge scripts/rigoristi.py "
                "per i rigori ufficiali di quest'anno."
            )
            archivio["stagione_in_corso"] = voce
        else:
            archivio["stagioni"][stagione] = voce
        scritte += 1
        nel_listone = sum(1 for pid in giocatori if pid in listone)
        print(f"{stagione}: {len(giocatori)} giocatori, di cui {nel_listone} nel listone di oggi "
              f"({len(listone) - nel_listone} del listone non hanno giocato in Serie A quella stagione)")

    if scritte:
        archivio["stagioni"] = dict(sorted(archivio["stagioni"].items(), reverse=True))
        store.save_json(PATH, archivio)
        print(f"Scritto {PATH.relative_to(store.DATA_DIR.parent)}")
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
