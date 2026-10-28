# Verificatie WP-34, ronde 1 (verifier, na builderronde 2)
Resultaat: NEEDS_LARS

Automatisch en op de publieke pagina's is alles groen; geen blokkerende fout gevonden. Wat openblijft is bewust aan Lars gelaten: de ingelogde pagina's (AC-9, AC-7 deels), de kaart met MapTiler-key en de lg-balk met getij en "nu" op echte data (zie "Beperkingen").

| Criterium | Resultaat | Bewijs |
|---|---|---|
| AC-1 | PASS | Met dummy `PUBLIC_SUPABASE_*`: `npm run check` 0 errors/0 warnings; `npm test` 106 files, 1248 tests groen; `npm run build` ok; `verify:build` ok; `npm run size`: initial JS 103.3 kB (budget 150), precache 604.7 kB (budget 900). |
| AC-2 | PASS | `git diff origin/develop...HEAD --name-only` onder `web/src`: alleen `.svelte`, `app.css`, `app.html`, `lib/timeline.ts` (nieuw), `lib/types.ts`, `lib/view.ts`. `types.ts` en `view.ts` zijn additief (`SummaryHour`, optioneel `hours`, één `push` en één `sort`; `today`/`tomorrow` ongewijzigd). In `web/test` is alleen `contrast.test.ts` gewijzigd (M); de rest is nieuw (A). Buiten `web/src`: `manifest.webmanifest` (voorzien). `package.json`, lockfile en `_headers` ongewijzigd. Enige gedragswijziging: dagtabs (AC-10). |
| AC-3 | PASS | `contrast.test.ts` en `tokens.test.ts` groen binnen `npm test` (tokensets gelijk, `PAIRS` per modus, inventaris geen kleurwaarden buiten tokenblokken, alle `var()` gedefinieerd). Geen hexwaarden in `.svelte` (grep leeg). `!important` komt niet voor in `app.css`. |
| AC-4 | PASS | `theme-color.test.ts` groen (twee `theme-color`-tags, `color-scheme`-meta, manifest `#fbfbfa`). |
| AC-5 | PASS | `rg "@import\|@font-face\|fonts\.googleapis\|fonts\.gstatic\|cdn\." web/src web/static` geen treffers; `no-external-css.test.ts` groen; diff van `web/static/_headers` leeg; geen `https://` in enig `web/build/**/*.css`. |
| AC-6 | PASS | Alle `a11y-*.test.ts` groen; `verdict-badge.test.ts` en `tab-bar.test.ts` groen. |
| AC-7 | NEEDS_LARS (deels PASS) | Uitgelogde pagina's gefotografeerd, 375x812 DPR 2, licht en donker, zie "Screenshots". Ingelogde pagina's (`profiel`, `alerts`, `mijn-sessies`) en `sessie` ontbreken bewust: geen testaccount aangemaakt. `scrollWidth` zie tabel hieronder. |
| AC-8 | PASS op publieke pagina's, rest NEEDS_LARS | Footer met Open-Meteo/CC BY 4.0, KNMI, DWD, ECMWF, NOAA, Rijkswaterstaat zichtbaar op `spot` en `login` (licht en donker). `home`: per spot een rij met "Vandaag" (label + stip + tekst) en een dunne balk voor morgen. `spot`: dagtabs en grote balk (morgen, 09-15 uur). `home-map`: foutmelding "De kaart is niet beschikbaar in deze versie van de app" (geen key); de lijst blijft werken. |
| AC-9 | NEEDS_LARS | Visuele keuring van `/alerts`, `/profiel`, `/mijn-sessies`, `/sessie/*`, `/s/[slug]`, tabbalk en Stille uren-balk: ingelogd, door Lars. |
| AC-10 | PASS | `spot-day-tabs.test.ts` groen. Ook in echte Chrome: 8 tabs, standaard "Vandaag" `aria-pressed=true`; klik op "Morgen" geeft `aria-pressed` op Morgen, alleen `dagpaneel-2026-10-29` heeft `display:block`, de andere zeven `none`. |
| AC-11 | PASS (deels visueel NEEDS_LARS) | `timeline.test.ts`, `summary-hours.test.ts`, `day-timeline.test.ts`, `timeline-placements.test.ts` groen. Visueel gezien: lijst (sm-balk morgen, 17 `.timeline`-elementen op `/`) en spotpagina (lg-balk morgen). Niet visueel gezien: md-balk vandaag, getij- en "nu"-markers, `/s/[slug]`, Stille uren. |
| B-2 | PASS (uitgelogd, `/login`) | `getComputedStyle` op `/login`, licht: `button[type=submit]` achtergrond `rgb(3, 105, 161)` = `--color-accent` `#0369a1`; veld rand `rgb(135, 142, 150)` = border-strong `#878e96`, hoogte 44px, font-size 16px; na `aria-invalid="true"` rand `rgb(185, 28, 28)` = `--color-error` `#b91c1c`. `.danger` en MapLibre-zoomknoppen niet toetsbaar zonder login/key: NEEDS_LARS. |

### scrollWidth op 375 px (`document.documentElement.scrollWidth`)
`home`, `home-map`, `spot`, `spot-morgen` en `login`, licht en donker: 375 (alle 10 gevallen, geen horizontale overloop). E1 (lang e-mailadres in header) niet getoetst: uitgelogd.

## Harde regels
- Geen secrets in de diff (grep op key/secret/jwt/service_role leeg). De echte publieke Supabase-waarden zijn alleen als env-variabele aan de dev-server meegegeven; geen `.env` in de worktree aangemaakt.
- Geen client-side Open-Meteo: geen treffers in de web-diff. Geen scraping, geen nieuwe dependency of betaalde dienst.
- Bronvermelding intact (footer, `/spot`).
- Offshore: geen wijziging aan beoordelingslogica; diff raakt alleen weergave en `hours` (kopie van bestaande rijen, geen nieuwe query).
- Geen bestanden buiten scope gewijzigd (`docs/` alleen WP-34-bestanden, `STATUS.md` en `WORK_PACKAGES_V2.md`, in lijn met de orchestratorbeslissing).
- Persoonsgegevens: alle PNG's zijn publieke, uitgelogde pagina's, bekeken: geen e-mailadressen, namen of tokens.

## Screenshots (`docs/wp/WP-34/screens/`)
`home-light/dark`, `home-map-light/dark`, `spot-light/dark`, `spot-morgen-light/dark` (extra, toont de dagtab Morgen met de lg-balk), `login-light/dark`. Uitgelogd, 375 px, DPR 2, `prefers-color-scheme` geemuleerd via CDP. De pagina's zijn full-page (hoogte begrensd op 2400 css-px).

## Beperkingen
- Het was woensdagavond 21:xx: voor vandaag zijn er geen daglichturen meer (E3). Daardoor zie je op `home` geen md-balk voor vandaag, en op `spot` toont "Vandaag" "Geen uren met daglicht". Het gedrag is correct en de logica is unit-getest, maar de md-balk met data is niet visueel gezien.
- Bloemendaal heeft geen getijstation: geen LW/HW-markers.
- Geen `MAPTILER`-key in de omgeving: het kaartbeeld (markers, attributie, MapLibre-knoppen, chip-stijl, `home-map`) toont de foutmelding. Lars moet de echte kaart bekijken.

## Problemen
F-1 (laag, niet blokkerend): volgorde op de spotpagina wijkt af van de blueprint ("Onder de freshness-regel de dagtabs, daarna de knop 'Toon ook donkere uren'"); in `spot/[id]/+page.svelte` staat de knop vóór de dagtabs (zichtbaar in `spot-morgen-light.png`). Niet in `deviations.md` gedocumenteerd. Visueel acceptabel; documenteren of omwisselen.
F-2 (laag, observatie): op `/login` staan label "E-mailadres" en veld naast elkaar op 375 px (labels zijn niet `.form-field`); geen fout, wel afwijkend van de andere formulieren. Lars kan beslissen.
F-3 (info): dagtabs scrollen horizontaal (E9): "zo" wordt op 375 px afgesneden. Dit is het voorziene gedrag.

## Voor Lars
1. Ingelogd bekijken in licht en donker: `/alerts` (met Stille uren-balk), `/profiel` (incl. `.danger` en een ongeldig veld), `/mijn-sessies`, `/sessie/nieuw`, beheer, delen, `/s/[slug]` (omkaderd tijdvak), tabbalk onderaan (ook scrollen tot onderaan: footer niet bedekt), lang e-mailadres in de header op 375 px.
2. Kaart met MapTiler-key: markers, zoomknoppen en `MapSwitch`.
3. De lijst en spotpagina op een dag met daglicht en een spot met getijstation (md-balk, LW/HW, "nu").
