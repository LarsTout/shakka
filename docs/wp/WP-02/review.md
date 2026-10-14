# Review WP-02, ronde 1
Oordeel: CHANGES_REQUIRED

De blueprint is sterk: scope en acceptatiecriteria zijn volledig gedekt, de contracten met WP-01 kloppen (17 kolommen, jsonb-vorm van `ridable_dirs` en `season`, CHECK-constraints, `SupabaseRest`/`FakeSupabase`-API, `writes`/`upserts`, `seed`, context manager), en de YAML 1.1-valkuilen zijn correct geanalyseerd. Er is één blokkerend punt, met een kleine fix.

## Blokkerend

B-1: `test_validate_default_path` maakt van AC-2 toch een permanente test. Waar: Testplan, AC-1 (`test_spots_cli.py::test_validate_default_path` eist letterlijk `25 spots valid (0 verified)`). Waarom: AC-2 zegt expliciet "eenmalige controle op de diff van deze WP, geen permanente test", en A9 zegt zelf dat extra spots mogen en dat Lars velden invult. Zodra Lars (zoals "Nodig van Lars" vraagt) één spot op `verified: true` zet of een spot toevoegt, wordt deze test rood. CI faalt dan op precies de bewerking die de WP mogelijk moet maken. Een builder kan dit niet zien, want de test is groen op de startset. Voorstel: laat de test alleen exitcode 0, `spots validate: ok` en een regel die matcht op `^ok      \d+ spots valid \(\d+ verified\)$` controleren. De exacte telling `25 ... (0 verified)` hoort alleen in de eenmalige AC-2-controle door de verifier, of in een test op een tijdelijk bestand via `--path`.

## Niet-blokkerend

N-1: `_MonthDay` is tegenstrijdig gespecificeerd. Er staat "Strikte `str`", maar E4 (`start: 2026-05-01` wordt een YAML-`date`) verwacht de melding "expected a quoted 'MM-DD' date". Een strikte `str` geeft dan de pydantic-melding "Input should be a valid string". Maak `_MonthDay` net als `_LocalTime` een before-validator die elke niet-`str` met dezelfde `ValueError` weigert. Zo hoeft de builder niet zelf te kiezen.

N-2: De regex `^\d{2}-\d{2}$` van `_MonthDay` laat met `re.match`/`re.search` een afsluitende newline door (`"05-01\n"`, want `$` matcht vóór een slot-`\n`). Ook accepteert `\d` Unicode-cijfers. `to_row` geeft de string ongewijzigd door, dus vuile waarden komen in de database en bij WP-05. Schrijf voor: `re.fullmatch(r"[0-9]{2}-[0-9]{2}", v)`. Doe hetzelfde bij `_LocalTime` (`[0-9]` in plaats van `\d`).

N-3: `test_only_changed_upserted` eist dat "de laatste upsert alleen die rij bevat". `FakeSupabase` legt geen payloads vast (alleen `writes` en `upserts`), dus de builder moet zelf een spy bedenken. Schrijf er een voor (bijv. een subklasse van `FakeSupabase` die `upsert` doorgeeft en `rows` vastlegt), of laat de eis vallen. `upserted == 1` en één extra `("upsert", "spots")` bewijzen het al grotendeels.

N-4: `UniqueKeySafeLoader.construct_mapping` voert `key in seen` uit vóór `super().construct_mapping`. Die controleert pas daarna of de sleutel hashbaar is. Een complexe sleutel (`? [a, b]: x`) geeft dan een `TypeError` in plaats van een `ConstructorError`, en `load_spots` crasht met een traceback. Controleer eerst `isinstance(key, collections.abc.Hashable)` en sla die sleutel anders over (de superklasse geeft dan de nette `ConstructorError` "found unhashable key").

N-5: R5 ("een upsert kan niet op een CHECK falen") klopt voor de CHECKs. Postgres weigert echter ook NUL-tekens (`\0`, of `\u0000` in jsonb) in `text`. In YAML kan dat met `"a\0b"`. Een sync faalt dan met een `DatabaseError`. Het risico is klein; overweeg in `_NonBlankStr` en `_MonthDay` een weigering van `"\x00"`.

N-6: Bij A7: `spots validate` negeert `SPOTS_PATH`, `spots sync` gebruikt het wel. Als Lars `SPOTS_PATH` zet, valideren en syncen ze verschillende bestanden. Dat is acceptabel, maar noem het in `SPOT_DATA.md` of in de help-tekst.

N-7: In de Edge cases staat E17 als één fout "met regel en kolom". Die regel bevat geen spot-id of index. Dat is in orde, want AC-3 noemt dubbele YAML-sleutels niet. Wees wel bewust dat het formaat afwijkt van "Elke fout bevat de spot-id (of de index)" in het WP-contract. Eventueel in `SPOT_DATA.md` §10 als voorbeeld opnemen.

N-8: In het Testplan bij AC-5 staat `seed("spots", [{"id": "zz-orphan", "name": "Orphan"}])`. Dat werkt omdat de projectie van de fake ontbrekende kolommen als `None` teruggeeft. Bij E29 (`test_invalid_db_row_overwritten`) moet de geseede rij ook een `name` hebben. Zet dat expliciet in de tekst.

## Gecontroleerd zonder bevinding
- Slug-regex, `btrim(name)`, lat/lon samen, de bereiken en enums in `20261015090000_m1_schema.sql`: Python is overal minstens zo streng (R5).
- De regex van `test_to_row_columns_match_migration` matcht precies de 18 kolomregels van `create table public.spots`, en geen constraint-regels.
- PyYAML-resolvers: `10:00` wordt int 600 (sexagesimaal, eerste cijfer 1–9); `09:30` blijft str (octaal vereist `[0-7_]+` zonder `:`, float-sexagesimaal vereist `.`). E1, E2, E4, E10 kloppen.
- `construct_yaml_map` roept `self.construct_mapping(node)` aan, dus de override in de subklasse werkt; `SafeConstructor.construct_mapping` roept `flatten_mapping` aan vóór de basisversie. Daarom ziet de dubbele-sleutelcontrole merge-sleutels niet (E38 klopt).
- pydantic 2.14.1 (lock) ondersteunt `validate_by_name`/`validate_by_alias` (pyproject eist ≥2.11). `StringConstraints(strict=..., pattern=...)` bestaat. In de conversietabel: lax `int` accepteert `bool`, lax `time` accepteert `int` als seconden, en strict `float` accepteert `int` maar weigert `bool`. De keuze voor eigen before-validators is terecht.
- De `conftest.py` isoleert env en `.env`, dus `test_sync_missing_config` en `test_validate_default_path` lezen geen echte configuratie.
- De puurheidstest staat de imports van `spot.py` toe. `from datetime import time` met `time(h, m)` valt niet onder de `time.time`-regel.
- Harde regels: geen kosten, geen externe API's, geen scraping, geen verzonnen spotdata (alleen `id`, `name` uit het plan en `verified: false`). Offshore blijft `no_go` ongeacht `ridable_dirs` (A4). Geen secrets in uitvoer.
- Rekenvoorbeeld `shore_normal_deg`: kust NNO–ZZW met water aan de westkant geeft 290. Dat klopt. Wind uit `shore_normal_deg` is onshore (meteorologische conventie).

## Gecontroleerde bronnen
- https://pypi.org/pypi/PyYAML/json (6.0.3 is de laatste versie, `requires_python >=3.8`)
- https://raw.githubusercontent.com/yaml/pyyaml/main/lib/yaml/constructor.py
- https://raw.githubusercontent.com/yaml/pyyaml/main/lib/yaml/resolver.py
- https://pydantic.dev/docs/validation/latest/concepts/conversion_table/
- https://pydantic.dev/docs/validation/latest/concepts/alias/
- https://pydantic.dev/docs/validation/latest/api/pydantic/types/ (`StringConstraints`)
- Lokaal: `supabase/migrations/20261015090000_m1_schema.sql`, `ingest/src/shakka/{db,config,cli,doctor}.py`, `ingest/tests/{fakes,conftest,test_domain_purity,test_fake_parity,test_cli}.py`, `ingest/uv.lock`
