"""RagContextProvider — official Agent Framework ContextProvider for RAG.
 
Implements the Agent Framework BaseContextProvider hook pattern.
 
Before each LLM call (before_run):
  - Reads pre-retrieved Azure AI Search results from session.state
    (placed there by AgentRuntime.run_stream before calling agent.run).
  - Formats them into numbered evidence blocks via build_context_blocks.
  - Injects the formatted context as additional instructions via
    context.extend_instructions(), which the framework appends to the
    agent's system prompt before the model call.
 
After each LLM call (after_run):
  - No-op for now; Cosmos DB / audit storage can be added here later.
 
This is what makes the repo a true Agent Framework implementation:
RAG context injection is a first-class ContextProvider, not ad-hoc
string formatting inside the orchestrator.
"""
 
import logging
from typing import Any
 
from agent_framework import AgentSession, BaseContextProvider, SessionContext
 
from app.agent_runtime.context_providers import build_context_blocks
from app.config.settings import TRACE_MODE
 
logger = logging.getLogger(__name__)
 
# Cross-provider key in session.state used to hand off pre-retrieved results
# from AgentRuntime to this provider without double-querying Azure AI Search.
_PENDING_RESULTS_KEY = "_rag_pending_results"
 
# When set to True in session.state, the provider injects a condensation
# instruction instead of numbered context blocks.  This tells the LLM to
# reformat its prior answer from conversation history, overriding the normal
# grounding rules that require numbered context blocks.
_CONDENSATION_MODE_KEY = "_rag_condensation_mode"
 
 
class RagContextProvider(BaseContextProvider):
    """Injects pre-retrieved search chunks as grounded context for each turn."""
 
    def __init__(self) -> None:
        super().__init__("rag")
 
    def store_results(self, session: AgentSession, results: list[dict]) -> None:
        """Called by AgentRuntime before agent.run() to pass retrieved chunks.
 
        Storing in session.state (not in the provider-scoped state slice)
        makes the data visible to before_run() via the session parameter.
        """
        session.state[_PENDING_RESULTS_KEY] = results
 
    def store_condensation_mode(
        self, session: AgentSession, prior_answer: str = "",
    ) -> None:
        """Signal that this turn is a condensation request (reformat prior answer).
 
        When set, before_run() injects a condensation instruction that includes
        the prior assistant answer directly, so the LLM knows exactly what to
        reformat — even on cold start when InMemoryHistory is empty.
        """
        session.state[_CONDENSATION_MODE_KEY] = prior_answer or True
 
    async def before_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """Inject retrieved chunks as system-level context before model call."""
        condensation_data = session.state.pop(_CONDENSATION_MODE_KEY, False)
        results: list[dict] = session.state.pop(_PENDING_RESULTS_KEY, [])
 
        if condensation_data:
            # condensation_data is either True (no prior answer) or the prior answer string
            prior_answer = condensation_data if isinstance(condensation_data, str) else ""
 
            instruction_parts = [
                "═══ CONDENSATION MODE — OVERRIDES GROUNDING RULES ═══",
                "The user is asking you to reformat, condense, or summarize "
                "your PREVIOUS answer from this conversation.",
                "",
                "FOR THIS RESPONSE ONLY:",
                "• IGNORE Rule 1 (\"Answer ONLY from context blocks\"). "
                "There are NO context blocks for this turn.",
                "• Reformat the answer below according to the user's instructions "
                "(number of points, brevity, bullet list, etc.).",
                "• Preserve the specific technical details, values, and facts "
                "— do NOT generalize or invent new content.",
                "• Do NOT add citations or [N] references.",
                "• Do NOT ask for clarification — the user IS referring to the "
                "answer below.",
            ]
 
            if prior_answer:
                # Include the actual prior answer so the LLM has it directly,
                # regardless of whether InMemoryHistory has it or not.
                # Truncate to avoid blowing up the context window.
                truncated = prior_answer[:4000]
                instruction_parts.extend([
                    "",
                    "═══ YOUR PREVIOUS ANSWER TO REFORMAT ═══",
                    truncated,
                    "═══ END OF PREVIOUS ANSWER ═══",
                ])
            else:
                instruction_parts.append(
                    "• Use your MOST RECENT assistant reply from the conversation "
                    "history as your source material."
                )
 
            instruction_parts.append("═══════════════════════════════════════════════════════")
 
            context.extend_instructions(
                self.source_id,
                "\n".join(instruction_parts),
            )
            logger.info(
                "RagContextProvider: condensation mode — injected reformat override "
                "(prior_answer_len=%d)",
                len(prior_answer),
            )
            return
 
        if not results:
            return
 
        context_blocks = build_context_blocks(results)
        context.extend_instructions(
            self.source_id,
            (
                "Context (retrieved from PSEG technical manuals):\n\n"
                f"{context_blocks}\n\n"
                "Answer the question using ONLY the context above. "
                "When the context covers the topic — even partially — provide a "
                "complete answer from the available information. "
                "Reference each source by its [N] label inline."
            ),
        )
 
        if TRACE_MODE:
            chunk_summary = "  |  ".join(
                "[{i}] {src} score={s:.4f}{r}".format(
                    i=i + 1,
                    src=r["source"],
                    s=r["score"],
                    r=(f" reranker={r['reranker_score']:.4f}"
                       if r.get("reranker_score") is not None else ""),
                )
                for i, r in enumerate(results)
            )
            logger.info("TRACE | context_injected: %s", chunk_summary)
            # Log the full context blocks so you can see exactly what the LLM receives.
            for i, r in enumerate(results, start=1):
                section_parts = [
                    r.get("section1") or "", r.get("section2") or "", r.get("section3") or "",
                ]
                section = " > ".join(p for p in section_parts if p)
                logger.info(
                    "TRACE | context_block[%d] (%s | %s):\n%s",
                    i, r["source"], section or "no section",
                    r["content"][:600],
                )
 
    async def after_run(
        self,
        *,
        agent: Any,
        session: AgentSession,
        context: SessionContext,
        state: dict[str, Any],
    ) -> None:
        """No-op — Cosmos DB / audit storage can be wired here later."""