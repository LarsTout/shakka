# Review WP-26, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

## Niet-blokkerend
N-1: `test_fixture_covers_day_seven` eist ICON op minstens één index 168-191, maar tussen ca. 00:00Z en het binnenkomen van de 00Z-run (ca. 03-04Z) loopt de laatst beschikbare ICON-run (18Z, horizon 7,5 dag) af rond index 150. E7 ("geen eis aan het tijdstip van capture") klopt dan niet. Laat de ICON-assertie vervallen, of voeg aan stap 1 toe: capture niet tussen 00:00 en 04:00 UTC.
N-2: WP-27 kan ook `tests/test_budget.py` aanpassen (RWS-verbruik); voeg de AC-2-test onderaan toe om een mergeconflict te beperken.
N-3: E5 noemt `test_plan_makes_no_requests_and_no_writes` (61,2 voor 51 spots) als ongewijzigd groen; de builder moet dat bevestigen (`_chunk_weight` blijft 1,2 per locatie, dus klopt rekenkundig).

## Zelf gecontroleerd
- Server-side en gewicht (AC-2): `DEFAULT_FORECAST_DAYS` staat alleen in `ingest/src/shakka/openmeteo/forecast.py:18`; `jobs/forecast.py` gebruikt de constante voor request en `_chunk_weight`. `budget.py:35` geeft `max(1.0, d/REFERENCE_DAYS)`, dus 8 dagen geeft hetzelfde gewicht als 7. Er komt geen browser-aanroep bij.
- Contracten: `DAYS_AHEAD_RANGE = (0, 7)` (`domain/alerts.py:28`) en `DAYS_AHEAD_UI_MAX = 6` (`web/src/lib/forms.ts:27`) kloppen met de blueprint. De bestaande tests zijn consistent met de beschreven wijzigingen (`CAPTURE_DATE`, `forecast_days=7` op regel 38 en 203, `DEFAULT_FORECAST_DAYS == 7` op regel 217, ICON in de last-hour-parametrisering op regel 149). De bestaande `test_fixture_knmi_horizon` en `test_fixture_sample_per_model` (indices 0, 12, 24) zijn onafhankelijk van de lengte.
- Omvang en raakvlak met WP-27: ingest-productiecode is één regel. RUNBOOK §9 (regels 94-123) is gescheiden van §10 (getij, regel 124); de curl-URL op regel 119 ligt binnen §9. Geen overlap in Python-bronbestanden.
- Rekenen: 192 uur geeft 00:00Z vandaag tot en met vandaag+7 23:00Z. De lokale dag +7 past daarin, behalve in het nachtelijke randgeval E1. Dat klopt.
- Geen externe bronnen opnieuw gecontroleerd.
