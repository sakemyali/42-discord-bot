from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .rag import Index, default_corpus_path, default_index_path


def main() -> int:
    load_dotenv()
    model_name = os.environ.get(
        "EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    corpus_dir = default_corpus_path()
    index_path = default_index_path()
    if not corpus_dir.exists():
        print(f"corpus directory not found: {corpus_dir}", file=sys.stderr)
        return 1
    print(f"reading corpus from {corpus_dir}")
    print(f"using embedding model {model_name}")
    idx = Index(model_name)
    n = idx.build(corpus_dir)
    idx.save(index_path)
    print(f"indexed {n} chunks -> {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
