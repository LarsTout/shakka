# Blueprint WP-26: Forecast-horizon 8 dagen (`days_ahead` 7 werkt)
Status: DRAFT
Revisie: 1

## Doel
De windverwachting 8 dagen ophalen in plaats van 7, zodat een alertregel met `days_ahead = 7` op de lokale dag vandaag+7 daglichturen met data heeft. Het Open-Meteo-gewicht blijft gelijk. Het alertformulier biedt 0 t/m 7 aan. Definitie en AC's: `docs/WORK_PACKAGES_V2.md`, sectie WP-26.

## Aannames
- **A1. Akkoord op 8 dagen is gegeven.** Lars heeft golf 1 laten starten. Er zijn geen kosten: `estimate_call_weight` geeft voor 7 en 8 dagen hetzelfde, want de factor `max(1, d/14)` blijft 1 (WP-03 A4 en A10).
- **A2. De uitleg "dag 7 heeft geen data" bestaat alleen als code-comment.** Hij staat bij `DAYS_AHEAD_UI_MAX` in `web/src/lib/forms.ts` en in WP-16 A8. In `AlertRuleForm.svelte` staat geen waarschuwing. De hint "Dagen ná vandaag: 3 betekent vandaag plus drie dagen." blijft staan. Het Svelte-bestand verandert dus niet.
- **A3. Geen databasewijziging.** De CHECK `alert_rules_days_ahead_range` staat al op 0–7. `DAYS_AHEAD_RANGE` (ingest) en `ALERT_DEFAULTS.days_ahead.max` (web) zijn al 7. `find_windows` (WP-07) ondersteunt 7 al. `FORECAST_HORIZON` in `shakka.jobs.inputs` is al 8 dagen en `SPOT_PAGE_DAYS` in `web/src/lib/page-data.ts` is al 8.
- **A4. ICON dekt dag 7 niet altijd volledig.** ICON global heeft een horizon van 7,5 dag (gecontroleerd, zie Externe afhankelijkheden). Of de uren 168–191 (UTC-dag vandaag+7) ICON-data hebben, hangt af van de laatste run. ECMWF IFS (15 dagen) en GFS (16 dagen) dekken dag 7 altijd (WP-03 A1). KNMI dekt ca. 2,5 dag (geen wijziging). De fixturetests zijn daarom zo opgezet dat ze niet afhangen van het moment van de capture (zie Testplan).
- **A5. Marine blijft 7 dagen.** Dat staat in "Buiten scope" van de WP. Op de spotpagina heeft dag 7 dus wind maar geen golven. Dat kan nu al: EWAM dekt ca. 80 uur en buiten de kust zijn er geen golven.
- **A6. Historische documenten blijven ongewijzigd.** `docs/WORK_PACKAGES.md` (WP-03 AC-2 en het contract `forecast_days: int = 7`) en de blueprints van WP-03 en WP-16 worden niet aangepast. `WORK_PACKAGES_V2.md` legt al vast dat WP-26 die contracten vervangt.
- **A7. De nachtelijke rand blijft bestaan (zie E1).** Een horizon van 9 dagen zou die rand dichten, met hetzelfde gewicht. Dat is buiten scope: de WP zegt 8, en het gat valt alleen in de nacht.

## Ontwerp
Dit is één constante in de ingest en één in de web. De rest is tests, een nieuwe fixture en documentatie.

**Ingest.** `DEFAULT_FORECAST_DAYS` in `shakka.openmeteo.forecast` gaat van 7 naar 8. `build_forecast_params`, `fetch_forecast` en `_chunk_weight` in `shakka.jobs.forecast` gebruiken die constante al. De job geeft geen `forecast_days` mee (WP-03 N-7), dus schatting en request blijven gelijk. Met `timezone=GMT` levert de request 192 uren, van vandaag 00:00Z tot en met vandaag+7 23:00Z. De lokale dag vandaag+7 (Amsterdam) loopt van 22:00Z of 23:00Z op UTC-dag +6 tot 22:00Z of 23:00Z op UTC-dag +7. Die dag valt dus volledig in de respons, behalve tijdens het randgeval E1.

**Koppeling.** Een nieuwe test borgt dat de horizon past bij de hoogste `days_ahead`: `DEFAULT_FORECAST_DAYS == DAYS_AHEAD_RANGE[1] + 1`. Wie later een van de twee verandert, ziet dan meteen dat de andere mee moet.

**Fixture.** `forecast_2loc_4models.json` wordt opnieuw opgehaald met `forecast_days=8`. `test_fixture_matches_current_params` blijft de bewaker en dwingt af dat `CAPTURE_URL` en de parameters gelijk zijn. Eén bestaande fixturetest gaat ervan uit dat ICON een waarde heeft in het laatste uur. Die test wordt beperkt tot ECMWF en GFS (A4). Twee nieuwe tests leggen de vorm van 8 dagen vast en tonen dat dag 7 data heeft.

**Web.** `DAYS_AHEAD_UI_MAX` gaat van 6 naar 7, met een nieuwe comment. `daysAheadOptions` verandert niet. Het voegt `current` alleen toe als die er nog niet in staat, en met maximum 7 gebeurt dat in de praktijk niet meer. Een guard-test legt vast dat `DAYS_AHEAD_UI_MAX` gelijk is aan `ALERT_DEFAULTS.days_ahead.max`.

**Zichtbaar effect.** Een regel met `days_ahead = 7` kan nu een window en een push opleveren op dag 7. Op de spotpagina toont de achtste dag data in plaats van "nog geen data". Op dag 7 rekent de consensus met 2 of 3 modellen, dus de confidence is daar meestal lager. Dat gedrag bestaat al voor dagen waarop KNMI ontbreekt (WP-05).

**Raakvlak met WP-27.** WP-26 wijzigt in de RUNBOOK alleen §9 (forecast), WP-27 alleen §10 (getij) en de secties over `doctor` en het gebruiksrapport. Geen van beide wijzigt hetzelfde Python-bestand.

## Bestanden
| Bestand | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/openmeteo/forecast.py` | wijzigen | `DEFAULT_FORECAST_DAYS: Final = 8`. Niets anders. |
| `ingest/tests/fixtures/openmeteo/forecast_2loc_4models.json` | vervangen | Een nieuwe, ongewijzigde capture met `forecast_days=8` (URL hieronder). |
| `ingest/tests/fixtures/openmeteo/README.md` | wijzigen | Regel `forecast_2loc_4models.json`: nieuwe opnamedatum en URL met `forecast_days=8`. De CC BY 4.0-regel blijft. |
| `ingest/tests/test_openmeteo_forecast.py` | wijzigen | `CAPTURE_URL` en `CAPTURE_DATE` bijwerken, `"forecast_days": "8"` en `DEFAULT_FORECAST_DAYS == 8` in `test_build_params_exact`, parametrisering van de last-hour-test aanpassen, drie nieuwe tests (zie Testplan). |
| `ingest/tests/test_budget.py` | wijzigen | Nieuwe test voor AC-2. |
| `ingest/tests/test_windows.py` | wijzigen | Nieuwe test voor AC-3. |
| `docs/RUNBOOK.md` | wijzigen | §9: één regel **Horizon.** na **Modellen en cel.**, en `forecast_days=8` in de curl-URL. |
| `web/src/lib/forms.ts` | wijzigen | `DAYS_AHEAD_UI_MAX = 7`, met een nieuwe comment. |
| `web/test/forms.test.ts` | wijzigen | `daysAheadOptions`-verwachtingen naar 0 t/m 7, plus de guard tegen `ALERT_DEFAULTS`. |
| `web/test/alert-rule-form.test.ts` | wijzigen | De test "no day 7 by default" wordt een test op optie 7 met label (AC-4). De test "row already has it" controleert dat 7 er precies één keer staat. |

## Interfaces en contracten
**`shakka.openmeteo.forecast`** (vervangt het WP-03-contract `forecast_days: int = 7`):
```python
DEFAULT_FORECAST_DAYS: Final = 8
def build_forecast_params(
    locations: Sequence[SpotLocation], *, forecast_days: int = DEFAULT_FORECAST_DAYS
) -> dict[str, str]: ...          # ongewijzigd behalve de default; "forecast_days": "8"
def fetch_forecast(
    http: httpx.Client, locations: Sequence[SpotLocation], *,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ForecastHour]: ...      # ongewijzigd
```
`build_forecast_params(FIXTURE_LOCATIONS)` is exact:
`{"latitude": "52.4700,52.1000", "longitude": "4.5700,4.2700", "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m", "models": "knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless", "wind_speed_unit": "kn", "timezone": "GMT", "timeformat": "unixtime", "forecast_days": "8", "cell_selection": "sea"}`. De sleutelvolgorde is ongewijzigd.

**`shakka.jobs.forecast`**: ongewijzigd. `_chunk_weight(n)` blijft `estimate_call_weight(n, 3, 4, DEFAULT_FORECAST_DAYS)` en geeft 1,2 per locatie.

**Fixture-capture-URL** (`CAPTURE_URL`, README en RUNBOOK §9, letterlijk):
```
https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=8&cell_selection=sea
```
Vorm van de fixture: een lijst van 2 elementen. Per element heeft `hourly.time` 192 integers, met stap 3600, en `time[0]` is 00:00Z van `CAPTURE_DATE` (formaat `YYYY-MM-DD`, de UTC-datum van de capture).

**`web/src/lib/forms.ts`**:
```ts
export const DAYS_AHEAD_UI_MAX = 7; // WP-26: equals the CHECK max; forecast covers local today+7
export function daysAheadOptions(current: string): string[]; // ongewijzigd; '' -> ['0'..'7']
```
Het label van de optie blijft `${n} (${daysAheadText(n)})`. Voor 7 is dat `7 (vandaag plus 7 dagen)`.

**RUNBOOK §9, nieuwe regel** (letterlijk, na **Modellen en cel.**):
> **Horizon.** 8 dagen (`forecast_days=8`, 192 uur vanaf vandaag 00:00 UTC), zodat een alertregel met `days_ahead` 7 de hele lokale dag vandaag+7 heeft. Het gewicht is gelijk aan dat van 7 dagen. KNMI dekt ca. 2,5 dag en ICON 7,5 dag, dus aan het eind van dag 7 rekenen soms alleen ECMWF en GFS (lagere zekerheid).

## Edge cases
- E1. Tussen 22:00/23:00Z en 00:00Z is lokaal al de volgende dag, en lokaal vandaag+7 is UTC-dag +8. → Die dag heeft dan alleen nachturen; na de run van 00:xxZ is hij compleet. Dit wordt geaccepteerd (A7).
- E2. ICON heeft geen data in de late uren van UTC-dag +7. → Die uren hebben 2 modellen (ECMWF en GFS) en een lagere confidence (WP-05). Er is geen fout en geen code-wijziging.
- E3. Het laatste uur van de respons (vandaag+7 23:00Z) heeft `gust_kn = None` (WP-03 A14). → Dat is lokaal 00:00 of 01:00 op dag +8, dus buiten daglicht en buiten `days_ahead` 7. Geen effect.
- E4. Een bestaande regel heeft al `days_ahead = 7`. → Optie 7 staat er precies één keer in en is geselecteerd. Er verschijnt geen extra optie.
- E5. Budget. → Ongewijzigd, want 25 spots × 1,2 = 30 calls per run. `test_plan_makes_no_requests_and_no_writes` (61,2 voor 51 spots) en `test_job_records_usage_after_success` (1,2) blijven groen zonder aanpassing.
- E6. Opslag. → `forecast_hours` groeit met hooguit 24 uur × 4 modellen per spot, ca. +11% op (48 + 192) uur. Dat is verwaarloosbaar ten opzichte van 500 MB.
- E7. De fixture wordt opgehaald terwijl ICON dag 7 maar gedeeltelijk dekt. → De tests blijven groen (A4). Er is geen eis aan het tijdstip van de capture.
- E8. De web en de ingest worden niet tegelijk uitgerold. → Beide gaan via dezelfde promotie `develop` → `main`. Zou de web eerder live staan, dan geeft dag 7 tijdelijk geen window, zoals nu. Er gaat niets stuk.

## Testplan
**AC-1** (`tests/test_openmeteo_forecast.py`, fixture `forecast_2loc_4models.json`, nieuw opgehaald):
- `test_build_params_exact` (bijgewerkt): `"forecast_days": "8"` en `DEFAULT_FORECAST_DAYS == 8`. De sleutelvolgorde is ongewijzigd.
- `test_fixture_matches_current_params` (ongewijzigd): `CAPTURE_URL` en de huidige parameters zijn gelijk.
- `test_fixture_has_eight_days` (nieuw): per locatie 192 elementen in `hourly.time`, alle stappen 3600, `time[0] % 86400 == 0`, en `time[0]` als UTC-datum is gelijk aan `CAPTURE_DATE`.
- `test_fixture_covers_day_seven` (nieuw): per locatie hebben ECMWF en GFS een `wind_speed_10m`-waarde (niet null) op alle indices 168–191, en ICON op minstens één index 168–191. Na het parsen bestaan er rijen met `valid_at >= time[0] + 7 dagen` voor `ecmwf` en `gfs`. Dit is de offline tegenhanger van AC-6.
- `test_fixture_last_hour_gust_is_none` (aangepast): wordt geparametriseerd over `[ModelKey.ECMWF, ModelKey.GFS]` in plaats van ook ICON (A4). De rest blijft gelijk.
- `test_forecast_days_cover_max_days_ahead` (nieuw): `DEFAULT_FORECAST_DAYS == DAYS_AHEAD_RANGE[1] + 1`, met `DAYS_AHEAD_RANGE` uit `shakka.domain.alerts`.
- Alle andere bestaande fixture- en parsertests draaien ongewijzigd groen op de nieuwe fixture, ook `test_fixture_knmi_horizon` en `test_job_fixture_end_to_end` (`calls == 2.4`).

**AC-2** (`tests/test_budget.py`):
- `test_weight_eight_days_equals_seven` (nieuw): `estimate_call_weight(25, 3, 4, 8) == estimate_call_weight(25, 3, 4, 7) == 30.0`.

**AC-3** (`tests/test_windows.py`, helpers `go_run` en `rule` uit `alert_fixtures`):
- `test_days_ahead_seven_reaches_local_today_plus_seven` (nieuw): `now = NOW` (wo 15-07-2026 08:00 lokaal), `go_run(utc(2026, 7, 22, 10), 3)`. Met `rule(min_go_hours=1, days_ahead=7)` is er precies één window `(utc(2026,7,22,10), utc(2026,7,22,13))`. Met `days_ahead=6` is het resultaat `[]`.

**AC-4** (`cd web && npm run check && npm test && npm run build`):
- `forms.test.ts` › `daysAheadOptions` (bijgewerkt): `''` geeft `['0' … '7']`, `'3'` heeft lengte 8, en `'7'` heeft lengte 8 met `'7'` precies één keer.
- `forms.test.ts` › `DAYS_AHEAD_UI_MAX matches the contract max` (nieuw): `DAYS_AHEAD_UI_MAX === ALERT_DEFAULTS.days_ahead.max`.
- `alert-rule-form.test.ts` › `offers day 7 with a Dutch label and no warning` (vervangt "no day 7 by default"): de opties zijn `['', '0', …, '7']`. De option met waarde `7` heeft de tekst `7 (vandaag plus 7 dagen)`. Het formulier bevat nergens de tekst "geen data", en de hint van `days_ahead` is `standaard: vandaag plus 3 dagen (…)`, net als nu.
- `alert-rule-form.test.ts` › `offers day 7 when the row already has it` (aangepast): met `days_ahead: 7` staat `'7'` precies één keer in de opties en is hij geselecteerd.

**AC-5**: `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .` is volledig groen.

**AC-6** (`NEEDS_LARS`): de query uit de WP, na de promotie naar `main` en één uurlijkse run. Draai hem bij voorkeur tussen 06:00 en 22:00 UTC. Vlak na 00:00 UTC kan ICON nog 0 rijen op dag +7 hebben, totdat de 00Z-run binnen is (A4).

## Externe afhankelijkheden
- Geen nieuwe packages.
- Open-Meteo Forecast API, `GET https://api.open-meteo.com/v1/forecast`. De parameters zijn ongewijzigd, behalve `forecast_days=8` (bereik 0–16). Overgenomen uit "Gecontroleerde externe documentatie" van WORK_PACKAGES_V2 en uit de WP-03-blueprint, niet opnieuw gecontroleerd: https://open-meteo.com/en/docs
- Het gewicht verandert niet tot 14 dagen. Overgenomen uit WORK_PACKAGES_V2 en WP-03 A4: https://open-meteo.com/en/pricing
- De horizon van ICON global is 7,5 dag, ICON-EU 5 dagen en ICON-D2 2 dagen, en ICON global wordt elke 6 uur ververst. **Zelf gecontroleerd** op 28-10-2026: https://open-meteo.com/en/docs/dwd-api. De pagina zegt niet of de runs van 06Z en 18Z korter lopen; daarom zijn de tests niet afhankelijk van ICON op dag 7.
- ECMWF IFS (15 dagen) en GFS (16 dagen) zijn overgenomen uit WP-03 A1.

## Risico's
- R1. ICON is op dag 7 vaker afwezig dan verwacht, waardoor de confidence daar meestal "medium" of lager is. Dat is acceptabel: verder vooruit hoort minder zekerheid. Er is geen actie nodig.
- R2. Na de uitrol krijgen gebruikers met `days_ahead = 7` voor het eerst meldingen voor dag 7. Dat is precies het doel. De deduplicatie van WP-08 werkt ongewijzigd.
- R3. De capture loopt over het netwerk vanaf de machine van de builder. Lukt dat niet, dan blokkeert stap 1. De builder verzint geen fixture en wijzigt de JSON niet met de hand.

## Buiten scope
- Marine (`DEFAULT_MARINE_DAYS` blijft 7), getij, `DEFAULT_DAYS_AHEAD` (blijft 3), `cell_selection` (WP-32).
- Een horizon van 9 dagen of meer (A7).
- `pipeline_fixtures.py`: de fakes hebben `forecast_days: int = 7` als ongebruikte default. Die blijven zo, want de job geeft het argument nooit mee.
- `AlertRuleForm.svelte`, migraties, RLS en de pgTAP-tests.
- Historische docs (A6) en de marine-regels in RUNBOOK §12.

## Gevolgen voor latere WP's
- **WP-32** (`cell_selection` per spot) gaat uit van `build_forecast_params` met `forecast_days=8` en van deze fixture, met 192 uren. Haalt WP-32 de fixture opnieuw op, dan blijven `test_fixture_has_eight_days` en `test_fixture_covers_day_seven` gelden.
- Wie `DAYS_AHEAD_RANGE` of `DEFAULT_FORECAST_DAYS` verandert, krijgt een rode `test_forecast_days_cover_max_days_ahead`. De web-guard bewaakt `DAYS_AHEAD_UI_MAX` tegen het contract.

## Stappenplan voor de builder
1. **Ingest-constante en fixture.**
   - Zet `DEFAULT_FORECAST_DAYS = 8`.
   - Haal de fixture op met de curl uit RUNBOOK §9, met de nieuwe URL, vanuit de repo-root. Gebruik `--fail` en wijzig de JSON niet.
   - Werk `CAPTURE_URL` en `CAPTURE_DATE` (UTC-datum van de capture) en de README-regel bij.
   - Pas `test_build_params_exact` en `test_fixture_last_hour_gust_is_none` aan en voeg `test_fixture_has_eight_days`, `test_fixture_covers_day_seven` en `test_forecast_days_cover_max_days_ahead` toe.
   - `uv run pytest tests/test_openmeteo_forecast.py tests/test_job_forecast.py` moet groen zijn.
2. **AC-2.** Voeg `test_weight_eight_days_equals_seven` toe aan `tests/test_budget.py`. Groen.
3. **AC-3.** Voeg `test_days_ahead_seven_reaches_local_today_plus_seven` toe aan `tests/test_windows.py`. De test is groen zonder productiewijziging; is hij rood, stop dan en meld het.
4. **Ingest volledig.** `uv run pytest`, `uv run ruff check .` en `uv run ruff format --check .` moeten groen zijn.
5. **Web.** Zet `DAYS_AHEAD_UI_MAX = 7` met de comment uit "Interfaces". Werk `forms.test.ts` en `alert-rule-form.test.ts` bij volgens het Testplan. Draai `npm run check && npm test && npm run build`.
6. **RUNBOOK §9.** Voeg de regel **Horizon.** letterlijk toe en zet `forecast_days=8` in de curl-URL. Wijzig geen andere secties (WP-27 werkt in §10 en verder).
7. Commit per stap (Engelse messages), en open de PR naar `develop`. AC-6 komt als `NEEDS_LARS` in `verification.md`.
