#!/usr/bin/env python3
"""Suggerisce la formazione per una giornata, a partire dai dati in data/.

Uso:
    python3 scripts/report_formazione.py --team-id t01 [--matchday 5]

I dati di stato giocatore (titolare/dubbio/infortunato/...) in data/players.json
vanno aggiornati prima del lancio (skill aggiorna-dati o aggiorna-formazioni).
"""
import argparse
import sys
from datetime import datetime
from statistics import NormalDist
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import store
from lib.roster import (PRODUZIONE_PREDEFINITA, SOGLIA_PARI, prossima_partita_lega,
                        scavalcato_di_recente, suggest_lineup)
from lib.simulazione import scarti_formazione
from rigoristi import testo_verifica


def _voti(rating: dict | None) -> str:
    """Il valore e i suoi tre pezzi, in colonna: voti (media frenata), produzione, contesto."""
    if rating is None:
        return "  -    senza voti"
    if rating.get("politico"):
        return " 6.00  6 politico (rinvio)"
    prod = rating["produzione"]
    ctx = rating["contesto"]
    pezzi = [f"voti {rating['base'] - (prod['effetto'] if prod else 0):.2f}"]
    # La colonna `prod` si stampa solo se la correzione per la produzione è accesa:
    # spenta, scrivere "prod n/d" farebbe credere che manchi un dato (vedi
    # PRODUZIONE_PREDEFINITA in lib/roster.py).
    if PRODUZIONE_PREDEFINITA:
        if prod:
            pezzi.append(f"prod {prod['effetto']:+.2f}")
        else:
            pezzi.append("prod     -" if rating.get("portiere") else "prod   n/d")
    pezzi.append(f"avv {ctx['effetto']:+.2f}" if ctx else "avv   n/d")
    return f"{rating['punteggio']:5.2f}  {'  '.join(pezzi)}"


def _dettaglio(e: dict) -> str:
    """Da cosa è fatto il valore, in parole: una riga per giocatore."""
    p, r = e["player"], e["rating"]
    if r is None and e.get("riserva_di"):
        return (f"[{p['role']}] {p['name']}: nessun voto perché finora in porta è andato "
                f"{e['riserva_di']}, della stessa squadra. Ne gioca uno solo dei due: {p['name']} "
                f"entra solo se {e['riserva_di']} non gioca, e invertirli non cambierebbe quasi mai "
                "il punteggio (solo se prendessero voto tutti e due, con un cambio del portiere a "
                "partita in corso). Non è un giudizio su di lui e non c'è niente da decidere: "
                "conta averli in distinta tutti e due.")
    if r is None:
        return (f"[{p['role']}] {p['name']}: nessun voto, quindi il modello non sa quanto vale. "
                "Non vuol dire che valga poco, né che valga di più di chi ha una media bassa. "
                "Decidi con le notizie.")
    if r.get("politico"):
        return f"[{p['role']}] {p['name']}: partita rinviata, 6 politico."
    n = r["n"]
    parti = [
        f"media {r['media']:.2f} su {n} vot{'o' if n == 1 else 'i'} "
        f"({r['titolare']} da titolare, {r['da_subentrato']} da subentrato"
        + (f", {n - r['titolare'] - r['da_subentrato']} senza dato" if n - r["titolare"] - r["da_subentrato"] else "")
        + f"), frenata verso {r['riferimento']:.2f} del ruolo"
    ]
    prod = r["produzione"]
    if prod and prod["voti_con_tiri"]:
        parti.append(
            f"{prod['gol_azione']} gol su azione contro {prod['gol_attesi']:.1f} attesi da "
            f"{prod['tiri_porta']} tiri in porta su {prod['tiri']} ({prod['effetto']:+.2f})"
        )
    elif p["role"] != "P" and PRODUZIONE_PREDEFINITA:
        parti.append("tiri non disponibili (BigBalls non ha il giocatore): produzione non conteggiata")
    ctx = r["contesto"]
    if ctx:
        parti.append(f"{ctx['avversario']} subisce {ctx['subiti']:.1f} gol a partita ({ctx['effetto']:+.2f})")
    return f"[{p['role']}] {p['name']} {r['punteggio']:.2f}: " + "; ".join(parti) + "."


ROMA = ZoneInfo("Europe/Rome")


def _stagione(d: dict | None) -> str:
    if not d or not d["partite_con_voto"]:
        return "non ha giocato in Serie A"
    testo = f"{d['squadra']} {d['partite_con_voto']} voti, fantamedia {d['fantamedia']:.2f}"
    if d["ruolo"] == "P":
        testo += f", {d['gol_subiti']} gol subiti"
    else:
        testo += f", {d['gol']} gol, {d['assist']} assist"
    if d["rigori_calciati"]:
        testo += f", rigori {d['rigori_segnati']} su {d['rigori_calciati']}"
    return testo


def _storico() -> dict:
    """Stagioni passate da data/storico_stagioni.json (import_storico_stagioni.py), dalla
    più recente. Solo contesto: non entra nel valore (il backtest non lo sostiene ancora)."""
    path = store.DATA_DIR / "storico_stagioni.json"
    return store.load_json(path)["stagioni"] if path.exists() else {}


def _quando(data_utc: str) -> str:
    return datetime.fromisoformat(data_utc.replace("Z", "+00:00")).astimezone(ROMA).strftime("%d/%m")


def _scadenza(turno: dict) -> str | None:
    """La formazione va inserita prima dell'inizio della partita che apre la giornata:
    la prima non rinviata del turno. Solo se il turno si ricostruisce dalle date."""
    giocate = [m for m in turno["partite"] if m["stato"] != "postponed"]
    if not turno["chiaro"] or not giocate:
        return None
    inizio = datetime.fromisoformat(giocate[0]["data_utc"].replace("Z", "+00:00")).astimezone(ROMA)
    return (
        f"Scadenza formazione: {inizio.strftime('%d/%m alle %H:%M')} (ora italiana), inizio di "
        f"{giocate[0]['squadra_casa']}-{giocate[0]['squadra_trasferta']}"
    )


def _partita(e: dict) -> str:
    """Prossima partita della squadra del giocatore, dal calendario: avversario, casa/trasferta, data."""
    m = e.get("partita")
    if not m:
        return "prossima partita: n/d"
    squadra = e["player"]["serie_a_team"]
    casa = m["squadra_casa"] == squadra
    avversario = m["squadra_trasferta"] if casa else m["squadra_casa"]
    rinviata = " RINVIATA" if m["stato"] == "postponed" else ""
    return f"vs {avversario} ({'C' if casa else 'T'}) {_quando(m['data_utc'])}{rinviata}"


def _rig(e: dict) -> str:
    """Marcatore compatto. `RIG!` = ha calciato quest'anno da primo delle fonti (dato
    ufficiale); `rig?` = primo per le fonti, o primo disponibile perché chi gli sta davanti è
    fuori, ma non ancora visto calciare. Chi ha calciato solo perché il primo mancava, o è
    stato scavalcato mentre era in campo dopo il suo ultimo rigore, non si marca: conta il
    fatto più recente. Il secondo rigorista vale +0,03."""
    v = e.get("rigorista")
    if not v:
        return "     "
    if scavalcato_di_recente(v):
        return "     "
    if v.get("conferma") == "confermato":
        return " RIG!"
    return " rig?" if v.get("consenso_sul_primo") or e.get("erede_rigorista") else "     "


def _titolarita(p: dict) -> str:
    prob = p.get("prob_titolare")
    if prob is not None:
        return f"{p['status']} {prob}%"
    return p["status"]


def _gol(r: dict, soglie: dict, inc: dict | None) -> None:
    """Il punteggio atteso non è un punteggio già fatto: quello vero si allontana di parecchi
    punti. Si stampa uno SCENARIO di 0, 1, 2, 3+ gol e quanto vale un punto in più. Con
    un'incertezza più larga di una fascia, un punto vale circa lo stesso numero di gol
    ovunque: non esiste un "sul filo" in cui ogni decimale conta.

    La larghezza viene da `scarti_formazione` (lib/simulazione.py): quanto i punti veri di
    una formazione intera, con sostituzioni e slot scoperti, si sono allontanati dal punteggio
    atteso nelle giornate passate. Non dal singolo giocatore moltiplicato per la radice di
    11, che il 29/09 dava ±5,3 invece di ±6,9. Ma è misurata con la probabilità di voto
    stimata dallo storico, non con quella del sito che usa questo report: cambiando
    stimatore possono cambiare sia il centro sia la larghezza, e nessuno dei due è
    verificato qui. Per questo le percentuali si arrotondano a 5 punti: più precisione di
    così i dati non la danno. Si verificano davvero dalla giornata 6, con le probabili
    salvate alla scadenza (data/status_scadenze.json)."""
    if not soglie.get("primo_gol"):
        return
    primo, fascia = float(soglie["primo_gol"]), float(soglie["fascia"])
    print(f"  Soglie della lega: primo gol a {primo:.0f}, poi uno ogni {fascia:.0f}.")
    if not inc:
        print("  Quanto è incerto questo numero non si può ancora misurare (servono giornate")
        print("  giocate): non leggere i gol dal totale atteso.")
        return
    sd = inc["sd"]
    dist = NormalDist(r["atteso"], sd)
    almeno = [1.0] + [1 - dist.cdf(primo + k * fascia) for k in range(12)]
    prob = [almeno[k] - almeno[k + 1] for k in range(3)] + [almeno[3]]
    per_punto = sum(dist.pdf(primo + k * fascia) for k in range(12))
    def circa(p):   # a 5 punti percentuali: più precisione di così i dati non la danno
        return f"{5 * round(p * 20):.0f}%"

    print(f"  Il punteggio vero di una formazione si è allontanato da quello atteso di circa {sd:.0f}")
    print(f"  punti (deviazione standard su {inc['n']} formazioni della lega rigiocate, giornate "
          f"{inc['giornate'][0]}-{inc['giornate'][-1]}). Quindi i")
    print("  gol sono uno SCENARIO APPROSSIMATIVO, arrotondato a 5 punti, non probabilità verificate:")
    print("    " + "   ".join(f"{k} gol {circa(p)}" for k, p in enumerate(prob[:3])) + f"   3 o più {circa(prob[3])}")
    print(f"  Con queste ipotesi un punto di valore atteso vale circa {per_punto:.2f} gol, vicino o lontano")
    print(f"  da una soglia: una scelta da 0.10 punti sposta {0.1 * per_punto:.2f} gol. Le decisioni si pesano")
    print("  in punti, non guardando quanto manca alla soglia. Né la larghezza né il centro sono")
    print("  verificati per questo report: sono misurati con una probabilità di voto diversa da quella")
    print(f"  del sito usata qui (e con quella il punteggio atteso ha sbagliato in media di {inc['media']:+.1f}")
    print("  punti). Si verificano dalla giornata 6, con le probabili salvate alla scadenza.")
    if soglie.get("da_confermare"):
        print("  ATTENZIONE: le soglie gol non sono confermate dalla lega, sono i valori")
        print("  standard di fantacalcio.it. Da verificare nel pannello della lega.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--matchday", type=int, default=None,
                        help="solo l'etichetta del titolo: il report calcola sempre il prossimo "
                             "turno dal calendario")
    args = parser.parse_args()

    config = store.load_league_config()
    regole = config.get("regole_lega", {})
    panchina_cfg = {k: v for k, v in (regole.get("panchina") or {}).items() if k in "PDCA"}
    if panchina_cfg:
        composizione = ", ".join(f"{n} {role}" for role, n in panchina_cfg.items())
        cambi = f"panchina di {sum(panchina_cfg.values())} ({composizione}), cambi solo tra pari ruolo"
    elif regole.get("sostituzioni_max") is None:
        cambi = "cambi illimitati nello stesso ruolo"
    else:
        cambi = f"massimo {regole.get('sostituzioni_max')} cambi"
    r = suggest_lineup(args.team_id)

    matchday_label = f"Giornata {args.matchday}" if args.matchday else "Prossima giornata"
    print(f"{matchday_label} — modalità {config['mode']}, {cambi}")
    lega = prossima_partita_lega(args.team_id)
    if args.matchday and lega and args.matchday != lega["giornata_serie_a"]:
        print(f"ATTENZIONE: hai chiesto la giornata {args.matchday}, ma il report calcola sempre il "
              f"prossimo turno dal calendario, cioè la giornata {lega['giornata_serie_a']} di Serie A "
              "per la lega. --matchday cambia solo questo titolo.")
    turno = r["turno"]
    if turno["partite"] and turno["chiaro"]:
        print(
            f"Prossimo turno dal calendario: {_quando(turno['partite'][0]['data_utc'])} - "
            f"{_quando(turno['partite'][-1]['data_utc'])} ({len(turno['partite'])} partite)"
        )
    scadenza = _scadenza(turno)
    if scadenza:
        print(scadenza)

    if r["modulo"]:
        print(f"Modulo consigliato: {r['modulo']}")
        print("Il numero è il fantavoto atteso se il giocatore prende voto, e ordina ogni ruolo:")
        print("  voti = media degli ultimi 5 voti, avvicinata alla media del ruolo se sono pochi;")
        if PRODUZIONE_PREDEFINITA:
            print("  prod = correzione dei gol su azione con quelli attesi dai tiri in porta;")
        print("  avv  = quanto subisce l'avversario rispetto alla media del campionato.")
        print("La probabilità di giocare NON entra nel numero: se un titolare non prende voto")
        print("entra il primo della panchina del suo ruolo, quindi conviene sempre mettere")
        print("avanti il più forte. Entra invece nella scelta di CHI va in panchina, perché i")
        print("posti sono pochi e uno slot scoperto vale 0. Il modulo si sceglie sulla somma")
        print("dei valori dei titolari (col valore atteso è stato provato e non ha mostrato guadagni).\n")
        panchina_per_ruolo = {}
        for e in r["panchina"]:
            panchina_per_ruolo.setdefault(e["player"]["role"], []).append(e["player"]["name"])
        print("TITOLARI:")
        for e in r["titolari"]:
            p = e["player"]
            riga = f"  [{p['role']}] {p['name']:<18} {_voti(e['rating']):<39}{_rig(e)} {_titolarita(p):<17} {_partita(e)}"
            prob = p.get("prob_titolare")
            politico = e["rating"] and e["rating"].get("politico")
            if prob is not None and prob < 75 and not politico and panchina_per_ruolo.get(p["role"]):
                riga += f"   <- se non gioca entra {panchina_per_ruolo[p['role']][0]}"
            print(riga)
    else:
        print("Nessuna formazione consigliata.")

    if r["modulo"]:
        totale = sum(r["panchina_cfg"].values()) if r["panchina_cfg"] else len(r["panchina"])
        print(f"\nPANCHINA — {len(r['panchina'])} di {totale} posti "
              "(per ogni titolare senza voto entra il primo del suo ruolo;")
        print("se le riserve di quel ruolo finiscono, lo slot vale 0):")
    elif r["panchina"]:
        print("\nROSA PER RUOLO:")
    contatori = {}
    for e in r["panchina"]:
        p = e["player"]
        contatori[p["role"]] = contatori.get(p["role"], 0) + 1
        etichetta = f"{p['role']}{contatori[p['role']]}"
        print(f"  {etichetta:<3} {p['name']:<18} {_voti(e['rating']):<39}{_rig(e)} {_titolarita(p):<17} {_partita(e)}")

    if r["modulo"] and r["esclusi"]:
        print("\nFUORI DISTINTA (la panchina ha pochi posti per ruolo: questi non entrano):")
        for e in r["esclusi"]:
            p = e["player"]
            print(f"  [{p['role']}] {p['name']:<18} {_voti(e['rating']):<30} {_titolarita(p):<17} {_partita(e)}")

    if r["modulo"] and r["copertura"]:
        print("\nRISCHIO SLOT VUOTO per ruolo (probabilità che tutti gli slot siano coperti). È una")
        print("STIMA, non ancora verificata: usa la probabilità di partire titolare del sito, che non")
        print("conta chi entra a partita in corso e non è ancora stata confrontata con chi ha preso")
        print("voto davvero. Per i portieri della stessa squadra la quota è rapportata ai portieri")
        print("disponibili di quella squadra: ne gioca quasi sempre uno solo.")
        piu_esposto = min(r["copertura"].values())
        for role, coperto in sorted(r["copertura"].items(), key=lambda x: x[1]):
            print(f"  {role}: coperto al {coperto:6.1%}   rischio {1 - coperto:.1%}"
                  + ("  <- il più esposto" if coperto == piu_esposto else ""))

    if r["modulo"] and r["atteso"] is not None:
        print(f"\nPUNTEGGIO ATTESO: {r['atteso']:.1f} punti (somma degli 11 slot, già scontata per")
        print("chi rischia di non prendere voto e per gli slot che possono restare vuoti).")
        if r["stimati"]:
            stime = ", ".join(f"{e['player']['name']} {e['stima']:.2f}" for e in r["stimati"])
            print(f"  Chi non ha voti è contato con la media del suo ruolo, una stima e non un dato: {stime}.")
        _gol(r, regole.get("soglie_gol") or {}, scarti_formazione())

    in_rosa = [e for e in r["titolari"] + r["panchina"] + r["esclusi"] if e.get("rigorista")]
    if in_rosa:
        valore = r["valore_rigorista"]
        verifica = (r.get("prova_rigoristi") or {}).get("verifica")
        print(f"\nRIGORISTI IN ROSA. Il primo rigorista vale circa +{valore:.2f} di fantavoto "
              "atteso a")
        print("partita; il secondo +0,03, cioè niente. NON è dentro il numero: le gerarchie sono")
        print("pareri di giornali che si contraddicono fra loro, e i rigori veri per metterle alla")
        print("prova sono ancora pochi. Serve come spareggio fra due giocatori equivalenti.")
        if verifica:
            print(f"  Finora {testo_verifica(verifica)}")
        print("  RIG! = ha calciato quest'anno da primo delle fonti (dato ufficiale di fantacalcio.it)")
        print("  rig? = primo per le fonti (o primo disponibile, se chi gli sta davanti è fuori), non")
        print("         ancora visto calciare. Zero rigori NON lo smentisce: dopo 5 giornate quasi")
        print("         nessun rigorista designato ne ha avuto uno da tirare.")

        def ordine(x):
            v = x["rigorista"]
            return (0 if _rig(x) == " RIG!" else 1 if _rig(x) == " rig?" else 2,
                    v["rango"] or 99, x["player"]["name"])

        for e in sorted(in_rosa, key=ordine):
            v, p = e["rigorista"], e["player"]
            tot = v["fonti_totali_sulla_squadra"]
            primo = v.get("fonti_che_lo_danno_primo", 0)
            r_ = v.get("rigori_stagione", {})
            fatti = f"{r_.get('segnati', 0)}/{r_.get('calciati', 0)}"
            rango = f"{v['rango']}º per le fonti" if v["rango"] else "fuori dalle liste delle fonti"
            conferma = v.get("conferma")
            scavalcato = scavalcato_di_recente(v)
            if scavalcato:   # il fatto più recente su di lui: viene prima di tutto il resto
                chi = ", ".join(f"{x['nome']} alla giornata {x['giornata']}" for x in scavalcato)
                davanti = (f" ({', '.join(e['erede_rigorista'])} è fuori, quindi per le fonti "
                           "toccherebbe a lui)") if e.get("erede_rigorista") else ""
                volte = "nell'unico episodio osservato" if len(scavalcato) == 1 else \
                    f"in {len(scavalcato)} episodi"
                quanto = (f"{rango}{davanti}, ma {volte} dopo il suo ultimo rigore ha calciato "
                          f"{chi} mentre lui era in campo: finché non ci sono altri rigori, il "
                          "fatto pesa più delle fonti")
            elif conferma == "confermato":
                quanto = (f"RIG! ha calciato {fatti} rigori quest'anno da primo delle fonti ({primo} su "
                          f"{tot} lo danno primo) — il rigore è già dentro la sua media")
            elif conferma == "sostituto":
                quanto = (f"{rango}: ha calciato {fatti} rigori quest'anno, ma quando chi gli sta "
                          "sopra non era in campo. È il sostituto, non il primo")
            elif conferma == "smentisce":
                quanto = (f"{rango}, ma ha calciato {fatti} rigori quest'anno con in campo chi le "
                          "fonti gli mettevano sopra: calcia prima di quanto dicono")
            elif conferma == "incerto":
                quanto = (f"{rango}: ha calciato {fatti} rigori quest'anno, e chi gli sta sopra era "
                          "in campo per una parte della partita: dipende dal minuto")
            elif e.get("erede_rigorista"):
                quanto = (f"rig? {rango}, ma {', '.join(e['erede_rigorista'])} è fuori: per le fonti "
                          "tocca a lui. Non l'ha ancora calciato")
            elif v["consenso_sul_primo"]:
                quanto = (f"rig? dato primo da {primo} fonti su {tot}, ma non l'ha ancora "
                          "calciato: supposizione")
            elif v["rango"]:
                quanto = f"{v['rango']}º nella gerarchia: vale +0,03, niente"
            else:
                quanto = "non in gerarchia"
            print(f"  [{p['role']}] {p['name']:<18} {v['squadra']:<12} {quanto}")

    if lega:
        dove = "in casa" if lega["casa"] else "in trasferta"
        print(f"\nAVVERSARIO DI LEGA: {lega['avversario_nome']}, {dove} "
              f"({lega['competizione']}, giornata {lega['giornata']} = Serie A {lega['giornata_serie_a']}).")
        avv, mio = lega["avversario"], lega["mio"]
        if avv["giocate"]:
            print(f"  Lui: {avv['punti'] / avv['giocate']:.1f} punti di media in {avv['giocate']} "
                  f"giornate, {avv['classifica']} punti in classifica.")
            print(f"  Tu:  {mio['punti'] / mio['giocate']:.1f} punti di media in {mio['giocate']} "
                  f"giornate, {mio['classifica']} punti in classifica.")
        else:
            print("  Prima giornata della lega: non c'è ancora storico per confrontarvi.")

    if r["modulo"]:
        print("\nDA COSA È FATTO IL VALORE (titolari e primi due cambi di ogni ruolo):")
        primi = {}
        for e in r["panchina"]:
            primi.setdefault(e["player"]["role"], []).append(e)
        for e in r["titolari"] + [e for role in "PDCA" for e in primi.get(role, [])[:2]]:
            print(f"  {_dettaglio(e)}")

    storico = _storico()
    if storico and (r["titolari"] or r["panchina"]):
        stagioni = list(storico)[:2]
        print(f"\nSTAGIONI PASSATE in Serie A ({', '.join(stagioni)}; solo contesto, non entra nel valore):")
        for e in r["titolari"] + r["panchina"]:
            p = e["player"]
            dati = " | ".join(f"{s}: {_stagione(storico[s]['giocatori'].get(p['id']))}" for s in stagioni)
            print(f"  [{p['role']}] {p['name']:<16} {dati}")

    if r["decisioni"]:
        print(f"\nDECISIONI TUE (sotto {SOGLIA_PARI:.2f} di differenza il modello non sa scegliere meglio di una moneta):")
        for d in r["decisioni"]:
            print(f"  - {d}")

    if r["non_disponibili"]:
        print("\nNON DISPONIBILI:")
        for nd in r["non_disponibili"]:
            p = nd["player"]
            print(f"  [{p['role']}] {p['name']:<22} {nd['motivo']}")

    if r["avvisi"]:
        print("\nDA VERIFICARE A MANO:")
        for a in r["avvisi"]:
            print(f"  - {a}")


if __name__ == "__main__":
    main()
