from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from statistics import mean

from . import store

EXCLUDED_STATUSES = {"infortunato", "squalificato"}
ROLES = ["P", "D", "C", "A"]
# Oltre questa età lo status di un titolare va ricontrollato: con la routine del
# mattino dovrebbe avere al massimo un giorno.
STATUS_VECCHIO_GIORNI = 4

# Forma recente: si guardano gli ultimi N voti presi, non le ultime N giornate.
FORMA_ULTIMI_VOTI = 5
# Chi ha pochi voti viene avvicinato alla media del suo ruolo, come se avesse
# FRENO_VOTI partite in più giocate "da giocatore medio". Senza freno, ordinando per
# media vince chi ha giocato una sola partita fortunata. Valore da ritarare quando
# ci saranno i voti veri (vedi .docs/difetti-consiglio-formazione.md, difetto 3).
FRENO_VOTI = 3

# Role counts per module, excluding the goalkeeper (always 1).
MODULE_ROLE_COUNTS = {
    "3-4-3": {"D": 3, "C": 4, "A": 3},
    "3-5-2": {"D": 3, "C": 5, "A": 2},
    "4-3-3": {"D": 4, "C": 3, "A": 3},
    "4-4-2": {"D": 4, "C": 4, "A": 2},
    "4-5-1": {"D": 4, "C": 5, "A": 1},
    "5-3-2": {"D": 5, "C": 3, "A": 2},
    "5-4-1": {"D": 5, "C": 4, "A": 1},
}


def _n(n: int, singolare: str, plurale: str) -> str:
    return f"{n} {singolare if n == 1 else plurale}"


def team_roster(team_id: str, players_by_id: dict):
    """Ritorna (rosa, player_id di ownership.json che non esistono più nel listone)."""
    roster, mancanti = [], []
    for o in store.load_ownership():
        if o["team_id"] != team_id:
            continue
        if o["player_id"] in players_by_id:
            roster.append({**players_by_id[o["player_id"]], "purchase_price": o["purchase_price"]})
        else:
            mancanti.append(o["player_id"])
    return roster, mancanti


def _matchday_sort_key(row: dict):
    """La giornata può essere nulla: la fonte la etichetta con circa un giorno di
    ritardo, quindi una riga senza giornata è quasi sempre la più recente. Va in
    fondo all'ordinamento invece di far fallire il confronto int/None."""
    matchday = row.get("matchday")
    return (1, 0) if matchday is None else (0, matchday)


def load_votes() -> dict:
    """player_id -> fantavoto presi, in ordine di giornata (le partite senza voto non ci sono)."""
    votes = defaultdict(list)
    for r in sorted(store.load_matchday_stats(), key=_matchday_sort_key):
        if r.get("fantavoto") is not None:
            votes[r["player_id"]].append(r["fantavoto"])
    return votes


def role_averages(votes: dict, players_by_id: dict) -> dict:
    per_role = defaultdict(list)
    for pid, v in votes.items():
        if pid in players_by_id:
            per_role[players_by_id[pid]["role"]].extend(v)
    return {role: mean(v) for role, v in per_role.items() if v}


def rate_player(player: dict, votes: dict, role_avg: dict) -> dict | None:
    """Media quando gioca (ultimi voti), quanti voti la sostengono, e il punteggio usato
    per ordinare: la media frenata verso quella del ruolo se i voti sono pochi.
    None se il giocatore non ha nessun voto: non si stima niente."""
    ultimi = votes.get(player["id"], [])[-FORMA_ULTIMI_VOTI:]
    if not ultimi:
        return None
    base = role_avg.get(player["role"], mean(ultimi))
    return {
        "media": mean(ultimi),
        "n": len(ultimi),
        "punteggio": (sum(ultimi) + FRENO_VOTI * base) / (len(ultimi) + FRENO_VOTI),
    }


def player_history_vs_opponent(player_id: str, opponent_serie_a_team: str):
    return [
        r
        for r in store.load_matchday_stats()
        if r["player_id"] == player_id
        and r["opponent_serie_a_team"] == opponent_serie_a_team
    ]


def prossimo_turno(adesso: datetime | None = None) -> dict:
    """Il prossimo turno di Serie A ricavato dalle date delle partite, senza inventare il
    numero di giornata (la fonte lo assegna solo dopo che la partita è stata giocata).

    Il turno sono le prime 10 partite non ancora giocate: se coprono le 20 squadre una
    volta ciascuna è un turno pulito. Se no (un recupero, un rinvio, un turno già
    iniziato) `chiaro` è False e nessuno viene escluso: va controllato a mano."""
    path = store.DATA_DIR / "calendario_serie_a.json"
    calendario = store.load_json(path) if path.exists() else []
    adesso = (adesso or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S")
    futuri = sorted(
        (m for m in calendario if m["stato"] != "finished" and m["data_utc"][:19] >= adesso),
        key=lambda m: m["data_utc"],
    )
    turno = futuri[:10]
    squadre = Counter(t for m in turno for t in (m["squadra_casa"], m["squadra_trasferta"]))
    per_squadra = {}
    for m in futuri:
        for t in (m["squadra_casa"], m["squadra_trasferta"]):
            per_squadra.setdefault(t, m)
    return {
        "partite": turno,
        "chiaro": len(turno) == 10 and len(squadre) == 20,
        "per_squadra": per_squadra,
    }


def _role_order(entries: list[dict]) -> list[dict]:
    """Con sostituzioni illimitate nello stesso ruolo conviene mettere avanti chi ha
    la media più alta quando gioca, qualunque sia la probabilità che giochi: se non
    scende in campo entra il successivo. La probabilità non entra nell'ordine.
    Chi non ha voti va in fondo, ordinato per probabilità di giocare."""
    con_voti = sorted((e for e in entries if e["rating"]), key=lambda e: -e["rating"]["punteggio"])
    senza_voti = sorted(
        (e for e in entries if not e["rating"]),
        key=lambda e: -(e["player"].get("prob_titolare") or 0),
    )
    return con_voti + senza_voti


def suggest_lineup(team_id: str, allowed_modules: list[str] | None = None) -> dict:
    """Sceglie il modulo con la somma di punteggi più alta tra i titolari (la lega non
    usa il modificatore di difesa) e ordina la panchina ruolo per ruolo con lo stesso
    criterio dei titolari, perché è lei a coprire chi non prende voto."""
    config = store.load_league_config()
    modules = allowed_modules or config["formation_modules"]
    players_by_id = {p["id"]: p for p in store.load_players()}
    roster, mancanti = team_roster(team_id, players_by_id)
    votes = load_votes()
    role_avg = role_averages(votes, players_by_id)

    avvisi = []
    if mancanti:
        avvisi.append(
            f"{_n(len(mancanti), 'giocatore', 'giocatori')} di ownership.json non più nel listone, fuori dal consiglio: "
            f"{', '.join(mancanti)}"
        )
    attesi = sum(config["roster_requirements"].values())
    if roster and len(roster) + len(mancanti) != attesi:
        avvisi.append(f"La rosa ha {len(roster) + len(mancanti)} giocatori invece di {attesi}.")

    turno = prossimo_turno()
    if roster and turno["partite"] and not turno["chiaro"]:
        avvisi.append(
            "Il prossimo turno non si ricostruisce dalle date (un recupero, un rinvio, o il "
            "turno è già iniziato): controlla a mano che le squadre dei titolari giochino."
        )

    non_disponibili = []
    per_ruolo = {role: [] for role in ROLES}
    for p in roster:
        partita = turno["per_squadra"].get(p["serie_a_team"])
        if p["status"] in EXCLUDED_STATUSES:
            non_disponibili.append({"player": p, "motivo": p.get("status_note") or p["status"]})
        elif turno["chiaro"] and partita and partita["stato"] == "postponed":
            non_disponibili.append(
                {"player": p, "motivo": f"partita rinviata: {partita['squadra_casa']}-{partita['squadra_trasferta']}"}
            )
        else:
            per_ruolo[p["role"]].append(
                {"player": p, "rating": rate_player(p, votes, role_avg), "partita": partita}
            )
    per_ruolo = {role: _role_order(entries) for role, entries in per_ruolo.items()}

    risultato = {
        "modulo": None,
        "titolari": [],
        "panchina": [e for role in ROLES for e in per_ruolo[role]],
        "non_disponibili": non_disponibili,
        "turno": turno,
        "scoperti": {},
        "avvisi": avvisi,
    }
    if not roster:
        avvisi.append(f"Nessun giocatore in ownership.json per la squadra {team_id}.")
        return risultato
    if not any(e["rating"] for entries in per_ruolo.values() for e in entries):
        avvisi.append(
            "Nessun giocatore della rosa ha ancora un voto: il motore non può consigliare "
            "una formazione finché non arrivano i voti. Sotto, la rosa per ruolo."
        )
        return risultato

    best = None
    for module in modules:
        counts = {"P": 1, **MODULE_ROLE_COUNTS[module]}
        titolari, scoperti = [], {}
        for role, n in counts.items():
            titolari.extend(per_ruolo[role][:n])
            if len(per_ruolo[role]) < n:
                scoperti[role] = n - len(per_ruolo[role])
        # Prima i moduli che si riempiono tutti, poi quelli con meno titolari senza
        # voti da decidere a mano, poi la somma dei punteggi più alta.
        chiave = (
            sum(scoperti.values()),
            sum(1 for e in titolari if not e["rating"]),
            -sum(e["rating"]["punteggio"] for e in titolari if e["rating"]),
        )
        if best is None or chiave < best[0]:
            best = (chiave, module, titolari, scoperti)

    _, module, titolari, scoperti = best
    in_campo = {e["player"]["id"] for e in titolari}
    risultato.update(
        modulo=module,
        titolari=titolari,
        panchina=[e for role in ROLES for e in per_ruolo[role] if e["player"]["id"] not in in_campo],
        scoperti=scoperti,
    )
    for role, n in scoperti.items():
        avvisi.append(f"Ruolo {role}: manca{'' if n == 1 else 'no'} {_n(n, 'giocatore disponibile', 'giocatori disponibili')}, nessun modulo lo copre.")
    senza_voti = [e["player"]["name"] for e in titolari if not e["rating"]]
    if senza_voti:
        avvisi.append(f"Titolari senza nessun voto, da decidere a mano: {', '.join(senza_voti)}.")
    squalifiche_path = store.DATA_DIR / "squalifiche.json"
    diffidati = {
        s["player_id"]
        for s in (store.load_json(squalifiche_path) if squalifiche_path.exists() else [])
        if s["tipo"] == "diffidato"
    }
    nomi_diffidati = [e["player"]["name"] for e in titolari if e["player"]["id"] in diffidati]
    if nomi_diffidati:
        avvisi.append(
            f"Diffidati tra i titolari: {', '.join(nomi_diffidati)}. Con un'ammonizione "
            "saltano la giornata successiva."
        )
    fuori_probabili = [
        e["player"]["name"] for e in titolari
        if e["player"]["status"] == "n/d" and "non trovato nelle probabili" in (e["player"].get("status_note") or "")
    ]
    if fuori_probabili:
        avvisi.append(
            f"Titolari che non compaiono nelle probabili (assenti, o nome scritto diversamente): "
            f"{', '.join(fuori_probabili)}. Verifica prima della deadline."
        )
    oggi = date.today()
    vecchi = []
    for e in titolari:
        agg = e["player"].get("status_updated_at")
        if agg and (oggi - date.fromisoformat(agg)).days > STATUS_VECCHIO_GIORNI:
            vecchi.append(f"{e['player']['name']} ({agg})")
    if vecchi and len(vecchi) == len(titolari):
        avvisi.append(
            f"Lo status di tutti i titolari è più vecchio di {STATUS_VECCHIO_GIORNI} giorni. "
            "La routine del mattino sta girando?"
        )
    elif vecchi:
        avvisi.append(f"Status più vecchio di {STATUS_VECCHIO_GIORNI} giorni: {', '.join(vecchi)}.")
    return risultato
