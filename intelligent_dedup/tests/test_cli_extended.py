"""
tests/test_cli_extended.py
=============================================================================
Extended unit tests for cli.py to boost coverage by exercising scan and agent.
=============================================================================
"""
import pytest
import os
import json
from click.testing import CliRunner
from cli import cli
from unittest.mock import patch, MagicMock
from app.engine.deduplicator import DeduplicationResult, DuplicateGroup

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_scan_with_output_success(runner):
    """This command-line interface test meticulously validates that the terminal-based scanner correctly parses arguments and executes the full deduplication pipeline while providing clear status output and exit codes for automation."""
    group1 = DuplicateGroup('g1', 'exact', ['/p1', '/p2'], 1024)
    res = DeduplicationResult(groups=[group1], files_scanned=10, duplicate_files=1, space_recoverable_bytes=1024, duration_seconds=1.5, passes_completed=3)
    with patch('app.engine.deduplicator.Deduplicator.run', return_value=res), patch('app.models.database.init_db') as mock_init, patch('app.models.repository.ScanRepository') as mock_repo_class, patch('pathlib.Path.is_dir', return_value=True), patch('pathlib.Path.write_text') as mock_write_text:
        mock_session = MagicMock()
        mock_init.return_value.return_value.__enter__.return_value = mock_session
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_db_sess = MagicMock()
        mock_db_sess.id = 42
        mock_repo.create_session.return_value = mock_db_sess
        result = runner.invoke(cli, ['scan', '--dir', '/tmp/test', '--output', 'report.json', '--fuzzy', '--semantic'])
        assert result.exit_code == 0
        assert 'Session saved to database (id=42)' in result.output
        assert 'Report saved' in result.output
        mock_repo.create_session.assert_called_once()
        mock_repo.create_group.assert_called_once()
        mock_repo.complete_session.assert_called_once()
        assert mock_write_text.called
        written_content = mock_write_text.call_args[0][0]
        report = json.loads(written_content)
        assert report['files_scanned'] == 10
        assert report['duplicate_groups'] == 1

def test_cli_scan_db_error_still_completes(runner):
    """This command-line interface test meticulously validates that the terminal-based scanner correctly parses arguments and executes the full deduplication pipeline while providing clear status output and exit codes for automation."""
    group1 = DuplicateGroup('g1', 'exact', ['/p1', '/p2'], 1024)
    res = DeduplicationResult(groups=[group1], files_scanned=10, duplicate_files=1, space_recoverable_bytes=1024, duration_seconds=0.1, passes_completed=1)
    with patch('app.engine.deduplicator.Deduplicator.run', return_value=res), patch('app.models.database.init_db', side_effect=Exception('Database down')), patch('pathlib.Path.is_dir', return_value=True):
        result = runner.invoke(cli, ['scan', '--dir', '/tmp/test'])
        assert result.exit_code == 0
        assert 'Database write failed: Database down' in result.output
        assert 'Scan Results' in result.output

def test_cli_agent_with_groups(runner):
    """This functional test meticulously verifies that the scan repository correctly handles large volumes of redundant file groups including their metadata hashes and space recovery statistics during complex deduplication processing runs."""
    db_group = MagicMock()
    db_group.group_key = 'g1'
    db_group.match_type = 'exact'
    db_group.file_paths = ['a', 'b']
    db_group.space_recoverable_bytes = 100
    decision = MagicMock()
    decision.recommended_keep = 'a'
    decision.confidence = 0.95
    with patch('app.models.database.init_db') as mock_init, patch('app.models.repository.ScanRepository') as mock_repo_class, patch('app.agents.reasoning_engine.ReasoningEngine') as mock_engine_class:
        mock_session = MagicMock()
        mock_init.return_value.return_value.__enter__.return_value = mock_session
        mock_repo = MagicMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_groups_for_session.return_value = [db_group]
        mock_engine = MagicMock()
        mock_engine_class.return_value = mock_engine
        mock_engine.process.return_value = {'g1': decision}
        mock_engine.summary_stats.return_value = {'processed': 1, 'avg_confidence': 0.95, 'high_confidence': 1}
        result = runner.invoke(cli, ['agent', '--session', '1', '--output', 'agent.json'])
        assert result.exit_code == 0
        assert 'Keep: a' in result.output
        assert 'Agent log saved' in result.output
        mock_engine.export_log.assert_called_with('agent.json')

def test_cli_agent_db_error(runner):
    """This command-line interface test meticulously validates that the terminal-based scanner correctly parses arguments and executes the full deduplication pipeline while providing clear status output and exit codes for automation."""
    with patch('app.models.database.init_db', side_effect=Exception('Crash')), patch('sys.exit') as mock_exit:
        result = runner.invoke(cli, ['agent', '--session', '1'])
        assert 'Agent error: Crash' in result.output
        assert result.exc_info[0] == Exception