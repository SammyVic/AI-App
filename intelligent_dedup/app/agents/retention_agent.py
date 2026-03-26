"""
=============================================================================
app/agents/retention_agent.py
=============================================================================
Local GenAI Agent that autonomously scores which file to KEEP within a
duplicate cluster, providing a transparent JSON reasoning log.

No external LLM calls. All decision-making is rule-based and auditable.
Each heuristic produces a score [0.0, 1.0]; a weighted sum determines the
recommendation. The full score breakdown is exposed to the UI.
=============================================================================
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Copy-marker patterns — files matching these are likely the "less canonical"
# ---------------------------------------------------------------------------
_COPY_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bcopy( of)?\b",
        r"\(copy\)",
        r"_bak\b",
        r"_backup\b",
        r"\(\d+\)$",     # e.g. "file (2).pdf"
        r" \d+\.\w+$",   # e.g. "file 2.jpg"
        r"~\$",          # MS Office temp
    ]
]

# Canonical folder names — prefer files inside these
_CANONICAL_FOLDER_KEYWORDS: frozenset[str] = frozenset({
    "documents", "doc", "projects", "work", "source", "originals",
    "masters", "archive", "assets", "library",
})

# Non-canonical / temporary paths — penalised
_TEMP_FOLDER_KEYWORDS: frozenset[str] = frozenset({
    "temp", "tmp", "cache", "downloads", "desktop", "appdata",
    "recycle", "trash", "backup", "old", "bak",
})

# Scoring weights (must sum to 1.0)
_WEIGHTS: dict[str, float] = {
    "location":   0.25,
    "timestamp":  0.20,
    "filename":   0.25,
    "depth":      0.15,
    "size_median":0.15,
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class AgentScore:
    """Detailed scoring for one candidate file within a duplicate group."""
    path: str
    total_score: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)   # human-readable notes


@dataclass
class AgentDecision:
    """
    Complete recommendation for one duplicate group.
    Exposed to the ViewModel and serialised to JSON for the reasoning log.
    """
    recommended_keep: str
    confidence: float                        # [0.0, 1.0]
    scores: list[AgentScore]
    reasoning: list[str]                     # ordered explanation lines

    def to_dict(self) -> dict:
        return {
            "recommended_keep": self.recommended_keep,
            "confidence": round(self.confidence, 4),
            "scores": [
                {
                    "path": s.path,
                    "total_score": round(s.total_score, 4),
                    "breakdown": {k: round(v, 4) for k, v in s.breakdown.items()},
                    "flags": s.flags,
                }
                for s in self.scores
            ],
            "reasoning": self.reasoning,
        }


# ---------------------------------------------------------------------------
# RetentionAgent
# ---------------------------------------------------------------------------

class RetentionAgent:
    """
    Analyses a duplicate group and returns an AgentDecision.

    Usage:
        agent = RetentionAgent()
        decision = agent.analyse(["C:/orig/file.txt", "C:/tmp/file.txt"])
    """

    def analyse(self, file_paths: list[str]) -> AgentDecision:
        """
        Score each candidate and return a ranked recommendation.
        """
        if not file_paths:
            raise ValueError("file_paths must not be empty.")

        # Gather metadata for all candidates
        candidates: list[dict] = []
        for path in file_paths:
            meta = self._gather_metadata(path)
            candidates.append(meta)

        # Filter out candidates with failed stat (file gone / inaccessible)
        valid = [c for c in candidates if c.get("exists")]
        if not valid:
            logger.warning("No accessible files in group — returning first path.")
            return self._fallback_decision(file_paths)

        # Compute individual heuristic scores
        sizes = [c["size"] for c in valid]
        median_size = float(sorted(sizes)[len(sizes) // 2])
        mtimes = [c["mtime"] for c in valid]
        max_mtime = max(mtimes) if mtimes else 0.0
        min_depth = min(c["depth"] for c in valid)

        scores: list[AgentScore] = []
        for meta in valid:
            score = AgentScore(path=meta["path"])
            bd: dict[str, float] = {}

            # 1. Location score: canonical > temp
            loc = self._location_score(meta["path"])
            bd["location"] = loc
            if loc > 0.7:
                score.flags.append("✅ Canonical directory")
            elif loc < 0.3:
                score.flags.append("⚠️ Temporary/backup directory")

            # 2. Timestamp score: prefer most recently modified
            if max_mtime > 0:
                bd["timestamp"] = meta["mtime"] / max_mtime
            else:
                bd["timestamp"] = 0.5
            if bd["timestamp"] > 0.95:
                score.flags.append("🕐 Most recently modified")

            # 3. Filename score: penalise copy-marker patterns
            fn_score = self._filename_score(meta["filename"])
            bd["filename"] = fn_score
            if fn_score < 0.5:
                score.flags.append("📋 Filename suggests copy/backup")

            # 4. Depth score: prefer shallower paths (closer to root)
            if meta["depth"] == min_depth:
                bd["depth"] = 1.0
                score.flags.append("📁 Shallowest path (likely canonical location)")
            else:
                bd["depth"] = min_depth / max(meta["depth"], 1)

            # 5. Size median score: prefer files closest to group median size
            if median_size > 0:
                ratio = meta["size"] / median_size
                bd["size_median"] = 1.0 - abs(1.0 - ratio)
                bd["size_median"] = max(0.0, bd["size_median"])
            else:
                bd["size_median"] = 0.5

            # Weighted total
            score.breakdown = bd
            score.total_score = sum(
                _WEIGHTS[k] * bd.get(k, 0.0) for k in _WEIGHTS
            )
            scores.append(score)

        # Sort descending by total score
        scores.sort(key=lambda s: s.total_score, reverse=True)
        winner = scores[0]
        second = scores[1] if len(scores) > 1 else None

        # Confidence = score gap normalised
        if second:
            gap = winner.total_score - second.total_score
            confidence = min(1.0, 0.5 + gap * 2)
        else:
            confidence = 1.0

        reasoning = self._build_reasoning(winner, scores)

        return AgentDecision(
            recommended_keep=winner.path,
            confidence=round(confidence, 4),
            scores=scores,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    # Heuristics
    # ------------------------------------------------------------------

    def _location_score(self, path: str) -> float:
        parts = set(Path(path).parts)
        lower_parts = {p.lower() for p in parts}
        if lower_parts & _CANONICAL_FOLDER_KEYWORDS:
            return 1.0
        if lower_parts & _TEMP_FOLDER_KEYWORDS:
            return 0.0
        return 0.5

    def _filename_score(self, filename: str) -> float:
        for pattern in _COPY_PATTERNS:
            if pattern.search(os.path.splitext(filename)[0]):
                return 0.1
        return 1.0

    def _gather_metadata(self, path: str) -> dict:
        meta: dict = {"path": path, "exists": False}
        try:
            stat = os.stat(path)
            meta.update({
                "exists": True,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "depth": len(Path(path).parts),
                "filename": os.path.basename(path),
            })
        except PermissionError as exc:
            logger.warning("Agent: permission error on %r: %s", path, exc)
        except OSError as exc:
            logger.warning("Agent: OS error on %r: %s", path, exc)
        return meta

    def _build_reasoning(self, winner: AgentScore, all_scores: list[AgentScore]) -> list[str]:
        lines = [
            f"🏆 Recommended: {winner.path}",
            f"   Total score: {winner.total_score:.3f}",
            "   Score breakdown:",
        ]
        for dim, val in winner.breakdown.items():
            lines.append(f"     {dim}: {val:.3f} (weight {_WEIGHTS.get(dim, 0):.2f})")
        for flag in winner.flags:
            lines.append(f"   {flag}")
        lines.append("")
        lines.append("📊 All candidates ranked:")
        for rank, s in enumerate(all_scores, start=1):
            lines.append(f"   {rank}. Score {s.total_score:.3f} — {s.path}")
        return lines

    def _fallback_decision(self, paths: list[str]) -> AgentDecision:
        return AgentDecision(
            recommended_keep=paths[0],
            confidence=0.0,
            scores=[AgentScore(path=p) for p in paths],
            reasoning=["⚠️ No accessible files found; returning first entry as default."],
        )
