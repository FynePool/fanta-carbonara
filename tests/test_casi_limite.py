"""I casi limite trovati nelle revisioni di Codex del 29/09, perché non tornino.

Non leggono data/: ogni caso è costruito a mano, quindi non cambiano con i dati del giorno.

    python3 -m unittest discover tests
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from lib import roster as R  # noqa: E402
from lib.simulazione import Simulazione  # noqa: E402
import rigoristi as RG  # noqa: E402

POLITICO = {"punteggio": 6.0, "politico": True}


def portiere(prob, rating=None, stima=4.70, quota=96.0, fuori=False, squadra="Inter"):
    return {"player": {"role": "P", "serie_a_team": squadra, "prob_titolare": prob},
            "rating": rating, "stima": None if rating else stima,
            "quota_portieri_squadra": quota, "portiere_fuori": fuori}


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


if __name__ == "__main__":
    unittest.main()
