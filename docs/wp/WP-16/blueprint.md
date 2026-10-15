# Blueprint WP-16: Profiel, favorieten en alertinstellingen
Status: DRAFT
Revisie: 2

## Doel
Ingelogde gebruikers beheren in de PWA:
- hun profiel op `/profiel`: gewicht, niveau, quiver (3–21 m², maximaal 10 kites) en standaard min/max kn;
- favorieten met een ster in de spotlijst (`/`) en op de spotpagina (`/spot/[id]`), alleen zichtbaar voor ingelogde gebruikers;
- per favoriet de alertregel op `/alerts`: aan/uit, min/max kn, richtingsklassen (alleen de drie rijdbare), weekdagen, tijdvenster, minimaal aantal go-uren en dagen vooruit. Een leeg veld toont "standaard: X (bron)".

Daarnaast:
- `#lib/rules.ts` met `effectiveRule()`, een exacte spiegel van Python `resolve_rule` (WP-07);
- `data/contracts/rule_resolution_cases.json` met 20 gevallen, getoetst door een Python-test en een vitest-test;
- formuliervalidatie gelijk aan de DB-constraints, met drifttests tegen de migraties.

De UI schrijft alleen naar `profiles` (uitsluitend `weight_kg`, `level`, `quiver_m2`, `default_min_kn` en `default_max_kn`), `favorites` en `alert_rules`. Uitgelogde gebruikers zien een loginprompt en er gaan dan geen queries naar die drie tabellen.

## Aannames
Voorstellen waar Lars op kan reageren staan als **Voorstel**.

- **A1. Geen route-loads voor `/profiel` en `/alerts`; laden op basis van `$session`.** Een universele load draait vóór `initAuth()` in de layout, dus de sessie is dan nog onbekend. De pagina's reageren op de `session`-store uit WP-13:
  - `undefined` → "Laden…" en geen query;
  - `null` → loginprompt en geen query (AC-6);
  - een sessie → laden via `#lib/user-page-data.ts`.

  Verandert de user-id (in- of uitloggen in een ander tabblad), dan laadt de pagina opnieuw. Een token-refresh (nieuw sessie-object, zelfde user-id) laadt niet opnieuw. Dit volgt "Gevolgen voor latere WP's" van WP-13 en WP-14 (`undefined` = nog niet queryen).
- **A2. Favorietenstore.** `#lib/favorites.ts` houdt de favoriete spot-id's van de ingelogde gebruiker bij in één Svelte-store. De store laadt opnieuw bij de eerste abonnee (dus bij elke paginanavigatie met sterren) en bij een andere user-id; dat is één kleine query. Wijzigen gaat optimistisch: de ster springt direct om en springt terug bij een fout.
- **A3. Signature van `effectiveRule` iets ruimer dan het contract.** Het contract noemt `effectiveRule(spot: Spot, profile: Profile | null, override: AlertRuleRow | null, defaults: AlertDefaults)`. De parameters worden `Pick`-types van precies die types (`Pick<Spot, 'default_min_kn'>`, `Pick<Profile, 'default_min_kn' | 'default_max_kn'> | null`, `Pick<AlertRuleRow, RuleField> | null`). Elke aanroep met `Spot`, `Profile` en `AlertRuleRow` compileert dus ongewijzigd. Het formulier kan zo een nog niet opgeslagen regel (zonder `user_id` en `updated_at`) controleren. Net als Python (`AlertRuleOverride.enabled: bool | None`, `resolve_rule` valt bij `None` terug op `True`) accepteert `effectiveRule` tijdens runtime `enabled: null` en behandelt het als "geen waarde" (bron `system`). Het parametertype houdt `enabled: boolean` (de DB-kolom is `not null default true`); de gedeelde gevallen gaan via een cast.
- **A4. Het gevallenbestand is handgeschreven en een JSON-lijst**, zoals het contract zegt (`{spot, profile, override, expected}`), met per geval één extra sleutel `name` (voor test-id's). Het wordt niet gegenereerd door `shakka contracts export` en staat dus niet in `CONTRACT_FILES`; `check_contracts` negeert andere bestanden in `data/contracts/` (bestaand gedrag, `test_export_and_check_tmp`). `expected` is een volledige effectieve regel inclusief `sources` (bron per veld), of `{"error": "conflict"}` of `{"error": "invalid"}`. De Python-test leidt de verwachte bronnen af uit `FIELD_SOURCES` van WP-07. Er komt **geen wijziging aan de Python-domeincode**; WP-07 liet een bronfunctie bewust open ("kan WP-16 additief toevoegen als het nodig is") en die is hiermee niet nodig.
- **A5. Een selectie gelijk aan de default wordt `null`.** Zijn bij richtingen alle drie de rijdbare klassen aangevinkt, of bij dagen alle zeven, dan schrijft het formulier `null` ("standaard"). Zo volgt de regel latere wijzigingen van de default. Een rij die via de CLI expliciet alle drie bevat, wordt bij opslaan `null`; dat betekent hetzelfde.
- **A6. Een favoriet zonder regel = standaardinstellingen, alert aan.** Zo werkt WP-10 al (`rule_row = None` → defaults, `enabled = True`). Een rij in `alert_rules` ontstaat pas bij "Opslaan". "Standaardinstellingen" verwijdert de rij (delete); dat is gelijk aan een rij met alleen `null`-waarden en `enabled = true`.
- **A7. Tijdvenster: alleen hele uren 01:00–23:00** (WP-07, "Gevolgen", WP-16). "Vanaf" heeft daarnaast "Geen ondergrens" (`null`), "Tot" heeft "Geen bovengrens" (`null`). 00:00 en 24:00 worden niet aangeboden: "Vanaf 00:00" is gelijk aan geen ondergrens, "Tot 00:00" telt geen enkel uur (E14) en 24:00 schrijft de UI nooit. De UI schrijft `HH:MM:00`. Staat er al een andere waarde in de database (bijv. `20:30:00` via de CLI), dan komt die als extra optie in de lijst, zodat ze niet stil verandert.
- **A8. Dagen vooruit: 0–6 in de UI.** Dit volgt het advies van WP-07 en WP-03 A10: dag 7 heeft nooit data. Staat er al 7 in de database, dan komt 7 als extra optie. De uitleg zegt "dagen ná vandaag: 3 = vandaag plus drie dagen".
- **A9. Voorstel: niveaulabels** `beginner` → "Beginner", `intermediate` → "Gemiddeld", `advanced` → "Gevorderd". Er is nog geen NL-label voor `Level`. De labels staan in `#lib/labels.ts`.
- **A10. Voorstel: bronlabels** in "standaard: X (bron)": `profile` → "je profiel", `spot` → "spotprofiel", `system` → "Shakka". `rule` → "je instelling voor deze spot" komt alleen in conflictmeldingen voor, nooit in een hint (een hint staat alleen bij een leeg veld).
- **A11. Quiver als lijst van invoervelden** met "Kite toevoegen" (uitgeschakeld bij 10) en per kite "Verwijder". Maten mogen een decimale komma of punt hebben, met hoogstens 2 decimalen (bijv. `10,5`). Lege velden worden genegeerd. Bij opslaan wordt de lijst oplopend gesorteerd. Dubbele maten mogen; de database staat ze toe en het kite-advies ontdubbelt zelf (WP-06).
- **A12. Tekstvelden in plaats van `type="number"`.** De velden gebruiken `type="text"` met `inputmode="numeric"` of `inputmode="decimal"` en een eigen parser. Zo is het gedrag gelijk in alle browsers (decimale komma, leeg = `null`) en goed te testen. Het formulier heeft `novalidate`; alle validatie zit in de pure module `#lib/forms.ts`.
- **A13. Conflicten tussen niveaus.** Een regel die met profiel of spot botst (WP-07 A6: expliciete max niet boven de effectieve min), weigert het formulier op `/alerts`, met een melding die beide waarden en bronnen noemt. `/profiel` controleert dit niet per spot: een profielgrens kan botsen met de `default_min_kn` van een spot. Zo'n favoriet krijgt op `/alerts` een zichtbare waarschuwing ("Voor deze spot komen geen alerts tot je dit aanpast"); WP-10 slaat hem dan over.
- **A14. Ontfavorieten verwijdert ook de regel** (FK `on delete cascade`, WP-01). Dat gebeurt alleen met de ster op de lijst of de spotpagina. `/alerts` heeft geen verwijderknop en vermeldt dit in de uitleg.
- **A15. Niet-geverifieerde spots.** Hun alertinstellingen zijn te bewerken, maar de kaart toont "Deze spot is nog niet geverifieerd. Je krijgt er pas alerts voor als het spotprofiel is gecontroleerd." (WP-10 verstuurt alleen voor `verified: true`.)
- **A16. Navigatie.** De header krijgt voor ingelogde gebruikers de links "Alerts" (`/alerts`) en "Profiel" (`/profiel`).
- **A17. Geen migraties, geen nieuwe packages, geen wijziging aan `ingest/src`.** De rechten bestaan al (WP-01): `profiles` heeft select en een kolomgrant voor update op de vijf kolommen, zonder insert (het profiel maakt de trigger `handle_new_user`). `favorites` en `alert_rules` hebben volledige CRUD op de eigen rijen.
- **A18. Eén tijdnotatie aan beide kanten.** `normalizeLocalTime` (TS) en `_fmt` in de Python-test geven dezelfde string: `'HH:MM'` als seconden en fractie 0 zijn, anders `'HH:MM:SS'` als de fractie 0 is, anders `'HH:MM:SS.ffffff'` (fractie rechts aangevuld tot 6 cijfers, zoals Python `time.isoformat()`). Invoer volgt de vormen die Postgres voor `time` teruggeeft (`HH:MM:SS` met hoogstens 6 fractiecijfers) plus `HH:MM`. Pydantic accepteert ruimer (bijv. meer dan 6 fractiecijfers, tijdzones die daarna als ongeldig worden geweigerd); die vormen komen uit PostgREST niet voor en vallen buiten de pariteit. Geval 20 in het gevallenbestand legt de pariteit voor seconden en fracties vast.

## Ontwerp

**Lagen** (volgens het patroon van WP-14):
```
routes/profiel, routes/alerts (+page.svelte, reageren op $session)
   ──> #lib/user-page-data.ts ──> #lib/user-data.ts ──> #lib/supabase.js
                              ──> #lib/data.ts (listSpots, bestaand)
components/FavoriteStar ──> #lib/favorites.ts ──> #lib/auth.js (session), #lib/user-data.ts
components/AlertRuleForm ──> #lib/user-data.ts
puur, zonder I/O: #lib/rules.ts, #lib/forms.ts, #lib/labels.ts, #lib/contracts.ts
```
- `user-data.ts` is de enige module die `profiles`, `favorites` en `alert_rules` aanroept, en de enige die schrijft. `data.ts` blijft alleen-lezen voor `spots`, `evaluations` en `tide_extremes` (WP-14 AC-6). Een broncodetest bewaakt beide.
- De Supabase-fouten worden `DataError` (uit `data.ts`), met alleen de operatie en de code.

**Effectieve regel.** `effectiveRule()` volgt de tabel uit WP-07 per veld uitgeschreven, met de afgeleide `max_kn` (`max(30, min_kn + 5)` via `alert_defaults.json`), de conflictfout (A6 van WP-07), de 24:00-afhandeling (`latest_local` 24:00 → geen bovengrens; `earliest_local` 24:00 → ongeldig), en dezelfde validatie als `AlertRuleOverride` en `ProfileDefaults`. Het resultaat bevat ook de bron per veld (`sources`). Daarmee toont het formulier "standaard: 14 kn (je profiel)". De pariteit met Python bewijst het gedeelde gevallenbestand.

**Formulieren.** `forms.ts` zet rijen om naar formulierwaarden (strings, lijsten) en terug, met Nederlandse foutmeldingen per veld. De pagina's tonen de fouten bij het veld (`aria-invalid`, `aria-describedby`) en een samenvatting met `role="alert"`. Bij een fout gaat er niets naar de database (AC-4). De grenzen komen uit `alert_defaults.json` (kn, `min_go_hours`, `days_ahead`) en uit constanten voor gewicht en quiver. Een node-test vergelijkt al die grenzen met de CHECK-constraints in de migratie.

**Harde regel offshore.** Het formulier toont alleen de klassen uit `ALERT_DEFAULTS.dir_classes.allowed` (de drie rijdbare). `contracts.ts` weigert het contractbestand als daar een niet-rijdbare klasse in staat. `parseAlertRuleForm` en `effectiveRule` weigeren elke andere waarde. Daarachter staan nog de DB-CHECK (WP-01) en de Python-validatie (WP-07).

**Waarom zo.** Laden op `$session` is de enige manier om AC-6 (geen queries bij uitgelogd of onbekend) hard te garanderen zonder dubbele sessielogica. Pure modules maken validatie en pariteit zonder netwerk toetsbaar. Eén schrijfmodule maakt de schrijfregel uit het contract met een broncodetest controleerbaar.

## Bestanden

| Pad | Actie | Inhoud |
|---|---|---|
| `web/src/lib/types.ts` | wijzigen | `LEVELS`, `Profile`, `PROFILE_COLUMNS`, `PROFILE_EDITABLE_COLUMNS`, `ProfileUpdate`, `FAVORITE_COLUMNS`, `RULE_FIELDS`, `RuleField`, `RULE_SOURCES`, `RuleSource`, `AlertRuleRow`, `ALERT_RULE_COLUMNS`, `AlertRuleValues`, `AlertDefaultItem`, `AlertDefaults`. Bestaande exports ongewijzigd. |
| `web/src/lib/contracts.ts` | wijzigen | Import van `alert_defaults.json`, `parseAlertDefaults`, `ALERT_DEFAULTS`. Bestaande exports ongewijzigd. |
| `web/src/lib/labels.ts` | wijzigen | `LEVEL_LABEL_NL`, `SOURCE_LABEL_NL`, `daysAheadText`. |
| `web/src/lib/rules.ts` | aanmaken | `FIELD_SOURCES`, `EffectiveRule`, `RuleConflict`, `RuleError`, `normalizeLocalTime`, `effectiveRule`. |
| `web/src/lib/forms.ts` | aanmaken | Constanten, `FORM_MESSAGES`, profiel- en regelformulier (omzetten, parsen, hints, samenvatting, opties). |
| `web/src/lib/user-data.ts` | aanmaken | Queries en writes op `profiles`, `favorites` en `alert_rules`. |
| `web/src/lib/user-page-data.ts` | aanmaken | `loadProfilePage`, `loadAlertsPage`. |
| `web/src/lib/favorites.ts` | aanmaken | `FavoritesState`, `favorites`, `toggleFavorite`. |
| `web/src/lib/components/FavoriteStar.svelte` | aanmaken | Ster (toggle). |
| `web/src/lib/components/AlertRuleForm.svelte` | aanmaken | Formulier voor één favoriet. |
| `web/src/lib/components/LoginPrompt.svelte` | aanmaken | Loginprompt. |
| `web/src/routes/profiel/+page.svelte` | aanmaken | Profielpagina. |
| `web/src/routes/alerts/+page.svelte` | aanmaken | Alertpagina. |
| `web/src/routes/+layout.svelte` | wijzigen | Navigatielinks "Alerts" en "Profiel" voor ingelogde gebruikers. |
| `web/src/routes/+page.svelte` | wijzigen | `<FavoriteStar>` direct na de spotlink. |
| `web/src/routes/spot/[id]/+page.svelte` | wijzigen | `<h1>` en `<FavoriteStar>` samen in `<div class="title-row">`. |
| `web/src/app.css` | wijzigen | Stijlen uit "Stijl". |
| `web/test/helpers/fake-supabase.ts` | wijzigen | Extra methodes en `writeCalls`. |
| `web/test/helpers/fake-session.ts` | aanmaken | Nep-`#lib/auth.js`. |
| `web/test/helpers/fake-favorites.ts` | aanmaken | Nep-`#lib/favorites.js` voor paginatests. |
| `web/test/fixtures/user-data.ts` | aanmaken | Profiel- en regelfixtures. |
| `web/test/*.test.ts` | aanmaken/wijzigen | Zie Testplan. |
| `data/contracts/rule_resolution_cases.json` | aanmaken | 20 gevallen (zie Interfaces). |
| `ingest/tests/test_rule_resolution_cases.py` | aanmaken | Python-kant van AC-2. |
| `docs/RUNBOOK.md` | wijzigen | §11 punt 8 (profiel, favorieten en alerts in de app), §12 één zin. |

Geen wijzigingen in `ingest/src`, `supabase/`, de bestaande contractbestanden, `.github/`, de service worker of `package.json`. `docs/STATUS.md` en `WORK_PACKAGES.md` werkt de orchestrator bij.

## Interfaces en contracten

Imports via `#lib/<bestand>.js`. Alle teksten voor de gebruiker zijn Nederlands; code, identifiers en `Error`-meldingen Engels. In `web/src` mag het woord "telegram" nergens voorkomen, ook niet in commentaar (AC-8).

### `web/src/lib/types.ts` (toevoegingen)
```ts
export const LEVELS: readonly SpotLevel[] = ['beginner', 'intermediate', 'advanced'];

/** Row of public.profiles (the columns the app uses; an unused legacy column is never selected). */
export interface Profile {
	user_id: string;
	weight_kg: number | null;
	level: SpotLevel | null;
	quiver_m2: number[];
	default_min_kn: number | null;
	default_max_kn: number | null;
	created_at: string;
	updated_at: string;
}
export const PROFILE_COLUMNS = [
	'user_id', 'weight_kg', 'level', 'quiver_m2', 'default_min_kn', 'default_max_kn', 'created_at', 'updated_at'
] as const;
/** The only profile columns `authenticated` may update (column grant, WP-01). */
export const PROFILE_EDITABLE_COLUMNS = [
	'weight_kg', 'level', 'quiver_m2', 'default_min_kn', 'default_max_kn'
] as const;
export type ProfileEditableColumn = (typeof PROFILE_EDITABLE_COLUMNS)[number];
export type ProfileUpdate = Pick<Profile, ProfileEditableColumn>;

export const FAVORITE_COLUMNS = ['user_id', 'spot_id', 'created_at'] as const;

/** Settable columns of alert_rules, in WP-07 RULE_FIELDS order. */
export const RULE_FIELDS = [
	'enabled', 'min_kn', 'max_kn', 'dir_classes', 'weekdays',
	'earliest_local', 'latest_local', 'min_go_hours', 'days_ahead'
] as const;
export type RuleField = (typeof RULE_FIELDS)[number];
/** Priority order, highest first (WP-07 RuleSource). */
export const RULE_SOURCES = ['rule', 'profile', 'spot', 'system'] as const;
export type RuleSource = (typeof RULE_SOURCES)[number];

/** Row of public.alert_rules. Times as PostgREST returns them ('17:00:00'). */
export interface AlertRuleRow {
	user_id: string;
	spot_id: string;
	enabled: boolean;
	min_kn: number | null;
	max_kn: number | null;
	dir_classes: DirClass[] | null;
	weekdays: number[] | null;
	earliest_local: string | null;
	latest_local: string | null;
	min_go_hours: number | null;
	days_ahead: number | null;
	updated_at: string;
}
export const ALERT_RULE_COLUMNS = [
	'user_id', 'spot_id', 'enabled', 'min_kn', 'max_kn', 'dir_classes', 'weekdays',
	'earliest_local', 'latest_local', 'min_go_hours', 'days_ahead', 'updated_at'
] as const;
export type AlertRuleValues = Pick<AlertRuleRow, RuleField>;

/** One item of data/contracts/alert_defaults.json (WP-07). A = element type of `allowed`. */
export interface AlertDefaultItem<T, A extends string | number = string | number> {
	field: RuleField;
	label_nl: string;
	default: T;
	sources: RuleSource[];
	min: number | null;
	max: number | null;
	allowed: A[] | null;
	min_span_kn: number | null;
}
/** An item whose `allowed` list is guaranteed by parseAlertDefaults. */
export type AlertDefaultChoiceItem<T, A extends string | number> = AlertDefaultItem<T, A> & { allowed: A[] };
export interface AlertDefaults {
	enabled: AlertDefaultItem<boolean>;
	min_kn: AlertDefaultItem<number>;
	max_kn: AlertDefaultItem<number>;
	dir_classes: AlertDefaultChoiceItem<DirClass[], DirClass>;
	weekdays: AlertDefaultChoiceItem<number[], number>;
	earliest_local: AlertDefaultItem<null>;
	latest_local: AlertDefaultItem<null>;
	min_go_hours: AlertDefaultItem<number>;
	days_ahead: AlertDefaultItem<number>;
}
```
Zo is `ALERT_DEFAULTS.dir_classes.allowed` van type `DirClass[]` (niet `null`) en bindt `AlertRuleForm` er zonder cast mee; `weekdays.allowed` is `number[]`.

### `web/src/lib/contracts.ts` (toevoegingen)
```ts
import alertDefaultsJson from '../../../data/contracts/alert_defaults.json';

/** Validates the shape of alert_defaults.json. Any deviation -> Error('contract alert_defaults is malformed'). */
export function parseAlertDefaults(json: unknown): AlertDefaults;
export const ALERT_DEFAULTS: AlertDefaults = parseAlertDefaults(alertDefaultsJson);
```
`parseAlertDefaults` staat ná `RIDABLE_DIR_CLASSES` en controleert:
- `_generated` is een string en `items` is een array van precies 9 items; `items[i].field === RULE_FIELDS[i]`;
- `label_nl` is een niet-lege string na `trim`;
- `sources` is een niet-lege array van waarden uit `RULE_SOURCES` die eindigt op `'system'`;
- `min`, `max` en `min_span_kn` zijn een eindig getal of `null`; `allowed` is een array of `null`;
- per veld:
  - `enabled.default` is een boolean;
  - `min_kn`, `max_kn`, `min_go_hours` en `days_ahead` hebben een eindig `default` en getallen voor `min` en `max`;
  - `max_kn.min_span_kn` is een getal;
  - `dir_classes.allowed` is een niet-lege array met alleen waarden uit `RIDABLE_DIR_CLASSES` (dus nooit `side_offshore` of `offshore`), en `dir_classes.default` is een niet-lege deelverzameling daarvan;
  - `weekdays.allowed` en `weekdays.default` zijn niet-lege arrays van gehele getallen 1–7;
  - `earliest_local.default` en `latest_local.default` zijn `null`.

Het resultaat is een object met sleutels uit `RULE_FIELDS` (de items zelf, gecast).

### `web/src/lib/labels.ts` (toevoegingen)
```ts
export const LEVEL_LABEL_NL: Record<SpotLevel, string> = {
	beginner: 'Beginner', intermediate: 'Gemiddeld', advanced: 'Gevorderd'
};
export const SOURCE_LABEL_NL: Record<RuleSource, string> = {
	rule: 'je instelling voor deze spot', profile: 'je profiel', spot: 'spotprofiel', system: 'Shakka'
};
/** 0 -> 'alleen vandaag', 1 -> 'vandaag plus 1 dag', n -> `vandaag plus ${n} dagen`. */
export function daysAheadText(n: number): string;
```

### `web/src/lib/rules.ts`
```ts
import type { AlertDefaults, AlertRuleRow, DirClass, Profile, RuleField, RuleSource, Spot } from './types.js';

/** Same table as WP-07 FIELD_SOURCES (highest priority first). */
export const FIELD_SOURCES: Readonly<Record<RuleField, readonly RuleSource[]>> = {
	enabled: ['rule', 'system'],
	min_kn: ['rule', 'profile', 'spot', 'system'],
	max_kn: ['rule', 'profile', 'system'],
	dir_classes: ['rule', 'system'],
	weekdays: ['rule', 'system'],
	earliest_local: ['rule', 'system'],
	latest_local: ['rule', 'system'],
	min_go_hours: ['rule', 'system'],
	days_ahead: ['rule', 'system']
};
/** Postgres `time` allows 24:00:00 (WP-07 END_OF_DAY_TIME_STRINGS). */
export const END_OF_DAY_TIMES: readonly string[] = ['24:00', '24:00:00'];

export interface EffectiveRule {
	enabled: boolean;
	min_kn: number;
	max_kn: number;
	dir_classes: DirClass[];       // in the order of defaults.dir_classes.allowed
	weekdays: number[];            // ascending
	earliest_local: string | null; // 'HH:MM' (see normalizeLocalTime)
	latest_local: string | null;
	min_go_hours: number;
	days_ahead: number;
	sources: Record<RuleField, RuleSource>;
}
export interface RuleConflict { min: number; minSource: RuleSource; max: number; maxSource: RuleSource }
export type RuleErrorField = RuleField | 'default_min_kn' | 'default_max_kn';

export class RuleError extends Error {
	readonly code: 'conflict' | 'invalid';
	readonly field: RuleErrorField;
	readonly conflict: RuleConflict | null;
	constructor(code: 'conflict' | 'invalid', field: RuleErrorField, message: string, conflict?: RuleConflict | null);
	// name = 'RuleError'
}

/** null -> null. '24:00' / '24:00:00': latest_local -> null (no upper bound, WP-07 E36);
 *  earliest_local -> RuleError('invalid', 'earliest_local') (WP-07 E37).
 *  Otherwise must match /^([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d)(?:\.(\d{1,6}))?)?$/,
 *  else RuleError('invalid', field). With ss = group 3 ?? '00' and frac = (group 4 ?? '').padEnd(6, '0'):
 *  ss === '00' && frac === '000000' -> 'HH:MM'; frac === '000000' -> 'HH:MM:SS';
 *  else 'HH:MM:SS.ffffff' (same string as Python time.isoformat(), see A18). */
export function normalizeLocalTime(value: string | null, field: 'earliest_local' | 'latest_local'): string | null;

/** Mirror of shakka.domain.alerts.resolve_rule (WP-07). Throws RuleError. */
export function effectiveRule(
	spot: Pick<Spot, 'default_min_kn'>,
	profile: Pick<Profile, 'default_min_kn' | 'default_max_kn'> | null,
	override: Pick<AlertRuleRow, RuleField> | null,
	defaults: AlertDefaults
): EffectiveRule;
```
Algoritme van `effectiveRule` (vergelijk altijd met `!== null`, nooit met `||`, want `days_ahead = 0` is geldig):
1. **Profiel valideren** (als niet `null`, zoals `ProfileDefaults`). `default_min_kn` en `default_max_kn` zijn `null` of een geheel getal (`Number.isInteger`) binnen `[defaults.min_kn.min, defaults.min_kn.max]` respectievelijk `[defaults.max_kn.min, defaults.max_kn.max]`. Zijn beide gezet, dan geldt `min < max`. Anders `RuleError('invalid', 'default_min_kn' | 'default_max_kn', …)`.
2. **Override valideren en normaliseren** (als niet `null`, zoals `AlertRuleOverride.from_row`). Een veld dat `undefined` is → `RuleError('invalid', field, 'missing …')`.
   - `enabled`: `null` of `typeof === 'boolean'` (`null` = geen waarde, zoals Python, zie A3).
   - `min_kn`, `max_kn`: `null` of een geheel getal binnen `[min, max]` van het veld. Zijn beide gezet, dan `min_kn < max_kn` (anders invalid op `max_kn`).
   - `dir_classes`: `null`, of een array met minstens één element, elk element in `defaults.dir_classes.allowed`. Ontdubbeld en gesorteerd in de volgorde van `allowed`.
   - `weekdays`: `null`, of een array met minstens één element, elk element een geheel getal in `defaults.weekdays.allowed`. Ontdubbeld en oplopend gesorteerd.
   - `earliest_local`, `latest_local`: via `normalizeLocalTime`. Zijn beide niet `null`, dan `earliest < latest` als stringvergelijking van de genormaliseerde waarden (anders invalid op `latest_local`). Stringvergelijking klopt: uren, minuten en seconden zijn met nullen aangevuld, de fractie heeft altijd 6 cijfers, en een weggelaten deel (`:00` of `.000000`) maakt de string een voorvoegsel, dat eerder sorteert.
   - `min_go_hours`, `days_ahead`: `null` of een geheel getal binnen `[min, max]`.
3. **Per veld oplossen.** Elke regel staat uitgeschreven, net als in WP-07. Bron = het eerste niveau met een waarde die niet `null` is:
   - `enabled`: regel als die niet `null` is, anders `defaults.enabled.default` (system);
   - `min_kn`: regel → `profile.default_min_kn` → `spot.default_min_kn` → `defaults.min_kn.default`;
   - `max_kn`: regel → `profile.default_max_kn` → system `Math.max(defaults.max_kn.default, min_kn + defaults.max_kn.min_span_kn)`;
   - `dir_classes`, `weekdays`, `min_go_hours`, `days_ahead`: regel → system-default (een kopie van de array, gesorteerd zoals in stap 2);
   - `earliest_local`, `latest_local`: regel → `null` (system).
4. **Conflict.** Is de bron van `max_kn` niet `system` en geldt `min_kn >= max_kn`, dan `RuleError('conflict', 'min_kn', \`min_kn ${min} (${minSource}) must be below max_kn ${max} (${maxSource})\`, { min, minSource, max, maxSource })`.
5. Geef `EffectiveRule` terug met `sources`.

### `data/contracts/rule_resolution_cases.json`
Een JSON-lijst, 2 spaties inspringing, een newline aan het eind. Elk element heeft exact de sleutels `name`, `spot`, `profile`, `override` en `expected`:
- `spot`: `{"default_min_kn": int | null}`;
- `profile`: `null` of `{"default_min_kn": int | null, "default_max_kn": int | null}`;
- `override`: `null` of een rij met exact de negen `RULE_FIELDS` zoals PostgREST ze geeft (tijden als `"17:00:00"`, arrays als lijst);
- `expected`: ofwel exact `{"enabled", "min_kn", "max_kn", "dir_classes", "weekdays", "earliest_local", "latest_local", "min_go_hours", "days_ahead", "sources"}` (`dir_classes` in contractvolgorde, `weekdays` oplopend, tijden genormaliseerd volgens A18 of `null`, `sources` met alle negen velden), ofwel `{"error": "conflict"}` of `{"error": "invalid"}`.

Getallen worden als gehele getallen geschreven (`12`, niet `12.0`).

Notatie in de tabel hieronder:
- **R0** = `{"enabled": true, "min_kn": null, "max_kn": null, "dir_classes": null, "weekdays": null, "earliest_local": null, "latest_local": null, "min_go_hours": null, "days_ahead": null}`;
- **D** = de systeemdefaults `enabled true, min 12, max 30, dir_classes ["onshore","side_onshore","sideshore"], weekdays [1,2,3,4,5,6,7], earliest null, latest null, min_go_hours 2, days_ahead 3`;
- **S** = alle bronnen `"system"`.

"R0 + {…}" betekent R0 met die velden vervangen. Het bestand bevat elk element voluit.

| # | `name` | `spot.default_min_kn` | `profile` | `override` | `expected` |
|---|---|---|---|---|---|
| 1 | `system_defaults` | null | null | null | D; S |
| 2 | `spot_min_only` | 16 | null | null | D met min 16; S met `min_kn: spot` |
| 3 | `spot_min_derives_max` | 28 | null | null | D met min 28, max 33; S met `min_kn: spot` |
| 4 | `profile_beats_spot` | 16 | {14, 26} | null | D met min 14, max 26; S met `min_kn: profile`, `max_kn: profile` |
| 5 | `profile_min_derives_max` | 16 | {27, null} | null | D met min 27, max 32; S met `min_kn: profile` |
| 6 | `empty_profile_falls_through` | 16 | {null, null} | null | D met min 16; S met `min_kn: spot` |
| 7 | `rule_all_fields` | 16 | {14, 26} | `{"enabled": false, "min_kn": 18, "max_kn": 24, "dir_classes": ["sideshore"], "weekdays": [6,7], "earliest_local": "17:00:00", "latest_local": "21:00:00", "min_go_hours": 3, "days_ahead": 5}` | `enabled false, 18, 24, ["sideshore"], [6,7], "17:00", "21:00", 3, 5`; alle bronnen `rule` |
| 8 | `rule_min_with_profile_max` | 16 | {14, 26} | R0 + `min_kn: 20` | D met min 20, max 26; S met `enabled: rule`, `min_kn: rule`, `max_kn: profile` |
| 9 | `rule_max_with_profile_min` | 16 | {14, 26} | R0 + `max_kn: 22` | D met min 14, max 22; S met `enabled: rule`, `min_kn: profile`, `max_kn: rule` |
| 10 | `rule_row_all_null` | null | null | R0 | D; S met `enabled: rule` |
| 11 | `rule_min_60_derives_65` | null | null | R0 + `min_kn: 60` | D met min 60, max 65; S met `enabled: rule`, `min_kn: rule` |
| 12 | `latest_2400_is_no_upper_bound` | null | null | R0 + `earliest_local: "17:00:00"`, `latest_local: "24:00:00"` | D met earliest `"17:00"`, latest null; S met `enabled: rule`, `earliest_local: rule` |
| 13 | `lists_deduplicated_and_sorted` | null | null | R0 + `dir_classes: ["sideshore","onshore","onshore"]`, `weekdays: [7,6,6]` | D met dir_classes `["onshore","sideshore"]`, weekdays `[6,7]`; S met `enabled`, `dir_classes` en `weekdays` op `rule` |
| 14 | `conflict_rule_min_profile_max` | null | {null, 20} | R0 + `min_kn: 25` | `{"error": "conflict"}` |
| 15 | `conflict_spot_min_profile_max` | 22 | {null, 20} | null | `{"error": "conflict"}` |
| 16 | `invalid_offshore_in_rule` | null | null | R0 + `dir_classes: ["onshore","offshore"]` | `{"error": "invalid"}` |
| 17 | `invalid_side_offshore_in_rule` | null | null | R0 + `dir_classes: ["side_offshore"]` | `{"error": "invalid"}` |
| 18 | `invalid_earliest_2400` | null | null | R0 + `earliest_local: "24:00:00"` | `{"error": "invalid"}` |
| 19 | `rule_enabled_null_falls_back` | null | null | R0 + `enabled: null` | D; S (ook `enabled: system`) |
| 20 | `times_with_seconds_and_fraction` | null | null | R0 + `earliest_local: "17:00:30"`, `latest_local: "17:00:30.5"` | D met earliest `"17:00:30"`, latest `"17:00:30.500000"`; S met `enabled`, `earliest_local` en `latest_local` op `rule` |

Voorbeeld van één volledig element (geval 2):
```json
{
  "name": "spot_min_only",
  "spot": {"default_min_kn": 16},
  "profile": null,
  "override": null,
  "expected": {
    "enabled": true, "min_kn": 16, "max_kn": 30,
    "dir_classes": ["onshore", "side_onshore", "sideshore"],
    "weekdays": [1, 2, 3, 4, 5, 6, 7],
    "earliest_local": null, "latest_local": null, "min_go_hours": 2, "days_ahead": 3,
    "sources": {"enabled": "system", "min_kn": "spot", "max_kn": "system", "dir_classes": "system",
                "weekdays": "system", "earliest_local": "system", "latest_local": "system",
                "min_go_hours": "system", "days_ahead": "system"}
  }
}
```
De dekking van de vier prioriteitsniveaus: regel (7–13, 20), profiel (4, 5, 8, 9), spot (2, 3, 6) en systeem (overal, plus 1 en 19).

Controle geval 20 tegen Python: Pydantic (speedate) leest `"17:00:30.5"` als `time(17, 0, 30, 500000)` ("1 to 6 digits are reflected in the time.microsecond"); `time(17, 0, 30) < time(17, 0, 30, 500000)`; `_fmt` geeft `"17:00:30"` en `"17:00:30.500000"`. In TS: `'17:00:30' < '17:00:30.500000'` (voorvoegsel).

### `web/src/lib/forms.ts`
```ts
export const WEIGHT_RANGE_KG = [30, 200] as const;       // profiles_weight_range
export const QUIVER_SIZE_RANGE_M2 = [3, 21] as const;    // profiles_quiver_valid
export const MAX_QUIVER_KITES = 10;                      // profiles_quiver_valid
export const DAYS_AHEAD_UI_MAX = 6;                      // WP-07/WP-03 A10: offered in the UI
export const HOUR_OPTIONS: readonly string[];            // '01:00', '02:00', ..., '23:00' (23 items)

export type FieldErrors<F extends string> = Partial<Record<F, string>>;
export type FormResult<T, F extends string> = { ok: true; value: T } | { ok: false; errors: FieldErrors<F> };

// Profile
export interface ProfileForm {
	weight_kg: string; level: '' | SpotLevel; quiver: string[]; default_min_kn: string; default_max_kn: string;
}
export function profileToForm(p: ProfileUpdate): ProfileForm;
export function parseProfileForm(f: ProfileForm, defaults: AlertDefaults): FormResult<ProfileUpdate, ProfileEditableColumn>;
/** Static hints for the empty kn fields of the profile. */
export function profileKnHints(defaults: AlertDefaults): { default_min_kn: string; default_max_kn: string };

// Alert rule
export interface AlertRuleForm {
	enabled: boolean; min_kn: string; max_kn: string; dir_classes: DirClass[]; weekdays: number[];
	earliest_local: string; latest_local: string; min_go_hours: string; days_ahead: string;
}
export interface RuleContext {
	spot: Pick<Spot, 'default_min_kn'>;
	profile: Pick<Profile, 'default_min_kn' | 'default_max_kn'> | null;
	defaults: AlertDefaults;
}
export function ruleToForm(row: AlertRuleValues | null, defaults: AlertDefaults): AlertRuleForm;
/** Step 1 of parseAlertRuleForm, shared with ruleHints. Never throws. `value` holds every field
 *  that parsed, with null for empty or failed fields AND for the later field of a failed cross-field
 *  check (max_kn on min >= max, latest_local on earliest >= latest), so `value` always passes
 *  step 2 of effectiveRule. */
export function parseRuleFields(f: AlertRuleForm, defaults: AlertDefaults): { value: AlertRuleValues; errors: FieldErrors<RuleField> };
export function parseAlertRuleForm(f: AlertRuleForm, ctx: RuleContext): FormResult<AlertRuleValues, RuleField>;
export type HintField = 'min_kn' | 'max_kn' | 'dir_classes' | 'weekdays' | 'earliest_local' | 'latest_local' | 'min_go_hours' | 'days_ahead';
export function ruleHints(f: AlertRuleForm, ctx: RuleContext): Partial<Record<HintField, string>>;
export function ruleSummary(r: EffectiveRule): string;
export type StoredRuleStatus = { ok: true; rule: EffectiveRule } | { ok: false; problem: string };
export function storedRuleStatus(row: AlertRuleValues | null, ctx: RuleContext): StoredRuleStatus;
export function timeOptions(current: string): string[];
export function daysAheadOptions(current: string): string[];
```

**Meldingen** (`FORM_MESSAGES`, met de grenzen ingevuld uit de constanten en `defaults`):

| Sleutel | Tekst |
|---|---|
| `weight` | `Vul een heel getal tussen 30 en 200 kg in.` |
| `level` | `Kies een niveau uit de lijst.` |
| `quiverSize` | `Elke kitemaat moet tussen 3 en 21 m² liggen (bijv. 9 of 10,5).` |
| `quiverCount` | `Je kunt maximaal 10 kites invullen.` |
| `kn` | `Vul een heel getal tussen 5 en 60 kn in.` |
| `minNotBelowMax` | `De maximale wind moet hoger zijn dan de minimale wind.` |
| `dirEmpty` | `Kies minstens één windrichting.` |
| `dirInvalid` | `Deze windrichting kun je niet kiezen.` |
| `weekdaysEmpty` | `Kies minstens één dag.` |
| `weekdaysInvalid` | `Kies dagen uit de lijst.` |
| `time` | `Kies een tijd uit de lijst.` |
| `latestMidnight` | `"Tot 00:00" telt geen enkel uur. Kies een later tijdstip of geen bovengrens.` |
| `timeOrder` | `"Tot" moet later zijn dan "Vanaf".` |
| `minGoHours` | `Vul een heel getal tussen 1 en 24 in.` |
| `daysAhead` | `Kies een waarde uit de lijst.` |
| `profileInvalid` | `Je profiel heeft ongeldige windgrenzen; pas die aan bij Profiel.` |
| `ruleInvalid` | `Deze instelling kan niet worden opgeslagen. Controleer de velden.` |
| `conflict(c)` | `` `Minimale wind ${formatKn(c.min)} kn (${SOURCE_LABEL_NL[c.minSource]}) moet lager zijn dan maximale wind ${formatKn(c.max)} kn (${SOURCE_LABEL_NL[c.maxSource]}).` `` |

**Regels:**
- **Gehele getallen** (`parseIntField(s, lo, hi)`): `trim`; leeg → `null`; anders `/^\d{1,3}$/` en `lo <= n <= hi`, anders een fout.
- **Quivermaat:** `trim`; `/^\d{1,2}([.,]\d{1,2})?$/`; een komma wordt een punt; dan `Number`; het bereik is `QUIVER_SIZE_RANGE_M2` (inclusief).
- **`parseProfileForm`:**
  - `weight_kg` volgt `WEIGHT_RANGE_KG`;
  - `level` is `''` (→ `null`) of een waarde uit `LEVELS`;
  - bij `quiver` vallen lege velden na `trim` weg; meer dan `MAX_QUIVER_KITES` → `quiverCount`; elke maat wordt geparsed (de eerste fout telt); het resultaat wordt oplopend gesorteerd. De fout staat onder sleutel `quiver_m2`;
  - `default_min_kn` en `default_max_kn` volgen het bereik `defaults.min_kn.min`–`max` en `defaults.max_kn.min`–`max`. Zijn beide gezet en geldt `min >= max`, dan `minNotBelowMax` op `default_max_kn`;
  - het resultaat `value` heeft exact de vijf sleutels van `PROFILE_EDITABLE_COLUMNS`.
- **`profileToForm`:** getallen worden `String(n)`; quivermaten worden `String(n).replace('.', ',')`; `null` wordt `''`.
- **`profileKnHints`:**
  - `default_min_kn`: `` `standaard: de waarde van de spot, anders ${formatKn(defaults.min_kn.default)} kn (Shakka)` ``;
  - `default_max_kn`: `` `standaard: ${formatKn(defaults.max_kn.default)} kn, of ${formatKn(defaults.max_kn.min_span_kn)} kn boven de minimale wind als dat hoger is (Shakka)` ``.
- **`ruleToForm`:**
  - bij `row === null`: `enabled = defaults.enabled.default`; de tekstvelden en selects `''`; `dir_classes` en `weekdays` krijgen een kopie van de default;
  - anders: getallen worden `String(n)`; `dir_classes` of `weekdays` `null` → een kopie van de default; tijden via `normalizeLocalTime`. Gooit die (`earliest_local` 24:00 of een onleesbare tijd) of geeft die `null` (bijv. `latest_local` 24:00), dan wordt het veld `''`.
- **`parseRuleFields(f, defaults)`** (stap 1 van `parseAlertRuleForm`, gedeeld met `ruleHints`). Begint met `value` = alle negen velden `null` behalve `enabled = f.enabled`, en `errors = {}`. Per veld wordt `value[field]` alleen gezet als het veld geldig is; bij een fout blijft het `null` en komt de melding in `errors[field]`:
  - `min_kn` en `max_kn` met de `defaults`-bereiken (`kn`). Zijn beide geldig gezet en geldt `min >= max`, dan `minNotBelowMax` op `max_kn` **en** `value.max_kn = null`;
  - `dir_classes`: leeg → `dirEmpty`; een waarde buiten `defaults.dir_classes.allowed` → `dirInvalid`; als verzameling gelijk aan `defaults.dir_classes.default` → `null` (geen fout); anders ontdubbeld en gesorteerd in de volgorde van `allowed`;
  - `weekdays`: leeg → `weekdaysEmpty`; een waarde die geen geheel getal uit `defaults.weekdays.allowed` is → `weekdaysInvalid`; gelijk aan de default-verzameling → `null` (geen fout); anders ontdubbeld en oplopend;
  - tijden: `''` → `null`; anders moet de waarde `/^([01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d{6})?)?$/` matchen (precies de uitvoer van `normalizeLocalTime`, zodat een via de CLI opgeslagen `20:30` of `17:00:30` ongewijzigd terug kan), anders `time`. Een `latest_local` van `'00:00'` → `latestMidnight` (waarde `null`). Zijn beide geldig gezet en geldt `earliest >= latest` (stringvergelijking, zie `effectiveRule` stap 2), dan `timeOrder` op `latest_local` **en** `value.latest_local = null`. Geschreven als `` `${v}:00` `` als `v` de vorm `HH:MM` heeft, anders `v` ongewijzigd;
  - `min_go_hours` met het `defaults`-bereik (`minGoHours`);
  - `days_ahead`: `''` → `null`; anders `/^\d$/` en binnen `defaults.days_ahead.min`–`max` (7 is dus geldig als hij al in de database stond), anders `daysAhead`.

  Omdat elk veld dat in `value` staat binnen zijn bereik ligt en beide controles tussen velden zijn toegepast, haalt `value` altijd stap 2 van `effectiveRule`. `parseRuleFields` gooit nooit.
- **`parseAlertRuleForm`:**
  1. `{ value, errors } = parseRuleFields(f, ctx.defaults)`.
  2. Zijn er fouten, dan `{ ok: false, errors }`; verder niets.
  3. Daarna `effectiveRule(ctx.spot, ctx.profile, value, ctx.defaults)` in een `try`:
     - `RuleError` met code `conflict` → `{ ok: false, errors: { [c.maxSource === 'rule' ? 'max_kn' : 'min_kn']: conflict(c) } }`;
     - `RuleError` met code `invalid` en veld `default_min_kn` of `default_max_kn` (ongeldig profiel; door de DB-constraints niet te verwachten) → `{ ok: false, errors: { min_kn: FORM_MESSAGES.profileInvalid } }`;
     - elke andere fout → `{ ok: false, errors: { [veld als het een RuleField is, anders 'min_kn']: FORM_MESSAGES.ruleInvalid } }`.
  4. Anders `{ ok: true, value }`, met exact de negen sleutels van `RULE_FIELDS`.
- **`ruleHints`** gooit nooit:
  - `lenient = parseRuleFields(f, ctx.defaults).value` (fouten genegeerd; zie hierboven: geldig voor stap 2 van `effectiveRule`).
  - `let eff: EffectiveRule | null = null; try { eff = effectiveRule(ctx.spot, ctx.profile, lenient, ctx.defaults); } catch { eff = null; }`. `effectiveRule` kan hier alleen nog gooien bij een conflict of een ongeldig profiel; de `catch` vangt elke fout.
  - Er is geen tweede aanroep (de fallback uit revisie 1 vervalt): alleen `min_kn` en `max_kn` hebben `eff` nodig. Voor de andere velden geldt bij lege invoer altijd de systeemwaarde (`FIELD_SOURCES` kent daar alleen `rule` en `system`), dus die hints komen direct uit `ctx.defaults`.
  - Een hint komt er alleen voor velden waarvan de invoer leeg is (`trim() === ''`). Voor `dir_classes` en `weekdays` geldt "leeg" als de selectie als verzameling gelijk is aan de default.
  - Teksten (`sys = SOURCE_LABEL_NL.system`):
    - `min_kn`/`max_kn`: bij `eff !== null` `` `standaard: ${formatKn(eff.x)} kn (${SOURCE_LABEL_NL[eff.sources.x]})` ``, anders `'standaard: botst met je andere windgrenzen'`;
    - `dir_classes`: `` `standaard: alle rijdbare richtingen (${sys})` ``;
    - `weekdays`: `` `standaard: alle dagen (${sys})` ``;
    - `earliest_local`: `` `standaard: geen ondergrens (${sys})` ``;
    - `latest_local`: `` `standaard: geen bovengrens (${sys})` ``;
    - `min_go_hours`: `` `standaard: ${ctx.defaults.min_go_hours.default} uur (${sys})` ``;
    - `days_ahead`: `` `standaard: ${daysAheadText(ctx.defaults.days_ahead.default)} (${sys})` ``.
- **`ruleSummary(r)`:** de delen hieronder, samengevoegd met `' · '`:
  - `r.enabled ? 'Aan' : 'Uit'`;
  - `` `${formatKn(r.min_kn)}–${formatKn(r.max_kn)} kn` ``;
  - als `r.dir_classes.length < ALERT_DEFAULTS.dir_classes.allowed.length`: de labels via `dirClassLabel`, met `', '` ertussen;
  - als `r.weekdays.length < 7`: `WEEKDAY_ABBR_NL[d - 1]`, met `', '` ertussen;
  - als er een tijd is: `` `${r.earliest_local ?? '00:00'}–${r.latest_local ?? '24:00'}` `` (alleen weergave; er wordt nooit 24:00 geschreven);
  - `` `min. ${r.min_go_hours} uur go` ``;
  - `daysAheadText(r.days_ahead)`.

  Voorbeeld met de defaults: `Aan · 12–30 kn · min. 2 uur go · vandaag plus 3 dagen`.
- **`storedRuleStatus(row, ctx)`:** `effectiveRule` in een `try`.
  - `conflict` → `` `Deze instellingen botsen: minimale wind ${min} kn (${bron}) is niet lager dan maximale wind ${max} kn (${bron}). Voor deze spot komen geen alerts tot je dit aanpast.` `` (met `formatKn` en `SOURCE_LABEL_NL`);
  - `invalid` (of een andere fout) → `'De opgeslagen instelling is ongeldig. Voor deze spot komen geen alerts tot je hem opnieuw opslaat.'`;
  - gelukt, maar `rule.latest_local === '00:00'` (alleen mogelijk zonder "Vanaf"; WP-07 E14: geen enkel uur telt) → `{ ok: false, problem: '"Tot 00:00" telt geen enkel uur. Voor deze spot komen geen alerts tot je dit aanpast.' }`;
  - anders `{ ok: true, rule }`.
- **`timeOptions(current)`:** `HOUR_OPTIONS`, plus `current` als die niet leeg is en er niet in staat; lexicografisch gesorteerd.
- **`daysAheadOptions(current)`:** `'0'` t/m `String(DAYS_AHEAD_UI_MAX)`, plus `current` als die niet leeg is en er niet in staat; numeriek gesorteerd.

### `web/src/lib/user-data.ts`
```ts
import { supabase } from '#lib/supabase.js';
import { DataError, fetchAllPages } from './data.js';

export function getProfile(userId: string): Promise<Profile | null>;
export function updateProfile(userId: string, values: ProfileUpdate): Promise<Profile>;
export function listFavoriteSpotIds(userId: string): Promise<string[]>;
export function addFavorite(userId: string, spotId: string): Promise<void>;
export function removeFavorite(userId: string, spotId: string): Promise<void>;
export function listAlertRules(userId: string): Promise<AlertRuleRow[]>;
export function saveAlertRule(userId: string, spotId: string, values: AlertRuleValues): Promise<AlertRuleRow>;
export function resetAlertRule(userId: string, spotId: string): Promise<void>;
```
De exacte queries (de tests controleren de volgorde van de aanroepen):

| Functie | Query | Fout |
|---|---|---|
| `getProfile` | `supabase.from('profiles').select(PROFILE_COLUMNS.join(',')).eq('user_id', userId).maybeSingle()` → `data ?? null` | `DataError('getProfile', code)` |
| `updateProfile` | `payload` = een object met precies de vijf sleutels, letterlijk uitgeschreven (`{ weight_kg: values.weight_kg, level: values.level, quiver_m2: values.quiver_m2, default_min_kn: values.default_min_kn, default_max_kn: values.default_max_kn }`); `supabase.from('profiles').update(payload).eq('user_id', userId).select(PROFILE_COLUMNS.join(',')).single()` | `DataError('updateProfile', code)` (bijv. `PGRST116` als er geen rij is) |
| `listFavoriteSpotIds` | `fetchAllPages('listFavoriteSpotIds', () => supabase.from('favorites').select('spot_id').eq('user_id', userId).order('spot_id', { ascending: true }))` → `rows.map(r => r.spot_id)` | via `fetchAllPages` |
| `addFavorite` | `supabase.from('favorites').insert({ user_id: userId, spot_id: spotId })` | code `23505` (bestaat al) → geen fout; anders `DataError('addFavorite', code)` |
| `removeFavorite` | `supabase.from('favorites').delete().eq('user_id', userId).eq('spot_id', spotId)` | `DataError('removeFavorite', code)` |
| `listAlertRules` | `fetchAllPages('listAlertRules', () => supabase.from('alert_rules').select(ALERT_RULE_COLUMNS.join(',')).eq('user_id', userId).order('spot_id', { ascending: true }))` | via `fetchAllPages` |
| `saveAlertRule` | `supabase.from('alert_rules').upsert({ user_id: userId, spot_id: spotId, enabled, min_kn, max_kn, dir_classes, weekdays, earliest_local, latest_local, min_go_hours, days_ahead }, { onConflict: 'user_id,spot_id' }).select(ALERT_RULE_COLUMNS.join(',')).single()`; de negen waarden worden letterlijk overgenomen uit `values` | `DataError('saveAlertRule', code)` (bijv. `23503` als de favoriet weg is) |
| `resetAlertRule` | `supabase.from('alert_rules').delete().eq('user_id', userId).eq('spot_id', spotId)` | `DataError('resetAlertRule', code)` |

Nooit `updated_at`, `created_at` of andere kolommen in een payload. Geen `Array.from`, `.rpc(` of `.from(` met iets anders dan een letterlijke tabelnaam in dit bestand.

### `web/src/lib/user-page-data.ts`
```ts
export type ProfilePageData = { kind: 'ok'; profile: Profile } | { kind: 'missing' } | { kind: 'error' };
export interface FavoriteRuleEntry { spot: Spot; rule: AlertRuleRow | null }
export type AlertsPageData =
	| { kind: 'ok'; profile: Profile | null; entries: FavoriteRuleEntry[] }
	| { kind: 'error' };

/** getProfile; null -> missing; throw -> console.warn('profile load failed') and error. */
export function loadProfilePage(userId: string): Promise<ProfilePageData>;
/** Promise.all([getProfile, listFavoriteSpotIds, listAlertRules, listSpots()]).
 *  entries: spots (in listSpots order: name, id) whose id is a favorite, with the rule row for that
 *  spot_id or null. Favorite ids without a spot are skipped. Throw -> console.warn('alerts load failed') and error. */
export function loadAlertsPage(userId: string): Promise<AlertsPageData>;
```
De `console.warn`-regels bevatten nooit de foutmelding, een user-id of een spot-id.

### `web/src/lib/favorites.ts`
```ts
export type FavoritesState =
	| { status: 'unknown' }                         // session not known yet
	| { status: 'signed_out' }
	| { status: 'loading'; userId: string }
	| { status: 'ready'; userId: string; ids: ReadonlySet<string> }
	| { status: 'error'; userId: string };

export const favorites: Readable<FavoritesState>;
/** Signed in and ready: flips spotId optimistically, calls addFavorite/removeFavorite, reverts on error.
 *  Returns true on success, false on error or when the state is not 'ready'. */
export function toggleFavorite(spotId: string): Promise<boolean>;
```
Implementatie:
- Een interne `writable<FavoritesState>({ status: 'unknown' })` en `favorites = readable(initial, start)`.
- `start` abonneert op de interne store en op `session` (uit `#lib/auth.js`), en zet `loadedFor = null`. De `stop` die `start` teruggeeft, zegt beide abonnementen op.
- Bij elke sessiewaarde:
  - `undefined` → `unknown`;
  - `null` → `signed_out`;
  - een sessie met `user.id !== loadedFor` → `loadedFor = id`, `loading`, dan `listFavoriteSpotIds(id)` → `ready` met `new Set(ids)`, of `error` bij een fout. Het resultaat wordt alleen gezet als `loadedFor` nog gelijk is aan `id`.
- `toggleFavorite`:
  - leest de huidige toestand; is die niet `ready`, dan `false`;
  - zet een nieuwe `Set` met de spot erbij of eraf;
  - roept `addFavorite` of `removeFavorite` aan;
  - bij een fout: alleen terugzetten als de toestand nog bij dezelfde `userId` hoort; `console.warn('favorite update failed')`; `false`.

### Componenten
- **`FavoriteStar.svelte`.** Props `{ spotId: string; spotName: string }`. Importeert alleen `#lib/favorites.js`. Lokale state `busy` en `failed`.
  - Bij `unknown` of `signed_out`: niets renderen.
  - Anders:
    ```svelte
    <button type="button" class="favorite-star" aria-pressed={pressed} aria-label="Favoriet: {spotName}"
      title={status === 'error' ? 'Favorieten konden niet worden geladen' : pressed ? 'Verwijder uit favorieten' : 'Voeg toe aan favorieten'}
      disabled={status !== 'ready' || busy} onclick={toggle}>
      <span aria-hidden="true">{pressed ? '★' : '☆'}</span>
    </button>
    {#if failed}<span class="error" role="status">Niet opgeslagen</span>{/if}
    ```
    Hierin is `pressed = status === 'ready' && ids.has(spotId)`. `toggle`: `busy = true`, `failed = !(await toggleFavorite(spotId))`, `busy = false`.
- **`LoginPrompt.svelte`.** Props `{ reason: string }`. Markup: `<div class="login-prompt"><p>Log in om {reason}.</p><p><a href="/login">Inloggen</a></p></div>`.
- **`AlertRuleForm.svelte`.** Props `{ userId: string; spot: Spot; profile: Profile | null; row: AlertRuleRow | null; onsaved: (row: AlertRuleRow | null) => void }`.
  - State:
    - `let form = $state<AlertRuleFormValues>(untrack(() => ruleToForm(row, ALERT_DEFAULTS)))` (`untrack` uit `'svelte'`), met het commentaar `// initial value only; submit/reset set form explicitly`. De prop `row` staat zo in een closure, wat de compilerwaarschuwing `state_referenced_locally` voorkomt; het formulier neemt bewust alleen de beginwaarde over (na opslaan zet `submit` `form` zelf);
    - `errors = $state<FieldErrors<RuleField>>({})`;
    - `status = $state<'idle' | 'saving' | 'saved' | 'reset' | 'failed'>('idle')`;
    - `failMessage = $state('')`.
  - `const ctx: RuleContext = $derived({ spot, profile, defaults: ALERT_DEFAULTS })`, `const hints = $derived(ruleHints(form, ctx))`. Het type `AlertRuleForm` uit `forms.ts` wordt geïmporteerd als `type AlertRuleForm as AlertRuleFormValues` om botsing met de componentnaam te voorkomen.
  - Id's: `` `${field}-${spot.id}` ``. Labels komen uit `ALERT_DEFAULTS[field].label_nl`.
  - Markup, in deze volgorde, in `<form novalidate onsubmit={submit} class="rule-form">`:
    1. `<div class="form-field checkbox-row"><input type="checkbox" id=… bind:checked={form.enabled} /><label for=…>Alert aan</label></div>`.
    2. `min_kn` en `max_kn`: `<label>`, `<input type="text" inputmode="numeric" autocomplete="off" bind:value aria-invalid={!!errors.x || undefined} aria-describedby=…>`, `<p class="hint" id="{id}-hint">{hints.x ?? ''}</p>` en bij een fout `<p class="error" id="{id}-error">`. `aria-describedby` is `{id}-hint`, plus `{id}-error` als er een fout is.
    3. `<fieldset><legend>Windrichtingen</legend>` met per code in `ALERT_DEFAULTS.dir_classes.allowed` een `<input type="checkbox" name="dir_classes-{spot.id}" value={code} bind:group={form.dir_classes} id="dir-{code}-{spot.id}">` en `<label for=…>{dirClassLabel(code)}</label>`. Daarna `<p class="hint">Aflandige en schuin aflandige wind zijn nooit kitebaar en staan hier daarom niet tussen.</p>`, de hint en de fout.
    4. `<fieldset><legend>Dagen</legend>` met voor 1–7 een checkbox `value={d}` (een getal), `bind:group={form.weekdays}` en het label `WEEKDAY_NL[d - 1]`. Daarna de hint en de fout.
    5. `earliest_local`: `<select bind:value={form.earliest_local}>` met `<option value="">Geen ondergrens</option>` en `timeOptions(form.earliest_local)`.
    6. `latest_local`: idem, met `Geen bovengrens`.
    7. `min_go_hours`: tekstveld, zoals stap 2.
    8. `days_ahead`: `<select>` met `<option value="">Standaard</option>` en voor elke `n` uit `daysAheadOptions(form.days_ahead)` `<option value={n}>{n} ({daysAheadText(Number(n))})</option>`. Daaronder `<p class="hint">Dagen ná vandaag: 3 betekent vandaag plus drie dagen.</p>` en de hint.
    9. `<button type="submit" disabled={status === 'saving'}>Opslaan</button>`, en alleen als `row !== null` `<button type="button" onclick={reset}>Standaardinstellingen</button>`.
    10. Meldingen:
        - als `Object.keys(errors).length`: `<p role="alert" class="error">Niet opgeslagen: controleer de gemarkeerde velden.</p>`;
        - `saved` → `<p role="status">Opgeslagen.</p>`;
        - `reset` → `<p role="status">Standaardinstellingen hersteld.</p>`;
        - `failed` → `<p role="alert" class="error">{failMessage}</p>`.
  - `submit`:
    1. `preventDefault`;
    2. `r = parseAlertRuleForm(form, ctx)`;
    3. bij een fout: `errors = r.errors`, `status = 'idle'`, return (geen write);
    4. anders `errors = {}`, `status = 'saving'`;
    5. `saved = await saveAlertRule(userId, spot.id, r.value)`;
    6. `form = ruleToForm(saved, ALERT_DEFAULTS)`, `onsaved(saved)`, `status = 'saved'`.

    Bij een fout: `status = 'failed'`, `failMessage` = `'Deze spot staat niet meer in je favorieten. Herlaad de pagina.'` als de `DataError` code `23503` heeft, anders `'Opslaan is niet gelukt. Probeer het opnieuw.'`.
  - `reset`: `await resetAlertRule(userId, spot.id)`, `form = ruleToForm(null, ALERT_DEFAULTS)`, `errors = {}`, `onsaved(null)`, `status = 'reset'`. Bij een fout `failed` met de algemene tekst.

### Routes
- **`/profiel`** (`src/routes/profiel/+page.svelte`, geen `+page.ts`).
  - `<svelte:head><title>Profiel · Shakka</title></svelte:head>`, `<h1>Profiel</h1>`.
  - Laden (zelfde patroon op `/alerts`):
    ```ts
    const userId = $derived($session ? $session.user.id : null);
    let page = $state<{ kind: 'idle' } | { kind: 'loading' } | ProfilePageData>({ kind: 'idle' });
    // /profiel only: form state (not rendered until page.kind === 'ok')
    let form = $state<ProfileForm>(profileToForm({ weight_kg: null, level: null, quiver_m2: [], default_min_kn: null, default_max_kn: null }));
    let errors = $state<FieldErrors<ProfileEditableColumn>>({});
    let status = $state<'idle' | 'saving' | 'saved' | 'failed'>('idle');
    const saving = $derived(status === 'saving');
    let token = 0;
    function load(id: string) { const t = ++token; page = { kind: 'loading' }; void loadProfilePage(id).then((r) => { if (t === token) { page = r; if (r.kind === 'ok') { form = profileToForm(r.profile); errors = {}; status = 'idle'; } } }); }
    function retry() { if (userId !== null) load(userId); }
    $effect(() => { const id = userId; if (id === null) { token++; page = { kind: 'idle' }; return; } load(id); });
    ```
    Op `/alerts` vervallen `form`, `errors`, `status` en `saving` (die zitten per favoriet in `AlertRuleForm`), en roept `load` `loadAlertsPage` aan. `retry` is op beide pagina's gelijk.
  - Weergave:
    - `$session === undefined` → `<p class="muted">Laden…</p>`;
    - `$session === null` → `<LoginPrompt reason="je profiel te bewerken" />`;
    - `loading` → `Laden…`;
    - `error` → `<div class="banner" role="alert"><p>Je profiel kon niet worden geladen. Controleer je verbinding.</p><button type="button" onclick={retry}>Opnieuw proberen</button></div>`;
    - `missing` → `<div class="banner" role="alert"><p>Je profiel is niet gevonden. Log uit en weer in. Helpt dat niet, neem dan contact op met de beheerder.</p></div>`;
    - `ok`: eerst `<p class="muted">Shakka gebruikt deze gegevens voor je alerts en voor het kite-advies in je meldingen. Alles is optioneel.</p>`, dan `<form novalidate onsubmit={submit}>` met:
      1. `weight_kg`: label `Gewicht (kg)`, tekstveld (`inputmode="numeric"`), hint `Voor het kite-advies. Leeg = geen kite-advies.`;
      2. `level`: label `Niveau`, `<select>` met `<option value="">Niet ingevuld</option>` en `LEVELS` met `LEVEL_LABEL_NL`;
      3. `<fieldset><legend>Quiver (kitematen in m²)</legend>`: per index `i` een label `Kite {i + 1} (m²)`, `<input id="quiver-{i}" type="text" inputmode="decimal" bind:value={form.quiver[i]}>` en `<button type="button" onclick={() => form.quiver.splice(i, 1)}>Verwijder kite {i + 1}</button>`. Daaronder `<button type="button" disabled={form.quiver.length >= MAX_QUIVER_KITES} onclick={() => form.quiver.push('')}>Kite toevoegen</button>`, de hint `Maten van 3 tot 21 m², maximaal 10 kites.` en de fout `quiver_m2`;
      4. `default_min_kn`: label `Standaard minimale wind (kn)`, hint uit `profileKnHints`;
      5. `default_max_kn`: label `Standaard maximale wind (kn)`, idem;
      6. `<button type="submit" disabled={saving}>Opslaan</button>`; meldingen zoals in `AlertRuleForm` (`Niet opgeslagen: controleer de gemarkeerde velden.`, `Opgeslagen.`, `Opslaan is niet gelukt. Probeer het opnieuw.`).

      Foutweergave per veld en `aria-describedby` zoals in `AlertRuleForm`.
  - `submit(e)`: `e.preventDefault()`; `const id = userId; if (id === null) return;`; `r = parseProfileForm(form, ALERT_DEFAULTS)`; een fout → `errors = r.errors`, `status = 'idle'`, geen write; anders `errors = {}`, `status = 'saving'`, `saved = await updateProfile(id, r.value)` → `page = { kind: 'ok', profile: saved }`, `form = profileToForm(saved)`, `status = 'saved'`. Bij een fout `status = 'failed'` met `Opslaan is niet gelukt. Probeer het opnieuw.`
- **`/alerts`** (`src/routes/alerts/+page.svelte`, geen `+page.ts`).
  - `<title>Alerts · Shakka</title>`, `<h1>Alerts</h1>`.
  - Bij `undefined` "Laden…"; bij `null` `<LoginPrompt reason="je alerts in te stellen" />`; laden met `loadAlertsPage` zoals op `/profiel`.
  - Bij `error`: een banner met `De alertinstellingen konden niet worden geladen. Controleer je verbinding.` en `<button type="button" onclick={retry}>Opnieuw proberen</button>`.
  - Bij `ok`:
    1. `<p class="muted">Voor elke favoriete spot staat een alert standaard aan, met de standaardinstellingen. Lege velden volgen de standaard. Je eigen windgrenzen voor alle spots stel je in bij je <a href="/profiel">profiel</a>. Haal je een spot uit je favorieten, dan verdwijnen ook de alertinstellingen voor die spot.</p>`;
    2. `entries.length === 0` → `<p>Je hebt nog geen favorieten. Tik op de ster bij een spot in de <a href="/">lijst</a> om hem toe te voegen.</p>`;
    3. anders, per entry:
       ```svelte
       <section class="alert-rule" data-spot={e.spot.id} aria-labelledby="rule-{e.spot.id}">
         <h2 id="rule-{e.spot.id}"><a href="/spot/{e.spot.id}">{e.spot.name}</a></h2>
         {#if !e.spot.verified}<p class="notice">Deze spot is nog niet geverifieerd. Je krijgt er pas alerts voor als het spotprofiel is gecontroleerd.</p>{/if}
         {#if st.ok}<p class="rule-summary">{ruleSummary(st.rule)}</p>{:else}<p class="banner warning" role="note">{st.problem}</p>{/if}
         <details><summary>Instellingen aanpassen</summary>
           <AlertRuleForm {userId} spot={e.spot} profile={page.profile} row={e.rule} onsaved={(row) => (e.rule = row)} />
         </details>
       </section>
       ```
       Hierin is `st = storedRuleStatus(e.rule, { spot: e.spot, profile: page.profile, defaults: ALERT_DEFAULTS })`, met `{@const}`. `e.rule = row` werkt op de `$state`-proxy van `page`. De `ok`-tak staat binnen `{#if page.kind === 'ok' && userId !== null}`, zodat `userId` daar een `string` is en `page` vernauwd is tot de `ok`-variant; de lus is `{#each page.entries as e (e.spot.id)}`. `<details>` blijft standaard dicht (geen `open`-attribuut); de tests openen hem zelf (zie Testplan, `alerts-page.test.ts`).
- **`+layout.svelte`.** In `<nav>`, na `Over` en vóór het e-mailadres: `{#if $session}<a href="/alerts">Alerts</a><a href="/profiel">Profiel</a>{/if}`. Daarvoor kan het bestaande `{#if $session}`-blok uitgebreid worden.
- **`/`.** Na `<a class="spot-link" …>` komt `<FavoriteStar spotId={spot.id} spotName={spot.name} />`.
- **`/spot/[id]`.** `<h1>{spot.name}</h1>` wordt `<div class="title-row"><h1>{spot.name}</h1><FavoriteStar spotId={spot.id} spotName={spot.name} /></div>`.

### Stijl (`web/src/app.css`, toevoegen)
- `.title-row { display: flex; align-items: center; gap: 0.5rem; }`
- `.favorite-star { min-width: 2.75rem; min-height: 2.75rem; background: none; border: none; font-size: 1.4rem; color: #8a5a00; cursor: pointer; }` en `.favorite-star:disabled { opacity: 0.5; cursor: default; }`
- `.form-field { margin: 0.75rem 0; }`, `.form-field label { display: block; font-weight: 600; }`, `.checkbox-row label { display: inline; font-weight: normal; margin-left: 0.25rem; }`
- `fieldset { border: 1px solid #ddd; border-radius: 0.25rem; margin: 0.75rem 0; padding: 0.5rem 0.75rem; }`, `fieldset label { display: inline; font-weight: normal; margin: 0 0.75rem 0 0.25rem; }`
- `.hint { margin: 0.125rem 0 0; font-size: 0.875rem; color: var(--color-muted); }`
- `.alert-rule { padding: 0.75rem 0; border-bottom: 1px solid #ddd; }`, `.rule-summary { margin: 0.25rem 0; }`, `.notice { font-size: 0.875rem; color: #8a5a00; }`
- `[aria-invalid='true'] { border-color: #a4161a; }`

### `docs/RUNBOOK.md`
- §11, nieuw punt 8, **Profiel, favorieten en alerts in de app (vanaf WP-16).**
  - Ingelogd zie je een ster bij elke spot (favoriet) en de pagina's Profiel en Alerts. Ze schrijven naar dezelfde tabellen als `shakka admin` (§12).
  - Een favoriet zonder eigen instellingen gebruikt de standaard. "Standaardinstellingen" verwijdert de eigen regel.
  - Een spot uit de favorieten halen verwijdert ook de regel.
  - Ontbreekt een profiel ("Je profiel is niet gevonden"), voer dan in de SQL Editor de backfill uit de migratie uit: `insert into public.profiles (user_id) select id from auth.users on conflict (user_id) do nothing;`.
  - Controle (WP-16 AC-7): zie §12 punt 6 (`admin alerts preview`).
- §12, aan het begin: één zin "Vanaf WP-16 kan dit ook in de app (Profiel, Alerts, ster bij een spot); de CLI blijft werken."

### Gevolgen voor latere WP's
- **WP-18:**
  - "Meldingen op dit apparaat" komt als eigen `<section>` bovenaan `/alerts`, boven de favorieten. De pagina laadt al op `$session`.
  - `push.ts` schrijft `push_subscriptions`. `user-tables.test.ts` (zie Testplan) staat `.from('` alleen in `data.ts` en `user-data.ts` toe; WP-18 voegt `push.ts` en die tabel toe aan die test.
- **WP-22:** bij het verwijderen van de legacy-kolom uit `profiles` faalt `schema-columns.test.ts` (alter-guard). Werk dan de test bij; `PROFILE_COLUMNS` verandert niet.
- **WP-23:**
  - account verwijderen hoort op `/profiel`;
  - de privacypagina noemt gewicht, niveau, quiver, windgrenzen, favorieten en alertinstellingen als profielgegevens;
  - geen nieuwe origins: `connect-src` blijft Supabase.
- **WP-10/WP-17:** geen wijziging. De app schrijft alleen waarden die `AlertRuleOverride.from_row` en `ProfileDefaults.from_row` accepteren, en weigert regels die `resolve_rule` als conflict zou overslaan.

## Edge cases

| # | Geval | Gedrag |
|---|---|---|
| E1 | `$session === undefined` op `/profiel` of `/alerts` | "Laden…", 0 queries. Komt daarna `null`: loginprompt, nog steeds 0 queries. |
| E2 | Uitloggen in een ander tabblad terwijl `/alerts` open is | `$session` wordt `null`, de loginprompt verschijnt, een lopende load wordt genegeerd (token). |
| E3 | Token-refresh (nieuw sessie-object, zelfde user-id) | Geen nieuwe load (`userId` blijft gelijk). |
| E4 | Uitgelogd op `/` of `/spot/[id]` | Geen ster en geen query naar `favorites` (status `signed_out`). |
| E5 | Ster aanklikken terwijl de favorieten laden | Knop `disabled`. |
| E6 | Insert faalt (netwerk) | Ster springt terug, "Niet opgeslagen", `console.warn` zonder details. |
| E7 | Favoriet bestaat al (ander tabblad, `23505`) | Geldt als gelukt. |
| E8 | Ontfavorieten van een spot met een eigen regel | Delete; de regel verdwijnt via de cascade (A14). |
| E9 | Profielrij ontbreekt | `/profiel`: "Je profiel is niet gevonden…", geen formulier en geen poging tot insert (geen grant). `/alerts`: `profile = null`, de defaults komen van spot en systeem. |
| E10 | `updateProfile` geeft `PGRST116` (rij net verdwenen) | "Opslaan is niet gelukt. Probeer het opnieuw." |
| E11 | Gewicht `25`, `201`, `75,5` of `abc` | `weight`-fout, 0 writes. `30` en `200` zijn geldig; leeg geeft `null`. |
| E12 | Quivermaat `2,5`, `22` of `9,123`, of 11 kites | Fout op `quiver_m2`, 0 writes. `3`, `21` en `10,5` zijn geldig; lege velden vallen weg. Bij 10 kites is "Kite toevoegen" uitgeschakeld. |
| E13 | Profiel min `20`, max `20` of `15` | `minNotBelowMax` op `default_max_kn`, 0 writes. |
| E14 | Regel min `20`, max `15` | `minNotBelowMax` op `max_kn`, 0 writes. |
| E15 | Regel min `25`, profiel max `20` (A13) | `conflict` op `min_kn`: "Minimale wind 25 kn (je instelling voor deze spot) moet lager zijn dan maximale wind 20 kn (je profiel).", 0 writes. |
| E16 | Spot `default_min_kn` 22, profiel max 20, regel leeg | Kaart: waarschuwing "Deze instellingen botsen…" (`storedRuleStatus`). Opslaan zonder aanpassing geeft `conflict` op `min_kn`; met een lagere `min_kn` of een hogere `max_kn` in de regel lukt het. |
| E17 | Alle richtingen uitgevinkt | `dirEmpty`, 0 writes. |
| E18 | Alle drie de richtingen of alle zeven dagen aangevinkt | `null` (standaard) in de payload (A5). |
| E19 | Tot `00:00` als bestaande waarde (via de CLI), zonder Vanaf | Kaart: waarschuwing `"Tot 00:00" telt geen enkel uur. Voor deze spot komen geen alerts tot je dit aanpast.` (`storedRuleStatus`), geen samenvatting `00:00–00:00`. In het formulier een extra optie `00:00`. Opslaan geeft `latestMidnight` tot de gebruiker hem wijzigt. (Met Vanaf erbij is de rij al `invalid`: `earliest < 00:00` kan niet.) |
| E20 | `latest_local` `24:00:00` in de database | Het formulier toont "Geen bovengrens". De samenvatting toont `…–24:00`. Opslaan schrijft `null`. |
| E21 | `earliest_local` `24:00:00` in de database | Kaart: "De opgeslagen instelling is ongeldig…". Het formulier toont "Geen ondergrens". Opslaan herstelt de regel (`null`). |
| E22 | `earliest_local` `20:30:00` (via de CLI) | Optie `20:30` erbij, geselecteerd. Opslaan schrijft `20:30:00` ongewijzigd. |
| E23 | `days_ahead` 7 in de database | Optie `7` erbij. 0–6 blijven de normale opties. |
| E24 | Vanaf `18:00`, Tot `17:00` (ook: Tot staat al op 17:00 en de gebruiker kiest Vanaf 19:00) | `ruleHints` gooit niet: `parseRuleFields` zet `latest_local` in de soepele waarde op `null`, en `effectiveRule` staat in een `try`. Het formulier blijft staan met de gewone hints. Bij Opslaan `timeOrder` op `latest_local`, 0 writes. |
| E25 | `days_ahead` 0 | Geldig, "alleen vandaag". Vergelijkingen met `!== null`, nooit met `||`. |
| E26 | Opslaan nadat de favoriet in een ander tabblad is verwijderd (`23503`) | "Deze spot staat niet meer in je favorieten. Herlaad de pagina." |
| E27 | Niet-geverifieerde favoriet | Bewerkbaar, met de melding uit A15. |
| E28 | Lege favorietenlijst | Uitleg met een link naar `/`. |
| E29 | `contracts.ts` krijgt een `alert_defaults.json` met `offshore` in `allowed` of `default` | Module-load faalt met `contract alert_defaults is malformed` (test). |
| E30 | Afgeleide `max_kn` boven 60 (regel min 60) | Hint "standaard: 65 kn (Shakka)", geen fout (WP-07 E3). |
| E31 | Supabase-foutmelding met details | Komt niet op de pagina en niet in de console (`DataError` bevat alleen operatie en code). |
| E32 | Tekst met `<script>` in een spotnaam | Svelte escapet; nergens `{@html}`. |
| E33 | Tijd met seconden of fractie in de database (`17:00:30`, `17:00:30.5`, via de CLI) | `normalizeLocalTime` geeft `17:00:30` resp. `17:00:30.500000` (gelijk aan Python, A18). Het formulier toont die waarde als extra optie; Opslaan schrijft hem ongewijzigd terug. |
| E34 | Min `20`, max `15` tijdens het typen, of een profiel met ongeldige grenzen | `ruleHints` gooit niet. Bij min ≥ max laat de soepele waarde `max_kn` weg; bij een conflict of ongeldig profiel wordt de kn-hint `standaard: botst met je andere windgrenzen`. |
| E35 | `enabled` `null` in een rij (niet mogelijk door `not null`, wel in de gevallen) | Zoals Python: geen waarde, dus `true` met bron `system` (geval 19). |
| E36 | `parseAlertRuleForm` met een ongeldig profiel (bijv. `{20, 20}`; door de DB-constraints niet te verwachten) | Fout op `min_kn`: `Je profiel heeft ongeldige windgrenzen; pas die aan bij Profiel.`, 0 writes. |

## Testplan
Alle webtests staan in `web/test/` en draaien met `npm test`. Tests voor pure logica en data komen vóór de implementatie. Mocks volgen WP-13/WP-14 (`vi.hoisted` plus `vi.mock('#lib/…js', async () => …)`), en elk bestand met mocks heeft `beforeEach(() => vi.clearAllMocks())`.

### Helpers en fixtures
- **`helpers/fake-supabase.ts` (wijzigen).**
  - De lijst methodes van de builder wordt `select`, `eq`, `gte`, `lt`, `not`, `order`, `range`, `maybeSingle`, `single`, `insert`, `update`, `upsert`, `delete` en `in`.
  - Nieuwe export: `writeCalls(calls: Call[]): Call[]` (aanroepen met een op uit `insert`, `update`, `upsert` of `delete`).
  - Bestaand gedrag blijft gelijk.
- **`helpers/fake-session.ts` (nieuw).**
  - `USER_ID = '00000000-0000-4000-8000-000000000001'`;
  - `SESSION = { user: { id: USER_ID, email: 'test@example.org' } }`;
  - `sessionStore = writable<unknown>(undefined)`;
  - `authModule = { session: sessionStore, initAuth: () => () => {}, signOut: async () => {}, initialAuthRedirectError: () => null }`.

  Gebruik: `vi.mock('#lib/auth.js', async () => (await import('./helpers/fake-session.js')).authModule)` en in de test `import { sessionStore, SESSION } from './helpers/fake-session.js'`.
- **`helpers/fake-favorites.ts` (nieuw).**
  - `favoritesState = writable<FavoritesState>({ status: 'signed_out' })`;
  - `toggleFavoriteMock = vi.fn(async () => true)`;
  - `favoritesModule = { favorites: favoritesState, toggleFavorite: toggleFavoriteMock }`.
- **`fixtures/user-data.ts` (nieuw).**
  - `PROFILE_EMPTY: Profile` (`user_id USER_ID`, alles `null`, quiver `[]`, `created_at`/`updated_at` `'2026-10-15T10:00:00+00:00'`);
  - `PROFILE_FULL` (75, `intermediate`, `[9, 12]`, 14, 26);
  - `ruleRow(spotId, overrides): AlertRuleRow` (`enabled true`, de rest `null`, `updated_at` zoals hierboven).

  Spots komen uit `fixtures/spot-data.ts` (`SPOT_VERIFIED` = `test-meer`, `SPOT_UNVERIFIED` = `test-strand`).

### Testbestanden

| Bestand | Tests |
|---|---|
| `rules.test.ts` (node) | **(AC-2)** Leest `../../data/contracts/rule_resolution_cases.json` met `node:fs`. `describe('effectiveRule rule_resolution_cases')` met per geval (`it.each`, naam = `name`) `spot = { ...SPOT_VERIFIED, default_min_kn }`, `profile = case.profile ? { ...PROFILE_EMPTY, ...case.profile } : null` en `override = case.override ? ({ ...ruleRow('test-meer'), ...case.override } as AlertRuleRow) : null` (de cast is nodig voor geval 19, `enabled: null`). Bij `expected.error`: gooit een `RuleError` met die `code`. Anders: `toEqual(expected)`. Dekking: precies 20 gevallen, unieke namen, elke bron uit `RULE_SOURCES` komt in minstens één `expected.sources` voor, er is minstens één `conflict` en één `invalid`, en de sleutels van elk element zijn exact `name, spot, profile, override, expected` (override: exact `RULE_FIELDS`). Verder: `FIELD_SOURCES[f]` is gelijk aan `ALERT_DEFAULTS[f].sources` voor elk veld; `normalizeLocalTime`: `'17:00:00'` → `'17:00'`, `'17:00'` → `'17:00'`, `'17:00:30'` blijft gelijk, `'17:00:00.000'` → `'17:00'`, `'17:00:30.000'` → `'17:00:30'`, `'17:00:30.5'` → `'17:00:30.500000'`, `'17:00:00.5'` → `'17:00:00.500000'`, `'17:00:00.000123'` → `'17:00:00.000123'`, `('24:00:00', 'latest_local')` → `null`, `('24:00', 'earliest_local')` → `RuleError` `invalid`, `'25:00'`, `'7:00'`, `'17:00+02'` en `'17:00:00.1234567'` → `invalid`; `effectiveRule` met override `min_kn` 4, 61 of 12.5, `days_ahead` 8, `weekdays` `[0]` of `[]`, `dir_classes` `[]`, `enabled` `'yes'`, of een ontbrekend veld → `invalid`; `enabled` `null` → `enabled: true` met `sources.enabled === 'system'` (spiegel van Python, A3); earliest `'17:00:30'` en latest `'17:00:30'` → `invalid` op `latest_local`; profiel `{20, 20}` → `invalid` met veld `default_max_kn`; conflictgeval 14 heeft `conflict` `{ min: 25, minSource: 'rule', max: 20, maxSource: 'profile' }`; `days_ahead` 0 in de regel geeft 0 (geen terugval op 3). |
| `contracts.test.ts` (wijzigen) | `ALERT_DEFAULTS`: de sleutels in `RULE_FIELDS`-volgorde, `dir_classes.allowed` exact `['onshore', 'side_onshore', 'sideshore']`, `min_kn.default === 12`, `max_kn.min_span_kn === 5`. `parseAlertDefaults` gooit `contract alert_defaults is malformed` bij een kopie met `offshore` in `allowed`, met `side_offshore` in `default`, met 8 items, met een verkeerde `field`-volgorde, met een lege `label_nl`, en met `sources` die niet op `system` eindigen. |
| `forms.test.ts` | Profiel: `parseProfileForm` met gewicht `'25'`, `'201'`, `'75,5'` en `'abc'` → fout `weight`; `'30'` en `'200'` → ok. Quiver `['2,5']`, `['22']` en `['9,123']` → fout `quiver_m2`; 11 maten → `quiverCount`; `['12', '', '10,5', ' 9 ']` → `[9, 10.5, 12]`. Min/max `'20'`/`'20'` → `minNotBelowMax` op `default_max_kn`; `'4'` → `kn`. Het resultaat heeft exact de vijf sleutels. `profileToForm(PROFILE_FULL)` geeft quiver `['9', '12']`, en `[10.5]` geeft `['10,5']`. `profileKnHints` geeft de twee teksten uit Interfaces. Regel: `ruleToForm(null)` geeft de defaults; een rij met `latest_local '24:00:00'` geeft `''`, `earliest_local '24:00:00'` geeft `''` en `'20:30:00'` geeft `'20:30'`. `parseAlertRuleForm`: E14, E15 (fout op `min_kn` met de tekst uit E15), E16 (conflict zonder regelwaarden → `min_kn`; met regel `max_kn` 26 → ok), E17, E18 (`null`), E19, E24, `days_ahead` `'7'` geldig, `'8'` ongeldig, `'0'` → 0; een geldig formulier geeft exact de negen sleutels met tijden `'17:00:00'`; `dir_classes` `['offshore']` (gecast) → `dirInvalid`. `ruleHints`: leeg formulier met `PROFILE_FULL` → `min_kn` `'standaard: 14 kn (je profiel)'` en `max_kn` `'standaard: 26 kn (je profiel)'`; zonder profiel met spot 16 → `'standaard: 16 kn (spotprofiel)'` en `'standaard: 30 kn (Shakka)'`; `min_kn` `'28'`, max leeg, zonder profiel → `max_kn` `'standaard: 33 kn (Shakka)'`; `min_kn` `'60'` → `'standaard: 65 kn (Shakka)'`; `days_ahead` leeg → `'standaard: vandaag plus 3 dagen (Shakka)'`; bij een conflict met het profiel → `'standaard: botst met je andere windgrenzen'`; een ingevuld veld heeft geen hint. `ruleSummary` van de defaults → `'Aan · 12–30 kn · min. 2 uur go · vandaag plus 3 dagen'`; van geval 7 → `'Uit · 18–24 kn · Sideshore (langs de kust) · za, zo · 17:00–21:00 · min. 3 uur go · vandaag plus 5 dagen'`. `storedRuleStatus` geeft bij E16 en E21 de twee teksten uit Interfaces. `timeOptions('')` heeft 23 items van `'01:00'` t/m `'23:00'` en bevat geen `'00:00'` en geen `'24:00'`; `timeOptions('20:30')` bevat `'20:30'` tussen `'20:00'` en `'21:00'`. `daysAheadOptions('')` → `'0'`…`'6'`; `daysAheadOptions('7')` eindigt op `'7'`. **(B-1, E24, E34)** `parseRuleFields` met Vanaf `'18:00'` en Tot `'17:00'` → `errors.latest_local` is `timeOrder`, `value.earliest_local === '18:00:00'`, `value.latest_local === null`; met min `'20'` en max `'15'` → `errors.max_kn` is `minNotBelowMax`, `value.min_kn === 20`, `value.max_kn === null`; met Tot `'00:00'` → `value.latest_local === null`. Voor elk van deze drie formulieren, en voor het lege formulier met profiel `{ default_min_kn: 20, default_max_kn: 20 }` (ongeldig) en met spot 22 en profiel `{ null, 20 }` (conflict): `expect(() => ruleHints(f, ctx)).not.toThrow()`, en `effectiveRule(ctx.spot, null, parseRuleFields(f, ALERT_DEFAULTS).value, ALERT_DEFAULTS)` gooit niet. Vanaf `'18:00'`, Tot `'17:00'`, rest leeg, met `PROFILE_FULL` → `ruleHints(...).min_kn === 'standaard: 14 kn (je profiel)'` en geen hint voor `latest_local`. Het ongeldige profiel en het conflict geven `min_kn` `'standaard: botst met je andere windgrenzen'` en `min_go_hours` `'standaard: 2 uur (Shakka)'`. **(N-5, E36)** `parseAlertRuleForm` met een geldig formulier en profiel `{20, 20}` → `{ ok: false, errors: { min_kn: 'Je profiel heeft ongeldige windgrenzen; pas die aan bij Profiel.' } }`. **(N-4, E19)** `storedRuleStatus(ruleRow('test-meer', { latest_local: '00:00:00' }), ctx)` → `ok: false` met de tekst `"Tot 00:00" telt geen enkel uur. Voor deze spot komen geen alerts tot je dit aanpast.`; met `latest_local: '00:30:00'` → `ok: true`. **(E33)** `ruleToForm` met `earliest_local '17:00:30.5'` → `'17:00:30.500000'`; `parseAlertRuleForm` met Vanaf `'17:00:30.500000'` schrijft `'17:00:30.500000'`, met Vanaf `'17:00:30'` schrijft `'17:00:30'`, met Vanaf `'17:00'` schrijft `'17:00:00'`; Vanaf `'17:0'` → `time`. |
| `labels.test.ts` (wijzigen) | `LEVEL_LABEL_NL` heeft voor elke waarde uit `LEVELS` een niet-leeg label. `SOURCE_LABEL_NL` heeft alle vier de bronnen. `daysAheadText(0)`, `(1)` en `(3)` geven de teksten uit Interfaces. |
| `schema-columns.test.ts` (wijzigen) | `PROFILE_COLUMNS` is gelijk aan de kolommen van `profiles` zonder `telegram_chat_id`, in dezelfde volgorde. `FAVORITE_COLUMNS` = `favorites`, `ALERT_RULE_COLUMNS` = `alert_rules`, en `RULE_FIELDS` = `ALERT_RULE_COLUMNS` zonder `user_id`, `spot_id` en `updated_at`, in volgorde. `PROFILE_EDITABLE_COLUMNS` is als set gelijk aan de kolommen in `grant update (…) on table public.profiles to authenticated` uit `20261015090100_m1_security.sql` (regex `/grant update \(([^)]*)\)\s+on table public\.profiles to authenticated/`). De alter-guard dekt ook `profiles`, `favorites` en `alert_rules`. |
| `form-ranges.test.ts` (node) | Leest alle migraties. `profiles_weight_range` (`between 30 and 200`) = `WEIGHT_RANGE_KG`. Uit `profiles_quiver_valid`: `cardinality(quiver_m2) <= 10` = `MAX_QUIVER_KITES`, `3 <= all` en `21 >= all` = `QUIVER_SIZE_RANGE_M2`. `profiles_min_kn_range`, `profiles_max_kn_range`, `alert_rules_min_kn_range` en `alert_rules_max_kn_range` = `[ALERT_DEFAULTS.min_kn.min, .max]` en `[ALERT_DEFAULTS.max_kn.min, .max]`; `alert_rules_min_go_hours_range` en `alert_rules_days_ahead_range` = de `min`/`max` uit `ALERT_DEFAULTS`. De array in `alert_rules_dir_classes_ridable` = `ALERT_DEFAULTS.dir_classes.allowed` (als set); `alert_rules_weekdays_iso` = `weekdays.allowed`. Zelfde zoekaanpak als WP-07 (fragment van 1500 tekens na de constraintnaam). |
| `user-data.test.ts` | Fake-supabase via `vi.mock('#lib/supabase.js', …)`, zoals in `data.test.ts`. Per functie de exacte reeks aanroepen uit de querytabel, inclusief `range(0, 999)` bij de lijsten. De `update`-payload heeft exact de sleutels `PROFILE_EDITABLE_COLUMNS`, ook als `values` extra sleutels bevat (via een cast meegegeven `updated_at`). De `select`-strings bevatten geen `telegram`. De `upsert` heeft `{ onConflict: 'user_id,spot_id' }` en een payload met exact `user_id`, `spot_id` en de negen `RULE_FIELDS`. `addFavorite` met fout `23505` → geen fout; met `42501` → `DataError` met code `42501`, en een `message: 'secret detail'` staat niet in de foutmelding. `saveAlertRule` met `23503` → `DataError` met code `23503`. `getProfile` met `data: null` → `null`. |
| `user-tables.test.ts` (node) | **(contract: alleen deze tabellen schrijven)** Leest alle `.ts`- en `.svelte`-bestanden onder `src/`. Bestanden met `/\.from\('/`: exact `lib/data.ts` en `lib/user-data.ts`. In `user-data.ts` noemt elke `.from('x')` alleen `profiles`, `favorites` of `alert_rules` (elk minstens één keer). `data.ts` bevat geen `/\.(insert\|update\|upsert\|delete)\(/`. In `user-data.ts`: `.update(` komt precies één keer voor en matcht `/\.from\('profiles'\)\s*\.update\(/`; elke `.insert(` matcht `/\.from\('favorites'\)\s*\.insert\(/`; elke `.upsert(` matcht `/\.from\('alert_rules'\)\s*\.upsert\(/`. Geen bestand onder `src/` bevat `.rpc(`. |
| `user-page-data.test.ts` | Mockt `#lib/user-data.js` en `#lib/data.js`. `loadProfilePage`: ok, `missing` (null) en `error` (reject met `new Error('secret detail')` → één `console.warn` zonder die tekst en zonder `USER_ID`). `loadAlertsPage`: favorieten `['test-strand', 'test-meer', 'weg']`, spots `[SPOT_VERIFIED, SPOT_UNVERIFIED]` (lijstvolgorde Testmeer, Teststrand) en een regel voor `test-meer` → entries `[{ spot: SPOT_VERIFIED, rule: R }, { spot: SPOT_UNVERIFIED, rule: null }]`; `'weg'` valt weg; elke functie wordt aangeroepen met `USER_ID`. Een error volgt het patroon hierboven. |
| `favorites.test.ts` | Mockt `#lib/supabase.js` (fake) en `#lib/auth.js` (fake-session); echte `favorites.ts` en `user-data.ts`. Bij sessie `undefined` en `null` en een abonnement: status `unknown` respectievelijk `signed_out`, 0 aanroepen. Met `SESSION` en een antwoord `[{ spot_id: 'test-meer' }]`: eerst `loading`, daarna `ready` met `{'test-meer'}`. Een nieuw sessie-object met dezelfde id geeft geen nieuwe query; een andere id wel. Opzeggen en opnieuw abonneren geeft een nieuwe query (A2). `toggleFavorite('test-strand')` → direct `ready` met beide id's en een insert-call; bij een insertfout → terug naar `{'test-meer'}` en `false`. `toggleFavorite` bij `signed_out` → `false` en geen call. Een trage load voor gebruiker A die afloopt nadat B is ingelogd, overschrijft B niet. |
| `favorite-star.test.ts` | **(AC-5)** Zelfde mocks als `favorites.test.ts`. Ingelogd, favorieten `[]`: de knop `Favoriet: Teststrand` met `aria-pressed="false"` (na `findByRole`, niet `disabled`). Klik → een call op `favorites` met ops `[['insert', { user_id: USER_ID, spot_id: 'test-strand' }]]` en `aria-pressed="true"`. Nog een klik → ops `[['delete'], ['eq', 'user_id', USER_ID], ['eq', 'spot_id', 'test-strand']]` en `aria-pressed="false"`. Insertfout → `aria-pressed="false"` en de tekst `Niet opgeslagen`. Uitgelogd (`null`) of onbekend (`undefined`): geen knop en `fake.calls.length === 0`. |
| `alert-rule-form.test.ts` | Mockt `#lib/supabase.js` (fake). Rendert `AlertRuleForm` met `userId USER_ID`, `spot SPOT_VERIFIED`, `profile PROFILE_FULL`, `row null` en `onsaved vi.fn()`. **(AC-3)** `within(getByRole('group', { name: 'Windrichtingen' })).getAllByRole('checkbox')` heeft exact de waarden `['onshore', 'side_onshore', 'sideshore']` en de toegankelijke namen `Aanlandig`, `Schuin aanlandig` en `Sideshore (langs de kust)`. Nergens in de component staat een checkbox met waarde `side_offshore` of `offshore` (`container.querySelectorAll('input[type=checkbox]')`), en geen label `Aflandig` of `Schuin aflandig`. **(AC-4)** min `20`, max `15`, klik Opslaan → de fout `De maximale wind moet hoger zijn dan de minimale wind.` en `writeCalls(fake.calls).length === 0`. Conflict: min `30` (profielmax 26) → een fout die `je profiel` bevat, 0 writes. Alle richtingen uit → `Kies minstens één windrichting.`, 0 writes. Geldig (min `14`, dagen alleen za en zo, Vanaf `17:00`) → precies één call op `alert_rules` met ops `upsert` (payload `{ user_id: USER_ID, spot_id: 'test-meer', enabled: true, min_kn: 14, max_kn: null, dir_classes: null, weekdays: [6, 7], earliest_local: '17:00:00', latest_local: null, min_go_hours: null, days_ahead: null }`, `{ onConflict: 'user_id,spot_id' }`), `select` en `single`; daarna `Opgeslagen.` en `onsaved` met de teruggegeven rij. Hints: het lege min-veld toont `standaard: 14 kn (je profiel)`. Opties van "Tot": geen `00:00` en geen `24:00`. Opties van "Dagen vooruit": `''` en `0`–`6`, geen `7`; met een `row` met `days_ahead: 7` wel `7`. Met een `row`: de knop `Standaardinstellingen` → een delete-call met `eq('user_id', USER_ID)` en `eq('spot_id', 'test-meer')`, en `onsaved(null)`. Zonder `row` is die knop er niet. **(B-1, E24)** Met `row = ruleRow('test-meer', { latest_local: '17:00:00' })`: `await user.selectOptions(getByLabelText('Vanaf (lokale tijd)'), '19:00')` (`@testing-library/user-event`, al aanwezig) gooit niet; daarna staan de knop `Opslaan` en de hint `standaard: 14 kn (je profiel)` er nog. Klik Opslaan → de tekst `"Tot" moet later zijn dan "Vanaf".`, `role="alert"` met `Niet opgeslagen: controleer de gemarkeerde velden.` en `writeCalls(fake.calls).length === 0`. Om een onopgevangen fout zichtbaar te maken, faalt de test ook als er tijdens de test een `error`-event op `window` komt (`window.addEventListener('error', spy)`, na afloop `expect(spy).not.toHaveBeenCalled()`). |
| `profile-page.test.ts` | Mockt `#lib/supabase.js` (fake) en `#lib/auth.js` (fake-session). **(AC-6)** `sessionStore.set(null)` → link `Inloggen` (`href="/login"`), tekst `Log in om je profiel te bewerken.` en `fake.calls.length === 0`. `undefined` → `Laden…` en 0 calls. **(AC-4)** Met `SESSION` en het antwoord `PROFILE_EMPTY` (een `profiles`-response voor `maybeSingle`), na `findByLabelText('Gewicht (kg)')`: gewicht `25` → Opslaan → de `weight`-fout en `writeCalls(...).length === 0`. Idem: "Kite toevoegen" en `25` → de quiverfout; min `20` en max `15` → `minNotBelowMax`. Geldig (gewicht `75`, niveau `Gemiddeld`, kites `9` en `12`) → precies één write: ops `[['update', { weight_kg: 75, level: 'intermediate', quiver_m2: [9, 12], default_min_kn: null, default_max_kn: null }], ['eq', 'user_id', USER_ID], ['select', PROFILE_COLUMNS.join(',')], ['single']]` en `Opgeslagen.`. Lege kn-velden tonen de hints uit `profileKnHints`. `missing` (data `null`) → de melding uit Interfaces. Een loadfout → `role="alert"` en `Opnieuw proberen` doet een nieuwe query. |
| `alerts-page.test.ts` | Zelfde mocks. **(AC-6)** `null` → `Log in om je alerts in te stellen.`, 0 calls; `undefined` → 0 calls. Met `SESSION` en de antwoorden profiles `PROFILE_FULL`, favorites `[{ spot_id: 'test-meer' }, { spot_id: 'test-strand' }]`, alert_rules `[ruleRow('test-meer', { min_kn: 18 })]` en spots `[SPOT_VERIFIED, SPOT_UNVERIFIED]`: twee secties in de volgorde Testmeer, Teststrand; Testmeer toont `Aan · 18–26 kn · min. 2 uur go · vandaag plus 3 dagen`; Teststrand toont de niet-geverifieerd-melding en `Aan · 14–26 kn · …`. Met profiel `{ default_max_kn: 20 }` en regel `min_kn: 25` voor Testmeer → `role="note"` met `Deze instellingen botsen`. Geen favorieten → de uitleg met een link naar `/`. Na opslaan in het formulier van Testmeer (min `16`) wordt de samenvatting `Aan · 16–26 kn · …`. **(N-8)** Vóór elke interactie met een formulier opent de test het `<details>`-element van die sectie expliciet: `const details = section.querySelector('details')!; details.open = true; await tick();` (`tick` uit `'svelte'`), en zoekt daarna met `within(section)`. Zo hangt de test niet af van hoe jsdom de inhoud van een dicht `<details>` of een klik op `<summary>` behandelt. Een extra test controleert dat `details.open` bij het laden `false` is. |
| `layout.test.ts` (wijzigen) | Ingelogd: links `Alerts` (`/alerts`) en `Profiel` (`/profiel`). Uitgelogd en onbekend: geen van beide. |
| `spot-list.test.ts`, `spot-page.test.ts` (wijzigen) | Extra `vi.mock('#lib/favorites.js', async () => (await import('./helpers/fake-favorites.js')).favoritesModule)`. De mock die een fout geeft bij een import van `#lib/supabase.js` blijft staan. Nieuwe tests: bij `signed_out` geen knop `Favoriet: …`; bij `{ status: 'ready', userId: USER_ID, ids: new Set(['test-meer']) }` heeft de lijst `Favoriet: Testmeer` met `aria-pressed="true"` en `Favoriet: Teststrand` met `false`; een klik roept `toggleFavoriteMock` aan met `'test-strand'`. Op de spotpagina staat de ster in `.title-row` naast de `h1`. De bestaande tests blijven groen. |
| `no-telegram.test.ts` (node) | **(AC-8)** Geen bestand onder `src/` bevat `/telegram/i`. |

### Python: `ingest/tests/test_rule_resolution_cases.py`
De structuur ligt vast; de builder vult alleen de opmaak in (ruff bepaalt de importvolgorde, zoals in `test_windows.py`):
```python
"""WP-16 AC-2: shared rule resolution cases (the TypeScript side is web/test/rules.test.ts)."""

import json
from datetime import time
from typing import Any

import pytest
from pydantic import ValidationError

from evaluation_fixtures import make_spot
from shakka.config import REPO_ROOT
from shakka.domain.alerts import (
    FIELD_SOURCES,
    RULE_FIELDS,
    AlertRuleOverride,
    ProfileDefaults,
    RuleSource,
    resolve_rule,
)
from shakka.domain.direction import DirClass
from shakka.domain.spot import SpotProfile

CASES_PATH = REPO_ROOT / "data" / "contracts" / "rule_resolution_cases.json"
CASES: list[dict[str, Any]] = json.loads(CASES_PATH.read_text(encoding="utf-8"))
DIR_ORDER = [c.value for c in DirClass]  # onshore, side_onshore, sideshore, ... (= contract order)
CASE_KEYS = {"name", "spot", "profile", "override", "expected"}


def _fmt(t: time | None) -> str | None:
    """None -> None; 'HH:MM' when second and microsecond are 0, else t.isoformat() (A18)."""
    if t is None:
        return None
    if t.second == 0 and t.microsecond == 0:
        return t.strftime("%H:%M")
    return t.isoformat()


def _parse(case: dict[str, Any]) -> tuple[ProfileDefaults | None, AlertRuleOverride | None]:
    p, o = case["profile"], case["override"]
    profile = ProfileDefaults.from_row(p) if p is not None else None
    override = AlertRuleOverride.from_row(o) if o is not None else None
    return profile, override


def _expected_sources(
    spot: SpotProfile, profile: ProfileDefaults | None, override: AlertRuleOverride | None
) -> dict[str, str]:
    """Per field the first level in FIELD_SOURCES[field] whose PARSED input is not None:
    RULE -> getattr(override, field) (None if override is None; so latest_local 24:00, which
    from_row turns into None, counts as system, and enabled None too);
    PROFILE -> profile.default_min_kn / default_max_kn (min_kn / max_kn only);
    SPOT -> spot.default_min_kn (min_kn only); SYSTEM -> always."""
    out: dict[str, str] = {}
    for field in RULE_FIELDS:
        for source in FIELD_SOURCES[field]:
            if source is RuleSource.RULE:
                value = getattr(override, field) if override is not None else None
            elif source is RuleSource.PROFILE:
                value = getattr(profile, f"default_{field}") if profile is not None else None
            elif source is RuleSource.SPOT:
                value = spot.default_min_kn
            else:
                value = True  # SYSTEM always has a value
            if value is not None:
                out[field] = source.value
                break
    return out


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_rule_resolution_cases(case: dict[str, Any]) -> None:
    spot = make_spot(default_min_kn=case["spot"]["default_min_kn"])
    expected = case["expected"]
    if expected.get("error") == "invalid":
        with pytest.raises(ValidationError):
            _parse(case)
        return
    profile, override = _parse(case)
    if expected.get("error") == "conflict":
        with pytest.raises(ValueError, match="must be below") as exc:
            resolve_rule(spot, profile, override)
        assert not isinstance(exc.value, ValidationError)
        return
    rule = resolve_rule(spot, profile, override)
    actual = {
        "enabled": rule.enabled,
        "min_kn": rule.min_kn,  # float; == with the int in the file
        "max_kn": rule.max_kn,
        "dir_classes": [c.value for c in sorted(rule.dir_classes, key=DIR_ORDER.index)],
        "weekdays": sorted(rule.weekdays),
        "earliest_local": _fmt(rule.earliest_local),
        "latest_local": _fmt(rule.latest_local),
        "min_go_hours": rule.min_go_hours,
        "days_ahead": rule.days_ahead,
    }
    assert actual == {k: v for k, v in expected.items() if k != "sources"}
    assert _expected_sources(spot, profile, override) == expected["sources"]


def test_rule_resolution_cases_coverage() -> None: ...
```
- `rule` komt dus uit `resolve_rule(make_spot(default_min_kn=…), ProfileDefaults.from_row(p) if p else None, AlertRuleOverride.from_row(o) if o else None)`, en `_expected_sources` werkt op dezelfde geparste modellen (niet op de ruwe JSON). Daardoor telt `latest_local` 24:00 in geval 12 en `enabled: null` in geval 19 als `system`.
- `invalid`: de `ValidationError` komt uit `from_row` (bij een ontbrekende kolom zou het een gewone `ValueError` zijn; die komt in de gevallen niet voor, want een override heeft altijd alle negen velden).
- `conflict`: beide `from_row`-aanroepen slagen, en `resolve_rule` geeft een `ValueError` die geen `ValidationError` is, met `"must be below"` in de melding.
- Anders: `actual` (zonder `sources`) is gelijk aan `expected` zonder `sources`, en `_expected_sources(...) == expected["sources"]`. Zo is gecontroleerd dat de bronnen in het bestand kloppen met de tabel `FIELD_SOURCES` van WP-07.
- Coverage: precies 20 gevallen, unieke namen, elke `RuleSource`-waarde komt in minstens één `sources` voor, minstens één `conflict` en één `invalid`, `set(case) == CASE_KEYS` per element, en een override heeft exact `set(RULE_FIELDS)` als sleutels.

### Per acceptatiecriterium
- **AC-1:** `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`; vanuit de root `bash scripts/check-no-client-openmeteo.sh`; en `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .`.
- **AC-2:** `cd ingest && uv run pytest -k rule_resolution_cases` en `cd web && npx vitest run test/rules.test.ts`, allebei op `data/contracts/rule_resolution_cases.json` (20 gevallen, alle vier de niveaus).
- **AC-3:** `alert-rule-form.test.ts` (groep Windrichtingen).
- **AC-4:** `profile-page.test.ts` (gewicht, quiver, min ≥ max, 0 writes) en `alert-rule-form.test.ts` (min ≥ max, conflict, 0 writes); ondersteund door `forms.test.ts`.
- **AC-5:** `favorite-star.test.ts` (insert en delete met `spot_id`); ondersteund door `favorites.test.ts`.
- **AC-6:** `profile-page.test.ts` en `alerts-page.test.ts` (loginprompt, `fake.calls.length === 0` bij `null` en `undefined`); `favorite-star.test.ts` (uitgelogd geen ster en geen query).
- **AC-7:** `NEEDS_LARS`.
  1. Log in op de gedeployde site of lokaal (`npm run dev` met `web/.env` op het echte project) en maak een geverifieerde spot favoriet.
  2. Draai `cd ingest && uv run shakka admin alerts preview --user-id <id>` en noteer de uitvoer.
  3. Zet op `/alerts` voor die spot "Alert aan" uit en sla op, of beperk de dagen.
  4. Draai de preview opnieuw. De favoriet staat nu als `disabled`, of de windows en berichten zijn veranderd.
- **AC-8:** `grep -rni "telegram" web/src` geeft niets; automatisch via `no-telegram.test.ts`.

## Externe afhankelijkheden
Gecontroleerd op 15 oktober 2026. **Geen nieuwe packages.** Gebruikt worden de versies uit WP-13/WP-14 (`@supabase/supabase-js` ^2.117.3, `@sveltejs/kit` ^3.0.1, `svelte` ^5.57.2, `vitest` ^5.0.4, `@testing-library/svelte` ^5.4.2).

| Onderwerp | Gebruik | Bron |
|---|---|---|
| supabase-js `update(values)`: een filter is nodig; rijen komen alleen terug met `.select()` na de filters | `updateProfile` | https://supabase.com/docs/reference/javascript/update |
| supabase-js `upsert(values, { onConflict })`: "Comma-separated UNIQUE column(s)"; rijen alleen met `.select()` | `saveAlertRule` (`'user_id,spot_id'` = PK) | https://supabase.com/docs/reference/javascript/upsert, https://supabase.github.io/postgrest-js/v2/classes/PostgrestQueryBuilder.html |
| supabase-js `insert`, `delete` met `.eq()` | Favorieten, reset | https://supabase.com/docs/reference/javascript/insert, https://supabase.com/docs/reference/javascript/delete |
| supabase-js `single()`: precies één rij, anders een fout; `maybeSingle()`: nul of één | `updateProfile`, `saveAlertRule`, `getProfile` | https://supabase.com/docs/reference/javascript/single, https://supabase.com/docs/reference/javascript/maybesingle |
| RLS: "To perform an UPDATE operation, a corresponding SELECT policy is required" | `profiles` en `alert_rules` hebben een select-policy (WP-01) | https://supabase.com/docs/guides/database/postgres/row-level-security |
| PostgREST-foutcodes: `PGRST116` (406, geen of meer dan één rij bij een enkelvoudig antwoord), `23505` en `23503` (409), `42501` (403/401) | Foutafhandeling | https://docs.postgrest.org/en/v12/references/errors.html |
| Kolomgrant: `authenticated` mag in `profiles` alleen `weight_kg`, `level`, `quiver_m2`, `default_min_kn` en `default_max_kn` updaten, zonder insert; `favorites` en `alert_rules` hebben volledige CRUD op de eigen rijen | Schrijfregel | `supabase/migrations/20261015090100_m1_security.sql` (WP-01; E12 en R8 in de WP-01-blueprint) |
| Svelte stores `readable(initial, start)`: `start` bij de eerste abonnee, de teruggegeven `stop` bij de laatste | `favorites.ts` | https://svelte.dev/docs/svelte/stores |
| Svelte 5 `bind:group` op checkboxes (bindt een array van de aangevinkte `value`s; dat niet-stringwaarden zoals de getallen 1–7 behouden blijven, staat in de docs alleen expliciet voor `<select bind:value>`, niet voor `bind:group`, dus R5-fallback), `$effect`, `$derived`, `$state` | Formulieren, laden | https://svelte.dev/docs/svelte/bind, https://svelte.dev/docs/svelte/$effect |
| Svelte `untrack(fn)` uit `'svelte'` en de compilerwaarschuwing `state_referenced_locally` ("This reference only captures the initial value of …"; oplossing: verwijzen binnen een closure) | Beginwaarde van `form` in `AlertRuleForm` | https://svelte.dev/docs/svelte/svelte, https://svelte.dev/docs/svelte/compiler-warnings |
| Pydantic 2.14 (lockfile) leest `time` uit strings volgens speedate: `HH:MM`, `HH:MM:SS`, `HH:MM:SS.FFFFFF` ("1 to 6 digits are reflected in the time.microsecond, extra digits are ignored"), optioneel een tijdzone | A18, geval 20 | https://pydantic.dev/docs/validation/latest/api/pydantic/standard_library_types/, https://github.com/pydantic/speedate |
| Resolutieregels | `effectiveRule` | `docs/wp/WP-07/blueprint.md` (Ontwerp, A6, A7, E36, E37, "Gevolgen", WP-16), `ingest/src/shakka/domain/alerts.py` |

Geen Open-Meteo, geen nieuwe dienst, geen analytics en geen derde partij. Alles loopt via de bestaande Supabase-client met de publishable key.

## Risico's
- **R1. Drift tussen TS en Python.** Mitigatie: het gedeelde gevallenbestand, met de bronnen getoetst tegen `FIELD_SOURCES` aan beide kanten, plus `FIELD_SOURCES` tegen `alert_defaults.json`. Een wijziging aan `resolve_rule` zonder een nieuw geval valt niet automatisch op; de review van zo'n WP moet het bestand uitbreiden.
- **R2. Upsert en kolomrechten tegen de echte database zijn niet unit-getest.** De tests gebruiken een nep-client. Mitigatie: stap 10 van het stappenplan doet een rooktest tegen de lokale stack (`supabase start`, RLS en grants zoals in productie), en AC-7 toetst het end-to-end.
- **R3. Conflicten via het profiel (A13).** Een profielgrens kan voor één spot een conflict geven dat pas op `/alerts` zichtbaar is. Dan komen er voor die spot geen alerts tot de gebruiker het aanpast. Mitigatie: een duidelijke waarschuwing per favoriet. Blokkeren op `/profiel` zou extra queries en complexere UX vragen.
- **R4. Ontfavorieten wist de regel (A14).** Onbedoeld werk kan verloren gaan. Mitigatie: de uitleg op `/alerts`. Een bevestigingsdialoog is buiten scope.
- **R5. Svelte 5-details.** Het wijzigen van `e.rule` in een `$state`-lijst is gedocumenteerd maar subtiel; dat `bind:group` getallen behoudt, staat niet letterlijk in de docs (zie Externe afhankelijkheden). De componenttests dekken beide. Werkt `bind:group` met getallen niet zoals verwacht, dan gebruikt de builder string-waarden plus omzetting naar getallen in `parseRuleFields` (en terug in `ruleToForm`), en legt dat vast in `deviations.md`.
- **R8. Fouten in afgeleide state breken een component.** Een `throw` in `$derived` die de template gebruikt, laat het formulier crashen (review B-1). Mitigatie: alles wat `AlertRuleForm` in `$derived` aanroept (`ruleHints`, `timeOptions`, `daysAheadOptions`) gooit nooit; `ruleHints` vangt `effectiveRule` af en krijgt een invoer die stap 2 altijd haalt. Tests in `forms.test.ts` en `alert-rule-form.test.ts` (E24, E34).
- **R6. Optimistische ster en meerdere tabbladen.** Een ster in een ander tabblad kan verouderd zijn tot de volgende navigatie (A2). Gevolgen zijn klein: een dubbele insert geldt als gelukt (E7), en een delete van een niet-bestaande rij is geen fout.
- **R7. Apparaatklok en tijdzone spelen hier geen rol.** Er is geen datumlogica in deze WP (tijden zijn lokale wandkloktijden als strings), dus de bestaande test `no-local-date-getters` blijft geldig.

## Buiten scope
- Push-instellingen en "Meldingen op dit apparaat" (WP-18); account verwijderen (WP-23); privacytekst (WP-23).
- Persoonlijke grenzen op de spotpagina of in de lijst (WP-14 toont spot-defaults).
- De legacy-kolom in `profiles`: niet in types, queries of UI; WP-22 verwijdert hem.
- Migraties, RLS-wijzigingen en wijzigingen aan `ingest/src` (domein, CLI, jobs).
- Volgorde van favorieten instellen, notities per favoriet, bevestigingsdialogen, offline bewerken.
- Een bronfunctie in Python (A4).
- `forecast_days` naar 8 (WP-03/WP-10; A8 begrenst alleen de UI).

## Stappenplan voor de builder
Werk in de worktree `/Users/larst/Dev/Shakka/.claude/worktrees/WP-16` op branch `wp/WP-16`, met Node 24. Lees of print `.env` en `web/.env` nooit. Na elke stap vanuit `web/`: `npm run check && npm test`. Vanaf stap 2 ook `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .`. Eén commit per stap, in het Engels (bijv. `WP-16: add rule resolution mirror and shared cases`).

1. **Types en contract (tests eerst).**
   - Breid `test/schema-columns.test.ts` en `test/contracts.test.ts` uit en schrijf `test/form-ranges.test.ts`, voorlopig zonder de `forms.ts`-constanten (die komen in stap 3).
   - Rood. Breid `src/lib/types.ts` en `src/lib/contracts.ts` uit (`parseAlertDefaults`, `ALERT_DEFAULTS`).
   - Groen.
2. **Effectieve regel en pariteit (tests eerst).**
   - Schrijf `data/contracts/rule_resolution_cases.json` (alle 20 elementen voluit, volgens de tabel), `ingest/tests/test_rule_resolution_cases.py` en `web/test/rules.test.ts`.
   - Draai eerst de Python-test: die moet groen zijn zonder codewijziging. Is hij rood, dan zit de fout in het JSON-bestand; corrigeer dat, niet `alerts.py`.
   - Maak dan `src/lib/rules.ts`. Groen.
3. **Labels en formulieren (tests eerst).**
   - Breid `test/labels.test.ts` uit, schrijf `test/forms.test.ts` en vul `form-ranges.test.ts` aan met de `forms.ts`-constanten. Rood.
   - Breid `src/lib/labels.ts` uit en maak `src/lib/forms.ts`. Groen.
4. **Data (tests eerst).**
   - Breid `test/helpers/fake-supabase.ts` uit en maak `test/helpers/fake-session.ts`, `test/fixtures/user-data.ts`, `test/user-data.test.ts` en `test/user-tables.test.ts`. Rood.
   - Maak `src/lib/user-data.ts`. Groen.
   - Controleer `grep -n "\.from(" web/src/lib/data.ts` (WP-14 AC-6, ongewijzigd).
5. **Paginadata (tests eerst).** Schrijf `test/user-page-data.test.ts`. Rood. Maak `src/lib/user-page-data.ts`. Groen.
6. **Favorieten.**
   - Schrijf `test/favorites.test.ts` en `test/favorite-star.test.ts`. Rood.
   - Maak `src/lib/favorites.ts` en `FavoriteStar.svelte`. Groen.
   - Voeg de ster toe aan `/` en `/spot/[id]`. Maak `test/helpers/fake-favorites.ts` en werk `spot-list.test.ts` en `spot-page.test.ts` bij (mock plus nieuwe tests). Groen.
7. **Alertformulier.** Schrijf `test/alert-rule-form.test.ts`. Maak `AlertRuleForm.svelte` en `LoginPrompt.svelte`. Groen.
8. **Pagina's en navigatie.**
   - Schrijf `test/profile-page.test.ts` en `test/alerts-page.test.ts`, en breid `test/layout.test.ts` uit.
   - Maak `src/routes/profiel/+page.svelte` en `src/routes/alerts/+page.svelte`, pas `+layout.svelte` aan en voeg de stijlen toe aan `app.css`.
   - Groen, plus `npm run build && npm run verify:build`.
9. **Guards en documentatie.** Schrijf `test/no-telegram.test.ts` en werk `docs/RUNBOOK.md` bij (§11 punt 8, §12).
10. **Rooktest tegen de lokale stack.** Docker moet draaien; lukt dat niet, dan noteer je het in `deviations.md` en blijft het onderdeel van AC-7.
    - `supabase start`, maak in Studio een gebruiker aan, en `cd ingest && uv run shakka spots sync` met de lokale `.env`.
    - Zet `web/.env` op de lokale stack, start `npm run dev` en log in via Mailpit.
    - Controleer:
      - ster aan en uit (rij in `favorites`);
      - profiel opslaan (alleen de vijf kolommen veranderen, geen `42501`);
      - een regel opslaan (upsert, ook een tweede keer = update) en "Standaardinstellingen" (rij weg);
      - ontfavorieten verwijdert de regel;
      - uitgelogd geeft de loginprompt, en het Network-paneel toont geen requests naar `profiles`, `favorites` of `alert_rules`.
11. **Eindcontrole.**
    - `cd web && npm ci && npm run check && npm test && npm run build && npm run verify:build`;
    - `bash scripts/check-no-client-openmeteo.sh` vanuit de root;
    - `grep -rni "telegram" web/src` geeft niets;
    - de grep van WP-13 AC-6 (`grep -rEn "googletagmanager|google-analytics|plausible|fonts.googleapis|cdn\." web/src web/static`) geeft niets;
    - `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run shakka contracts export --check`;
    - `git status`: geen `.env`, `web/build` of `node_modules` gestaged; `git diff --stat develop` toont alleen bestanden uit "Bestanden".

**Nodig van Lars:**
- AC-7 (zie Testplan).
- Een reactie op de voorstellen A9 (niveaulabels) en A10 (bronlabels).

## Verwerking review
Review ronde 1 (`docs/wp/WP-16/review.md`, CHANGES_REQUIRED). Beslissingen van de orchestrator zijn gevolgd.

**B-1 (blokkerend): `ruleHints` kan gooien bij een omgekeerd tijdvenster.** Overgenomen.
- Nieuwe functie `parseRuleFields` in `forms.ts` (Interfaces): stap 1 van `parseAlertRuleForm`, gedeeld met `ruleHints`. Hij past ook de controles tussen velden toe en zet dan het latere veld in de soepele waarde op `null`: `earliest >= latest` → `latest_local = null` (`timeOrder`), `min >= max` → `max_kn = null` (`minNotBelowMax`), `latest_local '00:00'` → `null`. Zo haalt de soepele waarde altijd stap 2 van `effectiveRule`.
- `ruleHints` roept `effectiveRule` één keer aan, in een `try` die elke fout vangt; bij een fout wordt de kn-hint `standaard: botst met je andere windgrenzen`. De tweede aanroep (fallback) uit revisie 1 is vervallen in plaats van in een eigen `try` gezet: alleen `min_kn` en `max_kn` hadden `eff` nodig, en de overige hints zijn bij lege invoer altijd de systeemwaarde, dus die komen nu direct uit `defaults`. Daarmee kan `ruleHints` niet meer gooien, en dat was het doel van de beslissing.
- Tests: `forms.test.ts` (Vanaf `18:00`/Tot `17:00`, min `20`/max `15`, Tot `00:00`, ongeldig profiel en conflict: `ruleHints` gooit niet; de waarden van `parseRuleFields`) en `alert-rule-form.test.ts` (rij met Tot `17:00`, daarna Vanaf `19:00` kiezen: geen crash, hint blijft, Opslaan toont `timeOrder`, 0 writes, geen `error`-event). Edge cases E24 en E34, risico R8.

**N-1: `enabled: null`.** Overgenomen als exacte spiegel: `effectiveRule` accepteert `null` en valt terug op de default met bron `system` (A3, algoritme stap 2 en 3). Nieuw geval 19 `rule_enabled_null_falls_back` in `rule_resolution_cases.json`; de test "`enabled null` → invalid" in `rules.test.ts` is vervangen door "`enabled null` → `true`, bron `system`", en `'yes'` geeft nu `invalid`. E35.

**N-2: succespad van de Python-test.** Overgenomen. De testopzet staat nu bijna volledig uitgeschreven: imports (`REPO_ROOT` uit `shakka.config`, `make_spot` uit `evaluation_fixtures`), `_parse` met `ProfileDefaults.from_row`/`AlertRuleOverride.from_row`, `rule = resolve_rule(spot, profile, override)`, het `actual`-dict, `_fmt` en `_expected_sources` met implementatie op de geparste modellen (24:00 bij geval 12 en `enabled: null` bij geval 19 tellen als `system`).

**N-3: pariteit bij tijdfracties.** Overgenomen door beide kanten op dezelfde manier te normaliseren (niet door de regex te beperken, want dan zou TS strenger zijn dan Python). A18 legt de vorm vast (`HH:MM`, `HH:MM:SS` of `HH:MM:SS.ffffff`, gelijk aan `time.isoformat()`); `normalizeLocalTime` is daarop aangepast, het stringvergelijk voor `earliest < latest` blijft kloppen. Nieuw geval 20 `times_with_seconds_and_fraction` en extra unit-tests. Het formulier accepteert nu ook die genormaliseerde vormen, zodat een via de CLI opgeslagen `17:00:30` ongewijzigd terug kan (E33). Gecontroleerd tegen de Pydantic- en speedate-documentatie (Externe afhankelijkheden).

**N-4: Tot `00:00` in de database.** Overgenomen. `storedRuleStatus` geeft bij `latest_local === '00:00'` `ok: false` met `"Tot 00:00" telt geen enkel uur. Voor deze spot komen geen alerts tot je dit aanpast.`, dus geen samenvatting `00:00–00:00` meer. E19 en `forms.test.ts` aangepast.

**N-5: tekst bij een ongeldig profiel.** Overgenomen. Nieuwe meldingen `profileInvalid` (`Je profiel heeft ongeldige windgrenzen; pas die aan bij Profiel.`) en `ruleInvalid` (voor elke andere, niet te verwachten fout); `parseAlertRuleForm` stap 3 kiest op basis van `RuleError.field`. E36 en een test in `forms.test.ts`. De tekst van `storedRuleStatus` voor een opgeslagen ongeldige regel blijft ongewijzigd.

**N-6: type- en uitvoeringsdetails.** Overgenomen.
- `AlertDefaultItem<T, A>` met `allowed: A[] | null`, plus `AlertDefaultChoiceItem` voor `dir_classes` (`DirClass[]`) en `weekdays` (`number[]`), zodat de component zonder cast bindt.
- "Opnieuw proberen" roept `retry()` aan, met een guard op `userId !== null`; `submit` op `/profiel` heeft dezelfde guard. Op `/alerts` staat de `ok`-tak in `{#if page.kind === 'ok' && userId !== null}`.
- De beginwaarde van `form`, `errors`, `status` en `saving` op `/profiel` staat nu in Interfaces.
- `AlertRuleForm` gebruikt `$state(untrack(() => ruleToForm(row, …)))` met commentaar, en `ctx` is `$derived`.

**N-7: `bind:group` in Externe afhankelijkheden.** Genoteerd, en de bewering in de tabel is gecorrigeerd: alleen `<select bind:value>` noemt het behoud van niet-stringwaarden expliciet; R5 verwijst ernaar. Geen ontwerpwijziging.

**N-8: `<details>` in `alerts-page.test.ts`.** Overgenomen als testbare variant: `<details>` blijft standaard dicht (UX ongewijzigd). De test zet `details.open = true` en wacht op `tick()` vóór elke interactie, en controleert in een aparte test dat hij bij het laden dicht is.

**N-9: voorstellen A9/A10 en A13/A14.** Genoteerd; ze wachten op een reactie van Lars en zijn niet gewijzigd.
