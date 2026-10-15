## WP-14: Spotlijst en spotpagina

- Routes `/` (spotlijst met dagsamenvattingen), `/spot/[id]` (uuroordeel, redenen, wind/vlagen/richting, getij, versheid) en `/go` (redirect naar de spotpagina; ongeldig → `/`).
- Pure modules `time` (Europe/Amsterdam via `Intl`), `view`, `labels`, `contracts`, `data` (alleen `spots`, `evaluations`, `tide_extremes`, gepagineerd), `page-data`, `go`. Componenten `VerdictBadge`, `WindArrow`, `HourVerdict`, `Freshness`.
- Drift-tests tegen de M1-migratie (incl. `alter table`), `data/contracts/*.json`, `direction.py` en de `/go`-fixture uit WP-08.
- Harde regels geborgd: geen Open-Meteo in `web/`, bronvermelding op elke pagina, geen tracking, `dir_class` nooit uit `dir_deg`.
- 203 web-tests, check 0 fouten, build + verify-build + guard groen; CI groen.

**Verificatie:** AC-1..6 PASS. AC-7 (Cloudflare Pages, `APP_BASE_URL`, handmatige terugknop-test na `/go`) doet Lars.

**Voor Lars:** A2 (labels "Go / Twijfel / Niet gaan"), A3 (donkere uren standaard verborgen). Pages-root is de repo-root (A7, al in WORK_PACKAGES).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
