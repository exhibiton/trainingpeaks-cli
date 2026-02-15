"""Authentication commands."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Optional

import typer

from tp_cli.commands.common import get_state, print_json_payload
from tp_cli.core.auth import AuthError, TrainingPeaksAuth

app = typer.Typer(help="Authenticate with TrainingPeaks")


@app.command("login")
def login_command(
    ctx: typer.Context,
    username: Optional[str] = typer.Option(None, help="TrainingPeaks username", envvar="TP_USERNAME"),
    password: Optional[str] = typer.Option(None, help="TrainingPeaks password", envvar="TP_PASSWORD"),
    force: bool = typer.Option(False, "--force", help="Force re-authentication"),
) -> None:
    """Authenticate and cache session cookies."""
    state = get_state(ctx)
    auth = TrainingPeaksAuth(config=state.config, username=username, password=password)

    try:
        status_ctx = state.console.status("Authenticating...") if not state.plain_output else nullcontext()
        with status_ctx:
            token, _ = auth.login(force=force)
            user_info = auth.get_user_info(token)

        user = user_info.get("user", {})
        payload = {
            "status": "success",
            "authenticated": True,
            "user": {
                "userId": user.get("userId"),
                "username": user.get("username"),
                "email": user.get("email"),
            },
        }

        if state.json_output:
            print_json_payload(state, payload)
            return

        if state.plain_output:
            user = payload["user"]
            typer.echo("status\tsuccess")
            typer.echo(f"user_id\t{user['userId']}")
            typer.echo(f"username\t{user['username']}")
            typer.echo(f"email\t{user['email']}")
            return

        state.console.print("Login successful")
        state.console.print(
            f"User: {payload['user']['username']} ({payload['user']['userId']})"
        )
    except AuthError as exc:
        if state.json_output:
            print_json_payload(state, {"status": "error", "message": str(exc)})
        elif state.plain_output:
            typer.echo("status\terror")
            typer.echo(f"message\t{exc}")
        else:
            state.console.print(f"Login failed: {exc}")
        raise typer.Exit(code=1)


@app.command("logout")
def logout_command(ctx: typer.Context) -> None:
    """Delete cached local credentials."""
    state = get_state(ctx)
    auth = TrainingPeaksAuth(config=state.config)
    removed = auth.logout()

    if state.json_output:
        print_json_payload(
            state,
            {
                "status": "success",
                "logged_out": bool(removed),
                "message": "Local cookie cache removed" if removed else "No cached cookie file",
            },
        )
        return

    if state.plain_output:
        typer.echo("status\tsuccess")
        typer.echo(f"logged_out\t{str(bool(removed)).lower()}")
        typer.echo(
            "message\tLocal cookie cache removed"
            if removed
            else "message\tNo local cookie cache file"
        )
        return

    if removed:
        state.console.print("Local cookie cache removed")
    else:
        state.console.print("No local cookie cache found")
