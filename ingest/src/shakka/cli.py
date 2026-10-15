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


@cli.command()
def evaluate() -> None:
    """Evaluate all spots with the spot defaults and store the hourly verdicts."""
    from shakka.jobs.evaluate import run_evaluate_cli

    raise SystemExit(run_evaluate_cli(echo=click.echo))


@cli.group()
def alerts() -> None:
    """Alerts: evaluate favorites and record the state (nothing is sent yet)."""


@alerts.command("run")
@click.option("--dry-run", is_flag=True, help="Compute and show the messages; write nothing.")
def alerts_run(dry_run: bool) -> None:
    """Compute alerts for all favorites. Shows message texts: use locally only."""
    from shakka.jobs.alerts import run_alerts_cli

    raise SystemExit(run_alerts_cli(dry_run=dry_run, echo=click.echo))


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


def main() -> None:
    cli()
