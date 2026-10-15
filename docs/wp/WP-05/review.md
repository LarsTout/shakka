# Review WP-05, ronde 1
Oordeel: CHANGES_REQUIRED

## Blokkerend

B-1: `SIDESHORE_MAX_DEG = 100` laat wind met een aflandige component als `sideshore` (rijdbaar) door. Dat schendt de harde regel.
Waar: Drempelwaarden (`SIDESHORE_MAX_DEG`, `SIDE_OFFSHORE_MAX_DEG`), Ontwerp/Richting (klassentabel), Interfaces (`defaults`), E15, Testplan AC-1 (`test_class_boundaries` 100/101), R3, en de geplande tekst voor `docs/SPOT_DATA.md` §4.
Waarom: de aanlandige component is `cos(d)`. Elke `d > 90` heeft een aflandige component: bij `d = 100` komt ongeveer 17% van de wind (sin 10°) van het land af. Dat is per definitie schuin aflandig. PROJECT_PLAN §4 en CLAUDE.md zeggen: "offshore en side-offshore zijn altijd `no_go`, niet configureerbaar". De blueprint voert zelf aan dat ±10° de onnauwkeurigheid van modelrichting en kustrichting is. Juist daarom hoort een marge aan de veilige kant te liggen, niet aan de onveilige. Nu wordt de onzekerheid gebruikt om aflandige uren als `go` te tellen. De blueprint toont niet aan dat 90 < d ≤ 100 geen aflandige wind is; hij erkent het juist ("laat maximaal 10° aflandige component toe"). Of je een harde veiligheidsregel versoepelt, bepaalt de planner niet; dat moet Lars beslissen.
Voorstel: `SIDESHORE_MAX_DEG = 90.0`, bovengrens inclusief. Bij `d = 90` is de aflandige component precies 0, en AC-1 (180 en 0 zijn `sideshore` bij normaal 270) blijft dan kloppen. Pas de grenstest aan naar 90/91 (90 is `sideshore`, 91 is `side_offshore`) en werk E15, R3, de onderbouwing en de SPOT_DATA-tekst bij. `SIDE_OFFSHORE_MAX_DEG = 157.5` mag blijven; die grens bepaalt alleen het label. Wil de planner de kosten van "wind evenwijdig aan de kust" zichtbaar maken, dan hoort dat als vraag in de lijst voor Lars, niet als default.

B-2: Het testgeval voor richtingsspreiding in AC-8 heeft een verkeerde verwachte uitkomst.
Waar: Testplan AC-8, "Richtingsspreiding: (270, 270, 270, 320) heeft een afwijking > 45 en geeft `low`".
Waarom: met de gedefinieerde berekening (circulair gemiddelde van eenheidsvectoren, spreiding = grootste afwijking tot het onafgeronde gemiddelde) is het gemiddelde ongeveer 281,9°. De afwijking van 320 is dan ongeveer 38,1°, en dat is niet groter dan 45. Er komt dus geen `low`. Bij gelijke snelheden en gezette vlagen wordt het `medium` (38,1 > 20). De test faalt, en dan moet de builder kiezen tussen de testdata en de drempel: een ontwerpkeuze die hij niet hoort te maken.
Voorstel: gebruik bijvoorbeeld (270, 270, 270, 0). Dan is het gemiddelde ongeveer 288,4° en de afwijking ongeveer 71,6°, dus `low`. Voeg ook een geval vlak onder de grens toe dat `medium` blijft, bijvoorbeeld het huidige (270, 270, 270, 320) met verwachting `medium` en `dir_spread_deg ≈ 38.1`.

## Niet-blokkerend

N-1: De invariant op `HourEvaluation` is via de constructor en `model_validate` waterdicht: `dir_class` offshore of side-offshore met `go` of `marginal` geeft een `ValidationError`. Volgens de pydantic-documentatie omzeilen `model_copy(update=...)` en `model_construct()` de validatie echter. `ev.model_copy(update={"verdict": "go", "reasons": ()})` levert dus een offshore-`go` op. De zin "Een inconsistente evaluatie is dus niet te maken" klopt daarom niet helemaal. `evaluate_hour` zelf maakt zo'n object nooit, en WP-07 filtert daarna nog op `dir_class in rule.dir_classes` (zonder offshore-klassen). Maar de alertjob van WP-10 werkt in het geheugen en niet via de DB-CHECK. Voorstel: overschrijf `model_copy` zodat het resultaat opnieuw gevalideerd wordt (`type(self).model_validate({**self.model_dump(), **(update or {})})`), voeg een test toe die laat zien dat `model_copy` naar offshore-`go` faalt, en pas de zin aan.

N-2: Maak de invariant sterker. Eis ook dat `dir_class == offshore` precies samengaat met `OFFSHORE` in `reasons`, en `side_offshore` met `SIDE_OFFSHORE`. Nu is `dir_class=offshore, verdict=no_go, reasons=(dark,)` geldig. Dan ontbreekt de "expliciete waarschuwing" die het plan bij offshore eist.

N-3: Een `go`-uur kan `gust_kn = None` hebben (A2/E3: dan is de betrouwbaarheid `medium`, wat `go` toelaat). Het contract van WP-08 heeft `WindowSnapshot.gust_max_kn: float`, en het bericht moet "de maximale vlagen in kn" bevatten. Noem dit onder "Gevolgen voor latere WP's" (WP-07 en WP-08 moeten een onbekende vlaag aankunnen, bijv. `float | None`), zodat het niet stil als 0 belandt.

N-4: Betrouwbaarheid `high` controleert `n_wind`, maar niet hoeveel modellen een richting hebben. Bij drie modellen met wind en één met richting is `dir_spread_deg = 0`, en dan is `high` mogelijk. Overweeg in regel 4 ook `n_dir >= CONFIDENCE_HIGH_MIN_MODELS`.

N-5: Veiligheid rond de grens. De consensus is een circulair gemiddelde. Met grens 90 kan één model side-offshore aangeven (bijv. 80, 80, 85, 100 bij normaal 0, gemiddelde ongeveer 86) terwijl het uur `sideshore` en `high` is. Optie voor Lars in de testweek: geef `low_confidence` als een model met richting een offshore-klasse heeft terwijl de consensus rijdbaar is. Dit vraagt geen nieuwe redencode.

N-6: Vlagen ten opzichte van `max_kn` worden niet beoordeeld. Bij wind 28 en vlaag 44 (ratio 1,57) volgt alleen `wind_borderline`. Dit is een kandidaat voor de testweek. Leg het als open punt vast bij de drempels (R1/R2).

N-7: Bij `GUSTY_RATIO`: de vastgelegde respons van WP-03 laat bij ongeveer 15 kn voor ICON en ECMWF een factor van ongeveer 1,2–1,4 zien en voor KNMI en GFS ongeveer 1,6–2,0. De onderbouwing klopt daarmee in grote lijnen. Bij hogere wind wordt de ratio-eis snel heel ruim (25 kn wordt pas vlagerig bij 40). Laat Lars dit expliciet toetsen.

N-8: De zin in de onderbouwing "100 laat maximaal 10° aflandige component toe" verdwijnt met B-1. Zorg dat ook de beschrijving van `SIDE_OFFSHORE_MAX_DEG` ("met de verruimde ondergrens") meegaat.

## Gecontroleerd en in orde
- Bevestigde beslissingen: een onbekende vlaag wordt nooit 0 (A2, E3/E4, vlaagregels alleen met `g` bekend, hooguit `medium`). Het getij wordt beoordeeld op het geschatte niveau via `estimate_tide_level` met een relatieve positie (A4, A5). Een dubbel laagwater werkt zonder aanname van afwisseling. Het agger-testgeval heb ik nagerekend: op 12:00Z is de positie ongeveer 0,017, op 16:30Z ongeveer 0,50.
- WP-06: WP-05 importeert niets uit `shakka.domain.kite` en zet geen kiteconstanten in `defaults.py`.
- Contracten: de enumwaarden, `evaluations`-kolommen en `evaluations_offshore_is_no_go` kloppen met `supabase/migrations/20261015090000_m1_schema.sql`. `ForecastHour`, `TideExtreme`, `estimate_tide_level`, `SpotProfile`, `DirRange` en `SeasonClosure` worden ongewijzigd en correct gebruikt. `REPO_ROOT` bestaat in `shakka.config`. De puurheidstest staat `astral`, `functools` en `statistics` al toe.
- De signatures van astral 3.2 (`sunrise`/`sunset(observer, date=None, tzinfo=timezone.utc)`, `Observer(latitude, longitude, elevation)`) kloppen. "date wordt altijd meegegeven" is terecht, want zonder `date` roept astral `today(tzinfo)` aan.
- Daglicht nagerekend voor 52,47 N / 4,57 O: 21-06 zonsopkomst ongeveer 03:18–03:19Z (03:00Z is donker met een marge van 15 min); 21-12 zonsopkomst ongeveer 07:50Z en zonsondergang ongeveer 15:29Z, dus daglichturen 08:00 t/m 14:00Z.
- Seizoen en tijdzone: de verwachtingen rond 29-03-2026 en 25-10-2026 (overgangen om 01:00Z) en de lokale datum op 28-03 23:00Z kloppen. Het venster [from, to) volgt WP-02 A4.
- Floatgrenzen in AC-4 (1,6·20, 1,9·20, 12+2, 30−2) vallen exact uit zoals verwacht.

## Gecontroleerde bronnen
- https://pypi.org/project/astral/
- https://raw.githubusercontent.com/sffjunkie/astral/3.2/src/astral/sun.py
- https://raw.githubusercontent.com/sffjunkie/astral/3.2/src/astral/__init__.py
- https://raw.githubusercontent.com/sffjunkie/astral/master/src/astral/sun.py
- https://pydantic.dev/docs/validation/latest/api/pydantic/base_model/ (`model_copy` en `model_construct` valideren niet)
