from typer.testing import CliRunner

from tp_cli.__main__ import app


runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--plain" in result.stdout
    for command in ["login", "logout", "fetch", "upload", "analyze", "export"]:
        assert command in result.stdout


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_json_and_plain_are_mutually_exclusive() -> None:
    result = runner.invoke(app, ["--json", "--plain", "fetch", "--help"])
    assert result.exit_code == 2
    assert "mutually exclusive" in result.stdout
