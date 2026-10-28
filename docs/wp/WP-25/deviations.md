# Afwijkingen en notities WP-25

## Notities (geen afwijking van de blueprint)
- N-4 (review): `RsvpPanel.serverClosed` wordt nooit gereset. Na een geweigerde aanmelding terwijl het aanmelden gesloten was, blijft het formulier weg als de organisator heropent, tot de bezoeker de pagina herlaadt. Gedrag is acceptabel; het staat als comment bij `serverClosed` in `RsvpPanel.svelte`.
- N-1 (review): `manage-page.test.ts` en het a11y-geval zetten de klok vast op `NOW_SESSIONS` (2026-07-15), zodat de schakelaar (A8) zichtbaar is.
- N-3 (review): de alter-guard in `session-schema.test.ts` maakt het woord `column` optioneel en matcht per komma-gescheiden clausule.

## Kleine afwijkingen
- `supabase test db` (pgTAP) is lokaal niet gedraaid: Docker draaide niet (A11). Het bewijs komt uit de CI-job `db`.
- `session-page-data.test.ts` en `a11y-session-pages.test.ts`: de `#lib/supabase.js`-mock kreeg een `rpc` (`createFakeRpc`) erbij, nodig voor `loadManagePage`.
