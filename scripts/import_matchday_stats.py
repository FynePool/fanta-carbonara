#!/usr/bin/env python3
"""Importa lo storico gol/assist/cartellini/falli/minuti, tiri, passaggi chiave, rigori
e subentrato per giocatore per partita da BigBalls Sports Data API, in
data/matchday_stats.json.

Fonte verificata in questa sessione con una chiamata reale:
GET /v1/stored/matches/{id}/stats restituisce un box score completo per
ogni giocatore delle due squadre (gol, assist, cartellini gialli/rossi,
falli commessi/subiti, minuti, più extra come tiri/passaggi/duelli — non
tutti importati qui). NON è il voto fantacalcio: il campo "rating" che la
fonte restituisce è un rating generico (tipo Opta/Sofascore), calcolato con
criteri diversi da quello di fantacalcio.it/leghe.fantacalcio.it, che è
l'unico che conta per lo scoring. `voto` e `fantavoto` restano quindi
sempre null qui: li riempie scripts/import_voti.py da fantacalcio.it, che va
lanciato dopo questo script e crea anche le righe dei giocatori che BigBalls non
riconosce (con le statistiche a null).

Gira su tutte le partite "finished" di data/calendario_serie_a.json (va
quindi rilanciato import_calendario_seriea.py prima, se serve aggiornarlo).

Matching giocatore: i nomi di BigBalls non sono coerenti tra loro (a volte
"M. Koné", a volte "Lautaro Martínez" per la stessa fonte) e non
condividono id con data/players.json (che usa "Cognome Iniziale.", es.
"Martinez L."). Il matching è euristico per squadra + cognome (+ iniziale
per disambiguare cognomi ripetuti nella stessa squadra): mai indovinato,
i "non trovati/ambigui" vengono stampati e NON scritti in matchday_stats.json.

Etichette di squadra vecchie: BigBalls scrive spesso la squadra della stagione scorsa o la
nazionale di chi ha cambiato squadra (Kean "Fiorentina", Curtis Jones "Liverpool", N.
González "Argentina"), dentro il box score della partita giusta e con i minuti giusti.
Il matching per squadra li perde. Li recupera la riconciliazione con i voti: se
fantacalcio.it (import_voti.py) ha già scritto una riga per quella partita a un giocatore
che BigBalls non ha abbinato, un nome del box score non abbinato che combacia con lui (per
cognome, iniziale se nota, e con minuti se ha preso voto) gli dà le statistiche. Solo righe
già confermate da fantacalcio.it vengono arricchite così: non se ne crea nessuna nuova.
Chi resta senza abbinamento viene marcato `bigballs: "non_trovato"` e non si riscarica.

Richiede BIGBALLS_API_KEY da ambiente. Merge idempotente per
(player_id, match_id): rilanciarlo aggiorna, non duplica.

Incrementale: scarica solo le partite finite che non sono ancora in archivio, quelle con
righe senza i campi introdotti dopo (tiri, passaggi chiave, rigori, subentrato: una volta
sola), e quelle con righe di fantacalcio.it non ancora cercate nel box score (di solito
il giorno dopo la partita, quando sono arrivati i voti). Così il giro quotidiano costa
poche chiamate (il piano free ne ha 500 al giorno). Le righe già presenti vengono
arricchite, non riscritte: si riempiono solo i campi vuoti, la giornata si aggiorna dal
calendario, e voto e fantavoto non vengono mai toccati.

Uso:
    python3 scripts/import_matchday_stats.py
    python3 scripts/import_matchday_stats.py --ricostruisci   # riscarica tutto
"""
import argparse
import html
import os
import sys
import unicodedata
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from import_calendario_seriea import normalize_team

API_BASE_URL = "https://api.bigballsdata.com/v1"

STAT_FIELDS = {
    "gol": "goals",
    "assist": "assists",
    "cartellini_gialli": "yellow_cards",
    "cartellini_rossi": "red_cards",
    "falli_commessi": "fouls_committed",
    "falli_subiti": "fouls_drawn",
    "minuti": "minutes",
    "tiri": "shots_total",
    "tiri_porta": "shots_on",
    "passaggi_chiave": "passes_key",
    "rigori_segnati": "penalty_scored",
    "rigori_sbagliati": "penalty_missed",
}
# Vero se il giocatore partiva dalla panchina: con minuti > 0 è entrato a partita in corso.
BOOL_FIELDS = {"subentrato": "substitute"}
# Tutti i campi che arrivano da BigBalls, nell'ordine in cui stanno nella riga.
CAMPI_BIGBALLS = [*STAT_FIELDS, *BOOL_FIELDS]


EXTRA_ACCENTS = str.maketrans({
    "ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ł": "l", "Ł": "L",
    "đ": "d", "Đ": "D", "ß": "ss", "ı": "i", "ð": "d", "Ð": "D",
})
NAME_PARTICLES = {"de", "van", "von", "da", "di", "la", "le", "mc", "du", "dos", "del"}


def strip_accents(s: str) -> str:
    s = s.translate(EXTRA_ACCENTS)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def split_name(raw: str):
    """Ritorna (cognome_normalizzato, iniziale_o_None) da un nome grezzo,
    gestendo 'Martinez L.'/'Konè M.' (Cognome Iniziale, formato di
    data/players.json), 'M. Koné' (Iniziale Cognome, formato BigBalls),
    'Lautaro Martínez' (Nome Cognome, con eventuali particelle come
    'De Bruyne') e 'Svilar'/'Vítinha' (solo cognome)."""
    raw_tokens = strip_accents(raw).lower().split()
    if len(raw_tokens) > 1 and raw_tokens[-1].endswith(".") and len(raw_tokens[-1].rstrip(".")) <= 3:
        # "martinez jo." / "esposito se." -> cognome + abbreviazione del nome (listone)
        return " ".join(t.replace(".", "") for t in raw_tokens[:-1]), raw_tokens[-1][0]
    tokens = [t.replace(".", "") for t in raw_tokens]
    if not tokens:
        return "", None
    if len(tokens) == 1:
        return tokens[0], None
    if len(tokens[-1]) == 1:  # "martinez l" -> cognome iniziale
        return " ".join(tokens[:-1]), tokens[-1]
    if len(tokens[0]) == 1:  # "m kone" -> iniziale cognome
        return " ".join(tokens[1:]), tokens[0]
    # "lautaro martinez" / "kevin de bruyne" -> nome [particelle] cognome
    i = len(tokens) - 1
    while i > 0 and tokens[i - 1] in NAME_PARTICLES:
        i -= 1
    # "de bruyne" da solo è tutto cognome: nessun nome da cui prendere l'iniziale
    return " ".join(tokens[i:]), (tokens[0][0] if i > 0 else None)


def build_player_index(players: list[dict]):
    """(squadra, cognome) -> lista di (player_id, iniziale_o_None).

    Nel listone l'iniziale c'è solo quando è scritta ("Martinez L.", "Martinez Jo.").
    Un nome senza iniziale è tutto cognome, anche se ha due parole: si registra sia
    intero ("kolo muani", per "R. Kolo Muani") sia con l'ultima parola ("anguissa", per
    "Andre-Frank Zambo Anguissa"), senza iniziale."""
    index: dict[tuple[str, str], list] = {}
    for p in players:
        tokens = strip_accents(p["name"]).lower().split()
        if len(tokens) > 1 and tokens[-1].endswith("."):
            cognome, iniziale = split_name(p["name"])
            chiavi = [cognome]
        else:
            iniziale = None
            parole = [t.replace(".", "") for t in tokens]
            chiavi = list(dict.fromkeys([" ".join(parole), parole[-1]]))
        for cognome in chiavi:
            index.setdefault((p["serie_a_team"], cognome), []).append((p["id"], iniziale))
    return index


def match_player(index: dict, team: str, raw_name: str):
    cognome, iniziale = split_name(raw_name)
    candidates = index.get((team, cognome), [])
    if len(candidates) == 1:
        pid, iniziale_listone = candidates[0]
        # stesso cognome e squadra ma nome diverso: è un altro giocatore, non questo
        if iniziale and iniziale_listone and iniziale != iniziale_listone:
            return None
        return pid
    if len(candidates) > 1 and iniziale:
        matches = [pid for pid, i in candidates if i == iniziale]
        if len(matches) == 1:
            return matches[0]
    return None


def stat_values(pr: dict) -> dict:
    """I campi BigBalls di una riga del box score. Un conteggio assente vale 0 (la fonte
    omette le chiavi a zero); subentrato assente resta None."""
    stats = pr.get("stats") or {}
    row = {}
    for field, source_key in STAT_FIELDS.items():
        raw_value = stats.get(source_key, {}).get("value")
        row[field] = int(raw_value) if raw_value is not None else 0
    for field, source_key in BOOL_FIELDS.items():
        raw_value = stats.get(source_key, {}).get("value")
        row[field] = None if raw_value is None else str(raw_value).lower() == "true"
    return row


def _parole(raw: str) -> list[str]:
    """Nome del box score in parole minuscole senza accenti né punteggiatura. Ripara le
    entità HTML ("N&apos;Diaye") e l'UTF-8 letto come Latin-1 ("OulaÃ¯")."""
    raw = html.unescape(raw or "")
    try:
        raw = raw.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    testo = strip_accents(raw).lower().replace("'", "").replace("-", " ").replace(".", " ")
    return testo.split()


def riconcilia(nome_bigballs: str, candidati: dict) -> str | None:
    """player_id del giocatore tra `candidati` (id -> nome del listone) che combacia con
    `nome_bigballs`, se è uno solo. Il cognome del listone, senza spazi, deve essere uguale
    a una sequenza di parole consecutive del nome BigBalls ("Delprato" = "E. Del Prato",
    "Ramon" in "Jacobo Ramón Naveros"); se il listone ha l'iniziale, deve essere quella
    della prima parola."""
    parole = _parole(nome_bigballs)
    if not parole:
        return None
    spezzoni = {"".join(parole[i:j]) for i in range(len(parole)) for j in range(i + 1, len(parole) + 1)}
    trovati = []
    for pid, nome in candidati.items():
        # Come in build_player_index: nel listone l'iniziale c'è solo se è scritta
        # ("Jones C."); senza, tutto il nome è cognome ("El Shaarawy", "Diego Carlos").
        if len(nome.split()) > 1 and nome.split()[-1].endswith("."):
            cognome, iniziale = "".join(_parole(" ".join(nome.split()[:-1]))), nome.split()[-1][0].lower()
        else:
            cognome, iniziale = "".join(_parole(nome)), None
        if cognome not in spezzoni:
            continue
        if iniziale and (len(parole) < 2 or parole[0][0] != iniziale):
            continue
        trovati.append(pid)
    return trovati[0] if len(trovati) == 1 else None


def fetch_match_stats(api_key: str, match_id: str):
    resp = requests.get(
        f"{API_BASE_URL}/stored/matches/{match_id}/stats",
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code} — {resp.text[:200]}")
    return resp.json().get("data", {}).get("players", [])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ricostruisci",
        action="store_true",
        help="riscarica tutte le partite giocate, non solo quelle mancanti (1 chiamata API per partita)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("BIGBALLS_API_KEY")
    if not api_key:
        print("ERRORE: imposta BIGBALLS_API_KEY come variabile d'ambiente.")
        return 1

    calendario = {m["match_id"]: m for m in store.load_json(store.DATA_DIR / "calendario_serie_a.json")}
    finished = [m for m in calendario.values() if m["stato"] == "finished"]
    players = store.load_players()
    players_by_id = {p["id"]: p for p in players}
    index = build_player_index(players)

    stats_path = store.DATA_DIR / "matchday_stats.json"
    existing = store.load_json(stats_path) if stats_path.exists() else []

    # Righe già in archivio: si aggiorna la giornata dal calendario (arriva dopo la
    # partita, e così si riempie senza chiamate API). Non se ne toglie mai nessuna, neanche
    # di chi è uscito dal listone o ha cambiato squadra: lo storico non si accorcia (vedi
    # store.save_matchday_stats). Le righe contaminate si fermano alla scrittura, sotto.
    by_key = {}
    for r in existing:
        match = calendario.get(r["match_id"])
        if match is not None:
            r["matchday"] = match["giornata"]
        by_key[(r["player_id"], r["match_id"])] = r

    # Le righe create da import_voti.py per giocatori che BigBalls non ha (statistiche a
    # null) non contano: una partita è scaricata solo se ha righe BigBalls.
    imported = {mid for (_, mid), r in by_key.items() if r.get("minuti") is not None}
    # Da riscaricare anche: le partite con righe senza i campi nuovi (una volta sola) e
    # quelle con righe di fantacalcio.it non ancora cercate nel box score.
    da_arricchire = {mid for (_, mid), r in by_key.items() if any(c not in r for c in CAMPI_BIGBALLS)}
    da_riconciliare = {
        mid for (_, mid), r in by_key.items() if r.get("minuti") is None and r.get("bigballs") != "non_trovato"
    }
    if args.ricostruisci:
        to_fetch = finished
    else:
        to_fetch = [
            m for m in finished
            if m["match_id"] not in imported or m["match_id"] in da_arricchire | da_riconciliare
        ]

    unmatched = []
    failed_matches = []
    nuove = arricchite = 0
    riconciliate = []  # (partita, nome listone, nome BigBalls, squadra BigBalls)
    non_trovate = []

    for match in to_fetch:
        try:
            player_rows = fetch_match_stats(api_key, match["match_id"])
        except RuntimeError as e:
            failed_matches.append((match["match_id"], str(e)))
            continue

        mid = match["match_id"]
        squadre = (match["squadra_casa"], match["squadra_trasferta"])
        gia_in_archivio = {pid for pid, m in by_key if m == mid}
        abbinati = {}  # player_id -> (valori BigBalls, squadra)
        liberi = []  # righe del box score non abbinate: nome, squadra BigBalls, valori
        for pr in player_rows:
            team = normalize_team(pr.get("team_name") or "")
            valori = stat_values(pr)
            player_id = match_player(index, team, pr["name"]) if team in squadre else None
            if player_id is None or player_id in abbinati:
                liberi.append((pr["name"], pr.get("team_name"), valori, team in squadre))
                continue
            abbinati[player_id] = (valori, team)

        # Riconciliazione con i voti: righe già scritte da fantacalcio.it per questa
        # partita, che BigBalls non ha abbinato per nome e squadra.
        attesi = {
            pid: players_by_id[pid]["name"]
            for pid in gia_in_archivio
            if by_key[(pid, mid)].get("minuti") is None and pid not in abbinati and pid in players_by_id
        }
        for nome, squadra_bb, valori, di_questa_partita in liberi:
            pid = riconcilia(nome, attesi)
            # Un voto senza minuti è un altro giocatore con lo stesso nome.
            if pid is not None and by_key[(pid, mid)].get("voto") is not None and not valori["minuti"]:
                pid = None
            if pid is None:
                if di_questa_partita:
                    unmatched.append((mid, normalize_team(squadra_bb or ""), nome))
                continue
            abbinati[pid] = (valori, None)
            del attesi[pid]
            riconciliate.append((mid, players_by_id[pid]["name"], nome, squadra_bb))

        for player_id, (valori, team) in abbinati.items():
            key = (player_id, mid)
            prev = by_key.get(key)
            if prev is None:
                if team is None:
                    continue  # la riconciliazione arricchisce, non crea
                in_casa = team == match["squadra_casa"]
                by_key[key] = {
                    "player_id": player_id,
                    "match_id": mid,
                    "matchday": match["giornata"],
                    "opponent_serie_a_team": match["squadra_trasferta"] if in_casa else match["squadra_casa"],
                    "home_away": "casa" if in_casa else "trasferta",
                    "voto": None,
                    "fantavoto": None,
                    **valori,
                }
                nuove += 1
                continue
            # Riga già in archivio: voto e fantavoto non si toccano mai. Con --ricostruisci
            # le statistiche vengono riscritte dalla fonte; se no si riempiono solo i campi
            # vuoti o mancanti.
            cambiati = False
            for campo in CAMPI_BIGBALLS:
                if args.ricostruisci or prev.get(campo) is None:
                    if prev.get(campo) != valori[campo] or campo not in prev:
                        cambiati = True
                    prev[campo] = valori[campo]
            prev.pop("bigballs", None)
            arricchite += cambiati

        # Chi fantacalcio.it ha in questa partita e BigBalls no: si marca, così il giro
        # dopo non riscarica la partita per lui. I campi nuovi restano vuoti.
        for pid in gia_in_archivio:
            r = by_key[(pid, mid)]
            if r.get("minuti") is None:
                for campo in CAMPI_BIGBALLS:
                    r.setdefault(campo, None)
                if r.get("bigballs") != "non_trovato":
                    r["bigballs"] = "non_trovato"
                    non_trovate.append((mid, players_by_id.get(pid, {}).get("name", pid)))

    merged = sorted(by_key.values(), key=lambda r: (r["matchday"] or 0, r["match_id"], r["player_id"]))
    try:
        store.save_matchday_stats(merged)
    except store.StoricoPerso as e:
        print(f"ERRORE: {e}")
        return 1

    print(f"OK: {len(to_fetch)} partite scaricate, {len(merged)} righe totali in matchday_stats.json "
          f"({nuove} nuove, {arricchite} arricchite).")
    if riconciliate:
        print(f"Riconciliate con i voti di fantacalcio.it ({len(riconciliate)}; squadra BigBalls tra parentesi):")
        for match_id, nome, nome_bb, squadra_bb in riconciliate:
            print(f"  match={match_id} {nome} = {nome_bb!r} ({squadra_bb})")
    if non_trovate:
        print(f"Con voto su fantacalcio.it ma non nel box score BigBalls ({len(non_trovate)}), marcate e non più "
              f"cercate: {', '.join(sorted({n for _, n in non_trovate}))}")
    if failed_matches:
        print(f"ATTENZIONE: {len(failed_matches)} partite non scaricate (riprovate al prossimo giro): {failed_matches}")
    if unmatched:
        print(f"ATTENZIONE: {len(unmatched)} giocatori delle due squadre non riconosciuti nel listone (non scritti):")
        for match_id, team, name in unmatched:
            print(f"  match={match_id} squadra={team!r} nome={name!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
