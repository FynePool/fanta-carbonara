#!/usr/bin/env python3
"""Rigoristi della Serie A: gerarchie da piu' fonti, consenso, e abbinamento col listone.

Perche' serve. Un rigore vale in media +1,9 di fantavoto (+3 se segnato, -2 se sbagliato),
e nella stagione 2025-26 ci sono stati 106 rigori in 380 partite, cioe' 0,139 per squadra
per partita. Il primo rigorista vale quindi circa **+0,26 di fantavoto atteso a partita**,
fino a +0,5 nelle squadre che ottengono piu' rigori. E' informazione che il modello non
puo' vedere: un rigorista designato che non ha ancora calciato non ha niente nei suoi voti
che lo riveli. Il secondo rigorista calcia solo se il primo non c'e': vale circa +0,03,
trascurabile.

Perche' NON e' un dato ufficiale. Le gerarchie sono valutazioni editoriali, e le tre fonti
lette il 27/09 **si contraddicono sul primo rigorista di 9 squadre su 20**. Quindi qui non
si sceglie una fonte: si tengono tutte, si calcola il consenso, e si marca `verificata`
solo dove almeno due fonti concordano sulla stessa posizione (la regola del progetto per le
informazioni qualitative, come per notizie_rosa.json).

Chi aggiorna i dati aggiunge o corregge le liste per fonte dentro `fonti` in
data/rigoristi.json (nomi come li scrive la fonte, in ordine di gerarchia), poi lancia
`calcola`: l'abbinamento col listone e il consenso li fa questo script, non a mano.

L'abbinamento rifiuta un nome quando le iniziali sono note e diverse, come fa
import_matchday_stats.py: all'Inter ci sono `Martinez L.` (Lautaro) e `Martinez Jo.` (il
portiere), e senza quel controllo "Lautaro Martinez" finiva sul portiere.

Uso:
    python3 scripts/rigoristi.py calcola    # ricalcola il consenso dalle liste e riscrive
    python3 scripts/rigoristi.py valida     # controlla senza scrivere
    python3 scripts/rigoristi.py mostra [--team-id ID]
"""
import argparse
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store

PATH = store.DATA_DIR / "rigoristi.json"
# Un rigore vale in media questo, col malus rigore sbagliato della lega e la conversione
# reale della Serie A (circa 78%): 0,78*3 + 0,22*(-2).
VALORE_RIGORE = 1.90
# Rigori per squadra a partita, dalla stagione scorsa in data/storico_stagioni.json.
# Lo ricalcola `calcola` e lo riscrive nel file: non e' un numero a mano.
RIGORI_PARTITA_DEFAULT = 0.139


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return "".join(c for c in s if c.isalnum() or c == " ").strip()


def _iniziale_listone(nome: str) -> str | None:
    """L'iniziale che il listone aggiunge per distinguere gli omonimi: 'Martinez Jo.' -> 'jo'."""
    pezzi = nome.split()
    if len(pezzi) >= 2 and pezzi[-1].endswith("."):
        return _norm(pezzi[-1].rstrip("."))
    return None


def abbina(nome_fonte: str, squadra: str, per_squadra: dict) -> tuple[dict | None, str | None]:
    """(giocatore del listone, motivo dello scarto). Cerca solo dentro la squadra indicata.

    Il listone abbrevia il nome proprio per distinguere gli omonimi ("Martinez L." e
    "Martinez Jo." all'Inter, "Adams A." e "Adams C." fra Venezia e Torino). Le fonti
    scrivono a volte solo il cognome ("Davis"), a volte nome e cognome ("Lautaro Martinez").
    Quindi: se il cognome porta a un solo giocatore e la fonte non da' un nome proprio, si
    abbina; se la fonte da' un nome proprio e il listone ha un'iniziale, le due devono
    combaciare, altrimenti si scarta invece di indovinare (difetto 7 del doc dei difetti)."""
    candidati = per_squadra.get(squadra, [])
    if not candidati:
        return None, f"nessun giocatore del listone nella squadra {squadra}"
    n = _norm(nome_fonte)
    pezzi = n.split()
    for p in candidati:                                    # nome intero uguale
        if _norm(p["name"]) == n:
            return p, None

    def cognome(p):
        return _norm(p["name"].split()[0])

    simili = [p for p in candidati if cognome(p) in pezzi and len(cognome(p)) > 3]
    simili += [p for p in candidati if p not in simili and pezzi and cognome(p) == pezzi[-1]]
    if not simili:
        return None, "cognome non trovato nella squadra"

    cognomi = {cognome(p) for p in simili}
    propri = [x for x in pezzi if x not in cognomi]        # i nomi propri dati dalla fonte

    if not propri:
        # la fonte da' solo il cognome: si abbina se non e' ambiguo
        if len(simili) == 1:
            return simili[0], None
        nomi = ", ".join(p["name"] for p in simili)
        return None, f"solo il cognome e piu' giocatori possibili ({nomi})"

    combaciano = []
    for p in simili:
        ini = _iniziale_listone(p["name"])
        if ini is None:
            combaciano.append(p)                           # niente iniziale, niente conflitto
        elif any(x.startswith(ini) for x in propri):
            combaciano.append(p)
    if len(combaciano) == 1:
        return combaciano[0], None
    if not combaciano:
        nomi = ", ".join(p["name"] for p in simili)
        return None, f"l'iniziale del listone non combacia col nome della fonte ({nomi})"
    nomi = ", ".join(p["name"] for p in combaciano)
    return None, f"omonimi ambigui ({nomi})"


def rigori_per_partita() -> float | None:
    """Rigori calciati per squadra per partita, dalla stagione piu' recente finita."""
    path = store.DATA_DIR / "storico_stagioni.json"
    if not path.exists():
        return None
    stagioni = store.load_json(path)["stagioni"]
    if not stagioni:
        return None
    ultima = stagioni[max(stagioni)]["giocatori"]
    totale = sum(d.get("rigori_calciati") or 0 for d in ultima.values())
    squadre = {d["squadra"] for d in ultima.values() if d.get("squadra")}
    if not squadre or not totale:
        return None
    return totale / len(squadre) / (2 * (len(squadre) - 1))   # partite di ogni squadra


def calcola(doc: dict, players: list[dict]) -> tuple[list[dict], list[str]]:
    per_squadra = defaultdict(list)
    for p in players:
        per_squadra[p["serie_a_team"]].append(p)

    posizioni = defaultdict(dict)
    problemi = []
    for fonte, d in sorted(doc["fonti"].items()):
        for squadra, lista in d["liste"].items():
            if squadra not in per_squadra:
                problemi.append(f"{fonte}: squadra '{squadra}' non esiste nel listone")
                continue
            for rango, nome in enumerate(lista, start=1):
                p, motivo = abbina(nome, squadra, per_squadra)
                if p is None:
                    problemi.append(f"{fonte} / {squadra} / '{nome}': {motivo}")
                    continue
                if p["role"] == "P":
                    problemi.append(
                        f"{fonte} / {squadra} / '{nome}' abbinato a {p['name']}, che e' un "
                        "PORTIERE: quasi certamente e' l'abbinamento sbagliato"
                    )
                posizioni[(squadra, p["id"])][fonte] = rango

    per_id = {p["id"]: p for p in players}
    fonti_per_squadra = {
        sq: sum(1 for d in doc["fonti"].values() if sq in d["liste"]) for sq in per_squadra
    }
    out = []
    for (squadra, pid), per_fonte in posizioni.items():
        p = per_id[pid]
        ranghi = sorted(per_fonte.values())
        consenso = ranghi[len(ranghi) // 2]              # mediana dei ranghi
        primo = sum(1 for r in per_fonte.values() if r == 1)
        out.append({
            "player_id": pid,
            "nome": p["name"],
            "squadra": squadra,
            "ruolo": p["role"],
            "rango": consenso,
            "rango_per_fonte": dict(sorted(per_fonte.items())),
            "fonti_che_lo_citano": len(per_fonte),
            "fonti_totali_sulla_squadra": fonti_per_squadra[squadra],
            # verificata = almeno due fonti indipendenti nella STESSA posizione
            "verificata": len(per_fonte) >= 2 and len(set(per_fonte.values())) == 1,
            # quante fonti lo danno PRIMO: e' il numero che conta, piu' informativo di un
            # si/no, perche' "3 fonti lo citano ma 2 lo danno primo" e' un caso normale
            "fonti_che_lo_danno_primo": primo,
            # e' questo che conta per il valore: il primo rigorista
            "consenso_sul_primo": primo >= 2,
        })
    out.sort(key=lambda x: (x["squadra"], x["rango"], x["nome"]))
    return out, problemi


def carica() -> dict:
    return store.load_json(PATH)


def primi_rigoristi() -> dict:
    """player_id -> voce, solo per chi ha il consenso di essere il PRIMO rigorista. E' quello
    che leggono roster.py e il report: il secondo rigorista vale troppo poco."""
    if not PATH.exists():
        return {}
    doc = carica()
    return {r["player_id"]: r for r in doc["rigoristi"] if r.get("consenso_sul_primo")}


def per_player_id() -> dict:
    if not PATH.exists():
        return {}
    return {r["player_id"]: r for r in carica()["rigoristi"]}


def valore_atteso(squadra: str | None = None) -> float:
    """Quanto vale essere il primo rigorista, in fantavoto atteso a partita."""
    doc = carica() if PATH.exists() else {}
    return doc.get("rigori_per_partita", RIGORI_PARTITA_DEFAULT) * VALORE_RIGORE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("comando", choices=["calcola", "valida", "mostra"])
    parser.add_argument("--team-id", default=None, help="mostra: solo i giocatori di questa squadra della lega")
    args = parser.parse_args()

    if not PATH.exists():
        print(f"{PATH} non esiste.")
        return 1
    doc = carica()
    players = store.load_players()

    if args.comando == "mostra":
        own = None
        if args.team_id:
            own = {o["player_id"] for o in store.load_ownership() if o["team_id"] == args.team_id}
        for r in doc["rigoristi"]:
            if own is not None and r["player_id"] not in own:
                continue
            stato = "verificata" if r["verificata"] else "fonti discordi"
            primo = "  <== PRIMO RIGORISTA" if r["consenso_sul_primo"] else ""
            print(f"  {r['ruolo']} {r['nome']:<18} {r['squadra']:<12} rango {r['rango']} "
                  f"({r['fonti_che_lo_citano']}/{r['fonti_totali_sulla_squadra']} fonti, {stato})"
                  f"{primo}")
        return 0

    nuovi, problemi = calcola(doc, players)
    print(f"{len(nuovi)} rigoristi da {len(doc['fonti'])} fonti su "
          f"{len({r['squadra'] for r in nuovi})} squadre.")
    primi = [r for r in nuovi if r["consenso_sul_primo"]]
    print(f"Con consenso sul primo rigorista: {len(primi)} squadre su "
          f"{len({r['squadra'] for r in nuovi})}. Le altre hanno le fonti discordi.")
    if problemi:
        print(f"\nDA GUARDARE ({len(problemi)}):")
        for x in problemi:
            print(f"  - {x}")
    rpp = rigori_per_partita()
    if rpp:
        print(f"\nRigori per squadra a partita (stagione scorsa): {rpp:.3f} "
              f"-> il primo rigorista vale +{rpp * VALORE_RIGORE:.2f} di fantavoto atteso.")

    if args.comando == "valida":
        cambiati = [r for r, v in zip(nuovi, doc["rigoristi"]) if r != v] if len(nuovi) == len(doc["rigoristi"]) else nuovi
        if len(nuovi) != len(doc["rigoristi"]) or cambiati:
            print(f"\nIl consenso salvato NON e' aggiornato: lancia `calcola`.")
            return 1
        print("\nIl consenso salvato e' aggiornato.")
        return 0

    doc["rigoristi"] = nuovi
    if rpp:
        doc["rigori_per_partita"] = round(rpp, 4)
    doc["valore_primo_rigorista"] = round((rpp or RIGORI_PARTITA_DEFAULT) * VALORE_RIGORE, 3)
    store.save_json(PATH, doc)
    print(f"\nScritto {PATH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
