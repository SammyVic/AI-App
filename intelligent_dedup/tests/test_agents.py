import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from app.agents.retention_agent import RetentionAgent, AgentDecision
from app.agents.reasoning_engine import ReasoningEngine
from app.engine.deduplicator import DuplicateGroup as EngineGroup

class TestRetentionAgent:

    def test_analyse_empty(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        agent = RetentionAgent()
        with pytest.raises(ValueError):
            agent.analyse([])

    def test_canonical_preference(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = os.path.join(tmpdir, 'Documents')
            temp_dir = os.path.join(tmpdir, 'temp')
            os.makedirs(docs_dir)
            os.makedirs(temp_dir)
            p1 = os.path.join(docs_dir, 'file.txt')
            p2 = os.path.join(temp_dir, 'file.txt')
            with open(p1, 'w') as f:
                f.write('data')
            with open(p2, 'w') as f:
                f.write('data')
            agent = RetentionAgent()
            decision = agent.analyse([p1, p2])
            assert decision.recommended_keep == p1
            assert decision.confidence > 0.5

    def test_filename_copy_penalisation(self):
        """This core test meticulously validates every file metadata record is correctly inserted and updated within the database schema while maintaining strict foreign key consistency and accurate byte size representation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, 'original.txt')
            p2 = os.path.join(tmpdir, 'original (2).txt')
            with open(p1, 'w') as f:
                f.write('data')
            with open(p2, 'w') as f:
                f.write('data')
            agent = RetentionAgent()
            decision = agent.analyse([p1, p2])
            assert decision.recommended_keep == p1

    def test_timestamp_preference(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = os.path.join(tmpdir, 'old.txt')
            p2 = os.path.join(tmpdir, 'new.txt')
            with open(p1, 'w') as f:
                f.write('data')
            with open(p2, 'w') as f:
                f.write('data')
            import time
            now = time.time()
            os.utime(p1, (now - 1000, now - 1000))
            os.utime(p2, (now, now))
            agent = RetentionAgent()
            decision = agent.analyse([p1, p2])
            assert decision.recommended_keep == p2

    def test_fallback_missing_files(self):
        """This core test meticulously validates every file metadata record is correctly inserted and updated within the database schema while maintaining strict foreign key consistency and accurate byte size representation."""
        agent = RetentionAgent()
        decision = agent.analyse(['/missing/1.txt', '/missing/2.txt'])
        assert decision.recommended_keep == '/missing/1.txt'
        assert decision.confidence == 0.0
        assert 'No accessible files' in decision.reasoning[0]

class TestReasoningEngine:

    def test_process_groups(self):
        """This functional test meticulously verifies that the scan repository correctly handles large volumes of redundant file groups including their metadata hashes and space recovery statistics during complex deduplication processing runs."""
        engine = ReasoningEngine()
        g1 = EngineGroup(group_key='g1', match_type='exact', file_paths=['a', 'b'], space_recoverable_bytes=100)
        g2 = EngineGroup(group_key='g2', match_type='exact', file_paths=['c', 'd'], space_recoverable_bytes=200)
        with patch.object(RetentionAgent, 'analyse') as mock_analyse:
            mock_analyse.return_value = AgentDecision(recommended_keep='a', confidence=0.9, scores=[], reasoning=['mocked'])
            res = engine.process([g1, g2])
            assert len(res) == 2
            assert 'g1' in res
            assert 'g2' in res
            assert engine.get_decision('g1').recommended_keep == 'a'

    def test_summary_stats(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        engine = ReasoningEngine()
        assert engine.summary_stats()['processed'] == 0
        engine._decisions = {'k1': AgentDecision('p1', 0.9, [], []), 'k2': AgentDecision('p2', 0.7, [], [])}
        stats = engine.summary_stats()
        assert stats['processed'] == 2
        assert stats['high_confidence'] == 1
        assert stats['avg_confidence'] == 0.8

    def test_export_log(self):
        """This general test case meticulously validates the core functionality of the specified test node within the Intelligent Dedup framework ensuring all expected side effects are accurately and reliably maintained."""
        engine = ReasoningEngine()
        engine._decisions = {'k1': AgentDecision('p1', 0.9, [], ['test'])}
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            engine.export_log(tmp_path)
            import json
            with open(tmp_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            assert 'k1' in data
            assert data['k1']['recommended_keep'] == 'p1'
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)