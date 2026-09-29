#!/usr/bin/env python3
"""Controlla la formazione inserita su leghe.fantacalcio.it per la prossima giornata di lega.

Legge la formazione salvata sul sito (endpoint `teamLineup`, vedi .docs/leghe-fc-api.md) e
la confronta con i dati di oggi e con il consiglio di `report_formazione.py`. Solo lettura:
non scrive in data/ e non tocca la formazione sul sito. Serve perché la formazione si
inserisce giorni prima della scadenza, e intanto un titolare si fa male o le probabili
cambiano: la lega non avvisa, e senza formazione dà lo 0-3 a tavolino.

La prima riga dell'output è il verdetto, scritto per la notifica del giro del mattino:
    FORMAZIONE OK                inserita, nessun indisponibile, in linea col consiglio (le
                                 differenze entro SOGLIA_PARI sono scelte tue, non errori)
    FORMAZIONE DA CORREGGERE     un infortunato o squalificato schierato, un giocatore non
                                 più in rosa, o un ruolo che vale più di SOGLIA_PARI punti
                                 attesi sotto il consiglio
    FORMAZIONE MANCANTE          non c'è, e mancano GIORNI_URGENZA giorni o meno alla scadenza
    FORMAZIONE NON CONTROLLATA   il controllo non ha potuto girare: sito, credenziali, dati
    FORMAZIONE NESSUN AVVISO     niente da controllare: formazione non ancora inserita con la
                                 scadenza lontana, turno in corso, nessuna giornata di lega
Solo NESSUN AVVISO non va in cima al riepilogo del giro del mattino (vedi la skill
aggiorna-dati): è la situazione normale fra un turno e l'altro.

Legge solo la mia formazione. Quella dell'avversario il sito la restituisce anche prima
della scadenza, ma non cambia quale formazione mi conviene.

Richiede LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD come variabili d'ambiente.

Uso:
    python3 scripts/controlla_formazione.py [--team-id ID] [--league-id ID]
"""
import argparse
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import leghe_fc_client as client
from lib import store
from lib.roster import (MODULE_ROLE_COUNTS, ROLES, SOGLIA_PARI, _slot_attesi, _valore,
                        prossimo_turno, quote_portieri, suggest_lineup)

ROMA = ZoneInfo("Europe/Rome")

# Decisione dell'utente (29/09): l'avviso di formazione mancante arriva dai 2 giorni prima
# della scadenza fino al giorno stesso (con la scadenza sabato: giovedì, venerdì e sabato
# mattina). Prima non serve: dopo un turno la formazione successiva manca per forza.
GIORNI_URGENZA = 2


def giorni_alla_scadenza(inizio: datetime, adesso: datetime) -> int:
    """Giorni di calendario (ora italiana) fra oggi e il giorno della scadenza: 0 il giorno
    stesso, anche se la routine gira alle 6 e la partita è alle 20:45."""
    return (inizio.astimezone(ROMA).date() - adesso.astimezone(ROMA).date()).days


def giornata_da_controllare(competizioni: list[dict], calendario: list[dict],
                            team_id: str) -> tuple[dict | None, str | None]:
    """(giornata, None) o (None, motivo): la prima giornata di lega non calcolata in cui la
    squadra gioca e il cui turno di Serie A non è ancora iniziato, se è il prossimo turno.

    Il numero del turno di Serie A non si legge dal calendario per le partite future
    (BigBalls lo assegna solo dopo la partita, vedi .docs/bigballs-api.md): si contano le
    partite finite di ogni squadra. Ogni squadra gioca una partita per turno, quindi il turno
    N è iniziato se almeno una squadra ne ha finite N. Un rinvio fa restare indietro una
    squadra, mai avanti: il conto non si inganna."""
    stagione = max((m["stagione"] for m in calendario), default=None)
    giocate = Counter()
    for m in calendario:
        if m["stagione"] == stagione and m["stato"] == "finished":
            giocate[m["squadra_casa"]] += 1
            giocate[m["squadra_trasferta"]] += 1
    iniziato = max(giocate.values(), default=0)

    candidate = []
    for comp in competizioni:
        if comp.get("eliminata"):
            continue
        for g in comp.get("calendario", []):
            if g.get("calcolata") or g["giornata_serie_a"] <= iniziato:
                continue
            partita = next((p for p in g["partite"] if team_id in (p["casa"], p["trasferta"])), None)
            if partita:
                casa = partita["casa"] == team_id
                candidate.append({
                    "competizione_id": comp["id"],
                    "competizione": comp["nome"],
                    "giornata": g["giornata"],
                    "giornata_serie_a": g["giornata_serie_a"],
                    "casa": casa,
                    "id_casa": partita["casa"],
                    "id_trasferta": partita["trasferta"],
                    "avversario_id": partita["trasferta"] if casa else partita["casa"],
                })
                break
    if not candidate:
        return None, "nessuna giornata di lega ancora da giocare per questa squadra"
    prima = min(candidate, key=lambda c: c["giornata_serie_a"])
    if prima["giornata_serie_a"] != iniziato + 1:
        return None, (f"la prossima giornata di lega è sul turno {prima['giornata_serie_a']} di Serie A, "
                      f"ma il prossimo turno è il {iniziato + 1}: niente da controllare oggi")
    return prima, None


def scadenza(turno: dict) -> datetime | None:
    """Inizio della prima partita non rinviata del turno (stessa regola del report)."""
    giocate = [m for m in turno["partite"] if m["stato"] != "postponed"]
    if not turno["chiaro"] or not giocate:
        return None
    return datetime.fromisoformat(giocate[0]["data_utc"].replace("Z", "+00:00"))


def formazione_salvata(risposta: dict, giornata: dict, team_id: str) -> dict | None:
    """La mia formazione dalla risposta di teamLineup, con gli id del listone (`fd<id>`), o
    None se non è stata inserita (il sito risponde `null` per la squadra)."""
    lato = risposta.get("home" if giornata["casa"] else "away")
    if not lato or not lato.get("starts"):
        return None
    if str(lato.get("tid")) != str(team_id):
        raise client.LegheFcError(f"la risposta della lega riguarda la squadra {lato.get('tid')}, non {team_id}")
    return {
        "titolari": [f"fd{x['pid']}" if x.get("pid") else None for x in lato["starts"]],
        "panchina": [f"fd{x['pid']}" if x.get("pid") else None for x in lato.get("bench") or []],
        "salvata": lato.get("ldate"),
        "salvataggi": lato.get("lucnt"),
    }


def _per_ruolo(entries: list[dict]) -> dict:
    ruoli = {role: [] for role in ROLES}
    for e in entries:
        ruoli[e["player"]["role"]].append(e)
    return ruoli


def _modulo(titolari: list[dict]) -> str:
    conta = Counter(e["player"]["role"] for e in titolari)
    return f"{conta['D']}-{conta['C']}-{conta['A']}"


def confronta(salvata: dict, consiglio: dict, players_by_id: dict,
              quote: tuple[dict, set] = ({}, set())) -> dict:
    """Confronta la formazione salvata col consiglio di suggest_lineup.

    Il valore di un ruolo è quello del report (`_slot_attesi`: titolari e riserve di quel
    ruolo nell'ordine del sito, con la probabilità di prendere voto), così una formazione
    uguale al consiglio vale esattamente quanto il consiglio. Un infortunato o squalificato
    schierato conta con probabilità 0: se è titolare entra il primo panchinaro del ruolo,
    se è in panchina il suo posto è buttato.

    Da correggere: un indisponibile o un giocatore fuori rosa schierato, o un ruolo che vale
    più di SOGLIA_PARI sotto il consiglio. Sotto quella soglia il modello non sa scegliere
    meglio di una moneta (vedi report), quindi una differenza lì è una scelta, non un errore.
    Col modulo diverso i ruoli non si confrontano uno a uno e vale la somma."""
    quota, fuori_porta = quote
    per_id = {e["player"]["id"]: e for e in consiglio["titolari"] + consiglio["panchina"] + consiglio["esclusi"]}
    problemi = []
    for nd in consiglio["non_disponibili"]:
        p = nd["player"]
        squadra = p["serie_a_team"]
        per_id[p["id"]] = {
            # probabilità 0: nel conto è come se non ci fosse
            "player": {**p, "prob_titolare": 0},
            "rating": None, "stima": 0.0,
            "quota_portieri_squadra": quota.get(squadra) if p["role"] == "P" else None,
            "titolare_porta_fuori": p["role"] == "P" and squadra in fuori_porta,
            "fuori": p["status"] + (f" ({p['status_note']})" if p.get("status_note") else ""),
        }

    def schierati(ids, dove):
        entries = []
        for pid in ids:
            if pid is None:
                problemi.append(f"un posto {dove} è vuoto")
                continue
            e = per_id.get(pid)
            if e is None:
                p = players_by_id.get(pid)
                nome = f"{p['name']} ({p['serie_a_team']})" if p else f"il giocatore con id {pid}"
                problemi.append(f"{nome} è {dove} ma non è nella tua rosa")
                continue
            if e.get("fuori"):
                problemi.append(f"{e['player']['name']} è {dove} ma è {e['fuori']}")
            entries.append(e)
        return entries

    titolari = schierati(salvata["titolari"], "titolare")
    panchina = schierati(salvata["panchina"], "in panchina")
    miei_t, miei_p = _per_ruolo(titolari), _per_ruolo(panchina)
    cons_t, cons_p = _per_ruolo(consiglio["titolari"]), _per_ruolo(consiglio["panchina"])

    ruoli = {}
    for role in ROLES:
        mio, _ = _slot_attesi(miei_t[role] + miei_p[role], len(miei_t[role]))
        suo, _ = _slot_attesi(cons_t[role] + cons_p[role], len(cons_t[role]))
        ruoli[role] = {"salvata": mio, "consiglio": suo}
    modulo = _modulo(titolari)
    stesso_modulo = modulo == consiglio["modulo"]
    atteso = sum(r["salvata"] for r in ruoli.values())
    atteso_consiglio = sum(r["consiglio"] for r in ruoli.values())
    sotto = []
    if stesso_modulo:
        sotto = [role for role, r in ruoli.items() if r["consiglio"] - r["salvata"] > SOGLIA_PARI]
    elif atteso_consiglio - atteso > SOGLIA_PARI:
        sotto = ["modulo"]

    differenze = []
    if not stesso_modulo:
        differenze.append(f"modulo {modulo} invece di {consiglio['modulo']}")
    for role in ROLES:
        miei = {e["player"]["id"] for e in miei_t[role]}
        suoi = {e["player"]["id"] for e in cons_t[role]}
        entrati = [e for e in miei_t[role] if e["player"]["id"] not in suoi]
        usciti = [e for e in cons_t[role] if e["player"]["id"] not in miei]
        if entrati and usciti:
            differenze.append(f"[{role}] titolari: {_nomi(entrati)} al posto di {_nomi(usciti)}")
        elif entrati:
            differenze.append(f"[{role}] titolari in più: {_nomi(entrati)}")
        elif usciti:
            differenze.append(f"[{role}] titolari in meno: {_nomi(usciti)}")
        if [e["player"]["id"] for e in miei_p[role]] != [e["player"]["id"] for e in cons_p[role]]:
            differenze.append(f"[{role}] panchina in quest'ordine: {_nomi(miei_p[role]) or 'nessuno'}; "
                              f"il consiglio: {_nomi(cons_p[role]) or 'nessuno'}")

    return {
        "problemi": problemi,
        "differenze": differenze,
        "ruoli": ruoli,
        "sotto": sotto,
        "modulo": modulo,
        "atteso": atteso,
        "atteso_consiglio": atteso_consiglio,
        "da_correggere": bool(problemi or sotto),
    }


def _nomi(entries: list[dict]) -> str:
    return ", ".join(
        f"{e['player']['name']} ({_valore(e):.2f})" if _valore(e) is not None else e["player"]["name"]
        for e in entries
    )


NOMI_RUOLO = {"P": "porta", "D": "difesa", "C": "centrocampo", "A": "attacco", "modulo": "modulo"}


def _quando(dt: datetime) -> str:
    return dt.astimezone(ROMA).strftime("%d/%m alle %H:%M")


def _consiglio_testo(consiglio: dict) -> list[str]:
    """Il consiglio di oggi, da inserire sul sito così com'è."""
    t = _per_ruolo(consiglio["titolari"])
    righe = [f"  Il consiglio di oggi, modulo {consiglio['modulo']}:"]
    for role in ROLES:
        righe.append(f"    [{role}] {', '.join(e['player']['name'] for e in t[role])}")
    panchina = []
    conta = Counter()
    for e in consiglio["panchina"]:
        role = e["player"]["role"]
        conta[role] += 1
        panchina.append(f"{role}{conta[role]} {e['player']['name']}")
    righe.append(f"    Panchina in quest'ordine: {', '.join(panchina)}")
    return righe


def _data_salvataggio(ldate: str | None) -> str | None:
    """Solo il giorno: il sito scrive l'ora senza fuso (probabilmente UTC, non verificato)."""
    if not ldate or len(ldate) < 8:
        return None
    return f"{ldate[6:8]}/{ldate[4:6]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--team-id", default=None, help="squadra della lega (default: my_team_id)")
    parser.add_argument("--league-id", default=None, help="lega (default: league_id di config/league.json)")
    args = parser.parse_args()

    config = store.load_league_config()
    team_id = str(args.team_id or config["my_team_id"])
    league_id = args.league_id or config["league_id"]

    competizioni_path = store.DATA_DIR / "lega_competizioni.json"
    calendario_path = store.DATA_DIR / "calendario_serie_a.json"
    if not competizioni_path.exists() or not calendario_path.exists():
        print("FORMAZIONE NON CONTROLLATA: mancano il calendario della lega o quello di Serie A in data/.")
        return 1
    giornata, motivo = giornata_da_controllare(store.load_json(competizioni_path),
                                               store.load_json(calendario_path), team_id)
    if giornata is None:
        print(f"FORMAZIONE NESSUN AVVISO: {motivo}.")
        return 0
    turno = prossimo_turno()
    inizio = scadenza(turno)
    if inizio is None:
        # Quasi sempre è il turno in corso. Può essere anche un recupero fra le prossime
        # partite: allora il controllo tace anche vicino alla scadenza, e lo dice il report
        # ("il prossimo turno non si ricostruisce dalle date").
        print("FORMAZIONE NESSUN AVVISO: il prossimo turno di Serie A non si ricostruisce dalle "
              "date (turno in corso, un recupero o un rinvio): se la scadenza è vicina, controlla "
              "la formazione a mano sul sito.")
        return 0

    nomi = {t["id"]: t["name"] for t in store.load_teams()}
    partita = (f"giornata {giornata['giornata']} di {giornata['competizione']} (Serie A "
               f"{giornata['giornata_serie_a']}) contro {nomi.get(giornata['avversario_id'], giornata['avversario_id'])}")
    quando = _quando(inizio)

    username = os.environ.get("LEGHE_FC_USERNAME")
    password = os.environ.get("LEGHE_FC_PASSWORD")
    if not username or not password:
        print(f"FORMAZIONE NON CONTROLLATA: mancano LEGHE_FC_USERNAME e LEGHE_FC_PASSWORD. "
              f"Controlla a mano la {partita}, scadenza {quando}.")
        return 1
    try:
        app_key = client.discover_app_key()
        jwt = client.get_league_jwt(client.login(username, password, app_key), league_id)
        path = (f"/gaming/v1/teamLineup/{giornata['competizione_id']}/{giornata['giornata']}/"
                f"{giornata['giornata_serie_a']}/{giornata['id_casa']}/{giornata['id_trasferta']}")
        risposta = client.authenticated_get(path, jwt, app_key)
        if risposta.get("cal"):
            print(f"FORMAZIONE NESSUN AVVISO: la lega ha già calcolato la {partita}.")
            return 0
        salvata = formazione_salvata(risposta, giornata, team_id)
    except (client.LegheFcError, OSError, KeyError, ValueError) as e:
        print(f"FORMAZIONE NON CONTROLLATA: il sito della lega non ha risposto come previsto ({e}). "
              f"Controlla a mano la {partita}, scadenza {quando}.")
        return 1

    consiglio = suggest_lineup(team_id)
    if salvata is None:
        giorni = giorni_alla_scadenza(inizio, datetime.now(timezone.utc))
        if giorni > GIORNI_URGENZA:
            print(f"FORMAZIONE NESSUN AVVISO: la formazione per la {partita} non è ancora inserita, "
                  f"ma la scadenza ({quando}) è fra {giorni} giorni: l'avviso parte "
                  f"{GIORNI_URGENZA} giorni prima.")
            return 0
        print(f"FORMAZIONE MANCANTE: nessuna formazione per la {partita}. Scadenza {quando}: "
              f"senza formazione la lega dà lo 0-3 a tavolino.")
        if consiglio.get("modulo"):
            print("\n".join(_consiglio_testo(consiglio)))
        return 0
    if not consiglio.get("modulo"):
        print(f"FORMAZIONE NON CONTROLLATA: la formazione della {partita} c'è, ma il report non "
              f"riesce a fare un consiglio da confrontare: {' '.join(consiglio['avvisi'])}")
        return 0

    players_by_id = {p["id"]: p for p in store.load_players()}
    esito = confronta(salvata, consiglio, players_by_id, quote_portieri(players_by_id))
    giorno = _data_salvataggio(salvata["salvata"])
    inserita = f"inserita il {giorno}" if giorno else "inserita"
    if esito["da_correggere"]:
        motivi = list(esito["problemi"])
        for r in esito["sotto"]:
            if r == "modulo":
                perdita = esito["atteso_consiglio"] - esito["atteso"]
            else:
                perdita = esito["ruoli"][r]["consiglio"] - esito["ruoli"][r]["salvata"]
            motivi.append(f"{NOMI_RUOLO[r]} sotto il consiglio di {perdita:.2f} punti attesi")
        print(f"FORMAZIONE DA CORREGGERE entro il {quando}: {'; '.join(motivi)}.")
    elif esito["differenze"]:
        print(f"FORMAZIONE OK: {partita}, {inserita}. Diversa dal consiglio di oggi solo in scelte "
              f"alla pari (sotto {SOGLIA_PARI:.2f} punti per ruolo). Scadenza {quando}.")
    else:
        print(f"FORMAZIONE OK: {partita}, {inserita} e uguale al consiglio di oggi. Scadenza {quando}.")

    volte = f" (salvata {salvata['salvataggi']} volte)" if salvata["salvataggi"] else ""
    print(f"  {partita[0].upper()}{partita[1:]}, {inserita}{volte}.")
    print(f"  Punteggio atteso: {esito['atteso']:.1f} la formazione inserita, "
          f"{esito['atteso_consiglio']:.1f} il consiglio di oggi (modulo {esito['modulo']} contro {consiglio['modulo']}).")
    for d in esito["differenze"]:
        print(f"  - {d}")
    if esito["da_correggere"]:
        print("\n".join(_consiglio_testo(consiglio)))
        print("  Il perché di ogni scelta lo spiega la skill formazione (/formazione).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
