# Review WP-16, ronde 1
Oordeel: CHANGES_REQUIRED

Samenvatting: de blueprint dekt alle acceptatiecriteria (AC-1 t/m AC-8). De harde regels zijn goed geborgd:
- offshore en side-offshore zijn nergens instelbaar (alleen `allowed` uit het contract, `parseAlertDefaults` weigert niet-rijdbare klassen, `parseAlertRuleForm` en `effectiveRule` weigeren ze, en daarachter staan de DB-CHECK en Pydantic);
- er komt geen tracking en geen nieuwe dienst bij;
- `sb_secret_` komt niet in `web/`.

De schrijfregel past bij de M1-securitymigratie:
- `profiles` alleen via `update` met letterlijk de vijf kolommen uit de kolomgrant, geen insert en geen upsert (WP-01 R8);
- `favorites` en `alert_rules` met insert, upsert en delete op de eigen rijen;
- upsert met `ON CONFLICT DO UPDATE` heeft de select-, insert- en update-policy nodig, en die zijn er alle drie.

De 18 gedeelde gevallen heb ik met de hand doorgerekend tegen `resolve_rule`, `AlertRuleOverride.from_row` en `ProfileDefaults.from_row` in `ingest/src/shakka/domain/alerts.py`. Ze kloppen allemaal: afgeleide max 33/32/65, conflicten 14 en 15, invalid 16 t/m 18, 24:00 bij 12, en de bronnen. Ook de spotwaarden 16, 22 en 28 vallen binnen `SpotProfile.default_min_kn` 5–40. De Python-test draait de echte domeincode. Er is één blokkerend punt, in `ruleHints`.

## Blokkerend

B-1: `ruleHints` kan gooien bij een omgekeerd tijdvenster, en dan crasht het formulier. Waar: Interfaces, `forms.ts`, **`ruleHints`**, en `AlertRuleForm` (`hints = $derived(ruleHints(form, ctx))`).
- Waarom: de "soepele" override parseert "elk veld apart", en elke fout wordt `null`. Zijn Vanaf (`18:00`) en Tot (`17:00`) elk apart geldig, dan blijven ze allebei staan. `effectiveRule` gooit dan `RuleError('invalid', 'latest_local')` (stap 2: `earliest < latest`).
- De fallback zet alleen `min_kn` en `max_kn` op `null` en laat de tijden staan. Daardoor gooit hij opnieuw, en niets vangt die fout op. Een fout in een `$derived` die de template gebruikt, breekt de component.
- Dit is een gewone gebruikersflow: Tot staat al op 17:00 en je kiest daarna Vanaf 19:00. E24 test alleen `parseAlertRuleForm`, niet `ruleHints`.
- Hetzelfde patroon kan bij elke andere combinatie van velden die effectiveRule als invalid ziet maar die de soepele parse per veld laat staan.
- Voorstel: leg vast dat de soepele parse ook de controles tussen velden toepast. Bij `earliest >= latest` wordt `latest_local` `null`; bij `min >= max` wordt `max_kn` `null`, net als de foutsleutels in `parseAlertRuleForm`. Laat `ruleHints` daarnaast nooit gooien: zet de fallback ook in een `try`, en geef bij een tweede fout alleen de statische hints terug (of `{}`). Voeg in `forms.test.ts` een test toe (Vanaf `18:00`, Tot `17:00`: `ruleHints` gooit niet), en in `alert-rule-form.test.ts` een test waarin die selectie het formulier niet laat crashen en bij Opslaan `timeOrder` toont.

## Niet-blokkerend

N-1: `enabled: null` is geen exacte spiegel. Volgens Interfaces stap 2 weigert `effectiveRule` een `enabled` dat geen boolean is, en `rules.test.ts` toetst dat `enabled null` `invalid` geeft. Python `AlertRuleOverride.enabled` is `bool | None` en valt bij `None` terug op de default (`True`); stap 3 ("enabled: regel, anders system") gaat daar ook van uit. In de praktijk komt het niet voor, want de DB-kolom is `not null default true`. Toch spreekt het "exacte spiegel" (A3/A4) tegen. Voorstel: accepteer `null` → system, of noem de afwijking expliciet als bewuste strengheid en haal de test eruit.

N-2: Maak het succespad van de Python-test expliciet. De conflict- en invalid-takken noemen `from_row` en `resolve_rule` letterlijk. Bij "Anders vergelijkt de test `rule.enabled`…" staat niet waar `rule` vandaan komt. Schrijf erbij: `rule = resolve_rule(make_spot(...), ProfileDefaults.from_row(p) if p else None, AlertRuleOverride.from_row(o) if o else None)`, en bij `_expected_sources`: met het geparste override-model, zodat `latest_local` 24:00 als `None`/`system` telt (geval 12). Noem ook de imports (`REPO_ROOT` uit `shakka.config`, `make_spot` uit `evaluation_fixtures`).

N-3: De pariteit bij tijden met fracties is onduidelijk. `normalizeLocalTime` geeft "anders de invoer ongewijzigd" terug, terwijl `_fmt` in Python `t.isoformat()` geeft (`'17:00:30.5'` tegenover `'17:00:30.500000'`). Of "numerically 0" ook voor `'17:00:00.5'` geldt, is ook niet vastgelegd. Dit valt buiten de gevallen en is via de UI niet bereikbaar. Voorstel: beperk de regex tot `HH:MM` en `HH:MM:SS` (PostgREST geeft voor `time` zonder fractie altijd `HH:MM:SS`), of normaliseer beide kanten op dezelfde manier.

N-4: Bij E19 (Tot `00:00` in de DB) noemt `storedRuleStatus` de regel `ok`. De samenvatting toont dan bijvoorbeeld `00:00–00:00`, terwijl er nooit alerts komen (WP-07 E14). Overweeg een waarschuwing in `storedRuleStatus` voor `latest_local === '00:00'`, net als bij conflicten.

N-5: Bij een `invalid` profiel geeft `parseAlertRuleForm` stap 3 de tekst "De opgeslagen instelling is ongeldig… tot je hem opnieuw opslaat." onder `min_kn`. Die tekst past niet bij een formulier dat net is ingediend. Door de DB-constraints komt dit niet voor; een eigen korte tekst ("Je profiel heeft ongeldige windgrenzen; pas die aan bij Profiel.") is duidelijker.

N-6: Kleine type- en uitvoeringsdetails die de builder anders zelf moet invullen:
- `AlertDefaultItem.allowed` is `(string | number)[] | null`, terwijl de component er `DirClass[]` mee bindt. Geef het item een tweede typeparameter of type `allowed` per veld.
- `onclick={() => load(userId)}`: `userId` is `string | null` (non-null assertion of guard).
- De initiële waarde van `form` op `/profiel` staat niet beschreven.
- `$state(ruleToForm(row, …))` kan in recente Svelte-versies een `state_referenced_locally`-waarschuwing geven. Dat is geen fout voor `npm run check`, maar `untrack` of een opmerking voorkomt verwarring.

N-7: Externe bronnen bij `bind:group`. De Svelte-docs zeggen expliciet dat `<select bind:value>` niet-stringwaarden behoudt. Voor `bind:group` op checkboxes staat dat er niet letterlijk. R5 heeft al een fallback; pas de bewering in "Externe afhankelijkheden" daarop aan.

N-8: In `alerts-page.test.ts` staat het formulier binnen een gesloten `<details>`. Werkt `getByRole` daar in jsdom anders dan verwacht, open dan eerst de `<summary>` in de test. Dit is een tip, geen ontwerpkeuze.

N-9: Voorstellen A9/A10 (labels) en A13/A14 (gedrag bij conflicten via het profiel en ontfavorieten) zijn redelijk en goed gedocumenteerd. Ze wachten op een reactie van Lars en blokkeren niet.

## Gecontroleerde bronnen
- https://supabase.com/docs/reference/javascript/upsert (`onConflict`; rijen alleen terug met `.select()`)
- https://docs.postgrest.org/en/v12/references/errors.html (`23505`/`23503` → 409, `42501` → 401/403, `PGRST116` → 406)
- https://svelte.dev/docs/svelte/stores (`readable(initial, start)`: start bij de eerste abonnee, stop bij nul; `$store` in runes-modus)
- https://svelte.dev/docs/svelte/$derived (gelijke waarde → geen updates verderop; onderbouwt E3)
- https://svelte.dev/docs/svelte/bind (`select` behoudt waardetypes; `bind:group` noemt dat niet expliciet)
- Repo: `ingest/src/shakka/domain/alerts.py` (`resolve_rule`, `AlertRuleOverride`, `ProfileDefaults`, `FIELD_SOURCES`), `ingest/src/shakka/domain/spot.py` (`default_min_kn` 5–40), `ingest/src/shakka/contracts.py`, `ingest/src/shakka/jobs/alerts.py`, `ingest/tests/evaluation_fixtures.py`, `data/contracts/alert_defaults.json`, `data/contracts/dir_classes.json`, `supabase/migrations/20261015090000_m1_schema.sql`, `supabase/migrations/20261015090100_m1_security.sql`, `web/src/lib/{auth,data,contracts,labels,types,time}.ts`, `web/src/routes/+layout.svelte`, `web/test/{data-tables,schema-columns,layout,spot-list}.test.ts`, `web/test/helpers/fake-supabase.ts`, `web/test/fixtures/spot-data.ts`, `web/vite.config.ts`, `web/package.json`, `docs/RUNBOOK.md` §11–12, de blueprints van WP-07, WP-13 en WP-14 ("Gevolgen voor latere WP's").
