# Review WP-07, ronde 1
Oordeel: CHANGES_REQUIRED

De blueprint is grondig. Hij dekt alle zes AC's met concrete tests en houdt zich aan de scope. De harde regel over offshore is op vier plekken geborgd: de override, `AlertRule`, het vangnet in `find_windows` en invariant 6 van `Window`. Bij alle vier de modellen valideert `model_copy` opnieuw. De tijdsemantiek klopt; ik heb elke verwachte uitkomst in de AC-3-tabel nagerekend (zie onderaan). Er is één blokkerend punt. Het zit op de grens met de database en is klein om op te lossen.

## Blokkerend

B-1: De databasekolom `time` accepteert `24:00:00`, maar `AlertRuleOverride` weigert die waarde. De overdracht aan WP-10 vangt alleen fouten uit `resolve_rule` af, niet die uit `from_row`.
- **Waar:** A7 ("alles wat de database accepteert [is] ook hier geldig, en omgekeerd"), de tabel `AlertRuleOverride` (`earliest_local`/`latest_local`), E12 en "Gevolgen voor latere WP's", WP-10.
- **Waarom:**
  - Postgres `time without time zone` loopt van `00:00:00` t/m `24:00:00`. De CHECK `alert_rules_time_window` staat bijvoorbeeld `earliest_local = 17:00, latest_local = 24:00` toe.
  - PostgREST geeft dan `"24:00:00"` terug. Pydantic (speedate, uur 0–23) en `datetime.time` kunnen dat niet weergeven, dus `AlertRuleOverride.from_row` geeft een `ValidationError`.
  - Elke ingelogde gebruiker kan zo'n rij via de PostgREST-API schrijven, buiten de UI om. RLS staat `update` op de eigen `alert_rules` toe.
  - Volgt WP-10 de blueprint letterlijk ("vang de `ValueError` uit `resolve_rule` af"), dan stopt de alertjob voor alle gebruikers. Dat is precies het risico dat R3 voor A6 wil voorkomen.
  - De bewering over pariteit in A7 klopt dus niet.
- **Voorstel:** kies één van twee richtingen en leg die vast.
  - (a) Behandel `"24:00"`/`"24:00:00"` bij `latest_local` expliciet als "geen bovengrens" (`None`). Dat is semantisch hetzelfde, want `t < 24:00` geldt altijd. `earliest_local = 24:00` blijft een `ValidationError`, of krijgt een eigen gedocumenteerde regel.
  - (b) Laat de weigering staan, maar:
    - schrap "en omgekeerd" in A7 en noem `24:00:00` als bekende uitzondering;
    - voeg een edge case en een test toe (`from_row` met `latest_local: "24:00:00"` geeft een `ValueError`);
    - schrijf onder "Gevolgen", WP-10, dat het samenstellen per favoriet (`AlertRuleOverride.from_row`, `ProfileDefaults.from_row` en `resolve_rule`) in één `try` staat die `ValueError` afvangt, de favoriet overslaat en het meldt.
  - Optioneel bij beide: zet onder WP-16 dat de UI geen `24:00` schrijft.

## Niet-blokkerend

N-1: De strengheid van `AlertRule` is niet volledig beschreven.
- De tabel van `AlertRule` noemt bij `weekdays`, `min_go_hours` en `days_ahead` geen strikte int.
- `test_weekday_out_of_range` verwacht wel een `ValidationError` voor `[True]` bij `AlertRule`. In lax-modus accepteert pydantic `bool` als `int`, en ook als `float` (conversietabel).
- Schrijf in de tabel van `AlertRule` expliciet: elementen van `weekdays` strikt int, `min_go_hours` en `days_ahead` strikt int. Dan hoeft de builder dit niet uit de test af te leiden.

N-2: A7 wijkt af van de letterlijke tekst van het contract.
- Het contract zegt "velden gelijk aan de kolommen van `alert_rules` behalve de sleutels". `updated_at` is geen sleutel, maar valt er in de blueprint wel buiten.
- De keuze is verdedigbaar. Neem hem op als bewuste afwijking, zodat de orchestrator WORK_PACKAGES kan bijwerken.

N-3: De docstring van `contracts_export` in `ingest/src/shakka/cli.py` wordt onvolledig.
- Hij luidt nu "Write reason codes, direction classes and confidence labels as JSON."; na deze WP schrijft de opdracht ook de alert-defaults.
- De blueprint verbiedt elke wijziging aan `cli.py`. Sta die ene docstringregel toe, of schrijf de docstring algemeen ("Write the generated JSON contracts.").

N-4: De betekenis van `min`/`max` bij `max_kn` in `alert_defaults.json` is onduidelijk.
- Volgens A5/E3 kan de effectieve `max_kn` 65 zijn, terwijl `max` 60 zegt.
- Schrijf onder "Betekenis" dat `min`/`max` de invoergrenzen zijn voor waarden van regel en profiel (DB-CHECK), en geen grenzen voor de effectieve waarde. Dat voorkomt dat WP-16 een afgeleide 65 als ongeldig toont.

N-5: Het interfacevoorbeeld importeert `Mapping` en `Sequence` niet (uit `collections.abc`). `date` wordt alleen gebruikt als het als annotatie terugkomt; anders geeft ruff `F401`. Het is cosmetisch, maar de builder kopieert het voorbeeld waarschijnlijk.

N-6: Er is geen test voor continuïteit bij de overgang naar zomertijd. Voeg naast E31 (wintertijd) een geval toe voor 2027-03-28:
- invoer: go op 00:00Z, 01:00Z en 02:00Z (lokaal 01:00 CET, 03:00 CEST en 04:00 CEST);
- verwacht: één window van 3 uur;
- doel: aantonen dat het lokale "gat" van 02:00 geen split geeft.

N-7: `test_ranges_match_migration` is voor `alert_rules_weekdays_iso` niet scherp genoeg.
- De blueprint zegt "de getallen uit `alert_rules_weekdays_iso`", maar het blok bevat ook `cardinality(weekdays) >= 1`.
- Specificeer dat de getallen uit `array[...]` komen, net als het bestaande `_sql_list` in `test_contracts.py`.
- Noem ook waar de helper voor de lijst van `dir_classes` staat (`alert_fixtures.py` naast `migration_range`).

N-8: `test_safety_grid` legt `now`, `min_go_hours` en het startuur niet vast.
- Leg vast: `rule(min_go_hours=1, dir_classes=subset)`, `now = utc(2026,7,15,6)` en een reeks vanaf `utc(2026,7,15,8)`.
- Zonder die waarden kan de test vacuüm slagen, bijvoorbeeld als alles vóór `now` valt.

N-9: E15 kan voor gebruikers verrassend zijn: `latest_local = 20:30` laat het uur 20:00–21:00 nog meetellen. Advies onder "Gevolgen", WP-16: bied in de UI alleen hele uren aan voor `earliest_local`/`latest_local`.

N-10: `days_ahead = 3` betekent "vandaag plus drie dagen", dus vier kalenderdagen. Het label "Dagen vooruit" in `FIELD_LABEL_NL` maakt dat niet duidelijk. Overweeg een advies voor WP-16 over de uitlegtekst; dit is niet kritiek.

N-11: `test_resolve_rejects_offshore_even_if_override_bypassed` gebruikt `model_construct` in een test.
- Dat mag: de ban in `test_no_model_construct_in_src` geldt alleen voor `src`.
- WP-05 zegt "Gebruik geen `model_construct`", maar alleen voor fixtures van `HourEvaluation`.
- Zet er een commentaar bij dat het om een bewuste omzeiling gaat, zodat de verifier geen bevinding maakt.

Over de voorgestelde defaults: `min_go_hours = 2` en `days_ahead = 3` zijn onderbouwd. Het argument voor `days_ahead` klopt met WP-03 A10, met de ruis in de deduplicatie van WP-08 en met de dekking van Harmonie. Het argument voor `min_go_hours` klopt met de tolerantie van ±1 uur in WP-08. Lars toetst ze; daarvoor zijn ze geen blokkerend punt.

Nagerekend en correct bevonden:
- **Kalender:** 2026-07-15 is woensdag, 07-17 vrijdag, 07-18 zaterdag, 07-19 zondag en 2026-11-04 woensdag. Op 2026-10-25 om 01:00Z eindigt de zomertijd; 00:00Z en 01:00Z zijn dan allebei lokaal 02:00.
- **AC-3-tabel:** alle verwachte windows kloppen met A8, A9 en A10, inclusief het geval van de lokale datum in `test_days_ahead_zero_and_local_today`.
- **Integratietest:** de spot uit `make_spot` met `model_hours` (wind 20, vlaag 24, 4 modellen, 270°) geeft `go` binnen de limieten 12–30. Richting 90° is `offshore` en 135° is `side_offshore`.
- **Bestaande contracttests:** `test_export_and_check_tmp` en `test_files_cover_all_codes` werken met een vierde bestand, mits `build_contracts()` het als laatste toevoegt. De blueprint legt die volgorde vast.
- **Gelijkheid met `default_limits`:** de afleiding in A5 is gelijk aan `default_limits` in `evaluation.py` (`max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN)`).

## Gecontroleerde bronnen
- https://www.postgresql.org/docs/current/datatype-datetime.html (bereik van `time without time zone`: 00:00:00 t/m 24:00:00)
- https://docs.rs/speedate/latest/speedate/struct.Time.html (parser van pydantic: `HH:MM` en `HH:MM:SS` toegestaan, uur 0–23)
- https://pydantic.dev/docs/validation/latest/api/pydantic/standard_library_types/ (een `list` wordt in lax-modus geaccepteerd voor `frozenset`; tijdstrings volgens RFC 3339)
- https://pydantic.dev/docs/validation/latest/concepts/conversion_table/ (`bool` wordt in lax-modus geaccepteerd voor `int` en `float`; in strict-modus niet)
- Lokaal: `supabase/migrations/20261015090000_m1_schema.sql`, `ingest/src/shakka/domain/{evaluation,defaults,direction,spot}.py`, `ingest/src/shakka/{contracts,cli}.py`, `ingest/tests/{test_contracts,test_domain_purity,evaluation_fixtures}.py`, `docs/wp/WP-05/blueprint.md` ("Gevolgen voor latere WP's"), `docs/wp/WP-03/blueprint.md` (A10), `docs/WORK_PACKAGES.md` (WP-07, WP-08, WP-10, WP-16)
