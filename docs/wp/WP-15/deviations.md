# Afwijkingen WP-15

De terugval van R2 (`runtime.ts`) was **niet** nodig: de dynamische `import()` met `?worker&url` bouwt, het workerbestand staat in `build/_app/immutable/workers/` en wordt door `vite preview` met 200 geserveerd (net als de MapLibre-chunk en de CSS). Er is dus geen melding aan Lars nodig voor AC-2.

## Klein (genoteerd, doorgegaan)
- **N-1 (review ronde 2): robuustere positieve check in `checkLazyMapLibre`.** De positieve helft zoekt niet op de tekst `maplibre` (die staat ook in `config.ts` en in de page-chunk), maar op een bestand buiten `entry/` dat zowel `setWorkerUrl` als `getWorkerCount` bevat. `getWorkerCount` komt alleen in de echte bibliotheek voor (gecontroleerd op de build: alleen `chunks/CV15SaqY.js`; de page-chunk `nodes/2.*.js` bevat wel `setWorkerUrl`, maar niet `getWorkerCount`). De negatieve helft (entry mag `maplibre` niet bevatten) is ongewijzigd, zodat de letterlijke AC-2-grep klopt. `verify-build.test.ts` heeft een extra geval: een page-chunk die alleen `maplibre.org` en `setWorkerUrl` noemt, telt niet als bibliotheek-chunk.
- **N-3 (review ronde 2): geen actie.** `startMap` heeft geen time-out op `deps.load()`; hangt de chunk-download, dan blijft "Kaart laden…" staan tot de gebruiker op "Lijst" klikt. Bewust zo.
- **`src/env.ts`:** de variabele stond in de eerste commit niet in het bestand (mislukte tekstvervanging); toegevoegd in de commit van stap 5. Vóór die tijd werd `PUBLIC_MAPTILER_KEY` dus niet gevalideerd. Daarna gecontroleerd: `PUBLIC_MAPTILER_KEY='a b' npm run build` faalt met de melding zonder de waarde, en een lege waarde bouwt.
- **N-7:** `$app/env/public` resolvet in vitest niet zonder mock (`globalThis.__sveltekit_dev`). In `spot-list.test.ts` is daarom, zoals in stap 7 voorzien, precies één regel `vi.mock('$app/env/public', () => ({ PUBLIC_MAPTILER_KEY: '' }))` toegevoegd.
- **Fixtures/tests:** `map-view` en `map-switch` gebruiken `waitFor` waar de blueprint "act/tick" noemt. De testbestanden volgen verder het testplan.
- **Rooktest in een browser** (stap 8) is niet uitgevoerd: er is geen browser-automatisering in de repo (geen nieuwe dependency toegevoegd). Wel gecontroleerd met `vite preview` en `curl`: pagina, MapLibre-chunk, CSS en workerbestand geven 200; bij `PUBLIC_MAPTILER_KEY=dummykey12345` bouwt en verifieert de build. Het gedrag bij 401/403 en rastertiles (A2) is gedekt door `map-start.test.ts` en valt onder AC-6.
- RUNBOOK: §11.9 was vrij; geen nummerwijziging.

## NEEDS_LARS
- AC-6: MapTiler-account met twee keys, `PUBLIC_MAPTILER_KEY` in Cloudflare Pages, controle op de gedeployde site (RUNBOOK §11.9), na een week het aantal requests bekijken. Reactie op A3, A5 en A6.
