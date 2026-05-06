#!/usr/bin/env python3
"""Print a one-screen status snapshot of the LightRAG ingest."""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

DOC_STATUS = Path(
    os.environ.get("LIGHTRAG_WORKING_DIR", "./rag_storage")
) / "kv_store_doc_status.json"
LOG_PATH = Path(os.environ.get("INGEST_LOG", "/tmp/ingest_run.log"))
START_FILE = Path("/tmp/ingest_start.txt")


def _fmt_seconds(s: float) -> str:
    s = int(s)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def main() -> int:
    if not DOC_STATUS.exists():
        print("no ingest yet — run `make ingest`")
        return 0

    data = json.loads(DOC_STATUS.read_text(encoding="utf-8"))
    counts = Counter(v.get("status", "?") for v in data.values())
    total = len(data)
    done = counts.get("processed", 0)
    failed = counts.get("failed", 0)
    in_progress = counts.get("processing", 0) + counts.get("pending", 0)

    elapsed = None
    if START_FILE.exists():
        try:
            t0 = time.mktime(
                time.strptime(START_FILE.read_text().strip(), "%Y-%m-%d %H:%M:%S")
            )
            elapsed = time.time() - t0
        except Exception:
            pass

    pct = (done + failed) / total * 100 if total else 0
    print(f"docs: {total}  ({pct:.0f}% complete)")
    for status in ("processed", "processing", "pending", "failed"):
        if counts.get(status):
            print(f"  {status:11} {counts[status]}")
    if elapsed is not None:
        print(f"elapsed: {_fmt_seconds(elapsed)}")
        if done > 0:
            rate = done / elapsed
            remaining = in_progress / rate if rate > 0 else 0
            print(f"rate:    {rate*60:.2f} docs/min")
            print(f"ETA:     {_fmt_seconds(remaining)} for the remaining {in_progress}")

    if LOG_PATH.exists():
        try:
            tail = LOG_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()[-3:]
            print("\nlast log lines:")
            for line in tail:
                print(f"  {line[:140]}")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
