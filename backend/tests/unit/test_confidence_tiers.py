"""Tests for the 3-tier confidence system (Defect A — cold zone false negatives).

Old behavior: binary gate at MIN_RERANKER_SCORE=1.8 — anything below was
refused with the canned 'no evidence' message, even when content existed
in the manual at score 1.5-1.7.

New behavior: 3 tiers
  HIGH   (avg >= 1.8 AND >= 2 chunks): normal answer
  MEDIUM (avg in [1.4, 1.8) OR <2 chunks but >= 1.4): proceed with
         'limited evidence' framing — LLM either answers with hedging
         or refuses based on whether the chunks actually contain the
         answer
  LOW    (avg < 1.4): refuse outright
"""

import pytest

from app.agent_runtime.agent import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    assess_confidence,
)


def _r(content: str, source: str, reranker: float) -> dict:
    return {
        "content": content,
        "source": source,
        "score": 0.025,
        "reranker_score": reranker,
    }


class TestHighTier:
    """HIGH: avg >= 1.8 AND >= 2 chunks. Normal answer flow."""

    def test_strong_avg_two_chunks_is_high(self):
        results = [_r("c1", "M1", 2.5), _r("c2", "M2", 2.0)]
        confidence, avg, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_HIGH
        assert pytest.approx(avg) == 2.25

    def test_just_above_threshold_is_high(self):
        results = [_r("c1", "M1", 1.85), _r("c2", "M2", 1.85)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_HIGH

    def test_many_strong_chunks_is_high(self):
        results = [_r(f"c{i}", "M1", 2.5) for i in range(7)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_HIGH


class TestMediumTier:
    """MEDIUM: borderline relevance. Proceed with hedging framing."""

    def test_borderline_avg_with_two_chunks_is_medium(self):
        results = [_r("c1", "M1", 1.5), _r("c2", "M2", 1.6)]
        confidence, avg, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_MEDIUM
        assert avg < 1.8
        assert avg >= 1.4

    def test_single_strong_chunk_is_medium(self):
        """Single chunk, even high-scoring, gets MEDIUM (corroboration needed)."""
        results = [_r("c1", "M1", 3.0)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_MEDIUM

    def test_single_borderline_chunk_is_medium(self):
        results = [_r("c1", "M1", 1.5)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_MEDIUM

    @pytest.mark.parametrize(
        "scores",
        [
            (1.5, 1.5),
            (1.6, 1.7),
            (1.4, 1.6),
            (1.7, 1.79),
        ],
    )
    def test_borderline_score_pairs_are_medium(self, scores):
        results = [_r("c1", "M1", scores[0]), _r("c2", "M2", scores[1])]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_MEDIUM


class TestLowTier:
    """LOW: avg < 1.4 (or 0 chunks). Refuse."""

    def test_no_chunks_is_low(self):
        confidence, _, _ = assess_confidence([])
        assert confidence == CONFIDENCE_LOW

    def test_weak_avg_is_low(self):
        results = [_r("c1", "M1", 1.0), _r("c2", "M2", 0.9)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_LOW

    def test_single_weak_chunk_is_low(self):
        results = [_r("c1", "M1", 1.0)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_LOW

    def test_very_weak_avg_is_low(self):
        results = [_r("c1", "M1", 0.5), _r("c2", "M2", 0.6)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_LOW


class TestBoundaries:
    """Exact threshold transitions — proves the math is right."""

    def test_avg_exactly_1_4_is_medium(self):
        results = [_r("c1", "M1", 1.4), _r("c2", "M2", 1.4)]
        confidence, avg, _ = assess_confidence(results)
        assert pytest.approx(avg) == 1.4
        assert confidence == CONFIDENCE_MEDIUM

    def test_avg_just_below_1_4_is_low(self):
        results = [_r("c1", "M1", 1.39), _r("c2", "M2", 1.39)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_LOW

    def test_avg_exactly_1_8_is_high(self):
        results = [_r("c1", "M1", 1.8), _r("c2", "M2", 1.8)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_HIGH

    def test_avg_just_below_1_8_is_medium(self):
        results = [_r("c1", "M1", 1.79), _r("c2", "M2", 1.79)]
        confidence, _, _ = assess_confidence(results)
        assert confidence == CONFIDENCE_MEDIUM


class TestProductionScenario:
    """Defect A — the production bug being fixed."""

    def test_cold_zone_borderline_now_proceeds_instead_of_refusing(self):
        """Old behaviour: refuse. New behaviour: MEDIUM (proceed with hedging).

        This is the production complaint: warm zone content scored 2.0+,
        cold zone scored ~1.6, gate refused cold zone with 'no evidence'
        even though content was in the manual.
        """
        cold_zone_results = [
            _r("Cold zone defined as ...", "winter_ops_manual.pdf", 1.6),
            _r("Cold zone procedures include ...", "winter_ops_manual.pdf", 1.55),
        ]
        confidence, _, _ = assess_confidence(cold_zone_results)
        assert confidence == CONFIDENCE_MEDIUM, (
            "Borderline cold-zone content should now go to MEDIUM, not LOW"
        )

    def test_warm_zone_strong_match_still_high(self):
        """Regression — warm zone scoring 2.0+ still gets HIGH tier."""
        warm_results = [
            _r("Warm zone procedures: ...", "summer_ops_manual.pdf", 2.5),
            _r("More warm zone info ...", "summer_ops_manual.pdf", 2.3),
        ]
        confidence, _, _ = assess_confidence(warm_results)
        assert confidence == CONFIDENCE_HIGH
