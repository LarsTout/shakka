# Blueprint WP-06: Kite-advies (puur)
Status: DRAFT
Revisie: 1

## Doel
Een pure module `shakka.domain.kite` die op basis van gewicht, niveau, quiver en windkracht een kitemaat **uit de eigen quiver** adviseert:
- `ideal_kite_size`: de ideale maat volgens een vastgelegde formule;
- `recommend_kite`: advies voor één uur (maat, fit, ideale maat);
- `recommend_for_window`: advies voor een window van meerdere uren, met een gedocumenteerde aggregatie;
- de voorbeeldtabel `ingest/tests/fixtures/kite_examples.yaml` (26 gevallen, `checked_by_lars: false`) waartegen de functie wordt getest.

WP-08 gebruikt `KiteAdvice` in `render_alert`; WP-10 bouwt een `RiderProfile` uit `profiles` en roept `recommend_for_window` aan.

## Aannames
Dit zijn voorstellen. Lars beoordeelt ze via de voorbeeldtabel; de reviewer toetst ze.

- **A1. Formule: J. Douglass-regel met een factor per niveau.** `ideaal (m²) = factor(niveau) × gewicht (kg) / wind (kn)`.
  - `intermediate`: **2,2**. Dit is de veelgebruikte regel "weight (kg) / wind (knots) × 2.2" (Peter's Kiteboarding Handbook; kitesurfingofficial.com noemt hem de J. Douglass-formule voor een gemiddelde freerider op een twintip van 138–142 cm, bij circa 14–22 kn).
  - `beginner`: **1,8**. Overgenomen uit The Kitesurf Centre ("Rider Weight / Wind Speed x Ability", beginner 1.8). Reden: een beginner kan vermogen nog niet goed wegdumpen; een kleinere kite is veiliger. kitesurfingofficial.com zegt hetzelfde in woorden ("Beginners should sit at the lower edge of every range").
  - `advanced`: **2,2**, gelijk aan intermediate. kitesurfingofficial.com laat gevorderden dezelfde maat houden als intermediate. The Kitesurf Centre noemt 2,3 voor een "independent rider", maar dat niveau valt in onze enum eerder onder `intermediate`. Een hogere factor voor gevorderden zou een groter, krachtiger advies geven zonder dat daar een eenduidige bron voor is.

  Bronnen lopen uiteen (kitesurfingofficial.com geeft bijvoorbeeld 12 m² voor 75 kg bij 18 kn, de formule geeft 9,2). Lars toetst de uitkomst via de voorbeeldtabel. Board, discipline (foil, wave, big air) en vlagerigheid zitten niet in het model (zie Buiten scope).
- **A2. Afronding.** `ideal_size_m2` wordt half-up afgerond op 0,1 m² (`math.floor(raw * 10 + 0.5) / 10`). De keuze uit de quiver en de fit gebruiken die afgeronde waarde, zodat `KiteAdvice` zelf reproduceerbaar is.
- **A3. Keuze uit de quiver: dichtstbijzijnde maat naar verhouding.** Trekkracht schaalt met het oppervlak, dus "dichtbij" is een verhouding, geen verschil in m². De grens tussen twee buren `a < b` is hun meetkundig gemiddelde `√(a·b)`. Ligt de ideale maat **precies** op de grens, dan wint de **kleinere** kite (veiligheid). Gevolg: een 9 wint van een 12 tot en met ideaal 10,39.
- **A4. Fit: band van factor 1,25 rond de ideale maat.** `ideal` als `ideaal / 1,25 ≤ maat ≤ ideaal × 1,25` (grenzen inclusief), `underpowered` als de maat kleiner is, `overpowered` als hij groter is. Een factor 1,25 in oppervlak komt overeen met circa 12 % in windsnelheid (circa 2 kn bij 18 kn). Bij een gangbare quiver (7/9/12/14) valt een keuze binnen de quiver daardoor meestal binnen de band; `underpowered` en `overpowered` signaleren vooral dat de grootste of kleinste kite niet toereikend is.
- **A5. Aggregatie per window: de bovenste mediaan (`statistics.median_high`) van de uurlijkse windsnelheden.** Daarna precies `recommend_kite` op die waarde. Redenen:
  - een mediaan is robuust tegen één uitschieter (zelfde gedachte als de consensus in WP-05);
  - bij een even aantal uren kiest `median_high` de sterkere van de twee middelste waarden. Dat geeft nooit een grotere kite dan de gewone mediaan, dus het leunt naar de veilige kant;
  - de waarde is altijd een echt uur uit het window, dus uitlegbaar in een bericht;
  - het maximum zou je het grootste deel van het window underpowered laten; het gemiddelde is gevoelig voor één piekuur.

  Vlagen tellen niet mee: het contract geeft alleen `wind_kn`, en vlagerigheid zit al in de evaluatie (`gusty`, `too_gusty`, WP-05).
- **A6. Invoerdomein.** Gelijk aan de DB-checks van WP-01 (`profiles_weight_range`, `profiles_quiver_valid`):
  - gewicht: geheel getal 30–200 kg (geen `bool`, geen float);
  - quiver: 0–10 maten, elk een eindig getal 3–21 m² (geen `bool`). Dubbele maten mogen (de DB staat ze toe) en worden samengevoegd; de quiver wordt oplopend gesorteerd opgeslagen;
  - wind: eindig getal 1–100 kn (geen `bool`). De ondergrens houdt de ideale maat begrensd (max. 440 m²); go-uren hebben in de praktijk minstens 5 kn.

  Ongeldige invoer geeft `ValueError` (pydantic's `ValidationError` is daar een subklasse van). Een lege quiver is geldig en geeft `None`.
- **A7. Constanten staan in `shakka.domain.kite`, niet in `shakka.domain.defaults`.** WP-05 maakt `defaults.py` parallel aan; een tweede schrijver in hetzelfde bestand geeft een mergeconflict, en kite-advies hangt volgens A-8 niet af van WP-05.
- **A8. Kleine uitbreiding op het contract** (alleen toevoegingen): de publieke helpers `pick_from_quiver` en `classify_fit`, en de constanten uit "Interfaces". Ze maken de keuze- en fitregel los testbaar en herbruikbaar voor WP-10 en WP-16 (formuliervalidatie met dezelfde grenzen).

## Ontwerp
Eén nieuw domeinbestand `ingest/src/shakka/domain/kite.py`. Het importeert alleen `math`, `statistics`, `types`, `collections.abc`, `enum`, `typing`, `pydantic` en `shakka.domain.spot` (voor `Level`). De bestaande puurheidstest dekt het automatisch.

**Berekening per uur** (`recommend_kite`):
1. Wind valideren (A6).
2. Lege quiver: `None`.
3. `ideal = ideal_kite_size(weight, level, wind)`: `raw = LEVEL_SIZE_FACTOR[level] * weight_kg / wind_kn` (exact in deze volgorde: eerst factor × gewicht, dan delen door wind), dan afronden volgens A2.
4. `size = pick_from_quiver(quiver, ideal)`: met de oplopende, unieke maten `s[0..n-1]` is de index het aantal `i` in `1..n-1` waarvoor `ideal * ideal > s[i-1] * s[i]`. Omdat de producten strikt stijgen, is dat altijd een prefix; vergelijken met het product vermijdt `sqrt` en `log`.
5. `fit = classify_fit(size, ideal)`: `size * FIT_TOLERANCE < ideal` → `underpowered`; `size > ideal * FIT_TOLERANCE` → `overpowered`; anders `ideal`. `FIT_TOLERANCE = 1.25` is exact representeerbaar.

**Monotonie (AC-4 en AC-5) volgt uit de constructie:** IEEE-vermenigvuldiging en -deling zijn monotoon, `floor` is monotoon, en de index in stap 4 is een aftelling van een monotone voorwaarde in `ideal`. Meer wind geeft dus nooit een grotere ideale maat of gekozen maat; meer gewicht nooit een kleinere ideale maat. De eigenschapstests tonen dit aan op een raster.

**Window** (`recommend_for_window`): waarden valideren, leeg → `None`, anders `recommend_kite(rider, statistics.median_high(values))`. De volgorde van de uren maakt niet uit.

**Modellen:** `RiderProfile` en `KiteAdvice` zijn bevroren pydantic-modellen met `extra="forbid"`, net als `SpotProfile` en `TideExtreme`. `RiderProfile` normaliseert de quiver in een before-validator naar een oplopende tuple van unieke floats, zodat elke consument dezelfde vorm ziet.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/domain/kite.py` | aanmaken | Constanten, `KiteFit`, `KiteAdvice`, `RiderProfile`, `ideal_kite_size`, `pick_from_quiver`, `classify_fit`, `recommend_kite`, `recommend_for_window` |
| `ingest/tests/fixtures/kite_examples.yaml` | aanmaken | De voorbeeldtabel, letterlijk zoals in "Voorbeeldtabel" hieronder |
| `ingest/tests/test_kite.py` | aanmaken | Alle tests uit het testplan |

Geen wijzigingen in `pyproject.toml`, `cli.py`, de database of `data/contracts`. `docs/STATUS.md` volgt de normale `/ship`-flow.

## Interfaces en contracten

```python
# ingest/src/shakka/domain/kite.py
"""Kite size advice from rider weight, level, quiver and wind. Pure: no I/O, no clock."""

import math
import statistics
from collections.abc import Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, Final

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from shakka.domain.spot import Level

LEVEL_SIZE_FACTOR: Final[Mapping[Level, float]] = MappingProxyType(
    {Level.BEGINNER: 1.8, Level.INTERMEDIATE: 2.2, Level.ADVANCED: 2.2}
)
WEIGHT_RANGE_KG: Final = (30, 200)          # inclusive, equal to DB check profiles_weight_range
WIND_RANGE_KN: Final = (1.0, 100.0)         # inclusive
QUIVER_SIZE_RANGE_M2: Final = (3.0, 21.0)   # inclusive, equal to DB check profiles_quiver_valid
MAX_QUIVER_KITES: Final = 10                # counted before de-duplication, like the DB check
FIT_TOLERANCE: Final = 1.25                 # size within [ideal / 1.25, ideal * 1.25] is "ideal"


class KiteFit(StrEnum):
    IDEAL = "ideal"
    UNDERPOWERED = "underpowered"
    OVERPOWERED = "overpowered"


class KiteAdvice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    size_m2: float        # always one of rider.quiver_m2
    fit: KiteFit
    ideal_size_m2: float  # rounded half-up to 0.1


class RiderProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    weight_kg: Annotated[int, Field(strict=True, ge=30, le=200)]
    level: Level
    quiver_m2: Annotated[tuple[float, ...], BeforeValidator(_normalize_quiver)] = ()


def ideal_kite_size(weight_kg: int, level: Level, wind_kn: float) -> float: ...
def pick_from_quiver(sizes_m2: Sequence[float], ideal_m2: float) -> float | None: ...
def classify_fit(size_m2: float, ideal_m2: float) -> KiteFit: ...
def recommend_kite(rider: RiderProfile, wind_kn: float) -> KiteAdvice | None: ...
def recommend_for_window(rider: RiderProfile, wind_kn_values: Sequence[float]) -> KiteAdvice | None: ...
```

Gedrag per functie:

| Functie | Gedrag | `ValueError` bij |
|---|---|---|
| `_normalize_quiver(v)` (privé) | Accepteert `list` of `tuple`. Geeft `tuple(sorted({float(x) for x in v}))`. | geen list/tuple; meer dan 10 elementen (vóór ontdubbelen); element `bool`, geen `int`/`float`, NaN, ±inf, buiten 3–21. Melding noemt de waarde. |
| `ideal_kite_size` | `level = Level(level)` (strings als `"beginner"` werken ook); `raw = LEVEL_SIZE_FACTOR[level] * weight_kg / wind_kn`; geeft `math.floor(raw * 10 + 0.5) / 10`. | `weight_kg` geen `int` of een `bool`, of buiten 30–200; onbekend niveau; `wind_kn` `bool`, geen `int`/`float`, niet eindig, of buiten 1–100. |
| `pick_from_quiver` | Lege reeks → `None`. Anders oplopend en ontdubbeld `s`; index = `sum(1 for i in range(1, len(s)) if ideal_m2 * ideal_m2 > s[i-1] * s[i])`; geeft `s[index]`. | een maat of `ideal_m2` die geen eindig getal > 0 is (of een `bool`). |
| `classify_fit` | zie Ontwerp stap 5 | `size_m2` of `ideal_m2` geen eindig getal > 0. |
| `recommend_kite` | Valideert eerst de wind (zelfde regels als `ideal_kite_size`), dan: lege quiver → `None`; anders `KiteAdvice(size_m2=pick, fit=classify_fit(pick, ideal), ideal_size_m2=ideal)`. | ongeldige wind, ook bij een lege quiver. |
| `recommend_for_window` | `values = list(wind_kn_values)`; valideer elk element; leeg → `None`; anders `recommend_kite(rider, statistics.median_high(values))`. | een ongeldig element (ook `None`). |

`_normalize_quiver` en `_check_wind` staan in het bestand vóór de klassen die ze gebruiken. De windvalidatie zit in één privé-helper `_check_wind(value: Any) -> float`, die alle drie de publieke windfuncties gebruiken. Meldingen zijn Engels en noemen het veld en de waarde, bijvoorbeeld `wind_kn must be between 1.0 and 100.0, got 0`.

**Contract richting WP-08 en WP-10 (ter informatie, geen code in deze WP):**
- WP-10 maakt alleen een `RiderProfile` als `profiles.weight_kg` en `profiles.level` gevuld zijn; anders `kite=None`. Een lege `quiver_m2` mag; `recommend_*` geeft dan `None`.
- WP-10 geeft aan `recommend_for_window` de `wind_kn` van de uren van het window door (`[h.wind_kn for h in window.hours if h.wind_kn is not None]`).
- WP-08 toont `size_m2` en eventueel `fit`; de Nederlandse labels voor `KiteFit` legt WP-08 vast.

## Voorbeeldtabel
Voorstel van de planner. Lars controleert elke regel en zet daarna `checked_by_lars: true`. Wil Lars een regel anders, dan is dat een signaal dat formule of factor niet klopt (zie Risico's R1); de tabel wordt niet los van de formule aangepast.

Leeswijzer: "ideaal" is de berekende maat, "advies" de gekozen kite, "fit" of die binnen de band van factor 1,25 valt.

| id | kg | niveau | quiver (m²) | wind (kn) | ideaal | advies | fit | Wat het toont |
|---|---|---|---|---|---|---|---|---|
| k01 | 75 | intermediate | 7, 9, 12 | 15 | 11,0 | 12 | ideal | basisgeval |
| k02 | 75 | intermediate | 7, 9, 12 | 18 | 9,2 | 9 | ideal | |
| k03 | 75 | intermediate | 7, 9, 12 | 22 | 7,5 | 7 | ideal | |
| k04 | 75 | intermediate | 7, 9, 12 | 30 | 5,5 | 7 | overpowered | kleinste kite te groot |
| k05 | 75 | intermediate | 7, 9, 12 | 10 | 16,5 | 12 | underpowered | grootste kite te klein |
| k06 | 75 | beginner | 7, 9, 12 | 15 | 9,0 | 9 | ideal | beginner kleiner dan k01 |
| k07 | 75 | advanced | 7, 9, 12 | 25 | 6,6 | 7 | ideal | advanced = intermediate |
| k08 | 60 | beginner | 6, 8, 10 | 18 | 6,0 | 6 | ideal | lichte rider |
| k09 | 60 | intermediate | 6, 8, 10 | 14 | 9,4 | 10 | ideal | |
| k10 | 60 | intermediate | 6, 8, 10 | 24 | 5,5 | 6 | ideal | |
| k11 | 90 | intermediate | 9, 12, 15, 17 | 16 | 12,4 | 12 | ideal | zware rider |
| k12 | 90 | intermediate | 9, 12, 15, 17 | 12 | 16,5 | 17 | ideal | |
| k13 | 90 | intermediate | 9, 12, 15, 17 | 9 | 22,0 | 17 | underpowered | |
| k14 | 90 | advanced | 9, 12, 15, 17 | 22 | 9,0 | 9 | ideal | |
| k15 | 100 | intermediate | 9, 12, 15, 17 | 35 | 6,3 | 9 | overpowered | |
| k16 | 80 | beginner | 10 | 25 | 5,8 | 10 | overpowered | één kite |
| k17 | 80 | intermediate | 10 | 12 | 14,7 | 10 | underpowered | één kite |
| k18 | 70 | intermediate | 5, 7, 9, 12, 14 | 28 | 5,5 | 5 | ideal | grote quiver |
| k19 | 70 | intermediate | 5, 7, 9, 12, 14 | 17 | 9,1 | 9 | ideal | |
| k20 | 70 | beginner | 5, 7, 9, 12, 14 | 13 | 9,7 | 9 | ideal | beginner, zelfde wind als k21 |
| k21 | 70 | intermediate | 5, 7, 9, 12, 14 | 13 | 11,8 | 12 | ideal | |
| k22 | 85 | intermediate | 7,5, 10,5, 13,5 | 19 | 9,8 | 10,5 | ideal | halve maten |
| k23 | 75 | intermediate | 12, 7, 9, 9 | 15 | 11,0 | 12 | ideal | ongesorteerd, dubbele 9 (= k01) |
| k24 | 110 | intermediate | 9, 12, 15, 17 | 14 | 17,3 | 17 | ideal | |
| k25 | 50 | beginner | 5, 7, 9 | 20 | 4,5 | 5 | ideal | |
| k26 | 65 | intermediate | 7, 9, 12 | 40 | 3,6 | 7 | overpowered | storm |

Geen enkel geval ligt dicht bij een afrondingsgrens (de fractie van `raw × 10` ligt nooit binnen 0,03 van ,5; het krapst is k21 met `raw × 10` = 118,46) of exact op een keuze- of fitgrens. Het dichtst bij een keuzegrens ligt k18 (ideaal² 30,25 tegen grens 35), het dichtst bij een fitgrens k04 (maat 7 tegen grens 6,875). Beide marges liggen ver boven de float-nauwkeurigheid, dus de uitkomst hangt niet af van float-details.

Inhoud van `ingest/tests/fixtures/kite_examples.yaml` (letterlijk overnemen):

```yaml
# Kite advice examples for shakka.domain.kite (WP-06).
# Proposed by the planner. Lars checks every case and then sets checked_by_lars to true.
# Formula: ideal = LEVEL_SIZE_FACTOR[level] * weight_kg / wind_kn, rounded half-up to 0.1 m2.
#   Factors: beginner 1.8, intermediate 2.2, advanced 2.2.
# Choice: nearest quiver size by ratio; the boundary between two neighbours is their
#   geometric mean, and an exact tie picks the smaller kite.
# Fit: ideal when ideal / 1.25 <= size <= ideal * 1.25, else underpowered or overpowered.
# Rationale and sources: docs/wp/WP-06/blueprint.md.
checked_by_lars: false
cases:
  - {id: k01, weight_kg: 75, level: intermediate, quiver_m2: [7, 9, 12], wind_kn: 15, expected: {size_m2: 12, ideal_size_m2: 11.0, fit: ideal}}
  - {id: k02, weight_kg: 75, level: intermediate, quiver_m2: [7, 9, 12], wind_kn: 18, expected: {size_m2: 9, ideal_size_m2: 9.2, fit: ideal}}
  - {id: k03, weight_kg: 75, level: intermediate, quiver_m2: [7, 9, 12], wind_kn: 22, expected: {size_m2: 7, ideal_size_m2: 7.5, fit: ideal}}
  - {id: k04, weight_kg: 75, level: intermediate, quiver_m2: [7, 9, 12], wind_kn: 30, expected: {size_m2: 7, ideal_size_m2: 5.5, fit: overpowered}}
  - {id: k05, weight_kg: 75, level: intermediate, quiver_m2: [7, 9, 12], wind_kn: 10, expected: {size_m2: 12, ideal_size_m2: 16.5, fit: underpowered}}
  - {id: k06, weight_kg: 75, level: beginner, quiver_m2: [7, 9, 12], wind_kn: 15, expected: {size_m2: 9, ideal_size_m2: 9.0, fit: ideal}}
  - {id: k07, weight_kg: 75, level: advanced, quiver_m2: [7, 9, 12], wind_kn: 25, expected: {size_m2: 7, ideal_size_m2: 6.6, fit: ideal}}
  - {id: k08, weight_kg: 60, level: beginner, quiver_m2: [6, 8, 10], wind_kn: 18, expected: {size_m2: 6, ideal_size_m2: 6.0, fit: ideal}}
  - {id: k09, weight_kg: 60, level: intermediate, quiver_m2: [6, 8, 10], wind_kn: 14, expected: {size_m2: 10, ideal_size_m2: 9.4, fit: ideal}}
  - {id: k10, weight_kg: 60, level: intermediate, quiver_m2: [6, 8, 10], wind_kn: 24, expected: {size_m2: 6, ideal_size_m2: 5.5, fit: ideal}}
  - {id: k11, weight_kg: 90, level: intermediate, quiver_m2: [9, 12, 15, 17], wind_kn: 16, expected: {size_m2: 12, ideal_size_m2: 12.4, fit: ideal}}
  - {id: k12, weight_kg: 90, level: intermediate, quiver_m2: [9, 12, 15, 17], wind_kn: 12, expected: {size_m2: 17, ideal_size_m2: 16.5, fit: ideal}}
  - {id: k13, weight_kg: 90, level: intermediate, quiver_m2: [9, 12, 15, 17], wind_kn: 9, expected: {size_m2: 17, ideal_size_m2: 22.0, fit: underpowered}}
  - {id: k14, weight_kg: 90, level: advanced, quiver_m2: [9, 12, 15, 17], wind_kn: 22, expected: {size_m2: 9, ideal_size_m2: 9.0, fit: ideal}}
  - {id: k15, weight_kg: 100, level: intermediate, quiver_m2: [9, 12, 15, 17], wind_kn: 35, expected: {size_m2: 9, ideal_size_m2: 6.3, fit: overpowered}}
  - {id: k16, weight_kg: 80, level: beginner, quiver_m2: [10], wind_kn: 25, expected: {size_m2: 10, ideal_size_m2: 5.8, fit: overpowered}}
  - {id: k17, weight_kg: 80, level: intermediate, quiver_m2: [10], wind_kn: 12, expected: {size_m2: 10, ideal_size_m2: 14.7, fit: underpowered}}
  - {id: k18, weight_kg: 70, level: intermediate, quiver_m2: [5, 7, 9, 12, 14], wind_kn: 28, expected: {size_m2: 5, ideal_size_m2: 5.5, fit: ideal}}
  - {id: k19, weight_kg: 70, level: intermediate, quiver_m2: [5, 7, 9, 12, 14], wind_kn: 17, expected: {size_m2: 9, ideal_size_m2: 9.1, fit: ideal}}
  - {id: k20, weight_kg: 70, level: beginner, quiver_m2: [5, 7, 9, 12, 14], wind_kn: 13, expected: {size_m2: 9, ideal_size_m2: 9.7, fit: ideal}}
  - {id: k21, weight_kg: 70, level: intermediate, quiver_m2: [5, 7, 9, 12, 14], wind_kn: 13, expected: {size_m2: 12, ideal_size_m2: 11.8, fit: ideal}}
  - {id: k22, weight_kg: 85, level: intermediate, quiver_m2: [7.5, 10.5, 13.5], wind_kn: 19, expected: {size_m2: 10.5, ideal_size_m2: 9.8, fit: ideal}}
  - {id: k23, weight_kg: 75, level: intermediate, quiver_m2: [12, 7, 9, 9], wind_kn: 15, expected: {size_m2: 12, ideal_size_m2: 11.0, fit: ideal}}
  - {id: k24, weight_kg: 110, level: intermediate, quiver_m2: [9, 12, 15, 17], wind_kn: 14, expected: {size_m2: 17, ideal_size_m2: 17.3, fit: ideal}}
  - {id: k25, weight_kg: 50, level: beginner, quiver_m2: [5, 7, 9], wind_kn: 20, expected: {size_m2: 5, ideal_size_m2: 4.5, fit: ideal}}
  - {id: k26, weight_kg: 65, level: intermediate, quiver_m2: [7, 9, 12], wind_kn: 40, expected: {size_m2: 7, ideal_size_m2: 3.6, fit: overpowered}}
```

Lars kan later eigen gevallen toevoegen (bijvoorbeeld met zijn eigen gewicht en quiver) met een nieuwe `id`; de tests pikken ze automatisch op.

## Edge cases

| # | Geval | Verwacht |
|---|---|---|
| E1 | Lege quiver | `recommend_kite` en `recommend_for_window` geven `None` (na windvalidatie) |
| E2 | Quiver met één kite | altijd die kite; fit volgt de band |
| E3 | Ongesorteerde quiver met dubbele maten (`[12, 7, 9, 9]`) | `RiderProfile.quiver_m2 == (7.0, 9.0, 12.0)`; advies gelijk aan gesorteerd |
| E4 | Quiver met 11 elementen, ook als er dubbelen tussen zitten | `ValueError` (zelfde regel als de DB-check) |
| E5 | Quivermaat 2.9, 21.5, NaN, inf, `True`, `"9"` | `ValueError` |
| E6 | Gewicht 29, 201, `75.0`, `True` | `ValueError` |
| E7 | Wind 0, 0.5, 100.5, NaN, inf, -5, `True`, `"15"` | `ValueError`; ook bij een lege quiver |
| E8 | Wind precies 1 en 100 | geldig |
| E9 | Ideale maat precies op het meetkundig gemiddelde van twee buren | kleinere kite (quiver `(9, 16)`, ideaal 12,0 → 9) |
| E10 | Ideale maat net boven de grens | grotere kite (ideaal 12,1 → 16) |
| E11 | Ideaal groter dan de grootste of kleiner dan de kleinste kite | grootste resp. kleinste kite, fit `underpowered` resp. `overpowered` als buiten de band |
| E12 | Maat precies op de bandgrens (`size == ideal * 1.25` of `size * 1.25 == ideal`) | `ideal` (inclusief) |
| E13 | Afronding op ,x5 | half-up: 75 kg, intermediate, 20 kn → 8,25 → 8,3 |
| E14 | Window leeg | `None` |
| E15 | Window met één uur | gelijk aan `recommend_kite` voor dat uur |
| E16 | Window met even aantal uren | bovenste van de twee middelste waarden |
| E17 | Window in andere volgorde | zelfde advies |
| E18 | Window met `None`, NaN of 0 | `ValueError` |
| E19 | Niveau als string `"advanced"` in `ideal_kite_size` / `RiderProfile` | geaccepteerd en omgezet naar `Level`; `"expert"` geeft `ValueError` |
| E20 | Onbekend veld in `RiderProfile` | `ValueError` (`extra="forbid"`) |

## Testplan
Alles in `ingest/tests/test_kite.py`. Tests eerst (zie stappenplan). De fixture laadt de YAML met `yaml.safe_load` vanuit `Path(__file__).parent / "fixtures" / "kite_examples.yaml"` (tests mogen `yaml` en `pathlib` gebruiken; de puurheidsregel geldt alleen voor `shakka.domain`).

Gedeelde testconstanten:
```python
QUIVERS = [(7.0, 9.0, 12.0), (5.0, 7.0, 9.0, 12.0, 14.0), (6.0, 8.0, 10.0),
           (9.0, 12.0, 15.0, 17.0), (10.0,), (7.5, 10.5, 13.5)]
WEIGHTS = range(50, 111, 5)
WINDS = [8 + 0.5 * i for i in range(65)]  # 8.0 .. 40.0
```

**AC-1 (voorbeeldtabel):**
- `test_examples_file_shape`: top-level sleutels zijn precies `{"checked_by_lars", "cases"}`; `checked_by_lars` is een `bool`; minstens 15 gevallen; unieke `id`'s; elk geval heeft precies de sleutels `id, weight_kg, level, quiver_m2, wind_kn, expected` en `expected` precies `size_m2, ideal_size_m2, fit`; `expected.size_m2` zit in `quiver_m2`.
- `test_example` (geparametriseerd over de gevallen, `ids=` de case-id): `recommend_kite(RiderProfile(...), wind_kn)` geeft `size_m2 == expected.size_m2`, `ideal_size_m2 == expected.ideal_size_m2` en `fit == KiteFit(expected.fit)`.

**AC-2 (`checked_by_lars`):** geen test die op `true` controleert (dat zou de build blokkeren tot Lars tekent). `test_examples_file_shape` borgt dat het veld bestaat en een `bool` is. De verifier leest de waarde: `false` is `NEEDS_LARS`.

**AC-3 (eigenschappen quiver):**
- `test_size_always_from_quiver` (geparametriseerd over `QUIVERS` en `Level`): voor elke combinatie van `WEIGHTS` × `WINDS` zit `advice.size_m2` in `rider.quiver_m2` en in de oorspronkelijke invoer.
- `test_empty_quiver_gives_none`: voor alle `WEIGHTS` × `WINDS` × `Level` geeft `recommend_kite` `None`; `recommend_for_window(rider, [15, 18])` ook.
- `test_single_kite_always_chosen`: voor quivers `(3.0,)`, `(10.0,)`, `(21.0,)` en alle combinaties is `size_m2` die kite.

**AC-4 (meer wind, nooit groter):** `test_more_wind_never_bigger` (per quiver en niveau): per gewicht uit `WEIGHTS` loopt de wind door `WINDS` plus de randen 1.0 en 100.0, oplopend; `size_m2` en `ideal_size_m2` zijn niet-stijgend. Extra: `test_ideal_monotone_in_wind_fine_grid` op een fijn raster (1,0 tot 100,0 in stappen van 0,1) voor gewichten 30, 75 en 200.

**AC-5 (meer gewicht, nooit kleiner):** `test_heavier_never_smaller_ideal`: voor elk niveau en elke wind uit `WINDS` is `ideal_kite_size(w, level, wind)` niet-dalend over `w` van 30 tot en met 200 (stap 1). Extra (niet vereist, wel waar): `size_m2` is dan ook niet-dalend, getest met quiver `(5.0, 7.0, 9.0, 12.0, 14.0)`.

**AC-6 (window-aggregatie):**
- `test_window_uses_upper_median`: rider 75 kg, intermediate, quiver `(7, 9, 12)`, window `[12, 18, 25, 14]`. Verwacht `recommend_kite(rider, 18)`, dus `ideal_size_m2 == 9.2` en `size_m2 == 9`. De test toont ook dat het verschilt van de alternatieven: `ideal_kite_size(75, intermediate, x) != 9.2` voor het gemiddelde (17,25 → 9,6), de gewone mediaan (16 → 10,3) en het maximum (25 → 6,6), en `recommend_kite(rider, 25).size_m2 == 7 != 9`.
- `test_window_odd_length`: `[20, 10, 15]` → gelijk aan `recommend_kite(rider, 15)` (12 m², ideaal 11,0).
- `test_window_order_invariant`: alle permutaties van `[12, 18, 25, 14]` geven hetzelfde advies.
- `test_window_single_hour`: `[18]` → gelijk aan `recommend_kite(rider, 18)`.
- `test_window_empty`: `[]` → `None`.
- `test_window_invalid_value` (geparametriseerd): `[15, None]`, `[15, float("nan")]`, `[15, 0]` → `ValueError`.

**Aanvullende unit-tests (edge cases):**
- `test_ideal_values`: 75/intermediate/15 → 11.0; 75/beginner/15 → 9.0; 75/advanced/15 → 11.0; 75/intermediate/20 → 8.3 (E13, half-up); level als string `"beginner"` → 9.0 (E19).
- `test_pick_tie_goes_to_smaller`: `pick_from_quiver((9, 16), 12.0) == 9`; `(9, 16), 12.1 → 16`; `(9, 16), 11.9 → 9`; `pick_from_quiver((), 10.0) is None`; `pick_from_quiver((16, 9, 9), 12.1) == 16` (E9, E10). Via de publieke route: `recommend_kite(RiderProfile(weight_kg=60, level="intermediate", quiver_m2=(9, 16)), 11)` geeft ideaal 12,0, maat 9, fit `underpowered`.
- `test_classify_fit_bounds`: `classify_fit(10, 8.0) == ideal`, `classify_fit(10, 12.5) == ideal` (E12), `classify_fit(10, 7.9) == overpowered`, `classify_fit(10, 12.6) == underpowered`.
- `test_rider_profile_normalizes_quiver`: `[12, 7, 9, 9]` → `(7.0, 9.0, 12.0)` (E3); `[]` → `()`.
- `test_rider_profile_rejects` (geparametriseerd, E4–E6, E19, E20): 11 maten `[3,4,...,13]`, 11 maten met dubbelen `[9]*11`, maat 2.9, 21.5, NaN, inf, `True`, `"9"`; gewicht 29, 201, 75.0, `True`; niveau `"expert"`; extra veld `name="x"`. Elk geeft `ValueError`.
- `test_rider_profile_is_frozen`: toekennen aan `weight_kg` geeft een fout (pydantic `ValidationError`).
- `test_wind_rejects` (geparametriseerd, E7): 0, 0.5, 100.5, -5, NaN, inf, `True`, `"15"` geven `ValueError` in `ideal_kite_size` en in `recommend_kite`, ook met een lege quiver. 1 en 100 zijn geldig (E8).
- `test_ideal_rejects_weight`: 29, 201, 75.0, `True` → `ValueError`.

**Puurheid:** `tests/test_domain_purity.py` (WP-00) pakt `kite.py` automatisch op en moet groen blijven.

## Externe afhankelijkheden
- **Geen nieuwe packages.** `statistics`, `math` en `types` zijn standaardbibliotheek; `pydantic` (>=2.11) en `pyyaml` (tests) staan al in `ingest/pyproject.toml`.
- **Geen API's.**
- Bronnen voor de formule (gecontroleerd op 15 oktober 2026):
  - Peter's Kiteboarding Handbook, "Choosing the right kite size": "Weight (kg) / wind (knots) x 2.2 = size of kite you should be using", met als voorbeeld 58 kg / 16 kn × 2,2 = 7,9. https://kitesurfing-handbook.peterskiteboarding.com/progression/choosing-the-right-kite-size
  - kitesurfingofficial.com, kite size calculator: J. Douglass-formule `kite_m² = (weight_kg × 2.2) / wind_knots` voor intermediate freeriders op een twintip van 138–142 cm bij circa 14–22 kn; advanced en pro houden dezelfde maat als intermediate. https://kitesurfingofficial.com/tools/kite-size-calculator
  - kitesurfingofficial.com, "What size kite do I need?": "Beginners should sit at the lower edge of every range"; vermogen groeit met het kwadraat van de windsnelheid. https://kitesurfingofficial.com/journal/what-size-kite-do-i-need
  - The Kitesurf Centre, "How to choose the right kite size": "Rider Weight / Wind Speed x Ability", met beginner 1.8, intermediate 2.1, independent rider 2.3. https://www.thekitesurfcentre.com/news/how-to-choose-the-right-kite-size

## Risico's
- **R1. De formule is een vuistregel.** Bronnen verschillen tot zo'n 30 % (zie A1). Mitigatie: Lars toetst de voorbeeldtabel (AC-2) en kan de factoren in `LEVEL_SIZE_FACTOR` laten bijstellen. Bij een wijziging moeten de verwachte waarden in de tabel opnieuw berekend en opnieuw door Lars gecontroleerd worden (`checked_by_lars` terug op `false`).
- **R2. Board, discipline en vlagen zitten niet in het model.** Een foiler of iemand op een groot board heeft een kleinere kite nodig. Het advies is daarom een indicatie in het bericht, geen oordeel; het beïnvloedt de evaluatie en de alerts niet.
- **R3. Float-randgevallen.** Afronding en keuzegrens zijn gevoelig bij exacte grenswaarden. Mitigatie: de voorbeeldtabel vermijdt grenzen (zie Voorbeeldtabel); de grenstests (E9, E12, E13) gebruiken waarden die exact representeerbaar zijn of waarvan de float-uitkomst gecontroleerd is (2,2 × 75 = 165,0 en 1,8 × 75 = 135,0 exact na afronding; 165 / 20 = 8,25 exact). Faalt een van die grenstests toch door float-gedrag, dan schrijft de builder dat in `deviations.md` en stopt; hij past geen verwachte waarden aan.
- **R4. Window-advies op de mediaan kan in het sterkste uur overpowered zijn.** Bewust: zie A5. Als Lars dat in de M1-testweek mist, is een extra waarschuwing in WP-08 de plek, niet een andere aggregatie.

## Buiten scope
- Profiel opslaan, laden of bewerken (WP-01, WP-10, WP-16), inclusief het omzetten van een `profiles`-rij naar `RiderProfile`.
- Kite-advies in berichten en de Nederlandse labels voor `KiteFit` (WP-08).
- Contractbestanden in `data/contracts` (`shakka contracts export` is van WP-05).
- Correcties voor board, discipline, foil, vlagerigheid of temperatuur/luchtdichtheid.
- Elke afhankelijkheid van WP-05-code (`shakka.domain.defaults`, `evaluation`, `consensus`).

## Stappenplan voor de builder
Werk in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-06` op branch `wp/WP-06`. Na elke stap: `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .` groen, dan committen (Engelse commit message).

1. **Kern met tests eerst.** Schrijf in `tests/test_kite.py` de tests `test_ideal_values`, `test_ideal_rejects_weight`, `test_wind_rejects` (alleen het `ideal_kite_size`-deel), `test_pick_tie_goes_to_smaller` (zonder het `recommend_kite`-deel), `test_classify_fit_bounds`. Implementeer daarna in `src/shakka/domain/kite.py` de constanten, `KiteFit`, `_check_wind`, `ideal_kite_size`, `pick_from_quiver` en `classify_fit` tot ze groen zijn. Commit: `feat(kite): ideal size, quiver pick and fit classification`.
2. **Modellen en uuradvies.** Voeg de tests `test_rider_profile_normalizes_quiver`, `test_rider_profile_rejects`, `test_rider_profile_is_frozen`, het `recommend_kite`-deel van `test_wind_rejects` en van `test_pick_tie_goes_to_smaller` toe. Implementeer `_normalize_quiver`, `RiderProfile`, `KiteAdvice` en `recommend_kite`. Commit: `feat(kite): rider profile and per-hour recommendation`.
3. **Voorbeeldtabel.** Maak `tests/fixtures/kite_examples.yaml` letterlijk zoals in deze blueprint (`checked_by_lars: false`) en voeg `test_examples_file_shape` en `test_example` toe. Faalt een geval, dan is dat een afwijking: niet de tabel aanpassen, maar `deviations.md` schrijven en stoppen. Commit: `test(kite): add example table for Lars to check`.
4. **Eigenschapstests.** Voeg de tests voor AC-3, AC-4 en AC-5 toe. Ze horen zonder codewijziging groen te zijn; faalt er een, dan is dat een ontwerpfout: `deviations.md` en stoppen. Commit: `test(kite): property tests for quiver choice and monotonicity`.
5. **Window.** Schrijf de AC-6-tests en implementeer `recommend_for_window` met `statistics.median_high`. Commit: `feat(kite): window recommendation using the upper median`.
6. **Afronding.** Draai de volledige suite (inclusief `tests/test_domain_purity.py`) en de lint-commando's. Controleer dat `kite.py` geen imports buiten de lijst uit "Ontwerp" heeft.
