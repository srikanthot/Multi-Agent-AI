"""Tests for the Path B action-seeking guard added in Round 6.

Production over-fire risk identified during audit:
  Path B (generic Q + specific chunks => disambiguate) was firing on
  definitional questions like "What is PSEG?" when chunks happened to
  mention voltages. Bot would over-clarify when user just wanted a
  definition.

Round 6 adds an action-seeking guard:
  Path B fires ONLY when the question is action-seeking (asks for a
  procedure, value, tool list, spec, etc.) AND not definitional.
"""

import pytest

from app.agent_runtime.agent import (
    _is_action_seeking_question,
    detect_specificity_ambiguity,
)


def _chunk(content: str) -> dict:
    return {
        "content": content,
        "source": "test.pdf",
        "score": 0.025,
        "reranker_score": 2.5,
    }


# ---------------------------------------------------------------------------
# _is_action_seeking_question
# ---------------------------------------------------------------------------


class TestActionSeekingDetection:
    @pytest.mark.parametrize(
        "question",
        [
            "what tools are needed",
            "what is the procedure",
            "what torque value should I use",
            "what are the steps",
            "what is the clearance",
            "what spec applies",
            "how do I install the meter",
            "tell me the depth requirement",
            "what is the minimum clearance",
            "how do I test this",
            "what is the torque value",
            "give me the procedure",
            "what tools",
            "what specifications apply",
        ],
    )
    def test_action_seeking_returns_true(self, question):
        assert _is_action_seeking_question(question) is True


class TestDefinitionalDetection:
    @pytest.mark.parametrize(
        "question",
        [
            "What is PSEG?",
            "What's PSEG?",
            "Who is PSEG?",
            "Explain PSEG",
            "Describe the company",
            "Tell me about PSEG",
            "Tell me more about utilities",
            "What does PSEG mean?",
            "What is the meaning of utility?",
            "Definition of substation",
        ],
    )
    def test_definitional_returns_false(self, question):
        assert _is_action_seeking_question(question) is False


class TestEdgeCases:
    def test_empty_question_not_action_seeking(self):
        assert _is_action_seeking_question("") is False

    def test_pure_noun_not_action_seeking(self):
        # Single noun without action verb or seeking word
        assert _is_action_seeking_question("PSEG") is False

    def test_action_word_in_definitional_question_still_action_seeking(self):
        """Documented behaviour: any action-seeking word makes the question
        action-seeking. Trade-off: 'What is a tools manual?' is action-
        seeking by this rule. In practice this rarely triggers because
        such phrasing is uncommon, and Path B still requires generic-Q +
        specific-chunks to fire.
        """
        assert _is_action_seeking_question("What is a tools manual?") is True


# ---------------------------------------------------------------------------
# detect_specificity_ambiguity — Path B with the action-seeking guard
# ---------------------------------------------------------------------------


class TestPathBOverFireGuard:
    """Definitional questions must NOT trigger Path B even if chunks have specs."""

    def test_what_is_pseg_does_not_disambiguate(self):
        """The audit-identified over-fire case."""
        chunks = [
            _chunk(
                "PSEG (Public Service Enterprise Group) is a New Jersey utility "
                "that operates equipment at 13.8 kV, 26.4 kV and 69 kV."
            ),
            _chunk(
                "The pad-mount transformer is a common service-entrance device."
            ),
        ]
        is_amb, _ = detect_specificity_ambiguity("What is PSEG?", chunks)
        assert is_amb is False, (
            "Definitional question must NOT trigger Path B — the user "
            "wants a definition, not a clarification dialog"
        )

    def test_describe_substation_does_not_disambiguate(self):
        chunks = [
            _chunk(
                "A substation is an installation that operates at 26.4 kV "
                "and contains pad-mount transformers."
            ),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "Describe a substation", chunks,
        )
        assert is_amb is False

    def test_tell_me_about_x_does_not_disambiguate(self):
        chunks = [
            _chunk(
                "Cut-in cards are required for service connection. "
                "Common ratings include 15 kV, 25 kV systems."
            ),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "Tell me about cut-in cards", chunks,
        )
        assert is_amb is False


class TestPathBStillFiresForActionSeeking:
    """Action-seeking questions still trigger Path B (regression guard)."""

    def test_what_tools_with_voltage_chunks_disambiguates(self):
        """The original production failure — must still fire."""
        chunks = [
            _chunk("Service connection prose..."),
            _chunk(
                "For 69 kV one-piece molded splice, the following tools are "
                "needed: scoring knife, heat gun..."
            ),
        ]
        is_amb, block = detect_specificity_ambiguity(
            "What tools are needed?", chunks,
        )
        assert is_amb is True, "Action-seeking Q + voltage chunks must still disambiguate"
        assert "69 kV" in block

    def test_torque_value_question_disambiguates(self):
        """'what is the torque value' is action-seeking ('torque', 'value')
        and chunks span multiple voltages -> Path A fires (multi-voltage)."""
        chunks = [
            _chunk("For 15 kV, torque is 35 ft-lbs..."),
            _chunk("For 25 kV, torque is 50 ft-lbs..."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "what is the torque value?", chunks,
        )
        assert is_amb is True

    def test_how_do_i_install_disambiguates(self):
        chunks = [
            _chunk("For pad-mount transformer install..."),
            _chunk("For pole-mount transformer install..."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "how do I install the transformer?", chunks,
        )
        # "pad-mount" vs "pole-mount" -> Path A (multi-equipment) fires.
        # Path A doesn't depend on action-seeking, so this works regardless.
        assert is_amb is True

    def test_what_is_procedure_disambiguates(self):
        """'What is the procedure' — definitional opener but action word.

        Documented behaviour: definitional opener wins, no disambiguation.
        However Path A still fires if chunks span multiple voltages.
        """
        chunks_path_a = [
            _chunk("For 15 kV procedure..."),
            _chunk("For 25 kV procedure..."),
        ]
        is_amb, _ = detect_specificity_ambiguity(
            "what is the procedure?", chunks_path_a,
        )
        # Path A (2+ voltages, q has none of them) fires regardless of
        # the action-seeking guard
        assert is_amb is True
