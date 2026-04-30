"""
LLM provider — HuggingFace Inference API via LangChain.

Model: mistralai/Mistral-7B-Instruct-v0.3
  - Free tier on HuggingFace Inference API (serverless)
  - Supports tool/function calling → required for LangChain agents (bind_tools)
  - Strong instruction-following for agentic multi-step tasks

WHY two-layer setup (HuggingFaceEndpoint → ChatHuggingFace):
  HuggingFaceEndpoint handles the raw HTTP call to HF Inference API.
  ChatHuggingFace wraps it as a LangChain BaseChatModel so it works with:
    - LangChain agents (AgentExecutor, LangGraph nodes)
    - bind_tools() for tool calling
    - LCEL chains (pipe operator |)
    - Streaming callbacks

WHY not load model locally (transformers pipeline):
  Mistral-7B needs ~14GB RAM minimum. Kills Docker Desktop.
  HF Inference API is serverless — zero setup, same interface.
"""
from functools import lru_cache

from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

from config import get_settings


def get_llm() -> ChatHuggingFace:
    """
    Returns a LangChain ChatHuggingFace model backed by HF Inference API.

    Usage in agents:
        llm = get_llm()
        llm_with_tools = llm.bind_tools([tool1, tool2])

    Usage in LCEL chains:
        chain = prompt | get_llm() | StrOutputParser()
    """
    settings = get_settings()

    endpoint = HuggingFaceEndpoint(
        repo_id=settings.hf_model_id,
        temperature=settings.llm_temperature,
        huggingfacehub_api_token=settings.huggingface_api_token,
        # max_new_tokens: cap output length — prevents runaway generation in agents
        max_new_tokens=1024,
    )

    return ChatHuggingFace(llm=endpoint)


@lru_cache
def get_cached_llm() -> ChatHuggingFace:
    """
    Singleton LLM instance — reuse across requests.

    WHY: HuggingFaceEndpoint initialization is lightweight,
    but caching avoids redundant object creation on every request.
    Use this in routers. Use get_llm() directly in tests (easier to mock).
    """
    return get_llm()
