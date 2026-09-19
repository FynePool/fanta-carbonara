# Fanta Carbonara

Assistente da riga di comando per gestire una squadra di fantacalcio in una lega
**Classic** da 12 squadre (500 crediti, rose 3P-8D-8C-6A) su
[leghe.fantacalcio.it](https://leghe.fantacalcio.it), pensato per essere pilotato
insieme a Claude Code tramite le skill in `.claude/skills/`.

Copre tre momenti: **asta** (import listone + tracking live degli acquisti),
**mercato post-asta** (scambi e svincoli) e **formazione** (proposta titolari
a partire dallo storico voti e dalle probabili formazioni).

## Stato attuale

Priorità del momento: l'asta di inizio stagione. Finché le rose non sono
complete, il modulo formazione non ha nulla su cui basarsi. Vedi `CLAUDE.md`
per lo stato dettagliato e cosa manca ancora.

Non c'è scraping automatico delle rose reali in questa fase: il listone si
importa da un export ufficiale, gli acquisti d'asta si registrano a mano man
mano che avvengono, e lo status dei giocatori va aggiornato prima di ogni
deadline formazioni (a mano o con lo scraper delle probabili formazioni).

## Setup

```bash
pip install -r requirements.txt
```

Nessuna configurazione obbligatoria per asta/formazione: tutto legge e scrive
file JSON in `data/`. Solo per l'esplorazione dell'API di lega servono le
variabili d'ambiente (mai in chat, mai committate):

```bash
export LEGHE_FC_USERNAME=...
export LEGHE_FC_PASSWORD=...
```

## Struttura dati (`data/`)

Tutto JSON, versionato in git salvo dove indicato.

| File | Contenuto |
|---|---|
| `teams.json` | Le 12 squadre: id, nome, proprietario, crediti totali/rimanenti |
| `players.json` | Pool completo dei giocatori Serie A (non solo posseduti): id, nome, ruolo, squadra, quotazione, status |
| `ownership.json` | Chi possiede quale giocatore: player_id, team_id, prezzo, data, modalità (asta/scambio/svincolo) |
| `matchday_stats.json` | Storico voti/fantavoti per giornata e avversario (da popolare a stagione in corso) |
| `injuries.json` | Storico infortuni |
| `market_log.json` | Log di ogni movimento di mercato (acquisti, scambi, svincoli) |
| `formazioni_correnti.json` | Snapshot probabili formazioni più recente (**non** versionato) |
| `formazioni_history.json` | Storico delle probabili formazioni nel tempo |

`config/league.json` contiene regole di scoring, moduli ammessi, requisiti di
rosa e `my_team_id` (da impostare la prima volta che si popolano i dati veri).

## Script (`scripts/`)

**Pre-asta**
```bash
python3 scripts/import_listone.py --csv listone.csv     # da export ufficiale fantacalcio.it
python3 scripts/import_fantadraft.py                     # in alternativa, da FantaDraft (fonte pubblica aggregata)
```

**Durante l'asta** — vedi `.claude/skills/asta/SKILL.md`
```bash
python3 scripts/asta.py assegna --player-id <id> --team-id <id> --prezzo <n>
python3 scripts/asta.py stato [--team-id <id>]
python3 scripts/asta.py disponibili --ruolo <P|D|C|A> --top 15
```

**Mercato post-asta**
```bash
python3 scripts/asta.py scambio --team-a <id> --team-b <id> \
    --players-a <id1,id2> --players-b <id3> \
    --credits-a-b <n> --credits-b-a <n>

python3 scripts/asta.py svincolo --player-id <id> --team-id <id> [--rimborso <n>]
```

**Formazione** — vedi `.claude/skills/formazione/SKILL.md`
```bash
python3 scripts/scrape_formazioni.py                     # aggiorna probabili formazioni pubbliche
python3 scripts/apply_formazioni_status.py [--dry-run]   # le applica allo status dei giocatori
python3 scripts/report_formazione.py --team-id <id> [--matchday N]
```

**Lega reale (API non ufficiale, sola lettura)**
```bash
python3 scripts/leghe_fc_inspect.py leghe
python3 scripts/leghe_fc_inspect.py rose --league-id <id>
python3 scripts/leghe_fc_inspect.py listone --league-id <id>
```
Client in `scripts/lib/leghe_fc_client.py`, verificato end-to-end su una lega
di test. Non scrive mai in `data/`: il mapping verso `teams.json`/
`ownership.json` per la lega vera va deciso e costruito a parte, dopo l'asta.

## Regole di fondo

- Mai inventare un voto, uno status o un dato storico mancante: se manca, va
  segnalato come "da verificare a mano".
- Lo storico contro un singolo avversario è quasi sempre un campione piccolo
  (1-2 incontri a stagione): va trattato come indizio debole, non come dato solido.
- Mai committare credenziali, jwt, token o dati personali reali: le uniche
  variabili sensibili sono `LEGHE_FC_USERNAME`/`LEGHE_FC_PASSWORD`, sempre da
  ambiente.

Dettagli, cosa è già stato verificato e cosa manca ancora: `CLAUDE.md`.
