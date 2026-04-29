"""Tests for Defect D — "yes" / "sure" routing after a bot question.

Production failure pattern:
  Bot: "Would you like the step-by-step procedure for this section or
       information on inspection frequency and components?"
  User: "yes"
  Bot: "You're welcome! Let me know if you have any other questions
       about the technical manuals."   <-- BUG

The bot's "you're welcome" canned response fired because the intent
classifier saw "yes" as an acknowledgement.  After this fix, the
classifier checks whether the prior bot message ended with '?' — if so,
"yes"/"sure"/"yep" route to the RAG pipeline so the bot continues the
offer it just made.
"""

import pytest

from app.agent_runtime.intent_classifier import (
    INTENT_ACKNOWLEDGEMENT,
    INTENT_TECHNICAL,
    _assistant_ended_with_question,
    classify_intent,
)


class TestAssistantEndedWithQuestion:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Would you like the step-by-step procedure?", True),
            ("Do you want the inspection frequency or the components list?", True),
            ("There are 5 steps. Want me to walk through them?", True),
            ("The procedure is on page 12.", False),
            ("Steps: 1. Inspect. 2. Test. 3. Document.", False),
            ("", False),
            ("?", True),
            ("Final answer.\n\nWould you like more detail?", True),
            ("Question mark in the middle? But ends with period.", False),
        ],
    )
    def test_detects_trailing_question_mark(self, text, expected):
        assert _assistant_ended_with_question(text) is expected


class TestYesAfterBotQuestion:
    """The exact production failure pattern."""

    def test_yes_after_bot_question_routes_to_rag(self):
        intent, canned = classify_intent(
            "yes",
            has_history=True,
            prior_assistant_msg=(
                "Would you like the step-by-step procedure for this section "
                "or information on inspection frequency and components?"
            ),
        )
        assert intent == INTENT_TECHNICAL
        assert canned is None

    @pytest.mark.parametrize(
        "user_input",
        ["yes", "yep", "yeah", "yup", "sure", "yes please", "go ahead", "please continue"],
    )
    def test_all_affirmatives_route_to_rag_when_bot_asked(self, user_input):
        intent, canned = classify_intent(
            user_input,
            has_history=True,
            prior_assistant_msg="Would you like more detail on this?",
        )
        assert intent == INTENT_TECHNICAL, (
            f"Expected RAG for {user_input!r} after bot question, got {intent}"
        )
        assert canned is None


class TestYesWithoutBotQuestion:
    """When the bot's prior turn was NOT a question, "yes" is a polite close."""

    def test_yes_after_non_question_is_acknowledgement(self):
        intent, canned = classify_intent(
            "yes",
            has_history=True,
            prior_assistant_msg=(
                "The cut-in card requirement is documented in section 1.2 of "
                "the electric service manual."
            ),
        )
        assert intent == INTENT_ACKNOWLEDGEMENT
        assert canned is not None and "welcome" in canned.lower()

    def test_yes_with_no_history_is_acknowledgement(self):
        intent, canned = classify_intent("yes", has_history=False, prior_assistant_msg="")
        assert intent == INTENT_ACKNOWLEDGEMENT
        assert canned is not None


class TestNegativesAlwaysAcknowledge:
    """No / nope always close, regardless of bot question."""

    @pytest.mark.parametrize("user_input", ["no", "nope", "no thanks", "no thank you", "nah"])
    @pytest.mark.parametrize(
        "prior",
        [
            "",
            "The procedure is on page 5.",
            "Would you like more detail?",
        ],
    )
    def test_negative_always_acknowledges(self, user_input, prior):
        intent, canned = classify_intent(
            user_input,
            has_history=bool(prior),
            prior_assistant_msg=prior,
        )
        assert intent == INTENT_ACKNOWLEDGEMENT
        assert canned is not None


class TestRegressionExistingAcknowledgements:
    """Regression — true acknowledgements ('thanks', 'bye') still close."""

    @pytest.mark.parametrize(
        "user_input",
        [
            "thanks", "thank you", "bye", "goodbye",
            "ok", "okay", "got it", "alright",
            "perfect", "great", "awesome",
        ],
    )
    @pytest.mark.parametrize(
        "prior",
        ["Would you like more detail?", "The answer is X."],
    )
    def test_true_ack_always_closes(self, user_input, prior):
        intent, canned = classify_intent(
            user_input,
            has_history=True,
            prior_assistant_msg=prior,
        )
        assert intent == INTENT_ACKNOWLEDGEMENT, (
            f"{user_input!r} after {prior!r} should still acknowledge"
        )


class TestBackwardCompatibility:
    """The new prior_assistant_msg parameter is optional. Callers that don't
    pass it must not break."""

    def test_classify_intent_without_prior_msg_arg(self):
        intent, _ = classify_intent("yes", has_history=False)
        assert intent == INTENT_ACKNOWLEDGEMENT

    def test_classify_intent_default_prior_msg_empty(self):
        intent, _ = classify_intent("yes", has_history=True)
        # No prior_assistant_msg => can't detect bot question => acknowledge
        assert intent == INTENT_ACKNOWLEDGEMENT
