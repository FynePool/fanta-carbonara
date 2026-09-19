"""Client Python per l'API privata non ufficiale di leghe.fantacalcio.it.

Porting dei soli endpoint di lettura di @legasanpetrux/leghe-fc-client
(https://github.com/legasanpetrux/leghe-fc-client, MIT), un client
TypeScript open source per la stessa API. Non è un'API pubblica/ufficiale:
nessun ToS di Fantacalcio.it la documenta o la autorizza esplicitamente.
Uso a proprio rischio, solo in lettura, solo per la propria lega.

Verificato in questa sessione, end-to-end, con un account e una lega reali
(di test, non quella dell'asta):
- discover_app_key(): funziona senza credenziali (valore pubblico in homepage).
- login(): funziona con username/password reali. L'header corretto per la
  app key è `app_key` (underscore, minuscolo) — un tentativo iniziale con
  `appKey` falliva con 401 "Application key is missing".
- Le chiamate autenticate richiedono `Authorization: Bearer <jwt-di-lega>`.
  ATTENZIONE: il payload di login contiene DUE jwt diversi — `data.jwt`
  (jwt d'account, 808 caratteri nel test) e `data.leghe[i].jwt` (jwt
  specifico per quella lega, più lungo). Solo il secondo funziona per le
  chiamate `/onboarding/v1/league/*`: il primo tentativo con `data.jwt`
  dava 401 "ATH001 Not authorized to access the services" pur essendo
  ben formato. Usare sempre `get_league_jwt()`.
- Endpoint testati con successo: login, `/onboarding/v1/league/teams/all`
  (rose con crediti iniziali/spesi/rimanenti per squadra), `/onboarding/v1/
  league/players` (listone della lega, con le quotazioni proprie della
  lega — non quelle generiche di un aggregatore esterno), `/onboarding/v1/
  league/competitions` (vuoto sulla lega di test, nessuna competizione
  configurata).
"""
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
    "Origin": "https://leghe.fantacalcio.it",
    "Referer": "https://leghe.fantacalcio.it/",
}


class LegheFcError(Exception):
    pass


def discover_app_key() -> str:
    resp = requests.get(APP_KEY_SOURCE_URL, headers=BROWSER_HEADERS, timeout=20)
    resp.raise_for_status()
    match = APP_KEY_PATTERN.search(resp.text)
    if not match:
        raise LegheFcError(
            "authAppKey non trovata nell'HTML della homepage: la pagina è probabilmente cambiata."
        )
    return match.group(2)


def _api_headers(app_key: str, jwt: str | None = None) -> dict:
    headers = {**BROWSER_HEADERS, "app_key": app_key, "Accept": "application/json"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    return headers


def login(username: str, password: str, app_key: str | None = None) -> dict:
    """Ritorna il payload grezzo di /onboarding/v1/login: data.leghe è una
    lista di leghe con id, nome, alias, id_squadra e un jwt per lega."""
    app_key = app_key or discover_app_key()
    resp = requests.post(
        f"{API_BASE_URL}/onboarding/v1/login",
        json={"username": username, "password": password},
        headers=_api_headers(app_key),
        timeout=20,
    )
    if not resp.ok:
        raise LegheFcError(f"Login fallito: HTTP {resp.status_code} — {resp.text[:300]}")
    return resp.json()


def get_league_jwt(login_payload: dict, league_id: int | str | None = None) -> str:
    """Estrae il jwt corretto (specifico di lega, non quello d'account) dal
    payload di login(). Se league_id è None e c'è una sola lega, la usa."""
    leghe = login_payload["data"]["leghe"]
    if league_id is None:
        if len(leghe) != 1:
            raise LegheFcError(
                f"L'account ha {len(leghe)} leghe: specifica league_id esplicitamente."
            )
        return leghe[0]["jwt"]
    for lega in leghe:
        if str(lega["id"]) == str(league_id):
            return lega["jwt"]
    raise LegheFcError(f"Nessuna lega con id {league_id} trovata per questo account.")


def authenticated_get(path: str, jwt: str, app_key: str | None = None) -> dict:
    """path es. '/onboarding/v1/league/teams/all', '/onboarding/v1/league/players',
    '/onboarding/v1/league/competition/calendar/<id>'."""
    app_key = app_key or discover_app_key()
    resp = requests.get(
        f"{API_BASE_URL}{path}",
        headers=_api_headers(app_key, jwt),
        timeout=20,
    )
    if not resp.ok:
        raise LegheFcError(f"Richiesta fallita: HTTP {resp.status_code} — {resp.text[:300]}")
    return resp.json()


if __name__ == "__main__":
    key = discover_app_key()
    print(f"App key scoperta con successo (lunghezza {len(key)}, valore non stampato).")
