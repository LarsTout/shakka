# Review WP-03, ronde 2
Oordeel: APPROVED

Ronde 2 (revisie 2). B-1 uit ronde 1 is echt en consistent opgelost. De keuze (optie a: vlaag op T = ruwe waarde van T+1h, laatste uur `None`) staat op alle plekken die ertoe doen, en die plekken spreken elkaar niet tegen:
- aanname A14;
- Ontwerp/Parser;
- parserregels 3 en 6, met de expliciete opmerking dat regel 5 ook voor `gust[0]` geldt;
- de docstrings van `ForecastHour` en `parse_forecast_response`;
- "Gevolgen voor latere WP's" (bindend voor WP-05, plus WP-07);
- RUNBOOK-stap 9;
- R10 (terugdraaipad).

De tests volgen dezelfde regel. `test_fixture_values_match_raw_json` en `test_fixture_sample_per_model` vergelijken met `raw_gust[i + 1]`. De KNMI-horizontest leidt zijn verwachting af met dezelfde verschoven regel. Nieuw zijn E33 tot en met E36 met concrete synthetische invoer. Ik heb de verwachte uitkomsten van E35, E36, `test_parse_all_none_after_shift_dropped` en `test_parse_partial_null_is_none` nagerekend, en ze kloppen met parserregel 6.

De nieuwe structuurregel (`time` oplopend in stappen van exact 3600 s) is veilig:
- met `timezone=GMT` en `timeformat=unixtime` bestaat er geen zomer- of wintertijdsprong;
- een live-call op 14-10-2026 met exact de capture-URL gaf 168 tijdstappen, allemaal van 3600 s, van 1791936000 (2026-10-14 00:00Z) tot 1792537200 (2026-10-20 23:00Z), wat ook de horizon in "Gevolgen voor WP-05" bevestigt;
- KNMI levert `null`-waarden, maar die zitten in de waardearrays, niet in `time`, dus de regel raakt KNMI niet;
- een lege `time` is expliciet geldig;
- de dedup-test (E19) is terecht omgezet naar een geïnjecteerde `fetch=`, omdat een dubbel tijdstip nu al een parsefout is.

De punten N-1 tot en met N-9 zijn verwerkt zoals beschreven in "Verwerking review". Er zijn geen nieuwe blokkerende punten gevonden.

## Blokkerend
Geen.

## Niet-blokkerend
N-1: `test_fixture_values_match_raw_json` eist "exact die drie waarden" uit de ruwe JSON, terwijl de parser negatieve en niet-eindige waarden omzet naar `None`. In de huidige fixture komt dat niet voor, maar na een nieuwe capture faalt de test dan zonder dat de parser fout zit. Advies: pas in de test op de verwachte waarden dezelfde opschoning toe als parserregel 5 (niet-eindig of `< 0` → `None`, richting `int(round(x)) % 360`), via een eigen kleine helper in de test en niet via de parser.

N-2: Ter informatie voor WP-05. ECMWF IFS en GFS zijn na enkele dagen niet meer uurlijks (ECMWF na ca. 90 h 3-uurlijks, later 6-uurlijks; GFS na 120 h 3-uurlijks). Open-Meteo interpoleert die waarden naar uren. Daar is "Preceding hour max" voor `wind_gusts_10m` in feite een benadering. De verschuiving van een uur is dan onschadelijk, maar de vlaag per uur is verder vooruit minder scherp. Dit verandert niets aan het ontwerp. Een korte zin hierover onder "Gevolgen voor latere WP's" (WP-05) kan helpen bij het kiezen van de drempels voor `gusty` en `too_gusty`.

N-3: A14 is "beslist door de orchestrator namens Lars; Lars beoordeelt dit nog" (R10). Dat is geen akkoord van Lars. Zorg dat Lars de keuze bevestigt vóórdat WP-05 wordt gebouwd. Daarna is terugdraaien niet meer goedkoop, omdat WP-05 de semantiek bindend overneemt.

N-4: Bij `test_parse_rejects_non_hour_time` (E17) kan de builder de verstoring op twee manieren aanbrengen. Verschuift hij één element met 1800 s, dan vangt regel 3 (tijdstap) de fout op in plaats van regel 7. De test assert alleen `ForecastParseError`, dus beide werken. Wil je echt regel 7 raken, verschuif dan `start` met 1800 s, zodat de stappen 3600 s blijven. Dit is optioneel.

## Gecontroleerde bronnen
- https://open-meteo.com/en/docs (opnieuw gecontroleerd op 14-10-2026):
  - kolom "Valid time": `wind_speed_10m` en `wind_direction_10m` "Instant", `wind_gusts_10m` "Preceding hour max";
  - de zin "Most weather variables are given as an instantaneous value for the indicated hour. Some variables like precipitation are calculated from the preceding hour as an average or sum.";
  - standaardtijdzone GMT en de unixtime-semantiek.
- Live-call: https://api.open-meteo.com/v1/forecast?latitude=52.4700,52.1000&longitude=4.5700,4.2700&hourly=wind_speed_10m,wind_direction_10m,wind_gusts_10m&models=knmi_harmonie_arome_netherlands,dwd_icon_seamless,ecmwf_ifs,ncep_gfs_seamless&wind_speed_unit=kn&timezone=GMT&timeformat=unixtime&forecast_days=7&cell_selection=sea
  - de respons is een lijst van 2;
  - `location_id` ontbreekt bij element 0 en is 1 bij element 1;
  - `utc_offset_seconds` is 0 en `hourly_units.time` is `unixtime`;
  - `time` loopt van 1791936000 tot 1792537200 in stappen van 3600 s;
  - de KNMI-snelheid is `null` vanaf ongeveer index 77; ECMWF en GFS zijn gevuld tot het laatste uur.
- `docs/WORK_PACKAGES.md`: conventie "Uurwaarden horen bij het uur dat begint op `valid_at`" (r. 103), WP-03-sectie (AC-1 t/m AC-8, contracten) en WP-05-contracten (`compute_consensus`, `gusty`/`too_gusty`).
- `docs/wp/WP-03/review.md` ronde 1 (B-1 en N-1 t/m N-9) tegenover "Verwerking review" in revisie 2.
- Er is nog geen blueprint voor WP-05 of WP-07, dus er is geen contractconflict mogelijk. De gevolgen staan als bindende afspraak in deze blueprint.
