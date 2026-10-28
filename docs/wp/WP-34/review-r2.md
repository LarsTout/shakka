# Review WP-34, ronde 2
Oordeel: APPROVED

B-1 opgelost: `.who` wordt via eval vervangen en de volgorde is vastgelegd (uitgelogde shots eerst, PNG-controle, opruimen). Het e-mailadres staat in de code alleen in `+layout.svelte:52` en `login:47`, dus de checklist dekt het.
B-2 opgelost: de basisregels staan in `:where()`, `aria-invalid` is per element uitgeschreven, de verifier toetst het met `getComputedStyle`. `.danger` is `type="button"`, dus `button[type=submit]` (0,1,1) overschrijft hem niet.
Gewijzigde secties kloppen: de dagtabs zijn de enige gedragswijziging en hebben `spot-day-tabs.test.ts` (A15 houdt bestaande tests ongewijzigd). Oordeelkleuren worden als niet-tekst op 3:1 getoetst met tekst in de tekstkleur. `hours` is additief, zonder nieuwe query.
Niet-blokkerend: (1) `.hours > li` en `.spot-item` hebben een bovenlijn, en de eerste rij krijgt dan een lijn naast de sectielijn; laat de builder dat visueel controleren. (2) `selectedDay` blijft bij een route-wissel behouden, bewust of niet; één regel in `deviations.md` volstaat.
Geen ESCALATE: geen nieuwe RLS-, grant-, token-, geld- of offshore-raakvlakken.
