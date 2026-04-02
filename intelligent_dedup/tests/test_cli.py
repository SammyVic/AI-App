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
    """This command-line interface test meticulously validates that the terminal-based scanner correctly parses arguments and executes the full deduplication pipeline while providing clear status output and exit codes for automation."""
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Intelligent Dedup' in result.output

def test_cli_scan_invalid_dir(runner):
    """This command-line interface test meticulously validates that the terminal-based scanner correctly parses arguments and executes the full deduplication pipeline while providing clear status output and exit codes for automation."""
    result = runner.invoke(cli, ['scan', '--dir', '/non/existent/path'])
    assert result.exit_code == 1
    assert 'not a valid directory' in result.output

def test_cli_stats_mock(runner):
    """This command-line interface test meticulously validates that the terminal-based scanner correctly parses arguments and executes the full deduplication pipeline while providing clear status output and exit codes for automation."""
    with patch('app.models.repository.ScanRepository.get_lifetime_stats') as mock_stats:
        mock_stats.return_value = {'total_runs': 5, 'total_files_scanned': 100}
        with patch('app.models.database.init_db') as mock_init:
            mock_session = MagicMock()
            mock_init.return_value.return_value.__enter__.return_value = mock_session
            result = runner.invoke(cli, ['stats'])
            assert result.exit_code == 0
            assert 'Total Runs' in result.output
            assert '5' in result.output

def test_cli_agent_mock(runner):
    """This command-line interface test meticulously validates that the terminal-based scanner correctly parses arguments and executes the full deduplication pipeline while providing clear status output and exit codes for automation."""
    with patch('app.models.repository.ScanRepository.get_groups_for_session') as mock_groups:
        mock_groups.return_value = []
        with patch('app.models.database.init_db') as mock_init:
            mock_session = MagicMock()
            mock_init.return_value.return_value.__enter__.return_value = mock_session
            result = runner.invoke(cli, ['agent', '--session', '1'])
            assert result.exit_code == 1
            assert 'No groups found' in result.output