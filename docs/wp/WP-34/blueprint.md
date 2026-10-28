# Blueprint WP-34: Visueel ontwerp: strak, licht en donker
Status: DRAFT
Revisie: 2

## Doel
Shakka krijgt het uiterlijk van ontwerp B, "de dag als tijdlijn" (`docs/wp/WP-34/mockup-b.html`):
- grafiet op bijna-wit, één zeeblauw accent;
- een strak raster met dunne scheidingslijnen, zonder schaduwen en zonder pillen;
- per spot een dunne uurbalk in gedempte oordeelkleuren;
- een tabbalk onderaan;
- een donkere modus die `prefers-color-scheme` volgt.

Wat de app doet blijft gelijk, op twee bewuste uitzonderingen na: dagen als tabbladen op de spotpagina en de tijdlijnbalk. Beide zijn alleen weergave en gebruiken geen nieuwe data. Contrast blijft in beide modi minstens WCAG AA en wordt getoetst vanuit de tokens in `app.css`. Basis-scope en AC's: `docs/WORK_PACKAGES_V2.md`, WP-34. Wat ontwerp B daaraan verandert, staat onder A7 en "Aanpassingen aan de WP-tekst".

## Verwerking review
Ronde 1 (`review.md`):
- **B-1 (e-mailadres in screenshots)** → Eén vaste werkwijze, door de verifier af te vinken in `verification.md` (zie Testplan AC-7):
  - vóór elke ingelogde screenshot zet de verifier `.who` via eval op `test@example.com`;
  - `login-*` wordt uitgelogd gefotografeerd, vóór Lars inlogt;
  - de inloglink en het sessietoken komen nergens in tekst of commit;
  - de verifier bekijkt elke PNG vóór de commit op e-mailadressen en echte namen.
- **B-2 (specificiteit)** → Alle basisregels voor `button` en velden staan in `:where()` (specificiteit 0), en `[aria-invalid='true']` is per element uitgeschreven (zie Gedeelde regels). De verifier controleert op `/profiel` met `getComputedStyle` dat submit primair is, danger rood en een ongeldig veld een foutrand heeft.
- **N-1** → `cdn\.` staat in de regex van `no-external-css.test.ts`.
- **N-2** → De markerschaduw vervalt: ontwerp B heeft geen schaduwen.
- **N-3** → Accent op `notice-bg` en op `warning-bg` staat in `PAIRS`.
- **N-4** → Opgelost. WP-30 is gemerged, en `QuietHoursSettings` krijgt de 24-uursbalk.
- **N-5** → Testsessie annuleren en testaccount verwijderen staan als laatste stap van AC-7.

## Aannames
- **A1 (bevestigd).** De kaart blijft in de donkere modus licht (`streets-v4`). Markers en de laadmelding volgen de tokens. Een donkere kaartstijl wordt een vervolg-WP.
- **A2 (Lars kan aanpassen).** De kleuren komen uit `mockup-b.html` (`.screen.light`/`.screen.dark`). Vijf tokens staan niet in de mockup en zijn door de planner gekozen, met AA-controle: `surface-muted`, `error`, `warning-bg`, `notice-bg` en `on-verdict`. `contrast.test.ts` beslist.
- **A3.** De header is licht: `--color-header-bg` is gelijk aan `--color-bg`. Het merk staat in tekstkleur met hoofdletters (CSS). Daaronder een dunne lijn.
- **A4 (reviewer akkoord).** "Elke token in beide blokken" geldt voor `--color-*` plus `--shadow-card`. Afstand, radius en lettergrootte staan alleen in `:root`.
- **A5.** Extra tokens, alleen in `:root` behalve de kleur:
  - `--color-border-strong` (in beide blokken);
  - `--font-sans`, `--font-size-xs`, `--tap`, `--tabbar-h` en `--content-max`.
- **A6.** `--color-brand` blijft als alias `var(--color-accent)` in beide blokken.
- **A7 (Lars bevestigt; gevolg van zijn keuze voor B).** Ontwerp B wijkt op vier punten af van de WP-tekst:
  - geen schaduw (`--shadow-card: none`) en geen kaarten: spots en secties zijn rijen met dunne lijnen;
  - het "grote label" is een stip met tekst in groter, vetter schrift, geen gevulde pil;
  - op de gedempte oordeelkleuren haalt geen tekstkleur 4.5:1. Daarom staat er nergens tekst op een oordeelkleur, en worden de kleuren als niet-tekst (3:1) getoetst. `--color-on-verdict` blijft bestaan als tekstkleur op de danger-knop;
  - AC-8 "kaart met groot label" wordt "rij met groot label".
- **A8 (orchestrator bevestigt).** De tijdlijn op de lijst gebruikt de uurrijen die `getSpotSummaries` al ophaalt en nu na het tellen weggooit. `SpotSummary` krijgt een optioneel veld `hours`. Er komt geen nieuwe query, kolom of request bij.
- **A9.** De tijdlijn van vandaag begint bij het huidige uur, want de lijst en de spotpagina laden data vanaf `floorHour(now)`. "Nu" staat daardoor in het eerste segment. Eerdere uren laden is nieuwe data en valt buiten scope.
- **A10.** De tijdlijn is `aria-hidden="true"`. Alles wat hij toont, staat al als tekst op de pagina: de dagtekst, de uurlijst, de getijregel en de samenvatting van de stille uren. Er komt dus geen nieuwe schermlezertekst bij, en een oordeel hangt nooit alleen van kleur af.
- **A11.** Nieuwe zichtbare tekst blijft minimaal:
  - de tablink "Spots";
  - de dagtabs "Vandaag", "Morgen" en de datum;
  - in de balk `LW hh:mm`, `HW hh:mm`, `nu` en uurcijfers (aria-hidden).

  De bestaande linkteksten blijven, ook "Mijn sessies" (en dus niet "Sessies"), want `layout.test.ts` zoekt daarop.
- **A12.** De tabbalk staat er alleen als je ingelogd bent. `layout.test.ts` eist dat Alerts, Profiel en Mijn sessies uitgelogd ontbreken. Uitgelogd blijft de header met merk, "Over" en "Inloggen".
- **A13.** De tabbladen hebben geen actieve markering (`aria-current`). Daarvoor is route-state in de layout nodig, en dat is gedrag. Vervolg.
- **A14.** Twee plekken uit de opdracht vallen af:
  - tijdlijn op `/sessie/nieuw` (5a): die pagina laadt geen evaluaties, dus de balk zou nieuwe data vragen;
  - tijdlijn bij een kaartselectie: de kaart kent geen selectie, want markers zijn links naar de spotpagina. Een selectiepaneel is gedrag.

  Beide zijn vervolg-WP's.
- **A15.** Een niet-gekozen dag krijgt de klasse `day-inactive` (`display: none` in CSS), niet het attribuut `hidden`. In de browser is het effect gelijk. Met `hidden` zouden twee bestaande tests in `spot-page.test.ts` breken: de kop "Morgen" en de go-links van alle dagen. AC-2 houdt bestaande tests ongewijzigd.
- **A16 (Lars bevestigt).** Screenshots:
  - de publieke pagina's komen van een lokale build tegen het productieproject, alleen-lezend met de anon-key uit `web/.env`;
  - de ingelogde pagina's en `sessie` vragen een testaccount en een testsessie met een verzonnen voornaam ("Sanne"). Lars logt één keer in, in de browser van de preview-tool, via het plakveld op `/login`;
  - zonder die login zijn de 8 ingelogde bestanden `NEEDS_LARS`.

  Werkwijze B-1: zie Testplan AC-7.
- **A17. Omvang L.** Splitsing voorgesteld: **WP-34a** is Deel A, de stijl. **WP-34b** is Deel B: de tijdlijn, de dagtabs en de screenshots. Zie het Stappenplan. 34b hangt af van 34a. De orchestrator legt de splitsing vast in WORK_PACKAGES_V2.

## Aanpassingen aan de WP-tekst
De orchestrator neemt deze op in WORK_PACKAGES_V2:
- **AC-2.** De diff in `web/src` toont `.svelte`, `.css` en `app.html`, plus de uitzonderingen onder "Niet-CSS-wijzigingen":
  - `lib/timeline.ts` (nieuw);
  - `lib/types.ts` en `lib/view.ts`, alleen additief.

  Bestaande exportsignaturen veranderen niet. Bestaande tests veranderen niet, behalve `contrast.test.ts`.
- **AC-3.** De paren zijn die uit `PAIRS` hieronder. `--color-on-verdict` wordt getoetst op `--color-error`. Go, marginal en no-go worden als niet-tekst (3:1) getoetst op bg en surface. `--color-none` is decoratief (arcering).
- **AC-8.** "Op `home`: per spot een rij met een groot label voor vandaag en de tijdlijn."
- **AC-10 (nieuw, 34b).** Op de spotpagina wisselen dagtabs de zichtbare dag, en de eerste dag is standaard gekozen. Een test toetst het wisselen.
- **AC-11 (nieuw, 34b).** `DayTimeline` staat op vier plekken: de lijst (vandaag en morgen), de spotpagina (per dag, met LW/HW en nu), `/s/[slug]` (tijdvak omkaderd) en Stille uren (24 uur). De componenten zijn getest. `timeline.ts` is unit-getest.

## Ontwerp
**Tokens.**
- Bovenaan `app.css` staan precies twee tokenblokken: `:root` (licht, met `color-scheme: light dark`) en `@media (prefers-color-scheme: dark) { :root {…} }`.
- Alleen daar staan kleurwaarden.
- Al het andere gebruikt `var(--…)`, `currentcolor`, `transparent`, `inherit` of systeemkleuren in `forced-colors`.
- Een `repeating-linear-gradient` met `var()`-kleuren is toegestaan.

**Basislaag met specificiteit 0 (B-2).**
- Elementregels voor `button` en velden staan in `:where(…)`. Elke klasse (`.danger`, `.favorite-star`, `.share-button`), elke attribuutselector (`button[type='submit']`) en MapLibre (`.maplibregl-ctrl-group button`) wint daardoor zonder `!important`.
- Koppen, links en lijsten zijn gewone elementselectors (0,0,1).
- Pagina's krijgen hun uiterlijk zo via gedeelde regels, en lokale `<style>`-blokken met kleur of knopmaat verdwijnen.

**Raster en vlakken (B).**
- Geen kaarten. `main > section:not(.map-wrap)` krijgt een bovenlijn (`--color-border`) en ruimte erboven.
- `.spot-item`, `.alert-rule`, `.my-session`, `.manage-list li` en de uurregels zijn rijen met een bovenlijn.
- Radius is hoogstens 6 px.
- Labels zijn klein, in hoofdletters en gedempt: `.day-label`, `.badge-unverified`, `.day > h2`, `.form-field > label`.
- Cijfers zijn `tabular-nums`.

**Header en tabbalk.**
- De header is licht. Links het merk, rechts een `nav` "Hoofdmenu" met:
  - "Over";
  - ingelogd: `.who` (ellipsis) en "Uitloggen";
  - uitgelogd: "Inloggen".
- Ingelogd staat na de footer een `nav.tab-bar` met vier links: Spots (`/`), Alerts, Mijn sessies en Profiel.
  - Elke link is een inline SVG-icoon (paden uit de mockup-symbolen `i-sp`, `i-al`, `i-se`, `i-pr`, `stroke="currentColor"`, `aria-hidden`) met de tekst eronder.
  - De balk staat `position: fixed` onderaan, met `padding-bottom: env(safe-area-inset-bottom)`.
  - De footer krijgt dan de klasse `has-tab-bar` (ruimte onder de footer), zodat er niets onder de balk verdwijnt.
  - Er is geen JavaScript-menu, en de routes blijven gelijk.

**Spotlijst.**
- Elke `.spot-item` is een rij.
- Kop: links naam en regio, met daaronder het label "niet geverifieerd". Rechts de ster.
- Dan de tijdlijn van vandaag (`md`) en `p.day-summary.day-today`: "Vandaag:" als label, `VerdictBadge size="lg"` en de dagtekst.
- Dan `p.day-summary` voor morgen (compact), gevolgd door een dunne balk (`sm`).
- Tekst en volgorde van de tekst blijven gelijk, zodat `spot-list.test.ts` groen blijft.

**Spotpagina.**
- De terug-link krijgt een CSS-chevron, en de titelrij blijft gelijk.
- "Niet geverifieerd" wordt een lijn-notitie in de stijl van `.wn`.
- Onder de freshness-regel staat de groep dagtabs (`role="group"`, `aria-label="Dag"`). Elke knop heeft `aria-pressed`, `aria-controls` en de stijl van een onderstreepte tab.
- Daarna de knop "Toon ook donkere uren" (ongewijzigd) en alle `section.day`. Alleen de gekozen dag is zichtbaar (A15).
- Per dag:
  - het label (`h2`);
  - `DayTimeline size="lg"` met de getij-extremen van die dag en, alleen vandaag, "nu";
  - de getijregel;
  - de "Ik ga"-knoppen (primair, in accent);
  - de uurregels.
- Uurregels: tijd en oordeel (stip met tekst), wind en richting op de eerste regel. Richtingsklasse, betrouwbaarheid en redenen staan klein en gedempt eronder.

**Kaart.**
- `MapSwitch` wordt een onderstreepte tab-schakelaar: de ingedrukte knop krijgt tekstkleur en een onderlijn van 2 px, de andere is gedempt.
- `MapView` krijgt een omlijnde container met `--radius-lg`.
- Markers: een chip op `--color-surface` met `--color-text`, een rand in `--color-border-strong`, de stip met het oordeel, en geen schaduw.

**Tijdlijn.**
- `lib/timeline.ts` rekent puur. Het bouwt een `Timeline` uit:
  - evaluaties of samenvattingsuren;
  - getij-extremen;
  - een sessietijdvak;
  - stille uren.
- `DayTimeline.svelte` tekent dat in drie maten:
  - `sm`: 4 px, zonder cijfers;
  - `md`: 8 px, met cijfers;
  - `lg`: 28 px, met cijfers, markers en het omkaderde tijdvak.
- Stijl in de eigen `<style>`, alleen met tokens. `forced-color-adjust: none` houdt de segmenten zichtbaar in de forced-colors-modus.

**Formulieren en overige pagina's.**
- Velden: rand `--color-border-strong`, radius 4 px, `font-size: 1rem` (geen zoom op iOS), `min-height: var(--tap)`.
- Checkbox en radio: `accent-color: var(--color-text)`.
- Knoppen:
  - secundair: transparant met een sterke rand;
  - primair: accent;
  - danger: error met on-verdict.
- Banners: een vlak in `notice-bg` of `warning-bg` met een linkerrand van 3 px.
- `.notice` en `.notice-ok`: tekstkleur met een linkerrand in marginal of go.
- Stille uren krijgt de 24-uursbalk onder de samenvatting. `/s/[slug]` krijgt onder "Georganiseerd door" de `lg`-balk met het tijdvak.

**Toegankelijkheid.**
- Focus: `:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px }`.
- Links in lopende tekst blijven onderstreept.
- Transities (alleen `background-color` en `color`, 120 ms) staan binnen `prefers-reduced-motion: no-preference`.
- In `forced-colors: active` krijgen knoppen en knop-links een rand in `CanvasText`.
- Elk aanraakdoel is minstens `--tap` hoog.

**Thema-kleur.** `app.html` krijgt een `color-scheme`-meta en twee `theme-color`-tags (licht eerst). Het manifest gaat naar de lichte waarden.

### Niet-CSS-wijzigingen (AC-2)
1. `lib/timeline.ts` (nieuw): pure functies voor de tijdlijn. Ze staan in `.ts` zodat ze zonder render te testen zijn.
2. `lib/types.ts`: nieuw type `SummaryHour` en het optionele veld `SpotSummary.hours`. Additief.
3. `lib/view.ts`: `summarizeSpots` vult `hours`. De signatuur blijft gelijk, en de velden `today` en `tomorrow` blijven gelijk (`view.test.ts` toetst met `toEqual`).
4. In `.svelte`:
   - de prop `size` op `VerdictBadge`;
   - de state `selectedDay` op de spotpagina;
   - `$derived`-tijdlijnen op de lijst, de spotpagina, `/s/[slug]` en in `QuietHoursSettings`;
   - de header- en tabbalk-markup in `+layout.svelte`.
5. Buiten `web/src`:
   - `web/static/manifest.webmanifest`;
   - `web/test/contrast.test.ts` (omgebouwd);
   - nieuwe tests en `web/test/helpers/tokens.ts`.

## Bestanden
| Bestand | Actie | Deel | Inhoud |
|---|---|---|---|
| `web/src/app.css` | wijzigen | A | Herschreven: tokenblokken, `:where`-basis, typografie, header, tabbalk, footer, knoppen, velden, rijen, banners, labels, oordeelstip, spotpagina, a11y-media. |
| `web/src/app.html` | wijzigen | A | `color-scheme`-meta, twee `theme-color`-tags. |
| `web/static/manifest.webmanifest` | wijzigen | A | `theme_color` en `background_color` `#fbfbfa`. |
| `web/src/routes/+layout.svelte` | wijzigen | A | Header-`nav` zonder de drie app-links; `nav.tab-bar` met iconen na de footer; `class:has-tab-bar`. |
| `web/src/lib/components/VerdictBadge.svelte` | wijzigen | A | Prop `size`, klasse `verdict-lg`. |
| `web/src/routes/+page.svelte` | wijzigen | A+B | A: `.spot-head`/`.spot-title`, `day-today`, `day-label`/`day-text`, `size="lg"`. B: twee `DayTimeline`'s. |
| `web/src/routes/spot/[id]/+page.svelte` | wijzigen | A+B | A: `<style>` weg, `class="back-link"`. B: dagtabs, `day-inactive`, `DayTimeline` per dag. |
| `web/src/routes/s/[slug]/+page.svelte` | wijzigen | B | `DayTimeline` met tijdvak na `.session-organizer`. |
| `web/src/lib/components/QuietHoursSettings.svelte` | wijzigen | B | 24-uursbalk na `.quiet-summary`. |
| `web/src/lib/components/DayTimeline.svelte` | aanmaken | B | Weergave van een `Timeline`. |
| `web/src/lib/timeline.ts` | aanmaken | B | `dayTimeline`, `sessionTimeline`, `quietTimeline`, `hoursOnDay`, `dayTabLabel`. |
| `web/src/lib/types.ts` | wijzigen | B | `SummaryHour`, `SpotSummary.hours?`. |
| `web/src/lib/view.ts` | wijzigen | B | `summarizeSpots` vult `hours` (gesorteerd). |
| `web/src/routes/mijn-sessies/+page.svelte` | wijzigen | A | `<style>` weg (`.share-button` en `.my-session` naar `app.css`). |
| `web/src/routes/sessie/[slug]/delen/+page.svelte` | wijzigen | A | `<style>` weg (`.share-actions` en `.share-button` naar `app.css`). |
| `web/src/routes/sessie/[slug]/beheer/+page.svelte` | wijzigen | A | `<style>`: `currentcolor` wordt `var(--color-border)`, de min-height-regel vervalt. |
| `web/src/lib/components/SessionForm.svelte` | wijzigen | A | `<style>` weg. |
| `web/src/lib/components/MapSwitch.svelte` | wijzigen | A | `<style>`: tab-schakelaar met tokens. |
| `web/src/lib/components/MapView.svelte` | wijzigen | A | `<style>`: tokens, container, marker zonder schaduw, `.verdict-none` eruit. |
| `web/test/helpers/tokens.ts` | aanmaken | A | `readTokens`, `stripTokenBlocks`. |
| `web/test/tokens.test.ts` | aanmaken | A | Parser op een inline fixture. |
| `web/test/contrast.test.ts` | wijzigen | A | Tokenparen per modus plus inventaris. |
| `web/test/theme-color.test.ts` | aanmaken | A | AC-4. |
| `web/test/verdict-badge.test.ts` | aanmaken | A | AC-6. |
| `web/test/no-external-css.test.ts` | aanmaken | A | AC-5. |
| `web/test/tab-bar.test.ts` | aanmaken | A | Tabbalk ingelogd en uitgelogd. |
| `web/test/timeline.test.ts` | aanmaken | B | Pure functies. |
| `web/test/summary-hours.test.ts` | aanmaken | B | `summarizeSpots().hours`. |
| `web/test/day-timeline.test.ts` | aanmaken | B | Component. |
| `web/test/spot-day-tabs.test.ts` | aanmaken | B | AC-10. |
| `web/test/timeline-placements.test.ts` | aanmaken | B | Lijst, `/s/[slug]`, Stille uren. |
| `docs/wp/WP-34/screens/*.png` | aanmaken (verifier) | B | 16 screenshots. |

## Interfaces en contracten

### Tokenblokken in `app.css`
```css
/* Design tokens (WP-34, design B). Colour values only in these two blocks. */
:root {
	color-scheme: light dark;
	/* colours, shadow, then the mode-independent tokens */
}
@media (prefers-color-scheme: dark) {
	:root {
		/* colours and shadow only */
	}
}
```
Elk blok staat er precies één keer, en er is geen ander `:root`-blok.

### Kleurtokens (in beide blokken)
| Token | Licht | Donker | Gebruik |
|---|---|---|---|
| `--color-bg` | `#fbfbfa` | `#15181b` | pagina |
| `--color-surface` | `#ffffff` | `#1b1f23` | velden, markerchip |
| `--color-surface-muted` | `#f1f2f4` | `#22272c` | hover, laadmelding van de kaart |
| `--color-text` | `#1d2125` | `#e4e6e9` | tekst, ster, tab-onderlijn, "nu"-lijn |
| `--color-muted` | `#5b626a` | `#9ba2aa` | labels, hints, footer, inactieve tab, stille uren in de balk |
| `--color-border` | `#e3e5e8` | `#2b3036` | scheidingslijnen, balk "buiten"/"vrij" |
| `--color-border-strong` | `#878e96` | `#6f7780` | randen van velden en secundaire knoppen |
| `--color-accent` | `#0369a1` | `#4fb3e8` | links, primaire knop |
| `--color-brand` | `var(--color-accent)` | `var(--color-accent)` | alias |
| `--color-on-accent` | `#ffffff` | `#0b1a24` | tekst op accent |
| `--color-focus` | `#0369a1` | `#4fb3e8` | focusring |
| `--color-header-bg` | `#fbfbfa` | `#15181b` | header en tabbalk; `theme-color` |
| `--color-header-text` | `#1d2125` | `#e4e6e9` | merk |
| `--color-go` | `#3f7a58` | `#6aa883` | balksegment, stip, rand van `.notice-ok` |
| `--color-marginal` | `#a77c25` | `#c4a052` | balksegment, stip, rand van `.notice` en `.banner` |
| `--color-no-go` | `#a3746a` | `#b48a80` | balksegment, stip |
| `--color-none` | `#c4c8cd` | `#4a5058` | arcering "geen data" en stip "geen oordeel" (decoratief) |
| `--color-on-verdict` | `#ffffff` | `#0b1a24` | tekst op de danger-knop |
| `--color-error` | `#b91c1c` | `#f87171` | fouttekst, rand `aria-invalid`, danger-knop |
| `--color-warning-bg` | `#fbf1ef` | `#261b1a` | `.banner.warning` |
| `--color-notice-bg` | `#faf6ee` | `#221f17` | `.banner` |

`--shadow-card: none` staat in beide blokken (A7).

### Overige tokens (alleen `:root`)
| Token | Waarde |
|---|---|
| `--font-sans` | `system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif` |
| `--font-size-xs` / `-sm` / `-base` / `-lg` / `-xl` / `-verdict` | `0.75rem` / `0.8125rem` / `1rem` / `1.0625rem` / `1.75rem` / `1.125rem` |
| `--space-1` … `--space-6` | `0.25rem`, `0.5rem`, `0.75rem`, `1rem`, `1.5rem`, `2rem` |
| `--radius` / `--radius-lg` | `0.25rem` / `0.375rem` |
| `--tap` / `--tabbar-h` / `--content-max` | `2.75rem` / `3.5rem` / `40rem` |

Typografie:
- `body`: `--font-sans`, base, `line-height: 1.45`, `font-variant-numeric: tabular-nums`;
- `h1`: xl, 600, `letter-spacing: -0.01em`, `line-height: 1.2`;
- `h2`: lg, 600;
- `h3`: base, 600;
- labelstijl (`.day-label, .badge-unverified, .day > h2, .form-field > label`): xs, `text-transform: uppercase`, `letter-spacing: 0.08em`, 500, `--color-muted`;
- sm voor `.hint`, `.compact`, `.site-footer`, `.waves`, `.dir-class`, `.confidence` en `.reasons`.

### Gedeelde regels (`app.css`)
- **Knop, basis:** `:where(button:not(.map-canvas button))` krijgt:
  - `font: inherit`, gewicht 500, `min-height: var(--tap)`, `padding: var(--space-2) var(--space-4)`;
  - `border: 1px solid var(--color-border-strong)`, `border-radius: var(--radius-lg)`;
  - `background: transparent`, `color: var(--color-text)`.

  Hover: `--color-surface-muted`. `:disabled`: `opacity: 0.55`.
- **Primair:** `button[type='submit'], .share-button, .go-run` krijgt accent als achtergrond en rand, `--color-on-accent`, gewicht 600, en `text-decoration: none` voor links. Knop-links krijgen `display: inline-flex; align-items: center; min-height: var(--tap)`.
- **Danger:** `.danger` krijgt error als achtergrond en rand, met `--color-on-verdict`.
- **Ster en header:** `.favorite-star` en `.site-header button` krijgen `background: transparent; border: 0`. `.favorite-star` krijgt `color: var(--color-text)`.
- **Veld, basis:** `:where(input:not([type='checkbox'], [type='radio']), select, textarea)` krijgt:
  - `font: inherit; font-size: 1rem`, `min-height: var(--tap)`, `box-sizing: border-box`, `max-width: 100%`;
  - `padding: var(--space-2) var(--space-3)`, rand border-strong, `--radius`, achtergrond surface, tekst text.

  In `.form-field` krijgt het veld `width: 100%`.
- **Foutrand:** `input[aria-invalid='true'], select[aria-invalid='true'], textarea[aria-invalid='true']` krijgt `border-color: var(--color-error)`.
- **Checkbox en radio:** `:where(input[type='checkbox'], input[type='radio'])` krijgt `accent-color: var(--color-text)` en 1.125rem.
- **Rij:** `.spot-item, .alert-rule, .my-session, .hours > li, .manage-list li` krijgt `border-top: 1px solid var(--color-border)` en `padding-block: var(--space-3)`.
- **Sectie:** `main > section:not(.map-wrap)` krijgt `border-top: 1px solid var(--color-border)`, `margin-top: var(--space-5)` en `padding-top: var(--space-4)`.
- **Banner:**
  - `.banner`: notice-bg, `border-left: 3px solid var(--color-marginal)`, `border-radius: 0 var(--radius) var(--radius) 0`;
  - `.banner.warning`: warning-bg, rand error;
  - `.banner.unverified`: transparant, `border-left: 2px solid var(--color-border-strong)`, `--color-muted`, sm.
- **Notitie:** `.notice` en `.notice-ok` krijgen tekstkleur, sm, en een `border-left` van 2 px in marginal of go.
- **Oordeel:**
  - `.verdict`: `inline-flex; align-items: center; gap: 0.4em; color: inherit; font-weight: 600`;
  - `.verdict::before`: `content: ''; width: 0.5em; height: 0.5em; border-radius: 50%`;
  - `.verdict-go::before` tot en met `.verdict-none::before` krijgen achtergrond `--color-<oordeel>`;
  - `.verdict-lg`: `font-size: var(--font-size-verdict)`, en de stip 0.625em.
- **Tabs:** `.view-toggle button, .day-tabs button` krijgen:
  - geen rand en geen achtergrond, `--color-muted`, `border-bottom: 2px solid transparent`, `border-radius: 0`;
  - `[aria-pressed='true']`: `--color-text` en `border-bottom-color: var(--color-text)`.

  `.day-tabs` is `display: flex; overflow-x: auto` met een onderlijn in border-color. `.day-inactive` is `display: none`.
- **Tabbalk:** `.tab-bar` krijgt:
  - `position: fixed; inset: auto 0 0 0`;
  - `display: grid; grid-template-columns: repeat(4, 1fr)`;
  - header-bg, een bovenlijn, `padding-bottom: env(safe-area-inset-bottom)`, `z-index: 10`.

  Links: `flex column`, `min-height: var(--tabbar-h)`, xs, `--color-muted`, geen onderstreping. SVG 1.375rem, `fill: none; stroke: currentcolor; stroke-width: 1.5`. `.site-footer.has-tab-bar` krijgt `padding-bottom: calc(var(--tabbar-h) + env(safe-area-inset-bottom) + var(--space-4))`.
- **Header:** `.site-header` krijgt:
  - `display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between`;
  - header-bg, een onderlijn;
  - `.brand`: header-text, sm, 700, uppercase, `letter-spacing: 0.16em`, geen onderstreping;
  - `.who`: `flex: 1 1 8rem; min-width: 0`, ellipsis, muted, sm.

  Header, `main` en footer: `padding-inline: max(var(--space-4), calc((100% - var(--content-max)) / 2 + var(--space-4)))`, en minimaal `env(safe-area-inset-left)` en `env(safe-area-inset-right)`.

### `VerdictBadge.svelte`
```ts
let { verdict, size = 'sm' }: { verdict: Verdict; size?: 'sm' | 'lg' } = $props();
```
```svelte
<span class={['verdict', `verdict-${verdict}`, size === 'lg' && 'verdict-lg']} data-verdict={verdict}>{verdictLabel(verdict)}</span>
```

### `lib/types.ts` (additief)
```ts
/** Daylight row kept by summarizeSpots for the list timeline (WP-34). */
export type SummaryHour = Pick<SummaryRow, 'valid_at' | 'verdict' | 'reasons'>;
// in SpotSummary:
	hours?: SummaryHour[]; // daylight rows of today and tomorrow, sorted by valid_at (WP-34)
```
`summarizeSpots` voegt elke rij toe die het telt, dus na alle bestaande filters, en sorteert per spot op `Date.parse(valid_at)`. Verder verandert er niets.

### `lib/timeline.ts`
```ts
import type { Evaluation, ReasonCode, TideExtreme, Verdict } from './types.js';

export const HOUR_MS = 3_600_000;
export type SlotKind = Verdict | 'none' | 'outside' | 'quiet' | 'free';
export type TimelineHour = Pick<Evaluation, 'valid_at' | 'verdict'> & { reasons?: readonly ReasonCode[] };
export interface TimelineTick { pos: number; label: string }               // pos in [0, 1]
export interface TimelineMarker { pos: number; label: string; kind: 'low' | 'high' | 'now'; row: 0 | 1 }
export interface Timeline {
	slots: SlotKind[];                                   // one per hour, equal width, left to right
	ticks: TimelineTick[];
	markers: TimelineMarker[];                           // sorted by pos
	window: { from: number; to: number } | null;         // fractions of the axis
}

/** Hours whose local date (Europe/Amsterdam) is dateKey. */
export function hoursOnDay<T extends Pick<Evaluation, 'valid_at'>>(hours: readonly T[], dateKey: string): T[];

/** 'Vandaag' | 'Morgen' | formatDateKey(dateKey, 'day'). */
export function dayTabLabel(dateKey: string, todayKey: string): string;

/** Daylight hours (no 'dark' reason) of one day. Axis = first daylight hour to last + 1 h, one slot per
 *  HOUR_MS step; a missing hour is 'none'. Ticks at boundaries whose local hour % 3 === 0, label 'HH'.
 *  Tides become markers 'LW hh:mm' / 'HW hh:mm', now becomes 'nu'; each only when 0 <= pos <= 1.
 *  Marker rows: in pos order, a marker less than 0.2 after the last row-0 marker gets row 1.
 *  null when there is no daylight hour. */
export function dayTimeline(
	hours: readonly TimelineHour[],
	opts?: { tides?: readonly TideExtreme[]; now?: Date }
): Timeline | null;

/** Session window on its local day. startH/endH = local hour + minute/60 (endH = 24 when ends_at is on
 *  the next local date at 00:00). Axis = [min(6, floor(startH)), max(22, ceil(endH))). A slot whose hour
 *  overlaps [startH, endH) gets the verdict of the evaluation with the same local date and hour, or 'none';
 *  other slots are 'outside'. window = [(startH - axisFrom) / n, (endH - axisFrom) / n]. Ticks every
 *  3 local hours. No markers. null when start and end lie on different local dates (other than end at
 *  00:00) or when endH <= startH. */
export function sessionTimeline(
	evaluations: readonly TimelineHour[],
	startsAt: string,
	endsAt: string
): Timeline | null;

/** 24 slots for local hours 0..23: 'quiet' when h*60 lies in [from, until) (wrapping past midnight
 *  when from > until), else 'free'. Ticks 00, 06, 12, 18, 24. Accepts 'HH:MM' or 'HH:MM:SS'.
 *  null when either is null or invalid, or both are equal. */
export function quietTimeline(quietFrom: string | null, quietUntil: string | null): Timeline | null;
```
Lokale uren en datums gaan alleen via `localParts`, `localDateKey` en `formatLocal` uit `time.ts`. Gebruik geen `getHours` en dergelijke (`no-local-date-getters.test.ts`).

### `DayTimeline.svelte`
```ts
let { timeline, size = 'md' }: { timeline: Timeline; size?: 'sm' | 'md' | 'lg' } = $props();
```
```svelte
<div class="timeline timeline-{size}" aria-hidden="true">
  <div class="timeline-track">
    {#if size === 'lg'}{#each timeline.markers as m (m.kind + m.pos)}
      <span class="timeline-marker timeline-marker-{m.kind}" class:timeline-marker-row2={m.row === 1} style:left="{m.pos * 100}%">{m.label}</span>
    {/each}{/if}
    <div class="timeline-bar">{#each timeline.slots as k, i (i)}<span class="slot slot-{k}"></span>{/each}</div>
    {#if timeline.window}<span class="timeline-window" style:left="{timeline.window.from * 100}%" style:width="{(timeline.window.to - timeline.window.from) * 100}%"></span>{/if}
  </div>
  {#if size !== 'sm'}<div class="timeline-ticks">{#each timeline.ticks as t (t.pos)}<span class="timeline-tick" style:left="{t.pos * 100}%">{t.label}</span>{/each}</div>{/if}
</div>
```
Stijl (in `<style>`, alleen tokens):
- **Balk:** `display: flex; gap: 2px` (1px bij `sm`), hoogte 4, 8 of 28 px (0.25, 0.5 of 1.75rem). De buitenste segmenten hebben radius 2px.
- **Segmenten:**
  - `slot-go`, `slot-marginal` en `slot-no_go` krijgen `--color-<oordeel>`;
  - `slot-none`: `repeating-linear-gradient(135deg, var(--color-none) 0 1px, transparent 1px 4px)`;
  - `slot-outside` en `slot-free`: `--color-border`;
  - `slot-quiet`: `--color-muted`.
- **Venster:** `1.5px solid var(--color-text)`, radius 3px. Het steekt 0.3rem boven en onder de balk uit.
- **Markers:**
  - het label staat boven de balk, een lijn loopt door de balk;
  - `low` en `high` krijgen een gestippelde lijn in `--color-muted`, `now` een doorgetrokken lijn van 1.5px in `--color-text`;
  - `row2` staat één labelregel hoger, en `.timeline-track` reserveert daarvoor ruimte als `size === 'lg'`;
  - een marker met `pos > 0.8` lijnt rechts uit (`translateX(-100%)`, lijn rechts).
- **Cijfers:** xs, muted. `pos 0` staat links, `pos 1` rechts uitgelijnd, de rest `translateX(-50%)`.
- `.timeline { forced-color-adjust: none }`.

### Plaatsing (DOM)
- **Lijst** (`+page.svelte`), binnen `{#if summary}`:
  1. `{@const tl = summary.hours ? dayTimeline(hoursOnDay(summary.hours, summary.today.date)) : null}`, en `tm` net zo voor `summary.tomorrow.date`;
  2. `{#if tl}<DayTimeline timeline={tl} />{/if}`;
  3. `p.day-summary.day-today`;
  4. `p.day-summary`;
  5. `{#if tm}<DayTimeline timeline={tm} size="sm" />{/if}`.

  Kop:
  ```svelte
  <div class="spot-head">
    <div class="spot-title">
      <a class="spot-link">…</a>{#if spot.region}<span class="muted"> · {spot.region}</span>{/if}
      {#if !spot.verified}<span class="badge-unverified">niet geverifieerd</span>{/if}
    </div>
    <FavoriteStar …/>
  </div>
  ```
  De vandaag-regel:
  ```svelte
  <p class="day-summary day-today"><span class="day-label">Vandaag:</span> {#if best}<VerdictBadge verdict={best} size="lg" />{/if} <span class="day-text">{text}</span></p>
  ```
- **Spotpagina:**
  ```ts
  let selectedDay = $state<string | null>(null);
  const activeDay = $derived(groups.some((g) => g.dateKey === selectedDay) ? selectedDay : (groups[0]?.dateKey ?? null));
  ```
  - Tabs: `<div class="day-tabs" role="group" aria-label="Dag">`, per groep `<button type="button" aria-pressed={g.dateKey === activeDay} aria-controls="dagpaneel-{g.dateKey}" onclick={() => (selectedDay = g.dateKey)}>{dayTabLabel(g.dateKey, todayKey)}</button>`.
  - Sectie: `<section class="day" class:day-inactive={g.dateKey !== activeDay} id="dagpaneel-{g.dateKey}" aria-labelledby="dag-{g.dateKey}">`.
  - In de sectie, na de `h2`: `{@const tl = dayTimeline(g.hours, { tides: dayTides, now: g.dateKey === todayKey ? now : undefined })}{#if tl}<DayTimeline timeline={tl} size="lg" />{/if}`.
  - De tijdlijn negeert `showDark`: hij toont altijd daglicht.
- **`/s/[slug]`**, na `p.session-organizer`: `{#if bar}<DayTimeline timeline={bar} size="lg" />{/if}`. Daarbij `const bar = $derived(data.kind === 'ok' && data.evaluations && session ? sessionTimeline(data.evaluations, session.starts_at, session.ends_at) : null)`.
- **Stille uren**, na `p.quiet-summary`: `{#if quiet}<DayTimeline timeline={quiet} />{/if}`. Daarbij `const quiet = $derived(quietTimeline(profile?.quiet_from ?? null, profile?.quiet_until ?? null))`. De balk toont de opgeslagen waarden, niet het formulier.
- **Layout:**
  ```svelte
  <header class="site-header"><a class="brand" href="/">Shakka</a><nav aria-label="Hoofdmenu"><a href="/over">Over</a>{#if $session}<span class="who">…</span><button …>…</button>{:else if $session === null}<a href="/login">Inloggen</a>{/if}</nav></header>
  ```
  Na `</footer>`:
  ```svelte
  {#if $session}<nav class="tab-bar" aria-label="Tabbalk"><a href="/">…Spots</a><a href="/alerts">…Alerts</a><a href="/mijn-sessies">…Mijn sessies</a><a href="/profiel">…Profiel</a></nav>{/if}
  ```
  De footer krijgt `class:has-tab-bar={!!$session}`.

### DOM-haken (ongewijzigd)
`data-spot`, `data-verdict`, `.spot-list`, `.spot-item`, `.spot-link`, `.skip-link`, `#main`, `.site-header`, `.day-summary`, `.title-row`, `.tides`, `.hour`, `.waves`, `.map-marker*`, `.prewrap`, en alle bestaande `id`'s, `aria-*` en teksten.

### `app.html` (vervangt de huidige `theme-color`-regel)
```html
<meta name="color-scheme" content="light dark" />
<meta name="theme-color" content="#fbfbfa" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#15181b" media="(prefers-color-scheme: dark)" />
```
Het manifest krijgt `"background_color": "#fbfbfa"` en `"theme_color": "#fbfbfa"`.

### `web/test/helpers/tokens.ts`
```ts
export type TokenSet = Record<string, string>;
/** Custom properties of the light `:root` block and of the `:root` inside
 *  `@media (prefers-color-scheme: dark)`. Strips comments first. Hex values are
 *  lowercased and expanded to 6 digits. A value `var(--x)` is resolved in the same
 *  mode, then in light (one level). Throws if either block is missing or occurs twice. */
export function readTokens(css: string): { light: TokenSet; dark: TokenSet };
/** The CSS with both token blocks removed (for the inventory). */
export function stripTokenBlocks(css: string): string;
```

### `PAIRS` en `DECORATIVE` in `contrast.test.ts`
Vorm: `[voorgrond, achtergrond, minimum, waar]` met tokennamen, getoetst in `light` en `dark`.

| Voorgrond | Achtergronden | Min |
|---|---|---|
| `--color-text` | bg, surface, surface-muted, warning-bg, notice-bg | 4.5 |
| `--color-muted` | bg, surface, surface-muted, warning-bg, notice-bg | 4.5 |
| `--color-accent` | bg, surface, header-bg, notice-bg, warning-bg | 4.5 |
| `--color-on-accent` | accent | 4.5 |
| `--color-header-text` | header-bg | 4.5 |
| `--color-on-verdict` | error | 4.5 |
| `--color-error` | bg, surface, warning-bg | 4.5 |
| `--color-focus` | bg, surface, header-bg | 3 |
| `--color-border-strong` | bg, surface | 3 |
| `--color-go`, `--color-marginal`, `--color-no-go` (balk en stip) | bg, surface | 3 |

`DECORATIVE = { '--color-border': 'scheidingslijnen, balk buiten/vrij', '--color-brand': 'alias van accent', '--color-none': 'arcering geen data; tekst draagt de betekenis' }`.

## Edge cases
- **E1.** Lang e-mailadres op 375 px → `.who` breekt af met ellipsis, en `scrollWidth` blijft 375 of minder.
- **E2.** Uitgelogd → geen tabbalk, de header toont merk, "Over" en "Inloggen". Is de auth onbekend, dan alleen merk en "Over".
- **E3.** Vandaag geen daglichturen meer → geen balk vandaag, en de dagtekst "geen daglichturen meer" blijft.
- **E4.** Spot zonder summary → "Nog geen data", zonder balk.
- **E5.** `SpotSummary` zonder `hours` (fixtures, `MAP_SUMMARIES`) → geen balk, de rest is ongewijzigd.
- **E6.** Een ontbrekend uur tussen daglichturen → een gearceerd `none`-segment.
- **E7.** Getij buiten de as van de dag → geen marker. De getijregel blijft.
- **E8.** Twee markers dicht bij elkaar (bijv. "nu" en LW) → de tweede krijgt `row: 1`, en de labels overlappen niet.
- **E9.** Acht dagtabs op 343 px → `.day-tabs` scrolt horizontaal, en de pagina loopt niet over.
- **E10.** Na `refreshAll` bestaat de gekozen dag niet meer → `activeDay` valt terug op de eerste groep.
- **E11.** `/s/[slug]`: `evaluations === null`, een sessie over twee datums, of `endH <= startH` → geen balk. De uurlijst is als voorheen.
- **E12.** Een sessie van 05:30 tot 08:00 → de as loopt van 05 tot 22, en het venster begint midden in het eerste segment.
- **E13.** Stille uren uit, `profile === null` of ongeldig → geen balk. Bij 22:00–07:00 loopt de periode over middernacht (9 `quiet`-segmenten).
- **E14.** Zomertijdwissel → `dayTimeline` stapt in UTC-uren, en de labels komen uit `localParts`. In `sessionTimeline` valt een dubbel lokaal uur in hetzelfde segment; de laatste evaluatie wint.
- **E15.** `forced-colors: active` → de balk houdt zijn kleuren, en knoppen krijgen een rand in `CanvasText`.
- **E16.** `prefers-reduced-motion: reduce` → geen transities.
- **E17.** Donkere modus met kaart → lichte tegels met donkere markerchips. De MapLibre-knoppen houden hun eigen stijl.
- **E18.** Tekst op 200 % → alles staat in rem. Header, spotkop en tabs lopen door `flex-wrap`/`overflow-x` op meer regels.
- **E19.** iPhone standalone → tabbalk, header en `main` respecteren `env(safe-area-inset-*)`.

## Testplan
Alle webtests draaien in `npm test`. Fixtures: `test/fixtures/spot-data.ts` (`NOW_FRESH`, `pageData()`, `EVAL_*`, `SPOT_*`), plus de mocks uit de bestaande tests van dezelfde pagina (kopiëren, niet wijzigen).

- **AC-1.**
  - `npm run check && npm test && npm run build && npm run verify:build && npm run size` slaagt.
- **AC-2.**
  - Verifier: `git diff develop... --name-only -- web/src` toont alleen `.svelte`, `app.css`, `app.html`, `lib/timeline.ts`, `lib/types.ts` en `lib/view.ts`.
  - Verifier: `git diff develop... -- web/test` raakt alleen `contrast.test.ts` en nieuwe bestanden.
  - Verifier: de diff van `types.ts` en `view.ts` is additief.
- **AC-3.**
  - `tokens.test.ts`:
    - `reads light and dark blocks`: `#FFF` wordt `#ffffff`, en commentaar wordt genegeerd;
    - `resolves var() in mode, then light`;
    - `throws without dark block / with two light blocks`.
  - `contrast.test.ts`:
    - `contrast helpers`: ongewijzigd;
    - `colour token sets are equal`: ook `--shadow-card` staat in beide;
    - `pairs (%s mode)`: `PAIRS` × `['light','dark']` op `src/app.css`;
    - `every colour token is in PAIRS or DECORATIVE`;
    - `no colour values outside the token blocks`: regex `/#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})\b|rgba?\(|hsla?\(/i` over `.svelte` en `stripTokenBlocks(app.css)`;
    - `every var() used in src is defined`: over `src/**/*.{svelte,css}`, tegen de lichte set.
- **AC-4.**
  - `theme-color.test.ts`:
    - `two theme-color tags`: gelijk aan `--color-header-bg` per modus;
    - `color-scheme meta`;
    - `manifest`: `theme_color` is licht header-bg, `background_color` is licht bg.
- **AC-5.**
  - `no-external-css.test.ts › no external CSS sources`: geen treffer op `@import|@font-face|fonts\.googleapis|fonts\.gstatic|cdn\.|url\(\s*['"]?https?:` in `src/**/*.{css,svelte,html}` en `static/**/*.css` (N-1).
  - Verifier: de diff van `_headers` is leeg, en `rg -l "https://" web/build -g "*.css"` geeft geen nieuwe treffers ten opzichte van `develop` (een bestaande uit `maplibre-gl.css` geldt niet als regressie).
- **AC-6.**
  - De bestaande `a11y-*.test.ts` blijven groen.
  - `verdict-badge.test.ts`:
    - `lg`: de klassen `verdict`, `verdict-go` en `verdict-lg`, `data-verdict="go"` en `verdictLabel('go')`;
    - `default`: zonder `verdict-lg`.
  - `tab-bar.test.ts` (layout-mocks uit `layout.test.ts`):
    - `signed in: four links`: de nav "Tabbalk" bevat Spots → `/`, Alerts, Mijn sessies en Profiel, met de juiste `href`'s, en de SVG's zijn `aria-hidden`;
    - `signed out or unknown: no tab bar`;
    - `footer has-tab-bar only when signed in`.
- **B-2 (verifier, Deel A).** In de preview, ingelogd op `/profiel`, met `getComputedStyle`:
  - `button[type=submit]` heeft als `backgroundColor` de accentwaarde;
  - `.danger` heeft de errorwaarde;
  - een veld met `aria-invalid="true"` (via devtools gezet) heeft `borderColor` gelijk aan de errorwaarde.

  Op de kaart houden de zoomknoppen hun MapLibre-stijl. De waarden komen in `verification.md`.
- **AC-10.**
  - `spot-day-tabs.test.ts`:
    - `tabs per day, first pressed`: knoppen "Vandaag" en "Morgen", Vandaag `aria-pressed="true"`, de Morgen-sectie heeft `day-inactive`;
    - `click switches`: na een klik op "Morgen" draaien `aria-pressed` en `day-inactive` om, en `aria-controls` wijst naar een bestaand `id`;
    - `falls back when the day disappears`: rerender met alleen de evaluaties van morgen → "Morgen" is gekozen.
- **AC-11.**
  - `timeline.test.ts` (fixture: de uren van `NOW_FRESH`, 15 jul):
    - `dayTimeline slots and gaps`: drie uren met een ontbrekend uur ertussen → `['go','none','marginal']`, en `dark` wordt overgeslagen;
    - `ticks at local hours divisible by 3`;
    - `tide and now markers in range only, row staggering`;
    - `null without daylight`;
    - `sessionTimeline`: 11:00–16:00 → as 06–22, venster `[5/16, 10/16]`, binnen het venster de oordelen of `none`, erbuiten `outside`; 05:30–08:00 → as vanaf 05; over twee datums → `null`;
    - `quietTimeline`: 22:00:00–07:00:00 → 9× `quiet`; 13:00–15:00 → 2×; `null` bij uit of gelijke waarden;
    - `hoursOnDay`, `dayTabLabel`.
  - `summary-hours.test.ts`: `summarizeSpots` vult `hours` gesorteerd en zonder `dark` of uren buiten bereik. `today` en `tomorrow` zijn gelijk aan voorheen.
  - `day-timeline.test.ts`:
    - `renders one slot per hour with kind classes`;
    - `aria-hidden`;
    - `sm has no ticks`;
    - `markers only for lg`;
    - `window element with left/width`.
  - `timeline-placements.test.ts`:
    - `list: md for today and sm for tomorrow`: met `summarizeSpots`-fixture; een spot zonder summary heeft geen `.timeline`;
    - `public session: bar with window`, en `evaluations: null` → geen `.timeline`;
    - `quiet hours: bar for 22–07`, geen balk bij uit.
- **AC-7 en AC-8 (verifier, einde Deel B).** Preview-tool, `prefers-color-scheme` geëmuleerd, 375×812, DPR 1 of 2, build met `web/.env` (productie, alleen lezen). Per pagina komt `scrollWidth` in `verification.md`. De B-1-checklist, in deze volgorde, af te vinken in `verification.md`:
  1. `home`, `home-map`, `spot` en `login` uitgelogd fotograferen, vóór Lars inlogt. Op `login` is het plakveld leeg.
  2. Lars logt in via het plakveld. De link en het token komen niet in tekst, log of commit.
  3. Vóór elke ingelogde screenshot (`profiel`, `alerts`, `mijn-sessies`) eval: `document.querySelectorAll('.who').forEach((e) => (e.textContent = 'test@example.com'))`. Daarna controleren dat de header dat toont.
  4. De testsessie heeft organisator "Sanne" en geen echte namen. `sessie` (`/s/[slug]`) wordt in een uitgelogd venster gefotografeerd.
  5. Elke PNG wordt vóór de commit bekeken op e-mailadressen, echte namen en tokens.
  6. Opruimen (N-5): de testsessie annuleren via Mijn sessies en het testaccount verwijderen via Profiel → Account verwijderen. Noteren in `verification.md`.

  AC-8 wordt op de screenshots gecontroleerd:
  - de footer met de bronvermelding;
  - op `home` per spot een rij met een groot label en de balk;
  - op `spot` de dagtabs en de grote balk;
  - op `home-map` de kaartattributie, of de foutmelding zonder key.
- **AC-9.** `NEEDS_LARS`.

## Externe afhankelijkheden
- Geen packages. `web/package.json` blijft ongewijzigd.
- `:where()` heeft altijd specificiteit 0 en is "Widely available" sinds januari 2021. Bron: https://developer.mozilla.org/en-US/docs/Web/CSS/:where. Zelf gecontroleerd op 28-10-2026.
- `forced-color-adjust: none` voorkomt aanpassing in de forced-colors-modus. MDN noemt het "Limited availability". Waar het ontbreekt, is er ook geen forced-colors-modus (bijv. Safari), dus het faalt veilig. Bron: https://developer.mozilla.org/en-US/docs/Web/CSS/forced-color-adjust. Zelf gecontroleerd op 28-10-2026.
- `theme-color` met `media` en de `color-scheme`-meta: overgenomen uit revisie 1. Bronnen: MDN `meta/name/theme-color` en `meta/name/color-scheme`, gecontroleerd op 28-10-2026.
- "Het manifest kent geen media query": overgenomen uit WORK_PACKAGES_V2.
- Svelte 5 `class={[...]}` en `style:`-directive: Svelte `^5.57.2` staat al in `package.json`. Niet opnieuw gecontroleerd. Faalt `npm run check`, dan gebruikt de builder een template-string met dezelfde klassen.
- De iconen zijn inline SVG-paden uit `mockup-b.html` (eigen ontwerp), zonder externe bron of `xmlns`-URL.

## Risico's
- **R1. Krappe paren.** Met de hand berekend, de test beslist. In licht: border-strong op bg ≈3.20, marginal op bg ≈3.65 (niet-tekst), no-go op bg ≈3.85, accent op warning-bg ≈5.35. Faalt een paar, dan past de builder de tint minimaal aan en noteert dat in `deviations.md`.
- **R2. Twijfel en niet gaan lijken op elkaar** in de balk (twee warme middentonen, zoals in de mockup). Dat is acceptabel, want de balk is aanvullend (A10). Lars kan de tokens aanpassen.
- **R3. Dagtabs via CSS (A15).** jsdom laadt geen CSS, dus bestaande tests zien alle dagen. `spot-day-tabs.test.ts` toetst de klasse, en de verifier bekijkt de screenshot.
- **R4. Globale regels en MapLibre.** De basisregels hebben specificiteit 0, en MapLibre wint. De verifier kijkt naar de zoomknoppen.
- **R5. Tabbalk bedekt inhoud.** Daarom `has-tab-bar`-padding op de footer. De verifier scrolt op elke ingelogde pagina tot onderaan.
- **R6. Persoonsgegevens in screenshots.** Opgevangen met de B-1-checklist.
- **R7. Iconen.** De app-iconen houden het oude blauw. Dat lost WP-33 op.
- **R8. `theme-color` met `media`** is niet overal ondersteund. Een browser zonder ondersteuning valt terug op de eerste tag, de lichte.

## Buiten scope
Alles uit "Buiten scope" van WP-34. Daarnaast, als vervolg-WP's:
- **Kitemaat per uur** en een kolom Kite in de uurregels. Dat vraagt profieldata op de spotpagina.
- **Donkere kaartstijl** (A1).
- **Kaartselectie** met een tijdlijnpaneel (gedrag, A14).
- **Tijdlijn op `/sessie/nieuw`.** Die vraagt evaluaties (A14).
- **Eerdere uren van vandaag** in de balk (A9).
- **Nieuwe teksten en presentatie uit de mockup:**
  - de oordeelszin "Go van … tot …" en het blok Wind nu, Richting en Golf;
  - de groepen Favorieten en Alle spots;
  - de uurregels als `<table>`;
  - de stappen "1 Gegevens / 2 Delen";
  - de segmenten Aan/Uit en de dagen in de alertformulieren.
- **Actieve markering in de tabbalk** (A13).
- **Thema-schakelaar** en het overschrijven van MapLibre-CSS.

## Gevolgen voor latere WP's
- **Orchestrator.** Werk WORK_PACKAGES_V2 bij met "Aanpassingen aan de WP-tekst" en de splitsing in WP-34a en WP-34b (A17). Maak vervolg-WP's voor de kitemaat per uur, de donkere kaart, de kaartselectie en de tijdlijn op `/sessie/nieuw`.
- **Alle WP's die `/web` raken (WP-24, WP-29, WP-31, WP-33):**
  - geen kleurwaarden buiten de tokenblokken;
  - een nieuwe kleur wordt een token in beide blokken, plus een paar in `PAIRS`;
  - nieuwe basisregels voor elementen staan in `:where()`;
  - lokale `<style>` alleen voor layout, met tokens.
- **Tijdlijn.** Een nieuwe plek gebruikt `DayTimeline` met een `Timeline` uit `timeline.ts`. `SpotSummary.hours` is beschikbaar voor de lijst en de kaart.
- **WP-33.** `theme_color` en `background_color` zijn `#fbfbfa`, en `theme-color.test.ts` bewaakt dat. Het icoon kan `--color-accent` volgen.

## Stappenplan voor de builder
Elke stap eindigt met `npm run check && npm test` groen.

**Deel A (WP-34a): stijl**
1. **Parser.** Schrijf `test/helpers/tokens.ts` en `tokens.test.ts`.
2. **Tokens.**
   - Zet beide blokken bovenaan `app.css`.
   - Vervang elke hexwaarde in de bestaande regels door een token.
   - Haal de hexwaarden uit `spot/[id]`, `mijn-sessies`, `delen` en `MapView`. `.verdict-none` gaat naar `app.css`, de markerschaduw vervalt, en `currentcolor` in `beheer` wordt `var(--color-border)`.
   - Bouw `contrast.test.ts` om.
3. **Thema-kleur.** `app.html`, het manifest en `theme-color.test.ts`.
4. **Basislaag.**
   - Typografie, links, focus, `:where`-knoppen en -velden, de foutrand, rijen, secties, banners, labels, de oordeelstip, de tabs en de a11y-media.
   - Verwijder de `<style>`-blokken van spot, mijn-sessies, delen en SessionForm.
5. **Layout.** Header-`nav`, tabbalk met iconen, `has-tab-bar`. Schrijf `tab-bar.test.ts`. `layout.test.ts` en `a11y-layout.test.ts` blijven groen.
6. **Lijst, spotpagina en kaart.**
   - `VerdictBadge` met `size` en `verdict-badge.test.ts`.
   - Lijstmarkup zonder balk.
   - Spotpagina: back-link, uurregels, `.go-run`.
   - `MapSwitch` en `MapView`.
7. **Overige pagina's.**
   - Profiel, alerts (met Stille uren), login, mijn-sessies, nieuw, beheer, delen, `/s/[slug]`, `/go`, `/over` en `/privacy`.
   - Controleer elke pagina in de dev-server op 375 px, licht en donker.
8. **Afronding A.**
   - Schrijf `no-external-css.test.ts`.
   - Draai AC-1 volledig.
   - Doe de B-2-controle in de preview en noteer die in `verification.md`.

**Deel B (WP-34b): tijdlijn en dagtabs**

9. **Pure functies.** `lib/timeline.ts` en `timeline.test.ts`.
10. **Samenvattingsuren.** `SummaryHour` en `SpotSummary.hours` in `types.ts`, `summarizeSpots` in `view.ts`, en `summary-hours.test.ts`. `view.test.ts` en `spot-list.test.ts` blijven ongewijzigd groen.
11. **Component.** `DayTimeline.svelte` en `day-timeline.test.ts`.
12. **Lijst.** Twee balken per spot en het lijstdeel van `timeline-placements.test.ts`.
13. **Spotpagina.** `selectedDay`, `activeDay`, tabs, `day-inactive` en de `lg`-balk per dag. Schrijf `spot-day-tabs.test.ts`. `spot-page.test.ts` en `a11y-spot.test.ts` blijven ongewijzigd groen.
14. **Sessie en Stille uren.** `/s/[slug]` en `QuietHoursSettings`, plus de rest van `timeline-placements.test.ts`.
15. **Afronding B.** Draai AC-1 volledig, controleer AC-2 en loop alle pagina's na op 375 px in licht en donker.
16. **Screenshots (verifier).** Volg AC-7 met de B-1-checklist en het opruimen.

## Beslissingen orchestrator (28 oktober 2026)
- A7, A8, A9 en A14: akkoord zoals voorgesteld (de oordeelkleuren getoetst als niet-tekst 3:1, met tekst in de tekstkleur zoals in mockup B; `hours` additief op `SpotSummary`; de balk begint bij het huidige uur; de tijdlijn op 5a en de kaart wordt een vervolg-WP).
- Splitsing: geen aparte WP's. WP-34 blijft één WP met één branch en één PR, maar wordt in twee builderrondes gebouwd: ronde 1 = stappen 1–8 (basis), ronde 2 = stappen 9–16 (tijdlijn, dagtabs, screenshots). De verifier draait na ronde 2. De aanpassingen aan de WP-tekst (AC-2, AC-3, AC-8 en de nieuwe AC-10, AC-11) gaan na goedkeuring in WORK_PACKAGES_V2.
