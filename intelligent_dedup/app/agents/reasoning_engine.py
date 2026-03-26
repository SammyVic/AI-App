"""
=============================================================================
app/agents/reasoning_engine.py
=============================================================================
Batch-processes all duplicate groups through RetentionAgent and builds an
aggregate reasoning log. Exposes results for UI consumption and JSON export.
=============================================================================
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.agents.retention_agent import AgentDecision, RetentionAgent
from app.engine.deduplicator import DuplicateGroup

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Runs RetentionAgent over all duplicate groups and produces recommendations.

    Usage:
        engine = ReasoningEngine()
        decisions = engine.process(groups)
        engine.export_log("report.json")
    """

    def __init__(self) -> None:
        self._agent = RetentionAgent()
        self._decisions: dict[str, AgentDecision] = {}  # group_key -> decision

    def process(
        self,
        groups: list[DuplicateGroup],
        on_progress: Optional[callable] = None,
    ) -> dict[str, AgentDecision]:
        """
        Analyse all groups. Returns mapping of group_key -> AgentDecision.
        """
        self._decisions.clear()
        total = len(groups)
        for i, group in enumerate(groups):
            if not group.file_paths:
                continue
            try:
                decision = self._agent.analyse(group.file_paths)
                self._decisions[group.group_key] = decision
            except Exception as exc:
                logger.error("Agent failed for group %r: %s", group.group_key, exc)
            if on_progress:
                on_progress(i + 1, total)
        logger.info("ReasoningEngine: processed %d groups.", len(self._decisions))
        return self._decisions

    def get_recommendations(self) -> list[AgentDecision]:
        """Return all agent decisions sorted by confidence descending."""
        return sorted(self._decisions.values(), key=lambda d: -d.confidence)

    def get_decision(self, group_key: str) -> Optional[AgentDecision]:
        return self._decisions.get(group_key)

    def export_log(self, path: str) -> None:
        """Serialise all decisions to a human-readable JSON file."""
        data = {
            key: decision.to_dict()
            for key, decision in self._decisions.items()
        }
        try:
            Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            logger.info("Reasoning log exported to %r.", path)
        except OSError as exc:
            logger.error("Failed to export reasoning log to %r: %s", path, exc)

    def summary_stats(self) -> dict:
        """Statistics for the ViewModel stats panel."""
        decisions = list(self._decisions.values())
        if not decisions:
            return {"processed": 0, "avg_confidence": 0.0, "high_confidence": 0}
        confs = [d.confidence for d in decisions]
        return {
            "processed": len(decisions),
            "avg_confidence": round(sum(confs) / len(confs), 3),
            "high_confidence": sum(1 for c in confs if c >= 0.8),
        }
