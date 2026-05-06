"""Ingest corpus/ into LightRAG storage.

Reads every .md / .txt file under corpus/ (recursively) and inserts each as
one document. LightRAG handles chunking, entity/relation extraction (via the
LLM), and graph + vector indexing internally.

This step is slow — entity extraction calls the LLM per chunk. Plan on
30-90 minutes on a local Ollama for ~70 documents. Re-running picks up
where it left off (LightRAG dedupes by content hash and tracks doc status).
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

from .rag import build_rag, default_corpus_path, insert_documents


def _walk_corpus(corpus_dir: Path) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    for path in sorted(corpus_dir.rglob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            continue
        # Use just the leaf filename as the citation id
        docs.append((path.name, text))
    return docs


async def _run() -> int:
    load_dotenv()
    corpus_dir = default_corpus_path()
    if not corpus_dir.exists():
        print(f"corpus directory not found: {corpus_dir}", file=sys.stderr)
        return 1
    docs = _walk_corpus(corpus_dir)
    if not docs:
        print(f"no .md / .txt files under {corpus_dir}", file=sys.stderr)
        return 1
    use_groq = bool(os.environ.get("GROQ_API_KEY", "").strip())
    if os.environ.get("INGEST_LLM", "auto").lower() == "ollama":
        use_groq = False
    print(f"found {len(docs)} documents in {corpus_dir}")
    if use_groq:
        print(
            f"LLM (ingest) : Groq {os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')} — fast path"
        )
    else:
        print(
            f"LLM (ingest) : Ollama {os.environ.get('OLLAMA_LLM_MODEL', 'qwen2.5:7b')} — slow path (set GROQ_API_KEY for ~10x speedup)"
        )
    print(
        f"Embeddings   : {os.environ.get('EMBED_MODEL', 'paraphrase-multilingual-MiniLM-L12-v2')}\n"
        f"Working dir  : {os.environ.get('LIGHTRAG_WORKING_DIR', './rag_storage')}\n"
    )
    print(
        "Note: ingest is one-shot; rerun is safe (LightRAG dedupes by content hash).\n"
    )
    rag = await build_rag(use_groq_llm=use_groq)
    started = time.time()
    try:
        await insert_documents(rag, docs)
    finally:
        await rag.finalize_storages()
    elapsed = time.time() - started
    print(f"\ningest finished in {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
