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

Come si mettono alla prova le liste. Un rigore calciato NON dice "questo e' il primo
rigorista": dice che, in quel momento, chi le fonti gli mettono sopra non era in campo, o
che le fonti sbagliano. Il 27/09 il progetto contava "3 rigori su 5 smentiscono le liste",
ed era falso: in tutti e tre i casi il primo designato non era in campo (Pessina non ha
ancora giocato, Mina era in panchina, Busio infortunato). Quindi ogni rigore si valuta
guardando chi stava sopra al rigorista e dov'era (`valuta_rigori`):
  primo      l'ha calciato il primo delle fonti;
  coerente   chi gli sta sopra non era in campo in quel momento: conferma l'ordine, non che
             sia il primo (e' un sostituto);
  smentisce  qualcuno che le fonti gli mettono sopra era in campo per tutto il tempo in cui
             c'era lui;
  incerto    qualcuno sopra di lui era in campo solo per una parte (dipende dal minuto), o
             i minuti di uno dei due non si sanno: minuti ignoti non vuol dire assente.
I minuti in campo vengono dal box score (una partita di T minuti, T il massimo giocato:
titolare da 0 ai suoi minuti, subentrato da T meno i suoi minuti a T). Un "incerto" si
risolve cercando il minuto del rigore e scrivendolo in `minuti_rigori` con due fonti.

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


def rigori_ufficiali_stagione() -> tuple[dict, str | None]:
    """(player_id -> {segnati, calciati} in QUESTA stagione, etichetta della stagione).

    E' il solo dato **ufficiale** su chi calcia i rigori adesso, da fantacalcio.it
    (`stagione_in_corso` in storico_stagioni.json, scritto da
    `import_storico_stagioni.py --corrente`). Un rigorista dell'anno scorso puo' non
    esserlo piu': ha cambiato squadra, o sono cambiati i compagni.

    ATTENZIONE a cosa NON dice. Nelle prime 5 giornate del 2026-27 ci sono stati **5
    rigori in tutto il campionato**. Con circa 0,14 rigori per squadra a partita, dopo 5
    giornate una squadra ne ha avuti in media 0,7: quindi la quasi totalita' dei rigoristi
    designati ne ha calciati **zero**. Questo dato **conferma** un rigorista, non lo
    **esclude**: zero rigori non e' una smentita, e' assenza di occasioni."""
    path = store.DATA_DIR / "storico_stagioni.json"
    if not path.exists():
        return {}, None
    corrente = store.load_json(path).get("stagione_in_corso")
    if not corrente:
        return {}, None
    return (
        {
            pid: {"segnati": d["rigori_segnati"], "calciati": d["rigori_calciati"]}
            for pid, d in corrente["giocatori"].items()
            if d.get("rigori_calciati")
        },
        corrente.get("stagione"),
    )


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


IGNOTA = "ignota"


def _finestra(riga: dict | None, fine: int):
    """(da, a) minuti in campo nella partita, dal box score; None se non ha giocato (nessuna
    riga, o 0 minuti); IGNOTA se la riga c'è ma i minuti no (giocatore che BigBalls non ha:
    42 righe con voto e senza minuti il 29/09). Minuti ignoti e assenza non sono la stessa
    cosa: chi ha un voto ha giocato."""
    if riga is None:
        return None
    minuti = riga.get("minuti")
    if minuti is None:
        return IGNOTA
    if minuti <= 0:
        return None
    if riga.get("subentrato") is None:     # quanti minuti si sa, quando no
        return (0, minuti) if minuti >= 90 else IGNOTA
    return (fine - minuti, fine) if riga["subentrato"] else (0, minuti)


def valuta_rigori(voci: list[dict], righe: list[dict], per_id: dict,
                  minuti_rigori: list[dict]) -> tuple[dict, list[dict]]:
    """(player_id -> rigori valutati, elenco di tutti i rigori valutati). Per ogni rigore
    calciato quest'anno (box score BigBalls, che li ha tutti, verificato contro
    fantacalcio.it il 27/09) guarda chi le fonti mettono sopra al rigorista e se era in
    campo mentre c'era lui. Vedi il docstring del modulo per gli esiti."""
    per_squadra = defaultdict(list)
    for v in voci:
        per_squadra[v["squadra"]].append(v)
    per_partita = defaultdict(dict)
    for r in righe:
        per_partita[r["match_id"]][r["player_id"]] = r
    finestre_note = {(m["match_id"], m["player_id"]): tuple(m["finestra"]) for m in minuti_rigori}

    per_giocatore, tutti = defaultdict(list), []
    for r in sorted(righe, key=lambda r: (r.get("matchday") or 0, r["match_id"], r["player_id"])):
        calciati = (r.get("rigori_segnati") or 0) + (r.get("rigori_sbagliati") or 0)
        if not calciati or r["player_id"] not in per_id:
            continue
        pid = r["player_id"]
        voce = next((v for v in voci if v["player_id"] == pid), None)
        squadra = voce["squadra"] if voce else per_id[pid]["serie_a_team"]
        rango = voce["rango"] if voce else None
        partita = per_partita[r["match_id"]]
        fine = max(90, max((x.get("minuti") or 0) for x in partita.values()))
        sua = _finestra(r, fine)
        if sua is None:    # ha calciato, quindi ha giocato: i minuti del box score sono sbagliati
            sua = IGNOTA
        nota = finestre_note.get((r["match_id"], pid))
        if nota:           # minuto del rigore verificato a mano con le fonti
            sua = tuple(nota) if sua == IGNOTA else (max(sua[0], nota[0]), min(sua[1], nota[1]))
        sopra = []
        for v in sorted(per_squadra.get(squadra, []), key=lambda v: v["rango"] or 99):
            if v["player_id"] == pid or (rango is not None and (v["rango"] is None or v["rango"] >= rango)):
                continue
            riga_v = partita.get(v["player_id"])
            sue = _finestra(riga_v, fine)
            if sue is None:
                dove = "assente"
            elif sue == IGNOTA or sua == IGNOTA:
                dove = "minuti sconosciuti"
            else:
                comune = min(sua[1], sue[1]) - max(sua[0], sue[0])
                if comune <= 0:
                    dove = "non in campo in quel momento"
                elif sue[0] <= sua[0] and sue[1] >= sua[1]:
                    dove = "in campo"
                else:
                    dove = "in campo per una parte"
            sopra.append({"player_id": v["player_id"], "nome": v["nome"], "rango": v["rango"],
                          "dove": dove, "minuti": (riga_v or {}).get("minuti")})
        if rango == 1:
            esito = "primo"
        elif any(x["dove"] == "in campo" for x in sopra):
            esito = "smentisce"
        elif any(x["dove"] in ("in campo per una parte", "minuti sconosciuti") for x in sopra):
            esito = "incerto"
        else:
            esito = "coerente"
        valutato = {
            "giornata": r.get("matchday"),
            "match_id": r["match_id"],
            "player_id": pid,
            "nome": per_id[pid]["name"],
            "squadra": squadra,
            "rango": rango,
            "calciati": calciati,
            "esito": esito,
            "minuto_verificato": bool(nota),
            "sopra": sopra,
        }
        per_giocatore[pid].append(valutato)
        tutti.append(valutato)
    return per_giocatore, tutti


def _conferma(valutati: list[dict]) -> str:
    esiti = {v["esito"] for v in valutati}
    for esito, conferma in (("primo", "confermato"), ("smentisce", "smentisce"),
                            ("incerto", "incerto"), ("coerente", "sostituto")):
        if esito in esiti:
            return conferma
    return "supposizione"


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

    ufficiali, stagione_corrente = rigori_ufficiali_stagione()
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
            # il solo dato ufficiale: quanti rigori ha calciato DAVVERO quest'anno
            "rigori_stagione": ufficiali.get(pid, {"segnati": 0, "calciati": 0}),
            # riempito sotto da valuta_rigori
            "conferma": "supposizione",
        })
    # Chi ha calciato un rigore quest'anno ma nessuna fonte lo cita: e' il caso piu'
    # importante di tutti, perche' il dato ufficiale batte l'opinione.
    citati = {pid for (_sq, pid) in posizioni}
    for pid, r in ufficiali.items():
        if pid in citati or pid not in per_id:
            continue
        p = per_id[pid]
        out.append({
            "player_id": pid,
            "nome": p["name"],
            "squadra": p["serie_a_team"],
            "ruolo": p["role"],
            "rango": None,
            "rango_per_fonte": {},
            "fonti_che_lo_citano": 0,
            "fonti_totali_sulla_squadra": fonti_per_squadra.get(p["serie_a_team"], 0),
            "fonti_che_lo_danno_primo": 0,
            "verificata": False,
            "consenso_sul_primo": False,
            "rigori_stagione": r,
            "conferma": "supposizione",
        })
        problemi.append(
            f"{p['name']} ({p['serie_a_team']}) ha calciato {r['calciati']} rigori in "
            f"{stagione_corrente} ma NESSUNA fonte lo mette in gerarchia: il dato ufficiale "
            "batte l'opinione, guarda se le liste sono vecchie"
        )
    # Ogni rigore calciato messo alla prova contro le liste: chi stava sopra al rigorista
    # era in campo? "conferma" dice cosa prova quel rigore su di lui, "scavalcato_da" dice
    # chi ha calciato al posto suo mentre lui era in campo.
    per_rigore, tutti = valuta_rigori(out, store.load_matchday_stats(), per_id, doc.get("minuti_rigori", []))
    for r in out:
        r["conferma"] = _conferma(per_rigore.get(r["player_id"], []))
        r["scavalcato_da"] = [
            {"nome": v["nome"], "giornata": v["giornata"], "dove": x["dove"]}
            for v in tutti for x in v["sopra"]
            if x["player_id"] == r["player_id"] and x["dove"] in ("in campo", "in campo per una parte")
        ]
    for v in tutti:
        if v["esito"] in ("smentisce", "incerto"):
            chi = ", ".join(f"{x['nome']} ({x['rango']}º, {x['dove']}"
                            + (f", {x['minuti']}')" if x["minuti"] is not None else ")")
                            for x in v["sopra"] if x["dove"] in ("in campo", "in campo per una parte",
                                                                 "minuti sconosciuti"))
            problemi.append(
                f"{v['nome']} ({v['squadra']}, {v['rango'] or 'fuori lista'}º per le fonti) ha "
                f"calciato alla giornata {v['giornata']} con {chi}: "
                + ("le liste sono smentite, da rileggere" if v["esito"] == "smentisce" else
                   "incerto: cerca il minuto del rigore e chi era in campo, e scrivilo in "
                   "minuti_rigori con le fonti")
            )
    ufficiali_tot = sum(x["calciati"] for x in ufficiali.values())
    visti = sum(v["calciati"] for v in tutti)
    if visti != ufficiali_tot:
        problemi.append(f"rigori nel box score {visti}, nel dato ufficiale {ufficiali_tot}: "
                        "qualche rigore non si puo' mettere alla prova")
    out.sort(key=lambda x: (x["squadra"], x["rango"] if x["rango"] is not None else 99, x["nome"]))
    return out, problemi


def verifica_gerarchie(voci: list[dict]) -> dict:
    """Quante volte i rigori veri hanno confermato o smentito le liste, per esito. Conta i
    rigoristi, non i rigori: chi ne ha calciati due conta una volta, col suo esito."""
    conta = Counter(v["conferma"] for v in voci if v["conferma"] != "supposizione")
    return {k: conta.get(k, 0) for k in ("confermato", "sostituto", "incerto", "smentisce")}


def testo_verifica(v: dict) -> str:
    """Una frase sui rigoristi che hanno calciato: la usano rigoristi.py e il report."""
    totale = sum(v.values())
    if not totale:
        return "nessun rigore calciato finora."
    return (f"{totale} rigoristi hanno calciato: {v['confermato']} erano il primo delle fonti, "
            f"{v['sostituto']} hanno calciato con chi gli sta sopra fuori dal campo (l'ordine "
            f"regge), {v['incerto']} incerti (dipende dal minuto), {v['smentisce']} hanno "
            "calciato con in campo qualcuno che le fonti mettevano sopra.")


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
    ufficiali, stagione_corrente = rigori_ufficiali_stagione()
    print(f"\nDato UFFICIALE {stagione_corrente or '(assente)'}: "
          f"{sum(v['calciati'] for v in ufficiali.values())} rigori calciati in tutto il "
          f"campionato, da {len(ufficiali)} giocatori.")
    verifica = verifica_gerarchie(nuovi)
    print("Le liste messe alla prova dai rigori veri: " + testo_verifica(verifica))
    for r in nuovi:
        if r["conferma"] != "supposizione":
            print(f"  {r['conferma']:<11} {r['nome']} ({r['squadra']}, {r['rango'] or '-'}º per le fonti) "
                  f"{r['rigori_stagione']['segnati']}/{r['rigori_stagione']['calciati']}")
    print("  Tutti gli altri sono SUPPOSIZIONI (pareri di giornali). Zero rigori non smentisce")
    print("  nessuno: con circa 0,14 rigori per squadra a partita, dopo 5 giornate la quasi")
    print("  totalita' dei rigoristi designati non ne ha ancora calciato uno.")
    rpp = rigori_per_partita()
    if rpp:
        print(f"\nRigori per squadra a partita (stagione scorsa, 380 partite): {rpp:.3f} "
              f"-> il primo rigorista vale +{rpp * VALORE_RIGORE:.2f} di fantavoto atteso.")

    if args.comando == "valida":
        cambiati = [r for r, v in zip(nuovi, doc["rigoristi"]) if r != v] if len(nuovi) == len(doc["rigoristi"]) else nuovi
        if len(nuovi) != len(doc["rigoristi"]) or cambiati or doc.get("verifica_gerarchie") != verifica:
            print(f"\nIl consenso salvato NON e' aggiornato: lancia `calcola`.")
            return 1
        print("\nIl consenso salvato e' aggiornato.")
        return 0

    doc["rigoristi"] = nuovi
    doc["verifica_gerarchie"] = verifica_gerarchie(nuovi)
    if rpp:
        doc["rigori_per_partita"] = round(rpp, 4)
    doc["valore_primo_rigorista"] = round((rpp or RIGORI_PARTITA_DEFAULT) * VALORE_RIGORE, 3)
    store.save_json(PATH, doc)
    print(f"\nScritto {PATH}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
