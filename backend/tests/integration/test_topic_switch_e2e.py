"""End-to-end topic-switch tests with mocked retrieval and rewriter.

These tests run AgentRuntime.run_once() with all external dependencies mocked
(Cosmos, Azure Search, Azure OpenAI). They verify the full pipeline behaviour
for the topic-switch ticket:

  - When the rewriter blends two topics, retrieval scores low, gate rejects,
    and (after Fix D) the pipeline retries with the original question.
  - When the rewriter correctly preserves the new topic, normal flow runs.
  - When neither attempt finds enough evidence, the canned message shows.

NOTE: storage is disabled in these tests (Cosmos calls return None / are
no-ops via is_storage_enabled() returning False), so the tests focus purely
on the retrieve → gate → fallback → generate path.
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent_runtime import agent as agent_module
from app.agent_runtime.agent import AgentRuntime
from app.agent_runtime.session import AgentSession


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class FakeIdentity:
    user_id: str = "test-user"
    user_name: str = "Test User"
    auth_source: str = "test"
    is_authenticated: bool = True


def _result(content: str, source: str, reranker: float) -> dict:
    return {
        "content": content,
        "semantic_content": content,
        "title": "Test",
        "source": source,
        "url": "",
        "chunk_id": f"{source}-1",
        "parent_id": source,
        "section1": "",
        "section2": "",
        "section3": "",
        "layout_ordinal": 0,
        "page": "",
        "printed_page_label": "",
        "record_type": "text",
        "diagram_description": "",
        "diagram_category": "",
        "figure_ref": "",
        "table_caption": "",
        "score": 0.025,
        "reranker_score": reranker,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def runtime():
    return AgentRuntime()


@pytest.fixture
def session():
    return AgentSession(question="placeholder", session_id="test-thread-1")


@pytest.fixture
def identity():
    return FakeIdentity()


@pytest.fixture(autouse=True)
def _disable_storage():
    """Force storage-off mode so Cosmos calls don't run."""
    with patch.object(agent_module, "is_storage_enabled", return_value=False):
        yield


@pytest.fixture(autouse=True)
def _no_op_intent_classifier():
    """Force intent classifier to always return TECHNICAL so we test the RAG path."""
    with patch.object(
        agent_module,
        "classify_intent",
        return_value=("technical", None),
    ):
        yield


@pytest.fixture
def mock_buffer_response():
    """Mock the LLM call to avoid talking to Azure OpenAI."""
    with patch.object(
        agent_module,
        "_buffer_llm_response",
        new=AsyncMock(return_value=("<answer>mocked answer [1]</answer><meta>{}</meta>", {}, False)),
    ):
        yield


@pytest.fixture
def mock_persist():
    """Mock persistence so no Cosmos writes happen."""
    with patch.object(
        agent_module,
        "_persist_assistant",
        new=AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture
def mock_af_session():
    """Mock the AF session creation."""
    with patch.object(
        agent_module,
        "_get_or_create_af_session",
        new=AsyncMock(return_value=MagicMock()),
    ):
        yield


# ===========================================================================
# Topic-switch scenarios
# ===========================================================================


class TestTopicSwitchEndToEnd:
    """Full-pipeline smoke tests for the topic-switch ticket."""

    def test_clean_topic_switch_passes_gate(
        self, runtime, session, identity,
        mock_buffer_response, mock_persist, mock_af_session,
    ):
        """When retrieval finds strong chunks, the pipeline returns an answer."""
        strong_results = [
            _result("Vibratium info from manual", "vibration_manual.pdf", 2.8),
            _result("Vibratium specs", "vibration_manual.pdf", 2.5),
        ]
        with patch.object(agent_module, "retrieve", return_value=strong_results):
            result = asyncio.run(
                runtime.run_once("tell me about Vibratium", session, identity)
            )
        assert "mocked answer" in result["answer"]
        assert "I don't have enough evidence" not in result["answer"]

    def test_blended_query_weak_results_returns_canned_without_fallback(
        self, runtime, session, identity,
        mock_buffer_response, mock_persist, mock_af_session,
    ):
        """Without Fix D: weak rewrite results trigger the canned 'no evidence'.

        This test documents CURRENT behaviour. After Fix D this scenario should
        instead return a real answer if the original-query retrieval succeeds.
        """
        weak_results = [
            _result("partial match", "M1", 1.4),
            _result("weak match", "M2", 1.3),
        ]
        with patch.object(agent_module, "retrieve", return_value=weak_results):
            result = asyncio.run(
                runtime.run_once("tell me about Vibratium", session, identity)
            )
        # Current behaviour: gate rejects, canned message shown
        assert "I don't have enough evidence" in result["answer"]

    def test_gate_rejects_too_few_results(
        self, runtime, session, identity,
        mock_buffer_response, mock_persist, mock_af_session,
    ):
        """A single strong chunk fails because MIN_RESULTS=2."""
        single_chunk = [_result("strong but lonely", "M1", 3.5)]
        with patch.object(agent_module, "retrieve", return_value=single_chunk):
            result = asyncio.run(
                runtime.run_once("tell me about Vibratium", session, identity)
            )
        assert "I don't have enough evidence" in result["answer"]

    def test_retrieval_exception_returns_error(
        self, runtime, session, identity,
        mock_buffer_response, mock_persist, mock_af_session,
    ):
        """Search failure produces a clean error response."""
        with patch.object(
            agent_module, "retrieve", side_effect=RuntimeError("Azure Search down")
        ):
            result = asyncio.run(
                runtime.run_once("tell me about Vibratium", session, identity)
            )
        assert "error occurred" in result["answer"].lower()


class TestFallbackBehaviourAfterFix:
    """After Fix D lands, these document the EXPECTED fallback behaviour.

    Currently they are skipped — they will be enabled when retrieve() gets
    called twice (once with rewritten, once with original) on a gate failure.
    """

    @pytest.mark.fix_D
    def test_fallback_triggers_on_gate_rejection_after_rewrite(self):
        """Direct test of _retrieve_with_fallback: weak rewrite → fallback runs."""
        from app.agent_runtime.agent import _retrieve_with_fallback

        weak_then_strong = [
            [_result("weak 1", "M1", 1.4), _result("weak 2", "M2", 1.3)],
            [_result("strong 1", "M1", 2.8), _result("strong 2", "M1", 2.5)],
        ]
        retrieve_mock = MagicMock(side_effect=weak_then_strong)
        with patch.object(agent_module, "retrieve", retrieve_mock):
            results, query_used = asyncio.run(
                _retrieve_with_fallback(
                    search_query="blended fire dust Vibratium label",
                    original_question="tell me about Vibratium",
                    top_k=7,
                    thread_id="test",
                )
            )
        assert retrieve_mock.call_count == 2
        # Fallback returned the strong results
        assert results[0]["content"] == "strong 1"
        assert query_used == "tell me about Vibratium"

    @pytest.mark.fix_D
    def test_fallback_skipped_when_gate_passes_first_time(self):
        """If the rewrite produced strong results, fallback should NOT run."""
        from app.agent_runtime.agent import _retrieve_with_fallback

        strong_results = [
            _result("strong 1", "M1", 2.8),
            _result("strong 2", "M1", 2.5),
        ]
        retrieve_mock = MagicMock(return_value=strong_results)
        with patch.object(agent_module, "retrieve", retrieve_mock):
            results, query_used = asyncio.run(
                _retrieve_with_fallback(
                    search_query="rewritten transformer maintenance",
                    original_question="tell me about transformer maintenance",
                    top_k=7,
                    thread_id="test",
                )
            )
        assert retrieve_mock.call_count == 1
        assert query_used == "rewritten transformer maintenance"

    @pytest.mark.fix_D
    def test_fallback_canned_message_when_both_attempts_fail(self):
        """If both the rewritten and original queries fail, the helper returns
        the fallback (still-weak) results so the gate can emit the canned
        message."""
        from app.agent_runtime.agent import _retrieve_with_fallback

        weak_results = [
            _result("weak", "M1", 1.4),
            _result("weak", "M2", 1.3),
        ]
        retrieve_mock = MagicMock(return_value=weak_results)
        with patch.object(agent_module, "retrieve", retrieve_mock):
            results, query_used = asyncio.run(
                _retrieve_with_fallback(
                    search_query="rewritten nonexistent xyz",
                    original_question="tell me about NonexistentTopic XYZ",
                    top_k=7,
                    thread_id="test",
                )
            )
        # Both calls happened; gate logic outside this helper will reject.
        assert retrieve_mock.call_count == 2
        assert query_used == "tell me about NonexistentTopic XYZ"

    @pytest.mark.fix_D
    def test_fallback_not_attempted_when_no_rewrite_happened(self):
        """When the search_query equals the original question, only one
        retrieval should run regardless of gate outcome."""
        from app.agent_runtime.agent import _retrieve_with_fallback

        weak_results = [_result("weak", "M1", 1.0)]
        retrieve_mock = MagicMock(return_value=weak_results)
        with patch.object(agent_module, "retrieve", retrieve_mock):
            results, query_used = asyncio.run(
                _retrieve_with_fallback(
                    search_query="tell me about Vibratium",
                    original_question="tell me about Vibratium",
                    top_k=7,
                    thread_id="test",
                )
            )
        assert retrieve_mock.call_count == 1
        assert query_used == "tell me about Vibratium"
