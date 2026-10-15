# Review WP-07, ronde 2
Oordeel: APPROVED

Beoordeeld: revisie 2 van de blueprint. B-1 uit ronde 1 is opgelost, en de oplossing is overal in de blueprint consistent doorgevoerd. Ook N-1 t/m N-11 zijn verwerkt. De revisie brengt geen nieuwe blokkerende punten mee.

## Controle B-1 (24:00 uit de database)
- **Validator vóór het parsen.** `latest_local` en `earliest_local` krijgen elk een `field_validator(..., mode="before")`, met `END_OF_DAY_TIME_STRINGS = {"24:00", "24:00:00"}`.
  - Een before-validator draait vóór de `time`-parsing van pydantic, dus speedate ziet het uur 24 nooit.
  - Voor `latest_local` geeft de validator `None` terug, en dat valideert gewoon tegen `time | None`.
  - Voor `earliest_local` gooit de validator een `ValueError`. Pydantic geeft die door als `ValidationError` met de eigen melding (E37).
  - De kruisregel `earliest < latest` staat in een `model_validator(mode="after")` en ziet daardoor de omgezette waarde. Dat klopt met de tabeltekst "na die omzetting".
  - `"00:00:00"` wordt niet omgezet (E14). `model_copy` dumpt `time`/`None` en valideert die opnieuw zonder problemen.
- **`earliest_local` 24:00 blijft fout.** Dat staat consistent in de tabel, E37, A7, R3 en `test_end_of_day_time`. Er gaat niets verloren: de CHECK `alert_rules_time_window` staat `earliest = 24:00` alleen toe als `latest` NULL is, en zo'n regel telt geen enkel uur.
- **Tests.**
  - `test_end_of_day_time` dekt: `from_row` met `"24:00:00"`, de constructor met `"24:00"` en `"24:00:00"`, `resolve_rule`, `earliest_local` 24:00 via `from_row` en via de constructor, en `"00:00:00"`.
  - `test_latest_end_of_day_from_row` toont het effect in `find_windows`. Nagerekend: 19:00Z, 20:00Z en 21:00Z op 2026-07-15 zijn lokaal 21, 22 en 23 uur (CEST), dus het window is [19:00Z, 22:00Z). Dat klopt.
- **Nuance in A7.** Gecontroleerd tegen `supabase/migrations/20261015090000_m1_schema.sql`.
  - Elke override die Python accepteert, past binnen de CHECKs.
  - Omgekeerd geldt de pariteit nu met een expliciete lijst bekende verschillen: `latest` 24:00 wordt `None`, `earliest` 24:00 geeft een fout, en er zijn representatieverschillen zonder betekenis.
  - Voor onbekende gevallen bestaat een vangnet.
- **Gevolgen voor WP-10 en WP-16.**
  - WP-10: `from_row` (regel en profiel) en `resolve_rule` staan samen in één `try ... except ValueError` per favoriet. Dat vangt ook `ValidationError`. Bij een fout volgen log en teller, en de job draait door. De fout uit een profiel dat één keer per gebruiker wordt geparsed, is apart geregeld. R3 is daarop aangepast.
  - WP-16: de UI schrijft nooit `24:00`, en `effectiveRule()` neemt de omzetting van `latest_local` over.

## Controle van de nieuwe onderdelen
- **`StrictInt` per element.** `_IsoWeekday = Annotated[StrictInt, Field(ge=1, le=7)]` in `frozenset[...]` is juist.
  - In lax-modus accepteert een `frozenset`-veld een lijst. In strict-modus accepteert het alleen een `frozenset`, dus `strict=True` op het hele veld zou rijen uit de database weigeren.
  - Strict int weigert `bool` en `float`.
  - `test_weekday_out_of_range` dekt `[True]`, `[6.0]`, `[0]`, `[8]` en `[]`, plus het positieve lijstgeval `[6, 6, 7]`. Dat geldt voor zowel `AlertRuleOverride` als `AlertRule`.
  - `Field(..., strict=True, ge, le)` op een veld `int | None` wordt in de bestaande code al zo gebruikt: `float | None = Field(ge=0, ...)` in `evaluation.py`, en `Annotated[int, Field(strict=True, ...)]` in `tide.py` en `kite.py`.
- **Zomertijdtest 2027-03-28.** De datum klopt.
  - 1 maart 2027 is een maandag, dus 28 maart is de laatste zondag van maart. De overgang is om 01:00Z.
  - 00:00Z, 01:00Z en 02:00Z zijn lokaal 01:00 CET, 03:00 CEST en 04:00 CEST, dus de verwachte lokale uren zijn `[1, 3, 4]`.
  - `now = 2027-03-27 20:00Z` geeft `first_hour = 21:00Z`. `last_day` is 03-30, dus alle drie de uren tellen mee. Eén window [00:00Z, 03:00Z) is correct.
  - E31 (2026-10-25) is ook nog correct: 25 oktober 2026 is de laatste zondag van oktober.
- **Docstring van `cli.py`.** Het gaat om regel 149, de docstring van `contracts_export`. De nieuwe regel is 94 tekens lang, binnen ruff `line-length = 100`. De wijziging is consistent vastgelegd in Bestanden, Buiten scope, stap 3 en de eindcontrole (diff van precies één regel).
- **Migratiehelpers.** De regex `array\[(.*?)\]` matcht `array_position(` niet. In beide CHECKs komt `array_position(..., null)` vóór `array[...]`, dus de helpers lezen het juiste blok: `'onshore', 'side_onshore', 'sideshore'` en `1, 2, 3, 4, 5, 6, 7`. De `between`-bereiken komen overeen met `ALERT_KN_RANGE`, `MIN_GO_HOURS_RANGE` en `DAYS_AHEAD_RANGE`. `REPO_ROOT` bestaat in `shakka.config`.
- **Fixtures.** Gecontroleerd tegen de invarianten van `HourEvaluation` (WP-05): `hour()` levert geldige objecten.
  - `marginal` met `wind_borderline` is geldig.
  - `no_go` met `offshore` of `side_offshore` past bij `dir_class`.
  - `go` met `dir_class=None` is geldig volgens WP-05, en daardoor zinvol voor E29.
  - De spotwaarden 16, 28, 35 en 40 vallen binnen het spotbereik 5–40.
- **`test_contracts.py`.** De twee keer `3` staan op regel 94 en 97. Het voorschrift `len(CONTRACT_FILES)` klopt.

## Telegram (WP-09 vervalt)
De blueprint leunt nergens op Telegram. Telegram komt alleen voor als voorbeeld van een kolom die `ProfileDefaults.from_row` negeert (`telegram_chat_id`), en dat is geen afhankelijkheid. Ook als een latere migratie die kolom schrapt, blijven code en tests geldig, want `from_row` negeert alle andere kolommen. Zie N-1.

## Blokkerend
Geen.

## Niet-blokkerend
N-1: Laat `telegram_chat_id` weg uit het voorbeeld bij `ProfileDefaults` en uit de "volledige profiles-rij" in `test_from_row`, nu Web Push het enige kanaal wordt. Gebruik bijvoorbeeld `weight_kg`, `level` en `quiver_m2`. Dat is cosmetisch; het gedrag verandert niet.

N-2: Onder "Gevolgen", WP-16 staat de omzetting van `latest_local` 24:00, maar niet wat `effectiveRule()` doet met `earliest_local = "24:00:00"`. Zo'n rij kan alleen via de API buiten de UI om ontstaan. Een korte zin maakt de pariteit volledig, bijvoorbeeld: "regel ongeldig, toon als fout, net als het conflict uit A6".

N-3: Pydantic zet "Value error, " voor de melding van een `ValueError` uit een validator. `test_end_of_day_time` moet daarom op een deel van de melding toetsen (`earliest_local ... matches no hour`), niet op de exacte tekst. De blueprint formuleert het al zo; dit is alleen een aandachtspunt voor de builder.

## Gecontroleerde bronnen
- https://pydantic.dev/docs/validation/latest/concepts/conversion_table/: in strict-modus accepteert `frozenset` alleen een `frozenset`; in lax-modus ook een lijst. Een strict int weigert `bool` en `float`.
- https://www.postgresql.org/docs/current/datatype-datetime.html (uit ronde 1): `time` loopt t/m `24:00:00`.
- https://docs.rs/speedate/latest/speedate/struct.Time.html (uit ronde 1): de tijdparser van pydantic kent uur 0–23.
- Lokaal:
  - `supabase/migrations/20261015090000_m1_schema.sql` (`profiles`, `alert_rules`, CHECKs)
  - `ingest/src/shakka/cli.py` (regel 149)
  - `ingest/src/shakka/contracts.py`
  - `ingest/src/shakka/domain/{evaluation,spot,tide,kite}.py`
  - `ingest/src/shakka/config.py`
  - `ingest/tests/{test_contracts,evaluation_fixtures}.py`
  - `ingest/pyproject.toml` (ruff)
  - `docs/WORK_PACKAGES.md` (WP-07)
- Kalender nagerekend: 2027-03-28 (zondag, zomertijd) en 2026-10-25 (zondag, wintertijd).
