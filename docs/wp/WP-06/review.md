# Review WP-06, ronde 1
Oordeel: APPROVED

## Blokkerend
Geen.

Wat ik gecontroleerd heb:
- **Scope en AC's.** AC-1 t/m AC-6 hebben elk een of meer concrete tests (AC-2 bewust via de verifier, zonder test op `true`). Niets uit de non-goals: geen profielopslag, geen berichten, geen `data/contracts` en geen import uit WP-05-code. `kite.py` importeert alleen stdlib, `pydantic` en `shakka.domain.spot.Level`, dus parallel bouwen met WP-05 kan. Constanten staan in `kite.py` en niet in `defaults.py`, wat een mergeconflict voorkomt.
- **Contracten.** De signaturen zijn gelijk aan WORK_PACKAGES WP-06. Alle wijzigingen zijn toevoegingen: een default `()` voor `quiver_m2`, en `pick_from_quiver`, `classify_fit` en de constanten. Het invoerdomein sluit aan op de bestaande DB-checks in `supabase/migrations/20261015090000_m1_schema.sql`: `weight_kg` 30–200, en voor `quiver_m2` `cardinality <= 10` vóór ontdubbelen en 3–21. NaN en inf worden door Postgres ook geweigerd. `Level` komt uit `ingest/src/shakka/domain/spot.py`. Het patroon met bevroren pydantic-modellen en `extra="forbid"` volgt `SpotProfile`.
- **Voorbeeldtabel, alle 26 gevallen met de hand nagerekend.** Ik heb ideaal, keuze via de productgrenzen (7·9=63, 9·12=108; 6·8=48, 8·10=80; 9·12=108, 12·15=180, 15·17=255; 5·7=35, 7·9=63, 9·12=108, 12·14=168; 7,5·10,5=78,75, 10,5·13,5=141,75) en fit gecontroleerd. Alle verwachte waarden kloppen. De fractie van `raw × 10` ligt overal minstens 0,038 van ,5 af (k21: 118,46). De bewering in de blueprint klopt dus.
- **Float-gedrag van de grenstests.** `2.2*75 → 165.0`, `1.8*75 → 135.0` en `2.2*60 → 132.0` zijn exact na IEEE-afronding (de fout is kleiner dan een halve ulp). `132/11 = 12.0` en `12.0*12.0 == 9*16`, dus E9 geeft via de publieke route maat 9, `underpowered`. `165/20 = 8.25` geeft half-up 8,3. In `classify_fit` liggen de grenzen 10/8,0 en 10/12,5 exact op de band. De AC-6-getallen kloppen ook: de bovenste mediaan van [12, 18, 25, 14] is 18 (ideaal 9,2, maat 9). Gemiddelde 17,25 geeft ideaal 9,6, de gewone mediaan 16 geeft 10,3, en het maximum 25 geeft 6,6 met maat 7.
- **Monotonie AC-4/AC-5.** Het argument klopt. Vermenigvuldigen en delen met round-to-nearest zijn monotoon, net als `floor` en `/10`, en voor `ideal > 0` is `ideal²` monotoon. De index is een telling van drempels die monotoon in `ideal` worden overschreden. Er komt nooit een ideaal van 0 uit: het minimum is 1,8·30/100 = 0,54, afgerond 0,5. Daarmee is `classify_fit` (> 0) altijd geldig.
- **Pydantic.** `Field(strict=True)` op `int` weigert `bool` en `float` volgens de conversietabel van pydantic. Daarmee is E6 gedekt.

## Niet-blokkerend
N-1: Bronweergave in A1 is op één punt onnauwkeurig. Waar: A1 (beginner) en Externe afhankelijkheden. Waarom: de kite-size-calculator van kitesurfingofficial.com geeft beginners tot circa 18 kn juist een iets *grotere* kite, en pas vanaf 22 kn een kite die ongeveer 15 % kleiner is. Alleen het journal-artikel zegt "lower edge of every range". The Kitesurf Centre schrijft daarnaast dat hun formule "generally brings up a smaller kite than needed", met het oog op lessen. Factor 1,8 is ongeveer 18 % kleiner bij elke windkracht. Voorstel: zet die nuance in A1, zodat Lars bij het toetsen van k06, k08, k16, k20 en k25 weet dat de bronnen hier uiteenlopen. Dit is geen ontwerpwijziging.

N-2: Hoe het fijne windraster wordt opgebouwd, staat niet vast. Waar: Testplan AC-4, `test_ideal_monotone_in_wind_fine_grid`. Waarom: als de builder het raster cumulatief opbouwt (`x += 0.1`), komt de laatste waarde net boven 100,0 uit. `_check_wind` gooit dan een `ValueError` en de test faalt zonder dat het ontwerp fout is. Voorstel: schrijf `[i / 10 for i in range(10, 1001)]` voor.

N-3: De bewering over de grenzen is alleen waar in absolute zin. Waar: tekst onder de Voorbeeldtabel. Waarom: naar verhouding ligt k12 het dichtst bij een keuzegrens: ideaal 16,5 tegen √255 ≈ 15,97, ongeveer 3 %. In absolute ideaal² staat k18 met 4,75 het dichtst bij. De conclusie (ver boven de float-nauwkeurigheid) blijft staan. Voorstel: maak de zin preciezer.

N-4: `recommend_for_window` zegt niet welke waarden naar de mediaan gaan. Waar: Gedrag per functie. Waarom: `_check_wind` geeft een `float` terug. Het is netter om die gevalideerde waarden aan `median_high` te geven dan de ruwe invoer. De uitkomst verandert niet, maar het voorkomt een ontwerpkeuze bij de builder. Voorstel: `values = [_check_wind(v) for v in wind_kn_values]`.

N-5: In `test_window_uses_upper_median` geeft de gewone mediaan (16 kn, ideaal 10,3) dezelfde maat (9) als de bovenste mediaan. Het onderscheid blijkt dus alleen uit `ideal_size_m2`. Voor AC-6 is dat voldoende. Optioneel: een tweede window waarin ook de maat verschilt, bijvoorbeeld [12, 14, 17, 25]. Daar geeft de gewone mediaan 15,5 maat 12, en de bovenste mediaan 17 maat 9.

N-6: In A3 staat "tot en met ideaal 10,39". Omdat het ideaal op 0,1 wordt afgerond, is dat in de praktijk tot en met 10,3. Puur cosmetisch.

## Gecontroleerde bronnen
- https://kitesurfing-handbook.peterskiteboarding.com/progression/choosing-the-right-kite-size: formule "Weight (kg) / wind (knots) x 2.2" en voorbeeld 58/16 × 2,2 = 7,9 bevestigd.
- https://kitesurfingofficial.com/tools/kite-size-calculator: J. Douglass-formule `(weight_kg × 2.2) / wind_knots`, intermediate twintip, 14–22 kn bevestigd. Beginnernuance zie N-1.
- https://kitesurfingofficial.com/journal/what-size-kite-do-i-need: "Beginners should sit at the lower edge of every range" en het kwadraat van de windsnelheid bevestigd.
- https://www.thekitesurfcentre.com/news/how-to-choose-the-right-kite-size: "Rider Weight / Wind Speed x Ability", beginner 1,8, intermediate 2,1, independent 2,3 bevestigd.
- https://pydantic.dev/docs/validation/latest/concepts/conversion_table/: in strict mode weigert een `int` zowel `bool` als `float`.
- Lokaal: `ingest/src/shakka/domain/spot.py`, `ingest/tests/test_domain_purity.py`, `ingest/pyproject.toml`, `supabase/migrations/20261015090000_m1_schema.sql`, WORK_PACKAGES WP-06, WP-08 en WP-10.
