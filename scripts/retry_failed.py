"""Properly retry failed LightRAG documents.

LightRAG's `ainsert` re-call on the same content creates `dup-*` ghost
entries instead of retrying the original failures. This helper:

1. Strips the `dup-*` noise entries from doc_status.
2. Flips any `failed`-status `doc-*` entries to `pending`.
3. Reduces chunk size + bumps timeouts (override via env) so the slow,
   big docs that were timing out can complete.
4. Calls `apipeline_process_enqueue_documents()` which is the proper
   path for processing pending docs.
5. Reports before/after counts.

Run as:  .venv/bin/python scripts/retry_failed.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

# Make `bot` importable when running this script from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

# Ensure bot/rag.py sees the smaller-chunk + larger-timeout overrides if
# the user hasn't set them. These only apply to this retry run.
os.environ.setdefault("CHUNK_TOKEN_SIZE", "600")
os.environ.setdefault("CHUNK_OVERLAP", "80")
os.environ.setdefault("LLM_TIMEOUT_SEC", "900")
os.environ.setdefault("OLLAMA_TIMEOUT", "900")

from bot.rag import build_rag, working_dir_path  # noqa: E402


def _clean_doc_status() -> tuple[int, int]:
    """Remove dup-* entries; flip failed doc-* to pending. Returns (cleaned, requeued)."""
    path = working_dir_path() / "kv_store_doc_status.json"
    if not path.exists():
        print(f"no doc status at {path}", file=sys.stderr)
        return 0, 0
    data = json.loads(path.read_text(encoding="utf-8"))

    before = Counter(v.get("status", "?") for v in data.values())
    print("before:", dict(before), f"(total {len(data)})")

    # Drop ghost duplicates
    cleaned = {k: v for k, v in data.items() if not k.startswith("dup-")}
    n_dropped = len(data) - len(cleaned)

    # Flip failed → pending so the pipeline picks them up
    n_requeued = 0
    for k, v in cleaned.items():
        if v.get("status") == "failed":
            v["status"] = "pending"
            v.pop("error", None)
            v.pop("error_msg", None)
            v["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            n_requeued += 1

    after = Counter(v.get("status", "?") for v in cleaned.values())
    print("after :", dict(after), f"(total {len(cleaned)})")
    print(f"dropped {n_dropped} dup-* entries; requeued {n_requeued} failed → pending")

    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return n_dropped, n_requeued


async def _run() -> int:
    load_dotenv()
    n_dropped, n_requeued = _clean_doc_status()
    if n_requeued == 0:
        print("nothing to retry — already clean.")
        return 0
    print(
        f"\nspinning up LightRAG with chunk={os.environ['CHUNK_TOKEN_SIZE']}, "
        f"timeout={os.environ['LLM_TIMEOUT_SEC']}s ..."
    )
    rag = await build_rag()
    started = time.time()
    try:
        await rag.apipeline_process_enqueue_documents()
    finally:
        await rag.finalize_storages()
    elapsed = time.time() - started
    print(f"\nretry pass finished in {elapsed:.1f}s ({elapsed/60:.1f} min)")

    # Final counts
    path = working_dir_path() / "kv_store_doc_status.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    final = Counter(v.get("status", "?") for v in data.values())
    print("final :", dict(final), f"(total {len(data)})")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
