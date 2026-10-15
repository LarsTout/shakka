# Blueprint WP-08: Alert-deduplicatie en berichtopbouw (puur)
Status: DRAFT
Revisie: 1

## Doel
Twee pure domeinmodules:
1. `shakka.domain.dedup`: per gebruiker en spot bepalen welke windows een melding verdienen (`new`, `improved`, `worsened`, `cancelled`), met één melding per window. Oude statusregels worden aan nieuwe windows gekoppeld op overlap. Een kleine verschuiving geeft geen melding. Verlopen windows worden zonder melding afgesloten.
2. `shakka.domain.messages`: een kanaalonafhankelijk Nederlandstalig bericht (titel en body in platte tekst) plus de "ik ga"-link `go_url`.

Er is geen I/O. Laden en opslaan van `alert_state` doet WP-10, versturen doet WP-17 (Web Push, het enige kanaal sinds A-16), en de route `/go` bouwen WP-14 en WP-20.

## Aannames
- **A1. Contractafwijking (bindend): `WindowSnapshot.gust_max_kn: float | None`.** Een `go`-uur kan `gust_kn = None` hebben (WP-05 A2 en "Gevolgen", WP-07 "Gevolgen"). `gust_max_kn` is het maximum over de uren met een bekende vlaag, en `None` als geen enkel uur een vlaag heeft. Een onbekende vlaag wordt nooit 0: niet in de snapshot, niet in een vergelijking (vlagen zijn geen criterium, zie A3) en niet in een bericht (daar staat "vlagen onbekend"). De orchestrator past de contractregel in `docs/WORK_PACKAGES.md` (WP-08, Contracten) aan naar `gust_max_kn: float | None`.
- **A2. Richtingsklasse komt uit de uren, nooit uit `dir_deg`** (WP-05 A15). `WindowSnapshot.dir_class` is de klasse die in de meeste uren voorkomt. Bij een gelijke stand wint de klasse die het dichtst bij aflandig ligt (`sideshore` boven `side_onshore` boven `onshore`): bij twijfel toont het bericht de minst gunstige klasse. `dir_deg` is het circulaire gemiddelde van de uurrichtingen (`circular_mean_deg` uit WP-05) en is alleen informatief. Een snapshot weigert `side_offshore` en `offshore` (harde regel; een window bevat die uren nooit).
- **A3. Drempels voor een wezenlijke verandering (voorstel; Lars toetst in de M1-testweek).**
  Vergeleken worden de **basislijn** (de snapshot van de laatste melding, zie A4) en het huidige window:
  - **Tijd: een rand verschuift 2 uur of meer** (`EDGE_SHIFT_THRESHOLD = 2 h`).
    - Begin 2 uur of meer later, of eind 2 uur of meer eerder: `worsened`.
    - Begin 2 uur of meer eerder, of eind 2 uur of meer later: `improved`.
    - Onderbouwing: AC-4 eist dat ±1 uur geen melding geeft; 2 uur is de kleinste stap daarboven. Modellen verschuiven het moment van een front of het wegvallen van de wind van run tot run vaak een uur; dat is ruis. Bij het standaardminimum van 2 go-uren (WP-07 A1) is een verschuiving van 2 uur al een heel window, dus groter mag de drempel niet zijn.
    - Voor een begonnen window telt het begin vanaf het eerstvolgende hele uur (zie A5), zodat het verstrijken van de tijd zelf nooit een melding geeft.
  - **Wind: het minimum of het maximum van het window verandert 4 kn of meer** (`WIND_CHANGE_THRESHOLD_KN = 4.0`).
    - Daling van 4 kn of meer (minimum of maximum): `worsened`. Stijging van 4 kn of meer: `improved`.
    - "Meer wind is beter" geldt binnen een go-window: te veel wind is daar al uitgesloten, want uren boven `max_kn - 2` zijn `wind_borderline` (marginal) of `wind_too_strong` (WP-05). Het probleem dat overblijft is te weinig wind.
    - Onderbouwing: AC-4 eist dat ±2 kn geen melding geeft. 4 kn is bijna een Beaufort-klasse (Bft 4 = 11–16 kn, Bft 5 = 17–21 kn) en ongeveer één kitemaat bij de formule van WP-06 (75 kg, intermediate: 16 kn geeft 10,3 m², 20 kn geeft 8,3 m²). 3 kn zou de mediaan van de modellen bij elke run laten schommelen rond de drempel.
    - Verschillen worden op 0,1 kn afgerond vóór de vergelijking (`round(c - p, 1)`), zodat 18,2 − 14,2 telt als 4,0.
    - Alleen als geen enkel uur van de basislijn al voorbij is (`baseline.start >= eerstvolgend heel uur`). Bij een begonnen window vallen de vroege uren weg, en dan zijn minimum en maximum niet meer vergelijkbaar.
  - **Geen criterium:** vlagen (vlagerigheid zit al in het oordeel: `gusty` is marginal, `too_gusty` no_go), betrouwbaarheid en richting(sklasse). Alle uren in een window zijn per definitie `go` en rijdbaar voor de regel van de gebruiker. Deze velden staan wel in het bericht zodra er om een andere reden een melding komt. Zo blijft de ruis laag ("alerts die standaard goed staan", plan §1).
  - **Voorrang:** geldt een verslechteringscriterium, dan is het `worsened`, ook als er tegelijk een verbetering is (bijv. eerder begin maar 4 kn minder wind). Slecht nieuws gaat voor; het bericht toont het hele nieuwe window.
  - Een andere waarde is één constante in `dedup.py` plus de tests die precies op de grens liggen.
- **A4. De opgeslagen snapshot is de basislijn: wat de gebruiker het laatst te horen kreeg.** Bij een event wordt `snapshot` het huidige window; zonder event blijft de oude snapshot staan. `window_start` en `window_end` volgen wel elke run het huidige window (voor het koppelen op overlap). Zo kan sluipende verschuiving (bijv. elke run 1 uur later) nooit onder de drempel blijven: na twee runs is het verschil 2 uur en volgt `worsened`. Het bericht toont de basislijn als "Was: …", en dat is precies wat de gebruiker eerder zag.
- **A5. Begonnen windows.** Een entry is **begonnen** als `window_start <= now`. Het begin van een lopend window schuift elk uur op, omdat het huidige uur niet meetelt (WP-07 A9). Daarom:
  - blijft `window_start` van een begonnen entry staan op het oorspronkelijke begin (alleen `window_end` volgt het huidige window);
  - wordt een begonnen entry die geen window meer heeft (bijv. onder `min_go_hours` gezakt) **nooit** `cancelled` (WP-07 "Gevolgen"). Hij blijft ongewijzigd `active` tot `window_end <= now` en wordt dan `expired`. Komt er intussen weer een window dat overlapt, dan wordt het eraan gekoppeld en vergeleken met de basislijn, zonder `new`;
  - telt bij de vergelijking het begin van de basislijn vanaf het eerstvolgende hele uur: `max(baseline.start, floor_hour(now) + 1 h)`.
- **A6. `expired` betekent: afgesloten zonder melding.** Dat geldt voor een afgelopen window (`window_end <= now`, AC-3) en voor een entry die bij het samensmelten van twee windows is opgegaan in een andere entry (A7). De DB-CHECK kent alleen `active`, `cancelled` en `expired`; een vierde status is niet nodig.
- **A7. Splitsen en samensmelten (AC-5).** Koppelen is één-op-één, op de grootste overlap, met een vaste volgorde bij gelijke stand (zie Ontwerp).
  - **Splitsen:** het oude window wordt gekoppeld aan het deel met de grootste overlap (bij gelijke overlap het vroegste deel) en daarmee vergeleken (meestal `worsened`). Elk ander deel krijgt een eigen entry en een `new`-event. Zo weet de gebruiker dat het window korter is, en ook dat er later nog een window is.
  - **Samensmelten:** de vroegste oude entry met de grootste overlap wordt gekoppeld en vergeleken (meestal `improved`); de andere oude entry wordt stil `expired` (A6). Geen `cancelled`, want zijn uren zijn nog steeds go.
  - **Geen dubbele `new`-events:** na elke diff overlappen de spans van actieve entries elkaar niet, en elk huidig window ligt in precies één actieve entry. Een `new`-event komt alleen voor een window dat niet aan een actieve entry gekoppeld is. Dit wordt als invariant getest over een raster van scenario's.
- **A8. Een geannuleerd window dat terugkomt, hergebruikt zijn entry** (AC-3). Overlapt een huidig window (dat niet al aan een actieve entry hangt) een entry met status `cancelled`, dan wordt die entry weer `active` met `last_event = new` en volgt een `new`-event. Dezelfde `id` betekent in WP-17 dezelfde push-`tag`, zodat de nieuwe melding de annulering op de telefoon vervangt.
- **A9. `last_notified_at` wordt door `diff_windows` nooit gewijzigd.** Nieuwe entries krijgen `None`; bestaande houden hun waarde, ook bij een event. In M1 wordt niets afgeleverd, dus het veld blijft leeg (dat sluit aan op het voorstel bij WP-10). WP-17 vult het bij een geslaagde aflevering.
- **A10. Bericht bij `cancelled`: geen kite- en getij-regel.** Er is geen sessie meer om advies voor te geven. Het contract noemt kite-advies en getij onder "als het van toepassing is"; bij een annulering is het niet van toepassing. `render_alert` negeert `kite` en `tides` dan. De verplichte onderdelen (spotnaam, window, wind, vlagen, richting, klasse, betrouwbaarheid) komen uit de vorige snapshot.
- **A11. Volgorde van de regels in de body volgt het belang.** WP-17 kort de body in door hele regels vanaf het begin te nemen tot 150 tekens (besluit Lars: titel 50, body 150). Daarom staan tijd en wind in regel 1, "Was: …" (bij `improved`/`worsened`) in regel 2, dan richting, betrouwbaarheid, kite en getij. De titel is kort ("Go: Wijk aan Zee") en bevat de spotnaam.
- **A12. URL-codering zonder `urllib`.** De puurheidsregel verbiedt `urllib` in `shakka.domain`. `build_go_url` codeert zelf: ASCII-letters, cijfers en `-._~` blijven staan, al het andere wordt per UTF-8-byte `%XX` (hoofdletters). Dat is gelijk aan `urllib.parse.quote(s, safe="")`, en een test toont dat aan.
- **A13. Additieve uitbreidingen van het contract.** De signatures uit WORK_PACKAGES blijven gelijk (behalve A1). Erbij komen:
  - in `dedup`: `EDGE_SHIFT_THRESHOLD`, `WIND_CHANGE_THRESHOLD_KN`, `SNAPSHOT_KEYS`, `ALERT_STATE_COLUMNS`, de typealias `AlertStatus`, `AlertStateEntry.to_row()` en `AlertStateEntry.from_row(row)` (pure mapping voor WP-10), en `classify_change(previous, current, *, now)` (de drempelregel los testbaar);
  - in `messages`: `format_window_local(start, end)`, de labeltabellen en de constanten `TIDE_CONTEXT_MARGIN` en `MAX_TIDE_EXTREMES_IN_MESSAGE`.
- **A14. Geen nieuwe dependencies, geen migratie, geen wijziging aan bestaande code.** Alleen nieuwe bestanden (zie Bestanden). `docs/WORK_PACKAGES.md` (A1) werkt de orchestrator bij.

## Ontwerp

### Lagen
`dedup` importeert de standaardbibliotheek, `pydantic` en `shakka.domain.{alerts, consensus, direction}`. `messages` importeert de standaardbibliotheek (`math`, `string`, `datetime`, `collections.abc`, `typing`), `pydantic` en `shakka.domain.{consensus, dedup, defaults, direction, kite, spot, tide}`. Geen enkele bestaande module importeert deze twee, dus er zijn geen cycli. Geen `urllib` (A12), geen klok: `now` is altijd een parameter.

### Snapshot (`snapshot_window`)
Voor `window: Window` (WP-07; alle uren `go`, rijdbaar, aaneengesloten):
- `start`, `end` = `window.start`, `window.end`.
- `wind_min_kn`, `wind_max_kn` = min en max van `h.wind_kn`. Een uur met `wind_kn is None` geeft `ValueError` (een `go`-uur uit `evaluate_hour` heeft altijd wind; WP-05 A6).
- `gust_max_kn` = max van de `h.gust_kn` die niet `None` zijn, anders `None` (A1).
- `dir_deg`: `mean = circular_mean_deg([h.dir_deg ...])`; `int(round(mean)) % 360`. Is `mean` `None` (tegengestelde richtingen), dan de `dir_deg` van het eerste uur. Een uur met `dir_deg is None` geeft `ValueError`.
- `dir_class`: meest voorkomende `h.dir_class`; bij gelijke stand de klasse die later staat in de volgorde `onshore`, `side_onshore`, `sideshore` (A2).
- `confidence`: de slechtste van de uren (`low` < `medium` < `high`). Een uur met `confidence is None` geeft `ValueError`.

### Koppelen en vergelijken (`diff_windows`)
Invoer: de statusregels van één gebruiker en één spot (`previous`, in elke volgorde) en de huidige windows (`current`, uitvoer van `find_windows`). Notatie: `first_hour = floor_hour(now) + 1 h`; de span van een entry is `[window_start, window_end)`; `overlap(a, b)` is de lengte van de doorsnede (een `timedelta`, 0 als ze niet overlappen).

0. `now` naïef → `ValueError`; daarna `now = now.astimezone(UTC)`.
1. Controles (`ValueError`):
   - alle `spot_id`'s van `previous` en `current` samen zijn hooguit één waarde;
   - geen twee entries met dezelfde `id` (als `id` niet `None` is);
   - huidige windows overlappen elkaar niet (na sorteren op `start`: `vorige.end <= volgende.start`);
   - actieve entries met `window_end > now` overlappen elkaar niet. `diff_windows` levert dit zelf altijd zo op (invariant I2); een schending betekent een kapotte database.
2. `windows` = `current` gesorteerd op `start`; `snaps[j] = snapshot_window(windows[j])`. `state = list(previous)` (de invoer wordt niet gewijzigd).
3. **Verlopen:** elke `active` entry met `window_end <= now` wordt `status="expired"` (verder ongewijzigd, geen event).
4. Deel de overige actieve entries in: **begonnen** (`window_start <= now`) en **toekomstig** (`window_start > now`).
5. **Fase 1, begonnen entries** (op volgorde van `(window_start, index)`; door de controle in stap 1 is er hooguit één): koppel aan het vrije window met het vroegste `start` dat overlapt met `[max(window_start, first_hour), window_end)`. Het vroegste, niet het grootste: het lopende window loopt dan door vanaf nu, en de span blijft disjunct van latere windows.
6. **Fase 2, toekomstige entries:** alle paren (entry `i`, window `j`) met overlap > 0, gesorteerd op `(-overlap, windows[j].start, entry.window_start, entry.window_end, entry.id or "", i)`. Ga de lijst af en koppel een paar als beide nog vrij zijn (greedy).
7. **Fase 3, heractiveren:** zoals fase 2, maar met entries die vóór deze diff status `cancelled` hadden en windows die na fase 1 en 2 nog vrij zijn.
8. **Gekoppelde entries** (`e = previous[i]`, `W = windows[j]`, `C = snaps[j]`):
   - fase 3: `status="active"`, `window_start=W.start`, `window_end=W.end`, `snapshot=C`, `last_event=new`; event `new` (`current=C`, `previous=None`);
   - fase 1 en 2: `kind = classify_change(e.snapshot, C, now=now)`. `window_start` = `e.window_start` als begonnen, anders `W.start`; `window_end = W.end`. Is `kind` niet `None`, dan ook `snapshot=C` en `last_event=kind`, plus een event (`current=C`, `previous=e.snapshot`). Anders blijft de snapshot de basislijn (A4).
9. **Niet-gekoppelde actieve entries:**
   - begonnen: ongewijzigd (A5);
   - toekomstig, en de span overlapt een huidig window (dat dus aan een andere entry hangt): `status="expired"`, geen event (samensmelten, A6/A7);
   - toekomstig, zonder overlap: `status="cancelled"`, `last_event=cancelled`, snapshot ongewijzigd; event `cancelled` (`current=None`, `previous=e.snapshot`).
10. Entries met status `cancelled` die niet heractiveerd zijn, en entries met status `expired`, blijven ongewijzigd.
11. **Nieuwe windows** (vrij na fase 1–3), op volgorde van `start`: voeg toe `AlertStateEntry(id=None, spot_id=W.spot_id, window_start=W.start, window_end=W.end, status="active", snapshot=C, last_event=new, last_notified_at=None)` en een event `new` met `state_index` = de nieuwe positie.
12. `events` gesorteerd op `state_index`. Resultaat `DiffResult(events, new_state=state)`.

`new_state` bevat dus altijd elke entry uit `previous` precies één keer, op dezelfde positie (`new_state[i].id == previous[i].id`), gevolgd door de nieuwe entries. WP-10 hoeft alleen te schrijven waar `new_state[i] != previous[i]`, en de entries vanaf `len(previous)` in te voegen.

### `classify_change`
```
first_hour = floor_hour(now) + 1h
p_start   = max(P.start, first_hour)
d_start   = C.start - p_start
d_end     = C.end - P.end
worse  = d_start >= EDGE_SHIFT_THRESHOLD or d_end <= -EDGE_SHIFT_THRESHOLD
better = d_start <= -EDGE_SHIFT_THRESHOLD or d_end >= EDGE_SHIFT_THRESHOLD
if P.start >= first_hour:                       # no baseline hour has passed
    d_min = round(C.wind_min_kn - P.wind_min_kn, 1)
    d_max = round(C.wind_max_kn - P.wind_max_kn, 1)
    worse  |= d_min <= -WIND_CHANGE_THRESHOLD_KN or d_max <= -WIND_CHANGE_THRESHOLD_KN
    better |= d_min >= WIND_CHANGE_THRESHOLD_KN or d_max >= WIND_CHANGE_THRESHOLD_KN
return WORSENED if worse else IMPROVED if better else None
```
Alle tijden in UTC, zodat zomer- en wintertijd geen rol spelen. `gust_max_kn`, `confidence`, `dir_deg` en `dir_class` worden niet gelezen (A3).

### Waarom dit AC-1 t/m AC-5 haalt
- **AC-1:** in de tweede run is de basislijn gelijk aan het window, dus `classify_change` geeft `None`, en de spans en statussen veranderen niet. Ook als de tijd een uur doorloopt bij een lopend window: `p_start` wordt `first_hour` = `C.start`, het eind is gelijk, en wind wordt niet vergeleken.
- **AC-3:** cancel alleen voor een toekomstige entry zonder overlap; verlopen is een aparte stap vóór het koppelen; heractiveren in fase 3.
- **AC-5:** greedy met een volledige, vaste sorteersleutel is deterministisch en één-op-één. De invarianten staan in het Testplan.

### Bericht (`render_alert`)
Titel: `f"{EVENT_TITLE_NL[kind]}: {naam}"`, met `naam = " ".join(spot.name.split())` (geen regeleinden in de titel).

Regels van de body (gescheiden door `"\n"`, geen afsluitende newline). `S` is de snapshot waarover het bericht gaat: `event.current`, of bij `cancelled` `event.previous`.

| Soort | Regels, in deze volgorde |
|---|---|
| `new` | `when_wind(S)`, `direction(S)`, `confidence(S)`, [`kite`], [`tide`] |
| `improved`, `worsened` | `when_wind(S)`, `was(event.previous)`, `direction(S)`, `confidence(S)`, [`kite`], [`tide`] |
| `cancelled` | `cancel(S)`, `expected(S)`, `direction(S)`, `confidence(S)` |

Formaten (exact):
- `window(s)` = `format_window_local(s.start, s.end)`:
  - lokale tijd (`LOCAL_TZ`); `dag(d) = f"{WEEKDAY_ABBR_NL[d.isoweekday() - 1]} {d.day} {MONTH_ABBR_NL[d.month - 1]}"`;
  - valt het laatste moment (`end - 1 µs`) op dezelfde lokale datum als `start`: `f"{dag(ls)} {ls:%H:%M}–{le:%H:%M}"` (bijv. `za 18 okt 14:00–18:00`; een eind om middernacht wordt `00:00`);
  - anders: `f"{dag(ls)} {ls:%H:%M} – {dag(le)} {le:%H:%M}"`.
  - Het streepje is een en-dash (U+2013).
- `kn(x)` = `str(math.floor(x + 0.5))` (half naar boven).
- `wind_range(s)` = `f"{kn(min)}–{kn(max)} kn"`, of `f"{kn(min)} kn"` als beide afgerond gelijk zijn.
- `gusts(s)` = `f"vlagen tot {kn(g)} kn"`, of `"vlagen onbekend"` als `gust_max_kn is None`.
- `when_wind(s)` = `f"{window(s)} · {wind_range(s)}, {gusts(s)}"` (het puntje is U+00B7).
- `was(p)` = `f"Was: {window(p)} · {wind_range(p)}"`.
- `direction(s)` = `f"Wind uit {compass_label(s.dir_deg)} ({s.dir_deg}°) · {DIR_CLASS_LABEL_NL[s.dir_class]}"`.
- `confidence(s)` = `f"Betrouwbaarheid: {CONFIDENCE_LABEL_NL[s.confidence]}"`.
- `kite` (alleen als `kite is not None` en `kind != cancelled`):
  - `m2(x)`: afronden op 0,1; een geheel getal zonder decimalen (`9`), anders met een komma (`10,5`);
  - fit `ideal`: `f"Kite: {m2(size)} m² ({KITE_FIT_LABEL_NL[fit]})"`;
  - anders: `f"Kite: {m2(size)} m² ({KITE_FIT_LABEL_NL[fit]}, ideaal {m2(ideal)} m²)"`.
- `tide` (alleen als `kind != cancelled`, `spot.tide_sensitive != none`, `spot.rws_station` gezet en er minstens één extreem is):
  - extremen: `e.station == spot.rws_station.strip()` en `S.start - TIDE_CONTEXT_MARGIN <= e.at <= S.end + TIDE_CONTEXT_MARGIN` (grenzen inclusief), gesorteerd op `at`, hooguit `MAX_TIDE_EXTREMES_IN_MESSAGE`;
  - per extreem: `f"{TIDE_KIND_LABEL_NL[kind]} {tijd} ({niveau} cm)"`. `tijd` is lokaal `HH:MM`, met de afkorting van de weekdag ervoor (`zo 01:10`) als de lokale datum verschilt van die van `S.start`. `niveau` is `"0"` bij 0, anders `f"{level:+d}"` (`+110`, `-85`);
  - regel: `f"Getij ({TIDE_PREFERENCE_LABEL_NL[spot.tide_sensitive]}): " + ", ".join(...)`.
- `cancel(s)` = `f"Window {window(s)} vervalt"`; `expected(s)` = `f"Verwacht was: {wind_range(s)}, {gusts(s)}"`.

`go_url`: `build_go_url(base_url.strip(), spot.id, S.start, S.end)` als `kind != cancelled` en `base_url` niet `None` en niet leeg na `strip()`; anders `None`. Een lege `APP_BASE_URL` (`.env.example` heeft de sleutel zonder waarde) geeft dus geen link en geen fout. Een niet-lege, ongeldige `base_url` geeft een `ValueError` (configuratiefout, moet opvallen).

De URL staat niet in de body: het kanaal maakt er een knop of tik-actie van (WP-17: `url` in de payload).

### `build_go_url`
- `start` en `end` aware, hele uren, `start < end`; anders `ValueError`.
- `base_url`: na het weghalen van afsluitende `/` niet leeg, begint met `https://` of `http://`, bevat geen witruimte, `?` of `#`; anders `ValueError`.
- `iso(dt) = dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")`.
- Resultaat: `f"{base}/go?spot={q(spot_id)}&start={q(iso(start))}&end={q(iso(end))}"`, met `q` de eigen codering uit A12. Voorbeeld: `https://example.org/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z`.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `ingest/src/shakka/domain/dedup.py` | aanmaken | Constanten, `AlertStatus`, `AlertEventKind`, `_RevalidatingModel` (eigen kopie, zelfde code als in `alerts.py`), `WindowSnapshot` (met `to_json`/`from_json`), `snapshot_window`, `AlertStateEntry` (met `to_row`/`from_row`), `AlertEvent`, `DiffResult`, `classify_change`, `diff_windows`, private helpers (`_floor_hour`, `_overlap`, `_aware_utc`). |
| `ingest/src/shakka/domain/messages.py` | aanmaken | Constanten en labeltabellen, `AlertMessage`, `format_window_local`, `build_go_url`, `render_alert`, private helpers voor de regels en `_quote`. |
| `ingest/tests/dedup_fixtures.py` | aanmaken | Helpers voor de dedup-tests (zie Testplan). |
| `ingest/tests/message_fixtures.py` | aanmaken | Fixture-spots, snapshots, getij en `GOLDEN_CASES` (ook bruikbaar voor WP-17 AC-3). |
| `ingest/tests/test_dedup.py` | aanmaken | Snapshot, JSON en rijen, AC-1 t/m AC-6, validatie. |
| `ingest/tests/test_dedup_invariants.py` | aanmaken | AC-5: invarianten over twee scenarioroosters. |
| `ingest/tests/test_messages.py` | aanmaken | AC-7 t/m AC-9 en de formaatregels. |

Geen wijziging aan bestaande bronbestanden, tests, contractbestanden, migraties of `pyproject.toml`. `docs/STATUS.md` en de contractregel in `docs/WORK_PACKAGES.md` (A1) werkt de orchestrator bij.

## Interfaces en contracten

### `shakka.domain.dedup`
```python
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shakka.domain.alerts import Window
from shakka.domain.consensus import Confidence, circular_mean_deg
from shakka.domain.direction import RIDABLE_DIR_CLASSES, DirClass

EDGE_SHIFT_THRESHOLD: Final = timedelta(hours=2)   # proposal (A3)
WIND_CHANGE_THRESHOLD_KN: Final = 4.0              # proposal (A3)
SNAPSHOT_KEYS: Final[tuple[str, ...]] = (
    "start", "end", "wind_min_kn", "wind_max_kn", "gust_max_kn",
    "dir_deg", "dir_class", "confidence")
ALERT_STATE_COLUMNS: Final[tuple[str, ...]] = (
    "id", "spot_id", "window_start", "window_end", "status",
    "snapshot", "last_event", "last_notified_at")
AlertStatus = Literal["active", "cancelled", "expired"]

class AlertEventKind(StrEnum):
    NEW = "new"
    IMPROVED = "improved"
    WORSENED = "worsened"
    CANCELLED = "cancelled"

class WindowSnapshot(_RevalidatingModel):
    start: datetime                 # aware -> UTC, whole hour
    end: datetime                   # aware -> UTC, whole hour, > start
    wind_min_kn: float              # finite, >= 0
    wind_max_kn: float              # finite, >= wind_min_kn
    gust_max_kn: float | None       # finite, >= 0; None = unknown (A1), never 0 for unknown
    dir_deg: int                    # Field(strict=True, ge=0, le=359); informative only
    dir_class: DirClass             # must be in RIDABLE_DIR_CLASSES (hard rule)
    confidence: Confidence

    def to_json(self) -> dict[str, Any]:
        """JSON-ready dict with exactly SNAPSHOT_KEYS: start/end as 'YYYY-MM-DDTHH:MM:SSZ',
        floats, None, int and enum values (str)."""

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Self:
        """Inverse of to_json. Missing keys -> ValueError naming them; extra keys are ignored;
        invalid values -> ValidationError (a ValueError)."""

def snapshot_window(window: Window) -> WindowSnapshot:
    """Summary of a go window (see blueprint). ValueError if an hour lacks wind_kn, dir_deg
    or confidence."""

class AlertStateEntry(_RevalidatingModel):
    id: str | None                  # None = not stored yet; else min_length 1
    spot_id: str                    # min_length 1
    window_start: datetime          # aware -> UTC
    window_end: datetime            # aware -> UTC, > window_start
    status: AlertStatus
    snapshot: WindowSnapshot        # baseline: what the user was last told (A4)
    last_event: AlertEventKind | None
    last_notified_at: datetime | None   # aware -> UTC; never changed by diff_windows (A9)

    def to_row(self) -> dict[str, Any]:
        """alert_state columns without user_id (WP-10 adds it): ALERT_STATE_COLUMNS, but
        'id' only when not None. Datetimes stay aware datetimes (shakka.db encodes them),
        snapshot is to_json(), status/last_event are str or None."""

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> Self:
        """From an alert_state row (PostgREST JSON): all ALERT_STATE_COLUMNS required
        (missing -> ValueError naming them); user_id, created_at, updated_at and other keys
        are ignored. Timestamps may be ISO strings; snapshot is a mapping (from_json)."""

class AlertEvent(_RevalidatingModel):
    kind: AlertEventKind
    spot_id: str                    # min_length 1
    current: WindowSnapshot | None  # new/improved/worsened: set; cancelled: None
    previous: WindowSnapshot | None # improved/worsened/cancelled: set (baseline); new: None
    state_index: int                # Field(strict=True, ge=0); index in DiffResult.new_state

class DiffResult(_RevalidatingModel):
    events: list[AlertEvent]        # sorted by state_index, at most one per state_index
    new_state: list[AlertStateEntry]  # previous entries in input order, then new ones by start

def classify_change(previous: WindowSnapshot, current: WindowSnapshot, *,
                    now: datetime) -> AlertEventKind | None:
    """IMPROVED, WORSENED or None by the thresholds in the blueprint (A3). ValueError on a
    naive now."""

def diff_windows(previous: Sequence[AlertStateEntry], current: Sequence[Window], *,
                 now: datetime) -> DiffResult:
    """Match state entries of one user and one spot to the current windows and decide the
    events (see blueprint, steps 0-12). Inputs are not modified. ValueError on a naive now,
    mixed spot_ids, duplicate ids, overlapping windows or overlapping live active entries."""
```
- Alle modellen: `frozen=True`, `extra="forbid"`; `model_copy` valideert opnieuw (`_RevalidatingModel`, dezelfde 10 regels als in `alerts.py`: `dict(self)`, `update`, `model_validate`). `diff_windows` maakt elke gewijzigde entry via `model_copy(update=...)`.
- Validatie van `AlertEvent` (`model_validator(mode="after")`): `new` vereist `current` gezet en `previous is None`; `improved`/`worsened` beide gezet; `cancelled` vereist `current is None` en `previous` gezet.
- `WindowSnapshot`: `allow_inf_nan=False` op de floats; `start`/`end` naïef of geen heel uur → `ValidationError`.
- `to_json` voorbeeld:
  ```json
  {"start": "2026-07-18T12:00:00Z", "end": "2026-07-18T16:00:00Z", "wind_min_kn": 16.0,
   "wind_max_kn": 22.4, "gust_max_kn": null, "dir_deg": 225, "dir_class": "side_onshore",
   "confidence": "high"}
  ```
  Het formaat van `start`/`end` is gelijk aan `shakka.db.iso_utc` voor hele uren. `from_json` parseert ook `+00:00` (pydantic).
- Geen enkele publieke functie heeft een parameter met `offshore`, `allow`, `force` of `unsafe` in de naam (getest).

### `shakka.domain.messages`
```python
import math
import string
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from shakka.domain.consensus import CONFIDENCE_LABEL_NL
from shakka.domain.dedup import AlertEvent, AlertEventKind, WindowSnapshot
from shakka.domain.defaults import LOCAL_TZ
from shakka.domain.direction import DIR_CLASS_LABEL_NL, compass_label
from shakka.domain.kite import KiteAdvice, KiteFit
from shakka.domain.spot import SpotProfile, TideSensitivity
from shakka.domain.tide import TideExtreme

TIDE_CONTEXT_MARGIN: Final = timedelta(hours=3)     # contract: within the window or 3 h around
MAX_TIDE_EXTREMES_IN_MESSAGE: Final = 6
WEEKDAY_ABBR_NL: Final[tuple[str, ...]] = ("ma", "di", "wo", "do", "vr", "za", "zo")
MONTH_ABBR_NL: Final[tuple[str, ...]] = (
    "jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec")
EVENT_TITLE_NL: Final[dict[AlertEventKind, str]] = {
    AlertEventKind.NEW: "Go",
    AlertEventKind.IMPROVED: "Beter",
    AlertEventKind.WORSENED: "Slechter",
    AlertEventKind.CANCELLED: "Gaat niet door",
}
KITE_FIT_LABEL_NL: Final[dict[KiteFit, str]] = {
    KiteFit.IDEAL: "past goed",
    KiteFit.UNDERPOWERED: "aan de kleine kant",
    KiteFit.OVERPOWERED: "aan de grote kant",
}
TIDE_PREFERENCE_LABEL_NL: Final[dict[TideSensitivity, str]] = {
    TideSensitivity.PREFER_LOW: "voorkeur laagwater",
    TideSensitivity.PREFER_HIGH: "voorkeur hoogwater",
    TideSensitivity.AVOID_LOW: "liever geen laagwater",
}
TIDE_KIND_LABEL_NL: Final[dict[str, str]] = {"high": "hoog", "low": "laag"}
_URL_SAFE: Final[frozenset[str]] = frozenset(string.ascii_letters + string.digits + "-._~")

class AlertMessage(BaseModel):      # frozen, extra="forbid"
    spot_id: str                    # min_length 1
    kind: AlertEventKind
    title: str                      # min_length 1, no newline
    body: str                       # min_length 1, lines separated by "\n"
    go_url: str | None

def format_window_local(start: datetime, end: datetime) -> str:
    """'za 18 okt 14:00–18:00' in Europe/Amsterdam (see blueprint). ValueError if naive or
    start >= end."""

def build_go_url(base_url: str, spot_id: str, start: datetime, end: datetime) -> str:
    """{base_url}/go?spot={spot_id}&start={start}&end={end}; start/end ISO 8601 UTC with Z,
    percent-encoded like urllib.parse.quote(s, safe=""). Trailing '/' of base_url is dropped.
    ValueError on an invalid base_url, naive or non-whole-hour times, or start >= end."""

def render_alert(event: AlertEvent, spot: SpotProfile, *, kite: KiteAdvice | None,
                 tides: Sequence[TideExtreme], base_url: str | None) -> AlertMessage:
    """Plain-text Dutch message (see blueprint). ValueError if event.spot_id != spot.id."""
```

### Consistentie met afhankelijke WP's
- WP-07: `Window` (invarianten: go, rijdbaar, aaneengesloten, halfopen) wordt ongewijzigd gebruikt. Het verschuiven van het begin (A9 van WP-07) en het wegvallen van een begonnen window zijn opgevangen in A5. Afkappen op `days_ahead` gebeurt op lokale middernacht; daar zijn geen go-uren (`dark`), dus dat knipt in Nederland nooit een window door.
- WP-06: `KiteAdvice`, `KiteFit`; de labels voor `KiteFit` staan hier (WP-06 "Contract richting WP-08").
- WP-05: `Confidence`, `CONFIDENCE_LABEL_NL`, `DIR_CLASS_LABEL_NL`, `compass_label`, `circular_mean_deg`, `RIDABLE_DIR_CLASSES`; de klasse komt nooit uit `dir_deg` (A2).
- WP-04: `TideExtreme`; het stationfilter met `strip()` is gelijk aan de evaluatie.
- WP-01: `ALERT_STATE_COLUMNS` = de kolommen van `alert_state` zonder `user_id`, `created_at` en `updated_at`. Statussen en events zijn gelijk aan de CHECKs `alert_state_status_enum` en `alert_state_last_event_enum` (getest tegen de migratie); `window_end > window_start` (CHECK `alert_state_window_order`) is ook een modelregel; `snapshot` is een JSON-object (CHECK `alert_state_snapshot_object`).

### Gevolgen voor latere WP's
- **WP-10:**
  - Laad per gebruiker en favoriete spot **alle** `alert_state`-rijen met `status = active`, plus de rijen met `status = cancelled` en `window_end > now`. Ontbreekt een actieve rij, dan volgt een dubbele `new`. `expired`-rijen zijn niet nodig. Gebruik `AlertStateEntry.from_row`.
  - `diff_windows(previous, windows, now=now)` met dezelfde `now` als `find_windows`. Zet `from_row` en `diff_windows` in dezelfde `try ... except ValueError` per favoriet als de regelbepaling (WP-07, "Gevolgen"); een fout slaat die favoriet over.
  - Per event het bijbehorende `Window`: het window met `w.start == event.current.start and w.end == event.current.end` (uniek). Kite-advies: `recommend_for_window(rider, [h.wind_kn for h in w.hours if h.wind_kn is not None])`, en `kite=None` bij `cancelled` (wordt toch genegeerd, A10).
  - Getij: geef de extremen van het station van de spot mee die minstens `[window.start - 3 h, window.end + 3 h]` dekken; het bereik dat WP-10 voor de evaluatie laadt, is ruim genoeg.
  - `base_url = settings.app_base_url` (mag `None` of leeg zijn).
  - Opslaan: voor `i < len(previous)` alleen als `new_state[i] != previous[i]`: update op `id` met `to_row()` (zonder `id`). Voor `i >= len(previous)`: insert met `user_id` erbij; de teruggegeven `id` is de `state_id` van het bijbehorende event. "Renderen" en "opslaan" blijven aparte stappen (voor WP-17).
  - `last_notified_at` laat `diff_windows` ongemoeid (A9); in M1 blijft het leeg.
  - `snapshot` in de database is de basislijn (laatst gemelde stand), niet de nieuwste verwachting. Toon hem in de CLI dus als "laatst gemeld".
  - De opruimregel `window_end < now - 48h` (WP-10) raakt de logica niet: zulke rijen zijn `expired` of `cancelled` en spelen niet meer mee.
- **WP-17:**
  - De body is opgebouwd in volgorde van belang (A11); `to_push_text` mag hele regels vanaf het begin nemen. De titel is in de golden-tests hoogstens 26 tekens.
  - `ingest/tests/message_fixtures.py::GOLDEN_CASES` bevat de golden-berichten voor WP-17 AC-3.
  - Heractiveren hergebruikt de `id` (A8), dus de push-`tag` vervangt de eerdere annulering. Een entry die bij samensmelten `expired` wordt, krijgt geen melding; zijn oude melding blijft op de telefoon staan.
  - Overgang M1 → push (open punt WP-17): actieve rijen met `last_notified_at is None` zijn de rijen die in M1 een event kregen zonder aflevering.
- **WP-14 en WP-20:** het formaat van `/go` ligt vast. Fixture-string voor WP-14 AC-5: `https://example.org/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z` (`start` en `end` zijn hele uren in UTC, halfopen).

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `previous` en `current` leeg | `DiffResult([], [])`. |
| E2 | Zelfde windows, zelfde `now`, tweede keer | 0 events, `new_state` gelijk aan de invoer (AC-1). |
| E3 | Lopend window, `now` een uur later, zelfde evaluaties | 0 events: begin geclipt op `first_hour`, wind niet vergeleken (A5). `window_start` blijft het oorspronkelijke begin. |
| E4 | Begonnen window zakt onder `min_go_hours` en verdwijnt | Geen event; entry blijft `active` en ongewijzigd; `expired` zodra `window_end <= now` (A5). |
| E5 | Toekomstig window verdwijnt volledig | `cancelled` (event), snapshot blijft de basislijn. |
| E6 | `window_end <= now` | `expired`, geen event; ook precies op de grens (`==`). |
| E7 | `now` precies gelijk aan `window_start` | Begonnen (`<=`), dus nooit `cancelled`. |
| E8 | Geannuleerd window komt terug (overlap) | Zelfde entry weer `active`, event `new` (A8). |
| E9 | Geannuleerde en actieve entry overlappen hetzelfde nieuwe window | De actieve wint (fase 2 vóór fase 3); de geannuleerde blijft ongewijzigd. |
| E10 | Window schuift zonder overlap (10–12 wordt 14–16) | `cancelled` voor de oude entry plus `new` voor het nieuwe window. |
| E11 | Splitsen, gelijke overlap (10–18 wordt 10–13 en 15–18) | Koppeling aan 10–13 (vroegste): `worsened` (eind −5 h); 15–18 krijgt `new`. |
| E12 | Splitsen, ongelijke overlap (10–19 wordt 10–12 en 13–19) | Koppeling aan 13–19 (overlap 6 h): `worsened` (begin +3 h); 10–12 krijgt `new`. |
| E13 | Samensmelten (10–13 en 15–18 worden 10–18) | 10–13 gekoppeld (gelijke overlap, vroegste entry): `improved` (eind +5 h); 15–18 wordt stil `expired`. |
| E14 | Begonnen window splitst (span 10–18, `now` 11:30, windows 13–15 en 16–18) | Koppeling aan 13–15 (vroegste): `worsened` (begin +1 h is geen event, eind −3 h wel); 16–18 krijgt `new`. |
| E15 | Begin +2 h en wind_min −4 kn tegelijk / begin −2 h en wind −4 kn | `worsened` / `worsened` (voorrang, A3). |
| E16 | Precies op de drempel (2 h, 4,0 kn) | Event (`>=`). 1 h of 3,9 kn: geen event. |
| E17 | Sluipende verschuiving: elke run 1 h later | Geen event na run 2, `worsened` na run 3 (2 h ten opzichte van de basislijn). |
| E18 | Alleen vlagen, betrouwbaarheid of richting verandert | Geen event (A3). |
| E19 | Vlaag `None` in de basislijn, nu 30 kn | Geen event; nooit als 0 vergeleken. |
| E20 | Uur zonder `wind_kn`, `dir_deg` of `confidence` in een window | `snapshot_window` geeft `ValueError` (kan uit `evaluate_hour` niet voorkomen). |
| E21 | Richtingen 350 en 10 in één window | `dir_deg = 0`. Tegengestelde richtingen (gemiddelde onbepaald): `dir_deg` van het eerste uur. |
| E22 | Klassen gelijk verdeeld (2× onshore, 2× sideshore) | `sideshore` (A2). |
| E23 | Snapshot met `dir_class` offshore of side-offshore (bijv. uit een kapotte rij) | `ValidationError`, ook via `from_json` en `model_copy`. |
| E24 | Twee actieve entries met overlappende spans en `window_end > now` | `ValueError`. |
| E25 | `current` overlapt zichzelf, verschillende spots, dubbele `id`, naïeve `now` | `ValueError`. |
| E26 | Invoer ongesorteerd | Zelfde uitkomst; `new_state` volgt de volgorde van `previous`. |
| E27 | Window over lokale middernacht | `za 18 jul 22:00 – zo 19 jul 01:00`; eind precies om middernacht: `za 18 jul 22:00–00:00`. |
| E28 | Window op de dag van de wintertijd (2026-10-25 10:00Z–12:00Z) | `zo 25 okt 11:00–13:00` (CET). |
| E29 | `base_url` `None`, `""` of `"  "` | `go_url = None`, geen fout. |
| E30 | `base_url` met afsluitende `/` | Wordt weggehaald; zelfde URL. |
| E31 | `base_url` zonder schema, met `?`, `#` of spatie | `ValueError`. |
| E32 | Spot niet getijgevoelig, wel station en extremen | Geen getij-regel. |
| E33 | Getijgevoelig zonder `rws_station`, of geen extremen binnen de marge | Geen getij-regel. |
| E34 | Extreem precies op `start - 3 h` of `end + 3 h` | Wel in de regel (inclusief); één minuut erbuiten niet. |
| E35 | Extremen van een ander station | Genegeerd. |
| E36 | Extreem op een andere lokale datum dan het begin | Tijd met weekdag ervoor (`zo 01:10`). |
| E37 | Kite bij `cancelled` meegegeven | Genegeerd (A10). |
| E38 | Spotnaam met dubbele spaties of een regeleinde | Titel met enkele spaties. |
| E39 | `event.spot_id != spot.id` | `ValueError`. |
| E40 | Niveau 0 cm | `0 cm` (zonder plus). |

## Testplan
Tests eerst. Geen netwerk, geen klok: `now` is altijd een expliciete aware datetime. Ruff `DTZ` staat aan, dus elke `datetime(...)` in tests heeft `tzinfo=UTC`. Kalender (gecontroleerd in WP-07): 2026-07-15 woensdag, 2026-07-18 zaterdag (CEST, UTC+2), 2026-11-04 woensdag dus 2026-11-07 zaterdag (CET, UTC+1), 2026-10-25 zondag (wintertijd vanaf 01:00Z).

### Fixtures
`ingest/tests/dedup_fixtures.py`:
```python
SPOT_ID = "test-strand"
H = timedelta(hours=1)
NOW = utc(2026, 7, 15, 6)        # from alert_fixtures

def go_hour(at, *, wind=20.0, gust=None, dir_deg=270, dir_class=DirClass.ONSHORE,
            confidence=Confidence.HIGH, spot_id=SPOT_ID) -> HourEvaluation:
    """Valid go hour via the normal constructor (verdict go, reasons ())."""

def make_window(start, n, *, winds=None, gusts=None, dirs=None, classes=None,
                confidences=None, spot_id=SPOT_ID) -> Window:
    """Window of n go hours from start; per-hour lists override the go_hour defaults."""

def entry(start, end, *, status="active", snapshot=None, id=None, last_event=AlertEventKind.NEW,
          spot_id=SPOT_ID, last_notified_at=None) -> AlertStateEntry:
    """snapshot defaults to snapshot_window(make_window(start, hours(end - start)))."""

def persist(state: list[AlertStateEntry], prefix: str = "id") -> list[AlertStateEntry]:
    """Give entries with id None the id f'{prefix}-{index}' (simulates the database insert)."""

def windows_from_pattern(day_start: datetime, pattern: str, *, now: datetime,
                         min_go_hours: int = 1) -> list[Window]:
    """pattern like 'GG.GGG' (G = go hour, . = marginal) from day_start; uses
    alert_fixtures.hour/go and find_windows(..., rule(min_go_hours=...), now=now)."""
```

`ingest/tests/message_fixtures.py` (exacte waarden, gebruikt door `test_messages.py` en later WP-17):
- `PLAIN_SPOT = make_spot()` (normaal 270, niet getijgevoelig).
- `LOW_TIDE_SPOT = make_spot(tide_sensitive="prefer_low", rws_station="teststation")`, `AVOID_LOW_SPOT = make_spot(tide_sensitive="avoid_low", rws_station="teststation")`.
- `S_SUMMER = WindowSnapshot(start=2026-07-18 12:00Z, end=16:00Z, wind_min_kn=16.0, wind_max_kn=22.4, gust_max_kn=27.5, dir_deg=225, dir_class=side_onshore, confidence=high)`.
- Onderstaande snapshots in de veldvolgorde `start, end, wind_min_kn, wind_max_kn, gust_max_kn, dir_deg, dir_class, confidence` (in de code met keywords):
  - `P_SUMMER`: 2026-07-18 14:00Z, 16:00Z, 14.0, 18.0, 22.0, 230, side_onshore, medium;
  - `S_WINTER`: 2026-11-07 11:00Z, 14:00Z, 18.0, 24.0, None, 270, onshore, medium;
  - `P_WINTER`: 2026-11-07 11:00Z, 16:00Z, 18.0, 25.0, 30.0, 265, onshore, medium.
- `TIDES_SUMMER` (station `teststation`, tenzij anders): 04:20Z high 100; 10:30Z low -85; 13:00Z high 120 (station `anderstation`); 16:45Z high 110; 22:55Z low -80 (allemaal 2026-07-18).
- `TIDES_WINTER` (`teststation`, 2026-11-07): 09:10Z high 95; 15:40Z low -70.
- `KITE_IDEAL = KiteAdvice(size_m2=9.0, fit="ideal", ideal_size_m2=8.8)`, `KITE_OVER = KiteAdvice(size_m2=12.0, fit="overpowered", ideal_size_m2=9.4)`.
- `BASE = "https://example.org"`; `URL_SUMMER = "https://example.org/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z"`; `URL_WINTER = "https://example.org/go?spot=test-strand&start=2026-11-07T11%3A00%3A00Z&end=2026-11-07T14%3A00%3A00Z"`.
- `GOLDEN_CASES: list[GoldenCase]` met `GoldenCase(name, event, spot, kite, tides, base_url, title, body, go_url)` (NamedTuple). Events: `AlertEvent(kind=..., spot_id="test-strand", current=..., previous=..., state_index=0)`.

| `name` | event (current / previous) | spot, kite, tides, base_url | `title` | `body` | `go_url` |
|---|---|---|---|---|---|
| `new_summer_plain` | new: `S_SUMMER` / – | `PLAIN_SPOT`, None, `[]`, `BASE` | `Go: Teststrand` | `za 18 jul 14:00–18:00 · 16–22 kn, vlagen tot 28 kn`⏎`Wind uit ZW (225°) · Schuin aanlandig`⏎`Betrouwbaarheid: Hoog` | `URL_SUMMER` |
| `new_summer_kite_tide` | new: `S_SUMMER` / – | `LOW_TIDE_SPOT`, `KITE_IDEAL`, `TIDES_SUMMER`, None | `Go: Teststrand` | de 3 regels van `new_summer_plain`⏎`Kite: 9 m² (past goed)`⏎`Getij (voorkeur laagwater): laag 12:30 (-85 cm), hoog 18:45 (+110 cm)` | None |
| `improved_summer` | improved: `S_SUMMER` / `P_SUMMER` | `PLAIN_SPOT`, `KITE_OVER`, `[]`, `"https://example.org/"` | `Beter: Teststrand` | `za 18 jul 14:00–18:00 · 16–22 kn, vlagen tot 28 kn`⏎`Was: za 18 jul 16:00–18:00 · 14–18 kn`⏎`Wind uit ZW (225°) · Schuin aanlandig`⏎`Betrouwbaarheid: Hoog`⏎`Kite: 12 m² (aan de grote kant, ideaal 9,4 m²)` | `URL_SUMMER` |
| `new_winter_tide` | new: `S_WINTER` / – | `AVOID_LOW_SPOT`, None, `TIDES_WINTER`, None | `Go: Teststrand` | `za 7 nov 12:00–15:00 · 18–24 kn, vlagen onbekend`⏎`Wind uit W (270°) · Aanlandig`⏎`Betrouwbaarheid: Gemiddeld`⏎`Getij (liever geen laagwater): hoog 10:10 (+95 cm), laag 16:40 (-70 cm)` | None |
| `worsened_winter` | worsened: `S_WINTER` / `P_WINTER` | `PLAIN_SPOT`, None, `[]`, `BASE` | `Slechter: Teststrand` | `za 7 nov 12:00–15:00 · 18–24 kn, vlagen onbekend`⏎`Was: za 7 nov 12:00–17:00 · 18–25 kn`⏎`Wind uit W (270°) · Aanlandig`⏎`Betrouwbaarheid: Gemiddeld` | `URL_WINTER` |
| `cancelled_winter` | cancelled: – / `S_WINTER` | `AVOID_LOW_SPOT`, `KITE_IDEAL`, `TIDES_WINTER`, `BASE` | `Gaat niet door: Teststrand` | `Window za 7 nov 12:00–15:00 vervalt`⏎`Verwacht was: 18–24 kn, vlagen onbekend`⏎`Wind uit W (270°) · Aanlandig`⏎`Betrouwbaarheid: Gemiddeld` | None |

⏎ is `"\n"`. Controle van de getallen: 22,4 → 22; 27,5 → 28 (half naar boven); `compass_label(225)` = `ZW`, `compass_label(270)` = `W`; 12:00Z = 14:00 CEST; 11:00Z = 12:00 CET; getij 10:30Z = 12:30, 16:45Z = 18:45 (binnen 09:00Z–19:00Z), 04:20Z en 22:55Z vallen erbuiten; winter 09:10Z = 10:10 en 15:40Z = 16:40 (binnen 08:00Z–17:00Z).

### `tests/test_dedup.py`
**Snapshot en serialisatie**
- `test_snapshot_window_basic`: window van 4 uur met wind `[14.0, 18.5, 22.0, 16.0]`, vlagen `[None, 25.0, None, 30.5]`, richting `[260, 270, 280, 270]`, klassen `[onshore]*4`, betrouwbaarheid `[high, medium, high, high]` → `wind_min 14.0`, `wind_max 22.0`, `gust_max 30.5`, `dir_deg 270`, `onshore`, `medium`, `start`/`end` gelijk aan het window.
- `test_snapshot_gust_unknown`: alle vlagen `None` → `gust_max_kn is None` (niet 0).
- `test_snapshot_dir_wrap`: richtingen 350 en 10 → `dir_deg 0`; richtingen 0 en 180 (onbepaald gemiddelde) → `dir_deg` van het eerste uur.
- `test_snapshot_dir_class_mode_and_tie`: `[onshore, onshore, side_onshore]` → `onshore`; `[onshore, onshore, sideshore, sideshore]` → `sideshore`; `[side_onshore, onshore]` → `side_onshore`.
- `test_snapshot_window_invalid_hours`: een go-uur met `wind_kn=None`, met `dir_deg=None` of met `confidence=None` (via de normale `HourEvaluation`-constructor, dat is toegestaan) → `ValueError`.
- `test_snapshot_rejects_offshore` (E23): `WindowSnapshot(..., dir_class=offshore)` en `side_offshore` → `ValidationError`; ook via `from_json` en `model_copy(update=...)`.
- `test_snapshot_validation`: naïeve `start`, niet-heel uur, `end <= start`, `wind_min > wind_max`, negatieve of NaN wind, `dir_deg` 360 of `225.0` (strikt int) → `ValidationError`.
- **AC-6** `test_snapshot_json_roundtrip`: voor `S_SUMMER`, `S_WINTER` (vlaag `None`) en `P_WINTER`: `WindowSnapshot.from_json(s.to_json()) == s`, `json.dumps(s.to_json())` slaagt, en `from_json(json.loads(json.dumps(s.to_json()))) == s`. `to_json()` heeft exact de sleutels `SNAPSHOT_KEYS` en `start == "2026-07-18T12:00:00Z"`. `from_json` met `"+00:00"`-tijden geeft dezelfde snapshot; een ontbrekende sleutel geeft `ValueError` met de naam; een extra sleutel wordt genegeerd.
- `test_entry_row_roundtrip`: `AlertStateEntry` met `id="a1"` → `to_row()` heeft exact `ALERT_STATE_COLUMNS`; zonder `id` ontbreekt de sleutel `id`. Een PostgREST-achtige rij (tijden als `"2026-07-18T12:00:00+00:00"`, `snapshot` als dict, plus `user_id`, `created_at`, `updated_at`) geeft via `from_row` de verwachte entry. Een rij zonder `status` → `ValueError` met `status` in de melding.
- `test_alert_state_enums_match_migration`: met `alert_fixtures.migration_sql()`: de strings in de CHECK `alert_state_status_enum` zijn gelijk aan de `Literal`-waarden van `AlertStatus` (`typing.get_args`), en die in `alert_state_last_event_enum` aan `{k.value for k in AlertEventKind}`. (Neem de tekst vanaf de constraintnaam, pak de eerste match van `in \(([^)]*)\)` en lees daarin de waarden met `'([a-z_]+)'`. Zo telt `'object'` uit de volgende CHECK niet mee.)
- `test_event_invariants`: `new` met `previous` gezet, `cancelled` met `current` gezet, `improved` zonder `previous`, negatieve `state_index` → `ValidationError`.

**AC-1**
- `test_idempotent`, geparametriseerd over vier scenario's `(prev, cur, now)`:
  1. `([], [make_window(utc(2026,7,15,10), 4)], NOW)`;
  2. `([], [make_window(utc(2026,7,15,10), 3), make_window(utc(2026,7,15,14), 2)], NOW)`;
  3. begonnen: `([entry(10:00Z, 16:00Z, id="a1")], [make_window(utc(2026,7,15,12), 4)], utc(2026,7,15,11) + 30 min)`;
  4. geannuleerd plus nieuw: `([entry(09:00Z, 11:00Z, status="cancelled", last_event=AlertEventKind.CANCELLED, id="c1")], [make_window(utc(2026,7,15,13), 3)], NOW)`.

  Telkens `r1 = diff_windows(prev, cur, now=now)` en `r2 = diff_windows(persist(r1.new_state), cur, now=now)` → `r2.events == []` en `r2.new_state == persist(r1.new_state)`. (Alle tijden op 2026-07-15.)
- `test_running_window_hourly_sequence` (E3, E4): evaluaties met go-uren 2026-07-15 10:00Z t/m 13:00Z (`alert_fixtures.go_run`), regel `min_go_hours=2`. Runs met `now` = 08:17, 09:17, 10:17, 11:17, 12:17, 13:17 en 14:17 (UTC), elke keer `find_windows` met die `now` en `diff_windows` op de opgeslagen state van de vorige run. Verwacht: precies 1 event in totaal (`new` in de eerste run); na de run van 12:17 (window [13, 14) is te kort en bestaat niet meer) is de entry `active` met `window_start` 10:00Z; na 14:17 is de status `expired`. Nooit `cancelled`.

**AC-2**
- `test_new_window`: `diff_windows([], [make_window(utc(2026,7,15,10), 4)], now=NOW)` → 1 event `new` met `state_index 0`, `current == snapshot_window(w)`, `previous is None`; 1 entry met `id None`, `status "active"`, `window_start/end` gelijk aan het window, `last_event new`, `last_notified_at None`.

**AC-3**
- `test_cancel_before_start` (E5): entry 10–14, geen windows, `now = NOW` → 1 event `cancelled` (`current None`, `previous` = de snapshot van de entry); entry `status cancelled`, `last_event cancelled`, snapshot ongewijzigd.
- `test_expired_no_event` (E6): entry 02–05 met `now = NOW` (06:00) → 0 events, status `expired`. Ook `window_end == now` → `expired`.
- `test_cancelled_comes_back` (E8): eerst cancel zoals hierboven, dan `persist`, dan window 11–15 → 1 event `new` met `state_index 0`; entry 0 (zelfde `id`) is weer `active`, `last_event new`, snapshot = het nieuwe window; `len(new_state) == 1`.
- `test_begun_not_cancelled` (E4, E7): entry 10–14 met `now = utc(2026,7,15,10)` (exact) en geen windows → 0 events, entry ongewijzigd `active`. Met `now` 14:00 → `expired`.
- `test_active_beats_cancelled` (E9): geannuleerde entry 09–12 en actieve entry 13–16 (allebei `persist`), window 11–16 → koppeling aan de actieve entry (event `improved`, begin −2 h); de geannuleerde blijft ongewijzigd.
- `test_shift_without_overlap` (E10): entry 10–12, window 14–16 → events `cancelled` (index 0) en `new` (index 1).

**AC-4** (met `classify_change` en via `diff_windows`; basislijn `B = snapshot` van een window 2026-07-15 10:00Z–16:00Z met wind 16–22, `now = NOW`)
- `test_small_changes_no_event`, geparametriseerd: begin ±1 h, eind ±1 h, het hele window 1 h later of eerder, begin +1 h en eind −1 h samen, wind min/max beide +2 kn of −2 kn, wind_min −3,9 kn → `None`, en via `diff_windows` 0 events (entry gekoppeld, snapshot ongewijzigd = basislijn).
- `test_threshold_events`, geparametriseerd (minstens één per drempel en per richting): begin −2 h → `improved`; begin +2 h → `worsened`; eind +2 h → `improved`; eind −2 h → `worsened`; wind_min +4 → `improved`; wind_min −4 → `worsened`; wind_max +4 → `improved`; wind_max −4 → `worsened`; precies 4,0 met floatruis (basislijn 14,2, nu 18,2) → `improved` (E16). Via `diff_windows`: event met `previous == B`, `current` = nieuw; entry krijgt `snapshot = current` en `last_event = kind`.
- `test_worsened_wins` (E15): begin −2 h en wind_min −4 → `worsened`; eind +3 h en wind_max −5 → `worsened`.
- `test_ignored_fields` (E18, E19): alleen `gust_max_kn` (None → 30; 20 → 35), `confidence` (high → medium) of `dir_class`/`dir_deg` anders → `None`.
- `test_wind_ignored_once_begun`: basislijn 10–16 met wind 16–22, `now = utc(2026,7,15,11) + 30 min`, huidig window 12–16 met wind 22–26 → `None` (`P.start < first_hour`). Met `now = NOW` en dezelfde wind → `improved`.
- `test_drift_accumulates` (E17): drie runs met het window telkens 1 h later (10–16, 11–17, 12–18), `now = NOW`, state doorgegeven via `persist` → events: run 1 `new`, run 2 geen, run 3 `worsened` met `previous.start` 10:00Z.

**AC-5** (determinisme en splitsen/samensmelten; `now = NOW`)
- `test_split_equal` (E11), `test_split_unequal` (E12), `test_merge` (E13), `test_split_begun` (E14, `now = utc(2026,7,15,11) + 30 min`, entry 10–18 met basislijn 10–18): exact de uitkomst uit de tabel Edge cases (soorten, `state_index`, statussen, spans).
- `test_deterministic_order`: dezelfde invoer twee keer → gelijke `DiffResult`; `current` omgekeerd → gelijk resultaat; `previous` omgekeerd (met unieke `id`'s) → per `id` dezelfde resulterende entry en dezelfde events (vergeleken via `id` in plaats van index).
- `test_invalid_input` (E24, E25): naïeve `now`; entry en window van verschillende spots; twee entries met dezelfde `id`; overlappende windows (handmatig gemaakt); twee actieve entries 10–14 en 12–16 → `ValueError`. Lege invoer → `DiffResult([], [])`. De invoerlijsten zijn na afloop ongewijzigd.
- `test_no_bypass_parameters`: `inspect.signature` van `diff_windows`, `classify_change`, `snapshot_window`, `render_alert` en `build_go_url` bevat geen parameter met `offshore`, `allow`, `force` of `unsafe` in de naam; `now` is keyword-only.

### `tests/test_dedup_invariants.py` (AC-5)
Twee deterministische roosters. Per stap worden deze invarianten gecontroleerd op `r = diff_windows(prev, cur, now=now)`:
- **I1:** elk huidig window ligt binnen de span van precies één entry in `r.new_state` met status `active`;
- **I2:** de spans van de actieve entries met `window_end > now` overlappen elkaar niet;
- **I3:** elke `state_index` komt hooguit één keer voor in `r.events`. Voor `new`, `improved` en `worsened` is `r.new_state[idx]` `active` met `last_event == kind`; voor `cancelled` is de status `cancelled`;
- **I4:** het aantal `new`-events is gelijk aan het aantal huidige windows dat niet gekoppeld is aan een entry die vóór de diff `active` was. Twee `new`-events delen geen uur;
- **I5:** geen `cancelled`-event voor een entry met `window_start <= now` in `prev`;
- **I6:** `len(r.new_state) >= len(prev)` en `r.new_state[i].id == prev[i].id` voor `i < len(prev)`;
- **I7:** `diff_windows(persist(r.new_state), cur, now=now)` geeft 0 events en dezelfde state (idempotent).

Roosters (patronen met G = go, . = marginal, vanaf 2026-07-15 10:00Z, `min_go_hours=1`, via `windows_from_pattern`):
- **Rooster A (niet begonnen):** 6 uursloten, alle 64 × 64 paren `(p1, p2)`. Stap 1: `diff_windows([], W(p1), now=NOW)`; daarna `persist`; stap 2 met `W(p2)`, ook `now = NOW`. Invarianten na beide stappen; daarnaast per paar `p1 == p2` → 0 events in stap 2.
- **Rooster B (begonnen):** 5 uursloten, alle 32 × 32 paren. Stap 1 met `now0 = utc(2026,7,15,9) + 30 min`; stap 2 met `now1 = utc(2026,7,15,11) + 30 min` en `W(p2)` berekend met `now1` (uren vóór 12:00Z tellen niet). Invarianten na beide stappen, plus I5.

De roosters gebruiken alleen tijdsverschillen (wind constant 20), zodat elk event uit A3-tijdregels of uit splitsen/samensmelten/annuleren komt. Geschatte looptijd: enkele seconden.

### `tests/test_messages.py`
- **AC-7** `test_golden` (geparametriseerd over `GOLDEN_CASES`): `render_alert(case.event, case.spot, kite=case.kite, tides=case.tides, base_url=case.base_url)` geeft exact `title`, `body` en `go_url`, plus `spot_id == "test-strand"` en `kind == event.kind`. Dit dekt: zomer- en wintertijd, alle vier de soorten, de verplichte onderdelen, getij alleen bij een getijgevoelige spot met extremen, kite alleen als meegegeven (en niet bij `cancelled`), `go_url` `None` bij `cancelled` en zonder `base_url`.
- `test_required_parts_present` (AC-7): voor elk golden-geval komen in titel plus body voor: de spotnaam, `format_window_local` van de relevante snapshot, `" kn"`, `"vlagen"`, `compass_label(dir_deg)` en `f"({dir_deg}°)"`, het `DIR_CLASS_LABEL_NL`-label en het `CONFIDENCE_LABEL_NL`-label. Geen enkel bericht bevat "flandig" (aflandig).
- `test_tide_line_rules` (E32–E36): `PLAIN_SPOT` met `TIDES_SUMMER` → geen regel die met `Getij` begint; `LOW_TIDE_SPOT` met alleen extremen buiten de marge → geen getij-regel; `make_spot(tide_sensitive="prefer_low")` zonder `rws_station` → geen getij-regel; extremen precies op 09:00Z en 19:00Z (bij `S_SUMMER`) staan erin, 08:59Z en 19:01Z niet; een extreem op 2026-07-18 22:30Z bij een window 18:00Z–20:00Z (grens 23:00Z) toont `zo 00:30`; niveau 0 toont `0 cm`; `rws_station=" teststation "` (spaties) werkt.
- `test_kite_line_rules`: `KITE_IDEAL` → `Kite: 9 m² (past goed)`; underpowered `KiteAdvice(size_m2=14.0, fit="underpowered", ideal_size_m2=15.8)` → `Kite: 14 m² (aan de kleine kant, ideaal 15,8 m²)`; maat 10,5 → `10,5`; bij `cancelled` met kite: geen kite-regel.
- `test_go_url_rules` (E29–E31): `base_url` `None`, `""` en `"   "` → `None`; `"https://example.org/"` → `URL_SUMMER`; `"example.org"`, `"https://example.org/?x=1"`, `"https://exa mple.org"` → `ValueError`.
- `test_format_window_local` (E27, E28): 2026-07-18 20:00Z–23:00Z → `za 18 jul 22:00 – zo 19 jul 01:00`; 20:00Z–22:00Z → `za 18 jul 22:00–00:00`; 2026-10-25 10:00Z–12:00Z → `zo 25 okt 11:00–13:00`; naïef of `start >= end` → `ValueError`.
- `test_title_normalized` (E38): spotnaam `"Wijk  aan\nZee"` → titel `Go: Wijk aan Zee`. `test_spot_mismatch` (E39) → `ValueError`.
- **AC-8** `test_build_go_url_roundtrip`, geparametriseerd over (spot `test-strand`, 2026-07-18 12:00Z–16:00Z), (spot `wijk-aan-zee`, 2026-11-07 11:00Z–14:00Z) en (een aware `start` in `LOCAL_TZ`): met `urllib.parse.urlsplit` en `parse_qs` zijn `path == "/go"`, `qs["spot"] == [spot_id]` en `datetime.fromisoformat(qs["start"][0]) == start` (idem `end`); de queryparameters staan in de volgorde `spot`, `start`, `end`.
- `test_quote_matches_urllib`: `_quote(s) == urllib.parse.quote(s, safe="")` voor `"2026-07-18T12:00:00Z"`, `"a b+c/d?e&f=g#h"`, `"é~._-"` en `"Zoë"`.
- `test_build_go_url_invalid`: naïeve tijd, `start >= end`, `start` met minuten → `ValueError`.
- **AC-9** `test_body_max_length`: voor elk golden-geval `len(body) <= 1000`. Daarnaast een stress-geval: `LOW_TIDE_SPOT`, kite underpowered, een window van 16 uur (2026-07-18 04:00Z–20:00Z) en 20 extremen elk uur binnen de marge → hooguit `MAX_TIDE_EXTREMES_IN_MESSAGE` extremen in de regel en `len(body) <= 1000`.

### AC-10: puurheid
`tests/test_domain_purity.py` vindt `dedup.py` en `messages.py` automatisch en is groen; ze importeren geen `urllib` (A12). `dedup.py` en `messages.py` bevatten geen `.now(`, `.today(` of `model_construct` (bestaande test `test_no_model_construct_in_src`).

## Externe afhankelijkheden
- Geen nieuwe packages. Gebruikt: `pydantic` (al in `uv.lock`) en de standaardbibliotheek.
- Gecontroleerd gedrag:
  - `datetime.fromisoformat` accepteert sinds Python 3.11 een afsluitende `Z` (`'2011-11-04T00:05:23Z'` geeft `tzinfo=timezone.utc`); `isoweekday()` geeft 1 voor maandag ([Python-docs, datetime](https://docs.python.org/3.12/library/datetime.html)).
  - `urllib.parse.quote`: letters, cijfers en `_.-~` worden nooit gecodeerd, de standaard `safe` is `'/'` (daarom `safe=""` in de test), codering UTF-8; `parse_qs` decodeert de `%XX`-codes ([Python-docs, urllib.parse](https://docs.python.org/3.12/library/urllib.parse.html)). Alleen de tests gebruiken `urllib`; het domein heeft een eigen implementatie (A12).
  - Beaufort in knopen (onderbouwing van A3): 4 Bft = 11–16 kn, 5 Bft = 17–21 kn ([vaarbewijzen.nl, schaal van Beaufort](https://www.vaarbewijzen.nl/beaufort_schaal/), [gearfreaksurfschool.nl](https://gearfreaksurfschool.nl/info/blog/windkracht-beaufort-uitgelegd/)).
  - Zomer- en wintertijd via `zoneinfo` en `astimezone` (al gebruikt in WP-05 en WP-07).
- Geen API-endpoints, geen netwerk, geen kosten.

## Risico's
- **R1. Drempels niet getoetst aan echt gebruik.** 2 uur en 4 kn zijn een voorstel (A3). Te weinig meldingen: drempels omlaag (3 kn, maar 2 kn mag niet volgens AC-4). Te veel: wind naar 5 kn. Elke wijziging is één constante.
- **R2. Ruis bij splitsen.** Eén uur dat even `marginal` wordt, splitst een window: `worsened` plus `new`, en bij herstel `improved`. Dat zijn drie meldingen voor één twijfeluur. Bewust gekozen boven verzwijgen (A7); Lars toetst het in de testweek. Mogelijke mitigatie later: `min_go_hours` of de vlaagdrempels.
- **R3. Een lopend window dat instort geeft geen melding** (A5). De gebruiker is dan waarschijnlijk al op het strand en ziet de wind zelf. Komt het window terug, dan wordt het zonder `new` gekoppeld.
- **R4. Basislijn in plaats van nieuwste stand.** De opgeslagen `snapshot` is wat er gemeld is, niet de nieuwste verwachting (A4). WP-10 en een eventuele UI moeten dat zo tonen; staat onder "Gevolgen".
- **R5. Een ontbrekende actieve rij in WP-10 geeft een dubbele `new`.** Mitigatie: de laadregel onder "Gevolgen" en de invariant I4.
- **R6. Pushinkorting.** De volgorde van de regels is ontworpen voor 150 tekens; de echte weergave op iOS en Android is niet gemeten (WP-18 AC-5).

## Buiten scope
- `alert_state` laden, opslaan en opruimen, kite-advies per window berekenen, het filter op `verified` (WP-10).
- Versturen, `Notifier`, inkorten tot pushtekst, `last_notified_at` vullen, de overgang M1 → push (WP-17).
- De route `/go` en sessies (WP-14, WP-20).
- Stille uren voor meldingen (niet in het plan).
- Bronvermelding in berichten: die staat in de app (WP-13, WP-14), niet in een melding.
- Contractbestanden (`data/contracts/`) voor eventsoorten of `KiteFit`-labels; geen andere WP heeft ze nu nodig.
- Wijzigingen aan bestaande modules (`alerts`, `evaluation`, `kite`, `tide`, `spot`, `defaults`) en aan het databaseschema.

## Stappenplan voor de builder
Werk op branch `wp/WP-08` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-08`. Lees of print `.env` nooit. Draai na elke stap vanuit `ingest/`: `uv run pytest && uv run ruff check . && uv run ruff format --check .`. Eén commit per stap, commitberichten in het Engels.

1. **Modellen en snapshot, eerst de tests.**
   - Maak `tests/dedup_fixtures.py` (alle helpers behalve `windows_from_pattern`).
   - Schrijf in `tests/test_dedup.py` de tests onder "Snapshot en serialisatie" (inclusief AC-6, `test_entry_row_roundtrip`, `test_alert_state_enums_match_migration` en `test_event_invariants`). Rood.
   - Maak `src/shakka/domain/dedup.py` met de constanten, `AlertStatus`, `AlertEventKind`, `_RevalidatingModel`, `WindowSnapshot`, `snapshot_window`, `AlertStateEntry`, `AlertEvent` en `DiffResult`. Groen, inclusief `test_domain_purity.py`.

   Commit: `feat(domain): add alert window snapshots and alert state models`.
2. **Deduplicatie, eerst de tests.**
   - Schrijf de tests voor AC-1 t/m AC-5 in `tests/test_dedup.py`, voeg `windows_from_pattern` toe aan `dedup_fixtures.py` en schrijf `tests/test_dedup_invariants.py`. Rood.
   - Voeg `classify_change` en `diff_windows` (stappen 0–12 uit Ontwerp) toe aan `dedup.py`. Groen. Duurt `test_dedup_invariants.py` langer dan 30 seconden, meld dat dan in `deviations.md` in plaats van de roosters te verkleinen.

   Commit: `feat(domain): deduplicate alert windows into new, improved, worsened and cancelled events`.
3. **Berichten, eerst de tests.**
   - Maak `tests/message_fixtures.py` (alle waarden en `GOLDEN_CASES` exact zoals in het Testplan) en schrijf `tests/test_messages.py`. Rood.
   - Maak `src/shakka/domain/messages.py` (constanten, `AlertMessage`, `_quote`, `format_window_local`, `build_go_url`, de regelhelpers en `render_alert`). Groen.

   Commit: `feat(domain): render Dutch alert messages and go links`.
4. **Eindcontrole.** Draai de volledige suite en ruff. Controleer met `git status` en `git diff --stat develop` dat alleen de zeven bestanden uit "Bestanden" nieuw zijn en dat er geen bestaand bestand is gewijzigd. Controleer met `grep -n "urllib" ingest/src/shakka/domain/*.py` dat er niets wordt gevonden.
