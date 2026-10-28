# Afwijkingen WP-34 (ronde 1)

Alle afwijkingen zijn klein; geen raakt een contract, schema of acceptatiecriterium.

- `beheer/+page.svelte`: het hele `<style>`-blok is verwijderd (blueprint: alleen `currentcolor` en min-height weg). De lijstregel staat nu in `app.css` (`.manage-list`, rij met bovenlijn), de knophoogte komt uit de basisknop.
- `.verdict-none::before` krijgt een rand van 1px in `--color-none` bovenop de arcering, zodat de stip zichtbaar blijft; geen schaduw.
- `.spot-list > .spot-item:first-child` heeft geen bovenlijn (review-r2, punt 1). `.hours > li` houdt wel een bovenlijn naast de sectielijn.
- De CSS voor `.day-tabs` en `.day-inactive` staat al in `app.css` (hoort bij de gedeelde tabregel); de markup en `selectedDay` volgen in ronde 2. Wat `selectedDay` bij een route-wissel doet is ronde 2 (review-r2, punt 2).
- `test/a11y-*` en bestaande tests onveranderd; `contrast.test.ts` omgebouwd zoals gepland. Alle `PAIRS` slaagden zonder tintaanpassing.
- Niet gedaan in ronde 1: de dev-server-controle op 375 px (stap 7) en de B-2-controle met `getComputedStyle` (stap 8); er is geen browser/preview beschikbaar voor de builder. Beide gaan naar de verifier.
