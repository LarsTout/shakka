## WP-15: Kaart

- Wissel lijst ↔ kaart op `/` (`MapSwitch`, `MapView`); markers met het oordeel van vandaag (na zonsondergang "Morgen: …"), gestippelde rand voor niet-geverifieerde spots; tik opent de spotpagina.
- MapLibre GL als npm-bundel (geen CDN, geen MapTiler-SDK/telemetrie), uitsluitend lui geladen via `import()` in `platform.ts` na een klik; `checkLazyMapLibre` in `verify:build` bewaakt dat MapLibre buiten de entry-chunks blijft. De `?worker&url`-terugval was niet nodig.
- `PUBLIC_MAPTILER_KEY` optioneel; zonder key, zonder WebGL2 of bij een laadfout blijft de lijst bruikbaar met een Nederlandse melding. Attributie MapTiler/OSM/MapLibre altijd uitgeklapt + logo.
- 492 web-tests, check 0 fouten, build/verify/guard groen; CI groen.

**Verificatie:** AC-1..5 PASS. AC-6 (echte key, gedeployde site) doet Lars: MapTiler-account met twee keys (productie: alleen Pages-domein; lokaal: aparte key in `web/.env`), `PUBLIC_MAPTILER_KEY` in Cloudflare Pages.

**Voor Lars:** A3 (stijl `streets-v4`), A5 (keuze niet onthouden), A6 (markerinhoud).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
