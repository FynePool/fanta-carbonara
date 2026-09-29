"""I casi limite trovati nelle revisioni di Codex del 29/09, perché non tornino.

Non leggono data/: ogni caso è costruito a mano, quindi non cambiano con i dati del giorno.

    python3 -m unittest discover tests
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import roster as R  # noqa: E402
from lib.simulazione import Simulazione  # noqa: E402
import rigoristi as RG  # noqa: E402
import controlla_formazione as CF  # noqa: E402

POLITICO = {"punteggio": 6.0, "politico": True}


def portiere(prob, rating=None, stima=4.70, quota=96.0, fuori=False, squadra="Inter"):
    return {"player": {"role": "P", "serie_a_team": squadra, "prob_titolare": prob},
            "rating": rating, "stima": None if rating else stima,
            "quota_portieri_squadra": quota, "titolare_porta_fuori": fuori}


def arrotonda(t):
    return tuple(round(x, 4) for x in t)


class Portieri(unittest.TestCase):
    def test_coppia_della_stessa_squadra_invertita_vale_uguale(self):
        martinez = portiere(90, {"punteggio": 4.54})
        provedel = portiere(5)
        self.assertEqual(arrotonda(R._slot_attesi([martinez, provedel], 1)),
                         arrotonda(R._slot_attesi([provedel, martinez], 1)))
        self.assertAlmostEqual(R._slot_attesi([martinez, provedel], 1)[1], 95 / 96)

    def test_titolare_fuori_le_riserve_coprono_la_porta(self):
        # Martinez infortunato, quote del sito non aggiornate: una delle due riserve gioca
        players = {
            "m": {"role": "P", "serie_a_team": "Inter", "prob_titolare": 90, "status": "infortunato"},
            "p": {"role": "P", "serie_a_team": "Inter", "prob_titolare": 5, "status": "panchina"},
            "d": {"role": "P", "serie_a_team": "Inter", "prob_titolare": 1, "status": "panchina"},
        }
        quota, fuori = R.quote_portieri(players)
        self.assertEqual(quota["Inter"], 6.0)
        self.assertIn("Inter", fuori)
        provedel = portiere(5, quota=quota["Inter"], fuori=True)
        di_gennaro = portiere(1, quota=quota["Inter"], fuori=True)
        self.assertAlmostEqual(R._slot_attesi([provedel, di_gennaro], 1)[1], 1.0)

    def test_riserva_posseduta_da_sola_col_titolare_fuori(self):
        # Pdor saint-germain ha De Gea e Christensen ma non Lezzerini: se De Gea si ferma
        players = {
            "dg": {"role": "P", "serie_a_team": "Fiorentina", "prob_titolare": 90, "status": "infortunato"},
            "ch": {"role": "P", "serie_a_team": "Fiorentina", "prob_titolare": 5, "status": "panchina"},
            "le": {"role": "P", "serie_a_team": "Fiorentina", "prob_titolare": 1, "status": "panchina"},
        }
        quota, fuori = R.quote_portieri(players)
        christensen = portiere(5, quota=quota["Fiorentina"], fuori="Fiorentina" in fuori)
        self.assertAlmostEqual(R._slot_attesi([christensen], 1)[1], 5 / 6)

    def test_riserva_fuori_non_gonfia_il_titolare(self):
        # Grabara (riserva della Juventus, senza quota) infortunato: Vicario resta al 90%
        players = {
            "vi": {"role": "P", "serie_a_team": "Juventus", "prob_titolare": 90, "status": "titolare"},
            "gr": {"role": "P", "serie_a_team": "Juventus", "prob_titolare": None, "status": "infortunato"},
            "ne": {"role": "P", "serie_a_team": "Juventus", "prob_titolare": 5, "status": "panchina"},
        }
        quota, fuori = R.quote_portieri(players)
        self.assertNotIn("Juventus", fuori)
        vicario = portiere(90, {"punteggio": 5.0}, quota=quota["Juventus"], fuori=False, squadra="Juventus")
        self.assertAlmostEqual(R._slot_attesi([vicario], 1)[1], 0.90)

    def test_coppia_con_dato_mancante_non_supera_il_100(self):
        senza_dato = portiere(None)
        _, coperto = R._slot_attesi([portiere(90, {"punteggio": 4.54}), senza_dato], 1)
        self.assertLessEqual(coperto, 1.0 + 1e-9)


class SeiPolitico(unittest.TestCase):
    def test_due_portieri_col_6(self):
        self.assertEqual(arrotonda(R._slot_attesi([portiere(90, POLITICO), portiere(5, POLITICO)], 1)),
                         (6.0, 1.0))

    def test_portiere_col_6_e_uno_normale(self):
        self.assertEqual(arrotonda(R._slot_attesi([portiere(90, POLITICO), portiere(5)], 1)),
                         (6.0, 1.0))

    def test_6_politico_non_moltiplicato_per_la_titolarita(self):
        entry = {"player": {"role": "C", "serie_a_team": "X", "prob_titolare": 10}, "rating": POLITICO}
        self.assertEqual(arrotonda(R._slot_attesi([entry], 1)), (6.0, 1.0))


class ScenarioGol(unittest.TestCase):
    def test_le_percentuali_sommano_a_100(self):
        from report_formazione import percentuali_a_5
        self.assertEqual(percentuali_a_5([0.693, 0.197, 0.084, 0.026]), [70, 20, 10, 0])
        for prob in ([0.23, 0.26, 0.27, 0.24], [0.02, 0.18, 0.40, 0.40], [1.0, 0, 0, 0],
                     [0.124, 0.124, 0.376, 0.376]):
            risultato = percentuali_a_5(prob)
            self.assertEqual(sum(risultato), 100)
            self.assertTrue(all(x % 5 == 0 for x in risultato))


class Rigoristi(unittest.TestCase):
    VOCI = [{"player_id": "A", "nome": "Primo", "squadra": "X", "rango": 1},
            {"player_id": "B", "nome": "Secondo", "squadra": "X", "rango": 2}]
    PER_ID = {"A": {"name": "Primo", "serie_a_team": "X"}, "B": {"name": "Secondo", "serie_a_team": "X"}}

    def esito(self, riga_primo, riga_secondo=None):
        righe = [dict(match_id="m", matchday=1, player_id="B", rigori_segnati=1,
                      **(riga_secondo or {"minuti": 90, "subentrato": False}))]
        if riga_primo is not None:
            righe.append(dict(match_id="m", matchday=1, player_id="A", **riga_primo))
        return RG.valuta_rigori(self.VOCI, righe, self.PER_ID, [])[1][0]["esito"]

    def test_primo_assente_il_secondo_e_coerente(self):
        self.assertEqual(self.esito(None), "coerente")
        self.assertEqual(self.esito({"minuti": 0, "subentrato": True}), "coerente")

    def test_primo_in_campo_il_secondo_smentisce(self):
        self.assertEqual(self.esito({"minuti": 90, "subentrato": False}), "smentisce")

    def test_minuti_sconosciuti_non_sono_assenza(self):
        self.assertEqual(self.esito({"minuti": None, "subentrato": None, "fantavoto": 6.5}), "incerto")
        self.assertEqual(self.esito({"minuti": 90, "subentrato": False},
                                    {"minuti": None, "subentrato": None}), "incerto")

    def test_conta_il_rigore_piu_recente(self):
        self.assertEqual(RG._conferma([{"esito": "primo", "giornata": 5},
                                       {"esito": "smentisce", "giornata": 8}]), "smentisce")
        self.assertEqual(RG._conferma([{"esito": "smentisce", "giornata": 5},
                                       {"esito": "primo", "giornata": 8}]), "confermato")

    def test_scavalcato_dopo_la_conferma_non_ha_peso(self):
        voce = {"conferma": "confermato", "ultimo_rigore": 5, "consenso_sul_primo": True,
                "scavalcato_da": [{"nome": "Altro", "giornata": 8, "dove": "in campo"}],
                "rigori_stagione": {"calciati": 1, "segnati": 1}}
        self.assertTrue(R.scavalcato_di_recente(voce))
        rigorista = {"player": {"name": "Zaccagni"}, "rigorista": voce}
        altro = {"player": {"name": "Altro"}, "rigorista": None}
        self.assertEqual(R._spareggio_rigorista(rigorista, altro, 0.26), "")

    def test_scavalcato_prima_della_conferma_non_conta_piu(self):
        voce = {"ultimo_rigore": 8, "scavalcato_da": [{"nome": "Altro", "giornata": 5, "dove": "in campo"}]}
        self.assertFalse(R.scavalcato_di_recente(voce))


class VotiDUfficio(unittest.TestCase):
    def vero(self, righe):
        sim = Simulazione.__new__(Simulazione)
        sim.cfg = {"scoring": {"senza_voto_ammonito": 5.5, "senza_voto_espulso": 4}}
        sim.righe = righe
        sim._vero()
        return sim

    def test_solo_a_chi_ha_giocato(self):
        riga = dict(matchday=1, fantavoto=None)
        sim = self.vero([
            dict(riga, player_id="panchina", cartellini_gialli=1, minuti=0),     # Sabelli
            dict(riga, player_id="ammonito", cartellini_gialli=1, minuti=12),
            dict(riga, player_id="espulso", cartellini_rossi=1, cartellini_gialli=1, minuti=30),
            dict(riga, player_id="ignoto", cartellini_gialli=1, minuti=None),
        ])
        self.assertNotIn(("panchina", 1), sim.vero)
        self.assertEqual(sim.vero[("ammonito", 1)], 5.5)
        self.assertEqual(sim.vero[("espulso", 1)], 4.0)
        self.assertNotIn(("ignoto", 1), sim.vero)
        self.assertEqual(sim.voti_ufficio["minuti_ignoti"], 1)


def partita(casa, trasferta, stato="finished"):
    return {"stagione": "2026-27", "stato": stato, "squadra_casa": casa, "squadra_trasferta": trasferta}


def giornata_lega(giornata, serie_a, casa="io", trasferta="lui", calcolata=False):
    return {"giornata": giornata, "giornata_serie_a": serie_a, "calcolata": calcolata,
            "partite": [{"casa": casa, "trasferta": trasferta}]}


LEGA = [{"id": "1", "nome": "Campionato", "calendario": [giornata_lega(1, 6), giornata_lega(2, 7)]}]
# 4 squadre, 5 turni finiti: ognuna ha 5 partite
CINQUE_TURNI = [partita("A", "B") for _ in range(5)] + [partita("C", "D") for _ in range(5)]


class GiornataDaControllare(unittest.TestCase):
    def test_prossimo_turno(self):
        g, motivo = CF.giornata_da_controllare(LEGA, CINQUE_TURNI, "io")
        self.assertEqual((g["giornata"], g["giornata_serie_a"], g["avversario_id"]), (1, 6, "lui"))

    def test_turno_iniziato_la_formazione_e_chiusa(self):
        # A-B ha già giocato la sesta: la giornata 1 (Serie A 6) non si cambia più
        g, _ = CF.giornata_da_controllare(LEGA, CINQUE_TURNI + [partita("A", "B")], "io")
        self.assertEqual(g["giornata_serie_a"], 7)

    def test_un_rinvio_non_sposta_il_turno(self):
        # C-D rinviata al quinto turno: C e D sono a 4, il prossimo turno resta il 6
        calendario = CINQUE_TURNI[:-1] + [partita("C", "D", "postponed")]
        g, _ = CF.giornata_da_controllare(LEGA, calendario, "io")
        self.assertEqual(g["giornata_serie_a"], 6)

    def test_giornata_di_lega_piu_avanti_del_prossimo_turno(self):
        lega = [{"id": "1", "nome": "Coppa", "calendario": [giornata_lega(1, 8)]}]
        g, motivo = CF.giornata_da_controllare(lega, CINQUE_TURNI, "io")
        self.assertIsNone(g)
        self.assertIn("turno 8", motivo)

    def test_calcolata_e_di_altri_non_contano(self):
        lega = [{"id": "1", "nome": "Campionato", "calendario": [
            giornata_lega(1, 6, calcolata=True), giornata_lega(2, 6, "x", "y")]}]
        g, motivo = CF.giornata_da_controllare(lega, CINQUE_TURNI, "io")
        self.assertIsNone(g)


class AvvisoFormazioneMancante(unittest.TestCase):
    # scadenza sabato 10/10 alle 15:00 italiane; la routine gira alle 6:52 italiane
    SCADENZA = datetime(2026, 10, 10, 13, 0, tzinfo=timezone.utc)

    def giorni(self, giorno, ora_utc=4):
        return CF.giorni_alla_scadenza(self.SCADENZA, datetime(2026, 10, giorno, ora_utc, 52, tzinfo=timezone.utc))

    def test_da_due_giorni_prima_al_giorno_stesso(self):
        self.assertEqual([self.giorni(g) for g in (7, 8, 9, 10)], [3, 2, 1, 0])
        self.assertEqual([self.giorni(g) <= CF.GIORNI_URGENZA for g in (7, 8, 9, 10)],
                         [False, True, True, True])

    def test_conta_il_giorno_italiano(self):
        # 22:30 UTC del 7/10 è già l'8/10 in Italia: due giorni, non tre
        self.assertEqual(self.giorni(7, ora_utc=22), 2)


def giocatore(pid, ruolo, valore, prob=90, squadra=None, status="titolare"):
    return {"player": {"id": pid, "name": pid, "role": ruolo, "serie_a_team": squadra or pid,
                       "prob_titolare": prob, "status": status},
            "rating": {"punteggio": valore}, "stima": None,
            "quota_portieri_squadra": None, "titolare_porta_fuori": False}


def consiglio_343():
    """Un consiglio 3-4-3 con due fuori distinta e un infortunato."""
    t = ([giocatore("p1", "P", 5.0)] + [giocatore(f"d{i}", "D", 6.5 - i / 10) for i in range(3)]
         + [giocatore(f"c{i}", "C", 7.0 - i / 10) for i in range(4)]
         + [giocatore(f"a{i}", "A", 7.0 - i / 10) for i in range(3)])
    b = ([giocatore("p2", "P", 4.5)] + [giocatore(f"d{i}", "D", 6.0 - i / 10) for i in range(3, 5)]
         + [giocatore(f"c{i}", "C", 6.5 - i / 10) for i in range(4, 6)]
         + [giocatore(f"a{i}", "A", 6.5 - i / 10) for i in range(3, 5)])
    esclusi = [giocatore("c6", "C", 6.25), giocatore("a5", "A", 5.5)]
    rotto = giocatore("d9", "D", 7.0, status="infortunato")["player"]
    return {"modulo": "3-4-3", "titolari": t, "panchina": b, "esclusi": esclusi,
            "non_disponibili": [{"player": rotto, "motivo": "infortunato"}]}


def ids(entries):
    return [e["player"]["id"] for e in entries]


class ControlloFormazione(unittest.TestCase):
    def confronta(self, titolari=None, panchina=None):
        c = consiglio_343()
        salvata = {"titolari": titolari or ids(c["titolari"]), "panchina": panchina or ids(c["panchina"])}
        return CF.confronta(salvata, c, {})

    def test_uguale_al_consiglio(self):
        e = self.confronta()
        self.assertFalse(e["da_correggere"])
        self.assertEqual(e["differenze"], [])
        self.assertAlmostEqual(e["atteso"], e["atteso_consiglio"])

    def test_scelta_alla_pari_non_e_un_errore(self):
        # d3, primo cambio, vale 6.25: titolare al posto di d2 (6.3) è una scelta alla pari
        # (come Ndour per Ferguson il 27/09), e la formazione resta OK con la differenza scritta
        c = consiglio_343()
        titolari = ids(c["titolari"])
        panchina = ids(c["panchina"])
        c["panchina"][1]["rating"]["punteggio"] = 6.25
        titolari[titolari.index("d2")], panchina[panchina.index("d3")] = "d3", "d2"
        e = CF.confronta({"titolari": titolari, "panchina": panchina}, c, {})
        self.assertFalse(e["da_correggere"])
        self.assertTrue(e["differenze"])

    def test_distacco_sopra_la_soglia(self):
        c = consiglio_343()
        titolari = [x if x != "a0" else "a5" for x in ids(c["titolari"])]   # 5.5 invece di 7.0
        e = CF.confronta({"titolari": titolari, "panchina": ids(c["panchina"])}, c, {})
        self.assertTrue(e["da_correggere"])
        self.assertEqual(e["sotto"], ["A"])

    def test_infortunato_schierato(self):
        c = consiglio_343()
        titolari = [x if x != "d0" else "d9" for x in ids(c["titolari"])]
        e = CF.confronta({"titolari": titolari, "panchina": ids(c["panchina"])}, c, {})
        self.assertTrue(e["da_correggere"])
        self.assertIn("d9 è titolare ma è infortunato", e["problemi"][0])

    def test_giocatore_non_piu_in_rosa(self):
        c = consiglio_343()
        panchina = [x if x != "a4" else "venduto" for x in ids(c["panchina"])]
        e = CF.confronta({"titolari": ids(c["titolari"]), "panchina": panchina}, c, {})
        self.assertTrue(e["da_correggere"])
        self.assertIn("non è nella tua rosa", e["problemi"][0])


if __name__ == "__main__":
    unittest.main()
