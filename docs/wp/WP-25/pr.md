## WP-25: Moderatie voor organisatoren

**Wat er nu werkt**
- Een organisator kan op zijn eigen sessie een aanmelding van iemand anders verwijderen (RPC `organizer_delete_rsvp`, met bevestiging in de app).
- Een organisator kan het aanmelden sluiten en weer openen (`sessions.rsvps_closed_at`). Bij gesloten aanmelden weigert `rsvp_create` met `session_closed`. Wijzigen en afmelden met een token blijven werken.
- Nieuwe route `/sessie/[slug]/beheer`, bereikbaar via "Aanmeldingen beheren" in `/mijn-sessies`.
- `/s/[slug]` toont "De organisator heeft het aanmelden gesloten." in plaats van het formulier.
- RUNBOOK §16.5: de SQL-route is nu de terugvaloptie. Nieuwe §16.10 met de telefoontest (AC-7).

**Zo probeer je het**
1. Na de merge: `supabase db push` (nieuwe migratie `20261028090000_organizer_moderation.sql`), vóór de promotie naar `main`.
2. `cd web && npm run dev`. Maak een sessie, meld je aan via `/s/<slug>` in een privévenster, open dan `/mijn-sessies` → "Aanmeldingen beheren". Verwijder de aanmelding en zet het aanmelden dicht.
3. Volledige stappen: RUNBOOK §16.10.

**Voor Lars**
- A1: bevestig dat "sessie sluiten" betekent: aanmelden stoppen zonder te annuleren. Zo is het gebouwd.
- A2/A9: verwijderen kan ook bij geannuleerde of afgelopen sessies (binnen de bewaartermijn). De beheerlink staat ook bij geannuleerde sessies.
- pgTAP is lokaal niet gedraaid (geen Docker). Het bewijs voor AC-1 t/m AC-3 komt uit de CI-job `db`.

**Niet-blokkerende reviewpunten** (N-1 t/m N-4 uit `review.md`) zijn tijdens het bouwen verwerkt. Kleine afwijkingen staan in `deviations.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
