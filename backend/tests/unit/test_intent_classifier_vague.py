"""Tests for intent_classifier vague-query detection — Ticket #3.

These tests cover the 9 C8_vague_or_underspecified failures from the golden
set, plus regression cases that must NOT be classified as vague.

Production failure pattern:
  Users ask short, implicit-reference questions like 'Can I install the meter
  here?' or 'What SCADA do I need?'. Without explicit equipment/voltage
  context, the bot retrieves the most generic chunks it can find and answers
  with broad info — which is unhelpful and confusing for field technicians.
  After this fix the bot asks a clarifying question instead.
"""

import pytest

from app.agent_runtime.intent_classifier import (
    INTENT_VAGUE_QUERY,
    classify_intent,
)


class TestImplicitVagueQuestions:
    """The 9 production C8 failures — each must trigger vague-query."""

    @pytest.mark.parametrize(
        "question",
        [
            # T091
            "Can I install the meter here?",
            # T092
            "Is this temp service okay?",
            # T093
            "Can I use this collar adapter?",
            # T094
            "Can the gas meter go inside?",
            # T095
            "Is this gas pipe size okay?",
            # T096
            "Can I put the appliance in the attic?",
            # T097
            "Is this substation design acceptable?",
            # T098
            "What SCADA do I need?",
            # T099
            "Can we install lighting there?",
            # T100
            "What breaker should I use?",
        ],
    )
    def test_c8_failure_now_classified_vague(self, question):
        intent, canned = classify_intent(question, has_history=False)
        assert intent == INTENT_VAGUE_QUERY, (
            f"Expected vague_query for {question!r}, got {intent}"
        )
        assert canned is not None, "vague_query must return canned response"


class TestImplicitVagueExtras:
    """Adjacent variations that should also trigger vague-query."""

    @pytest.mark.parametrize(
        "question",
        [
            "Can I install this here?",
            "Can we put it inside?",
            "Is this okay?",
            "Is this acceptable?",
            "Is that allowed?",
            "What wire do I need?",
            "What relay should I use?",
            "Where do I install it?",
            "Can the meter fit here?",
            "Can we install lighting outside?",
        ],
    )
    def test_short_implicit_reference_is_vague(self, question):
        intent, _ = classify_intent(question, has_history=False)
        assert intent == INTENT_VAGUE_QUERY, (
            f"Expected vague_query for {question!r}, got {intent}"
        )


class TestSpecificQuestionsNotVague:
    """REGRESSION: specific questions with named entities, voltages, or
    enough technical detail must NOT be classified as vague."""

    @pytest.mark.parametrize(
        "question",
        [
            "What is the procedure for installing a 15 kV pad-mount transformer?",
            "Can I install a 25 kV pad-mount transformer for residential service?",
            "What torque value is required for transformer bushing flange bolts?",
            "What are the PPE requirements for arc flash category 2?",
            "Tell me about CSST sizing tables",
            "What is the cut-in card for a new electric service?",
            "Explain the SCADA RTU dimensions for a 26.4 kV substation",
            "How do I perform an insulation resistance test on a transformer",
            "What is the standard outlet pressure from the PSE&G gas meter?",
            "Describe the procedure for purging gas piping",
            "What does PSEG need before they will connect the electric service?",
        ],
    )
    def test_specific_question_not_vague(self, question):
        intent, _ = classify_intent(question, has_history=False)
        assert intent != INTENT_VAGUE_QUERY, (
            f"Specific question {question!r} was incorrectly classified as vague"
        )


class TestVagueOnlyFiresWithoutHistory:
    """When inside an active conversation, even short or vague-looking
    questions should proceed to RAG because they have prior context."""

    @pytest.mark.parametrize(
        "question",
        [
            "Can I install the meter here?",
            "Is this temp service okay?",
            "What SCADA do I need?",
            "What breaker should I use?",
            "Can we install lighting there?",
        ],
    )
    def test_vague_question_with_history_passes_through(self, question):
        intent, canned = classify_intent(question, has_history=True)
        assert intent != INTENT_VAGUE_QUERY, (
            f"With history, {question!r} should not be flagged vague — "
            f"the rewriter handles the implicit reference"
        )


class TestExistingVaguePatterns:
    """Original vague patterns must still work — regression for existing
    behaviour."""

    @pytest.mark.parametrize(
        "question",
        [
            "what about the procedure",
            "tell me about the steps",
            "safety",
            "maintenance",
            "the procedure",
            "equipment",
            "regulations",
            "how to",
            "what to do",
        ],
    )
    def test_original_patterns_still_match(self, question):
        intent, _ = classify_intent(question, has_history=False)
        assert intent == INTENT_VAGUE_QUERY, (
            f"Original pattern {question!r} no longer matches"
        )
