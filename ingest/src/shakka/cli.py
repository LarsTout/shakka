"""Command line entry point."""

import click


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="shakka", prog_name="shakka")
def cli() -> None:
    """Shakka ingest and admin tooling."""


def main() -> None:
    cli()
