# Afwijkingen WP-23

Alle afwijkingen zijn klein; geen raakt een contract, schema, externe API, dependency of acceptatiecriterium.

1. **Review ronde 2, N-1: `sveltekit:navigation-snapshot` in de inventaris.**
   - Wat: `docs/PRIVACY.md` (browsertabel, `sessionStorage`) noemt nu ook `sveltekit:navigation-snapshot`. Gecontroleerd in `node_modules/@sveltejs/kit/src/runtime/client` (`storage.set(` in `snapshots.js` en `client.js`): drie sleutels, plus `sveltekit:metadata` in `history.state` (geen opslag). `privacy-page.test.ts` toetst de sleutel.
   - Waarom: de inventaris moet volledig zijn. Impact: alleen documentatie en een test.
2. **Review ronde 2, N-2: "op dit apparaat".**
   - Wat: `/privacy` zegt "Dit wordt gewist zodra je op dit apparaat inlogt" in plaats van "zodra je inlogt". Toets 4a in `privacy-page.test.ts` eist daarom `gewist zodra je op dit apparaat inlogt`.
   - Waarom: een magic link kan in een andere browser opengaan; de sleutel wordt dan niet gewist. Impact: één zinsdeel in de tekst die Lars goedkeurt.
3. **Review ronde 2, N-4: spy om de fake storage.**
   - Wat: in `local-prefs.test.ts` toets "geen sleutel" gebruikt `vi.spyOn(s, 'removeItem')` om de bestaande `memory()`-fake. Impact: alleen test.
4. **Bundelmeting: dynamische import in `entry/start` (kit 3).**
   - Wat: `index.html` van de echte build preloadt `chunks/w6MXOQPw.js`, de client-runtime van kit. `entry/start.*.js` laadt die vanuit `init()` met `import(\`...\`)`. Met alleen statische imports meldde de kruiscontrole (A4/N-3) hem als "buiten de afsluiting". De gemeten grootte was al goed (de vereniging telt de preloadbestanden mee).
   - Oplossing: `check-bundle-size.mjs` kent `dynamicImports(code)`. Een preloadbestand telt als verklaard als het in de statische afsluiting zit, of door een bestand in die afsluiting dynamisch wordt geïmporteerd (plus de statische afsluiting daarvan). `initial.files` en de bestandsregels van de blueprint (dynamische imports tellen niet mee in de afsluiting, `lazy.js` niet in `initial`) zijn ongewijzigd; toets 7b (preload van `route.js` buiten de afsluiting) faalt nog steeds. Extra tests in `bundle-size.test.ts`.
   - Impact: interne verfijning van de cross-check; geen contractwijziging. Geen budget aangepast.
5. **Meting.** Gemeten op de echte build (gzip niveau 9): initiële JS 102,4 kB (17 bestanden, budget 150 kB), precache 595,2 kB (60 bestanden, budget 900 kB), MapLibre-chunk 279,5 kB.
6. **`privacy-page.test.ts`: `docs/PRIVACY.md` gelezen via `process.cwd()`.** `new URL(…, import.meta.url)` geeft in de jsdom-omgeving geen file-URL. Voor E19 (contactadres gezet) is een apart bestand `privacy-contact.test.ts` met `vi.mock`, omdat `vi.resetModules` met `vi.doMock` Svelte twee keer laadde. Alleen test.
7. **Axe-resultaten.** Alle 9 `a11y-*`-bestanden slaagden zonder gevonden overtredingen; er waren geen markup- of CSS-fixes nodig. De `AXE_OPTIONS` zijn getypeerd als `RunOptions` (type-check). `a11y-compiler.test.ts` gebruikt `vitePreprocess` voor de TypeScript in de componenten.
8. **Uitvoering.** Docker is niet bereikbaar in deze omgeving: `supabase db reset` en `supabase test db` zijn hier niet gedraaid (ook de CLI ontbreekt). `09_delete_my_account.test.sql` draait in de CI-job `db`.
