"""Tests for query_rewriter._is_already_standalone — heuristic that decides
whether a question already contains enough context to be used as-is for retrieval.

Each test documents the EXPECTED behaviour. Tests marked @pytest.mark.fix_C
exercise behaviour that the current code gets wrong and that the topic-switch
fix is supposed to correct.
"""

import pytest

from app.agent_runtime.query_rewriter import _is_already_standalone


# ---------------------------------------------------------------------------
# CURRENT BEHAVIOUR — these should pass on both old and new code.
# ---------------------------------------------------------------------------


class TestStandaloneShortQuestionsCurrent:
    """Short questions are forced through the rewriter under the current rule."""

    def test_one_word_question_is_not_standalone(self):
        assert _is_already_standalone("specifications") is False

    def test_two_word_question_is_not_standalone(self):
        assert _is_already_standalone("the procedure") is False

    def test_three_word_question_is_not_standalone(self):
        assert _is_already_standalone("what about it") is False

    def test_bare_followup_is_not_standalone(self):
        assert _is_already_standalone("explain more") is False

    def test_anaphora_only_is_not_standalone(self):
        assert _is_already_standalone("the same") is False


class TestStandaloneAnaphoraDetection:
    """Anaphora markers force rewriting regardless of length."""

    @pytest.mark.parametrize(
        "question",
        [
            "tell me more about this transformer maintenance procedure",
            "what about that 15 kV pad-mount installation",
            "explain those switching procedures in more detail",
            "the above mentioned procedure for cable splicing",
            "as you mentioned, what is the torque value",
            "you said earlier the fault current was 25 kA",
            "the same thing for outdoor switchgear assemblies",
            "from the previous discussion about transformers",
            "for that 25 kV bushing, what is the inspection frequency",
            "in that earlier procedure for grounding",
            "from before, what was the recommended PPE",
            "as you described earlier in this conversation",
            "the last one you mentioned about meter testing",
            "the one you described for transformer oil",
            "what you told me about the relay calibration",
            "like you said before about substation grounding",
        ],
    )
    def test_long_question_with_context_marker_needs_rewrite(self, question):
        assert _is_already_standalone(question) is False, (
            f"Question with anaphora should be rewritten: {question!r}"
        )


class TestStandaloneBackToAnaphora:
    """'back to' / 'going back to' / 'returning to' are anaphoric phrases
    users employ to revisit a prior topic. After Ticket #2 these are
    detected as needing a rewrite even though they look topical."""

    @pytest.mark.parametrize(
        "question",
        [
            "back to transformer maintenance, how often",
            "going back to GDS, who owns it",
            "returning to that previous question",
            "coming back to arc flash hazards, what PPE",
            "back to the 15 kV install, what tools",
            "let's go back to switching procedures",
            "lets return to that earlier topic",
            "back to my first question",
        ],
    )
    def test_back_to_phrasing_triggers_rewrite(self, question):
        assert _is_already_standalone(question) is False, (
            f"'back to' anaphora must trigger the rewriter: {question!r}"
        )


class TestStandaloneClearlySelfContainedQuestions:
    """Long questions with no anaphora and clear technical scope are standalone."""

    @pytest.mark.parametrize(
        "question",
        [
            "what is the recommended torque value for 15 kV transformer bushings during installation",
            "how do I perform an insulation resistance test on a pad-mount transformer",
            "what are the safety requirements for working on energized 25 kV switchgear",
            "describe the procedure for testing oil dielectric strength in distribution transformers",
            "what PPE is required when performing arc flash analysis on indoor switchgear",
            "list the steps for commissioning a new 4 kV substation feeder breaker",
            "what are the maintenance intervals for SF6 circuit breakers in distribution substations",
            "explain the grounding requirements for pole-mounted distribution transformers below 35 kV",
            "what is the procedure for replacing a load tap changer on a 138 kV power transformer",
            "describe the lockout tagout requirements for working on 13 kV underground residential distribution",
        ],
    )
    def test_long_specific_question_is_standalone(self, question):
        assert _is_already_standalone(question) is True


# ---------------------------------------------------------------------------
# EXPECTED BEHAVIOUR AFTER FIX C — topic-switch pivots that introduce a new
# named entity should be treated as standalone even if short. The current
# code returns False for all of these because of the ≤12 word cutoff.
# ---------------------------------------------------------------------------


class TestStandaloneTopicSwitchAfterFix:
    """After Fix C: a short question that introduces a named technical entity
    with no anaphora should be treated as standalone, so retrieval runs on the
    user's actual words rather than a context-blended rewrite."""

    @pytest.mark.parametrize(
        "question",
        [
            "tell me about Vibratium",
            "what is GDS",
            "explain NESC compliance",
            "describe SF6 breakers",
            "what is OSHA 1910.269",
            "tell me about IEEE 1584",
            "explain dielectric strength testing",
            "what is partial discharge",
        ],
    )
    @pytest.mark.fix_C
    def test_short_question_with_named_entity_should_be_standalone(self, question):
        assert _is_already_standalone(question) is True, (
            f"After Fix C, short topic-switch with named entity must be standalone: {question!r}"
        )


# ---------------------------------------------------------------------------
# Boundary / edge cases
# ---------------------------------------------------------------------------


class TestStandaloneEdgeCases:
    def test_empty_string_is_not_standalone(self):
        assert _is_already_standalone("") is False

    def test_whitespace_only_is_not_standalone(self):
        assert _is_already_standalone("   \n\t  ") is False

    def test_punctuation_only_is_not_standalone(self):
        assert _is_already_standalone("???") is False

    def test_exactly_twelve_words_old_rule(self):
        # "one two three four five six seven eight nine ten eleven twelve"
        twelve_word_q = (
            "what is the recommended torque value for fifteen kilovolt transformer bushings now"
        )
        # Should be considered standalone by length under the new rule
        # (no anaphora, has specific technical nouns).
        assert _is_already_standalone(twelve_word_q) is True

    def test_thirteen_words_no_anaphora(self):
        q = (
            "what is the recommended torque value for fifteen kilovolt transformer bushings during installation"
        )
        assert _is_already_standalone(q) is True

    def test_case_insensitivity(self):
        q1 = "what is the procedure for inspecting bushings on indoor switchgear"
        q2 = q1.upper()
        assert _is_already_standalone(q1) == _is_already_standalone(q2)

    def test_leading_trailing_whitespace(self):
        q = "   what is the procedure for inspecting bushings on indoor switchgear   "
        assert _is_already_standalone(q) is True
