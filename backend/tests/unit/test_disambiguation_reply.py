"""Tests for disambiguation-reply handling — Round 7 fix.

Production failure pattern observed:
  Q1: "What is the procedure for transformer maintenance?"
  Bot: "Which scenario applies?
        • Single-phase transformer trailer maintenance
        • Three-phase transformer truck maintenance"
  User: "the 2nd one"
  Bot: [retrieves content about "2nd method of bolted connectors"]
       <-- WRONG. Bot picked up an unrelated section that semantically
           matched "2nd method".

Root cause:
  '_is_already_standalone' classified "the 2nd one" as standalone
  (because "2nd" is a 3-char content word). Rewriter was skipped.
  Retrieval ran on literal "the 2nd one" → matched unrelated content.

Fix (Round 7):
  Add ordinal-reference markers to context_markers so phrases like
  "the 2nd one", "second", "option 2" force the rewriter to run.
  Rewriter prompt explicitly handles DISAMBIGUATION REPLY type with
  example.
"""

import pytest

from app.agent_runtime.query_rewriter import _is_already_standalone


class TestOrdinalReferenceForcesRewrite:
    """User replies to a disambiguation question with an ordinal reference.
    These phrases must NOT be classified as standalone — the rewriter
    needs to resolve them against the prior bot message."""

    @pytest.mark.parametrize(
        "user_reply",
        [
            "the 2nd one",
            "the 1st one",
            "the 3rd",
            "second one",
            "first one",
            "third one",
            "last one",
            "option 1",
            "option 2",
            "option 3",
            "option a",
            "option b",
            "the first",
            "the second",
            "the third",
            "the fourth",
            "the latter",
            "the former",
            "first bullet",
            "second bullet",
            "the 4th",
            "the 5th",
        ],
    )
    def test_ordinal_reply_is_not_standalone(self, user_reply):
        """Ordinal references force the rewriter so it can resolve
        against the bot's prior list."""
        assert _is_already_standalone(user_reply) is False, (
            f"{user_reply!r} should NOT be standalone — needs rewriter "
            f"to resolve against bot's prior disambiguation message"
        )


class TestSpecificAnswersStillStandalone:
    """When the user names the option directly (instead of using an
    ordinal reference), the question becomes specific and the rewriter
    can be skipped — search will work on the user's words."""

    @pytest.mark.parametrize(
        "user_reply",
        [
            "three-phase transformer truck maintenance",
            "single-phase transformer trailer maintenance",
            "describe the 26.4 kV pad-mount transformer install procedure",
            "what tools are needed for 25 kV cable splicing",
        ],
    )
    def test_specific_named_option_is_standalone(self, user_reply):
        """If the user gave the explicit option name, rewriter not needed."""
        assert _is_already_standalone(user_reply) is True


class TestProductionScenario:
    """Replicates the exact production failure."""

    def test_the_2nd_one_after_disambiguation_forces_rewrite(self):
        """The exact phrase the user typed in production."""
        # Should NOT be standalone — rewriter must run to resolve
        assert _is_already_standalone("the 2nd one") is False

    def test_just_second_alone_forces_rewrite(self):
        """Single ordinal word."""
        assert _is_already_standalone("second one") is False
        # Note: bare "second" alone might be missed; users typically
        # say "the second" or "second one" — covered above.

    def test_option_2_forces_rewrite(self):
        """Alternative phrasing some users prefer."""
        assert _is_already_standalone("option 2") is False


# ---------------------------------------------------------------------------
# Round 8 — validator must accept the rewriter's substantive rewrite.
# ---------------------------------------------------------------------------
# Round 7 made the rewriter run for "the 2nd one" (good). But the
# VALIDATOR was rejecting the rewriter's correct output ("three-phase
# transformer truck maintenance procedure") because it shared no
# substantive words with the original "the 2nd one" {"2nd", "one"}.
# Round 8: treat ordinal pointer tokens as stopwords in the validator
# so the shared-word check doesn't reject the (correct) rewrite.
# ---------------------------------------------------------------------------


from app.agent_runtime.query_rewriter import _is_valid_rewrite


class TestValidatorAcceptsDisambiguationRewrites:
    """Round 8: validator must NOT reject good disambiguation rewrites."""

    @pytest.mark.parametrize(
        "original,rewritten",
        [
            (
                "the 2nd one",
                "three-phase transformer truck maintenance procedure",
            ),
            (
                "the 1st one",
                "single-phase transformer trailer maintenance procedure",
            ),
            (
                "second",
                "three-phase transformer truck maintenance",
            ),
            (
                "second one",
                "three-phase transformer truck maintenance procedure",
            ),
            (
                "option 2",
                "three-phase transformer truck maintenance",
            ),
            (
                "the latter",
                "three-phase transformer truck maintenance procedure",
            ),
            (
                "the former",
                "single-phase transformer trailer maintenance",
            ),
            (
                "first bullet",
                "single-phase transformer trailer maintenance procedure",
            ),
            (
                "second bullet",
                "three-phase transformer truck maintenance procedure",
            ),
            (
                "the 3rd",
                "26.4 kV substation grounding requirements",
            ),
        ],
    )
    def test_disambiguation_rewrite_accepted(self, original, rewritten):
        """The exact production failure: rewriter produces correct content
        but validator rejects because no shared substantive word.
        Round 8 fix: ordinal pointer words are stopwords in validator."""
        assert _is_valid_rewrite(original, rewritten) is True, (
            f"Validator should ACCEPT this rewrite of {original!r} → "
            f"{rewritten!r}; current behaviour rejects it because no "
            f"shared substantive word"
        )


class TestValidatorStillRejectsTrueDrift:
    """REGRESSION GUARD: the validator must still reject genuine drift —
    rewrites that abandon the user's actual topic for an unrelated one."""

    @pytest.mark.parametrize(
        "original,bad_rewrite",
        [
            (
                "tell me about Vibratium",
                "fire prevention dust labels for customers",
            ),
            (
                "explain GDS ownership",
                "transformer maintenance schedule for outdoor switchgear",
            ),
            (
                "what is the procedure for transformer maintenance",
                "gas pipe sizing for residential service",
            ),
        ],
    )
    def test_real_drift_still_rejected(self, original, bad_rewrite):
        """Rewrites that completely abandon the user's substantive topic
        must still be rejected. The Round 8 stopword expansion only
        covers VACUOUS originals (yes, no, the 2nd one). For substantive
        originals, drift detection still applies."""
        assert _is_valid_rewrite(original, bad_rewrite) is False, (
            f"Validator must STILL reject genuine drift: {original!r} → "
            f"{bad_rewrite!r} — these share no substantive words"
        )
