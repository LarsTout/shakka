# Blueprint WP-02: Spotprofielen: schema, validatie, sync en startset
Status: APPROVED
Revisie: 2

## Doel
`data/spots.yaml` wordt streng gevalideerd en idempotent naar de tabel `spots` (WP-01) gesynchroniseerd. Concreet levert deze WP:
- `shakka.domain.spot`: bevroren pydantic-modellen en enums. Dit is de typebron voor WP-05, WP-06, WP-07, WP-08 en WP-10;
- `shakka.spots.loader.load_spots`: leest de YAML en verzamelt alle fouten in één `SpotValidationError`;
- `shakka.spots.sync.sync_spots`: upsert op `id`, nooit deletes, en meldt wees-spots;
- de CLI-groep `shakka spots` met `validate` en `sync`;
- `data/spots.yaml` met de 25 spots uit het plan, elk alleen `id`, `name` en `verified: false`;
- `docs/SPOT_DATA.md`: de handleiding voor Lars om de profielen in te vullen.

## Verwerking review
Ronde 1 (`review.md`, CHANGES_REQUIRED).

| Punt | Verwerking |
|---|---|
| **B-1** (blokkerend) `test_validate_default_path` maakte AC-2 permanent | Opgelost. De test controleert nu alleen exitcode 0, de regel `spots validate: ok` en een regel die volledig matcht op `^ok      \d+ spots valid \(\d+ verified\)$` (met `re.MULTILINE`). De exacte telling `25 spots valid (0 verified)` zit alleen nog in de eenmalige AC-2-controle door de verifier (Testplan AC-2, Stappenplan stap 6 en 9). De exacte uitvoertekst met vaste aantallen wordt getest op tijdelijke bestanden via `--path` (`test_validate_counts_on_tmp_file`). A9 vermeldt dit expliciet. |
| N-1 `_MonthDay` tegenstrijdig | Verwerkt. `_MonthDay` is nu net als `_LocalTime` een before-validator die elke niet-`str` (ook `date`) weigert met dezelfde melding "expected a quoted 'MM-DD' date". E4 klopt daarmee. |
| N-2 `$` en `\d` | Verwerkt. `_MonthDay` gebruikt `re.fullmatch(r"[0-9]{2}-[0-9]{2}", v)`, `_LocalTime` gebruikt `re.fullmatch(r"([01][0-9]\|2[0-3]):[0-5][0-9]", v)`. Nieuwe edge case E40 (afsluitende newline, fullwidth-cijfers) met tests. Hetzelfde voor `id`: `_SpotId` is nu een before-validator met `re.fullmatch(SPOT_ID_PATTERN, v)` in plaats van `StringConstraints(pattern=...)`, en `SPOT_ID_PATTERN` heeft geen `^`/`$` meer. Daardoor hangt niets af van het gedrag van `$` in de regex-engine van pydantic. E40 test ook `"zz-a\n"` als id; een niet-afdrukbare id komt niet in het foutlabel (loader stap 4). |
| N-3 payload van de laatste upsert | Verwerkt. `test_spots_sync.py` krijgt een spy `RecordingFake(FakeSupabase)` die per `upsert` een kopie van de rijen in `upsert_payloads` vastlegt en daarna `super().upsert(...)` aanroept (zie Testplan AC-5). `FakeSupabase` zelf wijzigt niet. |
| N-4 onhashbare sleutel | Verwerkt. `UniqueKeySafeLoader.construct_mapping` slaat een sleutel die niet `collections.abc.Hashable` is over; de superklasse geeft dan de `ConstructorError` "found unhashable key". Nieuwe edge case E39 met test. |
| N-5 NUL-tekens | Verwerkt. `_NonBlankStr` weigert `"\x00"` met "must not contain NUL characters". `_MonthDay`, `_LocalTime` en `id` weigeren het al via hun patroon. Nieuwe edge case E41 met test; R5 aangevuld. |
| N-6 `SPOTS_PATH` alleen bij `sync` | Verwerkt. Het gedrag blijft (A7), maar de help-teksten van beide `--path`-opties noemen het verschil, en `SPOT_DATA.md` §1 legt het uit. |
| N-7 formaat van YAML-fouten | Verwerkt als documentatie. E17, E20 en E39 hebben bewust het formaat `spots.yaml: line L, column C: ...` zonder spot-id (YAML-fouten ontstaan vóór er spots zijn). `SPOT_DATA.md` §10 neemt "found duplicate key" als voorbeeld op. Geen codewijziging. |
| N-8 `name` in geseede rijen | Verwerkt. Testplan AC-5 noemt nu voor elke `seed` expliciet `id` en `name`, ook bij `test_invalid_db_row_overwritten` (E29). |

## Aannames
Dit zijn voorstellen voor de open keuzes. Lars beoordeelt ze; de reviewer toetst ze tegen het plan.

- **A1. YAML-bibliotheek: PyYAML 6.0.3** (`yaml.SafeLoader`), met een eigen subklasse die dubbele sleutels weigert. PyYAML laat bij een dubbele sleutel stil de laatste waarde winnen; bij handmatig bewerken is dat een reële fout. Het plan noemt `yaml` al als verboden import in het domein, dus PyYAML ligt in de lijn van het plan. ruamel.yaml (YAML 1.2) is niet nodig: de valkuilen van YAML 1.1 vangt de validatie af (zie A3).
- **A2. Extra validatieregels bovenop de WP-lijst.** Elke regel maakt de data eenduidiger voor WP-05. Geen enkele regel maakt een geldig contractvoorbeeld ongeldig.
  1. `name` mag niet leeg zijn en niet alleen uit witruimte bestaan. Dit eist ook de DB-CHECK `spots_name_not_blank` (WP-01, "Gevolgen voor latere WP's").
  2. Optionele tekstvelden (`region`, `hazards`, `rws_station`, `notes`, `season[].note`) mogen leeg (`null` of weggelaten) zijn, maar niet `""` of alleen witruimte. Leeg betekent weglaten.
  3. `ridable_dirs` is `null` (geen override) of een lijst met minstens één bereik. `[]` wordt geweigerd: dat zou elk uur `no_go` maken zonder dat het zo bedoeld is.
  4. Een tijdvenster in `season` vraagt `from_time < to_time`. Vensters over middernacht zijn niet toegestaan; kiten in het donker is toch al `no_go`. WP-05 hoeft zo geen vensters over middernacht te ondersteunen.
  5. `tide_min_level_cm` mag alleen ingevuld zijn als `tide_sensitive` niet `none` is. Anders is onduidelijk of WP-05 de minimumwaterstand toepast.
  6. Getallen moeten echte YAML-getallen zijn, geen tekst (`"290"`) en geen boolean (`yes` wordt in YAML 1.1 `true`). Gehele velden weigeren ook `290.0`. `lat` en `lon` weigeren NaN en oneindig.
  7. `season`, `tide_sensitive` en `verified` mogen leeg (`null`) zijn. Ze krijgen dan hun default: `[]`, `none` en `false`. Lars kan zo een sjabloon met lege velden laten staan.
- **A3. Tijden en datums in YAML altijd tussen aanhalingstekens.** PyYAML leest `10:00` zonder aanhalingstekens als het getal 600 (sexagesimaal), maar `09:30` als tekst. Een tijd moet daarom een string `"HH:MM"` (24-uurs) zijn. Een getal geeft een foutmelding die om aanhalingstekens vraagt. Datums zijn strings `"MM-DD"`. `SPOT_DATA.md` legt dit uit.
- **A4. Betekenis van `season` en `ridable_dirs`.** Dit is een contract voor WP-05 en wordt zo in `SPOT_DATA.md` beschreven:
  - `start` en `end` zijn inclusief, in lokale tijd (`Europe/Amsterdam`);
  - `start > end` loopt over de jaargrens (bijvoorbeeld `"11-01"` tot `"02-28"`). `start == end` is één dag;
  - zonder tijdvenster geldt de sluiting de hele dag. Met een tijdvenster is kiten verboden van `from_time` (inclusief) tot `to_time` (exclusief), op elke dag binnen de periode;
  - `02-29` is toegestaan. Advies aan WP-05: vergelijk (maand, dag) als tuple. Dan werkt `02-29` in een niet-schrikkeljaar als start vanaf 1 maart en als einde tot en met 28 februari, zonder uitzonderingsregel;
  - `ridable_dirs`: bereiken met de klok mee, beide grenzen inclusief. `from > to` loopt over het noorden (`{from: 200, to: 20}` is 200–359 en 0–20). `from == to` is precies één graad;
  - `ridable_dirs` beperkt alleen. Offshore en side-offshore blijven altijd `no_go`, ook als ze binnen `ridable_dirs` vallen (harde regel, WP-05).
- **A5. YAML is de bron van waarheid; sync met wijzigingsdetectie.** `sync_spots` leest eerst de bestaande rijen en upsert alleen spots die nieuw of gewijzigd zijn. Een upsert schrijft altijd alle 17 kolommen, dus een veld dat uit de YAML verdwijnt, wordt in de database `null`. Handmatige wijzigingen in het Supabase-dashboard worden bij de volgende sync overschreven. Waarom wijzigingsdetectie: `updated_at` (trigger uit WP-01) geeft dan aan wanneer een profiel echt wijzigde, en een herhaalde sync schrijft niets. `SyncResult.upserted` telt de nieuwe plus gewijzigde spots; een tweede run geeft 0.
- **A6. Wees-spots worden alleen gemeld.** Een spot die in de database staat maar niet in de YAML, staat in `orphaned` en geeft een `warn`-regel. De exitcode blijft 0. Verwijderen gebeurt nooit automatisch, want een delete op `spots` neemt via de cascade favorieten, alertregels, forecasts en evaluaties mee.
- **A7. Pad voor de CLI.**
  - `spots validate` gebruikt `--path`, of anders `shakka.config.DEFAULT_SPOTS_PATH`. Het leest geen settings en heeft dus geen `.env` of Supabase-variabelen nodig; het werkt ook in CI.
  - `spots sync` gebruikt `--path`, of anders `get_settings().spots_path` (env `SPOTS_PATH`, standaard hetzelfde bestand).
  - Gevolg: met `SPOTS_PATH` gezet valideren en syncen beide commando's zonder `--path` verschillende bestanden. Dat is acceptabel (sync valideert zelf ook volledig vóór het schrijven), en staat in de help-teksten en in `SPOT_DATA.md` §1 (review N-6).
- **A8. `rws_station` wordt niet tegen een stationslijst gecontroleerd.** Alleen "niet leeg". De stationslijst komt uit WP-04 (`shakka tides stations`). WP-04 mag een controle toevoegen.
- **A9. Permanente datatest.** AC-2 is een eenmalige controle (Lars vult later velden in). Wel komt er een permanente test die eist dat `data/spots.yaml` foutloos valideert en minstens de 25 contract-id's bevat. Extra spots mogen. Zo vangt CI elke ongeldige bewerking door Lars af, en kan een id die favorieten vasthouden niet stil verdwijnen of hernoemd worden. Geen enkele permanente test op `data/spots.yaml` eist een exact aantal spots, exacte namen, een aantal `verified`-spots of de afwezigheid van velden: elke bewerking die Lars volgens `SPOT_DATA.md` doet, houdt CI groen (review B-1).
- **A10. `from_row` is streng.** Alle 17 kolommen moeten in de rij staan; extra sleutels (zoals `updated_at` of kolommen die een latere WP toevoegt) worden genegeerd. Een rij die niet aan de validatie voldoet, geeft een `ValueError` (pydantic `ValidationError` is daar een subklasse van). De database is losser dan de Python-validatie (lat/lon wereldwijd, geen `verified`-eisen). WP-10 moet die fout dus per spot afvangen, zodat één kapotte rij niet de hele run stopt. `sync_spots` overschrijft zo'n rij.
- **A11. Docker voor AC-6.** Net als bij WP-01 kan het zijn dat de builder geen toegang heeft tot Docker. Dan levert de builder de optionele lokale test en de commando's op, en toont de verifier AC-6 met de lokale stack, of markeert hij het als `NEEDS_LARS`.

## Ontwerp

**Domein (`shakka.domain.spot`).** Drie bevroren modellen (`frozen=True`, `extra="forbid"`): `DirRange`, `SeasonClosure` en het profiel. Lijsten zijn tuples, zodat een profiel echt onveranderlijk en hashbaar is. De validatie heeft twee lagen:
1. **Veldregels** (types, bereiken, enums, slug, `MM-DD`, `HH:MM`, onbekende velden). Die zitten in de veldtypes. Pydantic verzamelt ze per spot allemaal tegelijk, ook in geneste `season`- en `ridable_dirs`-items.
2. **Regels over meerdere velden** (lat/lon samen, eisen voor `verified: true`, A2.5). Die staan in één pure functie, `spot_rule_violations(spot) -> list[SpotRuleViolation]`, die elke overtreding apart teruggeeft.

Een after-validator van pydantic kan maar één fout melden. Daarom is het profiel gesplitst in `SpotProfileBase` (alleen velden) en `SpotProfile(SpotProfileBase)`. `SpotProfile` voegt een after-validator toe die `spot_rule_violations` aanroept en bij overtredingen een `ValueError` geeft met alle overtredingen samengevoegd. Directe constructie (`SpotProfile(...)`, `from_row`) is dus altijd volledig gevalideerd. De loader valideert eerst met `SpotProfileBase`, roept daarna zelf `spot_rule_violations` aan en meldt elke overtreding als aparte fout. Regels over meerdere velden worden alleen gecontroleerd als de velden van die spot afzonderlijk geldig zijn. Dat is bewust: een regel als "lat zonder lon" heeft geen zin als `lat` zelf al ongeldig is.

Getallen worden streng gecontroleerd met eigen before-validators (A2.6), niet met de lax-modus van pydantic. Die zou `true` als 1 en `"290"` als 290 accepteren, en een tijd als getal (aantal seconden) lezen. De pydantic-conversietabel bevestigt dat lax `int` een `bool` accepteert en lax `time` een `int` als seconden leest (zie Externe afhankelijkheden).

**Loader (`shakka.spots.loader`).** Leest het bestand als UTF-8 en parseert het met `UniqueKeySafeLoader` (een subklasse van `yaml.SafeLoader` die dubbele sleutels weigert). Daarna wordt de vorm gecontroleerd: een mapping met precies de sleutel `spots`, die een lijst bevat. Per item: is het een mapping, is de id dubbel, wat geeft `SpotProfileBase`, en wat geeft `spot_rule_violations`. Bestands-, YAML- en vormfouten stoppen meteen (één fout). Fouten per spot worden over alle spots verzameld. Elke foutregel heeft de vorm `spots[<index>] (<id>): <veldpad>: <melding>`.

**Sync (`shakka.spots.sync`).** Drie stappen: één `select` van alle bestaande spots (alle 17 kolommen; `SupabaseRest` pagineert zelf), een vergelijking per spot op genormaliseerde rijen (`from_row(...).to_row()`; een rij die niet te parsen is, telt als gewijzigd), en één `upsert(..., on_conflict="id")` van de nieuwe en gewijzigde rijen. Er is geen request als er niets gewijzigd is. Er gebeurt nooit een `delete`. Alle Python-validatie is minstens zo streng als de CHECK-constraints van `spots` (zie R5), dus een upsert kan niet op een CHECK falen.

**CLI.** Net als bij `doctor` staat de logica in een los module (`shakka.spots.commands`) met functies die een exitcode teruggeven, en roept `shakka.cli` die lazy aan. `open_db(settings)` is het enige punt waar een `SupabaseRest` ontstaat, zodat tests daar `FakeSupabase` kunnen inprikken. De uitvoer bevat nooit settings-waarden.

**Startset.** `data/spots.yaml` bevat de 25 spots in de volgorde van het plan, elk met alleen `id`, `name` en `verified: false`, plus een kort Engels kopcommentaar met een verwijzing naar `docs/SPOT_DATA.md`. Feitelijke spotdata vult Lars in (harde regel: niets verzinnen).

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/pyproject.toml` | wijzigen | Dependency `pyyaml>=6.0.3,<7` toevoegen (via `uv add`). Verder niets. |
| `ingest/uv.lock` | wijzigen | Bijgewerkt door `uv add`. |
| `ingest/src/shakka/domain/spot.py` | aanmaken | Enums, constanten, `DirRange`, `SeasonClosure`, `SpotProfileBase`, `SpotProfile`, `SpotRuleViolation` en `spot_rule_violations` (zie Interfaces). |
| `ingest/src/shakka/spots/__init__.py` | aanmaken | Alleen een docstring: `"""Spot profiles: YAML loading, validation and database sync (I/O)."""` |
| `ingest/src/shakka/spots/loader.py` | aanmaken | `SpotValidationError`, `UniqueKeySafeLoader` en `load_spots`. |
| `ingest/src/shakka/spots/sync.py` | aanmaken | `SyncResult` en `sync_spots`. |
| `ingest/src/shakka/spots/commands.py` | aanmaken | `open_db`, `run_validate` en `run_sync`. |
| `ingest/src/shakka/cli.py` | wijzigen | Groep `spots` met de commando's `validate` en `sync`. `doctor` blijft ongewijzigd. |
| `ingest/tests/spot_fixtures.py` | aanmaken | `FULL_SPOT_YAML`, `FULL_SPOT_ROW` en `MIN_SPOT_YAML` (zie Testplan). |
| `ingest/tests/test_spot_model.py` | aanmaken | Domeintests en AC-4. |
| `ingest/tests/test_spots_validation.py` | aanmaken | AC-3 (loader). |
| `ingest/tests/test_spots_sync.py` | aanmaken | AC-5. |
| `ingest/tests/test_spots_cli.py` | aanmaken | AC-1 en het CLI-deel van AC-3, plus `sync` via de CLI. |
| `ingest/tests/test_spots_data.py` | aanmaken | Permanente datatest (A9). |
| `ingest/tests/test_spot_docs.py` | aanmaken | AC-7. |
| `ingest/tests/test_spots_sync_local.py` | aanmaken | Optioneel, alleen tegen de lokale stack (AC-6-ondersteuning). |
| `data/spots.yaml` | aanmaken | De startset (zie Interfaces). |
| `docs/SPOT_DATA.md` | aanmaken | De handleiding voor Lars, in het Nederlands (zie Interfaces). |

Geen migraties: de tabel `spots` uit WP-01 volstaat. `docs/STATUS.md` werkt de orchestrator bij. `docs/RUNBOOK.md` blijft ongewijzigd; de sync-werkwijze staat in `SPOT_DATA.md`.

## Interfaces en contracten

### `shakka.domain.spot`
Toegestane imports: `re`, `math`, `datetime` (`date`, `time`), `enum` (`StrEnum`), `typing`, `collections.abc`, `pydantic`. Geen `.now(`/`.today(`. Valt onder `test_domain_purity.py`.

```python
"""Spot profile model: the validated shape of one entry in data/spots.yaml and one row of `spots`."""

class Level(StrEnum):
    BEGINNER = "beginner"; INTERMEDIATE = "intermediate"; ADVANCED = "advanced"

class SpotStatus(StrEnum):
    ALLOWED = "allowed"; LIMITED = "limited"; FORBIDDEN = "forbidden"

class TideSensitivity(StrEnum):
    NONE = "none"; PREFER_LOW = "prefer_low"; PREFER_HIGH = "prefer_high"; AVOID_LOW = "avoid_low"

SPOT_ID_PATTERN: Final = r"[a-z0-9]+(-[a-z0-9]+)*"   # always used with re.fullmatch
NL_LAT_RANGE: Final = (50.7, 53.7)          # inclusive
NL_LON_RANGE: Final = (3.2, 7.3)            # inclusive
TIDE_MIN_LEVEL_RANGE_CM: Final = (-300, 300)
DEFAULT_MIN_KN_RANGE: Final = (5, 40)
VERIFIED_REQUIRED_FIELDS: Final = ("lat", "lon", "shore_normal_deg", "status", "level")
# Columns of public.spots (WP-01) without updated_at, in table order.
SPOT_COLUMNS: Final[tuple[str, ...]] = (
    "id", "name", "region", "lat", "lon", "shore_normal_deg", "ridable_dirs", "hazards",
    "tide_sensitive", "tide_min_level_cm", "rws_station", "season", "status", "level",
    "default_min_kn", "notes", "verified",
)
```

**Hulptypes** (module-intern, namen vrij, gedrag vast):

| Type | Gedrag |
|---|---|
| `_StrictInt` | Before-validator: `bool` of een niet-`int` geeft `ValueError("expected an integer")`. |
| `_Number` | Before-validator: `bool`, of geen `int`/`float`, geeft `ValueError("expected a number")`. Niet eindig geeft `ValueError("expected a finite number")`. Resultaat `float(v)`. |
| `_NonBlankStr` | `StringConstraints(strict=True)` plus een after-validator, in deze volgorde: `"\x00" in v` geeft `ValueError("must not contain NUL characters")` (Postgres weigert NUL in `text` en `jsonb`); `v.strip() == ""` geeft `ValueError("must not be blank")`. |
| `_MonthDay` | `Annotated[str, BeforeValidator(...)]`. De before-validator: is `v` geen `str` (ook een YAML-`date` of `int`), of slaagt `re.fullmatch(r"[0-9]{2}-[0-9]{2}", v)` niet, of faalt `date(2000, int(v[:2]), int(v[3:]))` (2000 is een schrikkeljaar, dus `02-29` mag), dan `ValueError("expected a quoted 'MM-DD' date, e.g. \"05-01\"")`. Anders gaat `v` ongewijzigd door. `fullmatch` met `[0-9]` weigert een afsluitende newline en niet-ASCII-cijfers. |
| `_LocalTime` | Before-validator: een `time` met `tzinfo is None`, `second == 0` en `microsecond == 0` gaat ongewijzigd door. Een `str` waarvoor `re.fullmatch(r"([01][0-9]\|2[0-3]):[0-5][0-9]", v)` slaagt, wordt `time(int(v[:2]), int(v[3:]))`. Al het andere (ook `int`, zoals het ongequote `10:00`, en `"10:00\n"`) geeft `ValueError("expected a quoted 'HH:MM' time (24h), e.g. \"10:00\"")`. |
| `_SpotId` | `Annotated[str, BeforeValidator(...)]`. Is `v` geen `str`, of slaagt `re.fullmatch(SPOT_ID_PATTERN, v)` niet, dan `ValueError("expected a lowercase slug (a-z, 0-9, single hyphens), e.g. \"wijk-aan-zee\"")`. Bewust geen `StringConstraints(pattern=...)`: zo hangt het gedrag van `$` niet af van de regex-engine van pydantic (review N-2, E40). |
| `_none_to(default)` | Before-validator: `None` wordt `default`. |

**Modellen:**
```python
class DirRange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_by_name=True, validate_by_alias=True)
    from_deg: Annotated[int, <_StrictInt>, Field(ge=0, le=359)] = Field(alias="from")
    to_deg: Annotated[int, <_StrictInt>, Field(ge=0, le=359)] = Field(alias="to")

class SeasonClosure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    start: _MonthDay
    end: _MonthDay
    from_time: _LocalTime | None = None
    to_time: _LocalTime | None = None
    note: _NonBlankStr | None = None
    # after-validator, in this order:
    #   exactly one of from_time/to_time set -> ValueError("from_time and to_time must both be set or both be empty")
    #   both set and from_time >= to_time    -> ValueError("from_time must be before to_time")

class SpotProfileBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: _SpotId
    name: _NonBlankStr
    region: _NonBlankStr | None = None
    lat: Annotated[float, <_Number>, Field(ge=50.7, le=53.7)] | None = None
    lon: Annotated[float, <_Number>, Field(ge=3.2, le=7.3)] | None = None
    shore_normal_deg: Annotated[int, <_StrictInt>, Field(ge=0, le=359)] | None = None
    ridable_dirs: Annotated[tuple[DirRange, ...], Field(min_length=1)] | None = None
    hazards: _NonBlankStr | None = None
    tide_sensitive: Annotated[TideSensitivity, <_none_to(TideSensitivity.NONE)>] = TideSensitivity.NONE
    tide_min_level_cm: Annotated[int, <_StrictInt>, Field(ge=-300, le=300)] | None = None
    rws_station: _NonBlankStr | None = None
    season: Annotated[tuple[SeasonClosure, ...], <_none_to(())>] = ()
    status: SpotStatus | None = None
    level: Level | None = None
    default_min_kn: Annotated[int, <_StrictInt>, Field(ge=5, le=40)] | None = None
    notes: _NonBlankStr | None = None
    verified: Annotated[bool, <before: None -> False; non-bool -> ValueError("expected true or false")>] = False

class SpotRuleViolation(NamedTuple):
    field: str
    message: str

def spot_rule_violations(spot: SpotProfileBase) -> list[SpotRuleViolation]:
    """Cross-field rules, each violation separately, in this fixed order:
    1. lat set, lon None  -> ("lon", "required when lat is set")
       lon set, lat None  -> ("lat", "required when lon is set")
    2. tide_min_level_cm set and tide_sensitive == NONE
                          -> ("tide_min_level_cm", "only allowed when tide_sensitive is not none")
    3. verified is True: for each f in VERIFIED_REQUIRED_FIELDS that is None
                          -> (f, "required when verified is true")
       and if tide_sensitive != NONE and rws_station is None
                          -> ("rws_station", "required when verified is true and tide_sensitive is not none")
    Rule 3 does not repeat a field already reported by rule 1."""

class SpotProfile(SpotProfileBase):
    # after-validator: violations = spot_rule_violations(self); if violations:
    #   raise ValueError("; ".join(f"{v.field}: {v.message}" for v in violations))
    def to_row(self) -> dict[str, Any]: ...
    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "SpotProfile": ...
```
`SpotProfile` overschrijft geen velden en geen config.

**`to_row()`** geeft een `dict` met precies de sleutels uit `SPOT_COLUMNS`, in die volgorde. Alle waarden zijn JSON-klare Python-types (geen enums, geen `time`-objecten):

| Kolom | Waarde |
|---|---|
| `id`, `name`, `region`, `hazards`, `rws_station`, `notes` | `str` of `None` |
| `lat`, `lon` | `float` of `None` |
| `shore_normal_deg`, `tide_min_level_cm`, `default_min_kn` | `int` of `None` |
| `ridable_dirs` | `None` of `[{"from": int, "to": int}, ...]` |
| `tide_sensitive` | `str` (de `.value`) |
| `season` | `[{"start": "MM-DD", "end": "MM-DD", "from_time": "HH:MM" \| None, "to_time": "HH:MM" \| None, "note": str \| None}, ...]`, altijd alle vijf sleutels; tijden als `f"{t.hour:02d}:{t.minute:02d}"` |
| `status`, `level` | `str` (de `.value`) of `None` |
| `verified` | `bool` |

Dit is exact het jsonb-formaat uit het WP-01-contract (`ridable_dirs`: lijst `{"from", "to"}`; `season`: lijst `{"start", "end", "from_time", "to_time", "note"}`).

**`from_row(row)`**:
- ontbreekt een kolom uit `SPOT_COLUMNS`, dan `ValueError(f"spots row is missing columns: {', '.join(missing)}")`;
- extra sleutels (`updated_at`, toekomstige kolommen) worden genegeerd;
- het resultaat is `cls.model_validate({c: row[c] for c in SPOT_COLUMNS})`;
- `lat` en `lon` als `int` uit PostgREST (bijv. `52`) worden `float`.

Garantie: `SpotProfile.from_row(s.to_row()) == s` voor elk geldig `s`.

### `shakka.spots.loader`
```python
class SpotValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        # errors must be non-empty; stored as self.errors (a new list)
        # str(exc) == f"{len(errors)} spot validation error(s):\n" + "\n".join(errors)

class UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys."""
    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            seen: set[object] = set()
            for key_node, _value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    continue
                key = self.construct_object(key_node, deep=False)
                if not isinstance(key, collections.abc.Hashable):
                    # leave it to super(): it raises ConstructorError("found unhashable key")
                    continue
                if key in seen:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping", node.start_mark,
                        f"found duplicate key {key!r}", key_node.start_mark)
                seen.add(key)
        return super().construct_mapping(node, deep=deep)

def load_spots(path: Path) -> list[SpotProfile]:
    """Load and validate all spot profiles; raise SpotValidationError with every error found."""
```
**Algoritme `load_spots`** (exact; `name` is `path.name`):
1. `path.read_text(encoding="utf-8")`:
   - `FileNotFoundError` geeft `SpotValidationError([f"{path}: file not found"])`;
   - een andere `OSError` of een `UnicodeDecodeError` geeft `[f"{path}: cannot read file ({type(exc).__name__})"]`.
2. `yaml.load(text, Loader=UniqueKeySafeLoader)`:
   - een `yaml.MarkedYAMLError` met `problem_mark` geeft `[f"{name}: line {mark.line + 1}, column {mark.column + 1}: {exc.problem}"]`, en zonder mark `[f"{name}: {exc.problem}"]`;
   - een andere `yaml.YAMLError` geeft `[f"{name}: invalid YAML ({type(exc).__name__})"]`.
3. Vorm:
   - `None` geeft `[f"{name}: file is empty"]`;
   - geen `dict`, of zonder sleutel `spots` geeft `[f"{name}: top level must be a mapping with a 'spots' list"]`;
   - andere top-level sleutels geven per sleutel `f"{name}: unknown top-level key {key!r}"` (allemaal tegelijk);
   - `spots` geen `list` geeft dezelfde melding als hierboven.

   `spots: []` is geldig (0 spots).
4. Per item `i` (in volgorde), met `label = f"spots[{i}] ({item['id']})"` als het item een `dict` is met een `str`-id waarvoor `id.isprintable()` geldt, en anders `f"spots[{i}]"` (zo komt een id met een newline of NUL, E40, niet in de uitvoer en blijft elke fout één regel):
   - geen `dict` geeft `f"spots[{i}]: expected a mapping"`, en het item wordt overgeslagen;
   - is de `str`-id eerder gezien op index `j`, dan volgt `f"{label}: id: duplicate of spots[{j}]"` (de eerste index wordt onthouden);
   - `SpotProfileBase.model_validate(item)`. Bij een `ValidationError` volgt per fout uit `exc.errors(include_url=False, include_input=False)` de regel `f"{label}: {_loc(err['loc'])}: {err['msg']}"`, en het item wordt overgeslagen;
   - daarna levert elke `SpotRuleViolation` uit `spot_rule_violations(base)` de regel `f"{label}: {v.field}: {v.message}"`. Zijn er overtredingen, dan wordt het item overgeslagen;
   - anders wordt `SpotProfile.model_validate(item)` toegevoegd aan het resultaat.
5. Zijn er fouten, dan volgt `raise SpotValidationError(errors)`. Anders wordt de lijst profielen teruggegeven, in bestandsvolgorde.

`_loc(loc)`: `str`-delen worden met `.` verbonden, `int`-delen worden `[n]` achter het vorige deel. Voorbeelden: `("season", 0, "start")` wordt `season[0].start`, `("ridable_dirs", 0, "from")` wordt `ridable_dirs[0].from`, en `()` wordt `(spot)`.

### `shakka.spots.sync`
```python
@dataclass(frozen=True)
class SyncResult:
    upserted: int          # new + changed spots written
    orphaned: list[str]    # ids in the database but not in `spots`, sorted ascending

def sync_spots(db: SupabaseRest, spots: Sequence[SpotProfile]) -> SyncResult:
    """Upsert new/changed spots on `id`. Never deletes. YAML wins over manual database edits."""
```
Exact:
1. Dubbele `id` in `spots` geeft `ValueError("duplicate spot ids: ...")`, nog vóór een request.
2. `existing_rows = db.select("spots", columns=",".join(SPOT_COLUMNS))`.
3. `existing = {row["id"]: _normalized(row) for row in existing_rows}`. Daarin doet `_normalized` het volgende: `SpotProfile.from_row(row).to_row()`, en bij een `ValueError` `None` (dan geldt de rij als gewijzigd).
4. `changed = [s.to_row() for s in spots if existing.get(s.id) != s.to_row()]`, in de volgorde van de invoer.
5. `upserted = db.upsert("spots", changed, on_conflict="id") if changed else 0`.
6. `orphaned = sorted(set(existing) - {s.id for s in spots})`.
7. `return SyncResult(upserted=upserted, orphaned=orphaned)`.

Er is geen `delete`-aanroep in het module (de test controleert `writes`). Een `DatabaseError` gaat ongewijzigd naar de aanroeper.

### `shakka.spots.commands` en `shakka.cli`
```python
def open_db(settings: Settings) -> SupabaseRest:
    return SupabaseRest.from_settings(settings)

def run_validate(path: Path | None, *, echo: Callable[[str], None]) -> int: ...
def run_sync(path: Path | None, *, echo: Callable[[str], None]) -> int: ...
```
In `shakka/cli.py`:
```python
@cli.group()
def spots() -> None:
    """Validate and sync spot profiles (data/spots.yaml)."""

@spots.command("validate")
@click.option("--path", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Spots YAML file (default: data/spots.yaml; SPOTS_PATH is not read).")
def spots_validate(path: Path | None) -> None:
    from shakka.spots.commands import run_validate
    raise SystemExit(run_validate(path, echo=click.echo))

@spots.command("sync")
@click.option("--path", type=click.Path(dir_okay=False, path_type=Path), default=None,
              help="Spots YAML file (default: SPOTS_PATH, else data/spots.yaml).")
def spots_sync(path: Path | None) -> None:
    from shakka.spots.commands import run_sync
    raise SystemExit(run_sync(path, echo=click.echo))
```

**Uitvoer** (exacte regels; `n` = aantal spots, `k` = aantal fouten):

| Situatie | Regels | Exitcode |
|---|---|---|
| `validate` ok | `ok      {n} spots valid ({v} verified)`, dan `spots validate: ok` | 0 |
| `validate` fout | per fout `error   {fout}`, dan `spots validate: failed ({k} errors)` | 1 |
| `sync`: settings ongeldig of onvolledig (`pydantic.ValidationError` uit `get_settings`) | `error   configuration incomplete or invalid; run 'shakka doctor'`, dan `spots sync: failed` | 1 |
| `sync`: YAML ongeldig | per fout `error   {fout}`, dan `spots sync: failed ({k} validation errors, nothing written)`. `open_db` wordt niet aangeroepen. | 1 |
| `sync`: `DatabaseError` | `error   database: {exc}`, dan `spots sync: failed` | 1 |
| `sync` ok | `ok      {u} of {n} spots upserted ({n-u} unchanged)`; bij wezen `warn    {m} spots in database but not in YAML (not deleted): {', '.join(orphaned)}`; dan `spots sync: ok` | 0 |

Volgorde in `run_sync`: settings, pad (`path or settings.spots_path`), `load_spots`, dan `with open_db(settings) as db: sync_spots(db, spots)`. Er wordt nooit een settings-waarde getoond. `DatabaseError` is al geredigeerd door `SupabaseRest`.

### `data/spots.yaml` (exact)
```yaml
# Shakka spot profiles. Field guide: docs/SPOT_DATA.md
# After editing run: cd ingest && uv run shakka spots validate
# Never guess facts: leave a field out when unsure and keep verified: false.
spots:
  - id: wijk-aan-zee
    name: Wijk aan Zee
    verified: false
  # ... same three keys for each spot below, in this order:
```
De id's en namen, in deze volgorde:

| id | name |
|---|---|
| `wijk-aan-zee` | Wijk aan Zee |
| `ijmuiden` | IJmuiden |
| `zandvoort` | Zandvoort |
| `bloemendaal` | Bloemendaal |
| `noordwijk` | Noordwijk |
| `langevelderslag` | Langevelderslag |
| `katwijk` | Katwijk |
| `scheveningen` | Scheveningen |
| `kijkduin` | Kijkduin |
| `oostvoorne` | Oostvoorne |
| `brouwersdam` | Brouwersdam |
| `neeltje-jans` | Neeltje Jans |
| `vrouwenpolder` | Vrouwenpolder |
| `domburg` | Domburg |
| `workum` | Workum |
| `makkum` | Makkum |
| `hindeloopen` | Hindeloopen |
| `lemmer` | Lemmer |
| `den-helder` | Den Helder |
| `callantsoog` | Callantsoog |
| `petten` | Petten |
| `camperduin` | Camperduin |
| `schellinkhout` | Schellinkhout |
| `muiderberg` | Muiderberg |
| `lauwersmeer` | Lauwersmeer |

Geen andere velden, geen coördinaten, geen regio.

### `docs/SPOT_DATA.md` (Nederlands; verplichte inhoud)
1. **Doel en werkwijze.** Profielen invullen in `data/spots.yaml`, dan `cd ingest && uv run shakka spots validate`, committen via een PR. Na de merge draait Lars `uv run shakka spots sync` (met `.env` naar het remote project, na `supabase db push` van WP-01). Sync overschrijft wijzigingen in het dashboard (A5) en verwijdert nooit iets (A6). Een spot verwijderen kan alleen handmatig, en dat verwijdert via de cascade ook favorieten, alertregels, forecasts en evaluaties. Id's niet hernoemen: favorieten verwijzen ernaar. Let op: `spots validate` leest altijd `data/spots.yaml` (of `--path`), terwijl `spots sync` zonder `--path` de env-variabele `SPOTS_PATH` volgt als die gezet is. Wie `SPOTS_PATH` zet, geeft bij `validate` hetzelfde bestand mee met `--path` (sync valideert zelf ook volledig voordat er iets geschreven wordt).
2. **Basisregels.** Niets invullen wat je niet zeker weet; leeg laten (weglaten of `null`) en `verified: false`. YAML-tips: datums en tijden altijd tussen aanhalingstekens (`"05-01"`, `"10:00"`), met de uitleg waarom (`10:00` zonder aanhalingstekens wordt 600). Getallen zonder aanhalingstekens. `true`/`false` voor `verified`. Geen lege tekst `""`. Inspringen met spaties.
3. **Veldentabel.** Elk van de 17 velden uit `SPOT_COLUMNS` (elk als `` `veld` `` in de tekst), met type, verplicht ja/nee, toegestane waarden of bereik (de waarden uit Interfaces) en betekenis.
4. **`shore_normal_deg`.** Definitie: de richting loodrecht op de kust, van land naar water. Ga op het strand staan en kijk recht naar het water: de kompasrichting waarin je kijkt is `shore_normal_deg`. Rekenvoorbeeld 1: een kust die op het westen ligt (je kijkt naar het westen) geeft **270**. Rekenvoorbeeld 2: een kustlijn die loopt van 20° naar 200° (NNO–ZZW), met het water aan de westkant. De twee loodlijnen zijn 20 + 90 = 110 en 20 − 90 = −70, dus 290. Het water ligt aan de westkant, dus 290. Het verband met windrichting (meteorologisch, "waar de wind vandaan komt"): wind uit `shore_normal_deg` is onshore. Indicatief, met de voorbeelden uit WP-05 AC-1 voor 270: 270 onshore, 225/315 side-onshore, 180/0 sideshore, 135/45 side-offshore, 90 offshore. De exacte grenzen liggen vast in WP-05. Noem geen echte spot met een waarde.
5. **`ridable_dirs`.** Optionele override voor meren, dijken en dergelijke. Bereiken met de klok mee, grenzen inclusief, over het noorden via `{from: 200, to: 20}`. Leeg laten betekent geen override. Een override maakt offshore en side-offshore nooit rijdbaar.
6. **`season`.** Periodes waarin kiten niet mag, in lokale tijd, datums inclusief. Voorbeelden: (a) een hele periode, (b) met tijdvenster (`from_time` en `to_time`, beide of geen, `from_time` vóór `to_time`, verboden van `from_time` tot `to_time`), (c) over de jaargrens (`"11-01"` tot `"02-28"`), (d) meerdere regels. `02-29` mag.
7. **Getij.** De betekenis van `none`, `prefer_low`, `prefer_high` en `avoid_low`. `tide_min_level_cm` in cm ten opzichte van NAP, alleen bij `tide_sensitive` niet `none`. `rws_station`: kies de code met `shakka tides stations` (beschikbaar na WP-04).
8. **Eisen voor `verified: true`.** Verplicht: `lat`, `lon`, `shore_normal_deg`, `status` en `level`, en `rws_station` als `tide_sensitive` niet `none` is. Daarnaast de inhoudelijke check door Lars: de NKV-spotkaart, de gemeentelijke en lokale regels en de seizoenssluitingen. Alleen Lars zet `verified: true`.
9. **Volledig fictief voorbeeld.** Het `test-strand`-blok uit het WP-02-contract, duidelijk gemarkeerd als fictief en "niet overnemen in `data/spots.yaml`".
10. **Foutmeldingen lezen.** De vorm `spots[3] (domburg): season[0].start: ...`, met twee of drie voorbeelden. Daarnaast de tweede vorm voor fouten in de YAML zelf, die vóór de spots ontstaan en dus geen spot-id hebben: `spots.yaml: line 12, column 5: found duplicate key 'lat'` (zoek de spot via het regelnummer). Gebruik in de voorbeelden geen echte spotwaarden; een id uit de startset met een fictieve fout mag.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `from_time: 10:00` zonder aanhalingstekens (YAML-int 600) | Fout op `season[i].from_time`: "expected a quoted 'HH:MM' time" |
| E2 | `from_time: 09:30` zonder aanhalingstekens (YAML-str) | Geldig (de string is `"09:30"`) |
| E3 | `start: "02-29"` | Geldig. `"02-30"`, `"13-01"`, `"5-1"` en `"00-10"` geven een fout op `season[i].start` |
| E4 | `start: 2026-05-01` (YAML-date) | Fout: "expected a quoted 'MM-DD' date" |
| E5 | Seizoen `"11-01"` tot `"02-28"` | Geldig (over de jaargrens) |
| E6 | `from_time: "18:00"`, `to_time: "10:00"` of gelijk | Fout op `season[i]`: "from_time must be before to_time" |
| E7 | `ridable_dirs: [{from: 200, to: 20}]` | Geldig (over het noorden) |
| E8 | `ridable_dirs: []` | Fout op `ridable_dirs` (min. 1) |
| E9 | `ridable_dirs: [{from: 10}]` | Fout op `ridable_dirs[0].to` (ontbreekt) |
| E10 | `shore_normal_deg: yes`, `"290"` of `290.0` | Fout: "expected an integer" |
| E11 | `lat: .nan`, `lat: "52.0"` of `lat: true` | Fout op `lat` |
| E12 | `lat: 50.7` en `lon: 7.3` (grenzen) | Geldig |
| E13 | `lat: 52` (int) | Geldig, wordt `52.0` |
| E14 | `name: "  "`, `region: ""` | Fout: "must not be blank" |
| E15 | `id: 123` (YAML-int) | Fout op `id`; het label is `spots[i]`, zonder id |
| E16 | Item zonder `id` | Fout `id: Field required`; het label is `spots[i]` |
| E17 | Dubbele YAML-sleutel binnen een spot (`lat` twee keer) | Eén fout `spots.yaml: line L, column C: found duplicate key 'lat'`. Bewust zonder spot-id of index: YAML-fouten ontstaan vóór er spots zijn (review N-7; voorbeeld in `SPOT_DATA.md` §10). |
| E18 | Leeg bestand, alleen commentaar, top-level lijst, `spots: {}`, extra top-level sleutel | Eén vormfout (extra sleutels: één fout per sleutel) |
| E19 | Bestand bestaat niet | `"{path}: file not found"`, exitcode 1 |
| E20 | YAML-syntaxfout | Eén fout met regel en kolom (1-based) |
| E21 | `season:` of `tide_sensitive:` of `verified:` leeg (`null`) | Respectievelijk `()`, `none` en `false` |
| E22 | `verified: "true"` (string) | Fout: "expected true or false" |
| E23 | `tide_min_level_cm: -20` met `tide_sensitive: none` (of weggelaten) | Fout op `tide_min_level_cm` (A2.5) |
| E24 | `verified: true`, `tide_sensitive: avoid_low`, zonder `rws_station` | Fout op `rws_station` |
| E25 | `verified: true` zonder `lat` en `lon` (overige verplichte velden ingevuld) | Precies twee fouten (`lat`, `lon`), elk "required when verified is true". Regel 1 zwijgt, want beide ontbreken. |
| E26 | `verified: true` met alleen `lat` | `lon: required when lat is set`; regel 3 herhaalt `lon` niet |
| E27 | Een spot met een veldfout én een regelovertreding (`status: open` en `lat` zonder `lon`) | Alleen de veldfout. Regels over meerdere velden pas als de velden geldig zijn (Ontwerp). |
| E28 | `spots: []` | Geldig. `sync` doet geen upsert en meldt alle databasespots als wees. |
| E29 | Sync: de databaserij is ongeldig (bijv. `lat` 10.0 handmatig gezet) | `_normalized` geeft `None`, de rij wordt overschreven (telt in `upserted`) |
| E30 | Sync: niets gewijzigd | Geen upsert-request, `upserted == 0`, `writes` blijft leeg |
| E31 | Sync: een veld is uit de YAML verwijderd | De rij is gewijzigd en wordt ge-upsert met `null` voor dat veld |
| E32 | Sync: `DatabaseError` bij `select` of `upsert` | Exitcode 1 met de geredigeerde melding. Bij een fout in `select` wordt er niets geschreven. |
| E33 | `from_row` met een rij zonder `season` | `ValueError` "missing columns: season" |
| E34 | `from_row` met `updated_at` en een onbekende extra kolom | Genegeerd |
| E35 | `SpotProfile(...)` direct met `lat` zonder `lon` | `ValidationError` met `lon: required when lat is set` in de melding |
| E36 | Een toewijzing aan een veld van een profiel | `ValidationError` (bevroren) |
| E37 | `DirRange(from_deg=1, to_deg=2)` en `DirRange.model_validate({"from": 1, "to": 2})` | Allebei geldig en gelijk |
| E38 | Merge-sleutels (`<<: *anchor`) in de YAML | Geen fout van de dubbele-sleutelcontrole. Ze worden niet aangeraden. |
| E39 | Complexe (onhashbare) sleutel in een spot: `? [a, b]\n    : x` | Geen traceback. Eén fout `spots.yaml: line L, column C: found unhashable key` (de `ConstructorError` van de superklasse). |
| E40 | Afsluitende newline of niet-ASCII-cijfers: `start: "05-01\n"`, `start: "０５-01"` (fullwidth `05`), `from_time: "10:00\n"`, `id: "zz-a\n"` | Fout op respectievelijk `season[0].start` ("expected a quoted 'MM-DD' date"), `season[0].start`, `season[0].from_time` ("expected a quoted 'HH:MM' time") en `id`. Bij `id: "zz-a\n"` is het label `spots[0]` (id niet afdrukbaar), en geen enkele foutregel bevat een newline. De waarde komt nooit in de database. |
| E41 | NUL-teken in tekst: `name: "a\0b"`, `notes: "x\0"`, `season[0].note: "\0"` | Fout op het veld: "must not contain NUL characters" |

## Testplan
Tests eerst voor alle domeinlogica. Er worden geen echte spotwaarden in tests gebruikt: alleen de fictieve `test-strand` en ids met het prefix `zz`.

**`ingest/tests/spot_fixtures.py`:**
- `FULL_SPOT_YAML`: exact het contractvoorbeeld uit WORK_PACKAGES (WP-02, Contracten), `test-strand`;
- `FULL_SPOT_ROW`: de verwachte `to_row()` daarvan:
  ```python
  {"id": "test-strand", "name": "Teststrand", "region": "Testregio", "lat": 52.0, "lon": 4.2,
   "shore_normal_deg": 290, "ridable_dirs": [{"from": 200, "to": 20}], "hazards": None,
   "tide_sensitive": "avoid_low", "tide_min_level_cm": -20, "rws_station": "hoekvanholland",
   "season": [{"start": "05-01", "end": "09-30", "from_time": "10:00", "to_time": "18:00",
               "note": "badseizoen"}],
   "status": "allowed", "level": "intermediate", "default_min_kn": 14, "notes": None,
   "verified": True}
  ```
- `MIN_SPOT_YAML`: `spots:\n  - id: zz-min\n    name: Minimal\n    verified: false\n`;
- helper `write_spots(tmp_path, text) -> Path`.

**AC-1** (`shakka spots validate` geeft 0 op `data/spots.yaml`):
- `test_spots_cli.py::test_validate_default_path`: `CliRunner().invoke(cli, ["spots", "validate"])` zonder env. Eisen: exitcode 0; `re.search(r"^ok      \d+ spots valid \(\d+ verified\)$", result.output, re.MULTILINE)` slaagt; de regel `spots validate: ok` staat in de uitvoer. Géén exacte telling: die test zou rood worden zodra Lars een spot toevoegt of verifieert (review B-1);
- `test_spots_cli.py::test_validate_counts_on_tmp_file`: de exacte uitvoertekst met vaste aantallen, op tijdelijke bestanden via `--path`. `MIN_SPOT_YAML` geeft `ok      1 spots valid (0 verified)`, en `FULL_SPOT_YAML` geeft `ok      1 spots valid (1 verified)`, elk gevolgd door `spots validate: ok`;
- `test_spots_data.py::test_data_file_is_valid`: `load_spots(DEFAULT_SPOTS_PATH)` geeft geen exceptie;
- de verifier draait ook letterlijk `cd ingest && uv run shakka spots validate`.

**AC-2** (eenmalig, op de diff): de verifier draait vanuit `ingest/`:
```
uv run python -c "import yaml; d = yaml.safe_load(open('../data/spots.yaml')); print([(s['id'], s['name'], s['verified'], sorted(s)) for s in d['spots']])"
```
en controleert: precies de 25 id's uit de tabel, met de namen uit het plan, elk `verified` gelijk aan `False` en sleutels `['id', 'name', 'verified']`. Daarnaast toont `uv run shakka spots validate` op dat moment letterlijk `ok      25 spots valid (0 verified)`; ook dat is alleen deze eenmalige controle, geen test. De permanente test `test_spots_data.py::test_contract_ids_present` eist dat de 25 contract-id's aanwezig zijn (superset toegestaan, A9). Hij controleert de namen en de afwezigheid van andere velden níet, want Lars vult die later in.

**AC-3** (`test_spots_validation.py`). Geparametriseerd: `(yaml_text, expected_id_in_msg, expected_field_in_msg)`. Elk geval geeft `SpotValidationError`, en minstens één regel in `exc.errors` bevat zowel de id als de veldnaam:

| Geval | YAML (kern) | id | veld |
|---|---|---|---|
| dubbele id | twee items `id: zz-dup`, `name: A` en `name: B` | `zz-dup` | `id` |
| ongeldige slug | `id: Bad_Id` | `Bad_Id` | `id` |
| `lat` zonder `lon` | `id: zz-a`, `lat: 52.0` | `zz-a` | `lon` |
| buiten Nederland | `id: zz-b`, `lat: 48.0`, `lon: 2.0` | `zz-b` | `lat` (en ook een regel met `lon`) |
| `shore_normal_deg: 360` | `id: zz-c` | `zz-c` | `shore_normal_deg` |
| `ridable_dirs`-grens 400 | `id: zz-d`, `ridable_dirs: [{from: 400, to: 20}]` | `zz-d` | `ridable_dirs` |
| seizoensdatum `02-30` | `id: zz-e`, `season: [{start: "02-30", end: "03-31"}]` | `zz-e` | `season` |
| `from_time` zonder `to_time` | `id: zz-f`, `season: [{start: "05-01", end: "09-30", from_time: "10:00"}]` | `zz-f` | `season` en `to_time` |
| onbekende enum | `id: zz-g`, `status: open` | `zz-g` | `status` |
| onbekend veld | `id: zz-h`, `parking: true` | `zz-h` | `parking` |
| `verified: true` zonder `shore_normal_deg` | `id: zz-i`, `lat: 52.0`, `lon: 4.2`, `status: allowed`, `level: beginner`, `verified: true` | `zz-i` | `shore_normal_deg` |

(Elk item heeft ook `name: X`, tenzij anders vermeld.)

Daarnaast in hetzelfde bestand:
- `test_three_errors_in_one_exception`: items `{id: Bad_Id, name: X, status: open}` en `{id: zz-ok, name: Y, lat: 52.0}`. Dat geeft `len(exc.errors) == 3` (slug, status, lon), in die volgorde;
- `test_edge_cases`, geparametriseerd over E1, E3 (alle ongeldige varianten), E4, E6, E8, E9, E10, E11, E14, E15, E16, E17, E18, E19, E20, E22, E23, E24, E39, E40 (alle vier varianten, elk als eigen geval) en E41 (alle drie). Elk geeft een `SpotValidationError`, en de verwachte veldnaam of het kernwoord staat in de foutregel. Kernwoorden: E4 `expected a quoted 'MM-DD' date` (bewijst dat een YAML-`date` onze eigen melding krijgt, review N-1), E17 `found duplicate key 'lat'`, E39 `found unhashable key`, E41 `must not contain NUL characters`. De YAML-tekst van E40 en E41 gebruikt double-quoted escapes (`"０５-01"`, `"a\0b"`) in een Python raw string, zodat PyYAML de tekens maakt;
- `test_error_lines_are_single_line`: voor de gevallen E40 en E41 bevat geen enkele regel in `exc.errors` een `"\n"` of `"\x00"`;
- `test_valid_edge_cases`: E2, `"02-29"`, E5, E7, E12, E13 en E21 laden foutloos, met de verwachte waarden (bijv. E21: `season == ()`, `tide_sensitive is TideSensitivity.NONE`, `verified is False`);
- `test_error_format`: de foutregel voor `zz-e` begint met `spots[0] (zz-e): season[0].start: `;
- `test_file_order_preserved`: drie geldige spots komen terug in bestandsvolgorde.

Het CLI-deel: `test_spots_cli.py::test_validate_three_errors` op het bestand met drie fouten geeft exitcode 1, drie regels die met `error   ` beginnen, en `spots validate: failed (3 errors)`.

**AC-4** (`test_spot_model.py`):
- `test_full_fixture_loads`: `load_spots(write_spots(tmp_path, FULL_SPOT_YAML))` geeft één profiel; `to_row() == FULL_SPOT_ROW`;
- `test_to_row_columns_match_migration`: `list(row) == list(SPOT_COLUMNS)`. Daarnaast is `set(SPOT_COLUMNS)` gelijk aan de kolommen van `create table public.spots` uit `supabase/migrations/20261015090000_m1_schema.sql` min `updated_at`. Die kolommen worden geparst als het blok tussen `create table public.spots (` en de eerste `\n);`, met de regels die matchen op `^  ([a-z_]+) (text|double precision|smallint|jsonb|integer|boolean|timestamptz)\b`. Het verwachte resultaat staat ook als letterlijke lijst in de test;
- `test_roundtrip`: `SpotProfile.from_row(s.to_row()) == s` voor de volledige fixture, de minimale spot, een spot met twee seizoensregels zonder tijden, en een spot met `ridable_dirs` van twee bereiken;
- `test_from_row_ignores_extra_and_updated_at` (E34), `test_from_row_missing_column` (E33) en `test_from_row_int_lat` (E13 via de rij);
- `test_to_row_is_json_encodable`: `shakka.db.to_json(row)` geeft geen fout, en de typen zijn `str`, `int`, `float`, `bool`, `None`, `list` of `dict` (geen `Enum`-instanties, geen `time`);

Verder domeintests in hetzelfde bestand: `test_frozen` (E36), `test_extra_forbidden` voor alle drie de modellen, `test_dir_range_alias_and_name` (E37), `test_season_time_rules` (E6, plus beide-of-geen), `test_rule_violations_order` (E25, E26, E23, E24, en de volgorde uit de docstring), `test_direct_construction_enforces_rules` (E35) en `test_enum_values` (de exacte waardesets van de drie enums).

**AC-5** (`test_spots_sync.py`, met `FakeSupabase`). Spy, bovenaan dat testbestand (review N-3; `tests/fakes.py` blijft ongewijzigd):
```python
class RecordingFake(FakeSupabase):
    """FakeSupabase that also records the payload of every upsert."""

    def __init__(self) -> None:
        super().__init__()
        self.upsert_payloads: list[tuple[str, list[dict[str, Any]]]] = []

    def upsert(self, table: str, rows: Sequence[Mapping[str, Any]], *, on_conflict: str) -> int:
        self.upsert_payloads.append((table, [dict(r) for r in rows]))
        return super().upsert(table, rows, on_conflict=on_conflict)
```
Alle tests hieronder gebruiken `RecordingFake()`. Elke geseede `spots`-rij bevat minstens `id` en `name` (`name` is in de database `not null`; de fake vult ontbrekende kolommen bij `select` met `None`) (review N-8).
- `test_first_sync_upserts_all`: een lege fake en twee profielen (de volledige fixture en de minimale spot). Resultaat `upserted == 2` en `orphaned == []`, `db.upserts == [("spots", "id")]`, `db.upsert_payloads == [("spots", [full.to_row(), minimal.to_row()])]`, en `writes` bevat geen `delete`. `db.rows("spots")` bevat beide, met `to_row`-waarden;
- `test_orphan_reported_not_deleted`: met `seed("spots", [{"id": "zz-orphan", "name": "Orphan"}])` geeft de sync `orphaned == ["zz-orphan"]`, en `zz-orphan` staat nog in `rows("spots")`;
- `test_second_sync_is_noop`: twee keer achter elkaar. De tweede geeft `upserted == 0`, en `writes` en `upsert_payloads` groeien niet;
- `test_only_changed_upserted`: na de eerste sync (volledige fixture en minimale spot) wordt de minimale spot vervangen door `minimal.model_copy(update={"notes": "changed"})` (geldig, want `notes` is vrije tekst; `model_copy` valideert niet, maar de waarde voldoet aan `_NonBlankStr`). Resultaat `upserted == 1`, `writes` krijgt precies één extra `("upsert", "spots")`, en `db.upsert_payloads[-1] == ("spots", [changed.to_row()])`: de laatste upsert bevat alleen die rij;
- `test_removed_field_becomes_null` (E31): eerste sync met de volledige fixture, daarna een sync met dezelfde spot waaruit `region` is verwijderd (`full.model_copy(update={"region": None})`; `region` is niet verplicht bij `verified: true`). `upserted == 1`, en `region` van die rij in `rows("spots")` is `None`;
- `test_invalid_db_row_overwritten` (E29): `seed("spots", [{"id": "zz-min", "name": "Minimal", "lat": 10.0, "lon": 4.0}])`, daarna sync met de minimale spot (`MIN_SPOT_YAML`, id `zz-min`). Resultaat `upserted == 1`, `orphaned == []`, en daarna zijn `lat` en `lon` `None`;
- `test_duplicate_ids_rejected`: `ValueError` en 0 writes;
- `test_empty_input` (E28): `seed("spots", [{"id": "zz-a", "name": "A"}, {"id": "zz-b", "name": "B"}])`, sync met `[]`. Geen upsert, `orphaned == ["zz-a", "zz-b"]`.

**Sync via de CLI** (`test_spots_cli.py`; env via `monkeypatch.setenv("SUPABASE_URL", "https://testref.supabase.co")` en `SUPABASE_SECRET_KEY=sb_secret_TESTVALUE`; `monkeypatch.setattr(shakka.spots.commands, "open_db", lambda settings: fake)`):
- `test_sync_ok`: exitcode 0, `ok      2 of 2 spots upserted (0 unchanged)` en `spots sync: ok`;
- `test_sync_orphan_warns`: een `warn    1 spots in database but not in YAML (not deleted): zz-orphan`-regel, exitcode 0;
- `test_sync_missing_config`: zonder env geeft het exitcode 1, `run 'shakka doctor'`, en `open_db` wordt niet aangeroepen (een sentinel die faalt bij een aanroep);
- `test_sync_invalid_yaml_writes_nothing`: exitcode 1, `nothing written`, `open_db` niet aangeroepen;
- `test_sync_database_error`: een fake waarvan `select` `DatabaseError("select spots: HTTP 500", status=500)` gooit geeft exitcode 1, `error   database: select spots: HTTP 500`;
- `test_sync_output_has_no_secrets`: `sb_secret_TESTVALUE` en `testref` staan in geen enkele uitvoer van de bovenstaande gevallen;
- `test_help_lists_spots`: `shakka --help` toont `spots`, en `shakka spots --help` toont `validate` en `sync`.

**AC-6** (lokale stack, 25 rijen, idempotent):
- de builder of verifier draait vanuit de repo-root `supabase start` en `supabase db reset`, en vanuit `ingest/` (de lokale secret key uit `supabase status`, alleen als env, nooit in een bestand; env gaat in pydantic-settings vóór `.env`):
  ```
  SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_SECRET_KEY=<local> uv run shakka spots sync
  SUPABASE_URL=http://127.0.0.1:54321 SUPABASE_SECRET_KEY=<local> uv run python -c "from shakka.config import get_settings; from shakka.db import SupabaseRest; print(len(SupabaseRest.from_settings(get_settings()).select('spots', columns='id')))"
  ```
  De eerste sync meldt `25 of 25 spots upserted`, de telling geeft `25`. De tweede sync meldt `0 of 25 spots upserted (25 unchanged)`, de telling geeft weer `25`;
- `test_spots_sync_local.py` (optioneel). Dezelfde skip-regel als `test_fake_parity.py`: alleen met `SHAKKA_TEST_SUPABASE_URL` naar `127.0.0.1` of `localhost` en `SHAKKA_TEST_SUPABASE_SECRET_KEY`, anders `pytest.skip` zonder waarden in de reden. De test werkt met ids `zzs-full` (de volledige fixture met een andere id) en `zzs-min`:
  - delete vooraf en achteraf (`in_filter`);
  - de eerste sync geeft `upserted == 2`, de tweede `0`;
  - `from_row` op de echte rijen is gelijk aan de originelen (bewijst het jsonb- en tijdformaat en dat de CHECKs accepteren);
  - `"zzs-full" not in result.orphaned`.

**AC-7** (`test_spot_docs.py`): `docs/SPOT_DATA.md` bestaat en bevat:
- elke naam uit `SPOT_COLUMNS` als `` `naam` ``;
- `270`;
- `verified: true`;
- `shakka tides stations`;
- `shakka spots validate`;
- `NKV`.

**Regressie:** de volledige suite blijft groen (`uv run pytest`), inclusief `test_domain_purity.py` (dekt nu ook `spot.py`) en `test_repo_hygiene.py`. Lint en format zijn schoon.

## Externe afhankelijkheden

| Afhankelijkheid | Versie / waarde | Reden | Gecontroleerd |
|---|---|---|---|
| PyYAML | `pyyaml>=6.0.3,<7` (laatste: 6.0.3, `requires_python >=3.8`) | YAML parseren voor `data/spots.yaml` | https://pypi.org/pypi/PyYAML/json |
| PyYAML `SafeLoader` / `construct_mapping` | `BaseConstructor.construct_mapping(node, deep=False)` maakt een dict zonder controle op dubbele sleutels. `SafeConstructor.construct_mapping` roept eerst `flatten_mapping(node)` aan (merge-sleutels). `ConstructorError(MarkedYAMLError)` | `UniqueKeySafeLoader` | https://raw.githubusercontent.com/yaml/pyyaml/main/lib/yaml/constructor.py |
| PyYAML `MarkedYAMLError` | `__init__(context, context_mark, problem, problem_mark, note)`. `Mark.line` en `Mark.column` zijn 0-based. | Foutregel met regel en kolom (+1) | https://raw.githubusercontent.com/yaml/pyyaml/main/lib/yaml/error.py |
| PyYAML-resolvers (YAML 1.1) | bool: `yes/no/on/off/true/false` (alle hoofdlettervarianten). int: ook sexagesimaal `[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+` (dus `10:00` wordt 600, `09:30` blijft tekst). Timestamp: `YYYY-MM-DD`. null: `~`, `null` en leeg. | A3, E1, E2, E4, E10 | https://raw.githubusercontent.com/yaml/pyyaml/main/lib/yaml/resolver.py |
| pydantic (al aanwezig, lock 2.14.1) | Conversietabel: `float` strict accepteert `int` en weigert `bool`; lax `int` accepteert `bool`; lax `time` accepteert `int` als seconden; lax Enum accepteert de ruwe waarde (Python-invoer), strict niet. Daarom eigen before-validators en geen globale strict-modus. | Veldtypes | https://pydantic.dev/docs/validation/latest/concepts/conversion_table/ |
| pydantic-validators | `model_validator(mode="after")` met `-> Self`. Validators mogen `ValueError`, `AssertionError` of `PydanticCustomError` geven. `BeforeValidator`/`AfterValidator` via `Annotated`. | `SeasonClosure`, `SpotProfile` | https://pydantic.dev/docs/validation/latest/concepts/validators/ |
| pydantic-aliassen | `validate_by_alias` (standaard `True`) en `validate_by_name` (standaard `False`; hier `True` voor `DirRange`) | `DirRange` `from`/`to` | https://pydantic.dev/docs/validation/latest/concepts/alias/ |
| click (al aanwezig, 8.5.0) | `@group`, `click.Path(dir_okay=False, path_type=Path)` | CLI | bestaand gebruik in `shakka/cli.py` |
| Supabase lokaal | API `http://127.0.0.1:54321` (zoals in RUNBOOK sectie 6); `supabase status` toont de lokale secret key | AC-6 | `docs/RUNBOOK.md` (WP-01) |

Geen externe API's, geen nieuwe diensten, geen kosten. Geen nieuwe dev-dependencies (geen `types-PyYAML`: het project draait geen type checker).

## Risico's
- **R1. YAML 1.1-valkuilen** (`yes`/`no` als boolean, `10:00` als getal, datums als `date`). Mitigatie: strikte veldtypes (A2.6, A3), duidelijke foutmeldingen die om aanhalingstekens vragen, uitleg in `SPOT_DATA.md`, en tests E1, E2, E4, E10 en E22.
- **R2. Geen Docker bij de builder.** Dan is AC-6 niet lokaal te tonen (zoals bij WP-01, D1). Mitigatie: A11. De optionele lokale test en de exacte commando's liggen klaar voor de verifier. Anders is het `NEEDS_LARS`.
- **R3. Sync overschrijft handmatige databasewijzigingen.** Bewust (A5). Staat in `SPOT_DATA.md`.
- **R4. `from_row` faalt op een ongeldige databaserij** (de database is losser dan de Python-validatie). WP-10 moet per spot afvangen (A10). Sync herstelt zo'n rij bij de volgende run.
- **R5. Een DB-CHECK strenger dan de Python-validatie zou de sync pas tegen de echte database laten falen.** Gecontroleerd tegen migratie 1: slug, niet-lege naam, lat/lon samen, bereiken voor `shore_normal_deg`, `tide_min_level_cm` en `default_min_kn`, de enums, en de array-vorm van `ridable_dirs` en `season`. Alle zijn in Python minstens zo streng (lat/lon zelfs strenger). Postgres weigert daarnaast NUL-tekens in `text` en `jsonb`; die weigert Python ook (`_NonBlankStr`, en de patronen van `_SpotId`, `_MonthDay` en `_LocalTime`; E41, review N-5). De optionele lokale test bewijst het tegen echt Postgres.
- **R6. Pydantic-meldingen kunnen per versie verschillen.** De tests toetsen alleen de spot-id, het veldpad en onze eigen meldingen, niet de pydantic-tekst.
- **R7. Latere kolommen in `spots`.** Een migratie die een kolom toevoegt (toegestaan volgens WP-01) breekt `from_row` niet (extra sleutels worden genegeerd). Wel moet die WP `SPOT_COLUMNS`, `to_row` en de kolomtest in `test_spot_model.py` aanpassen, anders wordt de nieuwe kolom niet gesynchroniseerd. De kolomtest parseert alleen `create table public.spots`; een `alter table … add column` moet de test expliciet meenemen.
- **R8. Een id hernoemen in de YAML** laat de oude rij als wees achter, met de favorieten van gebruikers. Mitigatie: A9 (de 25 contract-id's moeten blijven bestaan), en `SPOT_DATA.md` waarschuwt.

## Buiten scope
- Feitelijke spotdata invullen (Lars), en `verified: true` zetten.
- De stationslijst van Rijkswaterstaat en `shakka tides stations` (WP-04). Validatie van `rws_station` tegen die lijst (eventueel WP-04).
- De evaluatie, richtingsklassen en drempels (WP-05). Hier staat alleen de betekenis van de velden (A4).
- Automatische sync in de uurlijkse run (WP-11 beslist of `spots sync` erin komt).
- Spots verwijderen of hernoemen via de CLI.
- Een migratie op `spots`. Wijzigingen aan `docs/RUNBOOK.md`.

## Gevolgen voor latere WP's
- **WP-04:** `rws_station` is vrije, niet-lege tekst. `shakka tides stations` moet de code tonen die Lars hier invult.
- **WP-05:**
  - gebruik de semantiek uit A4 (datums inclusief, `start > end` over de jaargrens, (maand, dag)-tuples vergelijken, tijdvenster `[from_time, to_time)` lokaal, `ridable_dirs` inclusief en met de klok mee);
  - `tide_min_level_cm` komt alleen voor bij `tide_sensitive != none`;
  - `season` en `ridable_dirs` zijn tuples;
  - `default_limits` kan `spot.default_min_kn` (5–40 of `None`) gebruiken.
- **WP-06:** `Level` is een `StrEnum` met waarden `beginner`, `intermediate` en `advanced`.
- **WP-10:**
  - `SpotProfile.from_row` vraagt alle 17 kolommen (select `",".join(SPOT_COLUMNS)` of `*`) en kan een `ValueError` geven; vang die per spot af (A10);
  - de beslissing van Lars "alerts alleen voor `verified: true`" leunt op `SpotProfile.verified`.
- **WP-11:** als de uurlijkse run spots synct, gebruik dan `sync_spots` (schrijft niets als er niets gewijzigd is).

## Stappenplan voor de builder
Werk op branch `wp/WP-02` in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-02`. Lees of print `.env` nooit. Na elke stap vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Eén commit per stap, commitberichten in het Engels.

1. **Dependency.** `cd ingest && uv add "pyyaml>=6.0.3,<7"`. Controleer dat alleen `pyproject.toml` (één regel in `dependencies`) en `uv.lock` wijzigen. De suite is groen.
   Commit: `build(ingest): add pyyaml`.
2. **Domeinmodel, eerst de tests.**
   - Schrijf `tests/spot_fixtures.py` en de domeintests uit `tests/test_spot_model.py`: alles behalve `test_full_fixture_loads`, die de loader nodig heeft. Bouw die fixture in deze stap via `SpotProfile.model_validate(yaml.safe_load(FULL_SPOT_YAML)["spots"][0])`. Rood.
   - Implementeer `src/shakka/domain/spot.py` exact volgens Interfaces. Groen, inclusief `test_domain_purity.py`.

   Commit: `feat(domain): add spot profile model with validation rules`.
3. **Loader, eerst de tests.**
   - Schrijf `tests/test_spots_validation.py` en voeg `test_full_fixture_loads` toe aan `test_spot_model.py`. Rood.
   - Implementeer `src/shakka/spots/__init__.py` en `src/shakka/spots/loader.py`. Groen.

   Commit: `feat(spots): load and validate spots.yaml collecting all errors`.
4. **Sync, eerst de tests.**
   - Schrijf `tests/test_spots_sync.py`. Rood.
   - Implementeer `src/shakka/spots/sync.py`. Groen.
   - Controleer met `grep -n "delete" ingest/src/shakka/spots/sync.py` dat er geen `delete`-aanroep is.

   Commit: `feat(spots): idempotent upsert sync with orphan reporting`.
5. **CLI, eerst de tests.**
   - Schrijf `tests/test_spots_cli.py`, zonder `test_validate_default_path` (die heeft `data/spots.yaml` nodig en komt in stap 6). `test_validate_counts_on_tmp_file` hoort wel bij deze stap. Rood.
   - Implementeer `src/shakka/spots/commands.py` en de groep `spots` in `src/shakka/cli.py`. Groen.

   Commit: `feat(cli): add spots validate and spots sync commands`.
6. **Startset.**
   - Maak `data/spots.yaml` exact volgens Interfaces (25 spots, alleen `id`, `name` en `verified: false`).
   - Schrijf `tests/test_spots_data.py` (`test_data_file_is_valid`, `test_contract_ids_present`) en `test_validate_default_path` (alleen het regex-patroon, geen exacte telling; zie Testplan AC-1). Groen.
   - Draai `uv run shakka spots validate`: exitcode 0, en de uitvoer is nu letterlijk `ok      25 spots valid (0 verified)` (eenmalige AC-2-controle, niet in een test vastleggen).

   Commit: `feat(data): add starter set of 25 unverified spots`.
7. **Handleiding.**
   - Schrijf `tests/test_spot_docs.py` (rood).
   - Schrijf `docs/SPOT_DATA.md` in het Nederlands met de tien verplichte onderdelen. Groen.
   - Geen echte spotwaarden in de tekst.

   Commit: `docs: add spot data guide for filling in profiles`.
8. **Lokale stack (AC-6).**
   - Schrijf `tests/test_spots_sync_local.py` (wordt overgeslagen zonder env).
   - Als Docker beschikbaar is: `supabase start` en `supabase db reset` vanuit de repo-root, en daarna vanuit `ingest/` de twee commando's uit het Testplan (AC-6) twee keer, plus de lokale test met de `SHAKKA_TEST_*`-variabelen. De lokale secret key alleen als env, nooit in een bestand.
   - Lukt het niet, noteer dat dan in `deviations.md` (alleen bewijs, geen ontwerpwijziging).

   Commit: `test(spots): optional sync test against local Supabase`.
9. **Eindcontrole.**
   - `cd ingest && uv sync && uv run pytest && uv run ruff check . && uv run ruff format --check .`;
   - `uv run shakka spots validate`: exitcode 0;
   - `git grep --untracked -nE "sb_(secret|publishable)_[A-Za-z0-9_-]{20,}|eyJhbGciOi" -- . ':!docs'`: geen treffers;
   - controleer dat `git diff develop -- data/spots.yaml` alleen de 25 spots met drie sleutels bevat (AC-2);
   - push alleen met toestemming van de orchestrator.
