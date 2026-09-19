"""Client Python per l'API privata non ufficiale di leghe.fantacalcio.it.

Verificato da codice sorgente reale (non da un riassunto): porting dei soli
endpoint di lettura di @legasanpetrux/leghe-fc-client
(https://github.com/legasanpetrux/leghe-fc-client, MIT), un client
TypeScript open source per la stessa API. Non è un'API pubblica/ufficiale:
nessun ToS di Fantacalcio.it la documenta o la autorizza esplicitamente.
Uso a proprio rischio, solo in lettura, solo per la propria lega.

Cosa è verificato DA QUESTA sessione, oggi, contro l'host reale:
- La app key (`authAppKey`) è un valore pubblico incorporato nell'HTML di
  https://leghe.fantacalcio.it/, uguale per chiunque la visiti: si estrae
  con una GET + regex, NESSUN login o DevTools richiesto. Testato live.

Cosa NON è ancora verificato (richiede un account e una lega reali, che
non esistono finché l'asta non è conclusa):
- Il login (POST /onboarding/v1/login con username/password) e tutte le
  chiamate autenticate successive. La struttura sotto rispecchia il codice
  sorgente del client TypeScript, ma non è stata eseguita end-to-end qui.
  Testare con le proprie credenziali reali, mai incollando la password in
  chat: impostarla come variabile d'ambiente e lanciare lo script in locale.
"""
import os
import re

import requests

API_BASE_URL = "https://apileague.fantacalcio.it"
APP_KEY_SOURCE_URL = "https://leghe.fantacalcio.it/"
APP_KEY_PATTERN = re.compile(r"""\b["']?authAppKey["']?\s*:\s*(["'])([A-Za-z0-9_-]{16,128})\1""")
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.5",
}


class LegheFcError(Exception):
    pass


def discover_app_key() -> str:
    """Verificato live in questa sessione (19/09/2026): funziona senza credenziali."""
    resp = requests.get(APP_KEY_SOURCE_URL, headers=BROWSER_HEADERS, timeout=20)
    resp.raise_for_status()
    match = APP_KEY_PATTERN.search(resp.text)
    if not match:
        raise LegheFcError(
            "authAppKey non trovata nell'HTML della homepage: la pagina è probabilmente cambiata."
        )
    return match.group(2)


def login(username: str, password: str, app_key: str | None = None) -> dict:
    """NON TESTATO end-to-end. Ritorna il payload grezzo di /onboarding/v1/login,
    che (da codice sorgente del client TS) contiene data.leghe: una lista di
    leghe con id, nome, alias, id_squadra e un jwt per lega."""
    app_key = app_key or discover_app_key()
    resp = requests.post(
        f"{API_BASE_URL}/onboarding/v1/login",
        json={"username": username, "password": password},
        headers={**BROWSER_HEADERS, "appKey": app_key},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def authenticated_get(path: str, jwt: str, app_key: str | None = None) -> dict:
    """NON TESTATO. path es. '/onboarding/v1/league/teams/all',
    '/onboarding/v1/league/players', '/onboarding/v1/league/competition/calendar/<id>'."""
    app_key = app_key or discover_app_key()
    resp = requests.get(
        f"{API_BASE_URL}{path}",
        headers={**BROWSER_HEADERS, "appKey": app_key, "Authorization": jwt},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    # Smoke test manuale, solo per la parte verificabile senza credenziali.
    key = discover_app_key()
    print(f"App key scoperta con successo (lunghezza {len(key)}, valore non stampato).")
    print("Login e chiamate autenticate non testate qui: servono LEGHE_FC_USERNAME/")
    print("LEGHE_FC_PASSWORD reali, da impostare come variabili d'ambiente in locale, mai in chat.")
