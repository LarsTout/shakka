# PR WP-28: Dependabot

Maandelijkse, gegroepeerde Dependabot-PR's naar `develop` voor `github-actions`, `npm` en `uv`. Draait WP-22 A17 terug. Twee tests bewaken de config en de SHA-pins met versiecommentaar. RUNBOOK §18.8 en §18.10 bijgewerkt.

## Nodig van Lars
- Na de merge naar `develop`: Settings, Advanced Security, "Dependabot alerts" en "Dependabot security updates" op Enable.
- Daarna AC-3: Insights, Dependency graph, Dependabot, per ecosysteem een geslaagde controle; bij de eerste Actions-PR SHA plus commentaar controleren (E1, E2).
- Eventueel nu al "Check for updates" per ecosysteem in die tab.
