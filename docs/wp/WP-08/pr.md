## WP-08: Alert-deduplicatie en berichtopbouw (puur)

- `shakka.domain.dedup`: `WindowSnapshot` (`gust_max_kn: float | None`), `AlertStateEntry`, `classify_change`, `diff_windows` (één-op-één koppeling op overlap, basislijn = laatst gemelde snapshot, begonnen windows nooit `cancelled`, deterministisch bij split/merge, zelfherstel van overlappende actieve entries).
- `shakka.domain.messages`: `render_alert` (NL, lokale tijd, regels op volgorde van belang voor inkorting in WP-17), `build_go_url` (eigen percent-encoding, gelijk aan `urllib.parse.quote`), `format_window_local`; zes golden-cases herbruikbaar voor WP-17.
- 1169 tests groen; verifier: 3000 willekeurige run-reeksen en crash-simulaties zonder invariantschending; CI groen.

**Verificatie:** AC-1..10 PASS.

**Voor Lars (testweek):** drempels voor "beter/slechter": windowrand ≥ 2 uur of wind ≥ 4 kn; een verschuiving van het hele window met 2 uur telt als slechter; 1-uurswindows die 1 uur opschuiven geven cancelled+new.

**Gevolg voor WP-10/WP-17:** schrijfvolgorde en alles-of-niets per gebruiker en spot (staat al in WORK_PACKAGES).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
