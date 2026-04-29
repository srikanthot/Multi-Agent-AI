"""Tests for Ticket #2 — long-distance anaphora and multi-topic disambiguation.

Two layers:
  1. rewrite_query() unit-level: given a longer history, does the rewriter's
     prompt actually contain it (governed by max_history_chars).
  2. agent.run_once / run_stream integration: does the runtime LOAD enough
     messages from Cosmos in the first place (governed by max_turns).



Production failure pattern:
  User asks Q1 about topic A, drifts through Q2-Q4 on topic B, then in Q5 asks
  'what about that earlier transformer thing'. The rewriter only sees the last
  4 messages — Q1 has slid out of the window — so the rewriter has no idea
  what the user is referring back to. After widening the window to 8 messages
  (= 4 Q&A pairs), Q1 stays visible and the rewriter can anchor correctly.

We test this by patching the rewriter LLM to verify what history it actually
receives. The mock captures the prompt sent to AzureOpenAI; we assert that
content from Q1 is present after widening (was absent before).
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from app.agent_runtime import query_rewriter
from app.agent_runtime.query_rewriter import rewrite_query


@dataclass
class FakeMessage:
    role: str
    content: str


def _build_long_history(*pairs: tuple[str, str]) -> list[FakeMessage]:
    out: list[FakeMessage] = []
    for u, a in pairs:
        out.append(FakeMessage(role="user", content=u))
        out.append(FakeMessage(role="assistant", content=a))
    return out


def _capture_rewriter_prompt(return_value: str = "rewritten query"):
    """Build a mock AzureOpenAI client that captures the messages it receives."""
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = return_value
    client.chat.completions.create.return_value = response
    return client


@pytest.fixture(autouse=True)
def _reset_singleton():
    query_rewriter._client = None
    yield
    query_rewriter._client = None


# ---------------------------------------------------------------------------
# Long-distance anaphora — Q1's topic must remain visible to the rewriter
# even after several intervening turns
# ---------------------------------------------------------------------------


class TestLongDistanceAnaphoraVisibility:
    """When the user references a topic from several turns back, the
    rewriter must be able to see it. With a 4-message window only the
    immediately preceding Q&A is visible — Q1 has slid out. With an 8-msg
    window (= 4 Q&A pairs), Q1 stays visible."""

    def test_q1_visible_after_three_intervening_turns(self):
        """Q1 about transformer, Q2-Q4 about cable, Q5 anaphoric to Q1.

        With max_turns=8, the rewriter prompt should contain content from Q1
        ('transformer maintenance').
        """
        history = _build_long_history(
            ("what is transformer maintenance", "Transformer maintenance procedures..."),
            ("now tell me about cable splicing for 25 kV", "Cable splicing involves..."),
            ("what tools for cable splicing", "Tools include..."),
            ("what about underground cables", "Underground cable considerations..."),
        )
        # 4 Q&A pairs = 8 messages. With current max_history_chars=1500 some
        # messages may be truncated, but the words 'transformer maintenance'
        # should be retained from the user's first question (40 chars).

        client = _capture_rewriter_prompt(
            return_value="transformer maintenance procedure details",
        )
        with patch.object(query_rewriter, "AzureOpenAI", return_value=client):
            rewrite_query(
                "what was that earlier transformer thing",
                history,
                max_history_chars=2500,  # exercises the post-fix budget
            )

        call = client.chat.completions.create.call_args
        prompt_user_msg = call[1]["messages"][1]["content"]
        assert "transformer maintenance" in prompt_user_msg.lower(), (
            "Q1's topic must be visible in the rewriter's prompt for "
            "long-distance anaphora to work."
        )

    def test_q1_invisible_with_old_4_message_window(self):
        """Sanity check: with the OLD 1500-char budget AND only the last
        4 messages worth of history loaded, Q1 is dropped.

        This documents what current code does so a regression would re-fail.
        """
        # Simulate the old behavior by passing only the last 4 messages
        history_full = _build_long_history(
            ("what is transformer maintenance", "Transformer maintenance procedures..."),
            ("now tell me about cable splicing for 25 kV", "Cable splicing involves..."),
            ("what tools for cable splicing", "Tools include..."),
            ("what about underground cables", "Underground cable considerations..."),
        )
        # Pass only the last 4 messages as the rewriter would see under
        # max_turns=4 (which is what agent.py currently passes)
        last_four = history_full[-4:]

        client = _capture_rewriter_prompt(return_value="something")
        with patch.object(query_rewriter, "AzureOpenAI", return_value=client):
            rewrite_query(
                "what was that earlier transformer thing",
                last_four,
            )

        call = client.chat.completions.create.call_args
        if call:
            prompt_user_msg = call[1]["messages"][1]["content"]
            assert "transformer maintenance" not in prompt_user_msg.lower(), (
                "Sanity check: with only the last 4 messages, Q1's topic "
                "is correctly absent. (Confirms current bug.)"
            )

    @pytest.mark.parametrize(
        "intervening_pairs",
        [1, 2, 3],
    )
    def test_q1_visible_when_window_holds_all_pairs(self, intervening_pairs):
        """Q1 stays visible as long as total Q&A pairs fit in the window
        (4 pairs for max_turns=8)."""
        pairs = [("what is the GDS owner", "GDS is owned by department X.")]
        for i in range(intervening_pairs):
            pairs.append((f"unrelated question {i}", f"unrelated answer {i}"))
        history = _build_long_history(*pairs)

        client = _capture_rewriter_prompt(return_value="GDS ownership info")
        with patch.object(query_rewriter, "AzureOpenAI", return_value=client):
            # 'going back to' is an anaphora marker, ensures rewriter is invoked.
            rewrite_query(
                "going back to that GDS topic, who is the contact",
                history,
                max_history_chars=2500,
            )

        call = client.chat.completions.create.call_args
        prompt_user_msg = call[1]["messages"][1]["content"]
        assert "gds" in prompt_user_msg.lower(), (
            f"Q1's named entity 'GDS' must remain visible after "
            f"{intervening_pairs} intervening Q&A pair(s)."
        )


# ---------------------------------------------------------------------------
# Multi-topic disambiguation — when the window contains multiple topics,
# the rewriter must pick the right one based on the new question's wording
# ---------------------------------------------------------------------------


class TestMultiTopicDisambiguation:
    """The rewriter sees a window containing multiple topics. It must pick
    the topic the new question most plausibly relates to, not blend them."""

    def test_rewriter_receives_multi_topic_history(self):
        """Verify the rewriter gets full multi-topic context. The mock
        returns a sane rewrite (we don't test the LLM's choice — we test
        that the prompt has all the data needed for it to choose correctly)."""
        history = _build_long_history(
            ("what is transformer maintenance", "Transformer maintenance involves..."),
            ("how often", "Annually for 15 kV, semi-annually for 25 kV..."),
            ("now describe arc flash hazards", "Arc flash hazards include..."),
            ("category 2 PPE", "Category 2 PPE includes..."),
        )

        client = _capture_rewriter_prompt(
            return_value="transformer maintenance frequency",
        )
        with patch.object(query_rewriter, "AzureOpenAI", return_value=client):
            # 'going back to' marker ensures rewriter runs.
            rewrite_query(
                "going back to that transformer topic, how often",
                history,
                max_history_chars=2500,
            )

        call = client.chat.completions.create.call_args
        prompt_user_msg = call[1]["messages"][1]["content"]
        # Both topics must be visible so the LLM can disambiguate.
        assert "transformer" in prompt_user_msg.lower()
        assert "arc flash" in prompt_user_msg.lower()


# ---------------------------------------------------------------------------
# Char budget — verify increased budget actually accommodates longer history
# ---------------------------------------------------------------------------


class TestRuntimeLoadsEnoughHistory:
    """Verify agent.py asks Cosmos for 8 prior messages, not 4.

    We patch chat_store.get_messages_for_user and inspect the max_turns kwarg
    on the call that comes from the query-rewriter path (NOT the condensation
    path which legitimately uses max_turns=2).
    """

    def test_run_once_loads_at_least_8_messages_for_rewriter(self):
        import asyncio
        from unittest.mock import AsyncMock

        from app.agent_runtime import agent as agent_module
        from app.agent_runtime.agent import AgentRuntime
        from app.agent_runtime.session import AgentSession

        @dataclass
        class FakeIdentity:
            user_id: str = "u"
            user_name: str = "U"
            auth_source: str = "test"
            is_authenticated: bool = True

        @dataclass
        class FakeUserMsg:
            sequence: int = 5

        recorded: list[int] = []

        async def fake_get_messages(thread_id, user_id, max_turns=12, before_sequence=None):
            recorded.append(max_turns)
            return []  # Empty → rewriter won't be called, but max_turns is captured

        with patch.object(agent_module, "is_storage_enabled", return_value=True), \
             patch.object(
                 agent_module,
                 "classify_intent",
                 return_value=("technical", None),
             ), \
             patch.object(
                 agent_module.chat_store,
                 "get_conversation",
                 new=AsyncMock(return_value=MagicMock(message_count=2)),
             ), \
             patch.object(
                 agent_module.chat_store,
                 "append_user_message",
                 new=AsyncMock(return_value=FakeUserMsg(sequence=5)),
             ), \
             patch.object(
                 agent_module.chat_store,
                 "get_messages_for_user",
                 side_effect=fake_get_messages,
             ), \
             patch.object(
                 agent_module,
                 "_persist_assistant",
                 new=AsyncMock(return_value=None),
             ), \
             patch.object(
                 agent_module,
                 "retrieve",
                 return_value=[
                     {"content": "x", "source": "s", "score": 0.03,
                      "reranker_score": 2.5, "title": "", "url": "",
                      "chunk_id": "1", "parent_id": "p", "section1": "",
                      "section2": "", "section3": "", "layout_ordinal": 0,
                      "page": "", "printed_page_label": "", "record_type": "text",
                      "diagram_description": "", "diagram_category": "",
                      "figure_ref": "", "table_caption": "", "semantic_content": ""},
                     {"content": "y", "source": "s", "score": 0.03,
                      "reranker_score": 2.5, "title": "", "url": "",
                      "chunk_id": "2", "parent_id": "p", "section1": "",
                      "section2": "", "section3": "", "layout_ordinal": 1,
                      "page": "", "printed_page_label": "", "record_type": "text",
                      "diagram_description": "", "diagram_category": "",
                      "figure_ref": "", "table_caption": "", "semantic_content": ""},
                 ],
             ), \
             patch.object(
                 agent_module,
                 "_buffer_llm_response",
                 new=AsyncMock(return_value=("answer", {}, False)),
             ), \
             patch.object(
                 agent_module,
                 "_get_or_create_af_session",
                 new=AsyncMock(return_value=MagicMock()),
             ):
            asyncio.run(
                AgentRuntime().run_once(
                    "what about that earlier transformer thing",
                    AgentSession(question="x", session_id="t1"),
                    FakeIdentity(),
                )
            )

        # The query-rewriter path calls get_messages_for_user with max_turns >= 8
        # after Ticket #2. Filter out the condensation calls (max_turns=2).
        rewriter_calls = [n for n in recorded if n != 2]
        assert rewriter_calls, "Rewriter path didn't call get_messages_for_user"
        assert max(rewriter_calls) >= 8, (
            f"Expected rewriter to load >=8 messages; got max_turns={rewriter_calls!r}"
        )


class TestCharBudget:
    def test_2500_char_budget_fits_eight_short_messages(self):
        """Eight ~150-char messages = ~1200 chars, fits comfortably in 2500."""
        history = _build_long_history(
            *[(f"question {i} " * 10, f"answer {i} " * 10) for i in range(4)]
        )
        client = _capture_rewriter_prompt(return_value="rewrite")
        with patch.object(query_rewriter, "AzureOpenAI", return_value=client):
            rewrite_query("what about it", history, max_history_chars=2500)

        call = client.chat.completions.create.call_args
        prompt_user_msg = call[1]["messages"][1]["content"]
        # All four user messages should appear
        for i in range(4):
            assert f"question {i}" in prompt_user_msg, (
                f"User Q{i} dropped from prompt — char budget too small"
            )

    def test_old_1500_char_budget_truncates_eight_messages(self):
        """Sanity check: the OLD 1500-char budget truncates 8 messages."""
        history = _build_long_history(
            *[(f"a long question with content {i} " * 10,
               f"a long answer with content {i} " * 10)
              for i in range(4)]
        )
        client = _capture_rewriter_prompt(return_value="rewrite")
        with patch.object(query_rewriter, "AzureOpenAI", return_value=client):
            rewrite_query("what about it", history, max_history_chars=1500)

        call = client.chat.completions.create.call_args
        prompt_user_msg = call[1]["messages"][1]["content"]
        # The earliest message should be dropped
        assert "question with content 0" not in prompt_user_msg
