# Blueprint WP-04: Getij-ingest (Rijkswaterstaat)
Status: DRAFT
Revisie: 1

## Doel
Eén keer per dag per gebruikt Rijkswaterstaat-station de astronomische hoog- en laagwaters ophalen (venster `now - 1 dag` tot `now + 8 dagen`), omrekenen naar cm NAP en UTC, en opslaan in `tide_extremes`. Oude extremen (`at < now - 48h`) worden opgeruimd. Daarnaast komen er:
- een pure functie `estimate_tide_level` die de waterstand op een willekeurig tijdstip schat met een cosinus tussen opeenvolgende extremen (input voor WP-05);
- `shakka tides stations`, waarmee Lars per spot een `rws_station` kiest;
- `shakka tides fetch [--force]`, de job die WP-11 elk uur aanroept (met de 20-uursregel).

## Aannames
Dit zijn concrete voorstellen. Lars beoordeelt ze; de reviewer toetst ze.

- **A1. Rechtstreeks via httpx naar de DDAPI20, niet via het package `ddlpy`.** De WP-tekst zegt "via `ddlpy`". Dit ontwerp roept dezelfde Rijkswaterstaat-API (DDAPI20) aan met dezelfde selectiecodes, maar met `httpx` via `shakka.http.make_client()`. Waarom:
  1. `ddlpy` 0.10.0 (laatste release, 23-12-2025, PyPI-naam `rws-ddlpy`) roept `requests.post(..., timeout=None)` aan voor de catalogus en de metingen. Een hangende RWS-call zou de uurlijkse run blokkeren tot de job-timeout van 15 minuten. In de volgorde van WP-11 komen `evaluate` en `alerts` ná `tides`. De projectregel "expliciete timeout" is met `ddlpy` niet te halen zonder monkeypatching.
  2. `ddlpy` trekt `pandas`, `numpy`, `pytz`, `tqdm`, `requests`, `platformdirs` en `click` binnen. Dat is veel gewicht voor twee POST-requests met kleine JSON. `tqdm` schrijft daarnaast voortgangsbalken naar de logs, en `ddlpy.locations()` cachet op schijf.
  3. Met httpx is alles te testen met `httpx.MockTransport` op een echte, ruwe JSON-respons. Dat is een betere fixture dan een pandas-DataFrame.

  De selectie blijft gelijk aan de WP: `ProcesType` `astronomisch`, `Groepering.Code` `GETETBRKD2`, en voor de waterstandreeks `Grootheid.Code` `WATHTE` en `Hoedanigheid.Code` `NAP`. De request-vorm komt uit de broncode van `ddlpy` 0.10 (`endpoints.json`, `_measurements_slice`) en uit de documentatie van Rijkswaterstaat (zie Externe afhankelijkheden). "Een vastgelegde echte ddlpy-respons" (WP-tekst) wordt dus "een vastgelegde echte DDAPI20-respons". De fetch is in tests te vervangen, zoals de WP vraagt. Er komen geen nieuwe dependencies.
- **A2. Eén gegroepeerde request per station.** Volgens rijkswaterstaatdata.nl/waterdata geeft een request met `Groepering.Code` `GETETBRKD2` "zowel de waterstand als het bijbehorende getijextreemtype (hoogwater of laagwater)". De request bevat daarom alleen `ProcesType` en `Groepering`, en géén `Grootheid` of `Hoedanigheid`. De reeks met extreemtypes heeft namelijk `Grootheid`/`Hoedanigheid` `NVT` (Deltares kenmerkendewaarden issue #4, hatyan-tests), en die zou anders wegvallen. De parser kiest de kanalen uit de respons:
  - waterstand: `Grootheid.Code == "WATHTE"` en `Hoedanigheid.Code == "NAP"`, met `Eenheid.Code == "cm"`;
  - type: `Typering.Code == "GETETTPE"`, met de tekst in `Meetwaarde.Waarde_Alfanumeriek`.

  Voor gemeten extremen (`GETETM2`) is dit bevestigd in hatyan (`convert_exttype_str2num`, bijgewerkt voor DDAPI20 in hatyan 2.13.0). Voor astronomische extremen is het alleen gedocumenteerd, niet zelf getest: ik kan vanuit de planner geen POST doen. Stap 2 van het stappenplan legt daarom eerst een echte respons vast, met harde stopregels. Wijkt de respons af, dan stopt de builder met een `deviations.md`.
- **A3. Codering van het extreemtype en aggers.** De codelijst is `hoogwater`, `laagwater`, `laagwater 1`, `topagger` en `laagwater 2` (hatyan, `convert_exttype_str2num`). Het voorstel:

  | RWS-tekst (na `strip().lower()`) | `kind` |
  |---|---|
  | `hoogwater` | `high` |
  | `laagwater`, `laagwater 1`, `laagwater 2` | `low` |
  | `topagger` | niet opgeslagen |
  | iets anders | `TideFetchError`: het station faalt en de bestaande data blijft staan |

  Gevolg: bij Hoek van Holland (dubbel laagwater) kunnen twee `low`-extremen achter elkaar staan. Een topagger is geen hoogwater. Hem als `high` opslaan zou in berichten (WP-08) "hoogwater 03:10" geven, en dat is misleidend. De interpolatie houdt geen rekening met `kind`. LW1 en LW2 geven samen een lange, vlakke laagwaterperiode, en dat klopt met de werkelijkheid. Het WP-criterium "`kind` wisselt af" wordt getoetst met precies die ene uitzondering: een `low`→`low`-paar mag alleen als de bron `laagwater 1` gevolgd door `laagwater 2` zegt. Den Helder heeft volgens openwatersio/tide-database #152 dubbel hoogwater. De tekst daarvan is onbekend. Valt die buiten de lijst, dan faalt dat station zichtbaar (`failed`) en wordt er niets verzonnen.
- **A4. Venster vervangen.** Na een geslaagde fetch worden in `[start, end]` de rijen van dat station verwijderd die niet in deze fetch zaten (`fetched_at < now`). Zo blijven er geen dubbele extremen staan als RWS een tijdstip een minuut verschuift. Volgorde: eerst upsert, dan delete. Faalt de upsert, dan wordt er niets verwijderd.
- **A5. Waarden.** Niveaus worden afgerond met half-up (`math.floor(v + 0.5)`). Een meting met `Kwaliteitswaardecode == "99"`, zonder numerieke waarde of met `|waarde| > 1000` cm wordt overgeslagen (een gat, dus `None` in de interpolatie). Waarden worden nooit `0`.
- **A6. Leeg is fout.** Levert een station 0 extremen op (HTTP 204, `Succesvol: false` of geen bruikbare metingen), dan geeft dat `TideFetchError` en komt het station in `failed`. Een venster van 9 dagen heeft er altijd circa 35. Een tikfout in `rws_station` valt zo meteen op.
- **A7. Geen retries en geen `api_usage` voor RWS in deze WP.** Een gefaald station heeft geen verse rijen. Door de 20-uursregel probeert de volgende uurlijkse run het dus vanzelf opnieuw. Het volume is circa 1 request per station per dag (maximaal 25). RWS publiceert geen limiet en geeft geen uptimegarantie. Registratie in `api_usage` (bron `rws`) en uniforme retries horen bij WP-22.
- **A8. Interpolatie.** De cosinus loopt tussen opeenvolgende extremen, ongeacht `kind`. Een gat van **strikt meer** dan 9 uur geeft `None`; precies 9 uur is toegestaan. Precies op een extreem geeft het niveau van dat extreem, ook bij het eerste of laatste.
- **A9. Coördinaten.** DDAPI20 levert ETRS89 lat/lon (EPSG:4258). Volgens RWS is dat voor weergave gelijk aan WGS84. Een station met lat/lon buiten [-90, 90] of [-180, 180], of zonder coördinaten, wordt overgeslagen in `tides stations`.
- **A10. Stationcodes** zijn de nieuwe DDAPI20-codes, zoals `hoekvanholland` (WP-02-fixture, ddlpy-voorbeelden). Oude codes zoals `HOEKVHLD` werken niet. Lars kiest codes met `shakka tides stations`.
- **A11. Uitbreidingen op het contract** (alleen toevoegingen, niets hernoemd):
  - `fetch_tide_extremes(..., *, http: httpx.Client | None = None)` en `list_tide_stations(*, http=None)`;
  - `TideIngestResult` krijgt `errors: list[str]` en `deleted: int`;
  - `TideExtreme` krijgt `to_row()` en `from_row()` voor WP-10;
  - extra pure helpers in `shakka.rws.tides` (request builders en parsers).
- **A12. Geen Docker bij de builder** (zie WP-01 D1). AC-5 wordt dan door de verifier of door Lars tegen de lokale stack gedraaid. De unit-tests dekken de job volledig af met `FakeSupabase`.

## Ontwerp

**Drie lagen, gescheiden zoals de projectregels voorschrijven.**
1. `shakka.domain.tide` (puur): het model `TideExtreme` en `estimate_tide_level`. Imports alleen `bisect`, `math`, `datetime`, `typing`, `collections.abc` en `pydantic`. `tests/test_domain_purity.py` dekt het nieuwe bestand automatisch.
2. `shakka.rws.tides` (I/O): de URL's en selectiecodes als constanten, pure request-builders en parsers, en twee fetch-functies op httpx. Dit is de enige plek in `ingest/src` waar `rijkswaterstaat.nl` voorkomt (een test bewaakt dat).
3. `shakka.jobs.tides` (I/O-lijm): stations uit `spots` halen, de 20-uursregel toepassen, per station ophalen, upserten en het venster vervangen, met foutisolatie per station. Daarna het globale opruimen.

**Waarom één gegroepeerde request.** Zie A2. De parser is defensief: hij negeert kanalen met een ander `ProcesType` of een andere `Groepering` en voegt waterstand en type samen op tijdstip (als UTC-instant). Een waterstand zonder type, een onbekend type, een verkeerde eenheid of tegenstrijdige dubbele tijdstippen geven allemaal `TideFetchError`. Zo komt er nooit half-geïnterpreteerde data in de database. Een station dat faalt, houdt zijn vorige data. Die dekt door het venster van 8 dagen vooruit nog dagen af.

**Tijd.** RWS geeft `Tijdstip` met een vaste offset `+01:00` (MET, ook in de zomer). De parser gebruikt `datetime.fromisoformat` en `.astimezone(UTC)`, dus de offset in de string bepaalt de omrekening. Een zomerdatum `12:00+01:00` wordt `11:00Z`, niet `10:00Z`. Requests sturen UTC met milliseconden (`2026-10-13T12:00:00.000+00:00`), net als `ddlpy` 0.10 (`_check_convert_dates`).

**20-uursregel.** Een station is "vers" als er een rij is met `fetched_at > now - 20h` (strikt). Dat kost één `select` op `tide_extremes`. Na een geslaagde fetch hebben alle rijen van het station in het venster `fetched_at = now`. Normaal haalt de uurlijkse run dus eens per ~20–21 uur per station op, en anders 0 RWS-requests.

**Catalogus.** `list_tide_stations` haalt de catalogus op (`OphalenCatalogus`) en koppelt `AquoMetadataLocatieLijst` aan `LocatieLijst` en `AquoMetadataLijst`, op dezelfde manier als `ddlpy.locations()`. Daarna filtert hij op de vier selectiecodes. Dit commando draait alleen handmatig, niet elk uur. Het heeft een timeout van 60 s, want de catalogus kan enkele MB zijn.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/domain/tide.py` | aanmaken | `TideKind`, `MAX_EXTREME_GAP`, `MAX_ABS_LEVEL_CM`, `TideExtreme`, `estimate_tide_level` |
| `ingest/src/shakka/rws/__init__.py` | aanmaken | Alleen de docstring `"""Rijkswaterstaat WaterWebservices (DDAPI20) client."""` |
| `ingest/src/shakka/rws/tides.py` | aanmaken | Constanten, `StationInfo`, `TideFetchError`, `format_rws_time`, `build_extremes_request`, `build_catalogue_request`, `parse_extremes_response`, `parse_stations`, `fetch_tide_extremes`, `list_tide_stations` |
| `ingest/src/shakka/jobs/__init__.py` | aanmaken (als hij nog niet bestaat) | Alleen de docstring `"""Jobs: glue between domain logic, external sources and the database."""`. Bestaat hij al (WP-02/WP-03 eerder gemerged), dan niet wijzigen. |
| `ingest/src/shakka/jobs/tides.py` | aanmaken | `TideIngestResult`, `TideFetcher`, constanten, `run_tide_ingest`, `delete_old_tides` |
| `ingest/src/shakka/cli.py` | wijzigen | Groep `tides` met `fetch [--force]` en `stations [--search TEXT]`, toegevoegd onder `doctor` en vóór `main()`. Imports lui (binnen de functies), net als bij `doctor`. |
| `ingest/scripts/capture_rws_fixtures.py` | aanmaken | Script dat de echte respons vastlegt (stap 2). Wordt niet door pytest gedraaid. Bevat geen hostnaam: importeert de URL's uit `shakka.rws.tides`. |
| `ingest/tests/fixtures/rws/waarnemingen_hoekvanholland.json` | aanmaken (vastgelegd) | Ruwe respons van `OphalenWaarnemingen`, venster 9 dagen |
| `ingest/tests/fixtures/rws/catalogus_subset.json` | aanmaken (vastgelegd) | Echte catalogus, ingekort volgens de regels in Interfaces |
| `ingest/tests/fixtures/rws/capture_info.json` | aanmaken (vastgelegd) | Metadata van de capture |
| `ingest/tests/test_domain_tide.py` | aanmaken | Model- en interpolatietests (AC-2) |
| `ingest/tests/test_rws_tides.py` | aanmaken | Builders, parsers op de fixtures (AC-1), fetch met MockTransport, hostbewaking |
| `ingest/tests/test_job_tides.py` | aanmaken | Jobtests met `FakeSupabase` (AC-3) |
| `ingest/tests/test_cli_tides.py` | aanmaken | CLI-tests (gemockt) |
| `docs/RUNBOOK.md` | wijzigen | Nieuwe sectie 9 "Getij (Rijkswaterstaat)" (zie Interfaces) |

Geen wijzigingen aan `pyproject.toml`, `uv.lock`, migraties, `shakka.db` of `tests/fakes.py`. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### Database (ongewijzigd, uit WP-01)
`tide_extremes(station text, at timestamptz, kind text check in ('high','low'), level_cm integer not null, fetched_at timestamptz not null)`, PK (`station`, `at`). Leesbaar voor `anon` en `authenticated`, schrijven alleen met de secret key. `TABLE_KEYS["tide_extremes"] == ("station", "at")`.

### `shakka.domain.tide`
```python
"""Tide extremes and water level interpolation. Pure: no I/O, no clock."""

TideKind = Literal["high", "low"]
MAX_EXTREME_GAP: Final = timedelta(hours=9)   # gap > this between two extremes -> no estimate
MAX_ABS_LEVEL_CM: Final = 1000                # sanity bound for NAP levels in cm

class TideExtreme(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    station: Annotated[str, Field(min_length=1, max_length=64)]
    at: datetime                                  # validator: aware required, normalised to UTC
    kind: TideKind
    level_cm: Annotated[int, Field(strict=True, ge=-MAX_ABS_LEVEL_CM, le=MAX_ABS_LEVEL_CM)]

    # field_validator("at"): naive (tzinfo None or utcoffset None) -> ValueError("at must be
    # timezone-aware"); otherwise return value.astimezone(UTC) (tzinfo is datetime.UTC).

    def to_row(self) -> dict[str, Any]:
        """{"station", "at" (aware UTC datetime), "kind", "level_cm"}; the job adds fetched_at."""
    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "TideExtreme":
        """Build from a tide_extremes row (PostgREST JSON). Uses only station, at, kind, level_cm;
        other keys (fetched_at) are ignored. `at` may be an ISO string with any offset."""

def estimate_tide_level(extremes: Sequence[TideExtreme], at: datetime) -> int | None: ...
```

`estimate_tide_level`, exact gedrag:
```
if at is naive: raise ValueError
if not extremes: return None
if more than one distinct station in extremes: raise ValueError("extremes from more than one station")
by_time = {}  # UTC instant -> extreme; the same instant with another level_cm -> ValueError
times = sorted(by_time); t = at.astimezone(UTC)
i = bisect_left(times, t)
if i < len(times) and times[i] == t: return by_time[t].level_cm
if i == 0 or i == len(times): return None              # before first / after last
t0, t1 = times[i-1], times[i]
if t1 - t0 > MAX_EXTREME_GAP: return None
f = (t - t0) / (t1 - t0)                                # 0 < f < 1
h = h0 + (h1 - h0) * (1 - cos(pi * f)) / 2
return math.floor(h + 0.5)
```
De invoer hoeft niet gesorteerd te zijn. `kind` wordt niet gebruikt. Dezelfde instant met hetzelfde niveau mag (dat telt als één extreem).

### `shakka.rws.tides`
```python
RWS_BASE_URL: Final = "https://ddapi20-waterwebservices.rijkswaterstaat.nl"
OBSERVATIONS_URL: Final = f"{RWS_BASE_URL}/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen"
CATALOGUE_URL: Final = f"{RWS_BASE_URL}/METADATASERVICES/OphalenCatalogus"

PROCES_TYPE: Final = "astronomisch"
GROEPERING: Final = "GETETBRKD2"
GROOTHEID: Final = "WATHTE"
HOEDANIGHEID: Final = "NAP"
EENHEID: Final = "cm"
TYPERING_EXTREME_TYPE: Final = "GETETTPE"
INVALID_QUALITY_CODE: Final = "99"
EXTREME_TYPE_KIND: Final[Mapping[str, TideKind | None]] = {
    "hoogwater": "high", "laagwater": "low", "laagwater 1": "low",
    "laagwater 2": "low", "topagger": None,   # None = valid type, not stored
}
OBSERVATIONS_TIMEOUT_S: Final = 30.0
CATALOGUE_TIMEOUT_S: Final = 60.0
MAX_ERROR_TEXT: Final = 200
STATION_CODE_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

class TideFetchError(Exception): ...

@dataclass(frozen=True, slots=True)
class StationInfo:
    code: str
    name: str
    lat: float
    lon: float

def format_rws_time(value: datetime) -> str:
    """Aware -> UTC 'YYYY-MM-DDTHH:MM:SS.mmm+00:00' (isoformat(timespec='milliseconds')).
    Naive -> ValueError."""

def build_extremes_request(station: str, start: datetime, end: datetime) -> dict[str, Any]:
    """Exactly:
    {"Locatie": {"Code": station},
     "AquoPlusWaarnemingMetadata": {"AquoMetadata": {"ProcesType": "astronomisch",
                                                     "Groepering": {"Code": "GETETBRKD2"}}},
     "Periode": {"Begindatumtijd": format_rws_time(start), "Einddatumtijd": format_rws_time(end)}}
    ValueError if start/end naive or start >= end."""

def build_catalogue_request() -> dict[str, Any]:
    """Exactly: {"CatalogusFilter": {"Compartimenten": True, "Eenheden": True, "Grootheden": True,
    "Groeperingen": True, "Hoedanigheden": True, "ProcesTypes": True, "Typeringen": True}}"""

def parse_extremes_response(payload: Any, station: str) -> list[TideExtreme]: ...
def parse_stations(payload: Any) -> list[StationInfo]: ...

def fetch_tide_extremes(station: str, start: datetime, end: datetime, *,
                        http: httpx.Client | None = None) -> list[TideExtreme]: ...
def list_tide_stations(*, http: httpx.Client | None = None) -> list[StationInfo]: ...
```

**`parse_extremes_response(payload, station)`**. Hulpregel: `code(obj, key)` = `obj.get(key, {}).get("Code", "")` als dat dicts zijn, anders `""`. Stappen:
1. `payload` is geen dict → `TideFetchError(f"{station}: unexpected response")`.
2. `payload.get("Succesvol") is False` → `TideFetchError(f"{station}: RWS error: {str(payload.get('Foutmelding'))[:MAX_ERROR_TEXT]}")`.
3. `WaarnemingenLijst` ontbreekt of is geen lijst → `TideFetchError(f"{station}: unexpected response")`.
4. Per item `w` in `WaarnemingenLijst`, met `meta = w.get("AquoMetadata") or {}`:
   - overslaan als `meta.get("ProcesType")` aanwezig is en niet `"astronomisch"` is, of als `code(meta, "Groepering")` niet leeg is en niet `"GETETBRKD2"` is;
   - een **typekanaal** als `code(meta, "Typering") == "GETETTPE"`;
   - anders een **niveaukanaal** als `code(meta, "Grootheid") == "WATHTE"` en `code(meta, "Hoedanigheid") == "NAP"`. Dan moet `code(meta, "Eenheid") == "cm"`, anders volgt `TideFetchError(f"{station}: unexpected unit ...")`;
   - anders negeren.
5. Geen niveaukanaal → `TideFetchError(f"{station}: no NAP water level channel")`. Geen typekanaal → `TideFetchError(f"{station}: no extreme type channel")`.
6. Niveaus, per meting `m` in de `MetingenLijst` van alle niveaukanalen:
   - `t = datetime.fromisoformat(m["Tijdstip"])`. Is die naive of niet te parsen, dan volgt `TideFetchError`. Daarna `t = t.astimezone(UTC)`;
   - overslaan als `WaarnemingMetadata.Kwaliteitswaardecode == "99"`, als `Meetwaarde.Waarde_Numeriek` ontbreekt, geen `int`/`float` is (bool telt niet) of niet eindig is, of als `abs(v) > MAX_ABS_LEVEL_CM`;
   - `level = math.floor(v + 0.5)`;
   - is er al een niveau voor `t`, dan geeft een ander getal `TideFetchError(... "conflicting levels")`; hetzelfde getal wordt genegeerd.
7. Types, per meting in alle typekanalen: `t` zoals hierboven, en `text = str(Meetwaarde.Waarde_Alfanumeriek or "").strip().lower()`.
   - `text` niet in `EXTREME_TYPE_KIND` → `TideFetchError(f"{station}: unknown extreme type {text!r}")` (tekst ingekort tot 40 tekens);
   - een conflicterend type op dezelfde `t` → `TideFetchError`.
8. Per niveau-tijdstip (oplopend):
   - zonder type op exact dezelfde instant → `TideFetchError(f"{station}: missing extreme type at {t}")`;
   - is het type `None` (topagger), dan wordt dat tijdstip niet opgeslagen;
   - anders `TideExtreme(station=station, at=t, kind=..., level_cm=level)`.

   Types zonder niveau worden genegeerd.
9. Resultaat leeg → `TideFetchError(f"{station}: no extremes")`. Anders de lijst, gesorteerd op `at`.

**`parse_stations(payload)`**
1. `payload.get("Succesvol") is False` → `TideFetchError("catalogue: RWS error: ...")`. `AquoMetadataLijst`, `LocatieLijst` of `AquoMetadataLocatieLijst` ontbreekt of is geen lijst → `TideFetchError("catalogue: unexpected response")`.
2. `ids`: de verzameling `AquoMetadata_MessageID` van de metadata-items met `item.get("ProcesType") == "astronomisch"`, `code(item, "Grootheid") == "WATHTE"`, `code(item, "Groepering") == "GETETBRKD2"` en `code(item, "Hoedanigheid") == "NAP"`.
3. Koppelingen: de metadata-id staat onder `AquoMetaData_MessageID` (zo spelt RWS het, zie `ddlpy.locations()`). Als die sleutel ontbreekt, wordt `AquoMetadata_MessageID` gebruikt. De locatie-id staat onder `Locatie_MessageID`. `loc_ids` = de locatie-id's waarvan de metadata-id in `ids` zit.
4. Per item in `LocatieLijst` met `Locatie_MessageID` in `loc_ids`, in lijstvolgorde:
   - `code = str(Code)`;
   - `name = str(Naam or "")`;
   - `lat` en `lon` via `float()`, voor `int`, `float` of `str` (bool niet);
   - overslaan als `code` leeg is, of als lat/lon ontbreken, niet eindig zijn of buiten [-90, 90] / [-180, 180] vallen;
   - de eerste per `code` wint.
5. Resultaat leeg → `TideFetchError("catalogue: no stations with astronomical extremes")`. Anders gesorteerd op `code`.

**Fetch-gedrag** (beide functies, via één interne helper `_post_json(client, url, body, *, label) -> Any`):
- Wordt `http` niet meegegeven, dan komt de client uit `make_client(timeout=OBSERVATIONS_TIMEOUT_S)` (of `CATALOGUE_TIMEOUT_S`) en wordt hij in een `with`-blok gesloten. Een meegegeven client wordt niet gesloten.
- `client.post(url, json=body)`.
- `httpx.HTTPError` → `raise TideFetchError(f"{label}: {type(exc).__name__}") from None`.
- Status 204 → `TideFetchError(f"{label}: no data (HTTP 204)")`. Status buiten 200–299 (ook 3xx) → `TideFetchError(f"{label}: HTTP {status}")`, plus `: {Foutmelding[:200]}` als de body JSON met `Foutmelding` is. Een body die geen JSON is → `TideFetchError(f"{label}: invalid JSON")`.
- `label` is de stationcode, of `catalogue`.
- `fetch_tide_extremes` controleert eerst:
  - `station` matcht niet op `STATION_CODE_RE` → `TideFetchError(f"invalid station code {station!r}")` (ingekort tot 70 tekens), zonder request;
  - `start`/`end` naive of `start >= end` → `ValueError`, zonder request.

  Daarna doet hij `parse_extremes_response(payload, station)`.
- `list_tide_stations` doet `parse_stations(payload)`.

### `shakka.jobs.tides`
```python
TIDE_REFRESH_AFTER: Final = timedelta(hours=20)
TIDE_WINDOW_BEFORE: Final = timedelta(days=1)
TIDE_WINDOW_AFTER: Final = timedelta(days=8)
TIDE_RETENTION: Final = timedelta(hours=48)

TideFetcher = Callable[[str, datetime, datetime], Sequence[TideExtreme]]

@dataclass(frozen=True, slots=True)
class TideIngestResult:
    stations: int                 # stations fetched and stored successfully in this run
    rows: int                     # rows upserted
    skipped: list[str]            # fresh (< 20h), sorted
    failed: list[str]             # sorted
    errors: list[str] = field(default_factory=list)   # "<station>: <ExcType>: <msg[:200]>"
    deleted: int = 0              # rows removed by the 48h cleanup

def run_tide_ingest(db: SupabaseRest, *, now: datetime, force: bool = False,
                    fetch: TideFetcher = fetch_tide_extremes) -> TideIngestResult: ...
def delete_old_tides(db: SupabaseRest, *, now: datetime) -> int: ...
```
`db` is getypeerd als `SupabaseRest`. In tests werkt `FakeSupabase` ook (duck typing, dezelfde methoden).

`run_tide_ingest`, exact:
1. `now` is naive → `ValueError`.
2. `rows = db.select("spots", columns="id,rws_station")`. Daaruit `stations` = de gesorteerde unieke lijst van `str(r["rws_station"]).strip()` voor de rijen waar die waarde niet `None` is en na `strip()` niet leeg.
3. Als `stations` leeg is: geen fetch, ga naar stap 6.
4. `fresh = set()`. Zonder `force`:
   ```python
   recent = db.select("tide_extremes", columns="station",
                      filters={"station": in_filter(stations),
                               "fetched_at": f"gt.{iso_utc(now - TIDE_REFRESH_AFTER)}"})
   fresh = {r["station"] for r in recent}
   ```
   `skipped = sorted(fresh ∩ stations)`.
5. Per station in `stations` dat niet in `fresh` zit, in volgorde. `start = now - TIDE_WINDOW_BEFORE`, `end = now + TIDE_WINDOW_AFTER`. Alles in `try`/`except Exception as exc`:
   - `extremes = list(fetch(station, start, end))`;
   - elk extreem heeft `e.station == station`, anders `ValueError("fetch returned another station")`;
   - dedupliceren op `e.at`: hetzelfde `level_cm` en `kind` geeft één rij, iets anders een `ValueError`;
   - `payload = [e.to_row() | {"fetched_at": now} for e in deduped]`;
   - `db.upsert("tide_extremes", payload, on_conflict="station,at")`;
   - `db.delete("tide_extremes", filters={"station": f"eq.{station}", "at": [f"gte.{iso_utc(start)}", f"lte.{iso_utc(end)}"], "fetched_at": f"lt.{iso_utc(now)}"})`;
   - daarna `stations_ok += 1` en `rows += len(payload)`.

   Bij een exception: `failed.append(station)`, `errors.append(f"{station}: {type(exc).__name__}: {str(exc)[:200]}")` en `logger.warning` met dezelfde tekst. Ga door met het volgende station.
6. `deleted = delete_old_tides(db, now=now)`. Een exception hier en in stap 2 en 4 wordt **niet** afgevangen: dat is een databaseprobleem voor de hele stap, en WP-11 isoleert per stap.
7. Return `TideIngestResult(stations_ok, rows, skipped, sorted(failed), errors, deleted)`.

`delete_old_tides`: `db.delete("tide_extremes", filters={"at": f"lt.{iso_utc(now - TIDE_RETENTION)}"})`, en geeft het aantal terug. Een naive `now` geeft `ValueError`.

Logger: `logging.getLogger(__name__)`. Aan het eind één `info` met de tellingen.

### CLI (`shakka.cli`)
```python
@cli.group()
def tides() -> None:
    """Rijkswaterstaat astronomical tide extremes."""

@tides.command("fetch")
@click.option("--force", is_flag=True, help="Ignore the 20-hour freshness rule.")
def tides_fetch(force: bool) -> None: ...

@tides.command("stations")
@click.option("--search", default=None, help="Case-insensitive filter on code or name.")
def tides_stations(search: str | None) -> None: ...
```
Imports gebeuren binnen de functies, als modules: `import shakka.rws.tides as rws`, `import shakka.jobs.tides as job`, `from shakka.db import SupabaseRest, DatabaseError`, `from shakka.config import get_settings`, `from shakka.http import make_client`. Zo kunnen tests `rws.list_tide_stations`, `rws.fetch_tide_extremes` en `SupabaseRest.from_settings` monkeypatchen.

`tides stations`:
- roept `rws.list_tide_stations()` aan, zonder settings en zonder `.env`;
- filtert met `--search`: hoofdletterongevoelige substring op `code` of `name`;
- print de kop `code\tname\tlat\tlon`, daarna per station `f"{s.code}\t{s.name}\t{s.lat:.5f}\t{s.lon:.5f}"`, en als laatste regel `f"{n} stations"`. Exitcode 0.
- Bij `TideFetchError`: `tides stations: <melding>` naar stderr, exitcode 1.

`tides fetch`:
1. `get_settings()`. Bij `pydantic.ValidationError`: print `tides fetch: configuration incomplete (run 'shakka doctor')`, exit 1, zonder waarden.
2. `with SupabaseRest.from_settings(settings) as db, make_client(timeout=rws.OBSERVATIONS_TIMEOUT_S) as http:` en daarbinnen `result = job.run_tide_ingest(db, now=datetime.now(UTC), force=force, fetch=functools.partial(rws.fetch_tide_extremes, http=http))`.
3. Uitvoer:
   - `tides: fetched {stations} station(s), {rows} row(s), deleted {deleted} old row(s)`;
   - als `skipped` niet leeg is: `tides: skipped (fetched < 20h ago): a, b`;
   - als `failed` niet leeg is: `tides: failed: a, b` en per `errors`-regel `  <regel>`.
4. Exitcode 1 als `failed` niet leeg is, anders 0.
5. Een `DatabaseError` (uit stap 2, 4 of 6 van de job): `tides fetch: database error: <str(exc)>`, exit 1. De meldingen van `DatabaseError` zijn al geredigeerd (WP-01).

### `ingest/scripts/capture_rws_fixtures.py`
Draaien: `cd ingest && uv run python scripts/capture_rws_fixtures.py`. Gedrag:
1. `now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)`. Venster: `start = now - 1 dag` en `end = now + 8 dagen`. Station: `hoekvanholland`.
2. `with make_client(timeout=60.0) as c`:
   - POST naar `OBSERVATIONS_URL` met `build_extremes_request(...)`;
   - POST naar `CATALOGUE_URL` met `build_catalogue_request()`.

   Een status buiten 200 geeft een duidelijke exit 1, zonder bestanden te schrijven.
3. Schrijft `tests/fixtures/rws/waarnemingen_hoekvanholland.json`: de geparste respons opnieuw geserialiseerd met `json.dumps(payload, indent=1, ensure_ascii=False) + "\n"`.
4. Inkorten van de catalogus. De gekozen locaties zijn:
   - `hoekvanholland` en `vlissingen` (als die bestaan);
   - de eerste locatie (op `Code`) zónder koppeling aan een metadata-item dat aan de vier selectiecodes voldoet. Dat is het negatieve geval.

   Daarvan blijven bewaard:
   - die `LocatieLijst`-items;
   - alle `AquoMetadataLocatieLijst`-items van die locaties;
   - alle `AquoMetadataLijst`-items waarnaar die koppelingen verwijzen;
   - alle andere top-level sleutels ongewijzigd.

   Wegschrijven naar `tests/fixtures/rws/catalogus_subset.json` in hetzelfde formaat. Faalt dit bij > 500 kB, dan is het inkorten mislukt.
5. Schrijft `tests/fixtures/rws/capture_info.json` met:
   - `captured_at`, `station`, `begin`, `end` (ISO UTC);
   - `request_waarnemingen` en `request_catalogus`;
   - `catalogue_station_count`: het aantal stations in `parse_stations` van de volledige catalogus;
   - `negative_location`: de code van de negatieve locatie.
6. Print per item in `WaarnemingenLijst`:
   - `ProcesType` en de codes van `Grootheid`, `Hoedanigheid`, `Eenheid`, `Groepering` en `Typering`;
   - het aantal metingen;
   - voor een typekanaal de verzameling `Waarde_Alfanumeriek`-waarden.

   Daarnaast print hij of `hoekvanholland` in `parse_stations` voorkomt, met de naam erbij.

### `docs/RUNBOOK.md`, nieuwe sectie 9 "Getij (Rijkswaterstaat)" (Nederlands)
- `uv run shakka tides stations --search hoek` toont stations met astronomische hoog- en laagwaters (code, naam, lat, lon). Zet de `code` als `rws_station` in `data/spots.yaml`. Neem het dichtstbijzijnde station aan dezelfde kust of hetzelfde zeegat. Dit commando heeft geen `.env` nodig.
- `uv run shakka tides fetch` haalt per station eens per 20 uur op; `--force` negeert die regel. Exitcode 1 betekent dat minstens één station faalde (zie de regels onder `failed`).
- Hoek van Holland kent een dubbel laagwater. Dat wordt opgeslagen als twee laagwaters; de topagger ertussen wordt niet opgeslagen.
- Een onbekend extreemtype (bijv. bij dubbel hoogwater) laat het station falen in plaats van iets te raden. Meld het dan als issue.
- Bron: Rijkswaterstaat WaterWebservices (DDAPI20), CC0. Geen uptimegarantie. Een storing van een paar dagen is geen probleem, want er staat 8 dagen vooruit in de database.
- Fixtures opnieuw vastleggen: `uv run python scripts/capture_rws_fixtures.py`. Daarna de tests bijwerken: `EXPECTED_EXTREMES` in `tests/test_rws_tides.py`.

### Gevolgen voor latere WP's
- **WP-05:**
  - `estimate_tide_level` krijgt de extremen van één station; extremen van meerdere stations geven `ValueError`;
  - `kind` kan twee keer `low` achter elkaar zijn (agger). Gebruik voor `prefer_low`, `prefer_high` en `avoid_low` het geschatte niveau, of de afstand tot het dichtstbijzijnde extreem van de gewenste soort, en ga niet uit van strikte afwisseling;
  - `None` betekent: geen schatting (`tide_unknown`).
- **WP-08:** berichten kunnen twee laagwaters kort na elkaar tonen. Dat klopt voor Hoek van Holland.
- **WP-10:** laad met `TideExtreme.from_row(row)`. Filter op `station=eq.<code>` en een `at`-bereik dat ruim genoeg is voor de interpolatie, dus minstens 9 uur vóór het eerste en na het laatste te evalueren uur.
- **WP-11:** roept `run_tide_ingest(db, now=now, fetch=partial(fetch_tide_extremes, http=http))` aan. `failed` niet leeg betekent dat de stap `partial` is (aan WP-11 om te beslissen). Exceptions uit de job zijn databasefouten.
- **WP-22:** `api_usage`-registratie voor bron `rws` en eventuele retries.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `rws_station` is `null`, `""` of alleen spaties | Genegeerd |
| E2 | Twee spots met hetzelfde station, ook met spaties eromheen | Eén fetch (na `strip()`) |
| E3 | Station 19 uur geleden opgehaald | `skipped`, geen fetch; met `force=True` wel een fetch |
| E4 | Precies 20 uur geleden, of 21 uur | Fetch (`gt`, strikt) |
| E5 | Fetch geeft een exception (`TideFetchError`, `RuntimeError`, …) | Station in `failed` en `errors`, de rest gaat door, de oude rijen van dat station blijven staan |
| E6 | Upsert of venster-delete faalt (`DatabaseError`) | Station in `failed`. Faalde alleen de delete, dan zijn de rijen wel opgeslagen (verse `fetched_at`, dus 20 uur geen nieuwe fetch) en blijven eventuele verschoven oude extremen tot de volgende fetch staan. |
| E7 | `select` op `spots` of `tide_extremes`, of de 48h-cleanup faalt | `DatabaseError` propageert; de CLI geeft exit 1 en WP-11 markeert de stap |
| E8 | Geen enkele spot heeft een station | Geen fetch; de cleanup draait wel; resultaat `stations=0, rows=0` |
| E9 | RWS verschuift een extreem (10:01 → 10:02) | De nieuwe rij wordt opgeslagen en de oude (`fetched_at < now`, binnen het venster) verwijderd |
| E10 | Rijen van het station buiten het venster (bijv. `now - 30h`) | Blijven staan tot de 48h-cleanup |
| E11 | `at` precies `now - 48h` | Blijft (`lt`, strikt); `now - 48h - 1s` gaat weg |
| E12 | HTTP 204, `Succesvol: false`, 0 bruikbare metingen | `TideFetchError` (A6) |
| E13 | HTTP 5xx, 4xx of 3xx, timeout, connectiefout, geen JSON | `TideFetchError` met status of klassenaam; de body wordt hooguit 200 tekens getoond, alleen `Foutmelding` |
| E14 | `Tijdstip` met `+01:00` in de zomer | Omgerekend met de offset uit de string (12:00+01:00 → 11:00Z) |
| E15 | `Tijdstip` zonder offset of onparseerbaar | `TideFetchError` |
| E16 | `topagger` | Niet opgeslagen; LW1 en LW2 worden twee `low`-extremen |
| E17 | Onbekende typetekst of een niveau zonder type | `TideFetchError`, het station faalt (fail closed) |
| E18 | Kwaliteitscode `99`, `Waarde_Numeriek` `null`, NaN of 999999999 | Meting overgeslagen; geeft een gat (interpolatie `None` bij een gat > 9 uur) |
| E19 | Eenheid niet `cm` | `TideFetchError` |
| E20 | Kanaal met `Hoedanigheid` `MSL`, een ander `ProcesType` of een andere `Groepering` | Genegeerd |
| E21 | Dezelfde instant twee keer met hetzelfde niveau | Eén extreem; met een ander niveau `TideFetchError` |
| E22 | Fetch geeft een extreem van een ander station, of conflicterende duplicaten | `ValueError` in de job, station in `failed` |
| E23 | Ongeldige stationcode (spatie, `/`, > 64 tekens) | `TideFetchError` zonder request |
| E24 | `estimate_tide_level` met een naive `at`, of extremen van twee stations | `ValueError` |
| E25 | `estimate_tide_level` met 0 extremen, of 1 extreem en `at` daar niet op | `None` |
| E26 | Ongesorteerde extremen | Zelfde uitkomst als gesorteerd |
| E27 | Gat van precies 9 uur | Schatting; bij 9 uur en 1 seconde `None` |
| E28 | Catalogus: locatie zonder coördinaten of buiten bereik | Overgeslagen |
| E29 | Catalogus zonder enige match | `TideFetchError` (schemadrift valt op) |
| E30 | Koppelingssleutel `AquoMetadata_MessageID` in plaats van `AquoMetaData_MessageID` | Beide geaccepteerd |
| E31 | Naive `now` in de job of in de cleanup | `ValueError` |
| E32 | Twee keer `run_tide_ingest(force=True)` met dezelfde data | Zelfde aantal rijen (idempotent) |

## Testplan
Tests eerst: `test_domain_tide.py` vóór `domain/tide.py`, en de parsertests vóór de parsers. De fixtures komen uit stap 2. Vaste testtijd: `NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)`. Helper in de tests: `ext(station, iso, kind, level)`.

### AC-1: conversietest op de fixture (`tests/test_rws_tides.py`)
Fixture: `waarnemingen_hoekvanholland.json` met `capture_info.json`. `result = parse_extremes_response(payload, "hoekvanholland")`.
- `test_fixture_count`: `len(result) == EXPECTED_EXTREMES`. Die constante zet de builder na stap 2 hard in de test, met een commentaar over hoe hij geteld is: het aantal metingen in het WATHTE/NAP-kanaal min het aantal `topagger`-types, geteld met een losse `jq`- of Python-oneliner op de fixture. Tweede controle in dezelfde test, onafhankelijk van de parser: een eenvoudige telling over de ruwe JSON op exact die regel geeft hetzelfde getal.
- `test_fixture_kinds_alternate`: voor elk opeenvolgend paar `(a, b)` geldt `a.kind != b.kind`, met als enige uitzondering `a.kind == b.kind == "low"` waarbij de ruwe types op `a.at` en `b.at` `laagwater 1` en `laagwater 2` zijn (typekaart uit de ruwe JSON). Zonder aggers in de fixture is de afwisseling dus strikt.
- `test_fixture_levels_are_int`: `type(e.level_cm) is int` voor alle extremen.
- `test_fixture_times_utc`: `e.at.tzinfo is UTC` voor alle, plus sortering. Het eerste en laatste extreem zijn gelijk aan `datetime.fromisoformat(<ruwe Tijdstip>).astimezone(UTC)` en `floor(<ruwe waarde> + 0.5)`.
- `test_fixture_window`: alle `at` liggen binnen `[begin, end]` uit `capture_info.json`.
- `test_offset_plus_one_converted`: een synthetische payload met één niveau en één type op `"2026-10-14T12:00:00.000+01:00"` geeft `at == datetime(2026, 10, 14, 11, 0, tzinfo=UTC)`. Een tweede case met `"2026-07-01T12:00:00.000+01:00"` geeft 11:00Z (E14).

Synthetische parsertests (kleine payloads uit een helper `payload(levels=[...], types=[...], unit="cm", ...)`):
- topagger wordt niet opgeslagen; `laagwater 1` en `laagwater 2` worden `low`; hoofdletters en spaties in de typetekst maken niet uit;
- onbekend type, een niveau zonder type, eenheid `m`, ontbrekend niveau- of typekanaal, een tijdstip zonder offset, conflicterende niveaus: elk geeft `TideFetchError` (E15, E17, E19, E21);
- kwaliteitscode `99`, `null`, `999999999` en een bool-waarde worden overgeslagen; als er dan niets overblijft, volgt `TideFetchError("... no extremes")` (E18, A6);
- een MSL-kanaal en een kanaal met `ProcesType: meting` worden genegeerd (E20);
- `Succesvol: false` met `Foutmelding` van 500 tekens geeft een melding van hooguit 200 tekens uit `Foutmelding`;
- de waarde 12.5 wordt 13 en -12.5 wordt -12 (half-up).

### AC-2: `estimate_tide_level` (`tests/test_domain_tide.py`)
Extremen: H1 = high +100 om 06:00Z, L1 = low -80 om 12:00Z, H2 = high +100 om 18:00Z (14-10-2026, station `x`).
- precies op H1, L1 en H2 geeft 100, -80 en 100;
- 09:00Z (halverwege, 6 uur ertussen) geeft `10` en ligt binnen `10 ± 1`;
- 07:30Z (f = 0,25) geeft `74` (100 − 180·0,14645 = 73,64);
- 05:59Z en 18:01Z geven `None`, net als een lege lijst (AC-2, E25);
- gat: high om 00:00Z en low om 09:00:01Z, op 04:30Z geeft `None`; met low om exact 09:00Z een getal (E27);
- monotonie: voor elke minuut van 06:00 tot 12:00 dalen de waarden of blijven ze gelijk, en van 12:00 tot 18:00 stijgen ze of blijven ze gelijk;
- dezelfde invoer in omgekeerde volgorde geeft dezelfde uitkomsten (E26);
- `low`→`low` (agger: -60 om 12:00 en -55 om 15:00) geeft halverwege `-57` (`floor(-57,5 + 0,5) = -57`), en dat zonder fout;
- een naive `at` en extremen van twee stations geven `ValueError`; hetzelfde tijdstip met twee niveaus geeft `ValueError` (E24);
- een `at` met `+02:00` geeft dezelfde uitkomst als de UTC-equivalent.

Modeltests: een naive `at` geeft `ValidationError`; `at` met `+01:00` wordt UTC; `level_cm=12.0`, `True` en `1001` geven `ValidationError`; `kind="agger"` geeft `ValidationError`; een extra veld geeft `ValidationError`; het model is frozen; `TideExtreme.from_row({"station": "x", "at": "2026-10-14T11:00:00+00:00", "kind": "high", "level_cm": 90, "fetched_at": "..."})` werkt; `from_row(json.loads(to_json(e.to_row()))) == e`.

### AC-3: job (`tests/test_job_tides.py`, `FakeSupabase` en een nep-fetch)
De nep-fetch is een klasse `FakeFetch` die per station een lijst extremen of een exception teruggeeft en de aanroepen `(station, start, end)` registreert. Spots worden geseed met de sleutels `id`, `name` en `rws_station`.
- `test_unique_nonempty_stations`: de spots `a: hoekvanholland`, `b: " hoekvanholland "`, `c: None`, `d: ""`, `e: "   "` en `f: vlissingen` geven exact de calls `["hoekvanholland", "vlissingen"]` (in die volgorde) met `start == NOW - 1d` en `end == NOW + 8d` (E1, E2).
- `test_fresh_station_skipped`: een geseede rij voor `hoekvanholland` met `fetched_at = NOW - 19h` geeft geen call voor dat station en `skipped == ["hoekvanholland"]`; met `force=True` volgt wel een call en is `skipped == []` (E3). Geparametriseerd met `20h` en `21h`: dan volgt wel een call (E4).
- `test_failure_isolated`: `vlissingen` geeft `TideFetchError`, en in een tweede parameter `RuntimeError`. De rijen van `hoekvanholland` zijn opgeslagen, `failed == ["vlissingen"]`, `errors[0]` begint met `"vlissingen: TideFetchError"`, en een vooraf geseede oude rij van `vlissingen` staat er nog (E5).
- `test_upsert_contract`: `("tide_extremes", "station,at") in db.upserts`; de opgeslagen rijen hebben exact de kolommen `station`, `at`, `kind`, `level_cm` en `fetched_at`, met `fetched_at == NOW`; `rows` is het aantal extremen.
- `test_cleanup_48h`: geseede rijen op `NOW-49h`, `NOW-48h` en `NOW-47h` (ander station, verse `fetched_at` zodat geen fetch nodig is). Na de run is alleen `NOW-49h` weg, en `deleted == 1` (E11). Een spy-subklasse van `FakeSupabase` registreert de `delete`-filters. Eén ervan is exact `{"at": f"lt.{iso_utc(NOW - timedelta(hours=48))}"}`.
- `test_window_replaced`: een geseede rij op `NOW+2d 10:01` met `fetched_at = NOW-25h` en een fetch die `NOW+2d 10:02` geeft. Daarna staat 10:02 er wel en 10:01 niet; een geseede rij op `NOW-30h` van hetzelfde station staat er nog (E9, E10).
- `test_idempotent`: twee keer `force=True` geeft hetzelfde aantal rijen (E32).
- `test_wrong_station_or_conflict_fails`: de fetch geeft een extreem met een ander station, of twee keer dezelfde `at` met andere niveaus. Dan staat het station in `failed` (E22).
- `test_no_stations`: geen spots met een station geeft 0 calls, `stations == 0` en de cleanup draait wel (E8).
- `test_naive_now_rejected` voor `run_tide_ingest` en `delete_old_tides` (E31).

### AC-4: `shakka tides stations` (echte netwerk-call)
Handmatig door de verifier: `cd ingest && uv run shakka tides stations --search "hoek van holland"` en `uv run shakka tides stations | grep -i "Hoek van Holland"` geven exitcode 0 en minstens één regel. Geautomatiseerd en zonder netwerk (`tests/test_rws_tides.py`):
- `test_parse_stations_fixture`: `parse_stations(catalogus_subset)` bevat code `hoekvanholland` met `"Hoek van Holland" in name`, `51 < lat < 53` en `3 < lon < 5`, en niet de `negative_location` uit `capture_info.json`.
- Synthetische tests: `ProcesType` `meting`, `Groepering` `""` en `Hoedanigheid` `MSL` worden uitgesloten; dubbele koppelingen geven één station; lat 200 of `None` wordt overgeslagen; beide MessageID-spellingen werken (E30); geen match geeft `TideFetchError` (E29); de uitvoer is gesorteerd op `code`.
- `tests/test_cli_tides.py`:
  - met een gemonkeypatchte `rws.list_tide_stations` toont `stations` de kop, de tab-gescheiden regels met 5 decimalen en `N stations`;
  - `--search hoek` filtert hoofdletterongevoelig;
  - een `TideFetchError` geeft exitcode 1;
  - het commando werkt zonder `SUPABASE_*`-variabelen (de autouse-fixture in `conftest.py` maakt de omgeving al leeg).

### AC-5: tegen de lokale stack (verifier of Lars; `NEEDS_LARS` als Docker ontbreekt)
1. `supabase start` (of `supabase db reset`). Wijs `.env` naar de lokale stack (RUNBOOK sectie 6).
2. `psql "$(supabase status -o env | sed -n 's/^DB_URL=\"\(.*\)\"$/\1/p')" -c "insert into public.spots (id, name, rws_station) values ('zzt-tide', 'Test getij', 'hoekvanholland') on conflict (id) do update set rws_station = excluded.rws_station;"`. Dit kan ook via Studio of de SQL-editor.
3. `cd ingest && uv run shakka tides fetch --force` geeft exitcode 0 en `fetched 1 station(s)`.
4. `select count(*) from public.tide_extremes where station = 'hoekvanholland' and at > now() and at <= now() + interval '8 days';` geeft ≥ 25.
5. Opnieuw `uv run shakka tides fetch` (zonder `--force`) toont `skipped (fetched < 20h ago): hoekvanholland`, en het aantal rijen blijft gelijk.
6. Opruimen: `delete from public.spots where id = 'zzt-tide';`

### Overige tests
- `tests/test_rws_tides.py`:
  - `test_build_extremes_request_exact`: exacte dict-gelijkheid met de vorm uit Interfaces, `Begindatumtijd == "2026-10-13T12:00:00.000+00:00"` voor `NOW - 1d`; een naive `start`, of `start >= end`, geeft `ValueError`;
  - `test_build_catalogue_request_exact`.
- Fetch met `httpx.MockTransport`:
  - de request is een `POST` naar exact `OBSERVATIONS_URL`, de body (`json.loads(request.content)`) is gelijk aan `build_extremes_request(...)` en `content-type` is `application/json`;
  - 200 met de fixture geeft dezelfde lijst als `parse_extremes_response`;
  - 204, 500 (met en zonder JSON-`Foutmelding`), 302, een body die geen JSON is, `httpx.ConnectError("boom secret-ish")` en `httpx.ReadTimeout` geven elk `TideFetchError`. De melding bevat `"boom"` niet, en `__cause__ is None` (E13);
  - een ongeldige stationcode geeft `TideFetchError` en 0 requests (E23).
- Eigen client: monkeypatch `shakka.rws.tides.make_client` naar een fabriek die een MockTransport-client teruggeeft en de `timeout` registreert. Na de call is die client gesloten (`client.is_closed`) en is de timeout 30.0 (60.0 voor de catalogus). Een meegegeven client is na de call níet gesloten.
- `list_tide_stations`: een POST naar `CATALOGUE_URL` met de catalogusbody; de fixture geeft dezelfde lijst als `parse_stations`.
- `test_rws_hosts_only_in_rws_package`: alle `*.py` onder `ingest/src` die `rijkswaterstaat.nl` bevatten, liggen onder `ingest/src/shakka/rws/`.
- `tests/test_cli_tides.py` voor `fetch`:
  - zonder config: exit 1 en `configuration incomplete`;
  - met `SUPABASE_URL` en `SUPABASE_SECRET_KEY` gezet, `SupabaseRest.from_settings` gemonkeypatcht naar een geseede `FakeSupabase` en `rws.fetch_tide_extremes` naar een nep-functie die `http` als keyword accepteert: exit 0 met de samenvattingsregel;
  - met een falend station: exit 1, met `failed:` in de uitvoer;
  - de secret staat niet in de uitvoer.
- `tests/test_domain_purity.py` (bestaand) is groen met `domain/tide.py`.

## Externe afhankelijkheden
Geen nieuwe packages. Gebruikt worden `httpx`, `pydantic` en `click`, die er al staan.

Gecontroleerd op 14 oktober 2026:

| Onderwerp | Bevinding | Bron |
|---|---|---|
| Endpoints DDAPI20 | `POST https://ddapi20-waterwebservices.rijkswaterstaat.nl/ONLINEWAARNEMINGENSERVICES/OphalenWaarnemingen` en `POST …/METADATASERVICES/OphalenCatalogus`. Tijden in ISO 8601 met offset; RWS antwoordt met `+01:00`. Max. 160.000 waarnemingen per request. Licentie CC0. Geen uptimegarantie. | https://rijkswaterstaatdata.nl/waterdata/ |
| Extremen met type | "gebruik de groeperingscode … (GETETBRKD2 of GETETBRKDMSL2). Met deze groepering ontvangt u zowel de waterstand als het bijbehorende getijextreemtype (hoogwater of laagwater)." Voorbeeldbody met alleen `Groepering`. | https://rijkswaterstaatdata.nl/waterdata/ |
| OpenAPI DDAPI20 | Request: `Locatie.Code`, `AquoPlusWaarnemingMetadata.AquoMetadata`, `Periode.Begindatumtijd/Einddatumtijd`. Respons: `Succesvol`, `Foutmelding`, `WaarnemingenLijst[].{AquoMetadata, Locatie, MetingenLijst[].{Tijdstip, Meetwaarde.{Waarde_Numeriek, Waarde_Alfanumeriek}, WaarnemingMetadata.{Kwaliteitswaardecode, Statuswaarde, …}}}`. `AquoMetadata` heeft `ProcesType` (`meting`/`verwachting`/`astronomisch`), `Grootheid`, `Hoedanigheid`, `Eenheid`, `Groepering` en `Typering` (`{Code, Omschrijving}`). Catalogus: `AquoMetadataLijst`, `LocatieLijst` (`Code`, `Naam`, `Lat`, `Lon`, `Coordinatenstelsel`) en `AquoMetadataLocatieLijst`. | https://ddapi20-waterwebservices.rijkswaterstaat.nl/webservices-api-docs (Swagger: https://ddapi20-waterwebservices.rijkswaterstaat.nl/swagger-ui/index.html) |
| ddlpy (referentie, niet als dependency) | Laatste release 0.10.0 (23-12-2025), PyPI-naam `rws-ddlpy`, sinds 0.8.0 op DDAPI20. `ProcesType` staat als string in `AquoMetadata`. Koppelsleutels `Locatie_MessageID`, `AquoMetaData_MessageID` en `AquoMetadata_MessageID`. Kwaliteitscode `99` betekent ongeldig. `timeout=None` voor metingen en catalogus. Dependencies: numpy, pandas, pytz, tqdm, requests, platformdirs, click. | https://pypi.org/pypi/rws-ddlpy/json, https://raw.githubusercontent.com/Deltares/ddlpy/main/ddlpy/ddlpy.py, https://raw.githubusercontent.com/Deltares/ddlpy/main/ddlpy/endpoints.json, https://deltares.github.io/ddlpy/history.html |
| Extreemtypes | Een apart kanaal met `Typering.Code` `GETETTPE` (`Grootheid` `NVT`), met de tekst in `Waarde_Alfanumeriek`: `hoogwater`, `laagwater`, `laagwater 1`, `topagger`, `laagwater 2`. Hoek van Holland heeft aggers (codes 3/4/5 in de verwachte reeks). | https://deltares.github.io/hatyan/_modules/hatyan/ddlpy_helpers.html, https://raw.githubusercontent.com/Deltares/hatyan/main/tests/test_ddlpy_helpers.py, https://deltares.github.io/hatyan/whats-new.html (2.13.0: bijgewerkt naar de nieuwe waterwebservices) |
| Type-kanaal heeft `Hoedanigheid` `NVT` | Daarom geen `Hoedanigheid` in de request | https://github.com/Deltares-research/kenmerkendewaarden/issues/4 |
| Dubbel laagwater HvH, dubbel hoogwater Den Helder | Bekende bijzonderheden van de RWS-extremen | https://github.com/openwatersio/tide-database/issues/152 |

Niet zelf geverifieerd (alleen POST mogelijk, en de planner kan geen POST doen): dat de astronomische `GETETBRKD2`-respons voor `hoekvanholland` echt een `GETETTPE`-kanaal heeft met deze teksten. Stap 2 legt dat vast en heeft stopregels.

## Risico's
- **R1. De respons wijkt af van A2/A3** (geen typekanaal bij astronomisch, andere teksten, of de server eist `Grootheid`/`Hoedanigheid`). Stap 2 vangt dat af vóór er parsercode is. De builder stopt met `deviations.md`, en de planner herziet de parser. Mogelijke uitweg (niet bouwen zonder herziening): het type afleiden uit de buren (lokaal maximum of minimum).
- **R2. Afwijking van de WP-tekst "via ddlpy"** (A1). De reviewer of Lars kan ddlpy alsnog eisen. Dan blijft alles behalve de binnenkant van `fetch_tide_extremes` en `list_tide_stations` gelijk. De timeout zou dan via een thread-wrapper moeten, en de fixture wordt een DataFrame.
- **R3. Agger-semantiek** (twee `low` achter elkaar) verrast WP-05 of WP-08. Dit staat in "Gevolgen voor latere WP's".
- **R4. Den Helder of andere stations met een onbekende typetekst** falen bij elke fetch (elk uur 1 request, want de 20-uursregel greept niet). Dit is zichtbaar in `failed` en via WP-11 bij Lars. Fail closed is bewust: niets verzinnen.
- **R5. RWS-storing.** Er is geen SLA. Door de 8 dagen vooruit blijft de evaluatie dagenlang werken. Tijdens een storing doet elke uurlijkse run per station 1 request, met een timeout van 30 s. Bij 25 stations is dat in het slechtste geval 12,5 minuten. Dat zit krap onder de job-timeout van 15 minuten uit WP-11. In de praktijk gaat het om een handvol stations, want spots delen stations. WP-22 kan een totaalbudget per stap toevoegen.
- **R6. Catalogusgrootte en -duur** (enkele MB). Alleen gebruikt door `tides stations` (handmatig), met een timeout van 60 s.
- **R7. Mergeconflicten** met WP-02 en WP-03 (parallel) in `ingest/src/shakka/cli.py` (elk een nieuwe groep) en `ingest/src/shakka/jobs/__init__.py`. Die zijn triviaal: alles behouden. De orchestrator rebaset op `origin/develop` vóór de PR.
- **R8. RWS wijzigt stationcodes of het schema opnieuw.** De parsers falen dan expliciet (`TideFetchError`, catalogus zonder match). Er komen geen stille nullen in de database.

## Buiten scope
- Getij in de evaluatie (WP-05) en in berichten (WP-08).
- Het kiezen van `rws_station` per spot en het invullen van spotdata (Lars, WP-02).
- Gemeten waterstanden, verwachtingen (`ProcesType` `verwachting`), 10-minutenreeksen en `GETETBRKDMSL2` (MSL).
- `api_usage`-registratie voor `rws`, retries met backoff en een tijdsbudget per stap (WP-22).
- Opruimen van stations die geen enkele spot meer gebruikt (die verouderen vanzelf binnen ~9 dagen door de 48h-cleanup).
- Uurlijkse scheduling en logging in `ingest_runs` (WP-11).
- Bronvermelding in de UI (WP-13, WP-14).

## Stappenplan voor de builder
Na elke stap: `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .` groen. Eén commit per stap, met een Engelse commit message.

1. **Domein.** Schrijf `tests/test_domain_tide.py` (AC-2 en de modeltests), zie ze falen, en schrijf dan `src/shakka/domain/tide.py`. De puurheidstest moet groen zijn. Commit: `WP-04: add tide domain model and interpolation`.
2. **Request builders en capture.** Maak `src/shakka/rws/__init__.py` en `src/shakka/rws/tides.py` met de constanten, `TideFetchError`, `StationInfo`, `format_rws_time`, `build_extremes_request` en `build_catalogue_request`, met de tests `test_build_*` eerst. Schrijf `scripts/capture_rws_fixtures.py` en draai het (netwerk nodig). Controleer de uitvoer tegen de **stopregels**:
   - (a) beide requests geven HTTP 200 en `Succesvol` is niet `false`;
   - (b) er is minstens één kanaal met `WATHTE`/`NAP`/`cm` en één kanaal met `Typering` `GETETTPE`;
   - (c) alle typeteksten (na `strip().lower()`) staan in `EXTREME_TYPE_KIND`;
   - (d) elk tijdstip in het niveaukanaal heeft een type op exact hetzelfde tijdstip;
   - (e) `parse_stations` (stap 3) vindt later `hoekvanholland`. Voorlopig: de catalogus bevat in `LocatieLijst` een item met `Code == "hoekvanholland"`.

   Faalt (a) t/m (d): schrijf `docs/wp/WP-04/deviations.md` met de geprinte kanaaloverzichten en **stop**. Commit de fixtures en het script: `WP-04: capture RWS DDAPI20 fixtures`.
3. **Parsers.** Schrijf eerst de parsertests (AC-1, de synthetische tests en `test_parse_stations_*`). Stel `EXPECTED_EXTREMES` vast zoals beschreven in het testplan. Implementeer daarna `parse_extremes_response` en `parse_stations`. Commit: `WP-04: parse RWS tide extremes and stations`.
4. **Fetch.** Schrijf de MockTransport-tests en de hostbewakingstest, en implementeer daarna `_post_json`, `fetch_tide_extremes` en `list_tide_stations`. Commit: `WP-04: fetch tide extremes and station list over httpx`.
5. **Job.** Maak `src/shakka/jobs/__init__.py` als hij nog niet bestaat. Schrijf `tests/test_job_tides.py` (AC-3), en implementeer daarna `src/shakka/jobs/tides.py`. Commit: `WP-04: add tide ingest job`.
6. **CLI.** Schrijf `tests/test_cli_tides.py` en voeg daarna de groep `tides` toe aan `src/shakka/cli.py`. Draai handmatig `uv run shakka tides stations --search hoek` (AC-4) en noteer de uitvoer voor de verifier. Commit: `WP-04: add tides CLI`.
7. **Runbook.** Voeg sectie 9 toe aan `docs/RUNBOOK.md`. Commit: `docs(WP-04): runbook tides section`.
8. **Lokale stack (als Docker beschikbaar is).** Voer AC-5 uit volgens het testplan. Zonder Docker noteer je dat in `deviations.md` als niet-blokkerend, net als bij WP-01 D1. AC-5 gaat dan naar de verifier of Lars.
