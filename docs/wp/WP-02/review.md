# Review WP-02, ronde 2
Oordeel: APPROVED

Ronde 2 toetst revisie 2 van de blueprint. B-1 uit ronde 1 is echt opgelost. N-1 t/m N-8 zijn verwerkt op een manier die klopt met de bestaande code. De revisie brengt geen nieuwe blokkerende punten mee.

## Controle B-1 (ronde 1)
- `test_validate_default_path` (Testplan AC-1) controleert nu alleen drie dingen: exitcode 0, de regel `spots validate: ok` en `re.search(r"^ok      \d+ spots valid \(\d+ verified\)$", ..., re.MULTILINE)`. Er is geen exacte telling meer. Het patroon past op de uitvoertabel: `ok` gevolgd door zes spaties, net zo breed als `error   ` en `warn    `.
- De exacte telling `25 spots valid (0 verified)` staat alleen nog in de eenmalige AC-2-controle (Testplan AC-2, stap 6 en stap 9). Daar hoort hij, volgens de WP.
- De vaste aantallen worden getest op tijdelijke bestanden via `--path` (`test_validate_counts_on_tmp_file`: `MIN_SPOT_YAML` geeft 1/0 en `FULL_SPOT_YAML` geeft 1/1). Die test hangt niet af van `data/spots.yaml`.
- De permanente datatests (`test_data_file_is_valid`, `test_contract_ids_present`) eisen alleen geldigheid en een superset van de 25 contract-id's. Lars kan dus velden invullen, spots verifiëren en spots toevoegen zonder dat CI rood wordt. Alleen een id hernoemen of verwijderen faalt, en dat is bewust (A9, R8).

## Blokkerend
Geen.

## Niet-blokkerend
N-1: In de tabel Hulptypes en in "Verwerking review" staat de regex van `_LocalTime` als `([01][0-9]\|2[0-3]):[0-5][0-9]`. De `\|` is alleen de markdown-escape voor een `|` binnen een tabelcel. In de code hoort `re.fullmatch(r"([01][0-9]|2[0-3]):[0-5][0-9]", v)` te staan. Wie de tekst letterlijk overneemt, krijgt een letterlijk `|`-teken in het patroon en daarmee een regex die nooit matcht. De tests vangen dat direct af (E2 en `FULL_SPOT_YAML` worden rood), dus het risico is klein.

N-2: Bij `_MonthDay` staat "faalt `date(2000, int(v[:2]), int(v[3:]))`". Bedoeld is: vang de `ValueError` van `date(...)` af en geef dan de eigen melding. Dat volgt al uit de beschrijving en E3 test het (`"00-10"`, `"13-01"`, `"02-30"`). Dit is alleen een leesbaarheidspunt.

N-3: `UniqueKeySafeLoader` roept `construct_object(key_node)` aan vóór `super().construct_mapping`. Dat werkt correct, omdat `construct_object` het resultaat cachet in `constructed_objects`: de superklasse krijgt hetzelfde object terug, ook bij een sequence-sleutel die als generator wordt opgebouwd. Daardoor doet E39 wat de blueprint belooft: een lijst is geen `Hashable`, de lus slaat die sleutel over en de basisklasse geeft "found unhashable key". Geen actie nodig.

## Gecontroleerd zonder bevinding
- `RecordingFake` (Testplan AC-5): `FakeSupabase.__init__` heeft alleen een keyword-only `clock` met een default, en de signatuur van `upsert(self, table, rows, *, on_conflict) -> int` komt exact overeen met `ingest/tests/fakes.py`. `seed` registreert niets in `writes`, dus "writes groeit met precies één `("upsert", "spots")`" en "writes en upsert_payloads groeien niet" (tweede sync) kloppen.
- E29: `seed` met `lat: 10.0` laat `from_row` falen, waarna `_normalized` `None` geeft. De rij geldt dan als gewijzigd en de upsert schrijft alle 17 kolommen. `existing.update(given)` in de fake zet daarbij `lat` en `lon` op `None`. Klopt.
- Testplan AC-5 (N-8): elke `seed` heeft nu `id` en `name`. De `select`-projectie van de fake vult ontbrekende kolommen met `None`.
- `_SpotId`, `_MonthDay` en `_LocalTime` als before-validators met `re.fullmatch` en `[0-9]`: een afsluitende newline en fullwidth-cijfers worden geweigerd (E40), en een NUL-teken ook. `_NonBlankStr` controleert eerst op NUL en pas daarna of de string leeg is. `"\x00".strip()` laat de NUL staan, dus E41 krijgt de NUL-melding.
- Het label gebruikt alleen `id.isprintable()`, en `errors(include_input=False)` neemt geen invoer op in de melding. Daardoor zijn alle foutregels voor E40 en E41 één regel (`test_error_lines_are_single_line`).
- PyYAML vertaalt `\0` in een double-quoted scalar naar U+0000. De reader-controle op niet-afdrukbare tekens kijkt naar de ruwe stream, en daar staat de escape, niet het teken zelf. E41 is dus via YAML te maken. Fullwidth-cijfers (U+FF10–FF19) vallen binnen het toegestane bereik van de reader.
- AC-3-tabel na de revisie: bij `Bad_Id` is de id afdrukbaar, dus het label bevat `Bad_Id`. In het geval `from_time` zonder `to_time` bevat de regel `season[0]` en `to_time` (de melding van de after-validator). `test_three_errors_in_one_exception` geeft in deze volgorde 2 veldfouten (`id`, `status`) en 1 regelovertreding (`lon`).
- Harde regels: geen kosten, geen externe API's, geen scraping, geen verzonnen spotdata, offshore blijft `no_go` (A4), geen secrets in de uitvoer (`test_sync_output_has_no_secrets`).
- Scope: er zijn geen nieuwe bestanden of functies buiten de WP bijgekomen. `tests/fakes.py` blijft ongewijzigd.

## Gecontroleerde bronnen
- https://raw.githubusercontent.com/yaml/pyyaml/main/lib/yaml/constructor.py (`construct_object` met caching in `constructed_objects`, controle "found unhashable key" in `BaseConstructor.construct_mapping`, `SafeConstructor.construct_mapping` met `flatten_mapping`, generator `construct_yaml_seq`)
- Lokaal: `ingest/tests/fakes.py` (`FakeSupabase.__init__`, `seed`, `select`, `upsert`, `_defaults`), `docs/wp/WP-02/review.md` (ronde 1)
