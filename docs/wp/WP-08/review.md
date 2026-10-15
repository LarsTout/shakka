# Review WP-08, ronde 1
Oordeel: CHANGES_REQUIRED

Samenvatting: de blueprint is grondig en dekt AC-1 t/m AC-10. Ik heb de deduplicatie met de hand doorgerekend en vond geen fout in de kernlogica. Het ging om idempotentie (ook voor lopende windows), één-op-één koppelen, splitsen en samensmelten (E11 t/m E14), heractiveren, verlopen en het sluipend verschuiven (E17). Ook de golden-berichten kloppen: zomer- en wintertijd, afronding, windroos, getijmarge en labels. Er zijn twee blokkerende punten: een test die tegen de eigen regels ingaat, en een contractgat met WP-10/WP-17 dat een favoriet dagen stil kan zetten.

## Blokkerend

B-1: `test_wind_ignored_once_begun` verwacht in de tweede helft het verkeerde resultaat. Waar: Testplan, AC-4, `test_wind_ignored_once_begun`. Waarom: "Met `now = NOW` en dezelfde wind → `improved`" bij het huidige window 12–16 tegen de basislijn 10–16. Met `now = 06:00Z` is `first_hour = 07:00Z` en dus `p_start = 10:00Z`. Dan is `d_start = +2 h`, en dat geeft `worse`. Omdat verslechtering voorgaat (A3), komt er `WORSENED` uit, niet `IMPROVED`. De builder krijgt een rode test en moet zelf kiezen wat er bedoeld is. Voorstel: neem voor de variant met `now = NOW` een huidig window 10–16 met wind 22–26. Dan geeft `d_min = +6` het resultaat `improved` en toont de test zuiver dat de wind wél wordt vergeleken. Of verwacht hier expliciet `worsened` en leg uit waarom.

B-2: De `ValueError` bij overlappende actieve entries botst met gedeeltelijk opslaan in WP-10 en met de afleverregel per event in WP-17. Waar: Ontwerp stap 1 (vierde controle), "Gevolgen voor latere WP's" (WP-10 Opslaan, WP-17). Waarom: de blueprint noemt een overlap "een kapotte database", maar die overlap ontstaat ook via een normale route. Neem een split (E11/E14): entry A wordt `worsened` met een kortere span en er komt een nieuwe entry N voor het andere deel. WP-17 slaat volgens zijn contract de state "voor dat event" niet op bij een tijdelijke fout. Mislukt alleen de aflevering voor A en wordt N wel ingevoegd, dan staan A met de oude span (bijv. 10–18) en N (15–18) allebei `active` en overlappen ze. Vanaf de volgende run geeft `diff_windows` voor die favoriet altijd `ValueError`. WP-10 slaat de favoriet dan over tot de oude `window_end` voorbij is: dagen geen alerts, zonder herstel. Hetzelfde kan in WP-10 gebeuren als de job crasht tussen inserts en updates (PostgREST-schrijfacties zijn niet transactioneel), en de blueprint legt geen schrijfvolgorde vast. Voorstel (één van beide):
  - (a) Leg onder "Gevolgen" vast dat WP-10 per (gebruiker, spot) eerst de updates van bestaande entries schrijft en daarna pas de inserts. Leg ook vast dat WP-17 de schrijfacties van één diff als geheel overslaat (alles of niets per gebruiker en spot) zodra een event niet geschreven wordt, of in elk geval geen nieuwe entry invoegt die overlapt met de oude span van een overgeslagen entry. Noem dit expliciet als randvoorwaarde voor de afleverregel van WP-17.
  - (b) Laat `diff_windows` deterministisch herstellen in plaats van een fout te geven. Bijvoorbeeld: van overlappende levende actieve entries blijft de entry met het vroegste `window_start` (daarna `id`) actief en worden de andere stil `expired`. Voeg daar een test voor toe.

## Niet-blokkerend

N-1: `diff_windows` controleert niet dat elk huidig window op of na `first_hour` begint. Bij gebruik volgens het contract (dezelfde `now` als `find_windows`) kan dat ook niet, maar met een window dat vóór `first_hour` begint, kan een niet-gekoppelde begonnen entry overlappen met een nieuwe entry. I2 breekt dan stil en de volgende run geeft een fout. Een extra controle (`window.start < first_hour` → `ValueError`) maakt de aanname expliciet. De testscenario's blijven daarbij geldig.

N-2: `DiffResult([], [])` (E1, `test_invalid_input`) is notatie. Een pydantic-model accepteert geen positionele argumenten. Schrijf in de tests `DiffResult(events=[], new_state=[])` om verwarring te voorkomen.

N-3: In `m2(x)` staat niet welke afronding geldt. Pythons `round` rondt half naar even af. De quiver accepteert willekeurige floats (bijv. 9,25). Kies expliciet voor half naar boven (`math.floor(x * 10 + 0.5) / 10`), net als `ideal_kite_size` en `kn()`.

N-4: In `format_window_local` worden `ls` en `le` gebruikt maar niet gedefinieerd. Dat zijn kennelijk de lokale `start` en de lokale `end` (niet `end - 1 µs`). Zet dat er in één zin bij.

N-5: Een zuivere verschuiving van 2 uur (10–16 wordt 12–18, E17) wordt `worsened` ("Slechter"), omdat verslechtering voorgaat. Dat volgt consequent uit A3, maar de gebruiker kan het onverwacht vinden. Neem het op in de lijst die Lars in de testweek toetst (bij R1/R2).

N-6: Met `min_go_hours = 1` (toegestaan, bereik 1–24) heeft een window van 1 uur dat 1 uur verschuift geen overlap. Dat geeft `cancelled` plus `new`, terwijl AC-4 "±1 uur geen melding" belooft. Bij de standaardwaarde 2 gebeurt dit niet. Benoem het als edge case of risico, zodat het een bewuste keuze is.

N-7: Klapperen over meerdere runs (split, merge, weer split) geeft voor dezelfde uren opnieuw een `new`, omdat de bij het samensmelten `expired` entry niet wordt hergebruikt. Binnen één diff blijft I4 gelden. R2 dekt dit grotendeels; noem dat ene geval er expliciet bij.

N-8: `classify_change` is publiek. Leg vast dat die functie `now` ook zelf naar UTC omzet vóór `_floor_hour`, net als stap 0 van `diff_windows`. Voor Nederlandse offsets maakt het geen verschil, maar zo is de functie op zichzelf correct.

## Gecontroleerde bronnen
- https://docs.python.org/3.12/library/urllib.parse.html (`quote`: letters, cijfers en `_.-~` worden nooit gecodeerd, standaard `safe='/'`, UTF-8)
- https://docs.python.org/3.12/library/datetime.html (`fromisoformat` met `Z` geeft `timezone.utc` sinds 3.11; `isoweekday()` maandag = 1)
- Lokaal: `ingest/src/shakka/domain/{alerts,evaluation,consensus,direction,kite,tide,spot,defaults}.py`, `ingest/src/shakka/db.py` (`iso_utc`, `to_json`), `ingest/tests/{alert_fixtures,evaluation_fixtures,test_domain_purity}.py`, `supabase/migrations/20261015090000_m1_schema.sql` (`alert_state`), WORK_PACKAGES WP-07, WP-08, WP-10, WP-14, WP-17, blueprints WP-05 en WP-07 ("Gevolgen").
- Handmatig gecontroleerd: weekdagen (2026-07-18 en 2026-11-07 zijn zaterdag, 2026-10-25 is zondag en de dag van de overgang naar wintertijd om 01:00Z), `compass_label(225) = ZW` en `compass_label(270) = W`, afronding 22,4 → 22 en 27,5 → 28, getijselectie en lokale tijden in alle golden-gevallen, kite-maten in A3 (2,2·75/16 = 10,3 en 2,2·75/20 = 8,3), regex voor de CHECK-test tegen de migratie.
