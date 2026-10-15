## WP-20: Sessie aanmaken en delen

- `/go` (uit push/alert): ingelogd → `/sessie/nieuw?spot&start&end`; uitgelogd → bewaart alleen `/go?`-paden van dezelfde origin (60 min) en keert na login terug. Open-redirect-proef door de verifier: 11 varianten geweigerd.
- `/sessie/nieuw`, `/sessie/[slug]/delen` (WhatsApp `wa.me/?text=` zonder tracking-parameters, Web Share alleen tekst, kopieerknop) en `/mijn-sessies` (bewerken, annuleren). "Ik ga"-links op de spotpagina, alleen ingelogd (`GO_RUN_MIN_HOURS = 1`).
- Sessies via `user-data.ts` (enige schrijfmodule): insert zonder `organizer_id`/`slug` (RLS + trigger), één `23505`-retry, update alleen bewerkbare velden, annuleren via `cancelled_at`. Tikkie alleen `https://tikkie.me/`.
- `localWallTimeToUtc` getest op 2026-10-25 en 2027-03-28. Gedeelde helpers voor WP-21: `SESSION_SLUG_RE`, `isValidSessionSlug`, `countCodePoints`, `isTikkieUrl`, `browserStorage`.
- 810 web-tests, check 0 fouten, build/verify/guard groen; CI groen.

**Verificatie:** AC-1..5 PASS. AC-6 (telefoon: push → "Ik ga" → sessie → WhatsApp) doet Lars; vereist WP-20 op productie en `APP_BASE_URL`.

**Voor Lars:** A10 (`GO_RUN_MIN_HOURS = 1`), A7 (één datum per sessie), A16 ("Ik ga" alleen ingelogd in M3).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
