# Afwijkingen WP-04

## D1. Review-punten N-3, N-4, N-5, N-6 overgenomen (klein, binnen de blueprint)
Op verzoek van de orchestrator, uit `review.md` (APPROVED, niet-blokkerend):
- N-3: een lege (of na dedupliceren lege) fetcher-uitvoer geeft `ValueError("fetch returned no extremes")` in de job. Het station komt in `failed` en zijn venster wordt niet gewist. Test: `test_empty_fetch_keeps_existing_window`.
- N-4: `rws_station` wordt in `run_tide_ingest` vooraf gefilterd op `STATION_CODE_RE`. Ongeldige codes gaan direct naar `failed`/`errors` (zonder fetch en zonder `in_filter`). Test: `test_invalid_station_code_fails_only_that_station`.
- N-5: beide parsers zetten structureel afwijkende JSON (ontbrekende sleutels, verkeerde types) om in `TideFetchError("<label>: unexpected response")`. Test: `test_structural_errors`, `test_parse_stations_errors`.
- N-6: typemetingen met `Kwaliteitswaardecode` `99` worden overgeslagen. Test: `test_quality_99_type_skipped`.

Impact: geen contractwijziging; alleen strengere foutafhandeling.

## D2. Stap 2 stopregels: allemaal geslaagd, geen afwijking van A2/A3
Echte DDAPI20-respons (hoekvanholland, 9 dagen) bevestigt de aannames: twee kanalen met `ProcesType` `astronomisch` en `Groepering` `GETETBRKD2`: (1) `Grootheid` `NVT`, `Hoedanigheid` `NVT`, `Eenheid` `DIMSLS`, `Typering` `GETETTPE`, 35 metingen, teksten `hoogwater` en `laagwater`; (2) `WATHTE`/`NAP`/`cm`, 35 metingen. Elk niveautijdstip heeft een type op hetzelfde tijdstip. `Tijdstip` heeft `+01:00` ook in oktober (CEST). Catalogus: 101 stations, `hoekvanholland` aanwezig. Het venster bevat geen aggers, dus `laagwater 1/2` en `topagger` zijn alleen synthetisch getest. `EXPECTED_EXTREMES = 35`.
Het capturescript is na stap 3 een tweede keer gedraaid (om `catalogue_station_count` met `parse_stations` te vullen); de fixtures zijn daarmee van de tweede run.

## D3. Kleine, niet-blokkerende punten
- Het `tides stations`-commando geeft bij `--search "hoek van holland"` twee stations (ook `hoekvanholland.maeslantkering.beneden.noord`). Dat is data uit RWS, geen fout.
- AC-5 (lokale stack) niet uitgevoerd: Docker is aanwezig, maar de daemon is vanuit deze sandbox niet bereikbaar (`permission denied` op `/var/run/docker.sock`). Niet blokkerend, net als bij WP-01 D1; gaat naar de verifier of Lars.
- `uv` stond niet op de PATH van de shell; gebruikt via `~/.local/bin/uv`.
- RUNBOOK-sectienummer 9 kan conflicteren met WP-02/WP-03 (zie review N-8); bij een merge hernummeren en alles behouden.
