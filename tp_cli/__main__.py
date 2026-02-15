"""Entry point for tp-cli."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from tp_cli import __version__
from tp_cli.commands import analyze as analyze_commands
from tp_cli.commands.auth import login_command, logout_command
from tp_cli.commands.export import export_command
from tp_cli.commands.fetch import fetch_command, get_command
from tp_cli.commands.upload import delete_command, upload_command
from tp_cli.core.config import ConfigError, default_config_path, load_config
from tp_cli.core.state import CLIState

app = typer.Typer(
    add_completion=False,
    help="TrainingPeaks command-line interface",
    invoke_without_command=True,
)


@app.callback()
def main_callback(
    ctx: typer.Context,
    json_output: bool = typer.Option(False, "--json", help="Output JSON where available"),
    plain_output: bool = typer.Option(
        False,
        "--plain",
        help="Output plain text (no rich formatting/tables)",
    ),
    config: Optional[Path] = typer.Option(None, "--config", help="Path to config file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Quiet output"),
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
) -> None:
    """Initialize global CLI state."""
    if version:
        typer.echo(__version__)
        raise typer.Exit(code=0)

    if json_output and plain_output:
        typer.echo("Options --json and --plain are mutually exclusive.")
        raise typer.Exit(code=2)

    cfg_path = (config or default_config_path()).expanduser().resolve()
    try:
        cfg = load_config(cfg_path)
    except ConfigError as exc:
        typer.echo(f"Config error: {exc}")
        raise typer.Exit(code=2)

    console = Console(
        quiet=quiet,
        no_color=plain_output,
        log_time=False,
        log_path=False,
    )
    ctx.obj = CLIState(
        json_output=(json_output and not plain_output),
        plain_output=plain_output,
        verbose=verbose,
        quiet=quiet,
        config_path=cfg_path,
        config=cfg,
        console=console,
    )

    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)


# Top-level commands
app.command("login")(login_command)
app.command("logout")(logout_command)
app.command("fetch")(fetch_command)
app.command("get")(get_command)
app.command("upload")(upload_command)
app.command("delete")(delete_command)
app.command("export")(export_command)
app.add_typer(analyze_commands.app, name="analyze")


def main() -> None:
    """Console script entrypoint."""
    app()


if __name__ == "__main__":
    main()
