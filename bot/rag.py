"""LightRAG-backed retrieval and answering.

The pipeline:

  question
     │
     ▼
  ┌─────────────────────────────────────────────────┐
  │ LightRAG (mode=mix)                             │
  │                                                 │
  │   1. extract entities from question             │ ← LLM
  │   2. vector search over chunks (cosine, 384-d)  │ ← embedder
  │   3. graph traversal over entity/relation graph │
  │   4. assemble context, generate answer          │ ← LLM
  └─────────────────────────────────────────────────┘
     │
     ▼
  RagAnswer { text, sources, raw_context, mode }

Storage backends are all local files under WORKING_DIR:
  - JsonKVStorage    (full text + metadata)
  - NanoVectorDB     (chunk + entity + relation embeddings)
  - NetworkXStorage  (entity / relation knowledge graph)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.ollama import ollama_model_complete
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.utils import EmbeddingFunc, setup_logger
from sentence_transformers import SentenceTransformer

DEFAULT_WORKING_DIR = "./rag_storage"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_OLLAMA_LLM = "qwen2.5:7b"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GROQ_BASE = "https://api.groq.com/openai/v1"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
DEFAULT_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_EMBED_DIM = 384
DEFAULT_QUERY_MODE = "mix"
DEFAULT_LLM_NUM_CTX = 16384


@dataclass
class RagAnswer:
    text: str
    sources: list[str]
    mode: str


class QueryFailed(RuntimeError):
    """Raised when the query-time LLM returns nothing usable.

    Most common cause is rate-limit/quota exhaustion on the configured provider
    (Gemini free tier is 20 RPD per model). Caller should surface a useful
    message to the user, not coerce None into the string "None".
    """


def _build_embedding_func(model_name: str | None = None) -> EmbeddingFunc:
    name = model_name or os.environ.get("EMBED_MODEL", DEFAULT_EMBED_MODEL)
    model = SentenceTransformer(name)
    dim = model.get_sentence_embedding_dimension() or DEFAULT_EMBED_DIM

    async def _embed(texts: list[str]) -> np.ndarray:
        vecs = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vecs.astype(np.float32)

    return EmbeddingFunc(
        embedding_dim=dim,
        func=_embed,
        max_token_size=512,
        model_name=name.split("/")[-1],
    )


def _ollama_llm_kwargs() -> dict[str, Any]:
    host = os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    num_ctx = int(os.environ.get("OLLAMA_NUM_CTX", str(DEFAULT_LLM_NUM_CTX)))
    return {
        "host": host,
        "options": {"num_ctx": num_ctx},
        "timeout": float(os.environ.get("OLLAMA_TIMEOUT", "300")),
    }


def _make_openai_compatible_func(
    name: str,
    api_key: str,
    model: str,
    base_url: str,
):
    """Build a LightRAG-compatible llm_model_func that talks to any
    OpenAI-compatible endpoint (Groq, Gemini's compat layer, OpenAI
    proper, OpenRouter, etc.)."""
    async def _func(prompt, system_prompt=None, history_messages=None, **kwargs):
        return await openai_complete_if_cache(
            model,
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            base_url=base_url,
            api_key=api_key,
            **{k: v for k, v in kwargs.items() if k != "hashing_kv"},
        )

    _func.__name__ = name  # LightRAG inspects this for cache keys
    return _func


def _groq_llm_func():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is empty but Groq was requested.")
    model = os.environ.get("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    base_url = os.environ.get("GROQ_BASE_URL", DEFAULT_GROQ_BASE)
    return _make_openai_compatible_func("groq_complete", api_key, model, base_url), model


def _gemini_llm_func():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is empty but Gemini was requested.")
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    base_url = os.environ.get("GEMINI_BASE_URL", DEFAULT_GEMINI_BASE)
    return _make_openai_compatible_func("gemini_complete", api_key, model, base_url), model


def detect_llm_provider() -> str:
    """Pick the LLM provider based on env, in priority order:
       gemini → groq → ollama. Override with LLM_PROVIDER=ollama|groq|gemini.
       Same selection drives both ingest and query."""
    forced = os.environ.get("LLM_PROVIDER", "auto").strip().lower()
    if forced in {"ollama", "groq", "gemini"}:
        return forced
    if os.environ.get("GEMINI_API_KEY", "").strip():
        return "gemini"
    if os.environ.get("GROQ_API_KEY", "").strip():
        return "groq"
    return "ollama"


async def build_rag(
    working_dir: str | None = None,
    provider: str | None = None,
) -> LightRAG:
    """Construct a LightRAG instance.

    The LLM provider is auto-detected from environment:
      gemini → groq → ollama  (first one with creds wins)
    Override by passing `provider=` explicitly or setting LLM_PROVIDER=...
    Embeddings always come from sentence-transformers.

    Loads existing storage if working_dir is already populated.
    """
    setup_logger("lightrag", level="INFO")
    wd = working_dir or os.environ.get("LIGHTRAG_WORKING_DIR", DEFAULT_WORKING_DIR)
    Path(wd).mkdir(parents=True, exist_ok=True)

    provider = (provider or detect_llm_provider()).lower()

    if provider == "gemini":
        llm_func, llm_model_name = _gemini_llm_func()
        llm_kwargs: dict[str, Any] = {
            "timeout": float(os.environ.get("GEMINI_TIMEOUT", "120")),
        }
        # Free tier is 15 RPM; concurrency 1 keeps us safely below.
        max_async = int(os.environ.get("GEMINI_MAX_ASYNC", "1"))
    elif provider == "groq":
        llm_func, llm_model_name = _groq_llm_func()
        llm_kwargs = {
            "timeout": float(os.environ.get("GROQ_TIMEOUT", "60")),
        }
        max_async = int(os.environ.get("GROQ_MAX_ASYNC", "8"))
    else:
        llm_func = ollama_model_complete
        llm_model_name = os.environ.get("OLLAMA_LLM_MODEL", DEFAULT_OLLAMA_LLM)
        llm_kwargs = _ollama_llm_kwargs()
        max_async = int(os.environ.get("LLM_MAX_ASYNC", "2"))

    rag = LightRAG(
        working_dir=wd,
        llm_model_func=llm_func,
        llm_model_name=llm_model_name,
        llm_model_max_async=max_async,
        llm_model_kwargs=llm_kwargs,
        embedding_func=_build_embedding_func(),
        chunk_token_size=int(os.environ.get("CHUNK_TOKEN_SIZE", "1200")),
        chunk_overlap_token_size=int(os.environ.get("CHUNK_OVERLAP", "100")),
        enable_llm_cache=True,
        default_llm_timeout=int(os.environ.get("LLM_TIMEOUT_SEC", "600")),
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()
    return rag


_REF_LINE_RE = re.compile(r"^\s*[-*]\s*\[\d+\]\s*(.+?\.md)\s*$", re.MULTILINE)
_REF_HEADER_RE = re.compile(r"###?\s*References\s*$", re.MULTILINE | re.IGNORECASE)


def _extract_sources(answer_text: str) -> list[str]:
    """Pull source filenames out of LightRAG's reference block.

    LightRAG with include_references=True appends a section like:

        ### References

        - [1] Intra Meta FAQ - 42 Tokyo.md
        - [2] Intra Meta ピアレビューについて.md

    Returns filenames in citation order, deduped, preserving spaces.
    """
    if not answer_text:
        return []
    m = _REF_HEADER_RE.search(answer_text)
    block = answer_text[m.end():] if m else answer_text
    found: list[str] = []
    for match in _REF_LINE_RE.finditer(block):
        name = match.group(1).strip()
        if name not in found:
            found.append(name)
    return found


def strip_references_block(answer_text: str) -> str:
    """Return the answer body with the trailing '### References' block removed."""
    m = _REF_HEADER_RE.search(answer_text)
    return answer_text[:m.start()].rstrip() if m else answer_text


async def query(
    rag: LightRAG,
    question: str,
    mode: str | None = None,
    top_k: int | None = None,
) -> RagAnswer:
    """Run a query end-to-end. Returns the answer plus extracted source list."""
    use_mode = mode or os.environ.get("LIGHTRAG_QUERY_MODE", DEFAULT_QUERY_MODE)
    param = QueryParam(
        mode=use_mode,
        top_k=top_k or int(os.environ.get("LIGHTRAG_TOP_K", "20")),
        include_references=True,
        response_type="Conversational, friendly, 3-6 sentences",
    )
    try:
        text = await rag.aquery(question, param=param)
    except Exception as exc:  # network / rate-limit / auth — bubble up cleanly
        raise QueryFailed(f"LLM call failed: {type(exc).__name__}: {exc}") from exc
    if text is None or (isinstance(text, str) and not text.strip()):
        raise QueryFailed(
            "LLM returned no answer — most likely rate-limit / quota "
            "exhaustion on the configured provider. Try again later or "
            "set LLM_PROVIDER=ollama in .env to switch to the local fallback."
        )
    if not isinstance(text, str):
        text = str(text)
    sources = _extract_sources(text)
    body = strip_references_block(text).strip()
    return RagAnswer(
        text=body,
        sources=sources,
        mode=use_mode,
    )


async def insert_documents(rag: LightRAG, docs: list[tuple[str, str]]) -> None:
    """Batch-insert documents.

    `docs` is a list of (source_id, text). source_id is used as the
    `file_path` so it appears in citation references.
    """
    if not docs:
        return
    file_paths = [src for src, _ in docs]
    texts = [text for _, text in docs]
    await rag.ainsert(texts, file_paths=file_paths)


def default_corpus_path() -> Path:
    return Path(os.environ.get("CORPUS_PATH", "corpus"))


def working_dir_path() -> Path:
    return Path(os.environ.get("LIGHTRAG_WORKING_DIR", DEFAULT_WORKING_DIR))
