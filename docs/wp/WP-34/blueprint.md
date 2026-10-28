# Blueprint WP-34: Visueel ontwerp: strak, licht en donker
Status: DRAFT
Revisie: 1

## Doel
Shakka krijgt een strak, licht uiterlijk met één accentkleur zeeblauw, kaarten met een zachte schaduw, een groot go/no-go-label per spot op de lijst en een donkere modus die `prefers-color-scheme` volgt. Wat de app doet en toont blijft gelijk. Contrast blijft in beide modi minstens WCAG AA en wordt getoetst vanuit de tokens in `app.css`. Volledige scope en AC's: `docs/WORK_PACKAGES_V2.md`, sectie WP-34.

## Aannames
- **A1 (Lars bevestigt).** De kaart blijft in de donkere modus licht: `MAPTILER_STYLE_ID` blijft `streets-v4`. Markers en de laadmelding volgen wel de tokens van de actieve modus. Een donkere markerchip op lichte tegels is goed leesbaar.
- **A2 (Lars kan aanpassen).** Zeeblauw is `#0369a1` in licht en `#4fb3e8` in donker. Lars kan elke waarde in de tokentabel wijzigen. `contrast.test.ts` vertelt dan direct of AA nog gehaald wordt.
- **A3 (Lars bevestigt).** De header is licht: wit in de lichte modus en `--color-surface` in de donkere. Het merk "Shakka" staat in accentkleur. `theme-color` volgt `--color-header-bg`, in licht dus `#ffffff`. Wil Lars een blauwe balk, dan zijn er drie wijzigingen:
  - `--color-header-bg` wordt de accentwaarde en `--color-header-text` de waarde van `--color-on-accent` (beide modi);
  - de twee `theme-color`-tags gaan naar dezelfde waarden;
  - `theme_color` in het manifest gaat mee.
  De paren in de test dekken dat al.
- **A4 (reviewer bevestigt).** WP-contract "Elke token staat in `:root` én in het donkere blok" lees ik samen met AC-3 als: elke **kleurtoken** (`--color-*`) plus `--shadow-card` staat in beide blokken. Afstanden, radius en lettergroottes verschillen niet per modus en staan alleen in `:root`.
- **A5.** Naast de tokens uit het contract komen er vijf extra tokens (alleen in `:root`, behalve de kleur):
  - `--color-border-strong`: rand van invoervelden, niet-tekst 3:1;
  - `--content-max`;
  - `--radius-pill`;
  - `--tap` (minimale aanraakmaat);
  - `--font-sans`.
  Het contract noemt de minimale set; extra tokens zijn niet uitgesloten.
- **A6.** `--color-brand` blijft bestaan als alias `var(--color-accent)`, in beide blokken, zodat de sets kleurtokens gelijk zijn.
- **A7.** In de donkere modus zijn de oordeelkleuren lichte tinten met donkere tekst (`--color-on-verdict` wisselt van wit naar bijna-zwart). Daardoor zijn dezelfde tokens ook bruikbaar als tekstkleur op donker (`.notice`, `.notice-ok`, ster, badge "niet geverifieerd").
- **A8.** Het grote label staat alleen op de spotlijst, zoals de WP vraagt. De spotpagina houdt kleine labels per uur, in de nieuwe stijl.
- **A9.** Geen splitsing in WP-34a en WP-34b. Vrijwel alle stijl zit in gedeelde regels in `app.css`, en de pagina's van "34b" krijgen die zonder eigen werk. Splitsen zou twee screenshotrondes en twee keer de tokentest opleveren voor weinig winst.
- **A10 (Lars bevestigt).** Screenshots (AC-7):
  - De publieke pagina's (`home`, `home-map`, `spot`, `login`) komen van een lokale build tegen het productie-Supabase-project. Dat gebeurt alleen-lezend, met de anon-key uit `web/.env`.
  - De ingelogde pagina's (`profiel`, `alerts`, `mijn-sessies`) en `sessie` vragen een testaccount en een testsessie met verzonnen namen. Lars logt één keer in, in de browser van de preview-tool, via het plakveld op `/login`.
  - Is die login er niet, dan zijn die 8 bestanden `NEEDS_LARS`.
  - Geen echt e-mailadres of echte deelnemersnaam in de repo: de repo is openbaar.

## Ontwerp
**Tokens.** Bovenaan `app.css` komen precies twee tokenblokken: een `:root { … }` (licht, met `color-scheme: light dark`) en een `@media (prefers-color-scheme: dark) { :root { … } }` (donker). Alleen daar staan kleurwaarden (hex, en `rgb()` in de schaduw). Alle andere regels in `app.css` en alle `<style>`-blokken in `.svelte` gebruiken `var(--…)`, `currentcolor`, `transparent`, `inherit` of systeemkleuren in `forced-colors`. Zo past een nieuwe tint zich op één plek aan en kan de test de paren rechtstreeks uit de CSS lezen.

**Gedeelde componentklassen in plaats van stijl per pagina.** De pagina's krijgen hun uiterlijk via elementregels en een kleine set gedeelde klassen in `app.css`:
- elementen: `h1`–`h3`, `a`, `button`, `input`, `select`, `textarea`, `fieldset`, `legend`, `details`/`summary`;
- klassen: kaart, banner, badge, primaire en danger-knop.

De lokale `<style>`-blokken met alleen knopmaten of hexkleuren verdwijnen. Daardoor gaan velden die WP-30 aan `/alerts` of `/profiel` toevoegt (tijdkeuzes, "Uit", een sectie "Stille uren") vanzelf mee:
- een `<section>` direct in `<main>` wordt een kaart;
- een `fieldset` wordt een groep;
- `input`/`select` krijgen de veldstijl;
- de opslaanknop (`type="submit"`) wordt primair.

**Kaarten.** De kaartstijl hangt aan één selectorlijst: `.card`, `main > section:not(.map-wrap)`, `main > form`, `.spot-item` en `.login-prompt`. Elke kaart krijgt:
- een witte (licht) of donkere (donker) achtergrond;
- een rand van 1 px;
- `--radius-lg` en `--shadow-card`.

`.card` is de expliciete uitwijk voor gevallen die niet direct in `main` staan.

**Header zonder JavaScript-menu.** De markup van `+layout.svelte` blijft gelijk. `.site-header` en de `nav` worden `flex-wrap`, met de volgende regels:
- Uitgelogd passen merk, "Over" en "Inloggen" op één regel.
- Ingelogd valt de `nav` onder het merk. De vier links passen op 343 px.
- `.who` heeft `flex: 1 1 8rem; min-width: 0` met ellipsis. Daardoor schuiven e-mail en "Uitloggen" samen naar de volgende regel, en wordt een lang adres afgekapt in plaats van dat de pagina overloopt.
- Elk navigatiedoel en elke knop is minstens `--tap` (2.75rem = 44 px) hoog.
- Header, `main` en footer lijnen uit op `--content-max` via `padding-inline: max(var(--space-4), calc((100% - var(--content-max)) / 2 + var(--space-4)))`. De `env(safe-area-inset-*)`-marges vangen de notch op, want `viewport-fit=cover` staat al aan.

**Spotlijst.**
- Elke `.spot-item` is een kaart. Het lijstje krijgt `display: grid` met `gap: var(--space-3)`.
- Bovenaan staat een `.spot-head`, een grid met twee kolommen: links `.spot-title` (naam groot en vet, " · regio" gedempt, badge "niet geverifieerd"), rechts de ster.
- Vandaag wordt `<p class="day-summary day-today">`. Daarin staat `<span class="day-label">Vandaag:</span>` op een eigen regel (klein, gedempt), daaronder `VerdictBadge size="lg"` naast `<span class="day-text">`.
- Morgen staat compact op één regel met het kleine label.
- De tekstinhoud en de volgorde van de tekst blijven gelijk, zodat `spot-list.test.ts` ongewijzigd groen blijft.

**Spotpagina en kaart.**
- Spotpagina:
  - Elke dag (`section.day`), het spotprofiel en de bronnen worden kaarten.
  - Uurregels krijgen een scheidingslijn op `li` (niet meer op `.hour`) en `tabular-nums` voor de tijd.
  - `.go-run` is een knop in `--color-go` met `--color-on-verdict`.
- Kaartweergave:
  - `MapSwitch` wordt een gesegmenteerde schakelaar: een spoor in `--color-surface-muted`, en de ingedrukte knop in accent met `--color-on-accent`. De toestand is dus niet alleen vet; het paar accent op surface-muted is 3:1 of meer.
  - `MapView` krijgt een afgeronde, omlijnde container. De laadmelding gebruikt surface-muted, de markers de surface-, tekst- en randtokens. `.verdict-none` verhuist naar `app.css`.
- De globale knopstijl slaat de MapLibre-bedieningsknoppen over via `button:not(.map-canvas button)`.

**Toegankelijkheid.**
- Focusring: `:focus-visible { outline: 3px solid var(--color-focus); outline-offset: 2px }`. De witte override in de header vervalt, want de header is nu licht.
- Links in lopende tekst houden hun onderstreping. Alleen navigatie, merk, spotnaam en knop-links verliezen die.
- Transities (alleen `background-color`, 120 ms) staan binnen `@media (prefers-reduced-motion: no-preference)`.
- In `@media (forced-colors: active)` krijgen `.verdict`, knoppen en knop-links `border: 1px solid CanvasText`, zodat ze zichtbaar blijven als achtergronden wegvallen.
- Invoervelden krijgen `font-size: 1rem`, zodat iOS niet inzoomt.
- Elk oordeel blijft tekst (`verdictLabel`).

**Thema-kleur.** `app.html` krijgt `<meta name="color-scheme" content="light dark">`, zodat de eerste paint al donker is, plus twee `theme-color`-tags, licht eerst. Een browser zonder `media`-ondersteuning neemt zo de lichte waarde. Het manifest gaat naar de lichte waarden.

**Contrasttest.** `contrast.test.ts` leest beide tokenblokken via `readTokens` en toetst `PAIRS` als tokenparen in beide modi. De inventaris toetst vier dingen:
- geen kleurwaarden buiten de tokenblokken;
- elke gebruikte `var(--x)` bestaat;
- de sets kleurtokens zijn gelijk;
- elke kleurtoken zit in een paar of in `DECORATIVE`.

### Niet-CSS-wijzigingen
Alle wijzigingen in `web/src` zitten in `.svelte`, `app.css` of `app.html` (AC-2). Markup verandert alleen hier, zonder gedrag, route of tekst te veranderen:
1. `VerdictBadge.svelte`: optionele prop `size` (zie Contracten). De exportsignatuur wordt alleen uitgebreid; bestaande aanroepen blijven geldig.
2. `routes/+page.svelte`: de wrappers `.spot-head`/`.spot-title`, de klasse `day-today` en de spans `day-label`/`day-text`, plus `size="lg"`. De ster staat nu na de regio en de badge in de DOM. De tabvolgorde verandert niet (link, dan ster), want regio en badge zijn niet focusbaar.
3. Buiten `web/src`:
   - `web/static/manifest.webmanifest` (twee kleuren);
   - `web/test/contrast.test.ts` (omgebouwd, toegestaan);
   - nieuwe tests en `web/test/helpers/tokens.ts`.
   Bestaande tests veranderen verder niet.

## Bestanden
| Bestand | Actie | Inhoud |
|---|---|---|
| `web/src/app.css` | wijzigen | Volledig herschreven: twee tokenblokken, basis (typografie, links, focus), header/footer, knoppen, formulieren, kaarten, banners, badges, lijst, spotpagina, sessies, a11y-media. |
| `web/src/app.html` | wijzigen | `color-scheme`-meta en twee `theme-color`-tags in plaats van één. |
| `web/static/manifest.webmanifest` | wijzigen | `theme_color` `#ffffff`, `background_color` `#f5f7fa`. |
| `web/src/lib/components/VerdictBadge.svelte` | wijzigen | Prop `size?: 'sm' \| 'lg'`, klasse `verdict-lg`. |
| `web/src/routes/+page.svelte` | wijzigen | Kaartmarkup zoals in Ontwerp; groot label vandaag. |
| `web/src/routes/+layout.svelte` | ongewijzigd | Alleen CSS-gestuurd (genoemd omdat de header verandert). |
| `web/src/routes/spot/[id]/+page.svelte` | wijzigen | `<style>`-blok weg (`.go-run`/`.go-runs` naar `app.css`). |
| `web/src/routes/mijn-sessies/+page.svelte` | wijzigen | `<style>`-blok weg (`.share-button` en `.my-session` naar `app.css`). |
| `web/src/routes/sessie/[slug]/delen/+page.svelte` | wijzigen | `<style>`-blok weg (`.share-actions`, `.share-button` naar `app.css`). |
| `web/src/routes/sessie/[slug]/beheer/+page.svelte` | wijzigen | `<style>`: `currentcolor` wordt `var(--color-border)`, de min-height-regel vervalt. |
| `web/src/lib/components/SessionForm.svelte` | wijzigen | `<style>`-blok weg (dekt de basisknop). |
| `web/src/lib/components/MapSwitch.svelte` | wijzigen | `<style>`: gesegmenteerde schakelaar met tokens. |
| `web/src/lib/components/MapView.svelte` | wijzigen | `<style>`: tokens, afgeronde container, `.verdict-none` eruit. |
| `web/test/helpers/tokens.ts` | aanmaken | `readTokens`, `stripTokenBlocks`. |
| `web/test/tokens.test.ts` | aanmaken | Parsertests op een inline CSS-fixture. |
| `web/test/contrast.test.ts` | wijzigen | Tokenparen per modus plus inventaris. |
| `web/test/theme-color.test.ts` | aanmaken | AC-4. |
| `web/test/verdict-badge.test.ts` | aanmaken | AC-6. |
| `web/test/no-external-css.test.ts` | aanmaken | AC-5 (bronbestanden). |
| `docs/wp/WP-34/screens/*.png` | aanmaken (verifier) | 16 screenshots (AC-7). |

## Interfaces en contracten

### Tokenblokken in `app.css` (letterlijk deze structuur)
```css
/* Design tokens (WP-34). Colour values only in these two blocks. */
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
Elk blok komt precies één keer voor, en er is geen ander `:root`-blok. Het donkere blok staat direct na het lichte.

### Kleurtokens (in beide blokken)
| Token | Licht | Donker | Gebruik |
|---|---|---|---|
| `--color-bg` | `#f5f7fa` | `#0f141a` | paginaachtergrond |
| `--color-surface` | `#ffffff` | `#182029` | kaarten, velden, secundaire knop |
| `--color-surface-muted` | `#eef2f6` | `#222b36` | hover, spoor van de schakelaar, laadmelding van de kaart |
| `--color-text` | `#111827` | `#e6edf3` | tekst |
| `--color-muted` | `#4b5563` | `#9aa7b4` | gedempte tekst, hints, footer |
| `--color-border` | `#e3e8ee` | `#2c3743` | scheidingslijnen, kaartrand (decoratief) |
| `--color-border-strong` | `#7b8594` | `#6b7888` | rand van invoervelden en secundaire knoppen |
| `--color-accent` | `#0369a1` | `#4fb3e8` | links, merk, primaire knop, ingedrukte schakelaar |
| `--color-brand` | `var(--color-accent)` | `var(--color-accent)` | alias (A6) |
| `--color-on-accent` | `#ffffff` | `#0b1220` | tekst op accent |
| `--color-focus` | `#0369a1` | `#4fb3e8` | focusring |
| `--color-header-bg` | `#ffffff` | `#182029` | header; gelijk aan `theme-color` |
| `--color-header-text` | `#111827` | `#e6edf3` | headerlinks, e-mail |
| `--color-go` | `#15803d` | `#4ade80` | label go, knop "Ik ga", `.notice-ok` |
| `--color-marginal` | `#a16207` | `#facc15` | label twijfel, `.notice`, ster, badge "niet geverifieerd", bannerrand |
| `--color-no-go` | `#b91c1c` | `#f87171` | label niet gaan |
| `--color-none` | `#4b5563` | `#9aa7b4` | marker zonder oordeel |
| `--color-on-verdict` | `#ffffff` | `#0b1220` | tekst op oordeelkleuren en op de danger-knop |
| `--color-error` | `#b91c1c` | `#f87171` | fouttekst, `aria-invalid`-rand, danger-knop |
| `--color-warning-bg` | `#fef2f2` | `#3a1d1f` | `.banner.warning` |
| `--color-notice-bg` | `#fef6e7` | `#33290f` | `.banner` |

`--shadow-card`, in beide blokken:
- licht: `0 1px 2px rgb(15 23 42 / 0.06), 0 2px 6px rgb(15 23 42 / 0.08)`;
- donker: `0 1px 2px rgb(0 0 0 / 0.5)`.

### Overige tokens (alleen `:root`)
| Token | Waarde |
|---|---|
| `--font-sans` | `system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif` |
| `--font-size-sm` / `-base` / `-lg` / `-xl` / `-verdict` | `0.875rem` / `1rem` / `1.25rem` / `1.75rem` / `1.5rem` |
| `--space-1` … `--space-6` | `0.25rem`, `0.5rem`, `0.75rem`, `1rem`, `1.5rem`, `2rem` |
| `--radius` / `--radius-lg` / `--radius-pill` | `0.5rem` / `0.875rem` / `999px` |
| `--tap` | `2.75rem` |
| `--content-max` | `40rem` |

Typografie:
- `body`: `--font-size-base`, `line-height: 1.5`;
- `h1`: `--font-size-xl`, gewicht 800, `letter-spacing: -0.02em`, `line-height: 1.2`;
- `h2`: `--font-size-lg`, gewicht 700;
- `h3`: base, gewicht 700;
- `.compact`, `.hint`, `.site-footer`, `.badge-unverified`, `.verdict`: `--font-size-sm`.

### Gedeelde klassen (in `app.css`)
- **Kaart**: `.card, main > section:not(.map-wrap), main > form, .spot-item, .login-prompt`. Elke kaart krijgt:
  - `background: var(--color-surface)`, `border: 1px solid var(--color-border)`;
  - `border-radius: var(--radius-lg)`, `box-shadow: var(--shadow-card)`;
  - `padding: var(--space-4)`, `margin: 0 0 var(--space-3)`.
  Het eerste en laatste kind van een kaart krijgen `margin-block` 0 aan de buitenkant.
- **Knoppen**:
  - Basis `button:not(.map-canvas button)`: `font: inherit`, gewicht 600, `min-height: var(--tap)`, `padding: var(--space-2) var(--space-4)`, `--radius`, rand `--color-border-strong`, achtergrond `--color-surface`, tekst `--color-text`. Hover gebruikt `--color-surface-muted`. `:disabled` krijgt `opacity: 0.55`.
  - Primair: `button[type='submit'], .share-button` met accent en on-accent.
  - `.go-run`: go met on-verdict.
  - `.danger`: error met on-verdict.
  - Knop-links (`.share-button`, `.go-run`) krijgen `display: inline-flex`, `min-height: var(--tap)` en `text-decoration: none`.
  - `.favorite-star` en `.site-header button` overschrijven de achtergrond en de rand.
- **Velden**: `input:not([type='checkbox']):not([type='radio']), select, textarea`:
  - `font: inherit; font-size: 1rem`, `min-height: var(--tap)`, `box-sizing: border-box`, `max-width: 100%`;
  - rand `--color-border-strong`, achtergrond surface, tekst text.
  - In `.form-field` krijgen ze `width: 100%`.
  - `[aria-invalid='true']` krijgt rand `--color-error`.
  - Checkbox en radio krijgen `accent-color: var(--color-accent)` en 1.25rem.
- **Groep**: `fieldset` met rand `--color-border`, `--radius`, transparante achtergrond. `legend` gewicht 600.
- **Banner**: `.banner` met notice-bg en `border-left: 4px solid var(--color-marginal)`. `.banner.warning` met warning-bg en `border-left-color: var(--color-error)`.
- **Oordeel**:
  - `.verdict`: inline-flex, pill, gewicht 700, kleur `--color-on-verdict`.
  - `.verdict-go`, `-marginal`, `-no_go` en `-none` krijgen achtergrond `--color-<oordeel>`.
  - `.verdict-lg`: `font-size: var(--font-size-verdict)`, gewicht 800, `padding: var(--space-2) var(--space-4)`, `--radius-lg`, `min-width: 6.5rem`, gecentreerd.

### `VerdictBadge.svelte`
```ts
let { verdict, size = 'sm' }: { verdict: Verdict; size?: 'sm' | 'lg' } = $props();
```
```svelte
<span class={['verdict', `verdict-${verdict}`, size === 'lg' && 'verdict-lg']} data-verdict={verdict}>{verdictLabel(verdict)}</span>
```

### DOM-haken (ongewijzigd)
`data-spot`, `data-verdict`, `.spot-list`, `.spot-item`, `.spot-link`, `.skip-link`, `#main`, `.site-header`, `.day-summary`, `.map-marker*`, `.prewrap` en alle bestaande `id`'s en `aria-*`.

### `app.html` (vervangt regel 8)
```html
<meta name="color-scheme" content="light dark" />
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#182029" media="(prefers-color-scheme: dark)" />
```

### Manifest
`"background_color": "#f5f7fa"` (= licht `--color-bg`), `"theme_color": "#ffffff"` (= licht `--color-header-bg`). De rest blijft ongewijzigd.

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

### `PAIRS` in `contrast.test.ts`
De vorm is `[voorgrond, achtergrond, minimum, waar]`, met tokennamen, en elk paar wordt getoetst in `light` en `dark`. `TEXT = 4.5`, `NON_TEXT = 3`.

| Voorgrond | Achtergronden | Min |
|---|---|---|
| `--color-text` | bg, surface, surface-muted, warning-bg, notice-bg | 4.5 |
| `--color-muted` | bg, surface, surface-muted, warning-bg, notice-bg | 4.5 |
| `--color-accent` | bg, surface, header-bg | 4.5 |
| `--color-on-accent` | accent | 4.5 |
| `--color-header-text` | header-bg | 4.5 |
| `--color-on-verdict` | go, marginal, no-go, none, error | 4.5 |
| `--color-error` | bg, surface, warning-bg | 4.5 |
| `--color-marginal` | bg, surface, notice-bg | 4.5 |
| `--color-go` | bg, surface | 4.5 |
| `--color-focus` | bg, surface, header-bg | 3 |
| `--color-border-strong` | bg, surface | 3 |
| `--color-error` (rand `aria-invalid`) | surface | 3 |
| `--color-accent` (ingedrukte schakelaar) | surface-muted | 3 |
| `--color-marginal` (ster) | surface | 3 |

`DECORATIVE = { '--color-border': 'scheidingslijnen en kaartrand', '--color-brand': 'alias van accent' }`.

## Edge cases
- **E1.** Lang e-mailadres op 375 px → `.who` breekt af met ellipsis. `scrollWidth` blijft 375 of minder.
- **E2.** Uitgelogd → merk, "Over" en "Inloggen" op één regel. Is de auth onbekend (`undefined`), dan alleen merk en "Over".
- **E3.** `summary.today.best` is `null` → geen groot label. "Vandaag:" en de dagtekst staan er wel; het grid laat geen gat.
- **E4.** Spot zonder summary → kaart met kop en "Nog geen data", zonder labelregel.
- **E5.** Lange spotnaam of regio → `overflow-wrap: anywhere` op `.spot-title`. De ster blijft rechts in zijn eigen kolom.
- **E6.** Donkere modus met kaart → lichte tegels, donkere markerchips met de oordeelkleuren van donker. De MapLibre-knoppen houden hun eigen stijl (A1).
- **E7.** Browser zonder `media` op `theme-color` → neemt de eerste tag, de lichte waarde.
- **E8.** `forced-colors: active` → labels en knoppen houden een rand in `CanvasText`, en de tekst blijft.
- **E9.** Tekst op 200 % → alles in rem. Header, kaartkop en dagregel lopen door `flex-wrap`/grid op meer regels in plaats van te overlopen.
- **E10.** WP-30 voegt `<input type="time">`/`<select>` en een sectie toe → die krijgen automatisch de veld-, groep- en kaartstijl. `color-scheme` maakt de native picker donker in de donkere modus.
- **E11.** Een `<section>` die niet direct in `main` staat (bijv. in een `div`) → geen kaart. De builder gebruikt dan `.card` en noemt dat in de commit.
- **E12.** `prefers-reduced-motion: reduce` → geen transities.
- **E13.** iPhone in standalone met notch → header en `main` houden `env(safe-area-inset-*)` als minimale marge aan.

## Testplan
Alle webtests draaien in `npm test` (vitest, jsdom of `@vitest-environment node`).

- **AC-1.**
  - `npm run check && npm test && npm run build && npm run verify:build && npm run size`: de bestaande suite, de build, de buildcontrole en het precachebudget slagen.
- **AC-2.**
  - Verifier: `git diff develop...wp/WP-34 --name-only -- web/src` toont alleen `.svelte`, `app.css` en `app.html`.
  - Verifier: `git diff develop...wp/WP-34 -- web/test` raakt alleen `contrast.test.ts` en nieuwe bestanden.
  - De markupwijzigingen staan onder "Niet-CSS-wijzigingen".
- **AC-3.**
  - `tokens.test.ts › reads light and dark blocks`: een inline fixture met beide blokken geeft de juiste sets. `#FFF` wordt `#ffffff`, en commentaar wordt genegeerd.
  - `tokens.test.ts › resolves var() in mode, then light`: `--color-brand: var(--color-accent)` lost per modus op.
  - `tokens.test.ts › throws without dark block / with two light blocks`: de parser weigert een afwijkende structuur.
  - `contrast.test.ts › contrast helpers`: ongewijzigd (referentiewaarden).
  - `contrast.test.ts › colour token sets are equal`: de `--color-*`-namen van licht en donker zijn gelijk, en `--shadow-card` staat in beide.
  - `contrast.test.ts › pairs (%s mode)`, `it.each` over `PAIRS` × `['light','dark']`: elk paar haalt zijn minimum. Fixture is `src/app.css`.
  - `contrast.test.ts › every colour token is in PAIRS or DECORATIVE`.
  - `contrast.test.ts › no colour values outside the token blocks`: geen treffer op `/#(?:[0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})\b|rgba?\(|hsla?\(/i` in `.svelte`-bestanden of in `stripTokenBlocks(app.css)`.
  - `contrast.test.ts › every var() used in src is defined`: elke `var(--x)` in `src/**/*.{svelte,css}` staat in de lichte set.
- **AC-4.**
  - `theme-color.test.ts › two theme-color tags`: precies twee tags. De tag met `media="(prefers-color-scheme: light)"` is gelijk aan licht `--color-header-bg`, die met `dark` aan donker.
  - `theme-color.test.ts › color-scheme meta`: `content="light dark"` is aanwezig.
  - `theme-color.test.ts › manifest`: `theme_color` is gelijk aan licht `--color-header-bg` en `background_color` aan licht `--color-bg`.
- **AC-5.**
  - `no-external-css.test.ts › no external CSS sources`: geen `@import`, `@font-face`, `fonts.googleapis`, `fonts.gstatic` of `url(http` in `src/**/*.{css,svelte,html}` en `static/**/*.css`.
  - Verifier: `git diff develop...wp/WP-34 -- web/static/_headers` is leeg, en `rg -l "https://" web/build -g "*.css"` geeft niets. Een treffer uit `maplibre-gl.css` die al op `develop` bestond, noteert de verifier als bestaand en niet als regressie.
- **AC-6.**
  - Bestaande `a11y-*.test.ts` blijven groen.
  - `verdict-badge.test.ts › lg`: `size="lg"` geeft de klassen `verdict`, `verdict-go` en `verdict-lg`, `data-verdict="go"` en de tekst `verdictLabel('go')`.
  - `verdict-badge.test.ts › default`: zonder `size` is er geen `verdict-lg`.
- **AC-7 en AC-8.** Verifier, met de preview-tool, `prefers-color-scheme` geëmuleerd, 375×812, DPR 1 of 2.
  - Bron: `cd web && npm run build && npm run preview` met `web/.env` (productie, alleen lezen).
  - Ingelogde pagina's en `sessie` alleen met een testaccount en een testsessie (A10).
  - Per pagina komt `document.documentElement.scrollWidth` in `verification.md`.
  - AC-8 wordt op de screenshots gecontroleerd: footer met de bronvermelding, groot label per spotkaart, kaartattributie als de kaart laadt. Zonder toegestane origin voor de MapTiler-key toont `home-map` de foutmelding; dat is toegestaan.
- **AC-9.** `NEEDS_LARS`.

## Externe afhankelijkheden
- Geen packages. `web/package.json` blijft ongewijzigd.
- `<meta name="theme-color" media="…">`: `media` is optioneel, en de kleur geldt alleen als de query matcht. MDN noemt het "Limited availability" (geen Baseline). Bron: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/meta/name/theme-color. Zelf gecontroleerd op 28-10-2026.
- `<meta name="color-scheme" content="light dark">`: de eerste waarde heeft de voorkeur, de tweede is toegestaan. Het werkt op documentniveau, net als de CSS-eigenschap `color-scheme`. Bron: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/meta/name/color-scheme. Zelf gecontroleerd op 28-10-2026.
- "Het manifest kent geen media query" (voor `theme_color`): overgenomen uit WORK_PACKAGES_V2, WP-34.
- Svelte 5 `class={[...]}` (clsx-vorm): Svelte `^5.57.2` staat al in `package.json`. De vorm bestaat sinds 5.16; dat is niet opnieuw gecontroleerd. Faalt `npm run check`, dan gebruikt de builder een template-string met dezelfde klassen.

## Risico's
- **R1. Rekenfout in het palet.** De verhoudingen zijn met de hand berekend. De krapste zijn marginal op bg (≈4.59), marginal op notice-bg (≈4.58) en go op bg (≈4.67), alle drie in licht. De test beslist. Faalt een paar, dan maakt de builder de voorgrond minimaal donkerder (licht) of lichter (donker) en noteert dat in `deviations.md`.
- **R2. Selector `main > section`.** De kaartstijl hangt aan de DOM-structuur. Een latere wrapper haalt de kaartstijl weg; dat is zichtbaar, maar niet kapot (E11).
- **R3. Globale element-stijlen raken MapLibre-elementen.** Dat geldt voor `a`, `:focus-visible` en `button`:
  - de knoppen sluit `:not(.map-canvas button)` uit;
  - links en focus in de kaart houden de specifiekere MapLibre-CSS.
  De verifier kijkt in de `home-map`-screenshot naar de zoomknoppen. Er is bewust geen globale `box-sizing`-reset.
- **R4. `theme-color` met `media`** is niet overal ondersteund. Het terugvalgedrag is acceptabel (E7).
- **R5. Persoonsgegevens in screenshots** in een openbare repo. Alleen een testaccount en verzonnen namen (A10). De verifier controleert dat vóór de commit.
- **R6. Kleuren in het icoon.** De placeholder-iconen houden het oude blauw (`#0b5e8a`). Dat lost WP-33 op, buiten scope.

## Buiten scope
Alles uit "Buiten scope" van WP-34 in WORK_PACKAGES_V2. Daarnaast:
- een groot label op de spotpagina (A8);
- `aria-current` of een actieve-linkstijl in de navigatie (dat is gedrag);
- een "stretched link" waarbij de hele spotkaart klikbaar wordt (dat is gedrag);
- de oordeelkleuren in de kaartmarkers apart afstemmen op lichte tegels in de donkere modus;
- MapLibre-CSS overschrijven.

## Gevolgen voor latere WP's
- **Alle WP's die `/web` raken (WP-24, WP-29, WP-31, WP-33):**
  - geen hex-, `rgb()`- of `hsl()`-kleuren meer in `.svelte` of buiten de tokenblokken; `contrast.test.ts` faalt anders;
  - een nieuwe kleur wordt een token in beide blokken, plus een paar in `PAIRS`;
  - een nieuwe sectie direct in `main` is automatisch een kaart, en submitknoppen zijn automatisch primair;
  - lokale `<style>`-blokken alleen voor layout, met tokens.
- **WP-30**, als die na WP-34 wordt gemerged in plaats van ervoor: de nieuwe velden hebben geen eigen styling nodig. Een eigen `<style>` met kleuren laat `contrast.test.ts` falen.
- **WP-33:** het nieuwe icoon kan `--color-accent` (`#0369a1`) volgen. `theme_color` en `background_color` in het manifest staan nu op de lichte tokenwaarden, en `theme-color.test.ts` bewaakt dat.
- **Vervolg-WP (optioneel):** een donkere MapTiler-stijl (A1). Daarvoor zijn een tweede `MAPTILER_STYLE_ID`, een keuze op `matchMedia` en een herziening van de markerkleuren nodig.

## Stappenplan voor de builder
1. **Parser.**
   - Schrijf `web/test/helpers/tokens.ts` en `tokens.test.ts`.
   - Controle: `npm test -- tokens` is groen.
2. **Tokens en contrasttest.**
   - Zet de twee tokenblokken bovenaan `app.css`.
   - Vervang elke hexwaarde in de bestaande regels van `app.css` door de passende token.
   - Haal de hexwaarden uit de vier `.svelte`-bestanden: `spot/[id]`, `mijn-sessies`, `delen` en `MapView`. `.verdict-none` gaat naar `app.css`, `currentcolor` in `beheer` wordt `var(--color-border)`.
   - Bouw `contrast.test.ts` om.
   - Controle: `npm test` is groen.
3. **Thema-kleur.**
   - Pas `app.html` en het manifest aan en schrijf `theme-color.test.ts`.
   - Controle: `npm test` is groen.
4. **Basislaag in `app.css`.**
   - Typografie, links, focus, knoppen, velden, fieldset, details, kaartselector, banners, badges, header/footer-layout met safe-area, en de media-blokken voor reduced motion en forced colors.
   - Verwijder de overbodige `<style>`-blokken: spot, mijn-sessies, delen, SessionForm.
   - Controle: `npm run check && npm test` is groen.
5. **Spotlijst.**
   - Breid `VerdictBadge` uit (`size`) en schrijf `verdict-badge.test.ts`.
   - Pas de markup in `routes/+page.svelte` aan en voeg de lijst- en kaartstijlen toe.
   - Controle: `npm test` is groen, inclusief `spot-list.test.ts` en `a11y-home.test.ts`.
6. **Spotpagina en kaart.**
   - Spotpagina: dagkaarten, uurregels en `.go-run`.
   - `MapSwitch` als segmentschakelaar; container en markers van `MapView`.
   - Controle: `npm test` is groen.
7. **Overige pagina's.**
   - Profiel, alerts, login, mijn-sessies, nieuw, beheer, delen, `/s/[slug]`, `/go`, `/over`, `/privacy`.
   - Alleen gedeelde regels; een lokale `<style>` alleen voor layout, met tokens.
   - Controleer elke pagina in de dev-server op 375 px, licht en donker.
   - Controle: `npm test` is groen.
8. **Afronding.**
   - Schrijf `no-external-css.test.ts`.
   - Draai `npm run check && npm test && npm run build && npm run verify:build && npm run size`.
   - Controleer `git diff develop... --name-only -- web/src` (AC-2).
9. **Screenshots (verifier).**
   - De 16 screenshots volgens het testplan AC-7, met de `scrollWidth`-waarden in `verification.md`.
