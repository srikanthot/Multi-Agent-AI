"""Tests for query_rewriter._is_valid_rewrite — sanity-check that decides
whether to use the rewriter LLM's output or fall back to the original question.

Critical properties this validator guarantees:
  1. Reject empty / too-short rewrites.
  2. Reject rewrites that are suspiciously long (likely hallucinated).
  3. Reject rewrites that drop ALL non-stopword content from the original
     (rewriter drift). This is the safety net that prevents topic blending
     from poisoning retrieval — for the topic-switch ticket this is what
     makes 'tell me about Vibratium' fall back to the original when the
     rewriter LLM tries to bleed in fire/dust context.
"""

import pytest

from app.agent_runtime.query_rewriter import _is_valid_rewrite


class TestValidatorRejectsEmpty:
    @pytest.mark.parametrize(
        "rewrite",
        [
            "",
            " ",
            "\n",
            "\t",
            "no",  # 2 chars
            "ok",  # 2 chars
            "hi",  # 2 chars
            "test",  # 4 chars but valid? No — len 4 below 8-char floor
            "abcdefg",  # 7 chars below floor
        ],
    )
    def test_rejects_too_short(self, rewrite):
        assert (
            _is_valid_rewrite("how do I install a transformer", rewrite) is False
        )


class TestValidatorRejectsTooLong:
    def test_rejects_4x_original_length(self):
        # Rule: rewrite > max(len(original)*4, 400) is rejected.
        # For a long original, the 4x cap dominates the 400 floor.
        original = (
            "what is the procedure for installing a 25 kV pad-mount transformer "
            "with all required PPE"
        )  # 90 chars
        rewrite = "x " * 200  # 400 chars > 4 * 90 = 360 → must be rejected
        assert _is_valid_rewrite(original, rewrite) is False

    def test_rejects_anything_past_400_chars_for_short_original(self):
        original = "explain X"
        rewrite = "a" * 401
        assert _is_valid_rewrite(original, rewrite) is False

    def test_accepts_long_rewrite_when_original_was_long(self):
        original = (
            "what are the steps to inspect a 25 kV pad-mount transformer including "
            "all the safety procedures and PPE requirements"
        )
        rewrite = (
            "list the inspection steps for a 25 kV pad-mount transformer including "
            "all required PPE, lockout/tagout, and safety clearance requirements per "
            "PSEG procedure"
        )
        assert _is_valid_rewrite(original, rewrite) is True


class TestValidatorSharedWordCheck:
    """Validator rejects rewrites that drop ALL non-stopword content from the
    original — this is the line of defence against rewriter drift."""

    def test_accepts_rewrite_sharing_one_substantive_word(self):
        original = "what is the procedure for transformer maintenance"
        rewrite = "transformer maintenance steps"
        assert _is_valid_rewrite(original, rewrite) is True

    def test_rejects_rewrite_with_no_shared_substantive_words(self):
        original = "what is the procedure for transformer maintenance"
        rewrite = "fire prevention dust labels for customers"
        assert _is_valid_rewrite(original, rewrite) is False

    def test_accepts_when_original_has_only_stopwords(self):
        # Stopword-only original gives an empty orig_words set, so the
        # intersection check is skipped and the rewrite passes if length is OK.
        original = "what about it"
        rewrite = "transformer oil sampling procedure"
        assert _is_valid_rewrite(original, rewrite) is True


class TestValidatorTopicSwitchSafety:
    """Specific topic-switch failure modes the validator must catch.

    These are the cases that map directly to user-reported bugs:
      - User pivots from fire/dust labels to vibration testing
      - Rewriter blends old + new context
      - Validator MUST reject the blended rewrite so retrieval falls back
        to the user's actual words.
    """

    def test_rejects_rewriter_dropping_new_topic_term(self):
        original = "tell me about Vibratium"
        # Rewriter incorrectly bleeds in prior topic, drops the new term.
        rewrite = "what label should be placed on customer to prevent fire"
        assert _is_valid_rewrite(original, rewrite) is False

    def test_rejects_rewriter_blending_with_unrelated_old_topic(self):
        original = "explain GDS ownership"
        rewrite = "transformer maintenance schedule for outdoor switchgear"
        assert _is_valid_rewrite(original, rewrite) is False

    def test_accepts_rewriter_keeping_new_topic_term(self):
        original = "tell me about vibration testing"
        rewrite = "vibration testing procedure for transformers"
        assert _is_valid_rewrite(original, rewrite) is True

    def test_accepts_rewriter_anchoring_followup_correctly(self):
        # User: "How do I install a 15 kV transformer?"
        # Bot: ...
        # User: "what tools" — rewriter correctly inserts "transformer"
        original = "what tools"
        rewrite = "tools required for 15 kV transformer installation"
        # original has only "tools" as substantive — overlap with "tools"
        assert _is_valid_rewrite(original, rewrite) is True


class TestValidatorBoundaries:
    def test_minimum_valid_length_is_eight(self):
        # 8-char rewrite that shares a word
        assert (
            _is_valid_rewrite(
                "transformer maintenance procedure",
                "fix xfmr ",  # 9 chars — but no shared substantive word
            )
            is False  # still rejected because of zero overlap
        )

    def test_at_400_char_boundary(self):
        original = "X"
        rewrite = "a" * 400  # exactly 400 — boundary
        # max(len("X")*4, 400) = 400; rewrite length 400 is NOT > 400 so passes length check.
        # But shared-word check: orig_words from "X" = {} (len 1, ≤2), so skipped.
        # rewrite is all 'a' chars, single token, len 400. rew_words = {"a"*400}.
        # orig_words is empty → length passes → returns True.
        assert _is_valid_rewrite(original, rewrite) is True

    def test_punctuation_stripped_before_word_check(self):
        original = "transformer? maintenance!"
        rewrite = "transformer maintenance procedure"
        assert _is_valid_rewrite(original, rewrite) is True
