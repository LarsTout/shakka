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


def main() -> None:
    cli()
