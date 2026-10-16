# Review WP-22, ronde 2
Oordeel: APPROVED

Alleen B-1 t/m B-6 en de secties uit "Verwerking review" zijn beoordeeld. Geen escalatie nodig: de revisie raakt RLS, grants en privacy niet op een nieuwe manier.

## Blokkerend
Geen. Per punt uit ronde 1:

- B-1 opgelost. `07_sessions.test.sql` staat in Bestanden, met de exacte regels 68 en 69 (`db_usage` erbij). De eindvorm samen met WP-23 (`delete_my_account` in 67 en 69) staat erbij, met de regel "wie als tweede merget". `push_subscriptions_limit` en `sessions_starts_at_horizon` staan bewust in geen van de sets (security invoker, `revoke all`). `plan(112)` blijft.
- B-2 opgelost. De teller `push_non_retryable` loopt van `EventDelivery` via `PlanDelivery` en `AlertJobResult` naar `alert_counts`. Bij een waarde boven 0 krijgt de stap een `::warning::` en wordt hij `partial`. `alerts run` geeft exit 1. De pipeline-exitcode blijft bewust 0, en dat staat er ook zo. Er zijn tests voor de annotatie en de CLI-regel.
- B-3 opgelost. Brevo is afgewezen. Resend (tracking standaard uit) en Gmail met app-wachtwoord zijn onderbouwd, Postmark voldoet maar heeft maar 100 per maand. Een domein staat expliciet als betaald, de keuze en het akkoord liggen bij Lars (A15, R12, "Nodig van Lars" 4), en er wordt geen kost aangenomen. AC-6 stap 4 test dat de link direct naar `<project>.supabase.co/auth/v1/verify` wijst. De regel "geen tracking" is gehaald.
- B-4 opgelost. `jmt17.google.com` staat als exacte host in `PUSH_SERVICE_HOSTS`, met een testrij en E52. `android.googleapis.com` blijft er terecht buiten.
- B-5 opgelost. De CHECK is vervangen door de trigger `sessions_starts_at_horizon` (`BEFORE INSERT OR UPDATE OF starts_at`). De trigger controleert `old` pas na `tg_op = 'UPDATE'` (geneste if) en slaat een ongewijzigde `starts_at` over. Asserts 22–28 dekken insert, bewerken binnen de grens, bewerken erbuiten en de ongewijzigde oudere rij. R15 geeft een bruikbare terugval als `disable trigger` faalt met `42501`: rij zonder disable op 369 dagen, assert 28 gaat naar 371 dagen, het aantal asserts blijft 28, en de builder noteert het in `deviations.md`. De "ongewijzigd"-tak wordt in die terugval zwakker getoetst, en dat staat erbij.
- B-6 opgelost volgens de beslissing van de orchestrator: de grens is 100.000 requests (alleen tiles), met een zin en een bron in §17.8 dat map sessions alleen voor de MapTiler-SDK gelden.

Er is niets nieuws blokkerends geïntroduceerd.

## Niet-blokkerend
N-1: De zin in §17.8 spreekt `docs/PROJECT_PLAN.md` sectie 2 tegen (5.000 map sessions). Laat de orchestrator het plan bij de afsluiting van de WP gelijktrekken, zodat er één waarheid is.
N-2: Gmail vermeldt "Google verwerkt de adressen van de ontvangers" alleen in A15. Neem dat ook mee in de vervolgwijziging van "De maildienst" op `/privacy`.

## Gecontroleerde bronnen
Geen nieuwe externe bronnen gecontroleerd. Alleen de revisie in `docs/wp/WP-22/blueprint.md` (A8, A9, A13, A15, Interfaces `07_sessions`, Testplan AC-4 en AC-6, R15, Verwerking review) is gelezen.
