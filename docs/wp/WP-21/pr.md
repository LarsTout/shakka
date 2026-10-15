## WP-21: Publieke sessiepagina en RSVP zonder account

- Route `/s/[slug]` (noindex): sessie, deelnemers (voornamen in `<bdi>`), uuroordelen (`HourVerdict`/`Freshness`), Tikkie-link alleen `https://tikkie.me/`.
- `RsvpPanel`/`RsvpForm`: aanmelden, wijzigen, afmelden met bevestiging; carpool volgens WP-19 A6; `now` ververst mee en het formulier sluit na `ends_at`/`session_closed`.
- `#lib/rsvp.ts` is de enige `.rpc(`-aanroeper (allowlist); edit-token alleen in de POST-body en in `localStorage` per slug, nooit in URL/console; RPC-timeout 15 s; vaste NL-tekst per foutcode, nooit de ruwe servertekst.
- Contracttest tegen de WP-19-migratie; hergebruik van de WP-20-helpers. Verifier: XSS-proef (`<script>`, `<img onerror>`, U+202E) en hostile Tikkie-URL's geweigerd.
- 903 web-tests, check 0 fouten, build/verify/guard groen; CI groen.

**Verificatie:** AC-1..6 PASS. AC-7 (RSVP op een telefoon zonder account, `noindex` in de Cloudflare-preview) doet Lars.

**Hiermee is M3 compleet.** Voor Lars: A10 (0–8 plekken), A12 (organisator telt mee), A13 (bewaartermijn 7 dagen).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
