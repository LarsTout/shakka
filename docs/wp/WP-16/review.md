# Review WP-16, ronde 2
Oordeel: APPROVED

Samenvatting: revisie 2 lost B-1 volledig op. N-1 en N-3 geven aantoonbaar pariteit met Python, en de revisie introduceert geen nieuwe blokkerende punten. Ik heb de punten opnieuw gecontroleerd tegen `ingest/src/shakka/domain/alerts.py` (`AlertRuleOverride`, `ProfileDefaults`, `resolve_rule`, `FIELD_SOURCES`), `data/contracts/alert_defaults.json` en de bestaande web-modules.

**B-1 (ronde 1): opgelost.**
- `parseRuleFields` past nu ook de twee controles tussen velden toe en zet het latere veld in `value` op `null`: `min >= max` maakt `max_kn` `null` en `earliest >= latest` maakt `latest_local` `null`. Ook `latest_local '00:00'` wordt `null`.
- Elk veld dat in `value` blijft staan, ligt binnen het bereik dat stap 2 van `effectiveRule` controleert:
  - kn 5–60;
  - richtingen alleen uit `allowed` en niet leeg;
  - dagen 1–7 en niet leeg;
  - tijden via een regex die een deelverzameling is van wat `normalizeLocalTime` accepteert, geschreven als `HH:MM:00`, `HH:MM:SS` of `HH:MM:SS.ffffff`;
  - `min_go_hours` 1–24;
  - `days_ahead` 0–7;
  - `enabled` altijd een boolean.

  Stap 2 kan dus niet meer gooien. Alleen stap 4 (conflict) en stap 1 (een ongeldig profiel) kunnen dat nog, en die vangt de enige `try` in `ruleHints` op.
- De terugvalaanroep weghalen is correct en volledig. `ruleHints` geeft alleen een hint bij een leeg veld. Voor `dir_classes`, `weekdays`, `earliest_local`, `latest_local`, `min_go_hours` en `days_ahead` kent `FIELD_SOURCES` alleen `rule` en `system`. Bij een leeg veld is de effectieve waarde daar dus altijd de systeemdefault, en die hint kan zonder `effectiveRule` direct uit `defaults` komen. Alleen `min_kn` en `max_kn` hangen af van profiel en spot. Daar is de terugval-tekst "botst met je andere windgrenzen" een redelijke keuze. Het doel van de opdracht ("`ruleHints` gooit nooit") wordt hiermee strenger gehaald dan met een tweede `try`.
- De tests dekken het:
  - `forms.test.ts` test drie formulieren plus een ongeldig profiel plus een conflict, telkens met `not.toThrow`, en test daarnaast de waarden van `parseRuleFields`;
  - `alert-rule-form.test.ts` doet de echte gebruikersflow (Tot staat op 17:00, daarna Vanaf 19:00 kiezen), met een spy op `window`-`error`, `timeOrder` en 0 writes.

  R8 legt vast dat de andere `$derived`-aanroepen (`timeOptions`, `daysAheadOptions`) ook niet gooien. `storedRuleStatus` heeft een eigen `try`, en `ruleToForm` vangt de fouten van `normalizeLocalTime` af.

**N-1 (`enabled: null`): pariteit klopt.**
- Python: `enabled: bool | None = Field(default=None, strict=True)` accepteert `None`. `resolve_rule` geeft dan `True`, en `_expected_sources` ziet `None` op het niveau `RULE` en kiest dus `system`.
- TS: `null` geeft de default `true` met bron `system`. `'yes'` is aan beide kanten `invalid` (strict bool).
- Geval 19 (D, alle bronnen `system`) klopt met de hand doorgerekend.

**N-3 (tijdnormalisatie): pariteit klopt binnen de vormen die PostgREST teruggeeft.**
- `_fmt` geeft `HH:MM` als seconde en microseconde 0 zijn, en anders `isoformat()`. Dat is `HH:MM:SS` als de microseconde 0 is, en anders `HH:MM:SS.ffffff`. Dat is precies de regel in `normalizeLocalTime` (`ss`/`frac`, met `padEnd(6, '0')`).
- Speedate neemt 1 tot 6 fractiecijfers over in `time.microsecond`; zelf gecontroleerd. Dus `"17:00:30.5"` wordt `time(17,0,30,500000)` en daarna `"17:00:30.500000"`.
- Het vergelijken van strings in TS is gelijkwaardig aan het vergelijken van `time` in Python:
  - een weggelaten `:00`- of `.000000`-deel komt alleen voor als dat deel echt nul is, dus de kortere string is dan een voorvoegsel en echt kleiner;
  - alle andere delen hebben een vaste breedte en zijn met nullen aangevuld.
- Gelijke tijden (`'17:00:30'` en `'17:00:30'`) zijn aan beide kanten `invalid` (`not earliest < latest`).
- Geval 20 is met de hand doorgerekend:
  - Python: `from_row` slaagt (17:00:30 < 17:00:30.5), `_fmt` geeft `"17:00:30"` en `"17:00:30.500000"`, en de bronnen `enabled`, `earliest_local` en `latest_local` zijn `rule`;
  - TS: komt overeen.
- De afwijkingen buiten de pariteit zijn expliciet afgebakend in A18: meer dan 6 fractiecijfers (TS `invalid`, Python kapt af) en tijdzones (aan beide kanten `invalid`, via de regex respectievelijk `_naive`). Postgres geeft ze voor `time` niet terug.
- De terugweg klopt ook. `ruleToForm` geeft de genormaliseerde vorm, de formulier-regex accepteert precies die vormen, en `17:00:30.500000` wordt ongewijzigd geschreven. Postgres geeft daarna `17:00:30.5` terug, en dat normaliseert weer naar dezelfde string. De round-trip is stabiel (E33).

**Overige revisiepunten zonder bezwaar:**
- De 20 gevallen kloppen: 1–18 had ik al in ronde 1 gecontroleerd, 19 en 20 hierboven. De Python-test draait de echte `from_row`/`resolve_rule`. `make_spot(default_min_kn=None)` is geldig (`SpotProfile.default_min_kn` 5–40 of `None`). `DirClass` heeft de contractvolgorde, en `evaluation_fixtures` en `REPO_ROOT` worden al zo geïmporteerd in bestaande tests.
- `untrack(() => ruleToForm(row, …))` is onschadelijk.
- De user-id-guard (`retry`, `submit`, `{#if page.kind === 'ok' && userId !== null}`) is correct. Het vernauwen van `page`/`userId` in de template werkt, omdat `page.profile` niet in een closure staat. `onsaved` muteert alleen `e.rule` en wijst `e` niet opnieuw toe, en dat is toegestaan in runes-modus.
- De `<details>`-aanpak (`details.open = true` plus `tick()`) is robuust in jsdom. De extra test dat hij bij het laden dicht is, is zinvol.
- N-4 (`storedRuleStatus` bij `latest_local '00:00'`) en N-5 (`profileInvalid`) zijn netjes verwerkt.

## Blokkerend
Geen.

## Niet-blokkerend
N-1: Bij "Externe afhankelijkheden" staat dat speedate tijden met "optioneel een tijdzone" leest. De speedate-README noemt tijdzones alleen bij datetime, niet bij losse tijden. Voor de pariteit maakt het niet uit: een tijd met offset is in Python `invalid` (parsefout of `_naive`) en in TS ook (regex). Formuleer het eventueel voorzichtiger.

N-2: `untrack` is voor `state_referenced_locally` strikt genomen niet nodig. Volgens de docs is een closure de oplossing, en `untrack(() => …)` is die closure. Het kan blijven. Geeft `npm run check` toch nog een waarschuwing, noteer het dan in `deviations.md`, niet als fout.

N-3: De risico's staan in de volgorde R1–R5, R8, R6, R7. Hernummer R8 of zet hem achteraan. Dit is cosmetisch.

N-4: In `forms.test.ts` gebruikt de controle "`effectiveRule(...)` met `parseRuleFields(...).value` gooit niet" profiel `null`. Daardoor toetst hij alleen stap 2, en dat is precies de bedoeling. Een korte opmerking in de test dat dit de garantie van `parseRuleFields` toetst, en dus geen conflictcontrole is, voorkomt verwarring bij de builder.

N-5 (overgenomen uit ronde 1, N-9): de voorstellen A9/A10 (labels) en A13/A14 wachten nog op een reactie van Lars en blokkeren niet.

## Gecontroleerde bronnen
- https://github.com/pydantic/speedate ("Time: `HH:MM:SS.FFFFFF` 1 to 6 digits are reflected in the `time.microsecond`, extra digits are ignored"; `HH:MM` wordt ondersteund; tijdzone alleen bij datetime genoemd)
- https://svelte.dev/docs/svelte/compiler-warnings (`state_referenced_locally`; oplossing: verwijzen binnen een functie of closure)
- Uit ronde 1, nog geldig: https://supabase.com/docs/reference/javascript/upsert, https://docs.postgrest.org/en/v12/references/errors.html, https://svelte.dev/docs/svelte/stores, https://svelte.dev/docs/svelte/$derived, https://svelte.dev/docs/svelte/bind
- Repo (worktree WP-16):
  - `ingest/src/shakka/domain/alerts.py` (`AlertRuleOverride` met `enabled: bool | None`, strict; tijdvalidators; `_check_time_window`; `ProfileDefaults`; `resolve_rule` met `enabled` `None` → `True` en de conflictmelding "must be below");
  - `ingest/src/shakka/domain/direction.py` (volgorde van `DirClass`);
  - `ingest/src/shakka/domain/spot.py` (`default_min_kn` 5–40 of `None`);
  - `ingest/tests/evaluation_fixtures.py` (`make_spot`);
  - bestaande imports in `ingest/tests/test_alert_rules.py` en `alert_fixtures.py`;
  - `data/contracts/alert_defaults.json`;
  - `web/src/lib/{contracts,labels,time,types}.ts` (`dirClassLabel`, `formatKn`, `WEEKDAY_ABBR_NL`, `WEEKDAY_NL`, `RIDABLE_DIR_CLASSES`).
