# Blueprint WP-07: Alertregels en windows (puur)
Status: DRAFT
Revisie: 2

## Doel
Een pure module `shakka.domain.alerts` die:
1. de effectieve alertregel van een gebruiker voor een spot samenstelt uit gebruikersregel, profiel, spot en systeemdefaults (`resolve_rule`);
2. die regel valideert, zodat een regel nooit `side_offshore` of `offshore` kan bevatten;
3. de regel vertaalt naar `RiderLimits` voor de evaluatie (`rider_limits`);
4. uit een reeks `HourEvaluation`s (WP-05) de aaneengesloten `go`-windows vindt waarop een alert kan afgaan (`find_windows`).

Daarnaast komt er een vierde contractbestand, `data/contracts/alert_defaults.json`, via de bestaande `shakka contracts export`.

Er is geen I/O: regels laden (WP-10), deduplicatie en berichten (WP-08) en UI (WP-16) vallen erbuiten.

## Aannames
- **A1. Voorstel default `min_go_hours` = 2.**
  - 1 uur is te kort om voor te rijden: heen, opbouwen en afbouwen kosten samen al gauw 45 minuten. Bovendien geeft 1 uur veel losse meldingen voor uren aan de rand van een window, waar de modellen ±1 uur onzeker zijn (WP-08 tolereert ±1 uur juist daarom).
  - 3 uur mist de korte sessies die in Nederland veel voorkomen: een avondsessie na het werk in voor- en najaar (bijv. 17:00–19:00 tot zonsondergang) of een doorgaand front.
  - 2 uur is de kleinste reeks die een volwaardige sessie oplevert. De gebruiker kan per regel 1 t/m 24 kiezen (DB-CHECK).
- **A2. Voorstel default `days_ahead` = 3** (vandaag plus drie lokale dagen, dus vier kalenderdagen).
  - Met `forecast_days=7` loopt de data van UTC-vandaag 00:00Z t/m UTC-vandaag+6 23:00Z (WP-03 A10). `days_ahead = 7` heeft daardoor nooit data, en `days_ahead = 6` mist de hele laatste dag bij runs tussen lokaal 00:00 en 02:00 (dan is de lokale datum al een dag verder dan de UTC-datum). 3 blijft ver van die rand.
  - Windverwachtingen verder dan 3 à 4 dagen verschuiven sterk van run tot run. Elke verschuiving geeft in WP-08 een `new` gevolgd door `cancelled` of `worsened`. Meer dagen betekent dus meer ruis per gebruiker, en "alerts die standaard goed staan" (plan §1) vraagt om weinig ruis.
  - 3 dagen is genoeg om een weekend te plannen: op woensdag zie je zaterdag, op donderdag zondag.
  - KNMI Harmonie dekt ca. 2,5 dag; daarna zijn er nog drie modellen (ICON, ECMWF, GFS), zodat `high` betrouwbaarheid mogelijk blijft (WP-05, `CONFIDENCE_HIGH_MIN_MODELS = 3`).
  - De gebruiker kan per regel 0 t/m 7 kiezen (DB-CHECK). 7 is toegestaan omdat de database het toestaat, maar levert in de praktijk niets extra op (zie "Gevolgen voor latere WP's", WP-16).

  Lars bevestigt beide defaults (WORK_PACKAGES, "Nodig van Lars"); een andere waarde is één constante in `alerts.py`, het contractbestand opnieuw exporteren en de tests die de default noemen.
- **A3. Overige defaults.** `DEFAULT_WEEKDAYS` = alle zeven dagen; `DEFAULT_DIR_CLASSES` = `RIDABLE_DIR_CLASSES` (contract); geen tijdvenster (`earliest_local` en `latest_local` `None`), want daglicht zit al in de evaluatie (`dark`); `enabled` = `True` (gelijk aan de DB-default).
- **A4. Welke niveaus per veld een bron hebben.** De prioriteit is regel > profiel > spot > systeem, maar niet elk niveau heeft voor elk veld een waarde. Profiel heeft alleen `default_min_kn` en `default_max_kn` (WP-01), spot alleen `default_min_kn` (WP-02). Een niveau zonder bron wordt overgeslagen. Volledige tabel in Ontwerp. AC-1 wordt per veld en per niveau getoetst: voor een niveau zonder bron toont de test dat de waarde doorvalt naar het volgende niveau, ook als dat niveau wel andere velden gevuld heeft.
- **A5. Systeemwaarde van `max_kn` is afgeleid**: `max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN)`, met de effectieve `min_kn`. Dat is exact de regel van `default_limits` uit WP-05. Daardoor geldt `rider_limits(resolve_rule(spot, None, None)) == default_limits(spot)` (getest), en een hoge `min_kn` (rule tot 60, spot tot 40) geeft zonder expliciete `max_kn` nooit een ongeldige regel. De spot beïnvloedt `max_kn` alleen via deze afleiding.
- **A6. Conflict tussen niveaus is een fout.** Is `max_kn` expliciet gezet (regel of profiel) en is de effectieve `min_kn` (van welk niveau ook) daar niet onder, dan geeft `resolve_rule` een `ValueError`. De melding noemt beide waarden met hun bron (bijv. `min_kn 25.0 (rule) must be below max_kn 20.0 (profile)`). Stil bijstellen zou een instelling van de gebruiker of de spot negeren; zo'n regel kan toch nooit een `go`-uur opleveren. WP-10 vangt de fout per favoriet af (zie "Gevolgen voor latere WP's").
- **A7. `AlertRuleOverride` bevat de negen instelkolommen** van `alert_rules`: `enabled`, `min_kn`, `max_kn`, `dir_classes`, `weekdays`, `earliest_local`, `latest_local`, `min_go_hours`, `days_ahead`. Alle velden zijn optioneel (`None` = default). De sleutels (`user_id`, `spot_id`) en de metadata-kolom `updated_at` horen er niet in; `from_row` negeert die drie kolommen.
  - **Bewuste afwijking van WORK_PACKAGES.** Het contract zegt "velden gelijk aan de kolommen van `alert_rules` behalve de sleutels". `updated_at` is geen sleutel, maar valt hier toch buiten: het is door een trigger gezette metadata en geen instelling. Er is geen niveau om het naar door te laten vallen, en `AlertRule` heeft het niet. De orchestrator kan de contracttekst aanpassen naar "behalve de sleutels en `updated_at`".
  - **Verhouding tot de DB-CHECKs.** De validatie volgt de CHECK-constraints van WP-01. Elke override die hier geldig is, voldoet ook aan die CHECKs. Omgekeerd levert elke rij die de database accepteert een geldige override op, met deze bekende verschillen:
    - `latest_local = 24:00:00` (Postgres `time` loopt t/m `24:00:00`; Python `time` en pydantic niet) wordt `None`, "geen bovengrens". Dat betekent hetzelfde, want `t < 24:00` geldt voor elk lokaal uur (E36).
    - `earliest_local = 24:00:00` geeft een `ValidationError` met een eigen melding (E37). Zo'n regel kan nooit een uur laten meetellen, dus er gaat niets verloren. WP-10 slaat de favoriet over en meldt het.
    - Representatieverschillen zonder betekenis: dubbele waarden in `dir_classes` en `weekdays` worden ontdubbeld, tijdstrings worden `datetime.time`.

    Een rij die om een nog onbekende reden toch faalt, mag de alertjob niet stoppen: WP-10 zet `from_row` en `resolve_rule` per favoriet in één `try` (zie "Gevolgen voor latere WP's").
- **A8. Tijdvenster op het begin van het lokale uur.** Contract: "het lokale uur in `[earliest_local, latest_local)`". Een uur `[T, T+1h)` telt als `t = time(local.hour, local.minute)` met `local = T.astimezone(LOCAL_TZ)` voldoet aan `earliest_local <= t` (als gezet) en `t < latest_local` (als gezet). Bij hele uren betekent `latest_local = 21:00` dat het laatste uur 20:00–21:00 is. Bij een niet-heel tijdstip (bijv. `latest_local = 20:30`) telt het uur 20:00–21:00 nog mee; dat volgt letterlijk uit het contract en staat in de edge cases.
- **A9. "Vóór `now`" betekent: vanaf het volgende hele uur.** Het contract zegt `valid_at >= now` én "het uur waarin `now` valt telt niet". Die twee botsen alleen als `now` precies op een heel uur valt. Beide gelden met: een uur telt als `valid_at >= floor_hour(now) + 1h`. Bij `now = 14:17Z` is het eerste uur 15:00Z (gelijk aan `>= now`); bij `now = 14:00:00Z` ook 15:00Z (het uur waarin `now` valt telt niet).
- **A10. "Vandaag" is de lokale datum van `now`** (`now.astimezone(LOCAL_TZ).date()`). Een uur telt als `T.astimezone(LOCAL_TZ).date() <= vandaag + days_ahead`. Weekdag is `local.isoweekday()` (1 = maandag), net als in de DB-CHECK.
- **A11. `find_windows` vertrouwt het oordeel.** De wind- en vlaaggrenzen van de gebruiker zitten al in de evaluatie, mits de aanroeper (WP-10) evalueert met `rider_limits(rule)`. `find_windows` herberekent geen windgrenzen. Wel controleert het, als extra vangnet voor de harde regel, dat `dir_class` in `RIDABLE_DIR_CLASSES` zit (naast `verdict == go` en `dir_class in rule.dir_classes`), en het `Window`-model weigert elk uur dat niet `go` of niet rijdbaar is.
- **A12. Additieve uitbreidingen van het contract.** De signatures uit WORK_PACKAGES blijven exact zo. Erbij komen: `RuleSource`, `RULE_FIELDS`, `FIELD_SOURCES`, `FIELD_LABEL_NL`, de bereikconstanten (`ALERT_KN_RANGE`, `MIN_GO_HOURS_RANGE`, `DAYS_AHEAD_RANGE`, `ISO_WEEKDAYS`), `END_OF_DAY_TIME_STRINGS`, `AlertRuleOverride.from_row`, `ProfileDefaults.from_row`, en een overschreven `model_copy` die opnieuw valideert (zelfde patroon als `HourEvaluation` in WP-05).
- **A13. Geen nieuwe dependencies, geen migratie, geen wijziging aan WP-05-code.** WP-06 (kite-advies) is voor deze WP niet nodig; WORK_PACKAGES noemt alleen WP-05 als afhankelijkheid. De enige wijziging buiten `alerts.py`, `contracts.py` en de tests is één docstringregel in `cli.py` (zie Bestanden).

## Ontwerp

### Lagen
`shakka.domain.alerts` importeert alleen de standaardbibliotheek, `pydantic` en `shakka.domain.{defaults, direction, evaluation, spot}`. Er zijn geen cycli: geen enkele bestaande domeinmodule importeert `alerts`. `shakka.contracts` (I/O-module) importeert `alerts` om het nieuwe bestand te bouwen.

### Modellen en validatie
Alle modellen zijn pydantic, `frozen=True`, `extra="forbid"`. Een private basisklasse `_RevalidatingModel(BaseModel)` in `alerts.py` overschrijft `model_copy` op dezelfde manier als `HourEvaluation` (dump, update, `model_validate`). `AlertRuleOverride`, `ProfileDefaults`, `AlertRule` en `Window` erven daarvan. Zo kan geen enkele kopie de validatie omzeilen. `model_construct` blijft verboden in `ingest/src` (bestaande test `test_no_model_construct_in_src`).

**Strikte ints in verzamelingen.** In strict mode accepteert pydantic voor een `frozenset` alleen een `frozenset`, geen lijst (conversietabel). `strict=True` mag daarom nooit op het hele `weekdays`-veld staan, want lijsten uit de database moeten werken. De strengheid zit op de elementen: het elementtype is `Annotated[StrictInt, Field(ge=1, le=7)]` (alias `_IsoWeekday` in `alerts.py`). Zo wordt `[6, 7]` geaccepteerd en `[True]`, `[6.0]`, `[0]` en `[8]` geweigerd. Losse ints (`min_kn`, `max_kn`, `min_go_hours`, `days_ahead`) gebruiken `Field(strict=True, ge=..., le=...)`.

**`AlertRuleOverride`** (volgt de DB-CHECKs, elk veld optioneel, default `None`):

| Veld | Type | Validatie (anders `ValidationError`) |
|---|---|---|
| `enabled` | `bool \| None` | strikt bool |
| `min_kn`, `max_kn` | `int \| None` | strikt int (geen bool, geen float), 5 t/m 60; als beide gezet: `min_kn < max_kn` |
| `dir_classes` | `frozenset[DirClass] \| None` | niet leeg, elke waarde in `RIDABLE_DIR_CLASSES`. Lijsten uit de database (`["onshore"]`) worden geaccepteerd en ontdubbeld |
| `weekdays` | `frozenset[_IsoWeekday] \| None` | niet leeg, elk element strikt int in 1 t/m 7. Lijsten worden geaccepteerd en ontdubbeld |
| `earliest_local` | `time \| None` | naïef (geen `tzinfo`); strings als `"17:00"` en `"17:00:00"` (PostgREST) worden geparsed. `"24:00"` en `"24:00:00"` geven een `ValidationError` met de melding `earliest_local 24:00 matches no hour; use null or an earlier time` (E37) |
| `latest_local` | `time \| None` | naïef; strings zoals bij `earliest_local`. `"24:00"` en `"24:00:00"` worden `None` (E36). Als beide gezet (na die omzetting): `earliest < latest` |
| `min_go_hours` | `int \| None` | strikt int, 1 t/m 24 |
| `days_ahead` | `int \| None` | strikt int, 0 t/m 7 |

De 24:00-afhandeling zit in twee `field_validator(..., mode="before")`-methodes: voor `latest_local` geeft een string in `END_OF_DAY_TIME_STRINGS` `None` terug, voor `earliest_local` volgt een `ValueError` (die pydantic als `ValidationError` doorgeeft). Andere waarden gaan ongewijzigd door naar de gewone `time`-parsing. `"00:00"` en `"00:00:00"` worden niet omgezet: dat is `time(0, 0)` (E14). De omzetting geldt alleen voor `AlertRuleOverride`. `AlertRule` krijgt zijn tijden altijd als `time` of `None` uit `resolve_rule`.

`from_row(row)` neemt exact de negen kolommen uit `RULE_FIELDS`. Ontbreekt er één, dan volgt `ValueError` met de namen (zelfde stijl als `SpotProfile.from_row`). Andere sleutels (`user_id`, `spot_id`, `updated_at`) worden genegeerd. Een ongeldige waarde geeft een `ValidationError` (subklasse van `ValueError`).

**`ProfileDefaults`**: `default_min_kn: int | None = None`, `default_max_kn: int | None = None`; strikt int, 5 t/m 60, en `min < max` als beide gezet (volgt `profiles_min_kn_range`, `profiles_max_kn_range` en `profiles_min_lt_max`). `from_row(row)` neemt die twee kolommen (ontbrekend → `ValueError`) en negeert de rest (`weight_kg`, `quiver_m2`, `telegram_chat_id` enz.).

**`AlertRule`** (contractvelden, alle verplicht):

| Veld | Type | Validatie |
|---|---|---|
| `enabled` | `bool` | strikt bool |
| `min_kn` | `float` | eindig, `>= 0` |
| `max_kn` | `float` | eindig, `> min_kn` |
| `dir_classes` | `frozenset[DirClass]` | niet leeg; **elke waarde in `RIDABLE_DIR_CLASSES`** (harde regel) |
| `weekdays` | `frozenset[_IsoWeekday]` | niet leeg; elk element strikt int in 1 t/m 7 (geen bool, geen float) |
| `earliest_local`, `latest_local` | `time \| None` | naïef; `earliest < latest` als beide gezet |
| `min_go_hours` | `int` | strikt int (geen bool, geen float), 1 t/m 24 |
| `days_ahead` | `int` | strikt int (geen bool, geen float), 0 t/m 7 |

De controle op `dir_classes` staat dus op drie plekken: de DB-CHECK (WP-01), `AlertRuleOverride` en `AlertRule`. Ook een override die de validatie zou omzeilen (in tests via `model_construct`) wordt bij `resolve_rule` geweigerd, omdat `AlertRule` het laatste vangnet is.

### `resolve_rule`
Per veld de eerste waarde die niet `None` is, in deze volgorde:

| Veld | Regel | Profiel | Spot | Systeem |
|---|---|---|---|---|
| `enabled` | `override.enabled` | – | – | `True` |
| `min_kn` | `override.min_kn` | `profile.default_min_kn` | `spot.default_min_kn` | `DEFAULT_MIN_KN` (12,0) |
| `max_kn` | `override.max_kn` | `profile.default_max_kn` | – (alleen via de afleiding) | `max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN)` (A5) |
| `dir_classes` | `override.dir_classes` | – | – | `DEFAULT_DIR_CLASSES` |
| `weekdays` | `override.weekdays` | – | – | `DEFAULT_WEEKDAYS` |
| `earliest_local` | `override.earliest_local` | – | – | `None` |
| `latest_local` | `override.latest_local` | – | – | `None` |
| `min_go_hours` | `override.min_go_hours` | – | – | `DEFAULT_MIN_GO_HOURS` (2) |
| `days_ahead` | `override.days_ahead` | – | – | `DEFAULT_DAYS_AHEAD` (3) |

`profile` en `override` mogen `None` zijn; dan tellen al hun velden als `None`. `min_kn` en `max_kn` worden `float`. `spot.ridable_dirs`, `spot.status` en `spot.verified` spelen hier geen rol (die zitten in de evaluatie of in WP-10).

Algoritme:
1. Bepaal `min_kn` met zijn bron.
2. Bepaal `max_kn`: eerst regel, dan profiel; anders de afgeleide systeemwaarde.
3. Is `max_kn` expliciet (regel of profiel) en `min_kn >= max_kn`, dan `ValueError` met beide waarden en bronnen (A6). Bij een afgeleide `max_kn` kan dit niet voorkomen.
4. Bouw `AlertRule(...)` via de gewone constructor; die valideert alles nog eens.

`FIELD_SOURCES` legt de kolommen van de tabel hierboven vast als data (gebruikt door het contractbestand en door de test die de tabel controleert). De implementatie mag het niet "slim" generiek maken: elke regel van de tabel staat uitgeschreven in `resolve_rule`, zodat de review de code één-op-één met de tabel kan vergelijken.

### `rider_limits`
`RiderLimits(min_kn=rule.min_kn, max_kn=rule.max_kn)`. `AlertRule` garandeert al `min < max`, dus dit faalt nooit.

### `find_windows`
`find_windows(evaluations, rule, *, now)`:
0. `now` naïef → `ValueError`. Daarna `now = now.astimezone(UTC)`.
1. `rule.enabled is False` → `[]` (voordat de evaluaties gecontroleerd worden).
2. Controles op de invoer (`ValueError`): evaluaties van meer dan één `spot_id`, of dezelfde `valid_at` twee keer. Lege invoer → `[]`.
3. Sorteer op `valid_at` (de invoer mag in elke volgorde staan en wordt niet gewijzigd).
4. Bepaal `first_hour = floor_hour(now) + 1h` (A9) en `last_day = now.astimezone(LOCAL_TZ).date() + timedelta(days=rule.days_ahead)` (A10).
5. Een uur `ev` telt mee (`_qualifies`) als **alle** voorwaarden gelden, met `local = ev.valid_at.astimezone(LOCAL_TZ)` en `t = time(local.hour, local.minute)`:
   - `ev.verdict == Verdict.GO`;
   - `ev.dir_class is not None` en `ev.dir_class in RIDABLE_DIR_CLASSES` (vangnet, A11) en `ev.dir_class in rule.dir_classes`;
   - `local.isoweekday() in rule.weekdays`;
   - `rule.earliest_local is None or t >= rule.earliest_local`;
   - `rule.latest_local is None or t < rule.latest_local`;
   - `ev.valid_at >= first_hour`;
   - `local.date() <= last_day`.
6. Loop door de gesorteerde evaluaties en bouw reeksen van tellende uren waarbij elk volgend uur precies `vorige.valid_at + 1h` is (in UTC). Een uur dat niet telt, of een gat in de tijd, sluit de reeks af.
7. Elke reeks met `len >= rule.min_go_hours` wordt `Window(spot_id, start=eerste.valid_at, end=laatste.valid_at + 1h, hours=tuple(reeks))`.
8. Resultaat: lijst gesorteerd op `start`.

Alle vergelijkingen van "aaneengesloten" gebeuren in UTC, dus de nachten van de zomer- en wintertijdovergang geven geen extra gat en geen dubbel uur. Lokale tijd wordt alleen gebruikt voor weekdag, tijdvenster en datum.

**`Window`-invarianten** (`model_validator(mode="after")`, in deze volgorde):
1. `start` en `end` zijn aware en worden naar UTC genormaliseerd;
2. `hours` is niet leeg;
3. elk uur heeft `spot_id == self.spot_id`;
4. de uren volgen elkaar op met precies 1 uur;
5. `start == hours[0].valid_at` en `end == hours[-1].valid_at + 1h`;
6. elk uur heeft `verdict == go` en `dir_class in RIDABLE_DIR_CLASSES`.

Punt 6 maakt het onmogelijk een window te bouwen met een `marginal`-, `no_go`-, offshore- of side-offshore-uur, ook in tests en in WP-08. `min_go_hours` is geen invariant van `Window`, want het window kent de regel niet.

### Contractbestand `alert_defaults.json`
`shakka.contracts.build_contracts()` krijgt een vierde bestand. De vorm blijft `{"_generated": str, "items": [...]}` (WP-05, "Gevolgen voor latere WP's", WP-14). Elk item beschrijft één veld van `AlertRule`, in de volgorde van `RULE_FIELDS`, met exact deze sleutels: `field`, `label_nl`, `default`, `sources`, `min`, `max`, `allowed`, `min_span_kn`. Sleutels die voor een veld niet gelden zijn `null`. Exacte inhoud staat onder Interfaces.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/domain/alerts.py` | aanmaken | Constanten (incl. `END_OF_DAY_TIME_STRINGS`), `_IsoWeekday`, `RuleSource`, `RULE_FIELDS`, `FIELD_SOURCES`, `FIELD_LABEL_NL`, `_RevalidatingModel`, `AlertRuleOverride`, `ProfileDefaults`, `AlertRule`, `resolve_rule`, `rider_limits`, `Window`, `find_windows` (plus private helpers `_floor_hour`, `_qualifies`). |
| `ingest/src/shakka/contracts.py` | wijzigen | Module-docstring noemt ook de alert-defaults. `CONTRACT_FILES` krijgt `"alert_defaults.json"` als vierde (laatste) naam. `build_contracts()` bouwt dat bestand met de helper `_alert_defaults_items()`. Verder niets. |
| `ingest/src/shakka/cli.py` | wijzigen | **Alleen** de docstring van `contracts_export` (regel 149): `"""Write reason codes, direction classes, confidence labels and alert defaults as JSON."""`. Geen andere wijziging aan `cli.py`. |
| `data/contracts/alert_defaults.json` | aanmaken | Gegenereerd met `uv run shakka contracts export`. |
| `ingest/tests/alert_fixtures.py` | aanmaken | Helpers voor de alerttests (zie Testplan). |
| `ingest/tests/test_alert_rules.py` | aanmaken | AC-1, AC-2, `rider_limits`, `from_row`, 24:00-afhandeling, consistentie met `default_limits`, controle tegen de migratie. |
| `ingest/tests/test_windows.py` | aanmaken | AC-3, AC-4, `Window`-invarianten, veiligheid, zomer- en wintertijd, integratie met `evaluate_spot`. |
| `ingest/tests/test_contracts.py` | wijzigen | `test_cli_check_missing_and_export`: de vaste `3` wordt `len(CONTRACT_FILES)` (twee plekken). Nieuwe tests `test_alert_defaults_content` en `test_alert_defaults_ranges_match_migration` (AC-5). |

Geen migraties, geen nieuwe dependencies, geen wijziging aan `evaluation.py`, `defaults.py`, `direction.py`, `spot.py` of de bestaande contractbestanden (hun inhoud blijft byte-gelijk). `cli.py` alleen zoals hierboven. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

### `shakka.domain.alerts`
```python
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from typing import Annotated, Any, Final, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from shakka.domain.defaults import DEFAULT_MAX_KN, DEFAULT_MIN_KN, LOCAL_TZ, MIN_LIMIT_SPAN_KN
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass
from shakka.domain.evaluation import HourEvaluation, RiderLimits, Verdict
from shakka.domain.spot import SpotProfile

DEFAULT_MIN_GO_HOURS: Final = 2
DEFAULT_DAYS_AHEAD: Final = 3
ISO_WEEKDAYS: Final[frozenset[int]] = frozenset(range(1, 8))
DEFAULT_WEEKDAYS: Final[frozenset[int]] = ISO_WEEKDAYS
DEFAULT_DIR_CLASSES: Final[frozenset[DirClass]] = RIDABLE_DIR_CLASSES
# Mirrors of the CHECK constraints on alert_rules and profiles (WP-01), inclusive.
ALERT_KN_RANGE: Final = (5, 60)
MIN_GO_HOURS_RANGE: Final = (1, 24)
DAYS_AHEAD_RANGE: Final = (0, 7)
# Postgres `time` allows 24:00:00; Python `time` does not. latest_local 24:00 -> None.
END_OF_DAY_TIME_STRINGS: Final[frozenset[str]] = frozenset({"24:00", "24:00:00"})

_IsoWeekday = Annotated[StrictInt, Field(ge=1, le=7)]   # strict per element, list input OK

class RuleSource(StrEnum):            # declaration order = priority, highest first
    RULE = "rule"
    PROFILE = "profile"
    SPOT = "spot"
    SYSTEM = "system"

RULE_FIELDS: Final[tuple[str, ...]] = (
    "enabled", "min_kn", "max_kn", "dir_classes", "weekdays",
    "earliest_local", "latest_local", "min_go_hours", "days_ahead")
FIELD_SOURCES: Final[dict[str, tuple[RuleSource, ...]]] = {
    "enabled": (RuleSource.RULE, RuleSource.SYSTEM),
    "min_kn": (RuleSource.RULE, RuleSource.PROFILE, RuleSource.SPOT, RuleSource.SYSTEM),
    "max_kn": (RuleSource.RULE, RuleSource.PROFILE, RuleSource.SYSTEM),
    "dir_classes": (RuleSource.RULE, RuleSource.SYSTEM),
    "weekdays": (RuleSource.RULE, RuleSource.SYSTEM),
    "earliest_local": (RuleSource.RULE, RuleSource.SYSTEM),
    "latest_local": (RuleSource.RULE, RuleSource.SYSTEM),
    "min_go_hours": (RuleSource.RULE, RuleSource.SYSTEM),
    "days_ahead": (RuleSource.RULE, RuleSource.SYSTEM),
}
FIELD_LABEL_NL: Final[dict[str, str]] = {
    "enabled": "Alert aan",
    "min_kn": "Minimale wind (kn)",
    "max_kn": "Maximale wind (kn)",
    "dir_classes": "Windrichtingen",
    "weekdays": "Dagen",
    "earliest_local": "Vanaf (lokale tijd)",
    "latest_local": "Tot (lokale tijd)",
    "min_go_hours": "Minimaal aantal go-uren achter elkaar",
    "days_ahead": "Dagen vooruit (na vandaag)",
}

class AlertRuleOverride(_RevalidatingModel):
    enabled: bool | None = None          # strict bool
    min_kn: int | None = None            # Field(strict=True, ge=5, le=60)
    max_kn: int | None = None            # Field(strict=True, ge=5, le=60); min_kn < max_kn if both set
    dir_classes: frozenset[DirClass] | None = None     # non-empty, subset of RIDABLE_DIR_CLASSES
    weekdays: frozenset[_IsoWeekday] | None = None     # non-empty
    earliest_local: time | None = None   # naive; "24:00"/"24:00:00" -> ValidationError
    latest_local: time | None = None     # naive; "24:00"/"24:00:00" -> None; earliest < latest
    min_go_hours: int | None = None      # Field(strict=True, ge=1, le=24)
    days_ahead: int | None = None        # Field(strict=True, ge=0, le=7)

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """From an alert_rules row: exactly the RULE_FIELDS columns. Missing columns raise
        ValueError (names listed); user_id, spot_id, updated_at and other keys are ignored.
        Invalid values raise ValidationError (a ValueError)."""

class ProfileDefaults(_RevalidatingModel):
    default_min_kn: int | None = None    # Field(strict=True, ge=5, le=60)
    default_max_kn: int | None = None    # Field(strict=True, ge=5, le=60); min < max if both set

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """From a profiles row: default_min_kn and default_max_kn (missing -> ValueError);
        other columns are ignored."""

class AlertRule(_RevalidatingModel):
    enabled: bool                        # strict bool
    min_kn: float                        # finite, >= 0
    max_kn: float                        # finite, > min_kn
    dir_classes: frozenset[DirClass]     # non-empty subset of RIDABLE_DIR_CLASSES (hard rule)
    weekdays: frozenset[_IsoWeekday]     # non-empty
    earliest_local: time | None          # naive; earliest < latest if both set
    latest_local: time | None
    min_go_hours: int                    # Field(strict=True, ge=1, le=24)
    days_ahead: int                      # Field(strict=True, ge=0, le=7)

def resolve_rule(spot: SpotProfile, profile: ProfileDefaults | None,
                 override: AlertRuleOverride | None) -> AlertRule:
    """Effective rule: per field the first non-None of rule, profile, spot, system (see the
    table in the blueprint). max_kn without rule/profile value is
    max(DEFAULT_MAX_KN, min_kn + MIN_LIMIT_SPAN_KN). ValueError if an explicit max_kn is not
    above the effective min_kn (message names both values and sources), or if the result is
    invalid (e.g. an offshore class)."""

def rider_limits(rule: AlertRule) -> RiderLimits:
    """RiderLimits(min_kn=rule.min_kn, max_kn=rule.max_kn)."""

class Window(_RevalidatingModel):
    spot_id: str                          # min_length=1
    start: datetime                       # aware -> UTC; == hours[0].valid_at
    end: datetime                         # aware -> UTC; == hours[-1].valid_at + 1h (half-open)
    hours: tuple[HourEvaluation, ...]     # non-empty, consecutive, same spot, all go + ridable

def find_windows(evaluations: Sequence[HourEvaluation], rule: AlertRule, *,
                 now: datetime) -> list[Window]:
    """Maximal runs of consecutive qualifying hours with length >= rule.min_go_hours, sorted by
    start. [] if rule.enabled is False. ValueError on a naive now, mixed spot_ids or a
    duplicate valid_at. Input order is free and the input is not modified."""
```
De importlijst is wat de code hierboven gebruikt; ruff (`F401`) is leidend als de builder een import niet nodig blijkt te hebben. Volgorde van definities in het bestand: constanten, `_IsoWeekday`, `RuleSource` en de tabellen, `_RevalidatingModel`, daarna de modellen en functies (zodat `_RevalidatingModel` vóór de subklassen staat).

De lege-velden-, NaN- en typecontroles gebruiken pydantic-`Field` (`ge`, `le`, `strict=True`, `allow_inf_nan=False`, `min_length=1`) en `StrictInt` voor de elementen van `weekdays`, plus één `model_validator(mode="after")` per model voor de kruisregels. Elke fout is een `pydantic.ValidationError` (subklasse van `ValueError`) met een Engelse melding die de regel noemt; de `ValueError` uit stap 3 van `resolve_rule` is een gewone `ValueError`.

Geen enkele publieke functie in `alerts.py` heeft een parameter waarvan de naam `offshore`, `allow`, `force` of `unsafe` bevat (getest).

### `data/contracts/alert_defaults.json`
Exacte inhoud (zonder uitlijning; het echte bestand gebruikt `json.dumps(obj, ensure_ascii=False, indent=2) + "\n"`, zoals de andere drie):
```json
{
  "_generated": "Generated by `shakka contracts export` from shakka.domain. Do not edit.",
  "items": [
    {"field": "enabled", "label_nl": "Alert aan", "default": true, "sources": ["rule", "system"], "min": null, "max": null, "allowed": null, "min_span_kn": null},
    {"field": "min_kn", "label_nl": "Minimale wind (kn)", "default": 12.0, "sources": ["rule", "profile", "spot", "system"], "min": 5, "max": 60, "allowed": null, "min_span_kn": null},
    {"field": "max_kn", "label_nl": "Maximale wind (kn)", "default": 30.0, "sources": ["rule", "profile", "system"], "min": 5, "max": 60, "allowed": null, "min_span_kn": 5.0},
    {"field": "dir_classes", "label_nl": "Windrichtingen", "default": ["onshore", "side_onshore", "sideshore"], "sources": ["rule", "system"], "min": null, "max": null, "allowed": ["onshore", "side_onshore", "sideshore"], "min_span_kn": null},
    {"field": "weekdays", "label_nl": "Dagen", "default": [1, 2, 3, 4, 5, 6, 7], "sources": ["rule", "system"], "min": null, "max": null, "allowed": [1, 2, 3, 4, 5, 6, 7], "min_span_kn": null},
    {"field": "earliest_local", "label_nl": "Vanaf (lokale tijd)", "default": null, "sources": ["rule", "system"], "min": null, "max": null, "allowed": null, "min_span_kn": null},
    {"field": "latest_local", "label_nl": "Tot (lokale tijd)", "default": null, "sources": ["rule", "system"], "min": null, "max": null, "allowed": null, "min_span_kn": null},
    {"field": "min_go_hours", "label_nl": "Minimaal aantal go-uren achter elkaar", "default": 2, "sources": ["rule", "system"], "min": 1, "max": 24, "allowed": null, "min_span_kn": null},
    {"field": "days_ahead", "label_nl": "Dagen vooruit (na vandaag)", "default": 3, "sources": ["rule", "system"], "min": 0, "max": 7, "allowed": null, "min_span_kn": null}
  ]
}
```
Betekenis:
- `default` is de systeemwaarde. Bij `min_kn` geldt die alleen als regel, profiel en spot leeg zijn.
- `sources` is `FIELD_SOURCES` (hoogste prioriteit eerst).
- `min` en `max` zijn de **invoergrenzen** voor een waarde die de gebruiker in een regel of profiel opslaat (de DB-CHECKs, inclusief). Het zijn geen grenzen voor de effectieve waarde. Bij `max_kn` kan de afgeleide systeemwaarde boven `max` liggen: met `min_kn = 60` en geen expliciete `max_kn` is de effectieve `max_kn` 65 (E3). Die is geldig en de UI toont hem niet als fout.
- `min_span_kn` (alleen `max_kn`): de systeemwaarde van `max_kn` is `max(default, effectieve min_kn + min_span_kn)`.
- `allowed` van `dir_classes` volgt de declaratievolgorde van `DirClass` en bevat nooit `side_offshore` of `offshore`. Sets worden gesorteerd weggeschreven: `DirClass`-volgorde, getallen oplopend.
- `days_ahead` telt dagen ná vandaag (lokale datum): 0 = alleen vandaag, 3 = vandaag plus drie dagen.

Bouwregels voor `_alert_defaults_items()`: `default` van `min_kn` en `max_kn` is `DEFAULT_MIN_KN` en `DEFAULT_MAX_KN` (floats), `min_span_kn` is `MIN_LIMIT_SPAN_KN`, de bereiken komen uit `ALERT_KN_RANGE`, `MIN_GO_HOURS_RANGE` en `DAYS_AHEAD_RANGE`, labels uit `FIELD_LABEL_NL`. Niets wordt hard gecodeerd in `contracts.py`.

### Consistentie met afhankelijke WP's
- WP-05: `HourEvaluation`, `RiderLimits`, `Verdict`, `RIDABLE_DIR_CLASSES`, `DirClass`, `LOCAL_TZ`, `DEFAULT_MIN_KN`, `DEFAULT_MAX_KN` en `MIN_LIMIT_SPAN_KN` worden ongewijzigd gebruikt. De richtingsklasse komt altijd uit `HourEvaluation.dir_class`; `dir_deg` wordt nergens gebruikt (WP-05 A15). `gust_kn` wordt in deze WP niet gebruikt; een window mag uren met `gust_kn = None` bevatten.
- WP-01: de validatie van `AlertRuleOverride` en `ProfileDefaults` volgt de CHECKs `alert_rules_*` en `profiles_*_kn_range`/`profiles_min_lt_max`, met de verschillen uit A7 (24:00). Een test leest de bereiken en lijsten uit de migratie (zie Testplan).
- WP-02: alleen `SpotProfile.default_min_kn` wordt gebruikt.

### Gevolgen voor latere WP's
- **WP-08:**
  - `Window.hours` kan uren met `gust_kn = None` bevatten, en ook alleen zulke uren (WP-05, "Gevolgen"). Het advies `WindowSnapshot.gust_max_kn: float | None` blijft dus nodig.
  - Het begin van een lopend window schuift elk uur een uur op, omdat het huidige uur niet telt (A9). Het eind kan schuiven door `days_ahead` (afkapping op lokale middernacht van de laatste dag, die elke dag een dag opschuift) en door het tijdvenster.
  - Een begonnen window kan onder `min_go_hours` zakken en verdwijnen terwijl `window_end > now`. Dat is geen annulering: de deduplicatie moet alleen `cancelled` geven voor windows die verdwijnen vóór hun start (WP-08 AC-3).
- **WP-10:**
  - Evalueer per favoriet met `rider_limits(rule)` (A11); `find_windows` controleert de windgrenzen niet opnieuw.
  - `AlertRuleOverride.from_row` en `ProfileDefaults.from_row` zijn de mapping vanaf de rijen.
  - **Eén `try` per favoriet.** Het samenstellen van de regel per favoriet, dus `AlertRuleOverride.from_row`, `ProfileDefaults.from_row` en `resolve_rule`, staat samen in één `try ... except ValueError` (dat vangt ook `pydantic.ValidationError`). Bij een fout: sla die favoriet over, meld het (log met `user_id`/`spot_id` en de foutmelding, plus een teller in de samenvatting van de run) en ga door met de volgende favoriet. Wordt het profiel per gebruiker één keer geparsed, dan geldt een fout daarin voor elke favoriet van die gebruiker, met dezelfde afhandeling. Eén kapotte rij stopt dus nooit de hele alertjob. Bekende oorzaken: een conflict tussen niveaus (A6) en `earliest_local = 24:00:00` (E37); andere rijen die de database accepteert maar die hier falen, vallen onder dezelfde afhandeling.
  - De forecasthorizon moet minstens `days_ahead` lokale dagen dekken; met `now + 8 dagen` (WP-10 contract) is dat zo.
  - Bij `rule.enabled is False` kan de evaluatie worden overgeslagen; `find_windows` geeft dan toch `[]`.
- **WP-16:**
  - `effectiveRule()` spiegelt de tabel in Ontwerp, inclusief de afgeleide `max_kn`, de conflictfout (A6) en de 24:00-afhandeling uit A7 (`latest_local` `"24:00:00"` telt als geen bovengrens). `alert_defaults.json` levert defaults, bronnen, invoergrenzen en labels.
  - De UI schrijft nooit `24:00` of `24:00:00` naar `earliest_local` of `latest_local`; "geen bovengrens" is `null`.
  - Bied voor `earliest_local` en `latest_local` alleen hele uren aan. Een tijd als 20:30 laat het uur 20:00–21:00 nog meetellen (E15), en dat verrast gebruikers.
  - Bied `latest_local = 00:00` niet aan: dat telt geen enkel uur (E14).
  - Advies: bied `days_ahead` in de UI aan van 0 tot en met 6, niet 7 (WP-03 A10). De database en dit domein accepteren 7 wel.
  - Leg bij `days_ahead` in de uitlegtekst uit dat het om dagen ná vandaag gaat (3 = vandaag plus drie dagen, dus vier kalenderdagen). Het label in het contractbestand is daarom "Dagen vooruit (na vandaag)".
  - De invoergrenzen `min`/`max` van `max_kn` gelden niet voor de afgeleide waarde (zie "Betekenis" bij het contractbestand); toon een afgeleide 65 niet als fout.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `override` en `profile` zijn `None`, spot zonder `default_min_kn` | Systeemdefaults: `(True, 12.0, 30.0, RIDABLE, 1–7, None, None, 2, 3)`. |
| E2 | Spot `default_min_kn: 35`, verder leeg | `min_kn 35.0`, `max_kn 40.0` (afgeleid); gelijk aan `default_limits`. |
| E3 | Regel `min_kn: 60`, geen `max_kn` | `max_kn 65.0` (afgeleid), geldig, ook al is 65 boven de invoergrens 60. |
| E4 | Profiel `default_max_kn: 20`, spot `default_min_kn: 22`, regel leeg | `ValueError`; melding noemt `22.0 (spot)` en `20.0 (profile)`. |
| E5 | Regel `min_kn: 25`, profiel `default_max_kn: 20` | `ValueError`; melding noemt `rule` en `profile`. |
| E6 | Regel `min_kn: 15`, profiel `default_max_kn: 25` | `(15.0, 25.0)`. |
| E7 | Override met `dir_classes` `offshore` of `side_offshore`, ook gemengd met rijdbare klassen | `ValidationError` bij het maken van de override. Ook via `model_construct` (alleen in tests) faalt `resolve_rule`, door `AlertRule`. |
| E8 | `dir_classes: []` of `weekdays: []` | `ValidationError` (DB eist `cardinality >= 1`). |
| E9 | `dir_classes: ["onshore", "onshore"]` of `weekdays: [6, 6, 7]` | Geaccepteerd, ontdubbeld tot `{onshore}` en `{6, 7}`. |
| E10 | Weekdag 0 of 8, of `True` of `6.0` als weekdag | `ValidationError` (strikt int per element, 1–7), bij `AlertRuleOverride` en `AlertRule`. |
| E11 | `min_kn`, `max_kn`, `min_go_hours` of `days_ahead` als bool of float in de override; `min_go_hours` of `days_ahead` als bool of float in `AlertRule` | `ValidationError` (strikt int, zoals smallint). |
| E12 | `earliest_local: "17:00:00"` (PostgREST) of `"17:00"` | Wordt `time(17, 0)`. Met offset (`"17:00:00+02:00"`) → `ValidationError`. Voor `"24:00"`/`"24:00:00"` zie E36 en E37. |
| E13 | `earliest_local >= latest_local` | `ValidationError`. |
| E14 | Alleen `latest_local = 00:00` | Geldig (DB staat het toe), maar geen enkel uur telt (`t < 00:00` is nooit waar). `"00:00:00"` wordt `time(0, 0)`, niet `None`. |
| E15 | `latest_local = 20:30` | Het uur 20:00–21:00 telt nog mee (A8). |
| E16 | `days_ahead = 0` | Alleen lokale uren van vandaag. |
| E17 | `days_ahead = 7` | Geldig; in de praktijk geen data op de laatste dag (WP-03 A10). |
| E18 | `now` lokaal net na middernacht (bijv. 22:30Z in de zomer = 00:30 lokaal) | "Vandaag" is de nieuwe lokale datum. |
| E19 | `now` precies op een heel uur (14:00:00Z) | Het uur 14:00Z telt niet; eerste uur is 15:00Z (A9). |
| E20 | `now` naïef | `ValueError`. `now` in een andere tijdzone (aware) geeft hetzelfde resultaat als in UTC. |
| E21 | `rule.enabled is False` | `[]`, ook bij ongeldige evaluatie-invoer (de controle komt daarna). |
| E22 | Evaluaties van twee spots | `ValueError`. |
| E23 | Twee evaluaties met dezelfde `valid_at` | `ValueError`. |
| E24 | Evaluaties ongesorteerd | Zelfde resultaat als gesorteerd; invoer niet gewijzigd. |
| E25 | Lege invoer | `[]`. |
| E26 | Ontbrekend uur in de reeks (gat) | Splitst het window. |
| E27 | `go`-uur met `dir_class` buiten `rule.dir_classes` | Telt niet en splitst. |
| E28 | Offshore- of side-offshore-uur | Is altijd `no_go` (WP-05) en telt dus nooit. Het vangnet `dir_class in RIDABLE_DIR_CLASSES` en `Window`-invariant 6 sluiten het ook los daarvan uit. |
| E29 | `dir_class = None` | Uit `evaluate_hour` altijd `no_go` (`direction_unknown`). Een handmatig gemaakte `HourEvaluation` met `go` en `dir_class = None` is volgens de WP-05-invarianten wel geldig; `find_windows` telt zo'n uur niet (vangnet `dir_class is not None`) en `Window` weigert het (invariant 6). |
| E30 | Reeks precies `min_go_hours` lang | Wel een window (`>=`). |
| E31 | Reeks over de wintertijdovergang (2026-10-25 00:00Z, 01:00Z, 02:00Z = lokaal 02:00, 02:00, 03:00) | Eén window van 3 uur; geen gat, geen dubbeltelling (UTC-stappen). |
| E32 | Reeks over lokale middernacht met een weekdagfilter | Gesplitst op de lokale datum, niet de UTC-datum. |
| E33 | Window met een `marginal`-uur, een gat, een andere spot of een verkeerde `start`/`end` handmatig gemaakt | `ValidationError`. Ook via `model_copy(update=...)`. |
| E34 | `AlertRule.model_copy(update={"dir_classes": frozenset({DirClass.OFFSHORE})})` | `ValidationError` (opnieuw gevalideerd). |
| E35 | `from_row` met ontbrekende kolom | `ValueError` met de kolomnaam. Extra kolommen (`user_id`, `spot_id`, `updated_at`, `weight_kg`) worden genegeerd. |
| E36 | `latest_local: "24:00:00"` of `"24:00"` (Postgres staat `time` t/m 24:00:00 toe), met of zonder `earliest_local` | Wordt `None` ("geen bovengrens"); `from_row` slaagt. Met `earliest_local = "17:00:00"` tellen de uren 17:00 t/m 23:00 lokaal. |
| E37 | `earliest_local: "24:00:00"` of `"24:00"` | `ValidationError` met `earliest_local 24:00 matches no hour` in de melding. WP-10 slaat de favoriet over en meldt het. |
| E38 | Reeks over de zomertijdovergang (2027-03-28 00:00Z, 01:00Z, 02:00Z = lokaal 01:00 CET, 03:00 CEST, 04:00 CEST) | Eén window van 3 uur; het lokale "gat" om 02:00 geeft geen split (UTC-stappen). |

## Testplan
Tests eerst. Geen netwerk, geen klok: `now` is altijd een expliciete aware datetime. Ruff `DTZ` staat aan, dus elke `datetime(...)` in tests heeft `tzinfo=UTC`.

### Fixtures (`ingest/tests/alert_fixtures.py`)
```python
SPOT_ID = "test-strand"
H = timedelta(hours=1)

def utc(y, m, d, h) -> datetime: ...          # datetime(y, m, d, h, tzinfo=UTC)

def hour(at: datetime, verdict: str = "go", dir_class: DirClass | None = DirClass.SIDESHORE,
         spot_id: str = SPOT_ID) -> HourEvaluation:
    """Valid HourEvaluation via the normal constructor. Reasons follow from the arguments:
    go -> (); marginal -> (wind_borderline,); no_go -> (offshore,) for offshore,
    (side_offshore,) for side_offshore, (direction_unknown,) for None, else (wind_too_light,).
    wind_kn=20.0, gust_kn=None, dir_deg=None if dir_class is None else 270,
    confidence=medium, tide_level_cm=None."""

def go_run(start: datetime, n: int, **kw) -> list[HourEvaluation]:
    """n consecutive go hours from start."""

def rule(**overrides) -> AlertRule:
    """resolve_rule(make_spot(), None, AlertRuleOverride(**overrides))."""

def migration_sql() -> str:
    """All files in REPO_ROOT / "supabase" / "migrations" / "*.sql", sorted by name, joined
    with newlines. REPO_ROOT comes from shakka.config."""

def migration_range(constraint: str) -> tuple[int, int]:
    """The two numbers of the first `between (\\d+) and (\\d+)` after the constraint name."""

def migration_text_array(constraint: str) -> set[str]:
    """The quoted strings ('([a-z_]+)') inside the first `array[...]` after the constraint
    name. `array_position(` is not matched because the regex requires `array\\[`."""

def migration_int_array(constraint: str) -> set[int]:
    """The integers (\\d+) inside the first `array[...]` after the constraint name. Only the
    array content is read, so `cardinality(weekdays) >= 1` in the same CHECK is ignored."""
```
De drie `migration_*`-helpers zoeken vanaf `sql.index(constraint)` in een fragment van 1500 tekens, net als `_sql_list` in `test_contracts.py`; de array-regex is `array\[(.*?)\]` met `re.S`. `make_spot` komt uit `evaluation_fixtures` (bestaand). Een `go`-uur met `gust_kn=None` en `medium` is geldig volgens WP-05; zo testen de windows ook meteen het geval "vlaag onbekend".

Kalender (gecontroleerd): 2026-07-15 is woensdag, 2026-07-17 vrijdag, 2026-07-18 zaterdag, 2026-07-19 zondag; 2026-10-25 is de wintertijdovergang (01:00Z); 2026-11-04 is woensdag (CET, UTC+1); 2027-03-28 is zondag en de zomertijdovergang (01:00Z: 02:00 CET wordt 03:00 CEST). In juli geldt CEST (UTC+2).

### AC-1: prioriteit (`tests/test_alert_rules.py`)
`test_priority` is geparametriseerd over 9 velden × 4 niveaus = 36 gevallen. Gebruikte waarden: spot `default_min_kn=16` en `ridable_dirs=[{from: 200, to: 340}]`; profiel `ProfileDefaults(default_min_kn=14, default_max_kn=26)`; override met `enabled=False, min_kn=18, max_kn=24, dir_classes={sideshore}, weekdays={6, 7}, earliest_local=17:00, latest_local=21:00, min_go_hours=3, days_ahead=5`.

- Niveau **regel**: volledige override, volledig profiel en volledige spot. Verwacht: de override-waarde van het veld.
- Niveau **profiel**: override zonder dit veld, volledig profiel en spot. Verwacht: `14.0` voor `min_kn`, `26.0` voor `max_kn`. Voor de andere velden (geen profielbron): de systeemdefault.
- Niveau **spot**: geen override, `ProfileDefaults()` (leeg), spot met `default_min_kn=16`. Verwacht: `min_kn 16.0`. Voor `max_kn` (geen spotbron): de afgeleide `30.0`, en een extra geval met `default_min_kn=28` geeft `33.0`. Voor de overige velden: de systeemdefault.
- Niveau **systeem**: spot zonder `default_min_kn`, profiel en override `None`. Verwacht: `True, 12.0, 30.0, RIDABLE, {1..7}, None, None, 2, 3`.

Verder:
- `test_field_sources_table`: `FIELD_SOURCES` is exact de tabel uit Ontwerp (expliciete dict in de test), `RULE_FIELDS` is gelijk aan de veldnamen van `AlertRuleOverride` en `AlertRule`, in dezelfde volgorde.
- `test_default_rule_matches_default_limits`: voor `default_min_kn` ∈ {None, 5, 14, 26, 35, 40} geldt `rider_limits(resolve_rule(spot, None, None)) == default_limits(spot)`.
- `test_rider_limits`: `rider_limits(rule(min_kn=15, max_kn=25)) == RiderLimits(min_kn=15, max_kn=25)`.
- `test_defaults_values`: `DEFAULT_MIN_GO_HOURS == 2`, `DEFAULT_DAYS_AHEAD == 3`, `DEFAULT_WEEKDAYS == frozenset(range(1, 8))`, `DEFAULT_DIR_CLASSES == RIDABLE_DIR_CLASSES`.

### AC-2: validatie (`tests/test_alert_rules.py`)
- `test_override_rejects_offshore`, geparametriseerd over `["offshore"]`, `["side_offshore"]`, `["onshore", "offshore"]` en `[DirClass.SIDE_OFFSHORE]`: `AlertRuleOverride(dir_classes=...)` geeft `ValidationError`.
- `test_rule_rejects_offshore`: `AlertRule(...)` met een geldige basis en `dir_classes={offshore}` of `{sideshore, side_offshore}` geeft `ValidationError`.
- `test_resolve_rejects_offshore_even_if_override_bypassed`: `AlertRuleOverride.model_construct(dir_classes=frozenset({DirClass.OFFSHORE}))` in `resolve_rule` geeft `ValueError`. Zet direct boven de `model_construct`-regel het commentaar `# Deliberate validation bypass: proves AlertRule is the last safety net (allowed in tests only).` De ban op `model_construct` (`test_no_model_construct_in_src`) geldt alleen voor `ingest/src`; het verbod uit WP-05 geldt alleen voor fixtures van `HourEvaluation`.
- `test_model_copy_revalidates`: `rule().model_copy(update={"dir_classes": frozenset({DirClass.OFFSHORE})})`, `update={"min_kn": 40.0}` (boven `max_kn` 30) en `update={"unknown": 1}` geven `ValidationError`; `update={"min_go_hours": 4}` geeft een geldige kopie. Hetzelfde voor `AlertRuleOverride` met `dir_classes`.
- `test_min_ge_max_rejected`: `AlertRule` met `min_kn == max_kn` en met `min_kn > max_kn`; `AlertRuleOverride(min_kn=20, max_kn=20)`; `ProfileDefaults(default_min_kn=20, default_max_kn=15)`; en de conflicten E4 en E5 via `resolve_rule`. Alles `ValueError`; bij E4 en E5 bevat de melding beide bronnamen.
- `test_weekday_out_of_range`, geparametriseerd over `[0]`, `[8]`, `[1, 8]`, `[]`, `[True]` en `[6.0]`: `ValidationError` bij `AlertRuleOverride` én bij `AlertRule`. Plus een positief geval: `[6, 6, 7]` als lijst wordt bij beide geaccepteerd en is `frozenset({6, 7})` (E9; bewijst dat de strengheid per element zit en lijsten werken).
- `test_strict_ints_in_rule`: `AlertRule` met `min_go_hours=True`, `min_go_hours=2.0`, `days_ahead=True` of `days_ahead=3.0` (verder een geldige basis) geeft `ValidationError`.
- `test_other_ranges`: `ValidationError` bij `min_kn` 4 en 61, `min_go_hours` 0 en 25, `days_ahead` -1 en 8, `dir_classes=[]`, `earliest_local >= latest_local`, een tijd met `tzinfo`, `min_kn`, `min_go_hours` of `days_ahead` als `True` of als float (`12.5`, `2.0`) in de override, en NaN of negatieve `min_kn` in `AlertRule`. De grenzen 5, 60, 1, 24, 0 en 7 zijn geldig.
- `test_from_row`: een rij zoals PostgREST die geeft (`{"user_id": "…", "spot_id": "test-strand", "enabled": True, "min_kn": 14, "max_kn": None, "dir_classes": ["onshore", "sideshore"], "weekdays": [6, 7], "earliest_local": "17:00:00", "latest_local": None, "min_go_hours": None, "days_ahead": 2, "updated_at": "2026-10-15T10:00:00+00:00"}`) geeft de verwachte override. Een rij zonder `days_ahead` geeft `ValueError` met `days_ahead` in de melding. `ProfileDefaults.from_row` met een volledige `profiles`-rij geeft alleen de twee velden; zonder `default_max_kn` volgt `ValueError`.
- `test_end_of_day_time` (B-1, E36, E37, E14):
  - De rij uit `test_from_row` met `"latest_local": "24:00:00"` geeft `latest_local is None` en `earliest_local == time(17, 0)`; `resolve_rule(make_spot(), None, override).latest_local is None`.
  - `AlertRuleOverride(latest_local="24:00")` en `AlertRuleOverride(latest_local="24:00:00")` geven `latest_local is None`.
  - Dezelfde rij met `"earliest_local": "24:00:00"` en `"latest_local": None` geeft bij `from_row` een `ValueError` (`ValidationError`) met `earliest_local` in de melding; ook `AlertRuleOverride(earliest_local="24:00")`.
  - `AlertRuleOverride(latest_local="00:00:00").latest_local == time(0, 0)` (niet `None`).
- `test_ranges_match_migration`: met de helpers uit `alert_fixtures.py`:
  - `migration_range` voor `alert_rules_min_kn_range`, `alert_rules_max_kn_range`, `profiles_min_kn_range` en `profiles_max_kn_range` is gelijk aan `ALERT_KN_RANGE`; voor `alert_rules_min_go_hours_range` aan `MIN_GO_HOURS_RANGE`; voor `alert_rules_days_ahead_range` aan `DAYS_AHEAD_RANGE`.
  - `migration_text_array("alert_rules_dir_classes_ridable") == {c.value for c in RIDABLE_DIR_CLASSES}`.
  - `migration_int_array("alert_rules_weekdays_iso") == ISO_WEEKDAYS` (alleen de getallen uit `array[1, 2, 3, 4, 5, 6, 7]`, niet de `1` uit `cardinality(weekdays) >= 1`).
- `test_no_bypass_parameters`: `inspect.signature` geeft exact `resolve_rule(spot, profile, override)`, `rider_limits(rule)` en `find_windows(evaluations, rule, now)` (met `now` keyword-only). Geen publieke functie in `shakka.domain.alerts` heeft een parameter met `offshore`, `allow`, `force` of `unsafe` in de naam.

### AC-3: windows (`tests/test_windows.py`)
Tenzij anders vermeld: `now = utc(2026, 7, 15, 6)` (woensdag 08:00 lokaal), `rule(min_go_hours=1)` en `days_ahead` default 3.

| Test | Invoer | Verwacht |
|---|---|---|
| `test_three_go_hours_min_two` | `go_run(utc(2026,7,15,10), 3)`, `rule(min_go_hours=2)` | 1 window, `start` 10:00Z, `end` 13:00Z (= laatste uur + 1 uur), 3 uren |
| `test_single_go_hour_no_window` | 1 go-uur om 10:00Z, `rule()` (default 2) | `[]` |
| `test_go_marginal_go_min_one` | 10:00 go, 11:00 marginal, 12:00 go | 2 windows: [10, 11) en [12, 13) |
| `test_weekend_filter_local_date` | `weekdays={6, 7}`; go 2026-07-17 20:00Z, 21:00Z, 22:00Z, 23:00Z (vr 22:00 en 23:00, za 00:00 en 01:00 lokaal) plus 2026-07-19 21:00Z en 22:00Z (zo 23:00, ma 00:00 lokaal); `now = utc(2026,7,17,6)` | 2 windows: [2026-07-17 22:00Z, 2026-07-18 00:00Z) en [2026-07-19 21:00Z, 22:00Z) |
| `test_earliest_17_summer` | `earliest_local=17:00`; go 14:00Z, 15:00Z, 16:00Z op 2026-07-15 (16, 17, 18 lokaal) | 1 window [15:00Z, 17:00Z) |
| `test_earliest_17_winter` | idem op 2026-11-04 met go 15:00Z, 16:00Z, 17:00Z (16, 17, 18 lokaal); `now = utc(2026,11,4,6)` | 1 window [16:00Z, 18:00Z) |
| `test_latest_local` | `latest_local=20:00`; go 17:00Z, 18:00Z op 2026-07-15 (19, 20 lokaal) | 1 window [17:00Z, 18:00Z) |
| `test_latest_end_of_day_from_row` (E36) | override via `AlertRuleOverride.from_row` met `earliest_local "17:00:00"`, `latest_local "24:00:00"`, `min_go_hours` 1, overige instelkolommen `None`; `resolve_rule(make_spot(), None, override)`; go 2026-07-15 19:00Z, 20:00Z, 21:00Z (21, 22, 23 lokaal) | 1 window [19:00Z, 22:00Z): de late uren tellen mee |
| `test_days_ahead_one` | `days_ahead=1`, `now = utc(2026,7,15,8)`; go 2026-07-16 20:00Z t/m 23:00Z (16-07 22:00, 23:00, 17-07 00:00, 01:00 lokaal) | 1 window [2026-07-16 20:00Z, 22:00Z) |
| `test_days_ahead_zero_and_local_today` | `days_ahead=0`, `now = utc(2026,7,15,22) + 30 min` (16-07 00:30 lokaal); go 2026-07-16 08:00Z en 2026-07-16 22:00Z (17-07 00:00 lokaal) | 1 window [08:00Z, 09:00Z) op 16-07; "vandaag" is de lokale datum |
| `test_hours_before_now_excluded` | `now = utc(2026,7,15,10) + 17 min`; go 09:00Z t/m 12:00Z | 1 window [11:00Z, 13:00Z) |
| `test_now_on_whole_hour` | `now = utc(2026,7,15,10)` exact; go 10:00Z t/m 12:00Z | 1 window [11:00Z, 13:00Z) (A9) |
| `test_missing_hour_splits` | go 10, 11, 13, 14 (12 ontbreekt), `rule(min_go_hours=2)` | 2 windows: [10, 12) en [13, 15) |
| `test_dir_class_outside_rule_splits` | `dir_classes={sideshore}`; go 10 sideshore, 11 sideshore, 12 onshore, 13 sideshore | 2 windows: [10, 12) en [13, 14) |

Extra in `test_windows.py`:
- `test_exact_min_length`: een reeks van precies `min_go_hours=3` geeft 1 window; 2 uur geeft `[]`.
- `test_dst_fall_back_continuous` (E31): go 2026-10-25 00:00Z, 01:00Z, 02:00Z (`now = utc(2026,10,24,20)`, `rule(min_go_hours=3)`) geeft 1 window [00:00Z, 03:00Z) met 3 uren.
- `test_dst_spring_forward_continuous` (E38): go 2027-03-28 00:00Z, 01:00Z, 02:00Z (lokaal 01:00 CET, 03:00 CEST, 04:00 CEST), `now = utc(2027,3,27,20)` (za 21:00 lokaal), `rule(min_go_hours=3)`: 1 window [2027-03-28 00:00Z, 03:00Z) met 3 uren. Controleer in de test ook de lokale uren (`[h.valid_at.astimezone(LOCAL_TZ).hour for h in w.hours] == [1, 3, 4]`), zodat vaststaat dat de reeks echt over het lokale gat loopt.
- `test_unsorted_input_same_result`: omgekeerde invoer geeft hetzelfde resultaat; de invoerlijst is na afloop ongewijzigd.
- `test_invalid_input`: naïeve `now`, twee `spot_id`'s of een dubbele `valid_at` geven `ValueError`; lege invoer geeft `[]`.
- `test_now_other_timezone`: `now` in `LOCAL_TZ` geeft hetzelfde als de UTC-versie.
- `test_safety_grid`: geparametriseerd over elke niet-lege deelverzameling van `RIDABLE_DIR_CLASSES` (7 gevallen). Vastgelegd:
  - `now = utc(2026, 7, 15, 6)` en `rule(min_go_hours=1, dir_classes=subset)` (verder defaults, dus `days_ahead` 3, geen tijdvenster, alle weekdagen);
  - 24 uur vanaf `utc(2026, 7, 15, 8)` (t/m 2026-07-16 07:00Z, allemaal na `now` en binnen `days_ahead`), gevuld met deze cyclus van 8, drie keer herhaald: go `onshore`, go `side_onshore`, go `sideshore`, go `None`, marginal `sideshore`, no_go `offshore`, no_go `side_offshore`, no_go `None`;
  - verwacht: elk uur in elk window heeft `verdict == go` en `dir_class in subset`; geen uur heeft `side_offshore`, `offshore` of `None`; en er is **minstens één window** (elke deelverzameling heeft een go-uur in de cyclus), zodat de test niet vacuüm kan slagen. Controleer ook dat elk go-uur met een klasse uit `subset` in precies één window zit.
- `test_go_without_dir_class_not_counted` (E29): drie go-uren 10:00Z t/m 12:00Z waarvan 11:00Z `dir_class=None`, `rule(min_go_hours=1)`: 2 windows, [10, 11) en [12, 13).
- `test_integration_evaluate_spot`: `make_spot()` met `model_hours` van 2026-07-15 08:00Z t/m 13:00Z (wind 20, richting 270), `evaluate_spot(..., rider_limits(rule()))`, `now = utc(2026,7,15,6)`: 1 window [08:00Z, 14:00Z). Met richting 90 (offshore) of 135 (side-offshore) en elke rijdbare deelverzameling als `dir_classes`: `[]`. Met `rule(min_kn=22)` (wind 20 onder het minimum): `[]`.
- `test_window_invariants`: `Window` handmatig met een `marginal`-uur, een go-uur met `dir_class=None`, een gat, een uur van een andere spot, een verkeerde `start` of `end`, of een naïeve `start`: `ValidationError`. `model_copy(update={"end": ...})` met een verkeerde waarde: `ValidationError`.

### AC-4: uitgeschakeld (`tests/test_windows.py`)
- `test_disabled_returns_empty`: `rule(enabled=False)` met `go_run(utc(2026,7,15,10), 5)` geeft `[]`.
- `test_disabled_skips_input_checks`: `rule(enabled=False)` met evaluaties van twee spots geeft `[]` (E21). Met een naïeve `now` volgt wel `ValueError`.

### AC-5: contractbestand (`tests/test_contracts.py`)
- De bestaande `test_repo_files_up_to_date` en `test_export_and_check_tmp` dekken het vierde bestand automatisch via `CONTRACT_FILES`.
- `test_cli_check_missing_and_export`: `3` wordt `len(CONTRACT_FILES)` (bij `wrote` en bij `(unchanged)`).
- `test_alert_defaults_content`: het bestand van schijf heeft `_generated` en `items`. De `field`-volgorde is `RULE_FIELDS`. Elk item heeft exact de acht sleutels. `default` is gelijk aan de constanten (`True`, `DEFAULT_MIN_KN`, `DEFAULT_MAX_KN`, de gesorteerde `DEFAULT_DIR_CLASSES` en `DEFAULT_WEEKDAYS`, `None`, `None`, `DEFAULT_MIN_GO_HOURS`, `DEFAULT_DAYS_AHEAD`). `sources` is gelijk aan `FIELD_SOURCES`, `label_nl` is gelijk aan `FIELD_LABEL_NL` en niet leeg, en `allowed` van `dir_classes` is `["onshore", "side_onshore", "sideshore"]`. `side_offshore` en `offshore` komen nergens in het bestand voor (tekstzoektocht).
- `test_alert_defaults_ranges_match_migration`: `min`/`max` van `min_kn`, `max_kn`, `min_go_hours` en `days_ahead` in het bestand zijn gelijk aan `migration_range(...)` van de bijbehorende `alert_rules_*`-constraint (helper uit `alert_fixtures.py`).
- Handmatig, in het stappenplan: `uv run shakka contracts export --check` geeft exit 0.

### AC-6: puurheid
`tests/test_domain_purity.py` vindt `alerts.py` automatisch en is groen. `alerts.py` bevat geen `.now(`, `.today(` of `model_construct`.

## Externe afhankelijkheden
- Geen nieuwe packages. Gebruikt worden `pydantic` (al aanwezig, 2.x in `uv.lock`) en de standaardbibliotheek (`datetime`, `zoneinfo` via `LOCAL_TZ`, `enum`, `collections.abc`, `typing`).
- Gecontroleerd gedrag:
  - `datetime.isoweekday()` geeft 1 = maandag t/m 7 = zondag ([Python-docs, datetime](https://docs.python.org/3.12/library/datetime.html#datetime.datetime.isoweekday)), gelijk aan de DB-CHECK `weekdays <@ array[1..7]` (ISO).
  - `datetime.astimezone(ZoneInfo(...))` rekent zomer- en wintertijd correct om ([Python-docs, zoneinfo](https://docs.python.org/3.12/library/zoneinfo.html)). Het tijdvenster gebruikt `time(local.hour, local.minute)`, zodat het `fold`-attribuut geen rol speelt.
  - Postgres `time without time zone` loopt van `00:00:00` t/m `24:00:00` ([Postgres-docs, datetime types](https://www.postgresql.org/docs/current/datatype-datetime.html)). Python `datetime.time` en de tijdparser van pydantic kennen geen uur 24; daarom de omzetting in A7.
  - Pydantic v2 parseert in lax-modus `"17:00:00"` naar `datetime.time` en een lijst naar `frozenset`. In strict mode accepteert een `frozenset`-veld alleen een `frozenset` (geen lijst) en weigert een int-veld `bool` ([conversietabel](https://pydantic.dev/docs/validation/latest/concepts/conversion_table/)); daarom de strengheid per element via `StrictInt` ([strict mode](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/)). `Field(...)` in `Annotated` als type-argument van een container (`list[Annotated[int, Field(gt=0)]]`) is gedocumenteerd ([fields](https://pydantic.dev/docs/validation/latest/concepts/fields/)). `ValidationError` is een subklasse van `ValueError` ([standard types](https://pydantic.dev/docs/validation/latest/api/pydantic/standard_library_types/)). WP-05 bouwt al op dit gedrag.
- Geen API-endpoints, geen netwerk, geen kosten.

## Risico's
- **R1. Defaults niet getoetst aan echt gebruik.** `min_go_hours = 2` en `days_ahead = 3` zijn een voorstel (A1, A2). Lars toetst ze in de M1-testweek. Een wijziging is één constante plus een nieuwe export van het contractbestand.
- **R2. Profiel gaat voor spot.** Volgens het contract wint de algemene `default_min_kn` van het profiel van de specifieke `default_min_kn` van de spot. Een spot die meer wind nodig heeft (bijv. door choppy water) krijgt dan toch de lagere profielwaarde. Dat is bewust (de gebruiker kent zijn eigen ondergrens) en per spot te overrulen met een regel. Benoemd zodat Lars het in de testweek ziet.
- **R3. Fouten bij het samenstellen van een regel.** Een conflict tussen niveaus (A6), `earliest_local = 24:00:00` (E37) of een onverwachte DB-waarde geeft een `ValueError` in `from_row` of `resolve_rule`. Als WP-10 die niet per favoriet afvangt, stopt de alertjob voor alle gebruikers. Mitigatie: één `try` per favoriet rond `from_row` en `resolve_rule`, expliciet onder "Gevolgen voor latere WP's"; `latest_local = 24:00:00` wordt al geaccepteerd (E36); de DB-CHECKs maken conflicten binnen één niveau onmogelijk.
- **R4. Verschuivende windows.** Door het uitsluiten van het huidige uur en de afkapping op `days_ahead` verschuiven `start` en `end` van run tot run. WP-08 moet dit opvangen met zijn tolerantie (±1 uur) en mag een begonnen window dat te kort wordt niet als `cancelled` melden. Benoemd voor WP-08.
- **R5. Pariteit met WP-16.** De TypeScript-spiegel moet de afgeleide `max_kn`, de conflictfout en de 24:00-afhandeling exact overnemen. Mitigatie: de tabel in Ontwerp, `FIELD_SOURCES` en `min_span_kn` in `alert_defaults.json`, plus de gedeelde `rule_resolution_cases.json` uit WP-16.

## Buiten scope
- Regels, profielen en favorieten laden of opslaan, het filter op `verified` en de foutafhandeling per favoriet (WP-10).
- Deduplicatie, snapshots en berichten (WP-08); kite-advies (WP-06/WP-08).
- UI en `effectiveRule()` in TypeScript, `rule_resolution_cases.json` (WP-16).
- Wijzigingen aan de evaluatie, drempels of richtingsklassen (WP-05), aan het databaseschema (WP-01; bijv. een CHECK die `24:00` weigert) of aan `forecast_days` (WP-03).
- Wijzigingen aan `cli.py` buiten de ene docstringregel.
- Stille uren voor meldingen (geen onderdeel van het plan).
- Een functie die per veld de bron van de effectieve waarde teruggeeft (voor "standaard: X (bron)" in WP-16). Dat kan WP-16 additief toevoegen als het nodig is.

## Stappenplan voor de builder
Werk op branch `wp/WP-07` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-07`. Lees of print `.env` nooit. Na elke stap vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Eén commit per stap, commitberichten in het Engels.

1. **Regels, eerst de tests.**
   - Maak `tests/alert_fixtures.py` (alle helpers uit het Testplan, inclusief `migration_sql`, `migration_range`, `migration_text_array` en `migration_int_array`).
   - Schrijf `tests/test_alert_rules.py` (AC-1, AC-2, `test_end_of_day_time` en de overige tests in die sectie). Rood.
   - Maak `src/shakka/domain/alerts.py` met de constanten (incl. `END_OF_DAY_TIME_STRINGS`), `_IsoWeekday`, `RuleSource`, `RULE_FIELDS`, `FIELD_SOURCES`, `FIELD_LABEL_NL`, `_RevalidatingModel`, `AlertRuleOverride` (met de twee `mode="before"`-validators voor 24:00), `ProfileDefaults`, `AlertRule`, `resolve_rule` (de tabel uitgeschreven, zie Ontwerp) en `rider_limits`. Groen, inclusief `test_domain_purity.py`.

   Commit: `feat(domain): add alert rule resolution and validation`.
2. **Windows, eerst de tests.**
   - Schrijf `tests/test_windows.py` (AC-3, AC-4 en de extra tests, inclusief `test_latest_end_of_day_from_row`, `test_dst_spring_forward_continuous` en de vastgelegde `test_safety_grid`). Rood.
   - Voeg `Window` (zes invarianten) en `find_windows` (stappen 0–8 uit Ontwerp) toe aan `alerts.py`. Groen.

   Commit: `feat(domain): find contiguous go windows for alert rules`.
3. **Contractbestand, eerst de tests.**
   - Voeg `test_alert_defaults_content` en `test_alert_defaults_ranges_match_migration` toe aan `tests/test_contracts.py` en vervang de twee keer `3` in `test_cli_check_missing_and_export` door `len(CONTRACT_FILES)`. Rood.
   - Pas `src/shakka/contracts.py` aan (vierde naam in `CONTRACT_FILES`, `_alert_defaults_items()`, docstring).
   - Vervang in `src/shakka/cli.py` alleen de docstring van `contracts_export` door `"""Write reason codes, direction classes, confidence labels and alert defaults as JSON."""`.
   - Draai `uv run shakka contracts export`. Alleen `data/contracts/alert_defaults.json` is nieuw; de andere drie blijven `(unchanged)`. Controleer de inhoud tegen het voorbeeld in Interfaces. Groen, en `uv run shakka contracts export --check` geeft exit 0.

   Commit: `feat(contracts): export alert rule defaults`.
4. **Eindcontrole.** Volledige suite, ruff en `uv run shakka contracts export --check`. Controleer met `git status` en `git diff --stat develop` dat alleen de bestanden uit "Bestanden" zijn gewijzigd of aangemaakt, dat de diff van `cli.py` precies één regel is, en dat `reason_codes.json`, `dir_classes.json` en `confidence.json` byte-gelijk zijn gebleven.

## Verwerking review
Ronde 1 (`review.md`, CHANGES_REQUIRED).

| Punt | Verwerking |
|---|---|
| **B-1** (24:00:00 uit de database) | Beslissing van de orchestrator: optie (a) plus de robuustheid uit (b). `latest_local` `"24:00"`/`"24:00:00"` wordt `None` ("geen bovengrens") via een `mode="before"`-validator en de constante `END_OF_DAY_TIME_STRINGS` (A7, tabel `AlertRuleOverride`, E36). `earliest_local` 24:00 blijft een `ValidationError`, nu met een eigen melding (E37). Tests: `test_end_of_day_time` (rules) en `test_latest_end_of_day_from_row` (windows). De pariteitsclaim in A7 is genuanceerd: "en omgekeerd" geldt nu met een lijst bekende verschillen. Onder "Gevolgen", WP-10: `AlertRuleOverride.from_row`, `ProfileDefaults.from_row` en `resolve_rule` staan per favoriet samen in één `try ... except ValueError`; één kapotte rij stopt nooit de hele job. R3 is daarop aangepast. Onder WP-16: de UI schrijft nooit 24:00, en `effectiveRule()` neemt de omzetting over. |
| N-1 (strikte ints `AlertRule`) | Overgenomen. De tabel van `AlertRule` noemt nu strikte ints voor de elementen van `weekdays`, `min_go_hours` en `days_ahead`. Ontwerp legt het mechanisme vast: `strict=True` op het hele `frozenset`-veld zou lijsten weigeren (conversietabel nagekeken), dus `_IsoWeekday = Annotated[StrictInt, Field(ge=1, le=7)]` per element. Nieuwe test `test_strict_ints_in_rule`, en `[6.0]` plus een positief lijstgeval in `test_weekday_out_of_range`. |
| N-2 (`updated_at`) | Overgenomen als bewuste afwijking in A7, met een voorstel voor de contracttekst in WORK_PACKAGES. |
| N-3 (docstring `cli.py`) | Overgenomen. De docstring van `contracts_export` is de enige toegestane wijziging aan `cli.py` (Bestanden, Buiten scope, stap 3 en de eindcontrole). |
| N-4 (`min`/`max` bij `max_kn`) | Overgenomen in "Betekenis": het zijn invoergrenzen voor regel en profiel, geen grenzen voor de effectieve waarde. E3 en WP-16 verwijzen ernaar. |
| N-5 (imports) | Overgenomen. `Mapping` en `Sequence` uit `collections.abc`, `date` geschrapt, pydantic-imports en `Annotated` toegevoegd. `from_row` geeft `Self`. Ruff is leidend bij overbodige imports. |
| N-6 (zomertijdtest) | Overgenomen als E38 en `test_dst_spring_forward_continuous` (2027-03-28, met controle van de lokale uren 1, 3, 4). De kalender is aangevuld. |
| N-7 (migratieregex weekdays) | Overgenomen. Drie helpers in `alert_fixtures.py` (`migration_range`, `migration_text_array`, `migration_int_array`) die alleen de inhoud van `array[...]` lezen, net als `_sql_list`. |
| N-8 (`test_safety_grid`) | Overgenomen. `now`, `rule(min_go_hours=1, dir_classes=subset)`, het startuur en de cyclus van 8 liggen vast. Er komt een niet-vacuüm-controle bij (minstens één window per deelverzameling). |
| N-9 (E15, halve uren) | Overgenomen als advies onder WP-16: alleen hele uren aanbieden. |
| N-10 (`days_ahead`-label) | Overgenomen binnen de scope. Het label wordt "Dagen vooruit (na vandaag)" (`FIELD_LABEL_NL` en het contractbestand), "Betekenis" legt het uit, en onder WP-16 staat een advies voor de uitlegtekst. |
| N-11 (`model_construct` in test) | Overgenomen. Er komt een vast commentaar boven de `model_construct`-regel, met de uitleg waarom dat mag. |
