"""
Collaborative AI Thread — LangChain agent.

This agent participates in the shared chat thread alongside human users.
It receives events from the Redis Stream consumer (document.uploaded, user.question)
and posts responses back to the chat as a bot message.

WHY LangChain agent (not a plain LLM call):
  A plain LLM call = one prompt → one response.
  An agent = LLM decides which tools to call, in what order, how many times.
  For our use case: the agent may need to search the knowledge base, then
  summarize, then flag risks — that's multi-step, not one-shot.

Agent pattern used: Tool Calling Agent (ReAct-style via bind_tools)
  LLM sees: system prompt + user message + available tools
  LLM outputs: either a tool call OR a final answer
  Agent loop: run tool → feed result back → LLM decides next step
"""
import logging
from typing import Any

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from llm.provider import get_cached_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools — what the agent can do
# ---------------------------------------------------------------------------

@tool
def summarize_document(content: str) -> str:
    """
    Summarize the content of a document uploaded to the chat.
    Use this when a document has been uploaded and needs a summary for the thread.

    Args:
        content: Raw text content of the document.

    Returns:
        A concise summary of the document.
    """
    # WHY this is a tool and not inline logic:
    # The agent decides WHEN to call it. If the user asks a direct question,
    # the agent may skip summarization and go straight to search_knowledge_base.
    llm = get_cached_llm()
    response = llm.invoke(
        f"Summarize the following document in 3-5 bullet points:\n\n{content}"
    )
    return response.content


@tool
def search_knowledge_base(query: str, doc_id: str = "") -> str:
    """
    Search the knowledge base (pgvector) for relevant content.
    Use this when a user asks a question about a document.

    Args:
        query: The user's question or search query.
        doc_id: Optional — restrict search to a specific document.

    Returns:
        Relevant passages from the knowledge base.
    """
    # TODO: replace with real pgvector RAG search (next milestone)
    # This stub lets the agent run end-to-end while RAG is being built.
    logger.info(f"[RAG stub] query='{query}' doc_id='{doc_id}'")
    return (
        f"[Knowledge base search for '{query}' — "
        "RAG pipeline not yet connected. Returning placeholder.]"
    )


@tool
def flag_document_risks(content: str, doc_type: str = "unknown") -> str:
    """
    Proactively scan a document for risks, key dates, or critical clauses.
    Use this for contracts, invoices, or legal documents.

    Args:
        content: Raw text content of the document.
        doc_type: Type hint — 'contract', 'invoice', 'report', etc.

    Returns:
        A list of flagged risks or key items the user should review.
    """
    llm = get_cached_llm()
    response = llm.invoke(
        f"You are a document risk analyst. Review this {doc_type} and list "
        f"any risks, key dates, unusual clauses, or items that need attention:\n\n{content}"
    )
    return response.content


# All tools the agent can use — add new tools here, agent picks them automatically
AGENT_TOOLS = [summarize_document, search_knowledge_base, flag_document_risks]


# ---------------------------------------------------------------------------
# System prompt — sets the agent's persona in the chat thread
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an AI assistant participating in a collaborative chat thread \
alongside human users. You have access to tools to help analyze documents, answer questions, \
and flag important information.

Rules:
- Be concise — you are posting in a chat thread, not writing an essay
- If a document was uploaded, proactively summarize it and flag any risks
- If a user asks a question, search the knowledge base before answering
- Always explain what you found and why it matters
- If you are unsure, say so — do not hallucinate
"""


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def build_agent() -> AgentExecutor:
    """
    Build and return a LangChain AgentExecutor.

    WHY AgentExecutor (not raw agent):
      AgentExecutor handles the tool-call loop automatically:
        LLM → tool call → result → LLM → tool call → result → final answer
      Without it, you'd hand-write that loop yourself.

    WHY create_tool_calling_agent:
      Works with any LLM that supports bind_tools() — including ChatHuggingFace
      with Mistral-7B. It's the modern replacement for ReAct string-parsing agents.
    """
    llm = get_cached_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),  # where tool results are injected
    ])

    agent = create_tool_calling_agent(llm, AGENT_TOOLS, prompt)

    return AgentExecutor(
        agent=agent,
        tools=AGENT_TOOLS,
        verbose=True,       # logs each tool call + result — essential for debugging
        max_iterations=5,   # prevents infinite loops if LLM keeps calling tools
        handle_parsing_errors=True,  # graceful recovery from malformed LLM output
    )


async def run_agent(input_text: str, metadata: dict[str, Any] | None = None) -> str:
    """
    Entry point for all agent invocations.

    Called by:
      - routers/agents.py (HTTP, from Django internal call)
      - consumers/stream_consumer.py (Redis Stream event)

    Args:
        input_text: The instruction/question for the agent.
        metadata: Optional context — doc_id, org_id, chat_id, etc.

    Returns:
        Agent's final response as a string (posted to chat as bot message).
    """
    logger.info(f"Agent invoked | input='{input_text[:80]}...' | metadata={metadata}")

    agent_executor = build_agent()

    # Inject metadata into the input so agent has full context
    full_input = input_text
    if metadata:
        context_str = ", ".join(f"{k}={v}" for k, v in metadata.items())
        full_input = f"[Context: {context_str}]\n\n{input_text}"

    result = await agent_executor.ainvoke({"input": full_input})
    output = result.get("output", "")

    logger.info(f"Agent response: {output[:80]}...")
    return output
