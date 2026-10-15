## WP-19: Sessies: datamodel, RLS en RPC's

- Migratie `sessions` + `rsvps`: revoke all, expliciete grants, RLS (organisator alleen eigen rijen; `rsvps` zonder enige tabelrechten, ook niet voor `service_role`); pgcrypto-guard.
- Vijf RPC's, `security definer` met `set search_path = ''`: `get_public_session`, `rsvp_create`/`rsvp_update`/`rsvp_delete` (anon + authenticated, edit-token: 32 random bytes, alleen sha256-hash opgeslagen, alleen via POST), `purge_expired_sessions` (alleen `service_role`). Fouten als SQLSTATE `PT400` met de code als message.
- Rate limits: 10 sessies/organisator/24 u (trigger), RSVP-limiet via `recent_rsvp_creates` die alleen de RPC schrijft. Minimale gegevens: voornaam + carpool, geen e-mail/IP.
- Pipeline-stap `sessions_cleanup` (bewaartermijn 7 dagen, gelijk in SQL en Python met test). RUNBOOK §8, §13, §16.
- pgTAP `01` (71), `07` (112), `08` (71): 425 asserts groen in CI; 1569 ingest-tests; ronde 1 FAIL (één SQLSTATE) hersteld in `9e92c83`.

**Verificatie:** ronde 2 PASS op alle AC's en harde regels. `supabase db push` doet de orchestrator na de merge.

**Voor Lars:** A1 bewaartermijn 7 dagen; A4 (RSVP-limiet telt ook afmelden), A6 (carpoolregels), A7 (spot met sessies niet verwijderbaar), A10 (`rsvp_delete` werkt altijd). Risico N-7: iemand met de link kan een sessie vol zetten; organisator kan niets verwijderen (volgt uit de WP-spec; WP-20/22).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
