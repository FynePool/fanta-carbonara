"""Le giornate passate rigiocate con le regole vere della lega.

Per ogni rosa della lega e ogni giornata già giocata schiera la formazione coi soli dati
di prima, applica le regole (panchina a quota fissa per ruolo, sostituzioni solo tra pari
ruolo, slot scoperto = 0, voti d'ufficio) e conta i punti **veri**. La usano:

- `backtest_undici.py`, per confrontare regole di valore e varianti in punti veri;
- il report, per misurare di quanto il punteggio atteso di una **formazione intera**
  sbaglia i punti veri (`scarti_formazione`). Misurarlo sul singolo giocatore e
  moltiplicare per la radice di 11 ignora sostituzioni, slot scoperti e dipendenze: il
  29/09 dava ±5,3 punti, sulla formazione intera sono ±6,9.

Usa le funzioni vere di `roster.py` (`rate_player`, `_scegli_panchina`, `_slot_attesi`),
non una loro copia. La probabilità di prendere voto qui NON viene da `prob_titolare`
(fantacalcio.it la pubblica solo dal 21/09): si stima dalle giornate precedenti, quota di
giornate con voto frenata verso la quota media del ruolo.

Niente di quello che si usa per schierare viene dalla giornata da prevedere:
- chi è fuori (infortunato, squalificato) è quello della foto salvata prima della
  scadenza (`data/status_scadenze.json`); senza foto (giornate fino alla 5) nessuno è
  escluso;
- l'avversario viene dal calendario per la squadra del giocatore, non dalle righe del
  tabellino di quella giornata (che esistono solo per chi era nella partita: il 29/09 il
  termine avversario mancava a 65 casi giocatore-giornata).
"""
import statistics as st

from . import roster as R
from . import store

# Freno sulla quota di voti presi: come se il giocatore avesse questo numero di giornate
# in piu' "da giocatore medio del suo ruolo". Con 2-4 giornate alle spalle serve.
FRENO_QUOTA = 2.0


class Simulazione:
    def __init__(self, cfg=None, players=None, righe=None, calendario=None, teams=None):
        self.cfg = cfg or store.load_league_config()
        self.players = players or {p["id"]: p for p in store.load_players()}
        self.righe = righe if righe is not None else store.load_matchday_stats()
        self.calendario = calendario if calendario is not None else \
            store.load_json(store.DATA_DIR / "calendario_serie_a.json")
        self.teams = teams or [t["id"] for t in store.load_json(store.DATA_DIR / "teams.json")]
        self.panchina_cfg = {r: n for r, n in self.cfg["regole_lega"]["panchina"].items() if r in R.ROLES}
        self.rose = {t: R.team_roster(t, self.players)[0] for t in self.teams}
        path = store.DATA_DIR / "status_scadenze.json"
        self.foto = store.load_json(path)["scadenze"] if path.exists() else {}
        self._vero()
        self.avv_squadra = {}
        for m in self.calendario:
            if m.get("giornata") is not None:
                self.avv_squadra[(m["squadra_casa"], m["giornata"])] = m["squadra_trasferta"]
                self.avv_squadra[(m["squadra_trasferta"], m["giornata"])] = m["squadra_casa"]
        self._quote, self._status, self._modelli = {}, {}, {}

    def _vero(self):
        """(player_id, giornata) -> punti veri nella lega. Il fantavoto di fantacalcio.it,
        più i voti d'ufficio del regolamento: chi è ammonito o espulso senza voto prende 5,5
        o 4 (malus già compreso) e non viene sostituito. Solo se ha giocato: il panchinaro
        mai entrato che prende un cartellino non ha malus né voto (Sabelli, giornata 1).
        Se i minuti non si sanno, il voto d'ufficio non si assegna e si conta a parte."""
        scoring = self.cfg.get("scoring") or {}
        ufficio = [("cartellini_rossi", scoring.get("senza_voto_espulso")),
                   ("cartellini_gialli", scoring.get("senza_voto_ammonito"))]
        self.vero = {(r["player_id"], r["matchday"]): r["fantavoto"]
                     for r in self.righe if r.get("fantavoto") is not None}
        self.voti_ufficio = {"cartellini_gialli": 0, "cartellini_rossi": 0, "minuti_ignoti": 0}
        for r in self.righe:
            k = (r["player_id"], r["matchday"])
            if r["matchday"] is None or r.get("fantavoto") is not None or k in self.vero:
                continue
            for campo, voto in ufficio:
                if voto is None or not (r.get(campo) or 0):
                    continue
                if r.get("minuti") is None:
                    self.voti_ufficio["minuti_ignoti"] += 1
                elif r["minuti"] > 0:
                    self.vero[k] = float(voto)
                    self.voti_ufficio[campo] += 1
                break

    def giornate(self, dal: int = 3) -> list[int]:
        ultime = [r["matchday"] for r in self.righe
                  if r["matchday"] is not None and r.get("fantavoto") is not None]
        return list(range(dal, max(ultime) + 1)) if ultime else []

    def status_alla_scadenza(self, g):
        """player_id -> status com'era alla scadenza della giornata g, dall'ultima foto salvata
        prima della sua prima partita e che ne copre la maggior parte delle partite. None se
        non c'e' foto: allora non si esclude nessuno."""
        if g not in self._status:
            partite = [m for m in self.calendario if m.get("giornata") == g]
            ids = {m["match_id"] for m in partite}
            inizio = min((m["data_utc"][:19] for m in partite if m["stato"] != "postponed"), default=None)
            buone = [f for f in self.foto.values()
                     if inizio and f["salvato_il"][:19] <= inizio and len(ids & set(f["partite"])) > len(ids) / 2]
            self._status[g] = max(buone, key=lambda f: f["salvato_il"])["status"] if buone else None
        return self._status[g]

    def disponibile(self, p, g) -> bool:
        stato = self.status_alla_scadenza(g)
        return stato is None or stato.get(p["id"]) not in R.EXCLUDED_STATUSES

    def avversario(self, p, g):
        return self.avv_squadra.get((p["serie_a_team"], g))

    def quote(self, g) -> dict:
        """player_id -> quota di giornate (fra 1 e g-1) in cui ha preso voto, frenata verso
        la quota media del ruolo."""
        if g not in self._quote:
            n_giornate = g - 1
            presi = {pid: 0 for pid in self.players}
            for (pid, md), _ in self.vero.items():
                if md is not None and md < g and pid in presi:
                    presi[pid] += 1
            per_ruolo = {}
            for r_ in R.ROLES:
                v = [presi[pid] / n_giornate for pid in self.players if self.players[pid]["role"] == r_]
                per_ruolo[r_] = st.mean(v) if v else 0.5
            self._quote[g] = {
                pid: (presi[pid] + FRENO_QUOTA * per_ruolo[self.players[pid]["role"]])
                     / (n_giornate + FRENO_QUOTA)
                for pid in self.players
            }
        return self._quote[g]

    def modello(self, g, **par) -> dict:
        """Il modello di roster.py stimato coi soli dati prima della giornata g."""
        chiave = (g, tuple(sorted(par.items())))
        if chiave not in self._modelli:
            self._modelli[chiave] = R.costruisci_modello(
                self.righe, self.players, self.calendario, prima_di_giornata=g, **par)
        return self._modelli[chiave]

    def valore_modello(self, p, g, mo):
        """La regola di valore del motore: `rate_player` con l'avversario dal calendario."""
        rt = R.rate_player(p, mo, self.avversario(p, g))
        return rt["punteggio"] if rt else None

    def schiera(self, team, g, chiave=None, mo=None, panchina_con_prob=True, modulo_con_prob=False) -> dict:
        """Schiera la rosa `team` alla giornata g e conta i punti veri. `chiave(p, g, mo)` è la
        regola di valore (il motore, se None). Ritorna i punti veri, il punteggio atteso
        della formazione scelta (valore atteso degli slot, come nel report) e il modulo."""
        chiave = chiave or self.valore_modello
        mo = mo or self.modello(g)
        q = self.quote(g)
        prob = lambda e: q.get(e["player"]["id"], 0.5)
        per_ruolo = {r: [] for r in R.ROLES}
        for p in self.rose[team]:
            if self.disponibile(p, g):
                # le funzioni di roster.py vogliono le "entry" {player, rating}
                per_ruolo[p["role"]].append({"player": p, "rating": None})
        for r in R.ROLES:
            for e in per_ruolo[r]:
                v = chiave(e["player"], g, mo)
                e["rating"] = {"punteggio": v} if v is not None else None
                # come in suggest_lineup: chi non ha voti vale la media del ruolo negli
                # slot attesi, non 0
                e["stima"] = mo["media_ruolo"].get(r)
            per_ruolo[r].sort(key=lambda e: -(e["rating"]["punteggio"] if e["rating"] else -99))

        def schierati(ruolo, n):
            posti = self.panchina_cfg.get(ruolo, 0)
            if panchina_con_prob:
                t_, r_ = R._scegli_panchina(per_ruolo[ruolo], n, posti, prob)
            else:   # come faceva il report prima del 27/09: le riserve sono le successive per valore
                t_, r_ = per_ruolo[ruolo][:n], per_ruolo[ruolo][n:n + posti]
            return t_ + r_

        migliore, somma_migliore = None, None
        for module in self.cfg["formation_modules"]:
            counts = {"P": 1, **R.MODULE_ROLE_COUNTS[module]}
            if modulo_con_prob:
                s = sum(R._slot_attesi(schierati(r_, n), n, prob)[0] for r_, n in counts.items())
            else:   # somma dei valori dei titolari, senza scontare chi non prende voto
                s = sum((e["rating"]["punteggio"] if e["rating"] else 0)
                        for r_, n in counts.items() for e in per_ruolo[r_][:n])
            if somma_migliore is None or s > somma_migliore:
                somma_migliore, migliore = s, module

        punti, atteso = 0.0, 0.0
        for ruolo, n in {"P": 1, **R.MODULE_ROLE_COUNTS[migliore]}.items():
            in_distinta = schierati(ruolo, n)
            atteso += R._slot_attesi(in_distinta, n, prob)[0]
            presi = 0
            for e in in_distinta:   # titolari + le sole riserve ammesse dalla lega
                if presi >= n:
                    break
                fv = self.vero.get((e["player"]["id"], g))
                if fv is not None:  # senza voto: entra il prossimo DELLO STESSO RUOLO
                    punti += fv
                    presi += 1
            # se le riserve del ruolo finiscono, gli slot restano scoperti e valgono 0
        return {"punti": punti, "atteso": atteso, "modulo": migliore}


def scarti_formazione(dal: int = 3) -> dict | None:
    """Di quanto i punti veri di una formazione intera si sono allontanati dal punteggio
    atteso, rigiocando col motore tutte le rose della lega nelle giornate passate. `sd` è la
    deviazione standard degli scarti, `media` lo scarto medio (positivo = il punteggio atteso
    sottostimava). None se non ci sono giornate. ATTENZIONE: qui la probabilità di prendere
    voto è quella stimata dallo storico, non `prob_titolare` del report: la larghezza si
    trasferisce, lo scarto medio no."""
    sim = Simulazione()
    giornate = sim.giornate(dal)
    scarti = [s["punti"] - s["atteso"]
              for g in giornate for t in sim.teams if sim.rose[t]
              for s in [sim.schiera(t, g)]]
    if len(scarti) < 2:
        return None
    return {"sd": st.pstdev(scarti), "media": st.mean(scarti), "n": len(scarti), "giornate": giornate}
