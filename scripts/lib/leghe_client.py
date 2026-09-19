"""Client per leghe.fantacalcio.it — SCAFFOLD NON VERIFICATO.

Non esiste, a quanto risulta da ricerca pubblica, un'API ufficiale o
documentata per leghe.fantacalcio.it. L'unico approccio noto (vedi
github.com/zackbartowski/Fantabot) è HTML scraping autenticato via
cookie di sessione — e quel progetto stesso dichiara i propri selettori
"non verificati" perché mai testati contro l'HTML reale di una lega.

Questo modulo NON contiene selettori CSS indovinati: aggiungerli senza
poterli verificare contro una pagina reale è come costruire su sabbia.
Va completato SOLO dopo l'asta, quando esiste una lega vera, seguendo
questa procedura:

1. Login manuale nel browser sulla propria lega.
2. Copiare il cookie di sessione (DevTools -> Application/Storage -> Cookie)
   in una variabile d'ambiente (mai committarlo: vedi .gitignore, .env*).
3. Scaricare l'HTML reale di 2-3 pagine chiave (classifica, rosa, mercato)
   con questo client e salvarlo in una cartella locale non versionata.
4. Ispezionare quell'HTML reale e SOLO A QUEL PUNTO scrivere i selettori
   di parsing in questo file, verificandoli contro i dati reali.

Fino ad allora, qualunque dato "di lega" (rose, crediti, punteggi ufficiali)
va inserito a mano o importato da un export Excel ufficiale della lega
(funzione supportata nativamente da leghe.fantacalcio.it).
"""
import os

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


class LegheFantacalcioClient:
    """Wrapper HTTP minimo, cookie-based. Nessun parsing incluso: vedi docstring del modulo."""

    def __init__(self, league_url: str, session_cookie_env: str):
        self.league_url = league_url.rstrip("/")
        cookie = os.environ.get(session_cookie_env)
        if not cookie:
            raise RuntimeError(
                f"Variabile d'ambiente {session_cookie_env} non impostata. "
                "Serve il cookie di sessione ottenuto da un login manuale nel browser."
            )
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.session.headers["Cookie"] = cookie

    def fetch_page(self, path: str) -> str:
        """Scarica una pagina della lega (es. 'classifica', 'rose'). Nessun parsing: solo HTML grezzo."""
        url = f"{self.league_url}/{path.lstrip('/')}"
        resp = self.session.get(url, timeout=20)
        resp.raise_for_status()
        return resp.text
