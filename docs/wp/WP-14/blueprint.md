# Blueprint WP-14: Spotlijst en spotpagina
Status: DRAFT
Revisie: 1

## Doel
De PWA toont voor het eerst echte data, alleen uit Supabase (`spots`, `evaluations`, `tide_extremes`; RLS: `anon` mag lezen):
- `/`: lijst van alle spots met naam, regio, label "niet geverifieerd", een samenvatting van het oordeel voor de daglichturen van vandaag en morgen, en "Nog geen data" bij spots zonder evaluaties;
- `/spot/[id]`: per lokale dag een overzicht per uur met oordeel (tekst én kleur), wind en vlagen in kn, richtingspijl met windroos, label van de richtingsklasse, betrouwbaarheid en redenen als Nederlandse labels; daarnaast de getij-extremen per dag, profielinfo (status, seizoen, hazards, notes), een banner "niet geverifieerd", de versheid van de data (waarschuwing bij meer dan 3 uur oud) en `Attribution`;
- `/go?spot&start&end`: in M2 een redirect naar `/spot/{spot}`, bij ongeldige parameters naar `/`;
- `#lib/types.ts`, `#lib/data.ts`, `#lib/contracts.ts`, `#lib/time.ts` en `HourVerdict.svelte` als herbruikbare bouwstenen voor WP-12, WP-15, WP-16, WP-20 en WP-21.

Alle tijden in Europe/Amsterdam. Geen golven (WP-12), geen kaart (WP-15), geen favorieten (WP-16), geen persoonlijke limieten.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- **A1. Geen Supabase-typegeneratie; handgeschreven types plus een schematest.** `supabase gen types` vraagt de lokale stack (Docker) bij elke schemawijziging en een extra gegenereerd bestand. `#lib/types.ts` bevat de rijtypes met exact de kolomnamen uit de migratie. Een vitest-test (`schema-columns.test.ts`) leest `supabase/migrations/20261015090000_m1_schema.sql` en eist dat `SPOT_COLUMNS` en `EVALUATION_COLUMNS` precies de kolommen van `spots` en `evaluations` zijn, en dat `TIDE_EXTREME_COLUMNS` en `SUMMARY_COLUMNS` deelverzamelingen zijn. Een tweede test eist dat de TypeScript-unions voor redencodes, richtingsklassen en betrouwbaarheid exact gelijk zijn aan `data/contracts/*.json`. De supabase-client blijft ongetypeerd (`SupabaseClient`, WP-13); `data.ts` cast de rijen naar de rijtypes.
- **A2. Voorstel: oordeelslabels "Go", "Twijfel" en "Niet gaan".** Er is geen contractbestand voor `Verdict`-labels (WP-05 genereert alleen redenen, klassen en betrouwbaarheid). `go` → `Go` (gelijk aan de pushtitel "Go: …" van WP-08), `marginal` → `Twijfel`, `no_go` → `Niet gaan` (gelijk aan de tekst op `/over`). Ze staan in `#lib/labels.ts`. Een ander woord is één regel plus de tests.
- **A3. Donkere uren standaard verborgen.** De evaluatiejob slaat ook nachturen op (reden `dark`, altijd `no_go`, WP-05). Op de spotpagina zijn uren met de reden `dark` standaard verborgen; een knop "Toon ook donkere uren" (`aria-pressed`) laat ze zien. "Daglichturen" in de lijst zijn precies de uren zonder de reden `dark`. Er is geen eigen daglichtberekening in de browser.
- **A4. Tijdvak.** De spotpagina toont de uren van `floorHour(now)` tot lokale middernacht na dag 8 (vandaag plus 7 dagen); verstreken uren van vandaag niet. De lijst vat de uren samen van `floorHour(now)` tot het einde van morgen (lokaal). De getij-extremen worden geladen vanaf lokale middernacht vandaag tot hetzelfde einde.
- **A5. Versheid = het nieuwste `evaluated_at` van de geladen rijen.** De waarschuwing verschijnt als `now - nieuwste > 3 uur` (strikt; precies 3 uur is nog vers). Bekende beperking: de uurlijkse run evalueert ook als de forecast-ingest faalt (WP-11, E2), dus `evaluated_at` kan vers zijn terwijl de forecast ouder is. De app mag `forecast_hours` niet lezen (AC-6). Dit staat onder Risico's en "Gevolgen voor latere WP's" (WP-22).
- **A6. Laden via universele `+page.ts`-loads; de pagina's zijn puur presentatie.** De loads roepen `loadSpotList(now)` en `loadSpotPage(id, now)` uit `#lib/page-data.ts` aan. Die geven een gediscrimineerde unie terug (`ok`, `not_found`, `error`) in plaats van `error()` te gooien. Zo blijven alle teksten Nederlands (geen standaard-foutpagina van SvelteKit), en zijn de pagina's te testen door `+page.svelte` met fixturedata te renderen, zonder supabase-mock.
- **A7. Voorstel: Cloudflare Pages bouwt vanaf de repo-root.** `contracts.ts` importeert `data/contracts/*.json` buiten `web/` (contract van deze WP, A-14). De Cloudflare-documentatie zegt niet of bestanden buiten de "root directory" beschikbaar zijn tijdens de build, en communitymeldingen zeggen van niet. RUNBOOK §11.3 wordt daarom: root directory leeg (repo-root), build command `cd web && npm ci && npm run build`, output directory `web/build`. Lars heeft Pages nog niet ingericht (WP-13 AC-7 staat open), dus dit kost geen extra werk. Er komt geen kopie van de contractbestanden in `web/` (één bron van waarheid).
- **A8. Windroos-labels in TypeScript, met een pariteitstest.** `COMPASS_POINTS_NL` en `compassLabel` staan niet in een contractbestand. `#lib/labels.ts` krijgt dezelfde tabel en formule als `shakka.domain.direction.compass_label`; een vitest-test leest de tuple uit `ingest/src/shakka/domain/direction.py` en vergelijkt. Status-, getijvoorkeur- en getijtype-labels staan ook in `labels.ts`; waar Python al een label heeft (`TIDE_PREFERENCE_LABEL_NL`, `TIDE_KIND_LABEL_NL` in `messages.py`) is de tekst gelijk, met een hoofdletter.
- **A9. Paginering per 1000 rijen.** Supabase geeft standaard hoogstens 1000 rijen per request (`max_rows = 1000`, ook in `supabase/config.toml`). De lijst kan bij 25 spots al ruim 1000 evaluaties raken. `fetchAllPages` leest pagina's van 1000 met `.range()` tot een pagina korter is dan 1000, met een plafond van 50 pagina's (daarna `DataError`). Voorwaarde: `max_rows` blijft minstens 1000 (staat in de RUNBOOK).
- **A10. `/go` valideert streng op het formaat van WP-08.** `spot` is een slug (`^[a-z0-9]+(-[a-z0-9]+)*$`, hoogstens 100 tekens); `start` en `end` zijn exact `YYYY-MM-DDTHH:00:00Z`, een bestaand tijdstip, en `start < end`. Alles anders gaat naar `/`. Het window zelf wordt in M2 niet gebruikt (alleen de spot); WP-20 vervangt de route.
- **A11. Verversen na terugkeer.** Een geïnstalleerde PWA kan dagen later hervat worden met de oude pagina en de oude `now`; de versheidswaarschuwing zou dan ten onrechte ontbreken. Beide pagina's roepen daarom `refreshAll()` (kit 3, vervangt `invalidateAll`) aan als het document weer zichtbaar wordt en de data meer dan 10 minuten geleden geladen is. Een fout bij laden toont een knop "Opnieuw proberen" die ook `refreshAll()` aanroept.
- **A12. Geen nieuwe npm-packages.** Tijdzones via `Intl.DateTimeFormat` met `timeZone: 'Europe/Amsterdam'` (Node 24 en alle doelbrowsers hebben volledige ICU). Weekdag- en maandafkortingen uit eigen tabellen, gelijk aan WP-08 (`ma`…`zo`, `jan`, `feb`, `mrt`, …). Nergens `Date`-getters in lokale tijd (`getHours`, `toLocaleString`, …); een test bewaakt dat.
- **A13. Profielinfo op de spotpagina:** status, seizoenssluitingen, getijvoorkeur (met minimumwaterstand), getijstation, gevaren (`hazards`) en notities. Lege velden tonen "Niet ingevuld" (geen verzonnen data). `level` en `default_min_kn` worden niet getoond (niet gevraagd).
- **A14. Geen offline data.** De service worker van WP-13 laat Supabase-requests ongemoeid; offline toont een pagina de foutmelding met "Opnieuw proberen".
- **A15. Lijstvolgorde op naam** (`order=name`), zonder groepering per regio.

## Ontwerp

**Lagen.**
```
routes (+page.ts: één regel)  ──>  #lib/page-data.ts  ──>  #lib/data.ts  ──>  #lib/supabase.js (WP-13)
routes (+page.svelte)  ──>  components (HourVerdict, VerdictBadge, WindArrow, Freshness)
                       ──>  #lib/view.ts, #lib/labels.ts, #lib/contracts.ts, #lib/time.ts   (puur, geen I/O)
```
Alle logica die iets beslist (tijdzones, groeperen, samenvatten, versheid, labels, `/go`-validatie) zit in pure modules met tests vooraf. `data.ts` is de enige module die Supabase aanroept en leest alleen `spots`, `evaluations` en `tide_extremes`. De pagina's krijgen alles via `data` en roepen zelf niets aan behalve `refreshAll()`.

**Data.** `listSpots` (alle kolommen, op naam), `getSpot` (op id, `maybeSingle`; een id die geen slug is geeft `null` zonder query), `getEvaluations` (één spot, halfopen `[from, to)`, op `valid_at`), `getTideExtremes` (één station, getrimd, `[from, to)`, op `at`) en `getSpotSummaries(now)` (alle spots, alleen daglichturen via `.not('reasons', 'cs', '{dark}')`, van `floorHour(now)` tot het einde van morgen, gesorteerd op `spot_id` en `valid_at`, samengevat met de pure `summarizeSpots`). Alle lijstqueries gaan via `fetchAllPages` (A9). Elke Supabase-fout wordt een `DataError` met alleen de operatie en de foutcode, nooit de melding.

**Tijd.** `localParts` haalt jaar, maand, dag, uur en minuut in Europe/Amsterdam op met één gecachte `Intl.DateTimeFormat('en-GB', {timeZone, hourCycle: 'h23', …})`; de weekdag volgt uit `Date.UTC(y, m-1, d)`. Lokale dagen worden altijd als sleutel `YYYY-MM-DD` doorgegeven; "morgen" is `addDaysToKey(key, 1)` (kalenderrekenen, dus correct op de dag van 25 uur). `startOfLocalDay(key)` berekent het UTC-moment van lokale middernacht met een offsetcorrectie (Amsterdam wisselt om 01:00 UTC, nooit om middernacht). Uren beginnen in UTC op hele uren en Amsterdam wijkt hele uren af, dus `floorHour` in UTC is ook een heel lokaal uur.

**Pagina's.** De lijst toont per spot een link, regio, het label "niet geverifieerd" en twee regels ("Vandaag:", "Morgen:") met een oordeelsbadge en tekst, of "Nog geen data". De spotpagina groepeert de uren per lokale dag (`<section>` met kop "Vandaag (wo 15 jul)", "Morgen (…)" of "vr 17 jul"), toont per dag de getij-extremen en een `<ol>` met `HourVerdict` per uur. `HourVerdict` hangt alleen af van één `Evaluation`, zodat WP-21 hem kan hergebruiken. Kleur is nooit de enige drager: elke badge heeft tekst, en de pijl heeft een tekstalternatief.

**Waarom zo.** De pure modules maken de acceptatiecriteria toetsbaar zonder netwerk; de route-loads zijn één regel; de schema- en contracttests vangen drift tussen database, Python en TypeScript; en de UI verzint niets: elk leeg veld zegt dat het leeg is.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `web/tsconfig.json` | wijzigen | In `compilerOptions` erbij: `"resolveJsonModule": true`, `"esModuleInterop": true`. Verder ongewijzigd. |
| `web/vite.config.ts` | wijzigen | `import { searchForWorkspaceRoot } from 'vite';` en in het teruggegeven object `server: { fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../data/contracts'] } }`. Verder ongewijzigd. |
| `web/src/app.css` | wijzigen | Stijlen uit "Stijl" toevoegen; bestaande regels blijven. |
| `web/src/lib/types.ts` | aanmaken | Rijtypes, unions, kolomlijsten, `SpotSummary`, `DaySummary`. |
| `web/src/lib/contracts.ts` | aanmaken | Import van de drie JSON-bestanden, labels, `RIDABLE_DIR_CLASSES`. |
| `web/src/lib/labels.ts` | aanmaken | Oordeel-, status-, getijlabels, windroos, tekstformattering. |
| `web/src/lib/time.ts` | aanmaken | Lokale tijd, datumsleutels, `parseGoParams`. |
| `web/src/lib/view.ts` | aanmaken | Versheid, groeperen, zichtbare uren, getij per dag, samenvattingen. |
| `web/src/lib/data.ts` | aanmaken | Queries, `fetchAllPages`, `DataError`. |
| `web/src/lib/page-data.ts` | aanmaken | `loadSpotList`, `loadSpotPage`, paginatypes, `shouldRefreshOnResume`. |
| `web/src/lib/go.ts` | aanmaken | `goTarget`. |
| `web/src/lib/components/VerdictBadge.svelte` | aanmaken | Badge met tekst en kleur. |
| `web/src/lib/components/WindArrow.svelte` | aanmaken | SVG-windroos met pijl. |
| `web/src/lib/components/HourVerdict.svelte` | aanmaken | Eén uur. |
| `web/src/lib/components/Freshness.svelte` | aanmaken | "Bijgewerkt" en de verouderingswaarschuwing. |
| `web/src/routes/+page.ts` | aanmaken | Load van de lijst. |
| `web/src/routes/+page.svelte` | vervangen | Spotlijst (de placeholder van WP-13 verdwijnt). |
| `web/src/routes/spot/[id]/+page.ts` | aanmaken | Load van de spotpagina. |
| `web/src/routes/spot/[id]/+page.svelte` | aanmaken | Spotpagina. |
| `web/src/routes/go/+page.ts` | aanmaken | Redirect. |
| `web/src/routes/go/+page.svelte` | aanmaken | `<p>Doorsturen…</p>` (vangnet; wordt normaal niet getoond). |
| `web/test/helpers/fake-supabase.ts` | aanmaken | Nep-querybuilder die aanroepen vastlegt. |
| `web/test/fixtures/spot-data.ts` | aanmaken | Fixtures (zie Testplan). |
| `web/test/*.test.ts` | aanmaken | 12 testbestanden, zie Testplan. |
| `docs/RUNBOOK.md` | wijzigen | §11.3 (Pages vanaf de repo-root, A7), nieuw §11.7 (spotpagina en `/go`), §13.2 (`APP_BASE_URL`). |

Geen wijzigingen in `ingest/`, `supabase/`, `data/`, `.github/`, de service worker, de layout of `package.json`. `docs/STATUS.md` werkt de orchestrator bij.

## Interfaces en contracten

Imports van gedeelde code gaan via `#lib/<bestand>.js` (WP-13). Tijdstempels blijven in de rijtypes strings zoals PostgREST ze geeft (bijv. `2026-07-15T12:00:00+00:00`) en worden pas bij gebruik met `new Date(...)` geparsed.

### `web/src/lib/types.ts`
```ts
export const VERDICTS = ['go', 'marginal', 'no_go'] as const;
export type Verdict = (typeof VERDICTS)[number];

export const REASON_CODES = [
	'no_data', 'wind_too_light', 'wind_too_strong', 'wind_borderline', 'too_gusty', 'gusty',
	'offshore', 'side_offshore', 'direction_unknown', 'direction_not_ridable', 'dark',
	'season_closed', 'spot_forbidden', 'spot_limited', 'status_unknown', 'tide_too_low',
	'tide_unfavorable', 'tide_unknown', 'low_confidence'
] as const;
export type ReasonCode = (typeof REASON_CODES)[number];

export const DIR_CLASSES = ['onshore', 'side_onshore', 'sideshore', 'side_offshore', 'offshore'] as const;
export type DirClass = (typeof DIR_CLASSES)[number];

export const CONFIDENCES = ['high', 'medium', 'low'] as const;
export type Confidence = (typeof CONFIDENCES)[number];

export type SpotStatus = 'allowed' | 'limited' | 'forbidden';
export type SpotLevel = 'beginner' | 'intermediate' | 'advanced';
export type TideSensitivity = 'none' | 'prefer_low' | 'prefer_high' | 'avoid_low';
export type TideKind = 'high' | 'low';

export interface DirRange { from: number; to: number }
export interface SeasonClosure {
	start: string;            // 'MM-DD'
	end: string;              // 'MM-DD'
	from_time: string | null; // 'HH:MM'
	to_time: string | null;   // 'HH:MM'
	note: string | null;
}

/** Row of public.spots (all columns). */
export interface Spot {
	id: string;
	name: string;
	region: string | null;
	lat: number | null;
	lon: number | null;
	shore_normal_deg: number | null;
	ridable_dirs: DirRange[] | null;
	hazards: string | null;
	tide_sensitive: TideSensitivity;
	tide_min_level_cm: number | null;
	rws_station: string | null;
	season: SeasonClosure[];
	status: SpotStatus | null;
	level: SpotLevel | null;
	default_min_kn: number | null;
	notes: string | null;
	verified: boolean;
	updated_at: string;
}

/** Row of public.evaluations (all columns). */
export interface Evaluation {
	spot_id: string;
	valid_at: string;
	verdict: Verdict;
	reasons: ReasonCode[];
	wind_kn: number | null;
	gust_kn: number | null;
	dir_deg: number | null;
	dir_class: DirClass | null;
	confidence: Confidence | null;
	tide_level_cm: number | null;
	evaluated_at: string;
}

/** Row of public.tide_extremes without fetched_at. */
export interface TideExtreme {
	station: string;
	at: string;
	kind: TideKind;
	level_cm: number;
}

export type SummaryRow = Pick<Evaluation, 'spot_id' | 'valid_at' | 'verdict' | 'reasons' | 'evaluated_at'>;

/** Daylight hours (no 'dark' reason) of one local day, from floorHour(now). */
export interface DaySummary {
	date: string;               // local 'YYYY-MM-DD'
	go: number;
	marginal: number;
	no_go: number;
	best: Verdict | null;       // most favourable verdict of the day; null without hours
	first_go_at: string | null; // valid_at of the first go hour
}

export interface SpotSummary {
	spot_id: string;
	today: DaySummary;
	tomorrow: DaySummary;
	latest_evaluated_at: string; // max evaluated_at of the summarised rows
}

export const SPOT_COLUMNS = [
	'id', 'name', 'region', 'lat', 'lon', 'shore_normal_deg', 'ridable_dirs', 'hazards',
	'tide_sensitive', 'tide_min_level_cm', 'rws_station', 'season', 'status', 'level',
	'default_min_kn', 'notes', 'verified', 'updated_at'
] as const;
export const EVALUATION_COLUMNS = [
	'spot_id', 'valid_at', 'verdict', 'reasons', 'wind_kn', 'gust_kn', 'dir_deg', 'dir_class',
	'confidence', 'tide_level_cm', 'evaluated_at'
] as const;
export const TIDE_EXTREME_COLUMNS = ['station', 'at', 'kind', 'level_cm'] as const;
export const SUMMARY_COLUMNS = ['spot_id', 'valid_at', 'verdict', 'reasons', 'evaluated_at'] as const;
```
`SpotSummary` en `Spot` zijn ook de props van `MapView` in WP-15.

### `web/src/lib/contracts.ts`
```ts
import reasonCodesJson from '../../../data/contracts/reason_codes.json';
import dirClassesJson from '../../../data/contracts/dir_classes.json';
import confidenceJson from '../../../data/contracts/confidence.json';

export const UNKNOWN_REASON_LABEL = 'Onbekende reden';
export const UNKNOWN_DIR_CLASS_LABEL = 'Onbekende richtingsklasse';
export const UNKNOWN_CONFIDENCE_LABEL = 'Onbekend';

/** Codes in file order. */
export const CONTRACT_REASON_CODES: readonly string[];
export const CONTRACT_DIR_CLASSES: readonly string[];
export const CONTRACT_CONFIDENCES: readonly string[];
/** Codes with ridable: true in dir_classes.json, in file order. */
export const RIDABLE_DIR_CLASSES: readonly DirClass[];

/** Dutch label; never the raw code. Unknown code -> UNKNOWN_REASON_LABEL. */
export function reasonLabel(code: string): string;
/** 'no_go' | 'marginal' from the file; unknown code -> null. */
export function reasonEffect(code: string): Verdict | null;
export function dirClassLabel(code: string): string;   // unknown -> UNKNOWN_DIR_CLASS_LABEL
export function confidenceLabel(code: string): string; // unknown -> UNKNOWN_CONFIDENCE_LABEL
```
Bij het laden van de module valideert een interne functie `itemsOf(json, name)` de vorm `{"_generated": string, "items": [...]}` en per item `code` (niet-lege string) en `label_nl` (niet-lege string na `trim`); bij `reason_codes` ook `effect ∈ {no_go, marginal}` en bij `dir_classes` `ridable` als boolean. Een fout geeft `throw new Error('contract <name> is malformed')`. De labels gaan in `Map<string, string>`'s. `RIDABLE_DIR_CLASSES` wordt gecast naar `DirClass[]` (de contracttest bewaakt de gelijkheid).

### `web/src/lib/labels.ts`
```ts
export const VERDICT_LABEL_NL: Record<Verdict, string> = { go: 'Go', marginal: 'Twijfel', no_go: 'Niet gaan' };
export const STATUS_LABEL_NL: Record<SpotStatus, string> = {
	allowed: 'Toegestaan', limited: 'Beperkt toegestaan', forbidden: 'Verboden'
};
export const STATUS_UNKNOWN_NL = 'Onbekend (nog niet ingevuld)';
export const TIDE_SENSITIVITY_LABEL_NL: Record<TideSensitivity, string> = {
	none: 'Geen voorkeur', prefer_low: 'Voorkeur laagwater',
	prefer_high: 'Voorkeur hoogwater', avoid_low: 'Liever geen laagwater'
};
export const TIDE_KIND_LABEL_NL: Record<TideKind, string> = { high: 'Hoogwater', low: 'Laagwater' };
export const NOT_FILLED_NL = 'Niet ingevuld';
export const COMPASS_POINTS_NL = ['N', 'NNO', 'NO', 'ONO', 'O', 'OZO', 'ZO', 'ZZO',
	'Z', 'ZZW', 'ZW', 'WZW', 'W', 'WNW', 'NW', 'NNW'] as const;

export function verdictLabel(v: Verdict): string;
export function statusLabel(s: SpotStatus | null): string;           // null -> STATUS_UNKNOWN_NL
/** COMPASS_POINTS_NL[Math.floor((((deg % 360) + 360) % 360 + 11.25) / 22.5) % 16]  (same as Python compass_label) */
export function compassLabel(deg: number): string;
/** Math.floor(x + 0.5) as string (same as WP-08 _kn). */
export function formatKn(x: number): string;
/** 0 -> '0', otherwise with sign: '+95', '-70' (same as WP-08). */
export function formatLevelCm(cm: number): string;
/** wind null -> 'Wind onbekend'; else '18 kn, vlagen 24 kn' or '18 kn, vlagen onbekend'. */
export function windText(windKn: number | null, gustKn: number | null): string;
/** deg null -> 'Richting onbekend'; else 'Wind uit WZW (250°)'. */
export function directionText(deg: number | null): string;
/** '1 mei t/m 30 sep', plus ', 10:00–18:00' with times, plus ' (note)' with a note. En dash U+2013. */
export function seasonText(c: SeasonClosure): string;
/** 'Hoogwater 11:10 (+95 cm)' in local time. */
export function tideText(t: TideExtreme): string;
```
`seasonText` gebruikt `MONTH_ABBR_NL` uit `time.ts` en `Number(dd)` voor de dag (`'05-01'` → `1 mei`). Een ongeldige `MM-DD` (komt niet voor, WP-02 valideert) geeft de ruwe tekst terug in plaats van te gooien.

### `web/src/lib/time.ts`
```ts
export const LOCAL_TZ = 'Europe/Amsterdam';
export const WEEKDAY_ABBR_NL = ['ma', 'di', 'wo', 'do', 'vr', 'za', 'zo'] as const;   // ISO 1..7
export const WEEKDAY_NL = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag'] as const;
export const MONTH_ABBR_NL = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'] as const;
export const MONTH_NL = ['januari', 'februari', 'maart', 'april', 'mei', 'juni', 'juli', 'augustus',
	'september', 'oktober', 'november', 'december'] as const;

export type LocalPattern = 'time' | 'day' | 'dayLong' | 'dateTime' | 'dateKey';
export interface LocalParts { year: number; month: number; day: number; hour: number; minute: number; isoWeekday: number }

/** Wall-clock parts in Europe/Amsterdam. RangeError on an invalid Date. */
export function localParts(date: Date): LocalParts;
/** 'time' -> '14:00'; 'day' -> 'wo 15 jul'; 'dayLong' -> 'woensdag 15 juli';
 *  'dateTime' -> 'wo 15 jul 14:00'; 'dateKey' -> '2026-07-15'. All in Europe/Amsterdam. */
export function formatLocal(date: Date, pattern: LocalPattern): string;
export function localDateKey(date: Date): string;                        // formatLocal(date, 'dateKey')
/** Calendar arithmetic on 'YYYY-MM-DD' (no time zone involved). RangeError on a malformed key. */
export function addDaysToKey(key: string, days: number): string;
/** UTC instant of local midnight at the start of `key`. RangeError on a malformed key. */
export function startOfLocalDay(key: string): Date;
/** 'day' -> 'wo 15 jul', 'dayLong' -> 'woensdag 15 juli' for a date key. */
export function formatDateKey(key: string, pattern: 'day' | 'dayLong'): string;
/** Start of the UTC hour (= a whole local hour in Amsterdam). */
export function floorHour(date: Date): Date;

export interface GoParams { spot: string; start: Date; end: Date }
/** Parses /go?spot&start&end as produced by WP-08 build_go_url. null when anything is invalid (A10). */
export function parseGoParams(url: URL): GoParams | null;
```
Implementatieregels:
- `localParts`: één module-level `new Intl.DateTimeFormat('en-GB', { timeZone: LOCAL_TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })`, dan `formatToParts`. `isoWeekday = ((new Date(Date.UTC(year, month - 1, day)).getUTCDay() + 6) % 7) + 1`. `Number.isNaN(date.getTime())` → `RangeError('invalid date')`.
- Datumsleutel: regex `^(\d{4})-(\d{2})-(\d{2})$` en de roundtrip `new Date(Date.UTC(y, m-1, d)).toISOString().slice(0, 10) === key`, anders `RangeError`.
- `startOfLocalDay(key)`: `guess = Date.UTC(y, m-1, d)`; `off(t) = Date.UTC(parts(t).year, month-1, day, hour, minute) - floorMinute(t)`; `t1 = guess - off(guess)`; `t2 = guess - off(t1)`; resultaat `new Date(off(t1) === off(guess) ? t1 : t2)`.
- `floorHour(d) = new Date(Math.floor(d.getTime() / 3_600_000) * 3_600_000)`.
- `parseGoParams(url)`:
  1. `spot = url.searchParams.get('spot')`, `start = …get('start')`, `end = …get('end')` (eerste waarde bij dubbele parameters);
  2. een ervan `null` → `null`;
  3. `spot` matcht niet `^[a-z0-9]+(-[a-z0-9]+)*$` of is langer dan 100 tekens → `null`;
  4. `start` of `end` matcht niet `^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$` → `null`;
  5. `s = new Date(start)`; ongeldig of `s.toISOString() !== start.replace('Z', '.000Z')` (vangt `2026-02-30`, uur `24`) → `null`; idem `end`;
  6. `s >= e` → `null`;
  7. anders `{ spot, start: s, end: e }`. Andere parameters worden genegeerd.

### `web/src/lib/view.ts`
```ts
export const STALE_AFTER_MS = 3 * 60 * 60 * 1000;

/** Max evaluated_at; null for an empty list. */
export function latestEvaluatedAt(rows: ReadonlyArray<Pick<Evaluation, 'evaluated_at'>>): Date | null;
/** latest !== null && now - latest > STALE_AFTER_MS (strict). */
export function isStale(latest: Date | null, now: Date): boolean;

export function isDark(e: Pick<Evaluation, 'reasons'>): boolean;            // reasons includes 'dark'
export interface DayGroup { dateKey: string; hours: Evaluation[] }
/** Sorted by valid_at, grouped by local date key, groups in date order. */
export function groupByLocalDay(evals: readonly Evaluation[]): DayGroup[];
/** showDark ? all hours : hours without 'dark'. */
export function visibleHours(hours: readonly Evaluation[], showDark: boolean): Evaluation[];
/** Extremes whose local date key equals dateKey, sorted by at. */
export function tidesForDay(tides: readonly TideExtreme[], dateKey: string): TideExtreme[];
/** todayKey -> 'Vandaag (wo 15 jul)', todayKey+1 -> 'Morgen (do 16 jul)', else 'vr 17 jul'. */
export function dayHeading(dateKey: string, todayKey: string): string;

/** One SpotSummary per spot that has at least one row in [floorHour(now), end of tomorrow) without 'dark'.
 *  Rows outside that range or with 'dark' are ignored. */
export function summarizeSpots(rows: readonly SummaryRow[], now: Date): Record<string, SpotSummary>;
/** Text after 'Vandaag: ' / 'Morgen: ' (see rules). */
export function daySummaryText(d: DaySummary, isToday: boolean): string;
/** Max latest_evaluated_at over all summaries; null when empty. */
export function latestOfSummaries(s: Record<string, SpotSummary>): Date | null;
```
Regels:
- `summarizeSpots`: `todayKey = localDateKey(now)`, `tomorrowKey = addDaysToKey(todayKey, 1)`, `from = floorHour(now)`, `to = startOfLocalDay(addDaysToKey(todayKey, 2))`. Per rij met `from <= valid_at < to` en zonder `dark`: tel bij de dag van `localDateKey(valid_at)`. `best`: `go` als `go > 0`, anders `marginal` als `marginal > 0`, anders `no_go` als `no_go > 0`, anders `null`. `first_go_at`: de `valid_at` met de vroegste tijd onder de go-uren (vergelijk op `Date`, niet op string). Een dag zonder rijen heeft alle tellers 0, `best = null`, `first_go_at = null` en `date` gezet.
- `daySummaryText(d, isToday)`, met `t = formatLocal(new Date(d.first_go_at), 'time')`:
  - `go + marginal + no_go === 0` → `isToday ? 'geen daglichturen meer' : 'nog geen data'`;
  - `go > 0` → `` `${go} uur go vanaf ${t}` `` plus `` `, ${marginal} uur twijfel` `` als `marginal > 0`;
  - `marginal > 0` → `` `${marginal} uur twijfel, geen go` ``;
  - anders → `'niet gaan'`.

### `web/src/lib/data.ts`
```ts
import { supabase } from '#lib/supabase.js';

export const PAGE_SIZE = 1000;   // Supabase default max_rows
export const MAX_PAGES = 50;

export class DataError extends Error {
	readonly operation: string;
	readonly code: string | null;
	constructor(operation: string, code: string | null);   // message: `${operation} failed`
}

interface Rangeable { range(from: number, to: number): PromiseLike<{ data: unknown[] | null; error: { code?: string } | null }> }
/** Calls build() per page with .range(offset, offset + pageSize - 1) until a page is shorter than pageSize.
 *  error -> DataError(operation, error.code ?? null); more than maxPages full pages -> DataError(operation, 'too_many_rows'). */
export async function fetchAllPages<T>(operation: string, build: () => Rangeable,
	pageSize?: number, maxPages?: number): Promise<T[]>;

export function listSpots(): Promise<Spot[]>;
export function getSpot(id: string): Promise<Spot | null>;
export function getEvaluations(spotId: string, from: Date, to: Date): Promise<Evaluation[]>;
export function getSpotSummaries(now: Date): Promise<Record<string, SpotSummary>>;
export function getTideExtremes(station: string, from: Date, to: Date): Promise<TideExtreme[]>;
```
Exacte queries (volgorde van de aanroepen ligt vast; de tests controleren hem):

| Functie | Query |
|---|---|
| `listSpots()` | `fetchAllPages('listSpots', () => supabase.from('spots').select(SPOT_COLUMNS.join(',')).order('name', { ascending: true }).order('id', { ascending: true }))` |
| `getSpot(id)` | `id` matcht niet `^[a-z0-9]+(-[a-z0-9]+)*$` → `null` zonder query. Anders `supabase.from('spots').select(SPOT_COLUMNS.join(',')).eq('id', id).maybeSingle()`; `error` → `DataError('getSpot', code)`; `data` (of `null`). |
| `getEvaluations(spotId, from, to)` | `fetchAllPages('getEvaluations', () => supabase.from('evaluations').select(EVALUATION_COLUMNS.join(',')).eq('spot_id', spotId).gte('valid_at', from.toISOString()).lt('valid_at', to.toISOString()).order('valid_at', { ascending: true }))` |
| `getTideExtremes(station, from, to)` | `s = station.trim()`; leeg → `[]` zonder query. Anders `fetchAllPages('getTideExtremes', () => supabase.from('tide_extremes').select(TIDE_EXTREME_COLUMNS.join(',')).eq('station', s).gte('at', from.toISOString()).lt('at', to.toISOString()).order('at', { ascending: true }))` |
| `getSpotSummaries(now)` | `todayKey = localDateKey(now)`; `fetchAllPages('getSpotSummaries', () => supabase.from('evaluations').select(SUMMARY_COLUMNS.join(',')).gte('valid_at', floorHour(now).toISOString()).lt('valid_at', startOfLocalDay(addDaysToKey(todayKey, 2)).toISOString()).not('reasons', 'cs', '{dark}').order('spot_id', { ascending: true }).order('valid_at', { ascending: true }))`, daarna `summarizeSpots(rows, now)`. |

`data.ts` bevat geen `Array.from` (de AC-6-grep op `\.from(` zou die meetellen) en geen andere `.from(`-aanroep dan de vier hierboven, met een letterlijke tabelnaam.

### `web/src/lib/page-data.ts`
```ts
export const SPOT_PAGE_DAYS = 8;                    // today + 7
export const RESUME_REFRESH_MS = 10 * 60 * 1000;

export type SpotListData =
	| { kind: 'ok'; now: string; spots: Spot[]; summaries: Record<string, SpotSummary> }
	| { kind: 'error'; now: string };

export type SpotPageData =
	| { kind: 'ok'; now: string; spot: Spot; evaluations: Evaluation[]; tides: TideExtreme[] }
	| { kind: 'not_found'; now: string; id: string }
	| { kind: 'error'; now: string; id: string };

/** Promise.all([listSpots(), getSpotSummaries(now)]). Any throw -> console.warn('spot list load failed') and { kind: 'error' }. */
export function loadSpotList(now: Date): Promise<SpotListData>;
/** getSpot(id); null -> not_found. Then, with todayKey = localDateKey(now) and end = startOfLocalDay(addDaysToKey(todayKey, SPOT_PAGE_DAYS)):
 *  Promise.all([getEvaluations(spot.id, floorHour(now), end),
 *               station ? getTideExtremes(station, startOfLocalDay(todayKey), end) : []])
 *  with station = spot.rws_station?.trim() || null. Any throw -> console.warn('spot page load failed') and { kind: 'error' }. */
export function loadSpotPage(id: string, now: Date): Promise<SpotPageData>;
/** nowMs - Date.parse(loadedAtIso) > RESUME_REFRESH_MS */
export function shouldRefreshOnResume(loadedAtIso: string, nowMs: number): boolean;
```
`now` in de data is `now.toISOString()`. De `console.warn`-regels bevatten nooit de fouttekst of de id.

### `web/src/lib/go.ts`
```ts
/** '/spot/' + encodeURIComponent(spot) for valid params, otherwise '/'. */
export function goTarget(url: URL): string;
```

### Routes
- `src/routes/+page.ts`:
  ```ts
  import { loadSpotList } from '#lib/page-data.js';
  import type { PageLoad } from './$types';
  export const load: PageLoad = () => loadSpotList(new Date());
  ```
- `src/routes/spot/[id]/+page.ts`: `export const load: PageLoad = ({ params }) => loadSpotPage(params.id, new Date());`
- `src/routes/go/+page.ts`:
  ```ts
  import { redirect } from '@sveltejs/kit';
  import { goTarget } from '#lib/go.js';
  import type { PageLoad } from './$types';
  export const load: PageLoad = ({ url }) => {
  	redirect(307, goTarget(url));
  };
  ```
- Beide `+page.svelte`'s: `let { data }: PageProps = $props();` (`PageProps` uit `./$types`), `import { refreshAll } from '$app/navigation';`. In `onMount`: een `visibilitychange`-listener op `document` die `void refreshAll()` aanroept als `document.visibilityState === 'visible' && shouldRefreshOnResume(data.now, Date.now())`; de cleanup verwijdert de listener.

### `/` (`src/routes/+page.svelte`)
`<svelte:head><title>Spots · Shakka</title></svelte:head>`, `<h1>Spots</h1>`, `<p class="muted">Per spot het oordeel voor de daglichturen van vandaag en morgen, met de standaardgrenzen van de spot. Kies een spot voor het overzicht per uur.</p>`, dan:
- `kind === 'error'`: `<div class="banner" role="alert"><p>De spots konden niet worden geladen. Controleer je verbinding.</p><button type="button" onclick={() => refreshAll()}>Opnieuw proberen</button></div>`.
- `kind === 'ok'` en `spots.length === 0`: `<p>Er staan nog geen spots in de database.</p>`.
- anders: `<Freshness latest={latestOfSummaries(data.summaries)} now={new Date(data.now)} />` en `<ul class="spot-list">` met per spot (in de volgorde van `spots`):
  ```svelte
  <li class="spot-item" data-spot={spot.id}>
  	<a class="spot-link" href="/spot/{spot.id}">{spot.name}</a>
  	{#if spot.region}<span class="muted"> · {spot.region}</span>{/if}
  	{#if !spot.verified}<span class="badge-unverified">niet geverifieerd</span>{/if}
  	{#if summary}
  		<p class="day-summary">Vandaag: {#if summary.today.best}<VerdictBadge verdict={summary.today.best} />{/if} {daySummaryText(summary.today, true)}</p>
  		<p class="day-summary">Morgen: {#if summary.tomorrow.best}<VerdictBadge verdict={summary.tomorrow.best} />{/if} {daySummaryText(summary.tomorrow, false)}</p>
  	{:else}
  		<p class="no-data muted">Nog geen data</p>
  	{/if}
  </li>
  ```
  met `summary = data.summaries[spot.id]`.

### `/spot/[id]` (`src/routes/spot/[id]/+page.svelte`)
State: `let showDark = $state(false)`. Afgeleid: `now = new Date(data.now)`, `todayKey = localDateKey(now)`, `groups = groupByLocalDay(data.evaluations)`, `latest = latestEvaluatedAt(data.evaluations)`, `station = data.spot.rws_station?.trim() || null`.
- `kind === 'not_found'`: title `Spot niet gevonden · Shakka`; `<h1>Spot niet gevonden</h1><p>Deze spot bestaat niet (meer).</p><p><a href="/">Naar alle spots</a></p>`.
- `kind === 'error'`: title `Spot · Shakka`; `<h1>Spot</h1>` en de banner zoals op `/`, met de tekst `De gegevens konden niet worden geladen. Controleer je verbinding.`.
- `kind === 'ok'`, in deze volgorde:
  1. `<svelte:head><title>{spot.name} · Shakka</title></svelte:head>`; `<p><a href="/">Alle spots</a></p>`; `<h1>{spot.name}</h1>`; `{#if spot.region}<p class="muted">{spot.region}</p>{/if}`.
  2. Bij `!spot.verified`: `<div class="banner unverified" role="note"><p><strong>Niet geverifieerd.</strong> Dit spotprofiel is nog niet gecontroleerd. Richting, regels en getij kunnen ontbreken of onjuist zijn. Check ter plekke altijd de lokale regels.</p></div>`.
  3. `<p class="muted">Het oordeel gebruikt de standaardgrenzen van deze spot, niet je eigen alertinstellingen.</p>`
  4. `<Freshness latest={latest} {now} showUpdated />`.
  5. `groups.length === 0`: `<p class="no-data">Nog geen data voor deze spot.</p>`. Anders de knop `<button type="button" aria-pressed={showDark} onclick={() => (showDark = !showDark)}>{showDark ? 'Verberg donkere uren' : 'Toon ook donkere uren'}</button>` en per groep:
     ```svelte
     <section class="day" aria-labelledby="dag-{g.dateKey}">
     	<h2 id="dag-{g.dateKey}">{dayHeading(g.dateKey, todayKey)}</h2>
     	{#if station}
     		<p class="tides">Getij: {dayTides.length ? dayTides.map(tideText).join(' · ') : 'geen gegevens'}</p>
     	{/if}
     	{#if hours.length}
     		<ol class="hours">{#each hours as e (e.valid_at)}<li><HourVerdict evaluation={e} /></li>{/each}</ol>
     	{:else}
     		<p class="muted">Geen uren met daglicht.</p>
     	{/if}
     </section>
     ```
     met `dayTides = tidesForDay(data.tides, g.dateKey)` en `hours = visibleHours(g.hours, showDark)`.
  6. `<section class="spot-profile"><h2>Over deze spot</h2><dl>` met deze `dt`/`dd`-paren:
     - `Status` → `statusLabel(spot.status)`;
     - `Seizoenssluiting` → bij `season.length === 0` `Geen seizoenssluiting bekend`, anders `<ul>` met `seasonText` per regel;
     - `Getijvoorkeur` → `TIDE_SENSITIVITY_LABEL_NL[spot.tide_sensitive]`, plus `` `, minimaal ${formatLevelCm(x)} cm NAP` `` als `tide_min_level_cm` niet `null` is;
     - `Getijstation` → `station ?? NOT_FILLED_NL`;
     - `Gevaren` → `<span class="prewrap">{spot.hazards}</span>` of `NOT_FILLED_NL`;
     - `Notities` → idem met `spot.notes`.
  7. `<section class="sources"><h2>Bronnen</h2><Attribution /></section>` (volledige stand).

  Nergens `{@html}`; vrije tekst uit de database wordt alleen als tekst gerenderd.

### Componenten
- `VerdictBadge.svelte`: props `{ verdict: Verdict }`. Markup `<span class="verdict verdict-{verdict}" data-verdict={verdict}>{verdictLabel(verdict)}</span>`.
- `WindArrow.svelte`: props `{ deg: number | null }`. `<svg class="wind-arrow" viewBox="0 0 32 32" width="28" height="28" aria-hidden="true" focusable="false">` met een cirkel (`cx=16 cy=16 r=15`, `fill="none"`, `stroke="currentColor"`, `stroke-opacity="0.4"`), de letters `N`, `O`, `Z`, `W` (font-size 6, op (16,6), (27,18), (16,30), (5,18), `text-anchor="middle"`), en alleen bij `deg !== null` een `<g transform="rotate({(deg + 180) % 360} 16 16)">` met de schacht `<line x1="16" y1="24" x2="16" y2="10" stroke="currentColor" stroke-width="2" />` en de punt `<polygon points="16,6 12,12 20,12" fill="currentColor" />`. De pijl wijst dus waar de wind heen waait (wind uit 270 → `rotate(90 16 16)`, naar het oosten).
- `HourVerdict.svelte`: props `{ evaluation: Evaluation }`. Importeert alleen `contracts`, `labels`, `time`, `VerdictBadge` en `WindArrow` (geen data, geen spot), zodat WP-21 hem kan hergebruiken.
  ```svelte
  <div class="hour">
  	<time datetime={e.valid_at}>{formatLocal(new Date(e.valid_at), 'time')}</time>
  	<VerdictBadge verdict={e.verdict} />
  	<span class="wind">{windText(e.wind_kn, e.gust_kn)}</span>
  	<span class="direction"><WindArrow deg={e.dir_deg} /> {directionText(e.dir_deg)}</span>
  	<span class="dir-class">{e.dir_class ? dirClassLabel(e.dir_class) : 'Richtingsklasse onbekend'}</span>
  	<span class="confidence">Betrouwbaarheid: {e.confidence ? confidenceLabel(e.confidence) : 'onbekend'}</span>
  	{#if e.reasons.length}<ul class="reasons">{#each e.reasons as r (r)}<li>{reasonLabel(r)}</li>{/each}</ul>{/if}
  </div>
  ```
  De klasse komt altijd uit `dir_class`, nooit uit `dir_deg` (WP-05, A15); `dir_deg` is alleen informatie.
- `Freshness.svelte`: props `{ latest: Date | null; now: Date; showUpdated?: boolean }` (default `false`). `latest === null` → niets. `isStale(latest, now)` → `<div class="banner warning" role="alert"><p>Let op: deze verwachting is ouder dan 3 uur (bijgewerkt {formatLocal(latest, 'dateTime')}). De gegevens kunnen verouderd zijn.</p></div>`. Anders, bij `showUpdated`: `<p class="muted">Bijgewerkt: {formatLocal(latest, 'dateTime')}</p>`.

### Stijl (`web/src/app.css`, toevoegen)
- `.verdict { display: inline-block; padding: 0 0.4rem; border-radius: 0.25rem; color: #fff; font-weight: 600; }`, `.verdict-go { background: #1b7f3b; }`, `.verdict-marginal { background: #8a5a00; }`, `.verdict-no_go { background: #a4161a; }` (wit op deze kleuren heeft een contrast van minstens 5:1).
- `.badge-unverified { margin-left: 0.5rem; padding: 0 0.3rem; border: 1px solid #8a5a00; border-radius: 0.25rem; color: #8a5a00; font-size: 0.8rem; }`
- `.muted { color: var(--color-muted); }`, `.prewrap { white-space: pre-line; }`
- `.spot-list, .hours { list-style: none; padding: 0; margin: 0; }`, `.spot-item { padding: 0.75rem 0; border-bottom: 1px solid #ddd; }`, `.spot-link { font-weight: 600; }`, `.day-summary, .no-data { margin: 0.25rem 0 0; }`
- `.hour { display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #ddd; }`, `.hour time { font-weight: 600; min-width: 3rem; }`, `.reasons { flex-basis: 100%; margin: 0; padding-left: 1.25rem; font-size: 0.875rem; }`
- `.wind-arrow { vertical-align: middle; }`, `.day h2 { font-size: 1.1rem; margin-top: 1.5rem; }`, `.spot-profile dt { font-weight: 600; margin-top: 0.5rem; }`, `.spot-profile dd { margin-left: 0; }`
- `.banner.warning { background: #fdecea; border-color: #a4161a; }` (`.banner` bestaat al).

### `web/vite.config.ts` (alleen de toevoegingen)
```ts
import { searchForWorkspaceRoot } from 'vite';
// in the returned object, next to plugins and test:
server: {
	fs: {
		// contracts.ts imports ../data/contracts/*.json (outside web/); keep Vite's default root allowed.
		allow: [searchForWorkspaceRoot(process.cwd()), '../data/contracts']
	}
},
```
Vite schakelt de automatische workspace-root uit zodra `allow` gezet is; daarom staat `searchForWorkspaceRoot(process.cwd())` er expliciet in (Vite-docs).

### `docs/RUNBOOK.md`
- §11.3, de regel met root directory wordt: `framework preset "None", root directory leeg (repo-root), build command \`cd web && npm ci && npm run build\`, build output directory \`web/build\`. De app importeert \`data/contracts/*.json\` buiten \`web/\`; daarom bouwt Pages vanaf de repo-root (WP-14).` De rest van §11.3 blijft (inclusief `NODE_VERSION=24.22.0`; `web/.nvmrc` wordt vanaf de repo-root niet gelezen).
- Nieuw §11.7 **Spotlijst, spotpagina en `/go` (vanaf WP-14).** De app leest alleen `spots`, `evaluations` en `tide_extremes`. Het oordeel gebruikt de standaardgrenzen van de spot. "Ouder dan 3 uur" kijkt naar `evaluated_at`; die is ook vers als alleen de forecast-ingest faalt, dus controleer bij twijfel `ingest_runs` (§13.5). `/go?spot=…&start=…&end=…` stuurt in M2 door naar `/spot/<spot>`. De app pagineert per 1000 rijen; zet de Supabase-instelling "Max rows" (API settings) niet lager dan 1000.
- §13.2, de regel over `APP_BASE_URL` wordt: `de variable \`APP_BASE_URL\` op de productie-URL zonder pad of slash aan het eind (bijv. \`https://<project>.pages.dev\`), vanaf WP-14. Daarmee bevat elk alertbericht een werkende "ik ga"-link (\`/go\`).`

### Gevolgen voor latere WP's
- **WP-12:** voegt `getMarineHours` toe aan `data.ts` (en `marine_hours` aan de tabellentest `data-tables.test.ts`), breidt `SpotPageData` (`ok`) uit met `marine: MarineHour[]` en `loadSpotPage` met een derde query in de `Promise.all`. De golfregel komt in de spotpagina binnen de `<li>` na `<HourVerdict>`, gekoppeld op `valid_at`; `HourVerdict` zelf blijft ongewijzigd (WP-21 heeft geen golven nodig).
- **WP-15:** de `/`-data heeft al `spots: Spot[]` en `summaries: Record<string, SpotSummary>`, precies de props van `MapView`. De wissel lijst/kaart komt boven de `<ul class="spot-list">`; de lijst blijft de standaard.
- **WP-16:** de favorietenster komt in `.spot-item` (na de link) en in de kop van de spotpagina; gebruik `$session` (`undefined` = nog niet queryen).
- **WP-20:** vervangt `src/routes/go/+page.ts`; `parseGoParams` blijft het formaat bewaken. `goTarget` mag weg.
- **WP-21:** hergebruikt `HourVerdict` (props `{ evaluation }`), `VerdictBadge`, `getEvaluations` en `Attribution`.
- **WP-22:** de versheid is gebaseerd op `evaluated_at` (A5). Voorstel: een kolom met de `fetched_at` van de gebruikte forecast in `evaluations`, zodat de app eerlijk "verouderde forecast" kan tonen zonder `forecast_hours` te lezen. Egress door deze WP: de lijst ≈ 25 spots × ≈ 30 daglichturen × ≈ 130 bytes ≈ 0,1 MB per bezoek, de spotpagina ≈ 170 uren × ≈ 280 bytes ≈ 0,05 MB; verwaarloosbaar bij tientallen gebruikers.
- **WP-23:** deze WP voegt geen nieuwe origins toe; `connect-src` hoeft alleen Supabase te bevatten.
- **WORK_PACKAGES / WP-13:** "Nodig van Lars" bij WP-13 noemt root `web`; dat is door A7 achterhaald. Bijwerken door de orchestrator.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | Spot zonder evaluaties (geen coördinaten, nog geen forecast) | Lijst: "Nog geen data" (geen badge, geen fout). Spotpagina: "Nog geen data voor deze spot.", geen versheidsregel, profiel en bronnen wel. |
| E2 | Evaluaties alleen in het verleden (ingest ligt dagen stil) | Vallen buiten de query: hetzelfde als E1. |
| E3 | `evaluated_at` precies 3 uur oud | Geen waarschuwing (strikt `>`). 3 uur en 1 minuut: wel. |
| E4 | Klok van het apparaat loopt achter (`latest` in de toekomst) | `now - latest < 0`: geen waarschuwing. |
| E5 | Wintertijdnacht 25-10-2026: 00:00Z en 01:00Z | Beide in groep `2026-10-25`, beide getoond als `02:00`, geen fout (beide donker, dus standaard verborgen). |
| E6 | `now` = 2026-10-24T22:30Z (lokaal 25-10 00:30, dag van 25 uur) | Vandaag = `2026-10-25`, morgen = `2026-10-26` (kalenderrekenen, niet `now + 24 h`). |
| E7 | Zomertijdstart 29-03-2026 | `startOfLocalDay('2026-03-29')` = 2026-03-28T23:00Z, `startOfLocalDay('2026-03-30')` = 2026-03-29T22:00Z. |
| E8 | Na zonsondergang: vandaag geen daglichturen meer | Lijst: "Vandaag: geen daglichturen meer". Spotpagina: de dag verschijnt alleen als er rijen zijn; zijn ze allemaal donker, dan "Geen uren met daglicht." en de knop. |
| E9 | `wind_kn = null` | "Wind onbekend". `wind_kn = 0` → "0 kn, …". |
| E10 | `gust_kn = null` (onbekend, nooit 0; WP-05 A2) | "…, vlagen onbekend". |
| E11 | `dir_deg = null` | Geen pijl (alleen de roos), "Richting onbekend". |
| E12 | `dir_class = null` bij bekende `dir_deg` (geen `shore_normal_deg`) | "Richtingsklasse onbekend"; de klasse wordt niet afgeleid uit `dir_deg`. |
| E13 | `dir_deg = 90` met `dir_class = side_offshore` (grens, WP-05 A15) | Toont "Schuin aflandig" en "Niet gaan"; geen herberekening. |
| E14 | `confidence = null` (geen data) | "Betrouwbaarheid: onbekend". |
| E15 | Onbekende redencode (nieuwere database dan app) | "Onbekende reden", nooit de ruwe code. Idem richtingsklasse en betrouwbaarheid. |
| E16 | `reasons = []` (go) | Geen lijst met redenen. |
| E17 | Getijgevoelige spot zonder `rws_station`, of `rws_station` met witruimte | Zonder station: geen getijregel, geen query, "Getijstation: Niet ingevuld". Met witruimte: getrimd vóór de query. |
| E18 | Station gezet, geen extremen voor een dag | "Getij: geen gegevens". |
| E19 | Hoogwater rond middernacht | Komt in de dag van zijn lokale datum. |
| E20 | Lege `season`, `hazards`, `notes`, `status` | "Geen seizoenssluiting bekend", "Niet ingevuld", "Onbekend (nog niet ingevuld)". Niets verzonnen. |
| E21 | Meerregelige `hazards`/`notes`, of tekst met `<script>` | `white-space: pre-line`; Svelte escapet tekst, geen `{@html}`. |
| E22 | `/spot/Bad_ID` of `/spot/onbekend` | Geen slug: `getSpot` geeft `null` zonder query. Onbekend: `maybeSingle` geeft `null`. Beide: "Spot niet gevonden". |
| E23 | Netwerkfout of Supabase-fout | `{ kind: 'error' }`, Nederlandse melding, knop "Opnieuw proberen" (`refreshAll`). De Supabase-melding komt niet op de pagina of in de console. |
| E24 | Meer dan 1000 rijen voor de samenvatting | Tweede pagina via `.range(1000, 1999)`; meer dan 50 volle pagina's → `DataError('…', 'too_many_rows')` → foutmelding. |
| E25 | `/go` zonder parameters, met `spot=../x`, `spot=Test`, `start=2026-07-18T12:30:00Z`, `start=2026-02-30T12:00:00Z`, `start=2026-07-18T24:00:00Z`, `start=2026-07-18T12:00:00+00:00`, `start == end`, `start > end` | Redirect naar `/`. |
| E26 | `/go` met dubbele `spot`-parameter of extra parameters | Eerste waarde telt; extra parameters genegeerd. |
| E27 | `/go` met geldige parameters voor een spot die niet bestaat | Redirect naar `/spot/<spot>`, daar "Spot niet gevonden". |
| E28 | PWA na uren hervat | Bij `visibilitychange` naar zichtbaar en data ouder dan 10 minuten: `refreshAll()`, daarna klopt de versheid weer (A11). |
| E29 | Offline | Supabase-request faalt → E23. De shell komt uit de SW-cache (WP-13). |
| E30 | Gebruiker typt `/spot/test-strand/` (slash aan het eind) | SvelteKit-standaard (`trailingSlash: 'never'`) stuurt door. |
| E31 | Testomgeving in een andere tijdzone dan Amsterdam | Geen invloed: alles via `Intl` met expliciete `timeZone`; de test `no-local-date-getters` bewaakt dat er geen lokale getters zijn. |

## Testplan
Alle tests staan in `web/test/` en draaien met `npm test`. Tests voor pure logica komen vóór de implementatie: `contracts`, `labels`, `time`, `view`, `data` (met de nep-client), `page-data` en `go`. Mocks volgen het patroon van WP-13 (`vi.hoisted` plus `vi.mock('#lib/…js', …)`; als `#lib` in `vi.mock` niet oplost, het relatieve pad). Elk bestand met mocks heeft `beforeEach(() => vi.clearAllMocks())`. Pagina- en componenttests mocken `$app/navigation`: `vi.mock('$app/navigation', () => ({ refreshAll: nav.refreshAll }))` met `nav = vi.hoisted(() => ({ refreshAll: vi.fn() }))`.

### Fixtures (`web/test/fixtures/spot-data.ts`)
Alleen testdata (`test-strand`, `test-meer`, `teststation`; coördinaten 52,47 N / 4,57 O zijn testdata zoals in WP-05 A13), nooit in `data/spots.yaml`.
- `NOW_FRESH = '2026-07-15T12:30:00.000Z'` (lokaal wo 15 jul 14:30), `NOW_STALE = '2026-07-15T15:06:00.000Z'`, `EVALUATED_AT = '2026-07-15T12:05:00+00:00'`.
- `SPOT_UNVERIFIED: Spot`: `id 'test-strand'`, `name 'Teststrand'`, `region 'Testregio'`, `lat 52.47`, `lon 4.57`, `shore_normal_deg 270`, `ridable_dirs null`, `hazards 'Testgevaar: zandbank\nTweede regel'`, `tide_sensitive 'prefer_low'`, `tide_min_level_cm null`, `rws_station ' teststation '`, `season [{ start: '05-01', end: '09-30', from_time: '10:00', to_time: '18:00', note: null }]`, `status null`, `level null`, `default_min_kn null`, `notes null`, `verified false`, `updated_at '2026-07-01T00:00:00+00:00'`.
- `SPOT_VERIFIED: Spot`: als hierboven, maar `id 'test-meer'`, `name 'Testmeer'`, `verified true`, `status 'allowed'`, `rws_station null`, `tide_sensitive 'none'`, `season []`, `hazards null`, `notes 'Testnotitie'`.
- Evaluaties (`spot_id 'test-strand'`, `tide_level_cm null`, `evaluated_at EVALUATED_AT`):
  - `EVAL_GO`: `valid_at '2026-07-15T12:00:00+00:00'`, `go`, `[]`, wind `18.4`, gust `23.6`, dir `250`, `onshore`, `high`;
  - `EVAL_OFFSHORE`: `'2026-07-15T13:00:00+00:00'`, `no_go`, `['offshore']`, `15.2`, `19.8`, `90`, `offshore`, `medium`;
  - `EVAL_LOWCONF`: `'2026-07-15T14:00:00+00:00'`, `marginal`, `['low_confidence']`, `14.0`, `null`, `300`, `side_onshore`, `low`;
  - `EVAL_DARK`: `'2026-07-15T21:00:00+00:00'`, `no_go`, `['dark']`, `10.0`, `14.0`, `260`, `onshore`, `high`;
  - `EVAL_TOMORROW`: `'2026-07-16T08:00:00+00:00'`, `go`, `[]`, `17.0`, `21.0`, `255`, `onshore`, `high`.
- `TIDES`: `{ station: 'teststation', at: '2026-07-15T09:10:00+00:00', kind: 'high', level_cm: 95 }`, `{ …, at: '2026-07-15T15:40:00+00:00', kind: 'low', level_cm: -70 }`.
- `pageData(overrides)`: `{ kind: 'ok', now: NOW_FRESH, spot: SPOT_UNVERIFIED, evaluations: [EVAL_GO, EVAL_OFFSHORE, EVAL_LOWCONF, EVAL_DARK, EVAL_TOMORROW], tides: TIDES, ...overrides }`.
- `GO_URL_SUMMER = 'https://example.org/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z'` en `GO_URL_WINTER = 'https://example.org/go?spot=test-strand&start=2026-11-07T11%3A00%3A00Z&end=2026-11-07T14%3A00%3A00Z'` (exact de strings uit WP-08, `ingest/tests/message_fixtures.py`).

### Testbestanden

| Bestand | Tests |
|---|---|
| `contracts.test.ts` | **(AC-2)** Voor elke code in `reason_codes.json`, `dir_classes.json` en `confidence.json` (de bestanden via `node:fs` gelezen, los van de import): het label is niet leeg na `trim`, is niet gelijk aan de code, en is niet de fallback (`UNKNOWN_*`). Elk label is gelijk aan `label_nl` uit het bestand. `reasonLabel('bogus') === UNKNOWN_REASON_LABEL`, idem `dirClassLabel` en `confidenceLabel`. `RIDABLE_DIR_CLASSES` is exact `['onshore', 'side_onshore', 'sideshore']`. `reasonEffect('offshore') === 'no_go'`, `reasonEffect('gusty') === 'marginal'`, `reasonEffect('bogus') === null`. De sets `REASON_CODES`, `DIR_CLASSES` en `CONFIDENCES` uit `types.ts` zijn gelijk aan `CONTRACT_REASON_CODES`, `CONTRACT_DIR_CLASSES` en `CONTRACT_CONFIDENCES`, en `{effect} ∪ {'go'}` is gelijk aan `VERDICTS`. |
| `schema-columns.test.ts` (node) | Leest `../../supabase/migrations/20261015090000_m1_schema.sql`, pakt per tabel het blok van `create table public.<naam> (` tot de eerste regel `);`, en neemt de regels die matchen op `^  ([a-z_][a-z0-9_]*) ` met een naam die niet `constraint`, `primary`, `foreign`, `unique` of `check` is. `SPOT_COLUMNS` = kolommen van `spots` (als set en in dezelfde volgorde), `EVALUATION_COLUMNS` = kolommen van `evaluations` (idem), `TIDE_EXTREME_COLUMNS ⊆ tide_extremes`, `SUMMARY_COLUMNS ⊆ evaluations`. |
| `time.test.ts` | `formatLocal(new Date('2026-07-15T12:00:00Z'), 'time') === '14:00'` (CEST) en `'2026-01-15T12:00:00Z'` → `'13:00'` (CET); `'day'` → `'wo 15 jul'`; `'dayLong'` → `'woensdag 15 juli'`; `'dateTime'` → `'wo 15 jul 14:00'`; `'dateKey'` → `'2026-07-15'`; `'2026-07-14T22:30:00Z'` → dateKey `'2026-07-15'`; `2026-10-25T00:00Z` en `01:00Z` → beide `'02:00'`; `2026-03-29T01:00Z` → `'03:00'`; ongeldige `Date` → `RangeError`. `addDaysToKey('2026-12-31', 1) === '2027-01-01'`, `('2026-03-01', -1) === '2026-02-28'`, `('2026-10-25', 1) === '2026-10-26'`; `'2026-02-30'` → `RangeError`. `startOfLocalDay`: `'2026-07-15'` → `2026-07-14T22:00:00.000Z`, `'2026-01-15'` → `2026-01-14T23:00:00.000Z`, E7, `'2026-10-25'` → `2026-10-24T22:00:00.000Z`, `'2026-10-26'` → `2026-10-25T23:00:00.000Z`. `formatDateKey('2026-07-18', 'day') === 'za 18 jul'`. `floorHour(new Date('2026-07-15T12:30:45.5Z'))` → `12:00:00.000Z`. **(AC-5)** `parseGoParams(new URL(GO_URL_SUMMER))` → `{ spot: 'test-strand', start: 2026-07-18T12:00Z, end: 2026-07-18T16:00Z }` (vergelijk `getTime()`); `GO_URL_WINTER` idem; alle gevallen uit E25 en een ontbrekende `end` → `null`; E26 → eerste waarde; `spot` van 101 tekens → `null`. |
| `go-url-fixture.test.ts` (node) | **(AC-5, koppeling met WP-08)** Leest `../../ingest/tests/message_fixtures.py`, pakt het blok `URL_SUMMER = (` … `)` en `URL_WINTER = (` … `)`, en voegt de stringliterals (`/"([^"]*)"/g`) samen. Het resultaat is gelijk aan `GO_URL_SUMMER` en `GO_URL_WINTER`. Zo faalt deze test als WP-08 het formaat van `build_go_url` wijzigt. |
| `go.test.ts` | **(AC-5)** `goTarget(new URL(GO_URL_SUMMER)) === '/spot/test-strand'`; `goTarget(new URL('https://example.org/go'))` en de E25-gevallen → `'/'`. De route: `import { load } from '../src/routes/go/+page.ts'`; `load({ url: new URL(GO_URL_SUMMER) } as never)` gooit, en `isRedirect(e)` (uit `@sveltejs/kit`) is waar met `e.location === '/spot/test-strand'` en `e.status === 307`; met `https://example.org/go?spot=test-strand` gooit het een redirect naar `'/'`. |
| `labels.test.ts` | `compassLabel`: 0 → `N`, 11.24 → `N`, 11.25 → `NNO`, 250 → `WZW`, 359 → `N`, 360 → `N`, -10 → `N`. Pariteit: de tuple `COMPASS_POINTS_NL` uit `../../ingest/src/shakka/domain/direction.py` (regex op het blok tot `)`, dan `/"([^"]+)"/g`) is gelijk aan `COMPASS_POINTS_NL`. `formatKn(18.4) === '18'`, `(18.5) === '19'`, `(0) === '0'`. `formatLevelCm`: 0 → `'0'`, 95 → `'+95'`, -70 → `'-70'`. `windText(18.4, 23.6) === '18 kn, vlagen 24 kn'`, `(14, null) === '14 kn, vlagen onbekend'`, `(null, 20) === 'Wind onbekend'`. `directionText(250) === 'Wind uit WZW (250°)'`, `(null) === 'Richting onbekend'`. `seasonText` van de fixture → `'1 mei t/m 30 sep, 10:00–18:00'`; zonder tijden `'1 mei t/m 30 sep'`; `{ start: '11-01', end: '02-28', note: 'winter' }` → `'1 nov t/m 28 feb (winter)'`. `tideText(TIDES[0]) === 'Hoogwater 11:10 (+95 cm)'`, `TIDES[1]` → `'Laagwater 17:40 (-70 cm)'`. `statusLabel(null) === STATUS_UNKNOWN_NL`, `verdictLabel('no_go') === 'Niet gaan'`. |
| `view.test.ts` | `latestEvaluatedAt([])` → `null`; met twee rijen het maximum. `isStale`: `NOW_FRESH` en `EVALUATED_AT` → `false`; `NOW_STALE` → `true`; precies 3 uur (`'2026-07-15T15:05:00Z'`) → `false`; `latest` in de toekomst → `false`; `null` → `false`. `groupByLocalDay` op de fixture-evaluaties in willekeurige volgorde → twee groepen `2026-07-15` (4 uren, gesorteerd) en `2026-07-16`; E5 → één groep met twee uren. `visibleHours(…, false)` haalt `EVAL_DARK` weg, `true` laat hem staan. `tidesForDay(TIDES, '2026-07-15')` → beide, `'2026-07-16'` → `[]`; een extreme op `2026-07-15T22:30Z` valt in `2026-07-16`. `dayHeading`: vandaag → `'Vandaag (wo 15 jul)'`, morgen → `'Morgen (do 16 jul)'`, overmorgen → `'vr 17 jul'`. `summarizeSpots` met `now = NOW_FRESH` en rijen: `test-strand` 12:00Z go, 13:00Z go, 14:00Z marginal, 21:00Z `['dark']` no_go, `2026-07-16T08:00Z` no_go, `2026-07-17T10:00Z` go, `2026-07-15T11:00Z` go (vóór `floorHour`) → `today = { date: '2026-07-15', go: 2, marginal: 1, no_go: 0, best: 'go', first_go_at: '2026-07-15T12:00:00+00:00' }`, `tomorrow = { date: '2026-07-16', go: 0, marginal: 0, no_go: 1, best: 'no_go', first_go_at: null }`; een spot zonder rijen heeft geen sleutel; een spot met alleen een rij op 17-07 heeft geen sleutel. E6: met `now = 2026-10-24T22:30Z` zijn de datums `2026-10-25` en `2026-10-26`. `daySummaryText`: het `today` hierboven → `'2 uur go vanaf 14:00, 1 uur twijfel'`; alleen go → `'2 uur go vanaf 14:00'`; alleen marginal → `'1 uur twijfel, geen go'`; alleen no_go → `'niet gaan'`; leeg → `'geen daglichturen meer'` (vandaag) en `'nog geen data'` (morgen). `latestOfSummaries({})` → `null`. |
| `data.test.ts` | Met `test/helpers/fake-supabase.ts` en `vi.mock('#lib/supabase.js', () => ({ supabase: fake.client, initialUrlHash: '' }))`. Per functie de exacte reeks aanroepen uit de querytabel, inclusief `range(0, 999)`. `listSpots` geeft de rijen terug. `getSpot('Bad_ID')` → `null` en 0 aanroepen; `getSpot('test-strand')` met `data: null` → `null`. `getTideExtremes(' teststation ', …)` → `eq('station', 'teststation')`; `getTideExtremes('  ', …)` → `[]` en 0 aanroepen. `getSpotSummaries(new Date(NOW_FRESH))` → `gte('valid_at', '2026-07-15T12:00:00.000Z')`, `lt('valid_at', '2026-07-16T22:00:00.000Z')`, `not('reasons', 'cs', '{dark}')`, `order('spot_id', …)`, `order('valid_at', …)`, en het resultaat is `summarizeSpots(rows, now)`. Paginering: eerste antwoord 1000 rijen, tweede 3 → 1003 rijen en het tweede verzoek heeft `range(1000, 1999)`. `fetchAllPages('x', build, 2, 3)` met steeds 2 rijen → `DataError` met `code 'too_many_rows'`. Een antwoord `{ data: null, error: { code: '42501', message: 'secret detail' } }` → `DataError` met `operation`, `code '42501'`, en `message` zonder `'secret detail'`. |
| `data-tables.test.ts` (node) | **(AC-6)** Leest `src/lib/data.ts`. Alle treffers van `/\.from\(/g` zijn ook treffers van `/\.from\('(spots|evaluations|tide_extremes)'\)/g` (zelfde aantal), en er is minstens één treffer per tabel. |
| `page-data.test.ts` | Mockt `#lib/data.js` (`listSpots`, `getSpot`, `getEvaluations`, `getTideExtremes`, `getSpotSummaries`). `loadSpotPage('test-strand', new Date(NOW_FRESH))`: met `SPOT_UNVERIFIED` → `getEvaluations('test-strand', 2026-07-15T12:00Z, 2026-07-22T22:00Z)` en `getTideExtremes('teststation', 2026-07-14T22:00Z, 2026-07-22T22:00Z)`, resultaat `kind 'ok'` met `now === NOW_FRESH`. Met `SPOT_VERIFIED` (geen station) → `getTideExtremes` niet aangeroepen, `tides: []`. `getSpot` → `null` → `kind 'not_found'`. `getEvaluations` rejectet met `new Error('secret detail')` → `kind 'error'`, `console.warn` precies één keer aangeroepen en geen argument bevat `'secret detail'`. `loadSpotList` ok en error idem. `shouldRefreshOnResume(NOW_FRESH, Date.parse(NOW_FRESH) + 10*60*1000)` → `false`, `+ 10*60*1000 + 1` → `true`. |
| `hour-verdict.test.ts` | Rendert `HourVerdict` met `EVAL_GO`: `time` met tekst `14:00` en `datetime` `'2026-07-15T12:00:00+00:00'`, tekst `Go`, `18 kn, vlagen 24 kn`, `Wind uit WZW (250°)`, `Aanlandig`, `Betrouwbaarheid: Hoog`, geen `ul.reasons`; de `g` in de SVG heeft `transform` `rotate(70 16 16)`. Met `EVAL_OFFSHORE`: `[data-verdict="no_go"]` met tekst `Niet gaan`, `Aflandig`, `Aflandige wind: niet kiten`, en de tekst `offshore` staat niet in de component. Met `dir_deg: null, dir_class: null, confidence: null, wind_kn: null, reasons: ['no_data', 'direction_unknown'], verdict: 'no_go'`: `Wind onbekend`, `Richting onbekend`, `Richtingsklasse onbekend`, `Betrouwbaarheid: onbekend`, geen `g` met `transform`. |
| `spot-page.test.ts` | **(AC-3)** Rendert `src/routes/spot/[id]/+page.svelte` met `{ data: pageData() }` (cast naar de props als `svelte-check` `params` eist). (a) `screen.getByText('14:00', { selector: 'time' })` heeft `datetime` `'2026-07-15T12:00:00+00:00'`; (b) binnen `.hour` van dat uur staat de tekst `Go` als element (oordeel als tekst); (c) binnen `.hour` van `15:00`: `[data-verdict="no_go"]` met tekst `Niet gaan`, en de teksten `Aflandige wind: niet kiten` en `Aflandig`; (d) binnen `.hour` van `16:00` het label `Weermodellen zijn het oneens`; nergens de ruwe codes `offshore` of `low_confidence` als tekst (`queryByText` op exacte tekst); (e) `getByText(/niet geverifieerd/i)` bestaat; met `spot: SPOT_VERIFIED` niet; (f) met `now: NOW_STALE`: `getByRole('alert')` bevat `ouder dan 3 uur`; met `NOW_FRESH`: geen alert en wel `Bijgewerkt: wo 15 jul 14:05`; (g) een link met `href === 'https://open-meteo.com/'` (Attribution) en de tekst `Rijkswaterstaat`. Daarnaast: kop `Vandaag (wo 15 jul)` en `Morgen (do 16 jul)`; `23:00` staat er niet, na een klik op `Toon ook donkere uren` wel (en de knop heeft `aria-pressed="true"`); `Getij: Hoogwater 11:10 (+95 cm) · Laagwater 17:40 (-70 cm)`; de dag van morgen heeft `Getij: geen gegevens`; profiel: `Onbekend (nog niet ingevuld)`, `1 mei t/m 30 sep, 10:00–18:00`, `Voorkeur laagwater`, `teststation`, een element dat matcht op `/Testgevaar: zandbank/` (de tekst heeft twee regels) met klasse `prewrap`, en `Niet ingevuld` bij Notities. `evaluations: []` → `Nog geen data voor deze spot.` en geen alert. `{ kind: 'not_found', … }` → kop `Spot niet gevonden`. `{ kind: 'error', … }` → `role="alert"` met de foutmelding; een klik op `Opnieuw proberen` roept `refreshAll` één keer aan. Hervatten: met `now` 20 minuten vóór `Date.now()`, `document.visibilityState` op `'visible'` (`Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })`) en een `visibilitychange`-event → `refreshAll` aangeroepen; met `now` = `new Date().toISOString()` → niet. |
| `spot-list.test.ts` | **(AC-4)** Rendert `src/routes/+page.svelte` met `{ kind: 'ok', now: NOW_FRESH, spots: [SPOT_UNVERIFIED, SPOT_VERIFIED], summaries: { 'test-meer': S } }`, waarbij `S` de `SpotSummary` is uit `summarizeSpots` op rijen van `test-meer` (12:00Z go, 13:00Z go, 14:00Z marginal, 2026-07-16T08:00Z no_go). Het item `[data-spot="test-strand"]` bevat `Nog geen data` en `niet geverifieerd`, en de link `Teststrand` heeft `href="/spot/test-strand"`; er is geen `role="alert"`. Het item `test-meer` bevat geen `niet geverifieerd`, wel `Vandaag:` met badge `Go` en `2 uur go vanaf 14:00, 1 uur twijfel`, en `Morgen:` met badge `Niet gaan` en `niet gaan`. `spots: []` → `Er staan nog geen spots in de database.` `kind 'error'` → alert en `Opnieuw proberen` roept `refreshAll` aan. Met een summary waarvan `latest_evaluated_at` 4 uur vóór `now` ligt → alert met `ouder dan 3 uur`. |
| `no-local-date-getters.test.ts` (node) | Leest alle `.ts`- en `.svelte`-bestanden onder `src/` en eist dat geen ervan matcht op `/\.(getHours|getMinutes|getDate|getDay|getMonth|getFullYear|toLocaleString|toLocaleDateString|toLocaleTimeString)\(/` (A12). `getUTC*` mag. |

### `web/test/helpers/fake-supabase.ts`
```ts
export type Op = [name: string, ...args: unknown[]];
export interface Call { table: string; ops: Op[] }
export interface Response { data: unknown; error: { code?: string; message?: string } | null }
export function createFakeSupabase(): {
	client: { from(table: string): Builder };
	calls: Call[];
	/** Queue responses per table; an empty queue answers { data: [], error: null }. */
	respond(table: string, ...responses: Response[]): void;
	reset(): void;
};
```
De builder heeft `select`, `eq`, `gte`, `lt`, `not`, `order`, `range` en `maybeSingle`. Elke methode zet `[naam, ...args]` in `ops` en geeft de builder terug. De builder is thenable: `then(resolve, reject)` haalt het volgende antwoord van de rij van die tabel. Elke `from()` maakt een nieuwe `Call`.

### Per acceptatiecriterium
- **AC-1:** `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build` en vanuit de root `bash scripts/check-no-client-openmeteo.sh`; in CI via de bestaande job `web`.
- **AC-2:** `contracts.test.ts`.
- **AC-3:** `spot-page.test.ts` (a)–(g), ondersteund door `hour-verdict.test.ts`, `time.test.ts` en `view.test.ts`.
- **AC-4:** `spot-list.test.ts`.
- **AC-5:** `time.test.ts` (`parseGoParams`), `go.test.ts` (route en `goTarget`) en `go-url-fixture.test.ts` (fixture gelijk aan de WP-08-fixture).
- **AC-6:** de verifier draait letterlijk `grep -n "\.from(" web/src/lib/data.ts`; alle regels noemen `spots`, `evaluations` of `tide_extremes`. Automatisch: `data-tables.test.ts`.
- **AC-7:** `NEEDS_LARS`. Lars richt Pages in volgens de bijgewerkte RUNBOOK §11.3, zet de Actions-variable `APP_BASE_URL`, opent `/spot/<een ingevulde spot>` op de gedeployde site (actuele uren, "Bijgewerkt" van minder dan 3 uur geleden), en opent een `/go`-URL uit `uv run shakka admin alerts preview --user-id <id>` (die gebruikt `APP_BASE_URL` uit `.env`, zet die dus ook lokaal op de productie-URL) of handmatig gemaakt met `build_go_url`; die leidt naar de spotpagina.

Daarnaast blijven groen: alle bestaande webtests (de layout, de guard, `no-third-party`) en `cd ingest && uv run pytest` (inclusief `test_contracts.py`, dat bewaakt dat `data/contracts/*.json` actueel is; deze WP wijzigt die bestanden niet).

## Externe afhankelijkheden
Gecontroleerd op 15 oktober 2026. **Geen nieuwe packages.** Gebruikt worden de versies uit WP-13 (`@supabase/supabase-js` ^2.117.3, `@sveltejs/kit` ^3.0.1, `vite` ^8.3.4, `vitest` ^5.0.4).

| Onderwerp | Gebruik | Bron |
|---|---|---|
| supabase-js `select`, `eq`, `gte`, `lt`, `order(column, { ascending })` (meerdere keren aan te roepen) | Queries | https://supabase.com/docs/reference/javascript/select, https://supabase.com/docs/reference/javascript/order |
| supabase-js `not(column, operator, value)` met PostgREST-syntax, `cs` en `'{…}'` voor arrays | Donkere uren uitsluiten | https://supabase.com/docs/reference/javascript/not |
| supabase-js `range(from, to)`: 0-gebaseerd, inclusief, volgt de `order` | Paginering | https://supabase.com/docs/reference/javascript/range |
| supabase-js `maybeSingle()`: nul of één rij, meer is een fout | `getSpot` | https://supabase.com/docs/reference/javascript/maybesingle |
| Supabase `max_rows` standaard 1000 (CLI `api.max_rows`, project-API-settings) | A9 | https://supabase.com/docs/reference/cli/config, https://supabase.com/docs/guides/api/securing-your-api |
| SvelteKit 3: universele load (`PageLoad`), `PageProps` uit `./$types` | Routes | https://svelte.dev/docs/kit/load |
| SvelteKit 3: `redirect(status, location)`, `isRedirect(e)`, `Redirect.location`/`.status` | `/go` en de test | https://svelte.dev/docs/kit/@sveltejs-kit |
| SvelteKit 3: `refreshAll()` vervangt het verouderde `invalidateAll()` | Opnieuw laden | https://svelte.dev/docs/kit/$app-navigation, https://svelte.dev/docs/kit/migrating-to-sveltekit-3 |
| SvelteKit 3: `$app/tsconfig` verbiedt alleen het overschrijven van `paths`, `types`, `isolatedModules` en `verbatimModuleSyntax` | `resolveJsonModule`, `esModuleInterop` | https://svelte.dev/docs/kit/$app-tsconfig |
| Vite 8.3.4 `server.fs.allow` en `searchForWorkspaceRoot`; zodra `allow` gezet is, valt de automatische workspace-root weg | Dev-server mag `data/contracts` serveren | https://vite.dev/config/server-options |
| Cloudflare Pages: root directory, monorepo's; niet gedocumenteerd of bestanden buiten de root beschikbaar zijn | A7 | https://developers.cloudflare.com/pages/configuration/build-configuration/, https://developers.cloudflare.com/pages/configuration/monorepos/ |
| `Intl.DateTimeFormat` met `timeZone` en `hourCycle: 'h23'`, `formatToParts` | Lokale tijd | https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat |
| Formaat `/go` en fixture-strings | AC-5 | `docs/wp/WP-08/blueprint.md` ("Gevolgen", WP-14), `ingest/src/shakka/domain/messages.py::build_go_url` |

Geen Open-Meteo, geen MapTiler, geen CDN, geen analytics, geen nieuwe dienst.

## Risico's
- **R1. Cloudflare-build vanaf de repo-root (A7).** Als Lars Pages toch met root `web` inricht en Cloudflare kloont alleen die map, faalt de build met "Could not resolve ../../../data/contracts/…". Dat is direct zichtbaar (geen stille fout). Mitigatie: RUNBOOK §11.3 en "Nodig van Lars".
- **R2. SvelteKit 3 is jong.** `redirect()` in een universele load bij de eerste (client-side) paginalading van een statische SPA is gedocumenteerd voor loads, maar niet expliciet voor de browser. De builder controleert `/go` met `npm run preview`. Werkt het niet, dan schrijft hij `deviations.md` en gebruikt hij in `go/+page.svelte` `onMount(() => goto(goTarget(page.url), { replace: true }))` (`page` uit `$app/state`), met `goTarget` ongewijzigd en de routetest aangepast.
- **R3. Versheid op `evaluated_at` (A5).** Faalt alleen de forecast-ingest, dan toont de app "vers" terwijl de forecast ouder is. Binnen deze WP niet op te lossen zonder een vierde tabel; voorstel voor WP-22.
- **R4. JSON-imports buiten `web/`.** `svelte-check` of Vite kan klagen ondanks `resolveJsonModule` en `fs.allow`. Mitigatie: de configuratie staat hierboven vast; stap 1 controleert `check`, `test`, `build` én `npm run dev` direct na de eerste import. Blijft het misgaan, dan `deviations.md` en stoppen (het raakt A7 en het contract).
- **R5. Rijlimiet.** Verlaagt iemand `max_rows` onder 1000, dan stopt de paginering te vroeg en ontbreken rijen zonder fout. Mitigatie: RUNBOOK §11.7.
- **R6. Contrast en kleurenblindheid.** Kleur is nooit de enige drager (tekst in elke badge, data-attribuut, pijl met tekst). Een volledige toegankelijkheidscheck hoort bij WP-23.
- **R7. Schemadrift na latere migraties.** De schematest leest alleen de M1-migratie; een `alter table … add column` in een latere migratie wordt niet gezien. Een nieuwe kolom breekt de app niet (expliciete `select`), maar komt er dan ook niet in.
- **R8. Apparaatklok.** Versheid en "vandaag" hangen af van de klok van het apparaat. Een verkeerd ingestelde klok geeft een verkeerde dag of een gemiste waarschuwing.

## Buiten scope
- Golven en `marine_hours` (WP-12), kaart (WP-15), favorieten, profiel en persoonlijke grenzen (WP-16), sessies en de echte `/go`-afhandeling (WP-20, WP-21), push (WP-18).
- Een daglichtberekening, richtingsklassen of oordelen in de browser: alles komt uit `evaluations`.
- Supabase-typegeneratie (A1), offline cache van data (A14), het window uit `/go` markeren op de spotpagina, grafieken, sorteren of filteren van de lijst, groeperen per regio.
- Wijzigingen in `ingest/`, `supabase/`, `data/contracts/` of de CI-workflow; aanpassingen aan `WORK_PACKAGES.md` (zie "Gevolgen", WP-13-regel).

## Stappenplan voor de builder
Werk in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-14` op branch `wp/WP-14`, met Node 24. Lees of print `.env` en `web/.env` nooit. Na elke stap vanuit `web/`: `npm run check && npm test` (plus de genoemde extra's). Eén commit per stap, in het Engels (bijv. `WP-14: add contracts and row types`).

1. **Types, contracten en configuratie (tests eerst).**
   - Pas `web/tsconfig.json` en `web/vite.config.ts` aan zoals in Interfaces.
   - Schrijf `test/contracts.test.ts` en `test/schema-columns.test.ts`. Rood.
   - Maak `src/lib/types.ts` en `src/lib/contracts.ts`. Groen.
   - Controleer direct: `npm run check`, `npm test`, `npm run build`, en `npm run dev` (open `http://localhost:5173/`, geen 403 in de terminal of console voor `data/contracts`). Faalt een van deze op de JSON-import: `deviations.md` en stoppen (R4).
2. **Tijd (tests eerst).** Schrijf `test/fixtures/spot-data.ts`, `test/time.test.ts` (inclusief `parseGoParams`) en `test/go-url-fixture.test.ts`. Rood. Maak `src/lib/time.ts`. Groen.
3. **Labels (tests eerst).** Schrijf `test/labels.test.ts`. Rood. Maak `src/lib/labels.ts`. Groen.
4. **View-logica (tests eerst).** Schrijf `test/view.test.ts`. Rood. Maak `src/lib/view.ts`. Groen.
5. **Data (tests eerst).** Schrijf `test/helpers/fake-supabase.ts`, `test/data.test.ts` en `test/data-tables.test.ts`. Rood. Maak `src/lib/data.ts`. Groen. Draai `grep -n "\.from(" src/lib/data.ts` en controleer de uitvoer (AC-6).
6. **Paginadata en `/go` (tests eerst).** Schrijf `test/page-data.test.ts` en `test/go.test.ts`. Rood. Maak `src/lib/page-data.ts`, `src/lib/go.ts`, `src/routes/go/+page.ts` en `src/routes/go/+page.svelte`. Groen.
7. **Componenten.** Maak `VerdictBadge.svelte`, `WindArrow.svelte`, `HourVerdict.svelte` en `Freshness.svelte`, en schrijf `test/hour-verdict.test.ts`. Groen.
8. **Pagina's.** Maak `src/routes/spot/[id]/+page.ts` en `+page.svelte`, vervang `src/routes/+page.svelte` en maak `src/routes/+page.ts`; voeg de stijlen toe aan `app.css`. Schrijf `test/spot-page.test.ts`, `test/spot-list.test.ts` en `test/no-local-date-getters.test.ts`. Groen, plus `npm run build` en `npm run verify:build`.
9. **Handmatige rooktest.** Met `web/.env` op de lokale stack (`supabase start`, `cd ingest && uv run shakka spots sync` en eventueel `forecast fetch`, `tides fetch`, `evaluate` met de lokale `.env`) of zonder data: `npm run build && npm run preview`, open `/` (lijst of "Nog geen data"), `/spot/<id>`, `/spot/bestaat-niet`, de `GO_URL_SUMMER`-paden (`/go?spot=test-strand&start=2026-07-18T12%3A00%3A00Z&end=2026-07-18T16%3A00%3A00Z` moet naar `/spot/test-strand` gaan) en `/go?x=1` (naar `/`). Werkt de redirect niet: R2.
10. **Documentatie.** Werk `docs/RUNBOOK.md` bij (§11.3, §11.7, §13.2).
11. **Eindcontrole.**
    - `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`;
    - vanuit de root `bash scripts/check-no-client-openmeteo.sh` (exit 0);
    - de AC-6-grep en de AC-6-grep van WP-13 (`grep -rEn "googletagmanager|google-analytics|plausible|fonts.googleapis|cdn\." web/src web/static` geeft niets);
    - `cd ingest && uv run pytest`;
    - `git status`: geen `web/.env`, `web/build` of `node_modules` gestaged.

**Nodig van Lars (AC-7):**
- Cloudflare Pages inrichten volgens de bijgewerkte RUNBOOK §11.3 (root directory leeg, build `cd web && npm ci && npm run build`, output `web/build`, `NODE_VERSION=24.22.0`), plus §11.4 voor Supabase Auth;
- de GitHub Actions-variable `APP_BASE_URL` op de productie-URL zetten (§13.2);
- een reactie op de voorstellen A2 (oordeelslabels) en A7 (Pages vanaf de repo-root).
