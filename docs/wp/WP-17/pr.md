## WP-17: Web Push: backend (enige meldingskanaal)

- Migratie `push_subscriptions` met RLS, kolomprivileges (`authenticated`: insert op `user_id, endpoint, p256dh, auth`, select/delete eigen rijen; `anon` niets), pgTAP (222 asserts totaal, groen in CI).
- `shakka.domain.push` (puur): inkorting titel ≤ 50 / body ≤ 150 op regelgrens, payload ≤ 3000 bytes. `shakka.notify.{base,webpush}`: `WebPushNotifier` (pywebpush, TTL 12 u), proefhandtekening bij constructie zodat een fout `VAPID_SUBJECT` de run hard laat falen; alleen 404/410 permanent (abonnement verwijderd).
- `shakka.jobs.alerts`: aflevering tussen plannen en opslaan, alles-of-niets per gebruiker en spot, `id` vooraf voor de push-`tag`; schrijfvolgorde WP-10 ongewijzigd. Zonder VAPID: kanaal uit met `::warning::`, `alert_state` schuift door. `::warning::` bij `deferred > 0`.
- CLI `alerts test-push`, `alerts vapid-keys`; `hourly.yml` met drie VAPID-secrets; RUNBOOK §14.
- 1442 tests groen; CI (`ingest`, `web`, `db`) groen.

**Verificatie:** AC-1..8 PASS, inclusief logcontrole in vier modi (geen endpoint/sleutel/user-id/subject in output).

**Voor Lars:** `supabase db push` na de merge (migratie `20261015150000_push_subscriptions.sql`). VAPID-sleutels en secrets staan al (gezet door de orchestrator). Echte `alerts test-push` na WP-18.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
