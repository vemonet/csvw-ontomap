from typer.testing import CliRunner

from csvw_ontomap.__main__ import cli

runner = CliRunner()


def test_cli():
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
