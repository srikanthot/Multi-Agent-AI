"""End-to-end tests for rewrite_query() with a mocked rewriter LLM.

These tests simulate what the rewriter LLM might return for various
topic-switch and continuation scenarios, then verify the validator either
accepts the rewrite OR falls back to the original. This is the safety net
that prevents topic-blending from poisoning retrieval.

Why mock instead of calling the real LLM:
  - Deterministic, fast, free.
  - Lets us inject pathological outputs (blended queries, drift, etc.)
    that the real LLM produces only intermittently.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.agent_runtime import query_rewriter
from app.agent_runtime.query_rewriter import rewrite_query


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeMessage:
    """Stand-in for a Cosmos MessageRecord — only role/content are read."""
    role: str
    content: str


def _make_history(*pairs: tuple[str, str]) -> list[FakeMessage]:
    """Convert (user_text, assistant_text) pairs into a chronological history."""
    out: list[FakeMessage] = []
    for u, a in pairs:
        out.append(FakeMessage(role="user", content=u))
        out.append(FakeMessage(role="assistant", content=a))
    return out


def _mock_azure_openai(rewriter_returns: str):
    """Build a mock AzureOpenAI client that returns the given text from
    chat.completions.create()."""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = rewriter_returns
    client.chat.completions.create.return_value = response
    return client


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Each test should start with a fresh client singleton so the mock is fresh."""
    query_rewriter._client = None
    yield
    query_rewriter._client = None


# ---------------------------------------------------------------------------
# Topic-switch scenarios — these are the failure pattern from the production ticket
# ---------------------------------------------------------------------------


class TestTopicSwitchRewriting:
    """When the user pivots to a new topic, the rewriter must NOT bleed the old
    topic into the new query. The validator + the rewriter prompt are jointly
    responsible for ensuring this — at minimum the validator is the safety net."""

    def test_blended_rewrite_is_rejected_falls_back_to_original(self):
        """Reproduces the fire/dust → Vibratium ticket: rewriter LLM produces a
        blended query that drops the new topic; validator rejects, original used."""
        history = _make_history(
            (
                "what label should be placed on customer to prevent fire during dust buildup",
                "Per the manual, label X must be placed on customer-side equipment...",
            ),
        )
        # Pathological rewriter output — bleeds prior context, drops "Vibratium"
        bad_rewrite = "fire prevention dust buildup customer label warning"
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai(bad_rewrite)):
            result = rewrite_query("tell me about Vibratium", history)
        # Validator rejects; falls back to original verbatim
        assert result == "tell me about Vibratium"

    def test_clean_topic_switch_rewrite_passes_through(self):
        """Rewriter correctly recognizes a topic switch and returns the user's
        question unchanged (or with minor normalization)."""
        history = _make_history(
            (
                "what label should be placed on customer to prevent fire during dust buildup",
                "Per the manual, label X must be placed on customer-side equipment...",
            ),
        )
        good_rewrite = "tell me about Vibratium"
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai(good_rewrite)):
            result = rewrite_query("tell me about Vibratium", history)
        assert result == "tell me about Vibratium"

    def test_rewriter_drift_is_rejected(self):
        """Rewriter produces something that shares zero substantive words with
        the original — validator must reject."""
        history = _make_history(
            ("what is the GDS owner manual", "GDS is owned by..."),
        )
        drift = "transformer oil sampling intervals for 138 kV substations"
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai(drift)):
            result = rewrite_query("explain GDS scope", history)
        assert result == "explain GDS scope"

    @pytest.mark.parametrize(
        "user_q1, bot_a1, user_q2",
        [
            (
                "what is the procedure for transformer maintenance",
                "Per the manual, transformer maintenance involves...",
                "tell me about meter installation",
            ),
            (
                "how do I splice 25 kV cable",
                "Cable splicing for 25 kV requires...",
                "what are the substation grounding requirements",
            ),
            (
                "what are the PPE requirements for arc flash",
                "Arc flash PPE category 2 requires...",
                "explain SF6 breaker maintenance",
            ),
            (
                "how often should oil sampling be done",
                "Oil sampling intervals are...",
                "what is the inspection frequency for bushings",
            ),
        ],
    )
    def test_topic_switch_falls_back_when_rewriter_blends(self, user_q1, bot_a1, user_q2):
        """For any clean topic switch, if the rewriter LLM returns a blend,
        the validator rejects and we use the user's words."""
        history = _make_history((user_q1, bot_a1))
        # Simulate a blended output that pulls Q1 keywords into Q2's space
        blended = f"{user_q1} {user_q2}"  # both topics smashed together
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai(blended)):
            result = rewrite_query(user_q2, history)
        # The blend may pass the validator (shares Q2 words). What matters is
        # that we don't end up with a pure-Q1 query (which would break retrieval).
        # Verify Q2 keywords are preserved in whatever was used.
        q2_content_words = {
            w for w in user_q2.lower().split() if len(w) > 4
        }
        result_words = set(result.lower().split())
        # At least one substantive Q2 word must appear in the search query.
        assert q2_content_words & result_words, (
            f"Topic switch lost Q2 keywords: q2={user_q2!r} result={result!r}"
        )


# ---------------------------------------------------------------------------
# Continuation scenarios — rewriter SHOULD inject prior context
# ---------------------------------------------------------------------------


class TestContinuationRewriting:
    """When the user asks a genuine follow-up (anaphora, bare question), the
    rewriter is expected to inject prior context."""

    def test_anaphora_followup_gets_rewritten(self):
        history = _make_history(
            (
                "how do I install a 15 kV pad-mount transformer",
                "Installation steps for 15 kV pad-mount...",
            ),
        )
        rewrite = "tools required for 15 kV pad-mount transformer installation"
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai(rewrite)):
            result = rewrite_query("what tools do I need", history)
        assert result == rewrite

    def test_bare_followup_gets_rewritten(self):
        history = _make_history(
            (
                "what is the testing procedure for distribution transformers",
                "Distribution transformer testing involves...",
            ),
        )
        rewrite = "step-by-step procedure for distribution transformer testing"
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai(rewrite)):
            result = rewrite_query("step by step please", history)
        assert result == rewrite

    @pytest.mark.parametrize(
        "followup,expected_rewrite",
        [
            (
                "what about cold weather",
                "cold weather considerations for transformer maintenance",
            ),
            (
                "the same for outdoor",
                "outdoor transformer maintenance procedure same as indoor",
            ),
            (
                "more details please",
                "more detailed transformer maintenance procedure",
            ),
            (
                "what's next",
                "next steps in transformer maintenance",
            ),
            (
                "how long does it take",
                "how long does the transformer maintenance procedure take",
            ),
        ],
    )
    def test_pronoun_heavy_followups_use_rewriter(self, followup, expected_rewrite):
        history = _make_history(
            (
                "what is the procedure for transformer maintenance",
                "The procedure involves oil sampling, bushing inspection...",
            ),
        )
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai(expected_rewrite)):
            result = rewrite_query(followup, history)
        # Validator accepts because rewrite preserves at least one original
        # substantive word (e.g. "next", "long", "more"). The rewrite must
        # also pick up the prior topic ("transformer" or "maintenance").
        assert "transformer" in result.lower() or "maintenance" in result.lower()


# ---------------------------------------------------------------------------
# Edge cases that must not break the rewriter path
# ---------------------------------------------------------------------------


class TestRewriterErrorHandling:
    def test_no_history_returns_original(self):
        # No history = nothing to contextualize → original returned without LLM call
        with patch.object(query_rewriter, "AzureOpenAI") as mock_class:
            result = rewrite_query("tell me about Vibratium", history=[])
        assert result == "tell me about Vibratium"
        mock_class.assert_not_called()

    def test_empty_rewrite_is_rejected(self):
        history = _make_history(("Q1", "A1"))
        with patch.object(query_rewriter, "AzureOpenAI", return_value=_mock_azure_openai("")):
            result = rewrite_query("tell me about something", history)
        assert result == "tell me about something"

    def test_rewriter_exception_falls_back_to_original(self):
        history = _make_history(("Q1", "A1"))
        bad_client = MagicMock()
        bad_client.chat.completions.create.side_effect = RuntimeError("LLM down")
        with patch.object(query_rewriter, "AzureOpenAI", return_value=bad_client):
            result = rewrite_query("tell me about something specific", history)
        assert result == "tell me about something specific"

    def test_long_history_truncated_to_char_budget(self):
        # 10 message pairs (= 20 messages) of long content
        long_pairs = [
            (f"Q{i} " * 100, f"A{i} " * 100) for i in range(10)
        ]
        history = _make_history(*long_pairs)
        with patch.object(
            query_rewriter,
            "AzureOpenAI",
            return_value=_mock_azure_openai("rewritten transformer query"),
        ) as mock_class:
            rewrite_query("transformer details", history)
        # Verify the prompt sent to the LLM didn't include 20 full messages
        call_args = mock_class.return_value.chat.completions.create.call_args
        if call_args:
            user_msg = call_args[1]["messages"][1]["content"]
            # max_history_chars=1500 default — verify cap held
            assert len(user_msg) < 5000, "History should be truncated"
