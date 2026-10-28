# Blueprint WP-30: Stille uren voor meldingen
Status: DRAFT
Revisie: 1

## Doel
Een gebruiker stelt één dagelijkse periode in (bijv. 22:00–07:00, Nederlandse tijd) waarin geen alerts binnenkomen. Wat in die periode verandert, komt na afloop als actuele stand binnen (één melding per gewijzigd window), niet als een reeks oude meldingen. Scope, contracten en AC's: `docs/WORK_PACKAGES_V2.md`, sectie WP-30. Dit is een scopewijziging; Lars gaf akkoord op 28 oktober 2026.

## Aannames
- **A1 (Lars bevestigen).** Het gedrag is zoals in de WP: tijdens stille uren wordt niets afgeleverd en niets opgeslagen. De eerste run na afloop berekent de diff tegen de laatst gemelde stand. Een window dat in de stille uren ontstaat en weer verdwijnt, levert dus nooit een melding op. De builder legt het akkoord vast in `docs/PROJECT_PLAN.md` (sectie 4 "Alerts" en sectie 9).
- **A2.** Stille uren gelden in `LOCAL_TZ` (Europe/Amsterdam) voor iedereen. Er komt geen tijdzone per gebruiker. Ze gelden elke dag.
- **A3.** De poort werkt op favorieten met uitkomst `planned`, na `plan_favorite`. `skipped`, `ineligible` en `disabled` tellen zoals nu, ook tijdens stille uren. Een kapotte regel valt dus ook 's nachts op. `quiet` is het aantal verschillende gebruikers met minstens één `planned` favoriet die door stille uren is tegengehouden.
- **A4.** De poort geldt in elke modus van `run_alerts`: met en zonder notifier, en ook bij `dry_run`. `dry_run` laat dan zien wat een echte run zou doen. Zonder notifier slaan we tijdens stille uren ook geen state op, zodat het één regel is.
- **A5.** Een ongeldige waarde van de stille uren is alleen mogelijk buiten de CHECK om (half gezet, gelijk, of onleesbaar). Die geeft voor die favoriet `skipped` met de vaste fout `ValueError: invalid quiet hours`. Gevolg: exitcode 1 in de CLI, stap `partial`, geen aflevering en geen opslag.
- **A6.** De UI biedt hele uren 00:00 t/m 23:00. Een opgeslagen waarde die geen heel uur is (alleen mogelijk via SQL) verschijnt als extra optie en blijft bij opslaan ongewijzigd.
- **A7 (Lars bevestigen).** `shakka admin alerts preview` negeert stille uren: het toont wat er buiten de stille uren gemeld zou worden. Een admin-CLI om stille uren in te stellen komt er niet; dat doe je in de app.
- **A8.** De cron draait op minuut 17. Bij 22:00–07:00 komt de melding na afloop dus rond 07:17, of later als de run vertraagd is. De tekst op `/alerts` zegt "binnen een uur".
- **A9.** Migratietijdstempel `20261028120000`, de eerstvolgende vrije na `20261028090000_organizer_moderation.sql`. Neemt een parallelle WP een latere tijdstempel en merget die eerder, dan is na de merge `supabase db push --include-all` nodig (afspraak 5).
- **Nodig van Lars:** A1 en A7 bevestigen. Na de merge `supabase db push`.

## Ontwerp
**Database.** Er komen twee nullable `time`-kolommen op `profiles`, een CHECK met een vaste naam en een extra kolomgrant voor `authenticated`. Lezen is al gedekt door de tabelbrede `grant select` en de policy `profiles_select_own`; wijzigen door `profiles_update_own`. Er komen geen functies bij, dus de functielijsten in `07_sessions.test.sql` blijven ongewijzigd (afspraak 2).

**Domein.** `shakka.domain.quiet` is puur. Het rekent `now` om naar de lokale wandkloktijd en vergelijkt die met de halfopen periode `[start, end)`. Bij `start > end` loopt de periode over middernacht. Rond de zomer- en wintertijdwissel hoeft er niets speciaals te gebeuren. Een lokale tijd die niet bestaat (29 maart, 02:xx) valt nooit in de periode. Een tijd die twee keer voorkomt (25 oktober, 02:xx) valt er beide keren in. De nacht 22:00–07:00 duurt daardoor 8 of 10 echte uren.

**Job.** `run_alerts` krijgt één poort, direct na de afhandeling van `skipped`/`ineligible`/`disabled` en vóór de tak `dry_run`/`assign_new_ids`/`deliver_plan`/`store_plan`. Valt `now` in de stille uren van de gebruiker, dan gaat de favoriet niet naar aflevering, `store_plan` of `messages`. Zo hergebruiken we de alles-of-niets-regel van WP-17: wat niet is opgeslagen, wordt de volgende run opnieuw berekend. Dat is ook waarom er na afloop geen inhaalreeks komt. De diff vergelijkt de *actuele* windows met de laatst *gemelde* stand. Tussenliggende toestanden bestaan nergens. Er is geen extra databasequery nodig, want `profile_row` is al geladen. Wel krijgt `PROFILE_COLUMNS` de twee kolommen. `quiet` wordt een teller, geen warning, en maakt de stap niet `partial`.

**Web.** Op `/alerts` komt een nieuwe component `QuietHoursSettings` met twee selects (Van, Tot), de knoppen "Opslaan" en "Uit", en een samenvattingsregel. Hij staat als eerste in de geladen staat, direct onder `PushSettings`, en is ook zichtbaar zonder favorieten. De validatie zit in `parseQuietHours` en spiegelt de CHECK. Opslaan loopt via een nieuwe functie `updateQuietHours` die precies de twee kolommen schrijft. `updateProfile` en het profielformulier blijven ongemoeid: de stille uren horen niet bij `PROFILE_EDITABLE_COLUMNS`, maar bij een eigen `QUIET_HOURS_COLUMNS`. Zo verandert `ProfileUpdate` niet en blijft `/profiel` buiten deze WP.

**Waarom geen nieuwe `PlanOutcome` `"quiet"`.** Dan zou `plan_favorite` een klok-afhankelijke beslissing per gebruiker nemen, en zou de preview stille uren ineens gaan tonen. De poort hoort bij de aflevering, niet bij de planning.

## Bestanden
| Bestand | Actie | Inhoud |
|---|---|---|
| `supabase/migrations/20261028120000_quiet_hours.sql` | aanmaken | Kolommen, CHECK `profiles_quiet_hours_valid`, grant (letterlijk hieronder). |
| `supabase/tests/12_quiet_hours.test.sql` | aanmaken | CHECK, kolomrechten, A tegen B (zie Testplan AC-1). |
| `supabase/tests/01_schema.test.sql` | wijzigen | `columns_are` voor profiles plus twee kolommen; twee rijen in de `set_eq` van typen. `plan(70)` blijft. |
| `ingest/src/shakka/domain/quiet.py` | aanmaken | `QuietHours`, `QUIET_COLUMNS`, `quiet_hours_from_row`, `in_quiet_hours`. |
| `ingest/src/shakka/jobs/alerts.py` | wijzigen | `PROFILE_COLUMNS`, `AlertJobResult.quiet`, `quiet_now`, poort in `run_alerts`, logregel en CLI-regel met `quiet=`. |
| `ingest/src/shakka/pipeline.py` | wijzigen | `alert_counts` krijgt `"quiet"`. Geen warning, geen invloed op `partial`. |
| `ingest/tests/test_quiet.py` | aanmaken | AC-2. |
| `ingest/tests/test_job_alerts_quiet.py` | aanmaken | AC-3, AC-4 (job). |
| `ingest/tests/test_pipeline.py` | wijzigen | `test_alert_counts_shape` met `quiet`; nieuwe `test_hourly_quiet_is_ok_not_partial`. |
| `ingest/tests/test_cli_jobs.py` | wijzigen | Golden regel krijgt ` quiet=0` aan het eind. |
| `web/src/lib/types.ts` | wijzigen | `Profile` en `PROFILE_COLUMNS` plus twee kolommen; `QUIET_HOURS_COLUMNS`, `QuietHoursUpdate`. |
| `web/src/lib/user-data.ts` | wijzigen | `updateQuietHours`. |
| `web/src/lib/forms.ts` | wijzigen | `QUIET_HOUR_OPTIONS`, `quietHourOptions`, `QuietHoursForm`, `quietToForm`, `parseQuietHours`, `quietHoursSummary`, twee `FORM_MESSAGES`. |
| `web/src/lib/components/QuietHoursSettings.svelte` | aanmaken | Sectie "Stille uren" (DOM-contract hieronder). |
| `web/src/routes/alerts/+page.svelte` | wijzigen | `QuietHoursSettings` als eerste element in de tak `page.kind === 'ok'`. |
| `web/src/routes/privacy/+page.svelte` | wijzigen | Profielregel: "…, standaard windgrenzen en stille uren." |
| `docs/PRIVACY.md` | wijzigen | Rij "Profiel": `quiet_from`, `quiet_until` toevoegen aan de kolomlijst. |
| `web/test/schema-columns.test.ts` | wijzigen | Uitzondering voor de WP-30-migratie in de alter-guard; kolom- en grantvergelijking (Interfaces). |
| `web/test/user-tables.test.ts` | wijzigen | Drie keer `.update(`, waarvan twee op `profiles`. |
| `web/test/user-data.test.ts`, `web/test/forms.test.ts` | wijzigen | Tests voor `updateQuietHours` en de forms-functies. |
| `web/test/quiet-hours-settings.test.ts` | aanmaken | Componenttests AC-5. |
| `web/test/alerts-page.test.ts`, `web/test/privacy-page.test.ts` | wijzigen | Sectie aanwezig; privacytekst (AC-6). |
| `web/test/fixtures/user-data.ts` en andere `Profile`-literals in tests | wijzigen | `quiet_from: null, quiet_until: null` (typecheck). |
| `docs/PROJECT_PLAN.md` | wijzigen | Akkoord vastleggen (sectie 4 "Alerts" en sectie 9). |
| `docs/RUNBOOK.md` | wijzigen | De regel "Tellers in `ingest_runs`" (stap `alerts`) noemt `quiet`. |

## Interfaces en contracten

### Migratie `20261028120000_quiet_hours.sql` (letterlijk)
```sql
-- WP-30: quiet hours per user, local time (Europe/Amsterdam), every day. Both null = off.
-- start > end runs past midnight; the alert job holds back delivery and state inside [from, until).
alter table public.profiles add column quiet_from time null;
alter table public.profiles add column quiet_until time null;
alter table public.profiles add constraint profiles_quiet_hours_valid check (
  (quiet_from is null) = (quiet_until is null)
  and (quiet_from is null or quiet_from <> quiet_until)
);
grant update (quiet_from, quiet_until) on table public.profiles to authenticated;
```

### `shakka.domain.quiet`
```python
QUIET_COLUMNS: Final = ("quiet_from", "quiet_until")

@dataclass(frozen=True, slots=True)
class QuietHours:
    start: time  # naive local wall-clock time
    end: time
    # __post_init__: ValueError if a value is not a datetime.time, has tzinfo, or start == end

def quiet_hours_from_row(row: Mapping[str, Any]) -> QuietHours | None:
    """Both keys missing or None -> None. Exactly one None/missing -> ValueError.
    A value is a naive datetime.time or an ISO string 'HH:MM' / 'HH:MM:SS' (time.fromisoformat);
    any other type, an unparsable string or a time with an offset -> ValueError."""

def in_quiet_hours(now: datetime, quiet: QuietHours | None) -> bool:
    """ValueError if now is naive (checked first). None -> False.
    t = now.astimezone(LOCAL_TZ).time()  (naive)
    start < end: start <= t < end;  start > end: t >= start or t < end."""
```
Imports: alleen `collections.abc`, `dataclasses`, `datetime`, `typing` en `shakka.domain.defaults.LOCAL_TZ` (puurheidscheck).

### `shakka.jobs.alerts`
```python
PROFILE_COLUMNS: Final = (
    "user_id,weight_kg,level,quiver_m2,default_min_kn,default_max_kn,quiet_from,quiet_until"
)

@dataclass(frozen=True, slots=True)
class AlertJobResult:
    ...  # existing fields unchanged, in order
    push_non_retryable: int = 0
    quiet: int = 0  # users with >= 1 planned favorite held back by quiet hours (WP-30)

def quiet_now(fav: FavoriteRows, *, now: datetime) -> bool:
    """True if now falls in the quiet hours of fav's user. ValueError for an invalid value."""
    return in_quiet_hours(now, quiet_hours_from_row(fav.profile_row or {}))
```
Poort in `run_alerts`, direct na `assert plan.diff is not None`:
```python
try:
    held = quiet_now(fav, now=now)
except ValueError:
    counts["skipped"] += 1
    errors.append(f"spot {fav.spot_id}: ValueError: invalid quiet hours")
    logger.warning("alerts: skipped a favorite (ValueError)")
    continue
if held:
    quiet_users.add(fav.user_id)  # set[str], local
    continue
```
- `AlertJobResult(..., quiet=len(quiet_users))`.
- Aan het eind van de `logger.info`-regel komt ` quiet=%d`.
- De CLI-samenvatting `alerts: users=… deleted=N` krijgt ` quiet=N` aan het eind.
- `quiet` telt niet mee in `failed` (CLI) en niet in `partial` (pipeline).

### `shakka.pipeline.alert_counts`
Krijgt de sleutel `"quiet": result.quiet`, direct na `"deferred"`. Verder ongewijzigd.

### Web: `types.ts`
```ts
export interface Profile {
	// ...existing fields...
	quiet_from: string | null; // 'HH:MM:SS', Dutch local time
	quiet_until: string | null;
}
export const PROFILE_COLUMNS = [
	'user_id', 'weight_kg', 'level', 'quiver_m2', 'default_min_kn', 'default_max_kn',
	'created_at', 'updated_at', 'quiet_from', 'quiet_until'
] as const;
/** Columns `authenticated` may update for quiet hours (column grant, WP-30). */
export const QUIET_HOURS_COLUMNS = ['quiet_from', 'quiet_until'] as const;
export type QuietHoursUpdate = Pick<Profile, (typeof QUIET_HOURS_COLUMNS)[number]>;
```
`PROFILE_EDITABLE_COLUMNS` en `ProfileUpdate` blijven ongewijzigd.

### Web: `user-data.ts`
```ts
/** Writes exactly quiet_from and quiet_until (column grant, WP-30). */
export async function updateQuietHours(userId: string, values: QuietHoursUpdate): Promise<Profile>
```
- Payload: `{ quiet_from: values.quiet_from, quiet_until: values.quiet_until }`.
- Keten: `.from('profiles').update(payload).eq('user_id', userId).select(PROFILE_COLUMNS.join(',')).single()`.
- Bij een fout: `throw new DataError('updateQuietHours', error.code ?? null)`.

### Web: `forms.ts`
```ts
export const QUIET_HOUR_OPTIONS: readonly string[]; // '00:00', '01:00', ..., '23:00' (24)
export function quietHourOptions(current: string): string[]; // QUIET_HOUR_OPTIONS + current if absent, sorted
export interface QuietHoursForm { from: string; until: string } // 'HH:MM' or ''
export function quietToForm(p: Pick<Profile, 'quiet_from' | 'quiet_until'> | null): QuietHoursForm;
// per value: /^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$/ -> first 5 chars, otherwise ''
export function parseQuietHours(
	from: string,
	until: string
): { quiet_from: string | null; quiet_until: string | null } | { error: string };
export function quietHoursSummary(p: Pick<Profile, 'quiet_from' | 'quiet_until'> | null): string;
```
`parseQuietHours` (eerst trim):
1. beide `''` geeft `{ quiet_from: null, quiet_until: null }`;
2. precies één `''` geeft `{ error: FORM_MESSAGES.quietIncomplete }`;
3. één van beide past niet op `/^([01]\d|2[0-3]):[0-5]\d$/` geeft `{ error: FORM_MESSAGES.time }`;
4. gelijk geeft `{ error: FORM_MESSAGES.quietEqual }`;
5. anders `{ quiet_from: \`${from}:00\`, quiet_until: \`${until}:00\` }`.

Nieuwe `FORM_MESSAGES`:
- `quietIncomplete: 'Kies een begin- én een eindtijd, of zet stille uren uit.'`
- `quietEqual: 'Begin en einde van de stille uren mogen niet gelijk zijn.'`

`quietHoursSummary`:

| Situatie | Tekst |
|---|---|
| `null` of beide `null` | `'Stille uren staan uit.'` |
| van < tot | `'Elke dag van 13:00 tot 14:00 geen alerts.'` |
| van > tot | `'Elke dag van 22:00 tot 07:00 (de volgende dag) geen alerts.'` |
| half gezet of onleesbaar | `'De opgeslagen stille uren zijn ongeldig. Stel ze opnieuw in.'` |

### Web: `QuietHoursSettings.svelte` (DOM-contract)
Props: `{ userId: string; profile: Profile | null; onsaved: (profile: Profile) => void }`. De begintoestand komt uit `untrack(() => quietToForm(profile))`, zoals in `AlertRuleForm`.
- Opbouw: `<section class="quiet-hours" aria-labelledby="quiet-hours-title">` met `<h2 id="quiet-hours-title">Stille uren</h2>`.
- Uitleg in `<p class="muted">`: "In deze periode krijg je geen alerts, elke dag, in Nederlandse tijd. Verandert er intussen iets, dan krijg je na afloop binnen een uur alleen de actuele stand, geen reeks oude meldingen."
- Samenvatting: `<p class="quiet-summary">{quietHoursSummary(profile)}</p>`.
- Is `profile === null`: alleen `<p>Stille uren kun je instellen zodra je profiel is aangemaakt.</p>`, geen formulier.
- Formulier:
  - `<select id="quiet-from">` met label "Van" en `<select id="quiet-until">` met label "Tot";
  - elke select begint met `<option value="">–</option>`, gevolgd door `quietHourOptions(huidige waarde)`;
  - knoppen `Opslaan` (submit) en `Uit` (`type="button"`), allebei `disabled` tijdens het opslaan.
- Opslaan:
  - eerst `parseQuietHours`. Bij een fout verschijnt `<p role="alert" class="error">{fout}</p>` en volgt er geen aanroep;
  - anders `updateQuietHours(userId, waarde)`. Lukt dat, dan `form = quietToForm(saved)`, `onsaved(saved)` en `<p role="status">Opgeslagen.</p>`.
- Uit: `updateQuietHours(userId, { quiet_from: null, quiet_until: null })`. Lukt dat, dan zijn beide selects `''`, volgt `onsaved(saved)` en verschijnt `<p role="status">Stille uren staan uit.</p>`.
- Fout bij schrijven: `<p role="alert" class="error">Opslaan is niet gelukt. Probeer het opnieuw.</p>`. Het formulier houdt zijn waarden en `onsaved` wordt niet aangeroepen.

### Web: `/alerts`
Eerste element in de tak `{:else if page.kind === 'ok' && userId !== null}`:
`<QuietHoursSettings {userId} profile={page.profile} onsaved={(p) => { if (page.kind === 'ok') page.profile = p; }} />`

### `schema-columns.test.ts`
- Nieuwe constante `PROFILE_ADD_MIGRATIONS = ['20261028120000_quiet_hours.sql']`. WP-24 voegt daar zijn eigen migratie aan toe.
- De alter-guard slaat deze bestanden over.
- `PROFILE_COLUMNS` moet gelijk zijn aan `columns('profiles')` zonder de legacy-kolom, gevolgd door de kolommen uit `/alter table public\.profiles add column (\w+)/g` in die migraties, in volgorde.
- Nieuwe toets: de grant in de WP-30-migratie is precies `QUIET_HOURS_COLUMNS`.
- De bestaande grant-toets op `m1Security` tegen `PROFILE_EDITABLE_COLUMNS` blijft ongewijzigd.

## Edge cases
- E1. Beide kolommen `null`, of geen profielrij: nooit stil. De job gedraagt zich exact als vóór WP-30.
- E2. `22:00–07:00`: stil om 22:00 en om 06:59. Niet stil om 07:00 en om 21:59 (halfopen, over middernacht).
- E3. 29-03-2026: `02:00–03:00` is die dag nooit stil (de lokale tijd bestaat niet). `22:00–07:00` duurt 8 echte uren.
- E4. 25-10-2026: `02:00–03:00` is 2 echte uren stil (00:00–02:00 UTC). `22:00–07:00` duurt 10 echte uren.
- E5. Half gezet, gelijk of onleesbaar, buiten de CHECK om: `skipped` met de vaste fout zonder user-id (A5). Geen aflevering, geen opslag.
- E6. Een window ontstaat tijdens de stille uren en verdwijnt weer: na afloop 0 events en geen `alert_state`-rij.
- E7. Een gemeld window wordt tijdens de stille uren geannuleerd en komt identiek terug: na afloop 0 events. Blijft het weg, dan na afloop één `cancelled`.
- E8. Een gemeld window verbetert tijdens de stille uren: na afloop precies één `improved` tegen de laatst gemelde stand.
- E9. Een gemeld window eindigt tijdens de stille uren: `diff_windows` handelt dat af zoals nu. Geen inhaalmelding.
- E10. Meerdere runs tijdens de stille uren: geen enkele schrijfactie op `alert_state` voor die gebruiker. `delete_old_alert_state` draait gewoon door.
- E11. `dry_run` of geen notifier: de poort geldt ook (A4). Geen `messages` en geen opslag voor de stille gebruiker.
- E12. Twee gebruikers, één stil: de ander krijgt zijn melding. `targets` worden zoals nu in één select geladen.
- E13. Stille uren worden gewijzigd tijdens de stille uren: de volgende run gebruikt de nieuwe waarde.
- E14. `shakka admin alerts preview` negeert stille uren (A7). Het operatorrapport van WP-22 valt er ook niet onder.
- E15. Web: één select leeg geeft `quietIncomplete`; gelijke tijden geven `quietEqual`. In beide gevallen geen aanroep.
- E16. Web: beide selects leeg plus "Opslaan" schrijft `null`/`null`, hetzelfde als "Uit".
- E17. Web: een opgeslagen `22:30:00` verschijnt als optie `22:30`. Ongewijzigd opslaan schrijft `22:30:00`.
- E18. Web: zonder profielrij geen formulier. Lukt opslaan niet, dan een generieke fout en blijven de waarden staan.

## Testplan
Fixtures: `job_fixtures` (`seed_favorite`, `seed_profile`, `seed_forecasts`, `WINDS`, `USER_A/B`) en `make_db` uit `test_job_alerts.py`. Uit `test_job_alerts_push.py`: `SPLIT_WINDS`. Uit `push_fixtures`: `FakeNotifier` en `seed_subs`.
- Een profielrij in de jobtests moet `default_min_kn` en `default_max_kn` bevatten (mag `None`), anders geeft `ProfileDefaults.from_row` `skipped`.
- Run-tijden:
  - `T0 = 2026-07-14 19:17 UTC` (21:17 lokaal);
  - `T1 = 21:17 UTC` (23:17 lokaal);
  - `T1b = 2026-07-14 22:17 UTC` (00:17 lokaal);
  - `T2 = 2026-07-15 05:17 UTC` (07:17 lokaal).
- Vóór elke run: `seed_forecasts(db, winds=…, fetched_at=t - 7 min)`.

**AC-1 (pgTAP).** In `12_quiet_hours.test.sql`; `plan(N)` is het aantal onderstaande asserts.
- Fixture: twee auth-users zoals in `04_rls_users`.
- `ok(...)`: CHECK `profiles_quiet_hours_valid` bestaat (`pg_constraint`, `contype = 'c'`).
- `column_privs_are`:
  - `authenticated` op `quiet_from` en op `quiet_until` heeft `SELECT, UPDATE`;
  - `anon` op `quiet_from` heeft `{}`.
- `throws_ok 23514`: alleen `quiet_from` gezet, alleen `quiet_until` gezet, en `'22:00' = '22:00'`.
- `lives_ok`: `22:00/07:00`, daarna terug naar `null/null`.
- Als A:
  - `lives_ok`, eigen update naar `22:00/07:00`, met `is` op de waarde;
  - `lives_ok` op de update van B (0 rijen).
- Na `reset role`: `is` op `quiet_from` van B is `null`.
- `01_schema.test.sql` bevat de twee kolommen in `columns_are` en in de typen-`set_eq`: `('profiles','quiet_from','time without time zone',true)`, idem `quiet_until`.

**AC-2 (`test_quiet.py`).** Rekenvoorbeeld voor de DST-gevallen: de stille kwartieren tussen 12:00 UTC en 12:00 UTC de volgende dag.

| Periode | Nacht | Stille kwartieren |
|---|---|---|
| 22:00–07:00 | 28→29 maart | 32 (21:00–05:00 UTC) |
| 22:00–07:00 | 24→25 oktober | 40 (20:00–06:00 UTC) |
| 02:00–03:00 | 29 maart | 0 |
| 02:00–03:00 | 25 oktober | 8 |

- `test_overnight_boundaries`: `22:00–07:00` op 15-07-2026. Stil om 22:00, 23:30 en 06:59 lokaal; niet om 07:00 en 21:59.
- `test_same_day_boundaries`: `13:00–14:00`. Stil om 13:00 en 13:59; niet om 14:00 en 12:59.
- `test_dst_spring_2026_03_29`: 04:59 UTC stil, 05:00 UTC niet. Op 28-03: 20:59 UTC niet, 21:00 UTC wel. 32 kwartieren.
- `test_dst_autumn_2026_10_25`: 05:59 UTC stil, 06:00 UTC niet. Op 24-10: 19:59 UTC niet, 20:00 UTC wel. 40 kwartieren.
- `test_dst_gap_and_fold`: `02:00–03:00` geeft 0 kwartieren op 29-03 en 8 op 25-10.
- `test_none_is_never_quiet`: `in_quiet_hours(t, None) is False`.
- `test_naive_now_raises`: naïeve `now` geeft `ValueError`, ook met `quiet=None`.
- `test_quiet_hours_validation`: `start == end`, of een `time` met `tzinfo`, geeft `ValueError`.
- `test_from_row`:
  - `"22:00:00"`, `"22:00"` en `time(22)` worden gelezen;
  - beide `None` of beide sleutels afwezig geeft `None`;
  - half gezet, `"abc"`, `"22:00+01:00"` of gelijke tijden geven `ValueError`.
- `tests/test_domain_purity.py` blijft groen.

**AC-3 (`test_job_alerts_quiet.py`).**
- `test_quiet_user_gets_nothing_then_one_new`: A met `22:00:00`/`07:00:00` en B zonder profiel, allebei met 1 abonnement.
  - Op T1: B krijgt 1 aflevering, A geen. `quiet == 1`. A heeft geen `alert_state`-rij.
  - Op T2: precies 1 `new`-aflevering voor A en 0 voor B.
- `test_quiet_keeps_state_and_reports_improved_once`: A stil.
  - Op T0 met `SPLIT_WINDS`: 2× `new`, opgeslagen.
  - Op T1 met `WINDS`: 0 afleveringen. `alert_rows(db)` is gelijk aan vóór de run en er is geen update of insert op `alert_state`.
  - Op T2: `["improved"]`.
- `test_quiet_applies_in_dry_run_and_without_notifier`: op T1 geeft `dry_run=True` lege `messages` en `quiet == 1`. Zonder notifier geen `alert_state`-rijen.
- `test_invalid_quiet_hours_skips_favorite`:
  - `quiet_from="22:00:00"`, `quiet_until=None`, geeft `skipped == 1` en `errors == ("spot test-strand: ValueError: invalid quiet hours",)`;
  - geen aflevering;
  - `USER_A` komt niet voor in `errors`.
- `test_quiet_log_has_counts_only`: `caplog` bevat `quiet=1` en niet `USER_A`.

**AC-4.**
- `test_window_born_and_gone_in_quiet_gives_nothing`:
  - T1 met `WINDS` (stil);
  - T1b met alle winden op 6.0;
  - T2 met alle winden op 6.0: 0 events, geen `alert_state`-rij.
- `test_cancel_and_return_in_quiet_gives_nothing`:
  - T0 met `WINDS`: `new`;
  - T1 met alles op 6.0 (stil);
  - T1b met `WINDS` (stil);
  - T2 met `WINDS`: 0 events.
- `test_hourly_quiet_is_ok_not_partial` (in `test_pipeline.py`, opgezet zoals `test_hourly_deferred_warning`):
  - stille uren rond de `now` van `run_real`;
  - stap `alerts` heeft `status == "ok"`, geen warning met `alerts:`, en `counts["quiet"] == 1`.
- `test_alert_counts_shape` bevat `quiet`.

**AC-5 (web).**
- `forms.test.ts`:
  - `parseQuietHours` volgens regels 1–5 (beide volgordes van "één leeg"; `'24:00'`, `'7:00'` en `'22:00:00'` geven `FORM_MESSAGES.time`);
  - `quietToForm`, `quietHourOptions` (24 opties, extra `22:30` wordt gesorteerd ingevoegd) en `quietHoursSummary` (vier gevallen).
- `user-data.test.ts`:
  - `updateQuietHours writes exactly quiet_from and quiet_until`: de payload heeft precies twee sleutels, `eq('user_id')` en select `PROFILE_COLUMNS`;
  - `updateQuietHours reports PGRST116`.
- `quiet-hours-settings.test.ts` (mock van `#lib/user-data.js`):
  - `shows the stored hours`: `22:00:00`/`07:00:00` geeft selects `22:00`/`07:00` en de samenvatting;
  - `"Uit" writes null for both columns`: één aanroep met `(USER_ID, { quiet_from: null, quiet_until: null })`;
  - `equal times show a Dutch error without writing`: `quietEqual` met `role="alert"`, 0 aanroepen;
  - `one empty time shows a Dutch error without writing`;
  - `a valid choice writes only the two columns`: het argument is exact `{ quiet_from: '22:00:00', quiet_until: '07:00:00' }` en `onsaved` wordt aangeroepen;
  - `a failed save shows an error and keeps the values`;
  - `without a profile there is no form`.
- `alerts-page.test.ts`: in de ok-staat is er een heading "Stille uren", ook zonder favorieten.
- `a11y-alerts.test.ts` blijft groen.
- `schema-columns.test.ts` en `user-tables.test.ts` volgens Interfaces.

**AC-6.** `privacy-page.test.ts`:
- `names quiet hours as profile data`: `/privacy` bevat "stille uren";
- `PRIVACY.md profile row lists the quiet columns`: de rij `| Profiel |` bevat `` `quiet_from` `` en `` `quiet_until` ``.

## Externe afhankelijkheden
Geen nieuwe packages of endpoints.
- `zoneinfo`: stdlib, al in gebruik via `LOCAL_TZ`.
- Postgres `time` en kolomgrants: standaard, al in gebruik (WP-01).
- PostgREST geeft `time` terug als `'HH:MM:SS'`. Dat is hetzelfde formaat dat `earliest_local`/`latest_local` nu al gebruiken (WP-16, `normalizeLocalTime`).
- Niets opnieuw gecontroleerd. Er staat geen nieuwe bron in "Gecontroleerde externe documentatie".

## Risico's
- R1. `Profile` krijgt twee verplichte velden, dus alle `Profile`-literals in web-tests moeten mee. Dat is mechanisch: `npm run check` wijst ze aan.
- R2. Er zijn golden tests op de CLI-regel (`test_cli_jobs.py`) en de vorm van `alert_counts`. Die worden bewust bijgewerkt; elders blijven ze ongewijzigd.
- R3. Gebruikers verwachten een melding om precies 07:00. De uitleg op `/alerts` zegt "binnen een uur" (A8).
- R4. `quiet=1` staat in de openbare Actions-log. Het is een telling, net als `sent`, zonder user-id. Bij één gebruiker verraadt het alleen dat er iemand stille uren heeft.
- R5. Een migratiebotsing met een parallelle WP: zie A9. WP-24 loopt bewust niet parallel.

## Buiten scope
- Stille uren per spot of per weekdag, of een "niet storen"-knop (WP).
- Tijdzone per gebruiker (A2).
- Een admin-CLI om stille uren te zetten of te tonen; `format_profile` blijft ongewijzigd (A7).
- Stille uren in de preview (A7) en in het operatorvenster van WP-22.
- Het tijdvenster van alertregels (`earliest_local`/`latest_local`).
- Wijzigingen aan `/profiel`, `ProfileUpdate` of `updateProfile`.

## Gevolgen voor latere WP's
- **WP-24:**
  - zet `alert_channel` in `PROFILE_COLUMNS` (Python en web) ná `quiet_until`;
  - de e-mailaflevering komt ná de poort in `run_alerts`, zodat stille uren voor elk kanaal gelden. De poort zit al vóór de tak `dry_run`/aflevering;
  - voegt zijn migratie toe aan `PROFILE_ADD_MIGRATIONS` in `schema-columns.test.ts`;
  - verhoogt het aantal `.update(` in `user-tables.test.ts` als hij een eigen schrijffunctie toevoegt;
  - vult `columns_are`/`set_eq` in `01_schema.test.sql` aan.
- **Elke WP met een nieuwe profielkolom:** volgt hetzelfde patroon: een eigen `*_COLUMNS`, een eigen schrijffunctie en `PROFILE_ADD_MIGRATIONS`.

## Stappenplan voor de builder
Werk op `wp/WP-30` in `/Users/larst/Dev/Shakka/.claude/worktrees/WP-30`. Lees of print `.env` en `web/.env` nooit. Eén commit per stap, Engelse berichten. Na elke stap draaien:
- `cd ingest && uv run pytest && uv run ruff check . && uv run ruff format --check .`;
- `cd web && npm run check && npm test`;
- na stap 1 en aan het eind ook `supabase db reset && supabase test db`. Lukt dat niet (Docker), meld het aan de verifier.

0. **Uitgangspunt.**
   - `git merge-base --is-ancestor origin/develop HEAD` slaagt;
   - `grep -q usage_report ingest/src/shakka/pipeline.py` slaagt (WP-22);
   - `ls supabase/migrations/*delete_my_account*` bestaat (WP-23);
   - `grep -rq alert_channel ingest/src web/src supabase` vindt niets (WP-24 niet gemerged);
   - de volledige suite is groen.

   Zo niet: stop en meld het. Geen commit.
1. **Database en kolomcontract.** Migratie (letterlijk), `12_quiet_hours.test.sql`, `01_schema.test.sql`. Daarna `types.ts` (`Profile`, `PROFILE_COLUMNS`, `QUIET_HOURS_COLUMNS`, `QuietHoursUpdate`), `schema-columns.test.ts` en de `Profile`-literals in de tests. Commit `feat(WP-30): quiet hours columns on profiles`.
2. **Domein.** Eerst `test_quiet.py` (rood), dan `domain/quiet.py`. De puurheidscheck is groen. Commit `feat(WP-30): pure quiet hours check in local time`.
3. **Job en pipeline.**
   - Eerst `test_job_alerts_quiet.py` en de pipeline-tests (rood).
   - Dan in `alerts.py`: `PROFILE_COLUMNS`, `quiet`, `quiet_now`, de poort, de logregel en de CLI-regel.
   - Dan `alert_counts`, de golden in `test_cli_jobs.py` en de RUNBOOK-regel.

   Commit `feat(WP-30): hold back alerts during quiet hours`.
4. **Weblogica.** Eerst de tests in `forms.test.ts`, `user-data.test.ts` en `user-tables.test.ts`, dan `forms.ts` en `updateQuietHours`. Commit `feat(WP-30): quiet hours parsing and data access`.
5. **Web-UI.** Eerst `quiet-hours-settings.test.ts` en de uitbreiding van `alerts-page.test.ts`, dan `QuietHoursSettings.svelte` en `/alerts`. Daarna `a11y-alerts.test.ts` groen; zet zo nodig `updateQuietHours` in bestaande mocks. Commit `feat(WP-30): quiet hours section on /alerts`.
6. **Privacy.** `/privacy`, `docs/PRIVACY.md` en `privacy-page.test.ts`. Commit `docs(WP-30): quiet hours as profile data`.
7. **Plan.** In `docs/PROJECT_PLAN.md`:
   - sectie 4 "Alerts" krijgt deze bullet: "**Stille uren** (scopewijziging WP-30, akkoord Lars 28 oktober 2026): per gebruiker één dagelijkse periode in Nederlandse tijd zonder alerts. Wat in die periode verandert, komt na afloop als actuele stand binnen, niet als een reeks oude meldingen.";
   - in sectie 9, achter de bullet van WP-30: " Akkoord Lars: 28 oktober 2026."

   Commit `docs(WP-30): record scope approval in the plan`.
8. **Eindcontrole.** Draai alles uit de inleiding, plus `cd web && npm run build && npm run verify:build`.
