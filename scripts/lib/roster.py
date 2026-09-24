from collections import defaultdict
from statistics import mean

from . import store

EXCLUDED_STATUSES = {"infortunato", "squalificato"}
ROLES = ["P", "D", "C", "A"]

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

    non_disponibili = [p for p in roster if p["status"] in EXCLUDED_STATUSES]
    per_ruolo = {role: [] for role in ROLES}
    for p in roster:
        if p["status"] not in EXCLUDED_STATUSES:
            per_ruolo[p["role"]].append({"player": p, "rating": rate_player(p, votes, role_avg)})
    per_ruolo = {role: _role_order(entries) for role, entries in per_ruolo.items()}

    risultato = {
        "modulo": None,
        "titolari": [],
        "panchina": [e for role in ROLES for e in per_ruolo[role]],
        "non_disponibili": non_disponibili,
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
    return risultato
