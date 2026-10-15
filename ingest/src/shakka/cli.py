"""Command line entry point."""

from pathlib import Path

import click


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="shakka", prog_name="shakka")
def cli() -> None:
    """Shakka ingest and admin tooling."""


@cli.command()
def doctor() -> None:
    """Check configuration and Supabase connectivity."""
    from shakka.doctor import run_doctor

    raise SystemExit(run_doctor(echo=click.echo))


@cli.group()
def spots() -> None:
    """Validate and sync spot profiles (data/spots.yaml)."""


@spots.command("validate")
@click.option(
    "--path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Spots YAML file (default: data/spots.yaml; SPOTS_PATH is not read).",
)
def spots_validate(path: Path | None) -> None:
    """Validate the spots file without touching the database."""
    from shakka.spots.commands import run_validate

    raise SystemExit(run_validate(path, echo=click.echo))


@spots.command("sync")
@click.option(
    "--path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Spots YAML file (default: SPOTS_PATH, else data/spots.yaml).",
)
def spots_sync(path: Path | None) -> None:
    """Upsert new and changed spots into the database. Never deletes."""
    from shakka.spots.commands import run_sync

    raise SystemExit(run_sync(path, echo=click.echo))


@cli.group()
def forecast() -> None:
    """Wind forecast ingest (Open-Meteo, server-side)."""


@forecast.command("fetch")
@click.option("--dry-run", is_flag=True, help="Show the plan; no Open-Meteo requests, no writes.")
def forecast_fetch(dry_run: bool) -> None:
    """Fetch wind forecasts for all spots with coordinates."""
    from shakka.jobs.forecast import run_forecast_cli

    raise SystemExit(run_forecast_cli(dry_run=dry_run, echo=click.echo))


@cli.group()
def marine() -> None:
    """Wave forecast ingest (Open-Meteo Marine, server-side). Display only."""


@marine.command("fetch")
def marine_fetch() -> None:
    """Fetch wave forecasts for all spots with coordinates."""
    from shakka.jobs.marine import run_marine_cli

    raise SystemExit(run_marine_cli(echo=click.echo))


@cli.command()
def evaluate() -> None:
    """Evaluate all spots with the spot defaults and store the hourly verdicts."""
    from shakka.jobs.evaluate import run_evaluate_cli

    raise SystemExit(run_evaluate_cli(echo=click.echo))


@cli.group()
def alerts() -> None:
    """Alerts: evaluate favorites, record the state and deliver Web Push."""


@alerts.command("run")
@click.option("--dry-run", is_flag=True, help="Compute and show the messages; write nothing.")
def alerts_run(dry_run: bool) -> None:
    """Compute alerts for all favorites. Shows message texts: use locally only."""
    from shakka.jobs.alerts import run_alerts_cli

    raise SystemExit(run_alerts_cli(dry_run=dry_run, echo=click.echo))


@alerts.command("test-push")
@click.option("--user-id", type=click.UUID, required=True)
def alerts_test_push(user_id) -> None:
    """Send a test notification to every device of a user. Local use."""
    from shakka.jobs.push import run_test_push_cli

    raise SystemExit(run_test_push_cli(str(user_id), echo=click.echo))


@alerts.command("vapid-keys")
def alerts_vapid_keys() -> None:
    """Generate a VAPID key pair. Prints the private key: do not share or log the output."""
    from shakka.jobs.push import run_vapid_keys_cli

    raise SystemExit(run_vapid_keys_cli(echo=click.echo))


@cli.group()
def tides() -> None:
    """Rijkswaterstaat astronomical tide extremes."""


@tides.command("fetch")
@click.option("--force", is_flag=True, help="Ignore the 20-hour freshness rule.")
def tides_fetch(force: bool) -> None:
    """Fetch tide extremes for every station used by a spot."""
    import functools
    from datetime import UTC, datetime

    import pydantic

    import shakka.jobs.tides as job
    import shakka.rws.tides as rws
    from shakka.config import get_settings
    from shakka.db import DatabaseError, SupabaseRest
    from shakka.http import make_client

    try:
        settings = get_settings()
    except pydantic.ValidationError:
        click.echo("tides fetch: configuration incomplete (run 'shakka doctor')")
        raise SystemExit(1) from None
    try:
        with (
            SupabaseRest.from_settings(settings) as db,
            make_client(timeout=rws.OBSERVATIONS_TIMEOUT_S) as http,
        ):
            result = job.run_tide_ingest(
                db,
                now=datetime.now(UTC),
                force=force,
                fetch=functools.partial(rws.fetch_tide_extremes, http=http),
            )
    except DatabaseError as exc:
        click.echo(f"tides fetch: database error: {exc}")
        raise SystemExit(1) from None
    click.echo(
        f"tides: fetched {result.stations} station(s), {result.rows} row(s), "
        f"deleted {result.deleted} old row(s)"
    )
    if result.skipped:
        click.echo(f"tides: skipped (fetched < 20h ago): {', '.join(result.skipped)}")
    if result.failed:
        click.echo(f"tides: failed: {', '.join(result.failed)}")
        for line in result.errors:
            click.echo(f"  {line}")
    raise SystemExit(1 if result.failed else 0)


@tides.command("stations")
@click.option("--search", default=None, help="Case-insensitive filter on code or name.")
def tides_stations(search: str | None) -> None:
    """List stations with astronomical high and low water (code, name, lat, lon)."""
    import shakka.rws.tides as rws

    try:
        stations = rws.list_tide_stations()
    except rws.TideFetchError as exc:
        click.echo(f"tides stations: {exc}", err=True)
        raise SystemExit(1) from None
    if search:
        needle = search.lower()
        stations = [s for s in stations if needle in s.code.lower() or needle in s.name.lower()]
    click.echo("code\tname\tlat\tlon")
    for s in stations:
        click.echo(f"{s.code}\t{s.name}\t{s.lat:.5f}\t{s.lon:.5f}")
    click.echo(f"{len(stations)} stations")


@cli.group()
def contracts() -> None:
    """Generated contract files in data/contracts/."""


@contracts.command("export")
@click.option("--check", is_flag=True, help="Only check that the files are up to date.")
def contracts_export(check: bool) -> None:
    """Write reason codes, direction classes, confidence labels and alert defaults as JSON."""
    from shakka.contracts import run_contracts_export

    raise SystemExit(run_contracts_export(check=check, echo=click.echo))


@cli.group()
def admin() -> None:
    """Manage your profile, favorites and alert rules without a UI (M1)."""


@admin.group("profile")
def admin_profile() -> None:
    """Rider profile."""


@admin_profile.command("set")
@click.option("--user-id", type=click.UUID, required=True)
@click.option("--weight", type=int, default=None, help="Weight in kg (30-200).")
@click.option("--level", default=None, help="beginner, intermediate or advanced.")
@click.option(
    "--quiver",
    default=None,
    help='Sizes in m2, e.g. "7 9 12" or 7,9,12; decimals with a point. "" empties the quiver.',
)
@click.option("--min-kn", type=int, default=None, help="Default minimum wind (5-60 kn).")
@click.option("--max-kn", type=int, default=None, help="Default maximum wind (5-60 kn).")
def admin_profile_set(user_id, weight, level, quiver, min_kn, max_kn) -> None:
    """Change only the given profile fields."""
    from shakka.jobs import admin as ops

    def action(db, now, settings):
        parsed = None if quiver is None else ops.parse_quiver(quiver)
        row = ops.set_profile(
            db,
            str(user_id),
            weight_kg=weight,
            level=level,
            quiver_m2=parsed,
            min_kn=min_kn,
            max_kn=max_kn,
        )
        note = None if quiver is None else ops.quiver_comma_note(quiver)
        return [*([note] if note else []), "profile set: saved", *ops.format_profile(row)]

    raise SystemExit(ops.run_admin("profile set", action, echo=click.echo))


@admin_profile.command("show")
@click.option("--user-id", type=click.UUID, required=True)
def admin_profile_show(user_id) -> None:
    """Show the rider profile."""
    from shakka.jobs import admin as ops

    def action(db, now, settings):
        return ops.format_profile(ops.get_profile(db, str(user_id)))

    raise SystemExit(ops.run_admin("profile show", action, echo=click.echo))


@admin.group("favorite")
def admin_favorite() -> None:
    """Favorite spots."""


@admin_favorite.command("add")
@click.option("--user-id", type=click.UUID, required=True)
@click.option("--spot", required=True, help="Spot id, e.g. wijk-aan-zee.")
def admin_favorite_add(user_id, spot) -> None:
    """Add a favorite spot."""
    from shakka.jobs import admin as ops

    def action(db, now, settings):
        result = ops.add_favorite(db, str(user_id), spot)
        lines = [
            f"favorite add: added {spot}"
            if result.added
            else f"favorite add: {spot} is already a favorite"
        ]
        if not result.verified:
            lines.append(
                f"note: {spot} is not verified; it is evaluated but gives no alerts until "
                "verified: true"
            )
        return lines

    raise SystemExit(ops.run_admin("favorite add", action, echo=click.echo))


@admin_favorite.command("remove")
@click.option("--user-id", type=click.UUID, required=True)
@click.option("--spot", required=True, help="Spot id.")
def admin_favorite_remove(user_id, spot) -> None:
    """Remove a favorite spot (and its alert rule)."""
    from shakka.jobs import admin as ops

    def action(db, now, settings):
        if ops.remove_favorite(db, str(user_id), spot):
            return [f"favorite remove: removed {spot} (and its alert rule)"]
        return [f"favorite remove: {spot} was not a favorite"]

    raise SystemExit(ops.run_admin("favorite remove", action, echo=click.echo))


@admin_favorite.command("list")
@click.option("--user-id", type=click.UUID, required=True)
def admin_favorite_list(user_id) -> None:
    """List favorite spots."""
    from shakka.jobs import admin as ops

    def action(db, now, settings):
        infos = ops.list_favorites(db, str(user_id))
        lines = [
            f"{i.spot_id}\t{i.name}\t{'verified' if i.verified else 'not verified'}\t"
            f"{'own rule' if i.has_rule else 'default rule'}"
            for i in infos
        ]
        return [*lines, f"{len(infos)} favorite(s)"]

    raise SystemExit(ops.run_admin("favorite list", action, echo=click.echo))


@admin.group("rule")
def admin_rule() -> None:
    """Alert rules per favorite spot."""


@admin_rule.command("set")
@click.option("--user-id", type=click.UUID, required=True)
@click.option("--spot", required=True, help="Spot id (must be a favorite).")
@click.option("--min-kn", type=int, default=None, help="Minimum wind (5-60 kn).")
@click.option("--max-kn", type=int, default=None, help="Maximum wind (5-60 kn).")
@click.option(
    "--dir-classes", default=None, help="onshore,side_onshore,sideshore (never offshore)."
)
@click.option("--weekdays", default=None, help="ISO weekdays 1-7, e.g. 6,7.")
@click.option("--after", default=None, help="Earliest local start, HH:MM.")
@click.option("--before", default=None, help="Latest local end, HH:MM.")
@click.option("--min-go-hours", type=int, default=None, help="Minimum consecutive go hours (1-24).")
@click.option("--days-ahead", type=int, default=None, help="Days ahead after today (0-7).")
@click.option("--enable/--disable", "enabled", default=None, help="Switch the rule on or off.")
def admin_rule_set(
    user_id,
    spot,
    min_kn,
    max_kn,
    dir_classes,
    weekdays,
    after,
    before,
    min_go_hours,
    days_ahead,
    enabled,
) -> None:
    """Change only the given rule fields."""
    from shakka.jobs import admin as ops

    def action(db, now, settings):
        rule = ops.set_rule(
            db,
            str(user_id),
            spot,
            min_kn=min_kn,
            max_kn=max_kn,
            dir_classes=None if dir_classes is None else ops.parse_dir_classes(dir_classes),
            weekdays=None if weekdays is None else ops.parse_weekdays(weekdays),
            earliest_local=None if after is None else ops.parse_local_time(after),
            latest_local=None if before is None else ops.parse_local_time(before),
            min_go_hours=min_go_hours,
            days_ahead=days_ahead,
            enabled=enabled,
        )
        from shakka.jobs.alerts import format_rule

        return [f"rule set: saved for {spot}", f"rule: {format_rule(rule)}"]

    raise SystemExit(ops.run_admin("rule set", action, echo=click.echo))


@admin.group("alerts")
def admin_alerts() -> None:
    """Alerts without side effects."""


@admin_alerts.command("preview")
@click.option("--user-id", type=click.UUID, required=True)
def admin_alerts_preview(user_id) -> None:
    """Show what an alert run would do. Writes nothing; shows message texts (local use)."""
    from shakka.jobs import admin as ops

    def action(db, now, settings):
        plans = ops.preview_alerts(db, str(user_id), now=now, base_url=settings.app_base_url)
        return ops.format_preview(plans)

    raise SystemExit(ops.run_admin("alerts preview", action, echo=click.echo))


@cli.command("run-hourly")
def run_hourly_cmd() -> None:
    """Run all hourly steps (spots sync, forecast, marine, tides, evaluate, alerts).

    Records the run.
    """
    from shakka.pipeline import run_hourly_cli

    raise SystemExit(run_hourly_cli(echo=click.echo))


@cli.command("check-activity")
@click.option(
    "--last-commit-at", default="", help="ISO date of the last commit on the default branch."
)
def check_activity_cmd(last_commit_at: str) -> None:
    """Warn before GitHub disables the hourly schedule (60 days without activity)."""
    from shakka.activity import run_check_activity_cli

    raise SystemExit(run_check_activity_cli(last_commit_at, echo=click.echo))


def main() -> None:
    cli()
