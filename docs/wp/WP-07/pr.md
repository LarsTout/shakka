## WP-07: Alertregels en windows (puur)

- `shakka.domain.alerts`: `AlertRuleOverride`, `ProfileDefaults`, `AlertRule`, `resolve_rule` (regel > profiel > spot > systeem), `rider_limits`, `Window`, `find_windows`.
- Harde regel: offshore/side-offshore geweigerd in override, regel én window; `model_copy` hervalideert. Verifier: eigen steekproeven, 0 doorbraken.
- Tijdsemantiek: eerste meetellend uur floor(now)+1h, halfopen windows, zomer-/wintertijd in Europe/Amsterdam getest. `latest_local` 24:00 → geen bovengrens.
- Vierde contractbestand `data/contracts/alert_defaults.json`.
- 1061 tests groen; CI groen.

**Verificatie:** AC-1..6 PASS.

**Voor Lars (testweek):** defaults `min_go_hours = 2`, `days_ahead = 3`.

**Gevolg voor WP-10:** `from_row` + `resolve_rule` per favoriet in één `try`, zodat één kapotte rij de alertjob niet stopt.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
