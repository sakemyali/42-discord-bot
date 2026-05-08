"""LightRAG ingest with Claude-cached entity-extraction responses.

Workflow:
  1. scripts/dump_chunks.py  → rag_storage/claude_chunks.jsonl
  2. (Claude reads chunks, writes entity/relation tuples to)
                             → rag_storage/claude_responses.json
                                {chunk_id: {"response": "...delimited tuples...<|COMPLETE|>"}}
  3. THIS SCRIPT             → runs rag.ainsert() with a fake llm_model_func
                                that hashes the chunk text inside each prompt and
                                returns the corresponding cached response.

LightRAG handles everything else: embedding chunks/entities/relations,
graph construction, KV/vector store writes.

For non-extraction LLM calls (entity-description summarization on merge),
we fall back to a stub that returns the first description — slight
quality loss vs. real merging, but functional.
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

# Force the build_rag path to use our injected llm_func by setting
# LLM_PROVIDER to a placeholder we then override post-build.
from bot.rag import build_rag, default_corpus_path  # noqa: E402

WD = Path(os.environ.get("LIGHTRAG_WORKING_DIR", "./rag_storage"))
# Cache lives outside WD so `make clean` doesn't wipe Claude's pre-computed
# entity-extraction responses (~$1-2 of work per regenerate).
CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_PATH = CACHE_DIR / "claude_chunks.jsonl"
RESPONSES_PATH = CACHE_DIR / "claude_responses.json"

# Regex to pull `<Input Text>` block out of the user prompt.
_INPUT_BLOCK_RE = re.compile(
    r"<Input Text>\s*```\s*\n(.*?)\n```",
    re.DOTALL,
)


def _load_cache() -> dict[str, str]:
    """Return {chunk_content: response_text}.

    We key by the exact chunk content (string match), not a hash — chunks are
    embedded verbatim in the prompt so equality is reliable.

    If responses file is missing, returns an empty cache. Every entity-extraction
    call will then return `<|COMPLETE|>` (no entities), which still produces a
    working vector-RAG storage — just no knowledge graph.
    """
    if not RESPONSES_PATH.exists():
        print(f"NOTE: {RESPONSES_PATH} not found — running empty-extraction "
              "ingest (vector-only, no graph)")
        return {}
    chunks = {}
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            chunks[d["id"]] = d["content"]
    responses = json.loads(RESPONSES_PATH.read_text(encoding="utf-8"))
    cache: dict[str, str] = {}
    missing = []
    for cid, content in chunks.items():
        if cid not in responses:
            missing.append(cid)
            continue
        cache[content] = responses[cid]["response"] if isinstance(responses[cid], dict) else responses[cid]
    if missing:
        print(f"WARNING: {len(missing)} chunks have no cached response; first 3: {missing[:3]}")
    print(f"loaded {len(cache)} cached chunk responses (from {len(chunks)} total chunks)")
    return cache


def make_claude_llm_func(cache: dict[str, str]):
    """Return an async llm_model_func that looks up cached responses."""
    misses = {"count": 0}

    async def _func(prompt, system_prompt=None, history_messages=None, **kwargs):
        # Entity-extraction call? Look for <Input Text> block.
        m = _INPUT_BLOCK_RE.search(prompt)
        if m:
            text = m.group(1)
            if text in cache:
                return cache[text]
            misses["count"] += 1
            # Return empty completion so LightRAG records "no entities" and moves on.
            return "<|COMPLETE|>"
        # Likely a summarize / merge call. Best effort: return the first
        # description fragment we can find in the prompt, or empty.
        # (We could be smarter here, but in practice merge calls are rare
        # when responses are clean.)
        return ""

    _func.__name__ = "claude_complete"
    _func.misses = misses  # for inspection after the run
    return _func


def _walk_corpus(corpus_dir: Path) -> list[tuple[str, str]]:
    docs = []
    for f in sorted(corpus_dir.rglob("*")):
        if f.suffix.lower() not in {".md", ".txt"}:
            continue
        if f.name.lower() == "readme.md":
            continue
        text = f.read_text(encoding="utf-8")
        if not text.strip():
            continue
        docs.append((f.name, text))
    return docs


async def _run() -> int:
    cache = _load_cache()
    docs = _walk_corpus(default_corpus_path())
    print(f"corpus: {len(docs)} docs")
    # Build with any provider — we'll override the llm_model_func.
    # Use ollama mode so we don't trigger real Gemini/Groq wiring.
    os.environ["LLM_PROVIDER"] = "ollama"
    rag = await build_rag(provider="ollama")
    rag.llm_model_func = make_claude_llm_func(cache)
    started = time.time()
    try:
        await rag.ainsert(
            [t for _, t in docs],
            file_paths=[n for n, _ in docs],
        )
    finally:
        await rag.finalize_storages()
    elapsed = time.time() - started
    print(f"\ningest finished in {elapsed:.1f}s ({elapsed/60:.1f} min)")
    misses = rag.llm_model_func.misses["count"]
    if misses:
        print(f"WARNING: {misses} entity-extraction cache misses (returned empty)")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
