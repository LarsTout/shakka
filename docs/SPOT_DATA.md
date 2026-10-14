# Spotdata invullen

Handleiding voor het invullen van de spotprofielen in `data/spots.yaml`. De startset bevat 25 spots met alleen `id`, `name` en `verified: false`. De rest vul jij in, stap voor stap en alleen wat je zeker weet.

## 1. Doel en werkwijze
1. Vul profielen in `data/spots.yaml`.
2. Controleer ze: `cd ingest && uv run shakka spots validate`. Het commando leest geen `.env` en raakt de database niet.
3. Commit via een PR. CI draait dezelfde validatie.
4. Na de merge draai je `cd ingest && uv run shakka spots sync` (met `.env` naar het remote project, nadat `supabase db push` van WP-01 is gedaan).

Regels voor sync:
- De YAML is de bron van waarheid. Sync overschrijft wijzigingen die je in het Supabase-dashboard maakt.
- Sync schrijft alleen spots die nieuw of gewijzigd zijn. Een tweede run schrijft niets.
- Sync verwijdert nooit iets. Staat een spot wel in de database maar niet meer in de YAML, dan krijg je een `warn`-regel. Een spot verwijderen kan alleen handmatig, en dat verwijdert via de cascade ook favorieten, alertregels, forecasts en evaluaties.
- Hernoem id's niet. Favorieten van gebruikers verwijzen ernaar; een hernoemde id laat de oude rij als wees achter.

Let op: `spots validate` leest altijd `data/spots.yaml` (of `--path`), terwijl `spots sync` zonder `--path` de env-variabele `SPOTS_PATH` volgt als die gezet is. Wie `SPOTS_PATH` zet, geeft bij `validate` hetzelfde bestand mee met `--path`. Sync valideert zelf ook volledig voordat er iets geschreven wordt.

## 2. Basisregels
- Vul niets in wat je niet zeker weet. Laat het veld leeg (weglaten of `null`) en houd `verified: false`.
- Datums en tijden altijd tussen aanhalingstekens: `"05-01"`, `"10:00"`. YAML leest `10:00` zonder aanhalingstekens als het getal 600 (sexagesimale notatie). `09:30` blijft toevallig tekst, maar vertrouw daar niet op.
- Getallen zonder aanhalingstekens (`290`, niet `"290"`). Hele getallen zonder decimalen (`290`, niet `290.0`).
- `true` en `false` voor `verified`. Geen `yes` of `no`.
- Geen lege tekst (`""`). Wil je niets invullen, laat het veld dan weg.
- Inspringen met spaties, nooit met tabs.
- Dubbele sleutels binnen een spot en onbekende velden worden geweigerd.

## 3. Veldentabel
| Veld | Type | Verplicht | Waarden | Betekenis |
|---|---|---|---|---|
| `id` | tekst | ja | kleine letters, cijfers en enkele streepjes (`wijk-aan-zee`) | Vaste sleutel van de spot. Nooit hernoemen. |
| `name` | tekst | ja | niet leeg | Weergavenaam. |
| `region` | tekst | nee | niet leeg | Regio, bijvoorbeeld een provincie of waterlichaam. |
| `lat` | getal | nee | 50.7 t/m 53.7 | Breedtegraad. Samen met `lon`. |
| `lon` | getal | nee | 3.2 t/m 7.3 | Lengtegraad. Samen met `lat`. |
| `shore_normal_deg` | geheel getal | nee | 0 t/m 359 | Richting loodrecht op de kust, van land naar water (zie 4). |
| `ridable_dirs` | lijst | nee | minstens 1 bereik `{from, to}`, 0 t/m 359 | Optionele override van de rijdbare windrichtingen (zie 5). |
| `hazards` | tekst | nee | niet leeg | Gevaren, bijvoorbeeld stroming of obstakels. |
| `tide_sensitive` | tekst | nee | `none` (standaard), `prefer_low`, `prefer_high`, `avoid_low` | Gevoeligheid voor getij (zie 7). |
| `tide_min_level_cm` | geheel getal | nee | -300 t/m 300 | Minimale waterstand in cm t.o.v. NAP. Alleen als `tide_sensitive` niet `none` is. |
| `rws_station` | tekst | nee | niet leeg | Code van het Rijkswaterstaat-getijstation. |
| `season` | lijst | nee | lijst van sluitingen (standaard leeg) | Periodes waarin kiten niet mag (zie 6). |
| `status` | tekst | nee | `allowed`, `limited`, `forbidden` | Juridische status van de spot. |
| `level` | tekst | nee | `beginner`, `intermediate`, `advanced` | Niveau dat de spot vraagt. |
| `default_min_kn` | geheel getal | nee | 5 t/m 40 | Standaard minimale windsnelheid in knopen voor deze spot. |
| `notes` | tekst | nee | niet leeg | Vrije opmerkingen. |
| `verified` | waar/onwaar | nee | `true`, `false` (standaard `false`) | Door Lars gecontroleerd (zie 8). |

`lat` en `lon` moeten samen ingevuld zijn of allebei leeg. Lege waarden (`null`) voor `season`, `tide_sensitive` en `verified` betekenen respectievelijk een lege lijst, `none` en `false`.

## 4. `shore_normal_deg`
Dit is de richting loodrecht op de kust, van land naar water. Ga op het strand staan en kijk recht naar het water: de kompasrichting waarin je kijkt is `shore_normal_deg`.

- Rekenvoorbeeld 1: een kust die op het westen ligt (je kijkt naar het westen) geeft **270**.
- Rekenvoorbeeld 2: een kustlijn die loopt van 20° naar 200° (NNO-ZZW), met het water aan de westkant. De twee loodlijnen zijn 20 + 90 = 110 en 20 - 90 = -70, dus 290. Het water ligt aan de westkant, dus 290.

Verband met de wind (meteorologisch: de richting waar de wind vandaan komt): wind uit `shore_normal_deg` is onshore. Indicatief, voor 270: 270 is onshore, 225 en 315 side-onshore, 180 en 0 sideshore, 135 en 45 side-offshore, 90 offshore. De exacte grenzen liggen vast in WP-05. Offshore en side-offshore zijn altijd `no_go`.

## 5. `ridable_dirs`
Optionele override voor meren, dijken en dergelijke waar de kustrichting niet genoeg zegt.
- Bereiken lopen met de klok mee, beide grenzen inclusief.
- Over het noorden kan: `{from: 200, to: 20}` is 200 t/m 359 en 0 t/m 20.
- `from` gelijk aan `to` is precies een graad.
- Leeg laten (weglaten of `null`) betekent geen override. Een lege lijst `[]` wordt geweigerd.
- Een override beperkt alleen. Offshore en side-offshore blijven `no_go`, ook als ze binnen een bereik vallen.

```yaml
ridable_dirs: [{from: 200, to: 20}, {from: 90, to: 120}]
```

## 6. `season`
Periodes waarin kiten niet mag, in lokale tijd (`Europe/Amsterdam`). Begin en einde zijn inclusief.

(a) Een hele periode (de sluiting geldt de hele dag):
```yaml
season: [{start: "05-01", end: "09-30"}]
```
(b) Met tijdvenster. `from_time` en `to_time` zijn allebei ingevuld of allebei leeg, en `from_time` ligt voor `to_time`. Kiten is verboden van `from_time` (inclusief) tot `to_time` (exclusief), op elke dag binnen de periode. Vensters over middernacht zijn niet toegestaan.
```yaml
season: [{start: "05-01", end: "09-30", from_time: "10:00", to_time: "18:00", note: "toelichting"}]
```
(c) Over de jaargrens: een `start` na het `end` loopt door de jaarwisseling.
```yaml
season: [{start: "11-01", end: "02-28"}]
```
(d) Meerdere regels:
```yaml
season:
  - {start: "05-01", end: "05-31"}
  - {start: "07-01", end: "08-31", from_time: "09:00", to_time: "12:00"}
```
`start` gelijk aan `end` is een dag. `"02-29"` is toegestaan.

## 7. Getij
`tide_sensitive`:
- `none`: getij speelt geen rol.
- `prefer_low`: laag water is beter.
- `prefer_high`: hoog water is beter.
- `avoid_low`: laag water vermijden.

`tide_min_level_cm` is de minimale waterstand in cm ten opzichte van NAP en mag alleen bij `tide_sensitive` anders dan `none`. Voor `rws_station` kies je de code met `shakka tides stations` (beschikbaar na WP-04).

## 8. Eisen voor `verified: true`
Verplicht ingevuld: `lat`, `lon`, `shore_normal_deg`, `status` en `level`, en `rws_station` als `tide_sensitive` niet `none` is. Daarnaast de inhoudelijke controle door Lars: de NKV-spotkaart, de gemeentelijke en lokale regels en de seizoenssluitingen. Alleen Lars zet `verified: true`. Alerts gelden alleen voor geverifieerde spots.

## 9. Volledig fictief voorbeeld
Dit is een verzonnen spot om het formaat te laten zien. Niet overnemen in `data/spots.yaml`.

```yaml
spots:
  - id: test-strand
    name: Teststrand
    region: Testregio
    lat: 52.0
    lon: 4.2
    shore_normal_deg: 290
    ridable_dirs: [{from: 200, to: 20}]
    tide_sensitive: avoid_low
    tide_min_level_cm: -20
    rws_station: hoekvanholland
    season: [{start: "05-01", end: "09-30", from_time: "10:00", to_time: "18:00", note: "badseizoen"}]
    status: allowed
    level: intermediate
    default_min_kn: 14
    hazards: null
    notes: null
    verified: true
```

## 10. Foutmeldingen lezen
Elke fout staat op een eigen regel in de vorm `spots[<index>] (<id>): <veld>: <melding>`. De index begint bij 0 en telt de spots in het bestand. Alle fouten van alle spots komen in een keer.

Voorbeelden (fictieve fouten):
```
error   spots[3] (domburg): season[0].start: Value error, expected a quoted 'MM-DD' date, e.g. "05-01"
error   spots[7] (scheveningen): lon: required when lat is set
error   spots[9] (oostvoorne): shore_normal_deg: Input should be less than or equal to 359
```

Fouten in de YAML zelf ontstaan voordat er spots zijn en hebben dus geen spot-id. Ze noemen het regel- en kolomnummer:
```
error   spots.yaml: line 12, column 5: found duplicate key 'lat'
```
Zoek de spot via het regelnummer.
