"""Command line entry point."""

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


def main() -> None:
    cli()
