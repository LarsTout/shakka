# Review WP-27, ronde 1
Oordeel: APPROVED

Lichte review (S-WP): harde regels, contracten en testbaarheid. Geen ESCALATE nodig: de blueprint raakt geen RLS, grants, tokens, persoonsgegevens of geld, en de offshore-regel blijft onaangeroerd (de evaluatie is niet in scope).

## Blokkerend
Geen.

## Niet-blokkerend
N-1: De twee afwijkingen van de WP-tekst (A2 som per run, A7 `set`/`unset`) laten de AC toetsbaar: de totalen `calls == requests == n` zijn identiek, en de tests toetsen de Engelse woorden exact. Leg ze wel vast in `docs/wp/WP-27/deviations.md` (of bij de PR), want A7 beroept zich op een bevestiging van Lars die ik niet kan nalezen.
N-2: Stap 6 van `run_tide_ingest` noemt alleen `DatabaseError`. `BudgetGuard.record` kan ook `ValueError` gooien (onbekende bron, negatieve requests), maar dat is niet bereikbaar met `n > 0` en `SOURCE_RWS`. Geen actie nodig; houd het `except` bewust smal.
N-3: De wijziging in `pipeline.py` (importregel plus één `raise`) en in `Settings` (alleen de eerste regel van de URL-validator) is minimaal. De tekstconflicten met WP-26 beperken zich tot `docs/RUNBOOK.md`, en in `test_pipeline.py` alleen als WP-26 dezelfde tests raakt. Dat risico staat al in R4.

## Zelf gecontroleerd
- Geen waarden in `doctor` of logs. Er staat alleen de naam met `set` of `unset`, de exceptieklasse (`type(exc).__name__`, nooit `str(exc)`), en `db_error_summary` (`jobs/inputs.py:65`, geeft alleen status en code, nooit de melding). De `invalid SUPABASE_SECRET_KEY`-regel bevat een vaste tekst. `ValidationError` wordt in `doctor.py` al met `include_input=False` verwerkt. De tests (`SECRET not in out`, `testref not in out`, waarden als `TESTAPPURL` niet in de uitvoer) kunnen falen. Verdere meldingen in de log, `TideBudgetExhausted` en `api_usage: DatabaseError (HTTP 500)`, bevatten geen geheimen. Dit is de kern van afspraak 8.
- `BudgetGuard.record(source, weight, *, now, requests)` (`budget.py:106`) bestaat, `SOURCE_RWS` zit in `API_USAGE_SOURCES`, en de Open-Meteo-filter gebruikt het prefix `open_meteo_` (`budget.py:89`). Er is dus geen circulaire import (`jobs/inputs.py` importeert niets uit `jobs/tides.py`) en RWS telt niet mee voor Open-Meteo.
- `pipeline.py:211` gooit nu een kale `TimeoutError`. De enige test die de tekst toetst is `test_pipeline.py:630`; de blueprint past die aan. Elders (web, docs) staat de tekst niet in een contract.
- Puurheidscheck: de bestaande checker meldt `utcnow` en `time.time` al zonder aanroep (`test_domain_purity.py:126-132`). De nieuwe regel hoeft dus alleen `now` en `today` te dekken. In `domain/` komen alleen `self.now`/`stats.now` en `getattr(self, name)` voor; die blijven toegestaan.
- Volgorde: `(s in last, last.get(s, now), s)` zet nooit opgehaalde stations eerst, dan oudste eerst, dan alfabetisch. Dit is gelijkwaardig aan de oude 20-uursregel (`last > now - 20 h`, strikt).
