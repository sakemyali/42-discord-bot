"""Walk corpus/, run LightRAG's exact chunker, dump chunks for Claude-LLM ingest.

Output: rag_storage/claude_chunks.jsonl — one JSON object per line:
  {"id": "chunk-<md5>", "doc": "filename.md", "idx": 0, "tokens": 736, "content": "..."}

The chunk id is computed the same way LightRAG does, so the downstream
ingest can match cached responses by content-hash.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from lightrag.operate import chunking_by_token_size
from lightrag.utils import TiktokenTokenizer, compute_mdhash_id

CORPUS = Path(os.environ.get("CORPUS_PATH", "corpus"))
CACHE_DIR = Path("./cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUT = CACHE_DIR / "claude_chunks.jsonl"

CHUNK_TOKEN_SIZE = int(os.environ.get("CHUNK_TOKEN_SIZE", "1200"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "100"))


def main() -> None:
    tk = TiktokenTokenizer()
    n_docs = n_chunks = total_tokens = 0
    with OUT.open("w", encoding="utf-8") as fout:
        for f in sorted(CORPUS.rglob("*")):
            if f.suffix.lower() not in {".md", ".txt"}:
                continue
            if f.name.lower() == "readme.md":
                continue
            text = f.read_text(encoding="utf-8")
            if not text.strip():
                continue
            n_docs += 1
            chunks = chunking_by_token_size(
                tk, text,
                chunk_overlap_token_size=CHUNK_OVERLAP,
                chunk_token_size=CHUNK_TOKEN_SIZE,
            )
            for ci, c in enumerate(chunks):
                chunk_id = compute_mdhash_id(c["content"], prefix="chunk-")
                fout.write(json.dumps({
                    "id": chunk_id,
                    "doc": f.name,
                    "idx": ci,
                    "tokens": c["tokens"],
                    "content": c["content"],
                }, ensure_ascii=False) + "\n")
                n_chunks += 1
                total_tokens += c["tokens"]

    print(f"wrote {OUT}")
    print(f"  docs   : {n_docs}")
    print(f"  chunks : {n_chunks}")
    print(f"  tokens : {total_tokens:,}")


if __name__ == "__main__":
    main()
