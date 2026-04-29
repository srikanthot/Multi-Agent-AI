"""Tests for specificity-ambiguity detection — Tier 1 safety hardening.

Production failure pattern:
  User asks 'what tools are needed' (generic, no voltage/equipment named).
  Retrieved chunks contain content for 15 kV, 25 kV, 69 kV scenarios all
  mixed together.  The LLM picks the most "tool-list-shaped" chunk (the
  69 kV splice section) and answers with those specific tools.

  Field technician acts on the answer thinking it applies to their
  scenario — could be ordering wrong tools, attempting wrong procedure,
  working on wrong equipment.

After this fix:
  detect_specificity_ambiguity() scans chunks for voltage/equipment/state
  markers, compares against what the user's question named, and flags
  multi-specificity answers.  AgentRuntime then injects an explicit
  disambiguation instruction before the LLM generates, forcing it to
  list the options and ask rather than answer.
"""

import pytest

from app.agent_runtime.agent import (
    _equipment_classes_in_text,
    _voltage_buckets,
    detect_specificity_ambiguity,
)


def _chunk(content: str) -> dict:
    """Build a minimal chunk dict for testing."""
    return {
        "content": content,
        "source": "test.pdf",
        "score": 0.025,
        "reranker_score": 2.5,
    }


# ---------------------------------------------------------------------------
# Voltage extraction
# ---------------------------------------------------------------------------


class TestVoltageBuckets:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("for 15 kV transformer", {"15 kV"}),
            ("for 26.4 kV substation", {"26.4 kV"}),
            ("at 120 V residential", {"120 V"}),
            ("for 69 kV one-piece molded splice", {"69 kV"}),
            ("at 13.2 kV or 4.16 kV", {"13.2 kV", "4.16 kV"}),
            ("the 480 V switchboard", {"480 V"}),
            ("text with no voltage", set()),
            ("the customer", set()),
            ("Cat 4 PPE", set()),  # 'Cat 4' not voltage
        ],
    )
    def test_voltage_extraction(self, text, expected):
        assert _voltage_buckets(text) == expected

    def test_voltage_with_kilovolts_word(self):
        result = _voltage_buckets("at 26.4 kilovolts class")
        assert result == {"26.4 kV"}


# ---------------------------------------------------------------------------
# Equipment-class extraction
# ---------------------------------------------------------------------------


class TestEquipmentClasses:
    @pytest.mark.parametrize(
        "text,expected_subset",
        [
            ("a pad-mount transformer", {"pad-mount transformer"}),
            ("the pole-mount unit", {"pole-mount transformer"}),
            ("oil-filled switchgear", {"oil-filled"}),
            ("dry-type transformer", {"dry-type"}),
            ("SF6 circuit breaker", {"SF6 breaker"}),
            ("vacuum breaker installation", {"vacuum breaker"}),
            ("indoor switchgear", {"indoor"}),
            ("outdoor pad-mount", {"outdoor", "pad-mount transformer"}),
            ("energized work permit", {"energized"}),
            ("de-energized procedure", {"de-energized"}),
            ("single-phase residential", {"single-phase"}),
            ("three-phase commercial", {"three-phase"}),
            ("overhead service drop", {"overhead"}),
            ("underground service", {"underground"}),
            ("plain text without specifics", set()),
        ],
    )
    def test_class_extraction(self, text, expected_subset):
        out = _equipment_classes_in_text(text)
        assert expected_subset.issubset(out), (
            f"Expected at least {expected_subset} in {out} for {text!r}"
        )


# ---------------------------------------------------------------------------
# detect_specificity_ambiguity — the critical safety check
# ---------------------------------------------------------------------------


class TestVoltageAmbiguity:
    """When chunks span multiple voltages and the user didn't name one."""

    def test_three_voltages_unspecified_question_is_ambiguous(self):
        chunks = [
            _chunk("For 15 kV pad-mount transformer installation, the tools required are..."),
            _chunk("For 25 kV transformer installation, use the following torque values..."),
            _chunk("For 69 kV one-piece molded splice, special tools are needed..."),
        ]
        is_amb, block = detect_specificity_ambiguity("what tools are needed", chunks)
        assert is_amb is True
        assert "15 kV" in block
        assert "25 kV" in block
        assert "69 kV" in block
        assert "DO NOT pick one and answer" in block

    def test_user_specifies_voltage_not_ambiguous(self):
        chunks = [
            _chunk("For 15 kV transformer installation..."),
            _chunk("For 25 kV transformer installation..."),
            _chunk("For 69 kV transformer installation..."),
        ]
        # User said 25 kV — pick the 25 kV chunk and answer
        is_amb, _ = detect_specificity_ambiguity(
            "what tools are needed for 25 kV install", chunks,
        )
        assert is_amb is False

    def test_single_voltage_not_ambiguous(self):
        chunks = [
            _chunk("For 15 kV transformer installation, follow these steps..."),
            _chunk("Additional 15 kV procedures..."),
        ]
        is_amb, _ = detect_specificity_ambiguity("what tools are needed", chunks)
        assert is_amb is False


class TestEquipmentClassAmbiguity:
    """When chunks span conflicting equipment classes and user didn't pick one."""

    def test_pad_vs_pole_mount_ambiguous(self):
        chunks = [
            _chunk("For pad-mount transformer installation, dig a 2x2 ft pad..."),
            _chunk("For pole-mount transformer, climb to the top of the pole..."),
        ]
        is_amb, block = detect_specificity_ambiguity(
            "how do I install a transformer", chunks,
        )
        assert is_amb is True
        assert "pad-mount" in block.lower() or "pad-mount transformer" in block

    def test_indoor_vs_outdoor_ambiguous(self):
        chunks = [
            _chunk("For indoor switchgear, the clearance is 36 in."),
            _chunk("For outdoor switchgear, the clearance is 60 in."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "what is the clearance", chunks,
        )
        assert is_amb is True

    def test_energized_vs_deenergized_ambiguous(self):
        chunks = [
            _chunk("Energized work requires PPE category 4 and..."),
            _chunk("De-energized work requires lockout/tagout and..."),
        ]
        is_amb, block = detect_specificity_ambiguity(
            "what PPE is required", chunks,
        )
        assert is_amb is True
        assert "energized" in block.lower()

    def test_user_specifies_equipment_not_ambiguous(self):
        chunks = [
            _chunk("For pad-mount transformer..."),
            _chunk("For pole-mount transformer..."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "how do I install a pad-mount transformer", chunks,
        )
        assert is_amb is False


class TestNoAmbiguity:
    """Single-specificity content should never be flagged."""

    def test_empty_chunks_not_ambiguous(self):
        is_amb, _ = detect_specificity_ambiguity("any question", [])
        assert is_amb is False

    def test_single_topic_not_ambiguous(self):
        chunks = [
            _chunk("Cut-in cards are required before service connection."),
            _chunk("The cut-in card must be approved by the inspection authority."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "what is the cut-in card", chunks,
        )
        assert is_amb is False

    def test_one_voltage_one_equipment_not_ambiguous(self):
        chunks = [
            _chunk("For 15 kV pad-mount transformer install, do X..."),
            _chunk("For 15 kV pad-mount transformer maintenance, do Y..."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "what is the procedure", chunks,
        )
        assert is_amb is False


class TestProductionPattern:
    """Replicates the actual production failure observed during testing."""

    def test_tools_needed_with_mixed_voltages(self):
        """The exact scenario that broke during smoke-testing."""
        chunks = [
            _chunk(
                "Application for Wiring Inspection (form 432) is required "
                "before work is started by the customer. PSE&G must be notified "
                "through your Service Consultant."
            ),
            _chunk(
                "For installing a 69 kV one-piece molded splice (1,000 kcmil "
                "copper conductor XLPE insulation, W135500 Elastimold TC/S-3), "
                "the following special tools are needed: 1. Adjustable scoring "
                "knife. 2. Variable temperature electric heat gun..."
            ),
            _chunk(
                "For 25 kV pad-mount transformer installation, the required "
                "tools are: torque wrench rated for 35 ft-lbs..."
            ),
        ]
        is_amb, block = detect_specificity_ambiguity(
            "what tools are needed", chunks,
        )
        assert is_amb is True
        assert "DISAMBIGUATION REQUIRED" in block
        assert "wrong answer for a different scenario can cause injury" in block

    def test_general_service_question_with_voltage_chunks(self):
        chunks = [
            _chunk("Service connection requires a cut-in card."),
            _chunk("For 15 kV service drop installation..."),
            _chunk("For 25 kV service drop installation..."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "what is the procedure", chunks,
        )
        # 15 vs 25 kV span -> should be flagged
        assert is_amb is True
