# Afwijkingen WP-18

Geen afwijking raakt een contract, schema, externe API, dependency of acceptatiecriterium.

## Uit review ronde 2 (overgenomen)
- **N-1.** `login.test.ts`, geval 7 (Check je mail, standalone): zoekt op de alinea met "We hebben een inloglink gestuurd naar" en toetst daarin op "kopieer hem en plak hem hieronder bij ‘Inloglink plakken’". Zo geeft de hint in de plaksectie geen tweede treffer.
- **N-2.** `layout.test.ts`: `mocks.signOut.mockReturnValueOnce(...)` in plaats van `mockReturnValue`.
- **N-3.** `disablePush`: `let found` in de `try`, daarna `const sub = found` na `if (!found) return;`, zodat de closure geen narrowing-probleem heeft.
- **N-5.** Nog te doen bij AC-5: noteer in `verification.md` ook of "Verberg linkvoorvertoningen" werkt wanneer er geen andere mail met een link is (bijv. via Notities of Safari).

## Kleine afwijkingen
- **Stap 7 en 8 in één commit.** De login-wijziging en de auth/layout-wijziging raakten dezelfde testbestanden (`login.test.ts` heeft de mocks van stap 7 nodig). Eén commit: "release the push subscription on sign-out; pasted-link login with preview warning on /login".
- **Tests niet strikt eerst rood.** Voor `env-schema`, `platform`, `user-data`, `push`, `sw/push` en de UI zijn tests en implementatie in dezelfde stap geschreven en samen groen gedraaid; geen aparte rode run.
- **R2 en R3 deden zich niet voor.** Een mutatie van `publicEnv` na de import is zichtbaar in `push.ts` (geen `vi.resetModules` nodig), en de build slaagt zonder `PUBLIC_VAPID_PUBLIC_KEY` (geen wijziging in `.github/`). Andere bestaande tests (`spot-list`, `home-no-map`) hoefden niet aangepast.
- **`PUBLIC_VAPID_PUBLIC_KEY=abc`** geeft bij de build de melding "must be an uncompressed P-256 public key" en niet de base64url-melding: `abc` is geldige base64url (2 bytes). De waarde komt nergens in de melding. `abc!` geeft wel de base64url-melding (unit-test).
- **`fake-push.ts`:** `installPushEnv` wikkelt `unsubscribe` van elk abonnement zodat `current` op `null` gaat; `uninstall` verwijdert de gezette eigenschappen. Verder volgens het Testplan.
- **Testgevallen** zijn deels samengevoegd in `it.each`/gecombineerde tests (zelfde dekking als de lijsten in het Testplan).

## NEEDS_LARS
- **AC-5** (echte test op een iPhone en Android: `PUBLIC_VAPID_PUBLIC_KEY` in Cloudflare, aanzetten, `test-push`, echte alert, meten hoeveel van titel (50) en body (150) zichtbaar is, en of de werkwijze tegen de linkvoorvertoning (R1) werkt). Procedure: blueprint, Testplan, en RUNBOOK §14 punt 12 t/m 15.
