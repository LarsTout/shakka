## WP-26: Forecast-horizon 8 dagen (`days_ahead` 7 werkt)

**Wat er nu werkt**
- De forecast-ingest haalt 8 dagen op in plaats van 7 (`DEFAULT_FORECAST_DAYS = 8`). Het Open-Meteo-gewicht blijft gelijk (`estimate_call_weight(…, 8) == …(…, 7)`, getest).
- Een nieuwe fixture met 192 uur per locatie. Een test op `find_windows` laat zien dat `days_ahead=7` een window geeft op lokaal vandaag+7, en `days_ahead=6` niet.
- In `/alerts` kun je bij "dagen vooruit" nu 0 t/m 7 kiezen (`DAYS_AHEAD_UI_MAX = 7`), bewaakt tegen `ALERT_DEFAULTS`.
- RUNBOOK §9 is bijgewerkt (curl-URL en horizonregel).

**Zelf proberen** (vanaf `develop`)
- `cd ingest && uv run pytest tests/test_openmeteo_forecast.py tests/test_budget.py tests/test_windows.py`
- `cd web && npm run dev`, dan naar `/alerts`: de keuze "dagen vooruit" loopt tot 7.

**Open (NEEDS_LARS)**
- AC-6: draai na de promotie naar `main` en één uurlijkse run de query uit `docs/wp/WP-26/verification.md`. Doe dat bij voorkeur tussen 06:00 en 22:00 UTC: ICON global reikt ongeveer 7,5 dag, dus niet altijd tot het eind van dag 7.

**Niet-blokkerende reviewpunten**
- De ICON-assertie voor dag 7 is uit de fixturetests gehaald, zodat ze niet afhangen van het tijdstip van de capture (N-1). De last-hour-test geldt nu voor ECMWF en GFS.
- Bewust geaccepteerd: tussen ongeveer 22:00 en 00:00 UTC heeft lokaal vandaag+7 alleen nachturen (blueprint E1).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
