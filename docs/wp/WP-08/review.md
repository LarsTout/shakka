# Review WP-08, ronde 2
Oordeel: APPROVED

Samenvatting: B-1 en B-2 uit ronde 1 zijn echt en consistent opgelost. Ik heb de vier gevallen van `test_overlap_repair` en de gewijzigde `test_wind_ignored_once_begun` met de hand doorgerekend, inclusief I1 t/m I7 en de omgekeerde invoervolgorde. Uitkomst: alles klopt zoals beschreven. Het herstel in stap 4 hangt niet af van de invoervolgorde (sleutel `(window_start, id)`, uniek bij opgeslagen rijen) en is idempotent. Na stap 4 overlappen de behouden entries elkaar niet, de diff houdt I2 in stand, en daarom doet stap 4 bij de volgende run niets meer. De nieuwe controle op `first_hour` (N-1) botst niet met begonnen windows. De revisie brengt geen nieuwe blokkerende punten mee.

## Blokkerend
Geen.

## Controle van de punten uit ronde 1

**B-1, opgelost.** Bij `now = 11:30Z` is `first_hour` 12:00Z. De basislijn `B` (10–16) begint vóór `first_hour`, dus de wind telt niet mee. `p_start` is 12:00Z en gelijk aan `C.start`, en `d_end = 0`. Beide windvarianten geven daarom `None`. Via `diff_windows` gaat de entry naar fase 1 (begonnen), krijgt hij geen event en blijft `window_start` 10:00Z. Bij `now = NOW` (`first_hour` 07:00Z) en randen 10–16: wind 22–26 geeft `d_min = +6` en `d_max = +4`, dus `improved`. Wind 10–14 geeft `d_min = -6` en `d_max = -8`, dus `worsened`. De test toetst nu zuiver de windregel.

**B-2, opgelost.** Ik heb de tabel van `test_overlap_repair` nagerekend.
- *Half geschreven split* (`now` 06:00Z): `"a"` 10–18 heeft het vroegste begin en blijft. `"n"` 15–18 wordt `expired`. In fase 2 hebben 10–13 en 15–18 dezelfde overlap (3 uur), dus wint het vroegste window: `"a"` wordt gekoppeld aan 10–13. Dat geeft `d_end = -5 h`, dus `worsened@0`. 15–18 is daarna vrij en geeft `new@2`.
  - I1: 15–18 ligt alleen in de nieuwe entry, want `"n"` is niet meer actief.
  - I4: 15–18 telt niet als gekoppeld aan `"n"`, omdat `new_state[1]` niet actief is. Er is dus precies 1 `new`.
  - I7: bij `persist` en een tweede diff blijft stap 4 leeg, de koppelingen blijven gelijk aan de basislijn en er volgen 0 events.
  - Bij omgekeerde `previous` is het resultaat per `id` hetzelfde.
- *Zelfde begin:* de sleutel `(10:00, "a")` komt vóór `(10:00, "b")`. `"a"` wordt gekoppeld aan 10–16 en geeft geen event, want het window is gelijk aan de basislijn. `"b"` wordt `expired`.
- *Begonnen wint:* `"x"` (10:00Z) komt vóór `"a"` (12:00Z). In fase 1 wordt `"x"` gekoppeld aan 12–16 en geeft `classify_change` `None`. `window_start` blijft 10:00Z.
- *Keten:* `"c"` blijft. `"b"` overlapt `"c"` en wordt `expired`. `"a"` wordt alleen getoetst tegen `kept = ["c"]` en blijft dus. Zonder windows worden beide toekomstige entries `cancelled`, op de indexen 0 en 2.

De bewering in fase 1 ("na stap 4 hooguit één begonnen entry") klopt. Na stap 3 bevat elke begonnen entry `now` in zijn span, en het vroegste begin wint, dus een begonnen entry verdwijnt nooit ten gunste van een toekomstige (E44). De schrijfvolgorde en de alles-of-niets-regel onder "Gevolgen" sluiten aan op WP-10 en WP-17. Ze zijn strenger dan de huidige afleverregel van WP-17, maar spreken WP-17 AC-4 en AC-5 niet tegen.

**R7: acceptabel en in de kern juist beschreven.** Het kost een dubbele melding met een andere `tag`. De oude melding van de verlopen entry blijft op de telefoon staan; dat staat er ook bij onder WP-17. Zie N-1 voor een kleine onvolledigheid.

**N-1 uit ronde 1 (`ValueError` voor een window vóór `first_hour`): geen botsing.** De controle geldt voor de huidige `Window`s, niet voor entries. `find_windows` neemt alleen uren mee met `valid_at >= first_hour` (`alerts.py` regel 335, `first_hour = _floor_hour(now) + 1 h`, regel 359). Een begonnen window komt dus altijd al afgekapt binnen. Het oorspronkelijke begin staat alleen in `AlertStateEntry.window_start`, en daar kijkt de controle niet naar. De formule is gelijk in beide modules. Alle testscenario's voldoen eraan. Ik heb nagelopen: idempotentie scenario 3 (window precies op `first_hour`), de reeks van het lopende window, E14, AC-4 met `NOW` en rooster B (stap 2 met `W(p2)` op `now1`). De voorwaarde dat WP-10 dezelfde `now` doorgeeft, is al bindend vastgelegd.

N-2 t/m N-8 zijn verwerkt zoals beschreven. Ik heb de afronding van `m2` nagerekend: 9,25 → `9,3`, 9,75 → `9,8`, 9,96 → `10` en 15,8 → `15,8`. In `test_classify_change_now_timezone` geeft een offset van +05:30 zonder omzetting naar UTC `first_hour` 12:30Z, en daarmee 1,5 uur, dus `None`. De test laat dat verschil dus echt zien.

## Niet-blokkerend
N-1: De schrijfvolgorde (eerst updates, dan inserts) voorkomt overlap alleen tussen de updates en de inserts. Een crash midden in de updates kan nog steeds overlap geven. Voorbeeld: entries X 10–14 en Y 15–18, windows 10–12 en 13–18. In de diff wordt Y 13–18 en X 10–12. Is alleen Y bijgewerkt, dan overlappen X (10–14) en Y (13–18). Het herstel houdt X en zet Y op `expired`, en daarna krijgt 13–18 opnieuw `new`. Bij samensmelten kan het ook een `improved` van een andere entry worden in plaats van een `new`. R7 noemt alleen "opnieuw `new`". Formuleer R7 algemener ("een dubbele melding"). Of laat WP-10 binnen de updates eerst de entries schrijven die niet meer actief zijn of korter worden, en pas daarna de entries die langer worden. Het herstel vangt alle gevallen op, dus dit is geen correctheidsprobleem.

N-2: De alles-of-niets-regel per (gebruiker, spot) en de schrijfvolgorde staan nu alleen in deze blueprint. De afleverregel in `docs/WORK_PACKAGES.md` (WP-17) zegt nog "de state voor dat event". Laat de orchestrator dit overnemen in de WP-secties van WP-10 en WP-17, zodat de planners het niet missen. Neem daar ook het punt over de `tag` mee. Volgens WP-10 krijgt `state_id` pas een waarde na het opslaan, maar onder alles-of-niets komen alle schrijfacties na de afleveringen. WP-17 moet de `id` van een nieuwe entry dus zelf toekennen (`alert_state.id` is een `uuid` met een default, dus een id die de client meegeeft is toegestaan).

N-3: Bij `id is None` hangt de volgorde van het herstel af van de invoervolgorde (de laatste sleutel is `i`). Dat staat in A15 en komt bij opgeslagen rijen niet voor. Er is geen actie nodig.

## Gecontroleerde bronnen
- https://docs.python.org/3.12/library/urllib.parse.html (`quote`: letters, cijfers en `_.-~` worden nooit gecodeerd; standaard `safe='/'`; UTF-8; `parse_qs` decodeert `%XX`)
- https://pydantic.dev/docs/validation/latest/api/pydantic/base_model/ (`model_copy(update=...)` valideert niet. Dat onderbouwt de eigen kopie van `_RevalidatingModel`.)
- Lokaal: `ingest/src/shakka/domain/alerts.py` (`_floor_hour`, `first_hour`, filter `valid_at >= first_hour`, `_RevalidatingModel`), `supabase/migrations/20261015090000_m1_schema.sql` (`alert_state`: `id uuid default gen_random_uuid()`, CHECKs), `docs/WORK_PACKAGES.md` (WP-08, WP-10, WP-17), de vorige `review.md`.
- Met de hand nagerekend: alle vier de gevallen van `test_overlap_repair` (ook met omgekeerde invoer en I1 t/m I7), `test_wind_ignored_once_begun`, `test_classify_change_now_timezone`, `test_one_hour_window_shift`, `test_active_beats_cancelled`, `test_drift_accumulates`, de grensgevallen van `test_invalid_input` en de afrondingen van `m2`.
