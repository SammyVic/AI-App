import pytest
import os
import json
from click.testing import CliRunner
from cli import cli
from unittest.mock import patch, MagicMock

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Intelligent Dedup" in result.output

def test_cli_scan_invalid_dir(runner):
    result = runner.invoke(cli, ["scan", "--dir", "/non/existent/path"])
    assert result.exit_code == 1
    assert "not a valid directory" in result.output

def test_cli_stats_mock(runner):
    with patch("app.models.repository.ScanRepository.get_lifetime_stats") as mock_stats:
        mock_stats.return_value = {"total_runs": 5, "total_files_scanned": 100}
        with patch("app.models.database.init_db") as mock_init:
            # Mock session context manager
            mock_session = MagicMock()
            mock_init.return_value.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ["stats"])
            assert result.exit_code == 0
            assert "Total Runs" in result.output
            assert "5" in result.output

def test_cli_agent_mock(runner):
    with patch("app.models.repository.ScanRepository.get_groups_for_session") as mock_groups:
        mock_groups.return_value = [] # Trigger "No groups found"
        with patch("app.models.database.init_db") as mock_init:
            mock_session = MagicMock()
            mock_init.return_value.return_value.__enter__.return_value = mock_session
            
            result = runner.invoke(cli, ["agent", "--session", "1"])
            assert result.exit_code == 1
            assert "No groups found" in result.output
